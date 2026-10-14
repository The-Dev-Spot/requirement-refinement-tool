"""Clarity local application and requirement-quality tools."""
from __future__ import annotations

import argparse
import json
import sys
import sqlite3
from pathlib import Path

from .commands import add_commands, execute
from .audit import check_repository
from .guardrails import ValidationError, load_config, load_json, readiness
from .logbook import build


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    config = sub.add_parser("validate-config")
    config.add_argument("--config", type=Path, default=Path(".github/project-config.json"))
    gate = sub.add_parser("gate", help="Combine reported scores; does not perform semantic evaluation")
    gate.add_argument("report", type=Path)
    audit = sub.add_parser("check-repo", help="Scan tracked working-tree files; stage new files first")
    audit.add_argument("--root", type=Path, default=Path.cwd())
    log = sub.add_parser("logbook", help="Build a local preview and hash manifest")
    log.add_argument("run_id")
    log.add_argument("--run-dir", type=Path, required=True)
    log.add_argument("--config", type=Path, default=Path(".github/project-config.json"))
    from . import app_commands
    app_commands.add(sub)
    add_commands(sub)
    args = parser.parse_args(argv)
    try:
        if args.command in {'setup', 'start', 'doctor', 'mcp', 'backup', 'restore', 'source-bundle'}:
            return app_commands.execute(args)
        if args.command in {"work", "lint", "import-markdown", "linear-read", "benchmark"}:
            return execute(args)
        if args.command == "validate-config":
            load_config(args.config)
            print("Configuration valid. Live writes disabled.")
        elif args.command == "gate":
            result = readiness(load_json(args.report))
            print(json.dumps(result, indent=2))
            return 0 if result["verdict"] == "READY" else 1
        elif args.command == "check-repo":
            findings = check_repository(args.root)
            if findings:
                print("\n".join(findings))
                return 1
            print("Tracked-file hygiene checks passed. Human privacy review remains required.")
        elif args.command == "logbook":
            cfg = load_config(args.config)
            body, manifest = build(args.run_id, args.run_dir, cfg["logbook"]["inline_sections"])
            root = args.run_dir.resolve()
            targets = (root / (args.run_id + "-logbook-page.built.md"), root / (args.run_id + "-manifest.json"))
            for target in targets:
                if target.is_symlink() or target.exists():
                    raise ValidationError("Output already exists; use a new run revision")
            # Exclusive creation prevents overwriting an artifact or following an
            # existing symlink. An interrupted pair is visible and must be reconciled.
            with targets[0].open("x", encoding="utf-8") as fh:
                fh.write(body)
            with targets[1].open("x", encoding="utf-8") as fh:
                json.dump(manifest, fh, indent=2)
                fh.write("\n")
            print("Local evidence preview and manifest created. Nothing was published.")
        return 0
    except (KeyError, TypeError, RecursionError):
        print("ERROR: Malformed structured input; no operation completed.", file=sys.stderr)
        return 2
    except sqlite3.Error:
        print("ERROR: Local storage operation failed; refresh state and verify integrity before retrying.", file=sys.stderr)
        return 2
    except (ValidationError, OSError, ValueError) as exc:
        # Never include input payloads, raw responses or credential values here.
        print("ERROR: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
