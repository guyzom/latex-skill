#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Original project code; scope and terms: ../LICENSING.md.
"""Real-engine codebox gutters: four styles, RTL/LTR/RTL scope, wide numbers.

The mutation removes only the v4.28 outer-language hook. It must reproduce the
English border collision. The unchanged Hebrew crops must be pixel-identical.
These assertions measure geometry; they do not certify a human visual review.
"""
from __future__ import annotations

import os
import hashlib
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
import fitz
from font_paths import font_dir

ROOT = Path(__file__).resolve().parent.parent
STYLES = ("asm", "cstyle", "pystyle", "htmlstyle")


def source() -> str:
    text = r'''\def\lakitdocumentclass{article}
\def\lakitclassoptions{11pt,a4paper}
\input{preamble.tex}
\input{reader_theme.tex}
\hypersetup{pdftitle={Bidirectional codebox regression},pdfauthor={QA}}
\begin{document}
'''
    for i, style in enumerate(STYLES):
        if i:
            text += "\\newpage\n"
        text += f"\\section{{בדיקת קוד \\en{{{style}}}}}\n"
        for context in ("Hebrew before", "English context", "Hebrew after"):
            if context == "English context":
                text += "\\begin{englishprose}\n"
            text += ("\\begin{codebox}[nobreak=true,frametitle={\\en{" + context + "}}]\n"
                     "\\begin{asmblock}\n\\begin{lstlisting}[style=" + style + ",firstnumber=998]\n"
                     "alpha = 10\nbeta = 20\nresult = alpha + beta\n"
                     "\\end{lstlisting}\n\\end{asmblock}\n\\end{codebox}\n")
            if context == "English context":
                text += "\\end{englishprose}\n"
    text += r"""\newpage
\section{קוד מחוץ למסגרת}
\begin{asmblock}
\begin{lstlisting}[style=pystyle,firstnumber=998]
alpha = 10
beta = 20
result = alpha + beta
\end{lstlisting}
\end{asmblock}
"""
    return text + "\\end{document}\n"


def boxes(page):
    color = (242 / 255, 244 / 255, 247 / 255)
    result = []
    for d in page.get_drawings():
        fill = d.get("fill"); r = d["rect"]
        if fill and len(fill) == 3 and max(abs(a-b) for a, b in zip(fill, color)) < .01:
            if r.width > 100 and r.height > 30:
                if not any(all(abs(a-b) < .01 for a, b in zip(r, old)) for old in result):
                    result.append(r)
    return sorted(result, key=lambda r: r.y0)


def number_spans(page):
    result = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                if span["text"].strip() in {"998", "999", "1000"} and span["size"] < 7:
                    result.append(span)
    return result


