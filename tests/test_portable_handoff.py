import hashlib
import io
import json
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from clarity.guardrails import ValidationError
from clarity.refine.__main__ import main
from clarity.refine.portable import portable_archive
from refine_fixtures import assessment
from test_refine_controller import Fixture, PARSER


@unittest.skipUnless(PARSER, 'official Gherkin parser is required')
class PortableHandoffTests(Fixture):
    def sealed(self, crlf=False):
        if crlf:
            value = self.confirmed(); value['feature'] = value['feature'].replace('\r\n', '\n').replace('\n', '\r\n')
            self.c.submit(self.a, 'REQ1', self.version(), value)
            result = self.c.review(self.r, 'REQ1', self.version(), assessment(value))
            self.assertEqual(result['review']['quality']['verdict'], 'READY')
        else:
            self.ready()
        plan = self.c.plan(self.o, 'REQ1')
        approval = self.c.approve(self.o, 'REQ1', self.version(), plan['plan_digest'])
        return self.c.seal(self.o, 'REQ1', approval['approval_id'])

    def test_portable_view_contains_only_delivery_and_integrity_metadata(self):
        bundle = self.sealed()
        with zipfile.ZipFile(io.BytesIO(portable_archive(bundle))) as archive:
            self.assertEqual(set(archive.namelist()), {'requirement.md', 'acceptance.feature', 'handoff.json'})
            metadata = json.loads(archive.read('handoff.json'))
            self.assertEqual(metadata['kind'], 'clarity-portable-handoff')
            self.assertEqual(metadata['plan_digest'], bundle['plan_digest'])
            self.assertEqual(metadata['revision'], bundle['plan']['revision'])
            self.assertNotIn('approval', metadata); self.assertNotIn('actor', metadata)
            self.assertNotIn('sources', metadata); self.assertNotIn('execution_authority', metadata)
            for name, value in metadata['files'].items():
                self.assertEqual(hashlib.sha256(archive.read(name)).hexdigest(), value)
            trace = json.loads(bundle['files']['traceability.json'])
            self.assertEqual(metadata['scenario_ids'], sorted(s['id'] for s in trace['scenario_mappings']))

    def test_feature_crlf_bytes_are_unchanged(self):
        bundle = self.sealed(crlf=True)
        with zipfile.ZipFile(io.BytesIO(portable_archive(bundle))) as archive:
            original = bundle['files']['acceptance.feature'].encode('utf-8')
            self.assertIn(b'\r\n', original)
            self.assertEqual(archive.read('acceptance.feature'), original)

    def test_portable_view_is_repeatable_and_does_not_mutate_seal(self):
        bundle = self.sealed(); before = json.dumps(bundle, sort_keys=True)
        self.assertEqual(portable_archive(bundle), portable_archive(bundle))
        self.assertEqual(json.dumps(bundle, sort_keys=True), before)
        self.assertTrue(self.c.verify(self.a, 'REQ1')['valid'])

    def test_changed_sealed_payload_is_rejected(self):
        bundle = self.sealed(); bundle['files']['requirement.md'] += '\nAltered'
        with self.assertRaises(ValidationError): portable_archive(bundle)

    def test_unsealed_requirement_cannot_be_exported_by_cli(self):
        output = Path(self.tmp.name) / 'portable.zip'
        with patch('sys.stderr', new=io.StringIO()):
            code = main(['--state', str(self.root), 'portable', '--id', 'REQ1', '--approval', '999',
                         '--key-file', str(Path(self.tmp.name) / 'writer.key'), '--output', str(output)])
        self.assertEqual(code, 2); self.assertFalse(output.exists())

    def test_cli_reads_existing_seal_without_reapproving_or_dispatching(self):
        bundle = self.sealed(); output = Path(self.tmp.name) / 'portable.zip'
        before = self.version()
        with patch('sys.stdout', new=io.StringIO()):
            code = main(['--state', str(self.root), 'portable', '--id', 'REQ1', '--approval', str(bundle['approval']['id']),
                         '--key-file', str(Path(self.tmp.name) / 'writer.key'), '--output', str(output)])
        self.assertEqual(code, 0); self.assertEqual(self.version(), before)
        self.assertEqual(output.read_bytes(), portable_archive(bundle))
