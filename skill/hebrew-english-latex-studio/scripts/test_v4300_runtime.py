#!/usr/bin/env python3
"""Real-engine source fidelity for twelve technical symbols in LTR listings.

Retain sources/PDFs/logs outside the skill using HLLPDF_430_EVIDENCE_DIR.
Geometry/glyph assertions and renderer replay are not visual certification.
"""
from __future__ import annotations
import hashlib
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
from render_review import render, verify
ROOT=Path(__file__).resolve().parent.parent
SYMBOLS='–—…←→↔⇒−∞≠≤≥'
PATCH_RE=r'\n% <hllpdf:listing-technical-symbols>\n.*?% </hllpdf:listing-technical-symbols>'
STYLES=('asm','cstyle','pystyle','htmlstyle')
SAMPLES=[
 'a = "left–right"; b = "left—right"',
 'c = "wait…done"; d = "{left←right}"',
 'e = "[left→right]"; f = "left↔right"',
 'g = "left⇒right"; h = "left−right"',
 'i = "left∞right"; j = "left≠right"',
 'k = "left≤right"; m = "left≥right"',
 '# alpha–beta; alpha—beta; alpha…beta',
 '# alpha←beta; alpha→beta; alpha↔beta; alpha⇒beta',
 '# alpha−beta; alpha∞beta; alpha≠beta; alpha≤beta; alpha≥beta',
]
HEADER=r'''\def\lakitdocumentclass{article}
\def\lakitclassoptions{11pt,a4paper}
\input{preamble.tex}
'''

def document(body: str, theme='core', extra='') -> str:
    return (HEADER+('' if theme=='core' else '\\input{'+theme+'_theme.tex}\n')+
            extra+'\n'+r'\hypersetup{pdftitle={Technical symbols regression},pdfauthor={Synthetic QA}}'+'\n'+
            '\\begin{document}\n'+body+'\n\\end{document}\n')

def listing(lines, options='style=pystyle,breaklines=true'):
    return '\\begin{asmblock}\n\\begin{lstlisting}['+options+']\n'+'\n'.join(lines)+'\n\\end{lstlisting}\n\\end{asmblock}\n'

def matrix(theme='core', styles=STYLES, languages=('hebrew','english')):
    parts=[]; expected=[]
    for style in styles:
        for lang in languages:
            body=r'\section{בדיקת סימנים \en{'+style+' / '+lang+'}}\n'
            if lang=='english':body+='\\begin{englishprose}\n'
            for boxed in (False,True):
                lines=[f'{style[0]}{len(expected)+i:03d} '+s for i,s in enumerate(SAMPLES)]
                expected.extend(lines)
                block=listing(lines,'style='+style+',breaklines=true')
                if boxed: block='\\begin{codebox}[nobreak=true]\n'+block+'\\end{codebox}\n'
                body+=block
            if lang=='english':body+='\\end{englishprose}\n'
            parts.append(body)
    return document('\\newpage\n'.join(parts),theme),expected

