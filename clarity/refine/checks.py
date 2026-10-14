"""Deterministic handoff checks. A verified quotation is not proof of entailment."""
from __future__ import annotations

import re
import unicodedata
from typing import Any

from ..guardrails import digest
from ..audit import SECRETS
from .contracts import CATEGORIES, REQUIRED_KINDS, draft, require

SUSPICIOUS = re.compile(r"ignore\s+(?:all\s+)?(?:previous|prior)\s+instructions|(?:reveal|print|send)\s+(?:the\s+)?(?:secret|api.?key|password|token)|(?:bypass|disable)\s+(?:the\s+)?(?:approval|guardrail|safety)|system\s*:\s*you\s+are", re.I)
VAGUE = re.compile(r"\b(?:quickly|fast|successfully|user.friendly|seamless|as appropriate|etc|reasonable|adequate|efficient)\b", re.I)
UI = re.compile(r"\b(?:click|tap|press|navigate to|select from the dropdown)\b", re.I)
CASE_TAG = re.compile(r"@case_([A-Za-z0-9][A-Za-z0-9_-]{0,99})\Z")
SAFE_TAG = re.compile(r"@(?:case|risk|type|scope)_[A-Za-z0-9][A-Za-z0-9_-]{0,99}\Z")


def feature_index(feature: str) -> dict:
    """Parse and compile with the official parser; never substitute a regex parser.

Keyword-type checks are handoff policy, not statements about Gherkin grammar.
Scenario aliases, Rules, Backgrounds and example rows retain their original text.
"""
    from gherkin import Parser, Compiler
    ast = Parser().parse(feature)
    root = ast.get("feature")
    require(bool(root), "Feature is missing")
    scenarios, tags, rows = [], [], 0

    def walk(children, inherited_steps=()):
        nonlocal rows
        background = list(inherited_steps)
        for child in children:
            if "background" in child:
                background += child["background"]["steps"]
            elif "rule" in child:
                rule = child["rule"]
                tags.extend(t["name"] for t in rule.get("tags", []))
                walk(rule["children"], background)
            elif "scenario" in child:
                node = child["scenario"]
                own_tags = [t["name"] for t in node.get("tags", [])]
                tags.extend(own_tags)
                case_ids = [m.group(1) for tag in own_tags if (m := CASE_TAG.fullmatch(tag))]
                require(len(case_ids) == 1, "Each scenario needs exactly one direct @case_ID tag")
                require(bool(node["name"].strip()) and bool(node["steps"]), "Scenarios need names and steps")
                steps = background + node["steps"]
                kinds = {s.get("keywordType") for s in steps}
                require({"Context", "Action", "Outcome"} <= kinds, "Each scenario needs context, action and observable outcome")
                examples = node.get("examples", [])
                # An outline with no Examples has no compiled case; verify that below.
                for example in examples:
                    # Resolve template parameters in every argument, including tables
                    # and Doc Strings. Markup in ordinary scenarios remains literal.
                    parameters = set(re.findall(r'<([A-Za-z_][A-Za-z0-9_]*)>', node['name']))
                    for step in steps:
                        parameters.update(re.findall(r'<([A-Za-z_][A-Za-z0-9_]*)>', step['text']))
                    tags.extend(t["name"] for t in example.get("tags", []))
                    header = [c["value"] for c in example.get("tableHeader", {}).get("cells", [])]
                    require(bool(header) and len(set(header)) == len(header) and all(header), "Example headers must be unique and nonempty")
                    for step in steps:
                        argument_texts = []
                        if 'docString' in step:
                            argument_texts.append(step['docString']['content'])
                        if 'dataTable' in step:
                            argument_texts.extend(c['value'] for row in step['dataTable']['rows'] for c in row['cells'])
                        # Only parameter-looking tokens not used as markup are
                        # treated as templates. Attribute/closing tags stay literal.
                        for argument in argument_texts:
                            parameters.update(m.group(1) for m in re.finditer(r'<([A-Za-z_][A-Za-z0-9_]*)>', argument)
                                              if '</' + m.group(1) + '>' not in argument)
                    require(parameters <= set(header), 'Outline argument references a missing Examples column')
                    body = example.get("tableBody", [])
                    require(bool(body), "An Examples table needs data rows")
                    for row in body:
                        require(len(row["cells"]) == len(header) and all(c["value"].strip() for c in row["cells"]), "Example cells cannot be missing or empty")
                    rows += len(body)
                scenarios.append({"id": case_ids[0], "ast_id": node["id"], "name": node["name"], "line": node["location"]["line"], "steps": [s["text"] for s in steps]})

    tags.extend(t["name"] for t in root.get("tags", []))
    walk(root["children"])
    require(bool(scenarios) and len(scenarios) <= 200 and rows <= 500, "Feature has no scenarios or exceeds scenario/example limits")
    require(len({s["id"] for s in scenarios}) == len(scenarios), "Duplicate stable scenario ID")
    require(len({s["name"] for s in scenarios}) == len(scenarios), "Duplicate scenario name")
    ast["uri"] = "acceptance.feature"
    compiled = Compiler().compile(ast)
    require(bool(compiled) and len(compiled) <= 500, "Feature has no executable cases or too many examples")
    represented = {aid for case in compiled for aid in case.get("astNodeIds", [])}
    require(all(s["ast_id"] in represented for s in scenarios), "Every scenario/outline needs at least one executable case")
    for case in compiled:
        for step in case["steps"]:
            # Only unresolved outline parameters are rejected; literal comparisons
            # such as amount < limit do not match this placeholder form.
            require(not re.search(r"<[A-Za-z_][A-Za-z0-9_]*>", step["text"]), "Unresolved example placeholder")
    return {"language": root.get("language", "en"), "scenarios": scenarios, "tags": tags, "compiled_cases": len(compiled), "examples": [{"name": c["name"], "scenario_ids": [s["id"] for s in scenarios if s["ast_id"] in c.get("astNodeIds", [])], "steps": [step["text"] for step in c["steps"]]} for c in compiled]}


