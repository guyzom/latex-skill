#!/usr/bin/env python3
"""Measured TOC/list layout: static geometry and real-engine mutation controls."""
from __future__ import annotations
import argparse
import hashlib
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
from toc_layout_probe import horizontal_gap, measure
ROOT = Path(__file__).resolve().parent.parent
START, END = '% <hllpdf:measured-toc>', '% </hllpdf:measured-toc>'
OLD = r'''\makeatletter
\@ifundefined{l@chapter}{}{%
  \patchcmd{\l@chapter}{\setlength\@tempdima{1.5em}}{\setlength\@tempdima{2.0em}}{}{}}
\renewcommand*\l@section{\@dottedtocline{1}{1.5em}{3.2em}}
\renewcommand*\l@subsection{\@dottedtocline{2}{4.7em}{3.9em}}
\makeatother
'''
LABELS = [('chapter','1000','CHAPTER'), ('section','1.1','ALPHA'),
          ('section','100.100','BETA'), ('subsection','12.10.10','GAMMA'),
          ('subsection','100.100.100','DELTA'),
          ('subsubsection','12.10.10.10','EPSILON')]
HE = {'CHAPTER':'פרק הבדיקה', 'ALPHA':'הפרדה ראשונה', 'BETA':'הפרדה שנייה',
      'GAMMA':'הפרדה שלישית', 'DELTA':'הפרדה רביעית', 'EPSILON':'הפרדה חמישית',
      'FIGURE':'איור בדיקה', 'TABLE':'טבלת בדיקה'}


def fixture(document_class='report', size=12, english=False, theme='', mixed=False):
    header = fr'''\def\lakitdocumentclass{{{document_class}}}
\def\lakitclassoptions{{{size}pt,a4paper}}
\def\lakittocdepth{{3}}
\input{{preamble.tex}}
'''
    if theme: header += fr'\input{{{theme}.tex}}'+'\n'
    header += r'''\hypersetup{pdftitle={Measured contents regression},pdfauthor={Synthetic QA}}
\newcounter{tocside}
\begin{document}
'''
    if english: header += r'\begin{englishprose}'+'\n'
    header += r'''\makeatletter
\typeout{HLLPDF-WIDTH-BEFORE=\@pnumwidth}
\makeatother
\tableofcontents
\makeatletter
\typeout{HLLPDF-WIDTH-AFTER=\@pnumwidth}
\makeatother
\typeout{HLLPDF-SIDE-EFFECT=\arabic{tocside}}
\clearpage
\listoffigures
\clearpage
\listoftables
\clearpage
\addtocontents{toc}{\protect\stepcounter{tocside}}
'''
    rows = []
    for level, label, key in LABELS:
        if document_class == 'article' and level == 'chapter': continue
        title = key if english else HE[key]
        header += fr'\phantomsection\addcontentsline{{toc}}{{{level}}}{{\protect\numberline{{{label}}}{title}}}'+'\n'
        rows.append((0,label,title,'ltr' if english else 'rtl'))
    # Both lists keep their own width state, and four-digit page labels stress
    # the independent page-number column. No extra physical pages are needed.
    header += r'\setcounter{page}{1000}'+'\n'
    for ext, level, key in [('lof','figure','FIGURE'),('lot','table','TABLE')]:
        title = key if english else HE[key]
        header += fr'\phantomsection\addcontentsline{{{ext}}}{{{level}}}{{\protect\numberline{{100.100}}{title}}}'+'\n'
        rows.append((1 if ext=='lof' else 2,'100.100',title,'ltr' if english else 'rtl'))
    if mixed:
        header += r"""\begin{englishprose}
\phantomsection\addcontentsline{toc}{section}{\protect\numberline{100.100.100.100}LANGSHIFT}
\end{englishprose}
\phantomsection\addcontentsline{toc}{section}{\protect\numberline{12.11}מסלול חזרה}
"""
        rows.extend([(0,'100.100.100.100','LANGSHIFT','ltr'),(0,'12.11','מסלול חזרה','rtl')])
    header += ('Synthetic geometry fixture.\n' if english else 'מקור מלאכותי לבדיקת גאומטריית המסמך.\n')
    if english: header += r'\end{englishprose}'+'\n'
    return header+r'\end{document}', rows


