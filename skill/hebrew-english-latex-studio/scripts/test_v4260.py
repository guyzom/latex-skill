#!/usr/bin/env python3
"""v4.26.0 static contracts — no LuaLaTeX process.

BLD-69: a pass that fails is NAMED — its error record and TeX's l.N line —
before the recorded-source gate runs, and a missing runtime font inventory
says why it is missing. BLD-70: compile-time pgfplots contours are rejected
by the source hazard gate before the engine starts.

Evidence is canned (tests/tex_errors_ctx_*.log.txt are tails of real logs),
and build.sh itself is driven against a MOCK engine, so the ordering of what
it prints is asserted without a TeX installation.
"""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
import check_runtime_fonts as fonts
import check_source_hazards as hazards
from font_paths import font_dir

ROOT = Path(__file__).resolve().parent.parent
TESTS = ROOT / "tests"
BUILD = ROOT / "scripts" / "build.sh"
ERRLINES = ROOT / "scripts" / "tex_error_lines.sh"
CTX_LOGS = sorted(TESTS.glob("tex_errors_ctx_*.log.txt"))
STOPPED = "the compile stopped before the end of the document"
SYNC = "missing runtime font inventory; synchronize preamble.tex"


def context(log: Path, script: Path = ERRLINES) -> str:
    proc = subprocess.run(["bash", str(script), "--context", str(log)],
                          text=True, capture_output=True, check=True)
    return proc.stdout


class InventoryReason(unittest.TestCase):
    """The verdict is unchanged (still a failure); only the reason is new."""

    def test_01_every_halted_log_names_the_stop(self):
        self.assertEqual(len(CTX_LOGS), 8)
        for log in CTX_LOGS:
            with self.subTest(log=log.name):
                reason = fonts.missing_inventory_reason(log.read_text(encoding="utf-8"))
                self.assertIn(STOPPED, reason)
                self.assertNotIn("synchronize preamble.tex", reason)

    def test_02_no_pages_is_its_own_reason(self):
        reason = fonts.missing_inventory_reason(
            "warning  (pdf backend): no pages of output.\n")
        self.assertIn("the run produced no pages", reason)

    def test_03_completed_run_keeps_the_sync_advice(self):
        # The v4.22 'missing-inventory' case: a stripped preamble on a compile
        # that FINISHED. There, and only there, the old advice is right.
        self.assertEqual(fonts.missing_inventory_reason(
            "Output written on doc.pdf (1 page, 1234 bytes).\n"), SYNC)

    def test_04_a_malformed_frame_is_not_reinterpreted(self):
        with self.assertRaises(fonts.InventoryError) as caught:
            fonts.parse_inventory("!  ==> Fatal error occurred\nHLLFONT|FILE|1|1\n")
        self.assertEqual(str(caught.exception), SYNC)

    def test_05_halted_log_still_fails(self):
        text = (TESTS / "tex_errors_ctx_undefined.log.txt").read_text(encoding="utf-8")
        with self.assertRaises(fonts.InventoryError) as caught:
            fonts.parse_inventory(text)
        self.assertIn(STOPPED, str(caught.exception))

    def test_06_cli_prints_the_reason(self):
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "check_runtime_fonts.py"),
             str(TESTS / "tex_errors_ctx_lua_require.log.txt")],
            text=True, capture_output=True)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("✗ runtime fonts: missing runtime font inventory: " + STOPPED, proc.stdout)


class ContextRecords(unittest.TestCase):
    """Every branch of the record finder is load-bearing for a real log."""

    def test_07_default_mode_is_the_old_count(self):
        real = subprocess.run(["bash", str(ERRLINES), str(TESTS / "tex_errors_real.log.txt")],
                              text=True, capture_output=True, check=True).stdout
        dump = subprocess.run(["bash", str(ERRLINES), str(TESTS / "tex_errors_dump.log.txt")],
                              text=True, capture_output=True, check=True).stdout
        self.assertEqual(len(real.splitlines()), 5)
        self.assertEqual(dump, "")

    def mutated(self, anchor: str, replacement: str) -> Path:
        text = ERRLINES.read_text(encoding="utf-8")
        self.assertEqual(text.count(anchor), 1, anchor)
        path = Path(self.tmp.name) / "tex_error_lines.sh"
        path.write_text(text.replace(anchor, replacement), encoding="utf-8")
        return path

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="hllpdf4260-")

    def tearDown(self):
        self.tmp.cleanup()

    def test_08_chunk_name_opener_carries_tracebackless_lua_errors(self):
        # A Lua SYNTAX error and a callback error have no traceback: without
        # the chunk-name opener their message never reaches the record.
        for shape, message in [("lua_syntax", "unexpected symbol near '='"),
                               ("lua_callback", "cb boom")]:
            log = TESTS / f"tex_errors_ctx_{shape}.log.txt"
            self.assertIn(message, context(log))
            broken = self.mutated(
                r"return s !~ /^\t/ && s ~ /[[]\\(directlua|latelua)[]]:[0-9]+: /", "return 0")
            self.assertNotIn(message, context(log, broken))

    def test_09_traceback_anchor_carries_lua_file_errors(self):
        log = TESTS / "tex_errors_ctx_lua_file.log.txt"
        self.assertIn("./mymod.lua:2: module failure xyz", context(log))
        broken = self.mutated('if (line ~ /^stack traceback:$/ && held != "") {', "if (0) {")
        self.assertNotIn("module failure xyz", context(log, broken))

    def test_10_a_record_is_capped_but_keeps_its_base_line(self):
        log = Path(self.tmp.name) / "long.log"
        log.write_text("! Long error.\n" + "".join(f"context {i}\n" for i in range(60))
                       + "l.9 \\here\n", encoding="utf-8")
        lines = context(log).splitlines()
        self.assertEqual(lines[0], "! Long error.")
        self.assertIn("[... record truncated at 40 lines ...]", lines)
        self.assertEqual(lines[-1], "l.9 \\here")
        self.assertLessEqual(len(lines), 42)


