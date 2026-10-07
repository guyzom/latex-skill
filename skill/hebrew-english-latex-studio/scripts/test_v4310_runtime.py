#!/usr/bin/env python3
"""Real-engine controls for class-aware running heads and deep reference names.

Set HLLPDF_431_EVIDENCE_DIR to a NEW directory outside the skill to keep the
fixtures, logs, PDFs and measured glyphs. No automated result asserts that a
person or model viewed a page. Mutations are intentionally defective controls.
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
from check_pdf_render import _visible_parenthesis_overrides
from font_paths import font_dir

ROOT = Path(__file__).resolve().parent.parent
MAIN = 'נושא ראשי'
NEXT = 'הנושא הבא'
REFNAME = 'תת־פסקה'
THEMES = ('core', 'reader', 'clean')
CLASSES = ('article', 'report')


def compact(value: str) -> str:
    return ''.join(c for c in value if not c.isspace())


def physical_text(page, box: fitz.Rect) -> str:
    """Order an explicitly bounded single row by x, resolving visible parens.

    This is not a general bidi extractor. Parentheses are compared to the cmap
    of the embedded glyph, not just the logical ToUnicode map. Raster review
    remains necessary, including for Hebrew and the page outside this box.
    """
    overrides = _visible_parenthesis_overrides(page)
    chars = []
    for block in page.get_text('rawdict')['blocks']:
        for line in block.get('lines', []):
            for span in line['spans']:
                for char in span['chars']:
                    x, y = char['origin']
                    if box.x0 <= x <= box.x1 and box.y0 <= y <= box.y1:
                        c = char['c']
                        key = (ord(c), round(x, 3), round(y, 3)) if len(c) == 1 else None
                        chars.append((x, overrides.get(key, c)))
    return compact(''.join(c for _, c in sorted(chars)))


def header(page) -> str:
    return physical_text(page, fitz.Rect(page.rect.width / 2, 15, page.rect.width, 60))


def row(page, marker: str) -> str:
    hits = page.search_for(marker)
    if len(hits) != 1:
        raise AssertionError((marker, len(hits)))
    hit = hits[0]
    return physical_text(page, fitz.Rect(0, hit.y0, page.rect.width, hit.y1))


def document(body: str, *, cls='article', theme='core', head=True, extra='') -> str:
    return ('\\def\\lakitdocumentclass{' + cls + '}\n'
            '\\def\\lakitclassoptions{11pt,a4paper}\n'
            '\\def\\lakitlinespread{1.12}\n'
            '\\input{preamble.tex}\n' +
            ('' if theme == 'core' else '\\input{' + theme + '_theme.tex}\n') +
            '\\hypersetup{pdftitle={Running heads and reference controls},pdfauthor={Synthetic QA}}\n' +
            ('\\lakithead{בדיקת כותרות}\n' if head else '') + extra +
            '\\begin{document}\n' + body + '\n\\end{document}\n')


def matrix(cls: str, theme: str) -> str:
    top = 'section' if cls == 'article' else 'chapter'
    lower = 'subsection' if cls == 'article' else 'section'
    body = ('\\' + top + '{' + MAIN + '}\n'
            'זהו עמוד הפתיחה של הנושא הראשי. \\en{PAGEONE}\n\\clearpage\n'
            '\\' + lower + '*{הערה משנית}\n'
            'הערה זו אינה מחליפה את הנושא הראשי.\n'
            '\\subsubsection*{הערה עמוקה}\nזהו פירוט נוסף.\n'
            '\\paragraph*{הערה קצרה} הטקסט נמשך אחרי הכותרת.\n'
            '\\subparagraph*{פירוט מקומי} גם כאן נשמר שם הנושא הראשי.\n'
            '\\clearpage\n\\begin{englishprose}\n'
            '\\' + top + '[Alpha (SHORT)]{Alpha (NUMBERED)}\n'
            'The running head uses the short title, including its parentheses.\n'
            '\\end{englishprose}\n\\clearpage\n'
            'עברית אחרי חזרה מהכותרת באנגלית; שם הנושא נשאר באנגלית.\n'
            '\\clearpage\n\\begin{englishprose}\n'
            '\\' + top + '*{Beta (STARRED)}\n'
            'An unnumbered heading updates the correct class-level mark.\n'
            '\\end{englishprose}\n\\clearpage\n'
            'העמוד הבא נכתב בעברית; הכותרת שומרת את שפת המקור שלה.\n')
    return document(body, cls=cls, theme=theme)


def boundary() -> str:
    return document(r'''\section{נושא ראשי}
הטקסט בעמוד זה שייך לנושא הראשון.
\par
\vspace*{\dimexpr\textheight-\pagetotal-18pt\relax}
\section*{הנושא הבא}
כותרת זו וגוף הסעיף נמצאים בעמוד הבא.
''')


def references(cls: str) -> str:
    body = r'''\makeatletter
\typeout{HLL431-H1:\meaning\subparagraphautorefname}
\makeatother
\noindent\en{HREFONE} ראו \autoref{deep:target}.
\begin{englishprose}
\makeatletter
\typeout{HLL431-EN:\meaning\subparagraphautorefname}
\makeatother
\noindent ENREF See \autoref{deep:target}.
\end{englishprose}
\makeatletter
\typeout{HLL431-H2:\meaning\subparagraphautorefname}
\makeatother
\noindent\en{HREFTWO} ראו שוב \autoref{deep:target}.
\par
\noindent\en{UNLINKED} הפניה ללא קישור: \autoref*{deep:target}.
\clearpage
'''
    if cls == 'report':
        body += '\\chapter{פרק בדיקה}\n'
    body += r'''\section{ראשי}
\subsection{משני}
\subsubsection{עמוק}
\paragraph{פסקה} טקסט פסקה.
\subparagraph{פירוט}\label{deep:target} זהו יעד ההפניה העמוקה.
'''
    return document(body, cls=cls, head=False, extra='\\setcounter{secnumdepth}{5}\n')


def replace_once(source: str, old: str, new: str) -> str:
    if source.count(old) != 1:
        raise AssertionError('mutation anchor must match exactly once: ' + old)
    return source.replace(old, new, 1)


def mutate(core: str, kind: str | None) -> str:
    if kind is None:
        return core
    if kind == 'level':
        return replace_once(core,
            r'\ifx\HEB@sectionkind\HEB@mainsection', r'\iftrue')
    if kind == 'language':
        return replace_once(core,
            r'\iflanguage{english}{\markboth{\en{#1}}{}}{\markboth{\h{#1}}{}}',
            r'\markboth{\h{#1}}{}')
    if kind == 'timing':
        old = r'''\def\@ssect##1##2##3##4##5{%
      \HEBorigssect{##1}{##2}{##3}{##4}{##5}%
      % Lower starred headings must not replace the article's section mark.
      \ifx\HEB@sectionkind\HEB@mainsection
        \sectionmark{##5}%
      \fi
      \ignorespaces}'''
        new = r'''\def\@ssect##1##2##3##4##5{%
      \ifx\HEB@sectionkind\HEB@mainsection
        \sectionmark{##5}%
      \fi
      \HEBorigssect{##1}{##2}{##3}{##4}{##5}%
      \ignorespaces}'''
        return replace_once(core, old, new)
    if kind == 'reference':
        return replace_once(core, r'\def\subparagraphautorefname{תת־פסקה}%', '')
    raise ValueError(kind)


class RunningHeadRuntime(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        chosen = os.environ.get('HLLPDF_431_EVIDENCE_DIR')
        if chosen:
            cls.root = Path(chosen).resolve()
            if cls.root == ROOT or ROOT in cls.root.parents:
                raise ValueError('evidence must be outside the skill')
            cls.root.mkdir(parents=True, exist_ok=False)
        else:
            cls.tmp = tempfile.TemporaryDirectory(prefix='hllpdf431-runtime-')
            cls.addClassCleanup(cls.tmp.cleanup)
            cls.root = Path(cls.tmp.name)
        # Cache bytes are runtime data, not evidence; always remove the cache.
        cls.cache = tempfile.TemporaryDirectory(prefix='hllpdf431-font-cache-')
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
        cls.compile('mutation-level', matrix('article', 'reader'), mutation='level')
        for doc_class in CLASSES:
            cls.compile('mutation-language-' + doc_class, matrix(doc_class, 'reader'), mutation='language')
        cls.compile('page-boundary', boundary())
        cls.compile('mutation-timing', boundary(), mutation='timing')
        for doc_class in CLASSES:
            cls.compile('references-' + doc_class, references(doc_class))
        cls.compile('mutation-reference', references('article'), mutation='reference')
        inert = document(r'\section*{בלי כותרת רצה} מקור רגיל.\par\subsection*{פירוט} תוכן נוסף.', head=False,
                         extra=r'''\makeatletter
\let\SavedStart\@startsection
\let\SavedStar\@ssect
\AtEndDocument{\ifx\SavedStart\@startsection\else\errmessage{INERT START CHANGED}\fi
\ifx\SavedStar\@ssect\else\errmessage{INERT STAR CHANGED}\fi}
\makeatother
''')
        cls.compile('inert', inert)
        cls.compile('inert-mutation', inert, mutation='level')
        manual = document(r'''\section*{כותרת אוטומטית}
\markboth{\en{Manual (CUSTOM)}}{}
הבחירה הידנית היא הקובעת.\clearpage
הבחירה הידנית נשמרת גם בעמוד הבא.
''', extra='\\lakithead{בדיקת כותרות}\n')
        cls.compile('manual-override', manual)
        unchanged = document(r'''\section{נושא ראשי}
מסמך עברי רגיל ללא כותרת משנית מכוכבת.\clearpage
\section*{הנושא הבא}
זהו סעיף ראשי לא ממוספר.
''')
        cls.compile('unchanged', unchanged)
        cls.compile('unchanged-mutation', unchanged, mutation='language')
        cls.write_summary()

    @classmethod
    def write_summary(cls):
        (cls.root / 'measurements.json').write_text(json.dumps(cls.results, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    @classmethod
    def compile(cls, name: str, source: str, *, mutation: str | None = None):
        p = cls.root / name
        p.mkdir()
        (p / 'preamble.tex').write_text(mutate(cls.core, mutation), encoding='utf-8')
        for asset in ('reader_theme.tex', 'clean_theme.tex'):
            shutil.copyfile(ROOT / 'assets' / asset, p / asset)
        (p / 'probe.tex').write_text(source, encoding='utf-8')
        # Explicit per-fixture project root: never inherit the harness's root.
        env = dict(cls.env, HEBREW_LATEX_PROJECT_ROOT=str(p))
        for n in (1, 2, 3):
            proc = subprocess.run(['lualatex', '--no-shell-escape', '-halt-on-error',
                                   '-interaction=nonstopmode', 'probe.tex'], cwd=p, env=env,
                                  capture_output=True, text=True, timeout=180)
            (p / f'pass-{n}.txt').write_text(proc.stdout + proc.stderr, encoding='utf-8')
            if proc.returncode:
                raise AssertionError(name + ': ' + proc.stdout[-6000:] + proc.stderr)
        cls.paths[name] = p
        with fitz.open(p / 'probe.pdf') as pdf:
            cls.results[name] = {'pages': len(pdf), 'headers_physical': [header(pg) for pg in pdf],
                                 'pdf_sha256': hashlib.sha256((p / 'probe.pdf').read_bytes()).hexdigest(),
                                 'mutation': mutation, 'visual_review_claimed': False}

    def test_01_article_lower_starred_levels_keep_the_main_section(self):
        for theme in THEMES:
            result = self.results['article-' + theme]
            self.assertEqual(result['pages'], 6, theme)
            self.assertEqual(result['headers_physical'][:2], [compact(MAIN)[::-1]] * 2, theme)

    def test_02_report_preserves_chapter_scope_and_plain_opening_pages(self):
        for theme in THEMES:
            result = self.results['report-' + theme]
            self.assertEqual(result['pages'], 6, theme)
            self.assertEqual([result['headers_physical'][i] for i in (0, 2, 4)], ['', '', ''], theme)
            self.assertEqual(result['headers_physical'][1], compact(MAIN)[::-1], theme)

    def test_03_numbered_short_titles_preserve_english_after_return_to_hebrew(self):
        for doc_class in CLASSES:
            for theme in THEMES:
                result = self.results[doc_class + '-' + theme]
                self.assertEqual(result['headers_physical'][3], 'Alpha(SHORT)', (doc_class, theme))
                if doc_class == 'article':
                    self.assertEqual(result['headers_physical'][2], 'Alpha(SHORT)', theme)

    def test_04_starred_titles_preserve_english_after_return_to_hebrew(self):
        for doc_class in CLASSES:
            for theme in THEMES:
                result = self.results[doc_class + '-' + theme]
                self.assertEqual(result['headers_physical'][5], 'Beta(STARRED)', (doc_class, theme))
                if doc_class == 'article':
                    self.assertEqual(result['headers_physical'][4], 'Beta(STARRED)', theme)

    def test_05_level_and_language_mutations_reproduce_each_defect(self):
        self.assertNotEqual(self.results['mutation-level']['headers_physical'][1], compact(MAIN)[::-1])
        for doc_class in CLASSES:
            actual = self.results['mutation-language-' + doc_class]['headers_physical']
            self.assertNotEqual(actual[3], 'Alpha(SHORT)', doc_class)
            self.assertNotEqual(actual[5], 'Beta(STARRED)', doc_class)

    def test_06_new_heading_does_not_rename_the_previous_page(self):
        self.assertEqual(self.results['page-boundary']['pages'], 2)
        self.assertEqual(self.results['page-boundary']['headers_physical'], [compact(MAIN)[::-1], compact(NEXT)[::-1]])
        self.assertNotEqual(self.results['mutation-timing']['headers_physical'][0], compact(MAIN)[::-1])
        with fitz.open(self.paths['page-boundary'] / 'probe.pdf') as after, fitz.open(self.paths['mutation-timing'] / 'probe.pdf') as before:
            self.assertEqual(len(after), len(before))
            for a, b in zip(after, before):
                # Timing changes the running head only, never the body layout.
                clip = fitz.Rect(0, 62, a.rect.width, a.rect.height)
                self.assertEqual(a.get_pixmap(dpi=144, clip=clip).samples,
                                 b.get_pixmap(dpi=144, clip=clip).samples)

    def test_07_deep_reference_names_follow_each_language_switch(self):
        for doc_class in CLASSES:
            p = self.paths['references-' + doc_class]
            log = (p / 'probe.log').read_text(encoding='utf-8')
            self.assertRegex(log, 'HLL431-H1:.*' + REFNAME)
            self.assertRegex(log, 'HLL431-EN:.*subparagraph')
            self.assertRegex(log, 'HLL431-H2:.*' + REFNAME)
            with fitz.open(p / 'probe.pdf') as pdf:
                for marker in ('HREFONE', 'HREFTWO', 'UNLINKED'):
                    actual = row(pdf[0], marker)
                    self.assertIn(REFNAME[::-1], actual, (doc_class, marker, actual))
                    self.assertNotIn('subparagraph', actual)
                self.assertIn('subparagraph', row(pdf[0], 'ENREF'))

    def test_08_reference_targets_numbers_and_starred_link_policy_are_intact(self):
        for doc_class in CLASSES:
            with fitz.open(self.paths['references-' + doc_class] / 'probe.pdf') as pdf:
                self.assertEqual(len(pdf), 2)
                links = pdf[0].get_links()
                self.assertEqual(len(links), 3)
                names = {link.get('nameddest') for link in links}
                self.assertEqual(len(names), 1)
                name = names.pop()
                self.assertTrue(name.startswith('subparagraph.'), name)
                self.assertEqual(pdf.resolve_names()[name]['page'], 1)
                for marker in ('HREFONE', 'ENREF', 'HREFTWO', 'UNLINKED'):
                    self.assertIn('1.1.1.1.1', row(pdf[0], marker), marker)

    def test_09_reference_mutation_restores_the_english_leak(self):
        with fitz.open(self.paths['mutation-reference'] / 'probe.pdf') as pdf:
            self.assertIn('subparagraph', row(pdf[0], 'HREFONE'))
            self.assertIn('subparagraph', row(pdf[0], 'HREFTWO'))
            self.assertNotIn(REFNAME[::-1], row(pdf[0], 'HREFONE'))

    def test_10_optional_head_is_inert_and_repeated_setup_keeps_manual_override(self):
        with fitz.open(self.paths['inert'] / 'probe.pdf') as pdf:
            self.assertTrue(all(not header(pg) for pg in pdf))
        self.assertEqual((self.paths['inert'] / 'probe.pdf').read_bytes(),
                         (self.paths['inert-mutation'] / 'probe.pdf').read_bytes())
        self.assertEqual(self.results['manual-override']['headers_physical'], ['Manual(CUSTOM)'] * 2)

    def test_11_hebrew_only_control_is_byte_identical(self):
        self.assertEqual((self.paths['unchanged'] / 'probe.pdf').read_bytes(),
                         (self.paths['unchanged-mutation'] / 'probe.pdf').read_bytes())

    def test_12_fixed_fixtures_have_a4_no_missing_glyphs_or_overflow(self):
        for name, p in self.paths.items():
            if name.startswith('mutation'):
                continue
            log = (p / 'probe.log').read_text(encoding='utf-8')
            for unwanted in ('Missing character:', 'Overfull \\hbox', 'Overfull \\vbox', 'undefined references'):
                self.assertNotIn(unwanted, log, name)
            with fitz.open(p / 'probe.pdf') as pdf:
                self.assertTrue(pdf.metadata['title'])
                for pg in pdf:
                    self.assertAlmostEqual(pg.rect.width, 595.276, places=1)
                    self.assertAlmostEqual(pg.rect.height, 841.89, places=1)

    def test_13_managed_build_accepts_both_fixes_with_reproducibility(self):
        for name in ('article-reader', 'references-article'):
            p = self.paths[name]
            expected = (p / 'probe.pdf').read_bytes()
            env = dict(self.env, HEBREW_LATEX_PROJECT_ROOT=str(p), REPRO='1')
            for key in ('CONTENT_PROFILE', 'EXPECTED_PAPER', 'SECTION_MACROS', 'PDF_REQUIRE_TITLE',
                        'PDF_MIN_BOOKMARKS', 'PDF_MIN_BOOKMARK_DEPTH', 'PDF_WARN_NO_OUTLINE_AFTER',
                        'MAX_CROSS_PAGE_DESTINATIONS', 'DIRECT_NAVIGATION_DESTINATIONS'):
                env.pop(key, None)
            proc = subprocess.run(['bash', str(ROOT / 'scripts/build.sh'), str(p / 'probe.tex')],
                                  cwd=p, env=env, capture_output=True, text=True, timeout=300)
            (p / 'managed-build.log').write_text(proc.stdout + proc.stderr, encoding='utf-8')
            self.assertEqual(proc.returncode, 0, name + ': ' + proc.stdout[-7000:] + proc.stderr)
            self.assertEqual((p / 'probe.pdf').read_bytes(), expected, name)
        self.write_summary()


if __name__ == '__main__':
    unittest.main(verbosity=2)
