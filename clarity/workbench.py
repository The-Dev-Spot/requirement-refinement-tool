"""Offline read-only HTML review workbench; escaped text, no JS, no remote assets."""
from __future__ import annotations

import difflib
import html
import json


def render(status: dict) -> str:
    run = status["run"]
    snapshot = status["snapshot"]
    escape = html.escape
    before = snapshot["source"]["text"].splitlines()
    after = (snapshot["description"] + "\n\n" + snapshot["acceptance_criteria"]).splitlines()
    diff = "\n".join(difflib.unified_diff(before, after, fromfile="source snapshot", tofile="current requirement", lineterm=""))
    sections = [("Exact local export plan", json.dumps(status.get("proposed_plan") or {"blocked": status.get("plan_error") or "Not yet approvable"}, indent=2)), ("Current requirement", snapshot["description"] + "\n\n" + snapshot["acceptance_criteria"]), ("Changes from source", diff or "No text changes"), ("Evidence and investigation", json.dumps({"evidence": snapshot["evidence"], "investigation": snapshot["investigation"]}, indent=2, ensure_ascii=False)), ("Owner questions and decisions", json.dumps(status["questions"], indent=2, ensure_ascii=False)), ("Independent review and machine checks", json.dumps(status["review"], indent=2, ensure_ascii=False)), ("Audit trail", json.dumps(status["events"], indent=2, ensure_ascii=False))]
    blocks = "".join("<section><h2>" + escape(title) + "</h2><pre>" + escape(body) + "</pre></section>" for title, body in sections)
    return """<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>Clarity review workbench</title><style>
body{font:17px/1.6 system-ui,sans-serif;max-width:1050px;margin:40px auto;padding:0 24px}
h1{font-size:2.4rem}h2{font-size:1.25rem}section{border-top:1px solid;padding:18px 0}
pre{white-space:pre-wrap;overflow-wrap:anywhere;font:14px/1.6 ui-monospace,monospace}
</style><main><h1>Clarity</h1><p>Standalone requirement review</p>""" + "<h2>" + escape(snapshot["title"]) + "</h2><p>" + escape(run["id"]) + " · revision " + str(run["revision"]) + " · <strong>" + escape(run["state"]) + "</strong></p><p>Snapshot digest: <code>" + escape(status["snapshot_digest"]) + "</code></p><p>Read-only local snapshot. No approval buttons, scripts, remote resources or tracker writes. Refresh after changes; use the authenticated CLI for decisions.</p>" + blocks + "</main></html>"
