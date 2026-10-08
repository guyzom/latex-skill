#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Original project code; scope and terms: ../LICENSING.md.
"""Real-engine controls for the fixed running title's independent language.

HLLPDF_432_EVIDENCE_DIR optionally preserves fixtures in a NEW external folder.
This suite measures glyph positions and bytes; it does not attest visual review.
"""
from __future__ import annotations
import hashlib
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
from font_paths import font_dir
from test_v4310_runtime import physical_text, header as section_header

ROOT = Path(__file__).resolve().parent.parent
TITLE = 'Field Guide (CPU) [v2]'
COMPACT = 'FieldGuide(CPU)[v2]'
CLASSES = ('article', 'report')
THEMES = ('core', 'reader', 'clean')


def fixed_header(page):
    return physical_text(page, fitz.Rect(0, 15, page.rect.width / 2, 60))


def setup_title(title=TITLE, lang='english'):
    return ('\\selectlanguage{' + lang + '}\n\\lakithead{' + title + '}\n'
            '\\selectlanguage{hebrew}\n')


def document(body, *, doc_class='article', theme='core', setup=None, before='', after=''):
    if setup is None:
        setup = setup_title()
    return ('\\def\\lakitdocumentclass{' + doc_class + '}\n'
            '\\def\\lakitclassoptions{11pt,a4paper}\n'
            '\\def\\lakitlinespread{1.12}\n\\input{preamble.tex}\n' +
            ('' if theme == 'core' else '\\input{' + theme + '_theme.tex}\n') +
            '\\hypersetup{pdfauthor={Synthetic QA}}\n' + before + setup + after +
            '\\begin{document}\n' + body + '\n\\end{document}\n')


def matrix(doc_class, theme):
    top = 'section' if doc_class == 'article' else 'chapter'
    body = ('\\' + top + '{נושא ראשי}\n'
            'הכותרת הקבועה הוגדרה באנגלית. הכותרת השנייה מציגה את הנושא הנוכחי.\n'
            '\\begin{notebox}הבדיקה משתמשת בנתוני דמה בלבד; גודל הנייר והעיצוב נשמרים.\\end{notebox}\n'
            '\\begin{englishprose}Expected fixed title: ' + TITLE + '.\\end{englishprose}\n'
            '\\clearpage\n'
            'עמוד המשך בעברית. הסוגריים בשם המסמך צריכים להישאר בכיוון האנגלי.\n'
            '\\[ E = mc^2 \\]\n'
            '\\clearpage\n\\begin{englishprose}\n\\' + top + '[Next (short)]{Next (topic)}\n'
            'The section title and the fixed document title have independent language choices.\n'
            '\\end{englishprose}\n\\clearpage\n'
            'הטקסט חזר לעברית. שם הנושא ושם המסמך שומרים על שפתם המקורית.\n')
    return document(body, doc_class=doc_class, theme=theme)


def mutate(core, kind=None):
    if kind is None:
        return core
    pattern = r'  % <hllpdf:fixed-head-language>.*?  % </hllpdf:fixed-head-language>'
    matches = list(re.finditer(pattern, core, re.S))
    if len(matches) != 1:
        raise AssertionError('fixed-title mutation boundary changed')
    if kind == 'old':
        replacement = r'  \fancyhead[R]{\small\textcolor{cGray}{\h{#1}}}%'
    elif kind == 'late':
        replacement = r'''  \fancyhead[R]{\small\textcolor{cGray}{%
    \iflanguage{english}{\en{#1}}{\h{#1}}}}%'''
    else:
        raise ValueError(kind)
    return core[:matches[0].start()] + replacement + core[matches[0].end():]


