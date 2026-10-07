#!/usr/bin/env python3
"""Lexical-order controls: literal data must neither trigger nor hide math findings."""
from __future__ import annotations
import contextlib
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.dont_write_bytecode = True
import check_source_hazards as h
ROOT = Path(__file__).resolve().parent.parent


def flags(raw: str) -> list:
    return h.bare_command_findings(Path('case.tex'), h.mask_source(raw))


class LiteralMaskTests(unittest.TestCase):
    def test_01_verb_literals(self):
        for source in [r'\verb|$sqrt$|', r'\verb+$frac$+', r'\verb!$quad$!',
                       r'\verb*|$sqrt$|', r'\verb{$sqrt${', r'\verb|\(frac\)|']:
            with self.subTest(source=source):
                self.assertEqual(flags(source), [])

    def test_02_listing_literals_and_options(self):
        for source in [r'\lstinline|$sqrt$|', r'\lstinline{$sqrt$}',
                       r'\lstinline*$sqrt$*', r'\lstinline[language=Python]!$sqrt$!',
                       r'\lstinline[basicstyle={\ttfamily},morekeywords={a]b}]|$sqrt$|',
                       '\\lstinline[language=Python, % ] not a terminator\ncolumns=fullflexible]|$sqrt$|']:
            with self.subTest(source=source):
                self.assertEqual(flags(source), [])

    def test_03_live_math_after_percent(self):
        for command in [r'\verb|%|', r'\verb*|%|', r'\lstinline|%|', r'\lstinline{%}']:
            with self.subTest(command=command):
                self.assertEqual(len(flags(command + r' $sqrt{x}$')), 1)

    def test_04_live_math_after_dollar(self):
        for command in [r'\verb|$|', r'\verb*|$|', r'\lstinline|$|', r'\lstinline{$}']:
            with self.subTest(command=command):
                self.assertEqual(len(flags(command + r' $sqrt{x}$')), 1)

    def test_05_both_sides_remain_checked(self):
        findings = flags(r'$frac{a}{b}$ \verb|$sqrt$ %| $quad + x$')
        self.assertEqual(len(findings), 2)
        self.assertIn("'frac'", findings[0].message)
        self.assertIn("'quad'", findings[1].message)

    def test_06_corrected_live_math_stays_clean(self):
        self.assertEqual(flags(r'\verb|%| $\sqrt{x}$ \lstinline|$| $\frac{x}{2}$'), [])

    def test_07_true_comment_ignores_literal_decoys(self):
        raw = '% \\verb|%| $sqrt{x}$\n$frac{x}{y}$'
        self.assertEqual([f.line for f in flags(raw)], [2])

    def test_08_control_symbol_parity(self):
        self.assertEqual(len(flags(r'\% $sqrt{x}$')), 1)
        self.assertEqual(flags(r'\\% $sqrt{x}$'), [])
        self.assertEqual(len(flags(r'\\\% $sqrt{x}$')), 1)
        self.assertEqual(flags(r'\\\\% $sqrt{x}$'), [])

    def test_09_comment_after_completed_literal(self):
        self.assertEqual(flags(r'\verb|%| % $sqrt{x}$'), [])

    def test_10_literal_markers_in_literal_are_data(self):
        self.assertEqual(len(flags(r'\verb|\begin{verbatim}| $sqrt{x}$')), 1)
        self.assertEqual(len(flags(r'\lstinline|\verb+$frac$+| $sqrt{x}$')), 1)

    def test_11_completed_block_forms(self):
        for env in h.LITERAL_ENVS:
            for separator in ['', ' ', '\n', '% ignored\n']:
                raw = '\\begin' + separator + '{' + env + '}\n% $sqrt$ \\verb!x!\n\\end{' + env + '}\n$frac{x}{y}$'
                with self.subTest(env=env,separator=separator):
                    hits = flags(raw)
                    self.assertEqual(len(hits), 1)
                    self.assertIn("'frac'",hits[0].message)

    def test_12_block_percent_does_not_hide_terminator(self):
        raw = '\\begin{verbatim}\n%\\end{verbatim}\n$sqrt{x}$'
        self.assertEqual(len(flags(raw)), 1)

    def test_13_non_prose_tikz_policy_preserved(self):
        self.assertEqual(len(flags('\\begin{tikzpicture}\n$sqrt$\n\\end{tikzpicture}\n$frac{x}{y}$')), 1)

    def test_14_alltt_is_not_a_blanket_exemption(self):
        self.assertEqual(len(flags(r'\begin{alltt}\(sqrt{x}\)\end{alltt}')), 1)

    def test_15_unclosed_inline_cannot_swallow_later_lines(self):
        self.assertEqual([f.line for f in flags('\\verb|oops\n$sqrt{x}$\n|')], [2])
        self.assertEqual([f.line for f in flags('\\lstinline|oops\n$sqrt{x}$\n|')], [2])

    def test_16_unclosed_block_cannot_hide_rest_of_file(self):
        self.assertEqual([f.line for f in flags('\\begin{verbatim}\n$sqrt{x}$')], [2])

    def test_17_length_newlines_and_live_offsets_preserved(self):
        raw = 'עברית\r\n\\verb|$sqrt$ %| $frac{x}{y}$\r\n%\n'
        masked = h.mask_source(raw)
        self.assertEqual(len(masked), len(raw))
        for token in ('\r','\n'):
            self.assertEqual([i for i,c in enumerate(raw) if c==token],
                             [i for i,c in enumerate(masked) if c==token])
        self.assertEqual(masked.index('frac'),raw.index('frac'))
        self.assertEqual([f.line for f in flags(raw)], [2])

    def test_18_backslash_does_not_escape_literal_delimiter(self):
        self.assertEqual(len(flags(r'\verb|hello\| $sqrt{x}$')), 1)
        self.assertEqual(len(flags(r'\lstinline|hello\| $sqrt{x}$')), 1)

    def test_19_lstinline_brace_is_not_nested_in_raw_source(self):
        self.assertEqual(len(flags(r'\lstinline{{literal} $sqrt{x}$')), 1)

    def test_20_verb_brace_is_same_character_delimiter(self):
        self.assertEqual(len(flags(r'\verb{data}more{ $sqrt{x}$')), 1)

    def test_21_no_short_inline_or_custom_alias_assumptions(self):
        self.assertEqual(len(flags(r'|$sqrt$|')), 1)
        self.assertEqual(len(flags(r'\mycode|$sqrt$|')), 1)

    def test_22_mutation_of_real_inline_handler_recreates_false_positive(self):
        source = r'\verb|$sqrt$|'
        self.assertEqual(flags(source), [])
        with patch.object(h, '_inline_end', return_value=None):
            self.assertEqual(len(flags(source)), 1)

    def test_23_mutation_of_real_handler_recreates_missed_live_math(self):
        for source in [r'\verb|%| $sqrt{x}$',r'\verb|$| $sqrt{x}$']:
            self.assertEqual(len(flags(source)), 1)
            with patch.object(h, '_inline_end', return_value=None):
                self.assertEqual(flags(source), [])

    def test_24_needspace_literal_is_not_an_invocation(self):
        source = '\\begin{multicols}{2}\n\\verb|\\Needspace{2cm}|\n\\end{multicols}'
        self.assertEqual(h.needspace_findings(Path('case.tex'),h.mask_source(source),set()), [])
        active = source.replace(r'\verb|\Needspace{2cm}|',r'\Needspace{2cm}')
        self.assertEqual(len(h.needspace_findings(Path('case.tex'),h.mask_source(active),set())),1)

    def test_25_idempotent_mask(self):
        raw = 'Text \\verb|$sqrt$ %| $frac{x}{y}$\n% comment\n'
        once = h.mask_source(raw)
        self.assertEqual(h.mask_source(once),once)


    def test_31_tikz_comment_closer_does_not_end_picture(self):
        source = '\\begin{tikzpicture}\n% terminator: \\end{tikzpicture}\n' + r'\node[align=center]{Line\\$x$}; \pgfmathparse{sqrt(4)}' + '\n\\end{tikzpicture}\n$y+1$'
        self.assertEqual(flags(source), [])
        self.assertEqual(len(flags(source + ' $frac{a}{b}$')), 1)

    def test_32_normal_nonprose_closer_and_literal_decoy(self):
        for source in [
            r'\begin{tikzpicture} \verb|\end{tikzpicture}| $sqrt$ \end {tikzpicture} $y$',
            '\\begin{tikzpicture}\n\\\\% \\end{tikzpicture}\n$sqrt$\n\\end% whitespace\n{tikzpicture}\n$y$',
            r'\begin{tikzpicture} \begin{tikzpicture} $sqrt$ \end{tikzpicture} $frac$ \end{tikzpicture} $y$']:
            with self.subTest(source=source):
                self.assertEqual(flags(source), [])
                self.assertEqual(len(flags(source + ' $quad$')), 1)

    def test_33_real_nonprose_handler_mutation_recreates_draft_regression(self):
        source = '\\begin{tikzpicture}\n% terminator: \\end{tikzpicture}\n' + r'\node[align=center]{Line\\$x$}; \pgfmathparse{sqrt(4)}' + '\n\\end{tikzpicture}\n$y+1$'
        self.assertEqual(flags(source), [])
        def naive(text, pos, env):
            marker = r'\end{' + env + '}'
            at = text.find(marker, pos)
            return at + len(marker) if at >= 0 else None
        with patch.object(h, '_nonprose_end', side_effect=naive):
            self.assertEqual(len(flags(source)), 1)


class CliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='hllpdf423-unit-')
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)

    def run_cli(self, source, *args):
        p=self.root/'main.tex';p.write_text(source,encoding='utf-8')
        return subprocess.run([sys.executable,str(ROOT/'scripts/check_source_hazards.py'),*args,str(p)],
                              text=True,capture_output=True,timeout=30)

    def test_26_clean_literal_returns_zero(self):
        result=self.run_cli(r'\verb|$sqrt$|')
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_27_live_error_returns_one_and_original_line(self):
        result=self.run_cli('\\verb|%|\n\\lstinline|$| $sqrt{x}$')
        self.assertEqual(result.returncode,1)
        self.assertIn('main.tex:2: [BARE-LATEX-COMMAND]',result.stdout)

    def test_28_missing_input_is_tool_error(self):
        result=subprocess.run([sys.executable,str(ROOT/'scripts/check_source_hazards.py'),str(self.root/'absent.tex')],
                              capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,2)
        self.assertNotIn('gate clean',result.stdout)

    def test_29_needspace_strict_mode(self):
        raw='\\begin{multicols}{2}\n\\verb|\\Needspace{1cm}|\n\\end{multicols}'
        self.assertEqual(self.run_cli(raw,'--strict-layout').returncode,0)
        self.assertEqual(self.run_cli(raw.replace(r'\verb|\Needspace{1cm}|',r'\Needspace{1cm}'),'--strict-layout').returncode,1)

    def test_30_later_file_and_line_retained(self):
        a=self.root/'literal.tex';a.write_text(r'\verb|%| $\sqrt{x}$')
        b=self.root/'live.tex';b.write_text('\n\\lstinline|$| $sqrt{x}$')
        result=subprocess.run([sys.executable,str(ROOT/'scripts/check_source_hazards.py'),str(a),str(b)],
                              capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,1)
        self.assertIn('live.tex:2:',result.stdout)
        self.assertNotIn('literal.tex:1:',result.stdout)

if __name__=='__main__': unittest.main(verbosity=2)
