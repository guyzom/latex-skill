#!/usr/bin/env python3
"""Direct source controls for heading expressions and numbering depth."""
from __future__ import annotations
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
sys.dont_write_bytecode = True
from heading_source import label_findings, split_math_findings
ROOT = Path(__file__).resolve().parent.parent

DEEP = r'\subsubsection{כותרת עמוקה}\label{sec:deep}'
HOOK = r'\def\lakitsecnumdepth{3}\input{preamble.tex}'
BAD = r'\section{שער \texorpdfstring{$c^n$-$Z$}{c\textasciicircum n-Z}}'
GOOD = BAD.replace('$c^n$-$Z$', '$c^n-Z$')

DEPTH_CASES = [
 ('default_deep', DEEP, ['LABEL-ON-UNNUMBERED-HEADING']),
 ('declared_hook', HOOK+DEEP, []),
 ('spaced_hook', r'\def \lakitsecnumdepth { + 3 }\input {preamble.tex}'+DEEP, []),
 ('hook_after_core_is_not_counter', r'\input{preamble.tex}\def\lakitsecnumdepth{3}'+DEEP, ['LABEL-ON-UNNUMBERED-HEADING']),
 ('direct_counter', r'\setcounter{secnumdepth}{3}'+DEEP, []),
 ('setcounter_global', r'{\setcounter{secnumdepth}{3}}'+DEEP, []),
 ('addcounter_global', r'{\addtocounter{secnumdepth}{1}}'+DEEP, []),
 ('lower_later', HOOK+DEEP+r'\setcounter{secnumdepth}{2}'+DEEP, ['LABEL-ON-UNNUMBERED-HEADING']),
 ('raise_later_not_retroactive', DEEP+r'\setcounter{secnumdepth}{3}'+DEEP, ['LABEL-ON-UNNUMBERED-HEADING']),
 ('hook_scope', r'{\def\lakitsecnumdepth{3}}\input{preamble.tex}'+DEEP, ['LABEL-ON-UNNUMBERED-HEADING']),
 ('global_hook_scope', r'{\gdef\lakitsecnumdepth{3}}\input{preamble.tex}'+DEEP, []),
 ('renewcommand_hook', r'\renewcommand{\lakitsecnumdepth}{3}\input{preamble.tex}'+DEEP, []),
 ('unexecuted_definition', r'\newcommand{\later}{\setcounter{secnumdepth}{3}}'+DEEP, ['LABEL-ON-UNNUMBERED-HEADING']),
 ('unexecuted_primitive', r'\def\later{\setcounter{secnumdepth}{3}}'+DEEP, ['LABEL-ON-UNNUMBERED-HEADING']),
 ('verbatim_setting', '\\begin{verbatim}\n\\setcounter{secnumdepth}{3}\n\\end{verbatim}\n'+DEEP, ['LABEL-ON-UNNUMBERED-HEADING']),
 ('inline_literal_setting', r'\verb|\setcounter{secnumdepth}{3}|'+DEEP, ['LABEL-ON-UNNUMBERED-HEADING']),
 ('comment_setting', '% \\setcounter{secnumdepth}{3}\n'+DEEP, ['LABEL-ON-UNNUMBERED-HEADING']),
 ('starred_deep', HOOK+DEEP.replace('subsubsection{','subsubsection*{'), ['LABEL-ON-UNNUMBERED-HEADING']),
 ('starred_shallow_policy_unchanged', r'\section*{מבוא}\label{sec:intro}', []),
 # v4.19.0: an explicit lowering makes the shallow heading unnumbered, but the
 # anchor only becomes damage when something PRINTS its number. Measured under
 # secnumdepth=-2: \ref gave the empty string, \pageref gave the page and
 # \nameref the title. Four collections in the repository anchor 203 chapters
 # this way on purpose (216 \pageref uses), so the class is pinned by USE.
 ('lowered_shallow_number_ref', r'\setcounter{secnumdepth}{0}\section{מבוא}\label{sec:intro} ראה \ref{sec:intro}.', ['LABEL-ON-UNNUMBERED-HEADING']),
 ('lowered_shallow_autoref', r'\setcounter{secnumdepth}{0}\section{מבוא}\label{sec:intro} ראה \autoref{sec:intro}.', ['LABEL-ON-UNNUMBERED-HEADING']),
 ('lowered_shallow_pageref_only', r'\setcounter{secnumdepth}{0}\section{מבוא}\label{sec:intro} בעמוד \pageref{sec:intro}.', []),
 ('lowered_shallow_nameref_only', r'\setcounter{secnumdepth}{0}\section{מבוא}\label{sec:intro} ראה \nameref{sec:intro}.', []),
 ('lowered_shallow_unreferenced', r'\setcounter{secnumdepth}{0}\section{מבוא}\label{sec:intro}', []),
 ('lowered_shallow_other_key_ref', r'\setcounter{secnumdepth}{0}\section{מבוא}\label{sec:intro} ראה \ref{sec:other}.', []),
 ('deep_label_still_fires_unreferenced', r'\setcounter{secnumdepth}{0}'+DEEP, ['LABEL-ON-UNNUMBERED-HEADING']),
 ('paragraph_depth4', r'\setcounter{secnumdepth}{4}\paragraph{כותרת}\label{sec:p}', []),
 ('subparagraph_depth5', r'\setcounter{secnumdepth}{5}\subparagraph{כותרת}\label{sec:sp}', []),
 ('multiline_nested_heading', '\\setcounter{secnumdepth}{3}\n\\subsubsection[קצר]{כותרת\nעם \\textbf{הדגשה}}\n% comment\n\\label{sec:d}', []),
 ('depth2_nested_heading', '\\subsubsection{כותרת\nעם \\textbf{הדגשה}}\n% comment\n\\label{sec:d}', ['LABEL-ON-UNNUMBERED-HEADING']),
 ('unknown_value_not_silently_numbered', r'\setcounter{secnumdepth}{\customdepth}'+DEEP, ['HEADING-DEPTH-UNRESOLVED']),
 ('unknown_then_explicit', r'\setcounter{secnumdepth}{\customdepth}\setcounter{secnumdepth}{3}'+DEEP, []),
 ('deferred_setting_unknown', r'\AtBeginDocument{\setcounter{secnumdepth}{3}}'+DEEP, ['HEADING-DEPTH-UNRESOLVED']),
 ('theme_override', HOOK+r'\input{clean_theme.tex}'+DEEP, ['LABEL-ON-UNNUMBERED-HEADING']),
 ('provide_preserves_existing', r'\def\lakitsecnumdepth{2}\providecommand{\lakitsecnumdepth}{3}\input{preamble.tex}'+DEEP, ['LABEL-ON-UNNUMBERED-HEADING']),
 ('provide_initial', r'\providecommand{\lakitsecnumdepth}{3}\input{preamble.tex}'+DEEP, []),
 ('provide_initial_scope', r'{\providecommand{\lakitsecnumdepth}{3}}\providecommand{\lakitsecnumdepth}{3}\input{preamble.tex}'+DEEP, []),
 ('provide_core_default', r'\input{preamble.tex}\providecommand{\lakitsecnumdepth}{3}\setcounter{secnumdepth}{\lakitsecnumdepth}'+DEEP, ['LABEL-ON-UNNUMBERED-HEADING']),
 ('conditional_unresolved', r'\iftrue\setcounter{secnumdepth}{3}\else\setcounter{secnumdepth}{2}\fi'+DEEP, ['HEADING-DEPTH-UNRESOLVED']),
 ('no_label', r'\subsubsection{כותרת}', []),
]
MATH_CASES = [
 ('split_typeset_arg', BAD, ['SPLIT-MATH-IN-HEADING']),
 ('single_math_unit', GOOD, []),
 ('multiline', BAD.replace('$-$', '$\n-\n$'), ['SPLIT-MATH-IN-HEADING']),
 ('raw_inline', r'\section{שער $c^n$-$Z$}', ['SPLIT-MATH-IN-HEADING']),
 ('paren_inline', r'\section{שער \(c^n\)-\(Z\)}', ['SPLIT-MATH-IN-HEADING']),
 ('english_island_whole', BAD.replace('$c^n$-$Z$',r'\en{$c^n$-$Z$}'), []),
 ('foreignlanguage_whole', BAD.replace('$c^n$-$Z$',r'\foreignlanguage{english}{$c^n$-$Z$}'), []),
 ('prose_conjunction', r'\section{בין $x$ ובין $y$}', []),
 ('prose_after_heading', r'\section{כותרת} טקסט $x$-$y$', []),
 ('typeset_correct_metadata_ignored', r'\section{שער \texorpdfstring{$c^n-Z$}{$c^n$-$Z$}}', []),
 ('comment', '% '+BAD, []),
 ('inline_literal', r'\verb|'+BAD+'|', []),
 ('literal_percent_not_comment', r'\verb|50%| '+BAD, ['SPLIT-MATH-IN-HEADING']),
 ('listing_literal', '\\begin{lstlisting}\n'+BAD+'\n\\end{lstlisting}', []),
 ('macro_definition_only', r'\newcommand{\heading}{'+BAD+'}', []),
 ('primitive_definition_only', r'\def\heading{'+BAD+'}', []),
 ('english_base', r'\begin{englishprose}'+BAD+r'\end{englishprose}', []),
 ('english_then_hebrew', r'\begin{englishprose}'+BAD+r'\end{englishprose}'+BAD, ['SPLIT-MATH-IN-HEADING']),
 ('optional_heading', r'\section[שער $c^n$-$Z$]{שער תקין}', ['SPLIT-MATH-IN-HEADING']),
 ('formatting', r'\section{שער \textbf{$c^n$-$Z$}}', ['SPLIT-MATH-IN-HEADING']),
 ('separate_pdf_wrappers', r'\section{שער \texorpdfstring{$c^n$}{c\textasciicircum n}-\texorpdfstring{$Z$}{Z}}', ['SPLIT-MATH-IN-HEADING']),
]
class SourceTests(unittest.TestCase):
    def test_completed_literal_forms_preserve_later_known_findings(self):
        prefixes = [r'\verb{literal{', r'\verb*{literal{',
                    r'\verb[ordinary[', r'\lstinline{{literal}',
                    r'\lstinline*literal*',
                    r'\lstinline[basicstyle={\ttfamily},morekeywords={a]b}]!literal!',
                    '\\lstinline[language=Python,% ] is a comment\ncolumns=fullflexible]|literal|']
        for prefix in prefixes:
            with self.subTest(prefix=prefix):
                raw = prefix + '\n' + BAD + '\n' + DEEP
                maths, labels = split_math_findings(raw), label_findings(raw)
                self.assertEqual([row[1] for row in maths], ['SPLIT-MATH-IN-HEADING'])
                self.assertEqual([row[1] for row in labels], ['LABEL-ON-UNNUMBERED-HEADING'])
                self.assertEqual(maths[0][0], prefix.count('\n') + 2)
                self.assertEqual(labels[0][0], prefix.count('\n') + 3)

    def test_incomplete_literal_never_exempts_following_heading(self):
        for prefix in [r'\verb|unclosed', r'\verb{unclosed',
                       r'\lstinline|unclosed', r'\lstinline{unclosed',
                       r'\lstinline[language=Python', r'\begin{verbatim}']:
            with self.subTest(prefix=prefix):
                self.assertEqual([row[1] for row in split_math_findings(prefix+'\n'+BAD)],
                                 ['SPLIT-MATH-IN-HEADING'])
                self.assertEqual([row[1] for row in label_findings(prefix+'\n'+DEEP)],
                                 ['LABEL-ON-UNNUMBERED-HEADING'])

    def test_command_decoys_inside_completed_literal_remain_exempt(self):
        for prefix in [r'\verb|'+BAD+' '+DEEP+'|',
                       r'\verb*|'+BAD+' '+DEEP+'|',
                       r'\lstinline[basicstyle={\ttfamily}]|'+BAD+' '+DEEP+'|']:
            with self.subTest(prefix=prefix):
                self.assertEqual(split_math_findings(prefix), [])
                self.assertEqual(label_findings(prefix), [])

