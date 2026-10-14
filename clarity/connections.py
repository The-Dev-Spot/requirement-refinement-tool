"""Fixed-endpoint cloud transports. No redirects, ambient proxies, tools or retries."""
import base64
import http.client
import json
import re
import time
from html.parser import HTMLParser
from urllib.parse import quote, urlencode

from .guardrails import ValidationError, canonical, identifier
from .refine.contracts import require
from .refine.worker import decode


def request(host, path, *, method='GET', payload=None, headers=None, timeout=60, limit=1_000_000):
    """Called only with application-selected API hosts and constructed paths."""
    connection = http.client.HTTPSConnection(host, timeout=timeout)
    try:
        connection.request(method, path, body=canonical(payload).encode() if payload is not None else None,
                           headers={'Accept': 'application/json', 'Content-Type': 'application/json', **(headers or {})})
        response = connection.getresponse()
        require(response.status == 200, 'Connection rejected the request; check credentials, scope and service availability (HTTP ' + str(response.status) + ')')
        raw = response.read(limit + 1)
        require(len(raw) <= limit, 'Connection response exceeds the selected evidence budget')
        return decode(raw.decode('utf-8'))
    except (OSError, UnicodeError, http.client.HTTPException) as exc:
        raise ValidationError('Connection unavailable; no remote changes were made') from exc
    finally:
        connection.close()


class CloudModel:
    def __init__(self, provider, model, key, *, timeout=120, max_tokens=8192):
        require(provider in {'openai', 'anthropic'}, 'Unsupported cloud provider')
        require(isinstance(key, str) and key.strip() and not any(c in key for c in '\r\n'), 'Cloud API key is missing or invalid')
        self.provider, self.name, self.key = provider, model, key
        self.timeout, self.max_tokens, self.metrics = timeout, max_tokens, {}

    def probe(self):
        host, path, headers = self._connection()
        request(host, '/v1/models/' + quote(self.name, safe=''), headers=headers, timeout=15)
        return 'Selected model is accessible. No requirement evidence was sent.'

    def _connection(self):
        if self.provider == 'openai':
            return 'api.openai.com', '/v1/responses', {'Authorization': 'Bearer ' + self.key}
        return 'api.anthropic.com', '/v1/messages', {'x-api-key': self.key, 'anthropic-version': '2023-06-01'}

    def complete(self, system, payload):
        host, path, headers = self._connection()
        schema = payload['response_schema']
        common = {'model': self.name}
        if self.provider == 'openai':
            body = {**common, 'store': False, 'instructions': system, 'input': canonical(payload),
                    'max_output_tokens': self.max_tokens, 'text': {'format': {'type': 'json_schema', 'name': 'clarity_handoff', 'strict': True, 'schema': schema}}}
        else:
            body = {**common, 'max_tokens': self.max_tokens, 'system': system, 'messages': [{'role': 'user', 'content': canonical(payload)}],
                    'output_config': {'format': {'type': 'json_schema', 'schema': schema}}}
        data = request(host, path, method='POST', payload=body, headers=headers, timeout=self.timeout)
        usage = data.get('usage', {})
        self.metrics = {k: v for k, v in usage.items() if k in {'input_tokens', 'output_tokens', 'cache_read_input_tokens', 'cache_creation_input_tokens'} and type(v) is int and 0 <= v < 10**10}
        if self.provider == 'openai':
            require(data.get('status') == 'completed', 'Cloud model output is incomplete; nothing was submitted')
            parts = []
            for item in data.get('output', []):
                require(item.get('type') in {'message', 'reasoning'}, 'Model output contained an unauthorized tool/action')
                if item.get('type') == 'message':
                    for block in item.get('content', []):
                        require(block.get('type') == 'output_text', 'Model refused or returned an unsupported response')
                        parts.append(block['text'])
        else:
            require(data.get('stop_reason') == 'end_turn', 'Cloud model output is incomplete; nothing was submitted')
            parts = []
            for block in data.get('content', []):
                require(block.get('type') == 'text', 'Model output contained an unauthorized tool/action')
                parts.append(block['text'])
        return decode(''.join(parts))


def tenant_host(value):
    require(isinstance(value, str) and re.fullmatch(r'[a-z0-9][a-z0-9-]{0,61}\.atlassian\.net', value), 'Enter a tenant hostname such as team.atlassian.net, without a URL or path')
    return value


