#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Original project code; scope and terms: ../LICENSING.md.
"""Bounded academic caption contract controls using actual PDF glyphs.

The explicit legacy bold contract is protected by test_caption_styles.py.
These cases exercise the default regular/black contract and its destination ownership;
they do not infer document semantics or attest visual review.
"""
from __future__ import annotations

import contextlib
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
import fitz
import check_pdf_render as render

ROOT = Path(__file__).resolve().parent.parent


def caption_document(label='Figure 1: Central result.', *, font='tiro', color=0,
                     destination='fig.1', y=100, duplicate=False):
    doc = fitz.open()
    page = doc.new_page(width=595.276, height=841.89)
    rgb = tuple(((color >> shift) & 255) / 255 for shift in (16, 8, 0))
    page.insert_text((120, 200), label, fontname=font, fontsize=11, color=rgb)
    if duplicate:
        page.insert_text((120, 250), label, fontname=font, fontsize=11, color=rgb)
    doc.xref_set_key(doc.pdf_catalog(), 'Names',
        f'<</Dests<</Names[({destination})[{page.xref} 0 R /XYZ 0 {page.rect.height-y} null]]>>>>')
    return doc


class AcademicCaptionContract(unittest.TestCase):
    def sites(self, page):
        return render.caption_sites(page, 0, 'normal')

    def findings(self, doc):
        hard, soft = [], []
        count = render.dest_landing(doc, hard, soft, 0, 'normal')
        self.assertEqual(count, 1)
        return [row[1] for row in hard], [row[1] for row in soft]

    def test_regular_caption_prefix_excludes_description_geometry(self):
        with caption_document() as doc:
            sites = self.sites(doc[0])
            self.assertEqual([(x[0], x[1]) for x in sites], [('fig', '1')])
            label = doc[0].search_for('Figure 1:')[0]
            self.assertLess(abs(sites[0][2].x0-label.x0), .01)
            self.assertLess(abs(sites[0][2].x1-label.x1), .01)
            self.assertEqual(self.findings(doc), ([], []))

    def test_adjacent_pdf_fragments_on_one_physical_caption_baseline(self):
        with caption_document(label='') as doc:
            page = doc[0]
            first = 'Figure '
            page.insert_text((120, 200), first, fontname='tiro', fontsize=11)
            x = 120 + fitz.get_text_length(first, fontname='tiro', fontsize=11)
            page.insert_text((x, 200), '1:', fontname='helv', fontsize=11)
            x += fitz.get_text_length('1:', fontname='helv', fontsize=11) + 5
            page.insert_text((x, 200), 'Fragmented caption.', fontname='tiro', fontsize=11)
            self.assertEqual([(row[0], row[1]) for row in self.sites(page)], [('fig', '1')])
            self.assertEqual(self.findings(doc), ([], []))

    def test_table_appendix_and_multi_digit_numbers(self):
        for label, number in [('Table 12: Data.', '12'), ('Table A.2: Data.', 'A.2'),
                              ('Table 3.12: Data.', '3.12')]:
            with self.subTest(label=label), caption_document(label, destination='tbl.'+number) as doc:
                self.assertEqual([(x[0], x[1]) for x in self.sites(doc[0])], [('tbl', number)])
                self.assertEqual(self.findings(doc), ([], []))

    def test_default_regular_contract_and_explicit_legacy_contract(self):
        with caption_document() as doc:
            self.assertEqual([(x[0], x[1]) for x in render.caption_sites(doc[0])], [('fig', '1')])
            self.assertEqual(render.caption_sites(doc[0], 0x555555, 'bold'), [])

    def test_regular_contract_rejects_body_reference_and_wrong_style(self):
        controls = [('See Figure 1: Central result.', 'tiro', 0),
                    ('Figure 1 is central.', 'tiro', 0),
                    ('Figure 1: Central result.', 'tibo', 0),
                    ('Figure 1: Central result.', 'tiro', 0x555555)]
        for label, font, color in controls:
            with self.subTest(label=label, font=font, color=color), caption_document(label, font=font, color=color) as doc:
                self.assertEqual(self.sites(doc[0]), [])
                self.assertEqual(self.findings(doc), (['DEST-CAPTION-NOT-FOUND'], []))

    def test_wrong_number_cannot_fall_back_to_nearest_regular_caption(self):
        with caption_document('Figure 2: Different result.') as doc:
            self.assertEqual(self.findings(doc), (['DEST-CAPTION-NOT-FOUND'], []))

    def test_duplicate_regular_number_has_no_inferred_ownership(self):
        with caption_document(duplicate=True) as doc:
            self.assertEqual(self.findings(doc), (['DEST-CAPTION-AMBIGUOUS'], []))

    def test_regular_destination_at_caption_remains_hard_failure(self):
        with caption_document(y=195) as doc:
            self.assertEqual(self.findings(doc), (['DEST-AT-CAPTION'], []))

    def test_cli_declares_style_and_rejects_invalid_weight(self):
        with tempfile.TemporaryDirectory(prefix='studio-academic-caption-') as td:
            pdf = Path(td)/'regular.pdf'
            with caption_document() as doc:
                doc.save(pdf)
            result = subprocess.run([sys.executable, str(ROOT/'scripts/check_pdf_render.py'),
                str(pdf), '--caption-color', '000000', '--caption-label-weight', 'normal'],
                text=True, capture_output=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
            self.assertNotIn('DEST-CAPTION-NOT-FOUND', result.stdout)
            for invalid in ('', 'regular', 'normalfont', 'BOLD', 'normal,bold'):
                for script in ('check_pdf_render.py', 'validate_build_config.py'):
                    command = [sys.executable, str(ROOT/'scripts'/script), '--caption-label-weight', invalid]
                    if script == 'check_pdf_render.py':
                        command.append(str(pdf))
                    bad = subprocess.run(command, capture_output=True, text=True, timeout=30)
                    self.assertEqual(bad.returncode, 2, (script, invalid, bad.stdout+bad.stderr))

    def test_invalid_weight_preflight_preserves_published_pdf(self):
        with tempfile.TemporaryDirectory(prefix='studio-academic-config-') as td:
            project = Path(td)
            (project/'main.tex').write_text(r'\documentclass{article}\begin{document}Control.\end{document}')
            with caption_document() as doc:
                doc.save(project/'main.pdf')
            before = (project/'main.pdf').read_bytes()
            for invalid in ('', 'regular'):
                env = dict(os.environ, PDF_CAPTION_LABEL_WEIGHT=invalid)
                result = subprocess.run(['bash', str(ROOT/'scripts/build.sh'), str(project/'main.tex')],
                    cwd=project, env=env, text=True, capture_output=True, timeout=30)
                self.assertEqual(result.returncode, 2, result.stdout+result.stderr)
                self.assertIn('PDF_CAPTION_LABEL_WEIGHT', result.stdout)
                self.assertEqual((project/'main.pdf').read_bytes(), before)
                self.assertFalse((project/'main.log').exists())

    def test_direct_api_invalid_weight_is_tooling_failure(self):
        for invalid in ('', 'regular', None):
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(render.check('missing.pdf', caption_label_weight=invalid), 2)


if __name__ == '__main__':
    unittest.main(verbosity=2)
