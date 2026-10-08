#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Original project code; scope and terms: ../LICENSING.md.
"""Real-engine controls for bilingual flow tables, numbering and structural guards."""
from __future__ import annotations
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
from font_paths import font_dir
ROOT = Path(__file__).resolve().parent.parent


# ---- engine gate for REPRODUCTION controls -------------------------------
# The tests below are negative controls: they mutate the source back to the
# pre-fix form and assert the ORIGINAL DEFECT REAPPEARS. That defect is a
# property of the engine, and this package's own reference documentation says
# so -- references/output-recovery.md records its measurement "בסביבת האימות,
# LuaHBTeX 1.18.0" and adds, in as many words, that this is an observation in
# the documented environment and "לא טענה שההתנהגות קיימת בכל גרסאות המנוע".
# On LuaHBTeX 1.17.0 (TeX Live 2023) and 1.24.0 (TeX Live 2026) the unprotected form lays out
# correctly, so the control cannot fire. The PROTECTION is still exercised by
# the positive tests in this file, which pass on both engines; only the proof
# that the protection is necessary needs the engine that exhibits the defect.
# Skipping here is therefore honest: it never hides a regression in shipped
# behaviour, and it stops a green package from being reported red on the
# oldest engine recipe.md claims to support.
REPRODUCTION_ENGINE = (1, 18, 0)


def _engine_version():
    """(major, minor, patch) of the LuaHBTeX on PATH, or None if unknown."""
    try:
        out = subprocess.run(['lualatex', '--version'], capture_output=True,
                             text=True, timeout=30).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    m = re.search(r'LuaHBTeX,\s*Version\s*(\d+)\.(\d+)\.(\d+)', out)
    return tuple(int(g) for g in m.groups()) if m else None


ENGINE = _engine_version()
requires_reproduction_engine = unittest.skipUnless(
    ENGINE == REPRODUCTION_ENGINE,
    f'historical defect was measured on LuaHBTeX '
    f'{".".join(str(n) for n in REPRODUCTION_ENGINE)}; found '
    f'{".".join(str(n) for n in ENGINE) if ENGINE else "unknown"}')

HEADER = r'''\def\lakitclassoptions{11pt,a4paper}
\def\lakitgeometryoptions{margin=2.3cm,headheight=14pt}
\def\lakitlinespread{1.16}
\input{preamble.tex}
\input{flow_tables.tex}
\input{reader_theme.tex}
\hypersetup{pdftitle={Flow table regression},pdfauthor={Synthetic QA}}
'''
SMALL = r'''\begin{tablebox}\centering
\begin{tabular}{rr}\h{סמל} & \h{ערך}\\\en{TOKEN} & $2$\end{tabular}
\tabcap[טבלה קצרה]{\label{LABEL}טבלה קצרה לבדיקת הרצף.}
\end{tablebox}
'''
FLOW_OPEN = r'''\begin{flowtable}{3}{N{.12\flowtablewidth} E{.20\flowtablewidth} H{.68\flowtablewidth}}
{54 רשומות בדיקה}{tab:flow}{ID & TOKEN & תיאור}
'''
ROWS = '\n'.join(fr'{1000+i} & item[{i:02d}] & תיאור הרשומה כולל \en{{sample-{i:02d}}} וערך $x_i=i/4$, כדי לבדוק גלישה, המשכיות וכיווניות.\\' for i in range(1, 55))
BODY = r'''\begin{document}\chapter{דוח ניסוי}
הפניה לטבלה הארוכה: \autoref{tab:flow}. שמה: \nameref{tab:flow}.
'''+SMALL.replace('LABEL', 'tab:before')+FLOW_OPEN+ROWS+r'''
\end{flowtable}
'''+SMALL.replace('LABEL', 'tab:after')+r'''
\appendix\chapter{נספח}
\begin{flowtable}{3}{N{.12\flowtablewidth} E{.20\flowtablewidth} H{.68\flowtablewidth}}
{נתוני נספח}{tab:appendix}{ID & TOKEN & תיאור}
2001 & appendix[01] & רשומת נספח ראשונה.\\
2002 & appendix[02] & רשומת נספח שנייה.\\
\end{flowtable}
\clearpage\listoftables
\end{document}
'''


def numeric_column(doc):
    """Read physical left-to-right glyph positions, never trust extraction order."""
    out = []
    for page in doc:
        groups = {}
        for block in page.get_text('rawdict')['blocks']:
            for line in block.get('lines', []):
                for span in line['spans']:
                    for char in span['chars']:
                        x, y = char['origin']
                        if x > page.rect.width * .80 and 65 < y < page.rect.height - 60:
                            groups.setdefault(round(y, 1), []).append((x, char['c']))
        for y in sorted(groups):
            text = ''.join(c for x, c in sorted(groups[y])).strip()
            if re.fullmatch(r'\d{4}', text): out.append(text)
    return out


