#!/usr/bin/env python3
"""Deterministically assemble the Confluence log-book STORY PAGE body.

Why this exists (L-0030): under default effort/context, the agent tends to
*paraphrase* the inline sections when it composes the log-book page from memory,
producing an incomplete evidence page. This script
removes that failure mode: it reads the run folder's Markdown artifacts and emits
the page body with each inline section included VERBATIM. The agent then passes the
output straight to confluence_update_page (content_format: markdown) -- no
summarizing, no reconstruction from context.

Usage:
    python3 scripts/build-logbook-page.py DEMO-1234
    python3 scripts/build-logbook-page.py DEMO-1234 --run-dir docs/agent/runs/DEMO-1234 \
        --out docs/agent/runs/DEMO-1234/DEMO-1234-logbook-page.built.md

Cross-platform (mac/Linux/Windows) and dependency-free (standard library only).
"""

import argparse
import os
import re
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(REPO_ROOT, ".github", "project-config.yaml")

DEFAULT_JIRA_BASE = "https://jira.example.invalid"
DEFAULT_INLINE_SECTIONS = ["run-summary", "rewrite", "proposed-comment"]

SECTION_TITLES = {
    "run-summary": "Run summary",
    "rewrite": "Rewrite (corrected story)",
    "proposed-comment": "Proposed / posted comment",
    "eval-report": "Evaluation report",
    "quality-gates": "Quality gate",
    "investigation": "Investigation",
    "po-analysis": "PO analysis",
}


def read_config():
    """Minimal, dependency-free parse of the two values we need from the YAML."""
    jira_base = DEFAULT_JIRA_BASE
    inline = list(DEFAULT_INLINE_SECTIONS)
    config_paths = [CONFIG_PATH, os.path.join(REPO_ROOT, ".github", "project-config.local.yaml")]
    # The shipped config and its copied local override use block-style YAML.
    # Read only Jira's base URL and the log-book inline-section list; no secrets.
    for config_path in config_paths:
        if not os.path.exists(config_path):
            continue
        in_jira = False
        in_inline = False
        parsed_inline = []
        with open(config_path, encoding="utf-8") as handle:
            lines = handle.read().splitlines()
        for line in lines:
            stripped = line.strip()
            indent = len(line) - len(line.lstrip(" "))
            if re.match(r"^jira:\s*$", line):
                in_jira = True
                continue
            if in_jira and indent == 0 and stripped and not stripped.startswith("#"):
                in_jira = False
            if in_jira:
                m = re.match(r"\s*base_url:\s*[\"']?([^\"'\s]+)", line)
                if m:
                    jira_base = m.group(1)
            if re.match(r"^\s*inline_sections:\s*(#.*)?$", line):
                in_inline = True
                continue
            if in_inline:
                m = re.match(r"\s*-\s*([A-Za-z0-9_-]+)", line)
                if m:
                    parsed_inline.append(m.group(1))
                elif stripped and not stripped.startswith("#"):
                    in_inline = False
        if parsed_inline:
            inline = parsed_inline
    return jira_base, inline


