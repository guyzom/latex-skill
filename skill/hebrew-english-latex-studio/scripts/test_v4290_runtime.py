#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Original project code; scope and terms: ../LICENSING.md.
"""Real-engine nested-container regressions; geometry is not visual sign-off.

The reader/core/clean matrix covers 6 semantic wrappers x 4 listing styles x
2 outer languages x 3 themes. Independent mutations undo the number, border,
and nearest-container fixes. Evidence can be retained outside the skill with
HLLPDF_429_EVIDENCE_DIR. No font programs are copied to evidence.
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
from render_review import render, verify
ROOT = Path(__file__).resolve().parent.parent
WRAPPERS = ('defbox', 'thmbox', 'notebox', 'exbox', 'warnbox', 'keybox')
STYLES = ('asm', 'cstyle', 'pystyle', 'htmlstyle')
SLATE = (63/255, 74/255, 86/255)
TABLE = (185/255, 196/255, 210/255)
RESTORE = r"""  \ifhllpdf@lstnumbermasked
    \let\thelstnumber\hllpdf@savedlstnumber
    \hllpdf@lstnumbermaskedfalse
  \fi"""
EDGES = 'leftline=true,rightline=true,topline=true,bottomline=true,'

def header(theme='reader'):
    return (r"""\def\lakitdocumentclass{article}
