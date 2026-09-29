"""Small loopback-only workbench. No remote hosting, CORS, provisioning or shell API."""
from __future__ import annotations

import difflib
import hmac
import html
import secrets
import sqlite3
import threading
import time
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from ..guardrails import ValidationError, canonical
from .contracts import require
from .controller import Controller
from .handoff import archive
from .worker import decode, run_stage

CSS = """body{font:17px/1.6 system-ui,sans-serif;max-width:74rem;margin:2rem auto;padding:0 1.2rem;background:#f6f7f9;color:#16202b}h1,h2,h3{line-height:1.2}header,section{background:white;border:1px solid #d5dbe2;border-radius:.6rem;padding:1.2rem;margin:1rem 0}label{display:block;margin:.7rem 0}input,textarea,select,button{font:inherit;box-sizing:border-box;padding:.6rem;border:1px solid #8a97a6;border-radius:.25rem}input:not([type=hidden]),textarea{width:100%}textarea{min-height:7rem}button{margin:.6rem .5rem .4rem 0;cursor:pointer;background:#163e5c;color:white}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#eef1f5;padding:1rem}small{display:block;color:#435466}a{color:#164d75}details{margin:1rem 0}table{border-collapse:collapse;width:100%}td,th{border-bottom:1px solid #ccd3dc;padding:.5rem;text-align:left;vertical-align:top}.warning{border-left:5px solid #aa6900}.error{border-left:5px solid #a32424}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,28rem),1fr));gap:1rem}code{overflow-wrap:anywhere}"""


def esc(value):
    return html.escape(str(value), quote=True)


def field(name, label, value='', textarea=False, kind='text'):
    if textarea:
        control = '<textarea name="' + name + '" required>' + esc(value) + '</textarea>'
    else:
        control = '<input type="' + kind + '" name="' + name + '" value="' + esc(value) + '" required>'
    return '<label>' + esc(label) + control + '</label>'


def form(action, csrf, content, button, hidden=None):
    values = {'csrf': csrf, **(hidden or {})}
    controls = ''.join('<input type="hidden" name="' + esc(k) + '" value="' + esc(v) + '">' for k, v in values.items())
    return '<form method="post" action="' + esc(action) + '">' + controls + content + '<button type="submit">' + esc(button) + '</button></form>'


def page(title, body):
    return '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>' + esc(title) + '</title><style>' + CSS + '</style><body><header><a href="/">Clarity</a><h1>' + esc(title) + '</h1><p>Flexible input. One developer-ready quality standard. Gherkin acceptance criteria.</p></header><main>' + body + '</main></body></html>'


