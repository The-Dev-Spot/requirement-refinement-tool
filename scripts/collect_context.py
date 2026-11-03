"""Bounded, explicit read-only Linear/GitHub collection for Clarity.

This standalone coordinator runs OUTSIDE the isolated model reviewer. It
queries only operator-allowlisted issues and files and writes a non-authoritative
offline evidence packet. No mutation, repository clone, arbitrary URL fetch,
model invocation, question answering, or acceptance issuance is possible.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
from urllib import error, parse, request

from evidence_context import canonical, digest, validate_evidence_packet

MAX_HTTP = 800_000
MAX_FILE = 120_000
MAX_PLAN = 12_000
MAX_SOURCES = 20
ISSUE_RE = re.compile(r"[A-Z][A-Z0-9]+-[0-9]+\Z")
DOC_RE = re.compile(r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}\Z")
REPO_RE = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
SCOPE_RE = re.compile(r"[A-Z][A-Z0-9_]{2,63}\Z")
SHA_RE = re.compile(r"[0-9a-f]{40}\Z")
REV_RE = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?Z\Z")
PATH_PART_RE = re.compile(r"[A-Za-z0-9._-]+\Z")
LINEAR_QUERY = """query ClarityEvidenceIssue($id: String!) {
  issue(id: $id) { identifier title description updatedAt }
}"""
DOCUMENT_QUERY = """query ClarityEvidenceDocument($id: String!) {
  document(id: $id) { id title content updatedAt url }
}"""


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class ReadOnlyHTTP:
    """Explicit fixed-host transport; no caller-supplied URLs or redirects."""

    def __init__(self):
        self.opener = request.build_opener(NoRedirect)

    def json(self, method, url, headers, payload=None):
        if method not in ("GET", "POST"):
            raise ValueError("Only fixed read-only provider operations are supported")
        parsed = parse.urlsplit(url)
        if parsed.username or parsed.password or parsed.fragment:
            raise ValueError("Credential-bearing or fragmented URL is forbidden")
        if parsed.scheme != "https" or parsed.hostname not in (
                "api.github.com", "api.linear.app") or parsed.port not in (None, 443):
            raise ValueError("External destination forbidden")
        if method == "POST" and url != "https://api.linear.app/graphql":
            raise ValueError("Only Linear GraphQL read query may use POST")
        if method == "GET" and parsed.hostname != "api.github.com":
            raise ValueError("Only GitHub read endpoints may use GET")
        body = canonical(payload).encode() if payload is not None else None
        req = request.Request(url, data=body, headers=headers, method=method)
        try:
            with self.opener.open(req, timeout=8) as res:
                raw = res.read(MAX_HTTP + 1)
                if res.status != 200 or len(raw) > MAX_HTTP:
                    raise ValueError("Provider response exceeded bounds")
        except error.HTTPError as exc:
            # Do NOT print error bodies, URLs with source names, or token values.
            raise ValueError("Provider request denied (HTTP %d)" % exc.code) from None
        except (error.URLError, TimeoutError) as exc:
            raise ValueError("Provider unreachable or timed out") from None
        try:
            data = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            raise ValueError("Provider did not return JSON") from None
        if not isinstance(data, dict):
            raise ValueError("Malformed provider response")
        return data


class LinearRead:
    def __init__(self, http, key):
        self.http, self.key = http, key

    def issue(self, issue_id):
        response = self.http.json(
            "POST", "https://api.linear.app/graphql",
            {"Authorization": self.key, "Content-Type": "application/json"},
            {"query": LINEAR_QUERY, "variables": {"id": issue_id}})
        # A GraphQL HTTP 200 with errors is NOT a successful partial result.
        if response.get("errors") or not isinstance(response.get("data"), dict):
            raise ValueError("Linear GraphQL read failed or was partial")
        result = response["data"].get("issue")
        if not isinstance(result, dict) or result.get("identifier") != issue_id:
            raise ValueError("Linear issue not found or identifier mismatch")
        if (not isinstance(result.get("title"), str)
                or not isinstance(result.get("description"), str)
                or not isinstance(result.get("updatedAt"), str)
                or not REV_RE.fullmatch(result["updatedAt"])):
            raise ValueError("Linear source missing revision or content")
        return result

    def document(self, document_id):
        response = self.http.json(
            "POST", "https://api.linear.app/graphql",
            {"Authorization": self.key, "Content-Type": "application/json"},
            {"query": DOCUMENT_QUERY, "variables": {"id": document_id}})
        if response.get("errors") or not isinstance(response.get("data"), dict):
            raise ValueError("Linear GraphQL document read failed or was partial")
        result = response["data"].get("document")
        if (not isinstance(result, dict)
                or result.get("id") != document_id
                or not isinstance(result.get("title"), str)
                or not isinstance(result.get("content"), str)
                or not isinstance(result.get("url"), str)
                or not isinstance(result.get("updatedAt"), str)
                or not REV_RE.fullmatch(result["updatedAt"])):
            raise ValueError("Linear document missing, unverified, or incomplete")
        return result


class GitHubRead:
    def __init__(self, http, key):
        self.http, self.key = http, key

    def _get(self, path, query=None):
        url = "https://api.github.com" + path
        if query:
            url += "?" + parse.urlencode(query)
        return self.http.json(
            "GET", url,
            {"Authorization": "Bearer " + self.key,
             "Accept": "application/vnd.github+json",
             "X-GitHub-Api-Version": "2022-11-28"})

    def commit(self, repository, ref):
        owner, name = repository.split("/")
        sha = self._get("/repos/%s/%s/commits/%s" %
                        (owner, name, parse.quote(ref, safe=""))).get("sha")
        if not isinstance(sha, str) or not SHA_RE.fullmatch(sha):
            raise ValueError("GitHub commit SHA not verified")
        return sha

    def file(self, repository, path, sha):
        owner, name = repository.split("/")
        result = self._get("/repos/%s/%s/contents/%s" %
                           (owner, name, "/".join(parse.quote(x, safe="") for x in path.split("/"))),
                           {"ref": sha})
        if (result.get("type") != "file" or result.get("encoding") != "base64"
                or not isinstance(result.get("content"), str)
                or not isinstance(result.get("size"), int)
                or not 0 < result["size"] <= MAX_FILE):
            raise ValueError("GitHub source is not a bounded text file")
        try:
            content = base64.b64decode(result["content"].replace("\n", ""), validate=True)
            text = content.decode("utf-8", errors="strict")
        except (ValueError, UnicodeDecodeError):
            raise ValueError("GitHub content invalid or not UTF-8") from None
        if len(content) != result["size"] or "\x00" in text:
            raise ValueError("GitHub file size/content mismatch")
        return text


def read_private_key(path):
    """Keys come from private files, never command-line values or code."""
    p = Path(path)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(str(p), flags)
    except OSError:
        raise ValueError("Credential file must be a regular private file") from None
    with os.fdopen(fd, "rb") as stream:
        state = os.fstat(stream.fileno())
        if (not stat.S_ISREG(state.st_mode) or not 0 < state.st_size <= 4096
                or stat.S_IMODE(state.st_mode) & 0o077):
            raise ValueError("Credential file must be a small regular owner-only file")
        try:
            value = stream.read(4097).decode("ascii").strip()
        except UnicodeDecodeError:
            raise ValueError("Credential file must be ASCII") from None
    if not (20 <= len(value) <= 4096) or any(ch.isspace() for ch in value):
        raise ValueError("Credential file contains invalid value")
    return value


def read_bounded_json(path, maximum):
    p = Path(path)
    if p.is_symlink() or not p.is_file() or not 0 < p.stat().st_size <= maximum:
        raise ValueError("Missing or oversized private input JSON")
    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Expected JSON object")
    return data


def valid_path(path):
    if (not isinstance(path, str) or len(path) > 220
            or not 1 <= len(path.split("/")) <= 15
            or any(not PATH_PART_RE.fullmatch(p) or p in (".", "..")
                   for p in path.split("/"))
            or str(PurePosixPath(path)) != path):
        raise ValueError("Disallowed GitHub file path")
    return path


def validate_plan(plan, story, policy):
    allowed_keys = {"schema_version", "target_issue", "linear", "github"}
    if (not isinstance(plan, dict)
            or set(plan) not in (allowed_keys, allowed_keys | {"documents"})):
        raise ValueError("Collector plan requires exact bounded fields")
    target = plan.get("target_issue")
    if (plan["schema_version"] != 1 or not isinstance(target, str)
            or not ISSUE_RE.fullmatch(target)
            or story.get("source_issue_id") != target):
        raise ValueError("Collector plan target must match canonical story issue")
    issue_items, code_items, documents = plan["linear"], plan["github"], plan.get("documents", [])
    if (not isinstance(issue_items, list) or not 1 <= len(issue_items) <= 15
            or not isinstance(code_items, list) or len(code_items) > 10
            or not isinstance(documents, list) or len(documents) > 5
            or len(issue_items) + len(code_items) + len(documents) > MAX_SOURCES):
        raise ValueError("Collector plan exceeds source limits")
    ids = set()
    for item in issue_items:
        if not isinstance(item, dict) or set(item) != {"id", "scope", "focus"}:
            raise ValueError("Invalid Linear source selection")
        iid, scope, focus = item["id"], item["scope"], item["focus"]
        if (not isinstance(iid, str) or not ISSUE_RE.fullmatch(iid)
                or iid in ids or not isinstance(scope, str)
                or not SCOPE_RE.fullmatch(scope)
                or not isinstance(focus, str) or len(focus) > 100):
            raise ValueError("Invalid or repeated Linear issue selection")
        ids.add(iid)
    if target not in ids:
        raise ValueError("Target issue must be in Linear source selection")
    workspace = policy.get("evidence_linear_workspace")
    if not isinstance(workspace, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", workspace):
        raise ValueError("Linear workspace must be explicitly allowlisted")
    doc_ids = set()
    for selected in documents:
        if not isinstance(selected, dict) or set(selected) != {
                "id", "scope", "focus", "url"}:
            raise ValueError("Invalid Linear document selection")
        did, scope, focus, url = (selected["id"], selected["scope"],
                                  selected["focus"], selected["url"])
        prefix = "https://linear.app/" + workspace + "/document/"
        if (not isinstance(did, str) or not DOC_RE.fullmatch(did)
                or did in doc_ids or not isinstance(scope, str)
                or not SCOPE_RE.fullmatch(scope)
                or not isinstance(focus, str) or len(focus) > 100
                or not isinstance(url, str) or not url.startswith(prefix)
                or not re.fullmatch(r"[A-Za-z0-9_-]+", url[len(prefix):])):
            raise ValueError("Unauthorized or duplicate Linear document selection")
        doc_ids.add(did)
    allowed = policy.get("evidence_allowed_repositories")
    if not isinstance(allowed, list):
        raise ValueError("Explicit project repository allowlist required")
    paths = set()
    for item in code_items:
        if not isinstance(item, dict) or set(item) != {
                "repository", "ref", "path", "scope", "kind", "focus"}:
            raise ValueError("Invalid GitHub source selection")
        repo, ref, path = item["repository"], item["ref"], item["path"]
        if (not isinstance(repo, str) or not REPO_RE.fullmatch(repo)
                or repo not in allowed
                or not isinstance(ref, str) or ref not in ("main", "master")
                or not isinstance(item["scope"], str)
                or not SCOPE_RE.fullmatch(item["scope"])
                or item["kind"] not in ("CODE", "TEST", "DOCUMENT")
                or not isinstance(item["focus"], str)
                or len(item["focus"]) > 100):
            raise ValueError("Repository, revision or scope not authorized")
        valid_path(path)
        selector = (repo, ref, path)
        if selector in paths:
            raise ValueError("Repeated GitHub source")
        paths.add(selector)
    return plan


def snippet(text, focus, limit=2900):
    if not text.strip():
        raise ValueError("Empty source text")
    pos = text.casefold().find(focus.casefold()) if focus else 0
    if pos < 0:
        raise ValueError("Approved source focus not found")
    start = max(0, pos - 160)
    excerpt = text[start:start + limit].strip()
    # Stop obvious raw credentials from entering model context. This check is
    # conservative and NOT a substitute for a trusted secret scanner or
    # repository classification before model use.
    forbidden = re.compile(
        r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
        r"|github_pat_[A-Za-z0-9_]{20,}"
        r"|gh[pousr]_[A-Za-z0-9]{20,}"
        r"|sk-[A-Za-z0-9_-]{32,}"
        r"|Bearer\s+[A-Za-z0-9_.-]{30,}",
        re.IGNORECASE)
    if forbidden.search(excerpt):
        raise ValueError("Possible credential in selected source excerpt")
    return excerpt


def source_entry(index, provider, url, revision, scope, kind, claim, text):
    return {
        "id": "S-%03d" % index,
        "provider": provider, "url": url, "revision": revision,
        "scope": scope, "source_kind": kind, "authority_claim": claim,
        "excerpt": text, "excerpt_sha256": digest(text.encode()),
    }


def collect(plan, story, policy, linear, github):
    """Deterministic allowlisted retrieval; injected clients simplify offline tests."""
    validate_plan(plan, story, policy)
    workspace = policy["evidence_linear_workspace"]
    entries, original_issues, branch_heads = [], {}, {}
    index = 0
    for selected in plan["linear"]:
        iid = selected["id"]
        issue = linear.issue(iid)
        original_issues[iid] = (issue["updatedAt"],
                                digest((issue["title"] + "\n" + issue["description"]).encode()))
        text = snippet(issue["title"] + "\n\n" + issue["description"], selected["focus"])
        index += 1
        entries.append(source_entry(
            index, "linear", "https://linear.app/%s/issue/%s" % (workspace, iid),
            issue["updatedAt"], selected["scope"], "ISSUE", "UNVERIFIED", text))
    original_documents = {}
    for selected in plan.get("documents", []):
        did = selected["id"]
        document = linear.document(did)
        if document["url"] != selected["url"]:
            raise ValueError("Linear document URL changed since source selection")
        original_documents[did] = (document["updatedAt"],
            digest((document["title"] + "\n" + document["content"]).encode()))
        text = snippet(document["title"] + "\n\n" + document["content"],
                       selected["focus"])
        index += 1
        entries.append(source_entry(
            index, "linear", selected["url"], document["updatedAt"],
            selected["scope"], "DOCUMENT", "UNVERIFIED", text))
    for selected in plan["github"]:
        repo, ref, path = selected["repository"], selected["ref"], selected["path"]
        key = (repo, ref)
        if key not in branch_heads:
            branch_heads[key] = github.commit(repo, ref)
        head = branch_heads[key]
        content = github.file(repo, path, head)
        excerpt = snippet(content, selected["focus"])
        # Real line anchors are derived from the text offset, not guessed.
        offset = content.find(excerpt)
        if offset < 0:
            raise ValueError("Cannot establish GitHub excerpt line location")
        first = content.count("\n", 0, offset) + 1
        last = first + excerpt.count("\n")
        url = ("https://github.com/%s/blob/%s/%s#L%d-L%d" %
               (repo, head, path, first, last))
        index += 1
        entries.append(source_entry(index, "github", url, head,
                                    selected["scope"], selected["kind"],
                                    "IMPLEMENTATION" if selected["kind"] in ("CODE", "TEST")
                                    else "UNVERIFIED", excerpt))
    # Re-read each explicitly allowed source after collection. A response at
    # time T does not constitute a durable owner attestation or signing proof.
    changed = False
    for iid, old in original_issues.items():
        current = linear.issue(iid)
        now = (current["updatedAt"],
               digest((current["title"] + "\n" + current["description"]).encode()))
        changed = changed or old != now
    for did, old in original_documents.items():
        doc = linear.document(did)
        now = (doc["updatedAt"],
               digest((doc["title"] + "\n" + doc["content"]).encode()))
        changed = (old != now) or changed
    for (repo, ref), old in branch_heads.items():
        observed = github.commit(repo, ref)
        changed = (observed != old) or changed
    packet = {
        "schema_version": 1, "kind": "clarity-context-evidence",
        "target_issue": plan["target_issue"],
        "story_sha256": digest(canonical(story).encode()),
        "policy_sha256": digest(canonical(policy).encode()),
        "review_scope": story.get("review_scope", "LEGACY"),
        "freshness": "SOURCE_CHANGED" if changed else "SOURCE_UNVERIFIED",
        "sources": entries,
    }
    validate_evidence_packet(packet, story, policy)
    return packet


def write_private(path, packet):
    p = Path(path)
    if p.parent.is_symlink() or not p.parent.is_dir():
        raise ValueError("Private evidence output directory missing")
    if stat.S_IMODE(p.parent.stat().st_mode) & 0o077:
        raise ValueError("Private evidence output directory must be owner-only")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(str(p), flags, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            os.fchmod(output.fileno(), 0o600)
            output.write(canonical(packet) + "\n")
    except BaseException:
        p.unlink(missing_ok=True)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--story", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--linear-key-file", type=Path, required=True)
    parser.add_argument("--github-key-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        plan = read_bounded_json(args.plan, MAX_PLAN)
        story = read_bounded_json(args.story, 250_000)
        policy = read_bounded_json(args.policy, 100_000)
        validate_plan(plan, story, policy)
        linear = LinearRead(ReadOnlyHTTP(), read_private_key(args.linear_key_file))
        github = GitHubRead(ReadOnlyHTTP(), read_private_key(args.github_key_file))
        packet = collect(plan, story, policy, linear, github)
        write_private(args.output, packet)
        print("Read-only context: %d excerpts, status=%s, sha256=%s" %
              (len(packet["sources"]), packet["freshness"],
               digest(canonical(packet).encode())))
        print("No tracker write, model call, approval, or Forge dispatch.")
        return 0
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        # No provider exception bodies, token values or source excerpts logged.
        print("BLOCKED: evidence retrieval, validation or private output failed",
              file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
