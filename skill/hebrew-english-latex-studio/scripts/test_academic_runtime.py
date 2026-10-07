#!/usr/bin/env python3
"""Real-engine academic conventions in native English and native Hebrew.

Synthetic controls measure selective tags, actual reference destinations,
continuous native captions and serif headings. They do not assert scientific
correctness, visual sign-off or accessibility certification. An optional NEW
HLLPDF_ACADEMIC_EVIDENCE_DIR outside the skill preserves source/log/PDF evidence.
"""
from __future__ import annotations

import contextlib
import hashlib
import io
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
import check_pdf_render as render
from font_paths import font_dir
from heading_source import group, skip_space
from test_references_runtime import reference_string
from test_v4310_runtime import physical_text

ROOT = Path(__file__).resolve().parent.parent


def figure(caption, key):
    return (r'\begin{tikzpic}\begin{tikzpicture}\draw (0,0) rectangle (3,0.5);'
            + r'\node at (1.5,0.25){\en{Model}};\end{tikzpicture}\end{tikzpic}'
            + '\n' + r'\figcap{\label{' + key + '}' + caption + '}\n')


def table(caption, key):
    return (r'\begin{tablebox}\centering\begin{tabular}{ll}\toprule'
            + r'\en{ID}&\en{Value}\\\midrule\en{A}&\en{12}\\\bottomrule\end{tabular}'
            + '\n' + r'\tabcap{\label{' + key + '}' + caption + '}'
            + '\n' + r'\end{tablebox}' + '\n')


