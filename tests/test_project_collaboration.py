import copy
import unittest

from clarity.guardrails import ValidationError, digest
from clarity.refine.collaboration import question_order, questionnaire
from clarity.refine.project_tools import ProjectTools, validate_glossary
from test_refine_controller import Fixture, PARSER


def glossary():
    return {'schema_version': 1, 'reason': 'The project owner confirms these terms describe the agreed business domain.',
            'terms': [{'id': 'TERM-CANCEL', 'term': 'Cancellation', 'definition': 'Stopping a queued operation before it begins.',
                       'aliases': ['Cancel']}]}


class ProjectGlossaryTests(Fixture):
    def setUp(self):
        super().setUp(); self.tools = ProjectTools(self.root)

    def approve(self, value=None, expected=0):
        return self.tools.approve_glossary(self.o, 'PERSONAL', value or glossary(), expected)

    def attach(self, selected, replace=None):
        return self.tools.attach_glossary(self.o, 'REQ1', self.version(), selected['record'], selected['digest'], replace)

    def test_empty_project_has_no_implicit_definitions(self):
        self.assertEqual(self.tools.glossary(self.a, 'PERSONAL')['record'], 0)

    def test_only_operator_can_approve_project_terms(self):
        for key in (self.a, self.r):
            with self.assertRaises(ValidationError): self.tools.approve_glossary(key, 'PERSONAL', glossary(), 0)

    def test_exact_record_required_for_update(self):
        first = self.approve()
        with self.assertRaises(ValidationError): self.approve(expected=0)
        self.assertEqual(self.tools.glossary(self.a, 'PERSONAL')['record'], first['record'])

    def test_old_revisions_remain_readable(self):
        first = self.approve(); changed = glossary(); changed['terms'][0]['definition'] = 'Explicitly stopping a queued operation.'
        second = self.approve(changed, first['record'])
        self.assertNotEqual(first['record'], second['record'])
        self.assertEqual(self.tools.glossary(self.a, 'PERSONAL', first['record'])['glossary'], first['glossary'])

    def test_project_update_does_not_silently_change_selected_source(self):
        first = self.approve(); attached = self.attach(first)
        context = attached['context_digest']
        changed = glossary(); changed['terms'][0]['definition'] = 'A different definition awaiting explicit selection.'
        self.approve(changed, first['record'])
        self.assertEqual(self.status()['context_digest'], context)

    def test_explicit_selection_is_an_authoritative_versioned_source(self):
        selected = self.approve(); status = self.attach(selected)
        source = status['context']['sources']['GLOSSARY-' + str(selected['record'])]
        self.assertEqual(source['kind'], 'reference')
        self.assertTrue(source['authority'].startswith('operator:'))
        self.assertIn('local:glossary:PERSONAL:', source['locator'])
        self.assertTrue(self.c.verify(self.a, 'REQ1')['valid'])

    def test_author_cannot_attach_approved_glossary(self):
        selected = self.approve()
        with self.assertRaises(ValidationError):
            self.tools.attach_glossary(self.a, 'REQ1', self.version(), selected['record'], selected['digest'])

    def test_glossary_from_another_project_is_rejected(self):
        selected = self.tools.approve_glossary(self.o, 'OTHER', glossary(), 0)
        with self.assertRaises(ValidationError): self.attach(selected)

    def test_wrong_revision_digest_is_rejected(self):
        selected = self.approve(); selected['digest'] = '0' * 64
        with self.assertRaises(ValidationError): self.attach(selected)

    def test_duplicate_selection_is_rejected(self):
        selected = self.approve(); self.attach(selected)
        with self.assertRaises(ValidationError): self.attach(selected)

    def test_explicit_replace_retires_only_selected_old_glossary(self):
        first = self.approve(); self.attach(first)
        second = self.approve(expected=first['record'])
        result = self.attach(second, 'GLOSSARY-' + str(first['record']))
        self.assertNotIn('GLOSSARY-' + str(first['record']), result['context']['sources'])
        self.assertIn('GLOSSARY-' + str(second['record']), result['context']['sources'])
        self.assertIn('BRIEF', result['context']['sources'])

    def test_case_insensitive_alias_collision_is_rejected(self):
        value = glossary(); value['terms'].append({'id': 'OTHER', 'term': 'cancel', 'definition': 'A conflicting meaning.', 'aliases': []})
        with self.assertRaises(ValidationError): validate_glossary(value)

    @unittest.skipUnless(PARSER, 'official Gherkin parser is required')
    def test_attaching_glossary_invalidates_existing_draft_and_review(self):
        self.ready(); selected = self.approve(); self.attach(selected)
        self.assertTrue(self.status()['stale'])
        with self.assertRaises(ValidationError): self.c.plan(self.o, 'REQ1')


