#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Original project code; scope and terms: ../LICENSING.md.
"""Unit controls for explicit review recording and regenerated raster evidence."""
from __future__ import annotations
import json
import contextlib
import io
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
sys.dont_write_bytecode = True
import fitz
from render_review import digest, parse_pages, record, render, verify
from new_document import create
import check_content_density


class Release490Tests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='hllpdf-490-unit-')
        self.addCleanup(temp.cleanup); self.root = Path(temp.name)

    def fixture(self):
        pdf = self.root / 'two.pdf'
        with fitz.open() as doc:
            doc.new_page().insert_text((72, 110), 'PAGE ONE: alpha 123')
            doc.new_page().insert_text((120, 220), 'PAGE TWO: beta 456')
            doc.save(pdf)
        output = self.root / 'review'; render(pdf, output, dpi=72)
        return pdf, output / 'review.json'

    def attest(self, pdf, path, pages='1-2'):
        return record(pdf, path, pages, 'synthetic-test', 'Not a human inspection; testing evidence mechanics.')

    def test_page_selection_is_explicit_bounded_and_unique(self):
        self.assertEqual(parse_pages('1,3-5', 5), [1, 3, 4, 5])
        for bad in ['', 'all', '0', '1,1', '2-1', '1-999999999', '../1', '1-2,2', '01', '1,']:
            with self.subTest(bad=bad), self.assertRaises(ValueError): parse_pages(bad, 5)

    def test_partial_record_does_not_approve_other_pages(self):
        pdf, path = self.fixture(); original = json.loads(path.read_text())
        self.assertEqual(self.attest(pdf, path, '2'), [2])
        data = json.loads(path.read_text())
        self.assertEqual(data['pages'][0]['status'], 'pending')
        self.assertEqual(data['pages'][1]['status'], 'reviewed')
        for before, after in zip(original['pages'], data['pages']):
            self.assertEqual(before['sha256'], after['sha256'])
            self.assertEqual(before['image'], after['image'])
        self.assertTrue(verify(pdf, path))
        self.attest(pdf, path, '1'); self.assertEqual(verify(pdf, path, rerender=True), [])

    def test_blank_reviewer_and_notes_are_rejected_without_mutation(self):
        pdf, path = self.fixture(); original = path.read_bytes()
        for name, notes in [('', 'text'), ('name', '  ')]:
            with self.assertRaises(ValueError): record(pdf, path, '1', name, notes)
            self.assertEqual(path.read_bytes(), original)

    def test_stale_pdf_cannot_be_attested(self):
        pdf, path = self.fixture(); original = path.read_bytes()
        pdf.write_bytes(pdf.read_bytes() + b'\n%changed')
        with self.assertRaisesRegex(ValueError, 'stale'): self.attest(pdf, path)
        self.assertEqual(path.read_bytes(), original)

    def test_stale_image_cannot_be_attested(self):
        pdf, path = self.fixture(); original = path.read_bytes()
        image = path.parent / json.loads(original)['pages'][0]['image']
        image.write_bytes(image.read_bytes() + b'changed')
        with self.assertRaisesRegex(ValueError, 'stale'): self.attest(pdf, path)
        self.assertEqual(path.read_bytes(), original)

    def test_review_symlink_cannot_redirect_write(self):
        pdf, path = self.fixture(); link = path.parent / 'alias.json'; link.symlink_to(path)
        with self.assertRaisesRegex(ValueError, 'symlink'): self.attest(pdf, link)
        self.assertTrue(link.is_symlink())

    def test_swapped_images_with_updated_hashes_fail_fresh_render(self):
        pdf, path = self.fixture(); self.attest(pdf, path)
        data = json.loads(path.read_text())
        a, b = [path.parent / entry['image'] for entry in data['pages']]
        x, y = a.read_bytes(), b.read_bytes(); a.write_bytes(y); b.write_bytes(x)
        for entry in data['pages']: entry['sha256'] = digest(path.parent / entry['image'])
        path.write_text(json.dumps(data))
        # Demonstrates the exact gap in a hashes-only attestation, not an attack
        # on a signing system: this manifest is intentionally user-editable.
        self.assertEqual(verify(pdf, path), [])
        errors = verify(pdf, path, rerender=True)
        self.assertEqual(len([e for e in errors if 'pixels differ' in e]), 2)

    def test_pixel_equality_is_not_compressed_byte_equality(self):
        pdf, path = self.fixture(); self.attest(pdf, path)
        data = json.loads(path.read_text()); image = path.parent / data['pages'][0]['image']
        image.write_bytes(image.read_bytes() + b'\nnonvisual trailing metadata')
        data['pages'][0]['sha256'] = digest(image); path.write_text(json.dumps(data))
        self.assertEqual(verify(pdf, path, rerender=True), [])

    def test_invalid_dpi_and_renderer_metadata_fail_closed(self):
        pdf, path = self.fixture(); original = json.loads(path.read_text())
        for value in [True, '144', 0, 301, None]:
            data = {**original, 'dpi': value}; path.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, 'DPI'): verify(pdf, path)
        path.write_text(json.dumps({**original, 'renderer': ''}))
        with self.assertRaisesRegex(ValueError, 'renderer'): verify(pdf, path)

    def test_unknown_status_is_not_silently_overwritten(self):
        pdf, path = self.fixture(); data = json.loads(path.read_text())
        data['pages'][0]['status'] = 'automatic-pass'; path.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'status'): self.attest(pdf, path)

    def test_flow_table_is_counted_as_structure_not_emphasis(self):
        source = self.root / 'density.tex'
        source.write_text(r"""\section{א} 
\begin{flowtable}{1}{H{5cm}}{כותרת}{tab:a}{תא}
ערך\\
\end{flowtable}
\section{ב}
טקסט.
""")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            result = check_content_density.main([str(source)], 'report', [])
        self.assertEqual(result, 0)
        self.assertIn('1 tables', out.getvalue())
        self.assertIn('0% of body content sits inside EMPHASIS', out.getvalue())

    def test_flow_layer_only_copied_when_requested(self):
        for kind in ['note', 'technical', 'formula-sheet', 'data-report']:
            target = self.root / kind; create(kind, target)
            manifest = json.loads((target / 'project.json').read_text())
            self.assertEqual((target / 'flow_tables.tex').exists(), kind == 'data-report')
            if kind == 'data-report':
                self.assertEqual(manifest['copied_assets']['flow_tables.tex'], digest(target / 'flow_tables.tex'))


if __name__ == '__main__': unittest.main(verbosity=2)
