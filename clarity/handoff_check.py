"""Read-only Xray pilot receipts; never imports or updates remote tests."""
import argparse
import hashlib
import json
from pathlib import Path
from .guardrails import load_json, ValidationError, identifier
from .refine.contracts import require
from .refine.checks import feature_index


def verify(feature_bytes, receipt):
    require(receipt.get('edition') in {'xray-cloud', 'xray-server-dc'}, 'Select the Xray edition explicitly')
    identifier(receipt['project'])
    sha = hashlib.sha256(feature_bytes).hexdigest()
    require(receipt.get('feature_sha256') == sha, 'Pilot receipt does not match the approved feature bytes')
    index = feature_index(feature_bytes.decode('utf-8'))
    ids = {s['id'] for s in index['scenarios']}
    mapping = receipt.get('scenario_tests', {})
    require(set(mapping) == ids, 'Map every approved scenario ID exactly once')
    require(len(set(mapping.values())) == len(mapping), 'Two scenarios cannot silently map to one Test')
    import re
    for value in mapping.values(): require(isinstance(value, str) and re.fullmatch(re.escape(receipt['project']) + r'-[1-9][0-9]*', value), 'Test keys must belong to the selected project')
    require(receipt.get('repeat_strategy') in {'update-mapped-tests', 'new-version'}, 'Record the repeat-import strategy explicitly')
    observations = receipt.get('observations', {})
    required = {'scenario_ids', 'outlines', 'backgrounds', 'tables_docstrings', 'requirement_links', 'repeat_import'}
    require(set(observations) == required and all(v in {'PASS', 'FAIL', 'NOT_RUN', 'NOT_APPLICABLE'} for v in observations.values()), 'Record every edition pilot observation')
    return {'edition': receipt['edition'], 'feature_sha256': sha, 'scenario_count': len(ids), 'compiled_cases': index['compiled_cases'],
            'receipt_complete': all(v in {'PASS', 'NOT_APPLICABLE'} for v in observations.values()), 'remote_state_verified': False,
            'note': 'Local validation of an operator-supplied receipt only. Confirm actual remote results in the selected Xray instance.'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('feature', type=Path); parser.add_argument('receipt', type=Path)
    args = parser.parse_args(argv)
    try:
        require(args.feature.stat().st_size <= 100000, 'Feature exceeds size limit')
        result = verify(args.feature.read_bytes(), load_json(args.receipt)); print(json.dumps(result, indent=2))
        return 0 if result['receipt_complete'] else 1
    except (ValidationError, OSError, ValueError, TypeError, KeyError):
        print('Invalid feature or pilot receipt'); return 2


if __name__ == '__main__': raise SystemExit(main())