class GeometryTests(unittest.TestCase):
    def test_rtl_gap(self): self.assertEqual(horizontal_gap((50,0,70,10),(20,0,44,10)),6)
    def test_rtl_overlap(self): self.assertEqual(horizontal_gap((40,0,70,10),(20,0,44,10)),-4)
    def test_ltr_gap(self): self.assertEqual(horizontal_gap((20,0,44,10),(50,0,70,10),'ltr'),6)
    def test_ltr_overlap(self): self.assertEqual(horizontal_gap((20,0,54,10),(50,0,70,10),'ltr'),-4)
    def test_direction_is_explicit(self):
        with self.assertRaises(ValueError): horizontal_gap((0,0,10,10),(20,0,30,10),'auto')
    def test_nonfinite_rejected(self):
        with self.assertRaises(ValueError): horizontal_gap((float('nan'),0,10,10),(20,0,30,10))
    def test_inverted_box_rejected(self):
        with self.assertRaises(ValueError): horizontal_gap((10,0,0,10),(20,0,30,10))
    def test_missing_anchor_fails_closed(self):
        with fitz.open() as doc:
            page=doc.new_page()
            with self.assertRaises(ValueError): measure(page,'12.10','MISSING')
    def test_duplicate_anchor_fails_closed(self):
        with fitz.open() as doc:
            page=doc.new_page(); page.insert_text((50,50),'TITLE'); page.insert_text((50,100),'TITLE')
            with self.assertRaises(ValueError): measure(page,'12.10','TITLE')
    def test_text_geometry_and_digit_order(self):
        with fitz.open() as doc:
            page=doc.new_page(); page.insert_text((50,50),'12.10'); page.insert_text((110,50),'TITLE')
            hit=measure(page,'12.10','TITLE','ltr')
            self.assertGreater(hit.gap_pt,20); self.assertEqual(hit.physical_label,'12.10')


    def test_same_label_in_page_column_is_not_ambiguous(self):
        with fitz.open() as doc:
            page=doc.new_page(); page.insert_text((50,50),'1000')
            page.insert_text((300,50),'TITLE'); page.insert_text((400,50),'1000')
            hit=measure(page,'1000','TITLE','rtl')
            self.assertGreater(hit.label_box[0],390)

    def test_two_titles_on_one_line_are_still_ambiguous(self):
        with fitz.open() as doc:
            page=doc.new_page(); page.insert_text((50,50),'12.10 TITLE TITLE')
            with self.assertRaises(ValueError): measure(page,'12.10','TITLE','ltr')

    def test_rtl_glyph_fragments_form_one_title_not_many(self):
        chars=[]
        for c,x in [('1',80),('2',86),('א',60),('ב',54),('ג',48)]:
            chars.append({'c':c,'origin':(x,20),'bbox':(x,10,x+6,22)})
        class FragmentedPage:
            def get_text(self,kind):
                return {'blocks':[{'lines':[{'spans':[{'chars':chars}]}]}]}
            def search_for(self,text):
                raise AssertionError('fragment-prone search rectangles must not be used')
        hit=measure(FragmentedPage(),'12','אבג')
        self.assertEqual(hit.gap_pt,14)


class RuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(prefix='hllpdf-toc-')
        cls.root=Path(cls.tmp.name); cls.results={}; cls.logs={}
        cls.env=os.environ.copy(); fonts=str(font_dir())
        cls.env.update(OSFONTDIR=fonts, TTFONTS=fonts+'//:', HEBREW_LATEX_FONT_DIR=fonts,
                       SOURCE_DATE_EPOCH='1700000000', PYTHONDONTWRITEBYTECODE='1')
        cls.env.pop('HEBREW_LATEX_PROJECT_ROOT',None)
        cls.configs=[('report',10,False,''),('report',11,False,''),('report',12,False,''),
                     ('article',10,False,''),('article',11,False,'reader_theme'),
                     ('article',12,False,'clean_theme'),('report',12,True,''),
                     ('article',11,True,'reader_theme')]
        for i, config in enumerate(cls.configs):
            cls.results[i]=cls.compile(str(i),*config)
        cls.results[8]=cls.compile('8','article',12,False,'',mixed=True)
        cls.configs.append(('article',12,'mixed',''))
        cls.mutant=cls.compile('mutant','report',12,False,'',mutate=True)

    @classmethod
    def tearDownClass(cls):
        keep=os.environ.get('HLLPDF_TOC_EVIDENCE')
        if keep:
            target=Path(keep)
            if target.exists(): raise RuntimeError('evidence destination already exists')
            shutil.copytree(cls.root,target)
        cls.tmp.cleanup()

    @classmethod
    def compile(cls, name, document_class, size, english, theme, mutate=False, mixed=False):
        folder=cls.root/name; folder.mkdir()
        core=(ROOT/'assets/preamble.tex').read_text()
        if mutate:
            a=core.index(START); b=core.index(END,a)+len(END)
            core=core[:a]+OLD+core[b:]
        (folder/'preamble.tex').write_text(core)
        if theme: shutil.copyfile(ROOT/'assets'/f'{theme}.tex',folder/f'{theme}.tex')
        text,rows=fixture(document_class,size,english,theme,mixed)
        (folder/'main.tex').write_text(text)
        result=None
        for _ in range(3):
            result=subprocess.run(['lualatex','--no-shell-escape','-halt-on-error',
                                   '-interaction=nonstopmode','main.tex'],cwd=folder,env=cls.env,
                                  capture_output=True,text=True,timeout=120)
            if result.returncode: break
        cls.logs[name]=result.stdout
        return folder,rows,result

    def documents(self):
        for i,(folder,rows,result) in self.results.items():
            self.assertEqual(result.returncode,0,f'{self.configs[i]}\n{result.stdout[-3000:]}')
            yield i,folder,rows

    def test_all_nine_fixture_variants_compile(self):
        for _,folder,_ in self.documents():
            log=(folder/'main.log').read_text()
            self.assertNotIn('Missing character:',log)
            self.assertNotIn('Overfull \\hbox',log)
            self.assertNotIn('Overfull \\vbox',log)
            with fitz.open(folder/'main.pdf') as doc: self.assertEqual(len(doc),4)

    def test_every_number_has_readable_title_clearance(self):
        for _,folder,rows in self.documents():
            with fitz.open(folder/'main.pdf') as doc:
                for page,label,title,direction in rows:
                    item=measure(doc[page],label,title,direction)
                    self.assertGreaterEqual(item.gap_pt,3,(folder.name,item))
                    self.assertEqual(item.physical_label,label)

    def test_same_level_title_starts_align(self):
        for _,folder,rows in self.documents():
            with fitz.open(folder/'main.pdf') as doc:
                by_label={label:measure(doc[page],label,title,direction) for page,label,title,direction in rows if page==0}
                for a,b in [('1.1','100.100'),('12.10.10','100.100.100')]:
                    edge=2 if by_label[a].direction=='rtl' else 0
                    self.assertAlmostEqual(by_label[a].title_box[edge],by_label[b].title_box[edge],delta=.2)

    def test_page_labels_fit_inside_the_list_margin(self):
        for _,folder,rows in self.documents():
            with fitz.open(folder/'main.pdf') as doc:
                for page in (1,2):
                    # Four-digit page numbers must be whole, not clipped or
                    # extending into the outer page margin. No folio 1000 here.
                    hits=doc[page].search_for('1000')
                    self.assertEqual(len(hits),1)
                    self.assertGreaterEqual(hits[0].x0,64)
                    self.assertLessEqual(hits[0].x1,doc[page].rect.width-64)

    def test_local_measurement_does_not_leak(self):
        for i,_,_ in self.documents():
            before=re.search(r'HLLPDF-WIDTH-BEFORE=(.+)',self.logs[str(i)]).group(1)
            after=re.search(r'HLLPDF-WIDTH-AFTER=(.+)',self.logs[str(i)]).group(1)
            self.assertEqual(before,after)

    def test_raw_toc_directive_is_not_executed_twice(self):
        for i,_,_ in self.documents(): self.assertIn('HLLPDF-SIDE-EFFECT=1',self.logs[str(i)])

    def test_named_links_and_outline_still_resolve(self):
        for _,folder,rows in self.documents():
            with fitz.open(folder/'main.pdf') as doc:
                names=doc.resolve_names()
                links=[link for page in doc for link in page.get_links()]
                self.assertTrue(links); self.assertTrue(doc.get_toc())
                for link in links:
                    if 'nameddest' in link:
                        self.assertIn(link['nameddest'],names)
                        self.assertEqual(names[link['nameddest']]['page'],3)
                    else: self.assertEqual(link.get('page'),3)

    def test_third_pass_is_a_fixed_point(self):
        folder,_,_=self.results[2]
        old=hashlib.sha256((folder/'main.pdf').read_bytes()).hexdigest()
        result=subprocess.run(['lualatex','--no-shell-escape','-halt-on-error',
                               '-interaction=nonstopmode','main.tex'],cwd=folder,env=self.env,
                              capture_output=True,text=True,timeout=120)
        self.assertEqual(result.returncode,0,result.stdout[-2000:])
        self.assertEqual(old,hashlib.sha256((folder/'main.pdf').read_bytes()).hexdigest())

    def test_language_switches_within_one_toc_use_the_actual_font(self):
        folder,_,result=self.results[8]
        self.assertEqual(result.returncode,0)
        toc=(folder/'main.toc').read_text()
        self.assertIn(r'\babel@toc {english}',toc)
        self.assertGreaterEqual(toc.count(r'\babel@toc {hebrew}'),2)
        with fitz.open(folder/'main.pdf') as doc:
            item=measure(doc[0],'100.100.100.100','LANGSHIFT','ltr')
            self.assertGreaterEqual(item.gap_pt,5)

    def test_old_fixed_boxes_reproduce_negative_gaps(self):
        folder,rows,result=self.mutant
        self.assertEqual(result.returncode,0,result.stdout[-3000:])
        with fitz.open(folder/'main.pdf') as doc:
            values=[measure(doc[page],label,title,direction).gap_pt for page,label,title,direction in rows]
            self.assertLess(min(values),-5,values)
            # Regression control includes figure/table numbers, not only TOC.
            for page,label,title,direction in rows:
                if page in (1,2): self.assertLess(measure(doc[page],label,title,direction).gap_pt,0)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime',action='store_true')
    args=parser.parse_args()
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(RuntimeTests if args.runtime else GeometryTests)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(not result.wasSuccessful())
