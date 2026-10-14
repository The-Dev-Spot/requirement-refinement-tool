"""Efficiency regressions: preserve evidence and authority while reducing repetition."""
import copy
import http.client
import io
import json
import unittest
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch

from clarity.connections import CloudModel
from clarity.efficiency import budget, prompt_parts, scorecard
from clarity.guardrails import ValidationError, canonical, digest
from clarity.host_bridge import packet, receipt, serve, submit
from clarity.local_model import LocalModel
from clarity.refine.controller import _display_checks
from clarity.refine.handoff import archive
from clarity.refine.revisions import apply_revision
from clarity.refine.worker import Ollama, SYSTEM, preflight, request_packet, run_stage
from clarity.workspace import Workspace, initialize
from refine_fixtures import assessment
from test_refine_controller import Fixture
from test_refine_worker_web import FakeProvider
from test_workbench_v04 import HttpFixture, MODEL


def revision(value, **changes):
    result = {'base_draft_digest': digest(value), 'title': None, 'feature': None,
              'proposals': None, **{k: {'upsert': [], 'remove': []} for k in ('statements', 'scenarios', 'coverage')}}
    return {**result, **changes}


class PacketTests(Fixture):
    def test_compact_review_preserves_every_source_scenario_and_review_criterion(self):
        value = self.confirmed(); self.c.submit(self.a, 'REQ1', self.version(), value)
        status = self.status(self.r); before = copy.deepcopy(status)
        p = request_packet(status, 'review')
        self.assertEqual(p['context'], status['context'])
        self.assertEqual(p['draft'], value)
        self.assertEqual(p['machine_findings']['findings'], status['checks']['findings'])
        self.assertNotIn('scenario_index', p['machine_findings'])
        self.assertNotIn('brief', p); self.assertNotIn('output_contract', p)
        schema = p['response_schema']['properties']
        self.assertEqual(set(schema['statement_support']['properties']), {s['id'] for s in value['statements']})
        self.assertEqual(set(schema['scenario_fidelity']['properties']), {s['id'] for s in value['scenarios']})
        self.assertLess(len(canonical(p).encode()), 15967 * .75)  # Old booking task, including its schema.
        self.assertLess(sum(len(part.encode()) for part in prompt_parts(p)), 7000)
        self.assertEqual(status, before)

    def test_rewrite_feedback_has_no_repeated_machine_projection_or_previous_review_in_fresh_review(self):
        self.ready(); status = self.status()
        author = request_packet(status, 'revise')
        self.assertEqual(author['review_feedback'], status['review']['review'])
        self.assertNotIn('quality', author['review_feedback'])
        fresh = request_packet(status, 'review')
        self.assertNotIn('review_feedback', fresh)
        self.assertNotIn('Synthetic reviewer fixture', canonical(fresh))

    def test_stable_prefix_survives_changed_draft_and_feedback(self):
        self.ready(); status = self.status()
        first = prompt_parts(request_packet(status, 'revise'))
        status['draft']['title'] = 'Another draft title'
        second = prompt_parts(request_packet(status, 'revise'))
        self.assertEqual(first[0], second[0]); self.assertNotEqual(first[1], second[1])
        self.assertNotIn('response_schema', first[1])

    def test_capacity_rejection_is_recorded_without_reserving_or_calling_provider(self):
        provider = FakeProvider(error=True); provider.context_tokens = 1024; provider.max_tokens = 1024
        with self.assertRaisesRegex(ValidationError, 'context budget'):
            run_stage(self.c, self.a, 'REQ1', self.version(), 'intake', provider)
        self.assertIsNone(provider.packet); self.assertEqual(self.status()['run']['calls'], 0)
        self.assertEqual(self.status()['events'][-1]['kind'], 'model_preflight_rejected')

    def test_unknown_capacity_is_reported_without_inventing_a_token_count(self):
        usage = budget(SYSTEM, request_packet(self.status(), 'intake'))
        self.assertIsNone(usage['remaining_estimated_tokens'])
        self.assertGreater(usage['estimated_input_tokens'], 0)
        self.assertEqual(usage['context_limit_tokens'], 0)

    def test_display_cache_reuses_only_identical_inputs_and_detaches_results(self):
        value = self.confirmed(); self.c.submit(self.a, 'REQ1', self.version(), value)
        _display_checks.cache_clear()
        from clarity.refine.checks import check
        with patch('clarity.refine.controller.checks.check', wraps=check) as checked:
            first = self.status(); first['checks']['findings'].append({'fake': True})
            second = self.status()
            self.assertEqual(checked.call_count, 1)
            self.assertNotIn({'fake': True}, second['checks']['findings'])
            self.c.set_policy(self.o, 'PERSONAL', {**second['context']['policy']['policy'], 'risk_ids': ['RISK1']})
            self.assertTrue(self.status()['stale']); self.assertEqual(checked.call_count, 2)

    def test_approval_checks_bypass_display_cache(self):
        self.ready()
        from clarity.refine.checks import check
        with patch('clarity.refine.controller.checks.check', wraps=check) as checked:
            self.c.plan(self.o, 'REQ1')
            self.assertGreater(checked.call_count, 0)


