#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Original project code; scope and terms: ../LICENSING.md.
"""Bounded character-table and safe harness-startup controls; no TeX execution."""
from __future__ import annotations
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent.parent
CODES = {'2013','2014','2026','2190','2192','2194','21D2','2212','221E','2260','2264','2265'}

class CharacterTable(unittest.TestCase):
    def test_01_only_declared_technical_codepoints_are_registered(self):
        text = (ROOT/'assets/preamble.tex').read_text(encoding='utf-8')
        match = re.search(r'% <hllpdf:listing-technical-symbols>\n(.*?)% </hllpdf:listing-technical-symbols>', text, re.S)
        self.assertIsNotNone(match)
        block = match[1]
        self.assertEqual(set(re.findall(r'\{"([0-9A-F]+)\}', block)), CODES)
        self.assertEqual(set(re.findall(r'\\catcode"([0-9A-F]+)=\\active', block)), CODES)
        self.assertIn(r'\lst@CCPut \lst@ProcessOther', block)
        self.assertIn(r'\lst@AddToHookAtTop{SelectCharTable}', block)
        self.assertIn(r'\lst@ifactivechars', block)
        self.assertNotIn(r'\global', block)
        self.assertNotIn(r'\literate', block)

    def test_02_original_smart_quote_contract_is_preserved(self):
        text = (ROOT/'assets/preamble.tex').read_text(encoding='utf-8')
        block = re.search(r'% <hllpdf:listing-smart-quotes>\n(.*?)% </hllpdf:listing-smart-quotes>', text, re.S)[1]
        self.assertEqual(set(re.findall(r'\{"([0-9A-F]+)\}', block)), {'2018','2019','201C','201D'})

class HarnessStartup(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='hllpdf430-start-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.scripts = self.root/'skill/scripts'; self.scripts.mkdir(parents=True)
        self.bin = self.root/'bin'; self.bin.mkdir()
        self.calls = self.root/'calls.txt'
        self.text = (ROOT/'scripts/test_all.sh').read_text(encoding='utf-8')
        (self.scripts/'test_all.sh').write_text(self.text, encoding='utf-8')
        (self.scripts/'doctor.py').write_text('import os,sys\nfrom pathlib import Path\nwith Path(os.environ["CALLS"]).open("a") as f: f.write("doctor:"+" ".join(sys.argv[1:])+"\\n")\nsys.exit(int(os.environ.get("DOCTOR_RC","0")))\n')
        (self.scripts/'clean_harness_artifacts.py').write_text('import os\nfrom pathlib import Path\nwith Path(os.environ["CALLS"]).open("a") as f: f.write("sweep\\n")\n')
        self.mock('mkdir', 'printf "mkdir:%s\\n" "$*" >> "$CALLS"\nexit 1\n')
        self.mock('rm', 'printf "rm:%s\\n" "$*" >> "$CALLS"\nexit 0\n')
        self.mock('mktemp', 'printf "allocator\\n" >> "$CALLS"\nprintf "%s" "${ALLOCATED:-}"\nexit "${ALLOCATOR_RC:-0}"\n')
        self.env = dict(os.environ, PATH=str(self.bin)+':'+os.environ['PATH'], CALLS=str(self.calls),
                        HEBREW_LATEX_FONT_DIR=str(self.root), FAST='0', DOCTOR_RC='0', ALLOCATOR_RC='0', ALLOCATED='')

    def mock(self, name, content):
        p=self.bin/name;p.write_text('#!/bin/sh\n'+content);p.chmod(0o755)

    def run_harness(self, **changes):
        self.env.update(changes)
        r = subprocess.run(['bash', str(self.scripts/'test_all.sh')], env=self.env,
                           cwd=self.root, text=True, capture_output=True, timeout=20)
        calls = self.calls.read_text() if self.calls.exists() else ''
        self.assertEqual(r.returncode, 2, r.stdout+r.stderr)
        self.assertNotIn('═══ T1:', r.stdout)
        return r, calls

    def test_03_invalid_fast_mode_is_not_silently_full(self):
        r,c = self.run_harness(FAST='yes')
        self.assertEqual(c,''); self.assertIn('FAST must be 0 or 1',r.stdout)

    def test_04_failed_full_preflight_runs_no_allocator_or_cleanup(self):
        r,c = self.run_harness(DOCTOR_RC='2')
        self.assertEqual(c,'doctor:\n')
        self.assertIn('no regression tests ran',r.stdout)

    def test_05_fast_checks_qa_without_requiring_live_tex(self):
        r,c = self.run_harness(FAST='1',DOCTOR_RC='2')
        self.assertEqual(c,'doctor:--qa-only\n')
        self.assertIn('no regression tests ran',r.stdout)

    def test_06_crashed_preflight_is_also_a_tooling_failure(self):
        r,c = self.run_harness(DOCTOR_RC='1')
        self.assertEqual(c,'doctor:\n')
        self.assertIn('no regression tests ran',r.stdout)

    def test_07_failed_allocator_discards_any_partial_path(self):
        r,c = self.run_harness(ALLOCATOR_RC='1',ALLOCATED=str(self.root))
        self.assertEqual(c,'doctor:\nallocator\n')
        self.assertIn('cannot create harness scratch directory',r.stdout)

    def test_08_empty_success_is_rejected_before_path_derivation(self):
        r,c = self.run_harness()
        self.assertEqual(c,'doctor:\nallocator\n')
        self.assertIn('no usable directory',r.stdout)

    def test_09_missing_directory_is_rejected(self):
        r,c = self.run_harness(ALLOCATED=str(self.root/'absent'))
        self.assertEqual(c,'doctor:\nallocator\n')
        self.assertIn('no usable directory',r.stdout)

    def test_10_regular_file_is_not_a_scratch_directory(self):
        f=self.root/'regular';f.write_text('preserve me')
        r,c = self.run_harness(ALLOCATED=str(f))
        self.assertEqual(c,'doctor:\nallocator\n')
        self.assertEqual(f.read_text(),'preserve me')

    def test_11_valid_space_path_reaches_only_its_private_cache(self):
        p=self.root/'scratch with spaces';p.mkdir()
        r,c = self.run_harness(ALLOCATED=str(p))
        self.assertIn('mkdir:'+str(p)+'/font-cache\n',c)
        self.assertNotIn('mkdir:/font-cache',c)
        self.assertIn('cannot create private harness font cache',r.stdout)
        self.assertIn('sweep\n',c)

    def test_12_allocator_mutation_reproduces_wrong_derived_root_path_safely(self):
        start='if [ -z "$HARNESS_TMP" ] || [ ! -d "$HARNESS_TMP" ]; then\n'
        old = self.text.index(start); end = self.text.index('\nfi\n',old)+4
        (self.scripts/'test_all.sh').write_text(self.text[:old]+self.text[end:])
        r,c = self.run_harness()
        # mkdir/rm are recording stubs. This test NEVER writes /font-cache.
        self.assertIn('mkdir:/font-cache\n',c)
        self.assertIn('sweep\n',c)

    def test_13_preflight_mutation_reproduces_work_after_failed_prerequisites(self):
        start=self.text.index('# Prerequisites are not regression results.')
        end=self.text.index('# Every harness run owns',start)
        (self.scripts/'test_all.sh').write_text(self.text[:start]+self.text[end:])
        r,c = self.run_harness(DOCTOR_RC='2',ALLOCATOR_RC='1')
        self.assertEqual(c,'allocator\n')
        self.assertNotIn('no regression tests ran',r.stdout)

if __name__ == '__main__':
    unittest.main(verbosity=2)
