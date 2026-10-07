#!/usr/bin/env python3
"""Exercise real harness failure reporting and project scope without TeX."""
from __future__ import annotations

from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
HARNESS = ROOT / "scripts" / "test_all.sh"


def codebox_block() -> str:
    text = HARNESS.read_text(encoding="utf-8")
    start = text.index('echo "═══ T3f:')
    end = text.index('echo "═══ T4:', start)
    return text[start:end]


def failed_builder(block: str) -> subprocess.CompletedProcess[str]:
    # Source the actual harness section; intercept only its builder process.
    # This keeps reporting, branch selection and environment passing real.
    header = """set -uo pipefail
PASS=0
FAIL=0
ok() { printf 'OK: %s\\n' "$*"; PASS=$((PASS+1)); }
bad() { printf 'BAD: %s\\n' "$*"; FAIL=$((FAIL+1)); }
bash() { printf 'BUILDROOT=%s\\n' "$HEBREW_LATEX_PROJECT_ROOT" >> "$ROOT_REPORT"; return 1; }
"""
    with tempfile.TemporaryDirectory(prefix="studio-harness-scope-") as temp:
        report = Path(temp) / "builder-roots.txt"
        script = "ROOT_REPORT=" + shlex.quote(str(report)) + "\n" + header
        script += "SKILL_ROOT=" + shlex.quote(str(ROOT)) + "\nif :; then\n"
        script += block + "\nprintf 'COUNTS=%s,%s\\n' \"$PASS\" \"$FAIL\"\n"
        result = subprocess.run(["bash"], input=script, cwd=ROOT, text=True,
                                capture_output=True, timeout=10)
        # The harness suppresses builder stdout, so observe its real invocation
        # through the separate record made by the intercepted builder function.
        if report.exists():
            result.stdout += report.read_text(encoding="utf-8")
        return result


def report_errors(result: subprocess.CompletedProcess[str]) -> list[str]:
    errors = []
    if result.returncode:
        errors.append("harness section did not complete")
    roots = [line.removeprefix("BUILDROOT=") for line in result.stdout.splitlines()
             if line.startswith("BUILDROOT=")]
    if roots != [str(ROOT)]:
        errors.append("builder project root includes unrelated siblings")
    if "COUNTS=0,4" not in result.stdout or result.stdout.count("BAD: ") != 4:
        errors.append("failed prerequisite did not report all four controls")
    return errors


class HarnessControls(unittest.TestCase):
    def test_failed_base_build_reports_every_control_at_the_correct_root(self):
        result = failed_builder(codebox_block())
        self.assertEqual(report_errors(result), [], result.stdout + result.stderr)

    def test_parent_scope_regression_is_detected(self):
        block = codebox_block()
        target = 'HEBREW_LATEX_PROJECT_ROOT="$SKILL_ROOT"'
        self.assertIn(target, block)
        mutant = block.replace(target, 'HEBREW_LATEX_PROJECT_ROOT="$(cd .. && pwd)"', 1)
        result = failed_builder(mutant)
        self.assertIn("builder project root includes unrelated siblings", report_errors(result))

    def test_withheld_style_control_cannot_disappear_from_reporting(self):
        block = codebox_block()
        lines = block.splitlines(keepends=True)
        targets = [line for line in lines if 'bad "codebox_numbers.tex did not build' in line
                   and "four-style control" in line]
        self.assertEqual(len(targets), 1)
        result = failed_builder(block.replace(targets[0], "", 1))
        self.assertIn("failed prerequisite did not report all four controls", report_errors(result))


if __name__ == "__main__":
    unittest.main()
