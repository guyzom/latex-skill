#!/usr/bin/env python3
"""Actual glyph order, language, paragraph seams and semantic reference targets.

Set HLLPDF_REFERENCE_EVIDENCE to a new empty directory to retain sources, engine
logs and PDFs. The fixtures are synthetic controls, not scientific sources.
"""
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
from check_pdf_render import _visible_parenthesis_overrides, mirrored_paren_digits
ROOT = Path(__file__).resolve().parent.parent


def equation_dest(doc):
    """The single equation destination these fixtures link to.

    hyperref -- not this preamble -- derives a destination's NAME from
    \\theH<counter>, and that derivation differs between engine releases: where
    the equation counter is not reset by the sectioning level, one hyperref
    emits `equation.12` and another prefixes the section for uniqueness
    (`equation.2.12`). Measured: neither the v4.7.x nor the v4.11.x preamble
    defines \\theHequation at all, and forcing hyperref's unprefixed default
    turns one form into the other with no other change. Pinning the literal
    name therefore tested the installed hyperref, not this package, and failed
    on TeX Live 2023 while every substantive property below still held.
    The fixtures carry exactly one numbered equation, so deriving the name
    keeps the real assertions (link count, target page, rendered text,
    no mirrored parentheses) and drops the version coupling.
    """
    names = {ln.get('nameddest') for page in doc for ln in page.get_links()
             if (ln.get('nameddest') or '').startswith('equation.')}
    if len(names) != 1:
        raise AssertionError(f'expected exactly one equation destination, got {sorted(names)}')
    return names.pop()
HEADER = r'''\def\lakitdocumentclass{article}
\def\lakitclassoptions{11pt,a4paper}
\def\lakitgeometryoptions{margin=2.2cm,headheight=14pt}
\def\lakitlinespread{1.12}
\input{preamble.tex}
\hypersetup{pdftitle={Bilingual reference controls},pdfauthor={Synthetic QA}}
'''
BODY = r'''\begin{document}
\section{בדיקת הפניות דו־לשונית}
\noindent\en{HREF} ראו \eqref{eq:target}, \autoref{tbl:target}, \autoref{fig:target}, \autopageref{tbl:target}.
\par
\noindent\en{HEBSTART} זו שורה עברית לפני המעבר ללא שורה ריקה.
\begin{englishprose}
\noindent ENSTART This starts a new paragraph at the physical left margin.
\par
\noindent EREF See \eqref{eq:target}, \autoref{tbl:target}, \autoref{fig:target}, \autopageref{tbl:target}.
\end{englishprose}
\noindent\en{HEBAFTER} ראו שוב \autoref{tbl:target} ו־\autopageref{tbl:target}.
\begin{equation}y=\text{\eqref{eq:target}}\end{equation}
\begin{align}y&=\text{\eqref{eq:target}}\end{align}
\begin{gather}y=\text{\eqref{eq:target}}\end{gather}
\begin{multline}y=\text{\eqref{eq:target}}\end{multline}
\begin{alignat}{1}y&=\text{\eqref{eq:target}}\end{alignat}
\begin{flalign}y&=\text{\eqref{eq:target}}&&\end{flalign}
\[y=\text{\eqref{eq:target}}\]
\noindent\en{INLINE} ערך $y=\text{\eqref{eq:target}}$ כאן.
הפניה בהערת שוליים\footnote{ראו \eqref{eq:target}.}.
\clearpage
\section{יעדים נפרדים}
\setcounter{equation}{11}
\begin{equation}\label{eq:target}E=mc^2\end{equation}
\noindent\en{EQUATION-TARGET}
\begin{tablebox}\centering
\begin{tabular}{ll}\toprule\en{Value}&\en{ID}\\\midrule\en{12}&\en{A}\\\bottomrule\end{tabular}
\tabcap{\label{tbl:target}טבלת בדיקה סינתטית}
\end{tablebox}
\noindent\en{TABLE-TARGET}
\begin{tikzpic}\begin{tikzpicture}\node[draw]{\h{בדיקה}};\end{tikzpicture}\end{tikzpic}
\figcap{\label{fig:target}איור בדיקה סינתטי}
\noindent\en{FIGURE-TARGET}
\end{document}
'''
SELECTIVE = r'''\mathtoolsset{showonlyrefs=true,showmanualtags=false}
\begin{document}
\section{מספור למאוזכרות}
\begin{align}a&=1\label{eq:a}\\b&=2\label{eq:unused}\end{align}
\noindent\en{SELECT}\quad\eqref{eq:a}.
\begin{align}\tag{A.12}c&=\text{\eqref{eq:a}}\label{eq:manual}\end{align}
\noindent\en{MANUAL}\quad\eqref{eq:manual}.
\mathtoolsset{showonlyrefs=false}
\begin{equation}d=\text{\eqref{eq:a}}\label{eq:d}\end{equation}
\noindent\en{BACK}\quad\eqref{eq:d}.
\end{document}
'''


