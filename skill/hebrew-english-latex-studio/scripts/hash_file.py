#!/usr/bin/env python3
"""Print a deterministic SHA-256 digest for one file.

Python 3 is already a mandatory dependency of the skill, so this tiny helper
keeps hashing portable across GNU/Linux and macOS without requiring the
platform-specific `sha256sum` / `shasum` command names.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import sys


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", help="file to hash")
    args = parser.parse_args(argv)
    path = Path(args.file)
    try:
        print(sha256_file(path))
    except OSError as exc:
        print(f"hash_file: cannot read {path}: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
