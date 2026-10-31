#!/usr/bin/env node
// Deterministic, read-only Clarity L1-L10 checker. Does NOT score D1-D10 or assert READY.
// Uses the repository-pinned official Gherkin parser; emits evidence and NOT_RUN.
import fs from 'node:fs';
import crypto from 'node:crypto';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { Parser, AstBuilder, GherkinClassicTokenMatcher, compile } from '@cucumber/gherkin';
import { IdGenerator } from '@cucumber/messages';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const HARD = new Set(['L1', 'L2', 'L3', 'L5', 'L7', 'L9', 'L10']);
const sha256 = text => crypto.createHash('sha256').update(text, 'utf8').digest('hex');
const id = s => /^[A-Za-z0-9][A-Za-z0-9_.-]{0,99}$/.test(s);
const VAGUE = [
  'as appropriate', 'as needed', 'as required', 'where possible', 'if possible',
  'handle gracefully', 'user-friendly', 'and/or', 'and so on',
  'fast', 'quick', 'slow', 'responsive', 'scalable', 'robust', 'reliable',
  'stable', 'intuitive', 'seamless', 'simple', 'flexible', 'efficient',
  'performant', 'optimize', 'improved', 'better', 'enhanced', 'minimal',
  'reasonable', 'appropriate', 'gracefully', 'properly', 'correctly',
  'securely', 'some', 'several', 'various', 'many', 'few', 'tbd', 'todo', 'etc.'
];
const escapeRegex = value => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
const invalidTag = tag => !(/@[a-z][a-z0-9]*(?:-[a-z0-9]+)*/.test(tag) && /^@[a-z][a-z0-9]*(?:-[a-z0-9]+)*$/.test(tag)) &&
  !/^@risk:RISK-[0-9]+$/.test(tag) && !/^@nfr:[a-z][a-z0-9-]*$/.test(tag) &&
  !/^@case_[A-Za-z0-9][A-Za-z0-9_.-]{0,99}$/.test(tag);
const result = (status, details, evidence = []) => ({ status, details, evidence });

function extractScenarios(ast) {
  const scenarios = [];
  function visit(nodes) {
    for (const entry of nodes || []) {
      if (entry.scenario) scenarios.push(entry.scenario);
      if (entry.rule) visit(entry.rule.children);
    }
  }
  visit(ast.feature?.children);
  return scenarios;
}

function parseGherkin(feature) {
  const gen = IdGenerator.incrementing();
  const ast = new Parser(new AstBuilder(gen), new GherkinClassicTokenMatcher()).parse(feature);
  const pickles = compile(ast, 'acceptance.feature', gen);
  const scenarios = extractScenarios(ast);
  return { ast, scenarios, pickles };
}

function riskIds(register) {
  // Only lines in the authoritative table supply IDs; surrounding examples do not.
  const rows = register.split(/\r?\n/).filter(x => /^\s*\|\s*RISK-[0-9]+\s*\|/.test(x));
  return new Set(rows.map(row => row.split('|')[1].trim()));
}

