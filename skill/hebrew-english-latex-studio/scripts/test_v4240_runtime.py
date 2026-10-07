#!/usr/bin/env python3
"""Real-engine Roman/decimal/prefixed folios, wrong footer, and managed gate.

Set HLLPDF_FOLIO_EVIDENCE to an empty directory to retain reproducible sources,
PDFs, stdout, geometry and the managed-build rejection/preservation record.
"""
from __future__ import annotations
import contextlib
import io
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.dont_write_bytecode = True
import fitz
import check_pdf_render as render
from pdf_folios import declared_labels, footer_candidates
from font_paths import font_dir
ROOT = Path(__file__).resolve().parent.parent
HEADER = r'''\def\lakitdocumentclass{article}
\def\lakitclassoptions{11pt,a4paper}
\input{preamble.tex}
\hypersetup{pdftitle={Folio regression controls},pdfauthor={Synthetic QA}}
\begin{document}
'''


def pages(count, bad_last=False):
    rows=[]
    for i in range(count):
        rows.append(r'\section*{בדיקת מספור העמוד}'+ '\n' +
                    'המספר המודפס בתחתית העמוד צריך להתאים לתווית העמוד שבקובץ.\n')
        if bad_last and i == count - 1:
            rows.append(r'\makeatletter\def\ps@wrongfolio{\def\@oddfoot{\hfil\en{vi}\hfil}\let\@evenfoot\@oddfoot}\makeatother\thispagestyle{wrongfolio}'+'\n')
        rows.append(r'\newpage'+'\n')
    return ''.join(rows)


def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


