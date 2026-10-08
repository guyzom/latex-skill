#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Original project code; scope and terms: ../LICENSING.md.
"""Offline controls for opt-in font acquisition; never require network in QA."""
from __future__ import annotations
import io
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile
from unittest.mock import patch
sys.dont_write_bytecode = True
import download_fonts as downloader

class DownloadTests(unittest.TestCase):
    def setUp(self):
        import hashlib
        self.fonts = {name:b'font:' + name.encode() for name in
                      ['FrankRuhlLibre-Regular.ttf','Heebo-Bold.ttf','DejaVuSansMono.ttf']}
        self.pins = {name:hashlib.sha256(data).hexdigest() for name,data in self.fonts.items()}
        self.tmp = tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.stage = Path(self.tmp.name)

    def archive(self, duplicate=False, wrong_path=False):
        out=io.BytesIO()
        with zipfile.ZipFile(out,'w') as z:
            name='DejaVuSansMono.ttf';path=('wrong/' if wrong_path else 'dejavu-fonts-ttf-2.37/ttf/')+name
            z.writestr(path,self.fonts[name])
            if duplicate:
                import warnings
                with warnings.catch_warnings():
                    warnings.simplefilter('ignore');z.writestr(path,self.fonts[name])
            z.writestr('../../unrelated.txt',b'never extract')
        return out.getvalue()

    def fetcher(self,url):
        return self.archive() if url==downloader.DEJAVU else self.fonts[url.rsplit('/',1)[-1]]

    def test_verified_files_only_and_archive_paths_not_extracted(self):
        with patch.object(downloader,'pins',return_value=self.pins):downloader.stage(self.stage,self.fetcher)
        self.assertEqual({p.name for p in self.stage.iterdir()},set(self.fonts))
        for name,data in self.fonts.items():self.assertEqual((self.stage/name).read_bytes(),data)

    def test_changed_upstream_bytes_rejected(self):
        with patch.object(downloader,'pins',return_value=self.pins):
            with self.assertRaisesRegex(ValueError,'SHA-256'):downloader.stage(self.stage,lambda u:b'changed')
        self.assertEqual(list(self.stage.iterdir()),[])

    def test_duplicate_and_wrong_archive_members_rejected(self):
        for duplicate,wrong in [(True,False),(False,True)]:
            with self.subTest(duplicate=duplicate,wrong=wrong):
                with patch.object(downloader,'pins',return_value=self.pins):
                    with self.assertRaisesRegex(ValueError,'upstream member'):
                        downloader.stage(self.stage,lambda u:self.archive(duplicate,wrong) if u==downloader.DEJAVU else self.fetcher(u))

    def test_bad_archive_is_not_silently_accepted(self):
        with patch.object(downloader,'pins',return_value=self.pins):
            with self.assertRaises(zipfile.BadZipFile):
                downloader.stage(self.stage,lambda u:b'not a zip' if u==downloader.DEJAVU else self.fetcher(u))

    def test_timed_out_install_reports_failure_without_rollback_claim(self):
        destination = self.stage / 'installed'
        def timed_out_install(target, source, archive):
            # A font-cache timeout can happen after verified fonts were written.
            target.mkdir()
            (target / 'verified-marker.txt').write_text('already published')
            raise subprocess.TimeoutExpired('fc-cache', 60)
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(sys, 'argv', ['download_fonts.py', '--destination', str(destination)]), \
             patch.object(downloader, 'stage'), \
             patch.object(downloader, 'install', side_effect=timed_out_install), \
             redirect_stdout(stdout), redirect_stderr(stderr):
            self.assertEqual(downloader.main(), 1)
        self.assertEqual(stdout.getvalue(), '')
        self.assertIn('font download or installation failed', stderr.getvalue())
        self.assertIn('timed out after 60 seconds', stderr.getvalue())
        self.assertNotIn('no unverified font published', stderr.getvalue())
        self.assertEqual((destination / 'verified-marker.txt').read_text(), 'already published')

if __name__=='__main__':unittest.main()
