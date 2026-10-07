#!/usr/bin/env python3
"""Real-engine citation controls: actual keys, physical digits and link targets."""
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
# On LuaHBTeX 1.17.0 (TeX Live 2023) the unprotected form happens to lay out
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
    ENGINE is not None and ENGINE >= REPRODUCTION_ENGINE,
    f'defect reproduction needs LuaHBTeX >= '
    f'{".".join(str(n) for n in REPRODUCTION_ENGINE)}; found '
    f'{".".join(str(n) for n in ENGINE) if ENGINE else "unknown"}')
OLD = r'\def\@cite#1#2{\foreignlanguage{english}{[{#1\if@tempswa , #2\fi}]}}'
NEW = r'\def\@cite#1#2{\babelsublr{[{#1\if@tempswa , #2\fi}]}}'
HEADER = r'''\def\lakitdocumentclass{article}
\def\lakitclassoptions{11pt,a4paper}
\def\lakitgeometryoptions{margin=2.2cm,headheight=14pt}
\def\lakitlinespread{1.18}
\input{preamble.tex}
\input{document_components.tex}
\input{reader_theme.tex}
\hypersetup{pdftitle={Citation controls},pdfauthor={Synthetic QA}}
'''
ROWS = r'''\begin{document}
\section{בדיקת הפניות}
\noindent\en{C01}\quad\cite{ref01}\par
\noindent\en{C02}\quad\cite{ref01,ref02,ref03}\par
\noindent\en{C03}\quad\cite{ref12,ref02,ref10}\par
\noindent\en{C04}\quad\cite[p.~25]{ref01}\par
\noindent\en{C05}\quad\cite[\h{עמוד 25}]{ref02}\par
\def\fixturekeys{ref11,ref10}
\noindent\en{C06}\quad\cite{\fixturekeys}\par
\begin{englishprose}
\noindent C07\quad\cite{ref02,ref01}\par
\sourcelink{https://example.org/control?a=1&b=2\#part}{English reference}{Synthetic source annotation, not a factual source.}
\end{englishprose}
\sourcelink{https://example.org/hebrew}{מקור בדיקה}{זוהי רשומה מלאכותית לבדיקת הרכיב.}
הערה עם הפניה\footnote{הפניה בהערת שוליים \cite{ref03}.}.
\nocite{ref11}
\clearpage
\begin{thebibliography}{99}
'''
ENTRIES = '\n'.join(fr'\bibitem{{ref{i:02d}}}\en{{SOURCE-{i:02d}. Synthetic bibliography control ({2020+i}).}}' for i in range(1,13))
BODY = ROWS + ENTRIES + '\n' + r'\end{thebibliography}\end{document}'
EXPECTED_KEYS = ['ref01','ref01','ref02','ref03','ref12','ref02','ref10','ref01','ref02','ref11','ref10','ref02','ref01','ref03','ref11']


def physical_row(page, marker):
    hit = page.search_for(marker)[0]
    chars = []
    for block in page.get_text('rawdict')['blocks']:
        for line in block.get('lines', []):
            for span in line['spans']:
                for c in span['chars']:
                    x,y = c['origin']
                    if hit.y0 <= y <= hit.y1:
                        chars.append((x,c['c']))
    return ''.join(c for x,c in sorted(chars)).replace(' ', '')


