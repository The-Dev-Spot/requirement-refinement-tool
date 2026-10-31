// Maintainer checks only. This does not implement the runtime L1–L10 contract.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { parseDocument } from 'yaml';
import { AstBuilder, Parser, GherkinClassicTokenMatcher, compile } from '@cucumber/gherkin';
import { IdGenerator } from '@cucumber/messages';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const read = p => fs.readFileSync(path.join(root, p), 'utf8');
const walk = dir => fs.readdirSync(path.join(root, dir), {withFileTypes:true})
  .filter(x => !['.git', 'node_modules', '__pycache__'].includes(x.name))
  .flatMap(x => x.isDirectory() ? walk(path.join(dir,x.name)) : [path.join(dir,x.name)]);
const files = walk('');
let assertions = 0;
const check = (condition, message) => {assert.ok(condition,message); assertions++;};
const yaml = p => {
  const doc = parseDocument(read(p), {uniqueKeys:true});
  assert.deepEqual(doc.errors, [], `${p}: invalid YAML`);
  assertions++; return doc.toJS();
};
for (const file of files.filter(p => /\.ya?ml$/.test(p))) yaml(file);
const config = yaml('.github/project-config.yaml');
check(config.jira.base_url.endsWith('.example.invalid'), 'Jira URL must be fictional');
check(config.confluence.base_url.endsWith('.example.invalid'), 'Confluence URL must be fictional');
check(config.jira.project_key === 'DEMO', 'Only a fictional project may ship');
check(Object.values(config.jira.custom_fields).every(x => x === null), 'No live custom field IDs');
check(config.confluence.log_book.root_page_id === null, 'No live evidence root');
check(config.jira.teams.length === 0 && config.confluence.seed_pages.length === 0, 'No live teams or source pages');
check(JSON.stringify(JSON.parse(read('.github/mcp.json.example'))) === '{"mcpServers":{}}', 'No shipped MCP connections');
const contract = yaml('.github/agents/runtime-doc-contract.yaml');
assert.deepEqual(contract.workflow.stage_order, ['investigate','evaluate','rewrite','quality_gate','po_analysis','awaiting_approval','awaiting_po']); assertions++;
check(contract.intake_workflow.investigate_depth_default === 'DEEP', 'Intake must investigate deeply');
check(contract.write_policy.jira_write_trigger === 'explicit_operator_approval_only', 'Approval gate required');
check(contract.write_policy.approval_commands.includes('just add comments'), 'Comments-only command must be represented');
check(contract.workflow.closure_rule.otherwise_if_open_questions_remain === 'awaiting_po', 'Open questions do not close a run');
check(contract.retention.git_tracked === false, 'Runtime records stay private');
check(contract.workflow.closure_rule.first_if_comments_only_and_ready === 'awaiting_approval', 'Comments-only READY stays staged');
const exceptions = contract.write_policy.explicit_exceptions;
assert.deepEqual(exceptions.comments_only.forbidden, ['update_description','update_ac_checklist']); assertions++;
assert.deepEqual(exceptions.po_override.modes, ['review','apply']); assertions++;
check(exceptions.po_override.if_open_questions === 'awaiting_po' && exceptions.po_override.keep_open_question_markers, 'Override preserves questions and stays open');
check(contract.write_policy.ac_field_policy === 'description_and_create_writes_only', 'Comments cannot alter AC fields');
check(files.filter(p => /\.agent\.md$/.test(p)).length === 10, 'Expected ten agent profiles');
check(files.filter(p => /\.skill\.md$/.test(p)).length === 11, 'Expected eleven skill profiles');
for (const p of ['run-status','learnings','decision-index','runs-pruned']) {
  check(files.includes(`docs/agent/templates/registers/${p}.md`), `Missing ${p} template`);
  check(!files.includes(`docs/agent/${p}.md`), `Private ${p} register must not ship`);
}
check(!files.some(p => p.startsWith('docs/agent/runs/') && !p.endsWith('.gitkeep')), 'No run artifacts may ship');
// Only public, generic, reviewable standards may be committed under Reference/.
const allowedPublicReference = p => p === 'Reference/README.md' ||
  (p.startsWith('Reference/standards/') &&
   (p.endsWith('.md') || p === 'Reference/standards/catalog.yaml'));
check(files.filter(p => p.startsWith('Reference/')).every(allowedPublicReference),
  'Only public standards markdown/catalog may ship; private/org reference content forbidden');
for (const required of ['Reference/standards/README.md',
                        'Reference/standards/catalog.yaml',
                        'Reference/standards/nasa-requirements.md',
                        'Reference/standards/security.md',
                        'Reference/standards/experience.md'])
  check(files.includes(required), `Public standards pack missing ${required}`);
check(!files.some(p => p.startsWith('Reference/private/')),
  'Never commit private reference content');
check(!files.includes('.github/project-config.local.yaml') && !files.includes('.github/mcp.json'), 'No private config may ship');
for (const heading of ['## Jira payload', '## Review notes (run docs only — not posted)'])
  check(read('docs/agent/templates/{story_id}-rewrite.md').includes(heading), `Missing rewrite boundary ${heading}`);
for (const id of ['L9','L10']) check(read('docs/agent/templates/{story_id}-eval-report.md').includes(id), `Missing ${id} measurement`);

const nextId = IdGenerator.incrementing();
const ast = new Parser(new AstBuilder(nextId), new GherkinClassicTokenMatcher()).parse(read('examples/behavioral.feature'));
const pickles = compile(ast, 'examples/behavioral.feature', nextId);
check(pickles.length === 3, 'Fictional feature must compile to three examples');
check(ast.feature.children.length <= 8, 'Example AC count must respect the budget');
const checklist = read('examples/lean-requirement.md').split('\n').filter(l => l.startsWith('- [ ] '));
check(checklist.length === 3 && checklist.every(l => l.slice(6).length <= 250), 'Fictional checklist fits count and item budgets');
for (const file of files.filter(p => p.endsWith('.md'))) {
  for (const match of read(file).matchAll(/\[[^\]\n]+\]\(([^)\n]+)\)/g)) {
    const target = match[1].split('#')[0];
    if (!target || /^(https?:|mailto:)/.test(target) || /[{}<>*]/.test(target)) continue;
    check(fs.existsSync(path.resolve(root,path.dirname(file),target)), `${file}: broken link ${target}`);
  }
  check(!/-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|\bgh[pousr]_[A-Za-z0-9]{30,}|\bgithub_pat_[A-Za-z0-9_]{30,}/.test(read(file)), `${file}: possible credential`);
}
console.log(`Toolkit validation passed: ${assertions} assertions; 10 agents, 11 skills; fictional feature parsed and compiled.`);
console.log('Runtime semantic scoring and live Jira/Confluence integration are not exercised.');
