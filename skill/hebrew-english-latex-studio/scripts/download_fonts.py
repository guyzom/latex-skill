#!/usr/bin/env python3
"""Opt-in download of official fonts; stage and hash-verify before installation.

This utility is never invoked by build.sh. Run only when network acquisition
is intended. Local/offline imports remain supported by setup_fonts.sh.
"""
from __future__ import annotations
import argparse
import hashlib
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
sys.dont_write_bytecode = True
from install_fonts import pins, install
from font_paths import default_install_dir

FRANK = 'https://raw.githubusercontent.com/fontef/frankruhllibre/2372d1998e51dc011f86554c0d23f1ccf44afddf/fonts/ttf/'
HEEBO = 'https://raw.githubusercontent.com/OdedEzer/heebo/76c7d538568d3e6d7f052a12c5675c84430df25f/fonts/ttf/'
DEJAVU = 'https://github.com/dejavu-fonts/dejavu-fonts/releases/download/version_2_37/dejavu-fonts-ttf-2.37.zip'
MAX_DOWNLOAD_BYTES = 16 * 1024 * 1024


def fetch(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=60) as response:
        data = response.read(MAX_DOWNLOAD_BYTES + 1)
    if len(data) > MAX_DOWNLOAD_BYTES:
        raise ValueError('upstream response exceeds size limit')
    return data


def stage(stage_dir: Path, fetcher=fetch) -> None:
    """Read only exact font members; never unpack archive paths."""
    expected = pins()
    for prefix, url in [('FrankRuhlLibre-', FRANK), ('Heebo-', HEEBO)]:
        for name, digest in expected.items():
            if name.startswith(prefix) and name.endswith('.ttf'):
                data = fetcher(url + name)
                if hashlib.sha256(data).hexdigest() != digest:
                    raise ValueError(f'{name}: upstream SHA-256 differs from release pin')
                (stage_dir / name).write_bytes(data)
    with zipfile.ZipFile(io.BytesIO(fetcher(DEJAVU))) as archive:
        for name, digest in expected.items():
            if name.startswith('DejaVu') and name.endswith('.ttf'):
                members = [entry for entry in archive.infolist()
                           if entry.filename == 'dejavu-fonts-ttf-2.37/ttf/' + name]
                if len(members) != 1 or members[0].file_size > 8 * 1024 * 1024:
                    raise ValueError(f'{name}: missing, duplicate or oversized upstream member')
                data = archive.read(members[0])
                if hashlib.sha256(data).hexdigest() != digest:
                    raise ValueError(f'{name}: upstream SHA-256 differs from release pin')
                (stage_dir / name).write_bytes(data)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', type=Path, default=default_install_dir())
    args = parser.parse_args()
    try:
        with tempfile.TemporaryDirectory(prefix='latex-studio-font-download-') as td:
            source = Path(td)
            stage(source)
            install(args.destination.expanduser().absolute(), source, None)
        print(f'✓ downloaded, verified and installed fonts: {args.destination}')
        return 0
    except (OSError, ValueError, zipfile.BadZipFile, subprocess.TimeoutExpired) as exc:
        print(f'✗ font download or installation failed: {exc}', file=sys.stderr)
        return 1

if __name__ == '__main__':
    raise SystemExit(main())
