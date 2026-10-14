"""Regression coverage for configuration, assistant scope and local app workflows."""
import copy
import io
import json
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from clarity.guardrails import ValidationError, digest
from clarity.storage import transaction
from clarity.workspace import Workspace, initialize
from clarity.host_bridge import packet, submit, serve
from clarity.jobs import Jobs
from clarity.backup import backup, restore
from clarity.backup_crypto import encrypt, decrypt
from clarity.installation import setup, doctor
from clarity.refine.worker import run_stage
from clarity.refine.checks import feature_index as feature
from clarity.refine.contracts import DEFAULT_POLICY
from test_refine_controller import Fixture
import test_refine_worker_web as web_tests

MODEL = {'provider': 'ollama', 'model': 'local-test', 'port': 11434, 'max_tokens': 8192, 'timeout': 120, 'keep_alive': 300, 'allow_cloud': False, 'enabled': True}
SOURCE = {'project': 'PERSONAL', 'title': 'Local policy', 'text': 'Only the owner can cancel a booking before its start time.', 'locator': 'local:policy', 'revision': '1', 'effective_date': '2026-10-01', 'retrieved_at': 1.0}


class WorkspaceTests(Fixture):
    def setUp(self):
        super().setUp(); initialize(self.root); self.w = Workspace(self.root)

    def test_operator_only_configuration_and_version_conflicts(self):
        with self.assertRaises(ValidationError): self.w.save(self.a, 'model', 'LOCAL', 0, MODEL)
        self.w.save(self.o, 'model', 'LOCAL', 0, MODEL)
        version = self.w.records(self.a, 'model')[0]['version']
        with self.assertRaises(ValidationError): self.w.save(self.o, 'model', 'LOCAL', 0, MODEL)
        self.w.save(self.o, 'model', 'LOCAL', version, {**MODEL, 'enabled': False})
        with self.assertRaises(ValidationError): self.w.provider(self.a, 'LOCAL')

    def test_credentials_encrypted_and_never_returned_to_views(self):
        credential = 'synthetic-test-key-with-no-provider-access'
        self.w.save(self.o, 'model', 'CLOUD', 0, {**MODEL, 'provider': 'openai', 'allow_cloud': True}, credential)
        with transaction(self.root, write=False) as db:
            raw = db.execute('SELECT ciphertext FROM workspace_secrets').fetchone()[0]
            records = db.execute('SELECT payload FROM workspace_records').fetchone()[0]
        self.assertNotIn(credential.encode(), raw); self.assertNotIn(credential, records)
        shown = self.w.records(self.a, 'model')[0]
        self.assertTrue(shown['secret_present']); self.assertNotIn('secret_id', shown)
        self.assertNotIn(credential, json.dumps(shown))
        data, version = self.w.get(self.o, 'model', 'CLOUD')
        self.assertEqual(self.w.secret(data['secret_id']), credential)
        data.pop('secret_id'); self.w.save(self.o, 'model', 'CLOUD', version, data)
        data, _ = self.w.get(self.o, 'model', 'CLOUD')
        self.assertEqual(self.w.secret(data['secret_id']), credential)
        self.assertEqual((self.root / 'vault.key').stat().st_mode & 0o777, 0o600)

    def test_cloud_sharing_must_be_explicit(self):
        with self.assertRaises(ValidationError): self.w.save(self.o, 'model', 'CLOUD', 0, {**MODEL, 'provider': 'openai'})

    def test_source_versions_attach_and_replace_without_erasing_history(self):
        self.w.save(self.a, 'source', 'SRC1', 0, SOURCE)
        version = self.w.records(self.a, 'source')[0]['version']
        self.w.attach(self.a, 'REQ1', self.version(), 'SRC1')
        old = 'SRC1-' + str(version)
        self.w.save(self.a, 'source', 'SRC1', version, {**SOURCE, 'text': SOURCE['text'] + ' A changed policy applies.', 'revision': '2'})
        self.w.attach(self.a, 'REQ1', self.version(), 'SRC1', old)
        sources = self.status()['context']['sources']
        self.assertNotIn(old, sources)
        self.assertEqual(len([s for s in sources.values() if s['kind'] == 'reference']), 1)
        self.assertIn('source_superseded', [e['kind'] for e in self.status()['events']])
        self.assertTrue(self.c.verify(self.a, 'REQ1'))

    def test_cross_project_attachment_rejected(self):
        self.w.save(self.a, 'source', 'SRC1', 0, {**SOURCE, 'project': 'OTHER'})
        with self.assertRaises(ValidationError): self.w.attach(self.a, 'REQ1', self.version(), 'SRC1')

    def test_invalid_dates_and_arbitrary_tenant_hosts_rejected(self):
        with self.assertRaises(ValidationError): self.w.save(self.a, 'source', 'SRC1', 0, {**SOURCE, 'effective_date': 'yesterday'})
        for host in ('127.0.0.1', 'example.com', 'https://' + 'demo.atlassian.net', 'demo.atlassian.net/path'):
            value = {'provider': 'jira-cloud', 'host': host, 'username': 'user@example.invalid', 'scope': 'DEMO', 'project_scope': '', 'enabled': True}
            with self.assertRaises(ValidationError): self.w.save(self.o, 'connection', 'JIRA', 0, value)

    def test_backup_keeps_configuration_but_excludes_credentials_and_requires_fresh_keys(self):
        self.w.save(self.o, 'model', 'CLOUD', 0, {**MODEL, 'provider': 'openai', 'allow_cloud': True}, 'secret-for-test')
        envelope = backup(self.root, self.o)
        self.assertEqual(envelope['data']['schema_version'], 3)
        self.assertNotIn('workspace_secrets', envelope['data']['workspace'])
        dest = Path(self.tmp.name) / 'restored'; restore(dest, envelope, envelope['digest'])
        with transaction(dest, write=False) as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM workspace_secrets').fetchone()[0], 0)
            self.assertEqual(db.execute('SELECT SUM(active) FROM credentials').fetchone()[0], 0)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM workspace_records').fetchone()[0], 1)

    def test_encrypted_backup_authentication(self):
        data = backup(self.root, self.o); encrypted = encrypt(data, 'a long synthetic passphrase')
        self.assertEqual(decrypt(encrypted, 'a long synthetic passphrase'), data)
        self.assertNotIn('credential_bindings', json.dumps(encrypted))
        with self.assertRaises(ValidationError): decrypt(encrypted, 'a different long passphrase')
        encrypted['ciphertext'] = encrypted['ciphertext'][:-4] + 'AAAA'
        with self.assertRaises(ValidationError): decrypt(encrypted, 'a long synthetic passphrase')

    def test_probe_uses_synthetic_context_and_records_exact_profile_version(self):
        self.w.save(self.o, 'model', 'LOCAL', 0, MODEL)
        version = self.w.records(self.o, 'model')[0]['version']
        provider = web_tests.FakeProvider({'ready': True})
        with patch.object(self.w, 'provider', return_value=provider): self.w.probe(self.o, 'LOCAL', version)
        self.assertNotIn('REQ1', json.dumps(provider.packet))
        self.assertNotIn(self.status()['run']['brief'], json.dumps(provider.packet))
        self.assertEqual(self.w.records(self.o, 'check')[0]['connection_version'], version)

    def test_read_transaction_cannot_write(self):
        with transaction(self.root, write=False) as db:
            with self.assertRaises(Exception): db.execute("UPDATE credentials SET active=0")


