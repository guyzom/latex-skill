#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Original project code; scope and terms: ../LICENSING.md.
"""Real LuaLaTeX controls for four Unicode smart quotes inside listings.

HLLPDF_421_EVIDENCE_DIR keeps sources, logs, expected streams and measured
positions in a NEW directory outside the skill. Negative controls remove the
marked fix from a private preamble; they are diagnostic, not deliverable PDFs.
No fonts or external TeX packages are copied to the evidence output.
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
from listing_text_probe import probe

ROOT = Path(__file__).resolve().parent.parent
PATCH_RE = r'\n% <hllpdf:listing-smart-quotes>\n.*?% </hllpdf:listing-smart-quotes>\n'
STYLES = ('asm','cstyle','pystyle','htmlstyle')
SAMPLES = (
    r'\en{“alpha beta gamma delta epsilon”}',
    r'\en {‘alpha beta gamma delta epsilon’}',
    'x="smart “double” in string";',
    "x='smart ‘single’ in string';",
    '# don’t reverse a user’s apostrophe',
    'x={“alpha”}; y=[‘beta’]; z=“”;',
    '‘alpha’“beta”',
    '# “outer ‘inner’ close”',
)
HEADER = r'''\def\lakitdocumentclass{article}
\def\lakitclassoptions{11pt,a4paper}
\input{preamble.tex}
\hypersetup{pdftitle={בדיקת מירכאות בקוד},pdfauthor={Synthetic QA}}
'''
CATS = r'\typeout{HLLPDF-CATS:\the\catcode"2018,\the\catcode"2019,\the\catcode"201C,\the\catcode"201D}'


def listing(lines: list[str], options: str = 'style=pystyle') -> str:
    return ('\\begin{asmblock}\n\\begin{lstlisting}['+options+']\n'
            +'\n'.join(lines)+'\n\\end{lstlisting}\n\\end{asmblock}\n')


def document(body: str, extra: str = '') -> str:
    return HEADER + extra + '\n\\begin{document}\n'+CATS+'\n'+body+'\n'+CATS+'\n\\end{document}\n'


def matrix(theme: str) -> tuple[str, list[str]]:
    head = HEADER
    if theme == 'reader':
        head = head.replace('{article}','{report}').replace('{11pt,a4paper}','{12pt,a4paper}')
    elif theme == 'clean':
        head = head.replace('{11pt,a4paper}','{12pt,a4paper}')
    if theme != 'default':
        head += '\\input{'+theme+'_theme.tex}\n'
    body = ''; expected = []
    for idx, style in enumerate(STYLES):
        body += '\\section{בדיקת סגנון \\en{'+style+'}}\n'
        for boxed in (False, True):
            lines = [f'Q{idx*16 + (8 if boxed else 0)+i:02d} '+s for i,s in enumerate(SAMPLES,1)]
            expected.extend(lines)
            block = listing(lines, 'style='+style)
            if boxed:
                block = '\\begin{codebox}[nobreak=true,frametitle={\\en{sample.txt}}]\n'+block+'\\end{codebox}\n'
            body += block
        body += '\\clearpage\n'
    return head+'\\begin{document}\n'+CATS+'\n'+body+CATS+'\n\\end{document}\n', expected


class RuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        chosen = os.environ.get('HLLPDF_421_EVIDENCE_DIR')
        if chosen:
            cls.root = Path(chosen).resolve()
            if cls.root == ROOT or ROOT in cls.root.parents:
                raise ValueError('evidence directory must be outside the skill')
            cls.root.mkdir(parents=True, exist_ok=False)
        else:
            cls.tmp = tempfile.TemporaryDirectory(prefix='hllpdf-421-runtime-')
            cls.root = Path(cls.tmp.name)
        fonts = str(font_dir())
        cls.env = {**os.environ, 'HEBREW_LATEX_FONT_DIR':fonts, 'OSFONTDIR':fonts+':',
                   'TTFONTS':fonts+':', 'SOURCE_DATE_EPOCH':'1700000000', 'TZ':'UTC',
                   'PYTHONDONTWRITEBYTECODE':'1'}
        cls.results = {}; cls.sources = {}
        for theme in ('default','reader','clean'):
            src, lines = matrix(theme)
            cls.compile('matrix-'+theme,src,lines)
        src, lines = matrix('default')
        cls.compile('mutation-no-registration',src,lines,mutation=True)
        simple = ['S'+str(i)+' '+s for i,s in enumerate(SAMPLES,1)]
        cls.compile('extended-false',document(listing(simple,'style=pystyle,extendedchars=false')),simple)
        mapping = r'\lstset{literate={“}{{[DL]}}4 {”}{{[DR]}}4 {‘}{{[SL]}}4 {’}{{[SR]}}4}'
        translated = [s.translate(str.maketrans({'“':'[DL]','”':'[DR]','‘':'[SL]','’':'[SR]'})) for s in simple]
        cls.compile('explicit-literate',document(listing(simple),mapping),translated)
        delim = ['D01 alpha “beta gamma” omega', 'D02 alpha ‘delta epsilon’ omega']
        cls.compile('explicit-delimiters',document(listing(delim,'style=pystyle,morestring={[s]{“}{”}},morestring={[s]{‘}{’}}')),delim)
        cls.compile('external-file',document('\\begin{asmblock}\n\\lstinputlisting[style=pystyle]{sample.txt}\n\\end{asmblock}'),simple,external='\n'.join(simple)+'\n')
        long = [f'L{i:03d} # “alpha beta” ‘gamma’' for i in range(1,101)]
        cls.compile('long-pages',document(listing(long),r'\lakithead{בדיקת קוד ארוך}\fancyhead[L]{\en{\mbox{“HEADER”}}}'),long)
        wrap = [f'W{i:02d} '+('“alpha beta gamma” ‘delta epsilon’ '*7)+f'end{i:02d}' for i in range(1,5)]
        body = '\\begin{minipage}{190pt}\n'+listing(wrap,'style=pystyle,breaklines=true,breakatwhitespace=true')+'\\end{minipage}'
        cls.compile('wrapped-lines',document(body),wrap)
        escape = [r'E01 (*@\textbf{“alpha” ‘beta’}@*) omega', r'E02 (*@\textbf{“gamma” ‘delta’}@*) end']
        cls.compile('latex-escape',document(listing(escape,'style=pystyle,escapeinside={(*@}{@*)}')),['E01 “alpha” ‘beta’ omega','E02 “gamma” ‘delta’ end'])
        active_body = r'''\begingroup
\catcode"201D=13\relax
\def”{\char"201D\relax}
\let\SavedSmartQuote=”
'''+listing(['A01 “alpha beta”'])+r'''
\ifnum\catcode"201D=13\relax\else\errmessage{SMART QUOTE CATCODE LEAK}\fi
\ifx”\SavedSmartQuote\else\errmessage{SMART QUOTE MEANING LEAK}\fi
\endgroup
'''
        cls.compile('active-scope',document(active_body),['A01 “alpha beta”'])
        ascii_lines = ['# ASCII unchanged', 'def parser(line):', '    return line.split(",")',
                       'x = {"key": [1, 2, 3]}', "s = 'apostrophe'", '\t# tab follows source semantics']
        inline_body = r'''\begin{otherlanguage}{english}
\noindent\lstinline[style=pystyle]|“alpha beta”|\par
\noindent\lstinline[style=pystyle]{‘gamma delta’}\par
\end{otherlanguage}'''
        cls.compile('inline-forms',document(inline_body),['“alpha beta”','‘gamma delta’'])
        prose = r'''\begin{otherlanguage}{english}
Normal prose: “double quotes” and ‘single quotes’ remain native text.
\end{otherlanguage}
'''
        ascii_src = document(prose+listing(ascii_lines))
        cls.compile('ascii-after',ascii_src,ascii_lines)
        cls.compile('ascii-before',ascii_src,ascii_lines,mutation=True)
        (cls.root/'summary.json').write_text(json.dumps({k:{x:v for x,v in r.items() if x!='glyphs'} for k,r in cls.results.items()},ensure_ascii=False,indent=2)+'\n')

    @classmethod
    def compile(cls, name: str, source: str, expected: list[str], *, mutation: bool = False, external: str | None = None):
        directory = cls.root/name; directory.mkdir()
        core = (ROOT/'assets/preamble.tex').read_text()
        if mutation:
            core,n = re.subn(PATCH_RE,'\n',core,flags=re.S)
            if n != 1:
                raise ValueError('negative control must remove exactly one patch block')
        (directory/'preamble.tex').write_text(core)
        for fn in ('reader_theme.tex','clean_theme.tex'):
            shutil.copyfile(ROOT/'assets'/fn,directory/fn)
        (directory/'main.tex').write_text(source)
        (directory/'expected.json').write_text(json.dumps({'lines':expected,'font_contains':'DejaVuSansMono'},ensure_ascii=False,indent=2)+'\n')
        if external is not None:
            (directory/'sample.txt').write_text(external)
        for num in (1,2):
            result = subprocess.run(['lualatex','--no-shell-escape','-interaction=nonstopmode','-halt-on-error','-file-line-error','main.tex'],
                                    cwd=directory,env=cls.env,text=True,capture_output=True,timeout=120)
            (directory/f'pass-{num}.txt').write_text(result.stdout+result.stderr)
            if result.returncode:
                raise RuntimeError(f'{name}: pass {num} failed: {result.stdout[-1600:]}')
        result = probe(directory/'main.pdf', expected)
        cls.results[name] = result; cls.sources[name] = source
        (directory/'glyphs.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls,'tmp'):
            cls.tmp.cleanup()

    def assert_case(self, name: str):
        r = self.results[name]
        self.assertTrue(r['match'], f'{name}: mismatch at {r["first_mismatch"]}: {r["actual"][:350]}')

    def test_01_all_styles_unboxed_boxed_default(self):
        self.assert_case('matrix-default'); self.assertEqual(self.results['matrix-default']['pages'],4)

    def test_02_reader_report_12pt(self):
        self.assert_case('matrix-reader'); self.assertEqual(self.results['matrix-reader']['pages'],4)

    def test_03_clean_article_12pt(self):
        self.assert_case('matrix-clean'); self.assertEqual(self.results['matrix-clean']['pages'],4)

    def test_04_removing_real_fix_restores_wrong_order(self):
        r = self.results['mutation-no-registration']
        self.assertFalse(r['match'])
        for quote in '‘’“”':
            self.assertEqual(r['expected'].count(quote),r['actual'].count(quote))
        self.assertEqual(len(r['expected']),len(r['actual']))

    def test_05_extendedchars_false_does_not_disable_smart_quotes(self):
        self.assert_case('extended-false')

    def test_06_explicit_user_literate_mapping_wins(self):
        self.assert_case('explicit-literate')

    def test_07_custom_delimiters_still_work(self):
        self.assert_case('explicit-delimiters')
        with fitz.open(self.root/'explicit-delimiters/main.pdf') as d:
            spans = [s for b in d[0].get_text('dict')['blocks'] for l in b.get('lines',[]) for s in l['spans']]
            colored = [s for s in spans if s['color'] != 0 and 'beta' in s['text']]
            self.assertTrue(colored, 'custom curly-delimited string must retain syntax style')

    def test_08_external_file_preserves_glyphs(self):
        self.assert_case('external-file')

    def test_09_long_listing_still_splits_with_all_100_lines(self):
        self.assert_case('long-pages')
        self.assertGreaterEqual(self.results['long-pages']['pages'],2)
        with fitz.open(self.root/'long-pages/main.pdf') as d:
            self.assertTrue(all('HEADER' in p.get_text() for p in d))

    def test_10_wrapped_lines_keep_all_source_glyphs_in_order(self):
        self.assert_case('wrapped-lines')
        glyphs = self.results['wrapped-lines']['glyphs']
        baselines = {(g['page'], round(g['origin'][1],1)) for g in glyphs}
        self.assertGreater(len(baselines),4)

    def test_11_latex_escape_keeps_its_language_semantics(self):
        self.assert_case('latex-escape')

    def test_12_active_catcode_and_meaning_restored(self):
        self.assert_case('active-scope')

    def test_13_no_quote_catcode_leak_after_listings(self):
        for name in self.results:
            log = (self.root/name/'main.log').read_text(errors='replace')
            self.assertEqual(re.findall(r'HLLPDF-CATS:([^\n]+)',log),['12,12,12,12','12,12,12,12'],name)

    def test_14_ascii_pixels_unchanged(self):
        self.assert_case('ascii-after'); self.assert_case('ascii-before')
        with fitz.open(self.root/'ascii-before/main.pdf') as a, fitz.open(self.root/'ascii-after/main.pdf') as b:
            self.assertEqual(len(a),len(b))
            for p,q in zip(a,b):
                x=p.get_pixmap(dpi=144,alpha=False); y=q.get_pixmap(dpi=144,alpha=False)
                self.assertEqual((x.width,x.height,x.samples),(y.width,y.height,y.samples))

    def test_15_no_missing_glyphs_or_overfulls(self):
        for name in self.results:
            log=(self.root/name/'main.log').read_text(errors='replace')
            self.assertNotIn('Missing character:',log,name)
            self.assertNotIn('Overfull',log,name)

    def test_16_inline_delimiter_and_brace_forms(self):
        self.assert_case('inline-forms')


if __name__ == '__main__':
    unittest.main(verbosity=2)
