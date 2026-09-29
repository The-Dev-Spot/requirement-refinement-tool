"""Bounded read-only imports. Never mutate a tracker or follow credential redirects."""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .guardrails import ValidationError, canonical, digest, identifier
from .models import document

LINEAR_ENDPOINT = "https://api.linear.app/graphql"
ISSUE_QUERY = """query ClarityReadIssue($id: String!, $after: String) {
  issue(id: $id) { id identifier title description updatedAt url
    team { id } project { id }
    comments(first: 50, after: $after) {
      nodes { id body updatedAt }
      pageInfo { hasNextPage endCursor }
    }
  }
}"""


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValidationError("Tracker redirect refused")


class LinearReader:
    """Use a read-only, team-restricted API key. No OAuth onboarding is shipped.

Injected transports are trusted test/application code, not user configuration.
The issue revision is checked on each comments page. Fail, never silently return
partial evidence, when pagination/budgets/permissions cannot be satisfied.
"""
    def __init__(self, api_key: str, team_id: str, *, project_id: str | None = None, max_pages: int = 10, max_bytes: int = 1_000_000, transport=None):
        if not isinstance(api_key, str) or not api_key.strip() or any(c in api_key for c in "\r\n"):
            raise ValidationError("Invalid tracker credential")
        identifier(team_id)
        if project_id is not None:
            identifier(project_id)
        if type(max_pages) is not int or not 1 <= max_pages <= 20 or type(max_bytes) is not int or not 1000 <= max_bytes <= 2_000_000:
            raise ValidationError("Invalid retrieval budgets")
        self._key = api_key
        self.team = team_id
        self.project = project_id
        self.max_pages = max_pages
        self.max_bytes = max_bytes
        self._transport = transport or self._post

    def _post(self, variables: dict) -> dict:
        request = Request(LINEAR_ENDPOINT, data=canonical({"query": ISSUE_QUERY, "variables": variables}).encode(), headers={"Authorization": self._key, "Content-Type": "application/json"}, method="POST")
        opener = build_opener(_NoRedirect())
        for attempt in range(3):
            try:
                with opener.open(request, timeout=10) as response:
                    data = response.read(self.max_bytes + 1)
                    if len(data) > self.max_bytes:
                        raise ValidationError("Tracker response exceeds budget")
                    return json.loads(data)
            except HTTPError as exc:
                if exc.code == 429 or exc.code == 400:
                    raise ValidationError("Tracker rejected or rate-limited the read; retry later") from None
                if exc.code not in {502, 503, 504} or attempt == 2:
                    raise ValidationError("Tracker read failed; check permissions and availability") from None
            except (URLError, TimeoutError):
                if attempt == 2:
                    raise ValidationError("Tracker read timed out or is unavailable") from None
            except (UnicodeError, json.JSONDecodeError):
                raise ValidationError("Tracker returned invalid JSON") from None
            time.sleep(0.25 * (2 ** attempt))
        raise ValidationError("Tracker read failed")

    def read_issue(self, issue_id: str) -> dict:
        identifier(issue_id)
        cursor = None
        cursors = set()
        comment_ids = set()
        comments = []
        base = None
        size = 0
        for _ in range(self.max_pages):
            result = self._transport({"id": issue_id, "after": cursor})
            size += len(canonical(result).encode())
            if size > self.max_bytes:
                raise ValidationError("Combined tracker evidence exceeds budget")
            if not isinstance(result, dict) or result.get("errors"):
                raise ValidationError("Tracker returned errors or partial data")
            data = result.get("data")
            if not isinstance(data, dict):
                raise ValidationError("Tracker data is absent or malformed")
            issue = data.get("issue")
            if not isinstance(issue, dict) or not isinstance(issue.get("team"), dict) or issue["team"].get("id") != self.team:
                raise ValidationError("Issue absent, inaccessible, or outside the selected team")
            if self.project is not None and (not isinstance(issue.get("project"), dict) or issue["project"].get("id") != self.project):
                raise ValidationError("Issue outside the selected project")
            metadata = {k: issue.get(k) for k in ("id", "identifier", "title", "description", "updatedAt", "url")}
            if any(not isinstance(metadata[k], str) or not metadata[k] for k in ("id", "identifier", "title", "updatedAt", "url")):
                raise ValidationError("Incomplete tracker source metadata")
            if metadata["description"] is not None and not isinstance(metadata["description"], str):
                raise ValidationError("Invalid tracker description")
            if base is not None and metadata != base:
                raise ValidationError("Source changed during pagination; restart the read")
            base = metadata
            connection = issue.get("comments")
            if not isinstance(connection, dict) or not isinstance(connection.get("nodes"), list):
                raise ValidationError("Comments unavailable; evidence is incomplete")
            for item in connection["nodes"]:
                if not isinstance(item, dict) or any(not isinstance(item.get(k), str) or not item[k] for k in ("id", "body", "updatedAt")):
                    raise ValidationError("Incomplete comment evidence")
                if item["id"] in comment_ids:
                    raise ValidationError("Duplicate comment during pagination; restart the read")
                comment_ids.add(item["id"])
                comments.append({k: item[k] for k in ("id", "body", "updatedAt")})
            page = connection.get("pageInfo")
            if not isinstance(page, dict) or type(page.get("hasNextPage")) is not bool:
                raise ValidationError("Invalid pagination metadata")
            if not page["hasNextPage"]:
                source = {"provider": "linear", "team_id": self.team, "project_id": self.project, "issue": base, "comments": comments}
                return {"source": source, "revision": digest(source), "complete": True, "limitations": "Issue and paginated comments only; linked documents, attachments and other fields require separate authorized investigation. Concurrent comment edits may require a fresh read."}
            cursor = page.get("endCursor")
            if not isinstance(cursor, str) or not cursor or cursor in cursors:
                raise ValidationError("Pagination cursor missing or repeated")
            cursors.add(cursor)
        raise ValidationError("Retrieval budget exhausted; evidence is incomplete")


def import_markdown(path: Path, ac_path: Path, *, project: str, source_id: str, source_date: str, kind: str) -> dict:
    """Explicit local import; never follow paths/links suggested inside source text."""
    data = []
    for file in (path, ac_path):
        if file.is_symlink() or not file.is_file() or file.stat().st_size > 400000:
            raise ValidationError("Source must be a bounded local file, not a symlink")
        data.append(file.read_text(encoding="utf-8"))
    description, ac = data
    revision = hashlib.sha256(canonical(data).encode()).hexdigest()
    return document({"schema_version": 1, "project": project, "title": path.stem, "kind": kind, "description": description, "acceptance_criteria": ac, "source": {"id": source_id, "revision": revision, "text": description + "\n\n" + ac, "locator": "local:" + path.name}, "evidence": [{"id": "SRC-1", "title": path.name, "section": "Supplied requirement and acceptance criteria", "source_date": source_date, "locator": "local:" + path.name, "quote": description, "status": "confirmed"}], "investigation": {"summary": "Local supplied source only; independently review whether further investigation is required.", "missing": [], "conflicts": []}, "questions": [], "acknowledged_answers": [], "proposals": [], "risk_ids": [], "canonical_steps": [], "interface_touched": False, "regulated": False})