class BridgeTests(Fixture):
    def test_bridge_scoped_role_has_no_operator_tool_or_credentials(self):
        task = packet(self.c, self.a, 'REQ1')
        self.assertNotIn(self.a, json.dumps(task)); self.assertIn('system', task)
        path = Path(self.tmp.name) / 'writer.key'
        messages = [{'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': '2025-11-25'}}, {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'}]
        out = io.StringIO(); serve(self.root, path, 'REQ1', io.StringIO('\n'.join(map(json.dumps, messages))), out)
        tools = json.loads(out.getvalue().splitlines()[1])['result']['tools']
        self.assertEqual([t['name'] for t in tools], ['clarity_get_task', 'clarity_submit_result'])
        with self.assertRaises(ValidationError): packet(self.c, self.o, 'REQ1')

    def test_stale_policy_rejects_assistant_result_atomically(self):
        task = packet(self.c, self.a, 'REQ1')
        self.c.set_policy(self.o, 'PERSONAL', {**DEFAULT_POLICY, 'risk_ids': ['RISK1']})
        with self.assertRaises(ValidationError): submit(self.c, self.a, 'REQ1', task['expected_version'], task['context_digest'], {'questions': [self.question()], 'draft': None})
        self.assertEqual(self.status()['open_questions'], [])

    def test_assistant_question_workflow_stays_unapproved(self):
        task = packet(self.c, self.a, 'REQ1')
        result = submit(self.c, self.a, 'REQ1', task['expected_version'], task['context_digest'], {'questions': [self.question()], 'draft': None})
        self.assertEqual(result['run']['state'], 'awaiting_decision')
        self.assertNotIn('approval', [e['kind'] for e in result['events']])

    def test_oversized_packet_does_not_consume_call(self):
        for i in range(2): self.c.add_source(self.a, 'REQ1', self.version(), 'BIG' + str(i), 'Large reference', 'x' * 99000, 'local:large')
        provider = web_tests.FakeProvider(error=True)
        with self.assertRaises(ValidationError): run_stage(self.c, self.a, 'REQ1', self.version(), 'draft', provider)
        self.assertEqual(self.status()['run']['calls'], 0); self.assertIsNone(provider.packet)

    def test_policy_change_during_inference_rejects_result(self):
        c, o = self.c, self.o
        class Provider:
            name = 'synthetic'
            def complete(_, system, payload):
                c.set_policy(o, 'PERSONAL', {**DEFAULT_POLICY, 'risk_ids': ['RISK1']})
                return {'questions': [self.question()], 'draft': None}
        with self.assertRaises(ValidationError): run_stage(self.c, self.a, 'REQ1', self.version(), 'draft', Provider())
        self.assertEqual(self.status()['open_questions'], [])


class JobsTests(Fixture):
    def setUp(self):
        super().setUp(); initialize(self.root); self.jobs = Jobs(self.root); self.addCleanup(self.jobs.close)

    def test_background_cancellation_discards_inflight_result_and_blocks_duplicate(self):
        entered = threading.Event(); release = threading.Event()
        question = self.question()
        class Provider:
            name = 'synthetic'
            def complete(_, system, payload): entered.set(); release.wait(5); return {'questions': [question], 'draft': None}
        job = self.jobs.start(self.a, 'REQ1', self.version(), 'draft', Provider())
        self.assertTrue(entered.wait(3))
        try:
            with self.assertRaises(ValidationError): self.jobs.start(self.a, 'REQ1', self.version(), 'draft', Provider())
            self.jobs.cancel(self.a, job)
        finally: release.set()
        self.jobs.pool.shutdown(wait=True)
        self.assertEqual(self.jobs.list(self.a, 'REQ1')[0]['status'], 'cancelled')
        self.assertEqual(self.status()['open_questions'], [])
        self.assertEqual(self.status()['run']['calls'], 1)

    def test_interrupted_work_is_not_restarted(self):
        with transaction(self.root) as db: db.execute('INSERT INTO workspace_jobs VALUES(?,?,?,?,?,?,?,?)', ('old', 'REQ1', 'writer', 'draft', 'running', 1, 1, 'incomplete'))
        other = Jobs(self.root)
        try: self.assertEqual(other.list(self.a, 'REQ1')[0]['status'], 'interrupted')
        finally: other.close()


class HttpFixture(Fixture):
    def setUp(self):
        super().setUp()
        self.server = web_tests.Workbench(self.root, port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True); self.thread.start()
        self.addCleanup(self.close_server); self.cookie = None

    close_server = web_tests.WorkbenchTests.close_server
    request = web_tests.WorkbenchTests.request
    csrf = web_tests.WorkbenchTests.csrf
    login = web_tests.WorkbenchTests.login


class AppHttpTests(HttpFixture):
    def test_setup_pages_and_source_capture(self):
        _, _, body = self.login()
        for path in ('/settings', '/sources', '/help', '/projects', '/run/REQ1'):
            code, headers, content = self.request(path=path)
            self.assertEqual(code, 200, (path, content))
            self.assertIn('Clarity', content)
        fields = {k: str(v) for k, v in SOURCE.items() if k != 'retrieved_at'}
        result = self.request('POST', '/sources/save', {'csrf': self.csrf(body), 'id': 'SRC1', 'version': '0', **fields})
        self.assertEqual(result[0], 303, result[2])
        self.assertEqual(len(self.server.workspace.records(self.a, 'source')), 1)

    def test_author_cannot_save_model_configuration_through_http(self):
        _, _, body = self.login()
        data = {k: str(v).lower() if type(v) is bool else str(v) for k, v in MODEL.items()}
        result = self.request('POST', '/settings/model', {'csrf': self.csrf(body), 'id': 'LOCAL', 'version': '0', 'credential': '', **data})
        self.assertEqual(result[0], 400)

    def test_operator_can_save_and_view_masked_model(self):
        _, _, body = self.login(self.o)
        data = {k: str(v).lower() if type(v) is bool else str(v) for k, v in MODEL.items()}
        result = self.request('POST', '/settings/model', {'csrf': self.csrf(body), 'id': 'LOCAL', 'version': '0', 'credential': 'synthetic-secret', **data})
        self.assertEqual(result[0], 303, result[2])
        code, _, content = self.request(path='/settings')
        self.assertEqual(code, 200); self.assertIn('LOCAL', content); self.assertNotIn('synthetic-secret', content)

    def test_manual_assistant_result_checks_current_context(self):
        _, _, body = self.login(); task = packet(self.c, self.a, 'REQ1')
        data = {'csrf': self.csrf(body), 'version': task['expected_version'], 'context_digest': task['context_digest'], 'json': json.dumps({'questions': [self.question()], 'draft': None})}
        result = self.request('POST', '/run/REQ1/assistant', data)
        self.assertEqual(result[0], 303, result[2]); self.assertEqual(len(self.status()['open_questions']), 1)


class OutlineArgumentTests(unittest.TestCase):
    def outline(self, argument):
        return 'Feature: Table template\n  @case_SC1\n  Scenario Outline: Render a selected value\n    Given a selected record\n    When a user submits "<known>"\n' + argument + '\n    Then the record contains the selected value\n    Examples:\n      | known |\n      | ok    |\n'

    def test_missing_table_parameter_is_blocked(self):
        with self.assertRaises(ValidationError): feature(self.outline('      | field | <missing> |'))

    def test_missing_doc_string_parameter_is_blocked(self):
        with self.assertRaises(ValidationError): feature(self.outline('      """\n      {"value": "<missing>"}\n      """'))

    def test_defined_table_and_literal_markup_are_allowed(self):
        self.assertEqual(feature(self.outline('      | field | <known> |'))['compiled_cases'], 1)
        self.assertEqual(feature(self.outline('      """\n      <p>literal text</p>\n      """'))['compiled_cases'], 1)


class FullHttpJourneyTests(HttpFixture):
    def switch_role(self, token):
        _, _, body = self.request()
        self.request('POST', '/logout', {'csrf': self.csrf(body)})
        return self.login(token)

    def test_source_to_independent_review_approval_and_sealed_download(self):
        import zipfile
        from refine_fixtures import REFERENCE, sample, assessment
        _, _, body = self.login()
        source = REFERENCE['source']
        result = self.request('POST', '/run/REQ1/source', {'csrf': self.csrf(body), 'version': self.version(), 'source_id': 'POLICY1', 'title': source['title'], 'locator': source['locator'], 'text': source['text']})
        self.assertEqual(result[0], 303, result[2])
        _, _, body = self.switch_role(self.o)
        captured = self.status()['context']['sources']['POLICY1']
        result = self.request('POST', '/run/REQ1/confirm-source', {'csrf': self.csrf(body), 'version': self.version(), 'source_id': 'POLICY1', 'source_digest': captured['digest'], 'reason': 'The owner confirms this is the applicable current policy for this request.'})
        self.assertEqual(result[0], 303, result[2])
        _, _, body = self.switch_role(self.a)
        value = sample(self.status()['context']['sources']['POLICY1'])
        result = self.request('POST', '/run/REQ1/assistant', {'csrf': self.csrf(body), 'version': self.version(), 'context_digest': self.status()['context_digest'], 'json': json.dumps({'questions': [], 'draft': value})})
        self.assertEqual(result[0], 303, result[2])
        _, _, body = self.switch_role(self.r)
        result = self.request('POST', '/run/REQ1/assistant', {'csrf': self.csrf(body), 'version': self.version(), 'context_digest': self.status()['context_digest'], 'json': json.dumps(assessment(value))})
        self.assertEqual(result[0], 303, result[2]); self.assertEqual(self.status()['run']['state'], 'awaiting_approval')
        _, _, body = self.switch_role(self.o)
        plan = self.c.plan(self.o, 'REQ1', 'xray-cloud')
        result = self.request('POST', '/run/REQ1/approve', {'csrf': self.csrf(body), 'version': self.version(), 'profile': 'xray-cloud', 'plan_digest': plan['plan_digest']})
        self.assertEqual(result[0], 303, result[2])
        approval = [e['id'] for e in self.status()['events'] if e['kind'] == 'approval'][-1]
        result = self.request('POST', '/run/REQ1/seal', {'csrf': self.csrf(body), 'version': self.version(), 'approval_id': approval})
        self.assertEqual(result[0], 303, result[2]); self.assertEqual(self.status()['run']['state'], 'exported')
        # Binary response must retain exact approved feature bytes.
        import http.client
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port)
        conn.request('GET', result[1]['Location'], headers={'Cookie': self.cookie})
        response = conn.getresponse(); archive = response.read(); conn.close()
        self.assertEqual(response.status, 200)
        with zipfile.ZipFile(io.BytesIO(archive)) as bundle: self.assertEqual(bundle.read('acceptance.feature'), value['feature'].encode())

    def test_second_workbench_cannot_interrupt_the_first(self):
        from clarity.refine.web import Workbench
        with self.assertRaises(ValidationError): Workbench(self.root, port=0)
        self.assertEqual(self.request()[0], 200)


