#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Original project code; scope and terms: ../LICENSING.md.
"""Real engine font selection, relocation and fail-closed publication controls.

Set HLLPDF_422_EVIDENCE_DIR to a NEW directory outside the skill to retain
sources/PDFs/logs. Font programs and font caches stay in disposable directories.
"""
from __future__ import annotations
import hashlib,json,os,re,shutil,subprocess,sys,tempfile,unittest
from pathlib import Path
sys.dont_write_bytecode = True
import fitz
import check_runtime_fonts as checker
ROOT=Path(__file__).resolve().parent.parent
FORMS=[('rm',x) for x in ['normal','bold','italic','bolditalic']]+[('sf',x) for x in ['normal','bold']]+[('tt',x) for x in ['normal','bold','italic','bolditalic']]
STYLE={'normal':r'\mdseries\upshape','bold':r'\bfseries\upshape','italic':r'\mdseries\itshape','bolditalic':r'\bfseries\itshape'}
HEADER=r'''\def\lakitdocumentclass{article}
\def\lakitclassoptions{11pt,a4paper}
\input{preamble.tex}
\hypersetup{pdftitle={בדיקת בחירת גופנים},pdfauthor={Synthetic QA}}
'''

def matrix(theme='default'):
    head=HEADER
    if theme=='reader':head=head.replace('{article}','{report}').replace('{11pt,a4paper}','{12pt,a4paper}')
    if theme=='clean':head=head.replace('{11pt,a4paper}','{12pt,a4paper}')
    if theme!='default':head+='\\input{'+theme+'_theme.tex}\n'
    body=[]
    for language in ['english','hebrew']:
        body.append('\\begin{otherlanguage}{'+language+'}\n')
        for i,(family,style) in enumerate(FORMS):
            ident=f'{language}-{family}-{style}'
            sample='Sample “alpha beta” 0123 (x+y).'+(r' \char"1E0D{}' if family=='rm' else (r' \char"1E6E{}' if family=='sf' else ''))
            if language=='hebrew':sample='\\en{\\mbox{'+sample+'}}'
            body.append('{\\'+family+'family'+STYLE[style]+r'\noindent'+
                '\n\\directlua{local f=font.getfont(font.current()); local p=f.filename or "?"; '
                'local n=p:match("/([^/]+)" .. string.char(36)) or p; texio.write_nl("log","HLLSHAPE|'+ident+'|" .. n .. "|END")}\n'+
                sample+'\\par\\medskip}\n')
        body.append('\\end{otherlanguage}\n')
        if language=='english':body.append('\\clearpage\n')
    return head+'\\begin{document}\n'+''.join(body)+'\\end{document}\n'

def shape_records(text):
    # write_nl starts a new line but need not end it. TeX may append a shipout
    # diagnostic (" [1") on the same line. A protocol terminator separates the
    # observed filename from unrelated log data without trimming filename bytes.
    return re.findall(r'^HLLSHAPE\|([^|\r\n]+)\|([^|\r\n]+)\|END',text,re.M)

class EngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        chosen=os.environ.get('HLLPDF_422_EVIDENCE_DIR')
        if chosen:
            cls.root=Path(chosen).resolve()
            if cls.root==ROOT or ROOT in cls.root.parents:raise ValueError('Evidence must be outside skill')
            cls.root.mkdir(parents=True,exist_ok=False)
        else:
            cls.temp=tempfile.TemporaryDirectory(prefix='hllpdf422-runtime-');cls.root=Path(cls.temp.name)
        cls.private=tempfile.TemporaryDirectory(prefix='hllpdf422-private-');cls.private_root=Path(cls.private.name)
        cls.fonts=checker.font_dir();cls.env={**os.environ,'HEBREW_LATEX_FONT_DIR':str(cls.fonts),'TTFONTS':str(cls.fonts)+':',
            'OSFONTDIR':str(cls.fonts)+':','SOURCE_DATE_EPOCH':'1700000000','TZ':'UTC','PYTHONDONTWRITEBYTECODE':'1'}
        cls.env.pop('HEBREW_LATEX_PROJECT_ROOT',None)
        cls.cases={};cls.core=(ROOT/'assets/preamble.tex').read_text()
        for theme in ['default','reader','clean']:cls.compile('matrix-'+theme,matrix(theme))
        cls.alternate=cls.private_root/'תיקיית גופנים עם רווח_';shutil.copytree(cls.fonts,cls.alternate)
        cls.compile('relocated',matrix(),env={'HEBREW_LATEX_FONT_DIR':str(cls.alternate),'TTFONTS':str(cls.alternate)+':','OSFONTDIR':str(cls.alternate)+':'})
        # A same-byte different directory is intentionally NOT the selected root.
        wrong=cls.core.replace('local dir = os.getenv("HEBREW_LATEX_FONT_DIR")','local dir = os.getenv("HLLPDF_TEST_OTHER_FONT_DIR")')
        cls.compile('wrong-path',matrix(),core=wrong,env={'HLLPDF_TEST_OTHER_FONT_DIR':str(cls.alternate)})
        absent,n=re.subn(r'\n% <hllpdf:font-inventory>\n.*?% </hllpdf:font-inventory>\n','\n',cls.core,flags=re.S)
        if n!=1:raise ValueError('Inventory marker missing')
        cls.compile('missing-inventory',matrix(),core=absent)
        old=cls.core.replace(r'Path={\hllpdffontdir},','')
        for name in ['DejaVuSerif.ttf','DejaVuSerif-Bold.ttf','DejaVuSans.ttf','DejaVuSans-Bold.ttf']:
            old=old.replace('"[" .. hllpdf_font_dir .. "'+name+']:mode=node;"','"file:'+name+':mode=node;"')
        cls.compile('basename-control',matrix(),core=old)
        cls.managed={}
        for name in ['matrix-default','wrong-path','missing-inventory']:
            d=cls.root/name;pdf=d/'main.pdf';before=pdf.read_bytes()
            env={**cls.env,'REPRO':'1'}
            if name=='wrong-path':env['HLLPDF_TEST_OTHER_FONT_DIR']=str(cls.alternate)
            p=subprocess.run(['bash',str(ROOT/'scripts/build.sh'),str(d/'main.tex')],env=env,text=True,capture_output=True,timeout=240)
            (d/'managed.log').write_text(p.stdout+p.stderr)
            cls.managed[name]={'exit':p.returncode,'runtime_messages':p.stdout.count('runtime fonts:'),'runtime_rejection':'✗ runtime fonts:' in p.stdout,
                               'previous_pdf_preserved':pdf.read_bytes()==before}
        missing={**cls.env,'HEBREW_LATEX_FONT_DIR':str(cls.private_root/'absent')}
        d=cls.root/'missing-directory';d.mkdir();(d/'main.tex').write_text(matrix());(d/'preamble.tex').write_text(cls.core)
        p=subprocess.run(['lualatex','--no-shell-escape','-halt-on-error','-interaction=nonstopmode','main.tex'],cwd=d,env=missing,text=True,capture_output=True,timeout=90)
        cls.missing={'exit':p.returncode,'message':'font directory is missing' in p.stdout};(d/'stdout.log').write_text(p.stdout+p.stderr)
        (cls.root/'summary.json').write_text(json.dumps({'cases':cls.cases,'managed':cls.managed,'missing_directory':cls.missing},ensure_ascii=False,indent=2)+'\n')
    @classmethod
    def compile(cls,name,src,core=None,env=None):
        d=cls.root/name;d.mkdir();(d/'main.tex').write_text(src);(d/'preamble.tex').write_text(core or cls.core)
        for theme in ['reader_theme.tex','clean_theme.tex']:shutil.copyfile(ROOT/'assets'/theme,d/theme)
        cache=cls.private_root/('cache-'+name);cache.mkdir()
        current={**cls.env,'TEXMFCACHE':str(cache),'TEXMFVAR':str(cache),**(env or {})}
        for i in range(2):
            p=subprocess.run(['lualatex','--no-shell-escape','-halt-on-error','-interaction=nonstopmode','-recorder','main.tex'],cwd=d,env=current,text=True,capture_output=True,timeout=90)
            (d/f'pass-{i+1}.log').write_text(p.stdout+p.stderr)
            if p.returncode:raise AssertionError(name+' did not compile:\n'+p.stdout[-3500:])
        audit=checker.audit(d/'main.log',Path(current['HEBREW_LATEX_FONT_DIR']))
        (d/'font-audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n')
        text=(d/'main.log').read_text();shapes=shape_records(text)
        doc=fitz.open(d/'main.pdf');fonts=sorted({f[3] for page in doc for f in page.get_fonts()})
        cls.cases[name]={'pages':len(doc),'audit':audit,'shapes':shapes,'pdf_fonts':fonts,'missing_glyphs':text.count('Missing character:'),'pdf_sha256':hashlib.sha256((d/'main.pdf').read_bytes()).hexdigest()}
        doc.close()
    @classmethod
    def tearDownClass(cls):
        cls.private.cleanup()
        if hasattr(cls,'temp'):cls.temp.cleanup()
    def test_01_canonical_files(self):
        for name in ['matrix-default','matrix-reader','matrix-clean','relocated']:
            r=self.cases[name];self.assertEqual(r['audit']['status'],'verified');self.assertEqual(len(r['audit']['verified']),9)
    def test_02_supported_shapes(self):
        for name in ['matrix-default','matrix-reader','matrix-clean']:
            rows=self.cases[name]['shapes'];self.assertEqual(len(rows),20)
            for label,filename in rows:
                family,style=label.split('-')[1:]
                expected='DejaVuSansMono.ttf' if family=='tt' else ('Heebo-' if family=='sf' else 'FrankRuhlLibre-')+('Bold.ttf' if style in ['bold','bolditalic'] else 'Regular.ttf')
                self.assertEqual(filename,expected)
    def test_03_fallback_faces_and_glyphs(self):
        for name in ['matrix-default','matrix-reader','matrix-clean']:
            r=self.cases[name];self.assertEqual(r['missing_glyphs'],0)
            for family in ['DejaVuSerif','DejaVuSerif-Bold','DejaVuSans','DejaVuSans-Bold']:
                self.assertTrue(any(family==f.split('+')[-1] for f in r['pdf_fonts']),(name,family,r['pdf_fonts']))
    def test_04_special_path(self):
        self.assertTrue(all('תיקיית גופנים עם רווח_' in r['path'] for r in self.cases['relocated']['audit']['verified']))
    def test_05_wrong_directory_rejected(self):self.assertEqual(self.cases['wrong-path']['audit']['status'],'failed')
    def test_06_missing_inventory_rejected(self):self.assertEqual(self.cases['missing-inventory']['audit']['status'],'failed')
    def test_07_managed_checks_passes(self):
        r=self.managed['matrix-default'];self.assertEqual(r['exit'],0);self.assertGreaterEqual(r['runtime_messages'],4)
    def test_08_wrong_font_preserves_pdf(self):
        r=self.managed['wrong-path'];self.assertEqual(r['exit'],1);self.assertTrue(r['runtime_rejection']);self.assertTrue(r['previous_pdf_preserved'])
    def test_09_absent_inventory_preserves_pdf(self):
        r=self.managed['missing-inventory'];self.assertEqual(r['exit'],1);self.assertTrue(r['runtime_rejection']);self.assertTrue(r['previous_pdf_preserved'])
    def test_10_missing_directory_and_basename_control(self):
        self.assertNotEqual(self.missing['exit'],0);self.assertTrue(self.missing['message']);self.assertEqual(self.cases['basename-control']['audit']['status'],'failed')
    def test_11_relocation_pixels_unchanged(self):
        with fitz.open(self.root/'matrix-default/main.pdf') as a,fitz.open(self.root/'relocated/main.pdf') as b:
            self.assertEqual(len(a),len(b))
            for p,q in zip(a,b):
                x,y=p.get_pixmap(dpi=110),q.get_pixmap(dpi=110)
                self.assertEqual((x.width,x.height,x.samples),(y.width,y.height,y.samples))
    def test_12_shape_record_boundaries(self):
        self.assertEqual(shape_records('HLLSHAPE|english-tt-bolditalic|DejaVuSansMono.ttf|END [1\n'),
                         [('english-tt-bolditalic','DejaVuSansMono.ttf')])
        # Do not normalize/trim a genuinely different observed filename.
        self.assertEqual(shape_records('HLLSHAPE|english-tt-bolditalic|wrong.ttf|END\n'),
                         [('english-tt-bolditalic','wrong.ttf')])
        self.assertEqual(shape_records('HLLSHAPE|english-tt-bolditalic|DejaVuSansMono.ttf [1\n'),[])

if __name__=='__main__':unittest.main(verbosity=2)
