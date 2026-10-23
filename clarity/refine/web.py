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

from ..guardrails import ValidationError, canonical, digest
from .contracts import require
from .controller import Controller
from .collaboration import question_dependencies
from .handoff import archive, verify_bundle
from .worker import decode, run_stage, request_packet
from ..workspace import Workspace, initialize as initialize_settings
from ..jobs import Jobs, RuntimeLease
from ..efficiency import AUTHOR_STAGES, budget
from ..workspace import model_settings
from .worker import SYSTEM
from .. import host_bridge
from . import views
from pathlib import Path

from .views import esc, field, form, page


def boolean(value):
    require(value in {'true', 'false'}, 'Invalid switch')
    return value == 'true'


def render_status(status, csrf, model_enabled, planned=None, plan_error=None, *, models=(), sources=(), jobs=(), root=None, question_id=None):
    run = status['run']; role = status['actor']['role']; rid = run['id']
    path = '/run/' + rid + '/'
    pending = bool(status['open_questions'])
    base = {'version': run['version']}
    make = lambda action, content, label, hidden=None: form(path + action, csrf, content, label, {**base, **(hidden or {})})
    stages = ['Capture', 'Decisions', 'Draft', 'Review', 'Approve', 'Handoff']
    current = {'captured': 0, 'awaiting_decision': 1, 'awaiting_revision': 2, 'awaiting_review': 3, 'awaiting_approval': 4, 'approved': 4, 'exported': 5}.get(run['state'], 0)
    body = '<a href="/">← All requirements</a><ol class="stepper" aria-label="Refinement progress">' + ''.join('<li class="' + ('done' if i < current else 'current' if i == current else '') + '"><b>' + str(i + 1) + '</b>' + label + '</li>' for i, label in enumerate(stages)) + '</ol>'
    body += '<section><div class="eyebrow">' + esc(run['project']) + ' · ' + esc(rid) + '</div><h2>' + esc(run['state'].replace('_', ' ').title()) + '</h2><p>Revision ' + str(run['revision']) + '; version ' + str(run['version']) + '. Signed in as ' + esc(status['actor']['name']) + ' (' + esc(role) + ').</p>'
    body += '<h3>Original request</h3><p>' + esc(run['brief']) + '</p>'
    if status['stale']:
        body += '<p class="error">Evidence, decisions or policy changed. A fresh draft and independent review are required.</p>'
        affected = [v['id'] for v in (status['draft'] or {}).get('statements', []) if any(c['source_id'] not in status['context']['sources'] or status['context']['sources'][c['source_id']]['digest'] != c['source_digest'] for c in v['citations'])]
        if affected: body += '<p>Changed source citations affect: ' + esc(', '.join(affected)) + '.</p>'
    if model_enabled and role in {'author', 'reviewer'} and run['state'] not in {'exported', 'rejected'}:
        stage = ('intake' if pending else 'revise' if status['draft'] else 'draft') if role == 'author' else 'review'
        label = 'Reconsider open decisions' if stage == 'intake' else 'Refine this request' if stage in AUTHOR_STAGES else 'Run independent model review'
        body += make('model', '<small>Use the selected evidence for one budgeted call. Clarification can expose follow-ups; only an authorised owner can settle decisions.</small>', label, {'stage': stage})
    elif not model_enabled and role in {'author', 'reviewer'} and run['state'] not in {'exported', 'rejected'}:
        body += '<p class="notice">Use your coding assistant below, or select a saved local model. <a href="/settings">Manage setup</a></p>'
    if role in {'author', 'reviewer'}:
        try:
            packet = request_packet(status, ('intake' if pending else 'revise' if status['draft'] else 'draft') if role == 'author' else 'review')
            usage = budget(SYSTEM, packet)
            body += '<small>Estimated input: ' + str(usage['estimated_input_tokens']) + ' tokens. Task packet: ' + str(len(canonical(packet).encode())) + ' / 200000 bytes. Reserved calls this cycle: ' + str(run['calls']) + '.</small><small>Estimate = UTF-8 bytes ÷ 3 plus 512 wrapper tokens; actual tokenizers vary. Saved model budgets below reserve output space.</small>'
        except ValidationError: pass
    body += '</section>'
    if role in {'author', 'reviewer'} and run['state'] not in {'exported', 'rejected'}:
        body += views.assistant_panel(status, csrf, root)
        available = [m for m in models if m['enabled'] and m['provider'] != 'host-assistant']
        if available:
            body += '<section><h2>Run a saved model</h2>'
            if role == 'author' and pending:
                body += '<p>Drafting waits for owner decisions. You can explicitly reconsider the open questions after receiving new information.</p>'
            stages = (['intake'] if pending else ['revise', 'draft', 'intake'] if status['draft'] else ['draft', 'intake']) if role == 'author' else ['review']
            labels = {'draft': 'Create a complete draft', 'revise': 'Revise changed items only', 'intake': 'Reconsider open decisions' if pending else 'Check missing decisions only (optional)', 'review': 'Run independent review'}
            rendered = 0
            for stage in stages:
                profiles = [model_settings(m) for m in available if m.get('stage', 'any') in {'any', stage}]
                if not profiles: continue
                try: packet = request_packet(status, stage)
                except ValidationError: continue
                section = make('model-profile', views.select('profile', 'Model connection', [(m['id'], m['id'] + ' · ' + m['model']) for m in profiles]), labels[stage], {'stage': stage})
                section += '<details><summary>Input and output budgets before running</summary><div class="tablewrap"><table><thead><tr><th>Profile</th><th>Estimated input</th><th>Output reserve</th><th>Context remaining</th></tr></thead><tbody>'
                for m in profiles:
                    usage = budget(SYSTEM, packet, output_tokens=m.get(stage + '_max_tokens', m['max_tokens']), context_tokens=m['context_tokens'])
                    remaining = 'Unknown capacity' if usage['remaining_estimated_tokens'] is None else str(usage['remaining_estimated_tokens']) + (' · blocked' if not usage['fits_estimated_context'] else '')
                    section += '<tr><td>' + esc(m['id']) + '</td><td>' + str(usage['estimated_input_tokens']) + '</td><td>' + str(usage['output_limit_tokens']) + '</td><td>' + esc(remaining) + '</td></tr>'
                section += '</tbody></table></div></details>'
                body += section if rendered == 0 else '<details><summary>' + labels[stage] + '</summary>' + section + '</details>'
                rendered += 1
            body += '<small>Each action is one explicit call. Intake is optional; complete briefs can go straight to drafting. Only selected evidence is sent. Jobs run in the background without automatic retries.</small></section>'
    if jobs:
        body += '<section aria-live="polite"><div class="row"><h2>Model activity</h2><a href="/run/' + esc(rid) + '">Refresh status</a></div>'
        for job in jobs:
            body += '<p><span class="chip gray">' + esc(job['status']) + '</span> ' + esc(job['stage']) + ' · ' + esc(job['message']) + '</p>'
            if job['status'] in {'queued', 'running', 'cancel_requested'} and (job['actor'] == status['actor']['name'] or role == 'operator'):
                body += form('/jobs/cancel', csrf, '', 'Cancel this job', {'id': job['id'], 'run_id': rid})
        body += '</section>'
    efficiency = status.get('efficiency', {})
    if efficiency.get('reserved_attempts') or efficiency.get('assistant_submissions'):
        tokens = ('Unknown' if efficiency['input_tokens'] is None else str(efficiency['input_tokens']) + ' input / ' + str(efficiency['output_tokens']) + ' output')
        body += '<section><h2>Requirement efficiency</h2><p>' + str(efficiency['attempts']) + ' finished direct attempts · ' + str(efficiency['unfinished_attempts']) + ' unfinished reservations · ' + str(efficiency['revisions']) + ' draft revisions · ' + str(efficiency['elapsed_seconds']) + ' seconds in finished attempts.</p><p>Reported tokens: ' + tokens + '. Cached input: ' + ('unknown' if efficiency['cached_input_tokens'] is None else str(efficiency['cached_input_tokens'])) + ' (' + str(efficiency['cache_measured_attempts']) + ' attempts reported cache usage).</p><small>Usage available for ' + str(efficiency['measured_attempts']) + ' / ' + str(efficiency['attempts']) + ' finished attempts, including failures. External assistant submissions: ' + str(efficiency['assistant_submissions']) + '. Questions asked: ' + str(efficiency['questions_asked']) + '; owner answers: ' + str(efficiency['owner_answers']) + '. Assistant conversation usage and price remain unknown.</small><details><summary>Totals by stage</summary><pre>' + esc(canonical(efficiency['by_stage'])) + '</pre></details></section>'
    if status.get('model_calls'):
        body += '<section><details><summary>Recorded inference measurements</summary><p>Reserved calls this cycle: ' + str(run['calls']) + ' / ' + str(status['context']['policy']['policy']['max_model_calls']) + '.</p>'
        for call in status['model_calls']:
            metrics = call.get('metrics', {})
            body += '<p><strong>' + esc(call.get('provider', 'model') + ' · ' + call['model']) + '</strong> · ' + str(call['elapsed_seconds']) + ' seconds · ' + ('result recorded' if call['succeeded'] else 'attempt failed or cancelled') + '</p>'
            if 'load_duration' in metrics: body += '<small>Model loading: %.3f seconds.</small>' % (metrics['load_duration'] / 1e9)
            if 'provider_milliseconds' in metrics: body += '<small>Provider request: %.3f seconds; validation/recording: %.3f seconds.</small>' % (metrics['provider_milliseconds'] / 1000, metrics.get('validation_milliseconds', 0) / 1000)
            body += '<pre>' + esc(canonical(metrics)) + '</pre>'
        body += '<small>Usage is reported by the selected provider when available. No semantic confidence or price is inferred.</small></details></section>'
    questions = status['context']['questions']
    eligible = {q['id'] for q in status.get('ready_questions', status['open_questions'])}
    selected = questions.get(question_id)
    q = selected if selected and (selected['id'] in eligible or selected['state'] == 'answered') else status['next_question']
    if q:
        body += '<section class="decision"><span class="eyebrow">Decision ' + esc(q['id']) + ' · ' + str(len(status['open_questions'])) + ' open</span><h2>' + ('Review decision' if q['state'] == 'answered' else 'Next decision') + '</h2><h3>' + esc(q['text']) + '</h3><p>' + esc(q['why']) + '</p>'
        response = q.get('response')
        if response:
            labels = {'confirmed': 'Previously confirmed', 'partial': 'Partial answer', 'unknown': 'Not yet known', 'proposal': 'Proposed answer', 'needs_owner': 'Another owner must decide'}
            body += '<div class="notice"><strong>' + esc(labels.get(response['kind'], response['kind'])) + '</strong><p>' + esc(response['text']) + '</p>'
            if response.get('decision_owner'): body += '<small>Decision owner: ' + esc(response['decision_owner']) + '</small>'
            body += '</div>'
        if q.get('invalidated_by'):
            body += '<p class="notice">This answer needs reconfirmation because ' + esc(', '.join(q['invalidated_by'])) + ' changed.</p>'
        if q.get('response_history'):
            body += '<details><summary>Earlier responses (history only)</summary><p>These earlier responses provide context; they do not establish a current decision.</p>'
            for earlier in q['response_history']:
                body += '<p><strong>' + esc(labels.get(earlier['kind'], earlier['kind'])) + '</strong>: ' + esc(earlier['text']) + '</p>'
                if earlier.get('decision_owner'): body += '<small>Decision owner: ' + esc(earlier['decision_owner']) + '</small>'
                if role == 'operator':
                    content = field('reason', 'Why exclude this earlier response?', textarea=True)
                    content += '<small>This changes future model context and requires fresh drafting and review. The original audit record remains. Current answers and decision sources are unaffected.</small>'
                    body += make('exclude-response-history', content, 'Exclude earlier response from context',
                                 {'question_id': q['id'], 'response_digest': digest(earlier)})
            body += '</details>'
        if q.get('excluded_response_digests'):
            body += '<p class="muted">' + str(len(q['excluded_response_digests'])) + ' earlier response(s) explicitly excluded from model context; originals remain in the audit.</p>'
        if role == 'operator':
            kinds = [('', 'Choose a response type'), ('confirmed', 'Confirmed business decision'), ('partial', 'Partial answer'), ('unknown', 'I do not know yet'), ('proposal', 'Proposal for discussion'), ('needs_owner', 'Another owner must decide')]
            content = views.select('response_kind', 'Response type', kinds, required=True) + field('answer', 'Your response', textarea=True) + field('decision_owner', 'Decision owner or team (optional)', required=False)
            content += '<small>Only a confirmed decision resolves this question. Other responses preserve the gap. Changing a confirmed decision can require dependent answers to be reconfirmed.</small>'
            body += make('answer', content, 'Record response', {'question_id': q['id']})
        else:
            body += '<p>An operator with authority over the requirement must confirm this decision. An unanswered question is not filled with an assumption.</p>'
        body += '</section>'
    if questions:
        dependencies = question_dependencies(questions)
        body += '<section><details><summary>Question and decision history</summary><ul>'
        for item in questions.values():
            title = esc(item['id'] + ' · ' + item['text'])
            if item['id'] in eligible or item['state'] == 'answered':
                title = '<a href="/run/' + esc(rid) + '?question=' + esc(item['id']) + '">' + title + '</a>'
            body += '<li>' + title + ' <span class="chip gray">' + esc(item['state'].replace('_', ' ')) + '</span>'
            if item['state'] == 'open' and item['id'] not in eligible:
                unresolved = sorted(qid for qid in dependencies[item['id']] if questions[qid]['state'] not in {'answered', 'out_of_scope'})
                body += '<small>Resolve prerequisites first: ' + esc(', '.join(unresolved)) + '.</small>'
            body += '</li>'
        body += '</ul></details></section>'
    if status['draft']:
        value = status['draft']
        body += views.example_map(value, status['checks'].get('scenario_index'), status['open_questions'])
        body += '<section><h2>' + esc(value['title']) + '</h2>'
        for statement in value['statements']:
            body += '<h3>' + esc(statement['kind'].title() + ' · ' + statement['id']) + '</h3><p>' + esc(statement['text']) + '</p><details><summary>Evidence supporting this statement</summary>'
            for citation in statement['citations']:
                body += '<small>' + esc(citation['source_id']) + ' · ' + esc(citation['source_digest'][:12]) + '</small><blockquote>' + esc(citation['quote']) + '</blockquote>'
            body += '</details>'
        body += '<h3>Canonical acceptance criteria</h3><pre>' + esc(value['feature']) + '</pre><h3>Coverage and traceability</h3>' + views.coverage_table(value['coverage']) + '</section>'
        rewritten = '\n'.join(s['text'] for s in value['statements']) + '\n\n' + value['feature']
        delta = '\n'.join(difflib.unified_diff(run['brief'].splitlines(), rewritten.splitlines(), fromfile='original request', tofile='current handoff draft', lineterm=''))
        body += '<section><details><summary>Request-to-handoff text changes</summary><small>Text comparison, not an automated judgment that every change is justified. Inspect citations and independent review.</small><pre>' + esc(delta) + '</pre></details></section>'
        body += '<section><h2>Quality findings</h2><p>' + esc(status['review']['quality']['verdict'] if status['review'] else 'Independent review pending') + '</p>'
        for f in status['checks']['findings']:
            body += '<p><strong>' + esc(f['severity'] + ' · ' + f['code']) + '</strong>: ' + esc(f['message']) + ' <code>' + esc(f['scope']) + '</code></p>'
            body += '<small>' + esc(views.finding_action(f['code'])) + '</small>'
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
        available_sources = [source for source in sources if source['project'] == run['project']]
        if available_sources:
            old = [('','Keep all current sources')] + [(v['id'], 'Replace ' + v['id']) for v in status['context']['sources'].values() if v['kind'] == 'reference']
            body += '<details><summary>Attach a source from the library</summary>' + make('attach', views.select('source_id', 'Selected source version', [(v['id'] + '|' + str(v['version']), v['title'] + ' · version ' + str(v['version'])) for v in available_sources]) + views.select('supersedes', 'Source change', old), 'Attach selected version') + '<small>Replacing a reference preserves its history and requires a fresh draft, authority confirmation and independent review.</small></details>'
        body += '<details><summary>Add a reference</summary>' + make('source', field('source_id', 'New source/revision ID') + field('title', 'Reference title') + field('locator', 'Source locator') + field('text', 'Paste the relevant source text', textarea=True), 'Capture reference for authority review') + '</details>'
    body += '</section>'
    if role in {'author', 'reviewer'}:
        action = 'submit' if role == 'author' else 'review'
        body += '<section><details><summary>Analyst tools: structured ' + action + '</summary>' + make(action, field('json', 'Validated ' + action + ' JSON', textarea=True), 'Submit ' + action) + '</details>'
        body += '<details><summary>Add a targeted owner question</summary>' + make('ask', field('question_id', 'New question ID') + field('text', 'Question in plain language') + field('why', 'Why this affects behavior or testing') + field('impact', 'Impact (1–5)', '3', kind='number') + field('prerequisites', 'Prerequisite question IDs (optional)', required=False, hint='Separate existing IDs with spaces or commas.'), 'Ask a decision-focused question') + '</details></section>'
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
            export_path = '/export/' + esc(rid) + '/' + str(approvals[-1])
            body += '<p><a class="button" href="' + export_path + '">Download handoff · 2 files</a></p><p><a href="' + export_path + '?file=requirement.md">Requirement</a> · <a href="' + export_path + '?file=acceptance.feature">Acceptance feature</a></p><details><summary>Full evidence and audit download</summary><p>The full sealed bundle includes source text, traceability, review and file hashes. These remain stored even when you download only the delivery files.</p><a href="' + export_path + '?audit=full">Download full private audit bundle</a></details>'
        body += '<details><summary>Authorize another refinement cycle</summary>' + make('cycle', field('reason', 'Reason for a new budgeted cycle', textarea=True), 'Authorize another cycle') + '</details>'
        body += '<details><summary>Resolve duplicate or out-of-scope questions</summary>' + make('resolve-question', field('question_id', 'Open question ID') + '<label>Resolution<select name="resolution"><option>merged</option><option>out_of_scope</option></select></label>' + '<label>Merge target (blank when out of scope)<input name="target"></label>' + field('reason', 'Confirmed scope decision or merge rationale', textarea=True), 'Record explicit question resolution') + '</details></section>'
    body += '<section><details><summary>Durable audit trail</summary><pre>' + esc(canonical(status['events'])) + '</pre></details></section>'
    return page('Requirement workspace', body, 'Resolve the decisions. Trace the evidence. Review the exact handoff.')