def add_cases(cases, analyze, prefix):
    for name, raw, expected in cases:
        def test(self, raw=raw, expected=expected):
            self.assertEqual([flag for _, flag, _ in analyze(raw)], expected)
        setattr(SourceTests, 'test_'+prefix+'_'+name, test)
add_cases(DEPTH_CASES, label_findings, 'depth')
add_cases(MATH_CASES, split_math_findings, 'math')

class IntegrationTests(unittest.TestCase):
    def invoke(self, script, raw):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'main.tex'; p.write_text(raw,encoding='utf-8')
            return subprocess.run([sys.executable,str(ROOT/'scripts'/script),str(p)],capture_output=True,text=True,timeout=30)
    def test_new_math_rule_is_wired_into_real_hazard_gate(self):
        p=self.invoke('check_source_hazards.py',BAD)
        self.assertEqual(p.returncode,1,p.stdout+p.stderr)
        self.assertIn('[SPLIT-MATH-IN-HEADING]',p.stdout)
    def test_correct_math_passes_real_hazard_gate(self):
        p=self.invoke('check_source_hazards.py',GOOD)
        self.assertEqual(p.returncode,0,p.stdout+p.stderr)
    def test_inline_literal_percent_does_not_blind_new_rule(self):
        p=self.invoke('check_source_hazards.py',r'\verb|50%| '+BAD)
        self.assertEqual(p.returncode,1,p.stdout+p.stderr)
        self.assertIn('[SPLIT-MATH-IN-HEADING]',p.stdout)
    def test_valid_brace_verb_cannot_blind_live_gate_findings(self):
        prefix = '\\verb{literal{\n'
        for script, source, flag in [
            ('check_source_hazards.py', BAD, 'SPLIT-MATH-IN-HEADING'),
            ('check_bidi_figures.py', DEEP, 'LABEL-ON-UNNUMBERED-HEADING')]:
            with self.subTest(script=script):
                result = self.invoke(script, prefix+source)
                self.assertEqual(result.returncode, 1, result.stdout+result.stderr)
                self.assertIn(':2: ['+flag+']', result.stdout)
    def test_deep_fix_reaches_real_bidi_gate(self):
        p=self.invoke('check_bidi_figures.py',HOOK+DEEP)
        self.assertEqual(p.returncode,0,p.stdout+p.stderr)
    def test_lowered_depth_reaches_real_bidi_gate(self):
        p=self.invoke('check_bidi_figures.py',r'\setcounter{secnumdepth}{2}'+DEEP)
        self.assertEqual(p.returncode,1,p.stdout+p.stderr)
        self.assertIn('[LABEL-ON-UNNUMBERED-HEADING]',p.stdout)
    def test_dependency_is_required_by_build_preflight(self):
        self.assertIn('heading_source.py',(ROOT/'scripts/build.sh').read_text())
    def test_shipped_math_example_no_longer_teaches_split_expression(self):
        text=(ROOT/'assets/example_math.tex').read_text()
        self.assertIn('$c^n-Z$',text)
        self.assertNotIn('$c^n$-$Z$',text)
        self.assertEqual(split_math_findings(text),[])
    def test_short_code_is_explicitly_atomic_not_all_codeboxes(self):
        example=(ROOT/'assets/example_boxes.tex').read_text()
        self.assertIn(r'\begin{codebox}[nobreak=true,frametitle={\code{parser.py}}]',example)
        core=(ROOT/'assets/preamble.tex').read_text()
        code=core[core.index(r'\definecolor{cSlate}') : core.index(r'\makeatother',core.index(r'\definecolor{cSlate}'))]
        self.assertNotIn('nobreak=true',code)

if __name__=='__main__': unittest.main(verbosity=2)
