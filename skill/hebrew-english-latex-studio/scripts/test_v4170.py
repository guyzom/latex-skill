#!/usr/bin/env python3
"""Local publication controls and continuity of both v4.16.0 regression paths."""
from __future__ import annotations

import os
import json
import re
import subprocess
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
from package_skill import publish_archive
from test_v4160 import BIDI_CASES

ROOT = Path(__file__).resolve().parent.parent


class PublicationTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix='hllpdf-publication-')
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.temp = self.root / 'stage.skill'
        self.temp.write_bytes(b'new controlled test bytes')
        self.output = self.root / 'release.skill'

    def test_new_output_is_exact(self):
        publish_archive(self.temp, self.output)
        self.assertEqual(self.output.read_bytes(), self.temp.read_bytes())

    def test_identical_retry_keeps_inode_and_timestamp(self):
        self.output.write_bytes(self.temp.read_bytes())
        previous = self.output.stat()
        publish_archive(self.temp, self.output)
        current = self.output.stat()
        self.assertEqual((previous.st_ino, previous.st_mtime_ns), (current.st_ino, current.st_mtime_ns))

    def test_different_bytes_leave_previous_output_untouched(self):
        self.output.write_bytes(b'previous release')
        with self.assertRaisesRegex(ValueError, 'previous output preserved'):
            publish_archive(self.temp, self.output)
        self.assertEqual(self.output.read_bytes(), b'previous release')

    def test_empty_existing_file_is_not_disposable(self):
        self.output.touch()
        with self.assertRaises(ValueError): publish_archive(self.temp, self.output)
        self.assertEqual(self.output.stat().st_size, 0)

    def test_explicit_replace_is_available(self):
        self.output.write_bytes(b'previous release')
        expected = self.temp.read_bytes()
        publish_archive(self.temp, self.output, replace_existing=True)
        self.assertEqual(self.output.read_bytes(), expected)

    def test_symlink_not_followed_even_to_identical_bytes(self):
        self.output.symlink_to(self.temp)
        with self.assertRaises(ValueError): publish_archive(self.temp, self.output)
        self.assertTrue(self.output.is_symlink())
        self.assertEqual(self.temp.read_bytes(), b'new controlled test bytes')

    def test_dangling_symlink_preserved(self):
        target = self.root / 'missing'
        self.output.symlink_to(target)
        with self.assertRaises(ValueError): publish_archive(self.temp, self.output)
        self.assertTrue(self.output.is_symlink()); self.assertFalse(target.exists())

    def test_explicit_symlink_replacement_preserves_target(self):
        target = self.root / 'prior'; target.write_bytes(b'prior target')
        self.output.symlink_to(target)
        publish_archive(self.temp, self.output, replace_existing=True)
        self.assertFalse(self.output.is_symlink())
        self.assertEqual(target.read_bytes(), b'prior target')

    def test_directory_cannot_be_published_over(self):
        self.output.mkdir()
        with self.assertRaises(ValueError): publish_archive(self.temp, self.output)
        self.assertTrue(self.output.is_dir())

    def test_late_arriving_output_is_preserved(self):
        real_link = os.link
        def arrives_first(source, destination):
            destination.write_bytes(b'late controlled writer')
            return real_link(source, destination)
        with patch('package_skill.os.link', side_effect=arrives_first):
            with self.assertRaises(ValueError): publish_archive(self.temp, self.output)
        self.assertEqual(self.output.read_bytes(), b'late controlled writer')

    def test_unsupported_filesystem_fails_without_rename_fallback(self):
        with patch('package_skill.os.link', side_effect=OSError('controlled unsupported filesystem')):
            with self.assertRaises(OSError): publish_archive(self.temp, self.output)
        self.assertFalse(self.output.exists())

    def test_source_stage_survives_a_conflict(self):
        self.output.write_bytes(b'old')
        with self.assertRaises(ValueError): publish_archive(self.temp, self.output)
        self.assertEqual(self.temp.read_bytes(), b'new controlled test bytes')


