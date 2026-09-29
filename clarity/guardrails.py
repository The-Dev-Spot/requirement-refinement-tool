"""Deterministic checks over reported evidence and proposed publication plans.

These functions do not authenticate humans, run models, or call external services.
A future publisher must supply trusted policy, identity, current revisions and an
atomic idempotency store. Never let a model authorize its own publication.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit

DIMENSIONS = {f"D{i}" for i in range(1, 11)}
CHECKS = {f"L{i}" for i in range(1, 9)}
HARD_CHECKS = {"L1", "L2", "L3", "L5", "L7"}
STATES = {"PASS", "WARN", "FAIL", "NOT_RUN"}
ACTIONS = {"post_comment", "update_description", "update_acceptance_criteria", "create_issue", "publish_evidence"}
CONTENT_WRITES = {"update_description", "update_acceptance_criteria", "create_issue"}
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,99}\Z")
QUESTION = re.compile(r"^\s*# OPEN QUESTION -> PO:\s*(\S.*?)\s*$", re.MULTILINE)


class ValidationError(ValueError):
    """Invalid or unsafe local input; callers must fail closed."""


def identifier(value: str) -> str:
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise ValidationError("Invalid run identifier")
    return value


def canonical(value: Any) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValidationError("Value is not canonical JSON") from exc


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValidationError("Duplicate JSON key")
        result[key] = value
    return result


def load_json(path: Path) -> Any:
    def reject_constant(value: str) -> None:
        raise ValidationError("Non-finite JSON number")
    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique, parse_constant=reject_constant)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValidationError("Cannot read valid UTF-8 JSON") from exc


def load_config(path: Path) -> dict[str, Any]:
    cfg = load_json(path)
    expected = {"version", "project", "integration", "languages", "limits", "logbook"}
    if not isinstance(cfg, dict) or set(cfg) != expected or type(cfg["version"]) is not int or cfg["version"] != 1:
        raise ValidationError("Unsupported or incomplete configuration")
    if not isinstance(cfg["project"], str) or not cfg["project"].strip():
        raise ValidationError("Project name is required")
    integration = cfg["integration"]
    if not isinstance(integration, dict) or set(integration) != {"provider", "base_url", "project_key", "writes_enabled"}:
        raise ValidationError("Invalid integration configuration")
    if not isinstance(integration["provider"], str) or integration["provider"] not in {"local", "jira", "linear", "github"}:
        raise ValidationError("Unknown integration provider")
    # No live writer ships in this version. Even true-looking strings are rejected.
    if integration["writes_enabled"] is not False:
        raise ValidationError("Live writes are not implemented; writes_enabled must be false")
    key = integration["project_key"]
    if key is not None:
        identifier(key)
    url = integration["base_url"]
    if url is not None:
        if not isinstance(url, str):
            raise ValidationError("Invalid base URL")
        parsed = urlsplit(url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValidationError("Base URL must be HTTPS without credentials, query or fragment")
    languages = cfg["languages"]
    if not isinstance(languages, dict) or set(languages) != {"conversation", "artifacts"} or not all(isinstance(v, str) and re.fullmatch(r"[a-z]{2}(?:-[A-Z]{2})?", v) for v in languages.values()):
        raise ValidationError("Invalid language settings")
    limits = cfg["limits"]
    bounds = {"rewrite_iterations": (1, 3), "creator_questions": (1, 10), "retrieved_documents": (1, 100), "retrieved_characters": (1000, 1000000)}
    if not isinstance(limits, dict) or set(limits) != set(bounds):
        raise ValidationError("Invalid limits")
    for name, (low, high) in bounds.items():
        if type(limits[name]) is not int or not low <= limits[name] <= high:
            raise ValidationError("Limit outside allowed range: " + name)
    logbook = cfg["logbook"]
    if not isinstance(logbook, dict) or set(logbook) != {"inline_sections"}:
        raise ValidationError("Invalid logbook configuration")
    sections = logbook["inline_sections"]
    allowed = {"run-summary", "rewrite", "proposed-comment", "eval-report", "quality-gates", "investigation", "po-analysis", "po-challenge", "po-responses"}
    if not isinstance(sections, list) or not sections or any(not isinstance(s, str) or s not in allowed for s in sections) or len(sections) != len(set(sections)) or "run-summary" not in sections:
        raise ValidationError("Invalid inline sections; run-summary is required")
    return cfg


def open_questions(*texts: str) -> list[str]:
    """Deduplicate exact questions across artifacts, preserving first occurrence.

