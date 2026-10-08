#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Original project code; scope and terms: ../LICENSING.md.
r"""Compile original and explicitly repaired PDF-string fixtures with LuaLaTeX.

The negative source deliberately bypasses build.sh to reproduce the defect.
The source/build gate must reject it; a clean PDF is not a visual certificate.
Set HLLPDF_419_EVIDENCE_DIR to a new directory to preserve sources and results.
"""
from __future__ import annotations
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
from render_review import render, verify
ROOT=Path(__file__).resolve().parent.parent
BEFORE=r'''\def\lakitdocumentclass{article}
\def\lakitclassoptions{11pt,a4paper}
\input{preamble.tex}
\hypersetup{pdftitle={שורה ראשונה\\[2pt]שורה שנייה},pdfauthor={Synthetic QA}}
\begin{document}
\section{אלפא\\בטא}
בדיקת מעבר שורה רגיל.
\section{גמא\\[2pt]דלתא}
בדיקת מרווח אחרי מעבר שורה.
\section{אפסילון\\*זטא}
בדיקת מעבר שורה ללא פיצול עמוד.
\section{אטא\\*[2pt]תטא}
בדיקת שילוב אפשרויות.
\section[קצר תקין]{יוטא\\[2pt]קפא}
בדיקת הכותרת הקצרה.
\section{\texorpdfstring{למבדא\\*[2pt]מיו}{למבדא מיו}}
בדיקת בידוד המטא נתונים מן התצוגה.
\clearpage\tableofcontents
\end{document}
'''
AFTER=BEFORE.replace(r'pdftitle={שורה ראשונה\\[2pt]שורה שנייה}',r'pdftitle={שורה ראשונה שורה שנייה}')
for old,clean in [(r'גמא\\[2pt]דלתא','גמא דלתא'),(r'אפסילון\\*זטא','אפסילון זטא'),(r'אטא\\*[2pt]תטא','אטא תטא')]:
    AFTER=AFTER.replace('\\section{'+old+'}',r'\section{\texorpdfstring{'+old+'}{'+clean+'}}')
EXPECTED=['אלפא בטא','גמא דלתא','אפסילון זטא','אטא תטא','קצר תקין','למבדא מיו']

class RuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        chosen=os.environ.get('HLLPDF_419_EVIDENCE_DIR')
        if chosen:
            cls.root=Path(chosen).absolute(); cls.root.mkdir(parents=True,exist_ok=False)
        else:
            cls.tmp=tempfile.TemporaryDirectory(prefix='hllpdf-419-runtime-'); cls.root=Path(cls.tmp.name)
        cls.env=os.environ.copy(); fonts=str(font_dir())
        cls.env.update(OSFONTDIR=fonts+':',TTFONTS=fonts+':',HEBREW_LATEX_FONT_DIR=fonts,
                       SOURCE_DATE_EPOCH='1700000000',PYTHONDONTWRITEBYTECODE='1',TZ='UTC')
        cls.results={}
        for name,source in [('before',BEFORE),('after',AFTER)]:
            d=cls.root/name; d.mkdir(); (d/'main.tex').write_text(source,encoding='utf-8')
            shutil.copyfile(ROOT/'assets/preamble.tex',d/'preamble.tex')
            for n in range(1,4):
                result=subprocess.run(['lualatex','--no-shell-escape','-interaction=nonstopmode',
                                       '-halt-on-error','-file-line-error','main.tex'],cwd=d,env=cls.env,
                                      text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=120)
                (d/f'pass-{n}.txt').write_text(result.stdout)
                if result.returncode: raise RuntimeError(f'{name}: pass {n}: {result.stdout[-2000:]}')
            with fitz.open(d/'main.pdf') as doc:
                cls.results[name]={'pages':len(doc),'metadata':doc.metadata,'bookmarks':doc.get_toc(),
                                   'links':[[{'page':link.get('page'),'nameddest':link.get('nameddest'),
                                             'from':list(link['from'])} for link in p.get_links()] for p in doc]}
        (cls.root/'measurements.json').write_text(json.dumps(cls.results,ensure_ascii=False,indent=2)+'\n')
    @classmethod
    def tearDownClass(cls):
        if hasattr(cls,'tmp'): cls.tmp.cleanup()
    def test_original_leaks_optional_and_star_syntax(self):
        actual=[x[1] for x in self.results['before']['bookmarks']]
        self.assertEqual(actual,['אלפא בטא','גמא [2pt]דלתא','אפסילון *זטא','אטא *[2pt]תטא','קצר תקין','למבדא מיו'])
        self.assertEqual(self.results['before']['metadata']['title'],'שורה ראשונה [2pt]שורה שנייה')
    def test_repair_cleans_bookmarks_and_metadata(self):
        self.assertEqual([x[1] for x in self.results['after']['bookmarks']],EXPECTED)
        self.assertEqual(self.results['after']['metadata']['title'],'שורה ראשונה שורה שנייה')
    def test_page_content_pixels_unchanged(self):
        equality=[]
        with fitz.open(self.root/'before/main.pdf') as old, fitz.open(self.root/'after/main.pdf') as new:
            self.assertEqual(len(old),2); self.assertEqual(len(new),2)
            for p,q in zip(old,new):
                a=p.get_pixmap(dpi=144,alpha=False); b=q.get_pixmap(dpi=144,alpha=False)
                same=(a.width,a.height,a.n,a.samples)==(b.width,b.height,b.n,b.samples)
                equality.append({'page':p.number+1,'same_pixels':same,'dpi':144,'renderer':'mupdf'})
                self.assertTrue(same)
        (self.root/'visible-pixel-equivalence.json').write_text(json.dumps(equality,indent=2))
    def test_no_navigation_displacement(self):
        for name in ('before','after'):
            self.assertEqual([x[2] for x in self.results[name]['bookmarks']],[1]*6)
        self.assertEqual(self.results['before']['links'],self.results['after']['links'])
    def test_real_source_gate_negative_and_positive(self):
        for name,rc in [('before',1),('after',0)]:
            result=subprocess.run([sys.executable,str(ROOT/'scripts/check_source_hazards.py'),str(self.root/name/'main.tex')],
                                  capture_output=True,text=True,timeout=30)
            (self.root/name/'source-gate.txt').write_text(result.stdout+result.stderr)
            self.assertEqual(result.returncode,rc,result.stdout+result.stderr)
            self.assertEqual(result.stdout.count('[PDFSTRING-LINEBREAK-ARG]'),4 if rc else 0)
    def test_no_missing_glyphs_or_overfull_boxes(self):
        for name in ('before','after'):
            log=(self.root/name/'main.log').read_text()
            for word in ('Missing character:',r'Overfull \hbox',r'Overfull \vbox'):
                self.assertNotIn(word,log)
    def test_two_explicit_backends_and_same_backend_replay(self):
        for name in ('before','after'):
            for backend in ('poppler','mupdf'):
                pdf=self.root/name/'main.pdf'; out=self.root/name/backend
                render(pdf,out,144,backend=backend)
                self.assertEqual(verify(pdf,out/'review.json',require_attestations=False,rerender=True),[])
        # Different engines are not required to produce identical pixels.
if __name__=='__main__': unittest.main(verbosity=2)