export function lintStory(story, options = {}) {
  if (!story || typeof story !== 'object' || Array.isArray(story)) throw new Error('Story must be a JSON object');
  const {title, story_type, payload, feature, criteria, target_format = 'markdown', converted_payload} = story;
  if (typeof title !== 'string' || !title.trim() || typeof payload !== 'string' || !payload.trim()
      || !['behavioral', 'non-behavioral'].includes(story_type)
      || !['markdown', 'jira-wiki'].includes(target_format)) throw new Error('Invalid story title, type, payload or format');
  if (payload.length > 250000) throw new Error('Input too large');
  if (story_type === 'behavioral' && (typeof feature !== 'string' || !feature.trim()))
    throw new Error('Behavioral story requires Gherkin feature source');
  if (story_type === 'non-behavioral' && (typeof feature === 'string' && feature.trim()))
    throw new Error('Do not force Gherkin onto non-behavioral stories');
  if (story_type === 'non-behavioral' && (!Array.isArray(criteria) || !criteria.every(x=>typeof x === 'string')))
    throw new Error('Non-behavioral story requires criteria list');
  if (typeof converted_payload !== 'undefined' && typeof converted_payload !== 'string')
    throw new Error('Invalid converted payload');
  const check = {};
  let parsed, scenarioCount = 0;
  if (story_type === 'behavioral') {
    try {
      parsed = parseGherkin(feature);
      scenarioCount = parsed.scenarios.length;
      const bad = parsed.scenarios.filter(s => {
        const steps = s.steps || [];
        let given = false, when = false, then = false, badOrder = false;
        for (const step of steps) {
          const word = step.keyword.trim();
          if (word === 'Given') { if (when || then) badOrder = true; given = true; }
          if (word === 'When') { if (!given || then) badOrder = true; when = true; }
          if (word === 'Then') { if (!when) badOrder = true; then = true; }
          if (!step.text?.trim()) badOrder = true;
        }
        return !given || !when || !then || badOrder;
      });
      check.L1 = scenarioCount && !bad.length && parsed.pickles.length
        ? result('PASS', `Official parser compiled ${parsed.pickles.length} example(s); ${scenarioCount} scenario(s) with Given/When/Then`)
        : result('FAIL', 'Missing or invalid Given/When/Then scenario', bad.map(s=>s.location?.line));
    } catch (error) { check.L1 = result('FAIL', 'Official Gherkin parser rejected feature', [String(error.message).slice(0,300)]); }
  } else check.L1 = result('NOT_APPLICABLE', 'No Gherkin on a non-behavioral story');

  const all = payload + '\n' + (feature || '');
  const tags = all.split(/\r?\n/).flatMap((line, index) => {
    const trimmed = line.trim();
    if (!trimmed.startsWith('@')) return [];
    return trimmed.split(/\s+/).filter(t=>t.startsWith('@')).map(value=>({value, line:index+1}));
  });
  const invalid = tags.filter(t=>invalidTag(t.value));
  check.L2 = invalid.length ? result('FAIL', 'Invalid tag format/namespace', invalid)
    : result('PASS', `Validated ${tags.length} tags including optional @case_ identifiers`);
  const AC = story_type === 'behavioral' ? (parsed?.scenarios || []).flatMap(s => [s.name, ...s.steps.map(x=>x.text)]) : criteria;
  const vague = [];
  for(const [index,criterion] of AC.entries()) {
    for (const term of VAGUE) {
      const expr = new RegExp(`(^|[^a-z])${escapeRegex(term)}(?=$|[^a-z])`, 'i');
      const found = expr.exec(criterion);
      if (!found) continue;
      const pos = found.index + found[1].length;
      const neighborhood = criterion.slice(Math.max(0,pos-22), Math.min(criterion.length,pos+term.length+22));
      if (!/(?:\d+(?:[.,]\d+)?\s*(?:ms|sec|s|%|kb|mb|gb|hours?|minutes?|requests?|workers?|retry|retries|records?)|(?:<=|>=|<|>|≤|≥)\s*\d+)/i.test(neighborhood))
        vague.push({ac:index+1,term,excerpt:criterion.slice(0,160)});
    }
  }
  check.L3 = vague.length ? result('FAIL','Potential unqualified vague AC terms requiring review',vague)
    : result('PASS', 'No unqualified seed-list phrases in criteria; semantic ambiguity still requires D4');

  if (story_type === 'behavioral' && parsed) {
    const ui = [];
    for(const s of parsed.scenarios) for(const step of s.steps) {
      if (!['Given','When'].includes(step.keyword.trim())) continue;
      if (/\b(?:click(?:s|ed)?|tap(?:s|ped)?|press(?:es|ed)?|scroll(?:s|ed)?|navigate(?:s|d)? to|select .+ from .+ dropdown)\b/i.test(step.text))
        ui.push({scenario:s.name,step:step.text});
    }
    check.L4 = ui.length ? result('WARN', 'UI choreography rather than declarative behavior',ui)
      : result('PASS','No common imperative UI steps detected');
  } else check.L4 = result(story_type === 'non-behavioral'?'NOT_APPLICABLE':'NOT_RUN',
    story_type === 'non-behavioral'?'No behavioral steps':'Cannot review steps without valid parse');

  const seen = tags.filter(t=>t.value.startsWith('@risk:'));
  const riskRegister = options.riskRegister;
  if (typeof riskRegister !== 'string') check.L5 = result('NOT_RUN','Project risk register was not provided');
  else {
    const known = riskIds(riskRegister);
    const missing = seen.filter(t=>!known.has(t.value.slice(6)));
    check.L5 = missing.length ? result('FAIL','Risk tags are absent from approved risk register',missing)
      : result('PASS', `Resolved ${seen.length} explicit risk tag(s) against ${known.size} known risks; semantic D5 still required`);
  }

  const citations = (story.review_notes || '').split(/\r?\n/).filter(l=>/^\s*>\s*Source:/.test(l));
  const badCitations = citations.filter(l=>!/(?:last-modified|effective date|source\.export_date).*(?:\d{4}-\d\d-\d\d)/i.test(l));
  check.L6 = badCitations.length ? result('WARN','Malformed declared provenance lines',badCitations.slice(0,10))
    : result('PASS', `Checked syntax of ${citations.length} cited lines; independent source correctness belongs to D6`);

  const qLines = all.split(/\r?\n/).filter(l=>/OPEN\s*QUESTION|\bTODO\s*:\s*PO\b/i.test(l));
  const broken = qLines.filter(l=>!/^\s*(?:[-*]\s+)?# OPEN QUESTION -> PO: \S.+$/.test(l));
  check.L7 = broken.length ? result('FAIL', 'Malformed open-question marker(s)',broken.slice(0,10))
    : result('PASS', `${qLines.length} syntactically valid open-question marker(s)`);

  const catalog = options.stepCatalog;
  check.L8 = story_type === 'non-behavioral'
    ? result('NOT_APPLICABLE','No Gherkin step reuse for non-behavioral outcomes')
    : !catalog || /Status:\s*EMPTY/i.test(catalog)
      ? result('NOT_RUN','Advisory step catalog empty or missing; no claim of reuse')
      : result('NOT_RUN','Requires semantic near-duplicate comparison; not executed by this deterministic checker');
  const count = story_type === 'behavioral' ? scenarioCount : criteria.length;
  check.L9 = count < 1 || count > 8 ? result('FAIL', `Acceptance criteria count ${count}; must be 1..8`)
    : result('PASS', `Acceptance criteria count ${count}; target 3–6, hard maximum 8`);
  const longest = story_type === 'non-behavioral' ? Math.max(0,...criteria.map(s=>s.length)) : 0;
  const measured = target_format === 'jira-wiki' ? converted_payload : payload;
  check.L10 = typeof measured !== 'string' ? result('NOT_RUN','Jira wiki conversion output missing; cannot verify target payload length')
    : measured.length > 20000 ? result('FAIL',`Final payload length ${measured.length} > 20,000`)
    : measured.length > 10000 || longest > 250 ? result('WARN',`Payload ${measured.length} chars; longest checklist item ${longest}`)
    : result('PASS',`Final payload ${measured.length} chars; longest checklist item ${longest}`);
  const hardFailures = Object.entries(check).filter(([k,v])=>HARD.has(k) && v.status === 'FAIL').map(([k])=>k);
  const requiredMissing = Object.entries(check).filter(([k,v])=>HARD.has(k) && v.status === 'NOT_RUN').map(([k])=>k);
  const status = hardFailures.length ? 'FAIL' : requiredMissing.length ? 'BLOCKED' :
    Object.values(check).some(v=>v.status === 'WARN') ? 'WARN' : 'PASS';
  return {
    schema_version:1, kind:'clarity-deterministic-quality-report', source_sha256:sha256(JSON.stringify(story)),
    status, checks: check, hard_failures: hardFailures, required_not_run: requiredMissing,
    open_question_count:qLines.length, semantic_review_required:true,
    independent_review_required:true, ready_for_handover:false,
    authority:'advisory-data-only', tests_executed:false,
    note:'Mechanical PASS is NOT an overall DoR PASS. D1-D10 and independent evidence remain required.'
  };
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const args=process.argv.slice(2);
  try {
    const at=args.indexOf('--input');
    if(at < 0 || !args[at+1]) throw new Error('Usage: quality-gate.mjs --input story.json [--output report.json]');
    const input=JSON.parse(fs.readFileSync(args[at+1],'utf8'));
    const riskPath=path.join(ROOT,'docs/risk-register.md');
    const catalogPath=path.join(ROOT,'steps/catalog.md');
    const report=lintStory(input,{
      riskRegister:fs.existsSync(riskPath)?fs.readFileSync(riskPath,'utf8'):undefined,
      stepCatalog:fs.existsSync(catalogPath)?fs.readFileSync(catalogPath,'utf8'):undefined
    });
    const out=JSON.stringify(report,null,2)+'\n';
    const oi=args.indexOf('--output');
    if(oi>=0 && args[oi+1]) fs.writeFileSync(args[oi+1],out,{flag:'wx'});
    else process.stdout.write(out);
    process.exitCode=report.status==='FAIL'?2:report.status==='BLOCKED'?3:0;
  } catch(e) {process.stderr.write('Quality gate input error: '+String(e.message)+'\n');process.exitCode=4;}
}
