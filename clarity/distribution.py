"""Create a checksummed source-only handover from a clean committed checkout."""
import hashlib
import io
import json
import subprocess
import zipfile
from pathlib import Path
from .audit import check_repository
from .guardrails import ValidationError, canonical
from .refine.contracts import require
from .storage import write_private


def source_bundle(root, output):
    root = root.resolve()
    def git(*args):
        return subprocess.run(['git', *args], cwd=root, check=True, capture_output=True).stdout
    try:
        git('diff', '--quiet', 'HEAD', '--')
        revision = git('rev-parse', 'HEAD').decode().strip()
        names = git('ls-files', '-z', '--cached').decode().strip('\0').split('\0')
    except (OSError, subprocess.CalledProcessError):
        raise ValidationError('Build the bundle from a clean committed Git checkout') from None
    findings = check_repository(root)
    require(not findings, 'Source hygiene check failed; inspect clarity check-repo before packaging')
    require(bool(names) and output.resolve().is_relative_to(root) is False, 'Choose a bundle output outside the source checkout')
    files = {name: (root / name).read_bytes() for name in names}
    manifest = {'format': 'clarity-source-bundle-v1', 'source_revision': revision,
                'files': {name: hashlib.sha256(body).hexdigest() for name, body in files.items()},
                'excluded': ['Git metadata/history', 'untracked files', 'private state', 'credentials', 'backups']}
    files['SOURCE-MANIFEST.json'] = (canonical(manifest) + '\n').encode()
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, body in sorted(files.items()):
            item = zipfile.ZipInfo('clarity/' + name, date_time=(1980, 1, 1, 0, 0, 0)); item.compress_type = zipfile.ZIP_DEFLATED; item.external_attr = 0o600 << 16
            archive.writestr(item, body)
    body = stream.getvalue(); write_private(output, body)
    return {'source_revision': revision, 'file': str(output.absolute()), 'sha256': hashlib.sha256(body).hexdigest(), 'source_files': len(names)}