def document(main):
    other = 'hebrew' if main == 'english' else 'english'
    heading = 'Central equations' if main == 'english' else 'נוסחאות מרכזיות'
    second = 'Subsequent result' if main == 'english' else 'תוצאה נוספת'
    native = 'Native caption.' if main == 'english' else 'כיתוב מקומי בעברית.'
    minority = 'כיתוב מקומי בעברית.' if main == 'english' else 'Native English caption.'
    explanation = ('The reused equation is ' + r'\eqref{eq:reused}' + '.'
                   if main == 'english' else 'הנוסחה המאוזכרת היא ' + r'\eqref{eq:reused}' + '.')
    minority_heading = 'כותרת משנית בעברית' if main == 'english' else 'Minority English heading'
    # Native Hebrew math text uses its actual local font. In an English
    # prose island select Hebrew explicitly rather than ask Latin Modern
    # math text to supply glyphs it does not contain.
    hebrew_math_text = r'\text{מקדם}' if other == 'hebrew' else r'\text{\h{מקדם}}'
    babel = []
    forms = [r'\foreignlanguage[]{LANG}{BODY}', r'\foreignlanguage[date]{LANG}{BODY}',
             r'\foreignlanguage*{LANG}{BODY}',
             r'\begin{otherlanguage*}[]{LANG}BODY\par\end{otherlanguage*}',
             r'\begin{otherlanguage*}[date]{LANG}BODY\par\end{otherlanguage*}']
    for index, form in enumerate(forms):
        text = ('Minority English (2020–2023).' if other == 'english'
                else 'עברית מקומית עם ' + r'\en{English (2020–2023)}.')
        body = fr'\typeout{{ACADEMIC-INNER-{index}|\languagename}}' + text
        babel.append(form.replace('LANG', other).replace('BODY', body)
                     + fr'\typeout{{ACADEMIC-RETURN-{index}|\languagename}}' + '\n')
    return (fr'\def\lakitlanguageprofile{{{main}}}' + '\n'
        + r'\def\lakitdocumentclass{article}\def\lakitclassoptions{11pt,a4paper}' + '\n'
        + r'\def\lakitgeometryoptions{margin=2.7cm,headheight=14pt}' + '\n'
        + r'\def\lakitlinespread{1.08}\input{preamble.tex}\input{academic_theme.tex}' + '\n'
        + r'\pagestyle{plain}\hypersetup{pdftitle={Academic convention controls},pdfauthor={Synthetic QA}}' + '\n'
        + r'\begin{document}' + '\n'
        + fr'\section{{{heading}}}\label{{sec:central}}' + '\n'
        + r'\begin{equation}\label{eq:unused-before}\mathrm{UNUSEDBEFORE}=0\end{equation}' + '\n'
        + r'\noeqref{eq:central}' + '\n'
        + r'\begin{equation}\label{eq:central}\mathrm{CENTRALEQ}=1\end{equation}' + '\n'
        + r'\begin{equation}\label{eq:reused}\mathrm{REUSEDEQ}=2\end{equation}' + '\n'
        + explanation + '\n'
        + r'\begin{equation}\label{eq:unused-after}\mathrm{UNUSEDAFTER}=0\end{equation}' + '\n'
        + r'\begin{align*}\mathrm{DERIVATIONONE}&=x+x\\\mathrm{DERIVATIONTWO}&=2x\end{align*}' + '\n'
        + figure(native, 'fig:native-one') + table(native, 'tbl:native-one')
        + r'\clearpage' + '\n' + fr'\section{{{second}}}\label{{sec:subsequent}}' + '\n'
        + r'\begin{equation}\label{eq:second}\mathrm{SUBSEQUENTEQ}=3\end{equation}' + '\n'
        + (r'The next result uses \eqref{eq:second}.' if main == 'english'
           else r'התוצאה הנוספת משתמשת ב־\eqref{eq:second}.') + '\n'
        + figure(native, 'fig:native-two') + table(native, 'tbl:native-two')
        + fr'\begin{{{other}prose}}' + '\n' + fr'\subsection{{{minority_heading}}}' + '\n'
        + (r'An English reference \eqref{eq:reused}. \emph{ItalicMarker}.' if other == 'english'
           else r'הפניה בעברית \eqref{eq:reused} עם \en{English (term)}.') + '\n'
        + r'\noeqref{eq:minority-equation}' + '\n'
        + r'\begin{equation}\label{eq:minority-equation}\mathrm{ISLANDEQUATION}=4+'
        + hebrew_math_text + r'+\text{\en{Label (TNR)}}\end{equation}' + '\n'
        + (r'\noindent\en{ISLANDCONTINUATION} פסקה בעברית לאחר הנוסחה.\par'
           if other == 'hebrew' else r'\noindent ISLANDCONTINUATION An English paragraph after the equation.\par') + '\n'
        + r'\noeqref{eq:minority-align-two}' + '\n'
        + r'\begin{align}\mathrm{ISLANDALIGNONE}&=5\label{eq:minority-align-one}\\'
        + r'\mathrm{ISLANDALIGNTWO}&=6\label{eq:minority-align-two}\end{align}' + '\n'
        + figure(minority, 'fig:minority') + table(minority, 'tbl:minority')
        + fr'\end{{{other}prose}}' + '\n'
        + (r'The island result in \eqref{eq:minority-align-one} is referenced from the main prose.'
           if main == 'english' else r'התוצאה בנוסחה \eqref{eq:minority-align-one} מאוזכרת מן הפסקה הראשית.') + '\n'
        + '\n'.join(babel)
        + r'\end{document}' + '\n')


def label_fields(aux, key):
    line = next(line for line in aux.splitlines() if line.startswith(r'\newlabel{' + key + '}'))
    prefix = r'\newlabel{' + key + '}'
    outer = group(line, len(prefix))
    if outer is None:
        raise AssertionError(('malformed label', key, line))
    body = line[outer[0]:outer[1]-1]
    fields, position = [key], 0
    while skip_space(body, position) < len(body):
        field = group(body, position)
        if field is None:
            raise AssertionError(('malformed label field', key, line))
        fields.append(body[field[0]:field[1]-1])
        position = field[1]
    return fields


def equation_row(pdf, marker):
    hits = [(page, box) for page in pdf for box in page.search_for(marker)]
    if len(hits) != 1:
        raise AssertionError((marker, len(hits)))
    page, box = hits[0]
    return physical_text(page, fitz.Rect(0, box.y0, page.rect.width, box.y1))


