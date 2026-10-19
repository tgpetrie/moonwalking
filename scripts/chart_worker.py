"""Single-product local chart refresh worker. Unsigned public reads; owned cache only."""
import argparse
import datetime as dt
import email.utils
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

from snapshot_coinbase_daily import DAY, normalize
from chart_narration import narrate

ROOT = Path(__file__).resolve().parents[1]
BASE = 'https://api.exchange.coinbase.com'
SCHEMA = 'moonwalking.chart-worker-status/v1'
LEASE = 1800
PERIOD = 3600


def iso(t):
    return dt.datetime.fromtimestamp(t, dt.timezone.utc).isoformat().replace('+00:00', 'Z')


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def engine_fingerprint():
    paths = ['scripts/chart_evidence_packet.mjs', 'frontend/src/utils/macroChart.js',
             'frontend/src/utils/chartStructure.js', 'frontend/src/utils/chartTiming.js']
    return digest({p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in paths})


def atomic(path, data):
    tmp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with tmp.open('xb') as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        for attempt in range(4):
            try:
                os.replace(tmp, path)
                break
            except PermissionError:
                if attempt == 3:
                    raise
                time.sleep(0.05 * 2 ** attempt)
    finally:
        tmp.unlink(missing_ok=True)


class PublicClient:
    def __init__(self, opener=urllib.request.urlopen, sleep=time.sleep, clock=time.monotonic):
        self.opener, self.sleep, self.clock = opener, sleep, clock
        self.last = None
        self.requests = []

    def get(self, path):
        if not path.startswith('/products/'):
            raise ValueError('Only public product reads are allowed')
        for attempt in range(3):
            if self.last is not None:
                self.sleep(max(0, 1.05 - (self.clock() - self.last)))
            try:
                request = urllib.request.Request(BASE + path, headers={'Accept': 'application/json', 'User-Agent': 'moonwalking-local-chart-worker/1.0'})
                with self.opener(request, timeout=20) as response:
                    body = response.read(4 * 1024 * 1024 + 1)
                if len(body) > 4 * 1024 * 1024:
                    raise ValueError('Public response exceeds bounded size')
                value = json.loads(body)
                self.requests.append({'url': BASE + path, 'fetched_at': iso(time.time()), 'sha256': hashlib.sha256(body).hexdigest()})
                return value
            except urllib.error.HTTPError as error:
                if error.code not in (429, 503) or attempt == 2:
                    raise RuntimeError(f'Public provider HTTP {error.code}') from None
                retry = error.headers.get('Retry-After', '0')
                try:
                    delay = float(retry)
                except ValueError:
                    delay = max(0, email.utils.parsedate_to_datetime(retry).timestamp() - time.time())
                if delay > 120:
                    raise RuntimeError('Provider requested a pause over two minutes; retry at next scheduled check')
                self.sleep(max(2 ** (attempt + 1), delay))
            finally:
                self.last = self.clock()
        raise RuntimeError('Public request failed')


