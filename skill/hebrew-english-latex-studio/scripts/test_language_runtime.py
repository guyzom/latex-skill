#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Original project code; scope and terms: ../LICENSING.md.
"""Real-engine language profiles: base locale, native fonts, labels and RTL/LTR.

HLLPDF_LANGUAGE_EVIDENCE_DIR preserves the measured sources, logs and PDFs in a
new directory. Otherwise the controls run in a temporary directory. These are
synthetic fixtures; their PDF text checks do not replace visual review.
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
from font_paths import font_dir

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ('preamble.tex', 'reader_theme.tex', 'clean_theme.tex', 'flow_tables.tex',
          'deferred_notes.tex', 'document_components.tex', 'academic_theme.tex',
          'reference_theme.tex')
HEADER = r'''\def\lakitdocumentclass{article}
\def\lakitclassoptions{11pt,a4paper}
\def\lakitgeometryoptions{margin=2.2cm,headheight=14pt}
\def\lakitlinespread{1.12}
\input{preamble.tex}
\input{reader_theme.tex}
\input{flow_tables.tex}
\input{deferred_notes.tex}
\input{document_components.tex}
\lakithead{\en{Language Audit}}
\hypersetup{pdftitle={Language profile controls},pdfauthor={Synthetic QA}}
'''
ENGLISH = r'''\section{Native English heading}\label{sec:english}
\noindent Native English body with \emph{ItalicMarker} and ``quotation''.
\typeout{HLLCHECK-EN|\languagename|\the\exhyphenpenalty}
\begin{proof}An English proof with $1+1=2$.\end{proof}
\begin{enumerate}\item ListAlpha.\item ListBeta.\end{enumerate}
\begin{equation}\label{eq:main}E=mc^2\end{equation}
\noindent REFSTART \eqref{eq:main} REFEND. See \autoref{sec:english}.
\figcap[English figure]{\label{fig:en}English figure caption.}
\tabcap[English table]{\label{tab:en}English table caption.}
\begin{notebox}[frametitle={English callout}]Reader callout in English.\end{notebox}
\DeclareDocNote{en}{English note body.}
A deferred note\DocNoteMark{en}.\PrintDocNotes
\sourcelink{https://example.org}{SourceLabel}{Source context.}
'''
HEBREW = r'''\section{כותרת בעברית}\label{sec:hebrew}
\noindent פסקה בעברית עם \en{English (term)} ועם נוסחה $x=2$.
\typeout{HLLCHECK-HE|\languagename|\the\exhyphenpenalty}
\begin{proof}זוהי הוכחה בעברית.\end{proof}
\begin{enumerate}\item סעיף ראשון.\item סעיף שני.\end{enumerate}
\figcap{כיתוב איור בעברית.}
\tabcap{כיתוב טבלה בעברית.}
\begin{notebox}[frametitle={הערה בעברית}]תוכן קצר בעברית.\end{notebox}
\DeclareDocNote{he}{הערה בעברית עם \en{HEBREWNOTE}.}
הערה\DocNoteMark{he}.\PrintDocNotes
'''


def profile_header(profile, main):
    profile_line = '' if profile == 'default' else fr'\def\lakitlanguageprofile{{{profile}}}'+'\n'
    base_line = fr'\def\lakitmainlanguage{{{main}}}'+'\n' if profile == 'bilingual' else ''
    return profile_line + base_line + HEADER


def body(main):
    native, other = (ENGLISH, HEBREW) if main == 'english' else (HEBREW, ENGLISH)
    env = 'hebrewprose' if main == 'english' else 'englishprose'
    return (r'\begin{document}'+'\n'+
            r'\typeout{HLLCHECK-BASE|\languagename|\the\exhyphenpenalty}'+'\n'+
            r'\tableofcontents'+'\n'+native+r'\clearpage'+'\n'+
            fr'\begin{{{env}}}'+'\n'+other+fr'\end{{{env}}}'+'\n'+
            r'\typeout{HLLCHECK-RETURN|\languagename|\the\exhyphenpenalty}'+'\n'+
            r'\clearpage\noindent\doclang{\en{HeaderCheck}}\end{document}')


def table_alignment_fixture(profile, main, *, defect=None, apis=('open','frame','flow')):
    """Local table semantics and cell alignment are independent of the base locale."""
    source = profile_header(profile,main)+r'\begin{document}'+'\n'
    records = []
    for locale in ('hebrew','english'):
        source += fr'\begin{{{locale}prose}}\section{{\en{{Local table controls}}}}'+'\n'
        labels = []
        for api in apis:
            tag = {'open':'O','frame':'F','flow':'L'}[api]+locale[0].upper()
            label = 'tab:alignment-'+tag
            key,meaning = tag+'KEY',tag+'TEXT'
            caption = 'Caption'+tag
            source += fr'\noindent\en{{BODY{tag}}}\par'+'\n'
            prose = ([r'ראשון קצר.',
                r'שני ארוך: המונח \en{LLVM (CPU)} נשאר בכיוונו; הטווח \en{2020–2023}, '
                r'הערך \en{-12.50} והמודל \en{$x_{12}+5$} נשארים קריאים. '
                r'ההסבר נשבר בכמה שורות בעמודה בטוחה, בלי להקטין גופן ובלי לשנות סדר נתונים.',
                r'\en{control} הוא מונח באנגלית הפותח משפט עברי.'] if locale=='hebrew' else
                [r'First short note.',
                r'Second longer text retains LLVM (CPU), the range 2020–2023, '
                r'the value -12.50 and the model $x_{12}+5$. The Hebrew term \h{בקרה} '
                r'retains its direction. This explanation wraps in several lines without shrinking the font.',
                r'Third note contains the Hebrew term \h{קטן}.'])
            heading_key = r'\en{'+key+'}'
            heading_meaning = r'\en{'+meaning+'}'
            if locale=='hebrew':
                heading_key = r'\h{סמל '+heading_key+'}'
                heading_meaning = r'\h{משמעות '+heading_meaning+'}'
            else:
                heading_key = 'Symbol '+heading_key
                heading_meaning = 'Meaning '+heading_meaning
            wrapped = [r'\h{'+p+'}' if locale=='hebrew' and api!='flow' else p for p in prose]
            right_meaning = locale=='english'
            if defect=='reversed-hebrew-order' and locale=='hebrew' and api=='open':
                right_meaning = True
            if api=='flow':
                # flowtable owns native source-column order and H/E/N behavior.
                # Budget for the full-size key header as well as the digits.
                spec = r'@{}N{1.8cm}'+('H' if locale=='hebrew' else 'E')+r'{8cm}@{}'
                heading = heading_key+'&'+heading_meaning
                rows = '\n'.join(identifier+'&'+p+r'\\' for identifier,p in zip(('001','027','314'),wrapped))
                source += fr'\begin{{flowtable}}{{2}}{{{spec}}}{{{caption}}}{{{label}}}{{{heading}}}'+'\n'+rows+'\n'+r'\end{flowtable}'+'\n'
            else:
                alignment = r'\raggedleft' if locale=='hebrew' else r'\raggedright'
                if defect==('wrong-hebrew-alignment' if locale=='hebrew' else 'wrong-english-alignment'):
                    alignment = r'\raggedright' if locale=='hebrew' else r'\raggedleft'
                paragraph = r'>{'+alignment+r'\arraybackslash}p{8cm}'
                spec = '@{}'+('l'+paragraph if right_meaning else paragraph+'r')+'@{}'
                heading = heading_key+'&'+heading_meaning if right_meaning else heading_meaning+'&'+heading_key
                rows = '\n'.join((r'\en{'+identifier+'}&'+p if right_meaning
                                   else p+r'&\en{'+identifier+'}')+r'\\'
                                  for identifier,p in zip(('001','027','314'),wrapped))
                content = r'\toprule'+'\n'+heading+r'\\\midrule'+'\n'+rows+'\n'+r'\bottomrule'
                if api=='frame':
                    source += fr'\begin{{framedtable}}[{caption}]{{2}}{{{spec}}}{{{caption}}}{{{label}}}'+'\n'+content+'\n'+r'\end{framedtable}'+'\n'
                else:
                    source += r'\begin{center}\begin{otherlanguage}{english}'+'\n'+fr'\begin{{tabular}}{{{spec}}}'+'\n'+content+'\n'+r'\end{tabular}\end{otherlanguage}'+'\n'+fr'\tabcap[{caption}]{{\label{{{label}}}{caption}}}\end{{center}}'+'\n'
            records.append({'locale':locale,'api':api,'tag':tag,'label':label,
                            'key':key,'meaning':meaning,'caption':caption})
            labels.append(label)
        references = ', '.join(r'\ref{'+label+'}' for label in labels)
        source += ('ראו '+r'\en{'+references+'}' if locale=='hebrew' else 'See '+references)+'.\n'
        source += fr'\end{{{locale}prose}}\clearpage'+'\n'
    return source+r'\listoftables\end{document}'+'\n',records


def table_ink_rules(page):
    """Actual booktabs rule rectangles, excluding frame and prose strokes."""
    return sorted([fitz.Rect(d['rect']) for d in page.get_drawings()
                   if (d['color']==(0.,0.,0.) or d['fill']==(0.,0.,0.))
                   and d['rect'].height<1 and d['rect'].width>40],key=lambda r:r.y0)


def paragraph_glyph_lines(page, region, *, min_size=0):
    """Reassemble physical cell baselines, including split language/font spans."""
    lines = {}
    for block in page.get_text('rawdict')['blocks']:
        for line in block.get('lines',[]):
            for span in line['spans']:
                if span['size']<min_size:
                    continue  # actual mathematical scripts have smaller native tiers
                for char in span['chars']:
                    box = fitz.Rect(char['bbox'])
                    if char['c'].strip() and region.contains(fitz.Point(
                            (box.x0+box.x1)/2,char['origin'][1])):
                        lines.setdefault(round(char['origin'][1],1),[]).append(
                            {'char':char['c'],'box':box,'origin':char['origin'],
                             'size':span['size'],'font':span['font']})
    return [row for _,row in sorted(lines.items())]


class LanguageRuntime(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        keep = os.environ.get('HLLPDF_LANGUAGE_EVIDENCE_DIR')
        cls.tmp = None if keep else tempfile.TemporaryDirectory(prefix='hllpdf-language-')
        cls.root = Path(keep) if keep else Path(cls.tmp.name)
        if keep: cls.root.mkdir(parents=True, exist_ok=False)
        fonts = str(font_dir())
        cls.env = os.environ.copy()
        cls.env.pop('HEBREW_LATEX_PROJECT_ROOT', None)
        cls.env.update(OSFONTDIR=fonts, TTFONTS=fonts+'//:', HEBREW_LATEX_FONT_DIR=fonts,
                       SOURCE_DATE_EPOCH='1700000000', TZ='UTC', PYTHONDONTWRITEBYTECODE='1')
        cls.profiles = [('default','hebrew'), ('hebrew','hebrew'), ('english','english'),
                        ('hebrew-with-english','hebrew'), ('english-with-hebrew','english'),
                        ('bilingual','hebrew'), ('bilingual','english')]
        cls.results = {}
        for profile, main in cls.profiles:
            cls.results[profile,main] = cls.compile(profile_header(profile,main)+body(main),
                                                    profile+'-'+main, passes=3)

    @classmethod
    def tearDownClass(cls):
        if cls.tmp: cls.tmp.cleanup()

    @classmethod
    def compile(cls, source, name, passes=1, mutate=None, mutate_flow=None,
                local_sources=None):
        directory = cls.root/name
        directory.mkdir()
        for name in ASSETS: shutil.copyfile(ROOT/'assets'/name, directory/name)
        if mutate:
            p = directory/'preamble.tex'; old=p.read_text(); new=mutate(old)
            if old == new: raise AssertionError('mutation did not alter preamble')
            p.write_text(new)
        if mutate_flow:
            p = directory/'flow_tables.tex'; old=p.read_text(); new=mutate_flow(old)
            if old == new: raise AssertionError('mutation did not alter flow_tables')
            p.write_text(new)
        (directory/'main.tex').write_text(source, encoding='utf-8')
        for local_name, local_source in (local_sources or {}).items():
            path = directory / local_name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(local_source, encoding='utf-8')
        for n in range(passes):
            result = subprocess.run(['lualatex','--no-shell-escape','-halt-on-error',
                                     '-interaction=nonstopmode','main.tex'], cwd=directory,
                                    env=cls.env, text=True, capture_output=True, timeout=180)
            (directory/f'pass-{n+1}.txt').write_text(result.stdout+result.stderr)
            if result.returncode: break
        return result, directory

    def test_every_profile_has_real_base_locale_and_restores_it(self):
        for (profile,main),(result,directory) in self.results.items():
            with self.subTest(profile=profile,main=main):
                self.assertEqual(result.returncode,0,result.stdout[-5000:])
                penalty = 50 if main == 'english' else 10000
                self.assertIn(f'HLLCHECK-BASE|{main}|{penalty}',result.stdout)
                self.assertIn(f'HLLCHECK-RETURN|{main}|{penalty}',result.stdout)
                self.assertIn('HLLCHECK-EN|english|50',result.stdout)
                self.assertIn('HLLCHECK-HE|hebrew|10000',result.stdout)
                self.assertNotIn('Missing character:',result.stdout)
                with fitz.open(directory/'main.pdf') as doc:
                    self.assertEqual(doc.xref_get_key(doc.pdf_catalog(),'Lang'),
                                     ('string','en' if main == 'english' else 'he'))
                    all_text='\n'.join(page.get_text() for page in doc)
                    for token in ('Contents' if main=='english' else 'תוכן',
                                  'Figure','Table','Proof','ListAlpha','ListBeta',
                                  'English note body','HEBREWNOTE','Source:'):
                        self.assertIn(token,all_text)
                    self.assertNotIn('??',all_text)
                    self.assertIn('Native English heading',[x[1] for x in doc.get_toc()])

    def test_english_font_and_real_italic_for_explicit_modern_profiles(self):
        for (profile,main),(result,directory) in self.results.items():
            if profile in {'default','hebrew'}: continue
            with self.subTest(profile=profile,main=main):
                self.assertEqual(result.returncode,0,result.stdout[-4000:])
                with fitz.open(directory/'main.pdf') as doc:
                    spans=[s for p in doc for b in p.get_text('dict')['blocks']
                           for l in b.get('lines',[]) for s in l['spans']]
                    italic=[s for s in spans if 'ItalicMarker' in s['text']]
                    self.assertTrue(italic)
                    self.assertTrue(all('LMRoman' in s['font'] and 'Italic' in s['font']
                                        for s in italic),italic)
                    english=[s for s in spans if 'Native English body' in s['text']]
                    self.assertTrue(english)
                    self.assertTrue(all('LMRoman' in s['font'] for s in english),english)
                    self.assertTrue(any('FrankRuhlLibre' in s['font'] and
                                        re.search('[\u0590-\u05ff]',s['text']) for s in spans))

    def test_default_hebrew_preserves_profile_compatibility(self):
        a=self.results['default','hebrew'][1]/'main.pdf'
        b=self.results['hebrew','hebrew'][1]/'main.pdf'
        self.assertTrue(a.exists() and b.exists())
        self.assertEqual(a.read_bytes(),b.read_bytes())

    def test_supported_babel_forms_have_real_locale_and_restore_caller(self):
        forms = [r'\foreignlanguage[]{LANG}{BODY}',
                 r'\foreignlanguage[date]{LANG}{BODY}',
                 r'\foreignlanguage*{LANG}{BODY}',
                 r'\begin{otherlanguage*}[]{LANG}BODY\par\end{otherlanguage*}',
                 r'\begin{otherlanguage*}[date]{LANG}BODY\par\end{otherlanguage*}']
        for main, secondary in [('english', 'hebrew'), ('hebrew', 'english')]:
            blocks = []
            for number, form in enumerate(forms):
                prose = ('English range 2020–2023.' if secondary == 'english'
                         else 'פסקה בעברית עם טווח ' + r'\en{2020–2023}.')
                inside = fr'\typeout{{HLLBABEL-INNER-{number}|\languagename}}' + prose
                blocks.append(form.replace('LANG', secondary).replace('BODY', inside)
                              + fr'\typeout{{HLLBABEL-RETURN-{number}|\languagename}}\par')
            source = (profile_header(main+'-with-'+secondary, main)
                      + r'\begin{document}' + '\n'.join(blocks) + r'\end{document}')
            result, directory = self.compile(source, 'babel-forms-'+main)
            self.assertEqual(result.returncode, 0, result.stdout[-5000:])
            self.assertNotIn('Missing character:', result.stdout)
            for number in range(len(forms)):
                self.assertIn(f'HLLBABEL-INNER-{number}|{secondary}', result.stdout)
                self.assertIn(f'HLLBABEL-RETURN-{number}|{main}', result.stdout)
            from language_context import LanguageContext
            context = LanguageContext(source)
            for number in range(len(forms)):
                marker = 'HLLBABEL-INNER-'+str(number)
                self.assertEqual(context.is_english(*context.line_column(context.text.index(marker))),
                                 secondary == 'english')

    def test_literal_include_and_child_groups_restore_real_caller_locale(self):
        for main, secondary in [('english', 'hebrew'), ('hebrew', 'english')]:
            environment = secondary+'prose'
            child = (r'\typeout{HLLINCLUDE-ENTRY|\languagename}' + '\n'
                     + fr'\begingroup\selectlanguage{{{main}}}'
                     + r'\typeout{HLLINCLUDE-INNER|\languagename}Grouped text.\endgroup'
                     + '\n' + r'\input{leaf}'
                     + r'\typeout{HLLINCLUDE-CHILD-RETURN|\languagename}')
            source = (profile_header(main+'-with-'+secondary, main)
                      + r'\begin{document}' + fr'\begin{{{environment}}}\input{{child}}'
                      + r'\typeout{HLLINCLUDE-CALLER-RETURN|\languagename}'
                      + fr'\end{{{environment}}}'
                      + r'\typeout{HLLINCLUDE-BASE-RETURN|\languagename}\end{document}')
            result, directory = self.compile(source, 'literal-include-'+main,
                local_sources={'child.tex': child,
                               'leaf.tex': r'\typeout{HLLINCLUDE-LEAF|\languagename}Leaf text.'})
            self.assertEqual(result.returncode, 0, result.stdout[-5000:])
            self.assertNotIn('Missing character:', result.stdout)
            for marker in ('ENTRY', 'LEAF', 'CHILD-RETURN', 'CALLER-RETURN'):
                self.assertIn(f'HLLINCLUDE-{marker}|{secondary}', result.stdout)
            for marker in ('INNER', 'BASE-RETURN'):
                self.assertIn(f'HLLINCLUDE-{marker}|{main}', result.stdout)
            import check_bidi_figures as bidi
            contexts, findings = bidi.document_language_contexts(directory/'main.tex')
            self.assertFalse(findings)
            for filename in ('child.tex', 'leaf.tex'):
                context = contexts[directory/filename][0]
                self.assertEqual(context.entry_language, secondary)
                self.assertEqual(context.exit_language, secondary)
                self.assertEqual(context.config.main, main)

    def test_flowtable_supports_both_reading_orders_and_repeat_labels(self):
        for main,table_language in [('english','english'),('hebrew','hebrew'),
                                    ('english','hebrew'),('hebrew','english')]:
            with self.subTest(main=main, table_language=table_language):
                rows='\n'.join(fr'ROW{i} & \h{{שורה}} & {i}\\' for i in range(1,70))
                switch = table_language+'prose' if main != table_language else None
                before = fr'\begin{{{switch}}}' if switch else ''
                after = fr'\end{{{switch}}}' if switch else ''
                source=(profile_header(main,main)+r'\begin{document}'+before+'\n'+
                        r'\begin{flowtable}{3}{E{.35\flowtablewidth}H{.35\flowtablewidth}N{.3\flowtablewidth}}{\en{Flow caption}}{tab:flow}{FLOWFIRST & \h{תיאור} & FLOWLAST}'+'\n'+rows+'\n'+
                        r'\end{flowtable}'+after+r'\end{document}')
                result,directory=self.compile(source,'flow-'+main+'-'+table_language,passes=3)
                self.assertEqual(result.returncode,0,result.stdout[-5000:])
                self.assertNotIn('Missing character:',result.stdout)
                with fitz.open(directory/'main.pdf') as doc:
                    self.assertGreaterEqual(len(doc),2)
                    for page in doc:
                        first=page.search_for('FLOWFIRST');last=page.search_for('FLOWLAST')
                        self.assertTrue(first and last)
                        if table_language=='english': self.assertLess(first[0].x0,last[0].x0)
                        else: self.assertGreater(first[0].x0,last[0].x0)
                    text='\n'.join(p.get_text() for p in doc)
                    if table_language=='english':
                        self.assertIn('continued',text)
                        self.assertIn('Continued on next page',text)
                    for i in range(1,70): self.assertEqual(len(re.findall(rf'(?<![A-Z0-9])ROW{i}(?![0-9])',text)),1)
                if main != table_language:
                    result,broken=self.compile(source,'flow-mutant-'+main,passes=2,
                        mutate_flow=lambda t:t.replace(
                            r'\pretocmd{\LT@output}{\bodydir\pagedir}',
                            r'\pretocmd{\LT@output}{}'))
                    self.assertEqual(result.returncode,0,result.stdout[-5000:])
                    with fitz.open(broken/'main.pdf') as doc:
                        self.assertFalse(doc[0].search_for('FLOWFIRST') and
                                         doc[0].search_for('FLOWLAST'))


    def test_flowtable_destinations_include_the_reset_parent(self):
        table=r"""\begin{flowtable}{2}{E{.6\flowtablewidth}N{.4\flowtablewidth}}
{\en{Records}}{KEY}{Name & Count}
value & 12\\
\end{flowtable}
"""
        source=(profile_header('bilingual','hebrew')+r'\begin{document}'+'\n'+
                r'\section{נתונים בעברית}'+'\n'+table.replace('KEY','table:first')+
                r'\begin{englishprose}\section{English data}'+'\n'+
                table.replace('KEY','table:second')+
                r'\end{englishprose}\end{document}')
        result,directory=self.compile(source,'flow-destinations',passes=3)
        self.assertEqual(result.returncode,0,result.stdout[-5000:])
        self.assertNotIn('ignoring duplicate destination',result.stdout)
        with fitz.open(directory/'main.pdf') as doc:
            names=doc.resolve_names()
            self.assertIn('table.1.1',names)
            self.assertIn('table.2.1',names)
        result,directory=self.compile(source,'flow-destinations-mutant',passes=2,
            mutate_flow=lambda t:t.replace(r'\let\theHtable\theHtbl',
                r'\def\theHtable{\arabic{tbl}}'))
        self.assertEqual(result.returncode,0,result.stdout[-5000:])
        self.assertIn('ignoring duplicate destination',result.stdout)

    def test_report_has_native_english_chapter_and_appendix_labels(self):
        source=(profile_header('english','english').replace(
                r'\def\lakitdocumentclass{article}',r'\def\lakitdocumentclass{report}')+
                r"""\begin{document}\tableofcontents