class EvaluationAndPilotTests(unittest.TestCase):
    def test_diverse_corpus_counts_every_missing_trial_by_group(self):
        from clarity.evaluation import evaluate
        root = Path(__file__).parents[1]
        corpus = json.loads((root / 'examples/quality-corpus.json').read_text())
        result = evaluate(corpus, [], trials=3)
        self.assertEqual(len({c['need_id'] for c in corpus['cases']}), 20)
        self.assertEqual(len(result['trials']), 180)
        self.assertTrue(all(g['expected'] == 60 and g['provided'] == 0 for g in result['groups'].values()))
        self.assertFalse(result['semantic_accuracy_measured'])

    def test_blind_packets_omit_model_and_input_style(self):
        from clarity.evaluation import evaluate, blind_packets
        corpus = json.loads((Path(__file__).parents[1] / 'examples/quality-corpus.json').read_text())
        runs = [{'case_id': corpus['cases'][0]['id'], 'trial': 1, 'model': 'PRIVATE-MODEL-LABEL', 'result': {'questions': [{'id': 'Q1', 'text': 'Which policy is applicable?', 'why': 'The policy changes the permitted behavior.', 'impact': 5}], 'draft': None}}]
        report = evaluate(corpus, runs, 1)
        self.assertEqual(sum(r['contract_passed'] for r in report['trials']), 1)
        with __import__('tempfile').TemporaryDirectory() as tmp:
            directory = Path(tmp) / 'blind'; blind_packets(corpus, runs, directory)
            text = next(directory.glob('B-*.json')).read_text()
            self.assertNotIn('PRIVATE-MODEL-LABEL', text); self.assertNotIn('input_style', text)
            self.assertTrue((directory / 'ratings.csv').exists())

    def test_pilot_requires_exact_hash_unique_complete_mapping_and_observations(self):
        import hashlib
        from clarity.handoff_check import verify
        feature_bytes = b'Feature: A choice\n @case_SC1\n Scenario: Confirm a choice\n  Given an available choice\n  When the user confirms it\n  Then the choice is recorded\n'
        receipt = {'edition': 'xray-cloud', 'project': 'DEMO', 'feature_sha256': hashlib.sha256(feature_bytes).hexdigest(), 'scenario_tests': {'SC1': 'DEMO-1'}, 'repeat_strategy': 'update-mapped-tests', 'observations': {key: 'NOT_RUN' for key in ('scenario_ids', 'outlines', 'backgrounds', 'tables_docstrings', 'requirement_links', 'repeat_import')}}
        result = verify(feature_bytes, receipt)
        self.assertFalse(result['receipt_complete']); self.assertFalse(result['remote_state_verified'])
        with self.assertRaises(ValidationError): verify(feature_bytes + b'\n', receipt)
        with self.assertRaises(ValidationError): verify(feature_bytes, {**receipt, 'scenario_tests': {}})


