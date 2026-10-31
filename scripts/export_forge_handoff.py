#!/usr/bin/env python3
"""Package an explicitly reviewed Clarity requirement for Forge's v2 importer.

Local data-only export. No model, connector, runtime, tracker write or approval.
An archive hash proves byte integrity, not a review verdict or sender identity.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import stat
import sys
import zipfile

ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}\Z")
TAG = re.compile(r"(?<!\S)@case_([A-Za-z0-9][A-Za-z0-9_.-]{0,99})(?=\s|$)")
KINDS = {"behavior", "invariant", "operational", "migration", "research"}
SYSTEMS = {"local", "github", "jira", "linear"}
MAX_FILE = 1_000_000
MAX_ARCHIVE = 2_000_000


def _require(value, reason):
    if not value:
        raise ValueError(reason)


def _read(path: Path) -> bytes:
    path = path.absolute()
    _require(not any(p.is_symlink() for p in (path, *path.parents)), "Symlink input forbidden")
    _require(path.is_file() and stat.S_ISREG(path.stat().st_mode), "Source must be a regular file")
    _require(path.stat().st_size <= MAX_FILE, "Source exceeds 1 MB")
    data = path.read_bytes()
    data.decode("utf-8")
    _require(bool(data.strip()), "Empty source file")
    return data


def _json(data: bytes):
    def pairs(items):
        obj = {}
        for key, val in items:
            _require(key not in obj, "Duplicate JSON key")
            obj[key] = val
        return obj

    return json.loads(data.decode("utf-8"), object_pairs_hook=pairs,
                      parse_constant=lambda x: (_ for _ in ()).throw(ValueError("Non-finite JSON")))


def _hash(data: bytes):
    return hashlib.sha256(data).hexdigest()


def _canonical(value) -> bytes:
    return (json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False)
            + "\n").encode("utf-8")


def validate_criteria(data: bytes, has_feature: bool):
    obj = _json(data)
    _require(isinstance(obj, dict) and set(obj) == {"schema_version", "story_type", "criteria"}
             and type(obj["schema_version"]) is int and obj["schema_version"] == 2,
             "Expected v2 criteria document")
    kind = obj["story_type"]
    _require(kind in {"behavioral", "non-behavioral"}, "Unknown story type")
    _require(has_feature == (kind == "behavioral"), "Only behavioral work takes a Gherkin feature")
    entries = obj["criteria"]
    _require(isinstance(entries, list) and 1 <= len(entries) <= 8, "Provide 1 to 8 criteria (split larger stories)")
    ids = []
    for entry in entries:
        _require(isinstance(entry, dict) and set(entry) == {"id", "kind", "text", "verification", "scenario_id"},
                 "Unexpected criterion fields")
        cid = entry["id"]
        _require(isinstance(cid, str) and ID.fullmatch(cid) and cid not in ids,
                 "Invalid or duplicate criterion ID")
        ids.append(cid)
        _require(entry["kind"] in KINDS, "Invalid criterion kind")
        for field in ("text", "verification"):
            val = entry[field]
            _require(isinstance(val, str) and 1 <= len(val.strip()) <= 4000
                     and not any(ord(c) < 32 and c not in "\n\r\t" for c in val),
                     "Invalid criterion " + field)
        if kind == "behavioral":
            _require(entry["kind"] == "behavior" and entry["scenario_id"] == cid,
                     "Behavioral criterion must map to matching @case_ tag")
        else:
            _require(entry["kind"] != "behavior" and entry["scenario_id"] is None,
                     "Nonbehavioral outcomes do not take scenario tags")
    return obj, ids


def _feature_tags(content: bytes):
    tags, docstring = [], None
    for line in content.decode("utf-8").splitlines():
        stripped = line.strip()
        if docstring:
            if stripped.startswith(docstring):
                docstring = None
            continue
        marker = next((m for m in ('"""', "```") if stripped.startswith(m)), None)
        if marker:
            docstring = marker
        elif stripped.startswith("@"):
            tags.extend(TAG.findall(stripped))
    _require(docstring is None, "Unterminated feature doc string")
    return tags


def package(*, requirement: bytes, criteria: bytes, feature: bytes | None,
            run_id: str, revision: int, source_system: str, source_ref: str) -> bytes:
    _require(isinstance(run_id, str) and ID.fullmatch(run_id), "Invalid story ID")
    _require(type(revision) is int and revision > 0, "Revision must be positive integer")
    _require(source_system in SYSTEMS, "Unknown source system")
    _require(isinstance(source_ref, str) and 1 <= len(source_ref) <= 120
             and not any(ord(c) < 32 for c in source_ref), "Invalid source ref")
    requirement.decode("utf-8")
    _require(0 < len(requirement) <= MAX_FILE and bool(requirement.strip()), "Invalid requirement")
    document, ids = validate_criteria(criteria, feature is not None)
    if feature is not None:
        feature.decode("utf-8")
        _require(0 < len(feature) <= MAX_FILE and _feature_tags(feature) == ids,
                 "Feature @case_ tags must appear exactly once in approved criteria order")
    files = {"requirement.md": requirement, "criteria.json": criteria}
    if feature is not None:
        files["acceptance.feature"] = feature
    meta = {"schema_version": 2, "kind": "clarity-portable-handoff", "run_id": run_id,
            "revision": revision, "story_type": document["story_type"],
            "source": {"system": source_system, "ref": source_ref}, "criterion_ids": ids,
            "files": {name: _hash(data) for name, data in files.items()}}
    files["handoff.json"] = _canonical(meta)
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(files):
            entry = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = (stat.S_IFREG | 0o600) << 16
            archive.writestr(entry, files[name])
    result = output.getvalue()
    _require(len(result) <= MAX_ARCHIVE, "Archive exceeds 2 MB")
    return result


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--requirement", type=Path, required=True, help="Exact reviewed developer requirement .md")
    p.add_argument("--criteria", type=Path, required=True, help="Validated, format-aware v2 criteria.json")
    p.add_argument("--feature", type=Path, help="Behavioral Gherkin with @case_<criterion-id> tags")
    p.add_argument("--story-id", required=True)
    p.add_argument("--revision", type=int, required=True)
    p.add_argument("--source-system", choices=sorted(SYSTEMS), required=True)
    p.add_argument("--source-ref", required=True)
    p.add_argument("--output", type=Path, required=True, help="New .zip file only; never overwritten")
    a = p.parse_args()
    try:
        contents = package(requirement=_read(a.requirement), criteria=_read(a.criteria),
                           feature=_read(a.feature) if a.feature else None,
                           run_id=a.story_id, revision=a.revision,
                           source_system=a.source_system, source_ref=a.source_ref)
        dest = a.output.absolute()
        _require(not any(z.is_symlink() for z in (dest, *dest.parents)),
                 "Output must not be a symlink")
        with dest.open("xb") as out:
            out.write(contents)
        print(f"PASS: exported {dest} sha256={_hash(contents)}; data-only (not approval)")
        return 0
    except (OSError, ValueError, TypeError, KeyError, UnicodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
