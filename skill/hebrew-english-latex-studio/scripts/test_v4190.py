#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Original project code; scope and terms: ../LICENSING.md.
"""Empirical PDF-string boundaries and explicit, non-substituting render backends."""
from __future__ import annotations
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.dont_write_bytecode = True
import fitz
from pdf_string_source import FLAG, linebreak_findings
from render_review import digest, record, render, verify
from render_backends import check_raster_budget, MAX_PAGE_PIXELS
ROOT = Path(__file__).resolve().parent.parent
BAD = r'\section{אלפא\\*[2pt]בטא}'
CASES = [
 ('star', r'\section{אלפא\\*בטא}', 1),
 ('length', r'\section{אלפא\\[2pt]בטא}', 1),
 ('star_length', BAD, 1),
 ('plain', r'\section{אלפא\\בטא}', 0),
 ('plain_barrier', r'\section{אלפא\\{}[text]בטא}', 0),
 ('multiline', '\\section{אלפא\\\\\n [2pt]בטא}', 1),
 ('safe_short', r'\section[אלפא בטא]{אלפא\\*[2pt]בטא}', 0),
 ('bad_short', r'\section[אלפא\\*[2pt]בטא]{אלפא בטא}', 1),
 ('safe_pdf_branch', r'\section{\texorpdfstring{אלפא\\*[2pt]בטא}{אלפא בטא}}', 0),
 ('bad_pdf_branch', r'\section{\texorpdfstring{אלפא בטא}{אלפא\\*[2pt]בטא}}', 1),
 ('nested_pdf_branch', r'\section{\texorpdfstring{x}{\texorpdfstring{y}{אלפא\\*[2pt]בטא}}}', 1),
 ('nested_safe_branch', r'\section{\texorpdfstring{x}{\texorpdfstring{אלפא\\*[2pt]בטא}{תקין}}}', 0),
 ('formatted', r'\section{\textbf{אלפא\\*[2pt]בטא}}', 1),
 ('subsection', BAD.replace('section','subsection'), 1),
 ('paragraph', BAD.replace('section','paragraph'), 1),
 ('starred_heading', BAD.replace('section{','section*{'), 0),
 ('english', r'\begin{englishprose}\section{Alpha\\*[2pt]Beta}\end{englishprose}', 1),
 ('comment', '% '+BAD, 0),
 ('literal', r'\verb|'+BAD+'|', 0),
 ('literal_percent', r'\verb|50%| '+BAD, 1),
 ('listing', '\\begin{lstlisting}\n'+BAD+'\n\\end{lstlisting}', 0),
 ('definition', r'\newcommand{\demo}{'+BAD+'}', 0),
 ('primitive_definition', r'\def\demo{'+BAD+'}', 0),
 ('prose_break', r'\section{תקין} אלפא\\*[2pt]בטא', 0),
 ('metadata_title', r'\hypersetup{pdftitle={אלפא\\[2pt]בטא}}', 1),
 ('metadata_author', r'\hypersetup{pdfauthor={אלפא\\*בטא}}', 1),
 ('metadata_subject', r'\hypersetup{pdfsubject={אלפא\\*[2pt]בטא}}', 1),
 ('metadata_keywords', r'\hypersetup{pdfkeywords={אלפא,\\*[2pt]בטא}}', 1),
 ('metadata_multiple', r'\hypersetup{pdftitle={א\\*[2pt]ב},pdfauthor={ג\\*[2pt]ד}}', 2),
 ('metadata_unrelated_key', r'\hypersetup{unknown={אלפא\\*[2pt]בטא}}', 0),
 ('metadata_definition', r'\newcommand{\demo}{\hypersetup{pdftitle={א\\*[2pt]ב}}}', 0),
 ('metadata_safe_projection', r'\hypersetup{pdftitle={\texorpdfstring{א\\*[2pt]ב}{א ב}}}', 0),
 ('url_destination', r'\section{\href{https://example.invalid/\\*[2pt]}{תקין}}', 0),
 ('href_label', r'\section{\href{https://example.invalid/}{א\\*[2pt]ב}}', 1),
 ('line_comment_consumed', '\\section{א\\\\% comment\n*[2pt]ב}', 1),
]
class SourceTests(unittest.TestCase):
    def test_precise_source_line(self):
        self.assertEqual(linebreak_findings('\n\n'+BAD)[0][0],3)
    def test_real_gate_rejects_then_accepts(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'main.tex'
            for text, code in [(BAD,1),(r'\section[אלפא בטא]{אלפא\\*[2pt]בטא}',0)]:
                p.write_text(text,encoding='utf-8')
                out=subprocess.run([sys.executable,str(ROOT/'scripts/check_source_hazards.py'),str(p)],capture_output=True,text=True,timeout=30)
                self.assertEqual(out.returncode,code,out.stdout+out.stderr)
                self.assertEqual('['+FLAG+']' in out.stdout,code==1)
    def test_completed_literal_forms_preserve_live_pdf_string_findings(self):
        for prefix in [r'\verb{literal{', r'\verb*{literal{', r'\verb[ordinary[',
                       r'\lstinline{{literal}', r'\lstinline*literal*',
                       r'\lstinline[basicstyle={\ttfamily},morekeywords={a]b}]!literal!',
                       '\\lstinline[language=Python,% ] comment\ncolumns=fullflexible]|literal|']:
            with self.subTest(prefix=prefix):
                results = linebreak_findings(prefix+'\n'+BAD)
                self.assertEqual([row[1] for row in results], [FLAG])
                self.assertEqual(results[0][0], prefix.count('\n')+2)
    def test_incomplete_literals_never_hide_live_pdf_string_findings(self):
        for prefix in [r'\verb|unclosed', r'\verb{unclosed',
                       r'\lstinline|unclosed', r'\lstinline{unclosed',
                       r'\lstinline[language=Python', r'\begin{verbatim}']:
            with self.subTest(prefix=prefix):
                results = linebreak_findings(prefix+'\n'+BAD)
                self.assertEqual([row[1] for row in results], [FLAG])
                self.assertEqual(results[0][0], 2)
    def test_brace_literal_does_not_blind_real_pdf_string_gate(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td)/'main.tex'
            path.write_text('\\verb{literal{\n'+BAD, encoding='utf-8')
            result = subprocess.run([sys.executable, str(ROOT/'scripts/check_source_hazards.py'),
                                     str(path)], capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 1, result.stdout+result.stderr)
            self.assertIn(':2: ['+FLAG+']', result.stdout)
for name, raw, expected in CASES:
    def case(self,raw=raw,expected=expected):
        results=linebreak_findings(raw)
        self.assertEqual(len(results),expected,results)
        self.assertTrue(all(row[1]==FLAG for row in results))
    setattr(SourceTests,'test_'+name,case)


def fixture(path: Path, *, unit: float=1, rotation: int=0, offset: bool=False,
            pages: int=1) -> None:
    with fitz.open() as doc:
        for _ in range(pages):
            p=doc.new_page(width=240,height=180)
            p.draw_rect(fitz.Rect(55,40,75,60),color=None,fill=(1,0,0))
            p.draw_rect(fitz.Rect(5,5,20,20),color=None,fill=(0,0,1))
            if offset:
                doc.xref_set_key(p.xref,'MediaBox','[10 20 250 200]')
                doc.xref_set_key(p.xref,'CropBox','[50 50 170 150]')
            else:
                p.set_cropbox(fitz.Rect(40,30,160,130))
            doc.xref_set_key(p.xref,'UserUnit',str(unit))
            p.set_rotation(rotation)
        doc.save(path)

class RenderTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name); self.pdf=self.root/'doc.pdf'; fixture(self.pdf)
    def draw(self,backend='mupdf',box='cropbox',name='review'):
        out=self.root/name; render(self.pdf,out,72,page_box=box,backend=backend)
        return out, json.loads((out/'review.json').read_text())
    def test_default_stays_poppler(self):
        out=self.root/'default'; render(self.pdf,out,72)
        self.assertEqual(json.loads((out/'review.json').read_text())['renderer_backend'],'poppler')
    def test_mupdf_does_not_call_poppler(self):
        with patch('render_backends.subprocess.run',side_effect=AssertionError('unexpected external renderer')):
            out,data=self.draw()
            self.assertEqual(verify(self.pdf,out/'review.json',require_attestations=False,rerender=True),[])
        self.assertIn('MuPDF',data['renderer'])
    def test_missing_poppler_no_fallback(self):
        with patch('render_backends.shutil.which',return_value=None):
            with self.assertRaisesRegex(ValueError,'no silent'):
                self.draw('poppler')
        self.assertFalse((self.root/'review').exists())
    def test_invalid_backend(self):
        with self.assertRaisesRegex(ValueError,'backend'):
            self.draw('automatic')
    def test_raster_cap_precedes_engine(self):
        with patch('render_review.raster_dimensions',return_value=(10000,10000)), patch('render_review.render_pages',side_effect=AssertionError('too late')):
            with self.assertRaisesRegex(ValueError,'exceeds'):
                self.draw()
        self.assertFalse((self.root/'review').exists())
    def test_budget_edge(self):
        check_raster_budget([(10000,MAX_PAGE_PIXELS//10000)])
        with self.assertRaises(ValueError):
            check_raster_budget([(10000,MAX_PAGE_PIXELS//10000+1)])
    def test_mid_render_failure_no_publication(self):
        def fail(source,stage,*args):
            (stage/'page-1.png').write_bytes(b'partial'); raise ValueError('injected failure')
        with patch('render_review.render_pages',side_effect=fail):
            with self.assertRaisesRegex(ValueError,'injected'):
                self.draw()
        self.assertFalse((self.root/'review').exists())
        self.assertEqual(list(self.root.glob('.hllpdf-review-*')),[])
    def test_wrong_pixel_size_no_publication(self):
        def wrong(source,stage,*args):
            p=fitz.Pixmap(fitz.csRGB,fitz.IRect(0,0,12,10),False); p.save(stage/'page-1.png'); return 'injected'
        with patch('render_review.render_pages',side_effect=wrong):
            with self.assertRaisesRegex(ValueError,'geometry mismatch'):
                self.draw()
        self.assertFalse((self.root/'review').exists())
    def test_new_schema_requires_backend(self):
        out,data=self.draw(); del data['renderer_backend']; (out/'review.json').write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError,'explicit renderer'):
            verify(self.pdf,out/'review.json',require_attestations=False)
    def test_backend_identity_mismatch_rejected(self):
        out,data=self.draw(); data['renderer_backend']='poppler'; (out/'review.json').write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError,'identity disagrees'):
            verify(self.pdf,out/'review.json',require_attestations=False)
    def test_legacy_cannot_be_relabelled(self):
        out,data=self.draw(); data['schema']=2; (out/'review.json').write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError,'legacy'):
            verify(self.pdf,out/'review.json',require_attestations=False,rerender=True)
    def test_schema2_replay_remains_poppler(self):
        out,data=self.draw('poppler'); data['schema']=2; data.pop('renderer_backend'); (out/'review.json').write_text(json.dumps(data))
        self.assertEqual(verify(self.pdf,out/'review.json',require_attestations=False,rerender=True),[])
    def test_schema1_replay_keeps_full_media(self):
        out,data=self.draw('poppler','mediabox'); data['schema']=1
        for key in ['renderer_backend','page_box']: data.pop(key)
        for item in data['pages']:
            item.pop('width_px'); item.pop('height_px')
        (out/'review.json').write_text(json.dumps(data))
        self.assertEqual(verify(self.pdf,out/'review.json',require_attestations=False,rerender=True),[])
    def test_pending_not_automatic_approval(self):
        out,data=self.draw(); self.assertEqual(data['schema'],3)
        self.assertEqual(data['pages'][0]['status'],'pending')
        self.assertTrue(verify(self.pdf,out/'review.json'))
    def test_selected_attestation_only(self):
        self.pdf.unlink(); fixture(self.pdf,pages=2)
        out,data=self.draw(); record(self.pdf,out/'review.json','1','automated test','Synthetic attestation control, not a visual review')
        data=json.loads((out/'review.json').read_text())
        self.assertEqual([i['status'] for i in data['pages']],['reviewed','pending'])
        self.assertTrue(verify(self.pdf,out/'review.json'))
    def test_image_swapped_even_with_updated_hash_is_detected(self):
        out,data=self.draw(); image=out/data['pages'][0]['image']
        pix=fitz.Pixmap(str(image)); pix.set_pixel(0,0,(0,0,0)); pix.save(image)
        data['pages'][0]['sha256']=digest(image); (out/'review.json').write_text(json.dumps(data))
        self.assertEqual(verify(self.pdf,out/'review.json',require_attestations=False),[])
        self.assertTrue(any('pixels differ' in e for e in verify(self.pdf,out/'review.json',require_attestations=False,rerender=True)))
    def test_source_change_detected(self):
        out,data=self.draw(); self.pdf.write_bytes(self.pdf.read_bytes()+b'\n%changed\n')
        self.assertTrue(any('PDF digest' in e for e in verify(self.pdf,out/'review.json',require_attestations=False)))
    def test_no_overwrite(self):
        out,data=self.draw()
        with self.assertRaisesRegex(ValueError,'already exists'): self.draw()
    def test_content_crop_and_media(self):
        for backend in ('mupdf','poppler'):
            for box in ('cropbox','mediabox'):
                with self.subTest(backend=backend,box=box):
                    out,data=self.draw(backend,box,name=backend+box)
                    pix=fitz.Pixmap(str(out/data['pages'][0]['image']))
                    rgb=list(zip(*[iter(pix.samples)]*pix.n))
                    self.assertGreater(rgb.count((255,0,0)),300)
                    self.assertEqual(rgb.count((0,0,255))>0,box=='mediabox')
    def test_scaled_poppler_must_match_or_reject_not_substitute(self):
        self.pdf.unlink(); fixture(self.pdf,unit=2)
        try:
            out,data=self.draw('poppler')
        except ValueError as exc:
            self.assertIn('geometry mismatch',str(exc)); self.assertFalse((self.root/'review').exists())
        else:
            self.assertEqual(data['renderer_backend'],'poppler')
            self.assertEqual((data['pages'][0]['width_px'],data['pages'][0]['height_px']),(240,200))

# 3 scales x 4 rotations x 2 boxes. Each is a separately reported test method.
for unit in (0.5,1,2):
    for rotation in (0,90,180,270):
        for box in ('cropbox','mediabox'):
            def test(self,unit=unit,rotation=rotation,box=box):
                self.pdf.unlink(); fixture(self.pdf,unit=unit,rotation=rotation)
                before=digest(self.pdf); out,data=self.draw(box=box)
                dims=(120,100) if box=='cropbox' else (240,180)
                if rotation%180: dims=dims[::-1]
                expected=tuple(round(i*unit) for i in dims)
                self.assertEqual((data['pages'][0]['width_px'],data['pages'][0]['height_px']),expected)
                self.assertEqual(verify(self.pdf,out/'review.json',require_attestations=False,rerender=True),[])
                self.assertEqual(digest(self.pdf),before)
            setattr(RenderTests,f'test_geometry_{str(unit).replace(".","_")}_{rotation}_{box}',test)
for rotation in (0,90,180,270):
    for box in ('cropbox','mediabox'):
        def test(self,rotation=rotation,box=box):
            self.pdf.unlink(); fixture(self.pdf,unit=2,rotation=rotation,offset=True)
            before=digest(self.pdf); out,data=self.draw(box=box)
            dims=(240,200) if box=='cropbox' else (480,360)
            if rotation%180: dims=dims[::-1]
            self.assertEqual((data['pages'][0]['width_px'],data['pages'][0]['height_px']),dims)
            self.assertEqual(digest(self.pdf),before)
            pix=fitz.Pixmap(str(out/data['pages'][0]['image']))
            self.assertIn(bytes((255,0,0)),pix.samples)
        setattr(RenderTests,f'test_offset_{rotation}_{box}',test)
if __name__=='__main__': unittest.main(verbosity=2)
