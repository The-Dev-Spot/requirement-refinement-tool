"""Escaped server-rendered views for the local Clarity workbench."""
import html
import json
from pathlib import Path
from ..guardrails import canonical

CSS = (Path(__file__).parents[1] / 'assets/workbench.css').read_text()


def esc(value): return html.escape(str(value), quote=True)


def field(name, label, value='', textarea=False, kind='text', required=True, hint=''):
    needed = ' required' if required else ''
    attr = ' name="' + esc(name) + '"'
    control = '<textarea' + attr + needed + '>' + esc(value) + '</textarea>' if textarea else '<input type="' + esc(kind) + '"' + attr + ' value="' + esc(value) + '"' + needed + '>'
    return '<label>' + esc(label) + control + ('<small>' + esc(hint) + '</small>' if hint else '') + '</label>'


def select(name, label, options, selected=''):
    return '<label>' + esc(label) + '<select name="' + esc(name) + '">' + ''.join('<option value="' + esc(key) + '"' + (' selected' if str(key) == str(selected) else '') + '>' + esc(value) + '</option>' for key, value in options) + '</select></label>'


def form(action, csrf, content, button, hidden=None):
    values = {'csrf': csrf, **(hidden or {})}
    controls = ''.join('<input type="hidden" name="' + esc(k) + '" value="' + esc(v) + '">' for k, v in values.items())
    return '<form method="post" action="' + esc(action) + '">' + controls + content + '<button type="submit">' + esc(button) + '</button></form>'


def page(title, body, subtitle='Turn a rough idea into a requirement people can build and test.'):
    return '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>' + esc(title) + ' · Clarity</title><style>' + CSS + '</style><script src="/assets/workbench.js" defer></script></head><body><a class="skip" href="#main">Skip to content</a><header class="topbar"><div class="topinner"><a class="brand" href="/"><span class="mark" aria-hidden="true">c</span>Clarity</a><nav aria-label="Main"><a href="/">Requirements</a><a href="/sources">Sources</a><a href="/settings">Setup</a><a href="/help">Guide</a></nav><span class="local">● LOCAL WORKSPACE</span></div></header><main id="main" class="wrap"><div class="intro"><div><span class="eyebrow">From intent to shared understanding</span><h1>' + esc(title) + '</h1><p>' + esc(subtitle) + '</p></div></div>' + body + '<footer>Clarity · Local evidence, explicit decisions, one approved handoff.</footer></main></body></html>'


def dashboard(runs, actor, csrf):
    pending = sum(r['state'] == 'awaiting_decision' for r in runs)
    done = sum(r['state'] == 'exported' for r in runs)
    body = '<div class="row"><p class="muted">Signed in as <strong>' + esc(actor['actor']) + '</strong> · ' + esc(actor['role']) + '</p>' + form('/logout', csrf, '', 'Sign out') + '</div>'
    body += '<div class="stats">' + ''.join('<div class="stat"><strong>' + str(n) + '</strong><small>' + label + '</small></div>' for n, label in [(len(runs), 'Requirements'), (pending, 'Waiting for a decision'), (done, 'Sealed handoffs')]) + '</div>'
    body += '<div class="two-col"><section><div class="row"><h2>Your requirements</h2><span class="chip gray">' + str(len(runs)) + ' captured</span></div>'
    for r in runs:
        body += '<article class="story"><h3><a href="/run/' + esc(r['id']) + '">' + esc(r['id']) + ' <span aria-hidden="true">↗</span></a></h3><p>' + esc(r['brief'][:170]) + '</p><span class="chip ' + ('pending' if r['state'] == 'awaiting_decision' else 'gray') + '">' + esc(r['state'].replace('_', ' ')) + '</span><small>' + esc(r['project']) + ' · Revision ' + str(r['revision']) + '</small></article>'
    if not runs: body += '<div class="empty"><h3>Your next good requirement starts here.</h3><p>Capture the problem in your own words. Clarity will help expose the decisions that matter.</p></div>'
    body += '</section><section><span class="eyebrow">01 · Capture</span><h2>Start with the problem</h2>'
    if actor['role'] == 'author':
        body += form('/create', csrf, field('id', 'Brief ID', required=False, hint='Optional. Leave blank to create an ID.') + field('project', 'Project ID', 'PERSONAL') + field('brief', 'What needs to change, and why?', textarea=True) + select('presentation', 'How would you like guidance?', [('guided', 'Plain-language guidance'), ('concise', 'Concise analyst guidance')]), 'Capture request')
    else: body += '<p>Use your author login key to capture or draft a requirement. This ' + esc(actor['role']) + ' session handles ' + ('owner decisions, configuration and approval.' if actor['role'] == 'operator' else 'independent review.') + '</p>'
    body += '<small>The same handoff standard applies to both conversation styles.</small></section></div>'
    body += '<section><h2>Make Clarity yours</h2><div class="grid"><div><h3>Use your coding assistant</h3><p>Connect Copilot, Codex or Claude Code using the scoped MCP bridge.</p><a href="/settings">Choose your setup →</a></div><div><h3>Bring the right context</h3><p>Save relevant policies, notes or selected tracker pages. Attach only what a requirement needs.</p><a href="/sources">Open source library →</a></div><div><h3>Keep decisions visible</h3><p>Resolve owner questions, review the evidence and approve the exact handoff.</p><a href="/help">Read the workflow →</a></div></div></section>'
    return page('A little clarity goes a long way.', body)