class CodeboxRuntime(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        chosen = os.environ.get("HLLPDF_428_EVIDENCE_DIR")
        if chosen:
            cls.root = Path(chosen).resolve()
            if cls.root == ROOT or ROOT in cls.root.parents:
                raise ValueError("retained evidence must be outside the skill")
            cls.root.mkdir(parents=True, exist_ok=False)
        else:
            cls.tmp = tempfile.TemporaryDirectory(prefix="hllpdf428-runtime-")
            cls.addClassCleanup(cls.tmp.cleanup)
            cls.root = Path(cls.tmp.name)
        env = os.environ.copy(); fonts = str(font_dir())
        env.update(HEBREW_LATEX_FONT_DIR=fonts, OSFONTDIR=fonts, TTFONTS=fonts + "//:",
                   SOURCE_DATE_EPOCH="1700000000", TZ="UTC", PYTHONDONTWRITEBYTECODE="1")
        for variant in ("fixed", "mutation"):
            dest = cls.root / variant; dest.mkdir()
            for name in ("preamble.tex", "reader_theme.tex"):
                shutil.copyfile(ROOT / "assets" / name, dest / name)
            if variant == "mutation":
                p = dest / "preamble.tex"; core = p.read_text(encoding="utf-8")
                legacy = r"""\makeatletter
\AtBeginEnvironment{codebox}{%
  \lstset{resetmargins=false,xrightmargin=26pt}%
  \lst@AddToHook{PreInit}{\lstset{frame=none,backgroundcolor=\color{cSlateBg},%
    aboveskip=0pt,belowskip=0pt}}%
}
\makeatother"""
                changed, count = re.subn(r"% <hllpdf:codebox-gutter>.*?% </hllpdf:codebox-gutter>",
                                         lambda _: legacy, core, flags=re.S)
                if count != 1:
                    raise AssertionError(f"mutation did not replace exactly one codebox block: {count}")
                p.write_text(changed, encoding="utf-8")
            (dest / "probe.tex").write_text(source(), encoding="utf-8")
            local_env = dict(env, HEBREW_LATEX_PROJECT_ROOT=str(dest))
            for _ in range(2):
                p = subprocess.run(["lualatex", "--no-shell-escape", "-halt-on-error",
                                    "-interaction=nonstopmode", "probe.tex"], cwd=dest,
                                   env=local_env, text=True, capture_output=True, timeout=180)
                if p.returncode:
                    raise AssertionError(p.stdout[-5000:])
            log = (dest / "probe.log").read_text(errors="replace")
            if "Missing character:" in log:
                raise AssertionError("missing glyph in geometry fixture")

    def test_01_all_four_styles_keep_wide_digits_inside_each_frame(self):
        count = 0
        with fitz.open(self.root / "fixed/probe.pdf") as doc:
            self.assertEqual(len(doc), 5)
            for page in list(doc)[:4]:
                frames = boxes(page); self.assertEqual(len(frames), 3)
                numbers = number_spans(page); self.assertEqual(len(numbers), 9)
                for frame in frames:
                    row = [s for s in numbers if frame.y0 <= s["bbox"][1] < frame.y1]
                    self.assertEqual(len(row), 3)
                    for s in row:
                        count += 1
                        self.assertGreaterEqual(s["bbox"][0] - frame.x0, 2, (page.number, s))
        self.assertEqual(count, 36)

    def test_02_mutation_reproduces_english_collision_not_hebrew(self):
        with fitz.open(self.root / "mutation/probe.pdf") as doc:
            for page in list(doc)[:4]:
                frames = boxes(page); numbers = number_spans(page)
                for i, frame in enumerate(frames):
                    digits = [s for s in numbers if frame.y0 <= s["bbox"][1] < frame.y1]
                    self.assertEqual(len(digits), 3)
                    clearance = min(s["bbox"][0] - frame.x0 for s in digits)
                    if i == 1 and page.number in (2, 3):
                        self.assertLess(clearance, 0, (page.number, clearance))
                    else:
                        self.assertGreaterEqual(clearance, 2, (page.number, clearance))

    def test_03_hebrew_before_and_after_are_pixel_identical_to_mutation(self):
        with fitz.open(self.root / "fixed/probe.pdf") as fixed, fitz.open(self.root / "mutation/probe.pdf") as old:
            for p, q in zip(list(fixed)[:4], list(old)[:4]):
                frames = boxes(p); oldframes = boxes(q)
                self.assertEqual(len(frames), len(oldframes))
                for i in (0, 2):
                    self.assertEqual(frames[i], oldframes[i])
                    clip = frames[i] + (-2, -2, 2, 2)
                    a = p.get_pixmap(dpi=144, clip=clip, alpha=False)
                    b = q.get_pixmap(dpi=144, clip=clip, alpha=False)
                    self.assertEqual((a.width, a.height, hashlib.sha256(a.samples).hexdigest()),
                                     (b.width, b.height, hashlib.sha256(b.samples).hexdigest()))

    def test_04_five_page_a4_document_keeps_navigation(self):
        with fitz.open(self.root / "fixed/probe.pdf") as doc:
            self.assertEqual(len(doc.get_toc()), 5)
            self.assertEqual(doc.metadata["title"], "Bidirectional codebox regression")
            for page in doc:
                self.assertAlmostEqual(page.rect.width, 595.276, delta=.1)
                self.assertAlmostEqual(page.rect.height, 841.89, delta=.1)

    def test_05_unboxed_listing_keeps_its_own_frame_after_codebox(self):
        with fitz.open(self.root / "fixed/probe.pdf") as fixed, fitz.open(self.root / "mutation/probe.pdf") as old:
            # listings draws each side as one segment per source line, not
            # one path for the entire rectangle. Measure top/bottom strokes
            # and accumulated left/right segment height rather than assuming
            # that one drawing object equals one side of the frame.
            def edges(page):
                rows = [d["rect"] for d in page.get_drawings() if d.get("color") and
                        80 < d["rect"].y0 < 350]
                horizontal = [r for r in rows if r.width > 400 and r.height < .01]
                vertical = {}
                for r in rows:
                    if r.width < .01 and r.height > 0:
                        x = round(r.x0, 2)
                        vertical[x] = vertical.get(x, 0) + r.height
                return horizontal, vertical
            horizontal, vertical = edges(fixed[-1])
            self.assertEqual(len(horizontal), 2)
            self.assertEqual(len(vertical), 2)
            self.assertTrue(all(height > 50 for height in vertical.values()), vertical)
            self.assertEqual(edges(old[-1]), ([], {}))


if __name__ == "__main__":
    unittest.main(verbosity=2)
