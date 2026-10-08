#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Original project code; scope and terms: ../LICENSING.md.
"""Real LuaLaTeX quote-wrap controls and starred unnumbered references.

Negative fixtures are compiled directly solely to measure a defect; user PDFs
must pass build.sh. HLLPDF_420_EVIDENCE_DIR retains logs, source and measurements
in a NEW directory outside the skill. Counts below describe synthetic cases.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
sys.dont_write_bytecode = True
import fitz
from check_bidi_figures import scan_file
from font_paths import font_dir

ROOT = Path(__file__).resolve().parent.parent
WORDS = ('alpha', 'beta', 'gamma', 'delta', 'epsilon')
OFFSETS = tuple(range(0, 141, 10))
FORMS = {
 'canonical': r'\en{“alpha beta gamma delta epsilon”}',
 'spaced': r'\en {“alpha beta gamma delta epsilon”}',
 'second': r'\en{“OK” then “alpha beta gamma delta epsilon”}',
 'boxed': r'\en{“OK” then \mbox{“alpha beta gamma delta epsilon”}}',
}


def quote_metrics(pdf: Path) -> list[dict]:
    rows = []
    with fitz.open(pdf) as doc:
        for i, page in enumerate(doc):
            boxes = {}
            for word in WORDS:
                matches = page.search_for(word)
                if len(matches) != 1:
                    raise ValueError(f'page {i+1}: {word} anchor count={len(matches)}; expected 1')
                boxes[word] = list(matches[0])
            spread = max(q[1] for q in boxes.values()) - min(q[1] for q in boxes.values())
            rows.append({'page': i+1, 'boxes': boxes, 'split': spread > 2,
                         'vertical_spread_pt': spread,
                         'same_row_word_order': [w for w in sorted(WORDS, key=lambda w: boxes[w][0])]})
    return rows


def quote_source(form: str) -> str:
    source = r'''\def\lakitdocumentclass{article}
\def\lakitclassoptions{11pt,a4paper}
\input{preamble.tex}
\hypersetup{pdftitle={בדיקת ציטוטים},pdfauthor={Synthetic QA}}
\begin{document}
\pagestyle{empty}
'''
    for offset in OFFSETS:
        source += ('\\noindent\\begin{minipage}{230pt}\n\\noindent\\hspace*{'
                   + str(offset) + 'pt}הודעת המערכת היא ' + form
                   + ' והמשך ההסבר נשאר בעברית כדי לבחון את גבולות הציטוט.'
                   + '\\par\n\\end{minipage}\n\\clearpage\n')
    return source + '\\end{document}\n'

REF_SOURCE = r'''\def\lakitdocumentclass{article}
\input{preamble.tex}
\hypersetup{pdftitle={בדיקת הפניה מכוכבת},pdfauthor={Synthetic QA}}
\begin{document}
\setcounter{secnumdepth}{-2}
\section{כותרת ללא מספר}\label{sec:off}
\en{Value: [\ref*{sec:off}].}\par
\en{Page: [\pageref*{sec:off}].}\par
\end{document}
'''


class RuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        chosen = os.environ.get('HLLPDF_420_EVIDENCE_DIR')
        if chosen:
            cls.root = Path(chosen).absolute()
            cls.root.mkdir(parents=True, exist_ok=False)
        else:
            cls.tmp = tempfile.TemporaryDirectory(prefix='hllpdf-420-runtime-')
            cls.root = Path(cls.tmp.name)
        fonts = str(font_dir())
        cls.env = {**os.environ, 'HEBREW_LATEX_FONT_DIR': fonts, 'OSFONTDIR': fonts+':',
                   'TTFONTS': fonts+':', 'SOURCE_DATE_EPOCH': '1700000000',
                   'PYTHONDONTWRITEBYTECODE': '1', 'TZ': 'UTC'}
        cls.metrics = {}
        for name, form in FORMS.items():
            cls.compile(name, quote_source(form))
            rows = quote_metrics(cls.root/name/'main.pdf')
            for row, offset in zip(rows, OFFSETS):
                row['offset_pt'] = offset
            cls.metrics[name] = rows
        cls.compile('ref-star', REF_SOURCE)
        cls.compile('page-anchor', REF_SOURCE.replace(r'Value: [\ref*{sec:off}]', r'Value: [\pageref*{sec:off}]'))
        (cls.root/'quote-metrics.json').write_text(json.dumps(cls.metrics, indent=2)+'\n')

    @classmethod
    def compile(cls, name, source):
        directory = cls.root/name; directory.mkdir()
        shutil.copyfile(ROOT/'assets/preamble.tex', directory/'preamble.tex')
        (directory/'main.tex').write_text(source, encoding='utf-8')
        for n in range(1, 4):
            result = subprocess.run(['lualatex', '--no-shell-escape', '-interaction=nonstopmode',
                                     '-halt-on-error', '-file-line-error', 'main.tex'],
                                    cwd=directory, env=cls.env, text=True, capture_output=True, timeout=120)
            (directory/f'pass-{n}.txt').write_text(result.stdout+result.stderr)
            if result.returncode:
                raise RuntimeError(f'{name}: pass {n} failed: {result.stdout[-1800:]}')

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, 'tmp'):
            cls.tmp.cleanup()

    def test_source_whitespace_is_pixel_equivalent(self):
        results = []
        with fitz.open(self.root/'canonical/main.pdf') as a, fitz.open(self.root/'spaced/main.pdf') as b:
            self.assertEqual(len(a), len(OFFSETS)); self.assertEqual(len(b), len(a))
            for i, (p, q) in enumerate(zip(a, b), 1):
                x = p.get_pixmap(dpi=144, alpha=False); y = q.get_pixmap(dpi=144, alpha=False)
                same = (x.width, x.height, x.n, x.samples) == (y.width, y.height, y.n, y.samples)
                results.append({'page': i, 'dpi': 144, 'renderer': 'mupdf', 'same_pixels': same})
                self.assertTrue(same, f'page {i}')
        (self.root/'source-whitespace-pixels.json').write_text(json.dumps(results, indent=2))

    def test_both_missed_classes_can_split_in_real_layout(self):
        for name in ('spaced', 'second'):
            self.assertEqual(len(self.metrics[name]), len(OFFSETS))
            self.assertTrue(any(row['split'] for row in self.metrics[name]), name)

    def test_local_box_keeps_quote_and_word_order_intact(self):
        self.assertEqual(len(self.metrics['boxed']), len(OFFSETS))
        for row in self.metrics['boxed']:
            self.assertFalse(row['split'])
            self.assertEqual(row['same_row_word_order'], list(WORDS))

    def test_source_rule_fires_even_when_one_offset_happens_to_fit(self):
        findings = {}
        for name in FORMS:
            actual = scan_file(str(self.root/name/'main.tex'))
            findings[name] = actual
            expected = 0 if name == 'boxed' else len(OFFSETS)
            self.assertEqual(sum(x[1] == 'BREAKABLE-QUOTED-ISLAND' for x in actual), expected)
        (self.root/'quote-source-findings.json').write_text(json.dumps(findings, ensure_ascii=False, indent=2))

    def test_starred_number_is_empty_but_page_reference_is_valid(self):
        with fitz.open(self.root/'ref-star/main.pdf') as doc:
            text = ''.join(p.get_text() for p in doc).replace(' ', '').replace('\n', '')
            self.assertIn('Value:[].', text)
            self.assertIn('Page:[1].', text)
            self.assertEqual(sum(len(p.get_links()) for p in doc), 0)
        with fitz.open(self.root/'page-anchor/main.pdf') as doc:
            text = ''.join(p.get_text() for p in doc).replace(' ', '').replace('\n', '')
            self.assertIn('Value:[1].', text)
            self.assertIn('Page:[1].', text)
        result = {}
        for name, expected in (('ref-star', 1), ('page-anchor', 0)):
            issues = scan_file(str(self.root/name/'main.tex'))
            result[name] = issues
            self.assertEqual(sum(i[1] == 'LABEL-ON-UNNUMBERED-HEADING' for i in issues), expected)
        (self.root/'reference-source-findings.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))

    def test_no_missing_glyphs_or_overfulls(self):
        for name in (*FORMS, 'ref-star', 'page-anchor'):
            text = (self.root/name/'main.log').read_text()
            for bad in ('Missing character:', r'Overfull \hbox', r'Overfull \vbox', 'Undefined control sequence'):
                self.assertNotIn(bad, text, name)

    def test_probe_rejects_missing_anchor(self):
        pdf = self.root/'missing-anchor.pdf'
        with fitz.open() as doc:
            doc.new_page().insert_text((30,40), 'alpha beta gamma delta')
            doc.save(pdf)
        with self.assertRaisesRegex(ValueError, 'epsilon anchor count=0'):
            quote_metrics(pdf)

    def test_probe_rejects_duplicate_anchor(self):
        pdf = self.root/'duplicate-anchor.pdf'
        with fitz.open() as doc:
            doc.new_page().insert_text((30,40), 'alpha alpha beta gamma delta epsilon')
            doc.save(pdf)
        with self.assertRaisesRegex(ValueError, 'alpha anchor count=2'):
            quote_metrics(pdf)

if __name__ == '__main__':
    unittest.main(verbosity=2)
