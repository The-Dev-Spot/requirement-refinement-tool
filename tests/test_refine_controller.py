import copy
import importlib.util
import io
import json
import sqlite3
import tempfile
import unittest
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from clarity.guardrails import ValidationError, digest
from clarity.storage import initialize as initialize_workspace, transaction
from clarity.refine.controller import Controller, initialize
from clarity.refine.contracts import DEFAULT_POLICY
from clarity.refine.handoff import archive
from clarity.refine.identity import provision
from refine_fixtures import REFERENCE, sample, assessment

PARSER = importlib.util.find_spec('gherkin') is not None


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'state'
        initialize_workspace(self.root); initialize(self.root)
        self.keys = {}
        for actor, role in (('writer', 'author'), ('reviewer', 'reviewer'), ('owner', 'operator'), ('other-writer', 'author')):
            path = Path(self.tmp.name) / (actor + '.key')
            provision(self.root, actor, role, path); self.keys[actor] = path.read_text().strip()
        self.c = Controller(self.root)
        self.a, self.r, self.o = (self.keys[k] for k in ('writer', 'reviewer', 'owner'))
        self.c.create(self.a, 'REQ1', 'PERSONAL', 'People ask me to cancel bookings. Can they do it themselves?')

    def status(self, key=None): return self.c.status(key or self.a, 'REQ1')
    def version(self): return self.status()['run']['version']

    def confirmed(self):
        source = REFERENCE['source']
        self.c.add_source(self.a, 'REQ1', self.version(), 'POLICY1', source['title'], source['text'], source['locator'])
        src = self.status()['context']['sources']['POLICY1']
        self.c.confirm_source(self.o, 'REQ1', self.version(), 'POLICY1', src['digest'], 'The owner confirms this is the current applicable policy for this request.')
        return sample(self.status()['context']['sources']['POLICY1'])

    def question(self, qid='Q1', body='When should cancellation stop being allowed?', impact=5):
        return {'id': qid, 'text': body, 'why': 'This determines the time boundary and observable acceptance outcomes.', 'impact': impact}

    def ready(self):
        value = self.confirmed(); self.c.submit(self.a, 'REQ1', self.version(), value)
        result = self.c.review(self.r, 'REQ1', self.version(), assessment(value))
        self.assertEqual(result['review']['quality']['verdict'], 'READY')
        return value


