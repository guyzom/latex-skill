#!/usr/bin/env python3
"""Portable handwritten component fixtures for declared QA coverage.

Synthetic sample text exercises existing APIs; it is not user content or a
research citation. Fixture generation performs no engines and no visual claim.
"""
from __future__ import annotations
from pathlib import Path
import re
import shutil
import struct
import sys
import zlib
sys.dont_write_bytecode = True
from architecture_contract import ASSET_SPECS, HOOK_SPECS, REFERENCE_STYLE_HOOK_SPECS
from heading_source import clean_source

def core_body(lang):
    if lang == 'hebrew':
        title='בדיקת רכיבים קיימים'; intro='זו דוגמה סינתטית לבדיקת עימוד, שפה והפניות. היא אינה מסמך מחקר.'
        note='הנוסחה משמרת את סדר המשתנים והיחידות. ראו משוואה~\\eqref{eq:energy}.'
        minority='\\begin{englishprose}\nThis English paragraph keeps its native reading order. The quantity is $80\\punit{ns}$.\n\\end{englishprose}'
        tablecap='טבלת נתוני בדיקה'; figcap='תרשים סינתטי לבדיקת כיתוב'; objects='אובייקטים והפניות'
        labels=('הגדרה','משפט','הערה','דוגמה','אזהרה','רעיון מרכזי')
        tail='ההפניות צריכות להגיע לאובייקטים שלהן: טבלה~\\ref{tab:sample}, איור~\\ref{fig:sample}.'
    else:
        title='Existing component baseline'; intro='This synthetic fixture checks layout, language and references. It is not a research document.'
        note='The equation preserves variables and units. See equation~\\eqref{eq:energy}.'
        minority='\\begin{hebrewprose}\nהפסקה העברית שומרת על כיוון הקריאה שלה. הערך הוא $80\\punit{ns}$.\n\\end{hebrewprose}'
        tablecap='Synthetic test records'; figcap='Synthetic diagram caption'; objects='Objects and references'
        labels=('Definition','Theorem','Note','Example','Caution','Key idea')
        tail='References must reach their own objects: table~\\ref{tab:sample}, figure~\\ref{fig:sample}.'
    content=rf'''\section{{{title}}}
{intro}
\begin{{equation}}\label{{eq:energy}}
 E=\frac{{1}}{{2}}mv^2,\qquad x_{{i_j}}=\frac{{\alpha+\beta}}{{\sqrt{{1+\lambda^2}}}}.
\end{{equation}}
{note}
{minority}
'''
    for env,label in zip(('defbox','thmbox','notebox','exbox','warnbox','keybox'),labels):
        content+=rf'''\begin{{{env}}}[frametitle={{{label}}}]
{note}
\[ f(x)=x^2,\qquad f'(x)=2x. \]
\end{{{env}}}
'''
    content+=rf'''\clearpage
\section{{{objects}}}
\begin{{codebox}}[frametitle={{\en{{Python example}}}}]
\begin{{asmblock}}
\begin{{lstlisting}}[style=pystyle,firstnumber=98]
alpha = 10
beta = 20
result = alpha + beta
\end{{lstlisting}}
\end{{asmblock}}
\end{{codebox}}
\begin{{tablebox}}\centering
\begin{{tabular}}{{rr}}
\toprule
$i$ & $x_i$ \\
\midrule
1 & 10 \\
2 & 20 \\
\bottomrule
\end{{tabular}}
\tabcap{{\label{{tab:sample}}{tablecap}}}
\end{{tablebox}}
\begin{{tikzpic}}
\begin{{tikzpicture}}
\node[draw] (a) at (0,0) {{$x$}};
\node[draw] (b) at (3,0) {{$f(x)$}};
\draw[->] (a) -- (b);
\end{{tikzpicture}}
\end{{tikzpic}}
\figcap{{\label{{fig:sample}}{figcap}}}
{tail}
'''
    return content