class FolioRuntime(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        target=os.environ.get('HLLPDF_FOLIO_EVIDENCE')
        cls.tmp=None
        if target:
            cls.root=Path(target).resolve();cls.root.mkdir(parents=True,exist_ok=True)
            if any(cls.root.iterdir()):raise ValueError('folio evidence directory must be empty')
        else:
            cls.tmp=tempfile.TemporaryDirectory(prefix='hllpdf424-runtime-')
            cls.root=Path(cls.tmp.name)
        fonts=str(font_dir())
        cls.env={**os.environ,'HEBREW_LATEX_FONT_DIR':fonts,'OSFONTDIR':fonts,'TTFONTS':fonts+'//:',
                 'SOURCE_DATE_EPOCH':'1700000000','TZ':'UTC','PYTHONDONTWRITEBYTECODE':'1'}
        cls.env.pop('HEBREW_LATEX_PROJECT_ROOT',None)
        cache=cls.root/'private-cache';cache.mkdir()
        cls.env.update(TEXMFCACHE=str(cache),TEXMFVAR=str(cache))
        cls.results={}
        cls.sources={
          'roman':r'\pagenumbering{roman}'+pages(4),
          'upper':r'\pagenumbering{Roman}'+pages(4),
          'mixed':r'\pagenumbering{roman}'+pages(4)+r'\pagenumbering{arabic}'+pages(4),
          'wrong':r'\pagenumbering{roman}'+pages(4,True)+r'\pagenumbering{arabic}'+pages(4),
          'prefix':r'\setcounter{page}{12}\renewcommand{\thepage}{\en{A-\arabic{page}}}'+pages(4),
          'letters':r'\pagenumbering{alph}'+pages(4),
          # v4.25.0: body math that ends a page dips into the folio band.
          'bodymath':pages(1)+r'\section*{בדיקת מספור העמוד}'+'\n'
                     +r'\vspace*{\fill}\[ X \]'+'\n'+r'\newpage'+'\n'+pages(1),
        }
        for name,body in cls.sources.items():cls.compile(name,HEADER+body+'\n\\end{document}\n')

    @classmethod
    def tearDownClass(cls):
        (cls.root/'summary.json').write_text(json.dumps(cls.results,ensure_ascii=False,indent=2)+'\n')
        shutil.rmtree(cls.root/'private-cache',ignore_errors=True)
        if cls.tmp:cls.tmp.cleanup()

    @classmethod
    def compile(cls,name,source):
        p=cls.root/name;p.mkdir()
        (p/'main.tex').write_text(source)
        shutil.copyfile(ROOT/'assets/preamble.tex',p/'preamble.tex')
        for i in range(2):
            run=subprocess.run(['lualatex','--no-shell-escape','-halt-on-error','-interaction=nonstopmode','main.tex'],
                               cwd=p,env=cls.env,text=True,capture_output=True,timeout=180)
            (p/f'pass-{i+1}.txt').write_text(run.stdout+run.stderr)
            if run.returncode:raise AssertionError(name+': '+run.stdout[-2400:])
        with fitz.open(p/'main.pdf') as d:
            cls.results[name]={'labels':declared_labels(d),'footers':[footer_candidates(page) for page in d],
                               'pages':len(d),'pdf_sha256':digest(p/'main.pdf')}

    def checked(self,name):
        out=io.StringIO()
        with contextlib.redirect_stdout(out):rc=render.check(str(self.root/name/'main.pdf'))
        (self.root/name/'render-check.txt').write_text(out.getvalue())
        self.results[name]['checker_exit']=rc
        return rc,out.getvalue()

    def test_01_roman_four_pages(self):
        self.assertEqual(self.results['roman']['labels'],['i','ii','iii','iv'])
        self.assertEqual(self.checked('roman')[0],0)

    def test_02_upper_roman(self):
        self.assertEqual(self.results['upper']['footers'],[['I'],['II'],['III'],['IV']])
        self.assertEqual(self.checked('upper')[0],0)

    def test_03_mixed_reset(self):
        self.assertEqual(self.results['mixed']['labels'],['i','ii','iii','iv','1','2','3','4'])
        self.assertEqual(self.checked('mixed')[0],0)

    def test_04_real_wrong_footer_not_label(self):
        self.assertEqual(self.results['wrong']['labels'][3],'iv')
        self.assertEqual(self.results['wrong']['footers'][3],['vi'])
        rc,out=self.checked('wrong')
        self.assertEqual(rc,1);self.assertIn('p.4 [PAGE-NUMBER-REVERSED]',out)
        with patch.object(render,'declared_labels',return_value=None):
            with contextlib.redirect_stdout(io.StringIO()):old_rc=render.check(str(self.root/'wrong/main.pdf'))
        self.assertEqual(old_rc,0)
        self.results['wrong']['disabled_label_handler_exit']=old_rc

    def test_05_prefixed_number(self):
        self.assertEqual(self.results['prefix']['labels'],['A-12','A-13','A-14','A-15'])
        self.assertEqual(self.checked('prefix')[0],0)

    def test_06_alphabetic_labels(self):
        self.assertEqual(self.results['letters']['labels'],['a','b','c','d'])
        self.assertEqual(self.checked('letters')[0],0)

    def test_07_disabling_real_handler_restores_false_rejection(self):
        with patch.object(render,'declared_labels',return_value=None):
            with contextlib.redirect_stdout(io.StringIO()) as out:rc=render.check(str(self.root/'roman/main.pdf'))
        self.assertEqual(rc,1);self.assertIn('FOLIO-COVERAGE-LOW',out.getvalue())
        self.results['roman']['disabled_label_handler_exit']=rc

    def managed(self,name,sourcecase,prior=False):
        target=self.root/name;target.mkdir()
        for fn in ['main.tex','preamble.tex']:shutil.copyfile(self.root/sourcecase/fn,target/fn)
        original_source=digest(target/'main.tex')
        if prior:shutil.copyfile(self.root/'prefix/main.pdf',target/'main.pdf')
        original_pdf=digest(target/'main.pdf') if prior else None
        run=subprocess.run(['bash',str(ROOT/'scripts/build.sh'),str(target/'main.tex')],cwd=target,env=self.env,
                           capture_output=True,text=True,timeout=360)
        (target/'build.txt').write_text(run.stdout+run.stderr)
        self.assertEqual(digest(target/'main.tex'),original_source)
        result=dict(exit=run.returncode,source_sha256=original_source,prior_sha256=original_pdf,
                    final_sha256=digest(target/'main.pdf') if (target/'main.pdf').is_file() else None)
        if (target/'main.failed.pdf').is_file():result['failed_sha256']=digest(target/'main.failed.pdf')
        self.results[name]=result
        return run,target

    def test_08_managed_roman_is_accepted(self):
        run,target=self.managed('managed-roman','roman')
        self.assertEqual(run.returncode,0,(run.stdout+run.stderr)[-4000:])
        self.assertTrue((target/'main.pdf').is_file())

    def test_09_managed_wrong_footer_is_rejected_and_prior_kept(self):
        run,target=self.managed('managed-wrong','wrong',True)
        self.assertEqual(run.returncode,1,(run.stdout+run.stderr)[-4000:])
        self.assertIn('PAGE-NUMBER-REVERSED',run.stdout+run.stderr)
        record=self.results['managed-wrong']
        self.assertEqual(record['prior_sha256'],record['final_sha256'])
        self.assertNotEqual(record['prior_sha256'],record['failed_sha256'])

    def test_10_no_missing_glyphs_in_controls(self):
        for name in self.sources:
            with self.subTest(name=name):
                self.assertNotIn('Missing character:',(self.root/name/'main.log').read_text())


    def test_11_body_math_in_the_folio_band_is_not_a_second_folio(self):
        # v4.25.0. Precondition first, so a layout change cannot make this pass
        # vacuously: the engine really puts a centred math X into the band.
        self.assertEqual(sorted(self.results['bodymath']['footers'][1]),['2','X'])
        rc,out=self.checked('bodymath')
        self.assertEqual(rc,0,out)
        import pdf_folios
        original=pdf_folios._styled_candidates   # mutation: runs lose their face
        with patch.object(pdf_folios,'_styled_candidates',
                          lambda *a,**k:[(t,frozenset()) for t,_ in original(*a,**k)]):
            rc,out=self.checked('bodymath')
        self.assertEqual(rc,1);self.assertIn('p.2 [FOLIO-AMBIGUOUS]',out)
if __name__=='__main__':unittest.main(verbosity=2)
