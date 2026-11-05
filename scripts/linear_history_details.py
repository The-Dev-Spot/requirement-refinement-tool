"""Fixed-query, bounded Linear history details; no mutation or intake authority."""
from __future__ import annotations

from datetime import datetime
import re
from urllib.parse import urlsplit

from collect_context import LinearRead, REV_RE, snippet
from evidence_context import canonical, digest, HEX64

UUID = re.compile(r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}\Z")
MAX_COMMENTS = 20
MAX_COMMENT_EXCERPT = 800
MAX_DISCUSSION_BYTES = 90_000
SCOPE_QUERY = """query ClarityHistoricalScope($id: String!) {
  issue(id: $id) { id identifier url team { id key } project { id } }
}"""
DETAIL_QUERY = """query ClarityHistoricalIssue($id: String!) {
  issue(id: $id) {
    id identifier url title description updatedAt
    team { id key } project { id } state { id name type }
    comments(first: 21, orderBy: createdAt, includeArchived: true) {
      nodes { id issueId parentId url body createdAt updatedAt user { id } }
      pageInfo { hasNextPage hasPreviousPage }
    }
  }
}"""


def valid_uuid(value):
    return isinstance(value, str) and UUID.fullmatch(value) is not None


def valid_time(value):
    if not isinstance(value, str) or not REV_RE.fullmatch(value):
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


def valid_text(value, limit):
    return isinstance(value, str) and 1 <= len(value.strip()) <= limit and "\x00" not in value


def issue_url_matches(value, workspace, issue_id, fragment=""):
    if not isinstance(value, str) or len(value) > 750:
        return False
    url = urlsplit(value)
    return (url.scheme == "https" and url.netloc == "linear.app" and not url.query
            and url.fragment == fragment
            and re.fullmatch(r"/" + re.escape(workspace) + "/issue/" + re.escape(issue_id)
                             + r"(?:/[A-Za-z0-9_-]+)?", url.path) is not None)


class LinearHistoryRead(LinearRead):
    def _read(self, query, issue_id):
        response = self.http.json(
            "POST", "https://api.linear.app/graphql",
            {"Authorization": self.key, "Content-Type": "application/json"},
            {"query": query, "variables": {"id": issue_id}})
        if (not isinstance(response, dict) or response.get("errors")
                or not isinstance(response.get("data"), dict)
                or not isinstance(response["data"].get("issue"), dict)):
            raise ValueError("Historical Linear read failed or was partial")
        return response["data"]["issue"]

    def history_issue(self, issue_id, *, selection, workspace):
        if selection["id"] != issue_id:
            raise ValueError("Historical preflight target differs")
        metadata = self._read(SCOPE_QUERY, issue_id)
        validate_membership(metadata, selection, workspace)
        item = self._read(DETAIL_QUERY, issue_id)
        if item.get("id") != metadata["id"]:
            raise ValueError("Historical issue identity changed after preflight")
        return item


def validate_membership(item, selection, workspace):
    if (not isinstance(item, dict) or not {"id", "identifier", "url", "team", "project"} <= set(item)
            or not valid_uuid(item["id"]) or item["identifier"] != selection["id"]
            or not isinstance(item["url"], str)):
        raise ValueError("Historical scope metadata incomplete")
    if not issue_url_matches(item["url"], workspace, selection["id"]):
        raise ValueError("Historical issue workspace or URL differs from selection")
    team, project = item["team"], item["project"]
    if (not isinstance(team, dict) or team.get("id") != selection["team_id"]
            or team.get("key") != selection["id"].split("-")[0]
            or (project is None and selection["project_id"] is not None)
            or (project is not None and (not isinstance(project, dict)
                                        or not valid_uuid(project.get("id"))
                                        or project.get("id") != selection["project_id"]))):
        raise ValueError("Historical issue team/project differs from explicit selection")