def exam_body(lang):
    if lang=='hebrew':
        question='שאלה לדוגמה'; statement='חשבו את הנגזרת של הפונקציה. זו שאלת בדיקה סינתטית.'
        solution='משתמשים בכלל החזקה.'; cap='איור מקור סינתטי'; tablecap='ערכי הנגזרת'; ref='ראו שאלה~\\ref{q:sample} ואיור~\\ref{fig:source}.'
    else:
        question='Sample question'; statement='Differentiate the function. This is a synthetic test question.'
        solution='Apply the power rule.'; cap='Synthetic source figure'; tablecap='Derivative values'; ref='See question~\\ref{q:sample} and figure~\\ref{fig:source}.'
    minority=('\\begin{englishprose}The short English paragraph is local.\\end{englishprose}' if lang=='hebrew'
              else '\\begin{hebrewprose}הפסקה העברית קצרה ומקומית.\\end{hebrewprose}')
    return rf'''\section{{{question}}}
\qlabel{{{question}}}{{q:sample}}\pts{{10}}
\begin{{exbox}}
{statement}
\begin{{equation}}\label{{eq:exam}} f(x)=x^3.\end{{equation}}
\end{{exbox}}
{solution}
\[\finalans{{f'(x)=3x^2}}\]
{minority}
\begin{{keybox}}{solution}\end{{keybox}}
\begin{{notebox}}{ref}\end{{notebox}}
\srcfig{{0.35}}{{fixture.png}}{{\label{{fig:source}}{cap}}}
{ref}
\begin{{tablebox}}\centering
\begin{{tabular}}{{rr}}$x$ & $f'(x)$ \\ 1 & 3 \\ 2 & 12\end{{tabular}}
\tabcap{{\label{{tab:exam}}{tablecap}}}
\end{{tablebox}}
'''

def rail_body(lang):
    if lang=='hebrew':
        chapter='התנהגות ברירת המחדל'; explicit='בחירה מפורשת בכיוון'; label='הדוגמה משתמשת בכיוון ברירת המחדל של פס הנושאים.'
        direction='\\STdirRTL'; explanation='בדוגמה זו נבחר כיוון מימין לשמאל במפורש.'
        minority='\\begin{englishprose}The local English paragraph does not change the rail order.\\end{englishprose}'
        names='יסודות,שיטות,תוצאות'
    else:
        chapter='Default rail behavior'; explicit='Explicit direction selection'; label='This page retains the shipped default rail direction.'
        direction='\\STdirLTR'; explanation='This page explicitly selects left-to-right rail order.'
        minority='\\begin{hebrewprose}הפסקה המקומית אינה משנה את סדר פס הנושאים.\\end{hebrewprose}'
        names='Foundations,Methods,Results'
    body=rf'''\pagestyle{{STtopic}}
\part{{{chapter}}}
\chapter{{{chapter}}}
{label}
{minority}
\begin{{equation}}\label{{eq:rail}}E=\frac{{1}}{{2}}mv^2.\end{{equation}}
\begin{{tablebox}}\centering
\begin{{tabular}}{{rr}}$i$ & $x_i$ \\ 1 & 10 \\ 2 & 20\end{{tabular}}
\tabcap{{\label{{tab:rail}}{chapter}}}
\end{{tablebox}}
\clearpage
{direction}
\section{{{explicit}}}
{explanation}
\begin{{tikzpic}}\begin{{tikzpicture}}\node[draw] (a) at (0,0) {{$x$}};\node[draw] (b) at (3,0) {{$f(x)$}};\draw[->] (a)--(b);\end{{tikzpicture}}\end{{tikzpic}}
\figcap{{\label{{fig:rail}}{explicit}}}
'''
    return names,body

def fixture_families():
    return ('core', 'reader', 'academic', 'clean', 'custom', 'exam-clean',
            'legacy-clean', 'topicrail', 'source-links', 'deferred-notes',
            'flow-tables', 'reference-all')


def deferred_body(lang):
    title = 'Deferred note component' if lang == 'english' else 'רכיב הערות נדחות'
    native = 'A native keyed explanation.' if lang == 'english' else 'הסבר מקומי בעל מפתח קבוע.'
    other = 'hebrew' if lang == 'english' else 'english'
    minority = 'הסבר עברי מקומי.' if other == 'hebrew' else 'A local English explanation.'
    declarations = (rf'\DeclareDocNote[{lang}]{{native}}{{{native}}}' + '\n'
                    + rf'\DeclareDocNote[{other}]{{minority}}{{{minority}}}' + '\n')
    body = (rf'\section{{{title}}}' + '\n'
            + r'\begin{notebox}\en{NOTENATIVE}\DocNoteMark{native} $x=1$.\end{notebox}\PrintDocNotes' + '\n'
            + rf'\begin{{{other}prose}}' + minority + r'\DocNoteMark{minority}'
            + rf'\end{{{other}prose}}\PrintDocNotes' + '\n'
            + r'\clearpage\section{\doclang{' + title + r'}}\en{NOTEREUSE}\DocNoteMark{native}\DocNoteMark{minority}' + '\n'
            + r'\PrintDocNotes' + '\n')
    return declarations, body


