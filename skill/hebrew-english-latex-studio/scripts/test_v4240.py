#!/usr/bin/env python3
"""Actual PDF-object, footer geometry and legacy R3 compatibility tests."""
from __future__ import annotations
import contextlib
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import unittest.mock
from unittest.mock import patch
sys.dont_write_bytecode = True
import fitz
import check_pdf_render as render
import pdf_folios as f

ROOT = Path(__file__).resolve().parent.parent


def document(texts, rules=None):
    doc = fitz.open()
    for i, text in enumerate(texts):
        page = doc.new_page(width=595.276, height=841.89)
        page.insert_text((60, 80), f'Synthetic folio control {i + 1}')
        if text:
            width = fitz.get_text_length(text, fontname='helv', fontsize=11)
            page.insert_text(((page.rect.width-width)/2, 805), text, fontsize=11)
    if rules is not None:
        doc.set_page_labels(rules)
    return doc


def rules(style='D', start=1, prefix=''):
    return [dict(startpage=0, style=style, firstpagenum=start, prefix=prefix)]


def check(doc):
    return f.labelled_folios(doc, f.declared_labels(doc)).findings


class LabelsTests(unittest.TestCase):
    def test_01_decimal_labels(self):
        with document(['12','13','14'], rules(start=12)) as d:
            self.assertEqual(f.declared_labels(d), ['12','13','14'])
            self.assertEqual(check(d), [])

    def test_02_roman_lower_upper(self):
        for style, expected in [('r',['iv','v','vi']), ('R',['IV','V','VI'])]:
            with self.subTest(style=style), document(expected, rules(style,4)) as d:
                self.assertEqual(f.declared_labels(d), expected)
                self.assertEqual(check(d), [])

    def test_03_latin_numbering_is_pdf_not_spreadsheet(self):
        for style, expected in [('a',['z','aa','bb']),('A',['Z','AA','BB'])]:
            with self.subTest(style=style), document(expected,rules(style,26)) as d:
                self.assertEqual(f.declared_labels(d),expected)
                self.assertEqual(check(d),[])

    def test_04_ranges_and_reset(self):
        expected=['i','ii','1','2','A-12','A-13']
        r=rules('r')+[dict(startpage=2,style='D'),dict(startpage=4,style='D',firstpagenum=12,prefix='A-')]
        with document(expected,r) as d:
            self.assertEqual(f.declared_labels(d),expected)
            self.assertEqual(check(d),[])

    def test_05_utf16_hex_prefixes(self):
        with document(['iv','v','vi']) as d:
            d.xref_set_key(d.pdf_catalog(),'PageLabels','<</Nums[0<</P<FEFF00690076>>>1<</P<FEFF0076>>>2<</P<FEFF00760069>>>]>>')
            self.assertEqual(f.declared_labels(d),['iv','v','vi'])
            self.assertEqual(check(d),[])

    def test_06_literal_hex_lookalike_is_not_decoded(self):
        with document(['<FEFF0031>']) as d:
            d.xref_set_key(d.pdf_catalog(),'PageLabels',r'<</Nums[0<</P(\074FEFF0031\076)>>]>>')
            self.assertEqual(f.declared_labels(d),['<FEFF0031>'])

    def test_07_escaped_pdf_string(self):
        with document(['']) as d:
            d.xref_set_key(d.pdf_catalog(),'PageLabels',r'<</Nums[0<</P(A\(B\)\134C)>>]>>')
            self.assertEqual(f.declared_labels(d),[r'A(B)\C'])

    def test_08_indirect_tree_and_rule_and_string(self):
        with document(['A-12','A-13','B-1']) as d:
            p=d.get_new_xref();d.update_object(p,'(A-)')
            rule=d.get_new_xref();d.update_object(rule,f'<</P {p} 0 R /S/D/St 12>>')
            n1=d.get_new_xref();d.update_object(n1,f'<</Nums[0 {rule} 0 R]/Limits[0 0]>>')
            n2=d.get_new_xref();d.update_object(n2,'<</Nums[2<</P(B-)/S/D>>]/Limits[2 2]>>')
            root=d.get_new_xref();d.update_object(root,f'<</Kids[{n1} 0 R {n2} 0 R]/Limits[0 2]>>')
            d.xref_set_key(d.pdf_catalog(),'PageLabels',f'{root} 0 R')
            self.assertEqual(f.declared_labels(d),['A-12','A-13','B-1'])
            self.assertEqual(check(d),[])

    def test_09_absent_is_distinct_from_blank(self):
        with document(['1','2','3']) as d:
            self.assertIsNone(f.declared_labels(d))
            d.set_page_labels([dict(startpage=0,prefix='')])
            self.assertEqual(f.declared_labels(d),['','',''])
            self.assertIn('FOLIO-COVERAGE-LOW',[x[1] for x in check(d)])

    def invalid(self, raw):
        with document(['1','2','3']) as d:
            d.xref_set_key(d.pdf_catalog(),'PageLabels',raw)
            with self.assertRaises(f.FolioError):
                f.declared_labels(d)

    def test_10_unknown_style(self):
        self.invalid('<</Nums[0<</S/Q>>]>>')

    def test_11_non_positive_initial(self):
        for number in ['0','-1']:
            with self.subTest(number=number):self.invalid(f'<</Nums[0<</S/D/St {number}>>]>>')

    def test_12_wrong_field_types(self):
        for field in ['/S(D)','/St(1)','/P 12']:
            with self.subTest(field=field):self.invalid('<</Nums[0<<'+field+'>>]>>')

    def test_13_missing_zero_duplicate_and_unsorted_ranges(self):
        for raw in ['[1<</S/D>>]','[0<</S/D>>0<</S/r>>]','[0<</S/D>>2<</S/r>>1<</S/D>>]']:
            with self.subTest(raw=raw):self.invalid('<</Nums'+raw+'>>')

    def test_14_out_of_bounds_index(self):
        self.invalid('<</Nums[0<</S/D>>3<</S/D>>]>>')

    def test_15_empty_and_odd_arrays(self):
        for raw in ['<</Nums[]>>','<</Nums[0]>>','<</Kids[]>>','<</Nums(0)>>','<</Nums[0<<>>]/Kids[]>>']:
            with self.subTest(raw=raw):self.invalid(raw)

    def test_16_cycles(self):
        with document(['1','2','3']) as d:
            x=d.get_new_xref();d.update_object(x,f'<</Kids[{x} 0 R]>>')
            d.xref_set_key(d.pdf_catalog(),'PageLabels',f'{x} 0 R')
            with self.assertRaises(f.FolioError):f.declared_labels(d)

    def test_17_nonascii_scope_is_explicit(self):
        self.invalid('<</Nums[0<</P<FEFF05D0>>>]>>')

    def test_18_number_and_length_limits(self):
        self.invalid('<</Nums[0<</S/r/St 4000>>]>>')
        self.invalid('<</Nums[0<</S/a/St 5000>>]>>')
        self.invalid('<</Nums[0<</P('+ 'x'*129 +')>>]>>')

    def test_19_does_not_edit_original_pdf(self):
        with document(['i','ii','iii'],rules('r')) as d:
            before=[d.xref_object(i) for i in range(1,d.xref_length())]
            self.assertEqual(check(d),[])
            self.assertEqual(before,[d.xref_object(i) for i in range(1,d.xref_length())])

    def test_20_array_scanner_nested_strings_and_comments(self):
        raw=r'[0<</P(A\(B\) C)/S/D>> 2 17 0 R % next'+'\n4<</P<4142>>>]'
        self.assertEqual(f._array_items(raw),['0',r'<</P(A\(B\) C)/S/D>>','2','17 0 R','4','<</P<4142>>>'])
        for bad in ['[(', '[<4142','[[]', '[<<]', '[1] 2']:
            with self.subTest(bad=bad), self.assertRaises(f.FolioError):f._array_items(bad)