\def\lakitclassoptions{11pt,a4paper}
\input{preamble.tex}
""" + ('' if theme == 'core' else '\\input{'+theme+'_theme.tex}\n') + r"""\hypersetup{pdftitle={Nested container regression},pdfauthor={Synthetic QA}}
\begin{document}
""")

def listing(style='pystyle', first=998, extra='', lines=None):
    body = lines or ['alpha = 10', 'beta = 20', 'result = alpha + beta']
    return (r'\begin{asmblock}'+'\n'+r'\begin{lstlisting}[style='+style+
            ',firstnumber='+str(first)+extra+']\n'+'\n'.join(body)+'\n'+
            r'\end{lstlisting}'+'\n'+r'\end{asmblock}'+'\n')

def matrix(theme, wrappers=WRAPPERS, languages=('hebrew', 'english')):
    out = header(theme)
    for i, (wrapper, lang) in enumerate((w, l) for w in wrappers for l in languages):
        if i: out += '\\newpage\n'
        out += r'\section{בדיקת קינון \en{'+wrapper+' / '+lang+r'}}'+'\n'
        if lang == 'english': out += '\\begin{englishprose}\n'
        out += '\\begin{'+wrapper+'}[nobreak=true]\n'
        for style in STYLES:
            out += r'\begin{codebox}[nobreak=true,frametitle={\en{'+style+r'}}]'+'\n'
            out += listing(style) + '\\end{codebox}\n'
        out += '\\end{'+wrapper+'}\n'
        if lang == 'english': out += '\\end{englishprose}\n'
    return out + '\\end{document}\n'

def mutate(text, kind):
    """Undo one operational fix, never weaken the corresponding assertion."""
    if kind == 'numbers':
        if text.count(RESTORE) != 1: raise AssertionError('number mutation target drifted')
        return text.replace(RESTORE, r'  \relax')
    if kind == 'borders':
        if text.count(EDGES) != 2: raise AssertionError('border mutation targets drifted')
        return text.replace(EDGES, '')
    if kind == 'scope':
        old = r'    \hllpdf@incodeboxfalse'
        if text.count(old) != 1: raise AssertionError('scope mutation target drifted')
        return text.replace(old, r'    \relax')
    raise ValueError(kind)

def same_color(actual, expected):
    return actual is not None and len(actual) == 3 and max(abs(x-y) for x,y in zip(actual,expected)) < .0002

def fills(page, rgb):
    found=[]
    for d in page.get_drawings():
        r=d['rect']
        if same_color(d.get('fill'),rgb) and r.width>100 and r.height>30:
            if not any(max(abs(x-y) for x,y in zip(r,old))<.01 for old in found): found.append(r)
    return sorted(found,key=lambda r:(r.y0,r.x0))

def small_spans(page):
    return [s for b in page.get_text('dict')['blocks'] for l in b.get('lines',[])
            for s in l['spans'] if s['size']<7]

def edges(page, rect, color, tolerance=1.1):
    """Each edge must actually touch THIS fill; a distant page rule cannot pass."""
    found=set()
    for d in page.get_drawings():
        if not same_color(d.get('color'),color): continue
        for item in d['items']:
            if item[0]!='l': continue
            a,b=item[1:]
            if abs(a.x-b.x)<.01 and abs(a.y-b.y)>.8*rect.height:
                lo,hi=sorted((a.y,b.y))
                if lo>rect.y0+tolerance or hi<rect.y1-tolerance: continue
                for name,x in [('left',rect.x0),('right',rect.x1)]:
                    if abs(a.x-x)<=tolerance: found.add(name)
            if abs(a.y-b.y)<.01 and abs(a.x-b.x)>.8*rect.width:
                lo,hi=sorted((a.x,b.x))
                if lo>rect.x0+tolerance or hi<rect.x1-tolerance: continue
                for name,y in [('top',rect.y0),('bottom',rect.y1)]:
                    if abs(a.y-y)<=tolerance: found.add(name)
    return found

# Exact trusted sources used for the visual before/after reproductions.
STRESS = '\\def\\lakitdocumentclass{article}\n\\def\\lakitclassoptions{11pt,a4paper}\n\\input{preamble.tex}\n\\input{reader_theme.tex}\n\\hypersetup{pdftitle={Nested code frames regression},pdfauthor={Synthetic QA}}\n\\begin{document}\n\\section{קוד כחלק מדוגמה}\nטקסט עברי עם הפניה לקטע \\code{parser.py}.\n\\begin{exbox}[frametitle={דוגמה עם קוד ממוספר},nobreak=true]\nהמסגרת הפנימית צריכה לשמור את מספרי השורות שלה.\n\\begin{codebox}[frametitle={\\code{parser.py}},nobreak=true]\n\\begin{asmblock}\n\\begin{lstlisting}[style=pystyle,firstnumber=98]\nalpha = 10\nbeta = 20\nresult = alpha + beta\n\\end{lstlisting}\n\\end{asmblock}\n\\end{codebox}\nקטע קצר ישירות בדוגמה נשאר ללא מספרי שוליים:\n\\begin{asmblock}\n\\begin{lstlisting}[style=pystyle,firstnumber=198]\nleft = 1\nright = 2\nvalue = left + right\n\\end{lstlisting}\n\\end{asmblock}\n\\end{exbox}\n\\begin{asmblock}\n\\begin{lstlisting}[style=pystyle,firstnumber=298]\noutside = True\nvalue = 5\nprint(value)\n\\end{lstlisting}\n\\end{asmblock}\n\\newpage\n\\section{הקשר אנגלי וקינון כפול}\n\\begin{englishprose}\n\\begin{notebox}[frametitle={English outer note},nobreak=true]\n\\begin{exbox}[nobreak=true]\n\\begin{codebox}[frametitle={Nested code},nobreak=true]\n\\begin{asmblock}\n\\begin{lstlisting}[style=pystyle,firstnumber=998]\nalpha = 10\nbeta = 20\nresult = alpha + beta\n\\end{lstlisting}\n\\end{asmblock}\n\\end{codebox}\n\\end{exbox}\n\\end{notebox}\n\\end{englishprose}\n\\newpage\n\\section{אזור סמנטי בתוך מסגרת קוד}\n\\begin{codebox}[frametitle={\\en{Code container}},nobreak=true]\n\\begin{asmblock}\n\\begin{lstlisting}[style=pystyle,firstnumber=398]\nouter_start = 1\nresult = outer_start\nprint(result)\n\\end{lstlisting}\n\\end{asmblock}\n\\begin{notebox}[frametitle={הערה פנימית},nobreak=true]\nהקוד המקומי שייך להערה, ולא לרקע הקוד החיצוני.\n\\begin{asmblock}\n\\begin{lstlisting}[style=pystyle,firstnumber=498]\ninner = 1\nresult = inner\nprint(result)\n\\end{lstlisting}\n\\end{asmblock}\n\\end{notebox}\n\\begin{asmblock}\n\\begin{lstlisting}[style=pystyle,firstnumber=598]\nouter_end = 1\nresult = outer_end\nprint(result)\n\\end{lstlisting}\n\\end{asmblock}\n\\end{codebox}\n\\end{document}\n'
TABLE_SOURCE = '\\def\\lakitdocumentclass{article}\n\\def\\lakitclassoptions{11pt,a4paper}\n\\input{preamble.tex}\n\\input{reader_theme.tex}\n\\hypersetup{pdftitle={Nested neutral table},pdfauthor={Synthetic QA}}\n\\begin{document}\n\\section{טבלה בתוך דוגמה}\n\\begin{exbox}[frametitle={השוואת רכיבים},nobreak=true]\nטבלה פנימית אמורה לשמור מסגרת ניטרלית מלאה.\n\\begin{tablebox}\\centering\n\\begin{tabular}{r r}\n\\toprule\nרכיב & כמות \\\\\n\\midrule\nקלט & \\en{24} \\\\\nפלט & \\en{12} \\\\\n\\bottomrule\n\\end{tabular}\n\\tabcap{\\label{tab:nested}נתונים בתוך דוגמה}\n\\end{tablebox}\nהטבלה מסתיימת כאן, וסגנון הדוגמה נשמר.\n\\end{exbox}\n\\begin{tablebox}\\centering\n\\begin{tabular}{r r}\n\\toprule\nרכיב & כמות \\\\\n\\midrule\nקלט & \\en{24} \\\\\nפלט & \\en{12} \\\\\n\\bottomrule\n\\end{tabular}\n\\tabcap{\\label{tab:plain}טבלה עצמאית להשוואה}\n\\end{tablebox}\nראו טבלה~\\ref{tab:nested} וטבלה~\\ref{tab:plain}.\n\\end{document}\n'

def controls_source():
    out=header()
    out+=r"""\section{מספור מותאם ובחירה ללא מספור}
