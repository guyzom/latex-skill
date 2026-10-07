#!/usr/bin/env python3
"""Adversarial tests for canonical fonts, source projects and exact-byte review evidence."""
from __future__ import annotations
import hashlib
import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile
sys.dont_write_bytecode = True
import fitz
from font_paths import default_install_dir, font_dir, MANIFEST_DIR
import install_fonts
from install_fonts import pins, stage_from_skill
from new_document import create, KINDS
from render_review import render, verify, digest

ROOT = Path(__file__).resolve().parent.parent


class Release480Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='hllpdf-480-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_explicit_font_location_fails_closed(self):
        with patch.dict(os.environ, {'HEBREW_LATEX_FONT_DIR': str(self.root/'missing')}):
            self.assertEqual(font_dir(), self.root/'missing')

    def test_empty_and_relative_xdg_use_home_default(self):
        for value in ('', 'relative-data', '~/relative-data'):
            with self.subTest(xdg=value), \
                 patch.dict(os.environ, {'XDG_DATA_HOME': value}), \
                 patch.object(Path, 'home', return_value=self.root/'home'):
                self.assertEqual(default_install_dir(),
                                 self.root/'home/.local/share/fonts/hebrew-lualatex-pdf')

    def test_absolute_xdg_is_respected(self):
        with patch.dict(os.environ, {'XDG_DATA_HOME': str(self.root/'data')}):
            self.assertEqual(default_install_dir(), self.root/'data/fonts/hebrew-lualatex-pdf')

    def test_unset_xdg_uses_home_default(self):
        environment = dict(os.environ)
        environment.pop('XDG_DATA_HOME', None)
        with patch.dict(os.environ, environment, clear=True), \
             patch.object(Path, 'home', return_value=self.root/'home'):
            self.assertEqual(default_install_dir(),
                             self.root/'home/.local/share/fonts/hebrew-lualatex-pdf')

    def test_empty_font_override_installs_where_build_resolves(self):
        for xdg in ('', 'relative-data', str(self.root/'data')):
            with self.subTest(xdg=xdg), \
                 patch.dict(os.environ, {'HEBREW_LATEX_FONT_DIR': '', 'XDG_DATA_HOME': xdg}), \
                 patch.object(Path, 'home', return_value=self.root/'home'), \
                 patch.object(sys, 'argv', ['install_fonts.py']), \
                 patch.object(install_fonts, 'install') as operation, \
                 contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(install_fonts.main(), 0)
                self.assertEqual(operation.call_args.args[0], font_dir())

    def test_nonempty_font_override_remains_authoritative_for_install(self):
        target = self.root/'chosen'
        with patch.dict(os.environ, {'HEBREW_LATEX_FONT_DIR': str(target)}), \
             patch.object(sys, 'argv', ['install_fonts.py']), \
             patch.object(install_fonts, 'install') as operation, \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(install_fonts.main(), 0)
            self.assertEqual(operation.call_args.args[0], target)
            self.assertEqual(font_dir(), target)

    def test_installer_argument_has_precedence_over_environment(self):
        target = self.root/'argument'
        with patch.dict(os.environ, {'HEBREW_LATEX_FONT_DIR': str(self.root/'environment')}), \
             patch.object(sys, 'argv', ['install_fonts.py', str(target)]), \
             patch.object(install_fonts, 'install') as operation, \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(install_fonts.main(), 0)
            self.assertEqual(operation.call_args.args[0], target)

    def test_changed_font_and_sidecar_cannot_redefine_trust(self):
        target = self.root/'fonts'
        shutil.copytree(font_dir(), target)
        face = target/'Heebo-Regular.ttf'
        data = bytearray(face.read_bytes()); data[-1] ^= 1; face.write_bytes(data)
        manifest = target/'SHA256SUMS'
        old = pins()['Heebo-Regular.ttf']
        manifest.write_text(manifest.read_text().replace(old, digest(face)))
        result = subprocess.run([sys.executable, str(ROOT/'scripts/verify_font_bundle.py'), str(target)], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('canonical', result.stdout+result.stderr)

    def test_duplicate_manifest_record_rejected(self):
        target = self.root/'fonts'; shutil.copytree(font_dir(), target)
        path = target/'SHA256SUMS'
        path.write_text(path.read_text()+'\n'+path.read_text().splitlines()[0]+'\n')
        result = subprocess.run([sys.executable, str(ROOT/'scripts/verify_font_bundle.py'), str(target)], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)

    def _archive(self, member: str, data: bytes, duplicate=False):
        path = self.root/'input.skill'
        with zipfile.ZipFile(path, 'w') as z:
            z.writestr(member, data)
            if duplicate:
                z.writestr('other/'+Path(member).name, data)
        return path

    def test_archive_import_reads_only_verified_named_faces(self):
        name = 'Heebo-Regular.ttf'; data = (font_dir()/name).read_bytes()
        archive = self._archive('old/assets/fonts/'+name, data)
        stage = self.root/'stage'; stage.mkdir()
        stage_from_skill(archive, stage, {name:pins()[name]})
        self.assertEqual((stage/name).read_bytes(), data)

    def test_archive_duplicate_face_is_ambiguous(self):
        name = 'Heebo-Regular.ttf'; data = (font_dir()/name).read_bytes()
        archive = self._archive('old/assets/fonts/'+name, data, duplicate=True)
        with self.assertRaisesRegex(ValueError, 'expected one'):
            stage_from_skill(archive, self.root, {name:pins()[name]})

    def test_archive_traversal_and_digest_mismatch_rejected(self):
        name = 'Heebo-Regular.ttf'; data = (font_dir()/name).read_bytes()
        for member, body, message in [('../'+name,data,'unsafe'), ('old/'+name,b'not a font','canonical')]:
            archive = self._archive(member, body)
            with self.assertRaisesRegex(ValueError, message):
                stage_from_skill(archive, self.root, {name:pins()[name]})

    def test_all_starters_preserve_version_and_source_hashes(self):
        for kind in KINDS:
            dest = self.root/kind; create(kind,dest)
            m = json.loads((dest/'project.json').read_text())
            self.assertEqual(m['kind'],kind)
            self.assertEqual(m['skill_version'],(ROOT/'VERSION').read_text().strip())
            self.assertFalse(m['font_binaries_included'])
            self.assertEqual(m['font_manifest_sha256'], digest(MANIFEST_DIR/'SHA256SUMS'))
            for name, h in m['copied_assets'].items():
                self.assertEqual(digest(dest/name),h)
            self.assertNotIn('/mnt/data', (dest/'build.sh').read_text())

    def test_existing_directory_and_symlink_not_overwritten(self):
        dest = self.root/'existing'; dest.mkdir()
        (dest/'sentinel').write_text('untouched')
        with self.assertRaises(ValueError): create('note',dest)
        self.assertEqual((dest/'sentinel').read_text(),'untouched')
        link = self.root/'link'; link.symlink_to(dest, target_is_directory=True)
        with self.assertRaises(ValueError): create('note',link)
        self.assertTrue(link.is_symlink())

    def _review(self):
        pdf = self.root/'sample.pdf'
        with fitz.open() as d:
            d.new_page().insert_text((72,72),'Review fixture, not a human review')
            d.save(pdf)
        dest = self.root/'review'; render(pdf,dest,dpi=72)
        return pdf,dest/'review.json'

    def test_review_is_pending_until_explicitly_attested(self):
        pdf, path = self._review()
        self.assertTrue(verify(pdf,path))
        data = json.loads(path.read_text())
        self.assertEqual(data['pages'][0]['status'],'pending')
        data['pages'][0].update(status='reviewed',reviewer='synthetic-test-only',notes='Not a human inspection')
        path.write_text(json.dumps(data))
        self.assertEqual(verify(pdf,path),[])
        with self.assertRaises(ValueError): render(pdf,path.parent)

    def test_changed_pdf_and_image_invalidate_attestation(self):
        pdf,path=self._review(); data=json.loads(path.read_text())
        data['pages'][0].update(status='reviewed',reviewer='synthetic-test-only')
        path.write_text(json.dumps(data))
        image=path.parent/data['pages'][0]['image']; image.write_bytes(image.read_bytes()+b'changed')
        self.assertTrue(any('image digest' in e for e in verify(pdf,path)))
        pdf.write_bytes(pdf.read_bytes()+b'\n%changed')
        self.assertTrue(any('PDF digest' in e for e in verify(pdf,path)))

    def test_review_image_path_escape_rejected(self):
        pdf,path=self._review(); data=json.loads(path.read_text())
        data['pages'][0]['image']='../outside.png'; path.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError,'unsafe'): verify(pdf,path)

    def test_release_contains_no_font_programs(self):
        forbidden={'.ttf','.otf','.ttc','.woff','.woff2','.pfb','.pfa'}
        self.assertEqual([str(p.relative_to(ROOT)) for p in ROOT.rglob('*') if p.suffix.lower() in forbidden],[])


if __name__ == '__main__':
    unittest.main(verbosity=2)
