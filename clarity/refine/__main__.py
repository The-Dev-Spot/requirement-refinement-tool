"""Local-first Clarity refinement commands. No automatic approval or publication."""
from __future__ import annotations
import argparse
import json
import sqlite3
import sys
from pathlib import Path

from ..guardrails import ValidationError, load_json
from ..storage import initialize as initialize_workspace, private_path, write_private
from .contracts import require
from .controller import Controller, initialize
from .handoff import archive
from .identity import provision


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state', type=Path, required=True, help='Trusted private controller workspace; keep outside agent access')
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('init')
    key = sub.add_parser('key', help='OS-owner administration, not an agent operation')
    key.add_argument('--actor', required=True); key.add_argument('--role', choices=['author', 'reviewer', 'operator'], required=True); key.add_argument('--output', type=Path, required=True)
    serve = sub.add_parser('serve')
    serve.add_argument('--port', type=int, default=8765)
    serve.add_argument('--model'); serve.add_argument('--review-model'); serve.add_argument('--ollama-port', type=int, default=11434)
    project_commands = {'glossary', 'approve-glossary'}
    for name in ('capture', 'status', 'plan', 'seal', 'verify', 'action', 'stage', 'policy',
                 'portable', 'glossary', 'approve-glossary', 'attach-glossary', 'questionnaire'):
        cmd = sub.add_parser(name)
        cmd.add_argument('--key-file', type=Path, required=True)
        if name not in project_commands | {'policy'}: cmd.add_argument('--id', required=True)
        if name == 'capture':
            cmd.add_argument('--project', required=True); cmd.add_argument('--brief-file', type=Path, required=True); cmd.add_argument('--presentation', choices=['guided', 'concise'], default='guided')
        elif name == 'plan': cmd.add_argument('--profile', choices=['cucumber', 'xray-cloud', 'xray-server-dc'], default='cucumber')
        elif name == 'seal':
            cmd.add_argument('--approval', type=int, required=True); cmd.add_argument('--output', type=Path, required=True)
            cmd.add_argument('--full-audit', action='store_true', help='Include private evidence, traceability, review and manifest; default is the two delivery files')
        elif name == 'portable':
            cmd.add_argument('--approval', type=int, required=True); cmd.add_argument('--output', type=Path, required=True)
        elif name == 'action':
            cmd.add_argument('action', choices=['submit', 'review', 'ask', 'answer', 'source', 'confirm-source', 'approve', 'resolve-signal', 'resolve-question', 'new-cycle'])
            cmd.add_argument('--version', type=int, required=True); cmd.add_argument('--input', type=Path, required=True)
        elif name == 'stage':
            cmd.add_argument('stage', choices=['intake', 'draft', 'revise', 'review']); cmd.add_argument('--version', type=int, required=True); cmd.add_argument('--model', required=True); cmd.add_argument('--ollama-port', type=int, default=11434)
        elif name == 'policy': cmd.add_argument('--project', required=True); cmd.add_argument('--input', type=Path, required=True)
        elif name in project_commands:
            cmd.add_argument('--project', required=True)
            if name == 'glossary': cmd.add_argument('--record', type=int)
            else:
                cmd.add_argument('--expected-record', type=int, required=True); cmd.add_argument('--input', type=Path, required=True)
        elif name == 'attach-glossary':
            cmd.add_argument('--version', type=int, required=True); cmd.add_argument('--record', type=int, required=True)
            cmd.add_argument('--digest', required=True); cmd.add_argument('--replace-source')
        elif name == 'questionnaire':
            cmd.add_argument('--recipient', required=True); cmd.add_argument('--purpose', required=True)
            cmd.add_argument('--questions', nargs='+', required=True); cmd.add_argument('--dependencies', type=Path)
            cmd.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'init':
            if not (args.state / 'state.sqlite3').exists(): initialize_workspace(args.state)
            initialize(args.state)
            print('Refinement workspace initialized. No model or remote integration is enabled.')
            return 0
        if args.command == 'key':
            print('Capability ID: ' + provision(args.state, args.actor, args.role, args.output))
            return 0
        if args.command == 'serve':
            from .web import Workbench
            from .worker import Ollama
            require(type(args.port) is int and 1 <= args.port <= 65535, 'Invalid workbench port')
            provider = Ollama(args.model, port=args.ollama_port) if args.model else None
            reviewer = Ollama(args.review_model, port=args.ollama_port) if args.review_model else None
            with Workbench(args.state, args.port, provider, reviewer) as app:
                print('Workbench: ' + app.origin, flush=True)
                print('Loopback only. Verify the selected models and data handling before using private evidence.', flush=True)
                try: app.serve_forever()
                except KeyboardInterrupt: pass
            return 0
        private_path(args.key_file)
        require(args.key_file.stat().st_size < 256, 'Invalid capability file')
        token = args.key_file.read_text().strip()
        c = Controller(args.state)
        if args.command in {'action', 'policy', 'approve-glossary'}:
            require(not args.input.is_symlink() and args.input.stat().st_size <= 1_000_000, 'Input is unsafe or too large')
            data = load_json(args.input)
        if args.command == 'capture':
            require(not args.brief_file.is_symlink() and args.brief_file.stat().st_size <= 100000, 'Brief is unsafe or too large')
            result = c.create(token, args.id, args.project, args.brief_file.read_text(encoding='utf-8'), args.presentation)
        elif args.command == 'status': result = c.status(token, args.id)
        elif args.command == 'plan': result = c.plan(token, args.id, args.profile)
        elif args.command == 'verify': result = c.verify(token, args.id)
        elif args.command == 'seal':
            result = c.seal(token, args.id, args.approval)
            write_private(args.output, archive(result, full_audit=args.full_audit))
            print('Approved local handoff written. Nothing was uploaded to a tracker.')
            return 0
        elif args.command == 'portable':
            from .portable import portable_archive
            write_private(args.output, portable_archive(c.exported(token, args.id, args.approval)))
            print('Portable view of the sealed handoff written. No private source bundle or execution authority was exported.')
            return 0
        elif args.command in project_commands | {'attach-glossary'}:
            from .project_tools import ProjectTools
            tools = ProjectTools(args.state)
            if args.command == 'glossary': result = tools.glossary(token, args.project, args.record)
            elif args.command == 'approve-glossary': result = tools.approve_glossary(token, args.project, data, args.expected_record)
            else: result = tools.attach_glossary(token, args.id, args.version, args.record, args.digest, args.replace_source)
        elif args.command == 'questionnaire':
            from .collaboration import questionnaire
            dependencies = None
            if args.dependencies:
                require(not args.dependencies.is_symlink() and args.dependencies.stat().st_size <= 100000, 'Dependencies are unsafe or too large')
                dependencies = load_json(args.dependencies)
            rendered = questionnaire(c.status(token, args.id), args.recipient, args.purpose, args.questions, dependencies)
            write_private(args.output, rendered.encode('utf-8'))
            print('Questionnaire written. Review before sharing; returned answers still need operator confirmation.')
            return 0
        elif args.command == 'policy': result = {'policy_record': c.set_policy(token, args.project, data)}
        elif args.command == 'stage':
            from .worker import Ollama, run_stage
            result = run_stage(c, token, args.id, args.version, args.stage, Ollama(args.model, port=args.ollama_port))
        else:
            common = (token, args.id, args.version)
            if args.action == 'submit': result = c.submit(*common, data)
            elif args.action == 'review': result = c.review(*common, data)
            elif args.action == 'ask': result = c.ask(*common, data)
            elif args.action == 'answer': result = c.answer(*common, **data)
            elif args.action == 'source': result = c.add_source(*common, **data)
            elif args.action == 'confirm-source': result = c.confirm_source(*common, **data)
            elif args.action == 'approve': result = c.approve(*common, **data)
            elif args.action == 'resolve-signal': result = c.resolve_signal(*common, **data)
            elif args.action == 'resolve-question': result = c.resolve_question(*common, **data)
            else: result = c.new_cycle(*common, **data)
        print(json.dumps(result, indent=2))
        return 0
    except (ValidationError, OSError, ValueError, TypeError, KeyError, RecursionError, sqlite3.Error) as exc:
        message = str(exc) if isinstance(exc, ValidationError) else 'Invalid input or local storage failure; inspect state before retrying.'
        print('ERROR: ' + message, file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