class BindingRegressionTests(Fixture):
    def setUp(self):
        super().setUp(); initialize(self.root); self.w = Workspace(self.root)

    def test_provider_change_does_not_reuse_another_service_credential(self):
        self.w.save(self.o, 'model', 'MODEL', 0, {**MODEL, 'provider': 'openai', 'allow_cloud': True}, 'synthetic-first-provider-key')
        version = self.w.records(self.o, 'model')[0]['version']
        self.w.save(self.o, 'model', 'MODEL', version, {**MODEL, 'provider': 'anthropic', 'allow_cloud': True})
        self.assertFalse(self.w.records(self.o, 'model')[0]['secret_present'])

    def test_source_attachment_requires_the_displayed_library_version(self):
        self.w.save(self.a, 'source', 'SRC1', 0, SOURCE)
        version = self.w.records(self.a, 'source')[0]['version']
        self.w.save(self.a, 'source', 'SRC1', version, {**SOURCE, 'revision': '2'})
        with self.assertRaises(ValidationError): self.w.attach(self.a, 'REQ1', self.version(), 'SRC1', expected_source_version=version)

    def test_project_policy_rejects_stale_editor(self):
        first = self.c.set_policy(self.o, 'PERSONAL', DEFAULT_POLICY, 0)
        with self.assertRaises(ValidationError): self.c.set_policy(self.o, 'PERSONAL', DEFAULT_POLICY, 0)
        self.c.set_policy(self.o, 'PERSONAL', DEFAULT_POLICY, first)


