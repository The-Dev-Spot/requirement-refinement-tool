import copy
import http.client
import importlib.util
import io
import json
import re
import tempfile
import threading
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlencode

from clarity.guardrails import ValidationError
from clarity.refine.__main__ import main
from clarity.refine.worker import Ollama, decode, request_packet, run_stage
from clarity.refine.web import Workbench, render_status
from test_refine_controller import Fixture
from refine_fixtures import sample, assessment


class FakeProvider:
    name = 'synthetic-test-provider'
    def __init__(self, response=None, error=False): self.response, self.error, self.packet = response, error, None
    def complete(self, system, payload):
        self.packet = {'system': system, 'payload': copy.deepcopy(payload)}
        if self.error: raise ValidationError('Simulated provider failure')
        return copy.deepcopy(self.response)


class WorkerTests(Fixture):
    def test_question_generation_is_one_transaction_and_records_attempt(self):
        provider = FakeProvider({'questions': [self.question('Q1'), self.question('Q2', 'Which users may cancel?', 4)], 'draft': None})
        result = run_stage(self.c, self.a, 'REQ1', self.version(), 'draft', provider)
        self.assertEqual(len(result['open_questions']), 2)
        events = self.status()['events']
        self.assertIn('model_call_started', [e['kind'] for e in events])
        self.assertIn('model_call_finished', [e['kind'] for e in events])
        self.assertNotIn(self.a, json.dumps(provider.packet))
        self.assertNotIn('token', provider.packet['payload'])

    def test_credential_like_source_never_reaches_model(self):
        self.c.add_source(self.a, 'REQ1', self.version(), 'PRIVATE', 'Bad paste', 'ghp_' + 'x' * 36, 'local:test')
        provider = FakeProvider(error=True)
        with self.assertRaises(ValidationError): run_stage(self.c, self.a, 'REQ1', self.version(), 'draft', provider)
        self.assertIsNone(provider.packet)

    def test_model_cannot_approve_or_change_policy_by_returning_extra_fields(self):
        provider = FakeProvider({'questions': [self.question()], 'draft': None, 'approved': True})
        with self.assertRaises(ValidationError): run_stage(self.c, self.a, 'REQ1', self.version(), 'draft', provider)
        self.assertIsNone(self.status()['draft'])
        self.assertEqual(self.status()['run']['calls'], 1)

    def test_model_cannot_return_empty_success(self):
        with self.assertRaises(ValidationError): run_stage(self.c, self.a, 'REQ1', self.version(), 'draft', FakeProvider({'questions': [], 'draft': None}))

    def test_invalid_question_batch_rolls_back_all_questions(self):
        duplicate = [self.question('Q1'), self.question('Q2')]
        with self.assertRaises(ValidationError): run_stage(self.c, self.a, 'REQ1', self.version(), 'draft', FakeProvider({'questions': duplicate, 'draft': None}))
        self.assertEqual(self.status()['context']['questions'], {})

    def test_pending_owner_decision_does_not_spend_another_model_call(self):
        self.c.ask(self.a, 'REQ1', self.version(), self.question())
        before = self.status()['run']['calls']
        provider = FakeProvider(error=True)
        with self.assertRaises(ValidationError): run_stage(self.c, self.a, 'REQ1', self.version(), 'draft', provider)
        self.assertIsNone(provider.packet)
        self.assertEqual(self.status()['run']['calls'], before)

    def test_retries_are_bounded_and_failures_remain_visible(self):
        for _ in range(6):
            with self.assertRaises(ValidationError): run_stage(self.c, self.a, 'REQ1', self.version(), 'draft', FakeProvider(error=True))
        with self.assertRaises(ValidationError): run_stage(self.c, self.a, 'REQ1', self.version(), 'draft', FakeProvider(error=True))
        self.assertEqual(self.status()['run']['calls'], 6)
        self.assertEqual(sum(e['kind'] == 'model_call_finished' for e in self.status()['events']), 6)

    def test_wrong_stage_role_cannot_invoke_model(self):
        provider = FakeProvider(error=True)
        with self.assertRaises(ValidationError): run_stage(self.c, self.a, 'REQ1', self.version(), 'review', provider)
        self.assertIsNone(provider.packet)

    def test_model_draft_stays_unapproved(self):
        value = self.confirmed()
        provider = FakeProvider({'questions': [], 'draft': value})
        result = run_stage(self.c, self.a, 'REQ1', self.version(), 'draft', provider)
        self.assertEqual(result['run']['state'], 'awaiting_review')
        self.assertFalse(any(e['kind'] == 'approval' for e in self.status()['events']))

    def test_reviewer_packet_has_no_writer_or_previous_review_score(self):
        value = self.confirmed(); self.c.submit(self.a, 'REQ1', self.version(), value)
        status = self.status(self.r); status['review'] = {'secret_score': 'writer-score'}
        packet = request_packet(status, 'review')
        self.assertNotIn('writer-score', json.dumps(packet))
        self.assertIn('statement_support', packet['output_contract'])
        self.assertIn('scenario_fidelity', packet['output_contract'])

    def test_invalid_and_duplicate_json_are_rejected(self):
        for body in ('{"x":1,"x":2}', '{"x":NaN}', '[]', 'not json'):
            with self.assertRaises(ValidationError): decode(body)

    def test_transport_has_fixed_loopback_no_tools_and_no_redirects(self):
        class Response:
            status = 200
            def read(self, count): return json.dumps({'done': True, 'message': {'content': '{"ok":true}'}}).encode()
        class Connection:
            def __init__(self): self.request_args = None
            def request(self, *args, **kwargs): self.request_args = (args, kwargs)
            def getresponse(self): return Response()
            def close(self): pass
        conn = Connection()
        with patch('clarity.refine.worker.http.client.HTTPConnection', return_value=conn) as factory:
            result = Ollama('test-local-model').complete('system', {'brief': 'text'})
            self.assertTrue(result['ok'])
            factory.assert_called_once_with('127.0.0.1', 11434, timeout=120)
        request = json.loads(conn.request_args[1]['body'])
        self.assertEqual(conn.request_args[0], ('POST', '/api/chat'))
        self.assertNotIn('tools', request)
        self.assertFalse(request['stream'])
        self.assertEqual(request['format'], 'json')
        Response.status = 302
        with patch('clarity.refine.worker.http.client.HTTPConnection', return_value=conn), self.assertRaises(ValidationError): Ollama('test-local-model').complete('system', {})

    def test_tool_calls_and_truncation_are_rejected(self):
        for envelope in ({'done': True, 'done_reason': 'length', 'message': {'content': '{}'}}, {'done': True, 'message': {'content': '{}', 'tool_calls': [{'name': 'publish'}]}}, {'done': False, 'message': {'content': '{}'}}):
            response = unittest.mock.Mock(status=200); response.read.return_value = json.dumps(envelope).encode()
            connection = unittest.mock.Mock(); connection.getresponse.return_value = response
            with patch('clarity.refine.worker.http.client.HTTPConnection', return_value=connection), self.assertRaises(ValidationError): Ollama('test-local-model').complete('system', {})

    def test_cli_bootstrap_does_not_print_capability_secret(self):
        output = Path(self.tmp.name) / 'cli-author.key'
        out = io.StringIO()
        with redirect_stdout(out): rc = main(['--state', str(self.root), 'key', '--actor', 'cli-author', '--role', 'author', '--output', str(output)])
        self.assertEqual(rc, 0)
        self.assertNotIn(output.read_text().strip(), out.getvalue())

    def test_cli_bad_capability_returns_controlled_error(self):
        bad = Path(self.tmp.name) / 'bad.key'; bad.write_text('not-a-secret-capability'); bad.chmod(0o600)
        err = io.StringIO()
        with redirect_stderr(err): rc = main(['--state', str(self.root), 'status', '--key-file', str(bad), '--id', 'REQ1'])
        self.assertEqual(rc, 2)
        self.assertNotIn('not-a-secret-capability', err.getvalue())


