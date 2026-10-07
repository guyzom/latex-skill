#!/usr/bin/env python3
"""v5.4.1 harness controls: a routine FULL run declares itself, never implicitly.

v5.4.0 adds a catalog visual RELEASE gate to FULL, inside the catalog block
(the first of the two T1j3 banners, before T1j2), early in the run. It passes
only on sealed evidence of a human review of every primary catalog page, bound
to the exact candidate archive and to the reviewing machine's tool binaries, so
a CI runner can never hold it and every routine FULL run was red. A run that is not
a release now says so with HEBREW_LATEX_CATALOG_VISUAL=routine: that one gate
is left out, the size check expects one check fewer, and nothing else changes.
Without the declaration the delivered behaviour stands, and evidence, when
given, is always verified. These tests source the actual harness sections and
intercept only python3, as test_harness_controls does.
"""
from __future__ import annotations

from pathlib import Path
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parent.parent
HARNESS = ROOT / "scripts" / "test_all.sh"
EVIDENCE_VARS = ("HEBREW_LATEX_CATALOG_MATRIX_EVIDENCE", "HEBREW_LATEX_CATALOG_CANDIDATE_SHA")


def section(start_marker: str, end_marker: str) -> str:
    text = HARNESS.read_text(encoding="utf-8")
    start = text.index(start_marker)
    return text[start:text.index(end_marker, start + len(start_marker))]


def catalog_block() -> str:
    return section('echo "═══ T1j3: canonical studio catalog', 'echo "═══')


def size_block() -> str:
    return section("EXPECTED_FULL=", 'echo "  $PASS passed')


def run_bash(script: str, env: dict[str, str]) -> str:
    clean = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", **env}
    result = subprocess.run(["bash"], input=script, cwd=ROOT, text=True, env=clean,
                            capture_output=True, timeout=10)
    return result.stdout + result.stderr


def run_catalog(**env: str) -> tuple[str, list[str]]:
    script = """set -uo pipefail
PASS=0
FAIL=0
HARNESS_TMP=$(mktemp -d)
ok() { printf 'OK: %s\\n' "$*"; PASS=$((PASS+1)); }
bad() { printf 'BAD: %s\\n' "$*"; FAIL=$((FAIL+1)); }
# The harness sends checker output to its logs, so record the invocation apart.
python3() { case "$*" in *test_studio_matrix.py*) echo "VERIFY: $*" >> "$HARNESS_TMP/verify";; esac; return 0; }
""" + catalog_block() + """
cat "$HARNESS_TMP/verify" 2>/dev/null
printf 'COUNTS=%s,%s ROUTINE=%s\\n' "$PASS" "$FAIL" "${CATALOG_ROUTINE:-0}"
rm -rf "$HARNESS_TMP"
"""
    out = run_bash(script, env)
    return out, re.findall(r"^(OK|BAD|VERIFY): ", out, re.MULTILINE)


def run_size(passed: int, *, routine: bool, fast: bool = False) -> str:
    script = (f"PASS={passed}\nFAIL=0\nCATALOG_ROUTINE={int(routine)}\n"
              + ("FAST=1\n" if fast else "") + size_block()
              + "\nprintf 'FAIL=%s\\n' \"$FAIL\"\n")
    return run_bash(script, {})


def expected(name: str) -> int:
    return int(re.search(rf"^{name}=(\d+)$", HARNESS.read_text(encoding="utf-8"), re.M).group(1))


class RoutineCatalogTests(unittest.TestCase):
    def test_01_routine_without_evidence_leaves_only_the_visual_gate_out(self):
        out, marks = run_catalog(HEBREW_LATEX_CATALOG_VISUAL="routine")
        self.assertNotIn("BAD", marks, out)
        self.assertNotIn("VERIFY", marks, out)
        self.assertEqual(marks.count("OK"), 8, out)      # 7 static + topic-rail runtime
        self.assertIn("ROUTINE=1", out)
        self.assertIn("not a release", out)

    def test_02_no_declaration_keeps_the_delivered_failure(self):
        out, marks = run_catalog()
        self.assertEqual(marks.count("BAD"), 1, out)
        self.assertIn("requires HEBREW_LATEX_CATALOG_MATRIX_EVIDENCE", out)
        self.assertIn("ROUTINE=0", out)

    def test_03_an_unknown_declaration_is_rejected(self):
        for value in ("yes", "Routine", "skip"):
            with self.subTest(value=value):
                out, marks = run_catalog(HEBREW_LATEX_CATALOG_VISUAL=value)
                self.assertEqual(marks.count("BAD"), 1, out)
                self.assertNotIn("VERIFY", marks, out)
                self.assertIn("ROUTINE=0", out)

    def test_04_partial_evidence_still_fails_under_routine(self):
        for var in EVIDENCE_VARS:
            with self.subTest(given=var):
                out, marks = run_catalog(HEBREW_LATEX_CATALOG_VISUAL="routine", **{var: "x"})
                self.assertEqual(marks.count("BAD"), 1, out)
                self.assertIn("ROUTINE=0", out)

    def test_05_evidence_is_verified_with_or_without_the_declaration(self):
        evidence = {EVIDENCE_VARS[0]: "/evidence", EVIDENCE_VARS[1]: "a" * 64}
        for declared in ({}, {"HEBREW_LATEX_CATALOG_VISUAL": "routine"}):
            with self.subTest(declared=bool(declared)):
                out, marks = run_catalog(**evidence, **declared)
                self.assertIn("VERIFY", marks, out)
                self.assertIn("--require-visual", out)
                self.assertNotIn("BAD", marks, out)
                self.assertIn("ROUTINE=0", out)


class RoutineSizeTests(unittest.TestCase):
    def test_06_routine_expects_exactly_one_check_fewer(self):
        full = expected("EXPECTED_FULL")
        self.assertIn("FAIL=0", run_size(full - 1, routine=True))
        self.assertIn("FAIL=1", run_size(full, routine=True))
        self.assertIn("FAIL=1", run_size(full - 1, routine=False))
        self.assertIn("FAIL=0", run_size(full, routine=False))

    def test_07_fast_is_unaffected(self):
        fast = expected("EXPECTED_FAST")
        self.assertIn("FAIL=0", run_size(fast, routine=False, fast=True))
        self.assertIn("FAIL=1", run_size(fast - 1, routine=False, fast=True))


if __name__ == "__main__":
    unittest.main(verbosity=2)
