#!/usr/bin/env python3
"""Fail when a standalone skill tree contains release-time debris or unsafe paths."""
from __future__ import annotations

import argparse
from pathlib import Path
import stat
import sys
import unicodedata

ROOT = Path(__file__).resolve().parent.parent
BAD_DIRS = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
# Standalone releases are not repository backups. Block worktree .git FILES
# as well as VCS directories; both can expose private host/repository metadata.
VCS_NAMES = {".git", ".hg", ".svn", ".bzr"}
# This is a conservative debris check, NOT a general secret scanner. Values in
# arbitrary source/text still require review. Even .env.example is not assumed safe.
SECRET_NAMES = {".env", ".netrc", ".npmrc", ".pypirc", "credentials.json",
                "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519"}
OPAQUE_SUFFIXES = {".skill", ".zip", ".tar", ".tgz", ".tar.gz", ".tar.bz2",
                   ".tar.xz", ".7z", ".rar"}
SECRET_SUFFIXES = {".pem", ".key", ".p12", ".pfx", ".keystore", ".kdbx"}
BAD_EXACT = {".DS_Store", "Thumbs.db"}
BAD_SUFFIXES = {
    # Font programs are external dependencies; never distribute them in a skill.
    ".ttf", ".otf", ".ttc", ".woff", ".woff2", ".pfb", ".pfa",
    # Python/runtime caches.
    ".pyc", ".pyo",
    # Primary TeX/PDF build outputs and recorder state.
    ".pdf", ".aux", ".toc", ".out", ".log", ".fls", ".fdb_latexmk",
    ".synctex", ".synctex.gz", ".xdv", ".dvi",
    # Bibliography, index, glossary, and presentation side products.
    ".bbl", ".blg", ".bcf", ".run.xml", ".idx", ".ind", ".ilg",
    ".glo", ".gls", ".acn", ".acr", ".alg", ".lof", ".lot",
    ".nav", ".snm", ".vrb",
}
BAD_ENDINGS = (
    ".failed.log", ".failed.pdf", ".failed.aux", "~", ".swp", ".swo",
)


# A .skill ZIP may be installed on a different OS from the build host. Keep
# source names legal there too; this does NOT add a global path-length limit.
WINDOWS_RESERVED = {"CON", "PRN", "AUX", "NUL"} | {
    prefix + digit for prefix in ("COM", "LPT") for digit in "123456789¹²³"
}
WINDOWS_FORBIDDEN = set('<>:"\\|?*')


def portable_component_error(name: str) -> str | None:
    """Return the first portability issue for one component, not a full path."""
    if any(ch in WINDOWS_FORBIDDEN for ch in name):
        return "reserved character"
    if name.endswith((".", " ")):
        return "trailing period or space"
    if name.split(".", 1)[0].upper() in WINDOWS_RESERVED:
        return "reserved device name"
    return None


def validate(root: Path) -> list[str]:
    root = root.resolve()
    errors: list[str] = []
    if not root.is_dir():
        return [f"package root is not a directory: {root}"]
    portable_names: dict[str, str] = {}
    for path in sorted(root.rglob("*"), key=lambda p: p.as_posix()):
        rel = path.relative_to(root).as_posix()
        if any(ord(ch) < 32 or ord(ch) == 127 for ch in rel):
            errors.append(f"control character in path: {rel!r}")
        key = unicodedata.normalize("NFC", rel).casefold()
        previous = portable_names.get(key)
        if previous is not None and previous != rel:
            errors.append(f"case/Unicode-colliding paths: {previous!r} vs {rel!r}")
        else:
            portable_names[key] = rel
        portability_error = portable_component_error(path.name)
        if portability_error:
            errors.append(f"nonportable path ({portability_error}): {rel!r}")
        lower = path.name.lower()
        if lower in VCS_NAMES:
            errors.append(f"version-control metadata must not ship: {rel}")
        if lower in SECRET_NAMES or lower.startswith(".env.") or any(lower.endswith(x) for x in SECRET_SUFFIXES):
            errors.append(f"credential-like file must not ship: {rel}")
        if any(lower.endswith(x) for x in OPAQUE_SUFFIXES):
            errors.append(f"opaque or nested archive must not ship: {rel}")
        if path.is_symlink():
            errors.append(f"symlink not allowed in standalone package: {rel}")
            continue
        try:
            mode = path.stat().st_mode
        except OSError as exc:
            errors.append(f"cannot stat {rel}: {exc}")
            continue
        if path.is_dir():
            if path.name in BAD_DIRS:
                errors.append(f"cache directory must not ship: {rel}")
            continue
        if not stat.S_ISREG(mode):
            errors.append(f"non-regular file must not ship: {rel}")
            continue
        name = path.name
        lower = name.lower()
        if name in BAD_EXACT or any(lower.endswith(x) for x in BAD_ENDINGS):
            errors.append(f"artifact must not ship: {rel}")
            continue
        if any(lower.endswith(suffix) for suffix in BAD_SUFFIXES):
            # Text fixtures intentionally encode logs as *.log.txt, never *.log.
            errors.append(f"generated build artifact must not ship: {rel}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    errors = validate(args.root)
    if errors:
        for error in errors:
            print(f"✗ {error}")
        return 1
    print(f"✓ package hygiene clean: {args.root.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