def refresh(product, previous, client, now):
    # Five minutes of settlement margin around UTC midnight; never include an open day.
    cutoff = int(now - 300) // DAY * DAY
    metadata = client.get(f'/products/{product}')
    base, quote = product.split('-')
    if metadata.get('id') != product or metadata.get('base_currency') != base or metadata.get('quote_currency') != quote:
        raise ValueError('Public product metadata does not match the requested coin/units')
    if previous and previous['instrument']['product_id'] != product:
        raise ValueError('Existing cache belongs to a different product')
    start = max(int(dt.datetime(2010, 1, 1, tzinfo=dt.timezone.utc).timestamp()),
                previous['candles'][-1]['start'] - 6 * DAY if previous else 0)
    if start >= cutoff:
        raise ValueError('Clock is behind the cached history; refusing a backward refresh')
    if (cutoff - start) // (299 * DAY) > 24:
        raise ValueError('Requested history exceeds bounded pilot coverage')
    rows = []
    cursor = start
    windows = []
    while cursor < cutoff:
        stop = min(cursor + 299 * DAY, cutoff)
        query = urllib.parse.urlencode({'granularity': DAY, 'start': iso(cursor), 'end': iso(stop)})
        batch = client.get(f'/products/{product}/candles?{query}')
        if not isinstance(batch, list):
            raise ValueError('Public candles must be an array')
        # Keep each half-open window so boundary rows cannot conflict across requests.
        rows.extend(r for r in batch if isinstance(r, list) and r and cursor <= r[0] < stop)
        # Validate all rows, including out-of-window malformed payloads.
        if batch:
            try:
                normalize(batch, cursor, stop)
            except ValueError as e:
                if str(e) != 'No candles within the requested interval':
                    raise
        windows.append({'start': iso(cursor), 'end_exclusive': iso(stop), 'returned_rows': len(batch)})
        cursor = stop
    fresh = normalize(rows, start, cutoff)
    old = previous['candles'] if previous else []
    # The refreshed interval is authoritative, including newly observed missing buckets.
    candles = [c for c in old if c['start'] < start] + fresh
    gaps = (candles[-1]['start'] - candles[0]['start']) // DAY + 1 - len(candles)
    return {'schema_version': 'bhabit.chart-history.v1',
            'instrument': {'product_id': product, 'symbol': base, 'venue': 'coinbase-exchange', 'quote_currency': quote},
            'interval_seconds': DAY, 'captured_at': cutoff, 'candles': candles,
            'source': {'contract': 'moonwalking-local-worker/v1', 'stitched': False, 'fetched_at': iso(now),
                       'seed_source_sha256': digest(previous) if previous and not previous.get('source', {}).get('seed_source_sha256') else (previous or {}).get('source', {}).get('seed_source_sha256'),
                       'windows': windows, 'requests': client.requests,
                       'internal_missing_daily_intervals': gaps,
                       'identity_scope': 'Coinbase USD product; chain lineage not independently established.',
                       'coverage_scope': 'Available venue history. No gap filling, no all-time claim, no independent hourly validation.'}}


def evidence(history, node=None):
    script = "import {buildEvidencePacket} from './scripts/chart_evidence_packet.mjs'; let b=''; for await (const c of process.stdin) b+=c; console.log(JSON.stringify(buildEvidencePacket(Buffer.from(b))));"
    result = subprocess.run([node or shutil.which('node') or 'node', '--input-type=module', '-e', script],
                            cwd=ROOT, input=encoded(history), capture_output=True, timeout=90, check=False)
    if result.returncode:
        raise ValueError('History/evidence validation failed: ' + result.stderr.decode(errors='replace')[:500])
    packet = json.loads(result.stdout)
    if packet.get('schema_version') != 'moonwalking.chart-evidence/v1' or packet['instrument'] != history['instrument']:
        raise ValueError('Evidence output identity/schema mismatch')
    if packet.get('source', {}).get('sha256') != hashlib.sha256(encoded(history)).hexdigest():
        raise ValueError('Evidence output input hash mismatch')
    if dt.datetime.fromisoformat(packet['settings']['effective_cutoff_exclusive_utc'].replace('Z', '+00:00')).timestamp() != history['captured_at']:
        raise ValueError('Evidence output cutoff mismatch')
    return packet


def analysis_fingerprint(packet):
    return digest({k: packet.get(k) for k in ('reference_close',)} | {
        k: packet['evidence'][k] for k in ('pivots', 'recent_sequence', 'macro_anchors', 'macro_levels', 'macro_unavailable_reason')})


