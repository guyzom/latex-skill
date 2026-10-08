#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Original project code; scope and terms: ../LICENSING.md.
"""v5.3.5 static controls: the folio face is the (font, size) pair.

The v5.2.0 folio rewrite dropped v4.25.0's learned folio face (BLD-67); v5.3.5
restores it. The pair matters, not the font alone: six correct pages of the
fleet carry a second centred run in the folio's OWN font at another size -- body
text at 10.9pt (computer-architecture-exams 11/38/55/74), a text subscript and
a fraction's denominator at 8pt (lifting-optimization 17, particles-nuclei-
exams 29). A font-only face keeps all six ambiguous; the delivered v5.3.4 gate,
with no face at all, rejects them. These synthetic pages reproduce both shapes
with real glyphs; the controls are what the rule must leave visible.
"""
from __future__ import annotations

import contextlib
import io
from pathlib import Path
import sys
import tempfile
import unittest
import unittest.mock

sys.dont_write_bytecode = True
import fitz
import check_pdf_render as render
import pdf_folios
from pdf_folios import footer_candidates


def document(wrong=False):
    doc = fitz.open()
    for i in range(4):
        page = doc.new_page(width=595.276, height=841.89)
        page.insert_text((60, 150), 'A general document with selected design.')
        text = '21' if wrong and i == 0 else str(i + 12)
        width = fitz.get_text_length(text, fontsize=11)
        page.insert_text(((page.rect.width - width) / 2, 805), text, fontsize=11)
    doc.set_page_labels([dict(startpage=0, style='D', firstpagenum=12)])
    return doc


def body_run(page, text='31', size=10):
    """A centred run of body text in the folio's font, another size."""
    width = fitz.get_text_length(text, fontsize=size)
    page.insert_text(((page.rect.width - width) / 2, 775), text, fontsize=size)


def text_subscript(page):
    """eta_opt's shape: a mathematical base (brackets are not label characters)
    and its text subscript in the folio's font at 8pt, 0.15em (sub1) below."""
    width = fitz.get_text_length('opt', fontsize=8)
    start = (page.rect.width - width) / 2
    page.insert_text((start - fitz.get_text_length('(Q)', fontsize=12), 770), '(Q)', fontsize=12)
    page.insert_text((start, 771.8), 'opt', fontsize=8)


def faceless():
    """Mutation: every run loses its face, as in the delivered v5.3.4."""
    original = pdf_folios._styled_candidates
    return unittest.mock.patch.object(
        pdf_folios, '_styled_candidates',
        lambda *a, **k: [(t, frozenset()) for t, _ in original(*a, **k)])


def font_only():
    """Mutation: the face is the font alone (size dropped)."""
    original = pdf_folios._styled_candidates
    return unittest.mock.patch.object(
        pdf_folios, '_styled_candidates',
        lambda *a, **k: [(t, frozenset(f for f, _ in face)) for t, face in original(*a, **k)])


class FolioFaceSizeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='hllpdf5350-')
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'probe.pdf'

    def check(self, doc):
        doc.save(self.path)
        with contextlib.redirect_stdout(io.StringIO()) as out:
            code = render.check(str(self.path))
        return code, out.getvalue()

    def test_01_body_text_in_the_folio_font_is_not_a_second_folio(self):
        with document() as doc:
            body_run(doc[0])
            self.assertCountEqual(footer_candidates(doc[0], expected_label='12'), ['31', '12'])
            code, out = self.check(doc)                       # still SEEN, not a folio
            self.assertEqual(code, 0, out)
            self.assertIn('4/4 center footer folios', out)

    def test_02_text_subscript_in_the_folio_font_is_not_a_second_folio(self):
        with document() as doc:
            text_subscript(doc[0])
            self.assertCountEqual(footer_candidates(doc[0], expected_label='12'), ['opt', '12'])
            code, out = self.check(doc)
            self.assertEqual(code, 0, out)

    def test_03_same_font_same_size_second_run_stays_ambiguous(self):
        with document() as doc:
            body_run(doc[0], size=11)
            code, out = self.check(doc)
            self.assertEqual(code, 1, out)
            self.assertIn('FOLIO-AMBIGUOUS', out)

    def test_04_wrong_folio_survives_beside_a_filtered_run(self):
        with document(wrong=True) as doc:
            body_run(doc[0])
            code, out = self.check(doc)
            self.assertEqual(code, 1, out)
            self.assertIn('PAGE-NUMBER-REVERSED', out)

    def test_05_both_mutations_restore_the_false_rejection(self):
        for mutation in (faceless, font_only):
            for shape in (body_run, text_subscript):
                with self.subTest(mutation=mutation.__name__, shape=shape.__name__), \
                        document() as doc, mutation():
                    shape(doc[0])
                    code, out = self.check(doc)
                    self.assertEqual(code, 1, out)
                    self.assertIn('p.1 [FOLIO-AMBIGUOUS]', out)


if __name__ == '__main__':
    unittest.main(verbosity=2)