class RevisionTests(Fixture):
    def test_cancelled_revision_never_applies_and_records_the_attempt(self):
        value = self.ready(); cancelled = [False]
        class Provider:
            name = 'synthetic-cancellation'
            def complete(_, system, payload):
                cancelled[0] = True
                return {'questions': [], 'revision': revision(value, title='Must not be applied')}
        with self.assertRaisesRegex(ValidationError, 'cancelled'):
            run_stage(self.c, self.a, 'REQ1', self.version(), 'revise', Provider(), cancelled=lambda: cancelled[0])
        status = self.status()
        self.assertEqual(status['draft'], value)
        self.assertFalse(status['model_calls'][-1]['succeeded'])
        self.assertEqual(status['run']['revision'], 1)

    def test_failed_reused_provider_does_not_repeat_previous_token_measurements(self):
        class Provider:
            name = 'synthetic-reuse'; metrics = {}; fail = False
            def complete(instance, system, payload):
                if instance.fail: raise ValidationError('Synthetic failure before usage was returned')
                instance.metrics = {'input_tokens': 100, 'output_tokens': 10}
                return {'questions': [], 'ready_to_draft': True}
        provider = Provider()
        result = run_stage(self.c, self.a, 'REQ1', self.version(), 'intake', provider)
        self.assertEqual(result['efficiency']['input_tokens'], 100)
        provider.fail = True
        with self.assertRaises(ValidationError): run_stage(self.c, self.a, 'REQ1', self.version(), 'intake', provider)
        self.assertEqual(self.status()['efficiency']['input_tokens'], 100)
        self.assertEqual(self.status()['efficiency']['measured_attempts'], 1)
        self.assertEqual(self.status()['efficiency']['attempts'], 2)

    def test_small_edit_preserves_feature_evidence_and_requires_fresh_independent_review(self):
        value = self.ready()
        plan = self.c.plan(self.o, 'REQ1')
        approved = self.c.approve(self.o, 'REQ1', self.version(), plan['plan_digest'])
        changes = revision(value, title='Booking cancellation by the owner')
        response = {'questions': [], 'revision': changes}
        self.assertLess(len(canonical(response)), len(canonical({'questions': [], 'draft': value})) / 2)
        result = run_stage(self.c, self.a, 'REQ1', self.version(), 'revise', FakeProvider(response))
        self.assertEqual(result['draft']['feature'].encode(), value['feature'].encode())
        self.assertEqual(result['draft']['statements'], value['statements'])
        self.assertIsNone(result['review']); self.assertEqual(result['run']['state'], 'awaiting_review')
        self.assertEqual(result['run']['rewrites'], 1)
        with self.assertRaises(ValidationError): self.c.seal(self.o, 'REQ1', approved['approval_id'])
        with self.assertRaises(ValidationError): self.c.plan(self.o, 'REQ1')

    def test_missing_citation_in_edited_item_is_still_a_blocker(self):
        value = self.ready(); statement = copy.deepcopy(value['statements'][0]); statement['citations'] = []
        changes = revision(value, statements={'upsert': [statement], 'remove': []})
        result = run_stage(self.c, self.a, 'REQ1', self.version(), 'revise', FakeProvider({'questions': [], 'revision': changes}))
        reviewed = self.c.review(self.r, 'REQ1', self.version(), assessment(result['draft']))
        self.assertNotEqual(reviewed['review']['quality']['verdict'], 'READY')

    def test_bad_base_duplicate_operations_unknown_removal_extra_fields_and_noop_are_rejected(self):
        value = self.confirmed()
        cases = [revision(value), revision(value, base_draft_digest='0'*64, title='Changed'),
                 revision(value, statements={'upsert': [], 'remove': ['UNKNOWN']}),
                 revision(value, statements={'upsert': [value['statements'][0]]*2, 'remove': []}),
                 revision(value, statements={'upsert': [value['statements'][0]], 'remove': [value['statements'][0]['id']]}),
                 {**revision(value), 'approved': True}]
        for item in cases:
            with self.subTest(item=item), self.assertRaises(ValidationError): apply_revision(value, item)

    def test_coverage_uses_composite_identity_and_changed_feature_keeps_exact_bytes(self):
        value = self.confirmed(); row = copy.deepcopy(value['coverage'][0])
        changed = copy.deepcopy(row); changed['scenario_ids'] = []
        changed['not_applicable_reason'] = 'A synthetic reason to exercise assembly, not a quality judgment.'
        result = apply_revision(value, revision(value, coverage={'upsert': [changed], 'remove': []}, feature=value['feature']+'\n'))
        self.assertEqual(len(result['coverage']), len(value['coverage']))
        self.assertEqual(result['feature'].encode(), (value['feature']+'\n').encode())

    def test_changed_policy_during_revision_is_not_applied(self):
        value = self.ready(); c, o = self.c, self.o
        class Provider:
            name = 'synthetic-revision'
            def complete(_, system, payload):
                c.set_policy(o, 'PERSONAL', {**self.status()['context']['policy']['policy'], 'risk_ids': ['RISK1']})
                return {'questions': [], 'revision': revision(value, title='Changed title')}
        with self.assertRaises(ValidationError): run_stage(self.c, self.a, 'REQ1', self.version(), 'revise', Provider())
        self.assertEqual(self.status()['draft'], value)

    def test_exhausted_rewrite_budget_stops_before_inference(self):
        value = self.ready()
        for _ in range(3): self.c.submit(self.a, 'REQ1', self.version(), value)
        provider = FakeProvider(error=True); before = self.status()['run']['calls']
        with self.assertRaisesRegex(ValidationError, 'Rewrite budget exhausted'):
            run_stage(self.c, self.a, 'REQ1', self.version(), 'revise', provider)
        self.assertIsNone(provider.packet); self.assertEqual(self.status()['run']['calls'], before)

    def test_intake_is_optional_small_and_never_a_draft_or_approval(self):
        p = request_packet(self.status(), 'intake')
        self.assertNotIn('draft', p['response_schema']['properties'])
        result = run_stage(self.c, self.a, 'REQ1', self.version(), 'intake', FakeProvider({'questions': [], 'ready_to_draft': True}))
        self.assertIsNone(result['draft']); self.assertEqual(result['run']['revision'], 0)
        self.assertEqual(result['run']['calls'], 1)
        with self.assertRaises(ValidationError): self.c.plan(self.o, 'REQ1')

    def test_intake_questions_pause_further_calls_and_wrong_role_cannot_run_intake(self):
        result = run_stage(self.c, self.a, 'REQ1', self.version(), 'intake', FakeProvider({'questions': [self.question()], 'ready_to_draft': False}))
        self.assertEqual(len(result['open_questions']), 1)
        with self.assertRaises(ValidationError): preflight(self.status(), 'intake')
        self.c.answer(self.o, 'REQ1', self.version(), 'Q1', 'Only before the booking starts.')
        provider = FakeProvider(error=True)
        with self.assertRaises(ValidationError): run_stage(self.c, self.r, 'REQ1', self.version(), 'intake', provider)
        self.assertIsNone(provider.packet)