def signals(value: Any, scope: str = "input") -> list[dict]:
    found = []
    if isinstance(value, str):
        normalized = unicodedata.normalize("NFKC", value)
        normalized = ''.join(c for c in normalized if unicodedata.category(c) != 'Cf')
        if SUSPICIOUS.search(normalized):
            found.append({"id": "F-" + digest({"scope": scope, "text": value})[:24], "code": "instruction_signal", "severity": "security", "scope": scope, "message": "Review possible embedded instructions; wording alone does not establish an attack."})
    elif isinstance(value, dict):
        for key, item in value.items():
            found += signals(item, scope + "." + key)
    elif isinstance(value, list):
        for i, item in enumerate(value):
            found += signals(item, scope + "." + str(i))
    return found


def check(value: dict, sources: dict[str, dict], selected_policy: dict) -> dict:
    value = draft(value)
    findings = []

    def flag(code: str, scope: str, message: str, severity: str = "blocker"):
        findings.append({"id": "F-" + digest({"code": code, "scope": scope, "draft": digest(value)})[:24], "code": code, "severity": severity, "scope": scope, "message": message})

    statements = {s["id"]: s for s in value["statements"]}
    for kind in sorted(REQUIRED_KINDS - {s["kind"] for s in statements.values()}):
        flag("missing_section", kind, "Missing an evidence-backed " + kind + " statement")
    for statement in statements.values():
        sid = statement["id"]
        if not statement["citations"]:
            flag("unsupported_statement", sid, "Every statement requires an exact supporting source passage")
        seen = set()
        for citation in statement["citations"]:
            fingerprint = digest(citation)
            source = sources.get(citation["source_id"])
            if fingerprint in seen:
                flag("duplicate_citation", sid, "Duplicate supporting passage")
            seen.add(fingerprint)
            if source is None or source["digest"] != citation["source_digest"]:
                flag("stale_or_missing_source", sid, "Source identity/revision does not match captured evidence")
            elif citation["quote"] not in source["text"]:
                flag("fabricated_quote", sid, "Quoted passage is not present verbatim in the captured source")
            elif source["kind"] == "reference" and not source["authority"]:
                flag("unconfirmed_authority", sid, "Reference applicability requires a recorded operator decision")
    definitions = ' '.join(s['text'] for s in statements.values() if s['kind'] == 'definition').casefold()
    numeric_rules = {}
    for statement in statements.values():
        if statement['kind'] not in {'rule', 'constraint'}: continue
        body, sid = statement['text'], statement['id']
        for match in re.finditer(r'\b(?:within|after|for)\s+(\d+(?:\.\d+)?)\b\s*([A-Za-z%]*)', body, re.I):
            if not re.fullmatch(r'(?:milli)?seconds?|minutes?|hours?|days?|weeks?|months?|years?|bytes?|k[bg]|m[bg]|g[bg]|percent|%', match.group(2), re.I):
                flag('quantity_unit', sid, 'Check the unit and interpretation of this numeric duration or quantity', 'warning')
        if re.search(r'\b(?:[01]?\d|2[0-3]):[0-5]\d\b|\b20\d{2}-\d{2}-\d{2}\b', body) and not re.search(r'UTC|time.?zone|local time|[+-]\d\d:\d\d|Z\b', body, re.I):
            flag('time_context', sid, 'Check whether this date/time requires an explicit timezone or local-time rule', 'warning')
        if re.search(r'\b(?:up to|between)\s+\d', body, re.I) and not re.search(r'inclusiv|exclusiv|exactly|at most|at least', body, re.I):
            flag('numeric_boundary', sid, 'Confirm whether the stated numeric limits include their endpoints', 'warning')
        terms = set(re.findall(r'\b[A-Z]{2,8}\b', body)) - {'API', 'HTTP', 'HTTPS', 'JSON', 'CSV', 'UTF', 'UTC', 'ID', 'UI', 'XML'}
        if any(term.casefold() not in definitions for term in terms):
            flag('domain_term', sid, 'Check whether a domain abbreviation needs a shared definition', 'warning')
        key = re.sub(r'\d+(?:\.\d+)?', '#', ' '.join(body.casefold().split()))
        if key in numeric_rules and numeric_rules[key]['text'] != body:
            flag('numeric_rule_difference', sid, 'Near-identical rules differ numerically; compare scope and source revision with ' + numeric_rules[key]['id'], 'warning')
        numeric_rules[key] = statement
    if value["proposals"]:
        flag("unconfirmed_proposal", "draft", "Unconfirmed proposals cannot enter the approved handoff")
    if re.search(r"OPEN\s+QUESTION|\bTBD\b|\bTODO\b", value["feature"], re.I):
        flag("unfinished_acceptance", "feature", "Acceptance criteria contain unresolved placeholders/questions")
    index = None
    try:
        index = feature_index(value["feature"])
    except ImportError:
        flag("parser_not_run", "feature", "Official Gherkin parser is unavailable; no approval is possible")
    except Exception:
        # Never echo source contents from third-party parser exception messages.
        flag("invalid_gherkin", "feature", "Feature failed parser or context/action/outcome, stable-ID, or outline checks")
    mappings = {s["id"]: s for s in value["scenarios"]}
    rules = {s["id"] for s in statements.values() if s["kind"] in {"rule", "constraint"}}
    if index:
        if {s["id"] for s in index["scenarios"]} != set(mappings):
            flag("scenario_mapping", "feature", "Actual Gherkin scenarios and coverage mapping must match exactly")
        if index["language"] != "en":
            flag("language_not_run", "feature", "Lexical quality checks currently cover English only")
        for tag in index["tags"]:
            if not SAFE_TAG.fullmatch(tag):
                flag("unknown_tag", "feature", "Unknown tag namespace; tracker issue mappings belong in an explicit integration profile")
            if tag.startswith("@risk_") and tag[6:] not in selected_policy["risk_ids"]:
                flag("unknown_risk", "feature", "Risk is absent from the operator-selected policy register")
        for scenario in index["scenarios"]:
            for n, step in enumerate(scenario["steps"]):
                scope = scenario["id"] + ":" + str(n)
                if VAGUE.search(step):
                    flag("vague_wording", scope, "Check whether the outcome is measurable in this context", "warning")
                if UI.search(step):
                    flag("interaction_wording", scope, "Check whether interaction detail is itself required behavior", "warning")
                if selected_policy["canonical_steps"] and step not in selected_policy["canonical_steps"]:
                    flag("noncanonical_step", scope, "Explain why an existing step cannot express this behavior", "warning")
    for sid, mapping in mappings.items():
        if not mapping["statement_ids"] or not set(mapping["statement_ids"]) <= rules:
            flag("invalid_scenario_support", sid, "Scenarios must reference actual business rules or constraints")
    coverage = {(c["statement_id"], c["category"]): c for c in value["coverage"]}
    for key in set(coverage) - {(r, c) for r in rules for c in CATEGORIES}:
        flag("unknown_coverage", str(key), "Coverage refers to an unknown rule/constraint")
    for rule in rules:
        covered = set()
        for category in CATEGORIES:
            row = coverage.get((rule, category))
            if row is None or (not row["scenario_ids"] and row["not_applicable_reason"] is None):
                flag("missing_coverage", rule + ":" + category, "Provide scenarios or a reviewed applicability explanation")
                continue
            for sid in row["scenario_ids"]:
                if sid not in mappings or rule not in mappings[sid]["statement_ids"] or mappings[sid]["category"] != category:
                    flag("incorrect_coverage", rule + ":" + category, "Coverage mapping does not match its scenario")
                else:
                    covered.add(sid)
        if not covered:
            flag("untested_rule", rule, "Every rule or constraint requires at least one acceptance scenario")
    # Reject scenario mappings that disappear from the explicit coverage matrix.
    for sid, mapping in mappings.items():
        for rule in mapping["statement_ids"]:
            if sid not in coverage.get((rule, mapping["category"]), {}).get("scenario_ids", []):
                flag("unindexed_scenario", sid, "Scenario-to-rule relationship is absent from coverage")
    if any(pattern.search(str(value) + str(sources)) for pattern in SECRETS):
        flag("credential_literal", "evidence", "Remove credential-like literals before model processing or handoff")
    findings += signals({"draft": value, "sources": sources})
    return {"draft_digest": digest(value), "findings": findings, "scenario_index": index, "semantic_truth_verified": False}
