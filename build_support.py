"""Include the canonical human quality contract in installed wheels."""
from pathlib import Path
from shutil import copyfile
from setuptools.command.build_py import build_py

RESOURCES = {
    'AGENTS.md': 'AGENTS.md',
    'handoff-standard.md': 'docs/handoff-standard.md',
    'runtime-doc-contract.json': '.github/agents/runtime-doc-contract.json',
    'requirements.lock': 'requirements.lock',
}


class BuildPy(build_py):
    def run(self):
        super().run()
        directory = Path(self.build_lib) / 'clarity' / 'resources'
        directory.mkdir(parents=True, exist_ok=True)
        for name, source in RESOURCES.items(): copyfile(source, directory / name)
