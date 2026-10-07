#!/usr/bin/env python3
"""Hash a recorder manifest of project-local inputs by relative path + bytes."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import sys

sys.dont_write_bytecode = True


def manifest_hash(manifest: Path, project_root: Path) -> str:
    project_root = project_root.resolve(strict=True)
    if not project_root.is_dir():
        raise ValueError(f"project root is not a directory: {project_root}")
    if not manifest.is_file():
        raise ValueError(f"manifest does not exist: {manifest}")
    try:
        raw_lines = manifest.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise ValueError(f"manifest is not UTF-8: {manifest}: {exc}") from exc

    paths: set[Path] = set()
    for raw in raw_lines:
        if not raw:
            continue
        path = Path(raw).resolve()
        try:
            path.relative_to(project_root)
        except ValueError as exc:
            raise ValueError(f"project input escaped root: {path}") from exc
        if not path.is_file():
            raise ValueError(f"project input disappeared during build: {path}")
        paths.add(path)
    if not paths:
        raise ValueError("project input manifest is empty")

    h = hashlib.sha256()
    for path in sorted(paths, key=lambda p: p.relative_to(project_root).as_posix()):
        rel = path.relative_to(project_root).as_posix().encode("utf-8")
        data = path.read_bytes()
        h.update(len(rel).to_bytes(8, "big"))
        h.update(rel)
        h.update(len(data).to_bytes(8, "big"))
        h.update(data)
    return h.hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--project-root", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        print(manifest_hash(args.manifest, args.project_root))
    except (OSError, ValueError) as exc:
        print(f"project-input hash failed: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