def flow_body(lang):
    title = 'Multipage synthetic records' if lang == 'english' else 'רשומות סינתטיות לאורך עמודים'
    note = ('A synthetic row with units and a complete descriptive note.' if lang == 'english'
            else r'רשומה סינתטית עם יחידות ותיאור מלא. הסימון \en{sample} נשאר בכיוון הקריאה המתאים.')
    prose_col = 'E' if lang == 'english' else 'H'
    body = (rf'\section{{{title}}}' + '\n'
            + r'\begin{flowtable}{3}{N{.15\flowtablewidth} N{.20\flowtablewidth} '
            + prose_col + r'{.65\flowtablewidth}}{' + title + r'}{tab:flow}{\en{ID}&$x_i$&\doclang{' + title + '}}\n')
    for index in range(1, 49):
        body += f'{index:03d} & {index / 4 - 6:.2f} & {note}' + r'\\' + '\n'
    body += (r'\end{flowtable}' + '\n'
             + r'\noindent\en{FLOWEND} \autoref{tab:flow}. $\bar{x}=1/8$.\par' + '\n')
    return body


def reference_body(lang):
    topic = 'Reference component gallery' if lang == 'english' else 'גלריית רכיבי דף עזר'
    wide_topic = 'Wide topic control' if lang == 'english' else 'בדיקת נושא ברוחב מלא'
    secondary = 'A subtopic' if lang == 'english' else 'תת נושא'
    other = 'hebrew' if lang == 'english' else 'english'
    note = 'A short locally authored note.' if lang == 'english' else 'הערה קצרה בשפת הפסקה המקומית.'
    minority = 'הערה עברית מקומית.' if other == 'hebrew' else 'A local English note.'
    return (r'\makereferencetitle' + '\n'
            + r'\begin{referencewide}\section{' + wide_topic + r'}\en{WIDETOPIC} $x_{i_j}=\alpha+\beta$.\end{referencewide}' + '\n'
            + r'\begin{referencecolumns}' + '\n'
            + r'\begin{referenceentry}\section{' + topic + '}\n'
            + r'\subsection{' + secondary + r'}\en{ENTRYBODY} $x_{i_j}=1$.\end{referenceentry}' + '\n'
            + r'\begin{referencenote}\en{NATIVEBLOCK} ' + note + r'\end{referencenote}' + '\n'
            + rf'\begin{{{other}prose}}\begin{{referencenote}}\en{{MINORITYBLOCK}} {minority}\end{{referencenote}}\end{{{other}prose}}' + '\n'
            + r'\begin{referencewarning}\en{WARNINGBLOCK} ' + note + r'\end{referencewarning}' + '\n'
            + r'\begin{referenceformula}\noeqref{eq:central}\begin{equation}\label{eq:central}E=\frac12mv^2.\end{equation}\end{referenceformula}' + '\n'
            + r'\begin{referenceqa}\referencequestion{\en{QAQUESTION} $f(x)=x^2$.}\referencesolution{\en{QASOLUTION} $f\prime(x)=2x$.}\referencepurpose{\en{USEFIELD}}\referenceconditions{\en{CONDITIONSFIELD} $x\in\mathbb R$.}\end{referenceqa}' + '\n'
            + r'\begin{referenceqaseries}[\doclang{' + secondary + r'}]\referencequestion{\en{SERIESQUESTION} $a+b=c$.}' + '\n'
            + r'\begin{referencesolutionpart}\en{SERIESPARTONE} $a=c-b$.\end{referencesolutionpart}' + '\n'
            + r'\referencesolution{\en{SERIESPARTTWO} $b=c-a$.}\end{referenceqaseries}' + '\n'
            + r'\begin{referencefigure}\begin{tikzpic}\begin{tikzpicture}\node[draw] (a) at(0,0){$x$};\node[draw] (b) at(2,0){$f(x)$};\draw[->](a)--(b);\end{tikzpicture}\end{tikzpic}' + '\n'
            + r'\referencefigcap{\label{fig:ref}\doclang{' + secondary + r'}}\end{referencefigure}' + '\n'
            + r'\begin{referencetable}\begin{tablebox}\centering\begin{tabular}{rr}$i$&$x_i$\\1&10\\2&20\end{tabular}' + '\n'
            + r'\referencetabcap{\label{tab:ref}\doclang{' + secondary + r'}}\end{tablebox}\end{referencetable}' + '\n'
            + r'\noindent\en{REFERENCEEND \eqref{eq:central}, \ref{fig:ref}, \ref{tab:ref}}.\par' + '\n'
            + r'{\ReferenceSelectBodyFont $\mathsf{x}_{i_j}=\mathbb R$.}' + '\n'
            + r'\end{referencecolumns}' + '\n')


