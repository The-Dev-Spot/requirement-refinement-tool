import test from 'node:test';
import assert from 'node:assert/strict';
import { lintStory } from './quality-gate.mjs';

const register='# Risk register\n| id | risk | applies when | mandatory negative outcome | source |\n| --- | --- | --- | --- | --- |\n| RISK-1 | Duplicate jobs | event | no duplicate | approved policy |\n';
const catalog='## Given\nGiven an event exists\n';
const options={riskRegister:register,stepCatalog:catalog};
const backend = (changes={})=>({
 title:'Bounded worker pool', story_type:'non-behavioral',
 payload:'Objective: ensure the job controller runs within approved pool limits.\nScope: isolated synthetic test only.\nOut: production deployment.',
 criteria:[
  'At most one normal lease and one reserved critical lease per pool exists during a controlled run.',
  'An untrusted nonproduction incident never acquires the reserved critical lease.',
  'After restart, an incomplete lease can be recovered without duplicate job creation.'
 ],...changes
});
const behavior = (changes={})=>({
 title:'Idempotent backend events', story_type:'behavioral',
 payload:'A duplicate event must not create another job. The backend is the test boundary.',
 feature:`Feature: Idempotent processing
  @case_AC-1
  Scenario: Delivery occurs twice
    Given a valid event has been processed
    When the same event is delivered again
    Then exactly one job exists
  @case_AC-2
  Scenario: Restart and redelivery
    Given a valid event has been processed
    When the service is restarted and the event is retried
    Then exactly one job exists
  @case_AC-3
  Scenario: Different identity
    Given a valid event has been processed
    When a different event arrives
    Then an additional job exists
`,...changes
});

test('real nonbehavioral M0-like story has 10 explicit results but never becomes READY',()=>{
 const r=lintStory(backend(),options);
 assert.equal(r.status,'PASS');
 assert.equal(Object.keys(r.checks).length,10);
 assert.equal(r.checks.L1.status,'NOT_APPLICABLE');
 assert.equal(r.checks.L9.status,'PASS');
 assert.equal(r.ready_for_handover,false);
 assert.equal(r.semantic_review_required,true);
});
test('official parser actually accepts valid Gherkin and IDs',()=>{
 const r=lintStory(behavior(), options);
 assert.equal(r.checks.L1.status,'PASS');
 assert.equal(r.checks.L2.status,'PASS');
 assert.equal(r.checks.L9.status,'PASS');
 assert.equal(r.status,'PASS');
});
test('official parser rejects malformed Gherkin, cannot claim READY',()=>{
 const r=lintStory(behavior({feature:'Feature: X\n Scenario: Broken\n Given a'}),options);
 assert.equal(r.checks.L1.status,'FAIL');
 assert.equal(r.status,'FAIL');
});
test('vague unsourced speed claims fail L3',()=>{
 const r=lintStory(backend({criteria:['The system shall be fast and user-friendly.']}),options);
 assert.equal(r.checks.L3.status,'FAIL');
 assert.equal(r.status,'FAIL');
});
test('unsupported risk tag fails against configured risk register',()=>{
 const r=lintStory(behavior({feature:behavior().feature.replace('@case_AC-1','@risk:RISK-999 @case_AC-1')}),options);
 assert.equal(r.checks.L5.status,'FAIL');
});
test('missing risk register fails closed with NOT_RUN for required check',()=>{
 const r=lintStory(backend(),{stepCatalog:catalog});
 assert.equal(r.status,'BLOCKED');
 assert.deepEqual(r.required_not_run,['L5']);
});
test('empty public step catalog is advisory NOT_RUN, never falsely passes',()=>{
 const r=lintStory(backend(),{riskRegister:register,stepCatalog:'> Status: EMPTY'});
 assert.equal(r.checks.L8.status,'NOT_RUN');
 assert.equal(r.ready_for_handover,false);
});
test('strict 8 AC max and missing AC fail',()=>{
 const r=lintStory(backend({criteria:Array.from({length:9},(_,i)=>`Criterion ${i} has an observable result`)}),options);
 assert.equal(r.checks.L9.status,'FAIL');
 assert.equal(lintStory(backend({criteria:[]}),options).status,'FAIL');
});
test('Jira converted length unavailable cannot silently PASS',()=>{
 const r=lintStory(backend({target_format:'jira-wiki'}),options);
 assert.equal(r.checks.L10.status,'NOT_RUN');
 assert.equal(r.status,'BLOCKED');
});
test('malformed open questions fail, valid questions remain a semantic blocker',()=>{
 const r=lintStory(backend({payload:backend().payload+'\n# OPEN QUESTION: Who owns the policy?'}),options);
 assert.equal(r.checks.L7.status,'FAIL');
 const valid=lintStory(backend({payload:backend().payload+'\n# OPEN QUESTION -> PO: Who owns the policy?'}),options);
 assert.equal(valid.checks.L7.status,'PASS');
 assert.equal(valid.open_question_count,1);
 assert.equal(valid.ready_for_handover,false);
});
test('UI choreography warns; executable feature is not a test execution receipt',()=>{
 const r=lintStory(behavior({feature:behavior().feature.replace(
 'When the same event is delivered again','When the user clicks the Submit button')}),options);
 assert.equal(r.checks.L4.status,'WARN');
 assert.equal(r.tests_executed,false);
});
test('conditional vague term warning must not be interpreted as requirements truth',()=>{
 const r=lintStory(backend({criteria:['The service is fast within 250 ms per request.']}),options);
 assert.equal(r.checks.L3.status,'PASS');
 assert.equal(r.ready_for_handover,false);
});
test('input validation rejects attempt to force behavioral into nonbehavioral classification',()=>{
 assert.throws(()=>lintStory(backend({feature:behavior().feature}),options));
});