def read_file(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read().rstrip("\n")


def parse_context(run_dir, story_id):
    """Best-effort pull of status-panel values from the run-context file."""
    ctx = {}
    path = os.path.join(run_dir, story_id + "-run-context.md")
    if not os.path.exists(path):
        return ctx
    for line in open(path, encoding="utf-8"):
        m = re.match(r"\s*(mode|current_stage|verdict|reporter|type|opened|closed|story_type)\s*:\s*(.+)$", line)
        if m:
            key = m.group(1).strip()
            val = m.group(2).strip().strip('"')
            val = re.sub(r"\s{2,}#.*$", "", val)  # drop trailing inline "# ..." comment
            val = re.sub(r"\s+", " ", val).strip()
            ctx.setdefault(key, val)
    return ctx


def count_open_questions(run_dir, story_id):
    """Count distinct OPEN QUESTION -> PO markers across rewrite + proposed-comment."""
    marker = re.compile(r"^\s*#\s*OPEN QUESTION\s*->", re.IGNORECASE | re.MULTILINE)
    total = 0
    for name in (story_id + "-rewrite.md", story_id + "-proposed-comment.md"):
        p = os.path.join(run_dir, name)
        if os.path.exists(p):
            text = open(p, encoding="utf-8").read()
            total = max(total, len(marker.findall(text)))
    return total


def build(story_id, run_dir):
    jira_base, inline_sections = read_config()
    ctx = parse_context(run_dir, story_id)
    oq = count_open_questions(run_dir, story_id)

    out = []
    out.append('<ac:structured-macro ac:name="toc"/>')
    out.append("")
    out.append("## " + story_id)
    out.append("")
    out.append("> Run evidence log - maintained by the story pipeline. The Jira issue itself "
               "is the source of truth; this page records what the review run produced. "
               "Do not edit by hand.")
    out.append("")
    out.append("| | |")
    out.append("|---|---|")
    out.append("| **Jira** | [{0}]({1}/browse/{0}) |".format(story_id, jira_base))
    if ctx.get("verdict"):
        out.append("| **Verdict** | {0} |".format(ctx["verdict"]))
    if ctx.get("mode"):
        out.append("| **Mode** | {0} |".format(ctx["mode"]))
    if ctx.get("current_stage"):
        out.append("| **Run status** | {0} |".format(ctx["current_stage"]))
    if ctx.get("reporter"):
        out.append("| **Reporter** | {0} |".format(ctx["reporter"]))
    out.append("| **Open questions** | {0} |".format(oq))
    out.append("| **Run folder** | `docs/agent/runs/{0}/` |".format(story_id))
    out.append("")

    # Inline sections -- included VERBATIM, never summarized.
    missing = []
    for section in inline_sections:
        path = os.path.join(run_dir, "{0}-{1}.md".format(story_id, section))
        title = SECTION_TITLES.get(section, section.replace("-", " ").title())
        out.append("---")
        out.append("")
        out.append("## " + title)
        out.append("")
        if os.path.exists(path):
            out.append("<!-- inline (verbatim): {0}-{1}.md -->".format(story_id, section))
            out.append(read_file(path))
        else:
            missing.append(section)
            out.append("_(source file `{0}-{1}.md` not found in run folder)_".format(story_id, section))
        out.append("")

    # Evidence list -- every run artifact is also attached.
    md_files = sorted(
        f for f in os.listdir(run_dir)
        if f.startswith(story_id + "-") and f.endswith(".md")
        and not f.endswith("-logbook-page.built.md")
    )
    out.append("---")
    out.append("")
    out.append("## Evidence (attached)")
    out.append("")
    out.append("The complete run trail is attached to this page as Markdown files:")
    out.append("")
    for f in md_files:
        out.append("* `{0}`".format(f))
    out.append("")

    return "\n".join(out), missing


def main():
    ap = argparse.ArgumentParser(description="Build the Confluence log-book story page body (verbatim).")
    ap.add_argument("story_id", help="e.g. DEMO-1234")
    ap.add_argument("--run-dir", default=None, help="defaults to docs/agent/runs/<story_id>")
    ap.add_argument("--out", default=None, help="write body here; also printed to stdout")
    args = ap.parse_args()

    run_dir = args.run_dir or os.path.join(REPO_ROOT, "docs", "agent", "runs", args.story_id)
    if not os.path.isdir(run_dir):
        sys.stderr.write("ERROR: run folder not found: {0}\n".format(run_dir))
        return 2

    body, missing = build(args.story_id, run_dir)

    out_path = args.out or os.path.join(run_dir, args.story_id + "-logbook-page.built.md")
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(body + "\n")

    sys.stderr.write("Wrote {0} ({1} chars).\n".format(out_path, len(body)))
    if missing:
        sys.stderr.write("WARNING: missing inline source files: {0}\n".format(", ".join(missing)))
    sys.stdout.write(body + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