def render_status(status, csrf, model_enabled, planned=None, plan_error=None):
    run = status['run']; role = status['actor']['role']; rid = run['id']
    path = '/run/' + rid + '/'
    base = {'version': run['version']}
    make = lambda action, content, label, hidden=None: form(path + action, csrf, content, label, {**base, **(hidden or {})})
    body = '<section><h2>' + esc(run['state'].replace('_', ' ').title()) + '</h2><p>Revision ' + str(run['revision']) + '; version ' + str(run['version']) + '. Signed in as ' + esc(status['actor']['name']) + ' (' + esc(role) + ').</p>'
    body += '<h3>Original request</h3><p>' + esc(run['brief']) + '</p>'
    if status['stale']:
        body += '<p class="error">Evidence, decisions or policy changed. A fresh draft and independent review are required.</p>'
    if model_enabled and role in {'author', 'reviewer'} and run['state'] not in {'exported', 'rejected'}:
        stage = 'draft' if role == 'author' else 'review'
        if not (stage == 'draft' and status['open_questions']):
            body += make('model', '<small>Explicitly run the configured model using only this brief’s selected evidence. No approval or tracker write is granted.</small>', 'Refine this request' if stage == 'draft' else 'Run independent model review', {'stage': stage})
    elif not model_enabled:
        body += '<small>Model assistance is disabled. An authorized analyst can import a draft or review; model and live Xray validation are separate acceptance steps.</small>'
    body += '</section>'
    if status['next_question']:
        q = status['next_question']
        body += '<section class="warning"><h2>Next decision</h2><h3>' + esc(q['text']) + '</h3><p>' + esc(q['why']) + '</p>'
        if role == 'operator':
            body += make('answer', field('answer', 'Confirmed business answer', textarea=True), 'Record owner decision', {'question_id': q['id']})
        else:
            body += '<p>An operator with authority over the requirement must confirm this decision. An unanswered question is not filled with an assumption.</p>'
        body += '</section>'
    if status['draft']:
        value = status['draft']
        body += '<section><h2>' + esc(value['title']) + '</h2>'
        for statement in value['statements']:
            body += '<h3>' + esc(statement['kind'].title() + ' · ' + statement['id']) + '</h3><p>' + esc(statement['text']) + '</p><small>Sources: ' + esc(', '.join(c['source_id'] for c in statement['citations'])) + '</small>'
        body += '<h3>Canonical acceptance criteria</h3><pre>' + esc(value['feature']) + '</pre><h3>Coverage and traceability</h3><pre>' + esc(canonical(value['coverage'])) + '</pre></section>'
        rewritten = '\n'.join(s['text'] for s in value['statements']) + '\n\n' + value['feature']
        delta = '\n'.join(difflib.unified_diff(run['brief'].splitlines(), rewritten.splitlines(), fromfile='original request', tofile='current handoff draft', lineterm=''))
        body += '<section><details><summary>Request-to-handoff text changes</summary><small>Text comparison, not an automated judgment that every change is justified. Inspect citations and independent review.</small><pre>' + esc(delta) + '</pre></details></section>'
        body += '<section><h2>Quality findings</h2><p>' + esc(status['review']['quality']['verdict'] if status['review'] else 'Independent review pending') + '</p>'
        for f in status['checks']['findings']:
            body += '<p><strong>' + esc(f['severity'] + ' · ' + f['code']) + '</strong>: ' + esc(f['message']) + ' <code>' + esc(f['scope']) + '</code></p>'
            if f['severity'] == 'security' and role == 'operator':
                body += make('signal', field('reason', 'Why this exact wording is benign', textarea=True), 'Record signal disposition and require re-review', {'finding_id': f['id']})
        if status['review']:
            body += '<details><summary>Independent review rationale and ambiguity challenge</summary><pre>' + esc(canonical(status['review'])) + '</pre></details>'
        body += '</section>'
    body += '<section><h2>Selected evidence and decisions</h2>'
    for source in status['context']['sources'].values():
        body += '<details><summary>' + esc(source['id'] + ' · ' + source['title']) + '</summary><p>Authority: ' + esc(source['authority'] or 'not confirmed') + '</p><pre>' + esc(source['text']) + '</pre>'
        if role == 'operator' and source['kind'] == 'reference' and not source['authority']:
            body += make('confirm-source', field('reason', 'Why this source is authoritative and applies here', textarea=True), 'Confirm source applicability', {'source_id': source['id'], 'source_digest': source['digest']})
        body += '</details>'
    if role == 'author':
        body += '<details><summary>Add a reference</summary>' + make('source', field('source_id', 'New source/revision ID') + field('title', 'Reference title') + field('locator', 'Source locator') + field('text', 'Paste the relevant source text', textarea=True), 'Capture reference for authority review') + '</details>'
    body += '</section>'
    if role in {'author', 'reviewer'}:
        action = 'submit' if role == 'author' else 'review'
        body += '<section><details><summary>Analyst tools: structured ' + action + '</summary>' + make(action, field('json', 'Validated ' + action + ' JSON', textarea=True), 'Submit ' + action) + '</details>'
        body += '<details><summary>Add a targeted owner question</summary>' + make('ask', field('question_id', 'New question ID') + field('text', 'Question in plain language') + field('why', 'Why this affects behavior or testing') + field('impact', 'Impact (1–5)', '3', kind='number'), 'Ask a decision-focused question') + '</details></section>'
    if role == 'operator':
        body += '<section><h2>Approval and handoff</h2>'
        if plan_error:
            body += '<p>' + esc(plan_error) + '</p>'
        if planned:
            body += '<p>Profile: ' + esc(planned['plan']['profile']) + '. The feature below is exactly the one in this proposed handoff.</p><pre>' + esc(planned['files']['acceptance.feature']) + '</pre><details><summary>Exact file hashes and plan</summary><pre>' + esc(canonical(planned['plan'])) + '</pre></details>'
            body += make('approve', '<p>Approving confirms this exact revision and its evidence/decision context, not any later change.</p>', 'Approve this handoff', {'profile': planned['plan']['profile'], 'plan_digest': planned['plan_digest']})
        body += '<p>Export profile: <a href="?profile=cucumber">Cucumber</a> · <a href="?profile=xray-cloud">Xray Cloud</a> · <a href="?profile=xray-server-dc">Xray Server/DC</a>. These are local export profiles, not verified live imports.</p>'
        approvals = [e['id'] for e in status['events'] if e['kind'] == 'approval']
        if run['state'] == 'approved' and approvals:
            body += make('seal', '', 'Seal and get approved handoff', {'approval_id': approvals[-1]})
        if run['state'] == 'exported' and approvals:
            body += '<p><a href="/export/' + esc(rid) + '/' + str(approvals[-1]) + '">Get the sealed handoff again</a></p>'
        body += '<details><summary>Authorize another refinement cycle</summary>' + make('cycle', field('reason', 'Reason for a new budgeted cycle', textarea=True), 'Authorize another cycle') + '</details>'
        body += '<details><summary>Resolve duplicate or out-of-scope questions</summary>' + make('resolve-question', field('question_id', 'Open question ID') + '<label>Resolution<select name="resolution"><option>merged</option><option>out_of_scope</option></select></label>' + '<label>Merge target (blank when out of scope)<input name="target"></label>' + field('reason', 'Confirmed scope decision or merge rationale', textarea=True), 'Record explicit question resolution') + '</details></section>'
    body += '<section><details><summary>Durable audit trail</summary><pre>' + esc(canonical(status['events'])) + '</pre></details></section>'
    return page('Requirement workspace', body)