class ContinuityTests(unittest.TestCase):
    def test_measured_contents_and_geometry_share_the_release(self):
        core = (ROOT/'assets/preamble.tex').read_text(encoding='utf-8')
        self.assertIn('% <hllpdf:measured-toc>', core)
        self.assertIn(r'\hllpdf@tocmeasure{#1}', core)
        for relative in ['scripts/pdf_geometry.py', 'scripts/test_v4160.py',
                         'scripts/test_toc_layout.py', 'scripts/toc_layout_probe.py']:
            self.assertTrue((ROOT/relative).is_file(), relative)

    def test_earlier_language_controls_are_retained(self):
        self.assertEqual(len(BIDI_CASES), 24)
        names = {name for name, _, _ in BIDI_CASES}
        self.assertIn('spaced_en_token', names)
        self.assertIn('multiline_closing_tail', names)

    def test_harness_runs_both_paths_and_publication_checks(self):
        harness = (ROOT/'scripts/test_all.sh').read_text(encoding='utf-8')
        for invocation in ['python3 scripts/test_v4160.py', 'python3 scripts/test_toc_layout.py ',
                           'python3 scripts/test_toc_layout.py --runtime', 'python3 scripts/test_v4170.py']:
            self.assertIn(invocation, harness)


def golden_fragment_result(harness: str, *, positive_code: int = 1,
                           negative_code: int = 0, negative_flag: bool = False) -> dict:
    """Run the actual golden-gate shell block with a controlled local checker.

    Only the T1 block is selected; no TeX engine or later full-suite work runs.
    The stub is confined to a temporary directory and never modifies the real
    checker. This checks process status, not the checker's scientific content.
    """
    first = harness.index('echo "═══ T1: lint golden tests ═══"')
    last = harness.index('echo "═══ T1b:', first)
    fragment = harness[first:last]
    with tempfile.TemporaryDirectory(prefix='hllpdf-golden-exit-') as temp:
        root = Path(temp); (root/'scripts').mkdir(); (root/'tests').mkdir()
        (root/'tests/expected_flags.txt').write_text(
            (ROOT/'tests/expected_flags.txt').read_text(encoding='utf-8'), encoding='utf-8')
        # JSON data in a Python literal avoids interpolating any shell content.
        settings = repr(dict(positive=positive_code, negative=negative_code, flag=negative_flag))
        stub = """import pathlib, sys
settings = SETTINGS
if 'positives' in sys.argv[1]:
    for flag in pathlib.Path('tests/expected_flags.txt').read_text().splitlines():
        print('tests/lint_positives.tex:1: [' + flag + '] controlled finding')
    sys.exit(settings['positive'])
if settings['flag']:
    print('tests/lint_negatives.tex:1: [CONTROLLED] unexpected finding')
sys.exit(settings['negative'])
""".replace('SETTINGS', settings)
        (root/'scripts/check_bidi_figures.py').write_text(stub, encoding='utf-8')
        functions = """PASS=0; FAIL=0
ok() { PASS=$((PASS+1)); }
bad() { FAIL=$((FAIL+1)); }
"""
        command = functions + fragment + '\nprintf "RESULT %s %s\\n" "$PASS" "$FAIL"\n'
        proc = subprocess.run(['bash', '-c', command], cwd=root, text=True,
                              capture_output=True, timeout=20)
        if proc.returncode:
            raise RuntimeError(proc.stdout + proc.stderr)
        match = re.search(r'RESULT (\d+) (\d+)', proc.stdout)
        if not match: raise RuntimeError('golden-gate test did not report counts')
        return {'passed': int(match[1]), 'failed': int(match[2]), 'returncode': proc.returncode}


class GoldenExitTests(unittest.TestCase):
    def run_gate(self, **settings):
        harness = (ROOT/'scripts/test_all.sh').read_text(encoding='utf-8')
        return golden_fragment_result(harness, **settings)

    def test_finding_one_clean_zero_is_the_only_success_pair(self):
        # v4.19.0: T1 emits one `ok` per golden flag, plus the exactly-N floor
        # and the silent-on-negatives check. The literal 48 here was 46 flags
        # + 2 and broke the moment a 47th flag landed, so derive it from the
        # golden file instead of re-pinning a constant per release.
        flags = [l for l in (ROOT / 'tests/expected_flags.txt')
                 .read_text(encoding='utf-8').splitlines() if l.strip()]
        self.assertEqual(self.run_gate(),
                         {'passed': len(flags) + 2, 'failed': 0, 'returncode': 0})

    def test_positive_crash_after_all_flags_is_rejected(self):
        self.assertGreater(self.run_gate(positive_code=2)['failed'], 0)

    def test_positive_zero_with_expected_flags_is_rejected(self):
        self.assertGreater(self.run_gate(positive_code=0)['failed'], 0)

    def test_negative_silent_tooling_error_is_rejected(self):
        self.assertEqual(self.run_gate(negative_code=2)['failed'], 1)

    def test_negative_silent_finding_exit_is_rejected(self):
        self.assertEqual(self.run_gate(negative_code=1)['failed'], 1)

    def test_negative_printed_finding_with_exit_zero_is_rejected(self):
        self.assertEqual(self.run_gate(negative_flag=True)['failed'], 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
