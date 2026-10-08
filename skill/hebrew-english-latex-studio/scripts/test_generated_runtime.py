#!/usr/bin/env python3
"""Build generated English/custom and bilingual projects through the real pipeline.

Requires the full installed TeX/font/runtime dependencies and microtype. No build
gates are bypassed. Use --evidence-dir NEW_PATH to keep PDF, log, and source evidence;
otherwise all generated files live in an automatically removed temporary directory.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
sys.dont_write_bytecode = True
import fitz
from new_document import ROOT, create

EVIDENCE_DIR: Path | None = None


class GeneratedRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if EVIDENCE_DIR is None:
            cls.temporary = tempfile.TemporaryDirectory(prefix='hll-generated-runtime-')
            cls.root = Path(cls.temporary.name)
        else:
            cls.root = EVIDENCE_DIR.expanduser().absolute()
            cls.root.mkdir(parents=True, exist_ok=False)
            cls.temporary = None

    @classmethod
    def tearDownClass(cls):
        if cls.temporary is not None:
            cls.temporary.cleanup()

    def build(self, name: str, kind: str, **choices):
        project = self.root / name
        create(kind, project, **choices)
        # test_all owns a different project root for its shipped fixtures.
        # Each generated project is self-contained: bind its actual boundary
        # explicitly rather than inheriting the harness's unrelated boundary.
        env = dict(os.environ, HEBREW_LATEX_SKILL_ROOT=str(ROOT),
                   HEBREW_LATEX_PROJECT_ROOT=str(project))
        result = subprocess.run(['bash', str(project / 'build.sh')], env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, timeout=240)
        (project / 'runtime-output.txt').write_text(result.stdout, encoding='utf-8')
        self.assertEqual(result.returncode, 0, f'{name}:\n{result.stdout[-14000:]}')
        self.assertTrue((project / 'main.pdf').is_file())
        with fitz.open(project / 'main.pdf') as pdf:
            self.assertGreater(len(pdf), 0)
            text = '\n'.join(page.get_text() for page in pdf)
            metadata = pdf.metadata
            if EVIDENCE_DIR is not None:
                for index, page in enumerate(pdf):
                    page.get_pixmap(matrix=fitz.Matrix(1.25, 1.25)).save(project / f'page-{index+1}.png')
        return project, text, metadata

    def test_english_custom_design_and_extra_package(self):
        project, text, metadata = self.build('english-custom', 'general', language='english',
                                             theme='custom', packages=['microtype'])
        self.assertIn('Proposed agenda', text)
        self.assertIn('Next step', text)
        self.assertNotRegex(text, '[\u0590-\u05ff]')
        self.assertEqual(metadata['title'], 'Proposed agenda')
        source = (project / 'main.tex').read_text()
        self.assertIn(r'\input{theme.tex}', source)
        self.assertIn(r'\usepackage{microtype}', source)
        self.assertNotIn(r'\begin{englishprose}', source)
        manifest = json.loads((project / 'project.json').read_text())
        self.assertEqual(manifest['theme'], 'custom')

    def test_bilingual_data_references_and_multiple_table_destinations(self):
        _, text, _ = self.build('bilingual-data', 'data-report', language='bilingual', main_language='hebrew')
        self.assertIn('Data report', text)
        self.assertIn('Example records', text)
        self.assertRegex(text, '[\u0590-\u05ff]')
        # The two independent tables must preserve every numeric record.
        for record in ('001', '002', '003', '004', '005', '006'):
            self.assertEqual(len(re.findall(rf'(?<!\d){record}(?!\d)', text)), 2)
        self.assertNotIn('??', text)

    def test_bilingual_deferred_notes_keep_both_languages_and_keys(self):
        project, text, _ = self.build('bilingual-notes', 'annotated-note', language='bilingual', main_language='english')
        self.assertIn('Comparing values', text)
        self.assertIn('The two values refer to the same quantity', text)
        self.assertRegex(text, '[\u0590-\u05ff]')
        source = (project / 'main.tex').read_text()
        self.assertIn(r'\DeclareDocNote[english]{scope}', source)
        self.assertIn(r'\DeclareDocNote[hebrew]{secondary-scope}', source)
        self.assertNotIn('??', text)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--evidence-dir', type=Path)
    args, remaining = parser.parse_known_args()
    EVIDENCE_DIR = args.evidence_dir
    unittest.main(argv=[sys.argv[0], *remaining], verbosity=2)