class Runtime491Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='hllpdf-491-runtime-')
        cls.root = Path(cls.tmp.name)
        for name in ['preamble.tex','document_components.tex','reader_theme.tex']:
            shutil.copyfile(ROOT/'assets'/name, cls.root/name)
        fonts = str(font_dir()); cls.env = os.environ.copy()
        cls.env.update(OSFONTDIR=fonts, TTFONTS=fonts+'//:', HEBREW_LATEX_FONT_DIR=fonts,
                       SOURCE_DATE_EPOCH='1700000000', PYTHONDONTWRITEBYTECODE='1')
        # Harness-wide roots refer to the skill, but fixtures deliberately live
        # outside it. Production missing-key control owns this project root.
        cls.env.pop('HEBREW_LATEX_PROJECT_ROOT', None)
        cls.result = cls.compile(HEADER+BODY, 'positive', passes=3)

    @classmethod
    def tearDownClass(cls): cls.tmp.cleanup()

    @classmethod
    def compile(cls, text, name, passes=1):
        (cls.root/(name+'.tex')).write_text(text, encoding='utf-8')
        for _ in range(passes):
            result = subprocess.run(['lualatex','--no-shell-escape','-halt-on-error',
                                     '-interaction=nonstopmode',name+'.tex'],cwd=cls.root,
                                    env=cls.env,capture_output=True,text=True,timeout=120)
            if result.returncode: break
        return result

    def positive(self):
        self.assertEqual(self.result.returncode,0,self.result.stdout[-3000:])
        self.assertNotIn("Citation `",self.result.stdout)
        return fitz.open(self.root/'positive.pdf')

    def test_actual_citation_keys_are_preserved(self):
        with self.positive() as doc: self.assertEqual(len(doc),2)
        keys = re.findall(r'\\citation\{([^}]+)\}',(self.root/'positive.aux').read_text())
        self.assertEqual(keys,EXPECTED_KEYS)

    def test_physical_digit_order_is_not_reversed(self):
        with self.positive() as doc:
            for marker, expected in [('C01','[1]'),('C02','[1,2,3]'),('C03','[12,2,10]'),
                                     ('C04','[1,p.25]'),('C06','[11,10]'),('C07','[2,1]')]:
                self.assertIn(expected,physical_row(doc[0],marker),marker)
            self.assertIn('25',physical_row(doc[0],'C05'))
            self.assertNotIn('52',physical_row(doc[0],'C05'))

    def test_citation_links_resolve_to_the_matching_second_page_entry(self):
        with self.positive() as doc:
            names=doc.resolve_names()
            for i in range(1,13):
                target=names[f'cite.ref{i:02d}']
                self.assertEqual(target['page'],1)
                entry=doc[1].search_for(f'SOURCE-{i:02d}')[0]
                y=doc[1].rect.height-target['to'][1]
                self.assertLess(abs(y-entry.y0),20)
            citations=[ln for ln in doc[0].get_links() if ln.get('nameddest','').startswith('cite.')]
            self.assertEqual(len(citations),14)  # nocite records a key, not a visible link
            self.assertEqual({ln['nameddest'] for ln in citations}, {'cite.'+k for k in EXPECTED_KEYS})
            # Test the ordered associations, not just a set of valid targets:
            # swapping two existing source destinations must not pass.
            self.assertEqual([ln['nameddest'] for ln in citations],
                             ['cite.'+k for k in EXPECTED_KEYS[:-1]])
            for link in citations:
                expected_digit = str(int(link['nameddest'].removeprefix('cite.ref')))
                visible_digits = re.findall(r'\d+', doc[0].get_textbox(
                    link['from']+(-.2,-.2,.2,.2)))
                self.assertEqual(visible_digits, [expected_digit])

    def test_source_role_follows_context_and_uri_is_preserved(self):
        with self.positive() as doc:
            text=doc[0].get_text()
            self.assertEqual(text.count('Source:'),1)
            self.assertEqual(text.count('מקור:'),1)
            self.assertTrue(any(ln.get('uri')=='https://example.org/control?a=1&b=2#part'
                                for ln in doc[0].get_links()))

    @requires_reproduction_engine
    def test_old_language_wrapper_reproduces_literal_english_citations(self):
        path=self.root/'preamble.tex'; original=path.read_text()
        self.assertIn(NEW,original)
        try:
            path.write_text(original.replace(NEW,OLD))
            result=self.compile(HEADER+BODY,'old-broken',passes=2)
            self.assertEqual(result.returncode,0)
            self.assertIn("Citation `english'",result.stdout)
            keys=re.findall(r'\\citation\{([^}]+)\}',(self.root/'old-broken.aux').read_text())
            self.assertIn('english',keys); self.assertNotEqual(keys,EXPECTED_KEYS)
        finally: path.write_text(original)

    @requires_reproduction_engine
    def test_old_wrapper_can_silently_link_every_citation_to_existing_english_key(self):
        path=self.root/'preamble.tex'; original=path.read_text()
        shadow=BODY.replace(r'\end{thebibliography}',r'\bibitem{english}\en{SHADOW. Synthetic collision control.}\end{thebibliography}')
        try:
            path.write_text(original.replace(NEW,OLD))
            result=self.compile(HEADER+shadow,'old-silent',passes=3)
            self.assertEqual(result.returncode,0)
            self.assertNotIn("Citation `",result.stdout)
            with fitz.open(self.root/'old-silent.pdf') as doc:
                links=[ln.get('nameddest') for ln in doc[0].get_links() if ln.get('nameddest','').startswith('cite.')]
                self.assertTrue(links); self.assertEqual(set(links),{'cite.english'})
                self.assertIn('[13]',physical_row(doc[0],'C01'))
        finally: path.write_text(original)
        # The identical source, including the shadow key, must recover with
        # the real wrapper restored; absence of warnings alone is insufficient.
        result=self.compile(HEADER+shadow,'repaired-same-shadow',passes=3)
        self.assertEqual(result.returncode,0)
        self.assertNotIn("Citation `",result.stdout)
        with fitz.open(self.root/'repaired-same-shadow.pdf') as doc:
            links=[ln.get('nameddest') for ln in doc[0].get_links()
                   if ln.get('nameddest','').startswith('cite.')]
            self.assertEqual(links, ['cite.'+k for k in EXPECTED_KEYS[:-1]])
            self.assertIn('[1]',physical_row(doc[0],'C01'))

    def test_missing_key_is_a_production_build_failure_with_the_real_key(self):
        name='missing'; (self.root/(name+'.tex')).write_text(HEADER+r'\begin{document}הפניה \cite{missing-real-key}.\end{document}')
        result=subprocess.run(['bash',str(ROOT/'scripts/build.sh'),str(self.root/(name+'.tex'))],
                              cwd=self.root,env=self.env,capture_output=True,text=True,timeout=240)
        self.assertEqual(result.returncode,1,result.stdout[-2000:]+result.stderr[-1000:])
        self.assertIn("Citation `missing-real-key'",result.stdout)
        self.assertFalse((self.root/'missing.pdf').exists())


if __name__ == '__main__': unittest.main(verbosity=2)