class TechnicalSymbolRuntime(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        chosen=os.environ.get('HLLPDF_430_EVIDENCE_DIR')
        if chosen:
            cls.root=Path(chosen).resolve()
            if cls.root==ROOT or ROOT in cls.root.parents:raise ValueError('evidence must be outside the skill')
            cls.root.mkdir(parents=True,exist_ok=False)
        else:
            cls.tmp=tempfile.TemporaryDirectory(prefix='hllpdf430-runtime-')
            cls.addClassCleanup(cls.tmp.cleanup);cls.root=Path(cls.tmp.name)
        fonts=str(font_dir());cache=cls.root/'font-cache';cache.mkdir()
        cls.env=dict(os.environ,HEBREW_LATEX_FONT_DIR=fonts,OSFONTDIR=fonts+':',TTFONTS=fonts+':',
                     TEXMFCACHE=str(cache),TEXMFVAR=str(cache),SOURCE_DATE_EPOCH='1700000000',
                     TZ='UTC',PYTHONDONTWRITEBYTECODE='1')
        cls.core=(ROOT/'assets/preamble.tex').read_text(encoding='utf-8')
        cls.results={};cls.sources={}
        for theme in ('core','reader','clean'):
            src,lines=matrix(theme);cls.compile('matrix-'+theme,src,lines)
        src,lines=matrix('reader',('pystyle',),('english',))
        cls.compile('mutation-unregistered',src,lines,mutation=True)
        cls.compile('extended-false',document(listing(SAMPLES,'style=pystyle,extendedchars=false,breaklines=true')),SAMPLES)
        mappings={ch:f'[S{i:02d}]' for i,ch in enumerate(SYMBOLS)}
        extra='\\lstset{literate='+ ' '.join('{'+ch+'}{{'+value+'}}5' for ch,value in mappings.items())+'}\n'
        cls.compile('explicit-literate',document(listing(SAMPLES),extra=extra),
                    [line.translate(str.maketrans(mappings)) for line in SAMPLES])
        inline=['left–right','left—right','left…right','left←right','left→right','left↔right',
                'left⇒right','left−right','left∞right','left≠right','left≤right','left≥right']
        body='\\begin{englishprose}\n'
        body+='\n\n'.join('\\lstinline[style=pystyle]|'+x+'|' if i%2==0 else '\\lstinline[style=pystyle]{'+x+'}' for i,x in enumerate(inline))
        body+='\n\\end{englishprose}\n\\begin{asmblock}\n\\lstinputlisting[style=pystyle,breaklines=true]{external.txt}\n\\end{asmblock}\n'
        cls.compile('inline-and-file',document(body),inline+SAMPLES,external='\n'.join(SAMPLES)+'\n')
        active='\\begingroup\n'
        for ch in SYMBOLS:
            code=f'{ord(ch):04X}'
            active+='\\catcode"'+code+'=13\\relax\n\\def'+ch+'{\\char"'+code+'\\relax}\n\\expandafter\\let\\csname Saved'+code+'\\endcsname'+ch+'\n'
        active+=listing(SAMPLES)
        for ch in SYMBOLS:
            code=f'{ord(ch):04X}'
            active+='\\ifnum\\catcode"'+code+'=13\\relax\\else\\errmessage{CATCODE LEAK '+code+'}\\fi\n'
            active+='\\expandafter\\ifx\\csname Saved'+code+'\\endcsname'+ch+'\\else\\errmessage{MEANING LEAK '+code+'}\\fi\n'
        active+='\\endgroup\n'
        cls.compile('active-scope',document(active),SAMPLES)
        wrapped=[f'W{i:02d} '+('left'+ch+'right ')*7+f'end{i:02d}' for i,ch in enumerate(SYMBOLS)]
        body='\\begin{minipage}{220pt}\n'+listing(wrapped,'style=pystyle,breaklines=true,breakatwhitespace=true')+'\\end{minipage}\n'
        cls.compile('wrapped-lines',document(body),wrapped)
        long=[f'L{i:03d} '+SAMPLES[i%len(SAMPLES)] for i in range(70)]
        cls.compile('page-split',document('\\begin{codebox}\n'+listing(long)+'\\end{codebox}\n'),long)
        escaped=[r'E01 (*@\textbf{left—right}@*) end', r'E02 (*@\textbf{left≤right}@*) next→end']
        cls.compile('latex-escape',document(listing(escaped,'style=pystyle,escapeinside={(*@}{@*)}')),
                    ['E01 left—right end','E02 left≤right next→end'])
        ascii_lines=['a = "plain-text"','b = [1, 2, 3]','# A user’s “smart quote” stays unchanged.']
        body='טקסט עברי רגיל עם סימנים ומרווחים.\n'+listing(ascii_lines)+r'טווח \en{left—right} ומשוואה $E=mc^2$.'
        cls.compile('unchanged-control',document(body),ascii_lines)
        cls.compile('unchanged-control-before',document(body),ascii_lines,mutation=True)

    @classmethod
    def compile(cls,name,source,lines,*,mutation=False,external=None):
        p=cls.root/name;p.mkdir()
        core=cls.core
        if mutation:
            core,count=re.subn(PATCH_RE,'',core,flags=re.S)
            if count!=1:raise AssertionError('exactly one technical-symbol block must be removed')
        (p/'preamble.tex').write_text(core,encoding='utf-8')
        for asset in ('reader_theme.tex','clean_theme.tex'):shutil.copyfile(ROOT/'assets'/asset,p/asset)
        (p/'probe.tex').write_text(source,encoding='utf-8')
        (p/'expected.json').write_text(json.dumps({'lines':lines},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        if external is not None:(p/'external.txt').write_text(external,encoding='utf-8')
        env=dict(cls.env,HEBREW_LATEX_PROJECT_ROOT=str(p))
        for n in (1,2):
            r=subprocess.run(['lualatex','--no-shell-escape','-halt-on-error','-interaction=nonstopmode','probe.tex'],
                             cwd=p,env=env,capture_output=True,text=True,timeout=180)
            (p/f'pass-{n}.txt').write_text(r.stdout+r.stderr,encoding='utf-8')
            if r.returncode:raise AssertionError(name+': '+r.stdout[-5000:])
        result=probe(p/'probe.pdf',lines)
        (p/'glyphs.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        cls.results[name]=result;cls.sources[name]=p

    def test_01_all_styles_languages_themes_preserve_source_codepoints(self):
        for theme in ('core','reader','clean'):
            r=self.results['matrix-'+theme]
            self.assertTrue(r['match'],(theme,r['actual'],r['expected']))
            self.assertEqual(r['pages'],8,theme)
            self.assertTrue(set(SYMBOLS)<=set(r['actual']))

    def test_02_removing_only_new_registration_reproduces_reordering(self):
        r=self.results['mutation-unregistered'];self.assertFalse(r['match'])
        self.assertIsNotNone(r['first_mismatch'])
        self.assertIn('–leftright',r['actual'])
        self.assertIn('left–right',r['expected'])

    def test_03_explicit_literate_mapping_and_extendedchars_are_preserved(self):
        for name in ('extended-false','explicit-literate'):
            self.assertTrue(self.results[name]['match'],name)

    def test_04_inline_forms_external_file_and_active_character_scope(self):
        for name in ('inline-and-file','active-scope','latex-escape'):
            self.assertTrue(self.results[name]['match'],(name,self.results[name]['actual']))

    def test_05_line_and_page_breaks_keep_the_declared_stream(self):
        for name in ('wrapped-lines','page-split'):
            self.assertTrue(self.results[name]['match'],(name,self.results[name]['first_mismatch']))
        self.assertGreaterEqual(self.results['page-split']['pages'],2)

    def test_06_ascii_existing_quotes_and_prose_are_pixel_identical(self):
        paths=[self.sources[x]/'probe.pdf' for x in ('unchanged-control','unchanged-control-before')]
        with fitz.open(paths[0]) as after,fitz.open(paths[1]) as before:
            self.assertEqual(len(after),len(before))
            for a,b in zip(after,before):
                pa=a.get_pixmap(dpi=144);pb=b.get_pixmap(dpi=144)
                self.assertEqual((pa.width,pa.height,pa.n,pa.samples),(pb.width,pb.height,pb.n,pb.samples))
        self.assertTrue(self.results['unchanged-control']['match'])
        self.assertTrue(self.results['unchanged-control-before']['match'])

    def test_07_every_fixed_page_is_a4_with_no_missing_glyphs(self):
        for name,p in self.sources.items():
            if name.startswith('mutation'):continue
            log=(p/'probe.log').read_text(encoding='utf-8')
            self.assertNotIn('Missing character:',log,name)
            self.assertNotIn('Overfull \\hbox',log,name)
            self.assertNotIn('Overfull \\vbox',log,name)
            with fitz.open(p/'probe.pdf') as doc:
                for page in doc:
                    self.assertAlmostEqual(page.rect.width,595.276,places=1)
                    self.assertAlmostEqual(page.rect.height,841.89,places=1)

    def test_08_actual_build_pipeline_accepts_source_faithful_pdf(self):
        p=self.root/'pipeline';p.mkdir()
        for a in ('preamble.tex','reader_theme.tex'):shutil.copyfile(ROOT/'assets'/a,p/a)
        (p/'probe.tex').write_text(document(listing(SAMPLES),'reader'),encoding='utf-8')
        env=dict(self.env,HEBREW_LATEX_PROJECT_ROOT=str(p),REPRO='1')
        # Explicitly clear caller document contracts: this is an isolated fixture.
        for key in ('CONTENT_PROFILE','EXPECTED_PAPER','SECTION_MACROS','PDF_REQUIRE_TITLE','PDF_MIN_BOOKMARKS',
                    'PDF_MIN_BOOKMARK_DEPTH','PDF_WARN_NO_OUTLINE_AFTER','MAX_CROSS_PAGE_DESTINATIONS','DIRECT_NAVIGATION_DESTINATIONS'):
            env.pop(key,None)
        r=subprocess.run(['bash',str(ROOT/'scripts/build.sh'),str(p/'probe.tex')],env=env,
                         cwd=p,capture_output=True,text=True,timeout=300)
        (p/'build.log').write_text(r.stdout+r.stderr,encoding='utf-8')
        self.assertEqual(r.returncode,0,r.stdout[-7000:]+r.stderr)
        result=probe(p/'probe.pdf',SAMPLES)
        self.assertTrue(result['match']);self.results['pipeline']=result;self.sources['pipeline']=p

    def test_09_both_render_backends_replay_without_claiming_review(self):
        p=self.sources['inline-and-file'];pdf=p/'probe.pdf'
        for backend in ('poppler','mupdf'):
            out=p/('render-'+backend)
            render(pdf,out,144,backend=backend)
            self.assertEqual(verify(pdf,out/'review.json',require_attestations=False,rerender=True),[])
            self.assertTrue(verify(pdf,out/'review.json',require_attestations=True))

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls,'root') and cls.root.exists():
            summary={name:{k:v for k,v in result.items() if k!='glyphs'} for name,result in cls.results.items()}
            (cls.root/'results.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            shutil.rmtree(cls.root/'font-cache',ignore_errors=True)

if __name__=='__main__':unittest.main(verbosity=2)
