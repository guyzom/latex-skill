#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Original project code; scope and terms: ../LICENSING.md.
"""Install pinned fonts from a local directory, existing system files, or a prior skill.

Font binaries are never distributed in this package. No network access is made.
All inputs are staged and verified against THIS release before any publication.
"""
from __future__ import annotations
import argparse
import hashlib
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tempfile
import zipfile

sys.dont_write_bytecode = True
from atomic_replace import atomic_replace
from font_paths import MANIFEST_DIR, default_install_dir, font_dir

ROOT = Path(__file__).resolve().parent.parent
MAX_FACE_BYTES = 8 * 1024 * 1024


def pins() -> dict[str, str]:
    return {name: digest for digest, name in
            (line.split() for line in (MANIFEST_DIR / 'SHA256SUMS').read_text().splitlines() if line.strip())}


def stage_from_skill(archive: Path, stage: Path, expected: dict[str, str]) -> None:
    """Read only the named font members; never extract arbitrary archive paths."""
    with zipfile.ZipFile(archive) as z:
        for name in expected:
            if not name.endswith('.ttf'):
                continue
            candidates = [i for i in z.infolist()
                          if PurePosixPath(i.filename).name == name
                          and not i.is_dir()]
            if len(candidates) != 1:
                raise ValueError(f'{name}: expected one archive member; found {len(candidates)}')
            info = candidates[0]
            path = PurePosixPath(info.filename)
            if path.is_absolute() or '..' in path.parts or '\\' in info.filename:
                raise ValueError(f'unsafe archive member: {info.filename}')
            if info.file_size > MAX_FACE_BYTES:
                raise ValueError(f'{name}: archive member exceeds the size limit')
            data = z.read(info)
            if hashlib.sha256(data).hexdigest() != expected[name]:
                raise ValueError(f'{name}: input does not match the canonical release hash')
            (stage / name).write_bytes(data)


def stage_from_directory(source: Path, stage: Path, expected: dict[str, str]) -> None:
    for name in expected:
        if name.endswith('.ttf'):
            candidate = source / name
            if not candidate.is_file() or candidate.stat().st_size > MAX_FACE_BYTES:
                raise ValueError(f'font missing or oversized: {candidate}')
            shutil.copyfile(candidate, stage / name)


def discover_system(stage: Path, expected: dict[str, str]) -> None:
    candidates: dict[str, list[Path]] = {}
    if shutil.which('fc-list'):
        result = subprocess.run(['fc-list', '--format=%{file}\n'], text=True,
                                capture_output=True, timeout=30, check=False)
        for raw in result.stdout.splitlines():
            p = Path(raw)
            candidates.setdefault(p.name, []).append(p)
    for name, digest in expected.items():
        if not name.endswith('.ttf'):
            continue
        found = None
        for path in candidates.get(name, []):
            if path.is_file() and path.stat().st_size <= MAX_FACE_BYTES:
                if hashlib.sha256(path.read_bytes()).hexdigest() == digest:
                    found = path
                    break
        if found is None:
            raise ValueError(f'{name}: no hash-matching installed face. Use --from-skill PRIOR.skill '
                             'or --from-directory FONT_DIR; a similarly named font is not a substitute.')
        shutil.copyfile(found, stage / name)


def install(target: Path, source: Path | None, archive: Path | None) -> None:
    expected = pins()
    with tempfile.TemporaryDirectory(prefix='hllpdf-font-stage-') as temp:
        stage = Path(temp)
        for name in ('SHA256SUMS', *(n for n in expected if not n.endswith('.ttf'))):
            shutil.copyfile(MANIFEST_DIR / name, stage / name)
        if archive is not None:
            stage_from_skill(archive, stage, expected)
        elif source is not None:
            stage_from_directory(source, stage, expected)
        elif (font_dir() / 'FrankRuhlLibre-Regular.ttf').is_file():
            stage_from_directory(font_dir(), stage, expected)
        else:
            discover_system(stage, expected)
        result = subprocess.run([sys.executable, str(ROOT / 'scripts/verify_font_bundle.py'), str(stage)],
                                capture_output=True, text=True, timeout=60)
        if result.returncode:
            raise ValueError(result.stdout + result.stderr)
        # Preserve historical symlink-safe publication and do not install any
        # files until the complete staged collection has passed verification.
        target.mkdir(parents=True, exist_ok=True)
        for item in sorted(stage.iterdir()):
            atomic_replace(item, target / item.name)
    if shutil.which('fc-cache'):
        subprocess.run(['fc-cache', '-f', str(target)], stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, timeout=60, check=False)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('destination', nargs='?', type=Path, default=None)
    group = p.add_mutually_exclusive_group()
    group.add_argument('--from-directory', type=Path)
    group.add_argument('--from-skill', type=Path)
    a = p.parse_args()
    # Match the build resolver: an empty override selects the default path,
    # while any nonempty explicit path remains authoritative.
    target = a.destination or Path(os.environ.get('HEBREW_LATEX_FONT_DIR') or default_install_dir())
    try:
        install(target.expanduser().absolute(), a.from_directory, a.from_skill)
    except (OSError, ValueError, zipfile.BadZipFile, subprocess.TimeoutExpired) as exc:
        print(f'✗ font installation failed: {exc}', file=sys.stderr)
        return 2
    print(f'✓ verified font installation: {target.expanduser().absolute()}')
    print('Use HEBREW_LATEX_FONT_DIR when choosing a non-default destination.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