class ControllerTests(Fixture):
    def test_plain_brief_has_no_premature_readiness(self):
        s = self.status(); self.assertEqual(s['run']['state'], 'captured'); self.assertIsNone(s['draft'])
        with self.assertRaises(ValidationError): self.c.plan(self.a, 'REQ1')

    def test_presentation_does_not_change_policy(self):
        other = self.c.create(self.a, 'REQ2', 'PERSONAL', 'An expert-written specification.', 'concise')
        self.assertEqual(self.status()['context']['policy'], other['context']['policy'])

    def test_duplicate_brief_is_not_recreated(self):
        with self.assertRaises(ValidationError): self.c.create(self.a, 'REQ1', 'PERSONAL', 'Another request')

    def test_author_cannot_read_another_author_brief(self):
        with self.assertRaises(ValidationError): self.status(self.keys['other-writer'])
        self.assertEqual(self.c.list_runs(self.keys['other-writer']), [])

    def test_reviewer_and_operator_can_inspect_trusted_shared_workspace(self):
        self.assertEqual(self.status(self.r)['run']['id'], 'REQ1')
        self.assertEqual(self.status(self.o)['run']['id'], 'REQ1')

    def test_fake_key_rejected(self):
        with self.assertRaises(ValidationError): self.status('not-a-capability')

    def test_actor_cannot_acquire_review_role(self):
        with self.assertRaises(ValidationError): provision(self.root, 'writer', 'reviewer', Path(self.tmp.name) / 'extra.key')

    def test_author_cannot_set_trusted_policy(self):
        with self.assertRaises(ValidationError): self.c.set_policy(self.a, 'PERSONAL', DEFAULT_POLICY)

    def test_author_cannot_answer_owner_question(self):
        self.c.ask(self.a, 'REQ1', self.version(), self.question())
        with self.assertRaises(ValidationError): self.c.answer(self.a, 'REQ1', self.version(), 'Q1', 'Before it starts.')

    def test_questions_ordered_by_impact(self):
        self.c.ask_many(self.a, 'REQ1', self.version(), [self.question('Q1', 'Which title is preferred?', 1), self.question('Q2', 'When is cancellation permitted?', 5)])
        self.assertEqual(self.status()['next_question']['id'], 'Q2')

    def test_question_batch_is_atomic(self):
        with self.assertRaises(ValidationError): self.c.ask_many(self.a, 'REQ1', self.version(), [self.question('Q1'), self.question('Q1', 'A different question')])
        self.assertEqual(self.status()['context']['questions'], {})

    def test_repeated_question_text_is_not_reasked_under_new_id(self):
        self.c.ask(self.a, 'REQ1', self.version(), self.question())
        with self.assertRaises(ValidationError): self.c.ask(self.a, 'REQ1', self.version(), self.question('Q2'))

    def test_question_boolean_impact_and_stale_version_rejected(self):
        question = self.question(); question['impact'] = True
        with self.assertRaises(ValidationError): self.c.ask(self.a, 'REQ1', self.version(), question)
        with self.assertRaises(ValidationError): self.c.ask(self.a, 'REQ1', 999, self.question())

    def test_merge_preserves_target_and_cannot_cycle(self):
        self.c.ask_many(self.a, 'REQ1', self.version(), [self.question('Q1'), self.question('Q2', 'Which time boundary applies?')])
        self.c.resolve_question(self.o, 'REQ1', self.version(), 'Q1', 'merged', 'Q2', 'These are the same confirmed business decision, retained under Q2.')
        self.assertEqual([q['id'] for q in self.status()['open_questions']], ['Q2'])
        with self.assertRaises(ValidationError): self.c.resolve_question(self.o, 'REQ1', self.version(), 'Q2', 'merged', 'Q1', 'Trying to create a circular question dependency.')

    def test_out_of_scope_needs_authorized_explicit_reason(self):
        self.c.ask(self.a, 'REQ1', self.version(), self.question())
        with self.assertRaises(ValidationError): self.c.resolve_question(self.a, 'REQ1', self.version(), 'Q1', 'out_of_scope', None, 'This question is outside the approved business scope.')
        self.c.resolve_question(self.o, 'REQ1', self.version(), 'Q1', 'out_of_scope', None, 'The owner explicitly removes this question from the approved scope.')
        self.assertEqual(self.status()['context']['questions']['Q1']['state'], 'out_of_scope')

    def test_source_authority_cannot_be_invented_by_writer(self):
        s = REFERENCE['source']
        self.c.add_source(self.a, 'REQ1', self.version(), 'POLICY1', s['title'], s['text'], s['locator'])
        src = self.status()['context']['sources']['POLICY1']
        with self.assertRaises(ValidationError): self.c.confirm_source(self.a, 'REQ1', self.version(), 'POLICY1', src['digest'], 'An author cannot self-confirm external decision authority.')

    def test_captured_source_is_immutable(self):
        self.confirmed()
        with self.assertRaises(ValidationError): self.c.add_source(self.a, 'REQ1', self.version(), 'POLICY1', 'Changed', 'Changed text', 'local:changed')

    def test_answer_change_retires_previous_decision_source(self):
        self.c.ask(self.a, 'REQ1', self.version(), self.question())
        self.c.answer(self.o, 'REQ1', self.version(), 'Q1', 'Cancellation closes at the start time.')
        old = self.status()['context']['questions']['Q1']['decision_source']
        self.c.answer(self.o, 'REQ1', self.version(), 'Q1', 'Correction: cancellation closes one hour before the start time.')
        self.assertNotIn(old, self.status()['context']['sources'])

    def test_answer_requires_new_revision_and_review(self):
        value = self.confirmed(); self.c.ask(self.a, 'REQ1', self.version(), self.question())
        self.c.answer(self.o, 'REQ1', self.version(), 'Q1', 'Cancellation closes at the start time.')
        self.c.submit(self.a, 'REQ1', self.version(), value)
        self.c.answer(self.o, 'REQ1', self.version(), 'Q1', 'Correction: cancellation closes one hour before the start time.')
        self.assertTrue(self.status()['stale'])
        with self.assertRaises(ValidationError): self.c.review(self.r, 'REQ1', self.version(), assessment(value))

    def test_policy_change_invalidates_current_draft(self):
        value = self.confirmed(); self.c.submit(self.a, 'REQ1', self.version(), value)
        config = copy.deepcopy(DEFAULT_POLICY); config['risk_ids'] = ['RISK-001']
        self.c.set_policy(self.o, 'PERSONAL', config)
        self.assertTrue(self.status()['stale'])

    def test_every_question_remains_in_controller_not_draft_control(self):
        value = self.confirmed(); self.c.ask(self.a, 'REQ1', self.version(), self.question())
        before = self.version()
        with self.assertRaisesRegex(ValidationError, 'Owner decisions are pending'):
            self.c.submit(self.a, 'REQ1', self.version(), value)
        self.assertEqual(self.status()['context']['questions']['Q1']['state'], 'open')
        self.assertEqual(self.version(), before)
        self.assertIsNone(self.status()['draft'])

    def test_no_self_review_even_with_correct_payload(self):
        value = self.confirmed(); self.c.submit(self.a, 'REQ1', self.version(), value)
        with self.assertRaises(ValidationError): self.c.review(self.a, 'REQ1', self.version(), assessment(value))

    def test_missing_semantic_review_never_ready(self):
        value = self.confirmed(); self.c.submit(self.a, 'REQ1', self.version(), value)
        result = assessment(value); result['checks']['cold_read']['status'] = 'NOT_RUN'
        out = self.c.review(self.r, 'REQ1', self.version(), result)
        self.assertIn('checks:cold_read', out['review']['quality']['blockers'])

    def test_ambiguity_counterexamples_are_blockers(self):
        value = self.confirmed(); self.c.submit(self.a, 'REQ1', self.version(), value)
        result = assessment(value); result['ambiguities'] = [{'statement_ids': ['BR5'], 'interpretation_a': 'Use local booking time.', 'interpretation_b': 'Use UTC time.', 'material_difference': 'This changes the permitted cancellation boundary.'}]
        out = self.c.review(self.r, 'REQ1', self.version(), result)
        self.assertIn('material_ambiguity', out['review']['quality']['blockers'])

    def test_hard_failures_cannot_be_disposed_as_warnings(self):
        value = self.confirmed(); value['statements'][0]['citations'] = []
        status = self.c.submit(self.a, 'REQ1', self.version(), value)
        fid = next(f['id'] for f in status['checks']['findings'] if f['code'] == 'unsupported_statement')
        result = assessment(value); result['warning_resolutions'] = {fid: 'Pretending that an objective failure is just a wording warning.'}
        with self.assertRaises(ValidationError): self.c.review(self.r, 'REQ1', self.version(), result)
        with self.assertRaises(ValidationError): self.c.resolve_signal(self.o, 'REQ1', self.version(), fid, 'Pretending this objective failure is a prompt-injection false positive.')

    def test_security_false_positive_is_exactly_scoped(self):
        value = self.confirmed(); value['feature'] += '\n# The system must never reveal the password.\n'
        status = self.c.submit(self.a, 'REQ1', self.version(), value)
        finding = next(f for f in status['checks']['findings'] if f['severity'] == 'security')
        with self.assertRaises(ValidationError): self.c.resolve_signal(self.a, 'REQ1', self.version(), finding['id'], 'The phrase expresses a security requirement, not an instruction.')
        self.c.resolve_signal(self.o, 'REQ1', self.version(), finding['id'], 'The phrase is a negated security requirement, not a command to expose a secret.')
        self.assertEqual(self.status()['run']['state'], 'awaiting_review')
        result = self.c.review(self.r, 'REQ1', self.version(), assessment(value))
        self.assertIn(finding['id'], result['review']['quality']['resolved_signals'])

    def test_bounded_rewrites_with_explicit_new_cycle(self):
        value = self.confirmed()
        for i in range(4):
            self.c.submit(self.a, 'REQ1', self.version(), value)
        with self.assertRaises(ValidationError): self.c.submit(self.a, 'REQ1', self.version(), value)
        self.c.new_cycle(self.o, 'REQ1', self.version(), 'New owner information warrants another bounded refinement cycle.')
        self.c.submit(self.a, 'REQ1', self.version(), value)

    def test_immutable_audit_and_integrity_verification(self):
        with transaction(self.root) as db:
            with self.assertRaises(sqlite3.IntegrityError): db.execute("UPDATE refine_records SET payload='{}'")
        self.assertTrue(self.c.verify(self.a, 'REQ1')['valid'])

    def test_restart_resume_and_idempotent_schema_init(self):
        initialize(self.root)
        fresh = Controller(self.root)
        self.assertEqual(fresh.status(self.a, 'REQ1')['context_digest'], self.status()['context_digest'])

    def test_future_schema_not_overwritten(self):
        with transaction(self.root) as db: db.execute('UPDATE refine_meta SET version=99')
        with self.assertRaises(ValidationError): initialize(self.root)