class FixedTitleRuntime(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        chosen = os.environ.get('HLLPDF_432_EVIDENCE_DIR')
        if chosen:
            cls.root = Path(chosen).resolve()
            if cls.root == ROOT or ROOT in cls.root.parents:
                raise ValueError('evidence must be outside the skill')
            cls.root.mkdir(parents=True, exist_ok=False)
        else:
            cls.tmp = tempfile.TemporaryDirectory(prefix='hllpdf432-runtime-')
            cls.addClassCleanup(cls.tmp.cleanup)
            cls.root = Path(cls.tmp.name)
        cls.cache = tempfile.TemporaryDirectory(prefix='hllpdf432-font-cache-')
        cls.addClassCleanup(cls.cache.cleanup)
        fonts = str(font_dir())
        cls.env = dict(os.environ, HEBREW_LATEX_FONT_DIR=fonts, OSFONTDIR=fonts + ':',
                       TTFONTS=fonts + ':', TEXMFCACHE=cls.cache.name,
                       TEXMFVAR=cls.cache.name, SOURCE_DATE_EPOCH='1700000000',
                       TZ='UTC', PYTHONDONTWRITEBYTECODE='1')
        cls.core = (ROOT / 'assets/preamble.tex').read_text(encoding='utf-8')
        cls.paths = {}
        cls.results = {}
        for doc_class in CLASSES:
            for theme in THEMES:
                cls.compile(doc_class + '-' + theme, matrix(doc_class, theme))
        for mutation in ('old', 'late'):
            cls.compile('mutation-' + mutation, matrix('article', 'reader'), mutation=mutation)
        repeat = r'''\section*{נושא ראשי}
השם הראשון הוגדר באנגלית.\clearpage
\lakithead{כותרת בעברית}
השם השני הוגדר בעברית; אין לשנות את הכותרת של העמוד שכבר הופק.\clearpage
\selectlanguage{english}\lakithead{Revision (B) [12]}\selectlanguage{hebrew}
שם אנגלי חדש נשמר גם לאחר החזרה לעברית.
'''
        cls.compile('repeat', document(repeat))
        wrapped = matrix('article', 'core').replace(setup_title(),
                        setup_title(r'\en{' + TITLE + '}', lang='hebrew'), 1)
        cls.compile('wrapped', wrapped)
        short = r'\section*{נושא ראשי}בדיקה קצרה עם כותרת קבועה.'
        cls.compile('metadata-before', document(short, before='\\hypersetup{pdftitle={Explicit metadata}}\n'))
        cls.compile('metadata-after', document(short, after='\\lakitpdftitle{Later metadata}\n'))
        cls.compile('manual', document(short, after=r'\fancyhead[R]{\en{Manual (title) [9]}}'+'\n'))
        inert = document(short, setup='', before='\\hypersetup{pdftitle={Inert control}}\n')
        cls.compile('inert', inert)
        cls.compile('inert-old', inert, mutation='old')
        hebrew = document(short, setup=setup_title('כותרת בעברית', lang='hebrew'))
        cls.compile('hebrew', hebrew)
        cls.compile('hebrew-old', hebrew, mutation='old')
        cls.write_summary()

    @classmethod
    def write_summary(cls):
        (cls.root / 'measurements.json').write_text(json.dumps(cls.results, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')

    @classmethod
    def compile(cls, name, source, *, mutation=None):
        directory = cls.root / name
        directory.mkdir()
        (directory / 'preamble.tex').write_text(mutate(cls.core, mutation), encoding='utf-8')
        for asset in ('reader_theme.tex', 'clean_theme.tex'):
            shutil.copyfile(ROOT / 'assets' / asset, directory / asset)
        (directory / 'probe.tex').write_text(source, encoding='utf-8')
        env = dict(cls.env, HEBREW_LATEX_PROJECT_ROOT=str(directory))
        for i in (1, 2, 3):
            r = subprocess.run(['lualatex', '--no-shell-escape', '-halt-on-error',
                                '-interaction=nonstopmode', 'probe.tex'],
                               cwd=directory, env=env, capture_output=True, text=True, timeout=180)
            (directory / f'pass-{i}.txt').write_text(r.stdout + r.stderr, encoding='utf-8')
            if r.returncode:
                raise AssertionError(name + ': ' + r.stdout[-6000:] + r.stderr)
        cls.paths[name] = directory
        with fitz.open(directory / 'probe.pdf') as pdf:
            cls.results[name] = dict(pages=len(pdf), fixed_headers=[fixed_header(p) for p in pdf],
                                     section_headers=[section_header(p) for p in pdf],
                                     title=pdf.metadata['title'], mutation=mutation,
                                     pdf_sha256=hashlib.sha256((directory / 'probe.pdf').read_bytes()).hexdigest(),
                                     visual_review_claimed=False)

    def test_01_english_fixed_title_survives_language_changes_in_all_themes(self):
        for doc_class in CLASSES:
            for theme in THEMES:
                with self.subTest(doc_class=doc_class, theme=theme):
                    result = self.results[doc_class + '-' + theme]
                    self.assertEqual(result['pages'], 4)
                    expected = [COMPACT] * 4 if doc_class == 'article' else ['', COMPACT, '', COMPACT]
                    self.assertEqual(result['fixed_headers'], expected)

    def test_02_section_language_and_plain_chapter_openings_are_unchanged(self):
        for doc_class in CLASSES:
            for theme in THEMES:
                with self.subTest(doc_class=doc_class, theme=theme):
                    expected = ['ישאראשונ'] * 2 + ['Next(short)'] * 2
                    if doc_class == 'report':
                        expected[0] = expected[2] = ''
                    self.assertEqual(self.results[doc_class + '-' + theme]['section_headers'], expected)

    def test_03_metadata_fallback_and_explicit_overrides_remain_intact(self):
        for doc_class in CLASSES:
            for theme in THEMES:
                self.assertEqual(self.results[doc_class + '-' + theme]['title'], TITLE)
        self.assertEqual(self.results['metadata-before']['title'], 'Explicit metadata')
        self.assertEqual(self.results['metadata-after']['title'], 'Later metadata')
        self.assertEqual(self.results['repeat']['title'], TITLE)

    def test_04_repeated_setup_captures_each_new_language(self):
        self.assertEqual(self.results['repeat']['fixed_headers'],
                         [COMPACT, 'תירבעבתרתוכ', 'Revision(B)[12]'])
        self.assertEqual(self.results['repeat']['section_headers'], ['ישאראשונ'] * 3)

    def test_05_explicit_english_islands_and_manual_headers_still_work(self):
        self.assertEqual(self.results['wrapped']['fixed_headers'], [COMPACT] * 4)
        self.assertEqual(self.results['manual']['fixed_headers'], ['Manual(title)[9]'])

    def test_06_both_independent_mutations_reproduce_the_defect(self):
        for name in ('mutation-old', 'mutation-late'):
            with self.subTest(name=name):
                self.assertEqual(self.results[name]['pages'], 4)
                self.assertTrue(all(x and x != COMPACT for x in self.results[name]['fixed_headers']))
                self.assertEqual(self.results[name]['section_headers'],
                                 self.results['article-reader']['section_headers'])

    def test_07_mutations_change_the_title_not_body_pagination_or_rasters(self):
        with fitz.open(self.paths['article-reader'] / 'probe.pdf') as after:
            for name in ('mutation-old', 'mutation-late'):
                with fitz.open(self.paths[name] / 'probe.pdf') as before:
                    self.assertEqual(len(before), len(after))
                    for a, b in zip(after, before):
                        clip = fitz.Rect(0, 62, a.rect.width, a.rect.height)
                        self.assertEqual(a.get_pixmap(dpi=144, clip=clip).samples,
                                         b.get_pixmap(dpi=144, clip=clip).samples)

    def test_08_hebrew_and_inert_outputs_are_byte_identical(self):
        for name in ('hebrew', 'inert'):
            with self.subTest(name=name):
                self.assertEqual((self.paths[name] / 'probe.pdf').read_bytes(),
                                 (self.paths[name + '-old'] / 'probe.pdf').read_bytes())
        self.assertEqual(self.results['inert']['fixed_headers'], [''])
        self.assertEqual(self.results['hebrew']['fixed_headers'], ['תירבעבתרתוכ'])

    def test_09_no_missing_glyphs_overflow_or_non_A4_pages(self):
        for name, directory in self.paths.items():
            with self.subTest(name=name):
                log = (directory / 'probe.log').read_text(encoding='utf-8')
                self.assertNotIn('Missing character:', log)
                self.assertNotIn('Overfull \\hbox', log)
                self.assertNotIn('Overfull \\vbox', log)
                with fitz.open(directory / 'probe.pdf') as pdf:
                    for page in pdf:
                        self.assertLess(abs(page.rect.width - 595.276), 1)
                        self.assertLess(abs(page.rect.height - 841.89), 1)

    def test_10_managed_build_is_reproducible(self):
        source = self.paths['article-reader']
        directory = self.root / 'production'
        directory.mkdir()
        for name in ('probe.tex', 'preamble.tex', 'reader_theme.tex'):
            shutil.copyfile(source / name, directory / name)
        env = dict(self.env, HEBREW_LATEX_PROJECT_ROOT=str(directory), REPRO='1')
        r = subprocess.run(['bash', str(ROOT / 'scripts/build.sh'), str(directory / 'probe.tex')],
                           cwd=directory, env=env, capture_output=True, text=True, timeout=240)
        (directory / 'build.log.txt').write_text(r.stdout + r.stderr, encoding='utf-8')
        self.assertEqual(r.returncode, 0, r.stdout[-6000:] + r.stderr)
        with fitz.open(directory / 'probe.pdf') as pdf:
            self.assertEqual([fixed_header(p) for p in pdf], [COMPACT] * 4)
        # The production tool does its own clean reproducibility pass; do not
        # confuse it with direct-engine byte identity across differing flags.
        self.results['production'] = dict(pages=4, managed_build_returncode=r.returncode,
                                         repro_requested=True, visual_review_claimed=False,
                                         pdf_sha256=hashlib.sha256((directory / 'probe.pdf').read_bytes()).hexdigest())
        self.write_summary()


if __name__ == '__main__':
    unittest.main(verbosity=2)
