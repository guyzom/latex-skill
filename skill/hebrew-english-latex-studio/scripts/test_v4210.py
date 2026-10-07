#!/usr/bin/env python3
"""Source and negative controls for the bounded listing glyph-order probe."""
from __future__ import annotations
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
sys.dont_write_bytecode = True
import fitz
from listing_text_probe import compact, order_glyphs, probe
ROOT = Path(__file__).resolve().parent.parent


class ProbeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='hllpdf-421-probe-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.pdf = self.root/'probe.pdf'
        with fitz.open() as doc:
            page = doc.new_page()
            # Write objects out of reading order, and include non-code prose.
            page.insert_text((40, 85), 'beta()', fontname='cour')
            page.insert_text((40, 60), 'alpha()', fontname='cour')
            page.insert_text((40, 30), 'Caption', fontname='helv')
            doc.save(self.pdf)

    def test_visual_order_not_object_order(self):
        self.assertTrue(probe(self.pdf, ['alpha()', 'beta()'], 'Courier')['match'])

    def test_wrong_expected_order_fails(self):
        self.assertFalse(probe(self.pdf, ['beta()', 'alpha()'], 'Courier')['match'])

    def test_missing_expected_text_fails(self):
        self.assertFalse(probe(self.pdf, ['alpha()'], 'Courier')['match'])

    def test_extra_expected_text_fails(self):
        self.assertFalse(probe(self.pdf, ['alpha()', 'beta()', 'gamma()'], 'Courier')['match'])

    def test_wrong_font_is_error_not_pass(self):
        with self.assertRaisesRegex(ValueError, 'no glyphs'):
            probe(self.pdf, ['alpha()'], 'NotTheCodeFont')

    def test_blank_expected_is_error(self):
        for lines in ([], ['   '], [None], 'alpha()'):
            with self.subTest(lines=lines), self.assertRaises(ValueError):
                probe(self.pdf, lines, 'Courier')

    def test_invalid_font_is_error(self):
        for font in ('', '   ', None, 1):
            with self.subTest(font=font), self.assertRaises(ValueError):
                probe(self.pdf, ['alpha()'], font)

    def test_no_normalization_or_quote_replacement(self):
        self.assertNotEqual(compact('“beta”'), compact('"beta"'))
        self.assertNotEqual(compact('é'), compact('e\u0301'))
        self.assertEqual(compact('a\t b\n c'), 'abc')  # explicit whitespace limitation

    def test_baseline_jitter_keeps_x_order(self):
        raw = [{'page':1,'origin':(20,10.01),'c':'b'}, {'page':1,'origin':(10,10.05),'c':'a'},
               {'page':2,'origin':(10,3),'c':'c'}]
        self.assertEqual(''.join(x['c'] for x in order_glyphs(raw)), 'abc')

    def test_cli_exit_codes_and_evidence_not_overwritten(self):
        spec = self.root/'expected.json'; evidence = self.root/'result.json'
        def invoke(lines, *extra):
            spec.write_text(json.dumps({'lines':lines,'font_contains':'Courier'}))
            return subprocess.run([sys.executable,str(ROOT/'scripts/listing_text_probe.py'),str(self.pdf),
                                   '--expected',str(spec),*extra],capture_output=True,text=True,timeout=20)
        self.assertEqual(invoke(['alpha()','beta()'],'--output',str(evidence)).returncode,0)
        saved = evidence.read_bytes()
        self.assertEqual(invoke(['alpha()','beta()'],'--output',str(evidence)).returncode,2)
        self.assertEqual(saved, evidence.read_bytes())
        self.assertEqual(invoke(['beta()','alpha()']).returncode,1)
        self.assertEqual(invoke([]).returncode,2)

    def test_cli_schema_is_closed(self):
        spec = self.root/'bad.json'; spec.write_text('{"lines":["x"],"unknown":true}')
        result = subprocess.run([sys.executable,str(ROOT/'scripts/listing_text_probe.py'),str(self.pdf),
                                 '--expected',str(spec)],capture_output=True,text=True,timeout=20)
        self.assertEqual(result.returncode,2)

    def test_cli_missing_pdf_is_tool_error(self):
        spec = self.root/'missing.json'; spec.write_text('{"lines":["x"]}')
        result = subprocess.run([sys.executable,str(ROOT/'scripts/listing_text_probe.py'),str(self.root/'absent.pdf'),
                                 '--expected',str(spec)],capture_output=True,text=True,timeout=20)
        self.assertEqual(result.returncode,2)


class CoreContracts(unittest.TestCase):
    def test_extension_scope_and_order_are_explicit(self):
        text = (ROOT/'assets/preamble.tex').read_text()
        match = re.search(r'% <hllpdf:listing-smart-quotes>\n(.*?)% </hllpdf:listing-smart-quotes>',text,re.S)
        self.assertIsNotNone(match)
        block = match.group(1)
        self.assertEqual(set(re.findall(r'\{"([0-9A-F]+)\}',block)),{'2018','2019','201C','201D'})
        self.assertIn(r'\lst@CCPut \lst@ProcessOther',block)
        self.assertIn(r'\lst@AddToHookAtTop{SelectCharTable}',block)
        self.assertIn(r'\lst@ifactivechars',block)
        self.assertNotIn(r'\global\catcode',block)
        self.assertNotIn(r'\lstset{literate',block)

    def test_previous_union_is_not_lost(self):
        text = (ROOT/'assets/preamble.tex').read_text()
        self.assertIn('% <hllpdf:measured-toc>',text)
        for required in ('test_v4180_runtime.py','test_v4190_runtime.py','test_v4200_runtime.py'):
            self.assertTrue((ROOT/'scripts'/required).is_file())


if __name__ == '__main__':
    unittest.main(verbosity=2)
