#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Original project code; scope and terms: ../LICENSING.md.
"""Runtime inventory and integration contracts (no LuaLaTeX process)."""
from __future__ import annotations
import hashlib,json,os,re,shutil,subprocess,sys,tempfile,unittest
from pathlib import Path
sys.dont_write_bytecode = True
import check_runtime_fonts as c
ROOT=Path(__file__).resolve().parent.parent

def frame(paths,unnamed=3):
    lines=['HLLFONT|BEGIN|1']
    for i,p in enumerate(paths,1):
        h=str(p).encode().hex();chunks=[h[j:j+48] for j in range(0,len(h),48)]
        lines.append(f'HLLFONT|FILE|{i}|{len(chunks)}')
        lines.extend('HLLFONT|HEX|'+x for x in chunks)
    return '\n'.join(lines+[f'HLLFONT|END|{len(paths)}|{unnamed}'])+'\n'

class Contracts(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.d=Path(self.tmp.name)
        self.root=c.font_dir();self.paths=[self.root/n for n in sorted(c.ANCHORS)]
        self.log=self.d/'main.log';self.log.write_text(frame(self.paths))
    def tearDown(self):self.tmp.cleanup()
    def bad(self,text):
        with self.assertRaises(c.InventoryError):c.parse_inventory(text)
    def test_01_unicode_and_long_path(self):
        p='/tmp/תיקיית גופנים עם רווחים/'+('x'*90)+'.ttf'
        self.assertEqual(c.parse_inventory(frame([p])),([p],3))
    def test_02_ignores_unrelated_log_lines(self):
        self.assertEqual(c.parse_inventory('noise\n'+frame(self.paths)+'noise\n')[0],list(map(str,self.paths)))
    def test_03_missing(self):self.bad('not an inventory')
    def test_04_truncated(self):self.bad(frame(self.paths).rsplit('HLLFONT|END',1)[0])
    def test_05_duplicate_frame(self):self.bad(frame(self.paths)*2)
    def test_06_bad_index(self):self.bad(frame(self.paths).replace('FILE|1|','FILE|2|',1))
    def test_07_odd_hex(self):self.bad('HLLFONT|BEGIN|1\nHLLFONT|FILE|1|1\nHLLFONT|HEX|a\nHLLFONT|END|1|0')
    def test_08_bad_utf8(self):self.bad('HLLFONT|BEGIN|1\nHLLFONT|FILE|1|1\nHLLFONT|HEX|ff\nHLLFONT|END|1|0')
    def test_09_control_in_name(self):self.bad(frame(['/tmp/a\nb']))
    def test_10_empty_inventory(self):self.bad('HLLFONT|BEGIN|1\nHLLFONT|END|0|2')
    def test_11_footer_count(self):self.bad(frame(self.paths).replace('END|3|','END|2|'))
    def test_12_duplicate_path(self):self.bad(frame([self.paths[0],self.paths[0]]))
    def test_13_verified_real_pins(self):
        r=c.audit(self.log,self.root);self.assertEqual(r['status'],'verified');self.assertEqual(len(r['verified']),3)
    def test_14_same_bytes_wrong_directory(self):
        alt=self.d/'fonts';alt.mkdir()
        for p in self.paths:shutil.copyfile(p,alt/p.name)
        self.log.write_text(frame([alt/p.name for p in self.paths]));r=c.audit(self.log,self.root)
        self.assertEqual(r['status'],'failed');self.assertTrue(any('runtime path' in e for e in r['errors']))
    def test_15_wrong_bytes(self):
        alt=self.d/'fonts';alt.mkdir()
        for p in self.paths:shutil.copyfile(p,alt/p.name)
        p=alt/self.paths[0].name;p.write_bytes(p.read_bytes()+b'x')
        self.log.write_text(frame([alt/p.name for p in self.paths]));r=c.audit(self.log,alt)
        self.assertTrue(any('SHA-256' in e for e in r['errors']))
    def test_16_relative_filename(self):
        self.log.write_text(frame([p.name for p in self.paths]));r=c.audit(self.log,self.root)
        self.assertTrue(any('absolute' in e for e in r['errors']))
    def test_17_missing_anchor(self):
        self.log.write_text(frame(self.paths[:2]));self.assertEqual(c.audit(self.log,self.root)['status'],'failed')
    def test_18_harf_duplicate_resources(self):
        self.log.write_text(frame(self.paths+['harfloaded:'+str(p) for p in self.paths]));r=c.audit(self.log,self.root)
        self.assertEqual(r['status'],'verified');self.assertEqual(len(r['verified']),3)
    def test_19_uncontrolled_is_explicit(self):
        self.log.write_text(frame(self.paths+['/tmp/custom.otf']));r=c.audit(self.log,self.root)
        self.assertEqual(r['status'],'verified');self.assertEqual(r['uncontrolled'],['/tmp/custom.otf'])
    def source_list(self,text):
        p=self.d/'source.tex';p.write_text(text);s=self.d/'sources.txt';s.write_text(str(p)+'\n');return s
    def test_20_noncore_not_verified(self):
        self.log.write_text('plain');r=c.audit(self.log,self.root,source_list=self.source_list('plain'))
        self.assertEqual(r['status'],'not-applicable');self.assertFalse(r['verified'])
    def test_21_renamed_old_core_requires_inventory(self):
        self.log.write_text('plain');r=c.audit(self.log,self.root,source_list=self.source_list(r'\def\hllpdfcoreloaded{1}'))
        self.assertEqual(r['status'],'failed')
    def cli(self,path):
        return subprocess.run([sys.executable,str(ROOT/'scripts/check_runtime_fonts.py'),str(path),'--json'],text=True,capture_output=True)
    def test_22_cli_verified(self):
        p=self.cli(self.log);self.assertEqual(p.returncode,0);self.assertEqual(json.loads(p.stdout)['status'],'verified')
    def test_23_cli_failure(self):
        self.log.write_text('missing');p=self.cli(self.log);self.assertEqual(p.returncode,1);self.assertIn('missing runtime',p.stdout)
    def test_24_cli_tool_error(self):
        p=self.cli(self.d/'absent.log');self.assertEqual(p.returncode,2);self.assertIn('checker error',p.stderr)
    def test_25_core_bindings(self):
        s=(ROOT/'assets/preamble.tex').read_text()
        self.assertEqual(s.count(r'Path={\hllpdffontdir}'),3)
        for name in ['DejaVuSerif.ttf','DejaVuSerif-Bold.ttf','DejaVuSans.ttf','DejaVuSans-Bold.ttf']:
            self.assertIn('hllpdf_font_dir .. "'+name+']:mode=node;"',s)
        self.assertIn('finish_pdffile',s);self.assertIn('HLLFONT|BEGIN|1',s)
    def test_26_build_gates_and_cache(self):
        s=(ROOT/'scripts/build.sh').read_text();h=(ROOT/'scripts/test_all.sh').read_text()
        self.assertGreaterEqual(s.count('"$SCRIPT_DIR/check_runtime_fonts.py" "$LOG"'),2)
        self.assertIn('export TEXMFCACHE="$BUILD_DIR/font-cache"',s);self.assertIn('export TEXMFVAR="$TEXMFCACHE"',s)
        self.assertLess(s.index('export TEXMFCACHE'),s.index('run_latex()'))
        self.assertIn('export TEXMFCACHE="$HARNESS_TMP/font-cache"',h)
        self.assertIn('test_v4220.py',h);self.assertIn('test_v4220_runtime.py',h)

if __name__=='__main__':unittest.main(verbosity=2)
