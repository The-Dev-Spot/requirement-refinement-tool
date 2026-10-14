"""User-facing local app entry points, separate from the legacy snapshot CLI."""
import getpass
import json
from pathlib import Path
from .installation import DEFAULT_STATE
from .refine.contracts import require
from .storage import private_path, write_private


def add(sub):
    bundle = sub.add_parser('source-bundle', help='Clean committed source snapshot without Git history or runtime state')
    bundle.add_argument('--root', type=Path, default=Path.cwd()); bundle.add_argument('--output', type=Path, required=True)
    for name in ('setup', 'start', 'doctor', 'mcp', 'efficiency', 'backup', 'restore'):
        cmd = sub.add_parser(name)
        if name != 'restore': cmd.add_argument('--state', type=Path, default=DEFAULT_STATE)
        if name == 'start': cmd.add_argument('--port', type=int, default=8765)
        if name == 'mcp':
            cmd.add_argument('--key-file', type=Path, required=True); cmd.add_argument('--id', required=True)
            cmd.add_argument('--stage', choices=['intake', 'draft', 'revise', 'review'], help='Optional stage; author tasks otherwise use targeted revision when a draft exists')
        if name == 'efficiency':
            cmd.add_argument('--key-file', type=Path, required=True); cmd.add_argument('--id', required=True)
        if name == 'backup':
            cmd.add_argument('--key-file', type=Path, required=True); cmd.add_argument('--output', type=Path, required=True)
        if name == 'restore':
            cmd.add_argument('--input', type=Path, required=True); cmd.add_argument('--destination', type=Path, required=True); cmd.add_argument('--digest', required=True)


def execute(args):
    if args.command == 'source-bundle':
        from .distribution import source_bundle
        print(json.dumps(source_bundle(args.root, args.output), indent=2))
    elif args.command == 'setup':
        from .installation import setup
        print(json.dumps(setup(args.state), indent=2))
    elif args.command == 'doctor':
        from .installation import doctor
        print(json.dumps(doctor(args.state), indent=2))
    elif args.command == 'start':
        from .refine.web import Workbench
        require(1 <= args.port <= 65535, 'Invalid workbench port')
        with Workbench(args.state, args.port) as app:
            print('Clarity: ' + app.origin, flush=True)
            print('Sign in using a login-key file created by clarity setup. Press Ctrl+C to stop.', flush=True)
            try: app.serve_forever()
            except KeyboardInterrupt: pass
    elif args.command == 'mcp':
        from .host_bridge import serve
        serve(args.state, args.key_file, args.id, stage=args.stage)
    elif args.command == 'efficiency':
        from .refine.controller import Controller
        private_path(args.key_file); require(args.key_file.stat().st_size < 256, 'Invalid credential file')
        print(json.dumps(Controller(args.state).status(args.key_file.read_text().strip(), args.id)['efficiency'], indent=2))
    elif args.command == 'backup':
        from .backup import backup
        from .backup_crypto import encrypt
        private_path(args.key_file); require(args.key_file.stat().st_size < 256, 'Invalid credential file')
        envelope = backup(args.state, args.key_file.read_text().strip())
        password = getpass.getpass('Backup passphrase (12+ characters): ')
        require(password == getpass.getpass('Confirm passphrase: '), 'Passphrases differ')
        write_private(args.output, (json.dumps(encrypt(envelope, password), indent=2) + '\n').encode())
        print('Encrypted backup created. Keep this receipt separately: ' + envelope['digest'])
    elif args.command == 'restore':
        from .backup import restore
        from .backup_crypto import decrypt
        from .guardrails import load_json
        require(not args.input.is_symlink() and args.input.stat().st_size <= 28_000_000, 'Backup input is unsafe or too large')
        envelope = decrypt(load_json(args.input), getpass.getpass('Backup passphrase: '))
        restore(args.destination, envelope, args.digest)
        print('Restored. Run clarity setup --state ' + str(args.destination) + ' to create fresh login keys, then reconnect services.')
    return 0
