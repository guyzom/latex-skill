#!/usr/bin/env python3
"""Create a deterministic .skill archive from the standalone package tree."""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import sys
import tempfile
import subprocess
import zipfile

sys.dont_write_bytecode = True
from check_package_hygiene import validate  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FIXED_TIME = (1980, 1, 1, 0, 0, 0)


def version_of(root: Path) -> str:
    path = root / "VERSION"
    if not path.is_file():
        raise ValueError("VERSION is missing")
    version = path.read_text(encoding="utf-8").strip()
    if not version:
        raise ValueError("VERSION is empty")
    return version


def files_for(root: Path) -> list[Path]:
    return sorted((p for p in root.rglob("*") if p.is_file()), key=lambda p: p.relative_to(root).as_posix())


def mode_for(rel: str) -> int:
    if rel.startswith("scripts/") and rel.rsplit(".", 1)[-1] in {"py", "sh"}:
        return 0o755
    return 0o644


def verify_release_contract(root: Path) -> None:
    """Fail closed unless the package's own release/architecture contract passes."""
    checker = root / "scripts" / "test_release_contract.py"
    if not checker.is_file():
        raise ValueError("release contract checker is missing")
    env = __import__("os").environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        [sys.executable, str(checker)],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
        timeout=90,
    )
    if proc.returncode != 0:
        raise ValueError("release contract failed:\n" + proc.stdout.strip())


def publish_archive(temp: Path, output: Path, *, replace_existing: bool = False) -> None:
    """Publish without silent replacement; byte-identical retries are no-ops.

    Both paths are on the same filesystem: build_archive creates temp beside
    output. The default hard-link operation is an atomic create-if-absent, not
    a check-then-replace. No unsafe replacement fallback is used when a filesystem
    does not support links. Explicit replacement retains the old atomic rename
    semantics. This is a local, trusted single-writer workflow, not a registry
    of versions released elsewhere or a hostile-concurrency security boundary.
    """
    if replace_existing:
        temp.replace(output)
        return
    try:
        os.link(temp, output)
    except FileExistsError:
        # Never follow an existing output symlink, even to identical bytes.
        if not output.is_symlink() and output.is_file():
            if temp.read_bytes() == output.read_bytes():
                return
        raise ValueError(
            "output already exists with different bytes or is not a regular file; "
            "previous output preserved. Use a new VERSION/path for a release, "
            "or --replace-existing for an explicit scratch-file replacement."
        ) from None


def build_archive(root: Path, output: Path, *, replace_existing: bool = False) -> str:
    root = root.resolve()
    # Preserve the final path component: resolving an existing output symlink
    # would follow it and redirect the archive write. Default publication
    # rejects it; explicit replacement replaces the entry, not its target.
    output = output.expanduser().absolute()
    # Resolve the PARENT, not the leaf. Lexical containment misses both '..'
    # and an outside directory symlink pointing back into this source tree.
    # Resolving the leaf would instead follow an existing output symlink.
    output = output.parent.resolve() / output.name
    try:
        output.relative_to(root)
    except ValueError:
        pass
    else:
        raise ValueError("output archive must be outside the package root")
    errors = validate(root)
    if errors:
        raise ValueError("package hygiene failed:\n  " + "\n  ".join(errors))
    verify_release_contract(root)
    output.parent.mkdir(parents=True, exist_ok=True)
    # Freeze member enumeration before creating the temporary archive. Source
    # roots and output parents are trusted single-writer paths, not a sandbox.
    members = files_for(root)
    fd, raw_temp = tempfile.mkstemp(prefix=f".{output.name}.tmp.", dir=output.parent)
    __import__("os").close(fd)
    temp = Path(raw_temp)
    try:
        with zipfile.ZipFile(
            temp, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9,
            strict_timestamps=True,
        ) as zf:
            for path in members:
                rel = path.relative_to(root).as_posix()
                info = zipfile.ZipInfo(rel, FIXED_TIME)
                info.create_system = 3
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = (mode_for(rel) & 0xFFFF) << 16
                info.flag_bits |= 0x800  # UTF-8 names
                zf.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
        publish_archive(temp, output, replace_existing=replace_existing)
    finally:
        temp.unlink(missing_ok=True)
    return hashlib.sha256(output.read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--replace-existing", action="store_true",
                        help="explicitly replace a prior output; use a new version/path for releases")
    args = parser.parse_args(argv)
    try:
        version = version_of(args.root.resolve())
        output = args.output or (Path.cwd() / f"hebrew-english-latex-studio-v{version}.skill")
        digest = build_archive(args.root, output, replace_existing=args.replace_existing)
    except (OSError, ValueError) as exc:
        print(f"✗ package failed: {exc}", file=sys.stderr)
        return 2
    print(f"✓ deterministic skill archive: {output.resolve()}")
    print(f"  SHA-256 {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
