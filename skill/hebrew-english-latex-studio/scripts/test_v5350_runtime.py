#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Original project code; scope and terms: ../LICENSING.md.
"""v5.3.5 real-engine control: a text subscript in the folio's own font.

The construction from lifting-optimization p.17: a display ending a page whose
subscript is \\text{opt}. The engine sets 'opt' in the main font -- the folio's
font -- at script size, inside the folio band. Only the (font, size) face tells
it from the folio. Preconditions are asserted first, so a layout or font change
cannot make the test pass vacuously.
"""
from __future__ import annotations

import contextlib
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
import fitz
import check_pdf_render as render
import pdf_folios
from font_paths import font_dir

ROOT = Path(__file__).resolve().parent.parent
SOURCE = r'''\def\lakitdocumentclass{article}
\def\lakitclassoptions{11pt,a4paper}
\input{preamble.tex}
\hypersetup{pdftitle={Folio script control},pdfauthor={Synthetic QA}}
\begin{document}
\section*{בדיקת מספור העמוד}
המספר המודפס בתחתית העמוד צריך להתאים לתווית העמוד שבקובץ.
\newpage
\section*{בדיקת מספור העמוד}
\vspace*{\fill}
\[ \rho(\eta_{\text{opt}}) = 1 \]
\newpage
\section*{בדיקת מספור העמוד}
המספר המודפס בתחתית העמוד צריך להתאים לתווית העמוד שבקובץ.
\end{document}
'''


class TextSubscriptRuntime(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='hllpdf5350-runtime-')
        cls.root = Path(cls.tmp.name)
        fonts = str(font_dir())
        env = {**os.environ, 'HEBREW_LATEX_FONT_DIR': fonts, 'OSFONTDIR': fonts,
               'TTFONTS': fonts + '//:', 'SOURCE_DATE_EPOCH': '1700000000', 'TZ': 'UTC',
               'PYTHONDONTWRITEBYTECODE': '1'}
        env.pop('HEBREW_LATEX_PROJECT_ROOT', None)
        cache = cls.root / 'private-cache'
        cache.mkdir()
        env.update(TEXMFCACHE=str(cache), TEXMFVAR=str(cache))
        (cls.root / 'main.tex').write_text(SOURCE, encoding='utf-8')
        shutil.copyfile(ROOT / 'assets/preamble.tex', cls.root / 'preamble.tex')
        for _ in range(2):
            run = subprocess.run(['lualatex', '--no-shell-escape', '-halt-on-error',
                                  '-interaction=nonstopmode', 'main.tex'],
                                 cwd=cls.root, env=env, text=True, capture_output=True,
                                 timeout=180)
            if run.returncode:
                raise AssertionError(run.stdout[-2400:])
        cls.pdf = cls.root / 'main.pdf'

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def check(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            code = render.check(str(self.pdf))
        return code, out.getvalue()

    def test_01_precondition_opt_is_in_the_band_in_the_folio_font(self):
        with fitz.open(self.pdf) as doc:
            runs = dict(pdf_folios._styled_candidates(doc[1], expected_label='2'))
        self.assertEqual(sorted(runs), ['2', 'opt'])
        fonts = lambda face: {font for font, _ in face}
        self.assertEqual(fonts(runs['opt']), fonts(runs['2']))   # the folio's own font
        self.assertNotEqual(runs['opt'], runs['2'])              # at another size

    def test_02_text_subscript_is_not_a_second_folio(self):
        code, out = self.check()
        self.assertEqual(code, 0, out)
        self.assertIn('3/3 center footer folios', out)

    def test_03_a_font_only_face_restores_the_false_rejection(self):
        original = pdf_folios._styled_candidates
        with patch.object(pdf_folios, '_styled_candidates',
                          lambda *a, **k: [(t, frozenset(f for f, _ in face))
                                           for t, face in original(*a, **k)]):
            code, out = self.check()
        self.assertEqual(code, 1, out)
        self.assertIn('p.2 [FOLIO-AMBIGUOUS]', out)


if __name__ == '__main__':
    unittest.main(verbosity=2)
