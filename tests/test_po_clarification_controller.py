"""Decision-state regressions; synthetic fixtures do not establish model quality."""
import copy
import unittest

from clarity.guardrails import ValidationError
from clarity.refine.collaboration import question_order, questionnaire
from clarity.refine.contracts import DEFAULT_POLICY
from clarity.refine.controller import Controller, _records
from clarity.storage import transaction
from refine_fixtures import assessment
from test_refine_controller import Fixture, PARSER


class POClarificationControllerTests(Fixture):
    def q(self, qid, impact=3, prerequisites=None):
        value = self.question(qid, 'Which business behavior applies to ' + qid + '?', impact)
        if prerequisites is not None:
            value['prerequisites'] = prerequisites
        return value

    def ask(self, *questions):
        return self.c.ask_many(self.a, 'REQ1', self.version(), list(questions))

    def answer(self, qid, answer='The owner confirms the selected business behavior.', **kwargs):
        return self.c.answer(self.o, 'REQ1', self.version(), qid, answer, **kwargs)

    def test_legacy_question_and_confirmed_answer_remain_supported_after_restart(self):
        self.ask(self.q('Q1'))
        result = self.answer('Q1')
        question = result['context']['questions']['Q1']
        self.assertEqual(question['prerequisites'], [])
        self.assertEqual(question['state'], 'answered')
        self.assertEqual(question['response']['kind'], 'confirmed')
        self.assertEqual(result['context']['sources'][question['decision_source']]['authority'], 'owner')
        self.assertEqual(Controller(self.root).status(self.a, 'REQ1')['context_digest'], result['context_digest'])
        self.assertTrue(self.c.verify(self.a, 'REQ1')['valid'])

    def test_live_frontier_prioritizes_only_questions_with_resolved_prerequisites(self):
        # Forward references in one atomic batch are valid, even at higher impact.
        result = self.ask(self.q('Q2', 5, ['Q1']), self.q('Q1', 1), self.q('Q3', 3))
        self.assertEqual([q['id'] for q in result['open_questions']], ['Q2', 'Q3', 'Q1'])
        self.assertEqual([q['id'] for q in result['ready_questions']], ['Q3', 'Q1'])
        self.assertEqual(result['next_question']['id'], 'Q3')
        self.answer('Q3')
        self.assertEqual(self.status()['next_question']['id'], 'Q1')
        self.answer('Q1')
        self.assertEqual(self.status()['next_question']['id'], 'Q2')

    def test_invalid_dependency_batches_leave_no_partial_records(self):
        for prerequisites in (['UNKNOWN'], ['Q1'], ['Q2', 'Q2'], 'Q2', None, [False]):
            with self.subTest(prerequisites=prerequisites):
                bad = self.q('Q1'); bad['prerequisites'] = prerequisites
                before = self.status()
                with self.assertRaises(ValidationError): self.ask(bad, self.q('Q2'))
                self.assertEqual(self.status()['events'], before['events'])
                self.assertEqual(self.status()['run']['version'], before['run']['version'])
        with self.assertRaises(ValidationError): self.ask(self.q('Q1', 3, ['Q2']), self.q('Q2', 3, ['Q1']))
        self.assertEqual(self.status()['context']['questions'], {})

    def test_only_operator_can_record_all_response_kinds(self):
        self.ask(self.q('Q1'))
        for kind in ('confirmed', 'partial', 'unknown', 'proposal', 'needs_owner'):
            for key in (self.a, self.r):
                with self.subTest(kind=kind, key=key):
                    with self.assertRaises(ValidationError):
                        self.c.answer(key, 'REQ1', self.version(), 'Q1', 'Some response.', response_kind=kind)
        self.assertNotIn('response', self.status()['context']['questions']['Q1'])

    def test_nonconfirmed_responses_stay_open_without_becoming_sources(self):
        self.ask(self.q('Q1'))
        initial_sources = copy.deepcopy(self.status()['context']['sources'])
        for kind in ('partial', 'unknown', 'proposal', 'needs_owner'):
            with self.subTest(kind=kind):
                response = 'Recorded ' + kind + ' information awaiting a business decision.'
                result = self.answer('Q1', response, response_kind=kind, decision_owner='Project owner')
                question = result['context']['questions']['Q1']
                self.assertEqual(question['state'], 'open')
                self.assertEqual(question['response'], {'kind': kind, 'text': response, 'decision_owner': 'Project owner'})
                self.assertNotIn('decision_source', question)
                self.assertEqual(result['context']['sources'], initial_sources)
                self.assertEqual(result['run']['state'], 'awaiting_decision')
                with self.assertRaises(ValidationError):
                    self.c.intake_ready(self.a, 'REQ1', self.version(), result['context_digest'])
        with transaction(self.root, write=False) as db:
            recorded = _records(db, 'REQ1', 'question_response')
        self.assertEqual([r['data']['response']['kind'] for r in recorded], ['partial', 'unknown', 'proposal', 'needs_owner'])
        self.assertTrue(self.c.verify(self.a, 'REQ1')['valid'])

    def test_invalid_response_kind_and_owner_are_atomic(self):
        self.ask(self.q('Q1'))
        before = self.status()
        for kwargs in ({'response_kind': 'approved'}, {'response_kind': []}, {'decision_owner': ''}, {'decision_owner': False}):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValidationError): self.answer('Q1', **kwargs)
        self.assertEqual(self.status()['context_digest'], before['context_digest'])
        self.assertEqual(self.status()['events'], before['events'])

    def test_confirmation_requires_prerequisites_but_partial_information_can_be_recorded(self):
        self.ask(self.q('Q1'), self.q('Q2', 5, ['Q1']))
        with self.assertRaisesRegex(ValidationError, 'prerequisite.*Q1'): self.answer('Q2')
        result = self.answer('Q2', 'We may use the existing workflow.', response_kind='proposal')
        self.assertEqual(result['next_question']['id'], 'Q1')
        self.assertEqual(result['context']['questions']['Q2']['state'], 'open')
        self.answer('Q1')
        self.assertEqual(self.answer('Q2')['context']['questions']['Q2']['state'], 'answered')

    def test_merge_targets_preserve_prerequisites_and_control_live_answers(self):
        self.ask(self.q('Q1', 3, ['Q3']), self.q('Q2', 5), self.q('Q3', 1), self.q('Q4', 4, ['Q1']))
        self.c.resolve_question(self.o, 'REQ1', self.version(), 'Q1', 'merged', 'Q2',
                                'The operator confirms Q1 and Q2 describe the same decision.')
        self.assertEqual(self.status()['next_question']['id'], 'Q3')
        with self.assertRaisesRegex(ValidationError, 'prerequisite.*Q3'): self.answer('Q2')
        self.answer('Q3')
        self.assertEqual(self.status()['next_question']['id'], 'Q2')
        with self.assertRaisesRegex(ValidationError, 'prerequisite.*Q2'): self.answer('Q4')
        self.answer('Q2')
        self.assertEqual(self.status()['next_question']['id'], 'Q4')

    def test_merge_induced_self_dependency_and_indirect_cycles_are_atomic(self):
        self.ask(self.q('Q1', 3, ['Q2']), self.q('Q2', 3, ['Q3']), self.q('Q3'))
        before = self.status()
        for target in ('Q2', 'Q3'):
            with self.subTest(target=target):
                with self.assertRaises(ValidationError):
                    self.c.resolve_question(self.o, 'REQ1', self.version(), 'Q1', 'merged', target,
                                            'This proposed merge must be validated before recording.')
                self.assertEqual(self.status()['events'], before['events'])
                self.assertEqual(self.status()['context_digest'], before['context_digest'])

    def test_only_explicit_operator_disposition_satisfies_out_of_scope_prerequisite(self):
        self.ask(self.q('Q1'), self.q('Q2', 5, ['Q1']))
        for key in (self.a, self.r):
            with self.assertRaises(ValidationError):
                self.c.resolve_question(key, 'REQ1', self.version(), 'Q1', 'out_of_scope', None,
                                        'This business decision is outside the agreed scope.')
        self.c.resolve_question(self.o, 'REQ1', self.version(), 'Q1', 'out_of_scope', None,
                                'The operator confirms this decision is outside the agreed scope.')
        self.assertEqual(self.status()['next_question']['id'], 'Q2')
        self.answer('Q2')

    def test_reopening_confirmation_retires_source_but_keeps_immutable_history(self):
        self.ask(self.q('Q1'))
        first = self.answer('Q1', 'The original confirmed decision.')
        source_id = first['context']['questions']['Q1']['decision_source']
        result = self.answer('Q1', 'We do not yet know the applicable rule.', response_kind='unknown')
        self.assertNotEqual(result['context_digest'], first['context_digest'])
        self.assertNotIn(source_id, result['context']['sources'])
        self.assertNotIn('decision_source', result['context']['questions']['Q1'])
        with transaction(self.root, write=False) as db:
            answers = _records(db, 'REQ1', 'answer')
        self.assertEqual(answers[0]['data']['source']['id'], source_id)
        self.assertEqual(answers[0]['data']['source']['text'], 'The original confirmed decision.')

    def test_upstream_correction_reopens_confirmed_descendants_until_reconfirmed(self):
        self.ask(self.q('Q1'), self.q('Q2', 4, ['Q1']), self.q('Q3', 5, ['Q2']), self.q('Q4'))
        for qid in ('Q1', 'Q2', 'Q3', 'Q4'): self.answer(qid, 'Confirmed decision for ' + qid + '.')
        before = self.status()['context']['questions']
        result = self.answer('Q1', 'A changed confirmed foundational decision.')
        for qid in ('Q2', 'Q3'):
            question = result['context']['questions'][qid]
            self.assertEqual(question['state'], 'open')
            self.assertEqual(question['invalidated_by'], ['Q1'])
            self.assertEqual(question['response'], before[qid]['response'])
            self.assertNotIn('decision_source', question)
            self.assertNotIn(before[qid]['decision_source'], result['context']['sources'])
        self.assertEqual(result['context']['questions']['Q4']['state'], 'answered')
        self.assertEqual(result['next_question']['id'], 'Q2')
        with self.assertRaises(ValidationError): self.answer('Q3')
        self.answer('Q2', before['Q2']['response']['text'])
        self.assertNotIn('invalidated_by', self.status()['context']['questions']['Q2'])
        self.assertEqual(self.status()['context']['questions']['Q3']['state'], 'open')
        self.assertEqual(self.status()['next_question']['id'], 'Q3')

    def test_identical_confirmation_does_not_reopen_descendants(self):
        self.ask(self.q('Q1'), self.q('Q2', 3, ['Q1']))
        self.answer('Q1'); self.answer('Q2')
        before = self.status()['context']['questions']['Q2']
        result = self.answer('Q1')
        self.assertEqual(result['context']['questions']['Q2'], before)
        self.assertFalse(result['open_questions'])

    def test_stale_context_and_version_cannot_apply_followup_work(self):
        self.ask(self.q('Q1'))
        before = self.status()
        self.answer('Q1', 'We need the policy owner to decide.', response_kind='needs_owner')
        with self.assertRaises(ValidationError):
            self.c.ask_many(self.a, 'REQ1', self.version(), [self.q('Q2')], before['context_digest'])
        with self.assertRaises(ValidationError):
            self.c.intake_waiting(self.a, 'REQ1', self.version(), before['context_digest'])
        with self.assertRaises(ValidationError):
            self.c.reserve_call(self.a, 'REQ1', self.version(), 'intake', before['context_digest'])
        with self.assertRaises(ValidationError):
            self.c.answer(self.o, 'REQ1', before['run']['version'], 'Q1', 'A stale submitted answer.')

    def test_only_intake_can_reserve_with_open_questions_and_still_uses_budget(self):
        self.c.set_policy(self.o, 'PERSONAL', {**DEFAULT_POLICY, 'max_model_calls': 2})
        self.ask(self.q('Q1'))
        for stage in ('draft', 'revise'):
            with self.assertRaisesRegex(ValidationError, 'Owner decisions are pending'):
                self.c.reserve_call(self.a, 'REQ1', self.version(), stage, self.status()['context_digest'])
        self.assertEqual(self.status()['run']['calls'], 0)
        for _ in range(2):
            self.c.reserve_call(self.a, 'REQ1', self.version(), 'intake', self.status()['context_digest'])
        self.assertEqual(self.status()['run']['calls'], 2)
        with self.assertRaisesRegex(ValidationError, 'budget exhausted'):
            self.c.reserve_call(self.a, 'REQ1', self.version(), 'intake', self.status()['context_digest'])

    def test_intake_waiting_records_advice_without_ready_or_approval(self):
        with self.assertRaises(ValidationError):
            self.c.intake_waiting(self.a, 'REQ1', self.version(), self.status()['context_digest'])
        self.ask(self.q('Q1'))
        for key in (self.o, self.r):
            with self.assertRaises(ValidationError):
                self.c.intake_waiting(key, 'REQ1', self.version(), self.status()['context_digest'])
        result = self.c.intake_waiting(self.a, 'REQ1', self.version(), self.status()['context_digest'], assistant=True)
        self.assertEqual(result['run']['state'], 'awaiting_decision')
        self.assertIsNone(result['draft']); self.assertIsNone(result['review'])
        self.assertEqual(result['context']['questions']['Q1']['state'], 'open')
        with transaction(self.root, write=False) as db:
            waiting = _records(db, 'REQ1', 'intake_waiting')
            self.assertEqual(_records(db, 'REQ1', 'approval'), [])
        self.assertFalse(waiting[0]['data']['handoff_approved'])

    def test_questionnaire_uses_persisted_graph_and_validated_local_overrides(self):
        self.ask(self.q('Q2', 5, ['Q1']), self.q('Q1', 1), self.q('Q3', 3))
        status = self.status(); before = copy.deepcopy(status)
        rendered = questionnaire(status, 'Business owner', 'Resolve required business choices', ['Q1', 'Q2', 'Q3'])
        self.assertLess(rendered.index('## Q1'), rendered.index('## Q2'))
        self.assertIn('Resolve these decisions first: Q1.', rendered)
        order = question_order(status['context']['questions'], {'Q3': ['Q2']})
        self.assertEqual([q['id'] for q in order], ['Q1', 'Q2', 'Q3'])
        with self.assertRaises(ValidationError): question_order(status['context']['questions'], {'Q1': ['Q2']})
        self.assertEqual(status, before)

    @unittest.skipUnless(PARSER, 'Official Gherkin parser required for handoff regression')
    def test_upstream_change_blocks_approval_and_stale_descendant_evidence(self):
        value = self.confirmed()
        self.ask(self.q('Q1'), self.q('Q2', 5, ['Q1']))
        self.answer('Q1')
        supporting_text = value['statements'][0]['text']
        self.answer('Q2', supporting_text)
        status = self.status()
        source_id = status['context']['questions']['Q2']['decision_source']
        source = status['context']['sources'][source_id]
        value['statements'][0]['citations'] = [{'source_id': source_id, 'source_digest': source['digest'], 'quote': supporting_text}]
        self.c.submit(self.a, 'REQ1', self.version(), value)
        self.c.review(self.r, 'REQ1', self.version(), assessment(value))
        plan = self.c.plan(self.o, 'REQ1')
        approval = self.c.approve(self.o, 'REQ1', self.version(), plan['plan_digest'])
        self.answer('Q1', 'The foundational rule is no longer known.', response_kind='unknown')
        self.assertTrue(self.status()['stale'])
        self.assertNotIn(source_id, self.status()['context']['sources'])
        with self.assertRaises(ValidationError): self.c.seal(self.o, 'REQ1', approval['approval_id'])
        self.answer('Q1', 'The revised foundation is confirmed.')
        with self.assertRaisesRegex(ValidationError, 'Owner decisions are pending'):
            self.c.submit(self.a, 'REQ1', self.version(), value)
        self.answer('Q2', supporting_text)
        self.c.submit(self.a, 'REQ1', self.version(), value)
        result = self.c.review(self.r, 'REQ1', self.version(), assessment(value))
        self.assertEqual(result['review']['quality']['verdict'], 'NOT READY')
        self.assertTrue(any(f['code'] == 'stale_or_missing_source' for f in result['checks']['findings']))
        with self.assertRaises(ValidationError): self.c.plan(self.o, 'REQ1')


if __name__ == '__main__':
    unittest.main()