class Workbench(ThreadingHTTPServer):
    daemon_threads = True
    def __init__(self, root, port=8765, author_provider=None, reviewer_provider=None):
        self.controller = Controller(root)
        self.providers = {'draft': author_provider, 'review': reviewer_provider}
        self.sessions = {}
        self.session_lock = threading.Lock()
        super().__init__(('127.0.0.1', port), Handler)
        self.origin = 'http://127.0.0.1:' + str(self.server_port)


class Handler(BaseHTTPRequestHandler):
    server: Workbench

    def log_message(self, *args):
        pass  # No request bodies, query strings, session IDs, or credentials in logs.

    def setup(self):
        super().setup()
        self.connection.settimeout(150)
        self.new_cookie = None

    def session(self):
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get('Cookie', ''))
        except Exception:
            pass
        key = cookie.get('clarity_session')
        sid = key.value if key else ''
        with self.server.session_lock:
            now = time.time()
            self.server.sessions = {k: s for k, s in self.server.sessions.items() if s['expires'] > now}
            current = self.server.sessions.get(sid)
            if current is None:
                require(len(self.server.sessions) < 64, 'Too many local sessions; close unused sessions and retry later')
                sid = secrets.token_urlsafe(32)
                current = {'token': None, 'csrf': secrets.token_urlsafe(32), 'expires': now + 3600}
                self.server.sessions[sid] = current
                self.new_cookie = sid
            return sid, current

    def respond(self, code, body, content_type='text/html; charset=utf-8', location=None, download=None):
        encoded = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        for key, value in {'Content-Type': content_type, 'Content-Length': str(len(encoded)), 'Cache-Control': 'no-store', 'Referrer-Policy': 'no-referrer', 'X-Content-Type-Options': 'nosniff', 'X-Frame-Options': 'DENY', 'Content-Security-Policy': "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'"}.items():
            self.send_header(key, value)
        if self.new_cookie:
            self.send_header('Set-Cookie', 'clarity_session=' + self.new_cookie + '; HttpOnly; SameSite=Strict; Path=/; Max-Age=3600')
        if location:
            self.send_header('Location', location)
        if download:
            self.send_header('Content-Disposition', 'attachment; filename="' + download + '"')
        self.end_headers(); self.wfile.write(encoded)

    def guard(self, post=False):
        require(self.headers.get('Host') == '127.0.0.1:' + str(self.server.server_port), 'Unrecognized local host')
        if not post:
            require(self.headers.get('Sec-Fetch-Site') in (None, 'none', 'same-origin'), 'Cross-site local requests are not allowed')
        if post:
            require(self.headers.get('Origin') == self.server.origin, 'Cross-origin changes are not allowed')
            require(self.headers.get('Sec-Fetch-Site') in (None, 'same-origin'), 'Cross-site changes are not allowed')
            require(self.headers.get('Content-Type', '').split(';')[0] == 'application/x-www-form-urlencoded', 'Unsupported request body')
            require(self.headers.get('Transfer-Encoding') is None, 'Chunked requests are not accepted')

    def do_GET(self):
        try:
            self.guard(); _, session = self.session()
            parts = urlsplit(self.path); path = parts.path
            token = session['token']
            if not token:
                body = '<section><h2>Sign in to this local workspace</h2>' + form('/login', session['csrf'], field('token', 'Your workspace capability', kind='password'), 'Sign in') + '<small>Keys are never placed in browser storage or URLs. This is a trusted local workspace, not a hosted multi-tenant service.</small></section>'
                return self.respond(200, page('Welcome', body))
            if path == '/':
                runs = self.server.controller.list_runs(token)
                body = '<section><h2>Requirements</h2>' + ''.join('<p><a href="/run/' + esc(r['id']) + '">' + esc(r['id']) + '</a> · ' + esc(r['state']) + '</p>' for r in runs) + '</section>'
                body += '<section><h2>Start with the problem</h2>' + form('/create', session['csrf'], field('id', 'Brief ID') + field('project', 'Project ID', 'PERSONAL') + field('brief', 'What needs to change, and why?', textarea=True) + '<label>Conversation style<select name="presentation"><option value="guided">Plain-language guidance</option><option value="concise">Concise analyst guidance</option></select></label>', 'Capture request') + '<small>Creating a brief requires an author capability. The same handoff standard applies to both conversation styles.</small></section>'
                body += form('/logout', session['csrf'], '', 'Sign out')
                return self.respond(200, page('Requirements', body))
            bits = path.strip('/').split('/')
            if len(bits) == 2 and bits[0] == 'run':
                status = self.server.controller.status(token, bits[1])
                profile = parse_qs(parts.query).get('profile', ['cucumber'])[0]
                planned, error = None, None
                if status['run']['state'] in {'awaiting_approval', 'approved'}:
                    try:
                        planned = self.server.controller.plan(token, bits[1], profile)
                    except ValidationError as exc:
                        error = str(exc)
                stage = 'draft' if status['actor']['role'] == 'author' else 'review'
                return self.respond(200, render_status(status, session['csrf'], self.server.providers[stage] is not None, planned, error))
            if len(bits) == 3 and bits[0] == 'export':
                bundle = self.server.controller.exported(token, bits[1], int(bits[2]))
                return self.respond(200, archive(bundle), 'application/zip', download=bits[1] + '-handoff.zip')
            return self.respond(404, page('Not found', '<p>Unknown workspace route.</p>'))
        except (ValidationError, ValueError, KeyError, sqlite3.Error, OSError):
            self.respond(400, page('Request could not be completed', '<p>Check the capability, workspace state and request. No approval is implied by an error.</p>'))

    def do_POST(self):
        try:
            self.guard(post=True); sid, session = self.session()
            length = int(self.headers.get('Content-Length', '0'))
            require(0 < length <= 1_000_000, 'Request body size is invalid')
            values = parse_qs(self.rfile.read(length).decode('utf-8'), keep_blank_values=True, max_num_fields=30)
            require(all(len(v) == 1 for v in values.values()), 'Duplicate form field')
            data = {k: v[0] for k, v in values.items()}
            require(hmac.compare_digest(data.pop('csrf', ''), session['csrf']), 'Invalid request token')
            path = urlsplit(self.path).path
            if path == '/login':
                require(set(data) == {'token'}, 'Invalid sign-in fields')
                self.server.controller.list_runs(data['token'])  # Verifies the capability without echoing it.
                with self.server.session_lock:
                    self.server.sessions.pop(sid, None)
                    new_id = secrets.token_urlsafe(32)
                    self.server.sessions[new_id] = {'token': data['token'], 'csrf': secrets.token_urlsafe(32), 'expires': time.time() + 3600}
                    self.new_cookie = new_id
                return self.respond(303, '', location='/')
            token = session['token']; require(bool(token), 'Sign-in required')
            if path == '/logout':
                require(not data, 'Invalid sign-out request')
                with self.server.session_lock:
                    self.server.sessions.pop(sid, None)
                return self.respond(303, '', location='/')
            c = self.server.controller
            if path == '/create':
                require(set(data) == {'id', 'project', 'brief', 'presentation'}, 'Invalid capture fields')
                c.create(token, data['id'], data['project'], data['brief'], data['presentation'])
                return self.respond(303, '', location='/run/' + data['id'])
            bits = path.strip('/').split('/')
            require(len(bits) == 3 and bits[0] == 'run', 'Unknown action')
            rid, action = bits[1:]; version = int(data.pop('version'))
            # Never dynamically resolve a function name from untrusted input.
            allowed = {'answer': {'question_id', 'answer'}, 'source': {'source_id', 'title', 'text', 'locator'}, 'confirm-source': {'source_id', 'source_digest', 'reason'}, 'submit': {'json'}, 'review': {'json'}, 'model': {'stage'}, 'ask': {'question_id', 'text', 'why', 'impact'}, 'signal': {'finding_id', 'reason'}, 'cycle': {'reason'}, 'approve': {'profile', 'plan_digest'}, 'seal': {'approval_id'}, 'resolve-question': {'question_id', 'resolution', 'target', 'reason'}}
            require(action in allowed and set(data) == allowed[action], 'Invalid action fields')
            if action == 'answer': c.answer(token, rid, version, data['question_id'], data['answer'])
            elif action == 'source': c.add_source(token, rid, version, data['source_id'], data['title'], data['text'], data['locator'])
            elif action == 'confirm-source': c.confirm_source(token, rid, version, data['source_id'], data['source_digest'], data['reason'])
            elif action == 'submit': c.submit(token, rid, version, decode(data['json']))
            elif action == 'review': c.review(token, rid, version, decode(data['json']))
            elif action == 'ask': c.ask(token, rid, version, {'id': data['question_id'], 'text': data['text'], 'why': data['why'], 'impact': int(data['impact'])})
            elif action == 'signal': c.resolve_signal(token, rid, version, data['finding_id'], data['reason'])
            elif action == 'cycle': c.new_cycle(token, rid, version, data['reason'])
            elif action == 'resolve-question': c.resolve_question(token, rid, version, data['question_id'], data['resolution'], data['target'] or None, data['reason'])
            elif action == 'approve': c.approve(token, rid, version, data['plan_digest'], data['profile'])
            elif action == 'model':
                provider = self.server.providers.get(data['stage'])
                require(provider is not None, 'This model stage is not configured')
                run_stage(c, token, rid, version, data['stage'], provider)
            elif action == 'seal':
                # Seal itself rechecks the exact immutable approval and current state.
                c.seal(token, rid, int(data['approval_id']))
                return self.respond(303, '', location='/export/' + rid + '/' + str(int(data['approval_id'])))
            return self.respond(303, '', location='/run/' + rid)
        except (ValidationError, ValueError, KeyError, TypeError, UnicodeError, sqlite3.Error, OSError) as exc:
            message = str(exc) if isinstance(exc, ValidationError) else 'Malformed request or local storage operation failed.'
            self.respond(400, page('Action not completed', '<section class="error"><p>' + esc(message) + '</p><p>Refresh the requirement before retrying. A failed model attempt may have used its reserved budget; no approval or publication is implied.</p><a href="/">Return to workspace</a></section>'))
