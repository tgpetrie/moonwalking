"""Offline worker lifecycle checks. All prices are synthetic, never market evidence."""
import copy
import datetime as dt
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
import urllib.error
import urllib.parse

sys.path.insert(0, str(Path(__file__).resolve().parent))
import chart_worker as worker


def timestamp(day):
    return int(dt.datetime.fromisoformat(day).replace(tzinfo=dt.timezone.utc).timestamp())


NOW = timestamp('2026-01-20') + 43200
FIRST = timestamp('2026-01-10')


def rows(count=10):
    # Coinbase tuple: UTC start, low, high, open, close, volume.
    return [[FIRST + n * worker.DAY, 1, 3, 2, 2.1, 100] for n in range(count)]


class FakeClient:
    """No network: serve explicit synthetic daily rows and public identity."""
    def __init__(self, candles=None, metadata=None, error=None):
        self.rows = rows() if candles is None else candles
        self.metadata = metadata or {'id': 'AMP-USD', 'base_currency': 'AMP', 'quote_currency': 'USD'}
        self.error = error
        self.requests = []

    def get(self, path):
        self.requests.append({'url': path})
        if self.error:
            raise self.error
        if '/candles?' not in path:
            return self.metadata
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(path).query)
        start = dt.datetime.fromisoformat(query['start'][0].replace('Z', '+00:00')).timestamp()
        end = dt.datetime.fromisoformat(query['end'][0].replace('Z', '+00:00')).timestamp()
        return copy.deepcopy([r for r in self.rows if start <= r[0] <= end])


