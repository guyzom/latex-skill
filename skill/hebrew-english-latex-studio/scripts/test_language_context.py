#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Original project code; scope and terms: ../LICENSING.md.
"""Five-profile and nested-language source-gate regression controls."""
from __future__ import annotations

from contextlib import redirect_stdout
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import sys

sys.dont_write_bytecode = True

import check_bidi_figures as bidi
from language_context import LanguageContext, declared_config


def declared(profile='english', main=None):
    return ('\\def\\lakitlanguageprofile{' + profile + '}\n'
            + ('\\def\\lakitmainlanguage{' + main + '}\n' if main else ''))


class LanguageContextTests(unittest.TestCase):
    def setUp(self):
        # The complete harness confines its own project inputs to the skill
        # root. These disposable, separately rooted projects need their own
        # default boundary; retain fonts/toolchain and restore all env values.
        environment = patch.dict(os.environ)
        environment.start()
        self.addCleanup(environment.stop)
        os.environ.pop('HEBREW_LATEX_PROJECT_ROOT', None)

    def flags(self, source, **options):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'sample.tex'
            path.write_text(source, encoding='utf-8')
            return {kind for _, kind, _ in bidi.scan_file(str(path), **options)}

    def test_profile_mapping(self):
        for profile, main in [('hebrew', 'hebrew'), ('english', 'english'),
                              ('hebrew-with-english', 'hebrew'),
                              ('english-with-hebrew', 'english'),
                              ('bilingual', 'english'), ('bilingual', 'hebrew')]:
            with self.subTest(profile=profile, main=main):
                config = declared_config(declared(profile, main if profile == 'bilingual' else None))
                self.assertEqual(config.main, main)
                self.assertEqual(config.profile, profile)

    def test_legacy_default(self):
        self.assertEqual(declared_config('Text').main, 'hebrew')
        self.assertIn('QUOTES', self.flags("\\en{``quoted''}"))

    def test_explicit_hebrew_preserves_legacy_font(self):
        self.assertIn('QUOTES', self.flags(declared('hebrew') + "\\en{``quoted''}"))

    def test_assembled_provider_default_cannot_override_user(self):
        config = declared_config(declared() + r'\providecommand{\lakitlanguageprofile}{hebrew}')
        self.assertEqual(config.main, 'english')

    def test_unexecuted_macro_body_does_not_set_profile(self):
        config = declared_config(r'\newcommand{\example}{\def\lakitlanguageprofile{english}}')
        self.assertFalse(config.explicit)

    def test_comments_and_literal_bodies_do_not_set_profile(self):
        source = ('% ' + declared() + '\\begin{verbatim}\n' + declared()
                  + '\\end{verbatim}\nText')
        self.assertFalse(declared_config(source).explicit)

    def test_native_english_typography_and_bidi_are_clean(self):
        source = (declared() + "``Quoted text'' 1990--2000; 2020–2023.\n"
                  + r'\[x=\text{Specificity (TNR)}\]' + '\n'
                  + r'\texttt{A}$=1$ \en{A}, \en{B} \en{label}$=2$')
        self.assertEqual(self.flags(source), set())

    def test_english_across_lines_has_no_rtl_island_rule(self):
        source = declared() + '\\en{A},\n\\en{B}\n\\en{“two words”}\n'
        self.assertEqual(self.flags(source), set())

    def test_structural_and_math_failures_remain_in_english(self):
        source = (declared() + '\\section{Bad $x$}\n'
                  + r'\[x=\text{a_b} + \en{bad}\]' + '\n'
                  + r'$45°$')
        self.assertEqual(self.flags(source), {'MATH-IN-HEADING', 'TEXT-MATH-CARET',
                                               'LANG-RAW-IN-MATH', 'PUNCT-RAW-IN-MATH'})

    def test_raw_math_reference_contract_remains_in_english(self):
        self.assertEqual(self.flags(declared() + r'$\eqref{a}$'), {'MATH-WRAPPED-EQREF'})
        self.assertEqual(self.flags(declared() + r'$\text{\eqref{a}}$'), set())

    def test_hebrew_prose_in_english_still_detects_defects(self):
        source = (declared('english-with-hebrew') + '\\begin{hebrewprose}\n'
                  + "טקסט ``quoted'' 2020–2023.\n"
                  + r'\en{A}, \en{B}' + '\n\\end{hebrewprose}')
        self.assertEqual(self.flags(source), {'QUOTES', 'RANGE-SEP-BETWEEN-DIGITS',
                                               'ADJACENT-LTR-ISLANDS'})

    def test_hebrew_math_text_still_checked_in_english(self):
        source = declared() + r'\begin{hebrewprose}\[x=\text{Label (TNR)}\]\end{hebrewprose}'
        self.assertEqual(self.flags(source), {'TEXT-PARENS-IN-MATH'})

    def test_same_line_language_boundaries(self):
        source = declared('hebrew-with-english') + r'\begin{englishprose}2020–2023\end{englishprose} 2020–2023'
        self.assertEqual(self.flags(source), {'RANGE-SEP-BETWEEN-DIGITS'})

    def test_inner_hebrew_overrides_outer_english(self):
        source = declared() + r'\en{English \h{טווח 2020–2023} English}'
        context = LanguageContext(source)
        self.assertFalse(context.is_english(2, source.split('\n')[1].index('2020')))
        self.assertIn('RANGE-SEP-BETWEEN-DIGITS', self.flags(source))

    def test_supported_babel_optional_and_star_forms_both_directions(self):
        forms = [r'\foreignlanguage[]{LANG}{INNER 2020–2023}',
                 r'\foreignlanguage[date]{LANG}{INNER 2020–2023}',
                 r'\foreignlanguage*{LANG}{INNER 2020–2023}',
                 r'\begin{otherlanguage*}[]{LANG}INNER 2020–2023\end{otherlanguage*}',
                 r'\begin{otherlanguage*}[date]{LANG}INNER 2020–2023\end{otherlanguage*}']
        for main, secondary in [('english', 'hebrew'), ('hebrew', 'english')]:
            for form in forms:
                with self.subTest(main=main, form=form):
                    source = (declared(main + '-with-' + secondary)
                              + form.replace('LANG', secondary) + '\nRESTORED 2020–2023')
                    context = LanguageContext(source)
                    self.assertEqual(context.is_english(2, source.splitlines()[1].index('INNER')),
                                     secondary == 'english')
                    self.assertEqual(context.is_english(3), main == 'english')
                    with tempfile.TemporaryDirectory() as directory:
                        path = Path(directory) / 'babel.tex'
                        path.write_text(source, encoding='utf-8')
                        ranges = [line for line, kind, _ in bidi.scan_file(str(path))
                                  if kind == 'RANGE-SEP-BETWEEN-DIGITS']
                    self.assertEqual(ranges, [2 if secondary == 'hebrew' else 3])

    def test_babel_options_comments_and_nested_language_restore(self):
        source = declared('english-with-hebrew') + r'''\foreignlanguage% ignored star *
[date]{hebrew}{HEBREW \foreignlanguage% options comment
[]{english}{INNER} HEBREW_AGAIN}
ENGLISH_RESTORED'''
        context = LanguageContext(source)
        for word, expected in [('HEBREW', False), ('INNER', True),
                               ('HEBREW_AGAIN', False), ('ENGLISH_RESTORED', True)]:
            offset = context.text.index(word)
            self.assertEqual(context.is_english(*context.line_column(offset)), expected)

    def test_malformed_optional_language_arguments_do_not_exempt_tail(self):
        for form in [r'\foreignlanguage[date{english}{unclosed',
                     r'\foreignlanguage[]{english}{unclosed',
                     r'\begin{otherlanguage*}[date{english}']:
            with self.subTest(form=form):
                source = declared('hebrew-with-english') + form + '\nHEBREW 2020–2023'
                self.assertFalse(LanguageContext(source).is_english(3))
                self.assertIn('RANGE-SEP-BETWEEN-DIGITS', self.flags(source))

    def test_babel_syntax_in_definitions_and_literals_is_data(self):
        source = declared('hebrew-with-english') + r'''\newcommand{\example}{\foreignlanguage[]{english}{DATA}}
\verb|\foreignlanguage*{english}{DATA}|
\begin{verbatim}
\begin{otherlanguage*}[]{english}
\end{verbatim}
HEBREW 2020–2023'''
        self.assertFalse(LanguageContext(source).is_english(7))
        self.assertIn('RANGE-SEP-BETWEEN-DIGITS', self.flags(source))

    def test_valid_tex_literal_delimiters_preserve_live_language_and_scope_end(self):
        forms = [r'\verb{$sqrt${', r'\verb*{$sqrt${',
                 r'\lstinline{{text} $\sqrt{x}$', r'\lstinline[language=Python]{{text}',
                 r'\lstinline*$sqrt$*', r'\verb|hello\|', r'\lstinline|hello\|',
                 r'\verb{%{', r'\lstinline{%}']
        for form in forms:
            with self.subTest(form=form):
                source = (declared('hebrew-with-english') + '\\begin{englishprose}\n'
                          + form + '\nENGLISH 2020–2023\n\\end{englishprose}\n'
                          + 'HEBREW 2020–2023')
                context = LanguageContext(source)
                self.assertFalse(context.boundary_errors)
                self.assertTrue(context.is_english(4))
                self.assertFalse(context.is_english(6))
                with tempfile.TemporaryDirectory() as directory:
                    path = Path(directory) / 'literal.tex'
                    path.write_text(source, encoding='utf-8')
                    ranges = [line for line, kind, _ in bidi.scan_file(str(path))
                              if kind == 'RANGE-SEP-BETWEEN-DIGITS']
                self.assertEqual(ranges, [6])

    def test_profile_declarations_after_valid_brace_literals_remain_live(self):
        for form in [r'\verb{\def\lakitlanguageprofile{',
                     r'\lstinline{{text}', r'\verb{%{']:
            with self.subTest(form=form):
                config = declared_config(form + '\n' + declared('english-with-hebrew'))
                self.assertEqual(config.profile, 'english-with-hebrew')
                self.assertTrue(config.explicit)

    def test_existing_v423_safe_literal_fixture_has_no_cross_file_scope_error(self):
        from test_v4230_runtime import SAFE
        context = LanguageContext(SAFE)
        self.assertFalse(context.boundary_errors)
        self.assertFalse(context.exit_in_document)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            main = root / 'main.tex'
            main.write_text(SAFE, encoding='utf-8')
            (root / 'preamble.tex').write_text('% Literal source context fixture')
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(bidi.main(['bidi', str(main)]), 0, output.getvalue())

    def test_live_include_after_supported_literal_uses_both_callsite_locales(self):
        forms = [r'\verb{$sqrt${', r'\verb*{$sqrt${',
                 r'\lstinline{{text}', r'\lstinline[language=Python]{{text}',
                 r'\lstinline*$sqrt$*', r'\verb|hello\|', r'\lstinline|hello\|',
                 r'\verb{%{', r'\lstinline{%}']
        for main, local in [('hebrew', 'english'), ('english', 'hebrew')]:
            for form in forms:
                with self.subTest(main=main, form=form):
                    body = ('\\begin{' + local + 'prose}' + form
                            + r'\input{leaf}' + '\\end{' + local + 'prose}')
                    code, output = self.project_check(main+'-with-'+local, body,
                                                      {'leaf.tex': 'Range 2020–2023.'})
                    self.assertEqual(code, int(local == 'hebrew'), output)
                    self.assertNotIn('LANGUAGE-CONTEXT-UNRESOLVED', output)
                    if local == 'hebrew':
                        self.assertIn('PROJECT/leaf.tex:1: [RANGE-SEP-BETWEEN-DIGITS]', output)

    def test_completed_inline_literal_cannot_hide_live_legacy_list(self):
        forms = [r'\verb{literal{', r'\verb*{literal{', r'\lstinline{{text}',
                 r'\lstinline[language=Python]{{text}', r'\lstinline*literal*',
                 r'\verb|hello\|', r'\lstinline|hello\|', r'\verb{%{',
                 r'\lstinline{%}']
        for form in forms:
            with self.subTest(form=form):
                source = ('\\begin{otherlanguage}{english}\n' + form
                          + ' \\begin{itemize}\n\\item A\n\\end{itemize}\n'
                          + '\\end{otherlanguage}')
                self.assertEqual(self.flags(source), {'LIST-IN-LTR-ISLAND'})

    def test_inline_literal_detection_consumes_real_control_symbols(self):
        for command in ('verb', 'lstinline'):
            for count in (1, 2, 3, 4):
                with self.subTest(command=command, backslashes=count):
                    source = 'טקסט ' + '\\' * count + command + '|literal|'
                    self.assertEqual('VERB-IN-RTL-PROSE' in self.flags(source),
                                     bool(count % 2))
        source = r'טקסט \verbatimword|literal|'
        self.assertNotIn('VERB-IN-RTL-PROSE', self.flags(source))

    def test_inline_literal_rtl_detector_preserves_known_code_arguments(self):
        for command in ('code', 'codeline', 'texttt', 'url', 'path', 'nolinkurl'):
            for body in (r'\string\verb|literal|', '\n' + r'\string\verb|literal|' + '\n'):
                with self.subTest(command=command, body=body):
                    source = 'טקסט \\' + command + '{' + body + '} עברית'
                    self.assertNotIn('VERB-IN-RTL-PROSE', self.flags(source))
        self.assertIn('VERB-IN-RTL-PROSE', self.flags(
            r'טקסט \code{\string\verb|literal|} \verb|active|'))

    def test_incomplete_inline_literal_does_not_mask_live_structure(self):
        source = ('\\begin{otherlanguage}{english}\n'
                  + r'\verb|unclosed \begin{itemize}'
                  + '\n\\item A\n\\end{itemize}\n\\end{otherlanguage}')
        self.assertIn('LIST-IN-LTR-ISLAND', self.flags(source))
        self.assertEqual(bidi._blank_inline_literals(r'\verb|unclosed'),
                         r'\verb|unclosed')

    def test_english_inline_coordinates_use_common_literal_comment_mask(self):
        source = (r'\verb{%{ \en{English label} עברית' + '\n'
                  + '\\begin \n{verbatim}\n'
                  + r'\en{literal example}' + '\n\\end{verbatim}\n'
                  + r'\en{Live label} עברית')
        ranges = bidi._english_inline_ranges(source.split('\n'))
        first = source.split('\n')[0].index(r'\en{')
        self.assertEqual(ranges[1], [(first, first + len(r'\en{English label}'))])
        self.assertNotIn(4, ranges)
        self.assertEqual(ranges[6], [(0, len(r'\en{Live label}'))])

    def test_entry_locale_preserves_frozen_document_font_configuration(self):
        config = declared_config(declared('english-with-hebrew'))
        context = LanguageContext(r'\providecommand{\lakitlanguageprofile}{hebrew}'
                                  '\nHEBREW 2020–2023', entry_language='hebrew',
                                  document_config=config)
        self.assertIs(context.config, config)
        self.assertTrue(context.config.native_english_font)
        self.assertFalse(context.is_english(2))
        self.assertEqual(context.exit_language, 'hebrew')
        with self.assertRaisesRegex(ValueError, 'entry_language'):
            LanguageContext('Text', entry_language='')

    def test_include_callback_uses_executable_tokens_and_reports_exit_locale(self):
        calls = []
        def include(offset, command, language, in_document):
            calls.append((command, language, in_document))
            return offset + len(r'\input{part}'), 'hebrew'
        source = (declared() + r'\newcommand{\example}{\input{part}}'
                  + '\n' + r'\verb|\input{part}|'
                  + '\n' + r'\begin{document}{\input{part} INNER} RESTORED\end{document}')
        context = LanguageContext(source, include_callback=include)
        self.assertEqual(calls, [('input', 'english', True)])
        line = source.splitlines()[3]
        self.assertFalse(context.is_english(4, line.index('INNER')))
        self.assertTrue(context.is_english(4, line.index('RESTORED')))
        self.assertEqual(context.exit_language, 'english')
        self.assertTrue(context.has_document)

    def test_nested_blocks_restore_the_previous_language(self):
        source = (declared() + '\\begin{hebrewprose}\nעברית\n'
                  + '\\begin{englishprose}\nEnglish\n\\end{englishprose}\n'
                  + 'עברית\n\\end{hebrewprose}\nEnglish')
        ctx = LanguageContext(source)
        self.assertFalse(ctx.is_english(3))
        self.assertTrue(ctx.is_english(5))
        self.assertFalse(ctx.is_english(7))
        self.assertTrue(ctx.is_english(9))

    def test_group_scoped_selectlanguage(self):
        ctx = LanguageContext(declared() + '{\\selectlanguage{hebrew}עברית}\nEnglish')
        self.assertFalse(ctx.is_english(2, 25))
        self.assertTrue(ctx.is_english(3))

    def test_primitive_groups_restore_both_languages_and_gate_context(self):
        for begin, end in [('begingroup', 'endgroup'), ('bgroup', 'egroup')]:
            for main, secondary in [('hebrew', 'english'), ('english', 'hebrew')]:
                with self.subTest(begin=begin, main=main):
                    profile = 'hebrew-with-english' if main == 'hebrew' else 'english-with-hebrew'
                    source = (declared(profile) + '\\' + begin + '\n'
                              + '\\selectlanguage{' + secondary + '}\n'
                              + 'INNER 2020–2023\n\\' + end + '\nRESTORED 2020–2023')
                    ctx = LanguageContext(source)
                    self.assertEqual(ctx.is_english(4), secondary == 'english')
                    self.assertEqual(ctx.is_english(6), main == 'english')
                    with tempfile.TemporaryDirectory() as directory:
                        path = Path(directory) / 'scoped.tex'
                        path.write_text(source, encoding='utf-8')
                        ranges = [(line, kind) for line, kind, _ in bidi.scan_file(str(path))
                                  if kind == 'RANGE-SEP-BETWEEN-DIGITS']
                    self.assertEqual(ranges, [(4 if secondary == 'hebrew' else 6,
                                               'RANGE-SEP-BETWEEN-DIGITS')])

    def test_primitive_groups_nest_with_environments_and_braces(self):
        source = declared('english-with-hebrew') + r'''\begin{hebrewprose}
\begingroup
\selectlanguage{english}
{\selectlanguage{hebrew} INNER}
ENGLISH
\bgroup\selectlanguage{hebrew} DEEP
\egroup
ENGLISH AGAIN
\endgroup
HEBREW AGAIN
\end{hebrewprose}
ENGLISH RESTORED'''
        ctx = LanguageContext(source)
        inner_column = source.splitlines()[4].index('INNER')
        deep_column = source.splitlines()[6].index('DEEP')
        self.assertFalse(ctx.is_english(5, inner_column))
        self.assertTrue(ctx.is_english(6))
        self.assertFalse(ctx.is_english(7, deep_column))
        self.assertTrue(ctx.is_english(9))
        self.assertFalse(ctx.is_english(11))
        self.assertTrue(ctx.is_english(13))

    def test_primitive_groups_in_literal_examples_do_not_change_context(self):
        examples = [r'\verb|\begingroup\selectlanguage{english}|',
                    r'\verb|\endgroup|',
                    '\\begin{verbatim}\n\\bgroup\\selectlanguage{english}\n\\end{verbatim}',
                    '\\begin{verbatim}\n\\egroup\n\\end{verbatim}']
        for example in examples:
            with self.subTest(example=example):
                source = (declared('english-with-hebrew') + '\\begingroup\n'
                          '\\selectlanguage{hebrew}\n' + example + '\n'
                          'HEBREW 2020–2023\n\\endgroup\nENGLISH 2020–2023')
                ctx = LanguageContext(source)
                lines = source.splitlines()
                hebrew_line = next(i for i, line in enumerate(lines, 1) if line.startswith('HEBREW'))
                self.assertFalse(ctx.is_english(hebrew_line))
                self.assertTrue(ctx.is_english(len(lines)))
                self.assertIn('RANGE-SEP-BETWEEN-DIGITS', self.flags(source))

    def test_primitive_groups_in_unexecuted_macro_definitions_are_data(self):
        for command in [r'\begingroup\selectlanguage{english}', r'\endgroup',
                        r'\bgroup\selectlanguage{english}', r'\egroup']:
            with self.subTest(command=command):
                source = (declared('english-with-hebrew') + '\\begingroup\n'
                          '\\selectlanguage{hebrew}\n'
                          + '\\newcommand{\\example}{' + command + '}\n'
                          'HEBREW 2020–2023\n\\endgroup\nENGLISH 2020–2023')
                ctx = LanguageContext(source)
                self.assertFalse(ctx.is_english(5))
                self.assertTrue(ctx.is_english(7))
                self.assertIn('RANGE-SEP-BETWEEN-DIGITS', self.flags(source))

    def test_comment_or_code_cannot_close_prose_environment(self):
        source = (declared() + '\\begin{hebrewprose}\n'
                  + '% \\end{hebrewprose}\n'
                  + '\\verb|\\end{hebrewprose}|\nעברית')
        self.assertFalse(LanguageContext(source).is_english(5))

    def test_unbalanced_inline_island_does_not_exempt_rest(self):
        self.assertFalse(LanguageContext('\\en{unclosed\nעברית').is_english(2))

    def test_native_listing_no_wrapper_required(self):
        self.assertEqual(self.flags(declared() + '\\begin{lstlisting}\nx = 1\n\\end{lstlisting}'), set())

    def test_nested_hebrew_listing_still_requires_wrapper(self):
        source = (declared() + '\\begin{hebrewprose}\n\\begin{lstlisting}\n'
                  + 'x = 1\n\\end{lstlisting}\n\\end{hebrewprose}')
        self.assertIn('LISTING-OUTSIDE-LTR-ISLAND', self.flags(source))

    def test_native_english_list_in_otherlanguage_is_legal(self):
        source = (declared() + '\\begin{otherlanguage}{english}\n'
                  + '\\begin{itemize}\n\\item One\n\\end{itemize}\n\\end{otherlanguage}')
        self.assertEqual(self.flags(source), set())

    def test_native_english_bibliography_and_hebrew_island(self):
        source = (declared() + '\\begin{thebibliography}{9}\n'
                  + '\\bibitem{a} A. Author, Title (2026).\n'
                  + '\\end{thebibliography}\n'
                  + r'\en{Label:} \h{עברית}')
        self.assertEqual(self.flags(source), set())

    def test_modern_englishprose_captions_are_not_diagram_islands(self):
        source = (declared('hebrew-with-english') + '\\begin{englishprose}\n'
                  + '\\begin{tikzpic}\n\\begin{tikzpicture}\n\\draw (0,0) -- (1,0);\n'
                  + '\\end{tikzpicture}\n\\end{tikzpic}\n'
                  + '\\figcap{English figure caption.}\n'
                  + '\\begin{tablebox}\n\\tabcap{English table caption.}\n\\end{tablebox}\n'
                  + '\\end{englishprose}')
        self.assertEqual(self.flags(source, extra_ltr_aliases={'englishprose'}), set())

    def test_owned_hebrew_prose_is_not_an_ltr_caption_or_list_alias(self):
        body = ('\\begin{hebrewprose}\n'
                + '\\begin{tikzpic}\n\\begin{tikzpicture}\n\\draw (0,0) -- (1,0);\n'
                + '\\end{tikzpicture}\n\\end{tikzpic}\n'
                + '\\figcap{כיתוב איור תקין.}\n'
                + '\\begin{tablebox}\n\\tabcap{כיתוב טבלה תקין.}\n\\end{tablebox}\n'
                + '\\begin{itemize}\n\\item פריט תקין.\n\\end{itemize}\n'
                + '\\end{hebrewprose}')
        # The source CLI learns aliases from the core, including this Hebrew
        # wrapper. Exercise both externally supplied and locally discovered
        # aliases in every main-Hebrew profile, including the legacy default.
        definition = (r'\newenvironment{hebrewprose}'
                      r'{\begin{otherlanguage}{hebrew}}{\end{otherlanguage}}' + '\n')
        for prefix in ('', declared('hebrew'), declared('hebrew-with-english'),
                       declared('bilingual', 'hebrew')):
            with self.subTest(prefix=prefix, alias='shared'):
                self.assertEqual(self.flags(prefix + body,
                                           extra_ltr_aliases={'hebrewprose', 'englishprose'}), set())
            with self.subTest(prefix=prefix, alias='local'):
                self.assertEqual(self.flags(prefix + definition + body), set())

    def test_owned_hebrew_prose_does_not_hide_unsafe_diagram_ancestor(self):
        for wrapper in ('tikzpic', 'qcirc', 'asmblock'):
            source = (declared('bilingual', 'hebrew') + '\\begin{' + wrapper + '}\n'
                      + '\\begin{hebrewprose}\n\\tabcap{כיתוב בתוך תרשים.}\n'
                      + '\\begin{itemize}\n\\item פריט\n\\end{itemize}\n'
                      + '\\end{hebrewprose}\n\\end{' + wrapper + '}')
            with self.subTest(wrapper=wrapper):
                self.assertEqual(self.flags(source, extra_ltr_aliases={'hebrewprose'}),
                                 {'CAPTION-INSIDE-LTR-ISLAND', 'LIST-IN-LTR-ISLAND'})

    def test_actual_english_otherlanguage_keeps_caption_and_list_restrictions(self):
        source = (declared('bilingual', 'hebrew') + '\\begin{otherlanguage}{english}\n'
                  + '\\tabcap{An unsafe generic English wrapper.}\n'
                  + '\\begin{itemize}\n\\item Item\n\\end{itemize}\n'
                  + '\\end{otherlanguage}')
        self.assertEqual(self.flags(source, extra_ltr_aliases={'hebrewprose'}),
                         {'CAPTION-INSIDE-LTR-ISLAND', 'LIST-IN-LTR-ISLAND'})

    def test_project_english_alias_remains_unsafe_around_hebrew_prose(self):
        source = (declared('bilingual', 'hebrew')
                  + r'\newenvironment{qeng}{\begin{otherlanguage}{english}}{\end{otherlanguage}}'
                  + '\n\\begin{qeng}\n\\begin{hebrewprose}\n'
                  + '\\tabcap{כיתוב בתוך מעטפת לועזית.}\n'
                  + '\\begin{itemize}\n\\item פריט\n\\end{itemize}\n'
                  + '\\end{hebrewprose}\n\\end{qeng}')
        self.assertEqual(self.flags(source, extra_ltr_aliases={'hebrewprose'}),
                         {'CAPTION-INSIDE-LTR-ISLAND', 'LIST-IN-LTR-ISLAND'})

    def test_legacy_englishprose_keeps_legacy_restrictions(self):
        source = ('\\begin{englishprose}\n\\tabcap{English caption.}\n'
                  + '\\begin{itemize}\n\\item Item\n\\end{itemize}\n\\end{englishprose}')
        self.assertEqual(self.flags(source, extra_ltr_aliases={'englishprose'}),
                         {'CAPTION-INSIDE-LTR-ISLAND', 'LIST-IN-LTR-ISLAND'})

    def test_modern_minority_english_list_has_measured_layout_support(self):
        source = (declared('hebrew-with-english') + '\\begin{englishprose}\n'
                  + '\\begin{itemize}\n\\item Item\n\\end{itemize}\n\\end{englishprose}')
        self.assertEqual(self.flags(source, extra_ltr_aliases={'englishprose'}), set())

    def test_native_english_diagram_wrapper_still_rejects_caption(self):
        for profile in ('english', 'hebrew-with-english'):
            source = (declared(profile) + '\\begin{englishprose}\n\\begin{tikzpic}\n'
                      + '\\tabcap{Not a prose context.}\n\\begin{itemize}\n'
                      + '\\item Item\n\\end{itemize}\n\\end{tikzpic}\n\\end{englishprose}')
            with self.subTest(profile=profile):
                self.assertEqual(self.flags(source, extra_ltr_aliases={'englishprose'}),
                                 {'CAPTION-INSIDE-LTR-ISLAND', 'LIST-IN-LTR-ISLAND'})

    def test_project_parts_inherit_main_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'main.tex').write_text(declared() + '\\begin{document}Text\\end{document}')
            (root / 'parts').mkdir()
            part = root / 'parts' / 'one.tex'
            part.write_text("``quoted'' 2020–2023")
            with redirect_stdout(io.StringIO()):
                self.assertEqual(bidi.main(['bidi', str(part)]), 0)

    def test_inherited_profile_is_not_global_between_projects(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            files = []
            for name, profile in [('a', 'english'), ('b', 'hebrew')]:
                (root / name).mkdir()
                main = root / name / 'main.tex'
                main.write_text(declared(profile) + '\\begin{document}Text\\end{document}')
                part = root / name / 'part.tex'
                part.write_text('2020–2023')
                files.append(str(part))
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(bidi.main(['bidi', *files]), 1)
            self.assertNotIn(files[0] + ':1:', output.getvalue())
            self.assertIn(files[1] + ':1:', output.getvalue())

    def project_check(self, profile, body, parts, *, requested=None):
        """Run the real CLI discovery path, including single-part authoring."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            main = root / 'main.tex'
            main.write_text(declared(profile) + '\\begin{document}\n' + body
                            + '\n\\end{document}', encoding='utf-8')
            for name, source in parts.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(source, encoding='utf-8')
            paths = [root / name for name in requested] if requested else [main, *(
                root / name for name in parts)]
            output = io.StringIO()
            with redirect_stdout(output):
                code = bidi.main(['bidi', *map(str, paths)])
            return code, output.getvalue().replace(str(root), 'PROJECT')

    def test_literal_include_inherits_english_callsite_in_hebrew_document(self):
        code, output = self.project_check(
            'hebrew-with-english', r'\begin{englishprose}\input{parts/one}\end{englishprose}',
            {'parts/one.tex': 'English range 2020–2023.'}, requested=['parts/one.tex'])
        self.assertEqual(code, 0, output)

    def test_literal_include_inherits_hebrew_callsite_in_english_document(self):
        code, output = self.project_check(
            'english-with-hebrew', r'\begin{hebrewprose}\input{parts/one}\end{hebrewprose}',
            {'parts/one.tex': 'טווח עברי 2020–2023.'}, requested=['parts/one.tex'])
        self.assertEqual(code, 1, output)
        self.assertIn('PROJECT/parts/one.tex:1: [RANGE-SEP-BETWEEN-DIGITS]', output)
        self.assertNotIn('LANGUAGE-CONTEXT-UNRESOLVED', output)

    def test_repeated_includes_keep_all_callsite_contexts(self):
        for english_first in (True, False):
            english = r'\begin{englishprose}\input{part}\end{englishprose}'
            hebrew = r'\begin{hebrewprose}\input{part}\end{hebrewprose}'
            with self.subTest(english_first=english_first):
                code, output = self.project_check('english-with-hebrew',
                    english + hebrew if english_first else hebrew + english,
                    {'part.tex': 'Range 2020–2023.'})
                self.assertEqual(code, 1, output)
                self.assertEqual(output.count('[RANGE-SEP-BETWEEN-DIGITS]'), 1)

    def test_child_unscoped_selectlanguage_changes_caller_until_group_end(self):
        code, output = self.project_check('english-with-hebrew',
            '{\\input{part}\nINNER 2020–2023}\nRESTORED 2020–2023',
            {'part.tex': r'\selectlanguage{hebrew} CHILD 2020–2023'})
        self.assertEqual(code, 1, output)
        self.assertIn('PROJECT/main.tex:4: [RANGE-SEP-BETWEEN-DIGITS]', output)
        self.assertNotIn('PROJECT/main.tex:5:', output)
        self.assertIn('PROJECT/part.tex:1: [RANGE-SEP-BETWEEN-DIGITS]', output)
        self.assertNotIn('LANGUAGE-CONTEXT-UNRESOLVED', output)

    def test_child_local_groups_restore_its_entry_language_and_caller(self):
        source = (r'\begingroup\selectlanguage{hebrew} CHILD 2020–2023\endgroup'
                  + '\nCHILD_RESTORED 2020–2023')
        code, output = self.project_check('hebrew-with-english',
            '\\begin{englishprose}\\input{part}\nCALLER_ENGLISH 2020–2023'
            '\\end{englishprose}\nCALLER_HEBREW 2020–2023', {'part.tex': source})
        self.assertEqual(code, 1, output)
        self.assertIn('PROJECT/part.tex:1: [RANGE-SEP-BETWEEN-DIGITS]', output)
        self.assertNotIn('PROJECT/part.tex:2:', output)
        self.assertNotIn('PROJECT/main.tex:4:', output)
        self.assertIn('PROJECT/main.tex:5: [RANGE-SEP-BETWEEN-DIGITS]', output)

    def test_nested_literal_includes_follow_import_search_context(self):
        code, output = self.project_check('hebrew-with-english',
            r'\begin{englishprose}\import{parts/}{one}\end{englishprose}',
            {'parts/one.tex': r'\input{two}', 'parts/two.tex': 'Range 2020–2023.'})
        self.assertEqual(code, 0, output)

    def test_include_font_policy_stays_document_owned(self):
        code, output = self.project_check('english-with-hebrew',
            r'\begin{hebrewprose}\input{part}\end{hebrewprose}',
            {'part.tex': r'\providecommand{\lakitlanguageprofile}{hebrew}'
                         '\n' + r'\en{``quoted English''}'})
        self.assertEqual(code, 0, output)

    def test_prebody_provider_conditionals_do_not_change_body_locale(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            provider = root / 'preamble.tex'
            provider.write_text(r'\providecommand{\lakitlanguageprofile}{hebrew}'
                                '\n' + r'\ifdefined\unknown\selectlanguage{hebrew}\fi')
            main = root / 'main.tex'
            main.write_text(declared() + r'\input{preamble}'
                            '\n' + r'\begin{document}English 2020–2023\end{document}')
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(bidi.main(['bidi', str(main), str(provider)]), 0,
                                 output.getvalue())

    def test_unexecuted_or_literal_dynamic_includes_do_not_change_context(self):
        code, output = self.project_check('english-with-hebrew',
            r'\newcommand{\example}{\input{\jobname}}'
            + '\n' + r'\verb|\input{\jobname}|'
            + '\n' + r'\input{part}', {'part.tex': 'English 2020–2023'})
        self.assertEqual(code, 0, output)

    def test_literal_listing_options_do_not_execute_include_or_profile_tokens(self):
        source = (r'\lstinputlisting[morekeywords={\input{missing},'
                  r'\def\lakitlanguageprofile{hebrew},\selectlanguage{hebrew}},'
                  r'caption={English source listing}]{demo.py}'
                  + '\n' + r'\input{part}')
        code, output = self.project_check('english-with-hebrew', source,
            {'part.tex': 'English range 2020–2023.', 'demo.py': 'print("hello")'})
        self.assertEqual(code, 0, output)
        context = LanguageContext(declared('english-with-hebrew') + source)
        self.assertEqual(context.config.profile, 'english-with-hebrew')
        self.assertEqual(context.exit_language, 'english')
        code, output = self.project_check('english-with-hebrew', source,
            {'part.tex': r'\begin{hebrewprose}2020–2023\end{hebrewprose}',
             'demo.py': 'print("hello")'})
        self.assertEqual(code, 1, output)
        self.assertIn('PROJECT/part.tex:1: [RANGE-SEP-BETWEEN-DIGITS]', output)
        self.assertNotIn('LANGUAGE-CONTEXT-UNRESOLVED', output)

    def test_literal_listing_captions_and_titles_retain_text_language_guards(self):
        for key in ('caption', 'title'):
            for main, secondary in [('english', 'hebrew'), ('hebrew', 'english')]:
                with self.subTest(key=key, main=main):
                    source = (r'\lstinputlisting[' + key + '={\\foreignlanguage[]{'
                              + secondary + '}{2020–2023}}]{demo.py}')
                    code, output = self.project_check(main+'-with-'+secondary, source,
                                                     {'demo.py': 'print("hello")'})
                    self.assertEqual(code, int(secondary == 'hebrew'), output)
                    self.assertNotIn('LANGUAGE-CONTEXT-UNRESOLVED', output)
                    if secondary == 'hebrew':
                        self.assertIn('[RANGE-SEP-BETWEEN-DIGITS]', output)
        code, output = self.project_check('english-with-hebrew',
            r'\lstinputlisting[caption={\h{טווח 2020–2023}}]{demo.py}',
            {'demo.py': 'print("hello")'})
        self.assertEqual(code, 1, output)
        self.assertIn('[RANGE-SEP-BETWEEN-DIGITS]', output)

    def test_executable_listing_caption_include_is_conservatively_unresolved(self):
        code, output = self.project_check('english',
            r'\lstinputlisting[caption={\input{caption}}]{demo.py}',
            {'caption.tex': 'Caption text.', 'demo.py': 'print("hello")'})
        self.assertEqual(code, 1, output)
        self.assertIn('[LANGUAGE-CONTEXT-UNRESOLVED]', output)

    def test_listing_option_close_protected_by_braces_preserves_caption_and_tail(self):
        source = (r'\lstinputlisting[morekeywords={],\input{missing}},'
                  r'caption={\h{טווח 2020–2023}}]{demo.py}' + '\n'
                  + r'\begin{hebrewprose}\input{part}\end{hebrewprose}')
        code, output = self.project_check('english-with-hebrew', source,
            {'demo.py': 'print("hello")', 'part.tex': 'Range 2020–2023.'})
        self.assertEqual(code, 1, output)
        self.assertEqual(output.count('[RANGE-SEP-BETWEEN-DIGITS]'), 2)
        self.assertIn('PROJECT/part.tex:1:', output)
        self.assertNotIn('LANGUAGE-CONTEXT-UNRESOLVED', output)

    def test_bare_open_bracket_does_not_extend_listing_optional_argument(self):
        source = (r'\lstinputlisting[morekeywords=[,caption={English listing}]{demo.py}'
                  + '\n' + r'\begin{hebrewprose}\input{part}\end{hebrewprose}')
        from language_context import listing_arguments_end
        self.assertEqual(listing_arguments_end(source, len(r'\lstinputlisting')),
                         source.index('\n'))
        code, output = self.project_check('english-with-hebrew', source,
            {'demo.py': 'print("hello")', 'part.tex': 'Range 2020–2023.'})
        self.assertEqual(code, 1, output)
        self.assertEqual(output.count('[RANGE-SEP-BETWEEN-DIGITS]'), 1)
        self.assertIn('PROJECT/part.tex:1:', output)
        self.assertNotIn('LANGUAGE-CONTEXT-UNRESOLVED', output)

    def test_actual_dynamic_include_is_conservatively_unresolved(self):
        code, output = self.project_check('english', r'\input{\jobname}', {})
        self.assertEqual(code, 1, output)
        self.assertIn('[LANGUAGE-CONTEXT-UNRESOLVED]', output)

    def test_explicit_mismatched_project_boundary_remains_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            boundary = Path(directory) / 'different-project'
            boundary.mkdir()
            with patch.dict(os.environ, {'HEBREW_LATEX_PROJECT_ROOT': str(boundary)}):
                code, output = self.project_check('english', r'\input{part}',
                                                  {'part.tex': 'English range 2020–2023.'})
            self.assertEqual(code, 1, output)
            self.assertIn('[LANGUAGE-CONTEXT-UNRESOLVED]', output)
            self.assertIn('not in the subpath', output)

    def test_cross_file_language_and_group_boundaries_are_unresolved(self):
        pairs = [(r'\begin{englishprose}\input{part}', r'\end{englishprose}'),
                 (r'\begingroup\input{part}', r'\endgroup'),
                 (r'\input{part}\end{hebrewprose}', r'\begin{hebrewprose}')]
        for body, part in pairs:
            with self.subTest(body=body):
                code, output = self.project_check('hebrew-with-english', body,
                                                  {'part.tex': part})
                self.assertEqual(code, 1, output)
                self.assertIn('[LANGUAGE-CONTEXT-UNRESOLVED]', output)

    def test_literal_include_cycle_is_conservatively_unresolved(self):
        code, output = self.project_check('english', r'\input{part}',
                                          {'part.tex': r'\input{main}'})
        self.assertEqual(code, 1, output)
        self.assertIn('literal include cycle', output)

    def test_document_boundary_in_child_preserves_root_profile_and_later_visits(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sources = {'main.tex': declared('english-with-hebrew')
                       + r'\input{start}\input{part}\end{document}',
                       'start.tex': r'\begin{document}',
                       'part.tex': 'English 2020–2023.'}
            for name, text in sources.items():
                (root / name).write_text(text, encoding='utf-8')
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(bidi.main(['bidi', *(str(root / name) for name in sources)]),
                                 0, output.getvalue())
            contexts, findings = bidi.document_language_contexts(root / 'main.tex')
            self.assertFalse(findings)
            self.assertEqual(contexts[root / 'part.tex'][0].config.profile, 'english-with-hebrew')
            self.assertTrue(contexts[root / 'part.tex'][0].entry_in_document)
            self.assertFalse(contexts[root / 'main.tex'][0].exit_in_document)

    def test_document_include_cycle_cannot_disappear_during_root_discovery(self):
        code, output = self.project_check('english', r'\input{part}',
            {'part.tex': r'\begin{document}\input{main}\end{document}'})
        self.assertEqual(code, 1, output)
        self.assertIn('literal include cycle', output)

    def test_partial_snippet_api_keeps_placeholder_paths_and_source_guards(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'snippet.tex'
            path.write_text(declared() + r'\input{placeholder}'
                            + r'\begin{document}English 2020–2023\end{document}')
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(bidi.main(['bidi', str(path)], resolve_includes=False), 0)
            path.write_text(declared('english-with-hebrew')
                            + r'\begin{document}\begin{hebrewprose}2020–2023'
                            + r'\end{hebrewprose}\end{document}')
            with redirect_stdout(output):
                self.assertEqual(bidi.main(['bidi', str(path)], resolve_includes=False), 1)
            self.assertIn('[RANGE-SEP-BETWEEN-DIGITS]', output.getvalue())


if __name__ == '__main__':
    unittest.main()