def normalize_discussion(item, selection, workspace):
    """Validate provider identity and explicit project mapping, not policy authority."""
    if (not isinstance(item, dict) or not {
            "id", "identifier", "url", "title", "description", "updatedAt", "team", "project", "state", "comments"
            } <= set(item) or not valid_uuid(item.get("id"))
            or item.get("identifier") != selection["id"]
            or not valid_text(item.get("title"), 1000)
            or item.get("description") is not None and not isinstance(item["description"], str)
            or not valid_time(item.get("updatedAt"))):
        raise ValueError("Historical issue identity, content or revision invalid")
    validate_membership(item, selection, workspace)
    team, project, state = item.get("team"), item.get("project"), item.get("state")
    if (not isinstance(state, dict) or not valid_uuid(state.get("id"))
            or not valid_text(state.get("name"), 120)
            or state.get("type") not in ("triage", "backlog", "unstarted", "started", "completed", "canceled")):
        raise ValueError("Historical workflow state missing or invalid")
    connection = item.get("comments")
    if (not isinstance(connection, dict) or not isinstance(connection.get("nodes"), list)
            or len(connection["nodes"]) > MAX_COMMENTS
            or not isinstance(connection.get("pageInfo"), dict)
            or connection["pageInfo"].get("hasNextPage") is not False
            or connection["pageInfo"].get("hasPreviousPage") is not False):
        raise ValueError("Historical comments incomplete or exceed bounded coverage")
    comments, seen = [], set()
    for comment in connection["nodes"]:
        if (not isinstance(comment, dict) or not {
                "id", "issueId", "parentId", "url", "body", "createdAt", "updatedAt", "user"
                } <= set(comment) or not valid_uuid(comment.get("id"))
                or comment["id"] in seen or comment.get("issueId") != item["id"]
                or not issue_url_matches(comment["url"], workspace, selection["id"], "comment-" + comment["id"])
                or not valid_text(comment.get("body"), MAX_DISCUSSION_BYTES)
                or not valid_time(comment.get("createdAt")) or not valid_time(comment.get("updatedAt"))
                or comment.get("parentId") is not None and not valid_uuid(comment["parentId"])
                or comment.get("user") is not None and (
                    not isinstance(comment["user"], dict) or not valid_uuid(comment["user"].get("id")))):
            raise ValueError("Historical comment identity, parent, content or author invalid")
        seen.add(comment["id"])
        comments.append({"id": comment["id"], "url": comment["url"], "parent_id": comment.get("parentId"),
                         "author_id": comment["user"]["id"] if comment.get("user") else None,
                         "created_at": comment["createdAt"], "updated_at": comment["updatedAt"],
                         "body": comment["body"]})
    validate_threads(comments)
    record = {"issue_uuid": item["id"], "identifier": item["identifier"],
              "url": item["url"], "title": item["title"], "description": item["description"] or "",
              "updated_at": item["updatedAt"], "team": {"id": team["id"], "key": team["key"]},
              "project": {"id": project["id"]} if project is not None else None,
              "state": {k: state[k] for k in ("id", "name", "type")}, "comments": comments}
    if len(canonical(record).encode()) > MAX_DISCUSSION_BYTES:
        raise ValueError("Historical discussion exceeds bounded size")
    return record


def validate_threads(comments):
    parents = {c["id"]: c["parent_id"] for c in comments}
    for cid in parents:
        visited, current = set(), cid
        while current is not None:
            if current not in parents or current in visited:
                raise ValueError("Historical comment parent missing or cyclic")
            visited.add(current)
            current = parents[current]


def context_from_record(record, focus):
    comments = []
    for comment in record["comments"]:
        text = comment["body"]
        excerpt = snippet(text, focus if focus.casefold() in text.casefold() else "", MAX_COMMENT_EXCERPT)
        comments.append({k: comment[k] for k in (
            "id", "url", "parent_id", "author_id", "created_at", "updated_at") } | {
                "excerpt": excerpt, "excerpt_sha256": digest(excerpt.encode()),
                "body_sha256": digest(text.encode()), "excerpt_truncated": excerpt != text,
                "citation_id": "L-C-" + comment["id"],
            })
    # Metadata is also untrusted source text and must pass the existing secret guard.
    snippet(record["state"]["name"], "")
    return {k: record[k] for k in ("issue_uuid", "team", "project", "state")} | {
        "comments_coverage": "COMPLETE_VISIBLE_AT_READ_TIME",
        "discussion_sha256": digest(canonical(record).encode()), "comments": comments,
    }