def _chunk(tag: bytes, data: bytes) -> bytes:
    return struct.pack('!I', len(data)) + tag + data + struct.pack('!I', zlib.crc32(tag + data) & 0xffffffff)


def fixture_png(path: Path) -> None:
    """A small deterministic diagram, written with only the standard library."""
    width, height = 360, 160
    rows = []
    for y in range(height):
        row = bytearray(b'\x00')
        for x in range(width):
            border = ((20 <= x <= 120 or 240 <= x <= 340) and (40 <= y <= 43 or 117 <= y <= 120)) or ((20 <= x <= 23 or 117 <= x <= 120 or 240 <= x <= 243 or 337 <= x <= 340) and 40 <= y <= 120)
            line = 120 <= x <= 240 and 78 <= y <= 81
            black = border or line
            row.extend((0, 0, 0) if black else (255, 255, 255))
        rows.append(row)
    path.write_bytes(b'\x89PNG\r\n\x1a\n' + _chunk(b'IHDR', struct.pack('!IIBBBBB', width, height, 8, 2, 0, 0, 0)) + _chunk(b'IDAT', zlib.compress(b''.join(rows), 9)) + _chunk(b'IEND', b''))


def validate_fixture_source(metadata: dict, source: str) -> list[str]:
    """Reject loaded-only API/hook claims; this is source provenance, not QA.

    Actual build and PDF/render review remain the matrix runner's job. A source
    match does not establish scientific correctness, glyph geometry, every
    option or all combinations. Header callbacks have a bounded explicit
    indirect path whose actual labels must be present in the resulting PDF.
    """
    errors = []
    raw_source = source
    source = clean_source(source)
    tokens = set(re.findall(r'\\([A-Za-z]+)', source)) | set(re.findall(r'\\begin\{([A-Za-z]+)\}', source))
    by_path = {spec.path: spec for spec in ASSET_SPECS}
    for path in metadata['architecture_assets']:
        if path not in by_path or r'\input{' + Path(path).name + '}' not in source:
            errors.append(f'{path}: declared architectural asset is not input by the actual fixture')
    for path, symbols in metadata['public_usage'].items():
        for symbol in symbols:
            if symbol not in by_path[path].public_symbols:
                errors.append(f'{path}:{symbol}: API has no declared owner')
            elif symbol not in tokens:
                if (path != 'assets/topicrail.tex' or symbol not in ('STdrawrail', 'STgetname')
                        or r'\pagestyle{STtopic}' not in source or r'\STnames{' not in source
                        or r'\part{' not in source):
                    errors.append(f'{path}:{symbol}: loaded-only API claim lacks actual use')
    hook_specs = {hook.name: hook for hook in HOOK_SPECS}
    for name in metadata['configuration_hooks']:
        declaration = rf'\\(?:def|newcommand|renewcommand|providecommand)\s*(?:\{{\\{name}\}}|\\{name}\b)'
        match = re.search(declaration, source)
        if not match:
            errors.append(f'{name}: hook coverage lacks an authored declaration')
        elif hook_specs[name].define_before:
            owner_input = r'\input{' + Path(hook_specs[name].define_before).name + '}'
            if owner_input not in source or match.start() > source.index(owner_input):
                errors.append(f'{name}: authored hook declaration does not precede its owner')
    if any(ord(char) < 32 and char not in '\n\t' for char in raw_source):
        errors.append('fixture contains an unintended control character')
    return errors


