"""Cross-entry-point regressions for the shared PO clarification contract."""
import copy
import io
import json
import threading
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from clarity.clarification import clarification_contract
from clarity.evaluation import evaluate
from clarity.guardrails import ValidationError, digest
from clarity.host_bridge import packet, receipt, submit
from clarity.refine.__main__ import main
from clarity.refine.controller import engine_digest, _records
from clarity.refine.web import Workbench
from clarity.refine.worker import preflight, request_packet, run_stage
from clarity.storage import transaction
from refine_fixtures import assessment
from test_refine_controller import Fixture
from test_refine_worker_web import FakeProvider
import test_refine_worker_web as http_fixture


class ClarificationRuntimeTests(Fixture):
    def test_author_tasks_share_one_contract_and_keep_review_independent(self):
        value = self.confirmed()
        self.c.submit(self.a, 'REQ1', self.version(), value)
        contract = clarification_contract()
        self.assertTrue(contract.startswith('# PO clarification'))
        for stage in ('intake', 'draft', 'revise'):
            direct = request_packet(self.status(), stage)
            bridged = packet(self.c, self.a, 'REQ1', stage)['task']
            self.assertEqual(direct, bridged)
            self.assertEqual(direct['clarification_method'], contract)
            serialized = json.dumps(direct)
            self.assertEqual(serialized.count('# PO clarification'), 1)
            self.assertNotIn('name: po-clarification', serialized)
            schema = direct['response_schema']['properties']['questions']['items']
            self.assertIn('prerequisites', schema['required'])
            self.assertFalse(schema['additionalProperties'])
        review = packet(self.c, self.r, 'REQ1')['task']
        self.assertNotIn('clarification_method', review)
        self.assertNotIn('review_feedback', review)

    def test_explicit_intake_reuses_open_questions_without_false_readiness(self):
        self.c.ask(self.a, 'REQ1', self.version(), self.question())
        self.c.answer(self.o, 'REQ1', self.version(), 'Q1', 'The time boundary still needs a policy decision.',
                      response_kind='needs_owner', decision_owner='Booking policy owner')
        before = copy.deepcopy(self.status()['context'])
        provider = FakeProvider({'questions': [], 'ready_to_draft': False})
        result = run_stage(self.c, self.a, 'REQ1', self.version(), 'intake', provider)
        self.assertEqual(provider.packet['payload']['context'], before)
        self.assertEqual(result['context'], before)
        self.assertEqual(result['run']['state'], 'awaiting_decision')
        self.assertEqual(result['run']['calls'], 1)
        self.assertIsNone(result['draft']); self.assertIsNone(result['review'])
        self.assertEqual(result['efficiency']['pending_responses'], 1)
        self.assertEqual(result['efficiency']['owner_answers'], 0)
        task = packet(self.c, self.a, 'REQ1', 'intake')
        result = submit(self.c, self.a, 'REQ1', task['expected_version'], task['context_digest'],
                        {'questions': [], 'ready_to_draft': False}, 'intake')
        self.assertEqual(result['run']['calls'], 1)
        self.assertEqual(result['efficiency']['assistant_submissions'], 1)
        self.assertEqual(receipt(result)['ready_question_ids'], ['Q1'])
        self.assertFalse(any(e['kind'] in {'intake_ready', 'approval'} for e in result['events']))

    def test_intake_cannot_claim_ready_with_open_decisions_or_wait_without_one(self):
        with self.assertRaisesRegex(ValidationError, 'requires an unresolved'):
            run_stage(self.c, self.a, 'REQ1', self.version(), 'intake',
                      FakeProvider({'questions': [], 'ready_to_draft': False}))
        self.c.ask(self.a, 'REQ1', self.version(), self.question())
        with self.assertRaisesRegex(ValidationError, 'Owner decisions remain open'):
            run_stage(self.c, self.a, 'REQ1', self.version(), 'intake',
                      FakeProvider({'questions': [], 'ready_to_draft': True}))
        self.assertEqual(self.status()['context']['questions']['Q1']['state'], 'open')
        self.assertFalse(any(e['kind'] in {'intake_ready', 'approval'} for e in self.status()['events']))
        self.assertTrue(all(not call['succeeded'] for call in self.status()['model_calls']))

    def test_intake_persists_new_dependencies_and_accepts_legacy_question_shape(self):
        questions = [{**self.question('Q2', 'What happens to pending refunds?', 5), 'prerequisites': ['Q1']},
                     self.question('Q1', 'Which cancellation cases are in scope?', 2)]
        result = run_stage(self.c, self.a, 'REQ1', self.version(), 'intake',
                           FakeProvider({'questions': questions, 'ready_to_draft': False}))
        self.assertEqual(result['next_question']['id'], 'Q1')
        self.assertEqual(receipt(result)['ready_question_ids'], ['Q1'])
        self.assertEqual(receipt(result)['open_question_ids'], ['Q2', 'Q1'])
        self.assertEqual(result['context']['questions']['Q1']['prerequisites'], [])
        task = packet(self.c, self.a, 'REQ1', 'intake')
        self.assertEqual(task['task']['context']['questions']['Q2']['prerequisites'], ['Q1'])

    def test_imports_cannot_bypass_open_decision_guard(self):
        value = self.confirmed()
        self.c.ask(self.a, 'REQ1', self.version(), self.question())
        before = self.status()
        with self.assertRaisesRegex(ValidationError, 'Owner decisions are pending'):
            self.c.submit(self.a, 'REQ1', self.version(), value)
        with self.assertRaisesRegex(ValidationError, 'Owner decisions are pending'):
            submit(self.c, self.a, 'REQ1', self.version(), before['context_digest'],
                   {'questions': [], 'draft': value}, 'draft')
        self.assertEqual(self.status()['events'], before['events'])
        self.assertEqual(self.version(), before['run']['version'])
        self.assertIsNone(self.status()['draft'])

    def test_changed_owner_response_rejects_inflight_intake_result(self):
        self.c.ask(self.a, 'REQ1', self.version(), self.question())
        controller, owner = self.c, self.o
        class Provider:
            name = 'synthetic-stale-intake'
            def complete(_, system, payload):
                status = controller.status(owner, 'REQ1')
                controller.answer(owner, 'REQ1', status['run']['version'], 'Q1', 'The policy owner is still deciding.',
                                  response_kind='unknown')
                return {'questions': [], 'ready_to_draft': False}
        with self.assertRaisesRegex(ValidationError, 'Stale brief version'):
            run_stage(self.c, self.a, 'REQ1', self.version(), 'intake', Provider())
        status = self.status()
        self.assertFalse(status['model_calls'][-1]['succeeded'])
        self.assertFalse(any(e['kind'] == 'intake_waiting' for e in status['events']))
        self.assertEqual(status['context']['questions']['Q1']['response']['kind'], 'unknown')

    def test_partial_response_history_reaches_followup_without_becoming_evidence(self):
        self.c.ask(self.a, 'REQ1', self.version(), self.question())
        earlier = 'The refund should go to the original card; Finance still needs to set the deadline.'
        latest = 'The exact deadline is still unknown; Finance is the decision owner.'
        for message, kind in ((earlier, 'partial'), (latest, 'needs_owner'), (latest, 'needs_owner')):
            self.c.answer(self.o, 'REQ1', self.version(), 'Q1', message, response_kind=kind)
        task = packet(self.c, self.a, 'REQ1', 'intake')['task']
        question = task['context']['questions']['Q1']
        self.assertEqual(question['response']['text'], latest)
        self.assertEqual([r['text'] for r in question['response_history']], [earlier])
        self.assertNotIn('decision_source', question)
        self.assertEqual(set(task['context']['sources']), {'BRIEF'})
        self.c.answer(self.o, 'REQ1', self.version(), 'Q1', earlier, response_kind='partial')
        question = self.status()['context']['questions']['Q1']
        self.assertEqual([r['text'] for r in question['response_history']], [latest])
        self.assertEqual(question['response']['text'], earlier)

    def test_prompt_audit_and_quality_digest_include_shared_contract(self):
        provider = FakeProvider({'questions': [], 'ready_to_draft': True})
        first = run_stage(self.c, self.a, 'REQ1', self.version(), 'intake', provider)
        with patch('clarity.refine.worker.clarification_contract', return_value=clarification_contract() + '\nSynthetic contract amendment.'):
            second = run_stage(self.c, self.a, 'REQ1', self.version(), 'intake', provider)
        self.assertNotEqual(first['model_calls'][-1]['prompt_digest'], second['model_calls'][-1]['prompt_digest'])
        original = Path.read_bytes
        before = engine_digest()
        def amended(path):
            content = original(path)
            return content + b'\nSynthetic contract amendment.' if path.name == 'SKILL.md' and path.parent.name == 'po-clarification' else content
        with patch.object(Path, 'read_bytes', amended):
            self.assertNotEqual(engine_digest(), before)

    def test_operator_can_exclude_historical_sensitive_paste_and_recover_model_context(self):
        self.c.ask(self.a, 'REQ1', self.version(), self.question())
        accidental = 'Synthetic accidental paste: ' + 'ghp_' + 'x' * 36
        self.c.answer(self.o, 'REQ1', self.version(), 'Q1', accidental, response_kind='partial')
        self.c.answer(self.o, 'REQ1', self.version(), 'Q1', 'Cancellation closes at the start time.')
        before = self.status()
        earlier = before['context']['questions']['Q1']['response_history'][0]
        with self.assertRaisesRegex(ValidationError, 'credential-like'):
            preflight(before, 'draft')
        for key in (self.a, self.r):
            with self.assertRaises(ValidationError):
                self.c.exclude_response_history(key, 'REQ1', self.version(), 'Q1', digest(earlier),
                                                'This was a synthetic accidental sensitive paste.')
        result = self.c.exclude_response_history(self.o, 'REQ1', self.version(), 'Q1', digest(earlier),
                                                'This was a synthetic accidental sensitive paste.')
        self.assertNotEqual(before['context_digest'], result['context_digest'])
        self.assertEqual(before['context']['sources'], result['context']['sources'])
        question = result['context']['questions']['Q1']
        self.assertEqual(question['response_history'], [])
        self.assertEqual(question['excluded_response_digests'], [digest(earlier)])
        self.assertEqual(question['response'], before['context']['questions']['Q1']['response'])
        self.assertNotIn(accidental, json.dumps(preflight(result, 'draft')))
        with transaction(self.root, write=False) as db:
            self.assertEqual(_records(db, 'REQ1', 'question_response')[0]['data']['response']['text'], accidental)
            self.assertEqual(len(_records(db, 'REQ1', 'response_history_exclusion')), 1)
        self.assertTrue(self.c.verify(self.a, 'REQ1')['valid'])
        # A later change cannot reintroduce excluded history. A new explicit
        # current response is still selected and remains subject to scanning.
        self.c.answer(self.o, 'REQ1', self.version(), 'Q1', 'The corrected deadline is one hour before the start.')
        self.assertNotIn(accidental, json.dumps(preflight(self.status(), 'draft')))
        self.c.answer(self.o, 'REQ1', self.version(), 'Q1', accidental, response_kind='partial')
        with self.assertRaisesRegex(ValidationError, 'credential-like'):
            preflight(self.status(), 'intake')

    def test_history_exclusion_cannot_remove_current_answer_or_use_stale_selection(self):
        self.c.ask(self.a, 'REQ1', self.version(), self.question())
        self.c.answer(self.o, 'REQ1', self.version(), 'Q1', 'A tentative rule.', response_kind='proposal')
        self.c.answer(self.o, 'REQ1', self.version(), 'Q1', 'The confirmed current rule.')
        before = self.status(); question = before['context']['questions']['Q1']
        reason = 'This earlier proposal no longer belongs in selected context.'
        for version, fingerprint, rationale in (
            (self.version(), digest(question['response']), reason),
            (self.version() - 1, digest(question['response_history'][0]), reason),
            (self.version(), '0' * 64, reason),
            (self.version(), digest(question['response_history'][0]), 'Too short'),
        ):
            with self.subTest(version=version, fingerprint=fingerprint, rationale=rationale):
                with self.assertRaises(ValidationError):
                    self.c.exclude_response_history(self.o, 'REQ1', version, 'Q1', fingerprint, rationale)
        self.assertEqual(self.status()['events'], before['events'])
        self.assertEqual(self.status()['context'], before['context'])

    def test_history_selection_change_invalidates_existing_review_and_approval(self):
        value = self.confirmed()
        self.c.ask(self.a, 'REQ1', self.version(), self.question())
        self.c.answer(self.o, 'REQ1', self.version(), 'Q1', 'An earlier tentative boundary.', response_kind='proposal')
        self.c.answer(self.o, 'REQ1', self.version(), 'Q1', 'Cancellation closes at the start time.')
        self.c.submit(self.a, 'REQ1', self.version(), value)
        self.c.review(self.r, 'REQ1', self.version(), assessment(value))
        plan = self.c.plan(self.o, 'REQ1')
        approved = self.c.approve(self.o, 'REQ1', self.version(), plan['plan_digest'])
        earlier = self.status()['context']['questions']['Q1']['response_history'][0]
        result = self.c.exclude_response_history(self.o, 'REQ1', self.version(), 'Q1', digest(earlier),
                                                'The earlier tentative boundary no longer belongs in the selected context.')
        self.assertTrue(result['stale'])
        self.assertIsNone(result['review'])
        with self.assertRaises(ValidationError): self.c.seal(self.o, 'REQ1', approved['approval_id'])

    def test_cli_records_unknown_response_without_converting_it_to_evidence(self):
        self.c.ask(self.a, 'REQ1', self.version(), self.question())
        response_file = Path(self.tmp.name) / 'owner-response.json'
        response_file.write_text(json.dumps({'question_id': 'Q1', 'answer': 'The policy owner must decide.',
                                             'response_kind': 'unknown', 'decision_owner': 'Policy owner'}))
        output = io.StringIO()
        with redirect_stdout(output):
            code = main(['--state', str(self.root), 'action', 'answer', '--key-file', str(Path(self.tmp.name) / 'owner.key'),
                         '--id', 'REQ1', '--version', str(self.version()), '--input', str(response_file)])
        self.assertEqual(code, 0)
        question = self.status()['context']['questions']['Q1']
        self.assertEqual(question['state'], 'open')
        self.assertEqual(question['response']['decision_owner'], 'Policy owner')
        self.assertNotIn('decision_source', question)

    def test_quality_evaluation_accepts_question_dependencies_and_rejects_cycles(self):
        corpus = json.loads((Path(__file__).resolve().parents[1] / 'examples/quality-corpus.json').read_text())
        case = corpus['cases'][0]
        parent = self.question('Q1', 'Which cancellations are in scope?', 3)
        child = {**self.question('Q2', 'What happens to pending refunds?', 5), 'prerequisites': ['Q1']}
        def outcome(questions):
            report = evaluate(corpus, [{'case_id': case['id'], 'trial': 1, 'result': {'questions': questions, 'draft': None}}], trials=1)
            return next(row for row in report['trials'] if row['case_id'] == case['id'])
        self.assertTrue(outcome([child, parent])['contract_passed'])
        cyclic = {**parent, 'prerequisites': ['Q2']}
        self.assertTrue(outcome([child, cyclic])['invalid'])
        unknown = {**child, 'prerequisites': ['MISSING']}
        self.assertTrue(outcome([unknown, parent])['invalid'])