\chapter{Chapter heading}\label{ch:en}
English report body. \begin{proof}English proof.\end{proof}
\appendix\chapter{Appendix heading}\label{app:en}
See \autoref{ch:en} and \autoref{app:en}.
\end{document}""")
        result,directory=self.compile(source,'english-report',passes=3)
        self.assertEqual(result.returncode,0,result.stdout[-5000:])
        with fitz.open(directory/'main.pdf') as doc:
            text='\n'.join(p.get_text() for p in doc)
            for value in ['Chapter 1','Appendix A','English report body','Proof.']:
                self.assertIn(value,text)
            self.assertNotIn('??',text)
            self.assertNotRegex(text,'[\u0590-\u05ff]')

    def test_list_geometry_follows_the_paragraph_language(self):
        # Text extraction alone passed the old broken list: its label was in the
        # page margin and the body had no indentation. Measure actual glyphs.
        listing=r"""\noindent\en{BASELINE}\par
\begin{enumerate}
\item \en{FIRST}
\begin{enumerate}\item \en{NESTED}\end{enumerate}
\item \en{SECOND}
\end{enumerate}
\begin{itemize}\item \en{BULLET}\end{itemize}
\begin{description}\item[\en{TERM}] \en{DESCRIPTION}\end{description}
"""
        def metrics(directory,language):
            with fitz.open(directory/'main.pdf') as doc:
                self.assertEqual(len(doc),1)
                page=doc[0]
                hits={key:page.search_for(key)[0] for key in
                      ('BASELINE','FIRST','NESTED','SECOND','BULLET','DESCRIPTION')}
                first=hits['FIRST']
                labels=[w for w in page.get_text('words') if w[4]=='1.' and
                        abs((w[1]+w[3])/2-(first.y0+first.y1)/2)<3]
                self.assertEqual(len(labels),1)
                label=fitz.Rect(labels[0][:4])
                if language=='english':
                    indent=first.x0-hits['BASELINE'].x0
                    nested=hits['NESTED'].x0-first.x0
                    label_inside=label.x0-hits['BASELINE'].x0
                    gap=first.x0-label.x1
                else:
                    indent=hits['BASELINE'].x1-first.x1
                    nested=first.x1-hits['NESTED'].x1
                    label_inside=hits['BASELINE'].x1-label.x1
                    gap=label.x0-first.x1
                glyphs=[(s['text'],tuple(round(v,2) for v in s['bbox']))
                        for b in page.get_text('dict')['blocks']
                        for l in b.get('lines',[]) for s in l['spans']]
                return indent,nested,label_inside,gap,hits,glyphs
        for main in ('english','hebrew'):
            for language in ('english','hebrew'):
                with self.subTest(main=main,language=language):
                    env=language+'prose'
                    source=(profile_header('bilingual',main)+r'\begin{document}'+
                            fr'\begin{{{env}}}'+listing+fr'\end{{{env}}}'+
                            r'\end{document}')
                    result,directory=self.compile(source,f'lists-{main}-{language}')
                    self.assertEqual(result.returncode,0,result.stdout[-5000:])
                    indent,nested,label_inside,gap,hits,glyphs=metrics(directory,language)
                    self.assertGreater(indent,15)
                    self.assertGreater(nested,15)
                    self.assertGreater(label_inside,3)
                    self.assertGreater(gap,2)
                    # Enumerate and itemize share the same logical body inset.
                    coord='x0' if language=='english' else 'x1'
                    self.assertAlmostEqual(getattr(hits['FIRST'],coord),
                                           getattr(hits['SECOND'],coord),delta=.2)
                    self.assertAlmostEqual(getattr(hits['FIRST'],coord),
                                           getattr(hits['BULLET'],coord),delta=.2)
                    result,broken=self.compile(source,f'lists-mutant-{main}-{language}',
                        mutate=lambda t:t.replace(r'\usepackage[bidi=basic,layout=lists]{babel}',
                                                  r'\usepackage[bidi=basic]{babel}'))
                    self.assertEqual(result.returncode,0,result.stdout[-5000:])
                    old=metrics(broken,language)
                    if main==language:
                        # Enabling the upstream option must not move native lists.
                        self.assertEqual(glyphs,old[-1])
                    else:
                        self.assertLess(old[0],2)
                        self.assertLess(old[2],0)


    def test_uniform_captions_natural_tables_and_glossary_all_profiles(self):
        # Real TeX -> PDF controls, including native captionof/subcaption and
        # longtable. Marker text and glyph geometry check the output contract;
        # retained evidence still requires actual page-by-page visual review.
        import check_pdf_render as render
        for profile, main in self.profiles[1:]:
            with self.subTest(profile=profile, main=main):
                longtext = ('CAPTIONBODY ' + r'A deliberately long description with consistent typography, $x^2$ and \h{תוצאה}. '*8
                            if main == 'english' else
                            r'\en{CAPTIONBODY} ' + r'תיאור ארוך שנשבר לשורות ושומר על גופן וצבע אחידים, עם $x^2$ ועם \en{LLVM}. '*10)
                term = 'Compiler' if main == 'english' else r'\en{Compiler}'
                definition = ('Translates source. Sentence punctuation stays intact.' if main == 'english'
                              else r'מתרגם קוד מקור. פיסוק במשפט נשמר, עם $x^2$ ועם \en{LLVM}.')
                longtext += r' \href{https://example.org/caption}{CAPTIONLINK}'
                source = (profile_header(profile, main) + r'\usepackage{subcaption}' + '\n'
                    + r'\newsavebox{\naturaltable}' + '\n'
                    + r'\begin{document}\section{\en{Style controls}}' + '\n'
                    + r'\begin{tikzpic}\begin{tikzpicture}\draw (0,0) rectangle (2,1);\end{tikzpicture}\end{tikzpic}' + '\n'
                    + r'{\bfseries\sffamily\Large\figcap[Short figure]{\label{fig:uniform}' + longtext + r'}}' + '\n'
                    + r'\begin{center}\sbox{\naturaltable}{\begin{tabular}{rr}\en{001}&\en{-12.50}\\\en{002}&\en{0.00}\\\end{tabular}}' + '\n'
                    + r'\typeout{NATURALWIDTH|\the\wd\naturaltable|\the\linewidth}' + '\n'
                    + r'\usebox{\naturaltable}\tabcap[Short table]{\label{tab:natural}\en{Compact records.}}\end{center}' + '\n'
                    + r'\glossaryentry{' + term + '}{' + definition + '}\n'
                    + r'\begin{center}\rule{2cm}{1cm}\captionof{table}{\en{NATIVEBODY Native table caption.}}\label{tab:native}\end{center}' + '\n'
                    + r'\begin{figure}[H]\centering\begin{subfigure}{.45\linewidth}\centering\rule{1cm}{1cm}\caption{\en{SUBBODY Subfigure caption.}}\label{fig:sub}\end{subfigure}' + '\n'
                    + r'\caption{\en{NATIVEFIG Native figure caption.}}\label{fig:native}\end{figure}' + '\n'
                    + r'\begin{flowtable}{2}{ll}{\en{FLOWBODY Continuing table.}}{tab:flowstyle}{\en{State}&\en{Value}}' + '\n'
                    + '\n'.join(r'\en{Valid record '+str(i)+r'}&\en{-12.50}\\' for i in range(1,46)) + '\n'
                    + r'\end{flowtable}\en{See }\ref{fig:uniform}, \autoref{tab:natural}, \nameref{tab:native}, \ref{fig:sub}.' + '\n'
                    + r'\listoffigures\listoftables\end{document}')
                result, directory = self.compile(source, 'styles-'+profile+'-'+main, passes=3)
                self.assertEqual(result.returncode, 0, result.stdout[-6000:])
                log = (directory/'main.log').read_text()
                self.assertNotIn('Overfull', log)
                self.assertNotIn('undefined references', log)
                self.assertNotIn('Missing character:', log)
                width, limit = re.search(r'NATURALWIDTH\|([\d.]+)pt\|([\d.]+)pt', log).groups()
                self.assertLess(float(width), .75*float(limit))
                with fitz.open(directory/'main.pdf') as doc:
                    sites = [row for page in doc for row in render.caption_sites(page)]
                    self.assertIn(('fig', '1.1'), [(r[0],r[1]) for r in sites])
                    self.assertIn(('tbl', '1.1'), [(r[0],r[1]) for r in sites])
                    spans = [span for page in doc for block in page.get_text('dict')['blocks']
                             for line in block.get('lines', []) for span in line['spans']]
                    for marker in ('CAPTIONBODY','CAPTIONLINK','NATIVEBODY','SUBBODY','NATIVEFIG','FLOWBODY'):
                        actual = [span for span in spans if marker in span['text']]
                        self.assertTrue(actual, marker)
                        # The first occurrence is the caption; later ones are
                        # native list entries or nameref prose at body size.
                        for span in actual[:1]:
                            self.assertEqual(span['color'], 0, (marker,span))
                            self.assertFalse(span['flags'] & 16, (marker,span))
                            self.assertAlmostEqual(span['size'], 9.96264, delta=.12)
                    text = ''.join(page.get_text() for page in doc)
                    self.assertIn('Compiler', text)
                    self.assertIn('—', text)
                    self.assertNotIn('Compiler.', text)
                    self.assertEqual(sum(text.count('Valid record '+str(i)+'\n') for i in range(1,46)),45)
                    self.assertTrue(any(link.get('uri')=='https://example.org/caption'
                                        for page in doc for link in page.get_links()))
                if profile in ('english', 'hebrew'):
                    broken, mutant = self.compile(source, 'styles-split-'+main, passes=1,
                        mutate=lambda t:t.replace(r'\newcommand{\lakitcaptionlabelstyle}[1]{#1}',
                            r'\newcommand{\lakitcaptionlabelstyle}[1]{\textcolor{cGray}{\textbf{#1}}}'))
                    self.assertEqual(broken.returncode,0,broken.stdout[-5000:])
                    with fitz.open(mutant/'main.pdf') as doc:
                        detected = [(r[0],r[1]) for page in doc for r in render.caption_sites(page)]
                        self.assertNotIn(('fig','1.1'),detected)
                        self.assertIn('CAPTIONBODY',''.join(page.get_text() for page in doc))
                nav = subprocess.run([sys.executable, str(ROOT/'scripts/check_pdf_navigation.py'),
                                      str(directory/'main.pdf')], capture_output=True, text=True)
                self.assertEqual(nav.returncode,0,nav.stdout+nav.stderr)

    def test_subcaption_rtl_labels_and_explicit_preamble_styles(self):
        import check_pdf_render as render

        def caption_source(main):
            other = 'english' if main == 'hebrew' else 'hebrew'
            source = profile_header(main+'-with-'+other, main)
            source += r'\usepackage{subcaption}\begin{document}'+'\n'
            for locale, marker in ((main, 'SUBBASE'), (other, 'SUBMINORITY')):
                if locale != main:
                    source += fr'\begin{{{locale}prose}}'+'\n'
                description = (r'32 records \en{'+marker+r'} preserve $x^2$ and \h{תוצאה}. '
                               if locale == 'english' else
                               r'32 רשומות \en{'+marker+r'} שומרות $x^2$ ועם \en{LLVM}. ')
                source += (r'\begin{figure}[H]\centering'
                    + r'\begin{subfigure}{.8\linewidth}\centering\rule{2cm}{1cm}'
                    + r'\caption{'+description*6+r'}\label{sub:'+marker+r'}\end{subfigure}'
                    + r'\caption{\en{Parent '+marker+r'}}\label{fig:'+marker+r'}\end{figure}'+'\n')
                if locale != main:
                    source += fr'\end{{{locale}prose}}'+'\n'
                source += r'\clearpage'+'\n'
            return (source+r'\en{References: \subref{sub:SUBBASE}, '
                    + r'\subref{sub:SUBMINORITY}, \ref{fig:SUBBASE}.}\listoffigures\end{document}')

        def assert_sub_label(pdf, marker):
            with fitz.open(pdf) as doc:
                for page in doc:
                    # Older LuaHBTeX can mirror the drawn glyph while keeping
                    # its logical Unicode value. Inspect the embedded font's
                    # glyph IDs, as the render gate does, before testing order.
                    visible = render._visible_parenthesis_overrides(page)
                    raw = [c for b in page.get_text('rawdict')['blocks']
                           for l in b.get('lines', []) for s in l['spans'] for c in s['chars']]
                    spans = [s for b in page.get_text('dict')['blocks']
                             for l in b.get('lines', []) for s in l['spans']]
                    hits = [s for s in spans if marker in s['text']]
                    if not hits:
                        continue
                    # The first marker occurrence is the caption, before lists.
                    baseline = hits[0]['origin'][1]
                    row = [c for c in raw if abs(c['origin'][1]-baseline) < .2]
                    def drawn_char(char):
                        value = char['c']
                        origin = char['origin']
                        return visible.get((ord(value), round(origin[0], 3),
                                            round(origin[1], 3)), value)

                    openings = [c for c in row if drawn_char(c) == '(']
                    closings = [c for c in row if drawn_char(c) == ')']
                    # The historical unisolated label draws two closing
                    # parentheses. Missing/extra glyphs must fail, not skip.
                    self.assertEqual((len(openings), len(closings)), (1, 1),
                                     ('SUBCAPTION-PARENTHESIS-ORDER', marker,
                                      openings, closings))
                    self.assertLess(openings[0]['bbox'][0], closings[0]['bbox'][0],
                                    ('SUBCAPTION-PARENTHESIS-ORDER', marker, openings, closings))
                    letters = [c for c in row if c['c'] == 'a'
                               and openings[0]['bbox'][0] < c['bbox'][0] < closings[0]['bbox'][0]]
                    self.assertEqual(len(letters), 1, ('SUBCAPTION-LABEL-ISOLATION', marker, row))
                    self.assertEqual(hits[0]['color'], 0)
                    self.assertFalse(hits[0]['flags'] & 16)
                    self.assertAlmostEqual(hits[0]['size'], 9.96264, delta=.12)
                    return
            self.fail(('SUBCAPTION-MARKER-NOT-FOUND', marker, str(pdf)))

        for main in ('hebrew', 'english'):
            source = caption_source(main)
            result, directory = self.compile(source, 'subcaption-direction-'+main, passes=3)
            self.assertEqual(result.returncode, 0, result.stdout[-6000:])
            self.assertNotIn('Overfull', (directory/'main.log').read_text())
            for marker in ('SUBBASE', 'SUBMINORITY'):
                assert_sub_label(directory/'main.pdf', marker)
            navigation = subprocess.run([sys.executable, str(ROOT/'scripts/check_pdf_navigation.py'),
                                         str(directory/'main.pdf')], capture_output=True, text=True)
            self.assertEqual(navigation.returncode, 0, navigation.stdout+navigation.stderr)
            broken, mutant = self.compile(source, 'subcaption-unisolated-'+main, passes=3,
                mutate=lambda tex: tex.replace(
                    r'\DeclareCaptionLabelFormat{lakit-sub}{\en{\mbox{\lakitcaptionlabelstyle{(#2)}}}}',
                    r'\DeclareCaptionLabelFormat{lakit-sub}{(#2)}'))
            self.assertEqual(broken.returncode, 0, broken.stdout[-6000:])
            hebrew_marker = 'SUBBASE' if main == 'hebrew' else 'SUBMINORITY'
            with self.assertRaisesRegex(AssertionError, 'SUBCAPTION-PARENTHESIS-ORDER'):
                assert_sub_label(mutant/'main.pdf', hebrew_marker)

        def local_native_source(main, size):
            other = 'english' if main == 'hebrew' else 'hebrew'
            baseline = '8' if size == '6.3' else '12'
            select = fr'\fontsize{{{size}}}{{{baseline}}}\selectfont'
            text = ('Local records preserve mathematics $x^2$ and '+r'\h{תוצאה}. '
                    if main == 'english' else
                    r'רשומות מקומיות שומרות $x^2$ ועם \en{LLVM}. ')
            return (profile_header(main+'-with-'+other, main)
                + r'\usepackage{subcaption}\begin{document}'+select+'\n'
                + r'\noindent\en{BODYLOCAL}\newline\en{BODYSECOND}\par'+'\n'
                + r'\makeatletter\typeout{LOCALBASE|\f@size|\the\baselineskip|\f@baselineskip}'
                + r'{\lakitcaptionstyle\typeout{LOCALSTYLE|\f@size|\the\baselineskip|\f@baselineskip}'
                + r'\en{DIRECTLOCAL}\newline\en{DIRECTSECOND}\par}\makeatother'+'\n'
                + r'\begin{center}\rule{2cm}{1cm}\captionof{figure}{\en{NATSHORT} '+text+r'}\label{native:short}\end{center}'+'\n'
                + r'\begin{minipage}{.55\linewidth}\centering'+select+r'\rule{2cm}{1cm}'
                + r'\captionof{table}{\en{NATLONG} '+text*7+r'}\label{native:long}\end{minipage}'+'\n'
                + r'\begin{figure}[H]\centering'+select
                + r'\begin{subfigure}{.65\linewidth}\centering'+select+r'\rule{2cm}{1cm}'
                + r'\caption{\en{SUBLOCAL} '+text*5+r'}\label{native:sub}\end{subfigure}'
                + r'\caption{\en{PARENTLOCAL} '+text*3+r'}\label{native:parent}\end{figure}'+'\n'
                + r'\en{AFTERLOCAL}\par\makeatletter'
                + r'\ifdefined\hllpdf@nativecaptionfontsize\typeout{NATIVECAPTURE-LEAK}\fi'
                + r'\makeatother\en{References: \ref{native:short}, \ref{native:long}, '
                + r'\subref{native:sub}, \ref{native:parent}.}\end{document}')

        def assert_local_native(directory, size, check_baseline=True):
            log = (directory/'main.log').read_text()
            self.assertNotIn('NATIVECAPTURE-LEAK', log)
            self.assertNotIn('Overfull', log)
            with fitz.open(directory/'main.pdf') as doc:
                spans = [s for page in doc for b in page.get_text('dict')['blocks']
                         for l in b.get('lines', []) for s in l['spans']]
                if check_baseline:
                    def baseline(marker):
                        hits = [s for s in spans if marker in s['text']]
                        self.assertEqual(len(hits), 1, marker)
                        return hits[0]['origin'][1]
                    body_step = baseline('BODYSECOND')-baseline('BODYLOCAL')
                    caption_step = baseline('DIRECTSECOND')-baseline('DIRECTLOCAL')
                    self.assertAlmostEqual(body_step, caption_step, delta=.02,
                                           msg='CAPTION-BASELINE-STRETCH-APPLIED-TWICE')
                for marker in ('BODYLOCAL', 'BODYSECOND', 'DIRECTLOCAL', 'DIRECTSECOND',
                               'NATSHORT', 'NATLONG', 'SUBLOCAL', 'PARENTLOCAL', 'AFTERLOCAL'):
                    hits = [s for s in spans if marker in s['text']]
                    self.assertTrue(hits, marker)
                    for span in hits:
                        self.assertAlmostEqual(span['size'], float(size)*72/72.27, delta=.12,
                                               msg='NATIVE-CAPTION-LOCAL-SIZE: '+marker)
                        self.assertEqual(span['color'], 0)
                        self.assertFalse(span['flags'] & 16)
            nav = subprocess.run([sys.executable, str(ROOT/'scripts/check_pdf_navigation.py'),
                                  str(directory/'main.pdf')], capture_output=True, text=True)
            self.assertEqual(nav.returncode, 0, nav.stdout+nav.stderr)

        for main in ('hebrew', 'english'):
            for size in ('6.3', '9'):
                source = local_native_source(main, size)
                result, directory = self.compile(source, 'native-local-'+main+'-'+size, passes=3)
                self.assertEqual(result.returncode, 0, result.stdout[-6000:])
                assert_local_native(directory, size)
        source = local_native_source('english', '6.3')
        capture = (r'\AddToHook{cmd/caption@begin/after}{%'+'\n'
                   + r'  \edef\hllpdf@nativecaptionfontsize{\f@size}%'+'\n'
                   + r'  \edef\hllpdf@nativecaptionbaseline{\f@baselineskip}}')
        result, mutant = self.compile(source, 'native-local-reset-mutant', passes=3,
            mutate=lambda tex: tex.replace(capture, r'\AddToHook{cmd/caption@begin/after}{}'))
        self.assertEqual(result.returncode, 0, result.stdout[-6000:])
        with self.assertRaisesRegex(AssertionError, 'NATIVE-CAPTION-LOCAL-SIZE'):
            assert_local_native(mutant, '6.3')
        result, mutant = self.compile(source, 'caption-baseline-stretch-mutant', passes=3,
            mutate=lambda tex: tex.replace(r'\edef\hllpdf@captionbaseline{\f@baselineskip}%',
                                          r'\edef\hllpdf@captionbaseline{\the\baselineskip}%'))
        self.assertEqual(result.returncode, 0, result.stdout[-6000:])
        with self.assertRaisesRegex(AssertionError, 'CAPTION-BASELINE-STRETCH-APPLIED-TWICE'):
            assert_local_native(mutant, '6.3')

        # An explicit template may choose a different size, separator or label
        # format. Both pre-core options and normal later setup must remain final.
        options = 'font=Large,labelsep=period,labelformat=simple'
        for mode in ('early-options', 'package-options', 'preamble-setup'):
            prefix = (fr'\PassOptionsToPackage{{{options}}}{{subcaption}}'+'\n'
                      if mode == 'early-options' else '')
            package = (fr'\usepackage[{options}]{{subcaption}}'
                       if mode == 'package-options' else r'\usepackage{subcaption}')
            setup = fr'\captionsetup[sub]{{{options}}}' if mode == 'preamble-setup' else ''
            source = (prefix+profile_header('english', 'english')+package+setup+'\n'
                + r'\begin{document}\fontsize{6.3}{8}\selectfont\begin{figure}[H]\centering\fontsize{6.3}{8}\selectfont'
                + r'\begin{subfigure}{.85\linewidth}\centering\fontsize{6.3}{8}\selectfont\rule{2cm}{1cm}'
                + r'\caption{REQUESTEDSTYLE Explicit template.}\end{subfigure}'
                + r'\caption{Parent caption.}\end{figure}\end{document}')
            result, directory = self.compile(source, 'subcaption-explicit-'+mode, passes=1)
            self.assertEqual(result.returncode, 0, result.stdout[-6000:])
            with fitz.open(directory/'main.pdf') as doc:
                spans = [s for p in doc for b in p.get_text('dict')['blocks']
                         for l in b.get('lines', []) for s in l['spans']]
                requested = [s for s in spans if 'REQUESTEDSTYLE' in s['text']]
                self.assertEqual(len(requested), 1)
                self.assertAlmostEqual(requested[0]['size'], 14.3462, delta=.12)
                self.assertIn('a. REQUESTEDSTYLE', requested[0]['text'])
                self.assertNotIn('(a)', requested[0]['text'])

    def test_hebrew_data_starter_aligns_prose_and_numeric_columns(self):
        source = (ROOT/'assets/starter_data_report.tex').read_text()
        result, directory = self.compile(source, 'data-starter-alignment', passes=3)
        self.assertEqual(result.returncode, 0, result.stdout[-6000:])
        self.assertNotIn('Overfull', (directory/'main.log').read_text())

        def column_edges(pdf):
            with fitz.open(pdf) as doc:
                self.assertEqual(len(doc), 1)
                page = doc[0]
                ids = [box for text in ('001','002','003','004','005','006')
                       for box in page.search_for(text)]
                self.assertEqual(len(ids), 6)
                # A PDF extractor may join adjacent Hebrew and Latin spans
                # into one word; locate the actual numeric glyph rectangles.
                values = [box for text in ('-12.50','0.00','4.25','8.00','13.75','16.50')
                          for box in page.search_for(text)]
                self.assertEqual(len(values), 6)
                top = min(w[1] for w in ids) - .5
                bottom = max(w[3] for w in ids) + .5
                prose_edges = []
                for block in page.get_text('rawdict')['blocks']:
                    for line in block.get('lines', []):
                        chars = [c for span in line['spans'] for c in span['chars']
                                 if '\u0590' <= c['c'] <= '\u05ff']
                        if chars and top <= line['bbox'][1] and line['bbox'][3] <= bottom:
                            prose_edges.append(max(c['bbox'][2] for c in chars))
                self.assertEqual(len(prose_edges), 7)  # six records, one wrapped note
                return prose_edges, [w[2] for w in values], [w[2] for w in ids]

        prose, values, ids = column_edges(directory/'main.pdf')
        for edges in (prose, values, ids):
            self.assertLess(max(edges)-min(edges), .3)
        wrong = source.replace(r'\raggedleft', r'\raggedright')
        self.assertNotEqual(source, wrong)
        result, mutant = self.compile(wrong, 'data-starter-left-mutant')
        self.assertEqual(result.returncode, 0, result.stdout[-5000:])
        bad_prose, _, _ = column_edges(mutant/'main.pdf')
        self.assertGreater(max(bad_prose)-min(bad_prose), 20)

    def test_gallery_keeps_unframed_examples_prominent_and_content_sized(self):
        import check_pdf_render as render
        result, directory = self.compile((ROOT/'assets/example_tables.tex').read_text(),
                                         'unframed-gallery', passes=3)
        self.assertEqual(result.returncode, 0, result.stdout[-6000:])
        log = (directory/'main.log').read_text()
        for bad in ('Overfull', 'Missing character:', 'undefined references', 'multiply defined'):
            self.assertNotIn(bad, log)
        with fitz.open(directory/'main.pdf') as doc:
            sites = [(i, site) for i, page in enumerate(doc) for site in render.caption_sites(page)]
            self.assertEqual(len(sites), 20)
            self.assertEqual([site[1] for _, site in sites], list(map(str, range(1, 21))))
            # Actual filled containers: six optional frames, all after the
            # fourteen unframed captions. Grid exceptions stay unframed too.
            frames = [(i, d['rect']) for i, page in enumerate(doc) for d in page.get_drawings()
                      if d['fill'] == (1., 1., 1.) and d['rect'].width > 40
                      and d['rect'].height > 25]
            self.assertEqual(len(frames), 6)
            self.assertTrue(all(i > sites[13][0] for i, _ in frames))
            for i, frame in frames: self.assert_neutral_table_frame(doc[i], frame)
            compact_page = next(p for p in doc if p.search_for('Configuration'))
            compact = [compact_page.search_for(t)[0] for t in ('Configuration', 'Hit rate', 'Access time')]
            self.assertTrue(compact[0].x0 < compact[1].x0 < compact[2].x0)
            self.assertLess(compact[-1].x1-compact[0].x0, compact_page.rect.width/2)
            page = next(p for p in doc if p.search_for('Standard'))
            standard = page.search_for('Standard')[0]
            # Select the five-field table's physical header baseline, rather
            # than other occurrences of ID/Value in captions or examples.
            wide = [next(r for r in page.search_for(t) if abs(r.y0-standard.y0)<1)
                    for t in ('ID', 'Standard', 'Value', 'Model', 'Explanation')]
            self.assertTrue(all(a.x0 < b.x0 for a,b in zip(wide, wide[1:])))
            words = [w for w in page.get_text('words') if w[0] >= wide[-1].x0
                     and standard.y1 < w[1] < standard.y1+65]
            self.assertGreater(len({round(w[1], 1) for w in words}), 2)
            self.assertTrue(page.search_for('USB 3.0'))
            self.assertTrue(page.search_for('IEEE 802.11'))
            # Check the real row rules, not just word extents: a compact
            # table must not acquire fill glue or a full-width rule/frame.
            rules = [d['rect'] for d in compact_page.get_drawings() if d['color']==(0.,0.,0.)
                     and d['rect'].height < 1 and d['rect'].width > 40
                     and compact[0].y0-12 < d['rect'].y0 < compact[0].y1+65]
            self.assertTrue(rules)
            self.assertLess(max(r.width for r in rules), compact_page.rect.width*.6)
            dests = doc.resolve_names()
            for i, site in sites:
                self.assertEqual(dests['tbl.0.'+site[1]]['page'], i)
            self.assert_gallery_prose_alignment(doc,sites)
        nav = subprocess.run([sys.executable, str(ROOT/'scripts/check_pdf_navigation.py'),
                              str(directory/'main.pdf')], capture_output=True, text=True)
        self.assertEqual(nav.returncode, 0, nav.stdout+nav.stderr)
        self.assert_local_table_alignment_profiles()

    def assert_cell_paragraph_edge(self,page,region,locale,expected_edge,*,min_size=0):
        rows = paragraph_glyph_lines(page,region,min_size=min_size)
        self.assertTrue(rows,('missing actual paragraph glyphs',region))
        edges = [max(c['box'].x1 for c in row) if locale=='hebrew'
                 else min(c['box'].x0 for c in row) for row in rows]
        code = ('HEBREW' if locale=='hebrew' else 'ENGLISH')+'-CELL-ALIGNMENT'
        self.assertTrue(all(abs(edge-expected_edge)<.5 for edge in edges),
                        (code,expected_edge,edges,region))
        return rows

    def assert_gallery_prose_alignment(self,pdf,sites):
        """Check actual authored headers and all prose lines, including last lines."""
        def band(number):
            page_index,(_,_,caption) = next((i,site) for i,site in sites if site[1]==str(number))
            page = pdf[page_index]
            rules = [rule for rule in table_ink_rules(page) if rule.y1<caption.y0]
            self.assertGreaterEqual(len(rules),3)
            return page,*rules[-3:]
        def phrase(page,text,top,mid):
            hits = [fitz.Rect(word[:4]) for word in page.get_text('words')
                    if word[4].strip('.:') in text.split() and top.y1<word[1]<mid.y0]
            self.assertEqual(len(hits),len(text.split()),(text,hits))
            box = hits[0]
            for other in hits[1:]: box |= other
            return box
        def column(page,top,mid,bottom,left,right,locale,edge):
            for y0,y1 in ((top.y1+.2,mid.y0-.2),(mid.y1+.2,bottom.y0-.2)):
                self.assert_cell_paragraph_edge(page,fitz.Rect(left,y0,right,y1),locale,edge)
        # Natural Hebrew note/key columns: right alignment does not change the
        # centered mathematical column or Hebrew semantic source-column order.
        page,top,mid,bottom = band(1)
        note = phrase(page,'הערה',top,mid)
        model = phrase(page,'סיבוכיות זמן',top,mid)
        key = phrase(page,'שיטה',top,mid)
        self.assertLess(note.x1,model.x0)
        self.assertLess(model.x1,key.x0)
        column(page,top,mid,bottom,top.x0-1,model.x0-.2,'hebrew',note.x1)
        column(page,top,mid,bottom,model.x1+.2,top.x1+1,'hebrew',key.x1)
        # The same notation task has opposite semantic orders in local Hebrew
        # and English. The fixed prose budget is authored here, not a default.
        width = 8/2.54*72
        for number,locale in ((2,'hebrew'),(3,'english')):
            page,top,mid,bottom = band(number)
            meaning = phrase(page,'משמעות' if locale=='hebrew' else 'Meaning',top,mid)
            key = phrase(page,'סימון' if locale=='hebrew' else 'Symbol',top,mid)
            if locale=='hebrew':
                self.assertLess(meaning.x1,key.x0)
                left,right,edge = top.x0,top.x0+width,top.x0+width
            else:
                self.assertLess(key.x1,meaning.x0)
                left,right,edge = top.x1-width,top.x1,top.x1-width
                self.assertAlmostEqual(key.x0,top.x0,delta=.5)
            column(page,top,mid,bottom,left-1,right+1,locale,edge)
            self.assertGreater(len(paragraph_glyph_lines(page,
                fitz.Rect(left-1,mid.y1+.2,right+1,bottom.y0-.2))),5)
        # Both wrapped Hebrew prose columns, including the short term column.
        page,top,mid,bottom = band(5)
        explanation = phrase(page,'הסבר',top,mid)
        term = phrase(page,'מונח',top,mid)
        self.assertLess(explanation.x1,term.x0)
        boundary = top.x0+9/2.54*72
        column(page,top,mid,bottom,top.x0-1,boundary+1,'hebrew',boundary)
        column(page,top,mid,bottom,boundary+6,top.x1+1,'hebrew',top.x1)

    def alignment_table_geometry(self,pdf,record):
        found = [(page,box) for page in pdf for box in page.search_for(record['meaning'])]
        self.assertEqual(len(found),1,(record,found))
        page,meaning_header = found[0]
        keys = page.search_for(record['key'])
        self.assertEqual(len(keys),1)
        key_header = keys[0]
        rules = table_ink_rules(page)
        top = max((r for r in rules if r.y1<min(meaning_header.y0,key_header.y0)),key=lambda r:r.y0)
        mid = min((r for r in rules if r.y0>max(meaning_header.y1,key_header.y1)),key=lambda r:r.y0)
        bottom = min((r for r in rules if r.y0>mid.y1+.2),key=lambda r:r.y0)
        meaning_left = meaning_header.x0<key_header.x0
        width = 8/2.54*72
        left,right = (top.x0,top.x0+width) if meaning_left else (top.x1-width,top.x1)
        body = fitz.Rect(left-1,mid.y1+.2,right+1,bottom.y0-.2)
        heading = fitz.Rect(left-1,top.y1+.2,right+1,mid.y0-.2)
        key_body = (fitz.Rect(right+1,mid.y1+.2,top.x1+1,bottom.y0-.2) if meaning_left
                    else fitz.Rect(top.x0-1,mid.y1+.2,left-1,bottom.y0-.2))
        return page,{'meaning_left':meaning_left,'body':body,'heading':heading,
                     'key_body':key_body,'edge':right if record['locale']=='hebrew' else left,
                     'rules':(top,mid,bottom)}

    def assert_table_semantic_order(self,pdf,record):
        _,geometry = self.alignment_table_geometry(pdf,record)
        self.assertEqual(geometry['meaning_left'],record['locale']=='hebrew',
                         ('TABLE-SEMANTIC-COLUMN-ORDER',record,geometry))

    def assert_table_paragraph_alignment(self,pdf,record):
        page,geometry = self.alignment_table_geometry(pdf,record)
        marker = page.search_for('BODY'+record['tag'])
        self.assertEqual(len(marker),1)
        sizes = [span['size'] for block in page.get_text('dict')['blocks']
                 for line in block.get('lines',[]) for span in line['spans']
                 if fitz.Rect(span['bbox']).intersects(marker[0])]
        self.assertEqual(len(sizes),1)
        size = sizes[0]
        rows = self.assert_cell_paragraph_edge(page,geometry['body'],record['locale'],
                                              geometry['edge'],min_size=.95*size)
        self.assert_cell_paragraph_edge(page,geometry['heading'],record['locale'],geometry['edge'])
        self.assertGreater(len(rows),3,'the actual long cell must wrap')
        self.assertTrue(all(abs(c['size']-size)<.12 for row in rows for c in row),
                        'normal table glyphs must retain the local body size')
        # Read words/glyphs in their physical direction; extraction order is
        # not evidence of either Hebrew order or an LTR numeric island.
        hebrew = ''.join(c['char'] for c in sorted(rows[0],key=lambda c:-c['origin'][0])
                         if '\u0590'<=c['char']<='\u05ff')
        if record['locale']=='hebrew':
            self.assertEqual(hebrew,'ראשוןקצר')
            term = page.search_for('control',clip=geometry['body'])
            following = [fitz.Rect(word[:4]) for word in page.get_text('words')
                         if word[4]=='הוא' and geometry['body'].contains(fitz.Rect(word[:4]))]
            self.assertEqual((len(term),len(following)),(1,1))
            self.assertLess(following[0].x1,term[0].x0,
                            'LATIN-LEADING-HEBREW-CELL must retain RTL sentence order')
        numeric = paragraph_glyph_lines(page,geometry['key_body'])
        self.assertEqual([''.join(c['char'] for c in sorted(row,key=lambda c:c['origin'][0]))
                          for row in numeric],['001','027','314'])
        import check_pdf_render as render
        visible = render._visible_parenthesis_overrides(page)
        def physical_literal(text):
            boxes = page.search_for(text,clip=geometry['body'])
            self.assertEqual(len(boxes),1,(text,boxes,record))
            bounds = boxes[0]+(-.2,-.2,.2,.2)
            chars = [c for row in paragraph_glyph_lines(page,bounds) for c in row]
            return ''.join(visible.get((ord(c['char']),round(c['origin'][0],3),
                                       round(c['origin'][1],3)),c['char'])
                           for c in sorted(chars,key=lambda c:c['origin'][0]))
        for text in ('2020–2023','-12.50','LLVM (CPU)'):
            self.assertEqual(physical_literal(text),text.replace(' ',''),
                             ('LTR-CELL-CONTENT',record,text))
        all_chars = [c for row in paragraph_glyph_lines(page,geometry['body']) for c in row]
        mathematical = [c for c in all_chars if c['font'].startswith(('CM','MSAM','MSBM'))]
        x = [c for c in mathematical if c['char']=='x']
        plus = [c for c in mathematical if c['char']=='+']
        five = [c for c in mathematical if c['char']=='5']
        self.assertEqual((len(x),len(plus),len(five)),(1,1,1))
        self.assertLess(x[0]['origin'][0],plus[0]['origin'][0])
        self.assertLess(plus[0]['origin'][0],five[0]['origin'][0])
        subscripts = sorted([c for c in mathematical if c['size']<.9*size],
                            key=lambda c:c['origin'][0])
        self.assertEqual(''.join(c['char'] for c in subscripts),'12')
        if record['api']=='flow':
            self.assertAlmostEqual(geometry['rules'][0].width,
                (8+1.8)/2.54*72+12*72/72.27,delta=.5)
        else:
            self.assertLess(geometry['rules'][0].width,8/2.54*72+150,
                            'short keys must not be stretched to the paragraph width')
        return {'tag':record['tag'],'locale':record['locale'],'api':record['api'],
                'page':page.number+1,'meaning_body':list(geometry['body']),
                'physical_edge':geometry['edge'],'body_point_size':size,
                'actual_prose_lines':len(rows),'semantic_and_bidi_controls_passed':True}

    def assert_local_table_alignment_profiles(self):
        from test_academic_runtime import label_fields
        measurements = []
        profiles = [('english','english'),('hebrew','hebrew'),
                    ('english-with-hebrew','english'),('hebrew-with-english','hebrew'),
                    ('bilingual','english'),('bilingual','hebrew')]
        for profile,main in profiles:
            source,records = table_alignment_fixture(profile,main)
            result,directory = self.compile(source,'table-alignment-'+profile+'-'+main,passes=3)
            self.assertEqual(result.returncode,0,result.stdout[-6000:])
            log = (directory/'main.log').read_text()
            for bad in ('Overfull','Missing character:','undefined references','multiply defined'):
                self.assertNotIn(bad,log)
            aux = (directory/'main.aux').read_text()
            with fitz.open(directory/'main.pdf') as pdf:
                controls = []
                for record in records:
                    self.assert_table_semantic_order(pdf,record)
                    controls.append(self.assert_table_paragraph_alignment(pdf,record))
                    fields = label_fields(aux,record['label'])
                    target,_,y = pdf.resolve_link('#nameddest='+fields[4])
                    page,_ = self.alignment_table_geometry(pdf,record)
                    self.assertEqual(target,page.number)
                    self.assertGreaterEqual(y,0)
                    self.assertGreaterEqual(sum(link.get('nameddest')==fields[4]
                        for p in pdf for link in p.get_links()),2)  # authored ref + native list
                    self.assertEqual((directory/'main.lot').read_text().count(record['caption']),1)
            nav = subprocess.run([sys.executable,str(ROOT/'scripts/check_pdf_navigation.py'),
                                  str(directory/'main.pdf')],capture_output=True,text=True)
            self.assertEqual(nav.returncode,0,nav.stdout+nav.stderr)
            measurements.append({'profile':profile,'main':main,'controls':controls})
        for defect,code in [('wrong-hebrew-alignment','HEBREW-CELL-ALIGNMENT'),
                            ('wrong-english-alignment','ENGLISH-CELL-ALIGNMENT'),
                            ('reversed-hebrew-order','TABLE-SEMANTIC-COLUMN-ORDER')]:
            source,records = table_alignment_fixture('bilingual','english',defect=defect,apis=('open',))
            result,directory = self.compile(source,'table-alignment-negative-'+defect,passes=3)
            self.assertEqual(result.returncode,0,result.stdout[-5000:])
            with fitz.open(directory/'main.pdf') as pdf:
                affected = next(record for record in records if record['locale']==
                                ('english' if defect=='wrong-english-alignment' else 'hebrew'))
                if defect=='reversed-hebrew-order':
                    self.assert_table_paragraph_alignment(pdf,affected)
                    with self.assertRaisesRegex(AssertionError,code):
                        self.assert_table_semantic_order(pdf,affected)
                else:
                    self.assert_table_semantic_order(pdf,affected)
                    with self.assertRaisesRegex(AssertionError,code):
                        self.assert_table_paragraph_alignment(pdf,affected)
            measurements.append({'negative':defect,'named_policy_rejected':code,
                                 'independent_other_policy_still_passed':True})
        (self.root/'table-alignment-measurements.json').write_text(
            json.dumps(measurements,ensure_ascii=False,indent=2)+'\n')

    def assert_neutral_table_frame(self, page, frame, visible_border=True):
        # Actual PDF paints, not source declarations: table containers must
        # stay distinct from semantic blue/green/etc. White fill and gray ink.
        bounds = fitz.Rect(frame); bounds += (-3, -3, 3, 3)
        paints = [color for d in page.get_drawings() if bounds.contains(d['rect'])
                  for color in (d['color'], d['fill']) if color is not None]
        gray = 118 / 255
        allowed = ((0., 0., 0.), (1., 1., 1.), (gray, gray, gray))
        self.assertTrue(paints)
        for color in paints:
            self.assertTrue(any(all(abs(a-b)<.005 for a,b in zip(color,want))
                                for want in allowed), color)
        if visible_border:
            self.assertTrue(any(all(abs(v-gray)<.005 for v in color) for color in paints))

    def test_optional_frames_size_wrap_and_preserve_navigation(self):
        import check_pdf_render as render
        for main in ('english', 'hebrew'):
            with self.subTest(main=main):
                short = 'Compact records.' if main == 'english' else 'נתונים קצרים.'
                long = (r'FRAMECAP Long consistent caption with $x^2$ and \h{תוצאה}. '*4
                        if main == 'english' else
                        r'\en{FRAMECAP} תיאור ארוך עם $x^2$ ועם \en{LLVM}, הנשבר באופן טבעי. '*4)
                long += r' \href{https://example.org/framed-caption}{FRAMELINK}'
                prose = (r'Long prose wraps safely inside the chosen text column. '*5
                         if main == 'english' else
                         r'\h{תיאור עברי ארוך נשבר בעמודה בבטחה ושומר על גופן קריא, עם \en{LLVM}.} '*5)
                spec = (r'r>{\raggedright\arraybackslash}p{\framedtablewidth-2cm}'
                        if main == 'english' else
                        r'>{\raggedleft\arraybackslash}p{\framedtablewidth-2cm}r')
                row = r'\en{101}&'+prose+r'\\' if main == 'english' else prose+r'&\en{101}\\'
                source = (profile_header(main, main) + r'\newcounter{captioncalls}' + '\n'
                    + r'\newcommand{\captiononce}{\stepcounter{captioncalls}}' + '\n'
                    + r'\begin{document}\section{\en{Frame controls}}' + '\n'
                    + r'\begin{framedtable}[Short frame]{2}{rr}{\captiononce '+short+r'}{tab:frame-short}' + '\n'
                    + r'\toprule\en{ID}&\en{Value}\\\midrule\en{001}&\en{-12.50}\\\en{002}&\en{0.00}\\\bottomrule' + '\n'
                    + r'\end{framedtable}' + '\n'
                    + r'\begin{framedtable}[Long frame]{2}{'+spec+'}{'+long+r'}{tab:frame-long}' + '\n'
                    + r'\toprule'+row+r'\bottomrule\end{framedtable}' + '\n'
                    + r'\typeout{FRAMECALLS|\arabic{captioncalls}}' + '\n'
                    + r'\en{See }\autoref{tab:frame-short}, \nameref{tab:frame-short}, \ref{tab:frame-long}.' + '\n'
                    + r'\listoftables\end{document}')
                result, directory = self.compile(source, 'frames-'+main, passes=3)
                self.assertEqual(result.returncode, 0, result.stdout[-6000:])
                log = (directory/'main.log').read_text()
                for bad in ('Overfull', 'Missing character:', 'undefined references', 'multiply defined'):
                    self.assertNotIn(bad, log)
                self.assertIn('FRAMECALLS|1', log)  # no duplicate caption side effects
                with fitz.open(directory/'main.pdf') as doc:
                    self.assertEqual(len(doc), 1)
                    page = doc[0]
                    # Background rectangles are the actual frame interiors,
                    # not a source-width assertion. Include long wrapped cells.
                    frames = sorted([x['rect'] for x in page.get_drawings()
                                     if x['fill'] and x['rect'].height > 40
                                     and x['rect'].width > 40], key=lambda r:r.y0)
                    self.assertEqual(len(frames), 2)
                    self.assertLess(frames[0].width, page.rect.width/2)
                    self.assertGreater(frames[1].width, frames[0].width)
                    for frame in frames:
                        self.assert_neutral_table_frame(page, frame)
                        self.assertGreater(frame.x0, 55)
                        self.assertLess(frame.x1, page.rect.width-55)
                        words = [w for w in page.get_text('words')
                                 if frame.y0 < w[1] and w[3] < frame.y1]
                        self.assertTrue(words)
                        self.assertGreaterEqual(min(w[0] for w in words)-frame.x0, 9)
                        self.assertGreaterEqual(frame.x1-max(w[2] for w in words), 9)
                    sites = [x for x in render.caption_sites(page) if x[0]=='tbl']
                    self.assertCountEqual([(x[0],x[1]) for x in sites], [('tbl','1.1'),('tbl','1.2')])
                    for block in page.get_text('dict')['blocks']:
                        for line in block.get('lines', []):
                            for span in line['spans']:
                                if 'FRAMECAP' in span['text'] or 'FRAMELINK' in span['text']:
                                    self.assertEqual(span['color'], 0)
                                    self.assertFalse(span['flags'] & 16)
                                    self.assertAlmostEqual(span['size'], 9.96264, delta=.12)
                    dests = doc.resolve_names()
                    for number, frame in zip(('1.1','1.2'), frames):
                        dest = dests['tbl.'+number]
                        self.assertEqual(dest['page'], 0)
                        y = page.rect.height-dest['to'][1]
                        self.assertAlmostEqual(y, frame.y0-.9, delta=2)
                    text = page.get_text()
                    self.assertIn('001', text)
                    self.assertIn('101', text)
                    self.assertTrue(any(link.get('uri')=='https://example.org/framed-caption'
                                        for link in page.get_links()))
                    # Explicit LTR column order: the first declared numeric
                    # key in English is left; the last Hebrew key is right.
                    key = page.search_for('101')[0]
                    if main == 'english': self.assertLess(key.x0, frames[1].x0+50)
                    else: self.assertGreater(key.x1, frames[1].x1-50)
                self.assertIn('Short frame', (directory/'main.lot').read_text())
                self.assertIn('Long frame', (directory/'main.lot').read_text())
                self.assertIn(short.rstrip('.'), (directory/'main.aux').read_text())
                nav = subprocess.run([sys.executable, str(ROOT/'scripts/check_pdf_navigation.py'),
                                      str(directory/'main.pdf')], capture_output=True, text=True)
                self.assertEqual(nav.returncode, 0, nav.stdout+nav.stderr)
        # Actual engine failures, before mdframed can enter split trials.
        for name, spec, rows, phrase in (
                ('width', r'p{\linewidth}', 'Too wide.', 'exceeds the available width'),
                ('height', 'l', (r'Record\\'+'\n')*90, 'exceeds one page')):
            bad = (profile_header('english','english')+r'\begin{document}'
                   +r'\begin{framedtable}{1}{'+spec+r'}{Caption.}{tab:bad}'+rows
                   +r'\end{framedtable}\end{document}')
            result, _ = self.compile(bad, 'frames-rejected-'+name)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(phrase, result.stdout)

    def test_semantic_frames_match_real_boxes_and_adapt_column_structure(self):
        import check_pdf_render as render

        def source_for(main, theme):
            header = profile_header(main, main).replace(
                r'\input{reader_theme.tex}', '' if theme.startswith('core') else
                r'\input{' + theme + '_theme.tex}')
            if theme == 'core-custom':
                header += (r'\mdfapptodefinestyle{hllpdfsemanticgeometry}{leftmargin=12pt,rightmargin=5pt,'
                           r'innerleftmargin=13pt,innerrightmargin=8pt}'+'\n')
            short = 'Compact values.' if main == 'english' else 'מדידות קצרות.'
            caption = (r'Long uniform caption with $x^2$ and \h{מונח}. '*3 if main == 'english'
                       else r'תיאור אחיד וארוך עם $x^2$ ועם \en{LLVM}. '*3)
            caption += r' \href{https://example.org/frame-modes}{MODELINK}'
            compact = (r'SID2&VAL2\\\midrule001&-12.50\\002&0.00\\' if main == 'english'
                       else r'VAL2&SID2\\\midrule-12.50&001\\0.00&002\\')
            five = (r'CID5&CNT5&MEAN5&SD5&STATE5\\\midrule001&12&1.25&$x^2$&Observed\\'
                    if main == 'english' else
                    r'STATE5&SD5&MEAN5&CNT5&CID5\\\midrule\h{נצפה}&$x^2$&1.25&12&001\\')
            prose = (r'WRAPTEXT Long explanatory prose with $x^2$ and \h{מונח} wraps safely. '*4
                     if main == 'english' else
                     r'\h{\en{WRAPTEXT} תיאור ארוך שנשבר בבטחה, עם $x^2$ ועם \en{LLVM}.} '*4)
            spec = (r'rrc>{\raggedright\arraybackslash}p{\framedtablewidth-5cm}' if main == 'english'
                    else r'>{\raggedleft\arraybackslash}p{\framedtablewidth-5cm}crr')
            rows = (r'ID&Value&Model&Description\\\midrule101&-3.50&$x^2$&'+prose+r'\\'
                    if main == 'english' else
                    r'\h{תיאור}&\h{מודל}&\h{ערך}&\h{מזהה}\\\midrule'+prose+r'&$x^2$&-3.50&101\\')
            return (header+r'\newcounter{captioncalls}\newcounter{boxcalls}'+'\n'
                +r'\newcommand{\captiononce}{\stepcounter{captioncalls}}'+'\n'
                +r'\BeforeBeginEnvironment{defbox}{\stepcounter{boxcalls}}'+'\n'
                +r'\begin{document}\section{\en{Adaptable frame modes}}'+'\n'
                +r'\begin{defbox}[frametitle={\en{Semantic geometry reference}}]'
                +r'\begin{otherlanguage}{english}\noindent\rule{.25pt}{12pt}\hfill\rule{.25pt}{12pt}\par'
                +r'\noindent BOXREFMARK Actual semantic box in this document.\par\end{otherlanguage}\end{defbox}'+'\n'
                +r'\begin{semanticframedtable}[Two chosen fields]{2}{rr}{\captiononce '+short+r'}{tab:semantic-two}'+'\n'
                +r'\toprule '+compact+r'\bottomrule\end{semanticframedtable}'+'\n'
                +r'\begin{framedtable}[Five chosen fields]{5}{'+('rrrrl' if main=='english' else 'lcrrr')
                +r'}{\en{Five measured fields.}}{tab:fit-five}\toprule '+five+r'\bottomrule\end{framedtable}'+'\n'
                +r'\begin{semanticframedtable}[Four chosen fields]{4}{'+spec+r'}{'+caption+r'}{tab:semantic-four}'+'\n'
                +r'\toprule '+rows+r'\midrule\multicolumn{4}{p{\framedtablewidth+6\tabcolsep}}'
                +r'{\noindent\rule{.25pt}{12pt}\hfill\rule{.25pt}{12pt}}\\\bottomrule\end{semanticframedtable}'+'\n'
                +r'\typeout{MODECALLS|\arabic{boxcalls}|\arabic{captioncalls}}'+'\n'
                +r'\en{References: }\autoref{tab:semantic-two}, \nameref{tab:fit-five}, \ref{tab:semantic-four}.'+'\n'
                +r'\listoftables\end{document}')

        def geometry(directory, main, theme='core'):
            with fitz.open(directory/'main.pdf') as doc:
                self.assertEqual(len(doc), 1)
                page = doc[0]
                fills = [d['rect'] for d in page.get_drawings()
                         if d['fill'] and d['rect'].width > 40 and d['rect'].height > 25]
                def enclosing(marker):
                    rect = page.search_for(marker)[0]
                    return max((f for f in fills if f.contains(rect)), key=lambda f:f.width*f.height)
                reference = enclosing('BOXREFMARK')
                short = enclosing('SID2')
                fit = enclosing('CID5')
                long = enclosing('WRAPTEXT')
                for frame in (short, fit, long):
                    self.assert_neutral_table_frame(page, frame, theme != 'academic')
                for frame in (short, long):
                    self.assertAlmostEqual(frame.x0, reference.x0, delta=.3)
                    self.assertAlmostEqual(frame.x1, reference.x1, delta=.3)
                self.assertLess(fit.width, reference.width-40)
                # The outer frame is wide; natural short rows still occupy
                # their own compact width, rather than filling it with glue.
                sid, value = page.search_for('SID2')[0], page.search_for('VAL2')[0]
                self.assertLess(abs(sid.x0-value.x0), short.width/2)
                self.assertLess(sid.x0,value.x0) if main=='english' else self.assertGreater(sid.x0,value.x0)
                five = [page.search_for(t)[0] for t in ('CID5','CNT5','MEAN5','SD5','STATE5')]
                self.assertEqual(len({round(r.x0,1) for r in five}), 5)
                self.assertLess(five[0].x0,five[-1].x0) if main=='english' else self.assertGreater(five[0].x0,five[-1].x0)
                self.assertGreater(len({round(r.y0,1) for r in page.search_for('WRAPTEXT')}),2)
                # Actual PDF ink markers expose the inherited left/right
                # inset: the table adds exactly its normal cell padding.
                marks = [d['rect'] for d in page.get_drawings()
                         if d['type']=='s' and d['color']==(0.,0.,0.)
                         and .15 < d['width'] < .4 and d['rect'].width < .5
                         and 10 < d['rect'].height < 14]
                ref_marks=sorted([r for r in marks if reference.y0 < r.y0 < reference.y1],key=lambda r:r.x0)
                table_marks=sorted([r for r in marks if long.y0 < r.y0 < long.y1],key=lambda r:r.x0)
                self.assertEqual((len(ref_marks),len(table_marks)),(2,2))
                cell_pad = 6*72/72.27
                self.assertAlmostEqual(table_marks[0].x0-ref_marks[0].x0,cell_pad,delta=.3)
                self.assertAlmostEqual(ref_marks[1].x1-table_marks[1].x1,cell_pad,delta=.3)
                sites=[s for s in render.caption_sites(page) if s[0]=='tbl']
                numbers=('1','2','3') if theme in ('academic','reference','clean') else ('1.1','1.2','1.3')
                self.assertCountEqual([(s[0],s[1]) for s in sites], [('tbl',n) for n in numbers])
                dests=doc.resolve_names()
                for number,frame in zip(numbers,(short,fit,long)):
                    # Clean hides section numbering but retains the reset-parent
                    # anchor identity, independently of the printed number.
                    dest=dests[('tbl.0.' if theme == 'clean' else 'tbl.')+number]
                    self.assertEqual(dest['page'],0)
                    self.assertAlmostEqual(page.rect.height-dest['to'][1],frame.y0,delta=2)
                links=page.get_links()
                self.assertTrue(any(l.get('uri')=='https://example.org/frame-modes' for l in links))
                for block in page.get_text('dict')['blocks']:
                    for line in block.get('lines',[]):
                        for span in line['spans']:
                            if 'MODELINK' in span['text']:
                                self.assertEqual(span['color'],0)
                                self.assertFalse(span['flags'] & 16)
                                self.assertAlmostEqual(span['size'],9.96264,delta=.12)

        for theme in ('core','reader','academic','reference','clean','core-custom'):
            for main in ('english','hebrew'):
                with self.subTest(theme=theme,main=main):
                    source=source_for(main,theme)
                    result,directory=self.compile(source,'frame-modes-'+theme+'-'+main,passes=3)
                    self.assertEqual(result.returncode,0,result.stdout[-6000:])
                    log=(directory/'main.log').read_text()
                    self.assertIn('MODECALLS|1|1',log)
                    for bad in ('Overfull','Missing character:','undefined references','multiply defined'):
                        self.assertNotIn(bad,log)
                    geometry(directory,main,theme)
                    lot=(directory/'main.lot').read_text()
                    for entry in ('Two chosen fields','Five chosen fields','Four chosen fields'):
                        self.assertEqual(lot.count(entry),1)
                    nav=subprocess.run([sys.executable,str(ROOT/'scripts/check_pdf_navigation.py'),
                                        str(directory/'main.pdf')],capture_output=True,text=True)
                    self.assertEqual(nav.returncode,0,nav.stdout+nav.stderr)
        for name,source in (
            ('wrong-width',source_for('english','core').replace('semanticframedtable','framedtable')),
            ('wrong-insets',source_for('english','core').replace(r'\begin{document}',
                r'\renewcommand{\hllpdfsemanticframestyle}{hllpdftablegeometry}\begin{document}')),
            ('wrong-palette',source_for('english','core').replace(r'\begin{document}',
                r'\definecolor{cTblLine}{HTML}{B9C4D2}\begin{document}')),
            ('wrong-fill',source_for('english','core').replace(r'\begin{document}',
                r'\definecolor{cTblBg}{HTML}{FAFBFC}\begin{document}'))):
            result,directory=self.compile(source,'frame-modes-'+name,passes=2)
            self.assertEqual(result.returncode,0,result.stdout[-3000:])
            with self.assertRaises(AssertionError): geometry(directory,'english')
        for mode in ('framedtable','semanticframedtable'):
            for name,spec,rows,phrase in (
                ('width',r'p{\linewidth}','Too wide.','exceeds the available width'),
                ('height','l',(r'Record\\'+'\n')*90,'exceeds one page'),
                ('count','l','Invalid.','requires a positive column count')):
                count='0' if name=='count' else '1'
                source=(profile_header('english','english')+r'\begin{document}\begin{'+mode+r'}{'+count
                    +r'}{'+spec+r'}{Caption.}{tab:bad}'+rows+r'\end{'+mode+r'}\end{document}')
                result,_=self.compile(source,'frame-modes-rejected-'+mode+'-'+name)
                self.assertNotEqual(result.returncode,0)
                self.assertIn(phrase,result.stdout)

    def test_bad_profiles_fail_before_document_loading(self):
        cases=[('unknown',r'\def\lakitlanguageprofile{french}','unsupported language profile'),
               ('bilingual-missing',r'\def\lakitlanguageprofile{bilingual}','requires explicit lakitmainlanguage'),
               ('wrong-base',r'\def\lakitlanguageprofile{english}\def\lakitmainlanguage{hebrew}','conflicts'),
               ('bad-base',r'\def\lakitlanguageprofile{bilingual}\def\lakitmainlanguage{french}','must be hebrew or english')]
        for name,config,phrase in cases:
            with self.subTest(name=name):
                result,_=self.compile(config+HEADER+r'\begin{document}Never printed.\end{document}',name)
                self.assertNotEqual(result.returncode,0)
                self.assertIn(phrase,result.stdout)
                self.assertNotIn('Document Class:',result.stdout)

    def test_english_codebox_keeps_two_digit_labels_inside_rule(self):
        source=(profile_header('english','english')+r'\begin{document}'+
                r'\begin{codebox}\begin{asmblock}\begin{lstlisting}[style=pystyle]'+'\n'+
                '\n'.join('print(value)' for _ in range(12))+'\n'+
                r'\end{lstlisting}\end{asmblock}\end{codebox}\end{document}')
        def clearance(directory):
            with fitz.open(directory/'main.pdf') as doc:
                page=doc[0]
                rules=[x['rect'] for x in page.get_drawings()
                       if x['color'] and x['rect'].width < 1 and x['rect'].height > 40]
                self.assertTrue(rules)
                rule=min(rules,key=lambda r:r.x0)
                words=page.get_text('words')
                code=min(w[0] for w in words if 'print' in w[4])
                labels=[w for w in words if w[4].isdigit() and
                        rule.y0 < w[1] < rule.y1 and w[2] < code]
                self.assertEqual([w[4] for w in labels],[str(i) for i in range(1,13)])
                return min(w[0] for w in labels)-rule.x0
        result,directory=self.compile(source,'codebox-en',passes=2)
        self.assertEqual(result.returncode,0,result.stdout[-5000:])
        self.assertGreater(clearance(directory),8)
        result,directory=self.compile(source,'codebox-en-mutant',passes=2,
            mutate=lambda t:t.replace(r'\lstset{xleftmargin=26pt,xrightmargin=0pt}', ''))
        self.assertEqual(result.returncode,0,result.stdout[-5000:])
        self.assertLess(clearance(directory),0)

    def test_clean_exam_labels_localize_in_english(self):
        source=(profile_header('english','english').replace(r'\input{reader_theme.tex}',r'\input{clean_theme.tex}')+
                r'''\begin{document}\section{Question}
\begin{exbox}Question text.\end{exbox}
\begin{keybox}Takeaway text.\end{keybox}
\begin{notebox}Note body.\end{notebox}
\end{document}''')
        result,directory=self.compile(source,'clean-english',passes=3)
        self.assertEqual(result.returncode,0,result.stdout[-5000:])
        with fitz.open(directory/'main.pdf') as doc:
            text='\n'.join(p.get_text() for p in doc)
            for value in ('Solution:','Exam takeaway.','Note.'):
                self.assertIn(value,text)
            self.assertNotRegex(text,'[\u0590-\u05ff]')

if __name__=='__main__': unittest.main()
