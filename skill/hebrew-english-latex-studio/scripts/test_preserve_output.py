#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Original project code; scope and terms: ../LICENSING.md.
"""No-clobber recovery controls; these simulate the measured engine unlink."""
from __future__ import annotations
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.dont_write_bytecode = True
from preserve_output import recover, snapshot


class PreserveOutputTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='hllpdf-protect-')
        self.root = Path(self.tmp.name)
        self.target = self.root/'report.pdf'
        self.state = self.root/'private'
    def tearDown(self): self.tmp.cleanup()
    def save(self): snapshot(self.target,self.state)
    def restore(self): return recover(self.target,self.state)
    def seed(self): self.target.write_bytes(b'%PDF-previous\n'+bytes(range(256)))

    def test_absent_is_not_fabricated(self):
        self.save(); self.assertFalse(self.restore()); self.assertFalse(self.target.exists())
    def test_existing_is_not_rewritten(self):
        self.seed(); old=self.target.stat(); self.save(); self.assertFalse(self.restore())
        self.assertEqual(self.target.stat().st_ino,old.st_ino)
    def test_unlinked_file_is_recovered_exactly(self):
        self.seed(); self.target.chmod(0o640); old=self.target.read_bytes(); st=self.target.stat()
        self.save(); self.target.unlink(); self.assertTrue(self.restore())
        self.assertEqual(self.target.read_bytes(),old)
        self.assertEqual(stat.S_IMODE(self.target.stat().st_mode),0o640)
        self.assertEqual(self.target.stat().st_mtime_ns,st.st_mtime_ns)
        self.assertFalse(self.restore())
    def test_existing_concurrent_change_is_not_overwritten(self):
        self.seed(); self.save(); self.target.write_bytes(b'USER EDIT')
        self.assertFalse(self.restore()); self.assertEqual(self.target.read_bytes(),b'USER EDIT')
    def test_new_file_during_restore_is_not_clobbered(self):
        self.seed(); self.save(); self.target.unlink(); link=os.link
        def race(src,dest):
            self.target.write_bytes(b'CONCURRENT EDIT'); return link(src,dest)
        with patch('preserve_output.os.link',side_effect=race): self.assertFalse(self.restore())
        self.assertEqual(self.target.read_bytes(),b'CONCURRENT EDIT')
        self.assertEqual(list(self.root.glob('*.recover-*')),[])
    def test_symlink_is_restored_without_touching_referent(self):
        other=self.root/'real.pdf'; other.write_bytes(b'REAL'); self.target.symlink_to('real.pdf')
        self.save(); self.target.unlink(); self.assertTrue(self.restore())
        self.assertEqual(os.readlink(self.target),'real.pdf'); self.assertEqual(other.read_bytes(),b'REAL')
    def test_dangling_symlink_is_preserved(self):
        self.target.symlink_to('absent.pdf'); self.save(); self.target.unlink()
        self.assertTrue(self.restore()); self.assertEqual(os.readlink(self.target),'absent.pdf')
    def test_existing_dangling_symlink_is_not_clobbered(self):
        self.seed(); self.save(); self.target.unlink(); self.target.symlink_to('new-absent.pdf')
        self.assertFalse(self.restore()); self.assertEqual(os.readlink(self.target),'new-absent.pdf')
    def test_directory_target_is_rejected(self):
        self.target.mkdir()
        with self.assertRaises(ValueError): self.save()
    def test_corrupt_backup_does_not_restore_garbage(self):
        self.seed(); self.save(); self.target.unlink(); (self.state/'previous.bin').write_bytes(b'CORRUPT')
        with self.assertRaisesRegex(ValueError,'corrupt'): self.restore()
        self.assertFalse(self.target.exists())
    def test_wrong_target_cannot_use_snapshot(self):
        self.seed(); self.save()
        with self.assertRaisesRegex(ValueError,'does not match'): recover(self.root/'different.pdf',self.state)
    def test_boolean_schema_is_not_integer(self):
        self.save(); data=json.loads((self.state/'state.json').read_text()); data['schema']=True
        (self.state/'state.json').write_text(json.dumps(data))
        with self.assertRaises(ValueError): self.restore()
    def test_snapshot_will_not_overwrite_another_snapshot(self):
        self.seed(); self.save()
        with self.assertRaises(FileExistsError): self.save()
    def test_unicode_spaces_and_long_name(self):
        self.target=self.root/'מסמך הערות עברית 2026.pdf'; self.seed(); self.save(); self.target.unlink()
        self.assertTrue(self.restore()); self.assertTrue(self.target.read_bytes().startswith(b'%PDF'))


if __name__ == '__main__': unittest.main(verbosity=2)