class WorkbenchTests(Fixture):
    def setUp(self):
        super().setUp()
        self.server = Workbench(self.root, port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True); self.thread.start()
        self.addCleanup(self.close_server)
        self.cookie = None

    def close_server(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(timeout=2)

    def request(self, method='GET', path='/', data=None, extra=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        headers = dict(extra or {})
        if self.cookie: headers['Cookie'] = self.cookie
        body = None
        if data is not None:
            body = urlencode(data); headers.setdefault('Content-Type', 'application/x-www-form-urlencoded'); headers.setdefault('Origin', self.server.origin)
        conn.request(method, path, body=body, headers=headers)
        response = conn.getresponse(); content = response.read(); result = (response.status, dict(response.getheaders()), content.decode('utf-8', errors='replace'))
        if response.getheader('Set-Cookie'): self.cookie = response.getheader('Set-Cookie').split(';')[0]
        conn.close(); return result

    def csrf(self, body): return re.search(r'name="csrf" value="([^"]+)"', body).group(1)

    def login(self, key=None):
        _, _, body = self.request(); old_cookie = self.cookie
        result = self.request('POST', '/login', {'csrf': self.csrf(body), 'token': key or self.a})
        self.assertEqual(result[0], 303); self.assertNotEqual(old_cookie, self.cookie)
        return self.request()

    def test_session_rotation_and_secure_headers(self):
        code, headers, body = self.login()
        self.assertEqual(code, 200)
        self.assertIn("default-src 'none'", headers['Content-Security-Policy'])
        self.assertEqual(headers['Cache-Control'], 'no-store')
        self.assertEqual(headers['Referrer-Policy'], 'same-origin')
        self.assertNotIn(self.a, body)

    def test_host_header_rebinding_rejected(self):
        result = self.request(extra={'Host': 'attacker.invalid'})
        self.assertEqual(result[0], 400)

    def test_cross_site_get_rejected(self):
        self.assertEqual(self.request(extra={'Sec-Fetch-Site': 'cross-site'})[0], 400)

    def test_cross_origin_write_rejected(self):
        _, _, body = self.login()
        result = self.request('POST', '/create', {'csrf': self.csrf(body), 'id': 'REQ2', 'project': 'PERSONAL', 'brief': 'Plain input', 'presentation': 'guided'}, {'Origin': 'http://' + 'attacker.invalid'})
        self.assertEqual(result[0], 400)
        self.assertEqual(len(self.c.list_runs(self.a)), 1)

    def test_null_origin_is_still_rejected_before_login(self):
        _, _, body = self.request()
        result = self.request('POST', '/login', {'csrf': self.csrf(body), 'token': self.a}, {'Origin': 'null'})
        self.assertEqual(result[0], 400)
        self.assertIn('Cross-origin changes are not allowed', result[2])
        _, _, body = self.request()
        self.assertIn('Sign in to this local workspace', body)

    def test_missing_origin_is_still_rejected_before_login(self):
        _, _, body = self.request()
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        conn.request('POST', '/login', body=urlencode({'csrf': self.csrf(body), 'token': self.a}), headers={'Content-Type': 'application/x-www-form-urlencoded', 'Cookie': self.cookie})
        response = conn.getresponse()
        self.assertEqual(response.status, 400)
        self.assertIn(b'Cross-origin changes are not allowed', response.read())
        conn.close()

    def test_invalid_csrf_rejected(self):
        self.login()
        self.assertEqual(self.request('POST', '/create', {'csrf': 'wrong'})[0], 400)

    def test_plain_language_capture_requires_no_json(self):
        _, _, body = self.login()
        result = self.request('POST', '/create', {'csrf': self.csrf(body), 'id': 'REQ2', 'project': 'PERSONAL', 'brief': 'Customers keep calling me about bookings.', 'presentation': 'guided'})
        self.assertEqual(result[0], 303)
        self.assertEqual(self.c.status(self.a, 'REQ2')['run']['state'], 'captured')

    def test_unknown_actions_are_not_dynamic_method_calls(self):
        _, _, body = self.login()
        self.assertEqual(self.request('POST', '/run/REQ1/provision', {'csrf': self.csrf(body), 'version': self.version()})[0], 400)

    def test_get_export_never_mutates_approval(self):
        self.login(self.o)
        before = self.version()
        self.assertEqual(self.request(path='/export/REQ1/999')[0], 400)
        self.assertEqual(self.version(), before)

    def test_escaped_source_content_no_active_markup(self):
        self.c.create(self.a, 'REQ2', 'PERSONAL', '<script>injected()</script><img src="https://' + 'attacker.invalid/x">')
        self.login()
        code, _, body = self.request(path='/run/REQ2')
        self.assertEqual(code, 200)
        self.assertNotIn('<script>', body)
        self.assertNotIn('<img ', body)
        self.assertIn('&lt;script&gt;', body)

    def test_browser_cannot_assume_operator_role(self):
        _, _, body = self.login()
        self.c.ask(self.a, 'REQ1', self.version(), self.question())
        _, _, body = self.request(path='/run/REQ1')
        # An author page may have no model but still includes advanced import form.
        result = self.request('POST', '/run/REQ1/answer', {'csrf': self.csrf(body), 'version': self.version(), 'question_id': 'Q1', 'answer': 'Invent an owner decision.'})
        self.assertEqual(result[0], 400)
        self.assertEqual(self.status()['context']['questions']['Q1']['state'], 'open')
