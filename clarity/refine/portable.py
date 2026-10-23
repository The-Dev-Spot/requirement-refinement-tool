"""Optional recipient-neutral export of sealed handoffs; no pipeline dependency.

The usual two-file handoff and full private audit views remain unchanged. This
third view adds only identity and integrity metadata, never supporting sources,
credentials, reviewer identity or execution/publication permissions.
"""
from __future__ import annotations

import hashlib
import io
import json
import zipfile

from ..guardrails import identifier
from .contracts import require
from .handoff import verify_bundle


def portable_archive(bundle: dict) -> bytes:
    verify_bundle(bundle)
    plan = bundle['plan']
    trace = json.loads(bundle['files']['traceability.json'])
    require(trace['draft_digest'] == plan['draft_digest'], 'Traceability targets another draft')
    scenarios = [s['id'] for s in trace['scenario_mappings']]
    require(0 < len(scenarios) <= 200 and len(set(scenarios)) == len(scenarios), 'Unique scenario identities are required')
    for scenario in scenarios:
        identifier(scenario)
    payload = {name: bundle['files'][name].encode('utf-8')
               for name in ('requirement.md', 'acceptance.feature')}
    metadata = {key: plan[key] for key in ('run_id', 'revision', 'profile', 'draft_digest',
                                         'context_digest', 'review_digest', 'engine_digest')}
    metadata.update(schema_version=1, kind='clarity-portable-handoff', plan_digest=bundle['plan_digest'],
                    files={name: hashlib.sha256(body).hexdigest() for name, body in payload.items()},
                    scenario_ids=sorted(scenarios))
    payload['handoff.json'] = (json.dumps(metadata, ensure_ascii=True, sort_keys=True,
                                        separators=(',', ':'), allow_nan=False) + '\n').encode('utf-8')
    require(sum(map(len, payload.values())) <= 1_500_000
            and all(len(body) <= 1_000_000 for body in payload.values()), 'Portable handoff exceeds transfer budget')
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, body in sorted(payload.items()):
            item = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            item.create_system = 3
            item.external_attr = 0o100600 << 16
            item.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(item, body)
    return out.getvalue()
