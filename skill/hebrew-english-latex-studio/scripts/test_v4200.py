#!/usr/bin/env python3
"""The union release must retain both branches and classify quote boundaries.

Synthetic source-only controls; these do not predict every possible line wrap.
"""
from __future__ import annotations
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.dont_write_bytecode = True
import check_bidi_figures as bidi
from heading_source import label_findings
from pdf_string_source import linebreak_findings
from render_review import render, verify
import fitz
ROOT = Path(__file__).resolve().parent.parent
FLAG = 'BREAKABLE-QUOTED-ISLAND'

QUOTES = [
 ('plain', r'נבדק \en{“alpha beta”} כאן.', 1),
 ('space', r'נבדק \en {“alpha beta”} כאן.', 1),
 ('newline-before-argument', 'נבדק \\en\n{“alpha beta”} כאן.', 1),
 ('several-spaces', r'נבדק \en    {“alpha beta”} כאן.', 1),
 ('code-space', r'נבדק \code {show "alpha beta"} כאן.', 1),
 ('foreign-spaces', r'נבדק \foreignlanguage {english} {“alpha beta”} כאן.', 1),
 ('comment-after-command', 'נבדק \\en% editor note\n{“alpha beta”} כאן.', 1),
 ('second-curly', r'נבדק \en{“OK” then “alpha beta”} כאן.', 1),
 ('third-curly', r'נבדק \en{“OK” then “YES” then “alpha beta”} כאן.', 1),
 ('second-ascii', r'נבדק \code{show "OK" then "alpha beta"} כאן.', 1),
 ('second-single', "נבדק \\code{show 'OK' then 'alpha beta'} כאן.", 1),
 ('second-curly-single', r'נבדק \en{‘OK’ then ‘alpha beta’} כאן.', 1),
 ('later-Tex-quotes', "נבדק \\en{``OK'' then ``alpha beta''} כאן.", 1),
 ('multiline-later-quote', 'נבדק \\en{“OK” then\n“alpha beta”} כאן.', 1),
 ('later-quote-after-box', r'נבדק \en{\mbox{“old phrase”} then “alpha beta”} כאן.', 1),
 ('later-quote-after-math', r'נבדק \en{$f\prime$ “alpha beta”} כאן.', 1),
 ('short', r'נבדק \en{“alpha”} כאן.', 0),
 ('two-short', r'נבדק \en{“alpha” and “beta”} כאן.', 0),
 ('unquoted', r'נבדק \en{alpha beta} כאן.', 0),
 ('empty-ascii', r'נבדק \code{show ""} כאן.', 0),
 ('possessives', r"נבדק \en{users' data and servers' logs} כאן.", 0),
 ('contraction', r"נבדק \en{don't repeat this} כאן.", 0),
 ('inner-box', r'נבדק \en{\mbox{“alpha beta”}} כאן.', 0),
 ('inner-box-spaces', r'נבדק \en {\mbox {“alpha beta”}} כאן.', 0),
 ('outer-box', r'נבדק \mbox{\en{“alpha beta”}} כאן.', 0),
 ('outer-box-spaces', r'נבדק \mbox {\en {“alpha beta”}} כאן.', 0),
 ('outer-hbox', r'נבדק \hbox {\en{“alpha beta”}} כאן.', 0),
 ('outer-box-on-prior-line', 'נבדק \\mbox{\n\\en{“alpha beta”}\n} כאן.', 0),
 ('whole-multiline-box', 'נבדק \\en {\\mbox{“alpha\nbeta”}} כאן.', 0),
 ('no-phantom-box-space', r'נבדק \en{“alpha\mbox{ beta }gamma”} כאן.', 0),
 ('no-phantom-math-space', r'נבדק \en{“alpha$ x $beta”} כאן.', 0),
 ('math-primes', r"נבדק \en{$f'(x)$ and $g'(y)$} כאן.", 0),
 ('literal-command', r'\verb|\en {“alpha beta”}|', 0),
 ('comment-only', '% \\en {“alpha beta”}', 0),
 ('table-row-exemption', r'\en {“alpha beta”} & תא \\', 0),
 ('center-exemption', r'\begin{center}\en {“alpha beta”}\end{center}', 0),
 ('display-exemption', r'\[\text{\en {“alpha beta”}}\]', 0),
 ('escaped-command-token', r'נבדק \\en{“alpha beta”} כאן.', 0),
 ('foreign-french-exemption', r'נבדק \foreignlanguage{french}{“alpha beta”} כאן.', 0),
 ('nested-island-no-duplicate', r'נבדק \en{before \code{show "alpha beta"}} כאן.', 1),
]

