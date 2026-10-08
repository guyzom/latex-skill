#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Original project code; scope and terms: ../LICENSING.md.
"""Real LuaLaTeX controls for heading order, deep references and short code flow.

The old-source mutations are compiled deliberately outside build.sh to measure
bad layout; published documents must use the canonical source/build gates.
Set HLLPDF_418_EVIDENCE_DIR to a NEW empty directory to retain source/log/PDF data.
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
ROOT=Path(__file__).resolve().parent.parent


def formula_metrics(pdf: Path) -> list[dict]:
    rows=[]
    with fitz.open(pdf) as doc:
        for index,page in enumerate(doc):
            wanted={c:[] for c in ['c','n','Z','−','-']}
            for b in page.get_text('rawdict')['blocks']:
                for line in b.get('lines',[]):
                    for span in line['spans']:
                        for char in span['chars']:
                            if char['c'] in wanted: wanted[char['c']].append(char)
            for key in ['c','n','Z']:
                if len(wanted[key])!=1: raise ValueError(f'page {index+1}: {key} anchor count={len(wanted[key])}')
            coords={key: list(wanted[key][0]['origin']) for key in ['c','n','Z']}
            signs=wanted['−']+wanted['-']
            if len(signs)!=1: raise ValueError(f'page {index+1}: connector count={len(signs)}')
            coords['sign']=list(signs[0]['origin'])
            rows.append({'page':index+1,'origins':coords,
                         'physical_order':''.join(key for key in sorted(['c','n','Z'],key=lambda k:coords[k][0])),
                         'sign_between':coords['c'][0]<coords['sign'][0]<coords['Z'][0],
                         'exponent_raised':coords['n'][1]<coords['c'][1]-1})
    return rows


def occurrences(pdf: Path, term: str) -> list[dict]:
    with fitz.open(pdf) as doc:
        return [{'page':i+1,'rect':list(rect)} for i,p in enumerate(doc) for rect in p.search_for(term)]


class RuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        chosen=os.environ.get('HLLPDF_418_EVIDENCE_DIR')
        if chosen:
            cls.root=Path(chosen).absolute()
            cls.root.mkdir(parents=True,exist_ok=False)
        else:
            cls.tmp=tempfile.TemporaryDirectory(prefix='hllpdf-418-runtime-')
            cls.root=Path(cls.tmp.name)
        cls.env=os.environ.copy(); fonts=str(font_dir())
        cls.env.update({'OSFONTDIR':fonts+':','TTFONTS':fonts+':','HEBREW_LATEX_FONT_DIR':fonts,
                        'SOURCE_DATE_EPOCH':'1700000000','PYTHONDONTWRITEBYTECODE':'1'})
        cls.results={}
        for name,size,theme in [('math10',10,''),('math11reader',11,'reader_theme'),
                                ('math12',12,''),('math12clean',12,'clean_theme')]:
            cls.compile(name,cls.math_source(size,theme))
        cls.compile('math-old',cls.math_source(12,'').replace('$c^n-Z$','$c^n$-$Z$'))
        boxes=(ROOT/'assets/example_boxes.tex').read_text()
        cls.compile('code-short',boxes)
        cls.compile('code-old',boxes.replace(r'[nobreak=true,frametitle={\code{parser.py}}]',r'[frametitle={\code{parser.py}}]'))
        long=r'''\input{preamble.tex}
\begin{document}
\begin{codebox}[frametitle={\code{long.py}}]
\begin{asmblock}
\begin{lstlisting}[style=pystyle]
'''+''.join(f'row{i:03d} = {i}\n' for i in range(1,101))+r'''\end{lstlisting}
\end{asmblock}
\end{codebox}
\end{document}
'''
        cls.compile('code-long',long)
        for name,decl in [('deep-hook',r'\def\lakitsecnumdepth{3}'),
                          ('deep-direct',''),('deep-lowered',''),('deep-group','')]:
            source=fr'''\def\lakitdocumentclass{{article}}
{decl}
\input{{preamble.tex}}
\begin{{document}}
'''
            if name=='deep-direct': source+=r'\setcounter{secnumdepth}{3}'
            if name=='deep-lowered': source+=r'\setcounter{secnumdepth}{2}'
            if name=='deep-group': source+=r'{\setcounter{secnumdepth}{3}}'
            source+=r'''\section{ראשי}\subsection{משני}
\subsubsection{כותרת עמוקה}\label{sec:deep}
הפניה: \en{REF=\ref{sec:deep}}.
\end{document}
'''
            cls.compile(name,source)
        (cls.root/'compilation.json').write_text(json.dumps(cls.results,indent=2))

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls,'tmp'): cls.tmp.cleanup()

    @staticmethod
    def math_source(size,theme):
        s=fr'''\def\lakitdocumentclass{{article}}
\def\lakitclassoptions{{{size}pt,a4paper}}
\input{{preamble.tex}}
'''
        if theme: s+=fr'\input{{{theme}.tex}}'+'\n'
        return s+r'''\hypersetup{pdftitle={Heading order control},pdfauthor={Synthetic QA}}
\begin{document}
\section{שער \texorpdfstring{$c^n-Z$}{c\textasciicircum n-Z}}
בדיקת סדר רכיבי הביטוי בכותרת ובתוכן העניינים.
\clearpage\tableofcontents
\end{document}
'''

    @classmethod
    def compile(cls,name,source):
        d=cls.root/name; d.mkdir()
        for fn in ['preamble.tex','reader_theme.tex','clean_theme.tex']:
            shutil.copyfile(ROOT/'assets'/fn,d/fn)
        (d/'main.tex').write_text(source,encoding='utf-8')
        for n in range(1,4):
            result=subprocess.run(['lualatex','--no-shell-escape','-interaction=nonstopmode',
                                   '-halt-on-error','-file-line-error','main.tex'],cwd=d,env=cls.env,
                                  text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=120)
            (d/f'pass-{n}.txt').write_text(result.stdout)
            if result.returncode!=0:
                raise RuntimeError(f'{name}, pass {n}: {result.stdout[-2500:]}')
        log=(d/'main.log').read_text()
        if 'Missing character:' in log: raise RuntimeError(f'{name}: missing glyph')
        if not (d/'main.pdf').is_file(): raise RuntimeError(f'{name}: no PDF')
        with fitz.open(d/'main.pdf') as pdf:
            pages = len(pdf)
        cls.results[name]={'passes':3,'exit':0,'pages':pages,
                           'overfull_hbox':len(re.findall(r'Overfull \\hbox',log)),
                           'overfull_vbox':len(re.findall(r'Overfull \\vbox',log))}
        return d/'main.pdf'

    def pdf(self,name): return self.root/name/'main.pdf'
    def test_math_order_headings_and_contents_four_variants(self):
        for name in ['math10','math11reader','math12','math12clean']:
            rows=formula_metrics(self.pdf(name))
            self.assertEqual(len(rows),2)
            for row in rows:
                self.assertEqual(row['physical_order'],'cnZ',(name,row))
                self.assertTrue(row['sign_between'],(name,row))
                self.assertTrue(row['exponent_raised'],(name,row))
            (self.root/name/'geometry.json').write_text(json.dumps(rows,indent=2))
    def test_missing_formula_anchor_is_rejected(self):
        target=self.root/'missing-anchor.pdf'
        with fitz.open() as doc:
            page=doc.new_page(); page.insert_text((72,72),'cn-')
            doc.save(target)
        with self.assertRaisesRegex(ValueError,'Z anchor count=0'):
            formula_metrics(target)
    def test_ambiguous_formula_anchor_is_rejected(self):
        target=self.root/'ambiguous-anchor.pdf'
        with fitz.open() as doc:
            page=doc.new_page(); page.insert_text((72,72),'cn-Z Z')
            doc.save(target)
        with self.assertRaisesRegex(ValueError,'Z anchor count=2'):
            formula_metrics(target)
    def test_bookmark_formula_identity_four_variants(self):
        for name in ['math10','math11reader','math12','math12clean']:
            with fitz.open(self.pdf(name)) as doc:
                toc=doc.get_toc()
                self.assertEqual(len(toc),1,(name,toc))
                self.assertIn('c^n-Z',toc[0][1],(name,toc))
                self.assertEqual(toc[0][2],1)
    def test_old_math_source_reproduces_visual_order_bug(self):
        rows=formula_metrics(self.pdf('math-old'))
        self.assertEqual(rows[0]['physical_order'],'Zcn',rows)
        (self.root/'math-old'/'geometry.json').write_text(json.dumps(rows,indent=2))
    def test_short_code_title_and_both_lines_stay_together(self):
        fields={term:occurrences(self.pdf('code-short'),term) for term in ['parser.py','parse(line)', 'line.split']}
        for term, hits in fields.items(): self.assertEqual(len(hits),1,(term,hits))
        self.assertEqual(len({hits[0]['page'] for hits in fields.values()}),1,fields)
        self.assertGreater(fields['line.split'][0]['rect'][1],fields['parse(line)'][0]['rect'][1])
        (self.root/'code-short'/'geometry.json').write_text(json.dumps(fields,indent=2))
    def test_old_code_source_reproduces_one_plus_one_split(self):
        a=occurrences(self.pdf('code-old'),'parse(line)'); b=occurrences(self.pdf('code-old'),'line.split')
        self.assertEqual(len(a),1); self.assertEqual(len(b),1)
        self.assertEqual(b[0]['page'],a[0]['page']+1)
        (self.root/'code-old'/'geometry.json').write_text(json.dumps({'first':a,'second':b},indent=2))
    def test_short_code_keeps_line_numbers_inside_frame(self):
        p=subprocess.run([sys.executable,str(ROOT/'scripts/probe_lstnum.py'),str(self.pdf('code-short')),
                          '--expect','2','--anchor','parse(line)','--inside-rule'],capture_output=True,text=True,timeout=30)
        self.assertEqual(p.returncode,0,p.stdout+p.stderr)
    def test_long_code_can_still_split_and_keeps_all_100_rows(self):
        with fitz.open(self.pdf('code-long')) as doc:
            self.assertGreaterEqual(len(doc),2)
            labels=re.findall(r'row\d{3}','\n'.join(p.get_text() for p in doc))
            self.assertEqual(labels,[f'row{i:03d}' for i in range(1,101)])
        self.assertEqual(self.results['code-long']['overfull_vbox'],0)
    def test_numbered_deep_label_matches_engine_aux_and_visible_ref(self):
        for name in ['deep-hook','deep-direct','deep-group']:
            aux=(self.root/name/'main.aux').read_text()
            self.assertIn(r'\newlabel{sec:deep}{{1.1.1}',aux,(name,aux))
            self.assertIn('subsubsection.1.1.1',aux)
            with fitz.open(self.pdf(name)) as doc:
                text=''.join(p.get_text() for p in doc)
                self.assertIn('REF=1.1.1',re.sub(r'\s+','',text),text)
                self.assertTrue(any(link.get('nameddest')=='subsubsection.1.1.1' for p in doc for link in p.get_links()))
    def test_lowered_depth_mutation_binds_parent_not_deep_number(self):
        aux=(self.root/'deep-lowered'/'main.aux').read_text()
        self.assertIn(r'\newlabel{sec:deep}{{1.1}',aux)
        self.assertNotIn(r'\newlabel{sec:deep}{{1.1.1}',aux)

if __name__=='__main__': unittest.main(verbosity=2)
