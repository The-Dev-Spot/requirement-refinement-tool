"""Authenticated original GitHub discussion digests, collected before review.

Only trusted collectors and reconcilers may hold this symmetric key. No raw
issue text, model invocation, signing CLI, or approval authority is provided.
"""
from __future__ import annotations

import hashlib
import hmac

from evidence_context import canonical, digest, HEX64

DOMAIN = b"clarity-original-github-discussions-v1\x00"


def _mac(payload, key):
    if not isinstance(key, bytes) or not 32 <= len(key) <= 4096:
        raise ValueError("Trusted collector key must have at least 32 bytes")
    return hmac.new(key, DOMAIN + canonical(payload).encode(), hashlib.sha256).hexdigest()


def capture_snapshot(evidence, discussions, key):
    """Collector-internal: discussions must come from this collection's reads."""
    payload = {
        "schema_version": 1, "kind": "clarity-original-github-discussions",
        "target_issue": evidence["target_issue"], "review_scope": evidence["review_scope"],
        "evidence_sha256": digest(canonical(evidence).encode()),
        "story_sha256": evidence["story_sha256"], "policy_sha256": evidence["policy_sha256"],
        "coverage": "ALL_SELECTED_ISSUE_COMMENTS", "discussions": discussions,
    }
    envelope = {"payload": payload, "hmac_sha256": _mac(payload, key)}
    validate_snapshot(envelope, evidence, key)
    return envelope


def validate_snapshot(envelope, evidence, key):
    if (not isinstance(envelope, dict) or set(envelope) != {"payload", "hmac_sha256"}
            or not isinstance(envelope["hmac_sha256"], str)
            or not HEX64.fullmatch(envelope["hmac_sha256"])):
        raise ValueError("Authenticated original discussion snapshot required")
    payload = envelope["payload"]
    if not hmac.compare_digest(envelope["hmac_sha256"], _mac(payload, key)):
        raise ValueError("Original discussion snapshot authentication failed")
    if (not isinstance(payload, dict) or set(payload) != {
            "schema_version", "kind", "target_issue", "review_scope", "evidence_sha256",
            "story_sha256", "policy_sha256", "coverage", "discussions"}
            or type(payload["schema_version"]) is not int or payload["schema_version"] != 1
            or payload["kind"] != "clarity-original-github-discussions"
            or payload["target_issue"] != evidence["target_issue"]
            or payload["review_scope"] != evidence["review_scope"]
            or payload["evidence_sha256"] != digest(canonical(evidence).encode())
            or payload["story_sha256"] != evidence["story_sha256"]
            or payload["policy_sha256"] != evidence["policy_sha256"]
            or payload["coverage"] != "ALL_SELECTED_ISSUE_COMMENTS"
            or evidence["schema_version"] != 3
            or evidence.get("discussion_snapshot_sha256") != digest(canonical(payload["discussions"]).encode())
            or evidence["freshness"] != "SOURCE_UNVERIFIED"):
        raise ValueError("Original discussion snapshot binding or coverage differs")
    originals = [s for s in evidence["sources"] if s["source_kind"] == "ISSUE"]
    discussions = payload["discussions"]
    if (not originals or not isinstance(discussions, list)
            or len(discussions) != len(originals)):
        raise ValueError("Original snapshot must cover every selected issue")
    for source, entry in zip(originals, discussions):
        if (not isinstance(entry, dict) or set(entry) != {
                "source_id", "url", "revision", "discussion_sha256"}
                or entry["source_id"] != source["id"] or entry["url"] != source["url"]
                or entry["revision"] != source["revision"]
                or not isinstance(entry["discussion_sha256"], str)
                or not HEX64.fullmatch(entry["discussion_sha256"])):
            raise ValueError("Original discussion source identity or digest differs")
    return {entry["source_id"]: entry for entry in discussions}
