#!/usr/bin/env python3
"""Regression controls for inline language scope, physical PDF size and review boxes."""
from __future__ import annotations
import contextlib
import io
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
from unittest.mock import patch
sys.dont_write_bytecode = True
import fitz
from check_bidi_figures import scan_file
from check_pdf_page_size import check, expected_points
from render_review import digest, render, verify

TARGETS = {'LATIN-BEFORE-PAREN', 'TOKEN-PUNCT-ADRIFT'}
PAREN = {'LATIN-BEFORE-PAREN'}
TOKEN = {'TOKEN-PUNCT-ADRIFT'}
BIDI_CASES = [
 ('foreign_does_not_hide_tail_token', r'ראה \foreignlanguage{english}{term} וגם /audit כאן.', TOKEN),
 ('foreign_does_not_hide_tail_parens', r'ראה \foreignlanguage{english}{term} וגם Skill(/audit) כאן.', PAREN),
 ('spaced_en_token', r'ראה \en {/audit} כאן.', set()),
 ('spaced_en_parens', r'ראה \en {Skill(/audit)} כאן.', set()),
 ('foreign_safe', r'ראה \foreignlanguage{english}{Skill(/audit)} כאן.', set()),
 ('foreign_spaced', r'ראה \foreignlanguage {english} {Skill(/audit)} כאן.', set()),
 ('tight_en_safe', r'ראה \en{Skill(/audit)} כאן.', set()),
 ('en_does_not_hide_tail', r'ראה \en {term} וגם /audit כאן.', TOKEN),
 ('en_does_not_hide_head', r'ראה /audit וגם \en {term} כאן.', TOKEN),
 ('multiple_islands_tail', r'ראה \en{one} וכן \foreignlanguage{english}{two} וגם /audit כאן.', TOKEN),
 ('nested_safe', r'ראה \en {\textbf{Skill(/audit)}} כאן.', set()),
 ('multiline_en', 'ראה \\en {\nSkill(/audit)} כאן.', set()),
 ('multiline_command', 'ראה \\en\n{Skill(/audit)} כאן.', set()),
 ('multiline_foreign', 'ראה \\foreignlanguage\n{english}\n{Skill(/audit)} כאן.', set()),
 ('multiline_closing_tail', 'ראה \\en {\nterm} וגם /audit כאן.', TOKEN),
 ('multiline_closing_parens', 'ראה \\foreignlanguage{english}{\nterm} וגם Skill(/audit) כאן.', PAREN),
 ('comment_in_island', 'ראה \\en {% הסבר\nSkill(/audit)} כאן.', set()),
 ('comment_not_island', '% \\en{\nראה /audit כאן.', TOKEN),
 ('literal_not_island', '\\verb|\\en{|\nראה /audit כאן.', TOKEN),
 ('verbatim_not_island', '\\begin{verbatim}\n\\en{\n\\end{verbatim}\nראה /audit כאן.', TOKEN),
 ('escaped_close_in_island', r'ראה \en {x\} Skill(/audit)} כאן.', set()),
 ('nested_group_tail', r'ראה \en {\textbf{term}} וגם /audit כאן.', TOKEN),
 ('unclosed_not_exemption', 'ראה \\en{\nראה /audit כאן.', TOKEN),
 ('unrelated_language_not_exemption', r'ראה \foreignlanguage{hebrew}{מונח} וגם /audit כאן.', TOKEN),
]

class Scratch(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='hllpdf-4160-')
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def pdf(self, name='sample', width=None, height=None, unit=None, rotation=0, crop=None, indirect=False):
        width = expected_points('a4')[0] if width is None else width
        height = expected_points('a4')[1] if height is None else height
        target = self.root / f'{name}.pdf'
        with fitz.open() as doc:
            page = doc.new_page(width=width, height=height)
            page.insert_text((80, 180), 'VISIBLE CONTENT 123')
            if crop is not None:
                page.set_cropbox(fitz.Rect(crop))
            if unit is not None:
                if indirect:
                    ref = doc.get_new_xref(); doc.update_object(ref, str(unit))
                    doc.xref_set_key(page.xref, 'UserUnit', f'{ref} 0 R')
                else:
                    doc.xref_set_key(page.xref, 'UserUnit', str(unit))
            if rotation:
                page.set_rotation(rotation)
            doc.save(target)
        return target

    def result(self, pdf, expected='a4'):
        with contextlib.redirect_stdout(io.StringIO()):
            return check(str(pdf), expected)