This does not perform semantic deduplication. Malformed markers are rejected,
not silently interpreted as zero questions. Use stable question IDs in records.
"""
    found: dict[str, str] = {}
    for text in texts:
        for line in text.splitlines():
            if "OPEN QUESTION" in line.upper():
                match = QUESTION.fullmatch(line)
                if not match:
                    raise ValidationError("Malformed open-question marker")
                question = " ".join(match.group(1).split())
                found.setdefault(question.casefold(), question)
    return list(found.values())


def readiness(report: Mapping[str, Any]) -> dict[str, Any]:
    expected = {"dimensions", "checks", "open_questions", "unconfirmed_proposals", "interface_touched", "regulated", "injection_detected"}
    if not isinstance(report, dict) or set(report) != expected:
        raise ValidationError("Incomplete or unknown report fields")
    for key, required in (("dimensions", DIMENSIONS), ("checks", CHECKS)):
        values = report[key]
        if not isinstance(values, dict) or set(values) != required or any(not isinstance(v, str) or v not in STATES for v in values.values()):
            raise ValidationError("Incomplete or invalid " + key)
    for name in ("open_questions", "unconfirmed_proposals"):
        if not isinstance(report[name], list) or any(not isinstance(q, str) or not q.strip() for q in report[name]):
            raise ValidationError("Invalid " + name)
    for name in ("interface_touched", "regulated", "injection_detected"):
        if type(report[name]) is not bool:
            raise ValidationError("Boolean required: " + name)
    hard = {"D1", "D2", "D3", "D4", "D5", "D6"}
    if report["interface_touched"]:
        hard.add("D9")
    if report["regulated"]:
        hard.add("D10")
    blockers = [d for d in sorted(hard) if report["dimensions"][d] == "FAIL"]
    blockers += [c for c in sorted(HARD_CHECKS) if report["checks"][c] == "FAIL"]
    if report["injection_detected"]:
        blockers.append("suspected prompt injection requires review")
    incomplete = any(v == "NOT_RUN" for group in ("dimensions", "checks") for v in report[group].values())
    warnings = any(v != "PASS" for group in ("dimensions", "checks") for v in report[group].values())
    gate = "FAIL" if blockers else "WARN" if warnings or report["open_questions"] or report["unconfirmed_proposals"] else "PASS"
    return {"gate": gate, "verdict": "READY" if gate == "PASS" else "NOT READY", "incomplete": incomplete, "blockers": blockers, "report_digest": digest(report)}


@dataclass(frozen=True)
class Approval:
    approval_id: str
    run_id: str
    actor: str
    plan_digest: str
    actions: frozenset[str]
    issued_at: float
    expires_at: float


def authorize_plan(plan: dict[str, Any], report: dict[str, Any], approval: Approval | None, *, current_revision: str, now: float, allowed_actions: frozenset[str] = frozenset(), consumed_approvals: frozenset[str] = frozenset(), max_ttl: int = 900) -> tuple[str, ...]:
    """Validate a plan without sending it. Default policy allows NO actions.

Identity, approval creation, policy and replay state must be provided by a trusted
application. An approval JSON file written by an agent is NOT that boundary.
Atomic claim/execute/reconcile and actual adapters remain future work.
"""
    expected = {"run_id", "mode", "target", "source_revision", "report_digest", "actions", "payload"}
    if not isinstance(plan, dict) or set(plan) != expected:
        raise ValidationError("Invalid publication plan")
    identifier(plan["run_id"])
    if not isinstance(plan["mode"], str) or plan["mode"] not in {"review", "apply", "intake"}:
        raise ValidationError("Invalid run mode")
    if not isinstance(plan["target"], str) or not plan["target"].strip() or not isinstance(plan["payload"], dict) or not plan["payload"]:
        raise ValidationError("Target and payload are required")
    actions = plan["actions"]
    if not isinstance(actions, list) or not actions or any(not isinstance(a, str) or a not in ACTIONS for a in actions) or len(set(actions)) != len(actions):
        raise ValidationError("Invalid action list")
    if not set(actions) <= allowed_actions:
        raise ValidationError("Action is not allowed by publisher policy")
    if plan["mode"] == "intake" and set(actions) - {"create_issue", "publish_evidence"}:
        raise ValidationError("Intake cannot mutate an existing issue")
    if plan["mode"] != "intake" and "create_issue" in actions:
        raise ValidationError("Only intake may create an issue")
    if not isinstance(plan["source_revision"], str) or not plan["source_revision"] or current_revision != plan["source_revision"]:
        raise ValidationError("Source changed; re-review and re-approve")
    result = readiness(report)
    if plan["report_digest"] != result["report_digest"]:
        raise ValidationError("Evaluation changed; re-approve")
    if result["verdict"] != "READY" and CONTENT_WRITES.intersection(actions):
        raise ValidationError("NOT READY content cannot be published as requirements")
    if report["injection_detected"]:
        raise ValidationError("Quarantined evidence cannot be published")
    if not isinstance(approval, Approval):
        raise ValidationError("Explicit trusted approval required")
    identifier(approval.approval_id)
    if not isinstance(approval.actor, str) or not approval.actor.strip():
        raise ValidationError("Approver identity required")
    if approval.approval_id in consumed_approvals:
        raise ValidationError("Approval already consumed")
    if approval.run_id != plan["run_id"] or approval.plan_digest != digest(plan) or approval.actions != frozenset(actions):
        raise ValidationError("Approval does not match the exact plan")
    times = (approval.issued_at, approval.expires_at, now)
    if any(type(t) not in (int, float) or not math.isfinite(t) for t in times) or type(max_ttl) is not int or max_ttl <= 0:
        raise ValidationError("Invalid approval timestamps or policy")
    if not approval.issued_at <= now < approval.expires_at or not 0 < approval.expires_at - approval.issued_at <= max_ttl:
        raise ValidationError("Approval expired, future-dated or overlong")
    return tuple(actions)