class TransportTests(unittest.TestCase):
    def test_evaluation_retains_failed_trial_usage_and_reports_unknowns(self):
        from clarity.evaluation import evaluate
        corpus = json.loads((Path(__file__).resolve().parents[1] / 'examples/quality-corpus.json').read_text())
        case = corpus['cases'][0]
        runs = [{'case_id': case['id'], 'trial': 1, 'result': {'questions': [{'id': 'Q1', 'text': 'Which boundary?', 'why': 'It determines the acceptance boundary.', 'impact': 5}], 'draft': None}, 'metrics': {'input_tokens': 100, 'elapsed_seconds': 1}},
                {'case_id': case['id'], 'trial': 2, 'result': {'draft': None}, 'metrics': {'input_tokens': 200, 'elapsed_seconds': 3}}]
        result = evaluate(corpus, runs, trials=2)
        group = result['groups'][case['input_style']]
        self.assertEqual(group['efficiency']['input_tokens'], {'samples': 2, 'total': 300, 'median': 150})
        self.assertIsNone(group['efficiency']['output_tokens']['total'])
        self.assertEqual(group['p95_elapsed_seconds'], 3)
        failed = next(r for r in result['trials'] if r['case_id'] == case['id'] and r['trial'] == 2)
        self.assertTrue(failed['invalid']); self.assertEqual(failed['input_tokens'], 200)

    def test_cloud_schema_is_sent_once_and_explicit_cache_is_opt_in(self):
        payload = {'task': 'draft', 'context': {'sources': {'test': 'selected evidence'}}, 'response_schema': {'type': 'object'}}
        envelopes = {'openai': {'status': 'completed', 'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': '{}'}]}]},
                     'anthropic': {'stop_reason': 'end_turn', 'content': [{'type': 'text', 'text': '{}'}]}}
        for kind in envelopes:
            for mode in ('provider', 'prefix'):
                with self.subTest(kind=kind, mode=mode), patch('clarity.connections.request', return_value=envelopes[kind]) as send:
                    CloudModel(kind, 'selected', 'synthetic', cache_mode=mode).complete(SYSTEM, payload)
                    body = send.call_args.kwargs['payload']
                    messages = body.get('input', body.get('messages'))
                    self.assertNotIn('response_schema', canonical(messages))
                    self.assertNotIn('"type":"object"', canonical(messages))
                    self.assertIn('selected evidence', canonical(messages))
                    if kind == 'openai':
                        self.assertEqual(body['text']['format']['schema'], payload['response_schema'])
                        self.assertEqual('prompt_cache_options' in body, mode == 'prefix')
                    else:
                        self.assertEqual('cache_control' in body['messages'][0]['content'][0], mode == 'prefix')

    def test_nested_usage_including_failed_output_is_retained(self):
        envelope = {'status': 'incomplete', 'usage': {'input_tokens': 100, 'output_tokens': 30,
                    'input_tokens_details': {'cached_tokens': 80, 'cache_write_tokens': 10},
                    'output_tokens_details': {'reasoning_tokens': 20}}}
        provider = CloudModel('openai', 'selected', 'synthetic')
        with patch('clarity.connections.request', return_value=envelope), self.assertRaises(ValidationError):
            provider.complete(SYSTEM, {'response_schema': {}})
        self.assertEqual(provider.metrics['cache_read_input_tokens'], 80)
        self.assertEqual(provider.metrics['cache_creation_input_tokens'], 10)
        self.assertEqual(provider.metrics['reasoning_tokens'], 20)

    def test_local_transports_keep_native_schema_and_context_setting(self):
        for kind in ('ollama', 'local-openai'):
            conn = Mock(); conn.getresponse.return_value.status = 200
            if kind == 'ollama':
                provider = Ollama('selected'); envelope = {'done': True, 'message': {'content': '{}'}}
                target = 'clarity.refine.worker.http.client.HTTPConnection'
            else:
                provider = LocalModel('selected'); envelope = {'choices': [{'finish_reason': 'stop', 'message': {'content': '{}'}}]}
                target = 'clarity.local_model.http.client.HTTPConnection'
            provider.context_tokens = 4096
            conn.getresponse.return_value.read.return_value = json.dumps(envelope).encode()
            with patch(target, return_value=conn): provider.complete(SYSTEM, {'response_schema': {'type': 'object'}, 'context': {}})
            body = json.loads(conn.request.call_args.kwargs['body'])
            self.assertNotIn('response_schema', canonical(body['messages']))
            if kind == 'ollama': self.assertEqual(body['options']['num_ctx'], 4096)

    def test_scorecard_counts_failed_usage_and_distinguishes_provider_token_semantics(self):
        calls = [{'stage': 'draft', 'provider': 'anthropic', 'succeeded': False, 'elapsed_seconds': 1,
                  'metrics': {'input_tokens': 10, 'output_tokens': 2, 'cache_read_input_tokens': 80, 'cache_creation_input_tokens': 10}},
                 {'stage': 'review', 'provider': 'openai', 'succeeded': True, 'elapsed_seconds': 2,
                  'metrics': {'input_tokens': 100, 'output_tokens': 3, 'cache_read_input_tokens': 80}},
                 {'stage': 'intake', 'provider': 'custom', 'succeeded': False, 'elapsed_seconds': 1, 'metrics': {}}]
        result = scorecard(calls, {'revision': 1, 'state': 'exported'}, [])
        self.assertEqual((result['input_tokens'], result['output_tokens'], result['cached_input_tokens']), (200, 5, 160))
        self.assertEqual(result['measured_attempts'], 2); self.assertEqual(result['attempts'], 3)
        self.assertIsNone(result['by_stage']['intake']['input_tokens']); self.assertIsNone(result['cost'])

    def test_unreported_cache_and_unfinished_calls_are_unknown(self):
        result = scorecard([{'stage': 'draft', 'succeeded': False, 'elapsed_seconds': 1,
                           'metrics': {'input_tokens': 10, 'output_tokens': 3}}],
                          {'revision': 0, 'state': 'captured'}, [{'kind': 'model_call_started'}]*2)
        self.assertEqual(result['unfinished_attempts'], 1)
        self.assertIsNone(result['cached_input_tokens'])


