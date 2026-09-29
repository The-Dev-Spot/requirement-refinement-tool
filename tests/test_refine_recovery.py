import copy
import json
from pathlib import Path

from clarity.backup import backup, restore
from clarity.guardrails import ValidationError, digest
from clarity.refine.controller import Controller
from clarity.refine.identity import provision
from clarity.storage import initialize, transaction
from test_refine_controller import Fixture


class RecoveryTests(Fixture):
    def test_refinement_backup_keeps_briefs_sources_questions_and_decisions(self):
        self.confirmed()
        self.c.ask(self.a, 'REQ1', self.version(), self.question())
        self.c.answer(self.o, 'REQ1', self.version(), 'Q1', 'Cancellation is permitted before the scheduled start.')
        saved = json.loads(json.dumps(backup(self.root, self.o), sort_keys=True))
        self.assertEqual(saved['data']['schema_version'], 2)
        self.assertNotIn(self.a, json.dumps(saved))
        self.assertNotIn(self.o, json.dumps(saved))
        target = self.root.parent / 'restored'
        restore(target, saved, saved['digest'])
        key = self.root.parent / 'restored.key'
        provision(target, 'new-operator', 'operator', key)
        restored = Controller(target)
        status = restored.status(key.read_text().strip(), 'REQ1')
        self.assertEqual(status['context']['questions']['Q1']['state'], 'answered')
        self.assertIn('POLICY1', status['context']['sources'])
        self.assertTrue(restored.verify(key.read_text().strip(), 'REQ1')['valid'])
        with self.assertRaises(ValidationError): restored.status(self.a, 'REQ1')

    def test_inner_chain_corruption_is_rejected_even_with_recomputed_envelope_digest(self):
        saved = backup(self.root, self.o)
        saved['data']['refinement']['refine_records'][0]['hash'] = '0' * 64
        saved['digest'] = digest(saved['data'])
        with self.assertRaises(ValidationError): restore(self.root.parent / 'bad', saved, saved['digest'])
        self.assertFalse((self.root.parent / 'bad').exists())

    def test_legacy_workspace_keeps_version_one_format(self):
        target = self.root.parent / 'legacy'; initialize(target)
        key = self.root.parent / 'legacy.key'; provision(target, 'legacy-operator', 'operator', key)
        saved = json.loads(json.dumps(backup(target, key.read_text().strip()), sort_keys=True))
        self.assertEqual(saved['data']['schema_version'], 1)
        self.assertNotIn('refinement', saved['data'])
        restore(self.root.parent / 'legacy-restored', saved, saved['digest'])

    def test_unknown_refinement_tables_cannot_be_silently_dropped(self):
        with transaction(self.root) as db: db.execute('CREATE TABLE refine_future(value TEXT)')
        with self.assertRaises(ValidationError): backup(self.root, self.o)

    def test_author_cannot_backup_other_actors_evidence(self):
        with self.assertRaises(ValidationError): backup(self.root, self.a)

    def test_failed_restore_has_no_partial_evidence_commit(self):
        saved = backup(self.root, self.o)
        saved['data']['refinement']['refine_runs'][0]['invented_column'] = True
        saved['digest'] = digest(saved['data'])
        target = self.root.parent / 'failed'
        with self.assertRaises(ValidationError): restore(target, saved, saved['digest'])
        with transaction(target) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM refine_runs').fetchone()[0], 0)
            self.assertEqual(db.execute('SELECT count(*) FROM credentials').fetchone()[0], 0)
