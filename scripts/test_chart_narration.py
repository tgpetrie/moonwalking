"""Offline narration boundary tests; all chart values below are synthetic."""
import copy
import io
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import chart_narration as narration


def synthetic_packet():
    """A minimal evidence-contract fixture, not real prices or a prediction."""
    high = {'id': 'pivot-high', 'type': 'high', 'price': 20,
            'extreme_date_utc': '2024-05-02', 'confirmed_at_utc': '2024-05-20T00:00:00Z'}
    low = {'id': 'pivot-low', 'type': 'low', 'price': 2,
           'extreme_date_utc': '2025-05-02', 'confirmed_at_utc': '2025-05-19T00:00:00Z'}
    return {'schema_version': 'moonwalking.chart-evidence/v1',
            'instrument': {'product_id': 'AMP-USD', 'symbol': 'AMP',
                           'venue': 'coinbase-exchange', 'quote_currency': 'USD'},
            'reference_close': {'interval': 'weekly', 'price': 3,
                                'period_end_exclusive_utc': '2026-10-19T00:00:00Z'},
            'coverage': {'internal_missing_daily_intervals': 2},
            'source': {'contract': 'synthetic-unit-test/v1', 'stitched': False},
            'blocked_claims': ['probability', 'price-arrival date', 'trading instruction'],
            'evidence': {'recent_references': [copy.deepcopy(low),
                                             {'id': 'recent-high', 'type': 'high', 'price': 6,
                                              'extreme_date_utc': '2026-09-01',
                                              'confirmed_at_utc': '2026-09-21T00:00:00Z'}],
                         'macro_anchors': [high, low],
                         'macro_levels': [{'id': f'macro-{ratio:g}', 'ratio': ratio,
                                           'price': 2 + ratio * 18,
                                           'anchor_ids': ['pivot-high', 'pivot-low']}
                                          for ratio in (.5, .618, .786, 1, 1.618)],
                         'macro_unavailable_reason': None}}


class CatalogPlanTests(unittest.TestCase):
    def setUp(self):
        self.packet = synthetic_packet()
        self.facts = narration.catalog(self.packet)
        self.plan = narration.default_plan(self.facts)

    def assert_rejected(self, plan):
        with self.assertRaises(ValueError):
            narration.validate_plan(plan, self.facts)

    def test_catalog_computes_dated_prices_and_coverage_from_evidence(self):
        self.assertIn('$3 through 2026-10-18 UTC', self.facts['reference']['text'])
        self.assertIn('$11, +266.7%', self.facts['macro-0.5']['text'])
        self.assertIn('2 missing daily intervals', self.facts['coverage']['text'])
        self.assertIn('confirmed high $20 on 2024-05-02', self.facts['basis']['text'])
        self.assertIn('later low $2 on 2025-05-02', self.facts['basis']['text'])

    def test_valid_plan_renders_only_catalog_text_and_exact_source_union(self):
        self.assertEqual(narration.validate_plan(self.plan, self.facts), self.plan)
        rendered = narration.render(self.plan, self.facts)
        for paragraph, output in zip(self.plan['paragraphs'], rendered):
            ids = paragraph['fact_ids']
            self.assertEqual(output['text'], ' '.join(self.facts[i]['text'] for i in ids))
            self.assertEqual(output['sources'], sorted({s for i in ids for s in self.facts[i]['sources']}))
            self.assertEqual(output['fact_ids'], ids)

    def test_unknown_ids_are_rejected(self):
        self.plan['paragraphs'][1]['fact_ids'].append('moon-shot')
        self.assert_rejected(self.plan)

    def test_additional_fields_and_raw_prose_are_rejected(self):
        cases = ['Price will double.', {'paragraphs': self.plan['paragraphs'], 'prediction': '$100'}]
        paragraph_extra = copy.deepcopy(self.plan)
        paragraph_extra['paragraphs'][1]['text'] = 'Guaranteed recovery next month.'
        cases.append(paragraph_extra)
        price_extra = copy.deepcopy(self.plan)
        price_extra['paragraphs'][1]['target_price'] = 100
        cases.append(price_extra)
        for plan in cases:
            with self.subTest(plan=plan):
                self.assert_rejected(plan)

    def test_repeated_ids_or_wrong_topics_are_rejected(self):
        repeated = copy.deepcopy(self.plan)
        repeated['paragraphs'][1]['fact_ids'].append('macro-0.5')
        wrong_topic = copy.deepcopy(self.plan)
        wrong_topic['paragraphs'][1]['fact_ids'].append('reference')
        wrong_order = copy.deepcopy(self.plan)
        wrong_order['paragraphs'][0], wrong_order['paragraphs'][1] = wrong_order['paragraphs'][1], wrong_order['paragraphs'][0]
        for plan in (repeated, wrong_topic, wrong_order):
            with self.subTest(plan=plan):
                self.assert_rejected(plan)

    def test_required_context_cannot_be_omitted(self):
        for index, fact_id in ((0, 'reference'), (0, 'recent-low'), (1, 'basis'), (2, 'coverage'), (2, 'limits')):
            plan = copy.deepcopy(self.plan)
            plan['paragraphs'][index]['fact_ids'].remove(fact_id)
            with self.subTest(missing=fact_id):
                self.assert_rejected(plan)

    def test_extension_requires_selected_high_and_basis(self):
        self.plan['paragraphs'][1]['fact_ids'] = ['basis', 'macro-1.618']
        self.assert_rejected(self.plan)
        self.plan['paragraphs'][1]['fact_ids'].append('macro-1')
        self.assertEqual(narration.validate_plan(self.plan, self.facts), self.plan)

    def test_basis_alone_does_not_replace_price_references(self):
        self.plan['paragraphs'][1]['fact_ids'] = ['basis']
        self.assert_rejected(self.plan)

    def test_absent_range_and_absent_completed_candle_have_honest_plans(self):
        for no_close in (False, True):
            packet = synthetic_packet()
            packet['evidence']['macro_levels'] = []
            packet['evidence']['macro_unavailable_reason'] = 'Insufficient confirmed pivots'
            if no_close:
                packet['reference_close'] = None
            facts = narration.catalog(packet)
            self.assertNotIn('basis', facts)
            self.assertNotIn('macro-0.5', facts)
            plan = narration.default_plan(facts)
            self.assertEqual(plan['paragraphs'][1]['fact_ids'], ['unavailable'])
            narration.validate_plan(plan, facts)

    def test_wrong_evidence_schema_is_rejected(self):
        self.packet['schema_version'] = 'untrusted/v0'
        with self.assertRaisesRegex(ValueError, 'Unsupported'):
            narration.catalog(self.packet)

    def test_duplicate_json_fields_at_any_depth_are_rejected(self):
        for raw in ('{"paragraphs":[],"paragraphs":[]}',
                    '{"paragraphs":[{"topic":"position","topic":"levels"}]}'):
            with self.subTest(raw=raw):
                with self.assertRaisesRegex(ValueError, 'Duplicate'):
                    json.loads(raw, object_pairs_hook=narration.unique_object)


