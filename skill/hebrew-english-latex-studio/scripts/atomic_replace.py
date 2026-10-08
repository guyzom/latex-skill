#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Original project code; scope and terms: ../LICENSING.md.
"""Atomically replace a destination with the bytes of a regular source file.

The temporary file is created in the destination directory so os.replace stays
on one filesystem. Existing destination symlinks are replaced as directory
entries; they are never followed.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import stat
import sys
import tempfile

sys.dont_write_bytecode = True


def atomic_replace(source: Path, destination: Path) -> None:
    source_arg = source.absolute()
    if source_arg.is_symlink():
        raise ValueError(f"source must not be a symlink: {source_arg}")
    source = source_arg.resolve(strict=True)
    try:
        st = source.stat()
    except OSError as exc:
        raise ValueError(f"cannot stat source: {source}: {exc}") from exc
    if not stat.S_ISREG(st.st_mode):
        raise ValueError(f"source must be a regular file: {source}")

    destination = destination.absolute()
    parent = destination.parent
    if not parent.is_dir():
        raise ValueError(f"destination parent is not a directory: {parent}")

    fd, raw_temp = tempfile.mkstemp(prefix=f".{destination.name}.tmp.", dir=parent)
    temp = Path(raw_temp)
    try:
        with os.fdopen(fd, "wb", closefd=True) as out, source.open("rb") as inp:
            shutil.copyfileobj(inp, out, length=1024 * 1024)
            out.flush()
            os.fsync(out.fileno())
            os.fchmod(out.fileno(), stat.S_IMODE(st.st_mode))
        os.replace(temp, destination)
        # Persist the directory-entry replacement where the platform permits it.
        try:
            dfd = os.open(parent, os.O_RDONLY)
        except OSError:
            dfd = None
        if dfd is not None:
            try:
                os.fsync(dfd)
            except OSError:
                pass
            finally:
                os.close(dfd)
    finally:
        try:
            temp.unlink()
        except FileNotFoundError:
            pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args(argv)
    try:
        atomic_replace(args.source, args.destination)
    except (OSError, ValueError) as exc:
        print(f"atomic replace failed: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
