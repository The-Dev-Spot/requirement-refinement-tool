"""Read-only, operator-selected Linear/GitHub evidence packet (proposal v1).

Validates structure, citation shape, exact review-input bindings and excerpt
digests. It CANNOT authenticate provider data, policy adoption, tracker owner,
or claim that a source is fresh. No network, credentials, commands or writes.
"""
from __future__ import annotations

import hashlib
import json
import re
from urllib.parse import urlsplit

PACK_KEYS = frozenset(("schema_version", "kind", "target_issue", "story_sha256",
                       "policy_sha256", "review_scope", "freshness", "sources"))
SOURCE_KEYS = frozenset(("id", "provider", "url", "revision", "scope",
                         "source_kind", "authority_claim", "excerpt",
                         "excerpt_sha256"))
TYPES = frozenset(("ISSUE", "DECISION", "DOCUMENT", "CODE", "TEST"))
AUTHORITY = frozenset(("UNVERIFIED", "CLAIMED_ACTIVE", "DRAFT", "HISTORICAL",
                       "IMPLEMENTATION"))
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
HEX40 = re.compile(r"[0-9a-f]{40}\Z")
ID = re.compile(r"S-[0-9]{3}\Z")
ISSUE = re.compile(r"[A-Z][A-Z0-9]+-[0-9]+\Z")
SCOPE = re.compile(r"[A-Z][A-Z0-9_]{2,63}\Z")


def canonical(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def validate_evidence_packet(packet, story, policy):
    """Return the exact validated packet; reject unsupported authority claims."""
    if not isinstance(packet, dict) or set(packet) != PACK_KEYS:
        raise ValueError("Evidence packet has missing or unexpected fields")
    if packet["schema_version"] != 1 or packet["kind"] != "clarity-context-evidence":
        raise ValueError("Unknown evidence context version")
    issue = packet["target_issue"]
    if not isinstance(issue, str) or not ISSUE.fullmatch(issue):
        raise ValueError("Invalid pinned issue ID")
    if isinstance(story.get("source_issue_id"), str) and story["source_issue_id"] != issue:
        raise ValueError("Evidence issue differs from story source")
    if (packet["story_sha256"] != digest(canonical(story).encode())
            or packet["policy_sha256"] != digest(canonical(policy).encode())):
        raise ValueError("Evidence packet is not bound to this story and policy")
    scope = story.get("review_scope", "LEGACY")
    if packet["review_scope"] != scope or (policy.get("review_scope", "LEGACY") != scope):
        raise ValueError("Evidence scope is inconsistent with review scope")
    if not isinstance(scope, str) or not SCOPE.fullmatch(scope):
        raise ValueError("Evidence scope invalid")
    # No external source identity has been independently verified yet. Never
    # permit a caller to self-assert a trusted snapshot by editing JSON.
    if packet["freshness"] not in ("SOURCE_UNVERIFIED", "SOURCE_CHANGED"):
        raise ValueError("This evidence collector does not issue trusted freshness")
    sources = packet["sources"]
    if not isinstance(sources, list) or not 0 < len(sources) <= 30:
        raise ValueError("Evidence packet must contain 1..30 source excerpts")
    if len(canonical(packet).encode()) > 90_000:
        raise ValueError("Evidence packet exceeds safe review size")
    repositories = policy.get("evidence_allowed_repositories")
    workspace = policy.get("evidence_linear_workspace")
    if (not isinstance(repositories, list) or len(repositories) > 15
            or any(not isinstance(r, str)
                   or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", r)
                   for r in repositories)
            or len(set(repositories)) != len(repositories)):
        raise ValueError("Evidence repository allowlist must be explicit")
    if not isinstance(workspace, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", workspace):
        raise ValueError("Evidence Linear workspace allowlist must be explicit")
    seen = set()
    for source in sources:
        if not isinstance(source, dict) or set(source) != SOURCE_KEYS:
            raise ValueError("Malformed source citation")
        key = source["id"]
        if not isinstance(key, str) or not ID.fullmatch(key) or key in seen:
            raise ValueError("Invalid or duplicated source ID")
        seen.add(key)
        kind, authority, provider = (source["source_kind"],
                                      source["authority_claim"],
                                      source["provider"])
        if kind not in TYPES or authority not in AUTHORITY:
            raise ValueError("Unsupported source type or authority claim")
        if provider not in ("linear", "github"):
            raise ValueError("Evidence provider must be Linear or GitHub")
        excerpt = source["excerpt"]
        if not isinstance(excerpt, str) or not excerpt.strip() or len(excerpt) > 3200:
            raise ValueError("Invalid bounded source excerpt")
        if (not isinstance(source["excerpt_sha256"], str)
                or not HEX64.fullmatch(source["excerpt_sha256"])
                or digest(excerpt.encode()) != source["excerpt_sha256"]):
            raise ValueError("Source excerpt hash mismatch")
        if (not isinstance(source["scope"], str)
                or not SCOPE.fullmatch(source["scope"])):
            raise ValueError("Invalid source scope")
        revision, url = source["revision"], source["url"]
        if not isinstance(revision, str) or not isinstance(url, str):
            raise ValueError("Missing source revision or URL")
        parsed = urlsplit(url)
        if (parsed.scheme != "https" or parsed.username or parsed.password
                or parsed.port not in (None, 443) or parsed.query
                or len(url) > 750 or not parsed.path.startswith("/")):
            raise ValueError("Untrusted source URL")
        if provider == "github":
            # Only a commit-pinned GitHub blob is accepted; branch URLs and
            # arbitrary repository/issue URLs are not suitable for code facts.
            if parsed.hostname != "github.com" or not HEX40.fullmatch(revision):
                raise ValueError("GitHub evidence requires a pinned commit")
            bits = parsed.path.strip("/").split("/")
            if (len(bits) < 5 or bits[2] != "blob" or bits[3] != revision
                    or not all(re.fullmatch(r"[A-Za-z0-9._-]+", b) for b in bits)):
                raise ValueError("GitHub evidence URL is not a commit-pinned file")
            if bits[0] + "/" + bits[1] not in repositories:
                raise ValueError("GitHub repository not on trusted allowlist")
            if parsed.fragment and not re.fullmatch(r"L[0-9]+(?:-L[0-9]+)?", parsed.fragment):
                raise ValueError("Invalid GitHub line citation")
            if kind not in ("CODE", "TEST", "DOCUMENT"):
                raise ValueError("GitHub code excerpts cannot confer decisions")
            if authority not in ("IMPLEMENTATION", "UNVERIFIED", "HISTORICAL"):
                raise ValueError("GitHub content cannot ratify policy")
        else:
            if parsed.path.strip("/").split("/")[0] != workspace:
                raise ValueError("Linear workspace not on trusted allowlist")
            if parsed.hostname != "linear.app" or parsed.fragment:
                raise ValueError("Linear evidence requires a clean issue/document URL")
            if not re.fullmatch(r"/[^/]+/(?:issue|document)/[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)?", parsed.path):
                raise ValueError("Invalid Linear issue/document citation")
            if not (8 <= len(revision) <= 100 and
                    all(c.isalnum() or c in "-:TZ.+_" for c in revision)):
                raise ValueError("Linear revision must be explicit (updatedAt)")
            if kind in ("CODE", "TEST") or authority == "IMPLEMENTATION":
                raise ValueError("Linear issue content is not observed source code")
    return packet