def equation_geometry(pdf, marker, tag):
    """Ink boxes for one synthetic math row and its physically trailing tag."""
    hits = [(page, box) for page in pdf for box in page.search_for(marker)]
    if len(hits) != 1:
        raise AssertionError((marker, len(hits)))
    page, box = hits[0]
    overrides = render._visible_parenthesis_overrides(page)
    chars = []
    for block in page.get_text('rawdict')['blocks']:
        for line in block.get('lines', []):
            for span in line['spans']:
                for char in span['chars']:
                    x, y = char['origin']
                    if box.y0 <= y <= box.y1 and char['c'].strip():
                        c = char['c']
                        c = overrides.get((ord(c), round(x, 3), round(y, 3)), c)
                        chars.append((x, c, fitz.Rect(char['bbox'])))
    chars.sort(key=lambda char: char[0])
    text = ''.join(c for _, c, _ in chars)
    match = re.search(r'\('+str(tag)+r'\)$', text)
    if match is None:
        raise AssertionError(('missing physical trailing tag', marker, tag, text))
    content = chars[:match.start()]
    number = chars[match.start():]
    if not content or marker not in ''.join(c for _, c, _ in content):
        raise AssertionError(('missing math content', marker, text))
    content_box = fitz.Rect(content[0][2])
    for _, _, rect in content[1:]:
        content_box |= rect
    tag_box = fitz.Rect(number[0][2])
    for _, _, rect in number[1:]:
        tag_box |= rect
    return page, content_box, tag_box


