"""Versioned synthetic rule fixtures; this does NOT measure model accuracy."""
from __future__ import annotations

import copy

from .guardrails import ValidationError, open_questions
from .lint import check
from .models import document, fields


def run(suite: dict) -> dict:
    fields(suite, {"version", "label_source", "base", "cases"}, "benchmark")
    if suite["version"] != 1 or not isinstance(suite["cases"], list) or not suite["cases"]:
        raise ValidationError("Invalid benchmark suite")
    base = document(suite["base"])
    results = []
    ids = set()
    for case in suite["cases"]:
        fields(case, {"id", "patch", "expected_flags"}, "benchmark case")
        if case["id"] in ids or not isinstance(case["patch"], dict):
            raise ValidationError("Duplicate or malformed benchmark case")
        ids.add(case["id"])
        value = copy.deepcopy(base)
        value.update(case["patch"])
        checked = check(value)
        flags = {key for key, record in checked["checks"].items() if record["status"] != "PASS"}
        if checked["injection_flags"]:
            flags.add("INJECTION")
        try:
            if value["questions"] or open_questions(value["description"], value["acceptance_criteria"]):
                flags.add("QUESTION")
        except ValidationError:
            flags.add("QUESTION")
        if value["proposals"] or any(e["status"] != "confirmed" for e in value["evidence"]):
            flags.add("EVIDENCE")
        if value["investigation"]["conflicts"] or value["investigation"]["missing"]:
            flags.add("INVESTIGATION")
        expected = set(case["expected_flags"])
        results.append({"id": case["id"], "passed": flags == expected, "missed_flags": sorted(expected-flags), "unexpected_flags": sorted(flags-expected)})
    return {"cases": results, "passed": sum(r["passed"] for r in results), "total": len(results), "semantic_accuracy_measured": False, "label_source": suite["label_source"]}