MODEL_OPTIONS = [('host-assistant', 'Copilot / Codex / Claude Code (MCP)'), ('ollama', 'Ollama on this machine'), ('local-openai', 'Local OpenAI-compatible server'), ('openai', 'OpenAI API (optional cloud)'), ('anthropic', 'Anthropic API (optional cloud)')]


def settings(actor, csrf, models, connections, checks):
    editable = actor['role'] == 'operator'
    body = '<div class="notice">Choose your assistant or local model, add source connections, then capture a requirement. Configuration never grants approval.</div><section><span class="eyebrow">Your existing assistant</span><h2>Copilot, Codex or Claude Code</h2><p>Use the assistant and account you already have. Open a requirement as author or reviewer and choose <strong>Connect your assistant</strong> for its scoped MCP setup and task packet.</p><p>Assistant login stays in that application. Clarity never asks for your subscription token.</p><a href="/help#assistants">Assistant setup guide →</a></section>'
    if not editable: body += '<p class="notice">Sign in with your operator login key to change configuration. You can inspect the saved, credential-free settings below.</p>'
    body += '<section><div class="row"><h2>Models &amp; assistants</h2><span class="chip gray">' + str(len(models)) + ' saved</span></div>'
    for m in models:
        clean = {k: v for k, v in m.items() if k not in {'version', 'id', 'secret_present'}}
        body += '<details><summary>' + esc(m['id']) + ' · ' + esc(m['provider']) + ' · ' + esc(m['model']) + '</summary><small>Credential: ' + ('configured' if m.get('secret_present') else 'not stored') + ' · Version ' + str(m['version']) + '</small>'
        if editable: body += model_form(csrf, m)
        else: body += '<pre>' + esc(canonical(clean)) + '</pre>'
        body += '</details>'
    if editable: body += '<details open><summary>Add a model or assistant profile</summary>' + model_form(csrf, {}) + '</details>'
    body += '<small>Local model URLs are fixed to 127.0.0.1 at your chosen port. A loopback gateway can still forward data elsewhere; verify its deployment. Cloud profiles require explicit sharing permission.</small></section>'
    body += '<section><h2>Source connections</h2><p>Imports are read-only and limited to an explicitly selected issue or page within the configured project or space.</p>'
    for c in connections:
        body += '<details><summary>' + esc(c['id']) + ' · ' + esc(c['provider']) + '</summary><small>Credential: ' + ('configured' if c.get('secret_present') else 'not stored') + ' · Version ' + str(c['version']) + '</small>'
        body += connection_form(csrf, c) if editable else '<p>Scope: ' + esc(c['scope']) + '</p>'
        body += '</details>'
    if editable: body += '<details><summary>Add a source connection</summary>' + connection_form(csrf, {}) + '</details>'
    body += '<p>Use manual text capture for other sources, self-hosted trackers or documents.</p></section><section><h2>Project quality settings</h2><p>Set the project risk register, reusable step language and bounded refinement budgets. Changes require a new draft and review.</p><a class="button secondary" href="/projects">Manage project policy</a></section>'
    body += '<section><h2>Connection checks</h2><p>Checks use synthetic data. They test protocol access, never semantic requirement quality.</p>'
    for c in checks: body += '<p><span class="chip ' + ('pending' if c['status'] != 'passed' else '') + '">' + esc(c['status']) + '</span> ' + esc(c['connection']) + ': ' + esc(c['message']) + '</p>'
    if not checks: body += '<p class="muted">No diagnostics have been run yet.</p>'
    body += '</section>'
    return page('Set up your workspace', body, 'Your assistant, your sources, your quality settings.')