def validate_context(context, selection, workspace):
    if (not isinstance(context, dict) or set(context) != {
            "issue_uuid", "team", "project", "state", "comments_coverage", "discussion_sha256", "comments"}
            or not valid_uuid(context["issue_uuid"])
            or context["comments_coverage"] != "COMPLETE_VISIBLE_AT_READ_TIME"
            or not isinstance(context["discussion_sha256"], str)
            or not HEX64.fullmatch(context["discussion_sha256"])):
        raise ValueError("Historical details contract invalid")
    team, project, state = context["team"], context["project"], context["state"]
    if (team != {"id": selection["team_id"], "key": selection["id"].split("-")[0]}
            or project != ({"id": selection["project_id"]} if selection["project_id"] is not None else None)
            or not isinstance(state, dict) or set(state) != {"id", "name", "type"}
            or not valid_uuid(state["id"]) or not valid_text(state["name"], 120)
            or state["type"] not in ("triage", "backlog", "unstarted", "started", "completed", "canceled")):
        raise ValueError("Historical details mapping or state invalid")
    comments = context["comments"]
    if not isinstance(comments, list) or len(comments) > MAX_COMMENTS:
        raise ValueError("Historical details comments unbounded")
    seen = set()
    for comment in comments:
        if (not isinstance(comment, dict) or set(comment) != {
                "id", "url", "parent_id", "author_id", "created_at", "updated_at", "excerpt", "excerpt_sha256",
                "body_sha256", "excerpt_truncated", "citation_id"}
                or not valid_uuid(comment["id"]) or comment["id"] in seen
                or comment["citation_id"] != "L-C-" + comment["id"]
                or not issue_url_matches(comment["url"], workspace, selection["id"], "comment-" + comment["id"])
                or comment["parent_id"] is not None and not valid_uuid(comment["parent_id"])
                or comment["author_id"] is not None and not valid_uuid(comment["author_id"])
                or not valid_time(comment["created_at"]) or not valid_time(comment["updated_at"])
                or not valid_text(comment["excerpt"], MAX_COMMENT_EXCERPT)
                or comment["excerpt_sha256"] != digest(comment["excerpt"].encode())
                or not isinstance(comment["body_sha256"], str) or not HEX64.fullmatch(comment["body_sha256"])
                or type(comment["excerpt_truncated"]) is not bool
                or comment["excerpt_truncated"] is False and comment["body_sha256"] != comment["excerpt_sha256"]):
            raise ValueError("Historical comment excerpt provenance invalid")
        seen.add(comment["id"])
        snippet(comment["excerpt"], "")
    validate_threads(comments)
    snippet(state["name"], "")


def history_source_index(history):
    """Give comments individual provenance; a parent quote cannot stand in for one."""
    result = {}
    for source in history["historical_sources"]:
        if source["id"] in result:
            raise ValueError("Repeated historical source citation")
        result[source["id"]] = source
        for comment in source.get("history_context", {}).get("comments", []):
            cid = comment["citation_id"]
            if cid in result:
                raise ValueError("Historical comment reused across issue sources")
            result[cid] = {
                "id": cid, "provider": "linear", "source_kind": "HISTORICAL_COMMENT",
                "parent_source_id": source["id"], "source_issue_id": source["source_issue_id"],
                "url": comment["url"],
                "revision": comment["updated_at"], "scope": source["scope"],
                "authority": "HISTORICAL_UNVERIFIED", "excerpt": comment["excerpt"],
                "excerpt_sha256": comment["excerpt_sha256"],
            }
    return result


def prompt_source(source):
    result = {k: source[k] for k in ("id", "url", "revision", "authority", "project_mapping", "excerpt")}
    if "history_context" in source:
        result["history_context"] = source["history_context"]
    return result
