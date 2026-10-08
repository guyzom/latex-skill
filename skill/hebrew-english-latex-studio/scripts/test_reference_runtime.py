#!/usr/bin/env python3
"""Actual-engine reference layout, language, mathematics and boundary controls.

Coordinates and named destinations are measured from fresh LuaLaTeX PDFs; text
extraction order is never substituted for physical column reading order. An
optional NEW HLLPDF_REFERENCE_EVIDENCE_DIR outside the skill retains the source,
engine logs, measured geometry and PDFs. These tests do not claim visual review.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import contextlib
import hashlib
import io
import json
import math
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
import heading_source
import render_review
from font_paths import font_dir
from new_document import create
from pdf_folios import declared_labels, footer_candidates
from test_academic_runtime import label_fields
from test_references_runtime import reference_string
from test_v4310_runtime import physical_text

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ('preamble.tex', 'reference_columns.tex', 'reference_components.tex',
          'reference_shell.tex', 'reference_theme.tex')
PROFILES = (('english', 'english'), ('hebrew', 'hebrew'),
            ('english-with-hebrew', 'english'), ('hebrew-with-english', 'hebrew'),
            ('bilingual', 'english'), ('bilingual', 'hebrew'))
MARGIN = 10/25.4*72
GAP = 5/25.4*72


def marker(token):
    return r'\hypertarget{ref-'+token+r'}{\en{'+token+'}}'


def prose(locale, token):
    text = ('A bounded reference step. '+marker(token)+'.'
            if locale == 'english' else 'צעד עזר מוגדר. '+marker(token)+'.')
    return text+'\n'


def header(profile='english', main='english', *, options='10pt,a4paper', extra='',
           layers=ASSETS[1:], body_font_size='9', body_baseline='11'):
    return (fr'\def\lakitlanguageprofile{{{profile}}}\def\lakitmainlanguage{{{main}}}'+'\n'
        +fr'\def\lakitdocumentclass{{article}}\def\lakitclassoptions{{{options}}}'+'\n'
        +r'\def\lakitgeometryoptions{left=10mm,right=10mm,top=17mm,bottom=30mm,headheight=10pt,headsep=3mm,footskip=6mm}'+'\n'
        +r'\def\ReferenceColumnCount{2}\def\ReferenceColumnGap{5mm}'+'\n'
        +fr'\def\ReferenceBodyFontSize{{{body_font_size}}}\def\ReferenceBodyBaseline{{{body_baseline}}}'+'\n'
        +extra+'\n'+r'\input{preamble.tex}'+'\n'
        +''.join(r'\input{'+asset+'}\n' for asset in layers)
        +r'\hypersetup{pdftitle={Reference layout controls},pdfauthor={Synthetic QA}}'+'\n')


def fixture(profile, main):
    other = 'hebrew' if main == 'english' else 'english'
    heading = 'Reference topics' if main == 'english' else 'נושאי עזר'
    title = 'Reference layout controls' if main == 'english' else 'בדיקת עימוד דף עזר'
    short = 'Reference QA' if main == 'english' else 'בדיקת עזר'
    size, leading = ('9', '11') if profile in ('english-with-hebrew','hebrew-with-english') else ('7.2', '8.6')
    result = header(profile, main, body_font_size=size, body_baseline=leading)+fr'\renewcommand{{\ReferenceTitle}}{{{title}}}'+'\n'
    result += fr'\renewcommand{{\ReferenceShortTitle}}{{{short}}}'+'\n'
    result += r'\begin{document}\makereferencetitle'+'\n'
    for count in (2, 3):
        if count == 3:
            result += r'\clearpage'+'\n'
        result += fr'\begin{{referencecolumns}}[{count}]'+'\n'
        for index in range(count):
            token = f'C{count}{chr(65+index)}'
            result += fr'\section{{{heading}}}\label{{sec:{token}}}'+'\n'
            result += prose(main, token)
            # Both entry and final output contain actual minority language
            # switches. Physical assembly must retain the page's main direction.
            result += fr'\begin{{{other}prose}}'+'\n'+prose(other, token+'MIN')
            result += fr'\end{{{other}prose}}'+'\n'
            if index == 0:
                if count == 2:
                    result += r'\noeqref{eq:central}\begin{equation}\label{eq:central}\mathrm{CENTRAL}=1\end{equation}'+'\n'
                    result += r'\begin{equation}\label{eq:unused}\mathrm{UNUSED}=0\end{equation}'+'\n'
                    result += r'\begin{equation}\label{eq:reused}\mathrm{REUSED}=2\end{equation}'+'\n'
                    result += ('See '+r'\eqref{eq:reused}.' if main == 'english'
                               else 'ראו '+r'\eqref{eq:reused}.')+'\n'
                    result += r'\[\mathrm{UNITMARK}=10\punit{MeV}\]'+'\n'
                    result += r'\[\begin{pmatrix}\mathrm{MATA}&\mathrm{MATB}\\\mathrm{MATC}&\mathrm{MATD}\end{pmatrix}\]'+'\n'
                    result += r'\begin{referenceformula}\referencepurpose{'+prose(main, 'USEFIELD')+r'}\referenceconditions{'+prose(main, 'CONDITIONFIELD')+r'}\end{referenceformula}'+'\n'
                else:
                    result += r'\begin{referenceqa}\referencequestion{'+prose(main, 'QFIELD')+r'}\referencesolution{'+prose(main, 'AFIELD')+r'}\end{referenceqa}'+'\n'
                    result += r'\begin{referencewarning}'+prose(main, 'WARNINGFIELD')+r'\end{referencewarning}'+'\n'
                    result += r'\begin{referencefigure}\begin{qcirc}\begin{quantikz}\lstick{\ket{0}}&\gate{H}&\qw\\\lstick{\ket{1}}&\qw&\qw\end{quantikz}\end{qcirc}'+'\n'
                    result += r'\referencefigcap[Circuit short]{\label{fig:circuit}'+('Two-wire circuit.' if main == 'english' else 'מעגל בעל שני קווים.')+'}\n'
                    result += r'\end{referencefigure}'+'\n'
                result += fr'\begin{{{other}prose}}'+'\n'
                name = 'ISLANDTWO' if count == 2 else 'ISLANDTHREE'
                math_text = r'\text{מקדם}' if other == 'hebrew' else r'\text{\h{מקדם}}'
                result += r'\noeqref{eq:'+name+r'}\begin{equation}\label{eq:'+name+r'}\mathrm{'+name+'}='+str(count+1)+'+'+math_text+r'\end{equation}'+'\n'
                result += fr'\end{{{other}prose}}'+'\n'
            if index == count-1:
                note = 'notebox' if count == 2 else 'referencenote'
                result += r'\begin{'+note+'}'+prose(main, token+'NOTE')+r'\end{'+note+'}'+'\n'
                result += r'\begin{referencetable}\centering\begin{tabular}{ll}\toprule\en{ID}&\en{Value}\\\midrule\en{A}&\en{12}\\\bottomrule\end{tabular}'+'\n'
                result += r'\referencetabcap[Data short]{\label{tbl:c'+str(count)+'}'+('Local-width data.' if main == 'english' else 'נתונים ברוחב הטור.')+r'}\end{referencetable}'+'\n'
                # The last paragraph is deliberately minority prose.
                result += fr'\begin{{{other}prose}}'+prose(other, token+'TAIL')+fr'\end{{{other}prose}}'+'\n'
            if index < count-1:
                result += r'\par\columnbreak'+'\n'
        result += r'\end{referencecolumns}'+'\n'
    result += r'\begin{referencewide}'+'\n'
    result += r'\noeqref{eq:wide}\begin{equation}\label{eq:wide}\text{\en{\makebox[.82\linewidth][s]{WIDELEFT\hfill WIDERIGHT}}}\end{equation}'+'\n'
    result += r'\end{referencewide}\clearpage'+'\n'
    result += r'\vspace*{.60\textheight}\begin{referencecolumns}[3]\begin{referenceqaseries}'+'\n'
    result += r'\referencequestion{'+prose(main, 'SERIESQUESTION')+'}\n'
    for index in range(28):
        token = f'STEP{index:02d}'
        result += r'\begin{referencesolutionpart}[\en{'+token+'TITLE}]\n'
        result += prose(main, token)+r'\par'+'\n'+prose(main, token+'BODY')
        result += r'\[x_{'+str(index)+r'}=x_{'+str(index)+r'}+0\]'+'\n'
        result += r'\end{referencesolutionpart}'+'\n'
    result += r'\end{referenceqaseries}\end{referencecolumns}'+'\n'
    if profile in ('bilingual', 'english-with-hebrew', 'hebrew-with-english'):
        result += r'\clearpage'+fr'\begin{{{other}prose}}'+'\n'
        result += r'\begin{referencecolumns}[2]'+'\n'
        result += fr'\section{{'+('Secondary topics' if other == 'english' else 'נושאים נוספים')+'}\n'
        result += prose(other, 'SECONDARYA')+r'\par\columnbreak'+'\n'+prose(other, 'SECONDARYB')
        result += r'\end{referencecolumns}'+fr'\end{{{other}prose}}'+'\n'
    return result+r'\end{document}'+'\n'


def local_callout_fixture(profile, main):
    """Native bars, minority entry scopes and restoration after an LTR diagram."""
    other = 'hebrew' if main=='english' else 'english'
    locales = [main,main] if profile in ('english','hebrew') else [main,other,main]
    source = header(profile,main)+r'\begin{document}\begin{referencecolumns}[2]'+'\n'
    for index, locale in enumerate(locales):
        # Exercise both a prose island inside an atomic topic and an entire
        # topic inside a prose island; both preserve the page's main columns.
        outside = index==1
        if outside:
            source += fr'\begin{{{locale}prose}}'+'\n'
        source += r'\begin{referenceentry}'+'\n'
        if not outside:
            source += fr'\begin{{{locale}prose}}'+'\n'
        for kind, environment in (('N','referencenote'),('W','referencewarning')):
            token = f'LOCAL{index}{kind}'
            source += fr'\begin{{{environment}}}'+prose(locale,token)
            source += fr'\[\mathrm{{M{index}{kind}L}}=1+2=\mathrm{{M{index}{kind}R}}\]'+'\n'
            if index==0 and kind=='N':
                # The border belongs to the surrounding language at block
                # entry, even when a later body paragraph uses another locale.
                inner = 'hebrew' if locale=='english' else 'english'
                source += fr'\begin{{{inner}prose}}'+prose(inner,'INNERPROSE')
                source += fr'\end{{{inner}prose}}'+'\n'
                source += r'\begin{tikzpic}\begin{tikzpicture}\draw[->](0,0)--(3,0);'
                source += r'\node[below] at(0,0){\en{INNERTICKZERO}};'
                source += r'\node[below] at(3,0){\en{INNERTICKONE}};\end{tikzpicture}\end{tikzpic}'+'\n'
            source += fr'\end{{{environment}}}'+'\n'
        if not outside:
            source += fr'\end{{{locale}prose}}'+'\n'
        source += r'\end{referenceentry}'+'\n'
        if outside:
            source += fr'\end{{{locale}prose}}'+'\n'
        if index==len(locales)-2:
            source += r'\begin{tikzpic}\begin{tikzpicture}\draw[->](0,0)--(3,0);'
            source += r'\node[below] at(0,0){\en{TICKZERO}};'
            source += r'\node[below] at(3,0){\en{TICKONE}};\end{tikzpicture}\end{tikzpic}'+'\n'
    return source+r'\end{referencecolumns}\end{document}'+'\n'


def occurrences(pdf, token):
    return [(index, box) for index, page in enumerate(pdf) for box in page.search_for(token)]


def exact_occurrence(pdf, token):
    # Search tokens with distinct boundaries instead of substring count: STEP00
    # also occurs inside STEP00TITLE/BODY, whose coordinates are separate roles.
    cache = getattr(pdf, '_reference_occurrences', None)
    if cache is None:
        cache = {}
        for index, page in enumerate(pdf):
            for word in page.get_text('words'):
                cache.setdefault(word[4].strip('.:'), []).append((index, fitz.Rect(word[:4])))
        pdf._reference_occurrences = cache
    hits = cache.get(token, [])
    if len(hits) != 1:
        raise AssertionError((token, len(hits), hits))
    return hits[0]


def pdf_content_tokens(data):
    """Read operators without mistaking authored strings for PDF syntax.

    This small lexer only supplies the graphics/text operators below; it does
    not decode text, reconstruct glyphs or make a claim from extraction order.
    Literal strings, hex strings and TJ arrays are opaque operands.
    """
    source = data.decode('latin-1')
    position = 0
    while position < len(source):
        char = source[position]
        if char.isspace() or char == '\x00':
            position += 1
        elif char == '%':
            end = source.find('\n', position)
            position = len(source) if end < 0 else end+1
        elif char == '(':
            depth = 1
            position += 1
            while position < len(source) and depth:
                if source[position] == '\\':
                    position += 2
                else:
                    depth += (source[position] == '(')-(source[position] == ')')
                    position += 1
            if depth:
                raise AssertionError('unclosed PDF text string')
            yield '<string>'
        elif char == '<' and not source.startswith('<<', position):
            end = source.find('>', position+1)
            if end < 0:
                raise AssertionError('unclosed PDF hex string')
            position = end+1
            yield '<string>'
        elif source.startswith(('<<', '>>'), position):
            yield source[position:position+2]
            position += 2
        elif char in '[]':
            yield char
            position += 1
        else:
            end = position+1
            while end < len(source) and not (source[end].isspace()
                    or source[end] in '()<>[]%'):
                end += 1
            yield source[position:end]
            position = end


def assert_math_pdf_transforms(pdf):
    """Measure the effective PDF text basis, including inherited cm and Tz.

    Font size alone cannot expose a vertically squashed page: MuPDF's text
    trace reports its horizontal size. Actual graphics/text matrices therefore
    supply the shape check. This also covers a scale hidden in an outer q/cm.
    """
    records = []
    for page_number, page in enumerate(pdf, 1):
        fonts = {item[4]: item[3].split('+')[-1]
                 for item in page.get_fonts(full=True) if not item[-1]}
        ctm = fitz.Matrix(1, 1)
        text_matrix = fitz.Matrix(1, 1)
        font, font_size, horizontal_scale = None, None, 1.0
        stack, operands, array_depth = [], [], 0
        for token in pdf_content_tokens(page.read_contents()):
            if token == '[':
                array_depth += 1
                continue
            if token == ']':
                array_depth -= 1
                if array_depth < 0:
                    raise AssertionError('unbalanced PDF text array')
                if not array_depth:
                    operands.append('<array>')
                continue
            if array_depth:
                continue
            if token.startswith('/') or token.startswith('<'):
                operands.append(token)
                continue
            try:
                operands.append(float(token))
                continue
            except ValueError:
                pass
            if token == 'q':
                stack.append((fitz.Matrix(ctm), font, font_size, horizontal_scale))
            elif token == 'Q':
                if not stack:
                    raise AssertionError('unbalanced PDF graphics restoration')
                ctm, font, font_size, horizontal_scale = stack.pop()
            elif token == 'cm':
                ctm = fitz.Matrix(*operands[-6:])*ctm
            elif token == 'BT':
                text_matrix = fitz.Matrix(1, 1)
            elif token == 'Tm':
                text_matrix = fitz.Matrix(*operands[-6:])
            elif token == 'Tf':
                font, font_size = operands[-2][1:], operands[-1]
            elif token == 'Tz':
                horizontal_scale = operands[-1]/100
            elif token in ('Tj', 'TJ', "'", '"') and fonts.get(font, '').startswith(
                    ('CM', 'MSAM', 'MSBM')):
                effective = fitz.Matrix(horizontal_scale, 1)*text_matrix*ctm
                x_length = math.hypot(effective.a, effective.b)
                y_length = math.hypot(effective.c, effective.d)
                if min(x_length, y_length) <= 0:
                    raise AssertionError(('degenerate math text transform', page_number, font))
                ratio = x_length/y_length
                dot = (effective.a*effective.c+effective.b*effective.d)/(x_length*y_length)
                determinant = effective.a*effective.d-effective.b*effective.c
                if abs(ratio-1) > 0.00001 or abs(dot) > 0.00001 or determinant <= 0:
                    raise AssertionError(('anisotropic or reflected math text transform',
                        page_number, fonts[font], list(effective), ratio, dot))
                records.append({'page':page_number,'font':fonts[font],
                    'font_size_bp':font_size,'effective_basis_ratio':ratio,
                    'effective_basis_dot':dot})
            operands.clear()
        if stack or array_depth:
            raise AssertionError('unclosed PDF graphics or text array')
    if not records:
        raise AssertionError('no actual mathematics operators were measured')
    return {'math_text_show_operators':len(records),
        'maximum_basis_ratio_error':max(abs(row['effective_basis_ratio']-1) for row in records),
        'maximum_basis_dot':max(abs(row['effective_basis_dot']) for row in records)}


def assert_math_transform_reject_controls(pdf):
    """Distort fresh PDF bytes, including a shape-only change, without engines."""
    results = []
    for name, sx, sy in (('vertical-squash',1,.85),('horizontal-squash',.85,1)):
        with fitz.open(stream=pdf.tobytes(),filetype='pdf') as altered:
            for page in altered:
                page.wrap_contents()
                xref = page.get_contents()[0]
                altered.update_stream(xref,
                    f'q {sx} 0 0 {sy} 0 0 cm\n'.encode()
                    +altered.xref_stream(xref)+b'\nQ\n')
            try:
                assert_math_pdf_transforms(altered)
            except AssertionError as error:
                if 'anisotropic or reflected math text transform' not in str(error):
                    raise
                results.append({'control':name,'actual_pdf_change':True,'rejected':True})
            else:
                raise AssertionError(('distorted PDF control was accepted',name))
    return results


def assert_native_reference_math_typography(pdf, layout):
    """Check actual embedded programs and point sizes on unedited starters."""
    main, script, scriptscript = ((6.25,4.375,3.125)
        if layout == 'reference-compact' else (8.75,6.125,4.375))
    scale = 72/72.27
    traces = [trace for page in pdf for trace in page.get_texttrace()]
    body = 6.3 if layout=='reference-compact' else 9
    body_runs = [trace for trace in traces if abs(trace['size']-body*scale)<.008
                 and not trace['font'].startswith(('CM','MSAM','MSBM'))]
    if sum(len(trace['chars']) for trace in body_runs)<20:
        raise AssertionError(('missing native reference prose size',layout,body))
    at_main = [trace for trace in traces if abs(trace['size']-main*scale)<.008
               and trace['font'].startswith(('CM','MSAM','MSBM'))]
    main_fonts = sorted({trace['font'] for trace in at_main})
    for expected in ('CMR10','CMMI10','CMSY10'):
        if expected not in main_fonts:
            raise AssertionError(('missing reference main optical design',layout,expected,main_fonts))
    wrong = [name for name in main_fonts if re.fullmatch(
        r'(?:CMR|CMMI|CMSY|CMBX|CMMIB|CMBSY)(?!10$)\d+',name)]
    if wrong:
        raise AssertionError(('wrong reference main optical design',layout,wrong))
    programs = {}
    for page in pdf:
        for item in page.get_fonts(full=True):
            name = item[3].split('+')[-1]
            if name not in ('CMR10','CMMI10','CMSY10') or name in programs:
                continue
            embedded_name,extension,kind,data = pdf.extract_font(item[0])
            identity = re.search(rb'%!PS-AdobeFont-1\.0:\s*([^\s]+)',data[:256])
            if extension != 'pfa' or kind != 'Type1' or not identity or identity[1].decode()!=name:
                raise AssertionError(('reference math embedded program differs',name,extension,kind))
            matrix = re.search(rb'/FontMatrix\s*\[([^\]]+)\]',data)
            natural = [float(value) for value in matrix[1].split()] if matrix else []
            if natural != [.001,0,0,.001,0,0]:
                raise AssertionError(('math outline FontMatrix changed its natural shape',name,natural))
            program = {'font':name,'embedded_font_sha256':hashlib.sha256(data).hexdigest(),
                       'actual_program_identity':identity[1].decode(),
                       'actual_outline_font_matrix':natural}
            if name == 'CMMI10':
                advance = fitz.Font(fontbuffer=data).glyph_advance(ord('x'))
                if not .55 < advance < .59:
                    raise AssertionError(('main x glyph lacks the native CM10 proportion',advance))
                program['natural_x_advance_em'] = advance
            programs[name] = program
    if set(programs) != {'CMR10','CMMI10','CMSY10'}:
        raise AssertionError(('missing embedded main math programs',programs.keys()))
    return {'declared_prose_size_tex_pt':body,'actual_prose_text_runs':len(body_runs),
        'actual_prose_fonts':sorted({trace['font'] for trace in body_runs}),
        'declared_math_sizes_tex_pt':[main,script,scriptscript],
        'actual_main_math_fonts':main_fonts,'main_math_text_runs':len(at_main),
        'embedded_main_programs':[programs[name] for name in sorted(programs)],
        'actual_pdf_shape':assert_math_pdf_transforms(pdf)}


TYPOGRAPHY_SCOPE_ROLES = (
    ('OUTBEFORE',('NORMAL','BOLD')),
    ('COLUMNS',('NORMAL','BOLD')),
    ('OUTMIDDLE',('NORMAL','BOLD')),
    ('WIDE',('NORMAL','BOLD')),
    ('INHERITEDCOLUMN',('BOLD',)),
    ('OUTINHERITEDCOLUMN',('NORMAL',)),
    ('INHERITEDWIDE',('BOLD',)),
    ('OUTINHERITEDWIDE',('NORMAL',)),
    ('CUSTOMBEFORE',('NORMAL',)),
    ('CUSTOMCOLUMN',('NORMAL',)),
    ('CUSTOMWIDE',('NORMAL',)),
    ('CUSTOMAFTER',('NORMAL',)),
    ('OUTAFTER',('NORMAL','BOLD')),
)


def typography_scope_fixture(main, layout):
    """Authored outer sizing makes any leaked reference version measurable."""
    body, leading, math_size, script, scriptscript = (
        ('6.3','8.2','6.25','4.375','3.125') if layout=='reference-compact'
        else ('9','11','8.75','6.125','4.375'))
    extra = (fr'\def\ReferenceMathFontSize{{{math_size}}}'+'\n'
        +fr'\def\ReferenceMathScriptSize{{{script}}}'+'\n'
        +fr'\def\ReferenceMathScriptScriptSize{{{scriptscript}}}'+'\n')
    source = header(main,main,extra=extra,body_font_size=body,body_baseline=leading)
    # This independent outer contract is installed after the reference asset.
    # Matching text size is deliberate: a global S@ declaration would replace
    # ten-point mathematics here and pass an ordinary ten-point-only check.
    source += fr'\DeclareMathSizes{{{body}}}{{10}}{{7}}{{5}}'+'\n'
    source += r'\DeclareMathVersion{refcustom}'+'\n'
    source += r'\begin{document}\ReferenceSelectBodyFont'+'\n'
    expression = (r'x_{y_z}+\mathrm{Abc}+\mathbf{DEF}+\mathsf{Gh}'
                  r'+\mathit{IJ}+\mathtt{KL}+\mathcal{MN}+\mathbb{PQ}')
    nested = (r'x_{y_z}+\frac{\alpha_{\beta_\gamma}}{\sqrt[\delta_\epsilon]{u_v}}'
              r'+\mathrm{Abc}+\mathbf{D_{E_F}}+\mathsf{G_{H_I}}'
              r'+\mathit{J_{K_L}}+\mathtt{M_{N_O}}+\mathcal{P_{Q_R}}+\mathbb{S_{T_U}}')
    columns = (r'\begin{referencecolumns}[2]\begin{referenceentry}',
               r'\end{referenceentry}\end{referencecolumns}')
    wide = (r'\begin{referencewide}',r'\end{referencewide}')
    environments = {'COLUMNS':columns,'WIDE':wide,
        'INHERITEDCOLUMN':(r'{\boldmath'+columns[0],columns[1]+'}'),
        'INHERITEDWIDE':(r'{\boldmath'+wide[0],wide[1]+'}'),
        'CUSTOMBEFORE':(r'{\mathversion{refcustom}',''),
        'CUSTOMCOLUMN':columns,'CUSTOMWIDE':wide,'CUSTOMAFTER':('','}')}
    for phase, styles in TYPOGRAPHY_SCOPE_ROLES:
        opening,closing = environments.get(phase,('',''))
        source += opening+'\n'
        for style in styles:
            token = phase+style
            source += r'\noindent\begin{minipage}{\linewidth}'+marker(token)+r'\par'+'\n'
            source += r'{'+(r'\boldmath' if style=='BOLD'
                            and not phase.startswith('INHERITED') else '')+'\n'
            row_expression = nested if phase in ('COLUMNS','WIDE','INHERITEDCOLUMN','INHERITEDWIDE') else expression
            source += r'\['+row_expression+r'\]\par}'+marker(token+'END')+'\n'
            source += r'\end{minipage}\par'+'\n'
        source += closing+'\n'
    source += marker('ENDPROBE')+r'\par\end{document}'+'\n'
    return source


def typography_row_region(pdf, token):
    """The actual paired labels belong to one unbreakable authored row."""
    page_number,start = exact_occurrence(pdf,token)
    end_page,end = exact_occurrence(pdf,token+'END')
    if end_page!=page_number or end.y0<=start.y1:
        raise AssertionError(('typography row container split or reordered',token,page_number,start,end_page,end))
    page = pdf[page_number]
    left,right = MARGIN,page.rect.width-MARGIN
    if token.startswith(('COLUMNS','INHERITEDCOLUMN','CUSTOMCOLUMN')):
        physical = column_index(page,start,2,'english')
        if column_index(page,end,2,'english')!=physical:
            raise AssertionError(('typography row labels cross columns',token,start,end))
        width = (page.rect.width-2*MARGIN-GAP)/2
        left = MARGIN+physical*(width+GAP)
        right = left+width
    return page_number,fitz.Rect(left-.5,start.y1-.5,right+.5,end.y0+.5),start,end


def assert_typography_scope_rows(pdf, layout):
    """Observe all three tiers, alphabets and restoration in the actual PDF."""
    point_sizes = ((6.25,4.375,3.125) if layout=='reference-compact'
                   else (8.75,6.125,4.375))
    tokens = [phase+style for phase,styles in TYPOGRAPHY_SCOPE_ROLES
              for style in styles]+['ENDPROBE']
    exact_occurrence(pdf,'ENDPROBE')
    rows = []
    for token in tokens[:-1]:
        page_number,region,start,end = typography_row_region(pdf,token)
        # Paired labels in an actual row box associate its own glyphs even
        # when the next authored row lies in another column or on another page.
        traces = [trace for trace in pdf[page_number].get_texttrace()
            if region.contains(fitz.Rect(trace['bbox']))
            and trace['font'].startswith(('CM','MSAM','MSBM'))]
        if not traces:
            raise AssertionError(('no math in the authored scope row',token))
        local = token.startswith(('COLUMNS','WIDE','INHERITED','CUSTOMCOLUMN','CUSTOMWIDE'))
        custom = token.startswith('CUSTOM')
        sizes = point_sizes if local and not custom else (10,7,5)
        bold = token.endswith('BOLD')
        letter_fonts = ('CMMIB10','CMMIB7','CMMIB5') if bold else ('CMMI10','CMMI7','CMMI5')
        actual_tiers = []
        for expected_size,expected_font in zip(sizes,letter_fonts):
            found = [trace for trace in traces if trace['font']==expected_font
                     and abs(trace['size']-expected_size*72/72.27)<.008]
            if not found:
                raise AssertionError(('reference tier or restored outer math differs',
                    token,expected_font,expected_size,
                    sorted({(trace['font'],round(trace['size'],5)) for trace in traces})))
            actual_tiers.append({'font':expected_font,
                'actual_sizes_bp':sorted({trace['size'] for trace in found}),
                'actual_glyph_count':sum(len(trace['chars']) for trace in found)})
        at_main = {trace['font'] for trace in traces
                   if abs(trace['size']-sizes[0]*72/72.27)<.008}
        expected = ({'CMBX10','CMSSBX10','CMBXTI10','CMTT10','CMBSY10'}
                    if bold else {'CMR10','CMBX10','CMSS10','CMTI10','CMTT10','CMSY10'})
        if not expected<=at_main or not any(font.startswith('MSBM') for font in at_main):
            raise AssertionError(('reference alphabets or bold math differ',token,expected,at_main))
        nested_alphabets = []
        if local and not custom:
            families = {'bf':('CMBX10','CMBX7','CMBX5'),
                'sf':(('CMSSBX10',)*3 if bold else ('CMSS10',)*3),
                'it':(('CMBXTI10',)*3 if bold else ('CMTI10',)*3),
                'tt':('CMTT10',)*3,
                'cal':(('CMBSY10','CMBSY7','CMBSY5') if bold else ('CMSY10','CMSY7','CMSY5')),
                'bb':('MSBM10','MSBM7','MSBM5')}
            for alphabet,fonts in families.items():
                measured = []
                for size,font in zip(sizes,fonts):
                    hits = [trace for trace in traces if trace['font']==font
                            and abs(trace['size']-size*72/72.27)<.008]
                    if not hits:
                        raise AssertionError(('nested reference math alphabet differs',token,alphabet,font,size))
                    measured.append({'font':font,'actual_sizes_bp':sorted({trace['size'] for trace in hits}),
                        'actual_glyph_count':sum(len(trace['chars']) for trace in hits)})
                nested_alphabets.append({'alphabet':alphabet,'actual_tiers':measured})
        rows.append({'scope':token,'actual_page':page_number+1,
            'expected_math_sizes_tex_pt':list(sizes),'actual_main_fonts':sorted(at_main),
            'actual_measured_tiers':actual_tiers,
            'actual_row_region':list(region),'actual_paired_marker_boxes':[list(start),list(end)],
            'actual_nested_alphabets':nested_alphabets,
            'actual_math_runs':len(traces),'reference_scope':local,
            'preserved_authored_custom_version':custom,
            'inherited_bold_at_entry':token.startswith('INHERITED')})
    return rows


def assert_typography_scope_leak_control(pdf, layout):
    """Change one restored OUTAFTER math size in actual PDF bytes and reject."""
    page_number,region,_,_ = typography_row_region(pdf,'OUTAFTERNORMAL')
    page = pdf[page_number]
    candidates = [trace for trace in page.get_texttrace()
        if region.contains(fitz.Rect(trace['bbox']))
        and trace['font']=='CMMI10' and abs(trace['size']-10*72/72.27)<.008]
    if not candidates:
        raise AssertionError('scope-leak control lacks restored normal math')
    # Change just the first main-font selection after this marker's PDF Y.
    # Locate its actual origin, rather than replacing every same-size Tf.
    origin = candidates[0]['chars'][0][2]
    pdf_y = page.rect.height-origin[1]
    font_resource = next(item[4] for item in page.get_fonts(full=True)
                         if item[3].split('+')[-1]=='CMMI10' and not item[-1])
    content = page.read_contents()
    operators = re.compile(rb'/'+font_resource.encode()+
        rb'\s+9\.96264\s+Tf(?:(?!\bTf\b).)*?1 0 0 1 '
        rb'(?P<x>[\d.-]+) (?P<y>[\d.-]+) Tm',re.S)
    # PDF numbers have no required trailing zeros: 655.81 and 655.810
    # denote the same measured coordinate. Keep the actual glyph origin
    # association while comparing its numeric X/Y values.
    matches = [match for match in operators.finditer(content)
               if abs(float(match['x'])-origin[0])<.001
               and abs(float(match['y'])-pdf_y)<.001]
    if len(matches)!=1:
        raise AssertionError(('scope-leak control cannot locate exact restored operator',pdf_y,font_resource))
    match = matches[0]
    leaked_size = (6.25 if layout=='reference-compact' else 8.75)*72/72.27
    altered_content = content[:match.start()]+re.sub(rb'9\.96264(?=\s+Tf)',
        f'{leaked_size:.5f}'.encode(),match[0],count=1)+content[match.end():]
    with fitz.open(stream=pdf.tobytes(),filetype='pdf') as altered:
        altered_page = altered[page_number]
        first = altered_page.get_contents()[0]
        altered.update_stream(first,altered_content)
        for extra in altered_page.get_contents()[1:]:
            altered.update_stream(extra,b'')
        try:
            assert_typography_scope_rows(altered,layout)
        except AssertionError as error:
            if 'reference tier or restored outer math differs' not in str(error):
                raise
        else:
            raise AssertionError('actual PDF outside-scope leak control was accepted')
    return {'control':'restored-outer-main-size-leak','actual_pdf_change':True,'rejected':True}


def column_index(page, rect, count, main, margin=MARGIN, gap=GAP):
    width = (page.rect.width-2*margin-(count-1)*gap)/count
    physical = int(((rect.x0+rect.x1)/2-margin)/(width+gap))
    if not 0 <= physical < count:
        raise AssertionError(('outside columns', rect, physical))
    return count-1-physical if main == 'hebrew' else physical


def declared_reference_geometry(source):
    """Resolve the generated document's explicit dimensions in PDF points."""
    geometry = re.search(r'\\def\\lakitgeometryoptions\{([^{}]+)\}', source)
    if not geometry:
        raise AssertionError('reference fixture must declare its geometry')
    result = {}
    scales = {'mm':72/25.4, 'cm':72/2.54, 'in':72, 'pt':72/72.27, 'bp':1}
    for key, value in re.findall(r'(left|right|top|bottom|footskip)=([^,]+)', geometry.group(1)):
        dimension = re.fullmatch(r'([0-9]+(?:\.[0-9]+)?)(mm|cm|in|pt|bp)', value.strip())
        if not dimension:
            raise AssertionError(('unresolved reference geometry dimension', key, value))
        result[key] = float(dimension.group(1))*scales[dimension.group(2)]
    if set(result) != {'left','right','top','bottom','footskip'} or result['left']!=result['right']:
        raise AssertionError(('incomplete/asymmetric reference control geometry', result))
    gap = re.search(r'\\def\\ReferenceColumnGap\{([0-9]+(?:\.[0-9]+)?)(mm|cm|in|pt|bp)\}', source)
    result['gap'] = float(gap.group(1))*scales[gap.group(2)] if gap else GAP
    return result


