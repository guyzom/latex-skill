#!/usr/bin/env python3
"""Fast contract tests for honest and atomically published environment snapshots."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.dont_write_bytecode = True
import environment_report as er


class EnvironmentReportTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='hllpdf-env-test-');self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.asset=self.root/'dependency';self.asset.write_bytes(b'fixture')
        self.which=patch.object(er.shutil,'which',return_value=str(self.asset));self.which.start();self.addCleanup(self.which.stop)
        self.qa=patch.object(er,'_qa_versions',return_value=(er.EXPECTED_QA.copy(),[]));self.qa.start();self.addCleanup(self.qa.stop)
        def run(argv):
            return str(self.asset) if len(argv)==2 and not argv[1].startswith('-') else 'Synthetic version 1\nSecond line'
        self.run=patch.object(er,'run_command',side_effect=run);self.run.start();self.addCleanup(self.run.stop)

    def test_complete_snapshot_has_explicit_scope_and_files(self):
        r=er.collect();self.assertEqual(r['status'],'complete');self.assertTrue(r['fonts_verified'])
        self.assertEqual(len(r['tex_files']),len(er.REQUIRED_TEX_FILES)+len(er.EXTRA_TEX_FILES))
        self.assertEqual(r['scope'],'required-build-dependencies')

    def test_snapshot_is_repeatable_without_clock_or_host_name(self):
        a=er.collect();b=er.collect();self.assertEqual(a,b)
        text=json.dumps(a);self.assertNotIn('hostname',text);self.assertNotIn(str(self.root),text)
        self.assertNotIn('environ',a)

    def test_one_byte_dependency_change_changes_fingerprint(self):
        a=er.collect();self.asset.write_bytes(b'fixture!');b=er.collect()
        self.assertNotEqual(a['fingerprint_sha256'],b['fingerprint_sha256'])

    def test_hash_recomputes_from_exact_fields(self):
        r=er.collect();h=r.pop('fingerprint_sha256')
        self.assertEqual(h,hashlib.sha256(json.dumps(r,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest())

    def test_missing_command_is_not_complete(self):
        with patch.object(er.shutil,'which',return_value=None): r=er.collect()
        self.assertEqual(r['status'],'incomplete');self.assertEqual(len(r['commands']),0)
        self.assertTrue(any('lualatex' in e for e in r['errors']))

    def test_version_mismatch_is_not_complete(self):
        with patch.object(er,'_qa_versions',return_value=({'PyMuPDF':'0','fonttools':'0'},[])):
            r=er.collect()
        self.assertEqual(r['status'],'incomplete');self.assertEqual(len(r['errors']),2)

    def test_missing_tex_dependency_is_named(self):
        with patch.object(er,'run_command',return_value='/not/a/real/dependency'):
            r=er.collect()
        self.assertEqual(r['status'],'incomplete');self.assertTrue(any('babel.sty' in e for e in r['errors']))

    def test_timeout_is_recorded_not_silently_accepted(self):
        with patch.object(er,'run_command',side_effect=subprocess.TimeoutExpired('fixture',20)):
            r=er.collect()
        self.assertEqual(r['status'],'incomplete');self.assertFalse(r['fonts_verified'])
        self.assertTrue(any('TimeoutExpired' in e for e in r['errors']))

    def test_publish_replaces_symlink_not_its_target(self):
        target=self.root/'original';target.write_text('KEEP');dest=self.root/'out.json';dest.symlink_to(target)
        er.publish(er.collect(),dest)
        self.assertFalse(dest.is_symlink());self.assertEqual(target.read_text(),'KEEP')
        self.assertEqual(json.loads(dest.read_text())['status'],'complete')

    def test_failed_publication_leaves_prior_bytes(self):
        dest=self.root/'out.json';dest.write_text('PREVIOUS')
        with patch.object(er,'atomic_replace',side_effect=OSError('injected failure')):
            with self.assertRaises(OSError): er.publish(er.collect(),dest)
        self.assertEqual(dest.read_text(),'PREVIOUS')


if __name__=='__main__': unittest.main(verbosity=2)
