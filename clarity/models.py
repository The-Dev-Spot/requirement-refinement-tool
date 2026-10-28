"""Versioned standalone input contracts. Reject unknown fields and silent coercion."""
from __future__ import annotations

import re
from datetime import date
from typing import Any

from .guardrails import DIMENSIONS, STATES, ValidationError, canonical, identifier

MAX_INPUT_BYTES = 1_000_000


def fields(value: Any, names: set[str], label: str) -> dict:
    if not isinstance(value, dict) or set(value) != names:
        raise ValidationError("Invalid fields: " + label)
    return value


def text(value: Any, label: str, *, empty: bool = False) -> str:
    if not isinstance(value, str) or (not empty and not value.strip()) or "\x00" in value:
        raise ValidationError("Invalid text: " + label)
    return value


def strings(value: Any, label: str) -> list[str]:
    if not isinstance(value, list):
        raise ValidationError("Expected list: " + label)
    for item in value:
        text(item, label)
    if len(value) != len(set(value)):
        raise ValidationError("Duplicate entries: " + label)
    return value


def document(value: Any) -> dict:
    """Return a detached canonical snapshot, never a mutable caller reference."""
    import json
    names = {"schema_version", "project", "title", "kind", "description", "acceptance_criteria", "source", "evidence", "investigation", "questions", "acknowledged_answers", "proposals", "risk_ids", "canonical_steps", "interface_touched", "regulated"}
    fields(value, names, "requirement")
    if type(value["schema_version"]) is not int or value["schema_version"] != 1:
        raise ValidationError("Unsupported document version")
    if len(canonical(value).encode()) > MAX_INPUT_BYTES:
        raise ValidationError("Document exceeds size limit")
    for name in ("project", "title", "description", "acceptance_criteria"):
        text(value[name], name)
    identifier(value["project"])
    if value["kind"] not in ("behavioral", "checklist"):
        raise ValidationError("Explicit behavioral or checklist kind required")
    for flag in ("interface_touched", "regulated"):
        if type(value[flag]) is not bool:
            raise ValidationError("Expected boolean: " + flag)
    source = fields(value["source"], {"id", "revision", "text", "locator"}, "source")
    for name, item in source.items():
        text(item, "source " + name)
    investigation = fields(value["investigation"], {"summary", "conflicts", "missing"}, "investigation")
    text(investigation["summary"], "investigation summary")
    strings(investigation["conflicts"], "conflicts")
    strings(investigation["missing"], "missing")
    if not isinstance(value["evidence"], list) or len(value["evidence"]) > 100:
        raise ValidationError("Invalid evidence list")
    ids = {"requirement", "source"}
    for item in value["evidence"]:
        fields(item, {"id", "title", "section", "source_date", "locator", "quote", "status"}, "evidence")
        for name, part in item.items():
            text(part, "evidence " + name)
        identifier(item["id"])
        if item["id"] in ids:
            raise ValidationError("Duplicate or reserved evidence ID")
        ids.add(item["id"])
        try:
            date.fromisoformat(item["source_date"])
        except ValueError as exc:
            raise ValidationError("Evidence needs original source date") from exc
        if item["status"] not in {"confirmed", "inferred", "proposed", "contradicted", "unknown"}:
            raise ValidationError("Invalid evidence status")
    if not isinstance(value["questions"], list):
        raise ValidationError("Questions must be a list")
    questions = set()
    for item in value["questions"]:
        fields(item, {"id", "text"}, "question")
        identifier(item["id"])
        text(item["text"], "question")
        if item["id"] in questions:
            raise ValidationError("Duplicate question ID")
        questions.add(item["id"])
    for name in ("acknowledged_answers", "proposals", "risk_ids", "canonical_steps"):
        strings(value[name], name)
    for risk in value["risk_ids"]:
        if not re.fullmatch(r"RISK-[0-9]{3,}", risk):
            raise ValidationError("Invalid risk ID")
    return json.loads(canonical(value))


def assessment(value: Any, snapshot: dict, expected_digest: str) -> dict:
    """Semantic assessments remain a reviewer's responsibility, not lint truth."""
    import json
    fields(value, {"revision_digest", "dimensions"}, "assessment")
    if value["revision_digest"] != expected_digest:
        raise ValidationError("Review is for a stale snapshot")
    fields(value["dimensions"], DIMENSIONS, "dimension assessment")
    refs = {"source", "requirement"} | {item["id"] for item in snapshot["evidence"]}
    for item in value["dimensions"].values():
        fields(item, {"status", "rationale", "evidence_ids"}, "dimension")
        if not isinstance(item["status"], str) or item["status"] not in STATES:
            raise ValidationError("Invalid dimension status")
        text(item["rationale"], "review rationale")
        if len(item["rationale"].strip()) < 12:
            raise ValidationError("Dimension rationale is too short")
        cited = strings(item["evidence_ids"], "review evidence IDs")
        if not cited or not set(cited) <= refs:
            raise ValidationError("Unknown or absent review evidence reference")
    return json.loads(canonical(value))
