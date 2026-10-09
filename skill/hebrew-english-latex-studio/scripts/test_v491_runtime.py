#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Original project code; scope and terms: ../LICENSING.md.
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


def bibliography_paragraph_fixture(profile, main):
    header = (rf'\def\lakitlanguageprofile{{{profile}}}'+'\n'
              + (rf'\def\lakitmainlanguage{{{main}}}'+'\n' if profile == 'bilingual' else '')
              + HEADER.replace(r'\input{reader_theme.tex}', ''))
    english = ('An original synthetic entry preserves complete source details, '
               'readable continuation lines, ordinary paragraph spacing and native citation identity. ')*40
    hebrew = ('רשומה סינתטית מקורית שומרת על פרטי המקור ועל קריאות שורות ההמשך. '
              'הפסקה צריכה להישאר בכיוון המקומי ולשמור על זהות ההפניה. ')*22
    return header + r'''\begin{document}
\begin{englishprose}\noindent CITMARK \cite{qa-he,qa-en,qa-style}\par
{\Large\itshape STYLECONTROL Authored style.\par}\end{englishprose}
\begin{thebibliography}{99}
\bibitem{qa-en}\bibentryprose{english}{BIBEN Original source \textit{Title (2026)}.
Escaped details \& 25\% and MATHMARK $x+2$. \h{מונח קצר}.
''' + english + r' ENEND.}'+'\n'+r'''\bibitem{qa-he}\bibentryprose{hebrew}{מקור \en{BIBHE} רשומה בעברית עם \en{LLVM (CPU)}.
''' + hebrew + r' \en{HEEND}.}'+'\n'+r'''\setcounter{enumiv}{11}
\bibitem{qa-style}{\Large\itshape\bibentryprose{english}{BIBSTYLE Authored style retained.}}
\end{thebibliography}
\begin{englishprose}\noindent OUTSIDE English resumes normally.\par\end{englishprose}
\end{document}
'''


def _bib_marker(doc, marker):
    matches = [(i, rect) for i, page in enumerate(doc) for rect in page.search_for(marker)]
    if len(matches) != 1:
        raise AssertionError(f'{marker}: expected one visible occurrence, got {len(matches)}')
    return matches[0]


def _bib_line_extent(page, marker, exclude=None):
    rect = page.search_for(marker)[0]
    chars = []
    for block in page.get_text('rawdict')['blocks']:
        for line in block.get('lines', []):
            for span in line['spans']:
                for char in span['chars']:
                    box = fitz.Rect(char['bbox'])
                    if char['c'].strip() and rect.y0-.5 <= char['origin'][1] <= rect.y1+.5:
                        if exclude is None or not box.intersects(exclude):
                            chars.append(box)
    if not chars:
        raise AssertionError('no glyph extent for ' + marker)
    return min(b.x0 for b in chars), max(b.x1 for b in chars)


def assert_bibliography_paragraph_geometry(doc):
    first_en, en_start = _bib_marker(doc, 'BIBEN')
    last_en, en_end = _bib_marker(doc, 'ENEND')
    if last_en <= first_en:
        raise AssertionError('long English entry did not span physical pages')
    left, _ = _bib_line_extent(doc[last_en], 'ENEND')
    if abs(left-en_start.x0) > 1:
        raise AssertionError('English continuation does not start at local left reading edge')
    he_page, he_start = _bib_marker(doc, 'BIBHE')
    he_last, he_end = _bib_marker(doc, 'HEEND')
    labels = doc[he_page].search_for('[2]')
    if len(labels) != 1:
        raise AssertionError('missing native Hebrew-entry label [2]')
    _, right = _bib_line_extent(doc[he_page], 'BIBHE', labels[0])
    _, end_right = _bib_line_extent(doc[he_last], 'HEEND')
    if abs(right-end_right) > 1:
        raise AssertionError('Hebrew continuation does not end at local right reading edge')
    for number, marker in [(1, 'BIBEN'), (2, 'BIBHE'), (12, 'BIBSTYLE')]:
        page_num, body = _bib_marker(doc, marker)
        labels = doc[page_num].search_for(f'[{number}]')
        if len(labels) != 1 or labels[0].intersects(body):
            raise AssertionError(f'pending native label [{number}] overlaps entry body or is missing')
    for marker in ('STYLECONTROL', 'BIBSTYLE'):
        page_num, rect = _bib_marker(doc, marker)
        spans = [sp for b in doc[page_num].get_text('dict')['blocks'] for ln in b.get('lines', [])
                 for sp in ln['spans'] if marker in sp['text']]
        if len(spans) != 1:
            raise AssertionError('cannot identify authored style span')
        if marker == 'STYLECONTROL':
            control = (spans[0]['size'], spans[0]['font'], spans[0]['flags'], spans[0]['color'])
        elif control != (spans[0]['size'], spans[0]['font'], spans[0]['flags'], spans[0]['color']):
            raise AssertionError('entry overrides authored font/size/style/color')
    text = '\n'.join(p.get_text() for p in doc)
    if '25%' not in text or '&' not in text or 'OUTSIDE' not in text:
        raise AssertionError('escaped text or post-bibliography paragraph lost')


