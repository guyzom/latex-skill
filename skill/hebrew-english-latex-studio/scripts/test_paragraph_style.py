#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Original project code; scope and terms: ../LICENSING.md.
"""Genre-owned paragraph policy and measured native paragraph boundaries.

The default run needs no TeX engine. ``--with-engine`` adds six freshly created
letter profiles, four bounded native-language paper/layout fixtures and two
complete bilingual data reports, one for each main-language order, each with
both current and old-format Hyperref destination naming. It reads
physical first-line and continuation coordinates from the resulting PDFs, not
extraction order or a synthetic claim of visual review. ``--evidence-dir`` must
name a new directory outside the skill; otherwise runtime evidence is temporary.
"""
from __future__ import annotations

import argparse
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
import architecture_contract as architecture
import heading_source
import new_document
from template_registry import CatalogError, resolve_recipe, validate_hook_value

ROOT = Path(__file__).resolve().parent.parent
HOOK = 'lakitparagraphstyle'
PROFILES = (('english', 'english'), ('hebrew', 'hebrew'),
            ('english-with-hebrew', 'english'), ('hebrew-with-english', 'hebrew'),
            ('bilingual', 'english'), ('bilingual', 'hebrew'))
WITH_ENGINE = False
EVIDENCE_DIR: Path | None = None
TEX_TO_PDF = 72 / 72.27
EDGE_TOLERANCE = 1.0


def clean(source: str) -> str:
    return heading_source.clean_source(source)


def source_policy(source: str, expected: str) -> None:
    """The style has one source declaration, before its owning core is loaded."""
    source = clean(source)
    matches = list(re.finditer(r'\\def\\' + HOOK + r'\{([^{}]*)\}', source))
    if len(matches) != 1 or matches[0][1] != expected:
        raise AssertionError((HOOK, expected, [match[1] for match in matches]))
    owner = re.search(r'\\input\{preamble\.tex\}', source)
    if owner is None or matches[0].start() >= owner.start():
        raise AssertionError('paragraph policy must be declared before preamble.tex')


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def retained_evidence_root(path: Path) -> Path:
    root = path.expanduser().resolve()
    if ROOT == root or ROOT in root.parents:
        raise ValueError('paragraph evidence directory must be outside the skill')
    return root


def reference_link(pdf, page, source_bounds, kind: str, number: str,
                   locale: str, target_page: int, target_bounds) -> dict:
    """Bind a visible reference to its actual destination, independent of ID spelling."""
    import fitz
    source = fitz.Rect(source_bounds)
    target = fitz.Rect(target_bounds)
    expected = ({number, '(' + number + ')'} if kind == 'equation' else
                {('Table' if locale == 'english' else 'טבלה') + number})
    matches = []
    for link in page.get_links():
        rectangle = link['from']
        if not rectangle.intersects(source):
            continue
        characters = []
        for block in page.get_text('rawdict')['blocks']:
            for line in block.get('lines', []):
                for span in line['spans']:
                    for character in span['chars']:
                        box = fitz.Rect(character['bbox'])
                        center = fitz.Point((box.x0 + box.x1) / 2,
                                            (box.y0 + box.y1) / 2)
                        if rectangle.contains(center) and source.contains(center):
                            characters.append(character['c'])
        text = re.sub(r'\s+', '', ''.join(characters))
        if text in expected:
            matches.append((link, text))
    if len(matches) != 1:
        raise AssertionError(('visible reference must have exactly one link',
                              kind, number, locale, len(matches)))
    link, text = matches[0]
    name = link.get('nameddest')
    if name:
        # Named get_links().to uses raw PDF coordinates. resolve_link gives
        # physical page coordinates, matching the actual text geometry above.
        destination = pdf.resolve_link('#nameddest=' + name)
    elif link.get('kind') == fitz.LINK_GOTO and 'to' in link:
        destination = (link['page'], link['to'].x, link['to'].y)
    else:
        raise AssertionError(('reference is not a resolved internal link', kind, link))
    if destination[0] + 1 != target_page:
        raise AssertionError(('reference targets the wrong page', kind,
                              target_page, destination))
    point = fitz.Point(destination[1], destination[2])
    if not target.contains(point):
        raise AssertionError(('reference misses its rendered target', kind,
                              list(target), list(point)))
    return {'page': page.number + 1, 'text': text, 'destination': name,
            'bbox': list(link['from']), 'role': 'resolved-prose-link',
            'locale': locale, 'expected_page': target_page,
            'target_page': destination[0] + 1, 'target_point': list(point),
            'target_bounds': list(target)}


def table_opening_bounds(lines: list[dict], caption: dict, locale: str,
                         left: float, right: float) -> tuple:
    """The native table starts after its Data heading and before its caption ends."""
    title = 'Data' if locale == 'english' else 'נתונים'
    headings = [line for line in lines if line['page'] == caption['page']
                and re.fullmatch(r'\d*' + re.escape(title),
                                 re.sub(r'\s+', '', line['text']))]
    if len(headings) != 1:
        raise AssertionError(('table requires exactly one native Data heading', locale, headings))
    heading = headings[0]
    if heading['bbox'][3] >= caption['bbox'][1]:
        raise AssertionError(('table heading must precede its caption', heading, caption))
    # Older longtable creates its anchor before LTpre; newer versions create
    # it after that glue. Both enter this measured opening region. Earlier
    # section/formula anchors and later table content remain outside it.
    return (left, heading['bbox'][3], right, caption['bbox'][3])


