#!/usr/bin/env python3
"""Real PDF geometry tests for English/custom-color caption destinations."""
from __future__ import annotations
import contextlib
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
sys.dont_write_bytecode = True
import fitz
import check_pdf_render as render
from build_contract import parse_rgb_hex

ROOT = Path(__file__).resolve().parent


def document(label='Table 1.1.', *, color=0x555555, font='hebo', destination='tbl.1.1', y=100):
    doc = fitz.open()
    page = doc.new_page(width=595.276, height=841.89)
    rgb = tuple(((color >> shift) & 255) / 255 for shift in (16,8,0))
    page.insert_text((180,200), label, fontname=font, fontsize=12, color=rgb)
    if destination:
        doc.xref_set_key(doc.pdf_catalog(), 'Names',
            f'<</Dests<</Names[({destination})[{page.xref} 0 R /XYZ 0 {page.rect.height-y} null]]>>>>')
    return doc


class CaptionStyleTests(unittest.TestCase):
    def test_english_table_figure_and_appendix_numbers(self):
        for label, kind, number in [('Table 1.1.','tbl','1.1'), ('Figure 3.','fig','3'),
                                    ('Table A.2.','tbl','A.2'), ('Figure 0.1.','fig','1')]:
            with self.subTest(label=label), document(label) as doc:
                sites = render.caption_sites(doc[0])
                self.assertEqual([(x[0],x[1]) for x in sites],[(kind,number)])

    def test_regular_body_reference_is_not_caption(self):
        for label, font, color in [('Table 1.1.','helv',0x555555),
                                    ('Table 1.1.','hebo',0),
                                    ('See Table 1.1.','hebo',0x555555),
                                    ('Table 1.1 is discussed','hebo',0x555555)]:
            with self.subTest(label=label,font=font,color=color), document(label,font=font,color=color) as doc:
                self.assertEqual(render.caption_sites(doc[0]),[])

    def test_custom_color_requires_exact_declared_style(self):
        with document(color=0x536570) as doc:
            self.assertEqual(render.caption_sites(doc[0]),[])
            self.assertEqual([(x[0],x[1]) for x in render.caption_sites(doc[0],0x536570)],
                             [('tbl','1.1')])
            self.assertEqual(render.caption_sites(doc[0],0x536571),[])

    def test_correct_english_destination_is_measured(self):
        with document() as doc:
            hard,soft=[],[]
            self.assertEqual(render.dest_landing(doc,hard,soft),1)
            self.assertEqual(hard,[])
            self.assertEqual(soft,[])

    def test_destination_at_english_caption_is_rejected(self):
        with document(y=195) as doc:
            hard,soft=[],[]
            render.dest_landing(doc,hard,soft)
            self.assertEqual([x[1] for x in hard],['DEST-AT-CAPTION'])
            self.assertEqual(soft,[])

    def test_custom_caption_destination_is_measured(self):
        with document(color=0x536570) as doc:
            hard,soft=[],[]
            render.dest_landing(doc,hard,soft,caption_color=0x536570)
            self.assertEqual((hard,soft),([],[]))

    def test_wrong_caption_number_keeps_ownership_advisory(self):
        with document('Table 2.1.') as doc:
            hard,soft=[],[]
            render.dest_landing(doc,hard,soft)
            self.assertIn('DEST-PAIRED-BY-PROXIMITY',[x[1] for x in soft])

    def test_cli_custom_style_and_bad_values(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'caption.pdf'
            with document(color=0x536570) as doc:
                doc.save(path)
            good=subprocess.run([sys.executable,str(ROOT/'check_pdf_render.py'),
                                 '--caption-color','536570',str(path)],capture_output=True,text=True)
            self.assertEqual(good.returncode,0,good.stdout+good.stderr)
            self.assertNotIn('DEST-CAPTION-NOT-FOUND',good.stdout)
            self.assertIn('the one',good.stdout)
            for value in ('#536570','53657','1234567','gray','12GG34'):
                for script in ('check_pdf_render.py','validate_build_config.py'):
                    args=[sys.executable,str(ROOT/script),'--caption-color',value]
                    if script=='check_pdf_render.py':args.append(str(path))
                    bad=subprocess.run(args,capture_output=True,text=True)
                    self.assertEqual(bad.returncode,2,(value,script,bad.stdout+bad.stderr))

    def test_rgb_contract_and_api_bounds(self):
        self.assertEqual(parse_rgb_hex('aBcD01'),0xABCD01)
        for value in ('555555',-1,0x1000000):
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(render.check('missing.pdf',caption_color=value),2)


if __name__=='__main__':unittest.main(verbosity=2)