def line_text(page, marker):
    hit = page.search_for(marker)[0]
    return page.get_textbox(fitz.Rect(0, hit.y0-1, page.rect.width, hit.y1+1))


def reference_string(page, link):
    """Physical left-to-right glyphs near one actual link, including delimiters."""
    overrides = _visible_parenthesis_overrides(page)
    r = link['from']
    chars = []
    for block in page.get_text('rawdict')['blocks']:
        for line in block.get('lines', []):
            for span in line['spans']:
                for ch in span['chars']:
                    box = fitz.Rect(ch['bbox']); ox, oy = ch['origin']; c = ch['c']
                    if r.y0 - .2 <= oy <= r.y1 + .2 and r.x0-6 <= box.x0 and box.x1 <= r.x1+6:
                        if c in '()': c = overrides.get((ord(c),round(ox,3),round(oy,3)),c)
                        chars.append((ox,c))
    return ''.join(c for _,c in sorted(chars)).replace(' ','')


class ReferenceRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        evidence = os.environ.get('HLLPDF_REFERENCE_EVIDENCE')
        cls.tmp = None
        if evidence:
            cls.root = Path(evidence).resolve(); cls.root.mkdir(parents=True, exist_ok=True)
            if any(cls.root.iterdir()): raise ValueError('reference evidence directory must be empty')
        else:
            cls.tmp = tempfile.TemporaryDirectory(prefix='hllpdf-references-')
            cls.root = Path(cls.tmp.name)
        fonts=str(font_dir()); cls.env=os.environ.copy()
        cls.env.update(OSFONTDIR=fonts,TTFONTS=fonts+'//:',HEBREW_LATEX_FONT_DIR=fonts,
                       SOURCE_DATE_EPOCH='1700000000',TZ='UTC',PYTHONDONTWRITEBYTECODE='1')
        cls.env.pop('HEBREW_LATEX_PROJECT_ROOT',None)
        cls.base=(ROOT/'assets/preamble.tex').read_text()
        cls.standard=cls.compile('standard',HEADER+BODY)

    @classmethod
    def tearDownClass(cls):
        if cls.tmp: cls.tmp.cleanup()

    @classmethod
    def compile(cls,name,source,preamble=None,passes=3):
        d=cls.root/name; d.mkdir()
        (d/'preamble.tex').write_text(cls.base if preamble is None else preamble)
        (d/'main.tex').write_text(source)
        for i in range(passes):
            p=subprocess.run(['lualatex','--no-shell-escape','-halt-on-error','-interaction=nonstopmode','main.tex'],
                             cwd=d,env=cls.env,capture_output=True,text=True,timeout=120)
            (d/f'pass-{i+1}.txt').write_text(p.stdout+p.stderr)
            if p.returncode: break
        if p.returncode: raise AssertionError(f'{name}: {p.stdout[-3000:]}')
        if 'undefined references' in p.stdout: raise AssertionError(f'{name}: unresolved references')
        return d

    def check_references(self,path,expected='(12)'):
        with fitz.open(path/'main.pdf') as doc:
            target=equation_dest(doc)
            links=[(page,ln) for page in doc for ln in page.get_links()
                   if ln.get('nameddest')==target]
            self.assertEqual(len(links),11)
            for page,ln in links:
                self.assertEqual(ln.get('page'),1)
                self.assertIn(expected,reference_string(page,ln),reference_string(page,ln))
            for page in doc: self.assertEqual(list(mirrored_paren_digits(page)),[])

    def test_complete_reference_matrix(self):
        with fitz.open(self.standard/'main.pdf') as doc: self.assertEqual(len(doc),2)
        self.check_references(self.standard)

    def test_english_paragraph_seam_is_real_not_an_inline_language_switch(self):
        with fitz.open(self.standard/'main.pdf') as doc:
            page=doc[0]; eng=page.search_for('ENSTART')[0]; heb=page.search_for('HEBSTART')[0]
            self.assertGreater(eng.y0,heb.y1)
            self.assertLess(eng.x0,70)
            self.assertNotIn('ENSTART',line_text(page,'HEBSTART'))
            self.assertGreater(page.search_for('HEBAFTER')[0].x0,450)

    def test_custom_caption_and_page_names_follow_the_surrounding_language(self):
        with fitz.open(self.standard/'main.pdf') as doc:
            eng=line_text(doc[0],'EREF'); heb=line_text(doc[0],'HREF'); after=line_text(doc[0],'HEBAFTER')
            for text in ['Table 2.1','Figure 2.1','page 2']: self.assertIn(text,eng)
            for text in ['טבלה','איור','עמוד']: self.assertIn(text,heb)
            self.assertIn('טבלה',after);self.assertIn('עמוד',after)
            self.assertNotIn('page',heb+after)
            expected={'tbl.2.1','fig.2.1'}
            self.assertTrue(expected.issubset({ln.get('nameddest') for ln in doc[0].get_links()}))
            names=doc.resolve_names()
            for key in expected: self.assertEqual(names[key]['page'],1)

    def test_square_tag_form_preserves_number_and_actual_link_target(self):
        source=(HEADER+r'\newtagform{square}{[}{]}\usetagform{square}'+'\n'+BODY)
        p=self.compile('square',source)
        self.check_references(p,'[12]')

    def test_alphanumeric_tag_does_not_reverse(self):
        source=HEADER+BODY.replace(r'\setcounter{equation}{11}',r'\setcounter{equation}{11}\renewcommand{\theequation}{A.\arabic{equation}}')
        p=self.compile('alphanumeric',source)
        self.check_references(p,'(A.12)')

    def test_selective_numbering_manual_tags_and_switch_back(self):
        p=self.compile('selective',HEADER+SELECTIVE,passes=4)
        with fitz.open(p/'main.pdf') as doc:
            self.assertEqual(len(doc),1)
            self.assertIn('(1)',line_text(doc[0],'SELECT'))
            self.assertIn('(A.12)',line_text(doc[0],'MANUAL'))
            self.assertIn('(2)',line_text(doc[0],'BACK'))
            text=doc[0].get_text()
            self.assertEqual(text.count('(A.12)'),2)
            self.assertEqual(list(mirrored_paren_digits(doc[0])),[])
        aux=(p/'main.aux').read_text()
        self.assertIn(r'\MT@newlabel{eq:a}',aux)
        self.assertIn(r'\MT@newlabel{eq:manual}',aux)
        self.assertNotIn(r'\MT@newlabel{eq:unused}',aux)
        self.assertRegex(aux,r'\\newlabel\{eq:d\}\{\{2\}')

    def test_starred_autoref_remains_unlinked(self):
        source=HEADER+r'''\begin{document}\section{יעד}\label{sec:a}
\noindent\en{LINKED}\autoref{sec:a}\par
\noindent\en{UNLINKED}\autoref*{sec:a}\par
\begin{englishprose}STAR \autoref*{sec:a}\end{englishprose}\end{document}'''
        p=self.compile('starred',source)
        with fitz.open(p/'main.pdf') as doc:
            self.assertEqual(len(doc[0].get_links()),1)
            self.assertIn('section 1',line_text(doc[0],'STAR'))

    def test_removing_paragraph_boundary_reproduces_shared_baseline(self):
        old=self.base.replace(r'{\par\begin{otherlanguage}{english}\exhyphenpenalty=50\relax}',
                              r'{\begin{otherlanguage}{english}\exhyphenpenalty=50\relax}')
        self.assertNotEqual(old,self.base)
        p=self.compile('no-paragraph-boundary',HEADER+BODY,preamble=old)
        with fitz.open(p/'main.pdf') as doc:
            self.assertIn('ENSTART',line_text(doc[0],'HEBSTART'))

    def test_removing_reference_isolation_reproduces_mirrored_alignment(self):
        old=self.base.replace(r'\protected\def\eqref#1{\HEB@eqrefisolate{\HEB@nativeeqref{#1}}}',
                              r'\protected\def\eqref#1{\HEB@nativeeqref{#1}}')
        self.assertNotEqual(old,self.base)
        p=self.compile('no-isolation',HEADER+BODY,preamble=old)
        with self.assertRaises(AssertionError): self.check_references(p)
        with fitz.open(p/'main.pdf') as doc:
            self.assertTrue(any(list(mirrored_paren_digits(page)) for page in doc))

    def test_direction_only_patch_can_reverse_digits_and_is_rejected(self):
        old=self.base.replace(r'\let\bbl@eqnodir\relax\let\maketag@@@',r'\let\maketag@@@')
        self.assertNotEqual(old,self.base)
        p=self.compile('stale-display-direction',HEADER+BODY,preamble=old)
        with self.assertRaises(AssertionError): self.check_references(p)
        with fitz.open(p/'main.pdf') as doc:
            target=equation_dest(doc)
            strings=[reference_string(page,ln) for page in doc for ln in page.get_links()
                     if ln.get('nameddest')==target]
            self.assertTrue(any('21' in text for text in strings),strings)

    def test_valid_but_wrong_pdf_destination_is_not_accepted(self):
        p=self.root/'wrong-valid-destination';p.mkdir()
        with fitz.open(self.standard/'main.pdf') as doc:
            target=equation_dest(doc)
            link=next(ln for ln in doc[0].get_links() if ln.get('nameddest')==target)
            # a VALID destination that is not the equation's, derived for the
            # same reason as equation_dest: its name is hyperref's to choose.
            other=next(ln.get('nameddest') for page in doc for ln in page.get_links()
                       if (ln.get('nameddest') or '').startswith(('tbl.','fig.')))
            doc.xref_set_key(link['xref'],'A/D',f'({other})')
            doc.save(p/'main.pdf')
        with fitz.open(p/'main.pdf') as doc:
            self.assertTrue(all(ln.get('page',-1)>=0 for ln in doc[0].get_links()))
        with self.assertRaises(AssertionError): self.check_references(p)

    def test_reference_does_not_consume_pending_manual_tag_state(self):
        old=self.base.replace(r'\let\maketag@@@\ORIGmaketag@@@', '')
        self.assertNotEqual(old,self.base)
        p=self.compile('consumed-manual-tag',HEADER+SELECTIVE,preamble=old,passes=4)
        with fitz.open(p/'main.pdf') as doc:
            self.assertNotIn('(2)',line_text(doc[0],'BACK'))
        aux=(p/'main.aux').read_text()
        self.assertNotRegex(aux,r'\\newlabel\{eq:d\}\{\{2\}')

    def test_missing_label_remains_a_production_failure(self):
        p=self.root/'missing';p.mkdir();(p/'preamble.tex').write_text(self.base)
        (p/'main.tex').write_text(HEADER+r'\begin{document}חסר \eqref{eq:missing}.\end{document}')
        run=subprocess.run(['bash',str(ROOT/'scripts/build.sh'),str(p/'main.tex')],cwd=p,
                           env=self.env,capture_output=True,text=True,timeout=240)
        (p/'build.txt').write_text(run.stdout+run.stderr)
        self.assertEqual(run.returncode,1,run.stdout[-2000:]);self.assertFalse((p/'main.pdf').exists())
        self.assertIn('eq:missing',run.stdout)


if __name__=='__main__': unittest.main(verbosity=2)
