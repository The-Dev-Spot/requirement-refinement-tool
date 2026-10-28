"""Standalone CLI commands. Credentials come from private files, never JSON claims."""
from __future__ import annotations

import json
from pathlib import Path

from . import adapters, backup, benchmark, lint, workbench
from .guardrails import ValidationError, load_json
from .runtime import Workflow, provision
from .storage import initialize, private_path, write_private


def add_commands(sub):
    p = sub.add_parser("benchmark", help="Run synthetic rule regressions; not model evaluation")
    p.add_argument("suite", type=Path)
    p = sub.add_parser("lint", help="Run machine checks, not semantic evaluation")
    p.add_argument("snapshot", type=Path)
    p = sub.add_parser("import-markdown", help="Build a standalone snapshot from local files")
    p.add_argument("source", type=Path)
    p.add_argument("acceptance", type=Path)
    for name in ("project", "source-id", "source-date", "kind"):
        p.add_argument("--" + name, required=True)
    p.add_argument("--output", type=Path, required=True)
    p = sub.add_parser("linear-read", help="Explicit read-only issue/comments snapshot")
    p.add_argument("issue")
    p.add_argument("--team-id", required=True)
    p.add_argument("--project-id")
    p.add_argument("--key-file", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    work = sub.add_parser("work", help="Durable standalone workflow")
    work.add_argument("--state", type=Path, default=Path.home() / ".local/state/clarity")
    work.add_argument("--token-file", type=Path)
    actions = work.add_subparsers(dest="operation", required=True)
    actions.add_parser("init")
    p = actions.add_parser("provision", help="OS-owner administration, not an agent operation")
    p.add_argument("actor")
    p.add_argument("role", choices=("author", "reviewer", "operator"))
    p.add_argument("--output", type=Path, required=True)
    p = actions.add_parser("restore")
    p.add_argument("backup", type=Path)
    p.add_argument("--digest", required=True)
    actions.add_parser("list")
    p = actions.add_parser("create")
    p.add_argument("run_id")
    p.add_argument("snapshot", type=Path)
    for op in ("revise", "review"):
        p = actions.add_parser(op)
        p.add_argument("run_id")
        p.add_argument("version", type=int)
        p.add_argument("input", type=Path)
    for op in ("status", "plan", "verify", "view"):
        p = actions.add_parser(op)
        p.add_argument("run_id")
        if op == "view":
            p.add_argument("--output", type=Path, required=True)
    p = actions.add_parser("answer")
    p.add_argument("run_id")
    p.add_argument("version", type=int)
    p.add_argument("question_id")
    p.add_argument("answer_file", type=Path)
    p = actions.add_parser("decide")
    p.add_argument("run_id")
    p.add_argument("version", type=int)
    p.add_argument("decision", choices=("reject", "release_quarantine", "new_rewrite_cycle"))
    p.add_argument("--reason", required=True)
    p = actions.add_parser("approve")
    p.add_argument("run_id")
    p.add_argument("version", type=int)
    p.add_argument("plan_digest")
    p.add_argument("--ttl", type=int, default=900)
    p = actions.add_parser("seal")
    p.add_argument("approval_id")
    p = actions.add_parser("export")
    p.add_argument("export_id")
    p.add_argument("--output", type=Path, required=True)
    p = actions.add_parser("backup")
    p.add_argument("--output", type=Path, required=True)
    p = actions.add_parser("revoke")
    p.add_argument("credential_id")


def _key(path: Path | None) -> str:
    if path is None:
        raise ValidationError("Supply --token-file outside the agent workspace")
    private_path(path.absolute())
    if path.stat().st_size > 4096:
        raise ValidationError("Invalid credential file")
    return path.read_text(encoding="utf-8").strip()


def _output(path: Path, value: str | dict):
    body = value if isinstance(value, str) else json.dumps(value, indent=2, ensure_ascii=False)
    write_private(path.absolute(), (body + "\n").encode())


def execute(args) -> int:
    if args.command == "benchmark":
        result = benchmark.run(load_json(args.suite))
        print(json.dumps(result, indent=2))
        return 0 if result["passed"] == result["total"] else 1
    if args.command == "lint":
        result = lint.check(load_json(args.snapshot))
        print(json.dumps(result, indent=2))
        return 0 if not result["injection_flags"] and all(c["status"] == "PASS" for c in result["checks"].values()) else 1
    if args.command == "import-markdown":
        _output(args.output, adapters.import_markdown(args.source, args.acceptance, project=args.project, source_id=args.source_id, source_date=args.source_date, kind=args.kind))
        print("Local snapshot created; independent investigation and review still required.")
        return 0
    if args.command == "linear-read":
        reader = adapters.LinearReader(_key(args.key_file), args.team_id, project_id=args.project_id)
        _output(args.output, reader.read_issue(args.issue))
        print("Read-only tracker snapshot saved. Nothing was changed remotely.")
        return 0
    if args.operation == "init":
        initialize(args.state)
        print("Private standalone workspace initialized. No identities provisioned yet.")
        return 0
    if args.operation == "provision":
        key_id = provision(args.state, args.actor, args.role, args.output)
        print("Capability provisioned; ID: " + key_id + ". Secret written only to the selected private file.")
        return 0
    if args.operation == "restore":
        backup.restore(args.state, load_json(args.backup), args.digest)
        print("Restored. Provision fresh credentials; old keys and unused approvals are disabled.")
        return 0
    token = _key(args.token_file)
    workflow = Workflow(args.state)
    op = args.operation
    if op == "create":
        result = workflow.create(token, args.run_id, load_json(args.snapshot))
    elif op in {"revise", "review"}:
        result = getattr(workflow, op)(token, args.run_id, args.version, load_json(args.input))
    elif op in {"status", "plan", "verify"}:
        result = getattr(workflow, op)(token, args.run_id)
    elif op == "list":
        result = workflow.list_runs(token)
    elif op == "answer":
        if args.answer_file.stat().st_size > 10000:
            raise ValidationError("Answer file exceeds size limit")
        result = workflow.answer(token, args.run_id, args.version, args.question_id, args.answer_file.read_text(encoding="utf-8"))
    elif op == "decide":
        result = workflow.decide(token, args.run_id, args.version, args.decision, args.reason)
    elif op == "approve":
        result = workflow.approve(token, args.run_id, args.version, args.plan_digest, args.ttl)
    elif op == "seal":
        result = workflow.seal(token, args.approval_id)
    elif op == "export":
        _output(args.output, workflow.export(token, args.export_id))
        result = {"saved": True, "remote_published": False}
    elif op == "view":
        _output(args.output, workbench.render(workflow.status(token, args.run_id)))
        result = {"saved": True, "read_only": True}
    elif op == "backup":
        envelope = backup.backup(args.state, token)
        _output(args.output, envelope)
        result = {"saved": True, "digest": envelope["digest"], "credentials_included": False}
    elif op == "revoke":
        workflow.revoke(token, args.credential_id)
        result = {"revoked": True}
    else:
        raise ValidationError("Unsupported operation")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0
