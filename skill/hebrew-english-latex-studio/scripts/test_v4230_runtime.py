#!/usr/bin/env python3
"""Real LuaLaTeX controls for source-literal boundaries (no font redistribution).

HLLPDF_423_EVIDENCE_DIR retains new external sources/logs/PDFs; it must not exist.
The raw builds include deliberately wrong mathematics, not deliverable examples.
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
import fitz
from font_paths import font_dir
import check_runtime_fonts
ROOT = Path(__file__).resolve().parent.parent
HEADER = r'''\def\lakitdocumentclass{article}
\def\lakitclassoptions{11pt,a4paper}
\input{preamble.tex}
\hypersetup{pdftitle={בדיקת גבולות מקור},pdfauthor={Synthetic QA}}
\begin{document}
'''


def wrap(body: str) -> str:
    return HEADER + '\\begin{englishprose}\n' + body + '\n\\end{englishprose}\n\\end{document}\n'

SAFE_LINES = [
    r'\verb|$sqrt$|', r'\verb|%| $\sqrt{x}$', r'\verb|$| $\sqrt{x}$',
    r'\verb*|$sqrt$|', r'\verb{$sqrt${',
    r'\lstinline|$sqrt$|', r'\lstinline{$sqrt$}',r'\lstinline*$sqrt$*',
    r'\lstinline[language=Python]|$sqrt$|', r'\lstinline|%| $\sqrt{x}$',
    r'\lstinline|$| $\sqrt{x}$', r'\lstinline{{text} $\sqrt{x}$',
    r'\verb|hello\| $\sqrt{x}$',r'\lstinline|hello\| $\sqrt{x}$',
]
SAFE = wrap('\n\\par\\medskip\n'.join(SAFE_LINES) +
    '\n\\begin {verbatim}\n$sqrt$\n\\end{verbatim}\n'+
    '\n\\begin {lstlisting}\n$sqrt$\n\\end{lstlisting}\n')


TIKZ = wrap(r"""\begin{tikzpicture}
% A comment may name the terminator: \end{tikzpicture}
\node[draw,align=center] {Line\\$x$};
\pgfmathparse{sqrt(4)}\let\computedroot\pgfmathresult
\node[right] at (2,0) {\computedroot};
\end{tikzpicture}
\par
Live formula outside the picture: $y+1$.""")


def glyphs(pdf: Path) -> list[dict]:
    out=[]
    with fitz.open(pdf) as doc:
        for p in doc:
            for b in p.get_text('rawdict')['blocks']:
                for line in b.get('lines',[]):
                    chars=[(c['origin'][0],c['c']) for s in line['spans'] for c in s['chars']]
                    out.append({'page':p.number+1,'text':''.join(c for x,c in sorted(chars)),
                                'bbox':list(line['bbox'])})
    return out


class RuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        selected=os.environ.get('HLLPDF_423_EVIDENCE_DIR')
        if selected:
            cls.root=Path(selected).resolve()
            if cls.root==ROOT or ROOT in cls.root.parents:
                raise ValueError('Evidence must be outside the skill')
            cls.root.mkdir(parents=True,exist_ok=False)
        else:
            cls.temp=tempfile.TemporaryDirectory(prefix='hllpdf423-runtime-')
            cls.root=Path(cls.temp.name)
        cls.private=tempfile.TemporaryDirectory(prefix='hllpdf423-cache-')
        fonts=font_dir()
        cls.env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','SOURCE_DATE_EPOCH':'1700000000','TZ':'UTC',
                 'HEBREW_LATEX_FONT_DIR':str(fonts),'TTFONTS':str(fonts)+':','OSFONTDIR':str(fonts)+':',
                 'TEXMFCACHE':cls.private.name,'TEXMFVAR':cls.private.name}
        cls.env.pop('HEBREW_LATEX_PROJECT_ROOT',None)
        cls.sources={'safe':SAFE,
                     'bad-percent':wrap(r'\verb|%| $sqrt{x}$'),
                     'bad-dollar':wrap(r'\verb|$| $sqrt{x}$'),
                     'fixed':wrap(r'\verb|%| $\sqrt{x}$'), 'safe-tikz':TIKZ}
        cls.results={}
        for name,src in cls.sources.items():
            d=cls.root/name;d.mkdir();(d/'main.tex').write_text(src,encoding='utf-8')
            shutil.copyfile(ROOT/'assets/preamble.tex',d/'preamble.tex')
            for i in range(2):
                r=subprocess.run(['lualatex','--no-shell-escape','-halt-on-error','-interaction=nonstopmode',
                                  '-recorder','main.tex'],cwd=d,env=cls.env,capture_output=True,text=True,timeout=180)
                (d/f'raw-pass-{i+1}.log').write_text(r.stdout+r.stderr)
                if r.returncode: raise AssertionError(name+' failed raw compilation:\n'+r.stdout[-4000:])
            check=subprocess.run([sys.executable,str(ROOT/'scripts/check_source_hazards.py'),str(d/'main.tex')],
                                 capture_output=True,text=True,timeout=30)
            audit=check_runtime_fonts.audit(d/'main.log',fonts)
            cls.results[name]={'checker_exit':check.returncode,'checker_output':check.stdout+check.stderr,
                               'pdf_sha256':hashlib.sha256((d/'main.pdf').read_bytes()).hexdigest(),
                               'font_audit':audit,'glyph_lines':glyphs(d/'main.pdf')}
            (d/'source-gate.log').write_text(check.stdout+check.stderr)
        # A counted engine wrapper proves rejection happened before any engine
        # invocation. The prior PDF is different from the raw failing output.
        cls.private_bin=Path(cls.private.name)/'bin';cls.private_bin.mkdir()
        cls.counted=Path(cls.private.name)/'engine-calls.txt'
        wrapper=cls.private_bin/'lualatex'
        engine=shutil.which('lualatex')
        if not engine: raise RuntimeError('lualatex missing')
        wrapper.write_text('#!/usr/bin/env bash\nprintf "called\\n" >> "$HLLPDF_TEST_ENGINE_CALLS"\nexec '+
                          __import__('shlex').quote(engine)+' "$@"\n')
        wrapper.chmod(0o755)
        cls.managed={}
        for name in ['safe','bad-percent','bad-dollar','fixed','safe-tikz']:
            d=cls.root/name
            # Never present a raw bypass of a hard gate as a published build.
            shutil.copyfile(d/'main.pdf',d/'raw.pdf')
            (d/'main.pdf').unlink()
            if name.startswith('bad-'):
                shutil.copyfile(cls.root/'fixed'/'main.pdf',d/'main.pdf')
            prior=(d/'main.pdf').read_bytes() if (d/'main.pdf').exists() else None
            if cls.counted.exists():cls.counted.unlink()
            env={**cls.env,'PATH':str(cls.private_bin)+os.pathsep+cls.env['PATH'],
                 'HLLPDF_TEST_ENGINE_CALLS':str(cls.counted),'REPRO':'1'}
            r=subprocess.run(['bash',str(ROOT/'scripts/build.sh'),str(d/'main.tex')],env=env,
                             capture_output=True,text=True,timeout=300)
            (d/'managed.log').write_text(r.stdout+r.stderr)
            cls.managed[name]={'exit':r.returncode,'engine_calls':len(cls.counted.read_text().splitlines()) if cls.counted.exists() else 0,
                'gate_finding':'[BARE-LATEX-COMMAND]' in r.stdout,
                'prior_preserved':prior is not None and (d/'main.pdf').read_bytes()==prior,
                'raw_differs_from_prior':prior is not None and (d/'raw.pdf').read_bytes()!=prior,
                'output':r.stdout+r.stderr}
        (cls.root/'summary.json').write_text(json.dumps({'cases':cls.results,'managed':cls.managed},ensure_ascii=False,indent=2)+'\n')

    @classmethod
    def tearDownClass(cls):
        cls.private.cleanup()
        if hasattr(cls,'temp'):cls.temp.cleanup()

    def test_01_all_forms_compile_with_canonical_fonts(self):
        self.assertEqual(self.results['safe']['font_audit']['status'],'verified')
        self.assertEqual(self.results['safe']['checker_exit'],0)

    def test_02_literal_source_characters_remain_printed(self):
        text=''.join(row['text'] for row in self.results['safe']['glyph_lines'])
        self.assertGreaterEqual(text.count('$sqrt$'),8,text)
        self.assertIn('%',text)

    def test_03_bad_percent_is_flagged(self): self.assertEqual(self.results['bad-percent']['checker_exit'],1)
    def test_04_bad_dollar_is_flagged(self): self.assertEqual(self.results['bad-dollar']['checker_exit'],1)

    def test_05_mathematical_source_error_is_visible(self):
        for name in ['bad-percent','bad-dollar']:
            text=''.join(row['text'] for row in self.results[name]['glyph_lines']).replace(' ','')
            self.assertIn('sqrt',text)
        text=''.join(row['text'] for row in self.results['fixed']['glyph_lines']).replace(' ','')
        self.assertNotIn('sqrt',text)
        self.assertNotEqual(self.results['fixed']['pdf_sha256'],self.results['bad-percent']['pdf_sha256'])

    def test_06_safe_managed_build(self):
        r=self.managed['safe'];self.assertEqual(r['exit'],0,r['output']);self.assertGreaterEqual(r['engine_calls'],3)

    def test_07_fixed_managed_build(self):
        r=self.managed['fixed'];self.assertEqual(r['exit'],0,r['output']);self.assertGreaterEqual(r['engine_calls'],3)

    def test_08_bad_percent_stops_before_engine(self):
        r=self.managed['bad-percent'];self.assertEqual(r['exit'],1,r['output']);self.assertTrue(r['gate_finding']);self.assertEqual(r['engine_calls'],0)

    def test_09_bad_dollar_stops_before_engine(self):
        r=self.managed['bad-dollar'];self.assertEqual(r['exit'],1,r['output']);self.assertTrue(r['gate_finding']);self.assertEqual(r['engine_calls'],0)

    def test_10_distinct_prior_outputs_survive(self):
        for name in ['bad-percent','bad-dollar']:
            r=self.managed[name];self.assertTrue(r['raw_differs_from_prior']);self.assertTrue(r['prior_preserved'])


    def test_11_tikz_comment_marker_preserves_valid_managed_picture(self):
        row=self.results['safe-tikz']; managed=self.managed['safe-tikz']
        self.assertEqual(row['checker_exit'],0,row['checker_output'])
        self.assertEqual(row['font_audit']['status'],'verified')
        self.assertEqual(managed['exit'],0,managed['output'])
        self.assertGreaterEqual(managed['engine_calls'],3)
        printed=''.join(row['text'] for row in row['glyph_lines'])
        self.assertIn('Line',printed)
        self.assertIn('2.0',printed)

if __name__=='__main__': unittest.main(verbosity=2)
