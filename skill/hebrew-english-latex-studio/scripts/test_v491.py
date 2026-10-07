#!/usr/bin/env python3
"""Release controls for repository/credential debris, output aliases and review notes."""
from __future__ import annotations
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
sys.dont_write_bytecode = True
import fitz
from check_package_hygiene import validate
from package_skill import build_archive
from render_review import render, verify, record
ROOT = Path(__file__).resolve().parent.parent


class Release491Tests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='hllpdf-491-unit-')
        self.addCleanup(temp.cleanup); self.root = Path(temp.name)

    def write(self, name, text='synthetic sentinel\n'):
        p = self.root / name; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(text)
        return p

    def test_repository_directory_is_not_a_release_asset(self):
        self.write('.git/config')
        self.assertTrue(any('version-control' in e for e in validate(self.root)))

    def test_repository_worktree_file_is_also_rejected(self):
        self.write('.git', 'gitdir: /synthetic/private/path\n')
        self.assertTrue(any('version-control' in e for e in validate(self.root)))

    def test_conventional_secret_files_are_rejected(self):
        for name in ['.env', '.env.local', '.env.example', '.NETRC', 'id_ed25519', 'credential.pem', 'credentials.json']:
            with self.subTest(name=name):
                p = self.write(name)
                self.assertTrue(any('credential-like' in e for e in validate(self.root))); p.unlink()

    def test_opaque_nested_archives_are_rejected(self):
        for name in ['old.skill', 'backup.ZIP', 'fonts.tar.gz', 'data.7z']:
            with self.subTest(name=name):
                p = self.write(name)
                self.assertTrue(any('nested archive' in e for e in validate(self.root))); p.unlink()

    def test_ordinary_documentation_is_not_a_secret_finding(self):
        self.write('references/git-and-env.md', 'Discuss .git and .env without shipping them.')
        self.write('tests/tex_errors_real.log.txt', '! synthetic log fixture')
        self.assertEqual(validate(self.root), [])

    def test_parent_symlink_cannot_publish_inside_source(self):
        source = self.root / 'source'; source.mkdir()
        alias = self.root / 'alias'; alias.symlink_to(source, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'outside the package root'):
            build_archive(source, alias / 'out.skill')
        self.assertEqual(list(source.iterdir()), [])

    def test_parent_dotdot_cannot_publish_inside_source(self):
        source = self.root / 'source'; source.mkdir()
        with self.assertRaisesRegex(ValueError, 'outside the package root'):
            build_archive(source, self.root / 'unused' / '..' / 'source' / 'out.skill')
        self.assertEqual(list(source.iterdir()), [])

    def test_hygiene_failure_precedes_release_execution(self):
        source = self.root / 'source'; source.mkdir()
        (source / '.env').write_text('SYNTHETIC=1\n')
        output = self.root / 'release.skill'; output.write_bytes(b'existing-user-output')
        with self.assertRaisesRegex(ValueError, 'credential-like'):
            build_archive(source, output)
        self.assertEqual(output.read_bytes(), b'existing-user-output')

    def fixture(self):
        pdf = self.root / 'one.pdf'
        with fitz.open() as doc:
            doc.new_page().insert_text((72,100), 'Synthetic review control')
            doc.save(pdf)
        render(pdf, self.root / 'review', dpi=72)
        return pdf, self.root / 'review/review.json'

    def test_boolean_schema_is_not_integer_schema_one(self):
        pdf, review = self.fixture()
        data = json.loads(review.read_text()); data['schema'] = True
        review.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'unsupported review schema'):
            verify(pdf, review, require_attestations=False)

    def test_reviewed_page_without_notes_cannot_pass(self):
        pdf, review = self.fixture()
        record(pdf, review, '1', 'synthetic-test', 'Testing mechanics, not human inspection.')
        data = json.loads(review.read_text()); data['pages'][0]['notes'] = '  '
        review.write_text(json.dumps(data))
        self.assertTrue(any('nonempty notes' in e for e in verify(pdf, review)))

    def test_pending_page_may_have_blank_notes_but_is_not_approved(self):
        pdf, review = self.fixture()
        self.assertEqual(verify(pdf, review, require_attestations=False), [])
        self.assertTrue(any('not reviewed' in e for e in verify(pdf, review)))

    def test_recorded_notes_survive_fresh_render_verification(self):
        pdf, review = self.fixture()
        record(pdf, review, '1', 'synthetic-test', 'Testing mechanics, not human inspection.')
        self.assertEqual(verify(pdf, review, rerender=True), [])


if __name__ == '__main__': unittest.main(verbosity=2)