class Store:
    def __init__(self, directory, product):
        self.path = Path(directory).resolve()
        self.path.mkdir(parents=True, exist_ok=True)
        marker = self.path / 'owner.json'
        if marker.exists():
            if json.loads(marker.read_text()) != {'schema': SCHEMA, 'product_id': product}:
                raise ValueError('State directory is owned by a different worker/product')
        else:
            if any(self.path.iterdir()):
                raise ValueError('Refusing to adopt a nonempty unowned state directory')
            with marker.open('x') as f:
                json.dump({'schema': SCHEMA, 'product_id': product}, f)
        self.db = sqlite3.connect(self.path / 'jobs.sqlite3', timeout=10)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.executescript('''CREATE TABLE IF NOT EXISTS state(id INTEGER PRIMARY KEY CHECK(id=1), status TEXT, history TEXT, evidence TEXT);
        INSERT OR IGNORE INTO state(id,status) VALUES(1,'{}');
        CREATE TABLE IF NOT EXISTS lease(id INTEGER PRIMARY KEY CHECK(id=1), token TEXT, expires REAL);
        CREATE TABLE IF NOT EXISTS runs(id INTEGER PRIMARY KEY, attempted REAL, result TEXT, summary TEXT);''')
        self.db.commit()
        self.product = product

    def read(self):
        row = self.db.execute('SELECT status,history,evidence FROM state WHERE id=1').fetchone()
        return tuple(json.loads(x) if x else None for x in row)

    def claim(self, now):
        token = uuid.uuid4().hex
        self.db.execute('BEGIN IMMEDIATE')
        lease = self.db.execute('SELECT token,expires FROM lease WHERE id=1').fetchone()
        if lease and lease[1] > now:
            self.db.rollback()
            return None
        status, _, _ = self.read()
        defaults = {'last_success_at': None, 'candle_through_utc': None, 'reference_close': None,
                    'changed': None, 'analysis_changed': None, 'change_summary': [], 'run_count': 0}
        status = defaults | status
        status.update({'schema_version': SCHEMA, 'product_id': self.product, 'state': 'running',
                       'last_attempt_at': iso(now), 'next_run_at': iso(now + PERIOD), 'last_error': None})
        self.db.execute('INSERT OR REPLACE INTO lease VALUES(1,?,?)', (token, now + LEASE))
        self.db.execute('UPDATE state SET status=? WHERE id=1', (json.dumps(status),))
        self.db.commit()
        return token

    def finish(self, token, now, status, history=None, packet=None):
        self.db.execute('BEGIN IMMEDIATE')
        lease = self.db.execute('SELECT token,expires FROM lease WHERE id=1').fetchone()
        if not lease or lease[0] != token or lease[1] <= now:
            self.db.rollback()
            raise RuntimeError('Worker lease expired or was superseded; result discarded')
        if history is None:
            self.db.execute('UPDATE state SET status=? WHERE id=1', (json.dumps(status),))
        else:
            self.db.execute('UPDATE state SET status=?,history=?,evidence=? WHERE id=1',
                            (json.dumps(status), json.dumps(history), json.dumps(packet)))
        self.db.execute('INSERT INTO runs(attempted,result,summary) VALUES(?,?,?)', (now, status['state'], json.dumps(status['change_summary'])))
        self.db.execute('DELETE FROM runs WHERE id NOT IN (SELECT id FROM runs ORDER BY id DESC LIMIT 100)')
        self.db.execute('DELETE FROM lease WHERE id=1 AND token=?', (token,))
        self.db.commit()

    def export(self):
        # Serialize publication with job commits/claims, so an old exporter cannot
        # overwrite a newer generation after releasing its lease.
        self.db.execute('BEGIN IMMEDIATE')
        try:
            status, history, packet = self.read()
            if history:
                data = encoded(history)
                status['history_sha256'] = hashlib.sha256(data).hexdigest()
                atomic(self.path / 'history.json', data)
                atomic(self.path / 'evidence.json', encoded(packet))
            atomic(self.path / 'status.json', encoded(status))
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise


def run_once(store, *, seed=None, client=None, clock=time.time, producer=evidence, node=None, narrator=narrate):
    now = clock()
    token = store.claim(now)
    if token is None:
        return {'skipped': 'another worker owns the active lease'}
    old_status, previous, old_packet = store.read()
    store.export()  # Also repairs exports from a previously committed run after a crash.
    try:
        if previous is None and seed:
            previous = json.loads(Path(seed).read_bytes())
            producer(previous)  # Validate seed before it can influence a refresh.
        updated = refresh(store.product, previous, client or PublicClient(), now)
        if previous and updated['captured_at'] < previous['captured_at']:
            raise ValueError('Clock moved backwards')
        # Always validate parsing. Only regenerate saved evidence when numerical content/cutoff changes.
        changed = previous is None or digest(previous['candles']) != digest(updated['candles'])
        engine_hash = engine_fingerprint()
        engine_changed = old_status.get('engine_sha256') != engine_hash
        if not changed and not engine_changed and old_packet and updated['captured_at'] == previous['captured_at']:
            # Retain the exact numerical snapshot/hash; status records this new check separately.
            updated, packet = previous, old_packet
        else:
            packet = producer(updated)
        structural_changed = old_packet is None or analysis_fingerprint(packet) != analysis_fingerprint(old_packet)
        numerical_changed = structural_changed or engine_changed
        old_by_time = {c['start']: c for c in previous['candles']} if previous else {}
        added = sum(c['start'] not in old_by_time for c in updated['candles'])
        revised = sum(c['start'] in old_by_time and c != old_by_time[c['start']] for c in updated['candles'])
        removed = len(set(old_by_time) - {c['start'] for c in updated['candles']})
        summaries = ([f'Added {added} completed daily candles; revised {revised}; removed {removed} in the refreshed interval.'] if changed else ['No completed daily prices changed in the refreshed interval.'])
        summaries.append('First worker analysis established.' if old_packet is None else 'Completed weekly evidence or reference close changed.' if structural_changed else 'Completed weekly structure unchanged.')
        if engine_changed and old_packet:
            summaries.append('Calculation engine version changed; evidence regenerated.')
        if old_packet:
            old_ids = {p['id'] for p in old_packet['evidence'].get('pivots', [])}
            for p in packet['evidence'].get('pivots', []):
                if p['id'] not in old_ids:
                    summaries.append(f"New confirmed {p['type']}: extreme {p['extreme_date_utc']}, candle {p['bucket_start_utc'][:10]}, confirmed {p['confirmed_at_utc']}.")
        missing = updated['source']['internal_missing_daily_intervals']
        if missing:
            summaries.append(f'{missing} missing daily intervals inside available history; none filled.')
        last_day = updated['candles'][-1]['start']
        if last_day + DAY < updated['captured_at']:
            summaries.append('Provider history trails the latest closed UTC day; check candle coverage before interpreting freshness.')
        narration_detail = narrator(packet, old_status.get('narration_detail'))
        finished = clock()
        status = {'schema_version': SCHEMA, 'product_id': store.product, 'state': 'ok',
                  'generation_id': str(uuid.uuid4()), 'last_attempt_at': iso(now), 'last_success_at': iso(finished),
                  'next_run_at': iso(now + PERIOD), 'last_error': None, 'candle_through_utc': iso(last_day)[:10],
                  'reference_close': packet['reference_close'], 'changed': changed, 'analysis_changed': numerical_changed,
                  'change_summary': summaries, 'run_count': old_status.get('run_count', 0) + 1,
                  'narration': narration_detail['state'], 'narration_detail': narration_detail,
                  'history_path': '/.runtime/chart-worker/history.json'}
        status['engine_sha256'] = engine_hash
        status['completed_daily_sha256'] = digest(updated['candles'])
        status['weekly_evidence_sha256'] = analysis_fingerprint(packet)
        status['revision_examples'] = [{'start': c['start'], 'old': old_by_time[c['start']], 'new': c}
                                       for c in updated['candles'] if c['start'] in old_by_time and c != old_by_time[c['start']]][:10]
        store.finish(token, finished, status, updated, packet)
    except Exception as error:
        finished = clock()
        old_status.update({'state': 'error', 'last_error': str(error)[:700], 'last_attempt_at': iso(now),
                           'next_run_at': iso(now + PERIOD), 'run_count': old_status.get('run_count', 0) + 1,
                           'change_summary': ['Refresh failed. Last successful history and evidence kept.'],
                           'changed': None, 'analysis_changed': None})
        store.finish(token, finished, old_status)
    store.export()
    return store.read()[0]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--product', default='AMP-USD')
    p.add_argument('--state-dir', type=Path, default=ROOT / 'frontend/.runtime/chart-worker')
    p.add_argument('--seed', type=Path)
    p.add_argument('--loop', action='store_true', help='Hourly foreground runner; scheduled task normally uses one run')
    args = p.parse_args()
    if not re.fullmatch(r'[A-Z0-9]{1,20}-USD', args.product):
        p.error('Pilot accepts an explicit Coinbase BASE-USD product')
    store = Store(args.state_dir, args.product)
    while True:
        result = run_once(store, seed=args.seed)
        print(json.dumps(result), flush=True)
        if not args.loop:
            return 1 if result.get('state') == 'error' else 0
        time.sleep(PERIOD)


if __name__ == '__main__':
    sys.exit(main())
