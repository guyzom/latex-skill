#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Original project code; scope and terms: ../LICENSING.md.
"""Real-engine controls for protected code, painted parentheses and reader semantics."""
from __future__ import annotations
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
sys.dont_write_bytecode = True
import fitz
from check_pdf_render import mirrored_paren_digits
from font_paths import font_dir
ROOT=Path(__file__).resolve().parent.parent

MATRIX=r'''\def\lakitdocumentclass{article}
\input{preamble.tex}
\hypersetup{pdftitle={Code alignment matrix},pdfauthor={QA}}
\begin{document}
\section{בדיקת \code{I[23:20]}}
טקסט עם \code{arr[i]}.
\[\begin{aligned}\code{A}&=1\\\texttt{B}&=2\end{aligned}\]
\begin{align*}\code{A}&=1\\\texttt{B}&=2\end{align*}
\[\begin{array}{cc}\code{A}&1\\\texttt{B}&2\end{array}\]
\[\begin{cases}\code{A}& x>0\\\texttt{B}&x\leq0\end{cases}\]
\begin{equation}\begin{split}\code{A}&=1\\\texttt{B}&=2\end{split}\end{equation}
\[\begin{pmatrix}\code{A}&1\\\texttt{B}&2\end{pmatrix}\]
\[\code{A}+\texttt{B}\]
בדיקה בשורה: $\code{A}+\texttt{B}$
ממשיכים בעברית.
\end{document}
'''
READER=r'''\def\lakitdocumentclass{article}
\input{preamble.tex}
\input{document_components.tex}
\input{reader_theme.tex}
\hypersetup{pdftitle={Reader runtime controls},pdfauthor={QA}}
\begin{document}
\section{בדיקת מסמך}
\begin{exbox}[frametitle={כותרת נשמרת}]
תוכן הדוגמה נשמר, ואין כאן תוספת של פתרון אוטומטי.
\end{exbox}
\textbf{(1)} \textbf{(2)}
\sourcelink{https://example.org/probe}{קישור לבדיקה}{מקור הדגמה בלבד.}
\begin{englishprose}
\begin{exbox}[frametitle={TITLE-PRESERVED}]
BODY-PRESERVED
\end{exbox}
\end{englishprose}
\end{document}
'''