def model_form(csrf, m):
    from ..workspace import model_settings
    m = model_settings(m)
    content = field('id', 'Profile name / ID', m.get('id', '')) + select('provider', 'Connection type', MODEL_OPTIONS, m.get('provider', 'host-assistant')) + field('model', 'Exact model ID or assistant name', m.get('model', 'Codex'))
    content += '<div class="grid">' + field('port', 'Local server port', m.get('port', 11434), kind='number') + field('max_tokens', 'Maximum output tokens', m.get('max_tokens', 8192), kind='number') + field('timeout', 'Timeout in seconds', m.get('timeout', 120), kind='number') + field('keep_alive', 'Ollama keep-alive seconds', m.get('keep_alive', 300), kind='number') + '</div>'
    content += '<details><summary>Efficiency and stage settings</summary>' + select('stage', 'Use this profile for', [('any', 'Any stage'), ('intake', 'Intake questions'), ('draft', 'Complete draft'), ('revise', 'Targeted revision'), ('review', 'Independent review')], m['stage'])
    content += '<div class="grid">' + field('context_tokens', 'Server context capacity in tokens (0 = unknown)', m['context_tokens'], kind='number', hint='Use the capacity actually configured on the server. Input estimates reserve the selected output budget; no source is silently truncated.') + field('intake_max_tokens', 'Intake output token limit', m['intake_max_tokens'], kind='number') + field('revise_max_tokens', 'Revision output token limit', m['revise_max_tokens'], kind='number') + field('review_max_tokens', 'Review output token limit', m['review_max_tokens'], kind='number') + '</div>'
    content += select('cache_mode', 'Cloud prompt cache', [('provider', 'Provider default'), ('prefix', 'Explicit stable prefix (supported cloud models only)')], m['cache_mode']) + '<small>Explicit prefix caching requires compatible API support; test this profile after changing it. Local servers reuse stable prompts according to their own cache settings. Ollama keep-alive controls loading, not context capacity.</small></details>'
    content += field('credential', 'API key (optional; blank keeps saved key)', kind='password', required=False) + select('allow_cloud', 'Send selected evidence to this cloud provider?', [('false', 'No'), ('true', 'Yes, explicitly allow')], str(m.get('allow_cloud', False)).lower()) + select('enabled', 'Profile status', [('true', 'Enabled'), ('false', 'Disabled')], str(m.get('enabled', True)).lower())
    content += select('clear_credential', 'Saved credential', [('false', 'Keep when connection is unchanged'), ('true', 'Remove from this profile')])
    result = form('/settings/model', csrf, content, 'Save model profile', {'version': m.get('version', 0)})
    if m.get('id') and m.get('provider') != 'host-assistant': result += form('/settings/probe', csrf, '<small>Sends only a fixed synthetic request. Cloud API charges may apply.</small>', 'Test structured output', {'id': m['id'], 'version': m['version']})
    return result


def connection_form(csrf, c):
    content = field('id', 'Connection name / ID', c.get('id', '')) + select('provider', 'Source service', [('linear', 'Linear'), ('jira-cloud', 'Jira Cloud'), ('confluence-cloud', 'Confluence Cloud')], c.get('provider', 'linear')) + field('host', 'Atlassian tenant hostname (blank for Linear)', c.get('host', ''), required=False, hint='Tenant only, for example your-team.atlassian.net. No URL or path.') + field('username', 'Atlassian account email (blank for Linear)', c.get('username', ''), required=False) + field('scope', 'Allowed Linear team ID / Jira project key / Confluence space ID', c.get('scope', '')) + field('project_scope', 'Optional Linear project ID', c.get('project_scope', ''), required=False) + field('credential', 'Service token (blank keeps saved token)', kind='password', required=False) + select('enabled', 'Connection status', [('true', 'Enabled'), ('false', 'Disabled')], str(c.get('enabled', True)).lower())
    content += select('clear_credential', 'Saved credential', [('false', 'Keep when connection is unchanged'), ('true', 'Remove from this profile')])
    return form('/settings/connection', csrf, content, 'Save source connection', {'version': c.get('version', 0)})