class BidiTests(Scratch):
    pass

for name, text, expected in BIDI_CASES:
    def test(self, text=text, expected=expected):
        path = self.root / 'source.tex'; path.write_text(text, encoding='utf-8')
        found = {flag for _, flag, _ in scan_file(str(path))} & TARGETS
        self.assertEqual(found, expected)
    setattr(BidiTests, 'test_' + name, test)

class GeometryTests(Scratch):
    def test_missing_pymupdf_is_tooling_exit_two(self):
        # Run an isolated child; leave the real installed dependency untouched.
        script_dir = str(Path(__file__).resolve().parent)
        probe = """import importlib.abc, runpy, sys
class MissingPyMuPDF(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'fitz':
            raise ModuleNotFoundError('controlled missing PyMuPDF', name='fitz')
sys.meta_path.insert(0, MissingPyMuPDF())
sys.path.insert(0, sys.argv[1])
runpy.run_path(sys.argv[1] + '/check_pdf_page_size.py', run_name='__main__')
"""
        result = subprocess.run([sys.executable, '-c', probe, script_dir],
                                text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn('pymupdf not installed', result.stdout)
        self.assertNotIn('Traceback', result.stderr)

    def test_plain_a4(self): self.assertEqual(self.result(self.pdf()), 0)
    def test_explicit_unit_one(self): self.assertEqual(self.result(self.pdf(unit=1)), 0)
    def test_doubled_page_rejected(self): self.assertEqual(self.result(self.pdf(unit=2)), 1)
    def test_halved_page_rejected(self): self.assertEqual(self.result(self.pdf(unit=.5)), 1)
    def test_compensated_user_units_are_valid(self):
        w,h=expected_points('a4')
        self.assertEqual(self.result(self.pdf(width=w/2,height=h/2,unit=2)),0)
    def test_indirect_user_unit(self): self.assertEqual(self.result(self.pdf(unit=2,indirect=True)),1)
    def test_rotated_scaled_paper(self): self.assertEqual(self.result(self.pdf(unit=2,rotation=90)),1)
    def test_rotated_a4(self): self.assertEqual(self.result(self.pdf(rotation=90)),0)
    def test_letter_opt_in(self):
        p=self.pdf(width=612,height=792)
        self.assertEqual(self.result(p),1); self.assertEqual(self.result(p,'letter'),0)
    def test_cropped_page(self): self.assertEqual(self.result(self.pdf(crop=(40,40,500,700))),1)
    def test_invalid_zero_user_unit(self): self.assertEqual(self.result(self.pdf(unit=0)),2)
    def test_invalid_string_user_unit(self): self.assertEqual(self.result(self.pdf(unit='(2)')),2)
    def test_invalid_expected_paper(self): self.assertEqual(self.result(self.pdf(),'typo'),2)
    def test_non_pdf_image(self):
        pix=fitz.Pixmap(fitz.csRGB,fitz.IRect(0,0,50,50));p=self.root/'input.png';pix.save(p)
        self.assertEqual(self.result(p),2)
    def test_encrypted_pdf(self):
        p=self.pdf(); out=self.root/'encrypted.pdf'
        with fitz.open(p) as doc:
            doc.save(out,encryption=fitz.PDF_ENCRYPT_AES_256,owner_pw='owner',user_pw='test')
        self.assertEqual(self.result(out),2)

class ReviewTests(Scratch):
    def fixture(self, page_box='cropbox', rotation=0):
        pdf=self.pdf(width=400,height=400,crop=(75,75,325,325),rotation=rotation)
        out=self.root/'review';render(pdf,out,dpi=144,page_box=page_box)
        path=out/'review.json';data=json.loads(path.read_text())
        return pdf,path,data
    def save(self,path,data):path.write_text(json.dumps(data),encoding='utf-8')
    def verify_pending(self,pdf,path):return verify(pdf,path,require_attestations=False,rerender=True)
    def test_crop_is_default_and_pending(self):
        pdf,path,data=self.fixture()
        self.assertEqual(data['schema'],3);self.assertEqual(data['page_box'],'cropbox')
        self.assertEqual((data['pages'][0]['width_px'],data['pages'][0]['height_px']),(500,500))
        self.assertEqual(data['pages'][0]['status'],'pending')
        self.assertEqual(self.verify_pending(pdf,path),[])
        self.assertTrue(verify(pdf,path))
    def test_explicit_media_proof(self):
        pdf,path,data=self.fixture('mediabox')
        self.assertEqual((data['pages'][0]['width_px'],data['pages'][0]['height_px']),(800,800))
        self.assertEqual(self.verify_pending(pdf,path),[])
    def test_legacy_media_evidence_still_replays(self):
        pdf,path,data=self.fixture('mediabox')
        data['schema']=1;del data['page_box']
        for item in data['pages']:
            del item['width_px'];del item['height_px']
        self.save(path,data)
        self.assertEqual(self.verify_pending(pdf,path),[])
    def test_legacy_cannot_claim_crop(self):
        pdf,path,data=self.fixture();data['schema']=1;self.save(path,data)
        with self.assertRaisesRegex(ValueError,'legacy schema'):self.verify_pending(pdf,path)
    def test_policy_change_is_not_a_new_attestation(self):
        pdf,path,data=self.fixture();data['page_box']='mediabox';self.save(path,data)
        self.assertTrue(self.verify_pending(pdf,path))
    def test_dimensions_cannot_be_forged(self):
        pdf,path,data=self.fixture();data['pages'][0]['width_px']=800;self.save(path,data)
        self.assertTrue(self.verify_pending(pdf,path))
    def test_missing_policy_rejected(self):
        pdf,path,data=self.fixture();del data['page_box'];self.save(path,data)
        with self.assertRaisesRegex(ValueError,'explicit'):self.verify_pending(pdf,path)
    def test_rotated_crop(self):
        pdf=self.pdf(width=400,height=400,crop=(50,75,350,325),rotation=90)
        out=self.root/'rotated';render(pdf,out,dpi=144)
        data=json.loads((out/'review.json').read_text())
        self.assertEqual((data['pages'][0]['width_px'],data['pages'][0]['height_px']),(500,600))
    def test_non_integer_dpi_rejected(self):
        pdf=self.pdf()
        for dpi in (True,144.0,'144'):
            with self.subTest(dpi=dpi),self.assertRaises(ValueError):render(pdf,self.root/'out',dpi=dpi)
    def test_user_unit_is_honored_or_fails_without_publication(self):
        pdf=self.pdf(width=200,height=200,unit=2);out=self.root/'out'
        try:render(pdf,out,dpi=72)
        except ValueError as exc:
            self.assertIn('renderer geometry mismatch',str(exc));self.assertFalse(out.exists())
        else:
            data=json.loads((out/'review.json').read_text())
            self.assertEqual((data['pages'][0]['width_px'],data['pages'][0]['height_px']),(400,400))
    def test_wrong_renderer_size_fails_closed(self):
        pdf=self.pdf();out=self.root/'out'
        with patch('render_review.raster_dimensions',return_value=(1,1)):
            with self.assertRaisesRegex(ValueError,'renderer geometry mismatch'):render(pdf,out,dpi=72)
        self.assertFalse(out.exists())
    def test_bad_policy_rejected(self):
        with self.assertRaises(ValueError):render(self.pdf(),self.root/'out',page_box='trimbox')

if __name__=='__main__':unittest.main(verbosity=2)