class NarrateTests(unittest.TestCase):
    def setUp(self):
        self.packet = synthetic_packet()
        self.now = '2026-10-19T00:01:00Z'

    @staticmethod
    def requester(facts):
        return narration.default_plan(facts), 'synthetic-model-digest'

    def test_success_has_only_verified_rendered_sentences(self):
        result = narration.narrate(self.packet, requester=self.requester, now=self.now)
        self.assertEqual(result['state'], 'local_ai')
        self.assertEqual(result['model_digest'], 'synthetic-model-digest')
        self.assertEqual(result['generated_at'], self.now)
        facts = narration.catalog(self.packet)
        self.assertEqual(result['paragraphs'], narration.render(narration.default_plan(facts), facts))

    def test_timeout_and_bad_plan_use_deterministic_fallback(self):
        for requester in (mock.Mock(side_effect=TimeoutError('synthetic timeout')),
                          mock.Mock(return_value=({'paragraphs': [], 'prediction': 'up'}, 'digest'))):
            with self.subTest(requester=requester):
                result = narration.narrate(self.packet, requester=requester, now=self.now)
                self.assertEqual(result['state'], 'fallback')
                self.assertIn('unavailable or rejected', result['reason'])
                facts = narration.catalog(self.packet)
                self.assertEqual(result['paragraphs'], narration.render(narration.default_plan(facts), facts))

    def test_unchanged_facts_reuse_validated_plan_without_model_call(self):
        previous = narration.narrate(self.packet, requester=self.requester, now=self.now)
        requester = mock.Mock(side_effect=AssertionError('model must not be called'))
        cached = narration.narrate(self.packet, previous, requester=requester, now='2026-10-19T01:01:00Z')
        requester.assert_not_called()
        self.assertEqual(cached['state'], 'cached')
        self.assertEqual(cached['paragraphs'], previous['paragraphs'])
        self.assertEqual(cached['generated_at'], self.now)

    def test_cached_raw_prose_and_sources_are_replaced_from_current_catalog(self):
        previous = narration.narrate(self.packet, requester=self.requester, now=self.now)
        expected = copy.deepcopy(previous['paragraphs'])
        previous['paragraphs'][0]['text'] = 'Guaranteed tenfold gain tomorrow'
        previous['paragraphs'][0]['sources'] = ['made-up-source']
        requester = mock.Mock()
        cached = narration.narrate(self.packet, previous, requester=requester)
        requester.assert_not_called()
        self.assertEqual(cached['paragraphs'], expected)
        self.assertNotIn('Guaranteed', json.dumps(cached['paragraphs']))

    def test_invalid_cached_ids_trigger_fresh_bounded_request(self):
        previous = narration.narrate(self.packet, requester=self.requester, now=self.now)
        previous['paragraphs'][1]['fact_ids'].append('unknown')
        requester = mock.Mock(side_effect=self.requester)
        result = narration.narrate(self.packet, previous, requester=requester)
        requester.assert_called_once()
        self.assertEqual(result['state'], 'local_ai')

    def test_changed_dated_close_invalidates_fact_cache(self):
        previous = narration.narrate(self.packet, requester=self.requester, now=self.now)
        self.packet['reference_close']['price'] = 4
        requester = mock.Mock(side_effect=self.requester)
        result = narration.narrate(self.packet, previous, requester=requester)
        requester.assert_called_once()
        self.assertNotEqual(result['evidence_sha256'], previous['evidence_sha256'])
        self.assertIn('$4 through', result['paragraphs'][0]['text'])