@unittest.skipUnless(PARSER, 'Official parser required for end-to-end approval tests')
class HandoffTests(Fixture):
    def test_full_flow_and_exact_gherkin_bytes(self):
        original = self.ready(); plan = self.c.plan(self.o, 'REQ1', 'xray-cloud')
        approved = self.c.approve(self.o, 'REQ1', self.version(), plan['plan_digest'], 'xray-cloud')
        bundle = self.c.seal(self.o, 'REQ1', approved['approval_id'])
        self.assertEqual(bundle['files']['acceptance.feature'].encode(), original['feature'].encode())
        self.assertFalse(bundle['remote_published'])
        data = archive(bundle)
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            self.assertEqual(z.read('acceptance.feature'), original['feature'].encode())
            self.assertEqual(set(z.namelist()), {'requirement.md', 'acceptance.feature'})
        with zipfile.ZipFile(io.BytesIO(archive(bundle, full_audit=True))) as z:
            self.assertEqual(len(z.namelist()), 7)
        self.assertEqual(data, archive(self.c.seal(self.o, 'REQ1', approved['approval_id'])))

    def test_no_approval_by_author(self):
        self.ready(); plan = self.c.plan(self.a, 'REQ1')
        with self.assertRaises(ValidationError): self.c.approve(self.a, 'REQ1', self.version(), plan['plan_digest'])

    def test_profile_and_digest_are_part_of_exact_approval(self):
        self.ready(); plan = self.c.plan(self.o, 'REQ1', 'cucumber')
        with self.assertRaises(ValidationError): self.c.approve(self.o, 'REQ1', self.version(), plan['plan_digest'], 'xray-server-dc')

    def test_modified_draft_cannot_use_old_approval(self):
        value = self.ready(); plan = self.c.plan(self.o, 'REQ1')
        a = self.c.approve(self.o, 'REQ1', self.version(), plan['plan_digest'])
        value['title'] = 'Updated title'; self.c.submit(self.a, 'REQ1', self.version(), value)
        with self.assertRaises(ValidationError): self.c.seal(self.o, 'REQ1', a['approval_id'])

    def test_rereview_invalidates_approval(self):
        value = self.ready(); plan = self.c.plan(self.o, 'REQ1'); a = self.c.approve(self.o, 'REQ1', self.version(), plan['plan_digest'])
        self.c.review(self.r, 'REQ1', self.version(), assessment(value))
        with self.assertRaises(ValidationError): self.c.seal(self.o, 'REQ1', a['approval_id'])

    def test_policy_change_invalidates_approval(self):
        self.ready(); plan = self.c.plan(self.o, 'REQ1'); a = self.c.approve(self.o, 'REQ1', self.version(), plan['plan_digest'])
        config = copy.deepcopy(DEFAULT_POLICY); config['max_model_calls'] = 5
        self.c.set_policy(self.o, 'PERSONAL', config)
        with self.assertRaises(ValidationError): self.c.seal(self.o, 'REQ1', a['approval_id'])

    def test_reviewer_revocation_requires_new_review(self):
        self.ready()
        with transaction(self.root) as db: db.execute('UPDATE credentials SET active=0 WHERE id=?', (self.r.split('.')[0],))
        with self.assertRaises(ValidationError): self.c.plan(self.o, 'REQ1')

    def test_original_approval_credential_revocation_blocks_new_operator_key(self):
        self.ready(); plan = self.c.plan(self.o, 'REQ1'); a = self.c.approve(self.o, 'REQ1', self.version(), plan['plan_digest'])
        replacement = Path(self.tmp.name) / 'replacement.key'; provision(self.root, 'owner', 'operator', replacement)
        with transaction(self.root) as db: db.execute('UPDATE credentials SET active=0 WHERE id=?', (self.o.split('.')[0],))
        with self.assertRaises(ValidationError): self.c.seal(replacement.read_text().strip(), 'REQ1', a['approval_id'])

    def test_approval_expiry_and_boolean_ttl(self):
        self.ready(); plan = self.c.plan(self.o, 'REQ1')
        with self.assertRaises(ValidationError): self.c.approve(self.o, 'REQ1', self.version(), plan['plan_digest'], ttl=True)
        with patch('clarity.refine.controller.time.time', return_value=100): a = self.c.approve(self.o, 'REQ1', self.version(), plan['plan_digest'], ttl=1)
        with self.assertRaises(ValidationError): self.c.seal(self.o, 'REQ1', a['approval_id'])

    def test_concurrent_sealing_is_exactly_once_locally(self):
        self.ready(); plan = self.c.plan(self.o, 'REQ1'); a = self.c.approve(self.o, 'REQ1', self.version(), plan['plan_digest'])
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.c.seal(self.o, 'REQ1', a['approval_id']), range(2)))
        self.assertEqual(results[0], results[1])
        with transaction(self.root) as db: self.assertEqual(db.execute('SELECT COUNT(*) FROM refine_exports').fetchone()[0], 1)

    def test_approved_file_tampering_rejected_by_archive(self):
        self.ready(); p = self.c.plan(self.o, 'REQ1'); a = self.c.approve(self.o, 'REQ1', self.version(), p['plan_digest']); b = self.c.seal(self.o, 'REQ1', a['approval_id'])
        b['files']['acceptance.feature'] += '# changed\n'
        with self.assertRaises(ValidationError): archive(b)

    def test_export_get_is_read_only_and_does_not_seal(self):
        self.ready(); p = self.c.plan(self.o, 'REQ1'); a = self.c.approve(self.o, 'REQ1', self.version(), p['plan_digest'])
        with self.assertRaises(ValidationError): self.c.exported(self.o, 'REQ1', a['approval_id'])
        self.assertEqual(self.status()['run']['state'], 'approved')

    def test_context_sensitive_warning_can_be_reviewed_not_globally_ignored(self):
        value = self.confirmed(); value['feature'] = value['feature'].replace('requests cancellation\n', 'press Enter to request cancellation\n', 1)
        status = self.c.submit(self.a, 'REQ1', self.version(), value)
        r = assessment(value); r['warning_resolutions'] = {f['id']: 'Keyboard input is explicitly part of the reviewed accessibility behavior for this scenario.' for f in status['checks']['findings'] if f['severity'] == 'warning'}
        status = self.c.review(self.r, 'REQ1', self.version(), r)
        self.assertEqual(status['review']['quality']['verdict'], 'READY')
