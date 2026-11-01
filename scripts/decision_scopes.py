"""Opt-in, structural decision-scope checks for Clarity's review-only packets.

This module verifies declared structure and chronology, NOT the authenticity of
an owner, policy, tracker revision, model output, or external signature.
Unlabeled legacy policy packets retain existing fail-closed behavior.
"""
from __future__ import annotations

import re

STATUSES = frozenset({"ACTIVE", "HISTORICAL", "PENDING"})
FIELDS = frozenset({"id", "scope", "status", "source", "revision",
                    "authority", "text", "supersedes"})
SCOPE = re.compile(r"[A-Z][A-Z0-9_]{2,63}\Z")


def validate_scoped_decisions(story: dict, policy: dict) -> None:
    """Reject invalid or misleading scope claims before model invocation."""
    opt_in = any(("decision_register" in policy,
                  "review_scope" in policy,
                  "review_scope" in story))
    if not opt_in:
        return
    source_scope, policy_scope = story.get("review_scope"), policy.get("review_scope")
    if (not isinstance(source_scope, str)
            or not SCOPE.fullmatch(source_scope)
            or source_scope != policy_scope):
        raise ValueError("Scoped decisions require matching explicit story/policy review_scope")
    records = policy.get("decision_register")
    if not isinstance(records, list) or not 0 < len(records) <= 50:
        raise ValueError("Scoped decision register must contain 1..50 records")
    if policy.get("decisions"):
        raise ValueError("Do not mix unlabeled legacy decisions with scoped register")
    ids = {}
    for entry in records:
        if not isinstance(entry, dict) or set(entry) != FIELDS:
            raise ValueError("Scoped decision requires exact provenance/status fields")
        for key in FIELDS - {"supersedes"}:
            val = entry[key]
            if (not isinstance(val, str) or not val.strip()
                    or len(val) > (5000 if key == "text" else 300)):
                raise ValueError("Invalid scoped decision " + key)
        if not SCOPE.fullmatch(entry["scope"]):
            raise ValueError("Invalid scoped decision scope")
        if entry["status"] not in STATUSES:
            raise ValueError("Unknown scoped decision status")
        supersedes = entry["supersedes"]
        if (not isinstance(supersedes, list)
                or len(supersedes) > 50
                or any(not isinstance(x, str) or not x.strip()
                       or len(x) > 300 for x in supersedes)
                or len(set(supersedes)) != len(supersedes)):
            raise ValueError("Invalid decision supersedes references")
        if entry["id"] in ids:
            raise ValueError("Duplicate scoped decision ID")
        ids[entry["id"]] = entry

    for entry in records:
        if entry["status"] != "ACTIVE" and entry["supersedes"]:
            raise ValueError("Only ACTIVE decisions can explicitly supersede history")
        for predecessor_id in entry["supersedes"]:
            predecessor = ids.get(predecessor_id)
            if predecessor is None or predecessor_id == entry["id"]:
                raise ValueError("Unknown or self-referential superseded decision")
            if predecessor["scope"] != entry["scope"]:
                raise ValueError("Cross-scope supersession is forbidden")
            if predecessor["status"] != "HISTORICAL":
                raise ValueError("Superseded decision must be explicitly HISTORICAL")
    if not any(d["scope"] == source_scope and d["status"] == "ACTIVE"
               for d in records):
        raise ValueError("Review scope requires an ACTIVE source decision")


def unresolved_scoped_decisions(policy: dict) -> list[str]:
    """A PENDING in-scope decision forbids a positive review candidate."""
    scope = policy.get("review_scope")
    return [d["id"] for d in policy.get("decision_register", [])
            if d["scope"] == scope and d["status"] == "PENDING"]