\renewcommand{\thelstnumber}{Q\arabic{lstnumber}}
\begin{exbox}[nobreak=true]
\begin{notebox}[nobreak=true]
\begin{codebox}[nobreak=true,frametitle={\en{Custom formatter}}]
"""+listing()+r"""\end{codebox}
\begin{codebox}[nobreak=true,frametitle={\en{Explicit numbers=none}}]
"""+listing(first=698,extra=',numbers=none')+r"""\end{codebox}
\end{notebox}
"""+listing(first=798)+r"""\end{exbox}
"""+listing(first=898)+r"""\newpage
\section{אפשרויות מקומיות מפורשות}
\begin{exbox}[nobreak=true]
\begin{codebox}[nobreak=true,leftline=false,bottomline=false,frametitle={\en{Explicit two-edge frame}}]
"""+listing()+r"""\end{codebox}
\end{exbox}
\end{document}
"""
    return out

def split_source():
    return header()+r"""\section{קוד מפוצל בין עמודים}
בדיקת רצף מספרים, מסגרת סגורה וכיוון קוד בעת מעבר עמוד.
\vspace*{.43\textheight}
\begin{codebox}[frametitle={\en{Cross-page code}}]
"""+listing(first=998,lines=[f'value_{i:02d} = {i}' for i in range(30)])+r"""\end{codebox}
טקסט ההמשך מחוץ למסגרת שומר את הכיוון שלו: $E=mc^2$.
\end{document}
"""

class NestedContainers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        chosen=os.environ.get('HLLPDF_429_EVIDENCE_DIR')
        if chosen:
            cls.root=Path(chosen).resolve()
            if cls.root==ROOT or ROOT in cls.root.parents: raise ValueError('evidence must be outside the skill')
            cls.root.mkdir(parents=True,exist_ok=False)
        else:
            cls.tmp=tempfile.TemporaryDirectory(prefix='hllpdf429-runtime-')
            cls.addClassCleanup(cls.tmp.cleanup)
            cls.root=Path(cls.tmp.name)
        fonts=str(font_dir());cls.env=os.environ.copy()
        cls.env.update(HEBREW_LATEX_FONT_DIR=fonts,OSFONTDIR=fonts+':',TTFONTS=fonts+':',
                       SOURCE_DATE_EPOCH='1700000000',TZ='UTC',PYTHONDONTWRITEBYTECODE='1')
        cls.core=(ROOT/'assets/preamble.tex').read_text(encoding='utf-8')
        for theme in ('core','reader','clean'):
            cls.compile('matrix-'+theme,matrix(theme))
        for name,source in [('stress',STRESS),('table',TABLE_SOURCE),('controls',controls_source()),('split',split_source())]:
            cls.compile(name,source)
        cls.compile('mutation-numbers',matrix('reader',('exbox',),('hebrew',)),'numbers')
        cls.compile('mutation-code-edges',matrix('reader',('exbox',),('hebrew',)),'borders')
        cls.compile('mutation-table-edges',TABLE_SOURCE,'borders')
        cls.compile('mutation-scope',STRESS,'scope')
        cls.measurements={}
    @classmethod
    def compile(cls,name,source,mutation=None):
        p=cls.root/name;p.mkdir()
        (p/'preamble.tex').write_text(mutate(cls.core,mutation) if mutation else cls.core,encoding='utf-8')
        for asset in ('reader_theme.tex','clean_theme.tex'):shutil.copyfile(ROOT/'assets'/asset,p/asset)
        (p/'probe.tex').write_text(source,encoding='utf-8')
        env=dict(cls.env,HEBREW_LATEX_PROJECT_ROOT=str(p))
        for n in (1,2):
            r=subprocess.run(['lualatex','--no-shell-escape','-halt-on-error','-interaction=nonstopmode','probe.tex'],
                             cwd=p,env=env,text=True,capture_output=True,timeout=180)
            (p/f'pass-{n}.txt').write_text(r.stdout+r.stderr,encoding='utf-8')
            if r.returncode:raise AssertionError(name+': '+r.stdout[-5000:])
    def test_01_matrix_retains_432_numbers_inside_144_frames(self):
        total=0;clearances=[]
        for theme in ('core','reader','clean'):
            rgb=tuple(x/255 for x in ((244,246,248) if theme=='reader' else (242,244,247)))
            with fitz.open(self.root/f'matrix-{theme}/probe.pdf') as doc:
                self.assertEqual(len(doc),12,theme)
                for p in doc:
                    boxes=fills(p,rgb);self.assertEqual(len(boxes),4,(theme,p.number,boxes))
                    nums=[s for s in small_spans(p) if s['text'] in ('998','999','1000')]
                    self.assertEqual(len(nums),12,(theme,p.number,nums))
                    for box in boxes:
                        row=[s for s in nums if box.y0<s['bbox'][1]<box.y1]
                        self.assertEqual(len(row),3)
                        self.assertEqual(edges(p,box,SLATE),{'left','right','top','bottom'})
                        for s in row:
                            clearance=s['bbox'][0]-box.x0
                            self.assertGreaterEqual(clearance,2,(theme,p.number,s,box))
                            clearances.append(clearance);total+=1
        self.assertEqual(total,432)
        self.measurements['matrix']={'frames':144,'numbers':total,'minimum_left_clearance_pt':min(clearances)}
    def test_02_number_mutation_reproduces_silent_loss(self):
        with fitz.open(self.root/'mutation-numbers/probe.pdf') as doc:
            self.assertEqual(len(doc),1)
            self.assertFalse([s for s in small_spans(doc[0]) if s['text'] in ('998','999','1000')])
    def test_03_code_border_mutation_reproduces_one_edge(self):
        with fitz.open(self.root/'mutation-code-edges/probe.pdf') as doc:
            boxes=fills(doc[0],tuple(x/255 for x in (244,246,248)))
            self.assertEqual(len(boxes),4)
            for box in boxes:self.assertEqual(edges(doc[0],box,SLATE),{'right'})
    def test_04_nested_table_retains_four_edges_and_distinct_links(self):
        for variant,expected in [('table',4),('mutation-table-edges',1)]:
            with fitz.open(self.root/variant/'probe.pdf') as doc:
                self.assertEqual(len(doc),1)
                boxes=fills(doc[0],tuple(x/255 for x in (250,251,252)))
                self.assertEqual(len(boxes),2)
                self.assertEqual(len(edges(doc[0],boxes[0],TABLE)),expected)
                self.assertEqual(len(edges(doc[0],boxes[1],TABLE)),4)
                destinations=doc.resolve_names()
                self.assertIn('tbl.1.1',destinations);self.assertIn('tbl.1.2',destinations)
                self.assertNotEqual(destinations['tbl.1.1']['to'],destinations['tbl.1.2']['to'])
    def test_05_nearest_semantic_container_keeps_its_listing_frame(self):
        for name,want in [('stress',True),('mutation-scope',False)]:
            with fitz.open(self.root/name/'probe.pdf') as doc:
                page=doc[2]
                inner=[s for s in small_spans(page) if s['text'] in ('498','499','500')]
                self.assertEqual(inner,[])
                # A full-width listing inside the amber note has two long
                # horizontal thin table-colored strokes. The old scope has none.
                strokes=[d for d in page.get_drawings() if same_color(d.get('color'),TABLE)
                         and d['rect'].width>300 and d['rect'].height<.01]
                self.assertEqual(len(strokes),2 if want else 0)
                numbers=[s['text'] for s in small_spans(page)]
                self.assertEqual(numbers,['398','399','400','598','599','600'])
    def test_06_nested_and_following_formatter_scope(self):
        with fitz.open(self.root/'controls/probe.pdf') as doc:
            self.assertEqual(len(doc),2)
            self.assertEqual([s['text'] for s in small_spans(doc[0])],
                             ['Q998','Q999','Q1000','Q898','Q899','Q900'])
    def test_07_explicit_edge_overrides_remain_effective(self):
        with fitz.open(self.root/'controls/probe.pdf') as doc:
            boxes=fills(doc[1],tuple(x/255 for x in (244,246,248)))
            self.assertEqual(len(boxes),1)
            # Under the Hebrew mdframed backend leftline is the physical right.
            self.assertEqual(edges(doc[1],boxes[0],SLATE),{'top','left'})
    def test_08_split_code_keeps_every_number_once_and_closes_both_segments(self):
        with fitz.open(self.root/'split/probe.pdf') as doc:
            self.assertEqual(len(doc),2)
            seen=[];segments=0
            for page in doc:
                boxes=fills(page,tuple(x/255 for x in (244,246,248)))
                self.assertEqual(len(boxes),1)
                self.assertEqual(edges(page,boxes[0],SLATE),{'left','right','top','bottom'})
                segments+=1
                nums=[s for s in small_spans(page) if s['text'].isdigit() and 998<=int(s['text'])<=1027]
                for s in nums:
                    self.assertGreater(s['bbox'][0]-boxes[0].x0,2)
                    self.assertLess(s['bbox'][3],boxes[0].y1)
                seen.extend(int(s['text']) for s in nums)
            self.assertEqual(seen,list(range(998,1028)))
            self.measurements['split']={'segments':segments,'numbers':len(seen)}
    def test_09_fixed_logs_geometry_and_metadata_are_clean(self):
        total=0
        for name in ('matrix-core','matrix-reader','matrix-clean','stress','table','controls','split'):
            text=(self.root/name/'probe.log').read_text(encoding='utf-8',errors='replace')
            for bad in ('Missing character:',r'Overfull \hbox',r'Overfull \vbox','undefined references'):
                self.assertNotIn(bad,text,name)
            with fitz.open(self.root/name/'probe.pdf') as doc:
                total+=len(doc)
                self.assertTrue(doc.metadata.get('title'))
                for page in doc:
                    self.assertAlmostEqual(page.rect.width,595.276,delta=.1)
                    self.assertAlmostEqual(page.rect.height,841.890,delta=.1)
        self.measurements['fixed_pages']=total
    def test_10_both_explicit_renderers_can_replay_stress_and_split(self):
        for name in ('stress','split'):
            pdf=self.root/name/'probe.pdf'
            for backend in ('poppler','mupdf'):
                output=self.root/name/backend
                render(pdf,output,144,backend=backend)
                self.assertEqual(verify(pdf,output/'review.json',require_attestations=False,rerender=True),[])
    @classmethod
    def tearDownClass(cls):
        (cls.root/'measurements.json').write_text(json.dumps(cls.measurements,indent=2)+'\n',encoding='utf-8')

if __name__=='__main__':unittest.main(verbosity=2)
