"""Repeated, grouped evaluation with missing results and blind human review packets."""
import argparse
import csv
import json
import statistics
import math
from pathlib import Path
from .guardrails import canonical, digest, load_json, identifier, ValidationError
from .refine.contracts import require, draft, review, DEFAULT_POLICY, fields, text
from .refine.checks import check


def evaluate(corpus, runs, trials=3):
    require(corpus.get('version') == 2 and type(trials) is int and 1 <= trials <= 20, 'Unsupported corpus or trial count')
    cases = corpus['cases']; ids = {c['id'] for c in cases}
    require(len(ids) == len(cases) and bool(cases), 'Duplicate or empty evaluation corpus')
    index = {}
    for run in runs:
        key = (run['case_id'], run['trial'])
        require(run['case_id'] in ids and type(run['trial']) is int and 1 <= run['trial'] <= trials and key not in index, 'Unknown, duplicate or out-of-range trial')
        index[key] = run
    groups = {}; rows = []
    for case in cases:
        for trial in range(1, trials + 1):
            supplied = index.get((case['id'], trial))
            row = {'case_id': case['id'], 'need_id': case['need_id'], 'style': case['input_style'], 'trial': trial, 'missing': supplied is None, 'contract_passed': False}
            if supplied:
                # Failed/invalid outputs still cost time and tokens. Capture their
                # bounded measurements independently of contract validation.
                metrics = supplied.get('metrics', {})
                if isinstance(metrics, dict):
                    for name in ('elapsed_seconds', 'input_tokens', 'output_tokens', 'cached_input_tokens', 'model_calls', 'revisions', 'correction_minutes'):
                        metric = metrics.get(name)
                        if type(metric) in (int, float) and 0 <= metric < 10**10: row[name] = metric
                try:
                    result = supplied['result']
                    if result.get('questions'):
                        require(result.get('draft') is None and len(result['questions']) <= 5, 'Invalid question result')
                        seen = set()
                        for q in result['questions']:
                            fields(q, {'id', 'text', 'why', 'impact'}, 'evaluation question')
                            identifier(q['id']); text(q['text'], 'question', 3000); text(q['why'], 'question consequence', 3000)
                            require(q['id'] not in seen and type(q['impact']) is int and 1 <= q['impact'] <= 5, 'Invalid or duplicate question')
                            seen.add(q['id'])
                        row['questions'] = len(result['questions'])
                        row['contract_passed'] = True
                        row['outcome'] = 'questions'
                    else:
                        value = draft(result['draft']); checked = check(value, case['sources'], DEFAULT_POLICY)
                        assessment = review(result['review'], value, digest(value))
                        resolved = assessment['warning_resolutions']
                        allowed = {f['id'] for f in checked['findings'] if f['severity'] == 'warning'}
                        require(set(resolved) <= allowed, 'Invalid warning disposition')
                        blockers = [f for f in checked['findings'] if f['severity'] != 'warning' or f['id'] not in resolved]
                        failed = [v for section in ('checks', 'statement_support', 'scenario_fidelity') for v in assessment[section].values() if v['status'] != 'PASS']
                        row.update(contract_passed=not blockers and not failed and not assessment['ambiguities'], outcome='draft')
                except (ValidationError, KeyError, TypeError, ValueError): row['invalid'] = True
            rows.append(row)
            group = groups.setdefault(case['input_style'], {'expected': 0, 'provided': 0, 'contract_passed': 0})
            group['expected'] += 1; group['provided'] += int(supplied is not None); group['contract_passed'] += int(row['contract_passed'])
    for style, group in groups.items():
        group['contract_pass_rate'] = group['contract_passed'] / group['expected']
        values = [r['elapsed_seconds'] for r in rows if r['style'] == style and 'elapsed_seconds' in r]
        group['median_elapsed_seconds'] = statistics.median(values) if values else None
        group['latency_samples'] = len(values)
        group['p95_elapsed_seconds'] = sorted(values)[math.ceil(len(values)*.95)-1] if values else None
        group['handoff_contract_passed'] = sum(r['style'] == style and r.get('outcome') == 'draft' and r['contract_passed'] for r in rows)
        group['efficiency'] = {}
        for name in ('input_tokens', 'output_tokens', 'cached_input_tokens', 'model_calls', 'revisions', 'correction_minutes'):
            samples = [r[name] for r in rows if r['style'] == style and name in r]
            group['efficiency'][name] = {'samples': len(samples), 'total': sum(samples) if samples else None,
                                         'median': statistics.median(samples) if samples else None}
    return {'groups': groups, 'trials': rows, 'label_status': corpus['label_status'], 'semantic_accuracy_measured': False, 'experience_invariance_proven': False,
            'human_review_required': ['intent and scope', 'unsupported claims', 'missed material decisions', 'useful questions', 'false blocks', 'scenario sufficiency', 'correction effort'],
            'limitations': 'Contract pass is not semantic correctness. A question response is not a handoff. Human labels require independent ratification; no live run is fabricated.'}


def blind_packets(corpus, runs, directory):
    require(not directory.exists(), 'Blind packet destination must be new')
    directory.mkdir(mode=0o700, parents=True)
    cases = {c['id']: c for c in corpus['cases']}
    mapping = []; ratings = []
    for run in runs:
        case = cases[run['case_id']]
        blind_id = 'B-' + digest({'case': run['case_id'], 'trial': run['trial']})[:16]
        path = directory / (blind_id + '.json')
        path.write_text(json.dumps({'id': blind_id, 'business_need': case['oracle'], 'sources': case['sources'], 'result': run['result']}, indent=2))
        path.chmod(0o600)
        mapping.append({'blind_id': blind_id, 'case_id': run['case_id'], 'trial': run['trial'], 'model': run.get('model', '')})
        ratings.append({'blind_id': blind_id, 'reviewer': '', 'intent_preserved': '', 'unsupported_claims': '', 'missed_decisions': '', 'useful_questions': '', 'false_blocks': '', 'scenario_sufficiency': '', 'correction_minutes': '', 'notes': ''})
    require(bool(ratings), 'Supply actual trial outputs before preparing blind review')
    with (directory / 'ratings.csv').open('x', newline='') as fh:
        writer = csv.DictWriter(fh, fieldnames=list(ratings[0])); writer.writeheader(); writer.writerows(ratings)
    (directory / 'PRIVATE-unblinding.json').write_text(json.dumps(mapping, indent=2)); (directory / 'PRIVATE-unblinding.json').chmod(0o600)
    return len(ratings)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('corpus', type=Path); parser.add_argument('runs', type=Path)
    parser.add_argument('--trials', type=int, default=3); parser.add_argument('--blind-dir', type=Path)
    args = parser.parse_args(argv)
    try:
        corpus = load_json(args.corpus); runs = load_json(args.runs)
        report = evaluate(corpus, runs, args.trials)
        if args.blind_dir: blind_packets(corpus, runs, args.blind_dir)
        print(json.dumps(report, indent=2))
        return 0 if all(r['contract_passed'] for r in report['trials']) else 1
    except (ValidationError, KeyError, TypeError, ValueError, OSError):
        print('Invalid evaluation inputs or output destination')
        return 2


if __name__ == '__main__': raise SystemExit(main())
