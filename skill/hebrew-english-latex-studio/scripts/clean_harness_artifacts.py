#!/usr/bin/env python3
"""Remove the build artifacts the test harness writes into the package tree.

WHY THIS EXISTS (DEFECTS BLD-58). test_all.sh compiles the twelve bundled
examples into assets/example_*.pdf and twenty-eight fixtures into tests/, then
leaves them there. Those files are gitignored, so `git status` stays clean and
nothing looks wrong -- but scripts/package_skill.py selects files with
rglob("*") and is NOT git-aware, so a leftover PDF really would ship inside the
.skill zip. check_package_hygiene.py is right to reject them. The trouble is
WHEN it runs: T2d7 sits early in the harness, so a second consecutive local run
fails two checks (T2d7 and T2d8) on debris the FIRST run created. Measured: a
clean tree gives 163 passed / 0 failed; rerunning immediately on the same tree
gives 161 passed / 2 failed, with an identical 40-file artifact set both times.
CI never sees it -- it runs on a fresh clone -- so the false red lands on
exactly one person: whoever reruns the harness to verify a fix.

THE TARGET SET IS DERIVED, NOT RETYPED. This module imports BAD_SUFFIXES,
BAD_ENDINGS and BAD_EXACT from check_package_hygiene, so it removes precisely
what that gate rejects -- no more, and never a shape the gate tolerates. Two
consequences worth stating, because both are load-bearing:

  * On a pristine checkout this script is a NO-OP. Every tracked file must
    already pass the hygiene gate, or a fresh clone would fail CI; a file the
    gate accepts is therefore a file this script cannot touch. That is what
    makes it safe to run unconditionally, and test_harness_cleanup.py asserts
    it rather than trusting the argument.
  * The tests/*.log.txt evidence files (tex_errors_dump.log.txt,
    tex_errors_real.log.txt) survive for the same reason the gate passes them:
    ".txt" is not a rejected suffix. That naming convention -- recorded in
    AGENTS.md -- is what keeps permanent evidence out of a ".log" sweep, and
    deriving the set instead of globbing "*.log*" is what honours it.

SCOPE IS DELIBERATELY NARROW. Only assets/ and tests/ are walked: those are the
two directories the harness compiles into. scripts/, references/ and the
package root are left alone even when they hold a rejected shape, because
debris there was not put there by the harness and silently deleting a user's
file is not this script's business -- the hygiene gate should report it.

__pycache__ is NOT handled here and needs no handling: test_all.sh and build.sh
both `export PYTHONDONTWRITEBYTECODE=1`, the release contract enforces that they
keep doing so, and every checker that imports a sibling sets
`sys.dont_write_bytecode = True` for direct invocation. Measured across every
package entrypoint: zero .pyc files produced.
"""
import sys as _bytecode_sys
_bytecode_sys.dont_write_bytecode = True

import argparse
import os
from pathlib import Path
import stat
import sys

from check_package_hygiene import BAD_ENDINGS, BAD_EXACT, BAD_SUFFIXES

ROOT = Path(__file__).resolve().parent.parent
# The only directories the harness compiles into. Keep this list honest: a new
# fixture directory needs adding here AND in test_harness_cleanup.py's planted
# set, or its debris starts failing the next run all over again.
HARNESS_DIRS = ("assets", "tests")


def is_generated(path: Path) -> bool:
    """True when check_package_hygiene.py would reject this file by name."""
    name = path.name
    lower = name.lower()
    if name in BAD_EXACT or any(lower.endswith(end) for end in BAD_ENDINGS):
        return True
    return any(lower.endswith(suffix) for suffix in BAD_SUFFIXES)


def sweep(root: Path, dry_run: bool = False) -> list[str]:
    """Delete every harness-generated file under root; return their rel paths."""
    root = root.resolve()
    removed: list[str] = []
    for directory in HARNESS_DIRS:
        base = root / directory
        # v4.32: is_dir() alone follows a symlink at the traversal root.
        # rglob/os.walk can then visit its target even with descendant-link
        # following disabled. Reject a linked assets/ or tests/ directory,
        # including one pointing elsewhere INSIDE the selected package root.
        # Package hygiene must report it; cleanup must not "repair" its target.
        if base.is_symlink() or not base.is_dir():
            continue
        # Explicitly prune linked directories. This is not a concurrent,
        # hostile-filesystem sandbox; callers must not change the tree while
        # cleanup runs. Existing symlinks, including broken ones, remain intact.
        for parent, directories, files in os.walk(base, followlinks=False):
            parent_path = Path(parent)
            directories[:] = sorted(
                name for name in directories
                if not (parent_path / name).is_symlink()
            )
            for name in sorted(files):
                path = parent_path / name
                try:
                    mode = path.lstat().st_mode
                except OSError as exc:  # leave unreadable entries to hygiene
                    print(f"  ! could not inspect {path}: {exc}", file=sys.stderr)
                    continue
                # lstat never follows a file symlink. Also leave FIFOs/devices
                # alone: matching a suffix does not make one a generated file.
                if not stat.S_ISREG(mode) or not is_generated(path):
                    continue
                rel = path.relative_to(root).as_posix()
                if not dry_run:
                    try:
                        path.unlink()
                    except OSError as exc:  # reported; never hide a test result
                        print(f"  ! could not remove {rel}: {exc}", file=sys.stderr)
                        continue
                removed.append(rel)
    return sorted(removed)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Remove harness build artifacts.")
    parser.add_argument("root", nargs="?", type=Path, default=ROOT)
    parser.add_argument("--dry-run", action="store_true",
                        help="list what would be removed, delete nothing")
    parser.add_argument("--quiet", action="store_true",
                        help="print the count only (used by the harness trap)")
    args = parser.parse_args(argv)
    removed = sweep(args.root, dry_run=args.dry_run)
    verb = "would remove" if args.dry_run else "removed"
    if not args.quiet:
        for rel in removed:
            print(f"  {verb} {rel}")
    print(f"✓ harness artifacts: {verb} {len(removed)} file(s)")
    # Cleanup never fails a run. A harness that dies in its own trap would hide
    # the result it was about to report, which is strictly worse than debris.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