class Workbench(ThreadingHTTPServer):
    daemon_threads = True
    def __init__(self, root, port=8765, author_provider=None, reviewer_provider=None):
        self.lease = RuntimeLease(root)
        self.jobs = None
        try:
            super().__init__(('127.0.0.1', port), Handler)
            initialize_settings(root)
            self.controller = Controller(root)
            self.workspace = Workspace(root)
            self.jobs = Jobs(root)
            self.providers = {'draft': author_provider, 'review': reviewer_provider}
            self.sessions = {}
            self.session_lock = threading.Lock()
            self.origin = 'http://127.0.0.1:' + str(self.server_port)
        except BaseException:
            self.server_close()
            raise

    def server_close(self):
        if hasattr(self, 'socket'): super().server_close()
        if self.jobs: self.jobs.close()
        self.lease.close()


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
        # A global no-referrer policy makes browser form POSTs send Origin: null.
        # Preserve same-origin form headers while suppressing external referrers.
        for key, value in {'Content-Type': content_type, 'Content-Length': str(len(encoded)), 'Cache-Control': 'no-store', 'Referrer-Policy': 'same-origin', 'X-Content-Type-Options': 'nosniff', 'X-Frame-Options': 'DENY', 'Content-Security-Policy': "default-src 'none'; style-src 'unsafe-inline'; script-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'"}.items():
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
            if path == '/assets/workbench.js':
                return self.respond(200, (Path(__file__).parents[1] / 'assets/workbench.js').read_bytes(), 'text/javascript; charset=utf-8')
            token = session['token']
            if not token:
                body = '<section class="login"><span class="eyebrow">Welcome to Clarity</span><h2>Sign in to this local workspace</h2><p>Use the login key for the role you need today.</p>' + form('/login', session['csrf'], field('token', 'Workspace login key', kind='password'), 'Sign in') + '<small>Paste the contents of your author.key, reviewer.key or operator.key file created during setup. This key selects your workspace role.</small><p><strong>Author</strong> captures and drafts. <strong>Reviewer</strong> independently checks. <strong>Operator</strong> configures, answers and approves.</p><small>Run <code>clarity setup</code> first if you do not have these files. Keys stay out of URLs and browser storage.</small></section>'
                return self.respond(200, page('Welcome', body))
            if path == '/':
                runs = self.server.controller.list_runs(token)
                return self.respond(200, views.dashboard(runs, self.server.workspace.actor(token), session['csrf']))
            w = self.server.workspace
            actor = w.actor(token)
            if path == '/settings':
                models = w.records(token, 'model')
                versions = {m['id']: m['version'] for m in models}
                checks = [c for c in w.records(token, 'check') if versions.get(c['connection']) == c['connection_version']]
                return self.respond(200, views.settings(actor, session['csrf'], models, w.records(token, 'connection'), checks))
            if path == '/sources': return self.respond(200, views.sources(actor, session['csrf'], w.records(token, 'source'), w.records(token, 'connection')))
            if path == '/help': return self.respond(200, views.help_page())
            if path == '/projects':
                from ..storage import transaction
                from .controller import _policy, _records
                with transaction(self.server.controller.root, write=False) as db:
                    projects = {r[0] for r in db.execute('SELECT DISTINCT project FROM refine_runs')} | {r['data']['project'] for r in _records(db, None, 'policy')} | {'PERSONAL'}
                    policies = {p: _policy(db, p) for p in sorted(projects)}
                return self.respond(200, views.projects(actor, session['csrf'], policies))
            bits = path.strip('/').split('/')
            if len(bits) == 3 and bits[0] == 'run' and bits[2] == 'task.json':
                task = host_bridge.packet(self.server.controller, token, bits[1], parse_qs(parts.query).get('stage', [None])[0])
                return self.respond(200, canonical(task) + '\n', 'application/json', download=bits[1] + '-task.json')
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
                return self.respond(200, render_status(status, session['csrf'], self.server.providers[stage] is not None, planned, error, models=w.records(token, 'model'), sources=w.records(token, 'source'), jobs=self.server.jobs.list(token, bits[1]), root=self.server.controller.root, question_id=parse_qs(parts.query).get('question', [None])[0]))
            if len(bits) == 3 and bits[0] == 'export':
                bundle = self.server.controller.exported(token, bits[1], int(bits[2]))
                query = parse_qs(parts.query)
                if 'file' in query:
                    name = query['file'][0]
                    require(name in {'requirement.md', 'acceptance.feature'}, 'Choose a delivery file')
                    # Validate the same sealed file hashes used by either archive.
                    verify_bundle(bundle)
                    return self.respond(200, bundle['files'][name], 'text/plain; charset=utf-8', download=name)
                full = query.get('audit', [''])[0] == 'full'
                return self.respond(200, archive(bundle, full_audit=full), 'application/zip', download=bits[1] + ('-audit.zip' if full else '-handoff.zip'))
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
                rid = data['id'] or 'REQ-' + secrets.token_hex(5)
                c.create(token, rid, data['project'], data['brief'], data['presentation'])
                return self.respond(303, '', location='/run/' + rid)
            w = self.server.workspace
            if path in {'/settings/model', '/settings/connection'}:
                kind = path.rsplit('/', 1)[1]; object_id = data.pop('id'); version = int(data.pop('version')); credential = data.pop('credential')
                clear_credential = boolean(data.pop('clear_credential', 'false'))
                data['enabled'] = boolean(data['enabled'])
                if kind == 'model':
                    data['allow_cloud'] = boolean(data['allow_cloud'])
                    for name in ('port', 'max_tokens', 'timeout', 'keep_alive', 'context_tokens', 'intake_max_tokens', 'review_max_tokens', 'revise_max_tokens'):
                        if name in data: data[name] = int(data[name])
                w.save(token, kind, object_id, version, data, credential, clear_credential)
                return self.respond(303, '', location='/settings')
            if path == '/settings/probe':
                require(set(data) == {'id', 'version'}, 'Invalid diagnostic fields')
                w.probe(token, data['id'], int(data['version']))
                return self.respond(303, '', location='/settings')
            if path == '/sources/save':
                object_id = data.pop('id') or 'SRC-' + secrets.token_hex(6); version = int(data.pop('version'))
                data['retrieved_at'] = time.time()
                w.save(token, 'source', object_id, version, data)
                return self.respond(303, '', location='/sources')
            if path == '/sources/import':
                require(set(data) == {'connection', 'item', 'project'}, 'Invalid source import fields')
                w.import_source(token, data['connection'], data['item'], data['project'])
                return self.respond(303, '', location='/sources')
            if path == '/projects/save':
                require(set(data) == {'project', 'record', 'risk_ids', 'canonical_steps', 'max_rewrites', 'max_model_calls'}, 'Invalid policy fields')
                c.set_policy(token, data['project'], {'version': 1, 'risk_ids': [v.strip() for v in data['risk_ids'].splitlines() if v.strip()], 'canonical_steps': [v.strip() for v in data['canonical_steps'].splitlines() if v.strip()], 'max_rewrites': int(data['max_rewrites']), 'max_model_calls': int(data['max_model_calls'])}, int(data['record']))
                return self.respond(303, '', location='/projects')
            if path == '/jobs/cancel':
                require(set(data) == {'id', 'run_id'}, 'Invalid cancellation fields')
                c.status(token, data['run_id'])
                self.server.jobs.cancel(token, data['id'])
                return self.respond(303, '', location='/run/' + data['run_id'])
            bits = path.strip('/').split('/')
            require(len(bits) == 3 and bits[0] == 'run', 'Unknown action')
            rid, action = bits[1:]; version = int(data.pop('version'))
            # Never dynamically resolve a function name from untrusted input.
            allowed = {'answer': {'question_id', 'answer', 'response_kind', 'decision_owner'}, 'source': {'source_id', 'title', 'text', 'locator'}, 'attach': {'source_id', 'supersedes'}, 'confirm-source': {'source_id', 'source_digest', 'reason'}, 'submit': {'json'}, 'assistant': {'json', 'context_digest'}, 'review': {'json'}, 'model': {'stage'}, 'model-profile': {'stage', 'profile'}, 'ask': {'question_id', 'text', 'why', 'impact', 'prerequisites'}, 'signal': {'finding_id', 'reason'}, 'cycle': {'reason'}, 'approve': {'profile', 'plan_digest'}, 'seal': {'approval_id'}, 'resolve-question': {'question_id', 'resolution', 'target', 'reason'}}
            allowed['exclude-response-history'] = {'question_id', 'response_digest', 'reason'}
            require(action in allowed and set(data) == allowed[action], 'Invalid action fields')
            if action == 'answer': c.answer(token, rid, version, data['question_id'], data['answer'], response_kind=data['response_kind'], decision_owner=data['decision_owner'].strip() or None)
            elif action == 'exclude-response-history': c.exclude_response_history(token, rid, version, data['question_id'], data['response_digest'], data['reason'])
            elif action == 'source': c.add_source(token, rid, version, data['source_id'], data['title'], data['text'], data['locator'])
            elif action == 'attach':
                source_id, source_version = data['source_id'].split('|')
                w.attach(token, rid, version, source_id, data['supersedes'], int(source_version))
            elif action == 'assistant': host_bridge.submit(c, token, rid, version, data['context_digest'], decode(data['json']))
            elif action == 'confirm-source': c.confirm_source(token, rid, version, data['source_id'], data['source_digest'], data['reason'])
            elif action == 'submit': c.submit(token, rid, version, decode(data['json']))
            elif action == 'review': c.review(token, rid, version, decode(data['json']))
            elif action == 'ask': c.ask(token, rid, version, {'id': data['question_id'], 'text': data['text'], 'why': data['why'], 'impact': int(data['impact']), 'prerequisites': data['prerequisites'].replace(',', ' ').split()})
            elif action == 'signal': c.resolve_signal(token, rid, version, data['finding_id'], data['reason'])
            elif action == 'cycle': c.new_cycle(token, rid, version, data['reason'])
            elif action == 'resolve-question': c.resolve_question(token, rid, version, data['question_id'], data['resolution'], data['target'] or None, data['reason'])
            elif action == 'approve': c.approve(token, rid, version, data['plan_digest'], data['profile'])
            elif action in {'model', 'model-profile'}:
                provider = w.provider(token, data['profile'], data['stage']) if action == 'model-profile' else self.server.providers.get('draft' if data['stage'] in AUTHOR_STAGES else data['stage'])
                require(provider is not None, 'This model stage is not configured')
                self.server.jobs.start(token, rid, version, data['stage'], provider)
            elif action == 'seal':
                # Seal itself rechecks the exact immutable approval and current state.
                c.seal(token, rid, int(data['approval_id']))
                return self.respond(303, '', location='/export/' + rid + '/' + str(int(data['approval_id'])))
            return self.respond(303, '', location='/run/' + rid)
        except (ValidationError, ValueError, KeyError, TypeError, UnicodeError, sqlite3.Error, OSError) as exc:
            message = str(exc) if isinstance(exc, ValidationError) else 'Malformed request or local storage operation failed.'
            self.respond(400, page('Action not completed', '<section class="error"><p>' + esc(message) + '</p><p>Refresh the requirement before retrying. A failed model attempt may have used its reserved budget; no approval or publication is implied.</p><a href="/">Return to workspace</a></section>'))