def assert_bibliography_paragraph_navigation(doc):
    expected = ['qa-he', 'qa-en', 'qa-style']
    links = [ln for page in doc for ln in page.get_links()
             if ln.get('nameddest', '').startswith('cite.')]
    if [ln['nameddest'] for ln in links] != ['cite.'+key for key in expected]:
        raise AssertionError('citation links changed semantic key order')
    names = doc.resolve_names()
    for key, marker, number in [('qa-en', 'BIBEN', 1), ('qa-he', 'BIBHE', 2), ('qa-style', 'BIBSTYLE', 12)]:
        target = names['cite.'+key]
        page_num, body = _bib_marker(doc, marker)
        if target['page'] != page_num:
            raise AssertionError('citation target page differs from matching entry')
        target_y = doc[page_num].rect.height-target['to'][1]
        if abs(target_y-body.y0) > 25:
            raise AssertionError('citation target is not adjacent to matching entry')
    for link, number in zip(links, [2, 1, 12]):
        digits = re.findall(r'\d+', doc[0].get_textbox(link['from']+(-.2,-.2,.2,.2)))
        if digits != [str(number)]:
            raise AssertionError('printed citation number no longer matches key identity')


class BibliographyParagraphRuntime(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        retained = os.environ.get('HLLPDF_BIB_TEST_EVIDENCE_DIR')
        cls.tmp = None if retained else tempfile.TemporaryDirectory(prefix='hll-bibparagraph-')
        cls.root = Path(retained) if retained else Path(cls.tmp.name)
        if retained:
            cls.root.mkdir(parents=True, exist_ok=False)
        fonts = str(font_dir()); cls.env = os.environ.copy()
        cls.env.update(OSFONTDIR=fonts, TTFONTS=fonts+'//:', HEBREW_LATEX_FONT_DIR=fonts,
                       SOURCE_DATE_EPOCH='1700000000', PYTHONDONTWRITEBYTECODE='1')
        cls.env.pop('HEBREW_LATEX_PROJECT_ROOT', None)

    @classmethod
    def tearDownClass(cls):
        if cls.tmp is not None:
            cls.tmp.cleanup()

    def compile_fixture(self, name, source):
        directory = self.root/name; directory.mkdir()
        for asset in ['preamble.tex', 'document_components.tex', 'reader_theme.tex']:
            shutil.copyfile(ROOT/'assets'/asset, directory/asset)
        (directory/'main.tex').write_text(source, encoding='utf-8')
        for number in range(1, 4):
            result = subprocess.run(['lualatex', '--no-shell-escape', '-halt-on-error',
                                     '-interaction=nonstopmode', 'main.tex'], cwd=directory,
                                    env=self.env, capture_output=True, text=True, timeout=120)
            (directory/f'pass-{number}.txt').write_text(result.stdout+result.stderr)
            self.assertEqual(result.returncode, 0, result.stdout[-3000:])
        self.assertNotIn('undefined', (directory/'main.log').read_text())
        return directory

    def test_local_entry_paragraphs_keep_native_labels_styles_and_navigation(self):
        profiles = [('hebrew','hebrew'),('english','english'),
                    ('hebrew-with-english','hebrew'),('english-with-hebrew','english'),
                    ('bilingual','hebrew'),('bilingual','english')]
        for profile, main in profiles:
            with self.subTest(profile=profile, main=main):
                directory = self.compile_fixture(profile+'-'+main, bibliography_paragraph_fixture(profile, main))
                with fitz.open(directory/'main.pdf') as doc:
                    assert_bibliography_paragraph_geometry(doc)
                    assert_bibliography_paragraph_navigation(doc)

    def test_previous_inline_and_unsafe_prose_have_independent_geometry_failures(self):
        source = bibliography_paragraph_fixture('hebrew-with-english', 'hebrew')
        inline = source.replace(r'\bibentryprose{english}{BIBEN', r'\en{BIBEN')
        directory = self.compile_fixture('negative-inline', inline)
        with fitz.open(directory/'main.pdf') as doc:
            assert_bibliography_paragraph_navigation(doc)
            with self.assertRaisesRegex(AssertionError, 'English continuation'):
                assert_bibliography_paragraph_geometry(doc)
        unsafe = source.replace(r'\bibentryprose{english}{BIBEN', r'\begin{englishprose}BIBEN', 1)
        unsafe = unsafe.replace(' ENEND.}', ' ENEND.\\end{englishprose}', 1)
        directory = self.compile_fixture('negative-unsafe-environment', unsafe)
        with fitz.open(directory/'main.pdf') as doc:
            assert_bibliography_paragraph_navigation(doc)
            with self.assertRaisesRegex(AssertionError, 'pending native label'):
                assert_bibliography_paragraph_geometry(doc)
        good = self.compile_fixture('navigation-control', source)
        mutation = good/'wrong-valid-citation.pdf'
        with fitz.open(good/'main.pdf') as doc:
            link = next(ln for ln in doc[0].get_links() if ln.get('nameddest') == 'cite.qa-en')
            action = doc.xref_object(link['xref'])
            self.assertEqual(action.count('(cite.qa-en)'), 1)
            doc.update_object(link['xref'], action.replace('(cite.qa-en)', '(cite.qa-style)'))
            doc.save(mutation)
        with fitz.open(mutation) as doc:
            assert_bibliography_paragraph_geometry(doc)
            with self.assertRaisesRegex(AssertionError, 'semantic key order'):
                assert_bibliography_paragraph_navigation(doc)



if __name__ == '__main__': unittest.main(verbosity=2)
