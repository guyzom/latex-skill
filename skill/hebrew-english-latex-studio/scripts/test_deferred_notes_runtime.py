#!/usr/bin/env python3
"""Real-engine keyed-note controls: identity, counters, text, links and misuse.

Set HLLPDF_NOTES_EVIDENCE_DIR to a NEW directory to preserve all measured inputs,
engine outputs and PDFs. Without it, fixtures are isolated and removed on exit.
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
ROOT = Path(__file__).resolve().parent.parent
HEADER = r'''\def\lakitdocumentclass{article}
\def\lakitclassoptions{11pt,a4paper}
\def\lakitgeometryoptions{margin=2.2cm,headheight=14pt}
\def\lakitlinespread{1.16}
\input{preamble.tex}
\input{deferred_notes.tex}
\input{reader_theme.tex}
\hypersetup{pdftitle={Keyed note controls},pdfauthor={Synthetic QA}}
'''
DECL = r'''\DeclareDocNote{alpha}{\en{BODYA}: הערה ראשונה עם נוסחה $x=2$.}
\DeclareDocNote{beta}{\en{BODYB}: הערה שנייה שאינה אותה רשומה.}
\DeclareDocNote[english]{english}{BODYEN: English text with code \code{sample[10]}.}
\DeclareDocNote{unused}{UNUSED-BODY}
'''
BODY = r'''\begin{document}
\section{בדיקת הערות}
הערה רגילה\footnote{\en{NORMALONE}: הערה רגילה לפני הקופסה.}.
\begin{notebox}[frametitle={קופסה קצרה}]
\en{MARKA}\DocNoteMark{alpha}, \en{MARKB}\DocNoteMark{beta},
ואז אותה הערה שוב: \en{REPEATA}\DocNoteMark{alpha}.
\end{notebox}
\PrintDocNotes
הערה רגילה אחרי הקופסה\footnote{\en{NORMALFOUR}: המספור חייב להמשיך.}.
\begin{tablebox}\centering
\begin{tabular}{p{5cm}p{3cm}}
תא עם הערה\DocNoteMark{english} & $42$\\
\end{tabular}
\tabcap{\label{tab:notes}טבלה קצרה עם הערה באנגלית.}
\end{tablebox}
\PrintDocNotes
\PrintDocNotes
\typeout{HLLCOUNTER=\arabic{footnote}}
\clearpage
\section{הפניה מעמוד נוסף}
אותו מקור בעמוד הקודם\DocNoteMark{alpha}.
\begin{englishprose}Same English note\DocNoteMark{english}.\end{englishprose}
הערה רגילה אחרונה\footnote{\en{NORMALSIX}: הערה אחרונה.}.
\end{document}
'''


def linked_digits(doc, name):
    result = []
    for page in doc:
        for link in page.get_links():
            if link.get('nameddest') == name:
                box = link['from'] + (-.2,-.2,.2,.2)
                result.append(''.join(re.findall(r'\d+', page.get_textbox(box))))
    return result


class DeferredNotesRuntime(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        keep = os.environ.get('HLLPDF_NOTES_EVIDENCE_DIR')
        cls.tmp = None if keep else tempfile.TemporaryDirectory(prefix='hllpdf-notes-')
        cls.root = Path(keep) if keep else Path(cls.tmp.name)
        if keep: cls.root.mkdir(parents=True, exist_ok=False)
        fonts = str(font_dir()); cls.env = os.environ.copy()
        cls.env.pop('HEBREW_LATEX_PROJECT_ROOT', None)
        cls.env.update(OSFONTDIR=fonts, TTFONTS=fonts+'//:', HEBREW_LATEX_FONT_DIR=fonts,
                       SOURCE_DATE_EPOCH='1700000000', TZ='UTC', PYTHONDONTWRITEBYTECODE='1')
        cls.result, cls.positive_dir = cls.compile(HEADER+DECL+BODY, 'positive', passes=3)

    @classmethod
    def tearDownClass(cls):
        if cls.tmp: cls.tmp.cleanup()

    @classmethod
    def compile(cls, text, name, passes=1, mutate=None, production=False):
        directory = cls.root/name; directory.mkdir()
        for asset in ['preamble.tex','reader_theme.tex','deferred_notes.tex']:
            shutil.copyfile(ROOT/'assets'/asset, directory/asset)
        if mutate:
            p=directory/'deferred_notes.tex'; old=p.read_text(); new=mutate(old)
            if old == new: raise AssertionError('mutation did not change the shipped asset')
            p.write_text(new)
        (directory/'main.tex').write_text(text, encoding='utf-8')
        for i in range(passes):
            command = (['bash', str(ROOT/'scripts/build.sh'), str(directory/'main.tex')]
                       if production else ['lualatex','--no-shell-escape','-halt-on-error',
                                          '-interaction=nonstopmode','main.tex'])
            r = subprocess.run(command,cwd=directory,env=cls.env,capture_output=True,
                               text=True,timeout=180)
            (directory/f'pass-{i+1}.txt').write_text(r.stdout+r.stderr)
            if r.returncode: break
        return r,directory

    def positive(self):
        self.assertEqual(self.result.returncode,0,self.result.stdout[-4000:])
        return fitz.open(self.positive_dir/'main.pdf')

    def failure(self, body, name, phrase, preamble=HEADER+DECL):
        r,p = self.compile(preamble+r'\begin{document}'+body+r'\end{document}',name)
        self.assertNotEqual(r.returncode,0)
        self.assertIn(phrase,' '.join(re.sub(r'\(hllnotes\)', '', r.stdout).split()))
        return p

    def test_shared_numbering_and_no_duplicate_bodies(self):
        self.assertIn('HLLCOUNTER=5',self.result.stdout)
        with self.positive() as d:
            self.assertEqual(len(d),2)
            text='\n'.join(p.get_text() for p in d)
            for token in ['BODYA','BODYB','BODYEN','NORMALONE','NORMALFOUR','NORMALSIX']:
                self.assertEqual(text.count(token),1,token)
            self.assertNotIn('UNUSED-BODY',text)
            for key,digits in [('alpha',['2','2','2']),('beta',['3']),('english',['5','5'])]:
                self.assertEqual(linked_digits(d,'hllnote.'+key),digits)
            self.assertEqual(linked_digits(d,'Hfootnote.1'),['1'])
            self.assertEqual(linked_digits(d,'Hfootnote.2'),['4'])
            self.assertEqual(linked_digits(d,'Hfootnote.3'),['6'])

    def test_each_key_links_near_its_own_body_not_just_any_valid_target(self):
        with self.positive() as d:
            names=d.resolve_names()
            for key,token in [('alpha','BODYA'),('beta','BODYB'),('english','BODYEN')]:
                target=names['hllnote.'+key]; self.assertEqual(target['page'],0)
                hit=d[0].search_for(token)[0]
                y=d[0].rect.height-target['to'][1]
                self.assertLessEqual(abs(y-hit.y0),14,(key,y,hit))
                self.assertTrue(0 <= target['to'][0] <= d[0].rect.width)
            self.assertNotIn('hllnote.unused',names)
            later=[l for l in d[1].get_links() if l.get('nameddest','').startswith('hllnote.')]
            self.assertEqual([l['nameddest'] for l in later],['hllnote.alpha','hllnote.english'])
            self.assertTrue(all(l['page']==0 for l in later))

    def test_language_is_captured_not_inherited_from_flush(self):
        with self.positive() as d:
            page=d[0]; en=page.search_for('BODYEN')[0]
            self.assertLess(en.x0,100)  # English footnote starts on physical left.
            self.assertIn('English text with code sample[10]',page.get_text())
            self.assertNotIn('sample[01]',page.get_text())

    def test_two_digit_marks_keep_physical_order(self):
        declares='\n'.join(fr'\DeclareDocNote{{n{i}}}{{\en{{BODY{i}}}: הערת בדיקה.}}' for i in range(9,13))
        marks=' '.join(fr'מזהה\DocNoteMark{{n{i}}}.' for i in range(9,13))
        r,p=self.compile(HEADER+declares+r'\begin{document}\setcounter{footnote}{8}'+marks+
                         r'\PrintDocNotes עוד\footnote{LASTTHIRTEEN}.\end{document}', 'two-digit', passes=3)
        self.assertEqual(r.returncode,0,r.stdout[-3000:])
        with fitz.open(p/'main.pdf') as d:
            for i in range(9,13): self.assertEqual(linked_digits(d,'hllnote.n'+str(i)),[str(i)])
            self.assertEqual(linked_digits(d,'Hfootnote.1'),['13'])

    def test_undeclared_key_is_fatal(self):
        self.failure(r'טקסט\DocNoteMark{absent}.','unknown','undeclared note')

    def test_duplicate_declaration_is_fatal(self):
        self.failure(r'\DeclareDocNote{alpha}{אחרת}','duplicate','already declared')

    def test_unused_declaration_and_empty_flush_do_nothing(self):
        text=HEADER+DECL+r'\begin{document}\PrintDocNotes טקסט\footnote{ONLYBODY}.\PrintDocNotes\end{document}'
        r,p=self.compile(text,'empty',passes=2); self.assertEqual(r.returncode,0,r.stdout[-3000:])
        with fitz.open(p/'main.pdf') as d:
            self.assertEqual(linked_digits(d,'Hfootnote.1'),['1'])
            self.assertFalse(any(k.startswith('hllnote.') for k in d.resolve_names()))

    def test_unprinted_note_is_fatal_at_end(self):
        self.failure(r'טקסט\DocNoteMark{alpha}.','unprinted','unprinted notes')

    def test_pending_notes_block_later_ordinary_footnote(self):
        self.failure(r'טקסט\DocNoteMark{alpha}. עוד\footnote{אחרת}.','interleaved','before an ordinary footnote')

    def test_pending_notes_block_chapter_reset(self):
        self.failure(r'\chapter{א}טקסט\DocNoteMark{alpha}.\chapter{ב}', 'chapter-pending',
                     'before a chapter',preamble=(HEADER+DECL).replace('{article}','{report}',1))

    def test_chapter_reset_has_unique_keyed_targets(self):
        text=(HEADER+DECL).replace('{article}','{report}',1)+r'''\begin{document}
\chapter{א}טקסט\DocNoteMark{alpha}.\PrintDocNotes
\chapter{ב}טקסט\DocNoteMark{beta}.\PrintDocNotes\end{document}'''
        r,p=self.compile(text,'chapter-safe',passes=3); self.assertEqual(r.returncode,0,r.stdout[-3000:])
        with fitz.open(p/'main.pdf') as d:
            names=d.resolve_names()
            self.assertEqual(names['hllnote.alpha']['page'],0)
            self.assertEqual(names['hllnote.beta']['page'],1)
            self.assertEqual(linked_digits(d,'hllnote.alpha'),['1'])
            self.assertEqual(linked_digits(d,'hllnote.beta'),['1'])

    def test_nested_notes_and_recursive_flush_are_fatal(self):
        for i,inner in enumerate([r'\footnote{nested}',r'\DocNoteMark{beta}',r'\PrintDocNotes']):
            with self.subTest(inner=inner):
                pre=HEADER+DECL+fr'\DeclareDocNote{{nested}}{{טקסט {inner}}}'
                self.failure(r'טקסט\DocNoteMark{nested}.\PrintDocNotes',f'nested-{i}',
                             'nested notes',preamble=pre)

    def test_flush_in_box_is_fatal(self):
        for i,(a,b) in enumerate([(r'\begin{notebox}',r'\end{notebox}'),
                                   (r'\begin{minipage}{4cm}',r'\end{minipage}')]):
            with self.subTest(i=i):
                self.failure(a+r'טקסט\DocNoteMark{alpha}.\PrintDocNotes'+b,
                             f'inner-{i}','flush outside')

    def test_flush_in_multiple_columns_is_fatal(self):
        self.failure(r'\twocolumn טקסט\DocNoteMark{alpha}.\PrintDocNotes',
                     'two-column','flush outside')
        self.failure(r'\begin{multicols}{2}טקסט\DocNoteMark{alpha}.\PrintDocNotes\end{multicols}',
                     'multicols','flush outside',preamble=HEADER+DECL+r'\usepackage{multicol}')

    def test_keys_languages_and_empty_bodies_fail_closed(self):
        for i,decl,phrase in [(1,r'\DeclareDocNote{../x}{text}','invalid literal'),
                              (2,r'\DeclareDocNote{a b}{text}','invalid literal'),
                              (3,r'\DeclareDocNote[french]{x}{text}','note language'),
                              (4,r'\DeclareDocNote{x}{  }','empty body')]:
            with self.subTest(i=i): self.failure(decl, f'declaration-{i}', phrase)

    def test_marks_in_math_and_before_document_are_fatal(self):
        self.failure(r'$x\DocNoteMark{alpha}$','math','marks belong in text')
        r,p=self.compile(HEADER+DECL+r'\DocNoteMark{alpha}\begin{document}Text\end{document}',
                         'preamble-mark'); self.assertNotEqual(r.returncode,0)
        self.assertIn('requires the document body',' '.join(re.sub(r'\(hllnotes\)', '', r.stdout).split()))

    def test_non_arabic_numbering_is_rejected(self):
        self.failure(r'\renewcommand{\thefootnote}{\alph{footnote}}טקסט\DocNoteMark{alpha}.\PrintDocNotes',
                     'number-style','Arabic footnote numbering')

    def test_old_explicit_workaround_reproduces_duplicate_numbers(self):
        text=HEADER.replace(r'\input{deferred_notes.tex}','')+r'''\begin{document}
רגילה\footnote{BODYONE}.
\begin{notebox}ראשונה\footnotemark[2]. שנייה\footnotemark[3].\end{notebox}
\footnotetext[2]{BODYTWO}\footnotetext[3]{BODYTHREE}
אחרונה\footnote{BODYLAST}.\typeout{OLDCOUNTER=\arabic{footnote}}\end{document}'''
        r,p=self.compile(text,'old-workaround',production=True)
        self.assertEqual(r.returncode,0,(r.stdout+r.stderr)[-4000:])
        with fitz.open(p/'main.pdf') as d:
            self.assertEqual(linked_digits(d,'Hfootnote.2'),['2'])
            self.assertEqual(len(d[0].get_links()),2)  # Only the ordinary marks link.
            self.assertIn('BODYTWO',d[0].get_text()); self.assertIn('BODYTHREE',d[0].get_text())

    def test_counter_mutation_is_observable(self):
        r,p=self.compile(HEADER+DECL+BODY,'counter-mutant',passes=3,
                         mutate=lambda s:s.replace(r'\stepcounter{footnote}',r'\relax'))
        self.assertEqual(r.returncode,0,r.stdout[-3000:])
        with fitz.open(p/'main.pdf') as d:
            self.assertNotEqual(linked_digits(d,'hllnote.alpha'),['2','2','2'])
            self.assertEqual(linked_digits(d,'hllnote.alpha'),['1','1','1'])

    def test_valid_but_wrong_link_target_mutation_is_observable(self):
        r,p=self.compile(HEADER+DECL+BODY,'wrong-link-mutant',passes=3,
                         mutate=lambda s:s.replace(r'\hyperlink{hllnote.#1}',r'\hyperlink{hllnote.alpha}'))
        self.assertEqual(r.returncode,0,r.stdout[-3000:])
        with fitz.open(p/'main.pdf') as d:
            self.assertIn('hllnote.beta',d.resolve_names())  # A valid target is insufficient.
            self.assertEqual(linked_digits(d,'hllnote.beta'),[])
            self.assertIn('3',linked_digits(d,'hllnote.alpha'))

    def test_failed_production_build_does_not_publish_unprinted_notes(self):
        r,p=self.compile(HEADER+r'\begin{document}טקסט תקין.\end{document}',
                         'production-atomic',production=True)
        self.assertEqual(r.returncode,0,(r.stdout+r.stderr)[-4000:])
        saved=(p/'main.pdf').read_bytes()
        (p/'main.failed.pdf').write_bytes(saved)  # stale diagnostic from a prior failed run
        (p/'main.tex').write_text(HEADER+DECL+r'\begin{document}טקסט\DocNoteMark{alpha}.\end{document}')
        result=subprocess.run(['bash',str(ROOT/'scripts/build.sh'),str(p/'main.tex')],
                              cwd=p,env=self.env,capture_output=True,text=True,timeout=180)
        (p/'rejected-build.txt').write_text(result.stdout+result.stderr)
        self.assertEqual(result.returncode,1)
        self.assertEqual((p/'main.pdf').read_bytes(),saved)
        self.assertFalse((p/'main.failed.pdf').exists(), 'an empty engine output is not a diagnostic PDF')
        self.assertIn('unprinted notes',' '.join((p/'main.failed.log').read_text().split()))


if __name__=='__main__': unittest.main(verbosity=2)
