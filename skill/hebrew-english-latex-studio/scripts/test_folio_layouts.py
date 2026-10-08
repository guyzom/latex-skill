#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Original project code; scope and terms: ../LICENSING.md.
"""Actual PDF checks for explicit general-document folio layout contracts."""
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
from pdf_folios import declared_labels, labelled_folios, folio_alignment, footer_candidates
import unittest.mock
import pdf_folios


def faceless():
    """v5.3.5: run a check as the delivered v5.3.4 gate did, without the folio face.

    The three veto-narrowness tests below were written for a gate with no learned
    folio face, so "an unattached run stays ambiguous" was the only end-to-end
    outcome. The restored (font, size) face (BLD-67/BLD-72) now filters a run
    in another size. Their footer_candidates assertions -- the veto itself --
    are unchanged; their end-to-end assertions run in the regime they test.
    v5.4.1: v5.4.0's unconnected-prose test was written for the same faceless
    gate (its 8pt sentence sits beside an 11pt folio) and runs here too.
    """
    original = pdf_folios._styled_candidates
    return unittest.mock.patch.object(
        pdf_folios, '_styled_candidates',
        lambda *a, **k: [(t, frozenset()) for t, _ in original(*a, **k)])

ROOT = Path(__file__).resolve().parent


def document(layout='center', band='footer', *, numbered=True, labels=True,
             rotation=0, wrong=False):
    doc = fitz.open()
    for i in range(4):
        page = doc.new_page(width=595.276, height=841.89)
        page.insert_text((60, 150), 'A general document with selected design.')
        if numbered:
            text = '21' if wrong and i == 0 else str(i + 12)
            width = fitz.get_text_length(text, fontsize=11)
            alignment = folio_alignment(layout, i + 1)
            x = {'center': (page.rect.width-width)/2,
                 'left': 55, 'right': page.rect.width-55-width}[alignment]
            page.insert_text((x, 805 if band == 'footer' else 40), text, fontsize=11)
        page.set_rotation(rotation)
    if labels:
        doc.set_page_labels([dict(startpage=0, style='D', firstpagenum=12)])
    return doc


def insert_script_equation(page, *, scale=1., offset=-4.):
    """Real glyphs: a centred script digit connected to an equation's base."""
    text, size = 'Q=(x+a)', 12 * scale
    end = page.rect.width / 2 - 4
    start = end - fitz.get_text_length(text, fontsize=size)
    page.insert_text((start, 770), text, fontsize=size)
    page.insert_text((end, 770 + offset * scale), '2', fontsize=8 * scale)


def insert_multiline_body(page):
    text = ('zero net external impulse conserves momentum.\n'
            'Conservation of total energy need not conserve\n'
            'mechanical energy.')
    size = 8.
    width = fitz.get_text_length(text.splitlines()[1], fontsize=size)
    page.insert_text(((page.rect.width-width)/2, 760), text,
                     fontsize=size, lineheight=1.24)


def insert_tied_column_edges(page, *, overshoot=False):
    text, size = 'Ordinary body prose calibrates this column edge.', 8.
    width = fitz.get_text_length(text, fontsize=size)
    for i in range(40):
        edge = 384.5 if i % 2 == 0 else 572.5
        page.insert_text((edge-width, 100+12*i), text, fontsize=size)
    if overshoot:
        page.insert_text((583.-width, 600), text, fontsize=size)


def insert_body_grid(page, *, malformed=False, crossing=False, overshoots=0):
    text = 'Several ordinary words establish a repeated body column.'
    unit_width = fitz.get_text_length(text, fontsize=1.)
    lanes = ((22.5, 196.5, 10, 210., 30.),
             (210.5, 384.5, 26, 200., 12.),
             (398.5, 582.5 if malformed else 572.5, 7, 205., 42.))
    for left, right, count, top, pitch in lanes:
        for i in range(count):
            page.insert_text((left, top+i*pitch), text, fontsize=(right-left)/unit_width)
    if crossing:
        page.insert_text((22.5, 350), text, fontsize=550./unit_width)
    for i in range(overshoots):
        page.insert_text((398.5, 330+20*i), text, fontsize=(583.-398.5)/unit_width)


class FolioLayoutTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='hllpdf-layout-')
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'probe.pdf'

    def run_check(self, doc, **kwargs):
        doc.save(self.path)
        with contextlib.redirect_stdout(io.StringIO()) as out:
            code = render.check(str(self.path), **kwargs)
        self.path.unlink()
        return code, out.getvalue()

    def test_all_supported_geometry_contracts(self):
        for layout in ('center', 'left', 'right', 'outer', 'inner'):
            for band in ('footer', 'header'):
                with self.subTest(layout=layout, band=band), document(layout, band) as doc:
                    self.assertEqual(labelled_folios(doc, declared_labels(doc),
                                     layout=layout, band=band).findings, [])
                    code, out = self.run_check(doc, folio_layout=layout, folio_band=band)
                    self.assertEqual(code, 0, out)

    def test_center_remains_default_and_wrong_geometry_fails(self):
        with document('right') as doc:
            code, out = self.run_check(doc)
            self.assertEqual(code, 1, out)
            self.assertIn('FOLIO-COVERAGE-LOW', out)

    def test_changed_layout_still_detects_digit_reversal(self):
        for layout in ('left', 'right', 'outer', 'inner'):
            with self.subTest(layout=layout), document(layout, wrong=True) as doc:
                code, out = self.run_check(doc, folio_layout=layout)
                self.assertEqual(code, 1, out)
                self.assertIn('PAGE-NUMBER-REVERSED', out)

    def test_unlabelled_layout_keeps_inference(self):
        with document('outer', labels=False) as doc:
            code, out = self.run_check(doc, folio_layout='outer')
            self.assertEqual(code, 0, out)
            self.assertIn('legacy sequence inferred', out)

    def test_unlabelled_wrong_number_still_fails(self):
        with document('outer', labels=False, wrong=True) as doc:
            code, out = self.run_check(doc, folio_layout='outer')
            self.assertEqual(code, 1, out)
            self.assertIn('PAGE-NUMBER-REVERSED', out)

    def test_intentional_none_and_custom_report_unmeasured(self):
        for layout in ('none', 'custom'):
            with self.subTest(layout=layout), document(numbered=False) as doc:
                code, out = self.run_check(doc, folio_layout=layout)
                self.assertEqual(code, 0, out)
                self.assertIn('FOLIO-NOT-MEASURED', out)
                self.assertIn('printed numbering was not verified', out)
                self.assertNotIn('render check clean', out)

    def test_none_does_not_disable_offpage_gate(self):
        with document(numbered=False) as doc:
            doc[0].insert_text((-20, 100), 'Content off the paper')
            code, out = self.run_check(doc, folio_layout='none')
            self.assertEqual(code, 1, out)
            self.assertIn('INK-OFF-PAPER', out)

    def test_custom_does_not_hide_malformed_label_metadata(self):
        with document(numbered=False) as doc:
            doc.xref_set_key(doc.pdf_catalog(), 'PageLabels', '<</Nums[0<</S/Q>>]>>')
            code, out = self.run_check(doc, folio_layout='custom')
            self.assertEqual(code, 1, out)
            self.assertIn('FOLIO-LABELS-INVALID', out)

    def test_custom_supports_unicode_labels_without_claiming_measurement(self):
        with document(numbered=False) as doc:
            doc.xref_set_key(doc.pdf_catalog(), 'PageLabels', '<</Nums[0<</P<FEFF05D0>>>]>>')
            code, out = self.run_check(doc, folio_layout='custom')
            self.assertEqual(code, 0, out)
            self.assertIn('printed numbering was not verified', out)

    def test_rotated_page_uses_same_coordinate_space_as_text(self):
        for rotation in (90, 180, 270):
            with self.subTest(rotation=rotation), document(rotation=rotation) as doc:
                code, out = self.run_check(doc)
                self.assertEqual(code, 0, out)
                self.assertIn('4/4 center footer folios', out)

    def test_attached_super_and_subscript_digits_are_not_extra_folios(self):
        for scale in (.75, 1., 1.3):
            for offset in (-4., 4.):
                with self.subTest(scale=scale, offset=offset), document() as doc:
                    for page in doc:
                        insert_script_equation(page, scale=scale, offset=offset)
                    self.assertEqual(footer_candidates(doc[0], expected_label='12'), ['12'])
                    code, out = self.run_check(doc)
                    self.assertEqual(code, 0, out)
                    self.assertIn('4/4 center footer folios', out)

    def test_script_exclusion_does_not_hide_a_wrong_real_folio(self):
        with document(wrong=True) as doc:
            insert_script_equation(doc[0])
            self.assertEqual(footer_candidates(doc[0], expected_label='12'), ['21'])
            code, out = self.run_check(doc)
            self.assertEqual(code, 1, out)
            self.assertIn('PAGE-NUMBER-REVERSED', out)

    def test_duplicate_normal_and_different_size_unattached_folios_stay_ambiguous(self):
        for size in (11., 8.):
            with self.subTest(size=size), document() as doc:
                page = doc[0]
                text = '12'
                x = (page.rect.width - fitz.get_text_length(text, fontsize=size)) / 2
                page.insert_text((x, 775), text, fontsize=size)
                self.assertEqual(footer_candidates(page, expected_label='12'), ['12', '12'])
                with faceless():
                    code, out = self.run_check(doc)
                self.assertEqual(code, 1, out)
                self.assertIn('FOLIO-AMBIGUOUS', out)

    def test_distant_nondigit_ink_does_not_hide_small_footer(self):
        with document() as doc:
            page = doc[0]
            # Same footer band, large nearby row, but no typographic attachment.
            page.insert_text((page.rect.width / 2 - 70, 779), 'Q=(x+a)', fontsize=12)
            text, size = '21', 8
            x = (page.rect.width - fitz.get_text_length(text, fontsize=size)) / 2
            page.insert_text((x, 775), text, fontsize=size)
            self.assertCountEqual(footer_candidates(page, expected_label='12'), ['21', '12'])
            with faceless():
                code, out = self.run_check(doc)
            self.assertEqual(code, 1, out)
            self.assertIn('FOLIO-AMBIGUOUS', out)

    def test_adjacent_larger_digits_do_not_hide_a_script_sized_number(self):
        with document() as doc:
            page = doc[0]
            end = page.rect.width / 2 - 4
            page.insert_text((end-fitz.get_text_length('12', fontsize=12), 770),
                             '12', fontsize=12)
            page.insert_text((end, 766), '2', fontsize=8)
            self.assertCountEqual(footer_candidates(page, expected_label='12'), ['12', '2', '12'])
            with faceless():
                code, out = self.run_check(doc)
            self.assertEqual(code, 1, out)
            self.assertIn('FOLIO-AMBIGUOUS', out)

    def test_connected_multiline_body_does_not_become_a_footer_folio(self):
        with document() as doc:
            for page in doc:
                insert_multiline_body(page)
            self.assertEqual(footer_candidates(doc[0], expected_label='12'), ['12'])
            code, out = self.run_check(doc)
            self.assertEqual(code, 0, out)
            self.assertIn('4/4 center footer folios', out)

    def test_multiline_body_does_not_hide_wrong_or_duplicate_folios(self):
        with document(wrong=True) as doc:
            insert_multiline_body(doc[0])
            self.assertEqual(footer_candidates(doc[0], expected_label='12'), ['21'])
            code, out = self.run_check(doc)
            self.assertEqual(code, 1, out)
            self.assertIn('PAGE-NUMBER-REVERSED', out)
        with document() as doc:
            insert_multiline_body(doc[0])
            width = fitz.get_text_length('12', fontsize=11)
            doc[0].insert_text(((doc[0].rect.width-width)/2, 790), '12', fontsize=11)
            self.assertEqual(footer_candidates(doc[0], expected_label='12'), ['12', '12'])
            code, out = self.run_check(doc)
            self.assertEqual(code, 1, out)
            self.assertIn('FOLIO-AMBIGUOUS', out)

    def test_multiword_prefixed_decimal_roman_and_latin_labels_remain_checked(self):
        for style, wrong in (('D', '21'), ('R', 'XXI'), ('A', 'M')):
            for mismatch in (False, True):
                with self.subTest(style=style, mismatch=mismatch), document(numbered=False) as doc:
                    doc.set_page_labels([dict(startpage=0, style=style, firstpagenum=12,
                                              prefix='Appendix Part ')])
                    labels = declared_labels(doc)
                    for i, page in enumerate(doc):
                        insert_multiline_body(page)
                        text = 'Appendix Part '+wrong if mismatch and i == 0 else labels[i]
                        width = fitz.get_text_length(text, fontsize=11)
                        page.insert_text(((page.rect.width-width)/2, 805), text, fontsize=11)
                    expected = ('Appendix Part '+wrong if mismatch else labels[0]).replace(' ', '')
                    self.assertEqual(footer_candidates(doc[0], expected_label=labels[0]), [expected])
                    code, out = self.run_check(doc)
                    self.assertEqual(code, int(mismatch), out)
                    if mismatch:
                        self.assertIn('PAGE-NUMBER-ODD', out)

    def test_unconnected_multiword_run_is_not_excluded_as_body(self):
        with document() as doc:
            text, size = 'Conservation of total energy need not conserve', 8.
            width = fitz.get_text_length(text, fontsize=size)
            doc[0].insert_text(((doc[0].rect.width-width)/2, 775), text, fontsize=size)
            self.assertCountEqual(footer_candidates(doc[0], expected_label='12'),
                                  [text.replace(' ', ''), '12'])
            with faceless():
                code, out = self.run_check(doc)
            self.assertEqual(code, 1, out)
            self.assertIn('FOLIO-AMBIGUOUS', out)

    def test_prefix_only_wrong_literal_inside_multiline_context_remains_a_finding(self):
        for literal, wrong in (('front matter label', 'front matter error'),
                               ('appendix part i', 'appendix part error'),
                               ('Mix', 'front matter error'),
                               ('iV', 'front matter error'),
                               ('xIi', 'front matter error')):
            with self.subTest(literal=literal), fitz.open() as doc:
                page = doc.new_page(width=595.276, height=841.89)
                doc.set_page_labels([dict(startpage=0, prefix=literal)])
                width = fitz.get_text_length(wrong, fontsize=8)
                page.insert_text(((page.rect.width-width)/2, 775),
                                 'ordinary argument beforehand\n'+wrong+'\nordinary argument afterward',
                                 fontsize=8, lineheight=1.24)
                self.assertIn(wrong.replace(' ', ''),
                              footer_candidates(page, expected_label=literal))
                self.assertTrue(labelled_folios(doc, declared_labels(doc)).findings)
                code, out = self.run_check(doc)
                self.assertEqual(code, 1, out)
                self.assertTrue('PAGE-NUMBER-ODD' in out or 'FOLIO-AMBIGUOUS' in out, out)

    def test_hyperref_literal_counter_serialization_keeps_body_exclusion(self):
        for literal, wrong in (('12', '21'), ('XII', 'XXI'), ('L', 'M'), ('aa', 'ab')):
            for mismatch in (False, True):
                with self.subTest(literal=literal, mismatch=mismatch), fitz.open() as doc:
                    page = doc.new_page(width=595.276, height=841.89)
                    doc.set_page_labels([dict(startpage=0, prefix=literal)])
                    insert_multiline_body(page)
                    text = wrong if mismatch else literal
                    width = fitz.get_text_length(text, fontsize=11)
                    page.insert_text(((page.rect.width-width)/2, 805), text, fontsize=11)
                    self.assertEqual(footer_candidates(page, expected_label=literal), [text])
                    code, out = self.run_check(doc)
                    self.assertEqual(code, int(mismatch), out)
                    if mismatch:
                        self.assertTrue('PAGE-NUMBER-ODD' in out or 'PAGE-NUMBER-REVERSED' in out, out)

    def test_tied_column_right_edges_use_the_outer_supported_edge(self):
        with document() as doc:
            insert_tied_column_edges(doc[0])
            code, out = self.run_check(doc)
            self.assertEqual(code, 0, out)
            self.assertNotIn('INK-PAST-TEXT-BLOCK', out)

    def test_tied_column_edges_still_report_a_real_overshoot(self):
        with document() as doc:
            insert_tied_column_edges(doc[0], overshoot=True)
            code, out = self.run_check(doc)
            self.assertEqual(code, 0, out)  # This existing rule is a soft finding.
            self.assertIn('INK-PAST-TEXT-BLOCK', out)
            self.assertIn('text block (572.5)', out)
            self.assertIn('10.5pt past', out)

    def test_unequal_supported_body_columns_calibrate_outer_lane(self):
        with document() as doc:
            insert_body_grid(doc[0])
            self.assertEqual(render._proven_column_right_margin(doc), 572.5)
            code, out = self.run_check(doc)
            self.assertEqual(code, 0, out)
            self.assertNotIn('INK-PAST-TEXT-BLOCK', out)

    def test_proven_columns_retain_rare_and_repeated_overshoot_findings(self):
        for count in (1, 9):
            with self.subTest(count=count), document() as doc:
                insert_body_grid(doc[0], overshoots=count)
                code, out = self.run_check(doc)
                self.assertEqual(code, 0, out)
                self.assertIn('INK-PAST-TEXT-BLOCK', out)
                self.assertIn('x=583.0', out)

    def test_gutter_crossing_body_and_malformed_lanes_do_not_prove_columns(self):
        for kwargs in ({'crossing': True}, {'malformed': True}):
            with self.subTest(kwargs=kwargs), document() as doc:
                insert_body_grid(doc[0], **kwargs)
                self.assertIsNone(render._proven_column_right_margin(doc))
                code, out = self.run_check(doc)
                self.assertEqual(code, 0, out)
                self.assertIn('INK-PAST-TEXT-BLOCK', out)

    def test_dense_nested_indents_and_short_tables_do_not_prove_columns(self):
        text = 'Several ordinary words establish a repeated body column.'
        unit_width = fitz.get_text_length(text, fontsize=1.)
        for short in (False, True):
            with self.subTest(short=short), document() as doc:
                for left, right in ((22.5, 384.5), (210.5, 384.5), (398.5, 572.5)):
                    for i in range(8):
                        doc[0].insert_text((left, 100+i*(5 if short else 30)), text,
                                           fontsize=(right-left)/unit_width)
                self.assertIsNone(render._proven_column_right_margin(doc))

    def test_single_column_rare_and_repeated_long_lines_remain_findings(self):
        text = 'Ordinary body prose calibrates this column edge.'
        width = fitz.get_text_length(text, fontsize=8)
        for count in (1, 9):
            with self.subTest(count=count), document() as doc:
                for i in range(40):
                    doc[0].insert_text((384.5-width, 100+10*i), text, fontsize=8)
                for i in range(count):
                    doc[0].insert_text((583.-width, 550+12*i), text, fontsize=8)
                self.assertIsNone(render._proven_column_right_margin(doc))
                code, out = self.run_check(doc)
                self.assertEqual(code, 0, out)
                self.assertIn('INK-PAST-TEXT-BLOCK', out)
                self.assertIn('text block (384.5)', out)

    def test_proven_columns_do_not_disable_hard_offpaper_detection(self):
        with document() as doc:
            insert_body_grid(doc[0])
            doc[0].insert_text((580, 450), 'Off paper body words', fontsize=8)
            code, out = self.run_check(doc)
            self.assertEqual(code, 1, out)
            self.assertIn('INK-OFF-PAPER', out)

    def test_bad_contracts_fail_before_pdf_read(self):
        for kwargs in ({'folio_layout': 'centre'}, {'folio_band': 'body'},
                       {'max_cross_page': -1}):
            with self.subTest(kwargs=kwargs), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(render.check('absent.pdf', **kwargs), 2)

    def test_unreadable_supplied_source_is_tooling_error(self):
        with document() as doc:
            code, out = self.run_check(doc, source_paths=[str(self.path.with_suffix('.tex'))])
            self.assertEqual(code, 2, out)
            self.assertIn('cannot read supplied source', out)

    def test_cli_validates_new_options_and_negative_budget(self):
        with document('right', 'header') as doc:
            doc.save(self.path)
        good = subprocess.run([sys.executable, str(ROOT/'check_pdf_render.py'),
                               '--folio-layout', 'right', '--folio-band', 'header',
                               str(self.path)], text=True, capture_output=True)
        self.assertEqual(good.returncode, 0, good.stdout+good.stderr)
        for flags in (['--folio-layout', 'centre'], ['--folio-band', 'body'],
                      ['--max-cross-page', '-1'], ['--max-cross-page', 'oops']):
            with self.subTest(flags=flags):
                bad = subprocess.run([sys.executable, str(ROOT/'check_pdf_render.py'),
                                      str(self.path), *flags], text=True, capture_output=True)
                self.assertEqual(bad.returncode, 2, bad.stdout+bad.stderr)

    def test_build_preflight_rejects_bad_folio_settings(self):
        for flags in (['--folio-layout', 'centre'], ['--folio-band', 'body']):
            with self.subTest(flags=flags):
                bad = subprocess.run([sys.executable, str(ROOT/'validate_build_config.py'),
                                      *flags], text=True, capture_output=True)
                self.assertEqual(bad.returncode, 2, bad.stdout+bad.stderr)
                self.assertIn('PDF_FOLIO_', bad.stdout)


if __name__ == '__main__':
    unittest.main(verbosity=2)