class GeometryTests(unittest.TestCase):
    def test_21_wrong_digit_and_roman_order(self):
        for actual, r in [(['21','13','14'],rules(start=12)), (['vi','v','vi'],rules('r',4))]:
            with self.subTest(actual=actual), document(actual,r) as d:
                hits=check(d)
                self.assertEqual([(h[0],h[1]) for h in hits],[(1,'PAGE-NUMBER-REVERSED')])

    def test_22_wrong_nonnumeric_label(self):
        with document(['i','oops','iii'],rules('r')) as d:
            self.assertEqual([(h[0],h[1]) for h in check(d)],[(2,'PAGE-NUMBER-ODD')])

    def test_23_no_printed_folios_is_not_pass(self):
        with document(['','',''],rules('r')) as d:
            self.assertEqual([h[1] for h in check(d)],['FOLIO-COVERAGE-LOW'])

    def test_24_title_page_absence_uses_existing_floor(self):
        with document(['','ii','iii','iv'],rules('r')) as d:
            self.assertEqual(check(d),[])
        with document(['','','','iv'],rules('r')) as d:
            self.assertIn('FOLIO-COVERAGE-LOW',[h[1] for h in check(d)])

    def test_25_offset_body_digits_are_not_folios(self):
        with document(['1','2','3'],rules()) as d:
            for p in d:
                p.insert_text((50,805),'135',fontsize=11)
                p.insert_text((510,805),'7',fontsize=11)
                p.insert_text((295,710),'99',fontsize=11)
            self.assertEqual(check(d),[])

    def test_26_fragment_order_is_physical_not_extraction_order(self):
        with document(['','13','14'],rules(start=12)) as d:
            p=d[0];size=11
            w=fitz.get_text_length('12',fontsize=size)
            w1=fitz.get_text_length('1',fontsize=size)
            x=(p.rect.width-w)/2
            p.insert_text((x+w1,805),'2',fontsize=size) # stream order 2 then 1
            p.insert_text((x,805),'1',fontsize=size)
            self.assertEqual(f.footer_candidates(p),['12'])
            self.assertEqual(check(d),[])

    def test_27_ambiguous_two_footer_lines(self):
        with document(['1','2','3'],rules()) as d:
            d[0].insert_text((294.5,785),'1',fontsize=11)
            self.assertIn('FOLIO-AMBIGUOUS',[h[1] for h in check(d)])

    def test_28_noncentral_folios_do_not_satisfy_contract(self):
        with document(['','',''],rules()) as d:
            for p in d:p.insert_text((50,805),'1',fontsize=11)
            self.assertEqual([h[1] for h in check(d)],['FOLIO-COVERAGE-LOW'])

    def test_29_spaces_in_declared_prefix_are_not_digit_order(self):
        with document(['A- 12','A- 13'],rules(start=12,prefix='A- ')) as d:
            self.assertEqual(check(d),[])

    def test_30_label_count_mismatch(self):
        with document(['1','2','3']) as d:
            with self.assertRaises(f.FolioError):f.labelled_folios(d,['1'])

    def test_37_centred_body_equation_is_not_folio(self):
        with document(['1','2','3'],rules()) as d:
            for p in d:
                text='E=mc.'
                w=fitz.get_text_length(text,fontsize=11)
                p.insert_text(((p.rect.width-w)/2,785),text,fontsize=11)
            self.assertEqual(check(d),[])

    # v4.25.0 controls: a page style prints every folio in ONE typeface.
    # Measured on 22 real collections: 89 pages carried a correct folio plus a
    # centred body glyph from another face (a subscript, a math letter, a
    # plot's axis label) in the bottom band, and were rejected as ambiguous.
    def intrude(self, page, text='j', size=7, y=790, font='tiro'):
        width = fitz.get_text_length(text, fontname=font, fontsize=size)
        page.insert_text(((page.rect.width-width)/2, y), text, fontname=font, fontsize=size)

    def test_40_body_glyph_in_foreign_face_is_not_a_second_folio(self):
        with document(['1','2','3'],rules()) as d:
            self.intrude(d[0])
            self.assertCountEqual(f.footer_candidates(d[0]),['j','1'])   # still SEEN
            self.assertEqual(check(d),[])                           # not a folio

    def test_41_wrong_folio_survives_the_face_filter(self):
        with document(['9','2','3'],rules()) as d:
            self.intrude(d[0], '2')
            self.assertEqual([(h[0],h[1]) for h in check(d)],[(1,'PAGE-NUMBER-ODD')])

    def test_42_sole_candidate_is_compared_whatever_its_face(self):
        with document(['','2','3'],rules()) as d:
            self.intrude(d[0], '2')
            self.assertEqual([(h[0],h[1]) for h in check(d)],[(1,'PAGE-NUMBER-ODD')])

    def test_43_no_clean_page_learns_no_face(self):
        with document(['1','2','3'],rules()) as d:
            for p in d: self.intrude(p)
            # nothing observed, so the non-waivable coverage floor fails as well
            self.assertEqual([h[1] for h in check(d)],['FOLIO-AMBIGUOUS']*3+['FOLIO-COVERAGE-LOW'])

    def test_44_runs_all_outside_the_face_stay_ambiguous(self):
        with document(['','2','3'],rules()) as d:
            self.intrude(d[0], 'j', y=780); self.intrude(d[0], 'k', y=795)
            self.assertIn((1,'FOLIO-AMBIGUOUS'),[(h[0],h[1]) for h in check(d)])

    def test_45_disabling_the_face_filter_restores_the_false_rejection(self):
        with document(['1','2','3'],rules()) as d:
            self.intrude(d[0])
            original = f._styled_candidates     # mutation: every run loses its face
            with unittest.mock.patch.object(f, '_styled_candidates',
                    lambda *a, **k: [(t, frozenset()) for t, _ in original(*a, **k)]):
                self.assertEqual([h[1] for h in check(d)],['FOLIO-AMBIGUOUS'])


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='hllpdf424-unit-')
        self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'probe.pdf'

    def run_check(self,doc):
        doc.save(self.path)
        with contextlib.redirect_stdout(io.StringIO()) as out:
            rc=render.check(str(self.path))
        self.path.unlink()
        return rc,out.getvalue()

    def test_31_disable_real_label_handler_restores_old_failure(self):
        with document(['i','ii','iii','iv'],rules('r')) as d:
            self.assertEqual(self.run_check(d)[0],0)
            with patch.object(render,'declared_labels',return_value=None):
                rc,out=self.run_check(d)
                self.assertEqual(rc,1);self.assertIn('FOLIO-COVERAGE-LOW',out)

    def test_32_disable_handler_restores_missed_roman_error(self):
        with document(['i','ii','iii','vi','1','2','3','4'],rules('r')+[dict(startpage=4,style='D')]) as d:
            rc,out=self.run_check(d)
            self.assertEqual(rc,1);self.assertIn('PAGE-NUMBER-REVERSED',out)
            with patch.object(render,'declared_labels',return_value=None):
                self.assertEqual(self.run_check(d)[0],0)

    def test_33_unlabelled_legacy_keeps_coverage_and_inference(self):
        for texts, expected in [(['12','13','14','15','16'],0),(['21','13','14','15','16'],1),(['','',''],1)]:
            with self.subTest(texts=texts),document(texts) as d:
                self.assertEqual(self.run_check(d)[0],expected)

    def test_34_bad_metadata_is_not_inference_fallback(self):
        with document(['1','2','3']) as d:
            d.xref_set_key(d.pdf_catalog(),'PageLabels','<</Nums[0<</S/Q>>]>>')
            rc,out=self.run_check(d)
            self.assertEqual(rc,1);self.assertIn('FOLIO-LABELS-INVALID',out)

    def test_35_cli_and_corrupt_pdf(self):
        with document(['iv','v','vi'],rules('r',4)) as d:d.save(self.path)
        p=subprocess.run([sys.executable,str(ROOT/'scripts/check_pdf_render.py'),str(self.path)],text=True,capture_output=True,timeout=30)
        self.assertEqual(p.returncode,0,p.stdout+p.stderr)
        self.path.write_bytes(b'not a PDF')
        p=subprocess.run([sys.executable,str(ROOT/'scripts/check_pdf_render.py'),str(self.path)],text=True,capture_output=True,timeout=30)
        self.assertEqual(p.returncode,2,p.stdout+p.stderr)

    def test_36_short_document_wrong_label_is_checked(self):
        with document(['21'],rules(start=12)) as d:
            rc,out=self.run_check(d)
            self.assertEqual(rc,1);self.assertIn('PAGE-NUMBER-REVERSED',out)

    def test_38_missing_pdf_library_is_tooling_error(self):
        p=subprocess.run([sys.executable,'-S',str(ROOT/'scripts/check_pdf_render.py'),'unused.pdf'],
                         text=True,capture_output=True,timeout=30)
        self.assertEqual(p.returncode,2)
        self.assertIn('pymupdf not installed',p.stdout)
        self.assertNotIn('Traceback',p.stdout+p.stderr)

    def test_39_missing_helper_is_tooling_error(self):
        script=Path(self.tmp.name)/'check_pdf_render.py'
        script.write_bytes((ROOT/'scripts/check_pdf_render.py').read_bytes())
        p=subprocess.run([sys.executable,str(script),'unused.pdf'],
                         text=True,capture_output=True,timeout=30)
        self.assertEqual(p.returncode,2)
        self.assertIn('folio helper unavailable',p.stderr)
        self.assertNotIn('Traceback',p.stdout+p.stderr)


if __name__=='__main__':unittest.main(verbosity=2)
