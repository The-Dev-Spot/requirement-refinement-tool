"""OpenAI-compatible local inference on an explicitly selected loopback port."""
import http.client
from .guardrails import canonical, ValidationError
from .refine.contracts import require, text
from .refine.worker import decode
from .efficiency import prompt_parts, usage_metrics


class LocalModel:
    def __init__(self, model, *, port=8000, timeout=120, max_tokens=8192, key=''):
        text(model, 'model', 200)
        require(type(port) is int and 1 <= port <= 65535 and type(timeout) is int and 1 <= timeout <= 120 and type(max_tokens) is int and 256 <= max_tokens <= 16384, 'Invalid local model settings')
        require(isinstance(key, str) and not any(ord(c) < 32 for c in key), 'Invalid local model credential')
        self.key = key
        self.provider = 'local-openai'
        self.name, self.port, self.timeout, self.max_tokens = model, port, timeout, max_tokens
        self.metrics = {}

    def complete(self, system, payload):
        prefix, task = prompt_parts(payload)
        body = {'model': self.name, 'stream': False, 'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': prefix + '\n' + task}],
                'max_tokens': self.max_tokens, 'temperature': 0, 'response_format': {'type': 'json_schema', 'json_schema': {'name': 'clarity_handoff', 'strict': True, 'schema': payload['response_schema']}}}
        connection = http.client.HTTPConnection('127.0.0.1', self.port, timeout=self.timeout)
        try:
            headers = {'Content-Type': 'application/json'}
            if self.key: headers['Authorization'] = 'Bearer ' + self.key
            connection.request('POST', '/v1/chat/completions', body=canonical(body).encode(), headers=headers)
            response = connection.getresponse(); require(response.status == 200, 'Local inference request failed; check model/schema support')
            raw = response.read(1_000_001); require(len(raw) <= 1_000_000, 'Local model response exceeded its budget')
            data = decode(raw.decode()); choices = data.get('choices', [])
            self.metrics = usage_metrics(data.get('usage', {}))
            require(len(choices) == 1 and choices[0].get('finish_reason') == 'stop', 'Local model output was incomplete')
            message = choices[0]['message']; require(not message.get('tool_calls'), 'Model tools are not permitted')
            return decode(message['content'])
        except (OSError, UnicodeError, http.client.HTTPException) as exc:
            raise ValidationError('Local model unavailable; the attempt remains recorded') from exc
        finally: connection.close()
