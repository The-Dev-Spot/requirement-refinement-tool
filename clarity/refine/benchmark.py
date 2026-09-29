"""Same-need/different-input harness; report each input group, never claim parity by fixture alone."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from ..guardrails import ValidationError, digest, identifier, load_json
from .checks import check
from .contracts import DEFAULT_POLICY, draft, fields, items, require, review


def evaluate(corpus, outputs):
    fields(corpus, {'version', 'label_status', 'cases'}, 'parity corpus')
    require(type(corpus['version']) is int and corpus['version'] == 1, 'Unsupported corpus')
    require(isinstance(outputs, dict), 'Outputs must be keyed by case ID')
    cases = items(corpus['cases'], 'cases', 1000)
    require(bool(cases), 'Corpus cannot be empty')
    ids = set(); results = []; groups = {}
    for case in cases:
        fields(case, {'id', 'need_id', 'input_style', 'brief', 'sources', 'required_rule_ids'}, 'case')
        identifier(case['id']); require(case['id'] not in ids, 'Duplicate case ID'); ids.add(case['id'])
        require(case['input_style'] in {'expert', 'partial', 'plain'}, 'Unknown input style')
        group = groups.setdefault(case['input_style'], {'total': 0, 'provided': 0, 'contract_passed': 0})
        group['total'] += 1
        row = {'case_id': case['id'], 'need_id': case['need_id'], 'input_style': case['input_style'], 'contract_passed': False, 'missing_output': case['id'] not in outputs}
        if not row['missing_output']:
            group['provided'] += 1
            try:
                supplied = outputs[case['id']]
                fields(supplied, {'draft', 'review'}, 'benchmark output')
                value = draft(supplied['draft']); reviewed = review(supplied['review'], value, digest(value))
                checked = check(value, case['sources'], DEFAULT_POLICY)
                missing = sorted(set(case['required_rule_ids']) - {s['id'] for s in value['statements'] if s['kind'] in {'rule', 'constraint'}})
                allowed = {f['id'] for f in checked['findings'] if f['severity'] == 'warning'}
                require(set(reviewed['warning_resolutions']) <= allowed, 'Invalid benchmark warning disposition')
                flags = [f for f in checked['findings'] if f['severity'] != 'warning' or f['id'] not in reviewed['warning_resolutions']]
                failed_reviews = [key for section in ('checks', 'statement_support', 'scenario_fidelity') for key, v in reviewed[section].items() if v['status'] != 'PASS']
                row.update({'missing_rule_ids': missing, 'machine_findings': len(flags), 'review_reported_failures': failed_reviews, 'contract_passed': not flags and not missing and not failed_reviews and not reviewed['ambiguities']})
            except (ValidationError, TypeError, KeyError, ValueError):
                row['invalid_output'] = True
        group['contract_passed'] += int(row['contract_passed'])
        results.append(row)
    require(not set(outputs) - ids, 'Output supplied for an unknown case')
    for group in groups.values():
        group['contract_pass_rate'] = group['contract_passed'] / group['total']
    return {'groups': groups, 'cases': results, 'label_status': corpus['label_status'], 'semantic_accuracy_measured': False, 'experience_invariance_proven': False, 'limitations': 'Contract checks and reviewer-reported judgments only. Independent human labels, repeated live model runs, blind developer/tester reviews and time/cost measurements are still required.'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('corpus', type=Path); parser.add_argument('outputs', type=Path, help='JSON object keyed by case ID, each containing draft and independent review')
    args = parser.parse_args(argv)
    try:
        result = evaluate(load_json(args.corpus), load_json(args.outputs))
        print(json.dumps(result, indent=2))
        return 0 if all(r['contract_passed'] for r in result['cases']) else 1
    except (ValidationError, OSError, ValueError, TypeError) as exc:
        print('Invalid parity corpus or outputs')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
