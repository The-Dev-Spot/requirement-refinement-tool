"""Primary API transport fixtures; do not assert live service compatibility."""
import json
import unittest
from unittest.mock import Mock, patch
from clarity.connections import CloudModel, read_source, request
from clarity.local_model import LocalModel
from clarity.guardrails import ValidationError


class TransportTests(unittest.TestCase):
    def test_cloud_transports_are_fixed_schema_constrained_and_tool_free(self):
        schema = {'type': 'object', 'properties': {'ready': {'type': 'boolean'}}, 'required': ['ready'], 'additionalProperties': False}
        for kind, envelope, host, path in [
            ('openai', {'status': 'completed', 'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': '{"ready":true}'}]}], 'usage': {'input_tokens': 10, 'output_tokens': 3}}, 'api.openai.com', '/v1/responses'),
            ('anthropic', {'stop_reason': 'end_turn', 'content': [{'type': 'text', 'text': '{"ready":true}'}]}, 'api.anthropic.com', '/v1/messages')]:
            with self.subTest(kind=kind), patch('clarity.connections.request', return_value=envelope) as send:
                result = CloudModel(kind, 'selected-model', 'synthetic-test-key').complete('instruction', {'response_schema': schema})
                self.assertEqual(result, {'ready': True})
                args, kwargs = send.call_args; self.assertEqual(args, (host, path)); self.assertNotIn('tools', kwargs['payload'])
                self.assertNotIn('synthetic-test-key', json.dumps(kwargs['payload']))
                if kind == 'openai': self.assertFalse(kwargs['payload']['store']); self.assertEqual(kwargs['payload']['text']['format']['schema'], schema)
                else: self.assertEqual(kwargs['payload']['output_config']['format']['schema'], schema)

    def test_cloud_incomplete_refusal_and_tool_outputs_never_become_content(self):
        cases = [('openai', {'status': 'incomplete'}), ('openai', {'status': 'completed', 'output': [{'type': 'function_call'}]}), ('openai', {'status': 'completed', 'output': [{'type': 'message', 'content': [{'type': 'refusal'}]}]}), ('anthropic', {'stop_reason': 'max_tokens'}), ('anthropic', {'stop_reason': 'end_turn', 'content': [{'type': 'tool_use'}]})]
        for kind, envelope in cases:
            with patch('clarity.connections.request', return_value=envelope), self.assertRaises(ValidationError): CloudModel(kind, 'selected-model', 'synthetic-key').complete('system', {'response_schema': {}})

    def test_https_redirect_and_oversized_response_fail_without_forwarding(self):
        for status, body in [(302, b'{}'), (200, b'x' * 101)]:
            conn = Mock(); conn.getresponse.return_value = Mock(status=status); conn.getresponse.return_value.read.return_value = body
            with patch('clarity.connections.http.client.HTTPSConnection', return_value=conn), self.assertRaises(ValidationError): request('api.openai.com', '/v1/models', limit=100)
            self.assertEqual(conn.request.call_count, 1); conn.close.assert_called_once()

    def test_local_compatible_transport_rejects_truncation_and_records_usage(self):
        conn = Mock(); response = conn.getresponse.return_value; response.status = 200
        data = {'choices': [{'finish_reason': 'stop', 'message': {'content': '{"ready":true}'}}], 'usage': {'prompt_tokens': 10, 'completion_tokens': 2, 'untrusted': 'ignore'}}
        response.read.return_value = json.dumps(data).encode()
        model = LocalModel('local-test', port=1234)
        with patch('clarity.local_model.http.client.HTTPConnection', return_value=conn) as factory:
            self.assertEqual(model.complete('system', {'response_schema': {}}), {'ready': True})
            factory.assert_called_once_with('127.0.0.1', 1234, timeout=120)
        self.assertEqual(model.metrics, {'prompt_tokens': 10, 'completion_tokens': 2})
        self.assertEqual(conn.request.call_args.args, ('POST', '/v1/chat/completions'))
        data['choices'][0]['finish_reason'] = 'length'; response.read.return_value = json.dumps(data).encode()
        with patch('clarity.local_model.http.client.HTTPConnection', return_value=conn), self.assertRaises(ValidationError): model.complete('system', {'response_schema': {}})


class SourceTests(unittest.TestCase):
    jira = {'provider': 'jira-cloud', 'host': 'fictional.atlassian.net', 'username': 'reader@example.invalid', 'scope': 'DEMO', 'project_scope': '', 'enabled': True}

    def issue(self, project='DEMO', updated='1'):
        return {'fields': {'summary': 'A selected issue', 'description': {'type': 'doc', 'content': [{'type': 'paragraph', 'content': [{'type': 'text', 'text': 'Confirmed policy.'}]}]}, 'updated': updated, 'project': {'key': project}}}

    def test_jira_pages_comments_and_rechecks_revision(self):
        pages = [self.issue(), {'startAt': 0, 'comments': [{'body': {'type': 'paragraph', 'content': [{'type': 'text', 'text': 'First comment.'}]}}], 'total': 2}, {'startAt': 1, 'comments': [{'body': 'Second comment.'}], 'total': 2}, self.issue()]
        with patch('clarity.connections.request', side_effect=pages) as send: result = read_source(self.jira, 'synthetic-token', 'DEMO-1')
        self.assertIn('Confirmed policy.', result['text']); self.assertIn('Second comment.', result['text'])
        self.assertEqual(send.call_count, 4); self.assertEqual(result['revision'], '1')
        self.assertTrue(all(call.args[0] == 'fictional.atlassian.net' for call in send.call_args_list))

    def test_jira_wrong_project_and_changed_capture_are_rejected(self):
        with patch('clarity.connections.request', return_value=self.issue(project='OTHER')), self.assertRaises(ValidationError): read_source(self.jira, 'synthetic-token', 'DEMO-1')
        pages = [self.issue(), {'startAt': 0, 'comments': [], 'total': 0}, self.issue(updated='2')]
        with patch('clarity.connections.request', side_effect=pages), self.assertRaises(ValidationError): read_source(self.jira, 'synthetic-token', 'DEMO-1')

    def test_confluence_checks_space_and_removes_active_markup(self):
        profile = {**self.jira, 'provider': 'confluence-cloud', 'scope': '123'}
        page = {'title': 'A selected page', 'spaceId': '123', 'version': {'number': 1}, 'body': {'storage': {'value': '<p>Applicable policy.</p><script>bad()</script><style>hidden</style>'}}}
        with patch('clarity.connections.request', return_value=page): result = read_source(profile, 'synthetic-token', '99')
        self.assertIn('Applicable policy.', result['text']); self.assertNotIn('bad()', result['text']); self.assertNotIn('hidden', result['text'])
        page['spaceId'] = '456'
        with patch('clarity.connections.request', return_value=page), self.assertRaises(ValidationError): read_source(profile, 'synthetic-token', '99')