def packet(history):
    # Deliberately fixed weekly evidence: a revised native daily candle need not
    # alter completed weekly structure. Identity and cutoff still follow input.
    return {'schema_version': 'moonwalking.chart-evidence/v1',
            'instrument': copy.deepcopy(history['instrument']),
            'captured_at': history['captured_at'],
            'reference_close': {'price': 2.1, 'time': FIRST},
            'evidence': {'pivots': [], 'recent_sequence': [], 'macro_anchors': [],
                         'macro_levels': [], 'macro_unavailable_reason': 'Synthetic test fixture'}}


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = worker.Store(Path(self.temp.name) / 'owned', 'AMP-USD')

    def tearDown(self):
        self.store.db.close()
        self.temp.cleanup()

    def run_worker(self, client=None, now=NOW):
        return worker.run_once(self.store, client=client or FakeClient(), clock=lambda: now, producer=packet)

    def test_initial_refresh_persists_history_evidence_and_status(self):
        status = self.run_worker()
        self.assertEqual(status['state'], 'ok')
        self.assertTrue(status['changed'])
        self.assertTrue(status['analysis_changed'])
        self.assertEqual(status['run_count'], 1)
        _, history, evidence = self.store.read()
        self.assertEqual(len(history['candles']), 10)
        self.assertEqual(history['instrument'], evidence['instrument'])
        exported = json.loads((self.store.path / 'history.json').read_bytes())
        self.assertEqual(exported, history)
        self.assertEqual(json.loads((self.store.path / 'status.json').read_bytes())['history_sha256'], worker.digest(history))

    def test_unchanged_repeat_records_check_without_claiming_new_structure(self):
        self.run_worker()
        status = self.run_worker(now=NOW + 3600)
        self.assertEqual(status['state'], 'ok')
        self.assertFalse(status['changed'])
        self.assertFalse(status['analysis_changed'])
        self.assertEqual(status['run_count'], 2)
        self.assertIn('Completed weekly structure unchanged.', status['change_summary'])

    def test_daily_revision_can_leave_weekly_evidence_unchanged(self):
        self.run_worker()
        revised = rows()
        revised[-1][4] = 2.2
        status = self.run_worker(FakeClient(revised), NOW + 3600)
        self.assertTrue(status['changed'])
        self.assertFalse(status['analysis_changed'])
        self.assertIn('revised 1', status['change_summary'][0])
        self.assertEqual(self.store.read()[1]['candles'][-1]['close'], 2.2)

    def test_failure_retains_last_good_data_and_success_timestamp(self):
        success = self.run_worker()
        _, before_history, before_packet = self.store.read()
        status = self.run_worker(FakeClient(error=RuntimeError('synthetic provider failure')), NOW + 3600)
        self.assertEqual(status['state'], 'error')
        self.assertEqual(status['last_success_at'], success['last_success_at'])
        self.assertIn('synthetic provider failure', status['last_error'])
        self.assertEqual(self.store.read()[1:], (before_history, before_packet))

    def test_active_duplicate_lease_skips_without_provider_call(self):
        token = self.store.claim(NOW)
        client = FakeClient()
        result = self.run_worker(client, NOW + 1)
        self.assertIn('skipped', result)
        self.assertEqual(client.requests, [])
        self.assertEqual(self.store.db.execute('SELECT token FROM lease').fetchone()[0], token)

    def test_expired_lease_recovered_and_old_owner_is_fenced(self):
        old_token = self.store.claim(NOW)
        new_now = NOW + worker.LEASE + 1
        new_token = self.store.claim(new_now)
        self.assertNotEqual(old_token, new_token)
        with self.assertRaisesRegex(RuntimeError, 'superseded'):
            self.store.finish(old_token, new_now, {'state': 'ok', 'change_summary': []})
        self.assertEqual(self.store.db.execute('SELECT token FROM lease').fetchone()[0], new_token)
        self.store.finish(new_token, new_now, {'state': 'ok', 'change_summary': ['new owner']})
        self.assertEqual(self.store.read()[0]['change_summary'], ['new owner'])

    def test_empty_or_invalid_provider_retains_last_good(self):
        self.run_worker()
        before = self.store.read()[1:]
        malformed = rows()
        malformed[-1][1] = -1
        conflicting = rows() + [[rows()[-1][0], 1, 3, 2, 2.2, 100]]
        for bad in ([], malformed, conflicting):
            with self.subTest(payload=bad):
                status = self.run_worker(FakeClient(bad), NOW + 3600)
                self.assertEqual(status['state'], 'error')
                self.assertEqual(self.store.read()[1:], before)

    def test_current_utc_day_excluded_even_if_provider_returns_boundary(self):
        status = self.run_worker(FakeClient(rows(11)))
        self.assertEqual(status['state'], 'ok')
        history = self.store.read()[1]
        self.assertEqual(history['captured_at'], timestamp('2026-01-20'))
        self.assertEqual(history['candles'][-1]['start'], timestamp('2026-01-19'))
        self.assertTrue(all(c['complete'] and c['end'] <= history['captured_at'] for c in history['candles']))

    def test_missing_refreshed_row_is_removed_without_interpolation(self):
        self.run_worker()
        changed = rows()
        del changed[6]
        changed[-1][4] = 2.2
        status = self.run_worker(FakeClient(changed), NOW + 3600)
        history = self.store.read()[1]
        self.assertEqual(status['state'], 'ok')
        self.assertEqual(len(history['candles']), 9)
        self.assertNotIn(FIRST + 6 * worker.DAY, [c['start'] for c in history['candles']])
        self.assertEqual(history['source']['internal_missing_daily_intervals'], 1)
        self.assertIn('removed 1', status['change_summary'][0])
        self.assertEqual(history['candles'][-1]['close'], 2.2)

    def test_sqlite_repairs_partial_export_after_commit(self):
        self.run_worker()
        changed = rows()
        changed[-1][4] = 2.2
        real_atomic = worker.atomic
        failed = False

        def partial_export(path, data):
            nonlocal failed
            if path.name == 'evidence.json' and not failed:
                # Only fail after the new history has been committed/exported.
                current = json.loads((self.store.path / 'history.json').read_bytes())
                if current['candles'][-1]['close'] == 2.2:
                    failed = True
                    raise OSError('synthetic interrupted export')
            return real_atomic(path, data)

        with mock.patch.object(worker, 'atomic', side_effect=partial_export):
            with self.assertRaisesRegex(OSError, 'interrupted export'):
                self.run_worker(FakeClient(changed), NOW + 3600)
        committed = self.store.read()
        self.assertEqual(committed[0]['state'], 'ok')
        self.assertEqual(committed[1]['candles'][-1]['close'], 2.2)
        self.store.export()
        for name, expected in [('history.json', committed[1]), ('evidence.json', committed[2])]:
            self.assertEqual(json.loads((self.store.path / name).read_bytes()), expected)
        status = json.loads((self.store.path / 'status.json').read_bytes())
        self.assertEqual(status['generation_id'], committed[0]['generation_id'])
        self.assertEqual(status['history_sha256'], worker.digest(committed[1]))

    def test_mismatched_provider_or_cache_product_rejected(self):
        self.run_worker()
        before = self.store.read()[1:]
        bad = {'id': 'AMP-USD', 'base_currency': 'BTC', 'quote_currency': 'USD'}
        status = self.run_worker(FakeClient(metadata=bad), NOW + 3600)
        self.assertEqual(status['state'], 'error')
        self.assertEqual(self.store.read()[1:], before)
        foreign = copy.deepcopy(before[0])
        foreign['instrument']['product_id'] = 'BTC-USD'
        with self.assertRaisesRegex(ValueError, 'different product'):
            worker.refresh('AMP-USD', foreign, FakeClient(), NOW)

    def test_owned_directory_cannot_be_adopted_by_other_product(self):
        with self.assertRaisesRegex(ValueError, 'different worker/product'):
            worker.Store(self.store.path, 'BTC-USD')
        foreign = Path(self.temp.name) / 'foreign'
        foreign.mkdir()
        (foreign / 'keep.txt').write_text('owner data')
        with self.assertRaisesRegex(ValueError, 'nonempty unowned'):
            worker.Store(foreign, 'AMP-USD')
        self.assertEqual((foreign / 'keep.txt').read_text(), 'owner data')


