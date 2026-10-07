#!/usr/bin/env python3
"""v4.27.0 real-engine controls for BLD-71.

Three documents that differ in one line on page 2, one per branch of the
evidence export: a compile that stops after page 1 has shipped (a truncated
PDF — not exported), the same document finished but failing a gate (a
readable PDF — exported, as BLD-56 requires), and a compile that stops before
any page ships (nothing to export). Every managed build is preceded by a
raw-engine PRECONDITION, so a later TeX Live that finishes, deletes or never
writes the partial file turns these tests red instead of vacuously green.

Set HLLPDF_4270_EVIDENCE_DIR to a NEW directory outside the skill to retain the
sources, logs and gate output.
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
import fitz
from font_paths import font_dir
from test_v4270 import complete_pdf

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "scripts" / "build.sh"
TRUNCATED = "no readable diagnostic PDF"
PRESERVED = "failing PDF preserved"
NOTHING = "no nonempty diagnostic PDF was produced by this failed run."
NO_OUTPUT = "no output PDF file produced"
# The T3e overfull chain: it compiles, and the margin-breaking gate rejects it.
OVERFULL = ("\\[\n\\mathrm{B}:\\ +0.009\\to-0.002\\to-0.016,\\qquad\n"
            "\\frac{k-2}{k-1}:\\ 0.750\\to0.889\\to0.947,\\qquad\n"
            "k:\\ 5\\to10\\to20\\to40\\to80 .\n\\]")


def two_pages(page_two: str) -> str:
    return ("\\input{preamble.tex}\n\\begin{document}\nעמוד ראשון.\n\\clearpage\n"
            "עמוד שני.\n" + page_two + "\n\\end{document}\n")


def poppler_pages(path: Path) -> int | None:
    p = subprocess.run(["pdfinfo", str(path)], text=True, capture_output=True, timeout=60)
    for line in p.stdout.splitlines():
        if line.startswith("Pages:"):
            return int(line.split()[1])
    return None


def mupdf_pages(path: Path) -> int:
    try:
        with fitz.open(path) as doc:
            return doc.page_count
    except Exception:  # noqa: BLE001 - an unopenable file has no pages
        return 0


class EngineControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        chosen = os.environ.get("HLLPDF_4270_EVIDENCE_DIR")
        if chosen:
            cls.root = Path(chosen).resolve()
            if cls.root == ROOT or ROOT in cls.root.parents:
                raise ValueError("evidence must live outside the skill")
            cls.root.mkdir(parents=True, exist_ok=False)
        else:
            cls.temp = tempfile.TemporaryDirectory(prefix="hllpdf4270-runtime-")
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

    def raw(self, d: Path):
        """The engine alone, in build.sh's shape: into -output-directory."""
        (d / "out").mkdir()
        p = subprocess.run(["lualatex", "--no-shell-escape", "-interaction=nonstopmode",
                            "-halt-on-error", "-output-directory=out", "doc.tex"],
                           cwd=d, env=self.env, text=True, capture_output=True, timeout=300)
        log = (d / "out" / "doc.log").read_text(encoding="utf-8", errors="replace")
        return p.returncode, log, d / "out" / "doc.pdf"

    def gate(self, d: Path):
        p = subprocess.run(["bash", str(BUILD), "doc.tex"], cwd=d, env=self.env,
                           text=True, capture_output=True, timeout=900)
        (d / "gate.out").write_text(p.stdout + p.stderr, encoding="utf-8")
        return p.returncode, p.stdout + p.stderr

    def assert_in_order(self, output: str, *needles: str):
        positions = []
        for needle in needles:
            self.assertIn(needle, output)
            positions.append(output.index(needle))
        self.assertEqual(positions, sorted(positions), needles)

    def test_01_a_stop_after_a_shipped_page_exports_no_pdf(self):
        d = self.project("stopped-on-page-two", two_pages("\\undefinedmacroxyz"))
        rc, log, left = self.raw(d)
        self.assertNotEqual(rc, 0, "precondition: the document must halt the engine")
        self.assertIn(NO_OUTPUT, log, "precondition: the engine declares no output")
        self.assertTrue(left.is_file() and left.stat().st_size > 0,
                        "precondition: the engine leaves a nonempty file in -output-directory")
        self.assertIsNone(poppler_pages(left), "precondition: Poppler cannot open that file")
        self.assertEqual(mupdf_pages(left), 0, "precondition: MuPDF finds no page in it")
        shutil.rmtree(d / "out")
        # The engine unlinks CWD/doc.pdf when it stops; build.sh restores it.
        # cleanup() changed, so the earlier deliverable must still come back.
        prior = complete_pdf(1)
        (d / "doc.pdf").write_bytes(prior)
        (d / "doc.failed.pdf").write_bytes(b"stale diagnostic from an earlier failure\n")
        rc, out = self.gate(d)
        self.assertEqual(rc, 1, out)
        self.assert_in_order(out, "✗ lualatex exited 1 on pass 1", "l.6 \\undefinedmacroxyz",
                             "── full log preserved:", TRUNCATED, "is from an EARLIER run")
        self.assertNotIn(PRESERVED, out)
        self.assertFalse((d / "doc.failed.pdf").exists(), "stale or truncated evidence survived")
        self.assertIn(NO_OUTPUT, (d / "doc.failed.log").read_text(encoding="utf-8",
                                                                   errors="replace"))
        self.assertTrue((d / "doc.failed.aux").is_file(), "the failing aux must be preserved")
        self.assertEqual((d / "doc.pdf").read_bytes(), prior, "the earlier deliverable changed")

    def test_02_the_finished_twin_failing_a_gate_exports_a_readable_pdf(self):
        d = self.project("finished-overfull", two_pages(OVERFULL))
        rc, log, left = self.raw(d)
        self.assertEqual(rc, 0, "precondition: the twin must compile to the end")
        self.assertEqual(poppler_pages(left), 2, "precondition: the engine finished both pages")
        shutil.rmtree(d / "out")
        rc, out = self.gate(d)
        self.assertEqual(rc, 1, out)
        self.assertIn("MARGIN-BREAKING", out)
        self.assertIn(PRESERVED, out)
        self.assertNotIn(TRUNCATED, out)
        exported = d / "doc.failed.pdf"
        self.assertEqual(poppler_pages(exported), 2)
        self.assertEqual(mupdf_pages(exported), 2)
        render = subprocess.run(["pdftoppm", "-png", "-r", "40", "-f", "2", "-l", "2",
                                 str(exported), str(d / "page")],
                                capture_output=True, timeout=120)
        self.assertEqual(render.returncode, 0, render.stderr)
        self.assertTrue(list(d.glob("page*.png")), "page 2 of the evidence did not render")

    def test_03_a_stop_before_any_page_leaves_nothing_to_export(self):
        d = self.project("stopped-on-page-one",
                         "\\input{preamble.tex}\n\\begin{document}\n\\undefinedmacroxyz\n"
                         "\\end{document}\n")
        rc, log, left = self.raw(d)
        self.assertNotEqual(rc, 0, "precondition: the document must halt the engine")
        self.assertFalse(left.is_file() and left.stat().st_size > 0,
                         "precondition: no page shipped, so no nonempty file is left")
        shutil.rmtree(d / "out")
        (d / "doc.failed.pdf").write_bytes(b"stale diagnostic from an earlier failure\n")
        rc, out = self.gate(d)
        self.assertEqual(rc, 1, out)
        self.assertIn(NOTHING, out)
        self.assertNotIn(TRUNCATED, out)
        self.assertFalse((d / "doc.failed.pdf").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