def assert_reference_footer_clearance(pdf, source):
    """Measure actual folio placement and separation; no fixed body-band guess."""
    geometry = declared_reference_geometry(source)
    if declared_labels(pdf) != [str(i+1) for i in range(len(pdf))]:
        raise AssertionError('reference PDF page labels differ')
    measurements = []
    for index,page in enumerate(pdf):
        expected_y = page.rect.height-geometry['bottom']+geometry['footskip']
        words = page.get_text('words')
        folios = [word for word in words if word[4]==str(index+1)
                  and abs((word[0]+word[2])/2-page.rect.width/2)<5
                  and abs(word[3]-expected_y)<12]
        if len(folios)!=1:
            raise AssertionError(('one centered folio near the declared footer required', index+1,folios,expected_y))
        folio = fitz.Rect(folios[0][:4])
        body = [fitz.Rect(word[:4]) for word in words if word!=folios[0]
                and (word[1]+word[3])/2>=geometry['top']]
        body.extend(drawing['rect'] for drawing in page.get_drawings()
            if drawing['rect'].y0>=geometry['top']
            and geometry['left']-1<=drawing['rect'].x0
            and drawing['rect'].x1<=page.rect.width-geometry['right']+1)
        body_bottom = max((box.y1 for box in body), default=geometry['top'])
        clearance = folio.y0-body_bottom
        if clearance < 3:
            raise AssertionError(('body ink touches the folio', index+1,clearance,folio,body_bottom))
        sizes = [span['size'] for block in page.get_text('dict')['blocks']
                 for line in block.get('lines',[]) for span in line['spans']
                 if span['text']==str(index+1) and fitz.Rect(span['bbox']).intersects(folio)]
        if len(sizes)!=1 or abs(sizes[0]-8*72/72.27)>.05:
            raise AssertionError(('reference folio size differs',index+1,sizes))
        measurements.append({'page':index+1,'folio':list(folio),
            'body_bottom':body_bottom,'clearance':clearance,'size':sizes[0]})
    return measurements


