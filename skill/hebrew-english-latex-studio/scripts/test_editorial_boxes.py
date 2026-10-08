#!/usr/bin/env python3
"""Real-engine title/body distinction for ordinary reference-theme callouts.

The default run checks source coverage and the negative-control boundary without
running TeX. ``--with-engine`` adds two native-language documents exercising every
ordinary semantic environment in both local languages, optional titles, nesting
and page flow, plus old-style and independent body-color mutation counterparts.
Both mutations must fail the same measured PDF contract. These
geometry checks are not a substitute for inspecting rendered pages. A NEW
HLLPDF_EDITORIAL_BOXES_EVIDENCE_DIR outside the skill preserves the evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
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

ROOT = Path(__file__).resolve().parent.parent
WRAPPERS = ('defbox', 'thmbox', 'notebox', 'exbox', 'warnbox', 'keybox')
EVIDENCE_DIR: Path | None = None


def marker(token):
    return r'\en{' + token + '}'


def sentence(language, token):
    return (marker(token) + ' A distinct point with its own context.' if language == 'english'
            else 'נקודה מובחנת בעלת הקשר. ' + marker(token))


def heading(language, token):
    return (marker(token) + ' A bounded heading' if language == 'english'
            else 'כותרת מוגדרת ' + marker(token))


def document(main):
    other = 'hebrew' if main == 'english' else 'english'
    source = (fr'\def\lakitlanguageprofile{{{main}}}\def\lakitmainlanguage{{{main}}}' + '\n'
              + r'\def\lakitdocumentclass{article}\def\lakitclassoptions{11pt,a4paper}' + '\n'
              + r'\def\lakitgeometryoptions{margin=2.2cm,headheight=14pt}' + '\n'
              + r'\def\lakitlinespread{1.08}\input{preamble.tex}\input{reference_theme.tex}' + '\n'
              + r'\pagestyle{plain}\hypersetup{pdftitle={Synthetic ordinary callout controls},pdfauthor={Synthetic QA}}' + '\n'
              + r'\begin{document}' + '\n')
    pairs = []
    for local, prefix in ((main, 'NATIVE'), (other, 'MINORITY')):
        if prefix == 'MINORITY':
            source += r'\clearpage' + '\n' + fr'\begin{{{other}prose}}' + '\n'
        for index, wrapper in enumerate(WRAPPERS):
            title, body = f'{prefix}TITLE{index}', f'{prefix}BODY{index}'
            pairs.append({'environment': wrapper, 'local_language': local,
                          'title': title, 'body': body})
            source += (fr'\begin{{{wrapper}}}[nobreak=true,frametitle={{{heading(local, title)}}}]' + '\n'
                       + sentence(local, body) + '\n'
                       + r'\[f(x)=\frac{x^2}{1+x^2},\qquad x\in\mathbb R.\]' + '\n'
                       + fr'\end{{{wrapper}}}' + '\n')
        if prefix == 'MINORITY':
            source += fr'\end{{{other}prose}}' + '\n'
    source += r'\clearpage' + '\n'
    source += r'\begin{notebox}[nobreak=true]' + '\n'
    source += sentence(main, 'UNTITLEDBODY') + '\n' + r'\end{notebox}' + '\n'
    source += fr'\begin{{notebox}}[nobreak=true,frametitle={{{heading(main, "OUTERTITLE")}}}]' + '\n'
    source += sentence(main, 'OUTERBODY') + '\n'
    source += r'\begin{notebox}[nobreak=true]' + '\n'
    source += sentence(main, 'INNERBODY') + '\n' + r'\end{notebox}' + '\n'
    source += sentence(main, 'OUTERAFTER') + '\n' + r'\end{notebox}' + '\n'
    wrapped = ('A contextual heading whose full wording must stay readable. ' * 4
               if main == 'english' else 'כותרת בעלת הקשר שצריכה להישאר קריאה בשלמותה. ' * 5)
    source += (r'\begin{notebox}[nobreak=true,frametitle={' + marker('WRAPSTART') + ' '
               + wrapped + marker('WRAPEND') + '}]\n'
               + sentence(main, 'WRAPBODY') + '\n' + r'\end{notebox}' + '\n')
    source += (r'\begin{notebox}[nobreak=true,backgroundcolor=black!10,'
               + r'frametitlebackgroundcolor=black!15,frametitle={' + marker('OVERRIDETITLE') + '}]\n'
               + sentence(main, 'OVERRIDEBODY') + '\n' + r'\end{notebox}' + '\n')
    source += (fr'\begin{{notebox}}[nobreak=true,frametitle={{{heading(main, "SCOPEDTITLE")}}}]' + '\n'
               + sentence(main, 'SCOPEDBODY') + '\n' + r'\end{notebox}' + '\n'
               + sentence(main, 'OUTSIDEBODY') + '\n')
    source += (r'\clearpage\vspace*{.56\textheight}' + '\n'
               + fr'\begin{{notebox}}[frametitle={{{heading(main, "SPLITTITLE")}}}]' + '\n')
    for index in range(34):
        source += sentence(main, f'SPLITROW{index:02d}') + r'\par' + '\n'
    source += r'\end{notebox}' + '\n' + sentence(main, 'SPLITAFTER') + '\n' + r'\end{document}' + '\n'
    return source, pairs


def old_swap(theme):
    """Restore the actual visual fault at the owning style, not the checker."""
    marker_text = r'\mdfdefinestyle{hllpdfreferencetheme}{%'
    if theme.count(marker_text) != 1:
        raise AssertionError('ordinary callout style mutation target drifted')
    prefix, style = theme.split(marker_text)
    if style.count('backgroundcolor=white,') != 1 or style.count('frametitlebackgroundcolor=black!5,') != 1:
        raise AssertionError('title/body mutation targets drifted')
    style = style.replace('frametitlebackgroundcolor=black!5,', 'frametitlebackgroundcolor=white,', 1)
    for wrapper, color in zip(WRAPPERS, ('cBlueBg', 'cGreenBg', 'cAmberBg', 'cPurpleBg', 'cRedBg', 'cTealBg')):
        old = r'\renewmdenv[style=hllpdfreferencetheme,linecolor=black]{' + wrapper + '}'
        if style.count(old) != 1:
            raise AssertionError('old palette mutation target drifted: '+wrapper)
        style = style.replace(old, r'\renewmdenv[style=hllpdfreferencetheme,linecolor=black,backgroundcolor='
                              + color + ']{' + wrapper + '}', 1)
    return prefix + marker_text + style


def nonwhite_body(theme):
    """Change only the body paint so title and body assertions are independent."""
    marker_text = r'\mdfdefinestyle{hllpdfreferencetheme}{%'
    if theme.count(marker_text) != 1:
        raise AssertionError('ordinary callout body mutation owner drifted')
    prefix, style = theme.split(marker_text)
    if style.count('backgroundcolor=white,') != 1:
        raise AssertionError('ordinary callout body mutation target drifted')
    return prefix + marker_text + style.replace('backgroundcolor=white,',
                                                 'backgroundcolor=black!10,', 1)


def occurrence(pdf, token):
    matches = [(page.number, rect) for page in pdf for rect in page.search_for(token)]
    if len(matches) != 1:
        raise AssertionError(('marker must occur once', token, matches))
    return matches[0]


def gray_rectangles(page, expected):
    result = []
    for drawing in page.get_drawings():
        fill = drawing.get('fill')
        rect = drawing['rect']
        if (fill is not None and len(fill) == 3 and max(abs(value - expected) for value in fill) < .002
                and rect.width > 50 and rect.height > 3):
            if not any(max(abs(a-b) for a, b in zip(rect, old)) < .02 for old in result):
                result.append(rect)
    return result


def center(rect):
    return fitz.Point((rect.x0+rect.x1)/2, (rect.y0+rect.y1)/2)


def strip_gray(page, rect, expected):
    """Sample a clear strip at the measured field edge, away from text ink."""
    strip = fitz.Rect(rect.x0 + 1.5, (rect.y0+rect.y1)/2 - .4,
                      rect.x0 + 2.5, (rect.y0+rect.y1)/2 + .4)
    pixmap = page.get_pixmap(matrix=fitz.Matrix(4, 4), clip=strip,
                             colorspace=fitz.csGRAY, alpha=False)
    values = list(pixmap.samples)
    if not values or abs(sum(values)/len(values) - expected*255) > 2:
        raise AssertionError(('painted field edge is the wrong gray', rect, values, expected))
    return {'strip': list(strip), 'mean_gray': sum(values)/len(values)}


def white_body(pdf, token):
    page_number, text = occurrence(pdf, token)
    page = pdf[page_number]
    pale = gray_rectangles(page, .95)
    if any(rect.contains(center(text)) for rect in pale):
        raise AssertionError(('body lies in a pale title/body field', token, text, pale))
    whites = [rect for rect in gray_rectangles(page, 1) if rect.contains(center(text))]
    if not whites:
        raise AssertionError(('body has no painted white field', token, text))
    # The closest containing field distinguishes a nested body from its parent.
    field = min(whites, key=lambda rect: rect.width*rect.height)
    measured = strip_gray(page, fitz.Rect(field.x0, text.y0, field.x1, text.y1), 1)
    return {'page': page_number+1, 'text': list(text), 'field': list(field), **measured}


def title_body_contract(pdf, title, body):
    page_number, text = occurrence(pdf, title)
    page = pdf[page_number]
    candidates = [rect for rect in gray_rectangles(page, .95) if rect.contains(center(text))]
    if len(candidates) != 1:
        raise AssertionError(('title must be inside exactly one pale title strip', title, text, candidates))
    strip = candidates[0]
    body_record = white_body(pdf, body)
    if page_number+1 != body_record['page'] or strip.y1 > body_record['text'][1]+2:
        raise AssertionError(('title strip and its white body are not ordered', title, body, strip, body_record))
    sampled = strip_gray(page, strip, .95)
    return {'title': title, 'body': body, 'page': page_number+1,
            'title_text': list(text), 'title_strip': list(strip),
            'body_record': body_record, **sampled}


class EditorialBoxContract(unittest.TestCase):
    def test_fixture_covers_every_declared_ordinary_box_in_native_and_minority_prose(self):
        for main in ('english', 'hebrew'):
            source, pairs = document(main)
            other = 'hebrew' if main == 'english' else 'english'
            self.assertEqual(len(pairs), 12)
            for locale in (main, other):
                local = [pair for pair in pairs if pair['local_language'] == locale]
                self.assertEqual({pair['environment'] for pair in local}, set(WRAPPERS))
                self.assertEqual(len(local), len(WRAPPERS))
            start, end = fr'\begin{{{other}prose}}', fr'\end{{{other}prose}}'
            self.assertEqual(source.count(start), 1)
            self.assertEqual(source.count(end), 1)
            before, minority = source.split(start)
            minority, after = minority.split(end)
            for pair in pairs:
                scope = before if pair['local_language'] == main else minority
                for role in ('title', 'body'):
                    self.assertEqual(source.count(marker(pair[role])), 1)
                    self.assertIn(marker(pair[role]), scope)
            self.assertIn(marker('SPLITROW33'), after)
            self.assertIn(marker('WRAPSTART'), after)
            self.assertIn(marker('INNERBODY'), after)

    def test_old_style_mutation_preserves_every_separate_reference_component_hook(self):
        original = (ROOT/'assets/reference_theme.tex').read_text(encoding='utf-8')
        mutated = old_swap(original)
        boundary = r'\mdfdefinestyle{hllpdfreferencetheme}{%'
        self.assertEqual(original.split(boundary)[0], mutated.split(boundary)[0])
        self.assertNotEqual(original, mutated)
        for wrapper, color in zip(WRAPPERS, ('cBlueBg', 'cGreenBg', 'cAmberBg', 'cPurpleBg', 'cRedBg', 'cTealBg')):
            restored = r'\renewmdenv[style=hllpdfreferencetheme,linecolor=black,backgroundcolor=' + color + ']{' + wrapper + '}'
            self.assertEqual(mutated.count(restored), 1)

    def test_negative_control_rejects_missing_duplicate_or_changed_owner_targets(self):
        original = (ROOT/'assets/reference_theme.tex').read_text(encoding='utf-8')
        boundary = r'\mdfdefinestyle{hllpdfreferencetheme}{%'
        prefix, ordinary = original.split(boundary)
        wrong = [original.replace(boundary, ''), original+boundary,
                 prefix+boundary+ordinary.replace('frametitlebackgroundcolor=black!5,', '', 1),
                 prefix+boundary+ordinary.replace(r'\renewmdenv[style=hllpdfreferencetheme,linecolor=black]{notebox}', '')]
        for source in wrong:
            with self.subTest(source_sha256=hashlib.sha256(source.encode()).hexdigest()), self.assertRaises(AssertionError):
                old_swap(source)

    def test_independent_body_mutation_retains_the_title_policy(self):
        original = (ROOT/'assets/reference_theme.tex').read_text(encoding='utf-8')
        mutated = nonwhite_body(original)
        self.assertNotEqual(original, mutated)
        self.assertEqual(mutated.count('frametitlebackgroundcolor=black!5,'),
                         original.count('frametitlebackgroundcolor=black!5,'))
        self.assertEqual(mutated.replace('backgroundcolor=black!10,',
                                        'backgroundcolor=white,', 1), original)
        boundary = r'\mdfdefinestyle{hllpdfreferencetheme}{%'
        prefix, ordinary = original.split(boundary)
        for source in (original.replace(boundary, ''), original+boundary,
                       prefix+boundary+ordinary.replace('backgroundcolor=white,', '', 1)):
            with self.assertRaises(AssertionError):
                nonwhite_body(source)


class EditorialBoxes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        keep = str(EVIDENCE_DIR) if EVIDENCE_DIR else os.environ.get('HLLPDF_EDITORIAL_BOXES_EVIDENCE_DIR')
        cls.tmp = None if keep else tempfile.TemporaryDirectory(prefix='hllpdf-editorial-boxes-')
        cls.root = Path(keep).resolve() if keep else Path(cls.tmp.name)
        if keep:
            if cls.root == ROOT or ROOT in cls.root.parents:
                raise ValueError('preserved evidence must be outside the skill')
            cls.root.mkdir(parents=True, exist_ok=False)
        cache = cls.root / 'tex-cache'
        variable = cls.root / 'tex-var'
        cache.mkdir()
        variable.mkdir()
        fonts = str(font_dir())
        cls.env = os.environ.copy()
        cls.env.update(HEBREW_LATEX_FONT_DIR=fonts, OSFONTDIR=fonts+':', TTFONTS=fonts+':',
                       SOURCE_DATE_EPOCH='1700000000', TZ='UTC', PYTHONDONTWRITEBYTECODE='1',
                       TEXMFCACHE=str(cache), TEXMFVAR=str(variable), TEXMFOUTPUT=str(cls.root))
        cls.results, cls.pairs = {}, {}
        cls.measurements = {main: {} for main in ('english', 'hebrew')}
        for main in ('english', 'hebrew'):
            source, cls.pairs[main] = document(main)
            for suffix, mutate in (('', lambda value: value),
                                   ('-old-swap', old_swap),
                                   ('-nonwhite-body', nonwhite_body)):
                name = main + suffix
                directory = cls.root/name
                directory.mkdir()
                shutil.copyfile(ROOT/'assets/preamble.tex', directory/'preamble.tex')
                theme = (ROOT/'assets/reference_theme.tex').read_text(encoding='utf-8')
                (directory/'reference_theme.tex').write_text(mutate(theme), encoding='utf-8')
                (directory/'main.tex').write_text(source, encoding='utf-8')
                env = dict(cls.env, HEBREW_LATEX_PROJECT_ROOT=str(directory))
                for number in (1, 2):
                    result = subprocess.run(['lualatex', '--no-shell-escape', '-halt-on-error',
                                             '-interaction=nonstopmode', 'main.tex'], cwd=directory,
                                            env=env, text=True, capture_output=True, timeout=180)
                    (directory/f'pass-{number}.txt').write_text(result.stdout+result.stderr, encoding='utf-8')
                    if result.returncode:
                        raise AssertionError(name+': '+result.stdout[-6000:])
                cls.results[name] = directory

    def test_all_six_boxes_have_pale_titles_and_white_bodies_in_both_locales(self):
        for main in ('english', 'hebrew'):
            with fitz.open(self.results[main]/'main.pdf') as pdf:
                measured = []
                for pair in self.pairs[main]:
                    with self.subTest(main=main, **pair):
                        measured.append({**pair, **title_body_contract(pdf, pair['title'], pair['body'])})
                self.assertEqual(len(measured), 12)
                self.measurements[main]['native_and_minority_boxes'] = measured

    def test_old_swapped_background_mutation_is_rejected_in_both_main_languages(self):
        for main in ('english', 'hebrew'):
            with self.subTest(main=main), fitz.open(self.results[main+'-old-swap']/'main.pdf') as pdf:
                with self.assertRaisesRegex(AssertionError,
                        'title must be inside exactly one pale title strip|body lies in a pale title/body field'):
                    title_body_contract(pdf, 'NATIVETITLE0', 'NATIVEBODY0')

    def test_independent_nonwhite_body_mutation_is_rejected_with_a_correct_title(self):
        for main in ('english', 'hebrew'):
            with self.subTest(main=main), fitz.open(self.results[main+'-nonwhite-body']/'main.pdf') as pdf:
                number, title = occurrence(pdf, 'NATIVETITLE0')
                strips = [rect for rect in gray_rectangles(pdf[number], .95)
                          if rect.contains(center(title))]
                self.assertEqual(len(strips), 1, 'negative control must retain a real pale title')
                with self.assertRaisesRegex(AssertionError, 'body has no painted white field'):
                    title_body_contract(pdf, 'NATIVETITLE0', 'NATIVEBODY0')

    def test_untitled_and_nested_boxes_do_not_inherit_a_title_strip(self):
        for main in ('english', 'hebrew'):
            with self.subTest(main=main), fitz.open(self.results[main]/'main.pdf') as pdf:
                records = [white_body(pdf, token) for token in ('UNTITLEDBODY', 'INNERBODY', 'OUTERAFTER')]
                title_body_contract(pdf, 'OUTERTITLE', 'OUTERBODY')
                for token in ('UNTITLEDBODY', 'INNERBODY'):
                    record = white_body(pdf, token)
                    frame = fitz.Rect(record['field'])
                    pale_inside = [rect for rect in gray_rectangles(pdf[record['page']-1], .95)
                                   if frame.contains(center(rect))]
                    self.assertEqual(pale_inside, [], (main, token, frame, pale_inside))
                self.measurements[main]['untitled_and_nested'] = records

    def test_wrapped_title_keeps_every_line_inside_one_strip(self):
        for main in ('english', 'hebrew'):
            with self.subTest(main=main), fitz.open(self.results[main]/'main.pdf') as pdf:
                first = title_body_contract(pdf, 'WRAPSTART', 'WRAPBODY')
                page_number, last = occurrence(pdf, 'WRAPEND')
                strip = fitz.Rect(first['title_strip'])
                self.assertEqual(page_number+1, first['page'])
                self.assertTrue(strip.contains(center(last)), (main, last, strip))
                self.assertGreater(last.y0, first['title_text'][1]+8, (main, first, last))
                self.measurements[main]['wrapped_title'] = {**first, 'last_line': list(last)}

    def test_explicit_local_palette_override_does_not_leak_to_following_box(self):
        for main in ('english', 'hebrew'):
            with self.subTest(main=main), fitz.open(self.results[main]/'main.pdf') as pdf:
                page_number, title = occurrence(pdf, 'OVERRIDETITLE')
                body_number, body = occurrence(pdf, 'OVERRIDEBODY')
                self.assertEqual(page_number, body_number)
                page = pdf[page_number]
                self.assertEqual(len([rect for rect in gray_rectangles(page, .85)
                                      if rect.contains(center(title))]), 1)
                self.assertEqual(len([rect for rect in gray_rectangles(page, .9)
                                      if rect.contains(center(body))]), 1)
                scoped = title_body_contract(pdf, 'SCOPEDTITLE', 'SCOPEDBODY')
                outside_number, outside = occurrence(pdf, 'OUTSIDEBODY')
                for gray in (.85, .9, .95):
                    self.assertFalse(any(rect.contains(center(outside))
                                         for rect in gray_rectangles(pdf[outside_number], gray)))
                self.measurements[main]['following_default'] = scoped

    def test_split_box_retains_white_segments_and_only_one_optional_title(self):
        for main in ('english', 'hebrew'):
            with self.subTest(main=main), fitz.open(self.results[main]/'main.pdf') as pdf:
                title_number, title = occurrence(pdf, 'SPLITTITLE')
                strips = [rect for rect in gray_rectangles(pdf[title_number], .95)
                          if rect.contains(center(title))]
                self.assertEqual(len(strips), 1)
                rows = [white_body(pdf, f'SPLITROW{index:02d}') for index in range(34)]
                pages = sorted({record['page'] for record in rows})
                self.assertGreaterEqual(len(pages), 2, (main, pages))
                self.assertEqual(pages, list(range(min(pages), max(pages)+1)))
                for number in pages[1:]:
                    self.assertEqual(gray_rectangles(pdf[number-1], .95), [])
                after_number, after = occurrence(pdf, 'SPLITAFTER')
                self.assertEqual(after_number+1, pages[-1])
                self.assertGreater(after.y0, rows[-1]['text'][3])
                self.measurements[main]['split'] = {'pages': pages, 'rows': rows, 'title_page': title_number+1}

    def test_fixed_documents_have_clean_logs_native_metadata_and_a4_geometry(self):
        for main in ('english', 'hebrew'):
            with self.subTest(main=main):
                directory = self.results[main]
                log = (directory/'main.log').read_text(encoding='utf-8', errors='replace')
                for bad in ('Missing character:', r'Overfull \hbox', r'Overfull \vbox', 'undefined references'):
                    self.assertNotIn(bad, log)
                with fitz.open(directory/'main.pdf') as pdf:
                    self.assertEqual(pdf.xref_get_key(pdf.pdf_catalog(), 'Lang'),
                                     ('string', 'en' if main == 'english' else 'he'))
                    for page in pdf:
                        self.assertAlmostEqual(page.rect.width, 595.276, delta=.1)
                        self.assertAlmostEqual(page.rect.height, 841.890, delta=.1)

    @classmethod
    def tearDownClass(cls):
        inputs = {name: {asset: hashlib.sha256((directory/asset).read_bytes()).hexdigest()
                         for asset in ('main.tex', 'preamble.tex', 'reference_theme.tex')}
                  for name, directory in cls.results.items()}
        (cls.root/'measurements.json').write_text(json.dumps({'measurements': cls.measurements,
                                                             'input_sha256': inputs}, ensure_ascii=False,
                                                            indent=2)+'\n', encoding='utf-8')
        if cls.tmp:
            cls.tmp.cleanup()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--with-engine', action='store_true')
    parser.add_argument('--evidence-dir', type=Path)
    args, remaining = parser.parse_known_args()
    EVIDENCE_DIR = args.evidence_dir
    if EVIDENCE_DIR and not args.with_engine:
        parser.error('--evidence-dir requires --with-engine')
    classes = [EditorialBoxContract]
    if args.with_engine:
        classes.append(EditorialBoxes)
    if remaining:
        unittest.main(argv=[sys.argv[0], *remaining], verbosity=2,
                      defaultTest=[test.__name__ for test in classes])
    else:
        suite = unittest.TestSuite(unittest.TestLoader().loadTestsFromTestCase(test)
                                   for test in classes)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        sys.exit(0 if result.wasSuccessful() else 1)