class Runtime490Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        evidence = os.environ.get('HLLPDF_FLOW_EVIDENCE')
        cls.tmp = None if evidence else tempfile.TemporaryDirectory(prefix='hllpdf-490-runtime-')
        cls.root = Path(evidence) if evidence else Path(cls.tmp.name)
        if evidence: cls.root.mkdir(parents=True, exist_ok=False)
        for name in ['preamble.tex', 'flow_tables.tex', 'reader_theme.tex']:
            shutil.copyfile(ROOT / 'assets' / name, cls.root / name)
        fonts = str(font_dir()); cls.env = os.environ.copy()
        cls.env.update(OSFONTDIR=fonts, TTFONTS=fonts+'//:', HEBREW_LATEX_FONT_DIR=fonts,
                       SOURCE_DATE_EPOCH='1700000000', PYTHONDONTWRITEBYTECODE='1')
        cls.result = cls.compile(HEADER + BODY, 'positive', passes=3)

    @classmethod
    def tearDownClass(cls):
        if cls.tmp: cls.tmp.cleanup()

    @classmethod
    def compile(cls, text, name, passes=1):
        (cls.root / (name+'.tex')).write_text(text, encoding='utf-8')
        for _ in range(passes):
            result = subprocess.run(['lualatex', '--no-shell-escape', '-halt-on-error',
                                     '-interaction=nonstopmode', name+'.tex'], cwd=cls.root,
                                    env=cls.env, capture_output=True, text=True, timeout=90)
            if result.returncode: break
        return result

    def positive(self):
        self.assertEqual(self.result.returncode, 0, self.result.stdout[-4000:])
        return fitz.open(self.root / 'positive.pdf')

    def test_all_rows_once_in_correct_order_across_pages(self):
        with self.positive() as doc:
            self.assertGreaterEqual(len(doc), 5)
            self.assertEqual(numeric_column(doc), [str(i) for i in range(1001, 1055)]+['2001', '2002'])
            text = '\n'.join(page.get_text() for page in doc)
            for i in range(1, 55): self.assertEqual(text.count(f'item[{i:02d}]'), 1)
            for page in doc:
                text = page.get_text()
                if any(f'item[{i:02d}]' in text for i in range(1, 55)):
                    self.assertIn('ID', text); self.assertIn('TOKEN', text)
                for block in page.get_text('dict')['blocks']:
                    for line in block.get('lines', []):
                        x0,y0,x1,y1 = line['bbox']
                        self.assertGreaterEqual(x0, -1); self.assertLessEqual(x1, page.rect.width+1)
                        self.assertGreaterEqual(y0, -1); self.assertLessEqual(y1, page.rect.height+1)

    def test_shared_numbering_appendix_list_and_top_destination(self):
        with self.positive() as doc:
            aux = (self.root / 'positive.aux').read_text()
            for label, number in [('tab:before','1.1'), ('tab:flow','1.2'), ('tab:after','1.3'), ('tab:appendix','A.1')]:
                self.assertIn('\\newlabel{'+label+'}{{'+number+'}', aux)
            lot = (self.root / 'positive.lot').read_text()
            self.assertEqual(lot.count('\\contentsline'), 4)
            names = doc.resolve_names(); target = names['table.1.2']; page = doc[target['page']]
            first = page.search_for('1001')[0]
            y_top = page.rect.height - target['to'][1]
            self.assertLess(y_top, first.y0)
            self.assertGreaterEqual(y_top, 0)
            self.assertEqual(names['table.A.1']['page'], next(i for i,p in enumerate(doc) if '2001' in p.get_text()))
            self.assertTrue(any(link.get('nameddest') == 'table.1.2' for p in doc for link in p.get_links()))

    @requires_reproduction_engine
    def test_raw_hbox_column_reproduces_digit_reversal(self):
        path = self.root / 'flow_tables.tex'; original = path.read_text()
        broken = original.replace(r'\newcolumntype{N}[1]{>{\iflanguage{hebrew}{\raggedright}{\raggedleft}\arraybackslash\collectcell\en}p{#1}<{\endcollectcell}}',r'\newcolumntype{N}[1]{r}')
        # A bare p-column already protects plain digit order; removing only
        # the language wrapper did NOT reproduce this defect. Recreate the
        # actual old hbox-style r column instead of pretending otherwise.
        self.assertNotEqual(original, broken)
        try:
            path.write_text(broken); result = self.compile(HEADER+BODY, 'mutated', passes=2)
            self.assertEqual(result.returncode, 0, result.stdout[-2000:])
            with fitz.open(self.root / 'mutated.pdf') as doc:
                numbers = numeric_column(doc)
                self.assertNotEqual(numbers, [str(i) for i in range(1001, 1055)]+['2001','2002'])
                self.assertIn('2001', numbers[:5])
        finally: path.write_text(original)

    def test_pdf_digit_order_check_rejects_a_corrupt_cell_formatter(self):
        # An engine-independent adversarial formatter reverses the source
        # digits while leaving row tokens and table/navigation structure intact.
        # Inspect the rendered PDF: compile success cannot accept this defect.
        path = self.root / 'flow_tables.tex'; original = path.read_text()
        old = r'\newcolumntype{N}[1]{>{\iflanguage{hebrew}{\raggedright}{\raggedleft}\arraybackslash\collectcell\en}p{#1}<{\endcollectcell}}'
        broken = original.replace(old, r'''\ExplSyntaxOn
\cs_new:Npn \qaReverseNumber #1 { \en{\tl_reverse:n{#1}} }
\ExplSyntaxOff
\newcolumntype{N}[1]{>{\raggedright\arraybackslash\collectcell\qaReverseNumber}p{#1}<{\endcollectcell}}''')
        self.assertNotEqual(original, broken)
        try:
            path.write_text(broken)
            result = self.compile(HEADER+BODY, 'corrupt-number-formatter', passes=3)
            self.assertEqual(result.returncode, 0, result.stdout[-2000:])
            with fitz.open(self.root / 'corrupt-number-formatter.pdf') as doc:
                expected = [str(i) for i in range(1001, 1055)]+['2001','2002']
                numbers = numeric_column(doc)
                self.assertEqual(numbers, [n[::-1] for n in expected])
                with self.assertRaises(AssertionError): self.assertEqual(numbers, expected)
                text = '\n'.join(page.get_text() for page in doc)
                for i in range(1, 55): self.assertEqual(text.count(f'item[{i:02d}]'), 1)
                self.assertTrue(any(link.get('nameddest') == 'table.1.2'
                                    for page in doc for link in page.get_links()))
        finally: path.write_text(original)

    def test_english_context_is_supported_and_stays_on_page(self):
        # v5.0 supports an English multipage table within a Hebrew-base document.
        # Check actual rendered content, not merely a successful engine exit:
        # the old unguarded longtable path silently placed page one off canvas.
        opening = FLOW_OPEN.replace('{54 רשומות בדיקה}', '{54 synthetic records}')
        result = self.compile(HEADER+r'\begin{document}\begin{englishprose}'+
                              opening+ROWS+
                              r'\end{flowtable}\end{englishprose}\end{document}',
                              'english', passes=3)
        self.assertEqual(result.returncode, 0, result.stdout[-4000:])
        with fitz.open(self.root / 'english.pdf') as doc:
            self.assertGreaterEqual(len(doc), 2)
            text = '\n'.join(page.get_text() for page in doc)
            for i in range(1, 55):
                self.assertEqual(text.count(f'item[{i:02d}]'), 1)
                self.assertTrue(any(page.search_for(str(1000+i)) for page in doc))
            for page in doc:
                self.assertTrue(page.search_for('ID') and page.search_for('TOKEN'))
                self.assertLess(page.search_for('ID')[0].x0,
                                page.search_for('TOKEN')[0].x0)
                for block in page.get_text('dict')['blocks']:
                    for line in block.get('lines', []):
                        x0, y0, x1, y1 = line['bbox']
                        self.assertGreaterEqual(x0, -1)
                        self.assertLessEqual(x1, page.rect.width+1)
                        self.assertGreaterEqual(y0, -1)
                        self.assertLessEqual(y1, page.rect.height+1)

    def test_box_context_is_rejected(self):
        result = self.compile(HEADER+r'\begin{document}\begin{minipage}{.8\linewidth}'+FLOW_OPEN+r'1001 & token & text\\\end{flowtable}\end{minipage}\end{document}', 'boxed')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('flowtablerequiresouterone-columnmode', re.sub(r'\s+', '', result.stdout))

    def test_two_column_context_is_rejected(self):
        result = self.compile(HEADER.replace('11pt,a4paper','11pt,a4paper,twocolumn')+r'\begin{document}'+FLOW_OPEN+r'1001 & token & text\\\end{flowtable}\end{document}', 'twocolumn')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('flowtablerequiresone-columnmode', re.sub(r'\s+', '', result.stdout))

    def test_column_name_collision_is_rejected(self):
        text = HEADER.replace(r'\input{flow_tables.tex}',r'\newcolumntype{N}{r}\input{flow_tables.tex}')
        result = self.compile(text+r'\begin{document}text\end{document}', 'collision')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('columnnameNisalreadydefined', re.sub(r'\s+', '', result.stdout))


if __name__ == '__main__': unittest.main(verbosity=2)
