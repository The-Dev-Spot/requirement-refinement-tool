#!/usr/bin/env python3
"""Compatibility entry point; writes only a local preview and hash manifest."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from clarity.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main(["logbook", *sys.argv[1:]]))