MOCK_KPSE = """#!/bin/sh
case "$1" in
  -var-value=*) exit 0 ;;
  *.ttf) printf '%s/%s\\n' "$MOCK_FONT_DIR" "$1" ;;
  *) printf '/mock/%s\\n' "$1" ;;
esac
"""
# The mock engine replays a canned log, records what a real run would have
# read (the document and, when present, preamble.tex), counts its passes and
# exits with MOCK_RC. It writes a PDF only when told the run succeeded.
MOCK_LATEX = """#!/bin/sh
out=''
last=''
for arg in "$@"; do
  case "$arg" in -output-directory=*) out=${arg#*=} ;; esac
  last=$arg
done
stem=${last%.tex}
n=0
[ -f "$MOCK_STATE" ] && n=$(sed -n '1p' "$MOCK_STATE")
printf '%s\\n' "$((n + 1))" >"$MOCK_STATE"
cp "$MOCK_LOG" "$out/$stem.log"
printf 'INPUT %s\\n' "$MOCK_TEX" >"$out/$stem.fls"
[ -f "$MOCK_PREAMBLE" ] && printf 'INPUT %s\\n' "$MOCK_PREAMBLE" >>"$out/$stem.fls"
[ "$MOCK_RC" = 0 ] && cp "$MOCK_PDF" "$out/$stem.pdf"
exit "$MOCK_RC"
"""