class FinalAuditRegressionTests(Fixture):
    def test_preflight_rejection_is_audited_without_charging_or_changing_context(self):
        for i in range(2): self.c.add_source(self.a, 'REQ1', self.version(), 'LARGE' + str(i), 'Large selected text', 'x' * 99000, 'local:large')
        before = self.status()
        with self.assertRaises(ValidationError): run_stage(self.c, self.a, 'REQ1', self.version(), 'draft', web_tests.FakeProvider(error=True))
        after = self.status()
        self.assertEqual(after['run']['calls'], 0); self.assertEqual(before['context_digest'], after['context_digest'])
        self.assertIn('model_preflight_rejected', [e['kind'] for e in after['events']])

    def test_contextual_numeric_warnings_remain_reviewable_and_actionable(self):
        from clarity.refine import checks
        from refine_fixtures import sample
        value = sample(); rule = next(s for s in value['statements'] if s['kind'] == 'rule')
        rule['text'] = 'The SLA allows up to 5 attempts within 3. It resets at 12:00.'
        findings = checks.check(value, {}, DEFAULT_POLICY)['findings']
        expected = {'quantity_unit', 'numeric_boundary', 'time_context', 'domain_term'}
        self.assertTrue(expected <= {f['code'] for f in findings if f['severity'] == 'warning'})

    def test_outline_name_and_docstring_parameter_validation(self):
        helper = OutlineArgumentTests()
        valid = helper.outline('      """\n      {"value": "<known>"}\n      """')
        self.assertEqual(feature(valid)['compiled_cases'], 1)
        with self.assertRaises(ValidationError): feature(valid.replace('Render a selected value', 'Render <missing>'))


