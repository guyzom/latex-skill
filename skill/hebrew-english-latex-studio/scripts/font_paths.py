#!/usr/bin/env python3
"""Resolve an external, hash-pinned font installation without network access."""
from __future__ import annotations
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
MANIFEST_DIR = ROOT / 'assets' / 'fonts'


def default_install_dir() -> Path:
    # XDG paths must be absolute. An empty or relative value is unset by the
    # specification; treating it as Path('') would silently select the cwd.
    data = os.environ.get('XDG_DATA_HOME')
    base = Path(data) if data and Path(data).is_absolute() else Path.home() / '.local/share'
    return base / 'fonts' / 'hebrew-lualatex-pdf'


def font_dir() -> Path:
    """Explicit override wins, including an invalid override (fail closed later)."""
    override = os.environ.get('HEBREW_LATEX_FONT_DIR')
    if override:
        return Path(override).expanduser().resolve()
    for candidate in (default_install_dir(), MANIFEST_DIR):
        if (candidate / 'FrankRuhlLibre-Regular.ttf').is_file():
            return candidate.resolve()
    return default_install_dir().resolve()


if __name__ == '__main__':
    print(font_dir())