def write_fixture(root: Path, project: Path, family: str, language: str) -> dict:
    if family not in fixture_families() or language not in ('hebrew', 'english'):
        raise ValueError('unknown manual fixture family/language')
    project.mkdir(parents=True, exist_ok=False)
    assets = ['preamble.tex']
    if family == 'exam-clean':
        assets += ['exam_components.tex', 'clean_theme.tex']
    elif family == 'legacy-clean':
        assets += ['clean_variant.tex']
    elif family == 'topicrail':
        assets += ['topicrail.tex']
    elif family == 'source-links':
        assets += ['document_components.tex', 'reader_theme.tex']
    elif family in ('reader', 'academic', 'clean'):
        assets += [family + '_theme.tex']
    elif family == 'deferred-notes':
        assets += ['deferred_notes.tex', 'reader_theme.tex']
    elif family == 'flow-tables':
        assets += ['flow_tables.tex', 'reader_theme.tex']
    elif family == 'reference-all':
        assets += ['reference_components.tex', 'reference_columns.tex',
                   'reference_shell.tex', 'reference_theme.tex']
    by_name = {spec.basename: spec for spec in ASSET_SPECS}
    for name in assets:
        if name not in by_name:
            raise ValueError('fixture asset lacks an architectural owner')
        shutil.copyfile(root / by_name[name].path, project / name)
    if family == 'custom':
        from new_document import CUSTOM_THEME
        (project / 'theme.tex').write_text(CUSTOM_THEME, encoding='utf-8')
    if family in ('exam-clean', 'legacy-clean'):
        (project / 'illustrations').mkdir()
        fixture_png(project / 'illustrations' / 'fixture.png')
    cls = 'report' if family == 'topicrail' else 'article'
    pre = (rf'\def\lakitlanguageprofile{{{language}}}\def\lakitmainlanguage{{{language}}}' + '\n'
           + rf'\def\lakitdocumentclass{{{cls}}}' + '\n'
           + r'\def\lakitclassoptions{11pt,a4paper}' + '\n'
           + r'\def\lakitgeometryoptions{margin=2.3cm,headheight=14pt}' + '\n'
           + r'\def\lakitlinespread{1.08}\def\lakittocdepth{1}\def\lakitsecnumdepth{2}' + '\n'
           + rf'\def\lakitparagraphstyle{{{"indented" if family == "academic" else "block"}}}' + '\n')
    if family == 'flow-tables':
        # Repeated continuation text belongs above the footer's inspection
        # band, with ordinary centered folios kept below it. This is authored
        # page geometry, not a relaxed or custom folio-check waiver.
        pre += r'\def\lakitgeometryoptions{left=2.3cm,right=2.3cm,top=2.3cm,bottom=3.2cm,headheight=14pt}' + '\n'
    if family == 'reference-all':
        pre += (r'\def\ReferenceColumnCount{2}\def\ReferenceColumnGap{5mm}\def\ReferenceColumnRule{.3pt}\def\ReferenceColumnSkip{6pt}' + '\n'
                + r'\def\ReferenceBodyFontSize{9}\def\ReferenceBodyBaseline{11}' + '\n'
                + r'\def\ReferenceMathFontSize{8.75}\def\ReferenceMathScriptSize{6.125}\def\ReferenceMathScriptScriptSize{4.375}' + '\n'
                + r'\def\ReferenceTitle{\doclang{' + ('Reference component gallery' if language == 'english' else 'גלריית רכיבי דף עזר') + '}}\n'
                + r'\def\ReferenceShortTitle{\en{REFERENCEHEADER}}' + '\n'
                + r'\def\ReferenceSubtitle{\doclang{' + ('Synthetic component controls' if language == 'english' else 'בדיקות רכיבים סינתטיות') + '}}\n'
                + r'\def\ReferenceAuthor{\doclang{' + ('Synthetic QA' if language == 'english' else 'בדיקה סינתטית') + '}}\n'
                + r'\def\ReferenceDate{\en{2026}}' + '\n')
    # Caption hooks are declared using their public signatures, then the
    # chosen theme may deliberately override these shared presentation hooks.
    pre += r'\input{preamble.tex}' + '\n'
    pre += (r'\renewcommand{\lakitcaptionlabelstyle}[1]{\textcolor{cGray}{\textbf{#1}}}' + '\n'
            + r'\renewcommand{\lakitcaptionpunctuation}{.}' + '\n'
            + r'\lakitcaptionnumbering{continuous}' + '\n')
    pre += ''.join(r'\input{' + name + '}\n' for name in assets[1:])
    if family == 'custom':
        pre += r'\input{theme.tex}' + '\n'
    if family == 'topicrail':
        names, body = rail_body(language)
        pre += r'\STrailwidth{12}\STrailangle{40}\STnames{' + names + '}\n'
    elif family in ('exam-clean', 'legacy-clean'):
        pre += r'\renewcommand{\srcfigdir}{illustrations}' + '\n'
        body = exam_body(language)
    elif family == 'deferred-notes':
        declarations, body = deferred_body(language)
        pre += declarations
    elif family == 'flow-tables':
        body = flow_body(language)
    elif family == 'reference-all':
        # Exercise mutable hooks at their supported presentation boundary,
        # keeping note bars and complete formula/QA frames deliberate.
        for style in REFERENCE_STYLE_HOOK_SPECS:
            bars = (r'leftline=true,rightline=false,topline=false,bottomline=false'
                    if style.name in ('referencenotestyle', 'referencewarningstyle')
                    else r'leftline=true,rightline=true,topline=true,bottomline=true')
            pre += ('\\renewcommand{\\' + style.name + r'}{linecolor=black,backgroundcolor=black!5,' + bars
                    + r',innerleftmargin=3pt,innerrightmargin=3pt,innertopmargin=2pt,innerbottommargin=2pt,skipabove=3pt,skipbelow=3pt,startinnercode=\raggedright}' + '\n')
        body = reference_body(language)
    else:
        body = core_body(language)
    if family == 'source-links':
        label = 'Synthetic source annotation' if language == 'english' else 'תווית מקור סינתטית'
        other = 'hebrew' if language == 'english' else 'english'
        minority_label = 'תווית מקור בעברית' if other == 'hebrew' else 'A local English source'
        body += (rf'\sourcelink{{https://example.org/control?first=1&second=2\#part}}{{{label}}}{{{label}}}' + '\n'
                 + rf'\begin{{{other}prose}}\sourcelink{{https://example.org/local}}{{{minority_label}}}{{{minority_label}}}\end{{{other}prose}}' + '\n')
    pre += r'\hypersetup{pdftitle={Synthetic component QA},pdfauthor={}}' + '\n'
    source = pre + r'\begin{document}' + '\n' + body + r'\end{document}' + '\n'
    if any(ord(char) < 32 and char not in '\n\t' for char in source):
        raise ValueError('fixture source contains an unintended control character')
    (project / 'main.tex').write_text(source, encoding='utf-8')
    tokens = set(re.findall(r'\\([A-Za-z]+)', source)) | set(re.findall(r'\\begin\{([A-Za-z]+)\}', source))
    # These public commands execute through the actual running header; the
    # labels in the resulting PDF prove that the header was really drawn.
    indirect = {'assets/topicrail.tex': ['STdrawrail', 'STgetname']} if family == 'topicrail' else {}
    usage = {by_name[name].path: [symbol for symbol in by_name[name].public_symbols
                                if symbol in tokens or symbol in indirect.get(by_name[name].path, ())]
             for name in assets}
    configured = [hook.name for hook in HOOK_SPECS if hook.name in tokens]
    settings = {'CONTENT_PROFILE': 'generic', 'EXPECTED_PAPER': 'a4'}
    if family in ('academic', 'reference-all'):
        settings.update(PDF_CAPTION_COLOR='000000', PDF_CAPTION_LABEL_WEIGHT='normal')
    expected = {'required_tokens': [], 'uri_links': [], 'minimum_pages': 1}
    if family == 'source-links':
        expected['uri_links'] = ['https://example.org/control?first=1&second=2#part', 'https://example.org/local']
    elif family == 'deferred-notes':
        expected.update(required_tokens=['NOTENATIVE', 'NOTEREUSE'], minimum_pages=2,
                        named_destinations=['hllnote.native', 'hllnote.minority'])
    elif family == 'flow-tables':
        expected.update(required_tokens=['FLOWEND'], minimum_pages=2, numeric_row_ids=[f'{i:03d}' for i in range(1,49)])
    elif family == 'reference-all':
        expected['required_tokens'] = ['WIDETOPIC', 'ENTRYBODY', 'NATIVEBLOCK', 'MINORITYBLOCK',
                                       'WARNINGBLOCK', 'QAQUESTION', 'QASOLUTION', 'USEFIELD',
                                       'CONDITIONSFIELD', 'SERIESQUESTION', 'SERIESPARTONE',
                                       'SERIESPARTTWO', 'REFERENCEEND', 'REFERENCEHEADER']
    metadata = {'family': family, 'language': language, 'main_language': language,
            'architecture_assets': [by_name[name].path for name in assets],
            'public_usage': usage, 'indirect_public_usage': indirect,
            'configuration_hooks': configured, 'expected_pdf': expected,
            'build_settings': settings}
    errors = validate_fixture_source(metadata, source)
    if errors:
        raise ValueError('; '.join(errors))
    return metadata
