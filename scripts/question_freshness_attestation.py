"""Authenticate collector readbacks; never certify model or owner authority.

The shared HMAC key belongs ONLY to the trusted collector and reconciler.
Both can mint receipts: neither belongs in a model/PR execution environment.
No network, inference, or general-purpose signing CLI is provided here.
"""
from __future__ import annotations

import hashlib
import hmac
import time

from collect_context import read_private_key
from evidence_context import canonical, digest, HEX64

DOMAIN = b"clarity-question-freshness-v1\x00"
MAX_AGE_SECONDS = 900


def read_attestation_key(path):
    key = read_private_key(path).encode("ascii")
    _validate_key(key)
    return key


def _validate_key(key):
    if not isinstance(key, bytes) or not 32 <= len(key) <= 4096:
        raise ValueError("Separate collector attestation key must have at least 32 bytes")


def _mac(payload, key):
    _validate_key(key)
    return hmac.new(key, DOMAIN + canonical(payload).encode(), hashlib.sha256).hexdigest()


def attest_freshness(readback, challenge_sha256, key, started_at, completed_at):
    """Called by collector only AFTER its own recheck; not for submitted JSON."""
    if not isinstance(challenge_sha256, str) or not HEX64.fullmatch(challenge_sha256):
        raise ValueError("Exact independent challenge digest required")
    if (type(started_at) is not int or type(completed_at) is not int
            or started_at < 0 or not started_at <= completed_at):
        raise ValueError("Invalid collector read interval")
    payload = {
        "schema_version": 1,
        "kind": "clarity-authenticated-question-freshness",
        "challenge_sha256": challenge_sha256,
        "started_at": started_at,
        "completed_at": completed_at,
        "readback": readback,
    }
    return {"payload": payload, "hmac_sha256": _mac(payload, key)}


def verify_freshness(envelope, challenge, key, *, now=None, max_age_seconds=300):
    """Age is trusted caller configuration; model input cannot extend it."""
    if (type(max_age_seconds) is not int
            or not 1 <= max_age_seconds <= MAX_AGE_SECONDS):
        raise ValueError("Invalid trusted freshness age limit")
    if (not isinstance(envelope, dict)
            or set(envelope) != {"payload", "hmac_sha256"}
            or not isinstance(envelope["hmac_sha256"], str)
            or not HEX64.fullmatch(envelope["hmac_sha256"])):
        raise ValueError("Authenticated collector receipt required")
    payload = envelope["payload"]
    if not hmac.compare_digest(envelope["hmac_sha256"], _mac(payload, key)):
        raise ValueError("Collector receipt authentication failed")
    if (not isinstance(payload, dict) or set(payload) != {
            "schema_version", "kind", "challenge_sha256", "started_at",
            "completed_at", "readback"}
            or type(payload["schema_version"]) is not int
            or payload["schema_version"] != 1
            or payload["kind"] != "clarity-authenticated-question-freshness"
            or payload["challenge_sha256"] != digest(canonical(challenge).encode())):
        raise ValueError("Collector receipt is not bound to exact challenge")
    now = int(time.time()) if now is None else now
    start, end = payload["started_at"], payload["completed_at"]
    if (type(now) is not int or type(start) is not int or type(end) is not int
            or not 0 <= start <= end <= now or now - start > max_age_seconds):
        raise ValueError("Collector receipt expired or has invalid read interval")
    return payload["readback"]
