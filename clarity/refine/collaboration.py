"""Optional dependency-aware questionnaires. Answers still go through the operator."""
from __future__ import annotations

from .contracts import require, text


def question_order(questions: dict, dependencies: dict | None = None) -> list[dict]:
    """Topologically order questions, retaining impact ordering within each frontier.

    Dependencies are an explicit proposal, not permission to resolve a question.
    Merged questions follow their current target; out-of-scope/answered questions
    satisfy ordering only. The controller remains the authority on completeness.
    """
    dependencies = {} if dependencies is None else dependencies
    require(isinstance(dependencies, dict) and set(dependencies) <= set(questions), 'Unknown dependency owner')

    def effective(qid):
        seen = set()
        while questions[qid]['state'] == 'merged':
            require(qid not in seen, 'Question merge cycle')
            seen.add(qid)
            qid = questions[qid].get('target')
            require(isinstance(qid, str) and qid in questions, 'Missing merged question target')
        return qid

    edges = {qid: set() for qid in questions}
    for qid, prerequisites in dependencies.items():
        require(isinstance(prerequisites, list) and len(prerequisites) <= 100
                and all(isinstance(p, str) and p in questions for p in prerequisites), 'Unknown prerequisite question')
        require(len(set(prerequisites)) == len(prerequisites), 'Duplicate prerequisite question')
        owner = effective(qid)
        for prerequisite in prerequisites:
            target = effective(prerequisite)
            require(owner != target, 'Self dependency or merge-induced cycle')
            edges[owner].add(target)
    # Check the entire proposed graph, including answered nodes: answering is not
    # permission to make an invalid dependency map appear valid.
    remaining, done = set(questions), set()
    while remaining:
        ready = {qid for qid in remaining if edges[qid] <= done}
        require(bool(ready), 'Question dependencies contain a cycle')
        remaining -= ready
        done |= ready
    pending = {qid for qid, q in questions.items() if q['state'] == 'open'}
    done = set(questions) - pending
    ordered = []
    while pending:
        ready = sorted((qid for qid in pending if edges[qid] <= done),
                       key=lambda qid: (-questions[qid]['impact'], qid))
        require(bool(ready), 'Unresolved question dependency cycle')
        for qid in ready:
            ordered.append({**questions[qid], 'prerequisites': sorted(edges[qid])})
        pending.difference_update(ready)
        done.update(ready)
    return ordered


def questionnaire(status: dict, recipient: str, purpose: str, question_ids: list[str],
                  dependencies: dict | None = None) -> str:
    for label, value in (('recipient role', recipient), ('questionnaire purpose', purpose)):
        text(value, label, 1000)
    require(isinstance(question_ids, list) and 0 < len(question_ids) <= 100
            and all(isinstance(q, str) for q in question_ids)
            and len(set(question_ids)) == len(question_ids), 'Select unique question IDs')
    questions = status['context']['questions']
    require(set(question_ids) <= {qid for qid, q in questions.items() if q['state'] == 'open'},
            'Only current open questions may be exported')
    ordered = question_order(questions, dependencies)
    selected = set(question_ids)
    lines = ['# Discovery questionnaire', '', 'Recipient role: ' + recipient, '', 'Purpose: ' + purpose, '',
             'Requirement: ' + status['run']['id'], 'Workspace version: ' + str(status['run']['version']),
             'Context digest: ' + status['context_digest'], '',
             '## How to answer', '',
             'Partial answers and "I do not know" are useful. Distinguish facts, proposals and decisions you are authorised to make.',
             'Return answers using the stable question IDs. The operator must review and record them; this document does not approve a requirement.',
             'Only selected question text and consequences are included. Review before sharing; no source attachments are included.', '']
    for question in ordered:
        if question['id'] not in selected:
            continue
        lines += ['## ' + question['id'], '', question['text'], '', 'Why it matters: ' + question['why'], '']
        open_prerequisites = [qid for qid in question['prerequisites'] if questions[qid]['state'] == 'open']
        if open_prerequisites:
            lines += ['Resolve these decisions first: ' + ', '.join(open_prerequisites) + '.', '']
        lines += ['Answer:', '', '> ', '']
    lines += ['## Anything else?', '', 'What relevant decision or uncertainty have we missed?', '', '> ', '']
    return '\n'.join(lines)