def plain_adf(value):
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        text = value.get('text', '')
        children = ''.join(plain_adf(c) for c in value.get('content', []))
        return text + children + ('\n' if value.get('type') in {'paragraph', 'heading', 'listItem', 'tableRow', 'hardBreak'} else '')
    return ''


class TextHTML(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts = []; self.hidden = 0
    def handle_starttag(self, tag, attrs):
        if tag in {'script', 'style'}: self.hidden += 1
        if tag in {'p', 'br', 'div', 'li', 'tr', 'h1', 'h2', 'h3'}: self.parts.append('\n')
    def handle_endtag(self, tag):
        if tag in {'script', 'style'} and self.hidden: self.hidden -= 1
    def handle_data(self, data):
        if not self.hidden: self.parts.append(data)


def read_source(profile, key, item):
    """Read one explicitly selected object and enforce configured project/space."""
    kind = profile['provider']; identifier(item)
    if kind == 'linear':
        from .adapters import LinearReadOnly
        value = LinearReadOnly(key, profile['scope'], project_id=profile['project_scope'] or None).read_issue(item)
        issue = value['source']['issue']
        body = issue['title'] + '\n\n' + (issue['description'] or '') + '\n\n' + '\n\n'.join(c['body'] for c in value['source']['comments'])
        require(len(body.encode()) <= 100000, 'Selected issue exceeds 100 KB; use a relevant excerpt')
        return {'title': issue['identifier'] + ' ' + issue['title'], 'text': body, 'locator': issue['url'], 'retrieved_at': time.time(), 'revision': value['revision']}
    host = tenant_host(profile['host'])
    require(profile['username'] and key, 'Connection email/token is missing')
    auth = {'Authorization': 'Basic ' + base64.b64encode((profile['username'] + ':' + key).encode()).decode()}
    if kind == 'jira-cloud':
        require(re.fullmatch(r'[A-Z][A-Z0-9_]*-[1-9][0-9]*', item), 'Enter an issue key such as DEMO-1')
        path = '/rest/api/3/issue/' + quote(item, safe='') + '?fields=summary,description,updated,project'
        value = request(host, path, headers=auth)
        fields = value['fields']
        require(fields['project']['key'] == profile['scope'], 'Issue is outside the selected project')
        comments = []; start = 0
        for _ in range(10):
            page = request(host, '/rest/api/3/issue/' + item + '/comment?' + urlencode({'startAt': start, 'maxResults': 50}), headers=auth)
            require(page.get('startAt') == start and isinstance(page.get('comments'), list), 'Incomplete comment page')
            comments += [plain_adf(c['body']) for c in page['comments']]
            start += len(page['comments'])
            if start >= page['total']: break
            require(bool(page['comments']), 'Comment pagination did not advance')
        else: raise ValidationError('Comment budget exceeded; select a smaller source')
        again = request(host, path, headers=auth)
        require(again['fields']['updated'] == fields['updated'], 'Issue changed while reading; retry the capture')
        body = fields['summary'] + '\n\n' + plain_adf(fields.get('description')) + '\n\nComments:\n' + '\n\n'.join(comments)
        title, revision, locator = item + ' ' + fields['summary'], fields['updated'], 'https://' + host + '/browse/' + item
    else:
        require(kind == 'confluence-cloud' and item.isdigit(), 'Enter a numeric Confluence page ID')
        path = '/wiki/api/v2/pages/' + item + '?body-format=storage'
        value = request(host, path, headers=auth)
        require(str(value['spaceId']) == profile['scope'], 'Page is outside the selected space')
        parsed = TextHTML(); parsed.feed(value['body']['storage']['value'])
        body = value['title'] + '\n\n' + ''.join(parsed.parts)
        again = request(host, path, headers=auth)
        require(again['version']['number'] == value['version']['number'], 'Page changed while reading; retry the capture')
        title, revision, locator = value['title'], str(value['version']['number']), 'https://' + host + '/wiki/spaces/' + profile['scope'] + '/pages/' + item
    require(len(body.encode()) <= 100000 and body.strip(), 'Selected source is empty or exceeds 100 KB; use a relevant excerpt')
    return {'title': title, 'text': body, 'locator': locator, 'retrieved_at': time.time(), 'revision': revision}
