#!/usr/bin/env python3
"""Contract tests for clean_harness_artifacts.py (DEFECTS BLD-58).

Four assertions, in the order that makes each one mean something:

  1. NO-OP ON A PRISTINE TREE. Run the sweep against the real package's tracked
     shape and demand it removes nothing. This is the safety proof: the sweep
     deletes only what check_package_hygiene.py rejects, and every tracked file
     must already pass that gate or a fresh clone would fail CI -- so no source
     file is reachable. Asserted rather than argued.
  2. THE EVIDENCE FILES SURVIVE. tests/*.log.txt are permanent fixtures, and a
     naive "*.log*" sweep eats them. Planted explicitly so the convention is
     held by a test and not only by AGENTS.md prose.
  3. THE MEASURED DEBRIS GOES. Plant one file of each shape the harness really
     leaves (assets/example_*.pdf plus tests/*.{aux,log,out,pdf}) and demand the
     hygiene gate passes afterwards.
  4. NON-VACUITY. The SAME planted tree, with the sweep skipped, must FAIL the
     hygiene gate. Without this, assertion 3 would pass just as happily if the
     sweep were deleted, since a tree with nothing planted is clean either way.

A fifth assertion lives in test_release_contract.py rather than here: that
test_all.sh actually calls the sweep from its EXIT trap. A cleanup script
nothing invokes is the exact failure mode this defect is made of.
"""
import sys as _bytecode_sys
_bytecode_sys.dont_write_bytecode = True

from pathlib import Path
import shutil
import sys
import tempfile

import check_package_hygiene
from clean_harness_artifacts import sweep

ROOT = Path(__file__).resolve().parent.parent
# The shapes measured on two consecutive real harness runs (identical both
# times). Keep this list matched to HARNESS_DIRS in clean_harness_artifacts.py.
PLANTED_DEBRIS = (
    "assets/example_boxes.pdf",
    "assets/example_math.pdf",
    "tests/render_broken.aux",
    "tests/render_broken.log",
    "tests/render_broken.out",
    "tests/render_broken.pdf",
    "tests/dest_ok.pdf",
)
PLANTED_KEEPERS = (
    "tests/tex_errors_dump.log.txt",
    "tests/tex_errors_real.log.txt",
    "tests/expected_flags.txt",
    "tests/render_broken.tex",
    "assets/example_boxes.tex",
)

failures: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"  [ok ] {label}")
    else:
        print(f"  [FAIL] {label}{(': ' + detail) if detail else ''}")
        failures.append(label)


def build_tree(base: Path) -> None:
    for rel in PLANTED_KEEPERS + PLANTED_DEBRIS:
        path = base / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture\n", encoding="utf-8")


# --- 1. no-op on the real, pristine package tree -----------------------------
# Copy only what a checkout carries: the sweep must find nothing to do. Using a
# copy (not ROOT itself) keeps a buggy sweep from eating the working tree while
# still exercising the real file inventory.
pristine = Path(tempfile.mkdtemp(prefix="hllpdf-pristine."))
try:
    for directory in ("assets", "tests"):
        source = ROOT / directory
        if not source.is_dir():
            continue
        shutil.copytree(
            source,
            pristine / directory,
            ignore=lambda _d, names: [
                n for n in names
                if any(n.lower().endswith(s) for s in check_package_hygiene.BAD_SUFFIXES)
            ],
        )
    before = sorted(p for p in pristine.rglob("*") if p.is_file())
    removed_pristine = sweep(pristine)
    after = sorted(p for p in pristine.rglob("*") if p.is_file())
    check("sweep is a no-op on a pristine package tree",
          removed_pristine == [] and before == after,
          f"removed {removed_pristine}")
    check("permanent *.log.txt evidence fixtures survive a pristine sweep",
          all((pristine / rel).is_file()
              for rel in ("tests/tex_errors_dump.log.txt", "tests/tex_errors_real.log.txt")))
finally:
    shutil.rmtree(pristine, ignore_errors=True)

# --- 2. the measured debris goes, and only it --------------------------------
planted = Path(tempfile.mkdtemp(prefix="hllpdf-planted."))
try:
    build_tree(planted)
    removed = sorted(sweep(planted))
    check("sweep removes exactly the debris a real run leaves",
          removed == sorted(PLANTED_DEBRIS),
          f"removed {removed}")
    check("sweep leaves every source and evidence fixture in place",
          all((planted / rel).is_file() for rel in PLANTED_KEEPERS),
          "a keeper was deleted")
    check("hygiene gate passes on the swept tree",
          check_package_hygiene.validate(planted) == [])
finally:
    shutil.rmtree(planted, ignore_errors=True)

# --- 3. non-vacuity: without the sweep the same tree FAILS -------------------
control = Path(tempfile.mkdtemp(prefix="hllpdf-control."))
try:
    build_tree(control)
    errors = check_package_hygiene.validate(control)
    check("without the sweep the identical tree fails the hygiene gate",
          len(errors) >= len(PLANTED_DEBRIS),
          f"gate reported {len(errors)} error(s), want >= {len(PLANTED_DEBRIS)}")
finally:
    shutil.rmtree(control, ignore_errors=True)

print("-" * 72)
if failures:
    print(f"✗ harness cleanup contract: {len(failures)} assertion(s) failed")
    sys.exit(1)
print("✓ harness cleanup contract: sweep is a pristine no-op, removes the "
      "measured debris, and the gate proves it was the sweep that did it")