class QuestionnaireTests(unittest.TestCase):
    def setUp(self):
        self.questions = {qid: {'id': qid, 'text': 'Question ' + qid + '?', 'why': 'This changes an acceptance outcome.',
                               'impact': impact, 'state': 'open'} for qid, impact in [('Q1', 1), ('Q2', 5), ('Q3', 3)]}
        self.status = {'run': {'id': 'REQ1', 'version': 4}, 'context_digest': 'a' * 64,
                       'context': {'questions': self.questions, 'sources': {'PRIVATE': {'text': 'PRIVATE-SOURCE-MUST-NOT-LEAK'}}}}

    def test_impact_order_without_dependencies(self):
        self.assertEqual([q['id'] for q in question_order(self.questions)], ['Q2', 'Q3', 'Q1'])

    def test_prerequisites_precede_dependent_questions(self):
        order = [q['id'] for q in question_order(self.questions, {'Q2': ['Q1']})]
        self.assertLess(order.index('Q1'), order.index('Q2'))

    def test_cycles_are_rejected(self):
        with self.assertRaises(ValidationError): question_order(self.questions, {'Q1': ['Q2'], 'Q2': ['Q1']})

    def test_unknown_prerequisites_are_rejected(self):
        with self.assertRaises(ValidationError): question_order(self.questions, {'Q1': ['UNKNOWN']})

    def test_answered_prerequisites_do_not_block_order(self):
        self.questions['Q1']['state'] = 'answered'
        self.assertEqual(question_order(self.questions, {'Q2': ['Q1']})[0]['id'], 'Q2')

    def test_merge_targets_are_used(self):
        self.questions['Q1'].update(state='merged', target='Q3')
        order = [q['id'] for q in question_order(self.questions, {'Q2': ['Q1']})]
        self.assertEqual(order, ['Q3', 'Q2'])

    def test_merge_induced_self_dependency_is_rejected(self):
        self.questions['Q1'].update(state='merged', target='Q2')
        with self.assertRaises(ValidationError): question_order(self.questions, {'Q2': ['Q1']})

    def test_only_selected_questions_are_exported_without_private_sources(self):
        result = questionnaire(self.status, 'Business owner', 'Resolve cancellation behavior', ['Q2'], {'Q2': ['Q1']})
        self.assertIn('## Q2', result); self.assertNotIn('Question Q1?', result)
        self.assertIn('Resolve these decisions first: Q1', result)
        self.assertNotIn('PRIVATE-SOURCE-MUST-NOT-LEAK', result)
        self.assertIn(self.status['context_digest'], result)

    def test_answered_question_cannot_be_exported_as_open(self):
        self.questions['Q1']['state'] = 'answered'
        with self.assertRaises(ValidationError): questionnaire(self.status, 'Owner', 'Clarify a decision', ['Q1'])

    def test_export_does_not_mutate_workflow_context(self):
        before = copy.deepcopy(self.status)
        questionnaire(self.status, 'Owner', 'Clarify a decision', ['Q1', 'Q2'])
        self.assertEqual(self.status, before)