class FakeClock:
    def __init__(self):
        self.now = 0
        self.sleeps = []

    def clock(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


class PublicClientTests(unittest.TestCase):
    def test_retry_and_successive_requests_respect_completion_spacing(self):
        clock = FakeClock()
        starts = []
        requests = []

        def opener(request, timeout):
            starts.append(clock.now)
            requests.append(request)
            clock.now += .25  # Synthetic request duration.
            if len(starts) == 1:
                raise urllib.error.HTTPError(request.full_url, 429, 'slow', {'Retry-After': '3'}, None)
            return io.BytesIO(b'{"id":"AMP-USD"}')

        client = worker.PublicClient(opener=opener, sleep=clock.sleep, clock=clock.clock)
        self.assertEqual(client.get('/products/AMP-USD')['id'], 'AMP-USD')
        client.get('/products/AMP-USD')
        self.assertGreaterEqual(starts[1] - starts[0], 3.25)
        self.assertGreaterEqual(starts[2] - starts[1], 1.30 - 1e-8)
        self.assertTrue(all(request.full_url.startswith(worker.BASE + '/products/') for request in requests))
        self.assertTrue(all(request.get_header('Authorization') is None for request in requests))

    def test_long_retry_after_stops_without_early_retry(self):
        clock = FakeClock()
        calls = []

        def opener(request, timeout):
            calls.append(request)
            raise urllib.error.HTTPError(request.full_url, 429, 'slow', {'Retry-After': '121'}, None)

        client = worker.PublicClient(opener=opener, sleep=clock.sleep, clock=clock.clock)
        with self.assertRaisesRegex(RuntimeError, 'over two minutes'):
            client.get('/products/AMP-USD')
        self.assertEqual(len(calls), 1)
        self.assertEqual(clock.sleeps, [])

    def test_private_paths_rejected_before_request(self):
        opener = mock.Mock()
        client = worker.PublicClient(opener=opener)
        with self.assertRaisesRegex(ValueError, 'Only public product'):
            client.get('/accounts')
        opener.assert_not_called()


class EvidenceBoundaryTests(unittest.TestCase):
    def test_node_timeout_nonzero_hash_and_cutoff_mismatch_are_rejected(self):
        history = {'instrument': {'product_id': 'AMP-USD'}, 'captured_at': NOW}
        valid = {'schema_version': 'moonwalking.chart-evidence/v1', 'instrument': history['instrument'],
                 'source': {'sha256': worker.digest(history)},
                 'settings': {'effective_cutoff_exclusive_utc': worker.iso(NOW)}}
        output = lambda value, code=0: mock.Mock(returncode=code, stdout=json.dumps(value).encode(), stderr=b'synthetic failure')
        with mock.patch.object(worker.subprocess, 'run', side_effect=worker.subprocess.TimeoutExpired('node', 90)):
            with self.assertRaises(worker.subprocess.TimeoutExpired):
                worker.evidence(history)
        with mock.patch.object(worker.subprocess, 'run', return_value=output(valid, 1)):
            with self.assertRaisesRegex(ValueError, 'validation failed'):
                worker.evidence(history)
        wrong_hash = copy.deepcopy(valid)
        wrong_hash['source']['sha256'] = '0' * 64
        with mock.patch.object(worker.subprocess, 'run', return_value=output(wrong_hash)):
            with self.assertRaisesRegex(ValueError, 'input hash'):
                worker.evidence(history)
        wrong_cutoff = copy.deepcopy(valid)
        wrong_cutoff['settings']['effective_cutoff_exclusive_utc'] = worker.iso(NOW - worker.DAY)
        with mock.patch.object(worker.subprocess, 'run', return_value=output(wrong_cutoff)):
            with self.assertRaisesRegex(ValueError, 'cutoff mismatch'):
                worker.evidence(history)
        with mock.patch.object(worker.subprocess, 'run', return_value=output(valid)):
            self.assertEqual(worker.evidence(history), valid)

    def test_engine_change_regenerates_without_claiming_changed_prices(self):
        with tempfile.TemporaryDirectory() as directory:
            store = worker.Store(Path(directory) / 'own', 'AMP-USD')
            try:
                worker.run_once(store, client=FakeClient(), clock=lambda: NOW, producer=packet)
                produce = mock.Mock(side_effect=packet)
                with mock.patch.object(worker, 'engine_fingerprint', return_value='synthetic-new-engine'):
                    status = worker.run_once(store, client=FakeClient(), clock=lambda: NOW + 3600, producer=produce)
                produce.assert_called_once()
                self.assertFalse(status['changed'])
                self.assertTrue(status['analysis_changed'])
                self.assertIn('Calculation engine version changed; evidence regenerated.', status['change_summary'])
                self.assertIn('Completed weekly structure unchanged.', status['change_summary'])
            finally:
                store.db.close()

    def test_midnight_settlement_margin_withholds_just_closed_day(self):
        before_margin = timestamp('2026-01-20') + 120
        history = worker.refresh('AMP-USD', None, FakeClient(), before_margin)
        self.assertEqual(history['captured_at'], timestamp('2026-01-19'))
        self.assertEqual(history['candles'][-1]['start'], timestamp('2026-01-18'))


if __name__ == '__main__':
    unittest.main()