def sources(actor, csrf, values, connections):
    editable = actor['role'] in {'author', 'operator'}
    body = '<div class="notice">Capture relevant excerpts. Saving a source preserves it locally; attaching it selects a version for one requirement. An operator confirms whether it is authoritative.</div><section><h2>Source library</h2>'
    for s in values:
        body += '<details><summary>' + esc(s['title']) + ' <span class="chip gray">' + esc(s['project']) + '</span></summary><div class="source-meta"><span>' + esc(s['id']) + '</span><span>Revision ' + esc(s['revision']) + '</span><span>Version ' + str(s['version']) + '</span><span>Effective: ' + esc(s['effective_date'] or 'not stated') + '</span></div><p>' + esc(s['locator']) + '</p><pre>' + esc(s['text']) + '</pre>'
        if editable: body += '<details><summary>Save a new version</summary>' + source_form(csrf, s) + '</details>'
        body += '</details>'
    if not values: body += '<div class="empty"><h3>Bring the context that matters.</h3><p>A policy, a decision, a customer note or an existing specification can make the next question much clearer.</p></div>'
    body += '</section>'
    if editable:
        body += '<div class="grid"><section><h2>Capture text or a file</h2>' + source_form(csrf, {}) + '</section><section><h2>Import a selected issue or page</h2>'
        if connections: body += form('/sources/import', csrf, select('connection', 'Saved connection', [(c['id'], c['id'] + ' · ' + c['provider']) for c in connections if c['enabled']]) + field('item', 'Issue key, Linear issue ID or Confluence page ID') + field('project', 'Clarity project', 'PERSONAL'), 'Read and save selected source')
        else: body += '<p>Add a source connection in Setup, or capture text here.</p><a href="/settings">Configure a connection →</a>'
        body += '<small>No search across unrelated projects, remote edits or bulk ingestion. After import, inspect the captured source before attaching it.</small></section></div>'
    return page('The right context, in one place.', body, 'Versioned source material for better questions and traceable requirements.')


def source_form(csrf, s):
    content = field('id', 'Source ID (optional for a new source)', s.get('id', ''), required=False) + field('project', 'Clarity project', s.get('project', 'PERSONAL')) + field('title', 'Source title', s.get('title', '')) + field('locator', 'Where this source came from', s.get('locator', ''), hint='A reference label or URL. Clarity does not fetch this field.') + '<label>Load a UTF-8 text or Markdown file<input type="file" accept=".txt,.md,.feature,.csv" data-text-upload="text"><small role="status">The selected file appears below for review.</small></label>' + field('text', 'Relevant source text', s.get('text', ''), textarea=True) + field('revision', 'Source revision or version label', s.get('revision', 'manual')) + field('effective_date', 'Effective date, if known', s.get('effective_date', ''), kind='date', required=False)
    # Each editor uses its own form-local file target; IDs are fixed up by the script.
    return form('/sources/save', csrf, content, 'Save source version', {'version': s.get('version', 0)})


def projects(actor, csrf, policies):
    body = '<section><h2>Project policy register</h2><p>Policies bind every requirement in the project. Use stable risk IDs and one reusable step per line. Updating a policy invalidates earlier draft/review context.</p>'
    for key, value in policies.items():
        body += '<details><summary>' + esc(key) + ' · version ' + str(value['record']) + '</summary>'
        body += policy_form(csrf, key, value['policy'], value['record']) if actor['role'] == 'operator' else '<pre>' + esc(canonical(value)) + '</pre>'
        body += '</details>'
    if actor['role'] == 'operator':
        from .contracts import DEFAULT_POLICY
        body += '<details><summary>Add a project policy</summary>' + policy_form(csrf, '', DEFAULT_POLICY, 0) + '</details>'
    else: body += '<p>Use an operator login key to change policy.</p>'
    body += '</section>'
    return page('Project quality settings', body)