class DistributionTests(unittest.TestCase):
    def test_clean_snapshot_includes_manifest_and_hidden_source_but_no_history_or_runtime(self):
        import subprocess
        import tempfile
        import zipfile
        from clarity.distribution import source_bundle
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'repo'; root.mkdir()
            def git(*args): return subprocess.run(['git', *args], cwd=root, check=True, capture_output=True)
            git('init', '-q'); (root / 'README.md').write_text('# A neutral project\n')
            (root / '.github').mkdir(); (root / '.github/neutral.txt').write_text('Generic configuration.\n')
            git('add', 'README.md', '.github/neutral.txt')
            git('-c', 'user.name=Clarity test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'Synthetic source fixture')
            (root / 'private.key').write_text('untracked private fixture')
            output = Path(tmp) / 'source.zip'; result = source_bundle(root, output)
            with zipfile.ZipFile(output) as archive:
                names = archive.namelist()
                self.assertIn('clarity/.github/neutral.txt', names); self.assertIn('clarity/SOURCE-MANIFEST.json', names)
                self.assertFalse(any('/.git/' in n or n.endswith('.key') for n in names))
                manifest = json.loads(archive.read('clarity/SOURCE-MANIFEST.json'))
                self.assertEqual(manifest['source_revision'], result['source_revision'])
            (root / 'README.md').write_text('# Uncommitted change\n')
            with self.assertRaises(ValidationError): source_bundle(root, Path(tmp) / 'other.zip')