class AcademicRuntime(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        preserve = os.environ.get('HLLPDF_ACADEMIC_EVIDENCE_DIR')
        if preserve:
            cls.root = Path(preserve).resolve()
            if cls.root == ROOT or ROOT in cls.root.parents:
                raise ValueError('academic evidence must be outside the skill')
            cls.root.mkdir(parents=True, exist_ok=False)
        else:
            cls.tmp = tempfile.TemporaryDirectory(prefix='studio-academic-runtime-')
            cls.addClassCleanup(cls.tmp.cleanup)
            cls.root = Path(cls.tmp.name)
        fonts = str(font_dir())
        cls.env = dict(os.environ, HEBREW_LATEX_FONT_DIR=fonts, OSFONTDIR=fonts,
                       TTFONTS=fonts+'//:', SOURCE_DATE_EPOCH='1700000000',
                       TZ='UTC', PYTHONDONTWRITEBYTECODE='1')
        cls.env.pop('HEBREW_LATEX_PROJECT_ROOT', None)
        cls.directories = {}
        for main in ('english', 'hebrew'):
            directory = cls.root/main
            directory.mkdir()
            for asset in ('preamble.tex', 'academic_theme.tex'):
                shutil.copyfile(ROOT/'assets'/asset, directory/asset)
            (directory/'main.tex').write_text(document(main), encoding='utf-8')
            for number in range(4):
                result = subprocess.run(['lualatex', '--no-shell-escape', '-halt-on-error',
                    '-interaction=nonstopmode', 'main.tex'], cwd=directory, env=cls.env,
                    text=True, capture_output=True, timeout=180)
                (directory/f'pass-{number+1}.txt').write_text(result.stdout+result.stderr, encoding='utf-8')
                if result.returncode:
                    raise AssertionError(f'{main}:\n{result.stdout[-10000:]}')
            if 'undefined references' in result.stdout or 'Missing character:' in result.stdout:
                raise AssertionError(f'{main}: unresolved references or missing glyphs')
            cls.directories[main] = directory
        summary = {}
        for main, directory in cls.directories.items():
            with fitz.open(directory/'main.pdf') as pdf:
                summary[main] = {'pdf_sha256': hashlib.sha256((directory/'main.pdf').read_bytes()).hexdigest(),
                                 'pages': len(pdf), 'rendered_equation_rows': {marker: equation_row(pdf, marker)
                                     for marker in ('CENTRALEQ', 'REUSEDEQ', 'SUBSEQUENTEQ', 'UNUSEDBEFORE',
                                                    'UNUSEDAFTER', 'DERIVATIONONE', 'DERIVATIONTWO',
                                                    'ISLANDEQUATION', 'ISLANDALIGNONE', 'ISLANDALIGNTWO')},
                                 'caption_sites': [[kind, number] for page in pdf
                                     for kind, number, _ in render.caption_sites(page, 0, 'normal')]}
                summary[main]['minority_math_geometry'] = {}
                for marker, tag in (('ISLANDEQUATION', 4), ('ISLANDALIGNONE', 5), ('ISLANDALIGNTWO', 6)):
                    page, content_box, tag_box = equation_geometry(pdf, marker, tag)
                    summary[main]['minority_math_geometry'][marker] = {
                        'content_rect': list(content_box), 'tag_rect': list(tag_box),
                        'page_center_x': page.rect.width/2,
                        'expected_tag_right_x': page.rect.width-2.7/2.54*72}
        (cls.root/'measurements.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')

    def test_central_unreferenced_and_reused_equations_have_contiguous_visible_tags(self):
        for main, directory in self.directories.items():
            with self.subTest(main=main), fitz.open(directory/'main.pdf') as pdf:
                for marker, number in (('CENTRALEQ', 1), ('REUSEDEQ', 2), ('SUBSEQUENTEQ', 3)):
                    self.assertIn(f'({number})', equation_row(pdf, marker))
                for marker in ('UNUSEDBEFORE', 'UNUSEDAFTER', 'DERIVATIONONE', 'DERIVATIONTWO'):
                    row = equation_row(pdf, marker)
                    self.assertNotRegex(row, r'\(\d*\)', (main, marker, row))
                text = '\n'.join(page.get_text() for page in pdf)
                self.assertNotIn('??', text)
                self.assertNotIn('()', text)
                aux = (directory/'main.aux').read_text()
                for key, number in (('eq:central', '1'), ('eq:reused', '2'), ('eq:second', '3')):
                    self.assertEqual(label_fields(aux, key)[1], number)

    def test_actual_equation_links_reach_exact_numbered_equation_targets(self):
        for main, directory in self.directories.items():
            with self.subTest(main=main), fitz.open(directory/'main.pdf') as pdf:
                aux = (directory/'main.aux').read_text()
                central = label_fields(aux, 'eq:central')[4]
                reused = label_fields(aux, 'eq:reused')[4]
                second = label_fields(aux, 'eq:second')[4]
                links = [(page, link) for page in pdf for link in page.get_links()]
                self.assertEqual(sum(link.get('nameddest') == central for _, link in links), 0)
                for destination, number, count in ((reused, '2', 2), (second, '3', 1)):
                    relevant = [(page, link) for page, link in links if link.get('nameddest') == destination]
                    self.assertEqual(len(relevant), count)
                    resolved_page, _, resolved_y = pdf.resolve_link('#nameddest='+destination)
                    marker = 'REUSEDEQ' if destination == reused else 'SUBSEQUENTEQ'
                    target = pdf[resolved_page].search_for(marker)[0]
                    self.assertLessEqual(resolved_y, target.y0+3)
                    self.assertLess(target.y0-resolved_y, 40)
                    for page, link in relevant:
                        self.assertEqual(link.get('page'), resolved_page)
                        self.assertIn(f'({number})', reference_string(page, link))

    def test_continuous_figure_table_counters_survive_sections_and_language_islands(self):
        for main, directory in self.directories.items():
            with self.subTest(main=main), fitz.open(directory/'main.pdf') as pdf:
                sites = [site for page in pdf for site in render.caption_sites(page, 0, 'normal')]
                for kind in ('fig', 'tbl'):
                    self.assertEqual([number for k, number, _ in sites if k == kind], ['1', '2', '3'])
                destinations = render.caption_dests(pdf)
                self.assertEqual(set(destinations), {'fig.1', 'fig.2', 'fig.3', 'tbl.1', 'tbl.2', 'tbl.3'})
                hard, soft = [], []
                self.assertEqual(render.dest_landing(pdf, hard, soft, 0, 'normal'), 6)
                self.assertEqual((hard, soft), ([], []))

    def test_heading_numbers_serif_and_native_caption_labels_are_visible(self):
        for main, directory in self.directories.items():
            with self.subTest(main=main), fitz.open(directory/'main.pdf') as pdf:
                heading = 'Central equations' if main == 'english' else 'נוסחאות מרכזיות'
                native_word = 'Figure' if main == 'english' else 'איור'
                other_word = 'איור' if main == 'english' else 'Figure'
                text = '\n'.join(page.get_text() for page in pdf)
                self.assertIn(native_word, text)
                self.assertIn(other_word, text)
                matching = [span for page in pdf for block in page.get_text('dict')['blocks']
                            for line in block.get('lines', []) for span in line['spans']
                            if heading in span['text']]
                self.assertTrue(matching)
                expected_family = 'LMRoman' if main == 'english' else 'FrankRuhlLibre'
                self.assertTrue(all(expected_family in span['font'] and 'Bold' in span['font'] for span in matching), matching)
                hit = pdf[0].search_for(heading)[0]
                heading_row = physical_text(pdf[0], fitz.Rect(0, hit.y0, pdf[0].rect.width, hit.y1))
                self.assertIn('1', heading_row)
                self.assertIn('Central equations' if main == 'english' else heading, text)
                for page in pdf:
                    self.assertEqual(list(render.mirrored_paren_digits(page)), [])

    def test_supported_babel_forms_restore_native_locale_with_academic_theme(self):
        for main, directory in self.directories.items():
            other = 'hebrew' if main == 'english' else 'english'
            log = (directory/'pass-4.txt').read_text()
            for index in range(5):
                with self.subTest(main=main, index=index):
                    self.assertIn(f'ACADEMIC-INNER-{index}|{other}', log)
                    self.assertIn(f'ACADEMIC-RETURN-{index}|{main}', log)

    def test_minority_prose_equation_and_align_stay_centered_with_right_tags(self):
        for main, directory in self.directories.items():
            with self.subTest(main=main), fitz.open(directory/'main.pdf') as pdf:
                _, native_box, _ = equation_geometry(pdf, 'CENTRALEQ', 1)
                page, island_box, island_tag = equation_geometry(pdf, 'ISLANDEQUATION', 4)
                self.assertLess(abs((island_box.x0+island_box.x1)/2-page.rect.width/2), 2.0)
                # Same article text block in both languages: tags sit at its
                # physical right edge, independently of paragraph base.
                expected_right = page.rect.width-2.7/2.54*72
                self.assertLess(abs(island_tag.x1-expected_right), 2.0)
                continuation = [hit for p in pdf for hit in p.search_for('ISLANDCONTINUATION')]
                self.assertEqual(len(continuation), 1)
                if main == 'english':
                    self.assertLess(abs(continuation[0].x1-expected_right), 2.0)
                else:
                    self.assertLess(abs(continuation[0].x0-2.7/2.54*72), 2.0)
                self.assertIn('Label(TNR)', equation_row(pdf, 'ISLANDEQUATION'))
                hebrew_chars = []
                for block in page.get_text('rawdict')['blocks']:
                    for line in block.get('lines', []):
                        for span in line['spans']:
                            for char in span['chars']:
                                rect = fitz.Rect(char['bbox'])
                                if ('\u0590' <= char['c'] <= '\u05ff'
                                        and island_box.intersects(rect)):
                                    hebrew_chars.append((char['origin'][0], char['c']))
                self.assertEqual(''.join(c for _, c in sorted(hebrew_chars, reverse=True)), 'מקדם')
                rows = [equation_geometry(pdf, marker, tag) for marker, tag in
                        (('ISLANDALIGNONE', 5), ('ISLANDALIGNTWO', 6))]
                group_box = fitz.Rect(rows[0][1])
                group_box |= rows[1][1]
                self.assertLess(abs((group_box.x0+group_box.x1)/2-page.rect.width/2), 3.0)
                for row_page, _, tag_box in rows:
                    self.assertLess(abs(tag_box.x1-(row_page.rect.width-2.7/2.54*72)), 2.0)
                self.assertLess(abs((native_box.x0+native_box.x1)/2-page.rect.width/2), 2.0)
                aux = (directory/'main.aux').read_text()
                destination = label_fields(aux, 'eq:minority-align-one')[4]
                links = [(p, link) for p in pdf for link in p.get_links()
                         if link.get('nameddest') == destination]
                self.assertEqual(len(links), 1)
                self.assertIn('(5)', reference_string(*links[0]))

    def test_regular_black_caption_targets_and_wrong_weight_use_actual_render_gate(self):
        for main, directory in self.directories.items():
            with self.subTest(main=main), contextlib.redirect_stdout(io.StringIO()) as capture:
                status = render.check(str(directory/'main.pdf'), [str(directory/'main.tex')],
                                      max_cross_page=0, caption_color=0, caption_label_weight='normal')
            self.assertEqual(status, 0, capture.getvalue())
            self.assertNotIn('DEST-CAPTION-NOT-FOUND', capture.getvalue())
            with fitz.open(directory/'main.pdf') as pdf:
                self.assertTrue(all(not render.caption_sites(page, 0, 'bold') for page in pdf))

    @classmethod
    def compile_extra(cls, name, source, passes=3, academic=False):
        directory = cls.root/name
        directory.mkdir()
        shutil.copyfile(ROOT/'assets/preamble.tex', directory/'preamble.tex')
        if academic:
            shutil.copyfile(ROOT/'assets/academic_theme.tex', directory/'academic_theme.tex')
        (directory/'main.tex').write_text(source, encoding='utf-8')
        for number in range(passes):
            result = subprocess.run(['lualatex', '--no-shell-escape', '-halt-on-error',
                '-interaction=nonstopmode', 'main.tex'], cwd=directory, env=cls.env,
                text=True, capture_output=True, timeout=180)
            (directory/f'pass-{number+1}.txt').write_text(result.stdout+result.stderr, encoding='utf-8')
            if result.returncode:
                break
        return directory, result

    def test_caption_numbering_policy_restores_major_resets_for_article_and_report(self):
        for doc_class, major in (('article', 'section'), ('report', 'chapter')):
            source = (r'\def\lakitlanguageprofile{english}' + '\n'
                + fr'\def\lakitdocumentclass{{{doc_class}}}' + '\n'
                + r'\def\lakitclassoptions{11pt,a4paper}\input{preamble.tex}' + '\n'
                + r'\lakitcaptionnumbering{continuous}\lakitcaptionnumbering{continuous}' + '\n'
                + r'\lakitcaptionnumbering{within-major}\lakitcaptionnumbering{within-major}' + '\n'
                + r'\begin{document}' + '\n'
                + fr'\{major}{{First major unit}}' + '\n'
                + figure('First figure.', 'fig:first') + table('First table.', 'tbl:first')
                + r'\clearpage' + '\n' + fr'\{major}{{Second major unit}}' + '\n'
                + figure('Second figure.', 'fig:second') + table('Second table.', 'tbl:second')
                + r'\autoref{fig:first}; \autoref{fig:second}; \autoref{tbl:first}; \autoref{tbl:second}.' + '\n'
                + r'\end{document}' + '\n')
            directory, result = self.compile_extra('restored-'+doc_class, source)
            with self.subTest(doc_class=doc_class):
                self.assertEqual(result.returncode, 0, result.stdout[-10000:])
                self.assertNotIn('undefined references', result.stdout)
                aux = (directory/'main.aux').read_text()
                with fitz.open(directory/'main.pdf') as pdf:
                    sites = [site for page in pdf for site in render.caption_sites(page)]
                    for kind in ('fig', 'tbl'):
                        self.assertEqual([number for k, number, _ in sites if k == kind], ['1.1', '2.1'])
                        labels = [label_fields(aux, kind+':'+ordinal) for ordinal in ('first', 'second')]
                        self.assertEqual([fields[1] for fields in labels], ['1.1', '2.1'])
                        self.assertEqual(len(set(fields[4] for fields in labels)), 2)
                    hard, soft = [], []
                    self.assertEqual(render.dest_landing(pdf, hard, soft), 4)
                    self.assertEqual((hard, soft), ([], []))

    def test_caption_numbering_policy_rejects_unknown_and_post_document_calls(self):
        header = (r'\def\lakitlanguageprofile{english}\def\lakitdocumentclass{article}' + '\n'
                  + r'\input{preamble.tex}' + '\n')
        controls = [('unknown-policy', r'\lakitcaptionnumbering{per-paper}\begin{document}Control.\end{document}',
                     'Unknown caption-numbering policy'),
                    ('late-policy', r'\begin{document}\lakitcaptionnumbering{continuous}Control.\end{document}',
                     'Can be used only in preamble')]
        for name, body, diagnostic in controls:
            directory, result = self.compile_extra(name, header+body, passes=1)
            with self.subTest(name=name):
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(diagnostic, result.stdout)
                self.assertFalse((directory/'main.pdf').exists())

    def test_title_omits_empty_author_date_rows_and_preserves_supplied_rows_and_thanks(self):
        header = (r'\def\lakitlanguageprofile{english}\def\lakitdocumentclass{article}' + '\n'
                  + r'\def\lakitclassoptions{11pt,a4paper}\input{preamble.tex}\input{academic_theme.tex}' + '\n'
                  + r'\title{\TitleMacro}' + '\n')
        measurements = {}
        for name, metadata in [('title-empty', r'\author{}\date{}\newcommand{\TitleMacro}{TitleMarker}'),
                               ('title-supplied', r'\author{\AuthorMacro\thanks{AffiliationMarker}}\date{\DateMacro}'
                                + r'\newcommand{\TitleMacro}{TitleMarker}\newcommand{\AuthorMacro}{AuthorMarker}'
                                + r'\newcommand{\DateMacro}{DateMarker}')]:
            directory, result = self.compile_extra(name, header+metadata+'\n'
                + r'\begin{document}\maketitle\noindent BodyMarker.\end{document}', passes=2, academic=True)
            with self.subTest(name=name):
                self.assertEqual(result.returncode, 0, result.stdout[-10000:])
                self.assertNotIn('Missing character:', result.stdout)
                with fitz.open(directory/'main.pdf') as pdf:
                    text = '\n'.join(page.get_text() for page in pdf)
                    self.assertEqual(text.count('TitleMarker'), 1)
                    self.assertEqual(text.count('BodyMarker'), 1)
                    title = pdf[0].search_for('TitleMarker')[0]
                    body = pdf[0].search_for('BodyMarker')[0]
                    measurements[name] = body.y0-title.y1
                    for token in ('AuthorMarker', 'DateMarker', 'AffiliationMarker'):
                        self.assertEqual(text.count(token), 1 if name == 'title-supplied' else 0)
        self.assertGreater(measurements['title-supplied']-measurements['title-empty'], 20)

    def test_minority_equation_tag_preserves_fit_logic_for_wide_and_untagged_displays(self):
        header = (r'\def\lakitlanguageprofile{english}\def\lakitdocumentclass{article}' + '\n'
                  + r'\def\lakitclassoptions{11pt,a4paper}\def\lakitgeometryoptions{margin=2.7cm,headheight=14pt}' + '\n'
                  + r'\input{preamble.tex}\input{academic_theme.tex}\pagestyle{plain}' + '\n')
        body = (r'\begin{document}\begin{hebrewprose}' + '\n'
            + r'\noeqref{eq:fit}\begin{equation}\label{eq:fit}'
            + r'\text{\en{\makebox[400pt][s]{FITLEFT\hfill FITRIGHT}}}\end{equation}' + '\n'
            + r'\noeqref{eq:wide}\begin{equation}\label{eq:wide}'
            + r'\text{\en{\makebox[420pt][s]{WIDELEFT\hfill WIDERIGHT}}}\end{equation}' + '\n'
            + r'\begin{equation}\label{eq:hidden}'
            + r'\text{\en{\makebox[420pt][s]{HIDDENLEFT\hfill HIDDENRIGHT}}}\end{equation}' + '\n'
            + r'\begin{equation*}\text{\en{\makebox[420pt][s]{STARLEFT\hfill STARRIGHT}}}\end{equation*}' + '\n'
            + r'\end{hebrewprose}\end{document}')
        directory, result = self.compile_extra('wide-equation-fit', header+body, academic=True)
        self.assertEqual(result.returncode, 0, result.stdout[-10000:])
        self.assertNotIn('Missing character:', result.stdout)
        native_directory, native_result = self.compile_extra('wide-equation-native',
            header+body.replace('hebrewprose', 'englishprose'), academic=True)
        self.assertEqual(native_result.returncode, 0, native_result.stdout[-10000:])
        with fitz.open(directory/'main.pdf') as pdf, fitz.open(native_directory/'main.pdf') as native:
            page = pdf[0]
            def hit(token):
                boxes = page.search_for(token)
                self.assertEqual(len(boxes), 1, token)
                return boxes[0]
            def baseline(rect):
                values = [char['origin'][1] for block in page.get_text('rawdict')['blocks']
                          for line in block.get('lines', []) for span in line['spans']
                          for char in span['chars'] if fitz.Rect(char['bbox']).intersects(rect)
                          and rect.x0-.1 <= char['origin'][0] <= rect.x1+.1]
                self.assertTrue(values)
                return sum(values)/len(values)
            for left, right in (('FITLEFT', 'FITRIGHT'), ('WIDELEFT', 'WIDERIGHT'),
                                ('HIDDENLEFT', 'HIDDENRIGHT'), ('STARLEFT', 'STARRIGHT')):
                content = hit(left) | hit(right)
                if left == 'FITLEFT':
                    # Native TeX deliberately shifts a nearly full-width
                    # tagged formula to reserve real tag space. Protect that
                    # professional fit behavior with an actual LTR control,
                    # rather than force an unsafe absolute center.
                    for marker in (left, right, '(1)'):
                        control = native[0].search_for(marker)
                        self.assertEqual(len(control), 1)
                        actual = hit(marker)
                        self.assertLess(abs(actual.x0-control[0].x0), .1)
                        self.assertLess(abs(actual.x1-control[0].x1), .1)
                else:
                    self.assertLess(abs((content.x0+content.x1)/2-page.rect.width/2), 2.0)
            fit_tag, wide_tag = hit('(1)'), hit('(2)')
            fit_right, wide_right = hit('FITRIGHT'), hit('WIDERIGHT')
            self.assertLess(abs(baseline(fit_tag)-baseline(fit_right)), 1.0)
            self.assertGreater(fit_tag.x0-fit_right.x1, 1.0)
            self.assertFalse(wide_tag.intersects(wide_right))
            self.assertGreater(abs(baseline(wide_right)-baseline(wide_tag)), 10.0)
            for tag in (fit_tag, wide_tag):
                self.assertLess(abs(tag.x1-(page.rect.width-2.7/2.54*72)), 2.0)
            text = '\n'.join(p.get_text() for p in pdf)
            self.assertEqual(len(re.findall(r'\([12]\)', text)), 2)
            self.assertNotRegex(text, r'\((?:3|4)\)')


if __name__ == '__main__':
    unittest.main(verbosity=2)