class NextRunNarrationTests(unittest.TestCase):
    def packet(self):
        packet = synthetic_packet()
        # Illustrative fixture: the distant macro range must never enter this catalog.
        packet['evidence']['next_run'] = {'reference': {'close': 3, 'end': 1792368000},
            'start': 1760832000, 'confirmation': 2, 'lookback_days': 365,
            'above': [{'id': 'high-a', 'label': 'R1', 'type': 'high', 'price': 3.3,
                       'extreme_date_utc': '2026-10-01', 'confirmed_at_utc': '2026-10-04T00:00:00Z'},
                      {'id': 'high-b', 'label': 'R2', 'type': 'high', 'price': 3.6,
                       'extreme_date_utc': '2026-09-01', 'confirmed_at_utc': '2026-09-04T00:00:00Z'},
                      {'id': 'high-c', 'label': 'R3', 'type': 'high', 'price': 3.9,
                       'extreme_date_utc': '2026-08-01', 'confirmed_at_utc': '2026-08-04T00:00:00Z'}],
            'below': [{'id': 'low-a', 'label': 'S1', 'type': 'low', 'price': 2.8,
                       'extreme_date_utc': '2026-10-02', 'confirmed_at_utc': '2026-10-05T00:00:00Z'}]}
        return packet

    def test_next_run_excludes_macro_math_and_requires_nearest_references(self):
        facts = narration.catalog(self.packet())
        self.assertFalse(any(id_.startswith('macro-') for id_ in facts))
        plan = narration.default_plan(facts)
        narration.validate_plan(plan, facts)
        text = ' '.join(p['text'] for p in narration.render(plan, facts))
        self.assertIn('R1: prior daily high $3.3, +10.0%', text)
        self.assertIn('S1: prior daily low $2.8', text)
        self.assertIn('not predict', text)
        plan['paragraphs'][1]['fact_ids'].remove('next-R1')
        with self.assertRaisesRegex(ValueError, 'required context'):
            narration.validate_plan(plan, facts)

    def test_cannot_skip_a_closer_level_to_select_farther_level(self):
        facts = narration.catalog(self.packet())
        plan = narration.default_plan(facts)
        plan['paragraphs'][1]['fact_ids'] = ['basis', 'next-R1', 'next-S1', 'next-R3']
        with self.assertRaisesRegex(ValueError, 'closer reference'):
            narration.validate_plan(plan, facts)

    def test_no_levels_and_missing_close_never_fall_back_to_macro(self):
        packet = self.packet()
        packet['evidence']['next_run'].update(above=[], below=[])
        facts = narration.catalog(packet)
        self.assertIn('No next-run upside reference', facts['no-upside']['text'])
        narration.validate_plan(narration.default_plan(facts), facts)
        packet['evidence']['next_run']['reference'] = None
        facts = narration.catalog(packet)
        self.assertNotIn('basis', facts)
        narration.validate_plan(narration.default_plan(facts), facts)

    def test_new_scope_invalidates_previous_macro_cache_and_uses_fallback_on_failure(self):
        old = narration.narrate(synthetic_packet(), requester=lambda facts: (narration.default_plan(facts), 'test'))
        result = narration.narrate(self.packet(), old, requester=mock.Mock(side_effect=TimeoutError()))
        self.assertEqual(result['state'], 'fallback')
        self.assertNotEqual(result['evidence_sha256'], old['evidence_sha256'])
        self.assertNotIn('macro-', json.dumps(result['paragraphs']))

    def test_request_schema_enumerates_only_context_complete_next_run_plans(self):
        facts = narration.catalog(self.packet())
        tags = {'models': [{'name': narration.MODEL, 'digest': 'synthetic'}]}
        response = {'done': True, 'model': narration.MODEL,
                    'message': {'content': json.dumps(narration.default_plan(facts))}}
        opener = FakeOpener(tags, response)
        with mock.patch.object(narration.urllib.request, 'build_opener', return_value=opener):
            narration.request_plan(facts)
        branches = json.loads(opener.calls[1][0].data)['format']['properties']['paragraphs']['items']['anyOf']
        choices = branches[1]['properties']['fact_ids']['enum']
        self.assertTrue(choices)
        for ids in choices:
            self.assertTrue({'basis', 'next-R1', 'next-S1'}.issubset(ids))
            self.assertFalse('next-R3' in ids and 'next-R2' not in ids)


