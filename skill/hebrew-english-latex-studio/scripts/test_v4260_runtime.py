#!/usr/bin/env python3
"""v4.26.0 real-engine controls for BLD-69 and BLD-70.

Every managed build here is preceded by a raw-engine PRECONDITION, so a later
TeX Live that behaves differently turns these tests red instead of vacuously
green: the fatal compiles really write no runtime font inventory, and the
stale contour files really are read by a compile into -output-directory.

Set HLLPDF_4260_EVIDENCE_DIR to a NEW directory outside the skill to retain the
sources, logs and gate output.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
from font_paths import font_dir

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "scripts" / "build.sh"
STOPPED = "the compile stopped before the end of the document"


def document(body: str) -> str:
    return "\\input{preamble.tex}\n\\begin{document}\nשלום.\n" + body + "\n\\end{document}\n"


def contour_plot(key: str) -> str:
    return ("\\begin{tikzpic}\n\\begin{tikzpicture}\n"
            "\\begin{axis}[view={0}{90},width=6cm]\n"
            f"\\addplot3[{key}, domain=-2:2, samples=21] {{x^2+y^2}};\n"
            "\\end{axis}\n\\end{tikzpicture}\n\\end{tikzpic}\n"
            "\\figcap{\\label{fig:c}קווי גובה}")


def digest(paths) -> str:
    h = hashlib.sha256()
    for path in sorted(paths):
        h.update(path.name.encode() + b"\0" + path.read_bytes())
    return h.hexdigest()


class EngineControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        chosen = os.environ.get("HLLPDF_4260_EVIDENCE_DIR")
        if chosen:
            cls.root = Path(chosen).resolve()
            if cls.root == ROOT or ROOT in cls.root.parents:
                raise ValueError("evidence must live outside the skill")
            cls.root.mkdir(parents=True, exist_ok=False)
        else:
            cls.temp = tempfile.TemporaryDirectory(prefix="hllpdf4260-runtime-")
            cls.root = Path(cls.temp.name)
        fonts = font_dir()
        cls.env = {k: v for k, v in os.environ.items()
                   if k not in {"HEBREW_LATEX_PROJECT_ROOT", "REPRO"}}
        cls.env.update({"HEBREW_LATEX_FONT_DIR": str(fonts), "TTFONTS": f"{fonts}:",
                        "OSFONTDIR": f"{fonts}:", "SOURCE_DATE_EPOCH": "1700000000",
                        "TZ": "UTC", "PYTHONDONTWRITEBYTECODE": "1"})

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "temp"):
            cls.temp.cleanup()

    def project(self, name: str, source: str) -> Path:
        d = self.root / name
        d.mkdir()
        shutil.copyfile(ROOT / "assets" / "preamble.tex", d / "preamble.tex")
        (d / "doc.tex").write_text(source, encoding="utf-8")
        return d

    def raw(self, d: Path, output_directory: bool):
        args = ["lualatex", "--no-shell-escape", "-interaction=nonstopmode", "-halt-on-error"]
        if output_directory:
            (d / "out").mkdir(exist_ok=True)
            args.append("-output-directory=out")
        p = subprocess.run(args + ["doc.tex"], cwd=d, env=self.env, text=True,
                           capture_output=True, timeout=180)
        log = (d / "out" / "doc.log") if output_directory else (d / "doc.log")
        return p.returncode, log.read_text(encoding="utf-8", errors="replace")

    def gate(self, d: Path):
        p = subprocess.run(["bash", str(BUILD), "doc.tex"], cwd=d, env=self.env,
                           text=True, capture_output=True, timeout=600)
        (d / "gate.out").write_text(p.stdout + p.stderr, encoding="utf-8")
        return p.returncode, p.stdout + p.stderr

    def assert_in_order(self, output: str, *needles: str):
        positions = []
        for needle in needles:
            self.assertIn(needle, output)
            positions.append(output.index(needle))
        self.assertEqual(positions, sorted(positions), needles)

    # ---- BLD-69 --------------------------------------------------------------
    def fatal_case(self, name: str, body: str, *record: str):
        d = self.project(name, document(body))
        rc, log = self.raw(d, output_directory=True)
        self.assertNotEqual(rc, 0, "precondition: the document must halt the engine")
        self.assertNotIn("HLLFONT|BEGIN", log, "precondition: a halted run writes no inventory")
        shutil.rmtree(d / "out")
        rc, out = self.gate(d)
        self.assertEqual(rc, 1, out)
        self.assert_in_order(out, "▶ pass 1", "✗ lualatex exited 1 on pass 1: " + STOPPED,
                             *record, "✗ runtime fonts: missing runtime font inventory: " + STOPPED,
                             "after the compile error above. BUILD NOT OK.")
        self.assertNotIn("synchronize preamble.tex", out)
        self.assertTrue((d / "doc.failed.log").is_file(), "the failing log must be preserved")

    def test_01_undefined_macro_is_named_before_the_inventory(self):
        self.fatal_case("undefined", "\\undefinedmacroxyz",
                        "│ ! Undefined control sequence.", "│ l.4 \\undefinedmacroxyz")

    def test_02_failed_lua_require_is_named_before_the_inventory(self):
        self.fatal_case("require", '\\directlua{require("no_such_module_xyz")}',
                        "│ [\\directlua]:1: module 'no_such_module_xyz' not found:",
                        '│ l.4 \\directlua{require("no_such_module_xyz")}')

    def test_03_an_empty_document_is_not_a_preamble_problem(self):
        d = self.project("empty", "\\input{preamble.tex}\n\\begin{document}\n\\end{document}\n")
        rc, log = self.raw(d, output_directory=True)
        self.assertEqual(rc, 0, "precondition: an empty document compiles")
        self.assertIn("no pages of output", log)
        self.assertNotIn("HLLFONT|BEGIN", log)
        rc, out = self.gate(d)
        self.assertEqual(rc, 1, out)
        self.assertIn("✗ runtime fonts: missing runtime font inventory: the run produced no pages", out)
        self.assertNotIn("synchronize preamble.tex", out)

    # ---- BLD-70 --------------------------------------------------------------
    def test_04_a_stale_lua_module_never_reaches_the_engine(self):
        d = self.project("stale-lua", document(contour_plot("contour lua={levels={1,2}}")))
        rc, _ = self.raw(d, output_directory=False)
        self.assertEqual(rc, 0, "precondition: a plain compile in the source directory works")
        old = (d / "doc_contourtmp0.table").read_bytes()
        (d / "doc.tex").write_text(document(contour_plot("contour lua={levels={3}}").replace(
            "{x^2+y^2}", "{x^2+4*y^2}")), encoding="utf-8")
        rc, _ = self.raw(d, output_directory=True)
        self.assertEqual(rc, 0, "precondition: the stale module is found and the compile passes")
        self.assertEqual((d / "doc_contourtmp0.table").read_bytes(), old,
                         "precondition: the new function was contoured from the OLD data")
        before = digest(d.glob("doc_contourtmp0.*"))
        rc, out = self.gate(d)
        self.assertEqual(rc, 1, out)
        self.assertIn("[PGFPLOTS-CONTOUR-EXTERNAL]", out)
        self.assertIn("'contour lua'", out)
        self.assertNotIn("▶ pass 1", out)
        self.assertEqual(digest(d.glob("doc_contourtmp0.*")), before,
                         "a rejected build must not touch the source directory")

    def test_05_a_stale_gnuplot_table_never_reaches_the_engine(self):
        d = self.project("stale-gnuplot", document(contour_plot("contour gnuplot={levels={1,2}}")))
        rows = [f"{1.5 * c:.4f} {1.5 * s:.4f} 2.25" for c, s in
                [(1, 0), (0.7071, 0.7071), (0, 1), (-0.7071, 0.7071), (-1, 0),
                 (-0.7071, -0.7071), (0, -1), (0.7071, -0.7071), (1, 0)]]
        (d / "doc_contourtmp0.table").write_text("\n".join(rows) + "\n\n", encoding="utf-8")
        rc, log = self.raw(d, output_directory=True)
        self.assertEqual(rc, 0, "precondition: shell escape is off and the old table is read")
        self.assertIn("PGFPlots: reading {doc_contourtmp0.table}", log)
        shutil.rmtree(d / "out")
        rc, out = self.gate(d)
        self.assertEqual(rc, 1, out)
        self.assertIn("'contour gnuplot'", out)
        self.assertNotIn("▶ pass 1", out)
        self.assertFalse((d / "doc.pdf").exists(), "nothing may be published")

    def test_06_precomputed_and_tex_drawn_contours_build_clean(self):
        prepared = ("\\begin{tikzpic}\n\\begin{tikzpicture}\n"
                    "\\begin{axis}[view={0}{90},width=6cm]\n"
                    "\\addplot3[contour prepared] table {\n1 0 1\n0 1 1\n-1 0 1\n0 -1 1\n1 0 1\n};\n"
                    "\\end{axis}\n\\end{tikzpicture}\n\\end{tikzpic}\n"
                    "\\figcap{\\label{fig:p}קו גובה מחושב מראש}")
        filled = contour_plot("contour filled={number=4}")
        d = self.project("negatives", document(prepared + "\n\n" + filled))
        rc, out = self.gate(d)
        self.assertEqual(rc, 0, out)
        self.assertIn("✓ clean build", out)
        self.assertEqual(list(d.glob("doc_contourtmp*")), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
