"""Small offline hygiene check, not a full secret scanner or privacy guarantee."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

from .guardrails import ValidationError

ALLOWED_HOSTS = {"example.com", "example.invalid", "github.com", "api.github.com", "docs.github.com", "modelcontextprotocol.io", "cheatsheetseries.owasp.org", "cucumber.io", "api.linear.app", "linear.app", "www.sqlite.org", "pypi.org", "127.0.0.1", "docs.ollama.com", "docs.getxray.app", "developer.atlassian.com", "developers.openai.com", "platform.claude.com", "code.claude.com", "code.visualstudio.com"}
URL = re.compile(r"https?://[^\s<>\"')`]+")
EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@([A-Z0-9.-]+\.[A-Z]{2,})\b", re.I)
SECRETS = (
    re.compile(r"\bgh[pousr]_" + r"[A-Za-z0-9]{30,}\b"),
    re.compile(r"\bgithub_pat_" + r"[A-Za-z0-9_]{30,}\b"),
    re.compile(r"\bsk-" + r"[A-Za-z0-9_-]{32,}\b"),
    re.compile(r"-----BEGIN " + r"(?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"(?i)\bBearer\s+" + r"[A-Za-z0-9._~+/-]{24,}"),
)


def scan_text(text: str) -> set[str]:
    findings: set[str] = set()
    if any(pattern.search(text) for pattern in SECRETS):
        findings.add("credential-like literal")
    for match in EMAIL.finditer(text):
        if match.group(1).lower() not in {"example.com", "example.invalid"}:
            findings.add("non-example email")
    for match in URL.finditer(text):
        try:
            parsed = urlsplit(match.group(0))
            if parsed.username or parsed.password or parsed.hostname not in ALLOWED_HOSTS:
                findings.add("unreviewed host or credential-bearing URL")
        except ValueError:
            findings.add("malformed URL")
    return findings


def check_repository(root: Path) -> list[str]:
    root = root.resolve()
    try:
        result = subprocess.run(["git", "ls-files", "-z", "--cached"], cwd=root, check=True, capture_output=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ValidationError("Run inside a Git repository; stage files before scanning") from exc
    names = [name for name in result.stdout.decode("utf-8").split("\0") if name]
    if not names:
        raise ValidationError("No tracked files to scan")
    findings: list[str] = []
    for name in names:
        path = root / name
        parts = Path(name).parts
        forbidden = any(p in {".idea", "__pycache__", "node_modules", ".DS_Store", ".claude"} for p in parts)
        forbidden |= Path(name).name in {".env", "mcp.json", "project-config.local.json", "settings.local.json"}
        forbidden |= name.startswith((".clarity/", "knowledge/private/", "docs/agent/runs/"))
        forbidden |= Path(name).suffix in {".zip", ".pyc", ".log", ".docx", ".pptx", ".pdf", ".key", ".sqlite", ".sqlite3"}
        if forbidden:
            findings.append(name + ": forbidden runtime, private or binary artifact")
            continue
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root):
            findings.append(name + ": missing or unsafe path")
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            findings.append(name + ": not readable UTF-8 source")
            continue
        findings.extend(name + ": " + rule for rule in sorted(scan_text(text)))
    return findings