class ClarificationHttpTests(Fixture):
    request = http_fixture.WorkbenchTests.request
    csrf = http_fixture.WorkbenchTests.csrf
    login = http_fixture.WorkbenchTests.login
    close_server = http_fixture.WorkbenchTests.close_server

    def setUp(self):
        super().setUp()
        self.server = Workbench(self.root, port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start(); self.addCleanup(self.close_server)
        self.cookie = None
        self.c.ask(self.a, 'REQ1', self.version(), self.question())

    def test_server_requires_explicit_valid_response_kind(self):
        self.login(self.o)
        _, _, body = self.request(path='/run/REQ1')
        before = self.status()
        data = {'csrf': self.csrf(body), 'version': self.version(), 'question_id': 'Q1',
                'answer': 'A tentative response.', 'decision_owner': ''}
        for extra in ({}, {'response_kind': ''}, {'response_kind': 'approved'}):
            with self.subTest(extra=extra):
                self.assertEqual(self.request('POST', '/run/REQ1/answer', {**data, **extra})[0], 400)
        self.assertEqual(self.status()['events'], before['events'])
        self.assertEqual(self.version(), before['run']['version'])

    def test_nonconfirmed_response_is_escaped_and_does_not_grant_authority(self):
        self.login(self.o)
        _, _, body = self.request(path='/run/REQ1')
        data = {'csrf': self.csrf(body), 'version': self.version(), 'question_id': 'Q1',
                'answer': 'Unsure <script>bad()</script>', 'response_kind': 'proposal', 'decision_owner': '<b>Policy owner</b>'}
        self.assertEqual(self.request('POST', '/run/REQ1/answer', data)[0], 303)
        _, _, body = self.request(path='/run/REQ1')
        self.assertIn('&lt;b&gt;Policy owner&lt;/b&gt;', body)
        self.assertIn('&lt;script&gt;bad()&lt;/script&gt;', body)
        self.assertNotIn('<b>Policy owner</b>', body)
        question = self.status()['context']['questions']['Q1']
        self.assertEqual(question['state'], 'open')
        self.assertNotIn('decision_source', question)
        data.update(csrf=self.csrf(body), version=self.version(), answer='A suitable owner still needs to decide.',
                    response_kind='needs_owner', decision_owner='Policy owner')
        self.assertEqual(self.request('POST', '/run/REQ1/answer', data)[0], 303)
        _, _, body = self.request(path='/run/REQ1')
        self.assertIn('Earlier responses (history only)', body)
        self.assertIn('&lt;script&gt;bad()&lt;/script&gt;', body)
        self.assertIn('they do not establish a current decision', body)

    def test_question_history_shows_prerequisites_inherited_through_merge(self):
        self.c.ask_many(self.a, 'REQ1', self.version(), [
            {**self.question('Q2', 'What deadline applies to refunds?', 3), 'prerequisites': ['Q1']},
            self.question('Q3', 'When must a refund finish?', 4)])
        self.c.resolve_question(self.o, 'REQ1', self.version(), 'Q2', 'merged', 'Q3',
                                'These refer to the same refund deadline; retain Q3.')
        self.login(self.o)
        _, _, body = self.request(path='/run/REQ1')
        self.assertIn('Resolve prerequisites first: Q1.', body)
        self.assertNotIn('Resolve prerequisites first: .', body)