def baseline(page, rect):
    values = [char['origin'][1] for block in page.get_text('rawdict')['blocks']
              for line in block.get('lines', []) for span in line['spans']
              for char in span['chars'] if char['c'].strip()
              and rect.x0-.1 <= char['origin'][0] <= rect.x1+.1
              and rect.y0 <= char['origin'][1] <= rect.y1]
    if not values:
        raise AssertionError(('missing baseline', rect))
    return sorted(values)[len(values)//2]


def assert_step_title_reading_order(page, title, body, main):
    """An inline title precedes its prose, or the prose follows on a new line."""
    if (title & body).get_area()>.1:
        raise AssertionError(('step title overlaps its prose',title,body))
    offset = baseline(page,body)-baseline(page,title)
    if offset<-.5:
        raise AssertionError(('step prose precedes its title vertically',title,body,offset))
    if abs(offset)<=1:
        before = title.x0>body.x1+.5 if main=='hebrew' else title.x1<body.x0-.5
        if not before:
            raise AssertionError(('inline step title does not precede prose in paragraph reading order',main,title,body))
    elif offset<7:
        raise AssertionError(('wrapped step prose crowds its title line',title,body,offset))
    return {'title_baseline':baseline(page,title),'prose_baseline':baseline(page,body),
            'shared_baseline':abs(offset)<=1,'locale':main}


def assert_same_atomic_step_background(page, title, body, second):
    box = title | body | second
    frames = [drawing['rect'] for drawing in page.get_drawings() if drawing.get('fill')
        and drawing['rect'].width>60 and drawing['rect'].height>20
        and fitz.Rect(drawing['rect'].x0-2,drawing['rect'].y0-2,
                      drawing['rect'].x1+2,drawing['rect'].y1+2).contains(box)]
    if len(frames)!=1:
        raise AssertionError(('step title and prose do not share one atomic background',title,body,second,frames))
    return frames[0]


def reference_frame_rectangles(page):
    """Infer actual vector frame bounds, independently of TeX style settings."""
    vertical, horizontal = [], []
    for drawing in page.get_drawings():
        color = drawing.get('color')
        if (drawing['type'] not in ('s','fs') or not .35 <= (drawing.get('width') or 0) <= .85
                or not color or max(color)-min(color)>.01 or max(color)>.5):
            continue
        for item in drawing['items']:
            if item[0]!='l':
                continue
            a,b = item[1:]
            rect = fitz.Rect(min(a.x,b.x),min(a.y,b.y),max(a.x,b.x),max(a.y,b.y))
            segment = {'rect':rect,'width':drawing['width'],'color':color}
            if abs(a.x-b.x)<.001 and rect.height>12:
                vertical.append(segment)
            elif abs(a.y-b.y)<.001 and rect.width>100:
                horizontal.append(segment)
    frames = []
    for index, a in enumerate(vertical):
        for b in vertical[index+1:]:
            ra, rb = a['rect'], b['rect']
            if (abs(ra.y0-rb.y0) < .002 and abs(ra.y1-rb.y1) < .002
                    and abs(ra.x0-rb.x0) > 100 and abs(a['width']-b['width']) < .002
                    and a['color']==b['color']):
                left, right = sorted((ra.x0, rb.x0))
                lines = [line['rect'] for line in horizontal
                    if line['color']==a['color'] and abs(line['width']-a['width'])<.002
                    and abs(line['rect'].x0-left)<5 and abs(line['rect'].x1-right)<5]
                tops = [line.y0 for line in lines if abs(line.y0-ra.y0)<5]
                bottoms = [line.y0 for line in lines if abs(line.y0-ra.y1)<5]
                if len(tops)!=1 or len(bottoms)!=1:
                    continue
                bounds = fitz.Rect(left,tops[0],right,bottoms[0])
                fills = [drawing for drawing in page.get_drawings() if drawing.get('fill')
                    and drawing['rect'].width>=bounds.width-2
                    and drawing['rect'].height>=bounds.height-2
                    and abs(drawing['rect'].x0-bounds.x0)<2
                    and abs(drawing['rect'].y0-bounds.y0)<2
                    and abs(drawing['rect'].x1-bounds.x1)<2
                    and abs(drawing['rect'].y1-bounds.y1)<2]
                rounded = any(any(item[0]=='c' for item in drawing['items'])
                    and drawing.get('color')==a['color']
                    and fitz.Rect(bounds.x0-2,bounds.y0-2,bounds.x1+2,bounds.y1+2).contains(drawing['rect'])
                    for drawing in page.get_drawings())
                frames.append(dict(left=left, right=right,
                    top=tops[0], bottom=bottoms[0],
                    vertical_start=ra.y0, vertical_end=ra.y1,
                    background_gray=min(fills[0]['fill']) if len(fills)==1 else None,
                    rounded=rounded))
    return frames


def frame_edge_coverage(pixmap, frame, dpi):
    """Sample every border away from corners; pale fills do not count as ink."""
    data = memoryview(pixmap.samples)
    channels = pixmap.n-bool(pixmap.alpha)
    scale = dpi/72
    def gray(x, y):
        offset = y*pixmap.stride+x*pixmap.n
        return min(data[offset:offset+channels])
    result = {}
    for side in ('left','right','top','bottom'):
        vertical = side in ('left','right')
        axis = frame[side]*scale
        if vertical:
            start = math.ceil((frame['vertical_start']+4)*scale)
            end = math.floor((frame['vertical_end']-4)*scale)
        else:
            start = math.ceil((frame['left']+4)*scale)
            end = math.floor((frame['right']-4)*scale)
        low = max(0, math.floor(axis-2))
        high = min(pixmap.width if vertical else pixmap.height, math.ceil(axis+2)+1)
        visible = longest = missing = 0
        for position in range(start, end):
            present = min(gray(k,position) if vertical else gray(position,k)
                          for k in range(low,high)) < 220
            visible += present
            missing = 0 if present else missing+1
            longest = max(longest, missing)
        if end <= start:
            raise AssertionError('expected a measurable frame edge')
        result[side] = dict(samples=end-start, visible_samples=visible,
            coverage_fraction=visible/(end-start), longest_missing_px=longest)
    return result


def measured_frame_edges(pdf_path, review_directory, dpi, page_numbers=None):
    edges = []
    with fitz.open(pdf_path) as pdf:
        for page in pdf:
            if page_numbers is not None and page.number+1 not in page_numbers:
                continue
            pixmap = fitz.Pixmap(str(review_directory/f'page-{page.number+1}.png'))
            frames = reference_frame_rectangles(page)
            edges.extend({'page':page.number+1,'frame':index+1,'bounds':frame,
                          'side':side,**measurement}
                for index, frame in enumerate(frames)
                for side, measurement in frame_edge_coverage(pixmap, frame, dpi).items())
    return edges


def assert_visible_frame_edges(edges):
    missing = [edge for edge in edges if edge['coverage_fraction'] < .98]
    if not edges or missing:
        raise AssertionError(('rendered reference frame borders are incomplete', missing))


def gray_frame_background_bands(pixmap, frame, dpi):
    """Sample actual title/body interior strips, excluding the rounded corners."""
    scale = dpi/72
    pixels = memoryview(pixmap.samples)
    channels = pixmap.n-bool(pixmap.alpha)
    result = []
    for y in (frame['top']+3,(frame['top']+frame['bottom'])/2,frame['bottom']-3):
        values = []
        for x in range(math.ceil((frame['left']+6)*scale),math.floor((frame['right']-6)*scale),max(1,round(4*scale))):
            offset = round(y*scale)*pixmap.stride+x*pixmap.n
            values.append(min(pixels[offset:offset+channels]))
        background = max(values)
        if not 235<=background<=250:
            raise AssertionError(('Q/A title/body background is not continuous pale gray',y,background,frame))
        result.append({'pdf_y':y,'maximum_gray':background})
    if max(row['maximum_gray'] for row in result)-min(row['maximum_gray'] for row in result)>3:
        raise AssertionError(('Q/A title/body gray strips differ',result))
    return result


def authored_callout_languages(source):
    """Read a callout's enclosing prose locale, independently of page direction."""
    declared = re.search(r'\\def\\lakitmainlanguage\{(english|hebrew)\}', source)
    if not declared:
        raise AssertionError('callout fixture must declare its main language')
    main = declared.group(1)
    clean = heading_source.clean_source(source)
    languages, active, result = [], [], []
    tokens = r'\\(begin|end)\s*\{(englishprose|hebrewprose|referencenote|referencewarning)\}'
    for token in re.finditer(tokens, clean):
        boundary, environment = token.groups()
        if environment.endswith('prose'):
            locale = environment[:-5]
            if boundary == 'begin':
                languages.append(locale)
            elif not languages or languages.pop() != locale:
                raise AssertionError('callout source has an unbalanced prose-language scope')
            continue
        if boundary == 'begin':
            active.append({'environment':environment,
                           'language':languages[-1] if languages else main,
                           'body_start':token.end()})
        else:
            if not active or active[-1]['environment'] != environment:
                raise AssertionError('callout source has an unbalanced note/warning scope')
            callout = active.pop()
            body = clean[callout.pop('body_start'):token.start()]
            callout['markers'] = re.findall(r'\\hypertarget\{ref-([^{}]+)\}', body)
            result.append(callout)
    if languages or active:
        raise AssertionError('callout source has an unclosed language or note/warning scope')
    return main, result


def assert_language_leading_callout_bars(pdf, source):
    """Measure one open bar on each callout's actual local-language reading edge."""
    main, authored = authored_callout_languages(source)
    geometry = declared_reference_geometry(source)
    count = re.search(r'\\def\\ReferenceColumnCount\{([23])\}',source)
    columns = int(count.group(1)) if count else 2
    notes = []
    for page in pdf:
        closed = reference_frame_rectangles(page)
        drawings = page.get_drawings()
        for fill in drawings:
            color, box = fill.get('fill'), fill['rect']
            if (not color or max(color)-min(color)>.01 or not .93<min(color)<.97
                    or box.width<100 or box.height<12):
                continue
            if any(fitz.Rect(frame['left']-2,frame['top']-2,
                    frame['right']+2,frame['bottom']+2).contains(box) for frame in closed):
                continue
            sides = [drawing for drawing in drawings if drawing.get('color')==(0,0,0)
                and .5<(drawing.get('width') or 0)<.7
                and drawing['rect'].width<.01
                and abs(drawing['rect'].y0-box.y0)<2
                and abs(drawing['rect'].y1-box.y1)<2
                and box.x0-2<=drawing['rect'].x0<=box.x1+2]
            if len(sides)!=1:
                raise AssertionError(('note/warning requires exactly one vertical bar',
                    page.number+1,box,[list(side['rect']) for side in sides]))
            extra = [drawing for drawing in drawings if drawing.get('color')
                and (drawing.get('width') or 0)>.3
                and drawing['rect'].width>box.width-3
                and min(drawing['rect'].x1,box.x1)-max(drawing['rect'].x0,box.x0)>box.width-3
                and (abs(drawing['rect'].y0-box.y0)<2
                     or abs(drawing['rect'].y0-box.y1)<2)]
            if extra:
                raise AssertionError(('open note/warning has a horizontal enclosing edge',box,extra))
            words = [fitz.Rect(word[:4]) for word in page.get_text('words')
                     if box.contains(fitz.Point((word[0]+word[2])/2,(word[1]+word[3])/2))]
            if not words or not page.rect.contains(box):
                raise AssertionError(('note/warning has no contained prose or is outside the page',box))
            text = fitz.Rect(words[0])
            for word in words[1:]:
                text |= word
            if not fitz.Rect(box.x0-1,box.y0-2,box.x1+1,box.y1+2).contains(text):
                raise AssertionError(('note/warning text exceeds its background',box,text))
            notes.append({'page':page.number+1,'background':list(box),
                          'bar':list(sides[0]['rect']),'text_bounds':list(text),
                          'column':column_index(page,box,columns,main,
                                               margin=geometry['left'],gap=geometry['gap'])})
    notes.sort(key=lambda row:(row['page'],row['column'],row['background'][1]))
    if len(notes)!=len(authored):
        raise AssertionError(('authored and painted open callout populations differ',
                              len(authored),len(notes)))
    remaining = list(notes)
    for callout in authored:
        if callout['markers']:
            hits = [exact_occurrence(pdf, token) for token in callout['markers']]
            matching = [note for note in remaining if all(page+1==note['page']
                and fitz.Rect(note['background']).contains(fitz.Point(
                    (box.x0+box.x1)/2,(box.y0+box.y1)/2)) for page,box in hits)]
            if len(matching)!=1:
                raise AssertionError(('callout markers must belong to their own single background',
                                      callout,hits,matching))
            note = matching[0]
        else:
            note = remaining[0]
        remaining.remove(note)
        side = 'right' if callout['language']=='hebrew' else 'left'
        expected_x = note['background'][2 if side=='right' else 0]
        if abs(note['bar'][0]-expected_x)>2:
            raise AssertionError(('note/warning bar is on the wrong local-language reading edge',
                                  callout['language'],side,note))
        note.update(environment=callout['environment'],language=callout['language'],
                    expected_side=side,markers=callout['markers'])
    return notes


def assert_reference_callout_geometry(pdf, source):
    """Default sheets use two formulas, two closed Q/As and one locale-leading note."""
    profile = re.search(r'\\def\\lakitlanguageprofile\{([^{}]+)\}',source)
    bodies = 2 if profile and profile.group(1)=='bilingual' else 1
    formulas, questions = [],[]
    for page in pdf:
        for frame in reference_frame_rectangles(page):
            frame = {'page':page.number+1,**frame}
            gray = frame['background_gray']
            if gray is None:
                raise AssertionError(('closed callout has no single continuous background',frame))
            if gray>.99:
                if frame['rounded']:
                    raise AssertionError(('central formula must have a square plain frame',frame))
                formulas.append(frame)
            elif .93<gray<.97:
                if frame['rounded']:
                    raise AssertionError(('Q/A must use the proven square closed frame',frame))
                questions.append(frame)
            else:
                raise AssertionError(('unexpected closed callout background',frame))
    notes = assert_language_leading_callout_bars(pdf, source)
    if (len(formulas),len(questions),len(notes))!=(2*bodies,2*bodies,bodies):
        raise AssertionError(('default callout population differs',len(formulas),len(questions),len(notes),bodies))
    return {'central_formulas':formulas,'square_question_answers':questions,
            'language_leading_bar_notes':notes}


def authored_heading_numbers(source, main=None):
    """Native continuous counters and each heading's prose-language scope."""
    declared = re.search(r'\\def\\lakitmainlanguage\{(english|hebrew)\}', source)
    if main is None:
        main = declared.group(1) if declared else 'english'
    elif declared and declared.group(1) != main:
        raise AssertionError(('heading source main language differs', main, declared.group(1)))
    counters = [0, 0, 0]
    headings, languages = [], []
    tokens = r'\\(?:(section|subsection|subsubsection)\{([^{}\n]+)\}|(begin|end)\{(english|hebrew)prose\})'
    for command, title, boundary, language in re.findall(tokens, source):
        if boundary == 'begin':
            languages.append(language)
            continue
        if boundary == 'end':
            if not languages or languages.pop() != language:
                raise AssertionError('heading source has an unbalanced prose-language scope')
            continue
        level = ('section','subsection','subsubsection').index(command)+1
        counters[level-1] += 1
        counters[level:] = [0]*(3-level)
        headings.append({'title':title, 'level':level,
                         'number':'.'.join(str(n) for n in counters[:level]),
                         'language':languages[-1] if languages else main})
    if languages:
        raise AssertionError('heading source has an unclosed prose-language scope')
    return headings


def heading_position(pdf, title):
    matches = [(index, box) for index, page in enumerate(pdf) for box in page.search_for(title)]
    if not matches or len({index for index, _ in matches}) != 1:
        raise AssertionError(('heading is missing or crosses pages', title, matches))
    page_number = matches[0][0]
    box = fitz.Rect(matches[0][1])
    for _, part in matches[1:]:
        box |= part
    first_y = min(part.y0 for _, part in matches)
    first_line = fitz.Rect(next(part for _, part in matches if part.y0 == first_y))
    for _, part in matches:
        if abs(part.y0-first_y) < 2:
            first_line |= part
    return page_number, box, first_line


def visible_heading_number(page, first_line, main):
    # Dense entries can make extraction merge a previous paragraph's final
    # punctuation into a heading number. Measure actual glyphs on the title's
    # baseline, rather than treating extraction words as typographic objects.
    characters, title_baselines = [],[]
    for block in page.get_text('rawdict')['blocks']:
        for line in block.get('lines',[]):
            for span in line['spans']:
                for char in span['chars']:
                    box = fitz.Rect(char['bbox'])
                    characters.append((char,box))
                    if char['c'].strip() and first_line.contains(fitz.Point((box.x0+box.x1)/2,(box.y0+box.y1)/2)):
                        title_baselines.append(round(char['origin'][1],2))
    if not title_baselines:
        raise AssertionError(('native heading has no measured baseline',first_line))
    baseline_y = max(set(title_baselines),key=title_baselines.count)
    glyphs = []
    for char,box in characters:
        if char['c'] not in '0123456789.' or abs(char['origin'][1]-baseline_y)>.15:
            continue
        center = (box.x0+box.x1)/2
        if ((first_line.x1-.1<=center<=first_line.x1+35) if main=='hebrew'
                else (first_line.x0-35<=center<=first_line.x0+.1)):
            glyphs.append((center,char['c'],box))
    if not glyphs:
        raise AssertionError(('no visible native heading number',page.number+1,first_line))
    glyphs.sort(key=lambda row:row[0])
    number = ''.join(char for _,char,_ in glyphs)
    if not re.fullmatch(r'\d+(?:\.\d+)*',number):
        raise AssertionError(('heading numeric glyphs are malformed',number,first_line))
    rect = fitz.Rect(glyphs[0][2])
    for _,_,box in glyphs[1:]:
        rect |= box
    return number,rect


def assert_optional_wide_heading(pdf, parent_title, main, expected_number):
    """The authored wide scope is plain and full width, with native counters."""
    index, title, first = heading_position(pdf, parent_title)
    page = pdf[index]
    number, numeric = visible_heading_number(page, first, main)
    if number != expected_number:
        raise AssertionError(('wide parent number', number, expected_number))
    edge = numeric.x1 if main == 'hebrew' else numeric.x0
    expected_edge = page.rect.width-MARGIN if main=='hebrew' else MARGIN
    if abs(edge-expected_edge) > 2:
        raise AssertionError(('parent number is not on the main reading edge', main, edge, expected_edge))
    title_baseline = baseline(page,title)
    rules = [drawing['rect'] for drawing in page.get_drawings()
             if ((drawing.get('fill') == (0,0,0) and .3 < drawing['rect'].height < .8)
                 or (drawing.get('color') == (0,0,0) and .3 < (drawing.get('width') or 0) < .8
                     and drawing['rect'].height < .01))
             and abs(drawing['rect'].x0-MARGIN) < 1
             and abs(drawing['rect'].x1-(page.rect.width-MARGIN)) < 1
             and -.1 <= drawing['rect'].y0-title_baseline < 10]
    if len(rules) != 1:
        raise AssertionError(('optional full-width heading rule missing', title, rules))
    return {'page':index+1,'rule':list(rules[0]),'number':number,
            'title':parent_title,'heading_box':list(title),'number_box':list(numeric)}


def assert_numbered_reference_topics(pdf, source, main, columns):
    headings = authored_heading_numbers(source, main)
    profile = re.search(r'\\def\\lakitlanguageprofile\{([^{}]+)\}', source)
    body_count = 2 if profile and profile.group(1)=='bilingual' else 1
    geometry = declared_reference_geometry(source)
    margin, gap = geometry['left'], geometry['gap']
    primary = [row for row in headings if row['level']==1]
    if len(headings)!=16*body_count or [row['number'] for row in primary] != list(map(str, range(1,12*body_count+1))):
        raise AssertionError(('authored topic block population differs', body_count, primary))
    for block in range(body_count):
        locale = main if block==0 else ('hebrew' if main=='english' else 'english')
        body = headings[16*block:16*(block+1)]
        if any(row['language']!=locale for row in body):
            raise AssertionError(('authored topic block prose language differs', block+1, locale))
        subsections = [row['number'] for row in body if row['level']==2]
        expected = [str(12*block+n)+'.1' for n in (1,3,7,11)]
        if subsections!=expected or any(row['level']>2 for row in body):
            raise AssertionError(('authored local topic hierarchy differs', block+1,subsections,expected))
    if r'\begin{referencewide}' in source:
        raise AssertionError('default reference topics must remain independent local entries')
    entries = re.findall(r'\\begin\{referenceentry\}(.*?)\\end\{referenceentry\}',source,re.S)
    if len(entries)!=12*body_count:
        raise AssertionError(('default topic entry population differs',len(entries),12*body_count))
    outline = pdf.get_toc()
    if len(outline)!=len(headings):
        raise AssertionError(('bookmark population differs', len(outline), len(headings)))
    measured = []
    for row in headings:
        index, box, first = heading_position(pdf, row['title'])
        visible, numeric = visible_heading_number(pdf[index], first, row['language'])
        if visible != row['number']:
            raise AssertionError(('visible heading number differs', row, visible))
        marks = [entry for entry in outline if entry[1] in (row['title'],row['number']+' '+row['title'])]
        if len(marks)!=1 or marks[0][0]!=row['level'] or marks[0][2]!=index+1:
            raise AssertionError(('bookmark hierarchy or page differs', row, marks, index+1))
        column = column_index(pdf[index],box,columns,main,margin,gap)
        width = (pdf[index].rect.width-2*margin-(columns-1)*gap)/columns
        physical = columns-1-column if main=='hebrew' else column
        left = margin+physical*(width+gap)
        edge = numeric.x1 if row['language']=='hebrew' else numeric.x0
        expected_edge = left+width if row['language']=='hebrew' else left
        if abs(edge-expected_edge)>2:
            raise AssertionError(('topic number is not on its prose-language reading edge',row,edge,expected_edge))
        measured.append({**row,'page':index+1,'column':column,'box':list(box),'number_box':list(numeric)})
    positions = [(row['page'],row['column'],row['box'][1]) for row in measured]
    if positions!=sorted(positions):
        raise AssertionError(('topics do not follow main-language column reading order',positions))
    openings = []
    for primary_heading,entry in zip(primary,entries):
        local = authored_heading_numbers(entry,primary_heading['language'])
        if len([row for row in local if row['level']==1])!=1:
            raise AssertionError('one primary heading required in each reference entry')
        parent = next(row for row in measured if row['number']==primary_heading['number'])
        descendants = [row for row in measured if row['number'].startswith(parent['number']+'.')]
        if any((row['page'],row['column'])!=(parent['page'],parent['column']) for row in descendants):
            raise AssertionError(('short topic was split away from its subtopic',parent,descendants))
        page = pdf[parent['page']-1]
        box = fitz.Rect(parent['box'])
        width = (page.rect.width-2*margin-(columns-1)*gap)/columns
        physical = columns-1-parent['column'] if main=='hebrew' else parent['column']
        left = margin+physical*(width+gap)
        following = [fitz.Rect(line['bbox']) for block in page.get_text('dict')['blocks']
            for line in block.get('lines',[]) if line['spans']
            and fitz.Rect(line['bbox']).y0>box.y1+.1
            and left-1<=(line['bbox'][0]+line['bbox'][2])/2<=left+width+1]
        if not following:
            raise AssertionError(('topic opening is missing from its heading column',parent))
        opening = min(following,key=lambda rect:rect.y0)
        if opening.y0-box.y1>45:
            raise AssertionError(('topic heading is separated from its opening expression',parent,opening))
        next_head = [row for row in measured if row['level']==1 and row['page']==parent['page']
            and row['column']==parent['column'] and row['box'][1]>box.y1]
        if next_head and opening.y0>=min(row['box'][1] for row in next_head):
            raise AssertionError(('another topic intervenes before its opening',parent,opening))
        openings.append({'number':parent['number'],'page':parent['page'],
            'column':parent['column'],'heading':list(box),'first_following_ink':list(opening)})
    return {'headings':measured,'local_topic_openings':openings,
            'main_language_reading_order':positions,'geometry':geometry}


def assert_column_separator_geometry(page, columns, enabled=True, margin=MARGIN, gap=GAP):
    rules = []
    for drawing in page.get_drawings():
        color = drawing.get('fill') or drawing.get('color')
        width = drawing['rect'].width if drawing.get('fill') else drawing.get('width') or 0
        if (color and max(color)-min(color)<.01 and .4 < min(color) < .85
                and .1 < width < .4 and drawing['rect'].width < .4
                and drawing['rect'].height>40):
            rules.append(drawing['rect'])
    width = (page.rect.width-2*margin-(columns-1)*gap)/columns
    expected = [margin+(i+1)*width+i*gap+gap/2 for i in range(columns-1)] if enabled else []
    groups = {}
    for rect in rules:
        groups.setdefault((round(rect.y0,2),round(rect.y1,2)),[]).append((rect.x0+rect.x1)/2)
    if enabled and not groups:
        raise AssertionError(('column separators missing', expected))
    for actual in groups.values():
        actual.sort()
        if len(actual)!=len(expected) or any(abs(a-b)>.5 for a,b in zip(actual,expected)):
            raise AssertionError(('column separator geometry differs', actual, expected))
    return [list(rect) for rect in rules]


class ReferenceRuntime(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        preserve = os.environ.get('HLLPDF_REFERENCE_EVIDENCE_DIR')
        if preserve:
            cls.root = Path(preserve).resolve()
            if cls.root == ROOT or ROOT in cls.root.parents:
                raise ValueError('reference evidence must be outside the skill')
            cls.root.mkdir(parents=True, exist_ok=False)
        else:
            cls.tmp = tempfile.TemporaryDirectory(prefix='studio-reference-runtime-')
            cls.addClassCleanup(cls.tmp.cleanup)
            cls.root = Path(cls.tmp.name)
        if shutil.which('lualatex') is None:
            raise RuntimeError('lualatex is required for reference runtime controls')
        fonts = str(font_dir())
        cache = cls.root / 'tex-cache'
        variable = cls.root / 'tex-var'
        cache.mkdir()
        variable.mkdir()
        cls.env = dict(os.environ, HEBREW_LATEX_FONT_DIR=fonts, OSFONTDIR=fonts,
                       TTFONTS=fonts+'//:', SOURCE_DATE_EPOCH='1700000000', TZ='UTC',
                       PYTHONDONTWRITEBYTECODE='1', TEXMFCACHE=str(cache),
                       TEXMFVAR=str(variable), TEXMFOUTPUT=str(cls.root))
        cls.env.pop('HEBREW_LATEX_PROJECT_ROOT', None)
        cls.directories = {}
        def compile_profile(pair):
            profile, main = pair
            name = profile+'-'+main
            directory, result = cls.compile(name, fixture(profile, main), passes=3)
            if result.returncode:
                raise AssertionError(name+':\n'+result.stdout[-15000:])
            if 'undefined references' in result.stdout or 'Missing character:' in result.stdout:
                raise AssertionError(name+': unresolved references or missing glyphs')
            for line in result.stdout.splitlines():
                if ('Overfull ' in line or 'Package mdframed Warning' in line
                        or 'LaTeX Font Warning:' in line):
                    raise AssertionError(name+': '+line)
            return (profile, main), directory
        with ThreadPoolExecutor(max_workers=2) as executor:
            for key, directory in executor.map(compile_profile, PROFILES):
                cls.directories[key] = directory
        measurements = {}
        for (profile, main), directory in cls.directories.items():
            with fitz.open(directory/'main.pdf') as pdf:
                measurements[profile+'-'+main] = {'pages': len(pdf),
                    'pdf_sha256': hashlib.sha256((directory/'main.pdf').read_bytes()).hexdigest(),
                    'columns': {str(count): {token: {'page': page+1, 'rect': list(rect)}
                        for token in [f'C{count}{chr(65+i)}' for i in range(count)]
                        for page, rect in [exact_occurrence(pdf, token)]} for count in (2, 3)},
                    'folios': [footer_candidates(page, layout='center', band='footer') for page in pdf]}
        (cls.root/'measurements.json').write_text(json.dumps(measurements, ensure_ascii=False, indent=2)+'\n')

    @classmethod
    def compile(cls, name, source, passes=1, assets=ASSETS):
        directory = cls.root/name
        directory.mkdir()
        for asset in assets:
            shutil.copyfile(ROOT/'assets'/asset, directory/asset)
        (directory/'main.tex').write_text(source, encoding='utf-8')
        return directory, cls.run_engine(directory, passes)

    @classmethod
    def run_engine(cls, directory, passes):
        for number in range(passes):
            result = subprocess.run(['lualatex', '--no-shell-escape', '-halt-on-error',
                '-interaction=nonstopmode', 'main.tex'], cwd=directory, env=cls.env,
                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=180)
            (directory/f'pass-{number+1}.txt').write_text(result.stdout, encoding='utf-8')
            if result.returncode:
                break
        return result

    def test_two_and_three_columns_follow_physical_main_language_order(self):
        for (profile, main), directory in self.directories.items():
            with self.subTest(profile=profile, main=main), fitz.open(directory/'main.pdf') as pdf:
                for count in (2, 3):
                    found = [exact_occurrence(pdf, f'C{count}{chr(65+i)}') for i in range(count)]
                    self.assertEqual(len({page for page, _ in found}), 1)
                    positions = [(rect.x0+rect.x1)/2 for _, rect in found]
                    self.assertTrue(all((a > b if main == 'hebrew' else a < b)
                                        for a, b in zip(positions, positions[1:])), positions)
                    for expected, (page, rect) in enumerate(found):
                        self.assertEqual(column_index(pdf[page], rect, count, main), expected)
                        minor_page, minor = exact_occurrence(pdf, f'C{count}{chr(65+expected)}MIN')
                        self.assertEqual(minor_page, page)
                        self.assertEqual(column_index(pdf[page], minor, count, main), expected)
                    page, tail = exact_occurrence(pdf, f'C{count}{chr(64+count)}TAIL')
                    self.assertEqual(column_index(pdf[page], tail, count, main), count-1)
                if profile not in ('english', 'hebrew'):
                    first_page, first = exact_occurrence(pdf, 'SECONDARYA')
                    second_page, second = exact_occurrence(pdf, 'SECONDARYB')
                    self.assertEqual(first_page, second_page)
                    self.assertEqual(column_index(pdf[first_page], first, 2, main), 0)
                    self.assertEqual(column_index(pdf[second_page], second, 2, main), 1)

    def test_named_targets_follow_their_own_column_and_reference_links(self):
        for (profile, main), directory in self.directories.items():
            with self.subTest(profile=profile, main=main), fitz.open(directory/'main.pdf') as pdf:
                for count in (2, 3):
                    for index in range(count):
                        token = f'C{count}{chr(65+index)}'
                        page, rect = exact_occurrence(pdf, token)
                        resolved_page, resolved_x, resolved_y = pdf.resolve_link('#nameddest=ref-'+token)
                        self.assertEqual(resolved_page, page)
                        self.assertLessEqual(rect.x0-6, resolved_x)
                        self.assertLessEqual(resolved_x, rect.x1+6)
                        self.assertLess(abs(resolved_y-rect.y0), 15)
                aux = (directory/'main.aux').read_text()
                destination = label_fields(aux, 'eq:reused')[4]
                links = [(page, link) for page in pdf for link in page.get_links()
                         if link.get('nameddest') == destination]
                self.assertEqual(len(links), 1)
                self.assertIn('(2)', reference_string(*links[0]))
                target_page, _, target_y = pdf.resolve_link('#nameddest='+destination)
                self.assertLess(abs(target_y-pdf[target_page].search_for('REUSED')[0].y0), 35)

    def test_selective_tags_units_and_matrix_ink_preserve_mathematical_order(self):
        for (profile, main), directory in self.directories.items():
            with self.subTest(profile=profile, main=main), fitz.open(directory/'main.pdf') as pdf:
                for token, tag in (('CENTRAL', 1), ('REUSED', 2)):
                    page_index, box = occurrences(pdf, token)[0]
                    row = physical_text(pdf[page_index], fitz.Rect(0, box.y0, pdf[page_index].rect.width, box.y1))
                    self.assertIn(token+'='+str(tag), row)
                    self.assertIn('('+str(tag)+')', row)
                    symbols = occurrences(pdf, '('+str(tag)+')')
                    self.assertTrue(symbols)
                for token, tag, count in (('ISLANDTWO', 3, 2), ('ISLANDTHREE', 4, 3)):
                    page_index, box = occurrences(pdf, token)[0]
                    page = pdf[page_index]
                    physical = count-1 if main == 'hebrew' else 0
                    width = (page.rect.width-2*MARGIN-(count-1)*GAP)/count
                    column_left = MARGIN+physical*(width+GAP)
                    column_right = column_left+width
                    row = physical_text(page, fitz.Rect(column_left, box.y0, column_right+1, box.y1))
                    self.assertIn(token+'='+str(tag), row)
                    self.assertIn('('+str(tag)+')', row)
                    tags = [rect for rect in page.search_for('('+str(tag)+')')
                            if abs((rect.y0+rect.y1)/2-(box.y0+box.y1)/2)<5]
                    self.assertEqual(len(tags), 1)
                    self.assertLess(abs(tags[0].x1-column_right), 2)
                    self.assertGreater(tags[0].x0-box.x1, 1)
                page_index, unused = occurrences(pdf, 'UNUSED')[0]
                row = physical_text(pdf[page_index], fitz.Rect(unused.x0-5, unused.y0,
                    unused.x1+80, unused.y1))
                self.assertNotRegex(row, r'\(\d+\)')
                page_index, unit = occurrences(pdf, 'UNITMARK')[0]
                row = physical_text(pdf[page_index], fitz.Rect(unit.x0-5, unit.y0,
                    unit.x1+100, unit.y1))
                self.assertIn('UNITMARK=10MeV', row)
                a_page, a = occurrences(pdf, 'MATA')[0]
                b_page, b = occurrences(pdf, 'MATB')[0]
                c_page, c = occurrences(pdf, 'MATC')[0]
                d_page, d = occurrences(pdf, 'MATD')[0]
                self.assertEqual({a_page,b_page,c_page,d_page}, {a_page})
                self.assertLess(a.x0, b.x0)
                self.assertLess(c.x0, d.x0)
                self.assertLess(a.y0, c.y0)
                self.assertLess(b.y0, d.y0)
                self.assertTrue(all(not list(render.mirrored_paren_digits(page)) for page in pdf))

    def test_explicit_wide_display_uses_full_page_and_does_not_touch_columns(self):
        for (profile, main), directory in self.directories.items():
            with self.subTest(profile=profile, main=main), fitz.open(directory/'main.pdf') as pdf:
                left_page, left = occurrences(pdf, 'WIDELEFT')[0]
                right_page, right = occurrences(pdf, 'WIDERIGHT')[0]
                self.assertEqual(left_page, right_page)
                self.assertGreater(right.x1-left.x0, .70*(pdf[left_page].rect.width-2*MARGIN))
                self.assertLess(abs((left.x0+right.x1)/2-pdf[left_page].rect.width/2), 3)
                column_page, tail = exact_occurrence(pdf, 'C3CTAIL')
                self.assertGreaterEqual(left_page, column_page)
                if left_page == column_page:
                    self.assertGreater(left.y0, tail.y1)
        typography = {}
        for main in ('english','hebrew'):
            for layout in ('reference-compact','reference-readable'):
                name = 'math-scope-'+layout+'-'+main
                directory,result = self.compile(name,typography_scope_fixture(main,layout))
                self.assertEqual(result.returncode,0,result.stdout[-3000:])
                for diagnostic in ('Overfull ','Missing character:','LaTeX Font Warning:'):
                    self.assertNotIn(diagnostic,result.stdout)
                with fitz.open(directory/'main.pdf') as pdf:
                    typography[name] = {
                        'pdf_sha256':hashlib.sha256((directory/'main.pdf').read_bytes()).hexdigest(),
                        'actual_engine_exit':result.returncode,
                        'actual_math_scopes':assert_typography_scope_rows(pdf,layout),
                        'actual_pdf_shape':assert_math_pdf_transforms(pdf),
                        'actual_pdf_reject_controls':assert_math_transform_reject_controls(pdf)
                            +[assert_typography_scope_leak_control(pdf,layout)]}
                (self.root/'math-scope-measurements.json').write_text(
                    json.dumps(typography,ensure_ascii=False,indent=2)+'\n')

    def test_authored_long_solution_parts_cross_pages_without_missing_or_reordered_content(self):
        for (profile, main), directory in self.directories.items():
            with self.subTest(profile=profile, main=main), fitz.open(directory/'main.pdf') as pdf:
                locations = []
                for index in range(28):
                    token = f'STEP{index:02d}'
                    page, rect = exact_occurrence(pdf, token)
                    title_page, title = exact_occurrence(pdf, token+'TITLE')
                    body_page, body = exact_occurrence(pdf, token+'BODY')
                    self.assertEqual((page, title_page, body_page), (page, page, page))
                    expected_column = column_index(pdf[page], rect, 3, main)
                    self.assertEqual(column_index(pdf[page], title, 3, main), expected_column)
                    self.assertEqual(column_index(pdf[page], body, 3, main), expected_column)
                    assert_step_title_reading_order(pdf[page],title,rect,main)
                    assert_same_atomic_step_background(pdf[page],title,rect,body)
                    self.assertGreater(baseline(pdf[page], body)-baseline(pdf[page], rect), 8)
                    self.assertGreater(rect.x0, MARGIN-1)
                    self.assertLess(rect.x1, pdf[page].rect.width-MARGIN+1)
                    self.assertGreater(title.y0, 40)
                    self.assertLess(body.y1, .9*pdf[page].rect.height)
                    locations.append((page, expected_column, rect.y0))
                self.assertEqual(locations, sorted(locations))
                self.assertGreaterEqual(len({page for page, _, _ in locations}), 2)
                # Atomic frames keep each step's title and complete body inside
                # one background rectangle. Inter-step backgrounds do not overlap.
                frames = []
                for page_index in {page for page, _, _ in locations}:
                    page = pdf[page_index]
                    backgrounds = [drawing['rect'] for drawing in page.get_drawings()
                                   if drawing.get('fill') and drawing['rect'].width > 60
                                   and drawing['rect'].height > 20]
                    for index in range(28):
                        token = f'STEP{index:02d}'
                        p, rect = exact_occurrence(pdf, token)
                        if p != page_index:
                            continue
                        _, title = exact_occurrence(pdf, token+'TITLE')
                        _, body = exact_occurrence(pdf, token+'BODY')
                        box = title|rect|body
                        # Font ascent/descent boxes include empty leading outside
                        # actual glyph ink. The 2-point metadata allowance is
                        # bounded; the engine and real PDF render gate remain live.
                        enclosing = [frame for frame in backgrounds
                                     if fitz.Rect(frame.x0-2,frame.y0-2,frame.x1+2,frame.y1+2).contains(box)]
                        self.assertTrue(enclosing, (profile, main, token, box, backgrounds))
                        frames.append((page_index, enclosing[0]))
                for index, (page, frame) in enumerate(frames):
                    for other_page, other_frame in frames[index+1:]:
                        if page == other_page:
                            overlap = frame & other_frame
                            self.assertLess(overlap.get_area(), 1)

    def test_localized_semantics_captions_running_heads_and_uniform_center_folios(self):
        for (profile, main), directory in self.directories.items():
            with self.subTest(profile=profile, main=main), fitz.open(directory/'main.pdf') as pdf:
                text = '\n'.join(page.get_text() for page in pdf)
                for expected in (('Use:', 'Conditions:', 'Question:', 'Solution:', 'Caution', 'Figure', 'Table')
                                 if main == 'english' else
                                 ('שימוש:', 'תנאים:', 'שאלה:', 'פתרון:', 'זהירות', 'איור', 'טבלה')):
                    self.assertIn(expected, text)
                sites = [site for page in pdf for site in render.caption_sites(page, 0, 'normal')]
                self.assertEqual([(kind, number) for kind, number, _ in sites],
                                 [('tbl','1'),('fig','1'),('tbl','2')])
                hard, soft = [], []
                self.assertEqual(render.dest_landing(pdf, hard, soft, 0, 'normal'), 3)
                self.assertEqual((hard, soft), ([], []))
                aux = (directory/'main.aux').read_text()
                self.assertIn('Circuit short', aux)
                self.assertIn('Data short', aux)
                # Compact and readable captions retain their declared local
                # body size rather than the article class's \small preset.
                for page in pdf:
                    for kind, number, site in render.caption_sites(page, 0, 'normal'):
                        if (kind, number) not in (('fig', '1'), ('tbl', '2')):
                            continue
                        sizes = [span['size'] for block in page.get_text('dict')['blocks']
                                 for line in block.get('lines', []) for span in line['spans']
                                 if fitz.Rect(span['bbox']).intersects(site)]
                        self.assertTrue(sizes)
                        declared_size = 9 if profile in ('english-with-hebrew','hebrew-with-english') else 7.2
                        self.assertTrue(all(abs(size-declared_size)<.1 for size in sizes), sizes)
                labels = declared_labels(pdf)
                self.assertEqual(labels, [str(index+1) for index in range(len(pdf))])
                title = 'Reference layout controls' if main=='english' else 'בדיקת עימוד דף עזר'
                title_spans = [span for block in pdf[0].get_text('dict')['blocks']
                    for line in block.get('lines',[]) for span in line['spans'] if span['text']==title]
                self.assertEqual(len(title_spans),1)
                title_box = fitz.Rect(title_spans[0]['bbox'])
                self.assertLess(abs((title_box.x0+title_box.x1)/2-pdf[0].rect.width/2),2)
                self.assertLess(abs(title_spans[0]['size']-11*72/72.27),.05)
                short = 'Reference QA' if main == 'english' else 'בדיקת עזר'
                for index, page in enumerate(pdf):
                    self.assertEqual(footer_candidates(page, expected_label=str(index+1),
                                                     layout='center', band='footer'), [str(index+1)])
                    bottom_words = [word[4] for word in page.get_text('words')
                                    if (word[1]+word[3])/2 > .9*page.rect.height]
                    self.assertEqual(bottom_words, [str(index+1)])
                    headers = [fitz.Rect(span['bbox']) for block in page.get_text('dict')['blocks']
                               for line in block.get('lines', []) for span in line['spans']
                               if span['text'] == short and span['bbox'][1] < 40]
                    self.assertEqual(len(headers), 1)
                    edge = headers[0].x1 if main=='hebrew' else headers[0].x0
                    self.assertLess(abs(edge-(page.rect.width-MARGIN if main=='hebrew' else MARGIN)), 2)
                    header_spans = [span for block in page.get_text('dict')['blocks']
                        for line in block.get('lines',[]) for span in line['spans']
                        if span['text']==short and span['bbox'][1]<40]
                    self.assertTrue(all(abs(span['size']-8*72/72.27)<.05
                                        and span['color'] not in (0,0xffffff) for span in header_spans))
                    self.assertFalse([drawing for drawing in page.get_drawings()
                        if drawing['rect'].width>.8*(page.rect.width-2*MARGIN)
                        and drawing['rect'].y1<45 and drawing.get('color')==(0,0,0)])
        self.assert_local_callout_language_controls()

    def assert_local_callout_language_controls(self):
        """Actual local reading-edge rules, math and restoration in all profiles."""
        measurements = {}
        for profile, main in PROFILES:
            with self.subTest(local_callout_profile=profile,main=main):
                source = local_callout_fixture(profile,main)
                directory,result = self.compile('local-callouts-'+profile+'-'+main,source,passes=2)
                self.assertEqual(result.returncode,0,result.stdout[-15000:])
                warnings = [line for line in result.stdout.splitlines()
                            if any(message in line for message in ('Overfull ','Missing character:',
                                'LaTeX Font Warning:','Package mdframed Warning'))]
                self.assertEqual(warnings,[])
                with fitz.open(directory/'main.pdf') as pdf:
                    notes = assert_language_leading_callout_bars(pdf,source)
                    expected_locales = [main,main] if profile in ('english','hebrew') else [main,
                        'hebrew' if main=='english' else 'english',main]
                    authored = authored_callout_languages(source)[1]
                    self.assertEqual([note['language'] for note in authored],
                                     [locale for locale in expected_locales for _ in range(2)])
                    self.assertEqual(len(notes),2*len(expected_locales))
                    self.assertEqual({note['environment'] for note in notes},
                                     {'referencenote','referencewarning'})
                    for index, locale in enumerate(expected_locales):
                        for kind in ('N','W'):
                            left = exact_occurrence(pdf,f'M{index}{kind}L')
                            right = exact_occurrence(pdf,f'M{index}{kind}R')
                            self.assertEqual(left[0],right[0])
                            self.assertLess(left[1].x1,right[1].x0)
                            note = next(note for note in notes if f'LOCAL{index}{kind}' in note['markers'])
                            self.assertEqual(note['language'],locale)
                            self.assertEqual(note['expected_side'],'right' if locale=='hebrew' else 'left')
                            self.assertTrue(fitz.Rect(note['background']).contains(left[1]))
                            self.assertTrue(fitz.Rect(note['background']).contains(right[1]))
                    for prefix in ('','INNER'):
                        zero,one = exact_occurrence(pdf,prefix+'TICKZERO'),exact_occurrence(pdf,prefix+'TICKONE')
                        self.assertEqual(zero[0],one[0])
                        self.assertLess(zero[1].x1,one[1].x0)
                    measurements[profile+'-'+main] = {'pdf_sha256':hashlib.sha256(
                        (directory/'main.pdf').read_bytes()).hexdigest(),'pages':len(pdf),
                        'actual_engine_exit':result.returncode,'language_leading_bars':notes,
                        'math_left_to_right_and_diagram_ticks_passed':True}
                if profile in ('english','hebrew'):
                    measurements[profile+'-'+main]['actual_open_edge_controls'] = \
                        self.assert_callout_horizontal_edge_controls(directory,source,notes)
        (self.root/'local-callout-language-measurements.json').write_text(
            json.dumps(measurements,ensure_ascii=False,indent=2)+'\n')

    def assert_callout_horizontal_edge_controls(self,directory,source,notes):
        """An unrelated column rule is legal; a note's own extra edge is not."""
        note = next(row for row in notes if 'LOCAL0N' in row['markers'])
        box = fitz.Rect(note['background'])
        records = []
        for defect in ('opposite-column-rule','own-top-edge','own-bottom-edge'):
            path = directory/(defect+'.pdf')
            with fitz.open(directory/'main.pdf') as original:
                page = original[note['page']-1]
                if defect=='opposite-column-rule':
                    left,right,y = page.rect.width-box.x1,page.rect.width-box.x0,box.y0
                    # The positive rule must not accidentally enclose another
                    # callout in that column. Its only relation to this note
                    # is the shared vertical position of their top edges.
                    for other in notes:
                        bounds = fitz.Rect(other['background'])
                        overlaps = min(right,bounds.x1)-max(left,bounds.x0)>bounds.width-3
                        self.assertFalse(other['page']==note['page'] and overlaps
                            and min(abs(y-bounds.y0),abs(y-bounds.y1))<2)
                else:
                    left,right = box.x0,box.x1
                    y = box.y0 if defect=='own-top-edge' else box.y1
                page.draw_line(fitz.Point(left,y),fitz.Point(right,y),
                               color=(0,0,0),width=.6*72/72.27)
                original.save(path)
            with fitz.open(path) as actual:
                if defect=='opposite-column-rule':
                    measured = assert_language_leading_callout_bars(actual,source)
                    self.assertEqual(len(measured),len(notes))
                    outcome = 'accepted-unrelated-opposite-column-rule'
                else:
                    with self.assertRaisesRegex(AssertionError,'horizontal enclosing edge'):
                        assert_language_leading_callout_bars(actual,source)
                    outcome = 'rejected-actual-own-horizontal-edge'
            records.append({'control':defect,'outcome':outcome,'pdf_sha256':hashlib.sha256(
                path.read_bytes()).hexdigest(),'added_line':[left,y,right,y],
                'target_background':list(box),'target_language':note['language']})
        return records

    def test_actual_pdf_render_gate_accepts_reference_layout_with_declared_caption_contract(self):
        for (profile, main), directory in self.directories.items():
            with self.subTest(profile=profile, main=main), contextlib.redirect_stdout(io.StringIO()) as capture:
                status = render.check(str(directory/'main.pdf'), [str(directory/'main.tex')],
                    max_cross_page=0, caption_color=0, caption_label_weight='normal')
            self.assertEqual(status, 0, capture.getvalue())

    def frame_raster_proof(self, directory, views, page_numbers=None):
        pdf = directory/'main.pdf'
        proofs = []
        for backend, dpi in views:
            output = directory/f'frame-raster-{backend}-{dpi}'
            render_review.render(pdf, output, dpi=dpi, backend=backend)
            data = json.loads((output/'review.json').read_text())
            self.assertEqual(data['pdf_sha256'], hashlib.sha256(pdf.read_bytes()).hexdigest())
            self.assertEqual((data['renderer_backend'],data['dpi']), (backend,dpi))
            for page in data['pages']:
                self.assertEqual(hashlib.sha256((output/page['image']).read_bytes()).hexdigest(),
                                 page['sha256'])
            edges = measured_frame_edges(pdf, output, dpi, page_numbers)
            backgrounds = []
            with fitz.open(pdf) as document:
                for page in document:
                    if page_numbers is not None and page.number+1 not in page_numbers:
                        continue
                    pixmap = fitz.Pixmap(str(output/f'page-{page.number+1}.png'))
                    for frame in reference_frame_rectangles(page):
                        if frame['background_gray'] is not None and frame['background_gray']<.98:
                            backgrounds.append({'page':page.number+1,'bounds':frame,
                                'sampled_title_and_body_strips':gray_frame_background_bands(pixmap,frame,dpi)})
            proof = {'backend':backend,'dpi':dpi,'pdf_sha256':data['pdf_sha256'],
                     'rendered_pages':data['page_count'],'review':str(output/'review.json'),
                     'review_sha256':hashlib.sha256((output/'review.json').read_bytes()).hexdigest(),
                     'edges':edges,'uniform_gray_question_answer_interiors':backgrounds}
            proofs.append(proof)
            (directory/'frame-raster-measurements.json').write_text(
                json.dumps(proofs, ensure_ascii=False, indent=2)+'\n')
            assert_visible_frame_edges(edges)
        return proofs

    def test_generated_reference_profiles_build_managed_with_native_column_balance(self):
        # A real regression left the entire third column empty while engine
        # warnings and manually forced-column fixtures still passed. Exercise
        # the unedited public starter, whose unequal complete topic entries
        # require multicol's natural final balancing path.
        def build(choice):
            layout, profile, main = choice
            directory = self.root/('managed-'+layout+'-'+profile+'-'+main)
            create('formula-sheet', directory, language=profile, main_language=main, layout=layout)
            environment=dict(self.env, HEBREW_LATEX_SKILL_ROOT=str(ROOT))
            environment.pop('TEXMFOUTPUT', None)
            result = subprocess.run(['bash', str(directory/'build.sh')], cwd=directory,
                env=environment, text=True,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=240)
            (directory/'managed-build.txt').write_text(result.stdout, encoding='utf-8')
            return choice, directory, result
        choices = [(layout, profile, main) for layout in ('reference-compact','reference-readable')
                   for profile, main in PROFILES]
        with ThreadPoolExecutor(max_workers=2) as executor:
            builds = list(executor.map(build, choices))
        measurements = {}
        for (layout, profile, main), directory, result in builds:
            with self.subTest(layout=layout, profile=profile, main=main):
                self.assertEqual(result.returncode, 0, result.stdout[-2500:])
                for diagnostic in ('Overfull ', 'Missing character:',
                                   'Package mdframed Warning', 'LaTeX Font Warning:'):
                    self.assertNotIn(diagnostic, result.stdout)
                self.assertRegex(result.stdout, r'(?m)^\s*undefined references\s*:\s*0\s')
                source = (directory/'main.tex').read_text(encoding='utf-8')
                self.assertNotIn(r'\columnbreak', source)
                project = json.loads((directory/'project.json').read_text())
                initial = project['initial_source_sha256']
                self.assertEqual(hashlib.sha256(source.encode()).hexdigest(), initial['main.tex'])
                with fitz.open(directory/'main.pdf') as pdf:
                    geometry = declared_reference_geometry(source)
                    count = project['layout']['columns']
                    footers = assert_reference_footer_clearance(pdf,source)
                    measurements[layout+'-'+profile+'-'+main] = {
                        'actual_managed_build_exit': result.returncode,
                        'pdf_sha256': hashlib.sha256((directory/'main.pdf').read_bytes()).hexdigest(),
                        'pages': len(pdf), 'measured_every_page_folio_clearance':footers}
                    topics = assert_numbered_reference_topics(pdf,source,main,count)
                    measurements[layout+'-'+profile+'-'+main]['numbered_topic_hierarchy'] = topics
                    separator_geometry = [assert_column_separator_geometry(page,count,
                        margin=geometry['left'],gap=geometry['gap']) for page in pdf]
                    measurements[layout+'-'+profile+'-'+main]['every_page_column_separators'] = separator_geometry
                    measurements[layout+'-'+profile+'-'+main]['callout_geometry'] = assert_reference_callout_geometry(pdf,source)
                    measurements[layout+'-'+profile+'-'+main]['native_math_typography'] = assert_native_reference_math_typography(pdf,layout)
                    (self.root/'managed-profile-measurements.json').write_text(
                        json.dumps(measurements, ensure_ascii=False, indent=2)+'\n')
                if profile in ('english','hebrew'):
                    proofs = self.frame_raster_proof(directory,
                        [(backend,dpi) for backend in ('poppler','mupdf') for dpi in (144,300)])
                    measurements[layout+'-'+profile+'-'+main]['visible_frame_edges'] = {
                        'rendered_cases':len(proofs),
                        'measured_edges':sum(len(proof['edges']) for proof in proofs),
                        'minimum_coverage':min(edge['coverage_fraction'] for proof in proofs
                                               for edge in proof['edges'])}
                    (self.root/'managed-profile-measurements.json').write_text(
                        json.dumps(measurements, ensure_ascii=False, indent=2)+'\n')
                if profile not in ('english','hebrew'):
                    continue
                with fitz.open(directory/'main.pdf') as pdf:
                    self.assertEqual((topics['headings'][0]['page'],topics['headings'][0]['column']),(1,0))
                    page_balance = []
                    for index,page in enumerate(pdf):
                        primaries = [row for row in topics['headings'] if row['level']==1 and row['page']==index+1]
                        self.assertTrue(primaries)
                        top = min(row['box'][1] for row in primaries)
                        bottom = page.rect.height-geometry['bottom']
                        ink = [[] for _ in range(count)]
                        for word in page.get_text('words'):
                            rect = fitz.Rect(word[:4])
                            if top-.5<=rect.y0 and rect.y1<=bottom+2:
                                ink[column_index(page,rect,count,main,geometry['left'],geometry['gap'])].append(rect)
                        counts = [len(items) for items in ink]
                        depths = [max((rect.y1 for rect in items),default=0) for items in ink]
                        entry_heights = []
                        for row in primaries:
                            siblings = [other for other in primaries if other['column']==row['column']
                                        and other['box'][1]>row['box'][1]]
                            end = min((other['box'][1] for other in siblings),default=bottom+2)
                            entry_ink = [rect for rect in ink[row['column']]
                                         if row['box'][1]-.5<=rect.y0<end]
                            self.assertTrue(entry_ink)
                            entry_heights.append(max(rect.y1 for rect in entry_ink)-min(rect.y0 for rect in entry_ink))
                        balance_budget = max(entry_heights)+2*float(project['layout']['body_baseline'])
                        # Measured whole entries justify only one entry's slack.
                        # The unforced native sheet must actually use each column.
                        self.assertTrue(all(n>=25 for n in counts),(layout,main,index+1,counts))
                        self.assertLessEqual(max(depths)-min(depths),balance_budget,
                            (layout,main,index+1,depths,balance_budget))
                        page_balance.append({'page':index+1,'word_counts':counts,'column_depths':depths,
                            'entry_ink_heights':entry_heights,'balance_budget_pt':balance_budget})
                    measurements[layout+'-'+profile+'-'+main]['natural_column_balance'] = page_balance
                    (self.root/'managed-profile-measurements.json').write_text(json.dumps(measurements,ensure_ascii=False,indent=2)+'\n')
                with contextlib.redirect_stdout(io.StringIO()) as capture:
                    status = render.check(str(directory/'main.pdf'), [str(directory/'main.tex')],
                        max_cross_page=0, caption_color=0, caption_label_weight='normal')
                self.assertEqual(status, 0, capture.getvalue())
        # The ordinary theme and semantic component styles are separate public
        # providers. The first synthetic page includes an ordinary notebox,
        # whose actual border must remain visible at the failing DPI too.
        for main in ('english','hebrew'):
            directory = self.directories[(main,main)]
            with fitz.open(directory/'main.pdf') as pdf:
                page, note = exact_occurrence(pdf, 'C2BNOTE')
            proofs = self.frame_raster_proof(directory, [('poppler',144)], {page+1})
            enclosing = [edge for edge in proofs[0]['edges']
                         if fitz.Rect(edge['bounds']['left'],edge['bounds']['vertical_start'],
                                      edge['bounds']['right'],edge['bounds']['vertical_end']).contains(
                                          fitz.Point((note.x0+note.x1)/2,(note.y0+note.y1)/2))]
            self.assertTrue(enclosing, (main, note))

    def test_invalid_counts_geometry_and_nesting_fail_in_actual_engine(self):
        cases = [
            ('count-one', r'\begin{referencecolumns}[1]Control.\end{referencecolumns}', 'accepts only 2 or 3 columns', ''),
            ('count-four', r'\begin{referencecolumns}[4]Control.\end{referencecolumns}', 'accepts only 2 or 3 columns', ''),
            ('zero-gap', r'\begin{referencecolumns}Control.\end{referencecolumns}', 'column gap must be positive', r'\renewcommand{\ReferenceColumnGap}{0pt}'),
            ('negative-skip', r'\begin{referencecolumns}Control.\end{referencecolumns}', 'column skip must not be negative', r'\renewcommand{\ReferenceColumnSkip}{-1pt}'),
            ('negative-rule', r'\begin{referencecolumns}Control.\end{referencecolumns}', 'column rule must not be negative', r'\renewcommand{\ReferenceColumnRule}{-1pt}'),
            ('zero-font', r'\begin{referencecolumns}Control.\end{referencecolumns}', 'body font size must be positive', r'\renewcommand{\ReferenceBodyFontSize}{0}'),
            ('small-baseline', r'\begin{referencecolumns}Control.\end{referencecolumns}', 'baseline must not be smaller', r'\renewcommand{\ReferenceBodyBaseline}{8}'),
            ('zero-math-scriptscript', r'\begin{referencecolumns}Control.\end{referencecolumns}', 'Reference math sizes must be positive', r'\renewcommand{\ReferenceMathScriptScriptSize}{0}'),
            ('reversed-math-script', r'\begin{referencecolumns}Control.\end{referencecolumns}', 'Reference math script sizes must be ordered', r'\renewcommand{\ReferenceMathScriptSize}{3}'),
            ('reversed-math-main', r'\begin{referencewide}Control.\end{referencewide}', 'Reference math sizes must be ordered', r'\renewcommand{\ReferenceMathFontSize}{6}'),
            ('nested-columns', r'\begin{referencecolumns}\begin{referencecolumns}Control.\end{referencecolumns}\end{referencecolumns}', 'referencecolumns cannot be nested', ''),
            ('wide-in-columns', r'\begin{referencecolumns}\begin{referencewide}Control.\end{referencewide}\end{referencecolumns}', 'referencewide cannot be used inside', ''),
            ('columns-in-wide', r'\begin{referencewide}\begin{referencecolumns}Control.\end{referencecolumns}\end{referencewide}', 'referencecolumns cannot be nested inside', ''),
            ('inner-columns', r'\begin{minipage}{100pt}\begin{referencecolumns}Control.\end{referencecolumns}\end{minipage}', 'requires outer text mode', ''),
            ('list-columns', r'\begin{itemize}\item\begin{referencecolumns}Control.\end{referencecolumns}\end{itemize}', 'cannot be nested in a list', ''),
            ('float-in-columns', r'\begin{referencecolumns}\begin{figure}Control.\end{figure}\end{referencecolumns}', 'Floats is not supported inside', ''),
            ('longtable-in-columns', r'\begin{referencecolumns}\begin{longtable}{l}Control.\\\end{longtable}\end{referencecolumns}', 'longtable is not supported inside', r'\usepackage{longtable}'),
            ('too-tall-card', r'\begin{referencecolumns}\begin{referencenote}\vspace*{1.1\textheight}Control.\end{referencenote}\end{referencecolumns}', 'Reference block exceeds one full column', ''),
            ('too-tall-object', r'\begin{referencecolumns}\begin{referencefigure}\rule{5pt}{1.1\textheight}\end{referencefigure}\end{referencecolumns}', 'Reference object exceeds one full column', ''),
            ('nested-entry', r'\begin{referencecolumns}\begin{referenceentry}\begin{referenceentry}Control.\end{referenceentry}\end{referenceentry}\end{referencecolumns}', 'Reference entries cannot be nested', ''),
            ('too-tall-entry', r'\begin{referencecolumns}\begin{referenceentry}\rule{5pt}{1.1\textheight}\end{referenceentry}\end{referencecolumns}', 'Reference entry exceeds one full column', ''),
        ]
        for name, body, diagnostic, extra in cases:
            directory, result = self.compile(name, header(extra='')+extra+'\n'
                +r'\begin{document}'+body+r'\end{document}')
            with self.subTest(name=name):
                self.assertNotEqual(result.returncode, 0)
                self.assertTrue(''.join(diagnostic.split()) in ''.join(result.stdout.split()),
                                name+': '+result.stdout[-1800:])
                self.assertFalse((directory/'main.pdf').exists())
        _, result = self.compile('class-twocolumn', header(options='10pt,a4paper,twocolumn')
            +r'\begin{document}\begin{referencecolumns}Control.\end{referencecolumns}\end{document}')
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue('requiresaone-columndocumentclass' in ''.join(result.stdout.split()), result.stdout[-1800:])

    def test_missing_core_and_conflicting_theme_are_runtime_architecture_failures(self):
        for name, source, diagnostic in [
            ('missing-core', r'\input{reference_columns.tex}\end', 'requires preamble.tex first'),
            ('theme-conflict', header(layers=('reader_theme.tex','reference_theme.tex'))
                +r'\begin{document}Control.\end{document}', 'reference_theme.tex conflicts with reader_theme.tex')]:
            assets = ASSETS+('reader_theme.tex',)
            directory, result = self.compile(name, source, assets=assets)
            with self.subTest(name=name):
                self.assertNotEqual(result.returncode, 0)
                self.assertTrue(''.join(diagnostic.split()) in ''.join(result.stdout.split()),
                                name+': '+result.stdout[-1800:])
                self.assertFalse((directory/'main.pdf').exists())

    def test_native_heading_counters_stars_references_and_zero_separator(self):
        for main in ('english','hebrew'):
            names = ('Native parent','First child','Unnumbered note','Second child') if main=='english' else (
                'נושא ראשי','נושא משנה ראשון','הערה ללא מספר','נושא משנה שני')
            source = header(main, main, extra=r'\def\lakitsecnumdepth{2}\def\lakittocdepth{2}\def\ReferenceColumnRule{0pt}')
            source += r'\begin{document}\begin{referencewide}\section{'+names[0]+r'}\label{sec:native-parent}'+'\n'
            source += prose(main,'PARENTBODY')+r'\end{referencewide}\begin{referencecolumns}[2]'+'\n'
            source += r'\subsection{'+names[1]+r'}\label{sec:native-child}'+prose(main,'CHILDBODY')+'\n'
            source += r'\section*{'+names[2]+r'}'+prose(main,'STARREDBODY')+'\n'
            source += r'\subsection{'+names[3]+r'}\label{sec:native-next}'+prose(main,'NEXTBODY')+'\n'
            source += r'\ref{sec:native-parent}, \ref{sec:native-child}, \ref{sec:native-next}.'+'\n'
            source += r'\end{referencecolumns}\end{document}'+'\n'
            directory, result = self.compile('native-counter-'+main, source, passes=3)
            with self.subTest(main=main):
                self.assertEqual(result.returncode, 0, result.stdout[-1800:])
                self.assertNotIn('Overfull ', result.stdout)
                self.assertNotIn('LaTeX Font Warning:', result.stdout)
                aux = (directory/'main.aux').read_text()
                with fitz.open(directory/'main.pdf') as pdf:
                    assert_optional_wide_heading(pdf,names[0],main,'1')
                    assert_column_separator_geometry(pdf[0],2,enabled=False)
                    for title, number, label, level in zip((names[0],names[1],names[3]),
                            ('1','1.1','1.2'),
                            ('sec:native-parent','sec:native-child','sec:native-next'),(1,2,2)):
                        fields = label_fields(aux,label)
                        self.assertEqual(fields[1],number)
                        index, box, first = heading_position(pdf,title)
                        self.assertEqual(visible_heading_number(pdf[index],first,main)[0],number)
                        self.assertIn([level,title,index+1],pdf.get_toc())
                        target, _, y = pdf.resolve_link('#nameddest='+fields[4])
                        self.assertEqual(target,index)
                        self.assertLess(abs(y-box.y0),30)
                        links = [(page,link) for page in pdf for link in page.get_links()
                                 if link.get('nameddest')==fields[4]]
                        self.assertEqual(len(links),1)
                        self.assertIn(number,reference_string(*links[0]))
                    index, _, first = heading_position(pdf,names[2])
                    with self.assertRaises(AssertionError):
                        visible_heading_number(pdf[index],first,main)
                    self.assertNotIn(names[2],[entry[1] for entry in pdf.get_toc()])

    def test_atomic_topic_entry_preserves_nested_figure_table_and_named_anchors(self):
        for main in ('english','hebrew'):
            title = 'One complete topic' if main=='english' else 'נושא שלם אחד'
            source = header(main,main,extra=r'\def\lakitsecnumdepth{2}\def\lakittocdepth{2}')
            source += r'\begin{document}\begin{referencecolumns}[2]\vspace*{40pt}\begin{referenceentry}'+'\n'
            source += r'\section{'+title+r'}\label{sec:entry}'+prose(main,'ENTRYOPEN')+'\n'
            source += r'\[\mathrm{ENTRYFIRST}=1\]'+'\n'
            source += r'\begin{referencefigure}\begin{tikzpic}\begin{tikzpicture}\draw (0,0) rectangle (2,1);\node at (1,.5){\en{ENTRYFIG}};\end{tikzpicture}\end{tikzpic}'+'\n'
            source += r'\referencefigcap{\label{fig:entry}'+('A bounded figure.' if main=='english' else 'איור מוגדר.')+r'}\end{referencefigure}'+'\n'
            source += r'\begin{referencetable}\centering\begin{tabular}{ll}\toprule\en{ENTRYTABLE}&\en{Value}\\\midrule\en{A}&\en{12}\\\bottomrule\end{tabular}'+'\n'
            source += r'\referencetabcap{\label{tbl:entry}'+('A bounded table.' if main=='english' else 'טבלה מוגדרת.')+r'}\end{referencetable}'+'\n'
            source += prose(main,'ENTRYEND')+r'\end{referenceentry} See \ref{sec:entry}, \autoref{fig:entry}, \autoref{tbl:entry}.'+'\n'
            source += r'\end{referencecolumns}\end{document}'+'\n'
            directory,result = self.compile('nested-objects-entry-'+main,source,passes=3)
            with self.subTest(main=main):
                self.assertEqual(result.returncode,0,result.stdout[-1800:])
                self.assertNotIn('Overfull ',result.stdout)
                self.assertNotIn('LaTeX Font Warning:',result.stdout)
                aux = (directory/'main.aux').read_text()
                with fitz.open(directory/'main.pdf') as pdf:
                    first_expression = occurrences(pdf,'ENTRYFIRST')
                    self.assertEqual(len(first_expression),1)
                    positions = [exact_occurrence(pdf,'ENTRYOPEN'),first_expression[0]]
                    positions += [exact_occurrence(pdf,token) for token in ('ENTRYFIG','ENTRYTABLE','ENTRYEND')]
                    self.assertEqual(len({page for page,_ in positions}),1)
                    page_number = positions[0][0]
                    self.assertEqual({column_index(pdf[page],box,2,main) for page,box in positions},{0})
                    self.assertEqual([box.y0 for _,box in positions],sorted(box.y0 for _,box in positions))
                    for label,token in (('fig:entry','ENTRYFIG'),('tbl:entry','ENTRYTABLE')):
                        fields = label_fields(aux,label)
                        self.assertEqual(fields[1],'1')
                        target,x,y = pdf.resolve_link('#nameddest='+fields[4])
                        _,object_box = exact_occurrence(pdf,token)
                        self.assertEqual(target,page_number)
                        self.assertLess(y,object_box.y1)
                        self.assertGreaterEqual(y,0)
                        self.assertLess(abs(x-object_box.x0),pdf[target].rect.width/2)
                        links = [(page,link) for page in pdf for link in page.get_links() if link.get('nameddest')==fields[4]]
                        self.assertEqual(len(links),1)
                        self.assertIn('1',reference_string(*links[0]))
                    hard,soft = [],[]
                    self.assertEqual(render.dest_landing(pdf,hard,soft,0,'normal'),2)
                    self.assertEqual((hard,soft),([],[]))

    def test_section_stays_with_first_atomic_card_at_column_boundary(self):
        for main in ('english', 'hebrew'):
            heading = 'Boundary topic' if main == 'english' else 'כותרת מעבר'
            source = header(main, main)+r'\begin{document}\begin{referencecolumns}[2]'+'\n'
            source += prose(main, 'BEFOREBOUNDARY')+r'\par\vspace*{\dimexpr\textheight-60pt\relax}'+'\n'
            source += fr'\section{{{heading}}}\label{{sec:boundary}}'+'\n'
            source += r'\begin{referencenote}'+prose(main, 'BOUNDARYBODY')
            source += r'\par'+'\n'+prose(main, 'BOUNDARYSECOND')+r'\par'+'\n'+prose(main, 'BOUNDARYTHIRD')
            source += r'\end{referencenote}\end{referencecolumns}\end{document}'+'\n'
            directory, result = self.compile('orphan-boundary-'+main, source, passes=2)
            with self.subTest(main=main):
                self.assertEqual(result.returncode, 0, result.stdout[-1800:])
                self.assertNotIn('Overfull ', result.stdout)
                with fitz.open(directory/'main.pdf') as pdf:
                    page, body = exact_occurrence(pdf, 'BOUNDARYBODY')
                    before_page, before = exact_occurrence(pdf, 'BEFOREBOUNDARY')
                    self.assertEqual(before_page, page)
                    self.assertEqual(column_index(pdf[before_page], before, 2, main), 0)
                    self.assertEqual(column_index(pdf[page], body, 2, main), 1)
                    title_parts = [(index, rect) for index, p in enumerate(pdf) for rect in p.search_for(heading)]
                    self.assertTrue(title_parts)
                    self.assertEqual({index for index, _ in title_parts}, {page})
                    title = fitz.Rect(title_parts[0][1])
                    for _, rect in title_parts[1:]:
                        title |= rect
                    self.assertEqual(column_index(pdf[page], title, 2, main),
                                     column_index(pdf[page], body, 2, main))
                    self.assertGreater(body.y0, title.y0)
                    for token in ('BOUNDARYSECOND', 'BOUNDARYTHIRD'):
                        p, rect = exact_occurrence(pdf, token)
                        self.assertEqual(p, page)
                        self.assertEqual(column_index(pdf[p], rect, 2, main),
                                         column_index(pdf[page], body, 2, main))


def reference_heading_fixture(main, theme):
    """Narrow/wide native headings with actual scope and typography probes."""
    layers = ('reference_columns.tex', 'reference_components.tex', 'reference_shell.tex')
    if theme != 'core':
        layers += (theme+'_theme.tex',)
    source = header(main,main,layers=layers,body_font_size='6.3',body_baseline='7.8',
        extra=r'\def\lakitparagraphstyle{block}\def\lakitsecnumdepth{2}\def\lakittocdepth{2}')
    source += r'''
\makeatletter
\let\ReferenceHeadingOriginalStartsection\@startsection
\newcommand{\ReferenceHeadingScopeProbe}[1]{%
  \typeout{REF-HEAD-SCOPE:#1:\ifx\@startsection\ReferenceHeadingOriginalStartsection ORIGINAL\else WRAPPED\fi:\the\hyphenpenalty:\the\exhyphenpenalty:\the\rightskip:\the\leftskip}}
\newcommand{\ReferenceHeadingTitleProbe}[1]{%
  \typeout{REF-HEAD-TITLE:#1:\f@size:\the\baselineskip:\the\hyphenpenalty:\the\exhyphenpenalty:\the\rightskip:\the\leftskip}}
\makeatother
\begin{document}
\ReferenceHeadingScopeProbe{OUTERBEFORE}
\ReferenceSelectBodyFont
\ReferenceHeadingScopeProbe{PUBLICSELECT}
\normalsize
\begin{referencecolumns}[3]
\ReferenceSelectBodyFont\ReferenceSelectBodyFont
\ReferenceHeadingScopeProbe{COLUMNS}
'''
    def body(locale, token):
        text='A bounded reference step.' if locale=='english' else 'צעד עזר מוגדר.'
        return text+r'\par'+'\n'+marker(token)+r'\par'+'\n'
    titles = ('Eigenvalues and uncertainty in expectation values',
              'Measurements and probabilities', 'Phase-space measurements',
              'Dynamics waves and single-qubit expectation values') if main=='english' else (
              'הסתברות וערכים עצמיים במערכות קוונטיות',
              'מדידות והסתברויות', 'שלב-מרחב ומדידות',
              'דינמיקה גלים ותוחלת במערכת קוונטית')
    source += marker('HEADINGBEFORECOLUMN')+r'\par'+'\n'
    source += (r'\section[Column heading]{\texorpdfstring{\ReferenceHeadingTitleProbe{COLUMN}}{}'+
        titles[0]+r'}\label{sec:heading-column}'+'\n')
    source += marker('HEADINGAFTERCOLUMN')+r'\par'+'\n'+body(main,'HEADINGCOLUMNBODY')
    source += r'\ReferenceHeadingScopeProbe{COLUMNBODY}'+'\n'
    source += marker('HEADINGBEFORECHILD')+r'\par'+'\n'
    source += (r'\subsection[Child heading]{\texorpdfstring{\ReferenceHeadingTitleProbe{CHILD}}{}'+
        titles[1]+r' \texorpdfstring{$x_{y_z}$}{x}}\label{sec:heading-child}'+'\n')
    source += marker('HEADINGAFTERCHILD')+r'\par'+'\n'+body(main,'HEADINGCHILDBODY')
    source += (r'\section*{\texorpdfstring{\ReferenceHeadingTitleProbe{STAR}}{}'+
        titles[2]+r'}'+body(main,'HEADINGSTARBODY'))
    other = 'hebrew' if main=='english' else 'english'
    minority = 'Minority reference heading' if other=='english' else 'כותרת עזר בשפה נוספת'
    source += r'\par\columnbreak'+fr'\begin{{{other}prose}}'+'\n'
    source += r'\ReferenceHeadingScopeProbe{MINORITYBODY}'+'\n'
    source += r'\section*{\texorpdfstring{\ReferenceHeadingTitleProbe{MINORITY}}{}'+minority+r'}'+'\n'
    source += body(other,'HEADINGMINORITYBODY')+fr'\end{{{other}prose}}'+'\n'
    source += r'\par\columnbreak'+'\n'+body(main,'HEADINGTHIRDBODY')+'\n'
    source += r'\end{referencecolumns}\ReferenceHeadingScopeProbe{AFTERCOLUMNS}'+'\n'
    source += r'\begin{referencewide}\ReferenceSelectBodyFont\ReferenceHeadingScopeProbe{WIDE}'+'\n'
    source += marker('HEADINGBEFOREWIDE')+r'\par'+'\n'
    source += (r'\section[Wide heading]{\texorpdfstring{\ReferenceHeadingTitleProbe{WIDE}}{}'+
        titles[3]+r'}\label{sec:heading-wide}'+'\n')
    source += marker('HEADINGAFTERWIDE')+r'\par'+'\n'+body(main,'HEADINGWIDEBODY')
    source += r'\ReferenceHeadingScopeProbe{WIDEBODY}'+'\n'
    source += r'\end{referencewide}\ReferenceHeadingScopeProbe{OUTERAFTER}'+'\n'
    source += r'\ref{sec:heading-column}, \ref{sec:heading-child}, \ref{sec:heading-wide}.'+'\n'
    source += r'\[x_{y_z}+\frac{\alpha}{\sqrt{u}}=1\]'+'\n'
    return source+r'\end{document}'+'\n'


def reference_heading_probes(log, kind):
    return {match[0]:match[1].split(':') for match in re.findall(
        r'REF-HEAD-'+kind+r':([^:\n]+):([^\n]+)',log)}


def reference_heading_word_geometry(pdf, phase):
    before_page,before = exact_occurrence(pdf,'HEADINGBEFORE'+phase)
    after_page,after = exact_occurrence(pdf,'HEADINGAFTER'+phase)
    if before_page != after_page or after.y0 <= before.y1:
        raise AssertionError(('heading probe region split or reordered',phase,before,after))
    page = pdf[before_page]
    region = fitz.Rect(MARGIN-1,before.y1-1,page.rect.width-MARGIN+1,after.y0+.2)
    if phase in ('COLUMN','CHILD'):
        physical = column_index(page,before,3,'english')
        width = (page.rect.width-2*MARGIN-2*GAP)/3
        region.x0=MARGIN+physical*(width+GAP)-1
        region.x1=region.x0+width+2
    words = [word for word in page.get_text('words') if region.contains(fitz.Rect(word[:4]))
             and not re.fullmatch(r'[\d.]+',word[4])]
    if not words:
        raise AssertionError(('no native heading words in probe region',phase,region))
    lines = {}
    for word in words:
        lines.setdefault((word[5],word[6]),[]).append(word)
    gaps = []
    for row in lines.values():
        row.sort(key=lambda word:word[0])
        gaps.extend(right[0]-left[2] for left,right in zip(row,row[1:]))
    return {'page':before_page+1,'region':list(region),'words':[word[4] for word in words],
            'lines':len(lines),'gaps':gaps,'rows':[[list(word[:5]) for word in row]
                for row in lines.values()]}


class ReferenceHeadingRuntime(unittest.TestCase):
    """Fresh theme-independent heading flow and genuinely old-style controls."""
    compile = classmethod(ReferenceRuntime.compile.__func__)
    run_engine = classmethod(ReferenceRuntime.run_engine.__func__)

    @classmethod
    def setUpClass(cls):
        preserve = os.environ.get('HLLPDF_REFERENCE_HEADING_EVIDENCE_DIR')
        if preserve:
            cls.root=Path(preserve).resolve()
            if cls.root==ROOT or ROOT in cls.root.parents:
                raise ValueError('heading evidence must be outside the skill')
            cls.root.mkdir(parents=True,exist_ok=False)
        else:
            cls.tmp=tempfile.TemporaryDirectory(prefix='studio-reference-heading-runtime-')
            cls.addClassCleanup(cls.tmp.cleanup)
            cls.root=Path(cls.tmp.name)
        if shutil.which('lualatex') is None:
            raise RuntimeError('lualatex is required for heading runtime controls')
        fonts=str(font_dir())
        cache=cls.root/'tex-cache'
        variable=cls.root/'tex-var'
        cache.mkdir()
        variable.mkdir()
        cls.env=dict(os.environ,HEBREW_LATEX_FONT_DIR=fonts,OSFONTDIR=fonts,
            TTFONTS=fonts+'//:',SOURCE_DATE_EPOCH='1700000000',TZ='UTC',PYTHONDONTWRITEBYTECODE='1',
            TEXMFCACHE=str(cache),TEXMFVAR=str(variable),TEXMFOUTPUT=str(cls.root))
        cls.env.pop('HEBREW_LATEX_PROJECT_ROOT',None)
        cls.assets=ASSETS+('reader_theme.tex','academic_theme.tex')
        cls.directories={}
        def build(pair):
            main,theme=pair
            directory,result=cls.compile(main+'-'+theme,reference_heading_fixture(main,theme),
                passes=3,assets=cls.assets)
            if result.returncode:
                raise AssertionError(main+'-'+theme+': '+result.stdout[-6000:])
            for forbidden in ('Overfull ','Missing character:','LaTeX Font Warning:',
                              'undefined references','Token not allowed in a PDF string'):
                if forbidden in result.stdout:
                    raise AssertionError(main+'-'+theme+': '+forbidden+'\n'+result.stdout[-6000:])
            return pair,directory
        with ThreadPoolExecutor(max_workers=2) as executor:
            for pair,directory in executor.map(build,[(main,theme)
                    for main in ('english','hebrew') for theme in ('core','reader','academic','reference')]):
                cls.directories[pair]=directory
        cls.negative={}
        # Remove the new title-only setup in copied assets, reproducing native
        # old justified/hyphenated headings without changing body/font/theme.
        target=r'''\newcommand{\hllpdf@referenceheadingsetup}{%
  \raggedright
  \hyphenpenalty=10000\relax}'''
        asset=(ROOT/'assets/reference_columns.tex').read_text()
        if asset.count(target)!=1:
            raise AssertionError('negative control lost its exact layout owner target')
        for theme in ('core','academic'):
            name='old-justified-english-'+theme
            directory=cls.root/name
            directory.mkdir()
            for item in cls.assets:
                shutil.copyfile(ROOT/'assets'/item,directory/item)
            (directory/'reference_columns.tex').write_text(asset.replace(
                target,r'\newcommand{\hllpdf@referenceheadingsetup}{}',1))
            (directory/'main.tex').write_text(reference_heading_fixture('english',theme))
            result=cls.run_engine(directory,3)
            if result.returncode:
                raise AssertionError('old-style negative did not compile: '+result.stdout[-6000:])
            cls.negative[theme]=directory
        observations={}
        for pair,directory in cls.directories.items():
            with fitz.open(directory/'main.pdf') as pdf:
                observations['-'.join(pair)]={'pdf_sha256':hashlib.sha256((directory/'main.pdf').read_bytes()).hexdigest(),
                    'columns':reference_heading_word_geometry(pdf,'COLUMN'),
                    'wide':reference_heading_word_geometry(pdf,'WIDE'),
                    'child':reference_heading_word_geometry(pdf,'CHILD')}
        for theme,directory in cls.negative.items():
            with fitz.open(directory/'main.pdf') as pdf:
                observations['old-justified-'+theme]={'pdf_sha256':hashlib.sha256((directory/'main.pdf').read_bytes()).hexdigest(),
                    'columns':reference_heading_word_geometry(pdf,'COLUMN')}
        (cls.root/'heading-measurements.json').write_text(json.dumps(observations,ensure_ascii=False,indent=2)+'\n')

    def assert_scoped_heading_policy(self,directory):
        log=(directory/'pass-3.txt').read_text()
        titles=reference_heading_probes(log,'TITLE')
        self.assertEqual(set(titles),{'COLUMN','CHILD','STAR','MINORITY','WIDE'})
        for role,values in titles.items():
            self.assertEqual(values[2],'10000',(role,values))
            self.assertIn('fil',values[4],(role,values))
            self.assertEqual(values[5],'0.0pt',(role,values))
        scopes=reference_heading_probes(log,'SCOPE')
        for role in ('COLUMNS','COLUMNBODY','WIDE','WIDEBODY'):
            self.assertEqual(scopes[role][0],'WRAPPED',(role,scopes[role]))
        for role in ('OUTERBEFORE','PUBLICSELECT','AFTERCOLUMNS','OUTERAFTER'):
            self.assertEqual(scopes[role][0],'ORIGINAL',(role,scopes[role]))
        # The paragraph body keeps its actual native hyphen penalty; locally
        # ragged reference-theme prose remains its own distinct body policy.
        for role,values in scopes.items():
            if role=='MINORITYBODY':
                continue
            self.assertEqual(values[1],scopes['OUTERBEFORE'][1],(role,values))
            self.assertEqual(values[2],scopes['OUTERBEFORE'][2],(role,values))
        self.assertEqual(scopes['OUTERAFTER'][3:],scopes['OUTERBEFORE'][3:])
        for role,values in titles.items():
            native=scopes['MINORITYBODY'] if role=='MINORITY' else scopes['OUTERBEFORE']
            self.assertEqual(values[3],native[2])
        return titles

    def test_active_columns_and_wide_headings_are_natural_while_outer_scope_restores(self):
        for pair,directory in self.directories.items():
            with self.subTest(language=pair[0],theme=pair[1]):
                titles=self.assert_scoped_heading_policy(directory)
                with fitz.open(directory/'main.pdf') as pdf:
                    for phase in ('COLUMN','WIDE'):
                        geometry=reference_heading_word_geometry(pdf,phase)
                        size=float(titles[phase][0])*72/72.27
                        self.assertTrue(all(gap<.7*size for gap in geometry['gaps']),geometry)
                        self.assertTrue(all(not word.endswith('-') for word in geometry['words']),geometry)
                        edges=[(min(word[0] for word in row) if pair[0]=='english'
                            else max(word[2] for word in row)) for row in geometry['rows']]
                        self.assertLess(max(edges)-min(edges),.15,geometry)
                    for token,expected in (('HEADINGCOLUMNBODY',0),('HEADINGMINORITYBODY',1),('HEADINGTHIRDBODY',2)):
                        page,rect=exact_occurrence(pdf,token)
                        self.assertEqual(column_index(pdf[page],rect,3,pair[0]),expected)

    def test_native_counters_stars_navigation_and_theme_font_sizes_survive(self):
        for pair,directory in self.directories.items():
            with self.subTest(language=pair[0],theme=pair[1]):
                aux=(directory/'main.aux').read_text()
                with fitz.open(directory/'main.pdf') as pdf:
                    for label,number,level in (('sec:heading-column','1',1),
                            ('sec:heading-child','1.1',2),('sec:heading-wide','2',1)):
                        fields=label_fields(aux,label)
                        self.assertEqual(fields[1],number)
                        page,_,_=pdf.resolve_link('#nameddest='+fields[4])
                        self.assertGreaterEqual(page,0)
                        links=[(p,link) for p in pdf for link in p.get_links()
                            if link.get('nameddest')==fields[4]]
                        self.assertEqual(len(links),1)
                        self.assertIn(number,reference_string(*links[0]))
                    self.assertEqual([row[0] for row in pdf.get_toc()],[1,2,1])
                if pair[0]=='english' and pair[1] in self.negative:
                    current=reference_heading_probes((directory/'pass-3.txt').read_text(),'TITLE')
                    old=reference_heading_probes((self.negative[pair[1]]/'pass-3.txt').read_text(),'TITLE')
                    self.assertEqual({role:values[:2] for role,values in current.items()},
                                     {role:values[:2] for role,values in old.items()},
                                     'native theme heading font size and baseline must not change')
                    def math_faces(path):
                        with fitz.open(path/'main.pdf') as pdf:
                            region=reference_heading_word_geometry(pdf,'CHILD')
                            traces=pdf[region['page']-1].get_texttrace()
                            faces=[(trace['font'],round(trace['size'],5),len(trace['chars']))
                                for trace in traces if fitz.Rect(region['region']).contains(fitz.Rect(trace['bbox']))
                                and trace['font'].startswith(('CM','MSAM','MSBM'))]
                            self.assertTrue(faces,'actual nested heading mathematics is missing')
                            self.assertGreaterEqual(len({face[1] for face in faces}),3,
                                'nested heading math must retain three real script tiers')
                            return sorted(faces)
                    self.assertEqual(math_faces(directory),math_faces(self.negative[pair[1]]),
                        'reading-edge setup must preserve actual heading math faces and point sizes')

    def test_genuine_old_justified_headings_are_rejected_by_the_same_policy(self):
        for theme,directory in self.negative.items():
            with self.subTest(theme=theme):
                with self.assertRaises(AssertionError):
                    self.assert_scoped_heading_policy(directory)
                with fitz.open(directory/'main.pdf') as pdf:
                    old=reference_heading_word_geometry(pdf,'COLUMN')
                size=float(reference_heading_probes((directory/'pass-3.txt').read_text(),'TITLE')['COLUMN'][0])*72/72.27
                self.assertTrue(any(gap>=.7*size for gap in old['gaps'])
                    or any(word.endswith('-') for word in old['words']),
                    'negative must actually show stretched word gaps or automatic splits: '+str(old))


if __name__ == '__main__':
    unittest.main(verbosity=2)