class ConfigurationTests(Fixture):
    def setUp(self):
        super().setUp(); initialize(self.root); self.w = Workspace(self.root)

    def test_compatible_profiles_and_stage_specific_selection(self):
        self.w.save(self.o, 'model', 'OLD', 0, MODEL)
        self.assertEqual(self.w.provider(self.a, 'OLD', 'intake').max_tokens, 1024)
        self.w.save(self.o, 'model', 'SMALL', 0, {**MODEL, 'stage': 'intake', 'context_tokens': 4096, 'intake_max_tokens': 512})
        provider = self.w.provider(self.a, 'SMALL', 'intake')
        self.assertEqual((provider.max_tokens, provider.context_tokens), (512, 4096))
        with self.assertRaises(ValidationError): self.w.provider(self.a, 'SMALL', 'review')

    def test_invalid_budgets_cache_and_stage_are_rejected(self):
        for extra in ({'context_tokens': 100}, {'review_max_tokens': True}, {'intake_max_tokens': 0}, {'stage': 'approve'}, {'cache_mode': 'prefix'}):
            with self.subTest(extra=extra), self.assertRaises(ValidationError): self.w.save(self.o, 'model', 'BAD', 0, {**MODEL, **extra})

    def test_assistant_revisions_use_same_context_guards_and_compact_receipts(self):
        value = self.ready(); task = packet(self.c, self.a, 'REQ1')
        self.assertEqual(task['stage'], 'revise')
        result = submit(self.c, self.a, 'REQ1', task['expected_version'], task['context_digest'], {'questions': [], 'revision': revision(value, title='Changed title')})
        self.assertNotIn('scenario_index', canonical(receipt(result)))
        self.assertEqual(result['efficiency']['assistant_submissions'], 1)
        with self.assertRaises(ValidationError): packet(self.c, self.r, 'REQ1', 'revise')

    def test_assistant_diagnostics_are_small_by_default_and_expanded_only_on_request(self):
        self.ready(); path = Path(self.tmp.name) / 'writer.key'
        messages = [{'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {}},
                    {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': {'name': 'clarity_get_findings', 'arguments': {}}},
                    {'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call', 'params': {'name': 'clarity_get_findings', 'arguments': {'include_examples': True}}}]
        out = io.StringIO(); serve(self.root, path, 'REQ1', io.StringIO('\n'.join(map(json.dumps, messages))), out)
        values = [json.loads(json.loads(line)['result']['content'][0]['text']) for line in out.getvalue().splitlines()[1:]]
        self.assertNotIn('scenario_index', values[0]['checks']); self.assertIn('scenario_index', values[1]['checks'])
        self.assertNotIn('sources', values[0])


class DeliveryHttpTests(HttpFixture):
    def test_delivery_and_full_audit_are_views_of_same_approved_bytes(self):
        value = self.ready(); planned = self.c.plan(self.o, 'REQ1')
        approved = self.c.approve(self.o, 'REQ1', self.version(), planned['plan_digest'])
        sealed = self.c.seal(self.o, 'REQ1', approved['approval_id'])
        self.login(self.o)
        base = '/export/REQ1/' + str(approved['approval_id'])
        for suffix, expected in (('', 2), ('?audit=full', 7)):
            conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port)
            conn.request('GET', base+suffix, headers={'Cookie': self.cookie})
            response = conn.getresponse(); body = response.read(); conn.close()
            self.assertEqual(response.status, 200)
            with zipfile.ZipFile(io.BytesIO(body)) as z:
                self.assertEqual(len(z.namelist()), expected)
                self.assertEqual(z.read('acceptance.feature'), value['feature'].encode())
        self.assertEqual(self.request(path=base+'?file=acceptance.feature')[2], value['feature'])
        self.assertEqual(self.c.exported(self.o, 'REQ1', approved['approval_id']), sealed)
        self.assertIn('Download handoff · 2 files', self.request(path='/run/REQ1')[2])
        with self.assertRaises(ValidationError): preflight(self.status(), 'draft')

    def test_stage_configuration_and_budget_are_visible_before_running(self):
        self.server.workspace.save(self.o, 'model', 'SMALL', 0, {**MODEL, 'context_tokens': 16384, 'intake_max_tokens': 512})
        self.login()
        code, _, body = self.request(path='/run/REQ1')
        self.assertEqual(code, 200); self.assertIn('Input and output budgets before running', body)
        self.assertIn('Check missing decisions only', body); self.assertIn('Estimated input', body)


if __name__ == '__main__': unittest.main()