def help_page():
    return page('A clear path from idea to handoff.', '''<section><h2>First-time setup</h2><ol class="help-list"><li>Run <code>clarity setup</code>, then <code>clarity start</code>. Setup prints the locations of three private login-key files.</li><li>Sign in with <strong>operator.key</strong>. Open Setup to save a local model or source connection and configure project policy.</li><li>Sign out, then use <strong>author.key</strong> to capture the problem, attach relevant source versions and draft with your assistant or local model.</li></ol></section><section id="assistants"><h2>Use Copilot, Codex or Claude Code</h2><ol class="help-list"><li>Open a requirement as author. Expand <strong>Connect your assistant</strong>.</li><li>Copy the MCP configuration for your client. Use absolute paths to the workspace and <strong>author.key</strong>. Keep <strong>operator.key</strong> outside the assistant's access.</li><li>Ask the assistant to call <code>clarity_get_task</code>, investigate the supplied evidence and submit the required JSON using <code>clarity_submit_result</code>.</li><li>For independent review, start a fresh assistant conversation with the <strong>reviewer.key</strong> configuration. Do not reuse the writer's conversation as the independent review.</li></ol><p>You can also download a task packet and import its structured result. Your assistant's own subscription, login and data policies still apply. Clarity does not convert a subscription into an API key.</p></section><section><h2>The daily workflow</h2><ol class="help-list"><li><strong>Capture.</strong> State the problem and business value in your own words. Select only the relevant context.</li><li><strong>Decide.</strong> Clarity exposes missing decisions and explains why they matter. Use operator login to confirm business answers and source applicability.</li><li><strong>Draft.</strong> The author produces source-linked statements, Gherkin scenarios and coverage. Missing facts remain questions.</li><li><strong>Review.</strong> A separate reviewer checks meaning, completeness and ambiguity. Objective blockers must be fixed.</li><li><strong>Approve.</strong> The operator checks the exact handoff and approves that revision. Approval expires after 15 minutes.</li><li><strong>Handoff.</strong> Seal and download the approved bundle. Import only <code>acceptance.feature</code> into test management.</li></ol></section><section><h2>Local model setup</h2><p>Start Ollama or an OpenAI-compatible server such as LM Studio or vLLM on this machine. In Setup, choose its protocol, exact model ID, port and output budget. Test structured output with synthetic data before a real requirement. No model is downloaded automatically.</p><p>The local server must support the requested JSON schema and sufficient context/output length. A successful connection check does not prove semantic quality; use the evaluation guide before relying on a new model.</p></section><section><h2>When something needs attention</h2><ul class="help-list"><li><strong>Cross-origin error:</strong> open the exact <code>http://127.0.0.1:8765</code> address printed at startup and refresh the sign-in page.</li><li><strong>Stale version:</strong> refresh the requirement. Evidence, answers, policy or another operation changed its version.</li><li><strong>Oversized context:</strong> capture smaller relevant excerpts. Preflight rejection does not consume a model call.</li><li><strong>Provider failure:</strong> inspect the job status and explicitly retry. An inference attempt may already have consumed a reserved call.</li><li><strong>Pending decisions:</strong> use operator login to answer them. Repeated model calls cannot substitute for an owner decision.</li><li><strong>After restore:</strong> create fresh login keys and reconnect services. Backups exclude credentials.</li></ul><p>Run <code>clarity doctor</code> for local setup diagnostics. Detailed guides live in the repository's <code>docs/</code> directory.</p></section>''')


def coverage_table(rows):
    return '<div class="tablewrap"><table><thead><tr><th>Statement</th><th>Behavior</th><th>Scenarios / applicability</th></tr></thead><tbody>' + ''.join('<tr><td>' + esc(row['statement_id']) + '</td><td>' + esc(row['category']) + '</td><td>' + esc(', '.join(row['scenario_ids']) or row['not_applicable_reason'] or 'Missing coverage') + '</td></tr>' for row in rows) + '</tbody></table></div>'


def assistant_panel(status, csrf, root):
    run = status['run']; role = status['actor']['role']; rid = run['id']
    state_path = str(Path(root).absolute()) if root else '/absolute/path/to/clarity-state'
    key_path = str(Path(state_path) / 'keys' / (role + '.key'))
    args = ['mcp', '--state', state_path, '--key-file', key_path, '--id', rid]
    vscode = {'servers': {'clarity': {'type': 'stdio', 'command': 'clarity', 'args': args}}}
    claude = {'mcpServers': {'clarity': {'command': 'clarity', 'args': args}}}
    toml = '[mcp_servers.clarity]\ncommand = "clarity"\nargs = ' + json.dumps(args) + '\n'
    content = '<section><details><summary>Connect your assistant · Copilot / Codex / Claude Code</summary><p>Connect this one requirement with a <strong>' + esc(role) + '</strong> credential. Use <code>clarity_get_task</code> and <code>clarity_submit_result</code>; <code>clarity_get_findings</code> retrieves diagnostics only when needed.</p><p>Use absolute paths to your installed <code>clarity</code> executable and login-key file. The paths below use the default setup; adjust them if yours differ. Keep the operator key outside assistant access.</p>'
    content += '<details><summary>VS Code Copilot · workspace MCP configuration</summary><pre>' + esc(json.dumps(vscode, indent=2)) + '</pre></details><details><summary>Claude Code · MCP server configuration</summary><pre>' + esc(json.dumps(claude, indent=2)) + '</pre></details><details><summary>Codex · MCP server configuration</summary><pre>' + esc(toml) + '</pre></details>'
    content += '<p>Ask your assistant: “Call clarity_get_task. Investigate the supplied sources, follow the contract and submit the result with clarity_submit_result. Ask consequential questions where facts are missing.”</p><p>For independent review, use a fresh reviewer conversation with the reviewer key.</p><a class="button secondary" href="/run/' + esc(rid) + '/task.json">Download task packet</a><details><summary>Import assistant result manually</summary>'
    if role == 'author':
        content += '<p>Author tasks use targeted revision when a draft exists. Optional packets: <a href="/run/' + esc(rid) + '/task.json?stage=intake">intake questions only</a> · <a href="/run/' + esc(rid) + '/task.json?stage=draft">complete draft</a>. For MCP, append <code>--stage intake</code> or <code>--stage draft</code> to the command arguments.</p>'
    content += form('/run/' + rid + '/assistant', csrf, field('json', 'Assistant JSON result', textarea=True), 'Validate and record assistant result', {'version': run['version'], 'context_digest': status['context_digest']}) + '</details></details></section>'
    return content