class MockEngine(unittest.TestCase):
    """build.sh against a mock engine: what is printed, and in what order."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="hllpdf4260-mock-")
        self.project = Path(self.tmp.name) / "project"
        self.project.mkdir()
        bin_dir = Path(self.tmp.name) / "bin"
        bin_dir.mkdir()
        for name, body in [("kpsewhich", MOCK_KPSE), ("lualatex", MOCK_LATEX)]:
            (bin_dir / name).write_text(body, encoding="utf-8")
            (bin_dir / name).chmod(0o755)
        self.state = Path(self.tmp.name) / "passes"
        self.pdf = Path(self.tmp.name) / "dummy.pdf"
        self.pdf.write_bytes(b"%PDF-1.4\n%%EOF\n")
        self.env = {k: v for k, v in os.environ.items()
                    if k not in {"HEBREW_LATEX_PROJECT_ROOT", "REPRO"}}
        self.env.update({
            "PATH": f"{bin_dir}:{os.environ['PATH']}",
            "HEBREW_LATEX_FONT_DIR": str(font_dir()),
            "MOCK_FONT_DIR": str(font_dir()),
            "MOCK_STATE": str(self.state),
            "MOCK_PDF": str(self.pdf),
            "MOCK_PREAMBLE": str(self.project / "preamble.tex"),
        })

    def tearDown(self):
        self.tmp.cleanup()

    def build(self, body: str, *, log_text: str, rc: int, core: bool = True):
        tex = self.project / "doc.tex"
        head = "\\input{preamble.tex}\n" if core else "\\documentclass{article}\n"
        tex.write_text(head + "\\begin{document}\n" + body + "\\end{document}\n", encoding="utf-8")
        if core:
            # The canonical-core marker is what makes the inventory mandatory.
            (self.project / "preamble.tex").write_text(
                "\\def\\hllpdfcoreloaded{1}\n\\documentclass{article}\n", encoding="utf-8")
        log = Path(self.tmp.name) / "canned.log"
        log.write_text(log_text, encoding="utf-8")
        env = {**self.env, "MOCK_TEX": str(tex), "MOCK_LOG": str(log), "MOCK_RC": str(rc)}
        proc = subprocess.run(["bash", str(BUILD), str(tex)], text=True,
                              capture_output=True, env=env, timeout=300)
        passes = self.state.read_text().strip() if self.state.exists() else "0"
        return proc.returncode, proc.stdout + proc.stderr, passes

    def assert_in_order(self, output: str, *needles: str):
        positions = []
        for needle in needles:
            self.assertIn(needle, output)
            positions.append(output.index(needle))
        self.assertEqual(positions, sorted(positions), needles)

    def test_11_a_failed_pass_is_named_before_the_recorded_source_gate(self):
        canned = (TESTS / "tex_errors_ctx_lua_require.log.txt").read_text(encoding="utf-8")
        rc, out, passes = self.build(
            'שלום.\n\\directlua{require("no_such_module_xyz")}\n', log_text=canned, rc=1)
        self.assertEqual((rc, passes), (1, "1"), out)
        self.assert_in_order(
            out, "▶ pass 1", "✗ lualatex exited 1 on pass 1: " + STOPPED,
            "[\\directlua]:1: module 'no_such_module_xyz' not found:",
            'l.4 \\directlua{require("no_such_module_xyz")}',
            "✗ runtime fonts: missing runtime font inventory: " + STOPPED,
            "✗ recorded-source gate failed on pass 1, after the compile error above.")
        self.assertNotIn("synchronize preamble.tex", out)

    def test_12_a_finished_run_without_inventory_keeps_the_sync_advice(self):
        rc, out, passes = self.build(
            "שלום.\n", log_text="Output written on doc.pdf (1 page, 10 bytes).\n", rc=0)
        self.assertEqual((rc, passes), (1, "1"), out)
        self.assertIn("✗ runtime fonts: " + SYNC, out)
        self.assertNotIn("lualatex exited", out)
        self.assertNotIn("after the compile error above", out)

    def test_13_a_repeated_failure_is_named_once(self):
        # Without the canonical core the inventory check does not apply, so the
        # pass loop keeps going; every failing pass is reported, the record once.
        canned = (TESTS / "tex_errors_ctx_undefined.log.txt").read_text(encoding="utf-8")
        rc, out, passes = self.build("x\n\\undefinedmacroxyz\n", log_text=canned,
                                     rc=1, core=False)
        self.assertEqual(rc, 1, out)
        self.assertEqual(passes, "5", out)
        self.assertEqual(out.count("│ ! Undefined control sequence."), 1, out)
        self.assertEqual(out.count("(the same error as on the previous failing pass)"), 4, out)
        self.assertIn("✗ lualatex exited non-zero (1) on the final pass", out)

    def test_14_a_missing_input_is_still_a_dependency_error(self):
        rc, out, passes = self.build("x\n\\input{no-such-file}\n", log_text="", rc=0)
        self.assertEqual((rc, passes), (1, "0"), out)
        self.assertIn("✗ source dependency graph is incomplete or unsafe.", out)
        self.assertNotIn("▶ pass 1", out)

    def test_15_compile_time_contours_never_reach_the_engine(self):
        rc, out, passes = self.build(
            "\\begin{tikzpicture}\\begin{axis}[view={0}{90}]\n"
            "\\addplot3[contour lua={levels={1,2}}, domain=-2:2] {x^2+y^2};\n"
            "\\end{axis}\\end{tikzpicture}\n", log_text="", rc=0)
        self.assertEqual((rc, passes), (1, "0"), out)
        self.assertIn("[PGFPLOTS-CONTOUR-EXTERNAL]", out)
        self.assertIn("✗ source hazard gate failed. BUILD NOT OK.", out)
        self.assertNotIn("▶ pass 1", out)


class Wiring(unittest.TestCase):
    def test_16_every_engine_run_is_reported_before_its_recorded_gate(self):
        lines = BUILD.read_text(encoding="utf-8").splitlines()
        calls = [i for i, line in enumerate(lines)
                 if "run_latex" in line and not line.lstrip().startswith("#")
                 and "run_latex()" not in line]
        self.assertEqual(len(calls), 3)  # pass 1, passes 2-5, REPRO
        for i in calls:
            window = "\n".join(lines[i:i + 4])
            self.assertIn("report_engine_failure", window, lines[i])
            self.assertLess(window.index("report_engine_failure"),
                            window.index("check_recorded_sources"), lines[i])

    def test_17_contour_rule_message_and_docs(self):
        found = hazards.contour_external_findings(
            Path("x.tex"), hazards.mask_source("\\addplot3[contour gnuplot] {x};",
                                               envs=hazards.LITERAL_ENVS))
        self.assertEqual(len(found), 1)
        self.assertIn("'contour gnuplot'", found[0].message)
        self.assertIn("Precompute", found[0].message)
        self.assertIn("contour prepared", found[0].message)
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertTrue("PGFPLOTS-CONTOUR-EXTERNAL" in skill,
                        "SKILL.md does not document PGFPLOTS-CONTOUR-EXTERNAL")


if __name__ == "__main__":
    unittest.main(verbosity=2)
