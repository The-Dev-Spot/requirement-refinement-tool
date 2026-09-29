"""Executable L1-L8 checks. Heuristics are not proof of semantic correctness."""
from __future__ import annotations

import re
import unicodedata

from .guardrails import ValidationError, open_questions
from .models import document

LINT_VERSION = "1.0.0"
VAGUE = re.compile(r"\b(?:quickly|fast|user.friendly|seamless|as appropriate|etc\.?|reasonable|adequate|efficient)\b", re.I)
UI = re.compile(r"\b(?:click|tap|press|navigate to|select from the dropdown)\b", re.I)
SUSPICIOUS = re.compile(r"(?:ignore\s+(?:all\s+)?(?:previous|prior)\s+instructions|(?:reveal|print|send)\s+(?:the\s+)?(?:secret|api.?key|password|token)|(?:bypass|disable)\s+(?:the\s+)?(?:approval|guardrail|safety)|system\s*:\s*you\s+are)", re.I)
TAG = re.compile(r"@(risk|type|scope):[A-Za-z0-9_-]+\Z")


def injection_flags(snapshot: dict) -> list[str]:
    """Return locations, never raw potentially sensitive matching snippets."""
    fields = {}
    def collect(value, location="snapshot"):
        if isinstance(value, str):
            fields[location] = value
        elif isinstance(value, dict):
            for key, part in value.items():
                collect(part, location + "." + key)
        elif isinstance(value, list):
            for index, part in enumerate(value):
                collect(part, location + "[" + str(index) + "]")
    collect(snapshot)
    flags = []
    for location, body in fields.items():
        normalized = unicodedata.normalize("NFKC", body)
        normalized = "".join(c for c in normalized if unicodedata.category(c) != "Cf")
        if SUSPICIOUS.search(normalized):
            flags.append(location)
    return flags


def _walk(node):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from _walk(value)


def check(value: dict) -> dict:
    snapshot = document(value)
    checks = {f"L{i}": {"status": "PASS", "findings": []} for i in range(1, 9)}

    def flag(rule, status, message):
        rank = {"PASS": 0, "WARN": 1, "NOT_RUN": 2, "FAIL": 3}
        if rank[status] > rank[checks[rule]["status"]]:
            checks[rule]["status"] = status
        checks[rule]["findings"].append(message)

    ac = snapshot["acceptance_criteria"]
    steps = []
    tags = []
    if snapshot["kind"] == "behavioral":
        try:
            from gherkin import Parser, Compiler
        except ImportError:
            flag("L1", "NOT_RUN", "Install the pinned gherkin-official dependency")
        else:
            try:
                ast = Parser().parse(ac)
                ast["uri"] = "acceptance.feature"
                pickles = Compiler().compile(ast)
                if not ast.get("feature") or not pickles:
                    flag("L1", "FAIL", "At least one executable scenario is required")
                for scenario in pickles:
                    if not scenario.get("steps"):
                        flag("L1", "FAIL", "Empty scenario")
                for node in _walk(ast.get("feature", {})):
                    if "keywordType" in node:
                        steps.append(node["text"])
                    tags.extend(t["name"] for t in node.get("tags", []))
                # Gherkin grammar permits unusual ordering. Narrative/result
                # completeness is a project rule, not a claim about the grammar.
                for node in _walk(ast.get("feature", {})):
                    if node.get("keyword") == "Scenario Outline" and not any(e.get("tableBody") for e in node.get("examples", [])):
                        flag("L1", "FAIL", "Each outline needs at least one example row")
                    if node.get("keyword") in {"Scenario", "Scenario Outline"}:
                        if not any(s.get("keywordType") == "Outcome" for s in node.get("steps", [])):
                            flag("L1", "FAIL", "Each scenario needs an observable Then outcome")
                if ast.get("feature", {}).get("language", "en") != "en":
                    flag("L3", "NOT_RUN", "Vagueness vocabulary currently covers English only")
                    flag("L4", "NOT_RUN", "Style vocabulary currently covers English only")
            except Exception as exc:
                # Parser messages may include private source text: only return type.
                flag("L1", "FAIL", "Gherkin parse/compile failed: " + type(exc).__name__)
        if checks["L1"]["status"] in {"FAIL", "NOT_RUN"}:
            for rule in ("L2", "L3", "L4", "L5", "L8"):
                flag(rule, "NOT_RUN", "No valid acceptance syntax tree")
    else:
        items = []
        for line in ac.splitlines():
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            if line.lstrip().startswith("@"):
                tags.extend(line.split())
                continue
            match = re.fullmatch(r"\s*- \[[ xX]\] (.+?) \| Verify: (\S.+)\s*", line)
            if not match:
                flag("L1", "FAIL", "Checklist items require '- [ ] outcome | Verify: evidence/test'")
            else:
                items.append(match.group(1))
        steps = items
        if not items:
            flag("L1", "FAIL", "Checklist contains no verifiable outcomes")
    for tag in tags:
        if not TAG.fullmatch(tag):
            flag("L2", "FAIL", "Unknown or malformed tag namespace")
        if tag.startswith("@risk:") and tag[6:] not in snapshot["risk_ids"]:
            flag("L5", "FAIL", "Risk tag does not resolve to selected register")
    for index, step in enumerate(steps, 1):
        if VAGUE.search(step):
            flag("L3", "FAIL", f"Unquantified acceptance vocabulary in item {index}")
        if UI.search(step):
            flag("L4", "WARN", f"UI choreography in item {index}; check observable behavior")
        if snapshot["canonical_steps"] and step not in snapshot["canonical_steps"]:
            flag("L8", "WARN", f"Item {index} is not in the selected step catalog")
    if not snapshot["evidence"]:
        flag("L6", "WARN", "No structured source provenance supplied")
    try:
        open_questions(snapshot["description"], ac)
    except ValidationError:
        flag("L7", "FAIL", "Malformed open-question marker")
    return {"version": LINT_VERSION, "checks": checks, "injection_flags": injection_flags(snapshot), "limitations": "Grammar, syntax and lexical checks only; semantic truth and authority require independent review."}
