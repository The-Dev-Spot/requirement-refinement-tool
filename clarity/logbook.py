"""Build a local evidence preview. No remote upload and no claim of attachments."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from .guardrails import ValidationError, identifier, open_questions


def _read(path: Path, directory: Path) -> str:
    if path.is_symlink() or not path.is_file() or path.resolve().parent != directory:
        raise ValidationError("Missing or unsafe evidence file: " + path.name)
    try:
        return path.read_bytes().decode("utf-8")
    except (OSError, UnicodeError) as exc:
        raise ValidationError("Unreadable UTF-8 evidence: " + path.name) from exc


def build(story_id: str, run_dir: Path, sections: list[str]) -> tuple[str, dict[str, Any]]:
    identifier(story_id)
    if run_dir.is_symlink() or not run_dir.is_dir():
        raise ValidationError("Run directory must exist and not be a symlink")
    directory = run_dir.resolve()
    if not sections or "run-summary" not in sections or len(set(sections)) != len(sections):
        raise ValidationError("Unique sections including run-summary are required")
    for section in sections:
        identifier(section)
    sources: dict[str, str] = {}
    manifest: dict[str, Any] = {"run_id": story_id, "published": False, "files": []}
    for path in sorted(directory.glob(story_id + "-*.md")):
        if path.name.endswith("-logbook-page.built.md"):
            continue
        text = _read(path, directory)
        sources[path.name] = text
        data = text.encode("utf-8")
        manifest["files"].append({"name": path.name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    for section in sections:
        if story_id + "-" + section + ".md" not in sources:
            raise ValidationError("Missing required inline evidence: " + section)
    # Snapshot input can contain old questions; only count current requirement and
    # current comment artifacts. Use IDs in question records for semantic merging.
    question_texts = [sources.get(story_id + "-" + name + ".md", "") for name in ("rewrite", "proposed-comment")]
    count = len(open_questions(*question_texts))
    output = ["# " + story_id + " — evidence preview", "", "> LOCAL PREVIEW — not published. No attachments have been uploaded.", "", "Open questions in current artifacts: " + str(count), ""]
    for section in sections:
        name = story_id + "-" + section + ".md"
        output += ["## " + section.replace("-", " ").title(), "", "<!-- source: " + name + " -->", sources[name], ""]
    output += ["## Evidence manifest", "", "The accompanying JSON manifest records file hashes, not proof of remote persistence.", ""]
    for item in manifest["files"]:
        output.append("- `" + item["name"] + "` — SHA-256 `" + item["sha256"] + "`")
    return "\n".join(output) + "\n", manifest