class ParagraphPolicy(unittest.TestCase):
    def test_public_hook_is_a_closed_core_owned_enum_with_native_default(self):
        hooks = [hook for hook in architecture.HOOK_SPECS if hook.name == HOOK]
        self.assertEqual(len(hooks), 1)
        hook = hooks[0]
        self.assertEqual(hook.owner, 'assets/preamble.tex')
        self.assertEqual(hook.define_before, hook.owner)
        self.assertEqual(hook.scope, 'document')
        self.assertEqual(hook.value_type, 'enum')
        self.assertEqual(hook.default, 'indented')
        self.assertEqual(set(hook.allowed_values), {'indented', 'block'})
        self.assertTrue(hook.preset_allowed)
        for value in ('indented', 'block'):
            self.assertEqual(validate_hook_value(HOOK, value), value)

    def test_invalid_enum_is_rejected_instead_of_becoming_an_implicit_style(self):
        for value in ('', 'BLOCK', ' block', 'block ', 'none', '0pt', '17pt',
                      r'block\relax', 'indented,block'):
            with self.subTest(value=value), self.assertRaises(CatalogError):
                validate_hook_value(HOOK, value)

    def test_every_owned_starter_declares_its_genre_policy_before_the_core(self):
        catalog = new_document.CATALOG
        seen = set()
        for template in catalog.templates:
            expected = 'indented' if template.id == 'paper' else 'block'
            for starter in template.starters:
                with self.subTest(kind=template.id, starter=starter.asset_path):
                    source_policy((ROOT / starter.asset_path).read_text(), expected)
                    self.assertEqual(dict(starter.declared_hooks)[HOOK], expected)
                    seen.add(starter.asset_path)
        for layout in catalog.layouts:
            for starter in layout.starter_overrides:
                with self.subTest(layout=layout.id, starter=starter.asset_path):
                    source_policy((ROOT / starter.asset_path).read_text(), 'block')
                    self.assertEqual(dict(starter.declared_hooks)[HOOK], 'block')
                    seen.add(starter.asset_path)
        self.assertEqual(len(seen), 20)

    def test_all_recipe_choices_keep_style_owned_by_the_genre_and_core(self):
        count = 0
        for template in new_document.CATALOG.templates:
            for layout in new_document.CATALOG.layouts:
                if template.id not in layout.allowed_kinds:
                    continue
                for theme in (None, *new_document.THEMES):
                    for profile, main in PROFILES:
                        with self.subTest(kind=template.id, layout=layout.id,
                                          theme=theme, profile=profile, main=main):
                            recipe = resolve_recipe(template.id, layout=layout.id,
                                theme=theme, language=profile,
                                main_language=main if profile == 'bilingual' else None,
                                root=ROOT, catalog=new_document.CATALOG)
                            hooks = [hook for hook in recipe.hooks if hook.name == HOOK]
                            self.assertEqual(len(hooks), 1)
                            hook = hooks[0]
                            self.assertEqual(hook.value,
                                             'indented' if template.id == 'paper' else 'block')
                            self.assertEqual(hook.owner, 'assets/preamble.tex')
                            self.assertTrue(hook.provenance.startswith('starter:'), hook)
                            count += 1
        self.assertEqual(count, 396)

    def test_created_letters_bind_block_policy_to_source_and_metadata(self):
        with tempfile.TemporaryDirectory(prefix='studio-paragraph-create-') as tmp:
            for index, (profile, main) in enumerate(PROFILES):
                destination = Path(tmp) / str(index)
                new_document.create('letter', destination, language=profile,
                    main_language=main if profile == 'bilingual' else None)
                source_policy((destination / 'main.tex').read_text(), 'block')
                manifest = json.loads((destination / 'project.json').read_text())
                self.assertEqual(manifest['layout']['declared_hooks'][HOOK], 'block')
                self.assertEqual(manifest['initial_source_sha256']['main.tex'],
                                 digest(destination / 'main.tex'))

    def test_policy_change_does_not_overwrite_an_existing_project(self):
        with tempfile.TemporaryDirectory(prefix='studio-paragraph-existing-') as tmp:
            destination = Path(tmp) / 'letter'
            new_document.create('letter', destination, language='english')
            sentinel = destination / 'main.tex'
            sentinel.write_text('% User-authored project.\n\\def\\lakitparagraphstyle{indented}\n')
            before = {path.name: path.read_bytes() for path in destination.iterdir()}
            with self.assertRaises(ValueError):
                new_document.create('letter', destination, language='english')
            self.assertEqual(before, {path.name: path.read_bytes()
                                     for path in destination.iterdir()})

    def test_omitted_or_late_policy_mutations_are_observed_by_the_source_control(self):
        source = (ROOT / 'assets/starter_letter_english.tex').read_text()
        source_policy(source, 'block')
        declaration = r'\def\lakitparagraphstyle{block}'
        self.assertIn(declaration, source)
        mutations = (source.replace(declaration, ''),
                     source.replace(declaration, r'\def\lakitparagraphstyle{indented}'),
                     source.replace(declaration, '') + '\n' + declaration)
        for mutation in mutations:
            self.assertNotEqual(source, mutation)
            with self.assertRaises(AssertionError):
                source_policy(mutation, 'block')

    def test_retained_evidence_rejects_direct_and_symlinked_skill_descendants(self):
        for path in (ROOT, ROOT/'new-evidence'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                retained_evidence_root(path)
        with tempfile.TemporaryDirectory(prefix='paragraph-evidence-path-') as temporary:
            base = Path(temporary)
            alias = base/'skill-alias'
            alias.symlink_to(ROOT, target_is_directory=True)
            with self.assertRaises(ValueError):
                retained_evidence_root(alias/'new-evidence')
            valid = base/'new-evidence'
            self.assertEqual(retained_evidence_root(valid), valid.resolve())
            self.assertFalse(valid.exists(), 'path validation must not create evidence')

    def test_reference_links_require_the_printed_number_and_exact_target_region(self):
        import fitz
        def fixture(*, destination=(0, 80, 70), printed='1', copies=1):
            pdf = fitz.open()
            for _ in range(2):
                page = pdf.new_page()
                page.insert_text((80, 80), 'x = 1   (1)')
                page.insert_text((80, 180), 'y = 2   (2)')
                page.insert_text((80, 300), 'Equation (' + printed + ') explains the mean.')
            page = pdf[0]
            conclusion = page.search_for('Equation (' + printed + ') explains the mean.')[0]
            annotation = next(rect for rect in page.search_for('(' + printed + ')')
                              if rect.intersects(conclusion))
            for _ in range(copies):
                page.insert_link({'kind': fitz.LINK_GOTO, 'from': annotation,
                                  'page': destination[0],
                                  'to': fitz.Point(destination[1], destination[2])})
            # Reload annotations as a reader sees them in the finished PDF.
            document = fitz.open(stream=pdf.tobytes(), filetype='pdf')
            pdf.close()
            page = document[0]
            target = page.search_for('x = 1   (1)')[0]
            return document, page, conclusion, target
        pdf, page, conclusion, target = fixture()
        with pdf:
            record = reference_link(pdf, page, conclusion, 'equation', '1', 'english', 1, target)
            self.assertEqual(record['target_page'], 1)
        for arguments, error in (({'destination': (0, 80, 170)}, 'misses its rendered target'),
                                 ({'destination': (1, 80, 70)}, 'wrong page'),
                                 ({'printed': '2'}, 'exactly one link'),
                                 ({'copies': 0}, 'exactly one link'),
                                 ({'copies': 2}, 'exactly one link')):
            pdf, page, conclusion, target = fixture(**arguments)
            with self.subTest(arguments=arguments), pdf, self.assertRaisesRegex(AssertionError, error):
                reference_link(pdf, page, conclusion, 'equation', '1', 'english', 1, target)

        def table_fixture(*, destination=(0, 80, 160), printed='1', copies=1):
            pdf = fitz.open()
            for _ in range(2):
                page = pdf.new_page()
                page.insert_text((80, 80), 'x = 1   (1)')
                page.insert_text((80, 140), '2 Data')
                page.insert_text((80, 190), 'Table 1: Six records.')
                page.insert_text((80, 250), 'Table 2: Other records.')
                page.insert_text((80, 350), 'Table ' + printed + ' describes the sample.')
            page = pdf[0]
            source = page.search_for('Table ' + printed + ' describes the sample.')[0]
            annotation = next(rect for rect in page.search_for('Table ' + printed)
                              if rect.intersects(source))
            for _ in range(copies):
                page.insert_link({'kind': fitz.LINK_GOTO, 'from': annotation,
                                  'page': destination[0],
                                  'to': fitz.Point(destination[1], destination[2])})
            document = fitz.open(stream=pdf.tobytes(), filetype='pdf')
            pdf.close()
            page = document[0]
            lines = pdf_lines(document)
            caption = next(line for line in lines if line['page'] == 1
                           and line['text'] == 'Table 1: Six records.')
            target = table_opening_bounds(lines, caption, 'english', 80, page.rect.width - 80)
            return document, page, source, target, lines, caption
        # Both a pre-caption table-start anchor and a caption-local anchor
        # enter the same measured opening region without a padding constant.
        for destination in ((0, 80, 160), (0, 80, 180)):
            pdf, page, source, target, _, _ = table_fixture(destination=destination)
            with self.subTest(table_destination=destination), pdf:
                self.assertEqual(reference_link(pdf, page, source, 'table', '1',
                                                'english', 1, target)['target_page'], 1)
        for arguments, error in (({'destination': (0, 80, 130)}, 'misses its rendered target'),
                                 ({'destination': (0, 80, 70)}, 'misses its rendered target'),
                                 ({'destination': (0, 80, 240)}, 'misses its rendered target'),
                                 ({'destination': (1, 80, 160)}, 'wrong page'),
                                 ({'printed': '2'}, 'exactly one link'),
                                 ({'copies': 0}, 'exactly one link'),
                                 ({'copies': 2}, 'exactly one link')):
            pdf, page, source, target, _, _ = table_fixture(**arguments)
            with self.subTest(table_arguments=arguments), pdf, self.assertRaisesRegex(AssertionError, error):
                reference_link(pdf, page, source, 'table', '1', 'english', 1, target)
        pdf, _, _, _, lines, caption = table_fixture()
        with pdf:
            heading = next(line for line in lines if line['page'] == 1 and line['text'] == '2 Data')
            for mutation in ([line for line in lines if line is not heading], lines + [dict(heading)]):
                with self.assertRaisesRegex(AssertionError, 'exactly one native Data heading'):
                    table_opening_bounds(mutation, caption, 'english', 80, 515)


LETTER_ROLES = {
    'english': {
        'title': 'Subject of the letter', 'recipient': 'Recipient name',
        'recipient-role': 'Recipient role or organization', 'salutation': 'Dear recipient,',
        'opening': 'I would appreciate a short meeting', 'context': 'The aim is to clarify',
        'closing': 'Thank you for your time and consideration.',
        'signoff': 'Sincerely,', 'sender': 'Sender name',
    },
    'hebrew': {
        'title': 'נושא המכתב', 'recipient': 'שם הנמען', 'recipient-role': 'תפקיד או ארגון',
        'salutation': 'שלום רב,', 'opening': 'אבקש לתאם פגישה', 'context': 'מטרת הפגישה',
        'closing': 'תודה על הזמן ועל ההתייחסות.', 'signoff': 'בברכה,', 'sender': 'שם השולח',
    },
}
MINORITY_REQUEST = {
    'english': 'Please confirm receipt of this letter',
    'hebrew': 'אשמח לקבל אישור שהפנייה התקבלה',
}
DATA_ROLES = {
    'english': {'title': 'Data report', 'introduction': 'The table contains six synthetic records',
                'definition': 'Let', 'conclusion': 'contains six records.'},
    'hebrew': {'title': 'דוח נתונים', 'introduction': 'המסמך מציג שש רשומות',
               'definition': 'הוא ערך הרשומה', 'conclusion': 'יש שש רשומות'},
}
DATA_NOTES = {
    'english': ('The negative value is included', 'Zero is an observed value',
                'The record has the same weight', 'The value refers to',
                'The identifier denotes', 'This is the final record'),
    'hebrew': ('הערך השלילי נכלל', 'אפס הוא ערך נתון', 'הרשומה נכללת',
               'הערך מתייחס למשתנה', 'המזהה מציין רשומה', 'זו הרשומה האחרונה'),
}


def pdf_lines(pdf) -> list[dict]:
    result = []
    for page_number, page in enumerate(pdf):
        for block in page.get_text('dict')['blocks']:
            for line in block.get('lines', []):
                result.append({'page': page_number + 1,
                    'text': ''.join(span['text'] for span in line['spans']),
                    'bbox': list(line['bbox'])})
    return result


def unique_line(lines: list[dict], token: str) -> dict:
    hits = [line for line in lines if token in line['text']]
    if len(hits) != 1:
        raise AssertionError((token, len(hits), hits))
    return hits[0]


def reading_edge(line: dict, locale: str) -> float:
    return line['bbox'][0 if locale == 'english' else 2]


def assert_edge(line: dict, locale: str, expected: float) -> None:
    actual = reading_edge(line, locale)
    if abs(actual - expected) > EDGE_TOLERANCE:
        raise AssertionError((locale, line['text'], actual, expected, line['bbox']))


def fixture_prose(main: str, token: str) -> str:
    if main == 'english':
        return token + ' is a bounded paragraph used to measure its reading edge.'
    return r'\en{' + token + '} פסקה קצרה למדידת השוליים בתחילת השורה.'


def geometry_body(main: str, initial_theme: str = 'core') -> str:
    """Keep academic font setup in its supported preamble loading phase."""
    body = [r'\begin{document}',
        r'\typeout{PARTEST-CORE|\the\parindent|\the\parskip}',
        r'\section{' + ('Paragraph boundaries' if main == 'english' else 'גבולות פסקה') + '}',
        fixture_prose(main, 'HeadingFirst'), '\n',
        fixture_prose(main, 'OrdinarySecond'), '\n',
        fixture_prose(main, 'BeforeSameDisplay'), r'\[x=1\]',
        fixture_prose(main, 'SameAfterDisplay'), '\n',
        fixture_prose(main, 'BeforeNewDisplay'), r'\[y=2\]', '\n',
        fixture_prose(main, 'NewAfterDisplay'), '\n']
    themes = ('core', 'reader', 'custom') if initial_theme == 'core' else ('academic',)
    for theme in themes:
        prefix = theme.upper()
        body += [r'\clearpage\begingroup']
        if theme == 'reader':
            body += [r'\input{' + theme + '_theme.tex}']
        elif theme == 'custom':
            body += [r'\input{theme.tex}']
        body += [r'\typeout{PARTEST-' + prefix + r'-BEFORE|\the\parindent|\the\parskip}',
            r'\noindent ' + fixture_prose(main, prefix + 'OuterBase') + r'\par',
            r'\begin{referencecolumns}[2]',
            r'\typeout{PARTEST-' + prefix + r'-COL|\the\parindent|\the\parskip}',
            r'\noindent ' + fixture_prose(main, prefix + 'ColumnBaseA') + r'\par',
            fixture_prose(main, prefix + 'ColumnFirstA') + r'\par',
            r'\par\columnbreak',
            r'\noindent ' + fixture_prose(main, prefix + 'ColumnBaseB') + r'\par',
            fixture_prose(main, prefix + 'ColumnFirstB') + r'\par',
            r'\end{referencecolumns}',
            r'\typeout{PARTEST-' + prefix + r'-COLRETURN|\the\parindent|\the\parskip}',
            '\n',
            fixture_prose(main, prefix + 'AfterColumns') + r'\par',
            r'\begin{referencewide}',
            r'\typeout{PARTEST-' + prefix + r'-WIDE|\the\parindent|\the\parskip}',
            r'\noindent ' + fixture_prose(main, prefix + 'WideBase') + r'\par',
            fixture_prose(main, prefix + 'WideFirst') + r'\par',
            r'\end{referencewide}',
            r'\typeout{PARTEST-' + prefix + r'-WIDERETURN|\the\parindent|\the\parskip}',
            '\n',
            fixture_prose(main, prefix + 'AfterWide') + r'\par',
            r'\endgroup',
            r'\typeout{PARTEST-' + prefix + r'-GROUPRETURN|\the\parindent|\the\parskip}']
    return '\n'.join(body) + '\n' + r'\end{document}' + '\n'


class ParagraphRuntime(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import fitz
        from font_paths import font_dir
        cls.fitz = fitz
        cls.temporary = (None if EVIDENCE_DIR else
                         tempfile.TemporaryDirectory(prefix='studio-paragraph-runtime-'))
        cls.root = (retained_evidence_root(EVIDENCE_DIR) if EVIDENCE_DIR else
                    Path(cls.temporary.name))
        if EVIDENCE_DIR:
            cls.root.mkdir(parents=True, exist_ok=False)
        cache = cls.root / 'tex-cache'
        variable = cls.root / 'tex-var'
        cache.mkdir()
        variable.mkdir()
        fonts = str(font_dir())
        cls.env = dict(os.environ, HEBREW_LATEX_FONT_DIR=fonts, OSFONTDIR=fonts,
                       TTFONTS=fonts + '//:', SOURCE_DATE_EPOCH='1700000000', TZ='UTC',
                       PYTHONDONTWRITEBYTECODE='1', TEXMFCACHE=str(cache),
                       TEXMFVAR=str(variable), TEXMFOUTPUT=str(cls.root))
        cls.env.pop('HEBREW_LATEX_PROJECT_ROOT', None)
        cls.results = {}
        for profile, main in PROFILES:
            key = profile + '-' + main
            directory = cls.root / ('letter-' + key)
            new_document.create('letter', directory, language=profile,
                main_language=main if profile == 'bilingual' else None)
            cls.results[key] = cls.compile(directory)
        for main in ('english', 'hebrew'):
            for initial_theme in ('core', 'academic'):
                key = 'geometry-' + ('' if initial_theme == 'core' else 'academic-') + main
                directory = cls.root / key
                new_document.create('paper', directory, language=main, theme=initial_theme)
                source = (directory / 'main.tex').read_text()
                source_policy(source, 'indented')
                header = source.partition(r'\begin{document}')[0]
                if main == 'hebrew':
                    # Also measure the manual-authoring default; the owned paper
                    # declaration itself remains checked by the no-engine tests.
                    header = header.replace(r'\def\lakitparagraphstyle{indented}', '')
                    # A second class size distinguishes native preservation from
                    # accidentally hard-coding the 11-point article's 17pt indent.
                    header = header.replace(r'\def\lakitclassoptions{11pt,a4paper}',
                                            r'\def\lakitclassoptions{10pt,a4paper}')
                native = (r'\AddToHook{class/article/after}'
                          r'{\typeout{PARTEST-NATIVE|\the\parindent|\the\parskip}}' + '\n')
                header = header.replace(r'\input{preamble.tex}', native + r'\input{preamble.tex}')
                for name in ('reference_columns.tex', 'reader_theme.tex'):
                    shutil.copyfile(ROOT / 'assets' / name, directory / name)
                (directory / 'theme.tex').write_text(new_document.CUSTOM_THEME, encoding='utf-8')
                header += r'\input{reference_columns.tex}' + '\n'
                (directory / 'main.tex').write_text(header + geometry_body(main, initial_theme),
                                                   encoding='utf-8')
                cls.results[key] = cls.compile(directory)
        for main in ('english', 'hebrew'):
            for old_naming in (False, True):
                key = 'data-report-bilingual-' + main + ('-old-destinations' if old_naming else '')
                directory = cls.root / key
                # Academic covers the lower-body display/folio ambiguity that
                # the former continuous bilingual composition exposed in the matrix.
                new_document.create('data-report', directory, language='bilingual',
                                    main_language=main, theme='academic')
                source = (directory / 'main.tex').read_text()
                if old_naming:
                    # Reproduce Hyperref's pre-2024-11-01 LaTeX-format branch.
                    # Visible equation counters and complete document bodies stay
                    # unchanged while actual named destinations include sections.
                    source = source.replace(r'\begin{document}',
                        r'\renewcommand{\theHequation}{\theHsection.\arabic{equation}}'
                        + '\n' + r'\begin{document}', 1)
                    (directory / 'main.tex').write_text(source, encoding='utf-8')
                source_policy(source, 'block')
                cls.results[key] = cls.compile_generated(directory)

    @classmethod
    def tearDownClass(cls):
        if cls.temporary:
            cls.temporary.cleanup()

    @classmethod
    def compile(cls, directory: Path, passes: int = 2):
        result = None
        for number in range(passes):
            result = subprocess.run(['lualatex', '--no-shell-escape', '-halt-on-error',
                '-interaction=nonstopmode', 'main.tex'], cwd=directory, env=cls.env,
                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=180)
            (directory / f'engine-pass-{number + 1}.log').write_text(result.stdout, encoding='utf-8')
            if result.returncode:
                break
        return result, directory

    @classmethod
    def compile_generated(cls, directory: Path):
        # Table/counter state and cross references can need more than two
        # passes. Use the product wrapper's convergence and render checks for
        # these complete reports rather than accepting an intermediate PDF.
        environment = dict(cls.env, HEBREW_LATEX_SKILL_ROOT=str(ROOT))
        environment.pop('TEXMFOUTPUT', None)
        result = subprocess.run(['bash', 'build.sh'], cwd=directory, env=environment,
            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=300)
        (directory / 'generated-build.log').write_text(result.stdout, encoding='utf-8')
        return result, directory

    def checked_pdf(self, key: str):
        result, directory = self.results[key]
        self.assertEqual(result.returncode, 0, result.stdout[-9000:])
        self.assertNotIn('Missing character:', result.stdout)
        self.assertTrue((directory / 'main.pdf').is_file())
        return self.fitz.open(directory / 'main.pdf'), result.stdout, directory

    def write_measurement(self, directory: Path, rows: list[dict]) -> None:
        (directory / 'paragraph-geometry.json').write_text(json.dumps({
            'schema': 1, 'scope': 'measured PDF geometry; not visual review',
            'pdf_sha256': digest(directory / 'main.pdf'),
            'source_sha256': digest(directory / 'main.tex'),
            'edge_tolerance_pdf_points': EDGE_TOLERANCE, 'measurements': rows,
        }, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    def test_generated_native_mixed_and_bilingual_letters_have_flush_reading_edges(self):
        margin = 22 / 25.4 * 72
        for profile, main in PROFILES:
            with self.subTest(profile=profile, main=main):
                pdf, _, directory = self.checked_pdf(profile + '-' + main)
                with pdf:
                    lines = pdf_lines(pdf)
                    rows = []
                    locales = ('english', 'hebrew') if profile == 'bilingual' else (main,)
                    for locale in locales:
                        expected = margin if locale == 'english' else pdf[0].rect.width - margin
                        role_lines = {role: unique_line(lines, token)
                                      for role, token in LETTER_ROLES[locale].items()}
                        for role, line in role_lines.items():
                            assert_edge(line, locale, expected)
                            rows.append(dict(line, role=role, locale=locale,
                                             expected_reading_edge=expected))
                        context, closing = role_lines['context'], role_lines['closing']
                        ending = closing
                        if profile in ('english-with-hebrew', 'hebrew-with-english'):
                            minority = 'hebrew' if main == 'english' else 'english'
                            ending = unique_line(lines, MINORITY_REQUEST[minority])
                            minority_edge = (margin if minority == 'english'
                                             else pdf[0].rect.width - margin)
                            assert_edge(ending, minority, minority_edge)
                            rows.append(dict(ending, role='minority-request', locale=minority,
                                             expected_reading_edge=minority_edge))
                        continuation = [line for line in lines
                            if (context['page'], context['bbox'][1]) <
                               (line['page'], line['bbox'][1]) <
                               (ending['page'], ending['bbox'][1])]
                        self.assertTrue(continuation, 'context paragraph must wrap in the real starter')
                        for line in continuation:
                            assert_edge(line, locale, expected)
                            rows.append(dict(line, role='context-continuation', locale=locale,
                                             expected_reading_edge=expected))
                    self.write_measurement(directory, rows)

    def test_indented_papers_preserve_native_heading_and_display_paragraph_boundaries(self):
        margin = 27 / 25.4 * 72
        for main in ('english', 'hebrew'):
            with self.subTest(main=main):
                pdf, output, directory = self.checked_pdf('geometry-' + main)
                with pdf:
                    values = dict(re.findall(r'PARTEST-(NATIVE|CORE)\|([^\r\n]+)', output))
                    self.assertEqual(set(values), {'NATIVE', 'CORE'})
                    native, core = (value.split('|') for value in (values['NATIVE'], values['CORE']))
                    self.assertEqual(core, native, 'indented mode must preserve the class dimensions')
                    indent = float(re.fullmatch(r'([0-9.]+)pt', core[0])[1]) * TEX_TO_PDF
                    self.assertGreater(indent, 10)
                    lines = pdf_lines(pdf)
                    edge = margin if main == 'english' else pdf[0].rect.width - margin
                    shifted = edge + (indent if main == 'english' else -indent)
                    rows = []
                    for token, expected in (('HeadingFirst', edge), ('OrdinarySecond', shifted),
                                            ('SameAfterDisplay', edge), ('NewAfterDisplay', shifted)):
                        line = unique_line(lines, token)
                        assert_edge(line, main, expected)
                        rows.append(dict(line, role=token, locale=main,
                                         expected_reading_edge=expected))
                    self.write_measurement(directory, rows)

    def test_standalone_reference_layout_is_flush_and_restores_outer_policy_in_all_themes(self):
        margin = 27 / 25.4 * 72
        for main, initial_theme in ((main, theme) for main in ('english', 'hebrew')
                                    for theme in ('core', 'academic')):
            with self.subTest(main=main, initial_theme=initial_theme):
                key = 'geometry-' + ('' if initial_theme == 'core' else 'academic-') + main
                pdf, output, directory = self.checked_pdf(key)
                with pdf:
                    lines = pdf_lines(pdf)
                    states = dict(re.findall(r'PARTEST-([A-Z-]+)\|([^\r\n]+)', output))
                    rows = []
                    themes = ('CORE', 'READER', 'CUSTOM') if initial_theme == 'core' else ('ACADEMIC',)
                    for theme in themes:
                        before = states[theme + '-BEFORE']
                        indent = float(re.fullmatch(r'([0-9.]+)pt', before.split('|')[0])[1]) * TEX_TO_PDF
                        self.assertGreater(indent, 10)
                        for region in ('COL', 'WIDE'):
                            self.assertEqual(states[theme + '-' + region].split('|')[0], '0.0pt')
                            self.assertEqual(states[theme + '-' + region + 'RETURN'], before)
                        self.assertEqual(states[theme + '-GROUPRETURN'], before)
                        for suffix in ('A', 'B'):
                            base = unique_line(lines, theme + 'ColumnBase' + suffix)
                            first = unique_line(lines, theme + 'ColumnFirst' + suffix)
                            self.assertEqual(base['page'], first['page'])
                            expected = reading_edge(base, main)
                            assert_edge(first, main, expected)
                            rows.append(dict(first, role='column-first', theme=theme, locale=main,
                                             expected_reading_edge=expected))
                        base = unique_line(lines, theme + 'WideBase')
                        first = unique_line(lines, theme + 'WideFirst')
                        assert_edge(first, main, reading_edge(base, main))
                        rows.append(dict(first, role='wide-first', theme=theme, locale=main,
                                         expected_reading_edge=reading_edge(base, main)))
                        edge = margin if main == 'english' else pdf[0].rect.width - margin
                        shifted = edge + (indent if main == 'english' else -indent)
                        for token in ('AfterColumns', 'AfterWide'):
                            line = unique_line(lines, theme + token)
                            assert_edge(line, main, shifted)
                            rows.append(dict(line, role=token, theme=theme, locale=main,
                                             expected_reading_edge=shifted))
                    path = directory / 'reference-paragraph-geometry.json'
                    path.write_text(json.dumps({'schema': 1,
                        'scope': 'actual native PDF coordinates; not visual review',
                        'pdf_sha256': digest(directory / 'main.pdf'),
                        'measurements': rows}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    def test_complete_bilingual_data_reports_start_native_counterpart_on_page_two(self):
        margin = 22 / 25.4 * 72
        for main, old_naming in ((main, old) for main in ('english', 'hebrew')
                                for old in (False, True)):
            with self.subTest(main=main, old_destination_naming=old_naming):
                key = 'data-report-bilingual-' + main + ('-old-destinations' if old_naming else '')
                pdf, output, directory = self.checked_pdf(key)
                self.assertNotIn('There were undefined references', output)
                self.assertNotRegex(output, r'Warning: Reference .* undefined')
                source = (directory / 'main.tex').read_text()
                self.assertEqual(source.count(r'\clearpage'), 1)
                self.assertEqual(source.count(r'\bar{x}=\frac{1}{n}\sum_{i=1}^{n}x_i.'), 2)
                secondary = 'hebrew' if main == 'english' else 'english'
                with pdf:
                    self.assertEqual(len(pdf), 2, 'each complete native counterpart needs one page')
                    lines = pdf_lines(pdf)
                    rows = []
                    for locale, expected_page, prefix in ((main, 1, ''),
                                                          (secondary, 2, 'secondary-')):
                        page = pdf[expected_page - 1]
                        expected_edge = margin if locale == 'english' else page.rect.width - margin
                        role_lines = {role: unique_line(lines, token)
                                      for role, token in DATA_ROLES[locale].items()}
                        for role, line in role_lines.items():
                            self.assertEqual(line['page'], expected_page, (locale, role, line))
                            assert_edge(line, locale, expected_edge)
                            rows.append(dict(line, role=role, locale=locale,
                                expected_page=expected_page, expected_reading_edge=expected_edge))
                        self.assertLess(role_lines['title']['bbox'][1], 100,
                                        'counterpart title must begin at the native top reading area')
                        if locale == 'english':
                            # These are real wrapped source paragraphs, not injected
                            # measurement prose. Both continuations must stay flush.
                            for token in ('to the unweighted mean.', 'mean:', 'dataset.'):
                                line = unique_line(lines, token)
                                self.assertEqual(line['page'], expected_page)
                                assert_edge(line, locale, expected_edge)
                                rows.append(dict(line, role='native-prose-continuation', locale=locale,
                                    expected_page=expected_page, expected_reading_edge=expected_edge))
                        # The successful product wrapper deliberately removes
                        # private aux state. Bind named source labels to the
                        # visible PDF tags/references rather than requiring an
                        # unpublished compiler file or an intermediate PDF.
                        labels = {'eq:mean': str(expected_page),
                                  'tab:measurements': str(expected_page)}
                        for label in ('eq:mean', 'tab:measurements'):
                            owned = prefix + label
                            self.assertEqual(source.count(r'\label{' + owned + '}'),
                                             1 if label.startswith('eq:') else 0)
                            if label.startswith('tab:'):
                                self.assertEqual(source.count('{' + owned + '}'), 2)
                                self.assertEqual(source.count(r'\autoref{' + owned + '}'), 1)
                            else:
                                self.assertEqual(source.count(r'\eqref{' + owned + '}'), 1)
                        compact = lambda text: re.sub(r'\s+', '', text)
                        caption_prefix = ('Table' if locale == 'english' else 'טבלה')
                        caption_tag = caption_prefix + labels['tab:measurements'] + ':'
                        captions = [line for line in lines
                                    if compact(line['text']).startswith(caption_tag)]
                        self.assertEqual(len(captions), 1, (caption_tag, captions))
                        caption = captions[0]
                        self.assertEqual(caption['page'], expected_page)
                        conclusion = role_lines['conclusion']
                        prose_row = [line for line in lines if line['page'] == expected_page
                                     and line['bbox'][1] < conclusion['bbox'][3]
                                     and line['bbox'][3] > conclusion['bbox'][1]]
                        conclusion_text = compact(''.join(line['text'] for line in prose_row))
                        # A native RTL row can contain distinct extraction
                        # fragments for its prose and inline numeric reference.
                        # Bind links to the complete measured physical row.
                        prose_bounds = (min(line['bbox'][0] for line in prose_row),
                                        min(line['bbox'][1] for line in prose_row),
                                        max(line['bbox'][2] for line in prose_row),
                                        max(line['bbox'][3] for line in prose_row))
                        self.assertIn(labels['tab:measurements'],
                                      conclusion_text)
                        self.assertIn('(' + labels['eq:mean'] + ')',
                                      conclusion_text)
                        self.assertIn('=5', conclusion_text)
                        rows.append(dict(caption, role='table-caption', locale=locale,
                            expected_page=expected_page, table_number=labels['tab:measurements']))
                        # Require a real summation glyph in the definition display,
                        # with its numbered tag in the same body region. This checks
                        # actual math and not only the source labels or aux state.
                        lower = role_lines['definition']['bbox'][1]
                        upper = caption['bbox'][1]
                        operators = []
                        for block in page.get_text('dict')['blocks']:
                            for line in block.get('lines', []):
                                for span in line['spans']:
                                    if lower < span['bbox'][1] < upper and span['font'].startswith('CMEX'):
                                        operators.append(span)
                        self.assertEqual(len(operators), 1, (locale, operators))
                        tags = [line for line in lines if line['page'] == expected_page
                                and lower < line['bbox'][1] < upper
                                and compact(line['text']) == '(' + labels['eq:mean'] + ')']
                        self.assertEqual(len(tags), 1, (locale, tags))
                        rows.append({'page': expected_page, 'text': operators[0]['text'],
                            'bbox': list(operators[0]['bbox']), 'role': 'rendered-sum-operator',
                            'locale': locale, 'expected_page': expected_page})
                        # Follow the annotation around the visible reference,
                        # then require its physical target at the real formula
                        # or caption. Hyperref's private ID spelling varies by
                        # LaTeX format; page-only or name-only checks are weaker.
                        formula_top = min(operators[0]['bbox'][1], tags[0]['bbox'][1])
                        formula_bottom = max(operators[0]['bbox'][3], tags[0]['bbox'][3])
                        formula_bounds = (margin - 1, formula_top - 6,
                                          page.rect.width - margin + 1, formula_bottom + 2)
                        caption_bounds = table_opening_bounds(lines, caption, locale,
                                                             margin - 1, page.rect.width - margin + 1)
                        for kind, number, target_bounds in (
                                ('table', labels['tab:measurements'], caption_bounds),
                                ('equation', labels['eq:mean'], formula_bounds)):
                            record = reference_link(pdf, page, prose_bounds, kind,
                                                    number, locale, expected_page, target_bounds)
                            if old_naming and kind == 'equation':
                                self.assertTrue(record['destination'])
                                self.assertNotEqual(record['destination'], 'equation.' + number,
                                                    'old-format control must change real anchor names')
                            rows.append(record)
                        for token in DATA_NOTES[locale]:
                            line = unique_line(lines, token)
                            self.assertEqual(line['page'], expected_page, (locale, token, line))
                            self.assertGreaterEqual(line['bbox'][0], margin - EDGE_TOLERANCE)
                            self.assertLessEqual(line['bbox'][2], page.rect.width - margin + EDGE_TOLERANCE)
                            rows.append(dict(line, role='complete-table-record-note', locale=locale,
                                             expected_page=expected_page))
                    for token in ('001', '002', '003', '004', '005', '006',
                                  '-12.50', '0.00', '4.25', '8.00', '13.75', '16.50'):
                        # Native glyph spans identify the numeric cell even when
                        # Babel groups it with the adjacent Hebrew note in one
                        # dictionary line. Keep the exact sign/digits and page.
                        records = []
                        for page_number, page in enumerate(pdf, 1):
                            for block in page.get_text('dict')['blocks']:
                                for line in block.get('lines', []):
                                    for span in line['spans']:
                                        if span['text'].strip() == token:
                                            records.append({'page': page_number, 'text': token,
                                                'bbox': list(span['bbox']),
                                                'role': 'complete-numeric-table-cell',
                                                'locale': main if page_number == 1 else secondary,
                                                'expected_page': page_number})
                        self.assertEqual(sorted(row['page'] for row in records), [1, 2],
                                         (token, records))
                        for record in records:
                            self.assertGreaterEqual(record['bbox'][0], margin - EDGE_TOLERANCE)
                            self.assertLessEqual(record['bbox'][2],
                                pdf[record['page'] - 1].rect.width - margin + EDGE_TOLERANCE)
                        rows.extend(records)
                    self.write_measurement(directory, rows)

    def test_restoring_the_old_indented_letter_is_detected_by_actual_geometry(self):
        directory = self.root / 'negative-old-indented-letter'
        new_document.create('letter', directory, language='english')
        source = (directory / 'main.tex').read_text()
        declaration = r'\def\lakitparagraphstyle{block}'
        self.assertEqual(source.count(declaration), 1)
        (directory / 'main.tex').write_text(source.replace(declaration, ''), encoding='utf-8')
        result, _ = self.compile(directory, passes=1)
        self.assertEqual(result.returncode, 0, result.stdout[-8000:])
        with self.fitz.open(directory / 'main.pdf') as pdf:
            line = unique_line(pdf_lines(pdf), LETTER_ROLES['english']['salutation'])
            margin = 22 / 25.4 * 72
            self.assertGreater(reading_edge(line, 'english') - margin, 10)
            with self.assertRaises(AssertionError):
                assert_edge(line, 'english', margin)

    def test_invalid_runtime_policy_fails_before_emitting_a_pdf(self):
        directory = self.root / 'negative-invalid-policy'
        new_document.create('letter', directory, language='english')
        source = (directory / 'main.tex').read_text()
        declaration = r'\def\lakitparagraphstyle{block}'
        self.assertEqual(source.count(declaration), 1)
        (directory / 'main.tex').write_text(source.replace(declaration,
            r'\def\lakitparagraphstyle{arbitrary}'), encoding='utf-8')
        result, _ = self.compile(directory, passes=1)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('paragraph', result.stdout.lower())
        self.assertIn('paragraph style must be block or indented', result.stdout)
        self.assertFalse((directory / 'main.pdf').exists())


if __name__ == '__main__':
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--with-engine', action='store_true')
    parser.add_argument('--evidence-dir', type=Path)
    args, remaining = parser.parse_known_args()
    WITH_ENGINE = args.with_engine
    EVIDENCE_DIR = args.evidence_dir
    if EVIDENCE_DIR and not WITH_ENGINE:
        parser.error('--evidence-dir requires --with-engine')
    suite = unittest.TestSuite()
    loader = unittest.TestLoader()
    suite.addTests(loader.loadTestsFromTestCase(ParagraphPolicy))
    if WITH_ENGINE:
        suite.addTests(loader.loadTestsFromTestCase(ParagraphRuntime))
    if remaining:
        unittest.main(argv=[sys.argv[0], *remaining], verbosity=2,
                      defaultTest=['ParagraphPolicy', 'ParagraphRuntime'] if WITH_ENGINE
                      else ['ParagraphPolicy'])
    else:
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        sys.exit(0 if result.wasSuccessful() else 1)
