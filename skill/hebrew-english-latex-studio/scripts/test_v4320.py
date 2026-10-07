#!/usr/bin/env python3
"""Disposable-tree controls for cleanup's directory-symlink boundary.

Every removable file is synthetic. No test touches files outside its own
TemporaryDirectory, even the mutation which restores the old deletion defect.
Set HLLPDF_432_SOURCE_REPORT to an external JSON path for a result trace.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
from clean_harness_artifacts import sweep
from check_package_hygiene import validate

ROOT = Path(__file__).resolve().parent.parent
EVENTS: list[dict] = []
PAYLOAD = b'Synthetic cleanup sentinel; this is not a PDF document.\n'


class CleanupBoundary(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='hllpdf432-cleanup-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project = self.root / 'project'
        self.project.mkdir()
        self.outside = self.root / 'outside'
        self.outside.mkdir()

    def make(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(PAYLOAD)
        return path

    def preserved(self, path: Path):
        self.assertTrue(path.is_file(), str(path))
        self.assertEqual(path.read_bytes(), PAYLOAD)

    def test_top_level_external_directory_links_are_not_traversed(self):
        for name in ('assets', 'tests'):
            with self.subTest(name=name):
                target = self.outside / name
                sentinel = self.make(target / 'important.pdf')
                (self.project / name).symlink_to(target, target_is_directory=True)
                self.assertEqual(sweep(self.project, dry_run=True), [])
                self.assertEqual(sweep(self.project), [])
                self.preserved(sentinel)
                self.assertTrue((self.project / name).is_symlink())
                EVENTS.append(dict(case=name, outside_preserved=True,
                                   sha256=hashlib.sha256(sentinel.read_bytes()).hexdigest()))

    def test_top_level_links_inside_root_remain_hygiene_errors(self):
        target = self.project / 'references' / 'source-assets'
        sentinel = self.make(target / 'source.pdf')
        (self.project / 'assets').symlink_to(target, target_is_directory=True)
        self.assertEqual(sweep(self.project), [])
        self.preserved(sentinel)
        self.assertTrue(any('symlink' in e for e in validate(self.project)))

    def test_broken_harness_directory_links_remain_intact(self):
        for name in ('assets', 'tests'):
            (self.project / name).symlink_to(self.outside / 'absent', target_is_directory=True)
        self.assertEqual(sweep(self.project), [])
        self.assertTrue((self.project / 'assets').is_symlink())
        self.assertTrue((self.project / 'tests').is_symlink())

    def test_nested_directory_links_are_not_followed(self):
        for name in ('assets', 'tests'):
            base = self.project / name
            base.mkdir()
            external = self.make(self.outside / name / 'external.pdf')
            internal = self.make(self.project / 'references' / name / 'internal.log')
            (base / 'external').symlink_to(external.parent, target_is_directory=True)
            (base / 'internal').symlink_to(internal.parent, target_is_directory=True)
            (base / 'loop').symlink_to(base, target_is_directory=True)
            self.make(base / 'ordinary.aux')
        self.assertEqual(sweep(self.project), ['assets/ordinary.aux', 'tests/ordinary.aux'])
        for name in ('assets', 'tests'):
            self.preserved(self.outside / name / 'external.pdf')
            self.preserved(self.project / 'references' / name / 'internal.log')
            self.assertTrue((self.project / name / 'loop').is_symlink())

    def test_file_links_including_broken_ones_are_never_removed(self):
        base = self.project / 'assets'
        base.mkdir()
        source = self.make(self.outside / 'source.pdf')
        (base / 'linked.pdf').symlink_to(source)
        (base / 'broken.log').symlink_to(self.outside / 'absent.log')
        self.assertEqual(sweep(self.project), [])
        self.preserved(source)
        self.assertTrue((base / 'linked.pdf').is_symlink())
        self.assertTrue((base / 'broken.log').is_symlink())

    def test_real_nested_debris_is_removed_in_stable_order(self):
        expected = ['assets/a/result.pdf', 'assets/z/result.log', 'tests/q.aux']
        for rel in reversed(expected):
            self.make(self.project / rel)
        outside = self.make(self.outside / 'result.pdf')
        self.assertEqual(sweep(self.project), expected)
        for rel in expected:
            self.assertFalse((self.project / rel).exists())
        self.preserved(outside)

    def test_source_evidence_and_unicode_names_survive(self):
        keep = ['assets/מקור.tex', 'tests/sample.log.txt', 'tests/odd?.tex',
                'tests/sample.aux.tex', 'references/ordinary.pdf']
        for rel in keep:
            self.make(self.project / rel)
        self.make(self.project / 'tests' / 'generated.log')
        self.assertEqual(sweep(self.project), ['tests/generated.log'])
        for rel in keep:
            self.preserved(self.project / rel)

    def test_dry_run_reports_without_modification(self):
        p = self.make(self.project / 'assets' / 'generated.pdf')
        self.assertEqual(sweep(self.project, dry_run=True), ['assets/generated.pdf'])
        self.preserved(p)
        self.assertEqual(sweep(self.project), ['assets/generated.pdf'])
        self.assertFalse(p.exists())

    def test_second_cleanup_and_absent_directories_are_noops(self):
        self.assertEqual(sweep(self.project), [])
        self.make(self.project / 'tests' / 'generated.log')
        self.assertEqual(sweep(self.project), ['tests/generated.log'])
        self.assertEqual(sweep(self.project), [])

    @unittest.skipUnless(hasattr(os, 'mkfifo'), 'named pipes require a POSIX platform')
    def test_nonregular_suffix_match_is_not_a_generated_file(self):
        base = self.project / 'assets'
        base.mkdir()
        pipe = base / 'pipe.pdf'
        os.mkfifo(pipe)
        self.assertEqual(sweep(self.project), [])
        self.assertTrue(pipe.exists())
        self.assertFalse(pipe.is_file())

    def test_cli_dry_run_and_cleanup_preserve_external_directory(self):
        sentinel = self.make(self.outside / 'source.pdf')
        (self.project / 'assets').symlink_to(self.outside, target_is_directory=True)
        generated = self.make(self.project / 'tests' / 'test.log')
        command = [sys.executable, str(ROOT / 'scripts/clean_harness_artifacts.py'), str(self.project)]
        for dry in (True, False):
            r = subprocess.run(command + (['--dry-run'] if dry else []),
                               capture_output=True, text=True, timeout=30)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn('tests/test.log', r.stdout)
            self.assertNotIn('assets/source.pdf', r.stdout)
            self.preserved(sentinel)
            self.assertEqual(generated.exists(), dry)

    def test_removing_the_guard_reproduces_the_old_deletion(self):
        source = (ROOT / 'scripts/clean_harness_artifacts.py').read_text(encoding='utf-8')
        old = 'if base.is_symlink() or not base.is_dir():'
        self.assertEqual(source.count(old), 1, 'mutation site changed; review the test')
        mutation = source.replace(old, 'if not base.is_dir():', 1)
        module = self.root / 'mutated-cleanup.py'
        module.write_text(mutation, encoding='utf-8')
        sentinel = self.make(self.outside / 'synthetic.pdf')
        (self.project / 'assets').symlink_to(self.outside, target_is_directory=True)
        env = dict(os.environ, PYTHONPATH=str(ROOT / 'scripts'), PYTHONDONTWRITEBYTECODE='1')
        r = subprocess.run([sys.executable, str(module), str(self.project)], env=env,
                           capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse(sentinel.exists(), 'the mutant must actually reproduce the defect')
        self.assertIn('assets/synthetic.pdf', r.stdout)
        EVENTS.append(dict(case='removed-guard mutation', synthetic_target_deleted=True,
                           output=r.stdout, all_paths_inside_test_temporary_directory=True))


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(CleanupBoundary))
    chosen = os.environ.get('HLLPDF_432_SOURCE_REPORT')
    if chosen:
        path = Path(chosen).resolve()
        if path == ROOT or ROOT in path.parents:
            raise ValueError('the report must be outside the skill')
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            raise ValueError('refusing to overwrite a source-test report')
        path.write_text(json.dumps(dict(tests_run=result.testsRun,
                         failures=len(result.failures), errors=len(result.errors),
                         skipped=len(result.skipped), events=EVENTS), ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    raise SystemExit(not result.wasSuccessful())