class QuoteCases(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='hllpdf-420-source-')
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'source.tex'

    def findings(self, text):
        self.path.write_text(text + '\n', encoding='utf-8')
        return [x for x in bidi.scan_file(str(self.path)) if x[1] == FLAG]

    def test_line_number_and_single_ownership(self):
        found = self.findings('% note\n\nנבדק \\en\n{“alpha beta”} כאן.')
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0][0], 3)

    def test_removing_whitespace_support_recreates_miss(self):
        with patch.object(bidi, '_ISLAND_OPEN',
                          r'\\(?:en|code)\{|\\foreignlanguage\s*\{english\}\s*\{'):
            self.assertEqual(self.findings(r'נבדק \en {“alpha beta”} כאן.'), [])
            self.assertEqual(len(self.findings(r'נבדק \en{“alpha beta”} כאן.')), 1)
        self.assertEqual(len(self.findings(r'נבדק \en {“alpha beta”} כאן.')), 1)

    def test_cli_bad_and_good_exit_codes(self):
        for source, code in [(r'נבדק \en {“alpha beta”} כאן.', 1),
                             (r'נבדק \en{\mbox{“alpha beta”}} כאן.', 0)]:
            self.path.write_text(source, encoding='utf-8')
            result = subprocess.run([sys.executable, str(ROOT/'scripts/check_bidi_figures.py'), str(self.path)],
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, code, result.stdout + result.stderr)
            self.assertEqual(result.stdout.count('[' + FLAG + ']'), code)


def add_quote_case(name, source, expected):
    def test(self):
        self.assertEqual(len(self.findings(source)), expected, source)
    test.__name__ = 'test_' + name.replace('-', '_')
    setattr(QuoteCases, test.__name__, test)
for args in QUOTES:
    add_quote_case(*args)


class ReferenceCases(unittest.TestCase):
    def test_number_readers_with_and_without_star(self):
        for macro in ('ref', 'autoref', 'Autoref', 'cref', 'Cref', 'eqref'):
            for spelling in (f'\\{macro}'+'{sec:off}', f'\\{macro}*'+'{sec:off}',
                             f'\\{macro} * '+'{sec:off}'):
                with self.subTest(spelling=spelling):
                    source = (r'\setcounter{secnumdepth}{-2}'+'\n'+
                              r'\section{כותרת}\label{sec:off}'+'\n'+spelling)
                    self.assertEqual([x[1] for x in label_findings(source)], ['LABEL-ON-UNNUMBERED-HEADING'])

    def test_page_name_unreferenced_and_other_key_anchors_still_allowed(self):
        for reference in ('', r'\pageref{sec:off}', r'\pageref*{sec:off}', r'\nameref{sec:off}',
                          r'\nameref*{sec:off}', r'\ref*{sec:other}'):
            with self.subTest(reference=reference):
                source = r'\setcounter{secnumdepth}{-2}\section{כותרת}\label{sec:off}' + reference
                self.assertEqual(label_findings(source), [])

    def test_deep_wrong_number_policy_retained(self):
        self.assertEqual([x[1] for x in label_findings(r'\subsubsection{כותרת}\label{sec:off}')],
                         ['LABEL-ON-UNNUMBERED-HEADING'])


class UnionContracts(unittest.TestCase):
    def test_bookmark_checker_and_quote_checker_both_live(self):
        source = r'\section{כותרת\\*[2pt]חדשה}'+'\n'+r'נבדק \en {“alpha beta”} כאן.'
        self.assertEqual([x[1] for x in linebreak_findings(source)], ['PDFSTRING-LINEBREAK-ARG'])
        self.assertIsNotNone(bidi._quoted_literal('“OK” then “alpha beta”'))
        flags = (ROOT/'tests/expected_flags.txt').read_text().splitlines()
        self.assertIn(FLAG, flags)
        self.assertIn('TOKEN-PUNCT-ADRIFT', flags)

    def test_two_backends_replay_and_legacy_core_retained(self):
        with tempfile.TemporaryDirectory(prefix='hllpdf-420-union-') as tmp:
            root = Path(tmp); pdf = root/'probe.pdf'
            with fitz.open() as doc:
                page = doc.new_page(width=120, height=100)
                page.insert_text((10,40),'union')
                doc.save(pdf)
            for backend in ('poppler', 'mupdf'):
                review = root/backend
                render(pdf, review, 72, backend=backend)
                self.assertEqual(verify(pdf, review/'review.json', require_attestations=False, rerender=True), [])
                self.assertEqual(json.loads((review/'review.json').read_text())['schema'], 3)
        core = (ROOT/'assets/preamble.tex').read_text()
        self.assertIn('% <hllpdf:measured-toc>', core)

if __name__ == '__main__':
    unittest.main(verbosity=2)