def policy_form(csrf, project, policy, record):
    content = field('project', 'Project ID', project) + field('risk_ids', 'Applicable risk IDs, one per line', '\n'.join(policy['risk_ids']), textarea=True, required=False) + field('canonical_steps', 'Canonical step text, one per line', '\n'.join(policy['canonical_steps']), textarea=True, required=False) + field('max_rewrites', 'Maximum rewrites per cycle (1–3)', policy['max_rewrites'], kind='number') + field('max_model_calls', 'Maximum model calls per cycle (1–12)', policy['max_model_calls'], kind='number')
    return form('/projects/save', csrf, content, 'Record project policy', {'record': record})


def finding_action(code):
    actions = {'invalid_gherkin': 'Fix the tagged scenario, Given/When/Then structure or missing Examples parameters, then submit a new draft.', 'stale_or_missing_source': 'Attach the correct source version and regenerate the affected statement and review.', 'unconfirmed_authority': 'Ask the operator to confirm this source’s applicability with a reason.', 'fabricated_quote': 'Replace the citation with an exact supporting passage; if none exists, ask an owner question.', 'missing_coverage': 'Add the missing example, or record why this category does not apply and have the reviewer assess it.', 'quantity_unit': 'Confirm the unit with the owner or cited source. The reviewer may explain why it is already clear.', 'numeric_boundary': 'Ask whether equality belongs inside or outside the permitted range, and show that example.', 'time_context': 'Check the intended zone, local-time behavior and exact time boundary with the owner.', 'domain_term': 'Add a source-supported definition if the term changes interpretation.', 'numeric_rule_difference': 'Compare both cited policies and obtain the owner’s decision on which rule applies.'}
    return actions.get(code, 'Inspect the affected statement/scenario and its cited evidence. Correct a hard failure; contextual warnings need an independent rationale.')


def example_map(value, index, questions):
    body = '<section><span class="eyebrow">Rules · examples · questions</span><h2>Map the behavior</h2><p>Check an ordinary case, a refusal, an exact boundary and another path for each rule.</p><div class="grid">'
    for rule in value['statements']:
        if rule['kind'] not in {'rule', 'constraint'}: continue
        body += '<article class="card"><span class="chip gray">' + esc(rule['id']) + '</span><h3>' + esc(rule['text']) + '</h3>'
        related = [row for row in value['coverage'] if row['statement_id'] == rule['id']]
        for row in related:
            body += '<p><strong>' + esc(row['category'].title()) + '</strong> · ' + esc(', '.join(row['scenario_ids']) or row['not_applicable_reason'] or 'Needs an example') + '</p>'
        for example in (index or {}).get('examples', []):
            ids = {s['id'] for s in value['scenarios'] if rule['id'] in s['statement_ids']}
            if ids.intersection(example['scenario_ids']): body += '<details><summary>' + esc(example['name']) + '</summary><pre>' + esc('\n'.join(example['steps'])) + '</pre></details>'
        body += '</article>'
    body += '</div>'
    if questions: body += '<p class="notice">Open decisions: ' + esc(', '.join(q['id'] for q in questions)) + '. Resolve them before treating these examples as agreed behavior.</p>'
    return body + '</section>'