class FakeOpener:
    def __init__(self, tags, response):
        self.tags, self.response = tags, response
        self.calls = []

    def open(self, request, timeout):
        self.calls.append((request, timeout))
        value = self.tags if len(self.calls) == 1 else self.response
        return io.BytesIO(value if isinstance(value, bytes) else json.dumps(value).encode())


class RequestPlanTests(unittest.TestCase):
    def setUp(self):
        self.facts = narration.catalog(synthetic_packet())
        self.tags = {'models': [{'name': narration.MODEL, 'digest': 'installed-local-digest'}]}
        self.result = {'done': True, 'done_reason': 'stop', 'model': narration.MODEL,
                       'message': {'content': json.dumps(narration.default_plan(self.facts))}}

    def request(self, tags=None, response=None):
        opener = FakeOpener(self.tags if tags is None else tags,
                            self.result if response is None else response)
        with mock.patch.object(narration.urllib.request, 'build_opener', return_value=opener):
            result = narration.request_plan(self.facts)
        return result, opener

    def test_request_is_loopback_only_nonstreaming_no_tools_or_model_pull(self):
        (plan, digest), opener = self.request()
        self.assertEqual(digest, 'installed-local-digest')
        narration.validate_plan(plan, self.facts)
        self.assertEqual(opener.calls[0][0], narration.ENDPOINT + '/api/tags')
        req = opener.calls[1][0]
        self.assertEqual(req.full_url, narration.ENDPOINT + '/api/chat')
        body = json.loads(req.data)
        self.assertFalse(body['stream'])
        self.assertFalse(body['think'])
        self.assertEqual(body['model'], narration.MODEL)
        self.assertEqual(body['options']['temperature'], 0)
        self.assertNotIn('tools', body)
        self.assertEqual(len(opener.calls), 2)

    def test_missing_exact_installed_model_stops_before_chat(self):
        opener = FakeOpener({'models': [{'name': narration.MODEL + '-cloud'}]}, self.result)
        with mock.patch.object(narration.urllib.request, 'build_opener', return_value=opener):
            with self.assertRaisesRegex(ValueError, 'not installed'):
                narration.request_plan(self.facts)
        self.assertEqual(len(opener.calls), 1)

    def test_incomplete_truncated_or_wrong_model_response_rejected(self):
        mutations = ({'done': False}, {'done_reason': 'length'}, {'model': 'another-model'})
        for mutation in mutations:
            result = self.result | mutation
            with self.subTest(mutation=mutation):
                with self.assertRaisesRegex(ValueError, 'incomplete or identifies another model'):
                    self.request(response=result)
        missing_done = copy.deepcopy(self.result)
        del missing_done['done']
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            self.request(response=missing_done)

    def test_duplicate_plan_keys_rejected_at_response_boundary(self):
        result = copy.deepcopy(self.result)
        result['message']['content'] = '{"paragraphs": [], "paragraphs": []}'
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            self.request(response=result)

    def test_oversized_model_response_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'size limit'):
            self.request(response=b' ' * (1024 * 1024 + 1))

    def test_redirect_handler_blocks_even_other_local_urls(self):
        with self.assertRaisesRegex(ValueError, 'redirects are not allowed'):
            narration.NoRedirect().redirect_request(None, None, 302, 'move', {}, 'http://127.0.0.1:9999/elsewhere')


if __name__ == '__main__':
    unittest.main()