class Runtime480Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='hllpdf-480-runtime-'); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        for f in ['preamble.tex','reader_theme.tex','document_components.tex']:
            shutil.copyfile(ROOT/'assets'/f,self.root/f)
        self.env=os.environ.copy()
        fonts=str(font_dir())
        self.env.update(HEBREW_LATEX_FONT_DIR=fonts,OSFONTDIR=fonts,TTFONTS=fonts+'//:',
                        PYTHONDONTWRITEBYTECODE='1',SOURCE_DATE_EPOCH='1700000000',
                        HEBREW_LATEX_PROJECT_ROOT=str(self.root))

    def compile(self,text,name='main'):
        (self.root/(name+'.tex')).write_text(text,encoding='utf-8')
        for _ in range(2):
            p=subprocess.run(['lualatex','--no-shell-escape','-halt-on-error','-interaction=nonstopmode',name+'.tex'],
                             cwd=self.root,env=self.env,capture_output=True,text=True,timeout=90)
            if p.returncode: return p
        return p

    def test_code_all_alignment_contexts_and_heading(self):
        p=self.compile(MATRIX); self.assertEqual(p.returncode,0,p.stdout[-3000:])
        with fitz.open(self.root/'main.pdf') as d:
            self.assertIn('I[23:20]',d.get_toc()[0][1])
            text=''.join(page.get_text() for page in d)
            self.assertGreaterEqual(text.count('A'),8)
            self.assertGreaterEqual(text.count('B'),8)

    def test_removing_protection_reproduces_original_crash(self):
        path=self.root/'preamble.tex'; text=path.read_text()
        changed=text.replace(r'\protected\long\def\code#1',r'\long\def\code#1')
        self.assertNotEqual(text,changed); path.write_text(changed)
        p=self.compile(r'\input{preamble.tex}\begin{document}\[\begin{aligned}\code{A}&=1\end{aligned}\]\end{document}')
        self.assertNotEqual(p.returncode,0)
        self.assertIn('invalid in math mode',p.stdout)

    def test_reader_preserves_title_link_and_actual_parenthesis_glyphs(self):
        p=self.compile(READER); self.assertEqual(p.returncode,0,p.stdout[-3000:])
        with fitz.open(self.root/'main.pdf') as d:
            self.assertEqual(len(d),1)
            page=d[0]; text=page.get_text()
            self.assertEqual(text.count('TITLE-PRESERVED'),1)
            self.assertEqual(text.count('BODY-PRESERVED'),1)
            # No exam-style synthetic "solution" suffix. Hebrew extraction can
            # reverse runs, so test both logical and visual strings.
            self.assertNotIn('פתרון:',text); self.assertNotIn(':ןורתפ',text)
            self.assertIn('https://example.org/probe',[l.get('uri') for l in page.get_links()])
            self.assertEqual(list(mirrored_paren_digits(page)),[])
            # Both exboxes share one exact accent colour; their solid thin
            # rectangles reveal PHYSICAL placement independent of Unicode.
            bars=[]
            for drawing in page.get_drawings():
                rect=drawing['rect']; fill=drawing.get('fill')
                if fill and max(abs(a-b) for a,b in zip(fill,(87/255,68/255,101/255)))<.015 and 1<rect.width<5 and rect.height>15:
                    bars.append(rect)
            self.assertEqual(len(bars),2,[tuple(b) for b in bars])
            bars.sort(key=lambda r:r.y0)
            self.assertGreater(bars[0].x0,page.rect.width/2,'Hebrew accent must be physically right')
            self.assertLess(bars[1].x0,page.rect.width/2,'English accent must be physically left')

    def test_truly_reversed_parentheses_still_fail(self):
        with fitz.open() as d:
            p=d.new_page();p.insert_text((70,70),')12(');p.insert_text((70,100),')A.1(')
            self.assertEqual(len(list(mirrored_paren_digits(p))),2)
        with fitz.open() as d:
            p=d.new_page();p.insert_text((70,70),'(12)')
            self.assertEqual(list(mirrored_paren_digits(p)),[])

    def _default_font_fixture(self):
        # Simulate a home inside the disposable tree without changing HOME or
        # installing files in the user's actual account. Explicit font binding
        # still loads the real, pinned collection through this directory link.
        home = self.root/'home'
        target = home/'.local/share/fonts/hebrew-lualatex-pdf'
        target.parent.mkdir(parents=True)
        target.symlink_to(font_dir(), target_is_directory=True)
        return (r'\directlua{local realgetenv=os.getenv; os.getenv=function(key) '
                'if key=="HOME" then return "'+str(home)+'" end; return realgetenv(key) end}\n'
                r'\def\lakitdocumentclass{article}'+'\n'
                r'\def\lakitlanguageprofile{english}'+'\n'
                r'\input{preamble.tex}\begin{document}FONT-PATH-CONTROL\end{document}')

    def test_direct_engine_empty_or_relative_xdg_uses_default_font_path(self):
        fixture = self._default_font_fixture()
        self.env['HEBREW_LATEX_FONT_DIR'] = ''
        for index, xdg in enumerate(('', 'relative-data')):
            with self.subTest(xdg=xdg):
                self.env['XDG_DATA_HOME'] = xdg
                p = self.compile(fixture, name='xdg'+str(index))
                self.assertEqual(p.returncode, 0, p.stdout[-3000:])
                with fitz.open(self.root/('xdg'+str(index)+'.pdf')) as document:
                    self.assertIn('FONT-PATH-CONTROL', document[0].get_text())

    def test_old_relative_xdg_branch_reproduces_missing_directory(self):
        fixture = self._default_font_fixture()
        path = self.root/'preamble.tex'
        core = path.read_text()
        changed = core.replace(' or not (data:sub(1,1) == "/")', '')
        self.assertNotEqual(changed, core)
        path.write_text(changed)
        self.env.update(HEBREW_LATEX_FONT_DIR='', XDG_DATA_HOME='relative-data')
        p = self.compile(fixture)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn('font directory is missing', p.stdout)


if __name__=='__main__': unittest.main(verbosity=2)
