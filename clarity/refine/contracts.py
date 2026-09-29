"""Strict product contracts. Raw briefs are permissive; approved handoffs are not."""
from __future__ import annotations

import json
import re
from typing import Any

from ..guardrails import ValidationError, canonical, digest, identifier

CATEGORIES = ("positive", "negative", "boundary", "alternative")
KINDS = {"problem", "value", "scope", "exclusion", "definition", "rule", "constraint", "dependency"}
REQUIRED_KINDS = {"problem", "value", "scope", "exclusion", "rule"}
SEMANTIC_CHECKS = ("intent_preserved", "cold_read", "precise_rules", "no_invention", "appropriate_scope", "test_coverage", "observable_outcomes", "applicability", "dependencies", "nonfunctional_requirements")
MAX_BYTES = 1_000_000


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def fields(value: Any, names: set[str], label: str) -> dict:
    require(isinstance(value, dict) and set(value) == names, "Invalid fields: " + label)
    return value


def text(value: Any, label: str, limit: int = 50000) -> str:
    require(isinstance(value, str) and bool(value.strip()) and len(value) <= limit and not any(ord(c) < 32 and c not in '\n\r\t' for c in value), "Invalid text: " + label)
    return value


def items(value: Any, label: str, limit: int = 200) -> list:
    require(isinstance(value, list) and len(value) <= limit, "Invalid list: " + label)
    return value


def names(value: Any, label: str) -> list[str]:
    items(value, label)
    for v in value:
        identifier(v)
    require(len(value) == len(set(value)), "Duplicate " + label)
    return value


def detached(value: Any) -> Any:
    encoded = canonical(value)
    require(len(encoded.encode()) <= MAX_BYTES, "Input exceeds size limit")
    return json.loads(encoded)


def policy(value: Any) -> dict:
    fields(value, {"version", "risk_ids", "canonical_steps", "max_rewrites", "max_model_calls"}, "policy")
    require(type(value["version"]) is int and value["version"] == 1, "Unsupported policy schema")
    names(value["risk_ids"], "risk IDs")
    for step in items(value["canonical_steps"], "canonical steps"):
        text(step, "canonical step", 2000)
    require(type(value["max_rewrites"]) is int and 1 <= value["max_rewrites"] <= 3, "Invalid rewrite budget")
    require(type(value["max_model_calls"]) is int and 1 <= value["max_model_calls"] <= 12, "Invalid model-call budget")
    return detached(value)


DEFAULT_POLICY = {"version": 1, "risk_ids": [], "canonical_steps": [], "max_rewrites": 3, "max_model_calls": 6}


def draft(value: Any) -> dict:
    value = detached(value)
    fields(value, {"version", "title", "statements", "feature", "scenarios", "coverage", "proposals"}, "draft")
    require(type(value["version"]) is int and value["version"] == 1, "Unsupported draft schema")
    text(value["title"], "title", 300)
    require('\n' not in value["title"] and '\r' not in value["title"], "Title must be one line")
    text(value["feature"], "feature", 100000)
    seen = set()
    for s in items(value["statements"], "statements"):
        fields(s, {"id", "kind", "text", "citations"}, "statement")
        identifier(s["id"])
        require(s["id"] not in seen and isinstance(s["kind"], str) and s["kind"] in KINDS, "Duplicate statement or invalid kind")
        seen.add(s["id"])
        text(s["text"], "statement", 5000)
        for c in items(s["citations"], "citations", 20):
            fields(c, {"source_id", "source_digest", "quote"}, "citation")
            identifier(c["source_id"])
            require(isinstance(c["source_digest"], str) and re.fullmatch(r"[a-f0-9]{64}", c["source_digest"]), "Invalid source digest")
            text(c["quote"], "quote", 50000)
    seen = set()
    for s in items(value["scenarios"], "scenarios"):
        fields(s, {"id", "statement_ids", "category"}, "scenario mapping")
        identifier(s["id"])
        require(s["id"] not in seen and isinstance(s["category"], str) and s["category"] in CATEGORIES, "Duplicate scenario or invalid category")
        seen.add(s["id"])
        names(s["statement_ids"], "scenario statement IDs")
    coverage_keys = set()
    for c in items(value["coverage"], "coverage", 800):
        fields(c, {"statement_id", "category", "scenario_ids", "not_applicable_reason"}, "coverage")
        identifier(c["statement_id"])
        require(isinstance(c["category"], str) and c["category"] in CATEGORIES, "Invalid coverage category")
        key = (c["statement_id"], c["category"])
        require(key not in coverage_keys, "Duplicate coverage row")
        coverage_keys.add(key)
        names(c["scenario_ids"], "coverage scenarios")
        if c["not_applicable_reason"] is not None:
            require(not c["scenario_ids"], "Coverage cannot be both covered and inapplicable")
            require(len(text(c["not_applicable_reason"], "applicability reason", 2000).strip()) >= 20, "Explain why this category is inapplicable")
    for proposal in items(value["proposals"], "proposals"):
        text(proposal, "proposal", 5000)
    return value


def review(value: Any, current: dict, expected_digest: str) -> dict:
    value = detached(value)
    fields(value, {"draft_digest", "checks", "statement_support", "scenario_fidelity", "warning_resolutions", "ambiguities"}, "review")
    require(value["draft_digest"] == expected_digest, "Review is for a stale draft")
    fields(value["checks"], set(SEMANTIC_CHECKS), "semantic checks")
    for check in value["checks"].values():
        fields(check, {"status", "rationale"}, "semantic check")
        require(isinstance(check["status"], str) and check["status"] in {"PASS", "FAIL", "NOT_RUN"}, "Invalid review status")
        require(len(text(check["rationale"], "review rationale", 4000).strip()) >= 20, "Review needs a substantive rationale")
    for field, expected in (("statement_support", {s["id"] for s in current["statements"]}), ("scenario_fidelity", {s["id"] for s in current["scenarios"]})):
        fields(value[field], expected, field)
        for result in value[field].values():
            fields(result, {"status", "rationale"}, field + " item")
            require(isinstance(result["status"], str) and result["status"] in {"PASS", "FAIL", "NOT_RUN"}, "Invalid support status")
            require(len(text(result["rationale"], "support rationale", 4000).strip()) >= 20, "Explain support and intent, not just citation existence")
    require(isinstance(value["warning_resolutions"], dict), "Warning resolutions must be an object")
    for finding_id, reason in value["warning_resolutions"].items():
        identifier(finding_id)
        require(len(text(reason, "warning rationale", 2000).strip()) >= 20, "Explain the context-sensitive finding")
    for ambiguity in items(value["ambiguities"], "ambiguities"):
        fields(ambiguity, {"statement_ids", "interpretation_a", "interpretation_b", "material_difference"}, "ambiguity")
        names(ambiguity["statement_ids"], "ambiguity statements")
        require(bool(ambiguity["statement_ids"]) and set(ambiguity["statement_ids"]) <= {s["id"] for s in current["statements"]}, "Ambiguity must identify real statements")
        for name in ("interpretation_a", "interpretation_b", "material_difference"):
            text(ambiguity[name], name, 4000)
    return value


def source_record(source_id: str, title: str, body: str, locator: str, kind: str, authority: str | None) -> dict:
    identifier(source_id)
    text(title, "source title", 300)
    text(body, "source text", 100000)
    text(locator, "source locator", 2000)
    require(kind in {"request", "reference", "decision"}, "Invalid source kind")
    value = {"id": source_id, "title": title, "text": body, "locator": locator, "kind": kind, "authority": authority}
    return {**value, "digest": digest(value)}
