#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Original project code; scope and terms: ../LICENSING.md.
"""Project generation contracts: native language, independent axes, safe publication."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
import sys
from unittest.mock import patch
sys.dont_write_bytecode = True
import new_document as generator


class ProjectGeneratorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def make(self, name='project', **kwargs):
        dest = self.root / name
        generator.create(kwargs.pop('kind', 'general'), dest, **kwargs)
        return dest, (dest / 'main.tex').read_text(), json.loads((dest / 'project.json').read_text())

    def test_native_english_has_english_metadata_and_unwrapped_english_body(self):
        for kind in generator.KINDS:
            with self.subTest(kind=kind):
                _, source, manifest = self.make(kind, kind=kind, language='english')
                self.assertIn(r'\def\lakitmainlanguage{english}', source)
                self.assertNotRegex(source, '[\u0590-\u05ff]')
                self.assertNotIn(r'\begin{englishprose}', source)
                self.assertEqual(manifest['base_direction'], 'ltr')
                self.assertRegex(source, r'\\hypersetup\{pdftitle=\{[A-Za-z]')

    def test_legacy_default_remains_hebrew(self):
        dest = self.root / 'old-api'
        generator.create('note', dest)
        source = (dest / 'main.tex').read_text()
        self.assertIn(r'\def\lakitmainlanguage{hebrew}', source)
        self.assertIn('העברת משימה', source)

    def test_schema3_records_requested_resolved_recipe_and_catalog_snapshot(self):
        cases = [dict(kind='paper', language='english'),
                 dict(kind='formula-sheet', language='bilingual', main_language='hebrew',
                      layout='reference-readable', theme='core'),
                 dict(kind='general', language='hebrew-with-english', theme='custom')]
        for number, choices in enumerate(cases):
            with self.subTest(choices=choices):
                _, _, manifest = self.make('catalog-snapshot-' + str(number), **choices)
                recipe = generator.resolve_recipe(root=generator.ROOT, catalog=generator.CATALOG,
                                                   **choices)
                self.assertEqual(manifest['schema'], 3)
                self.assertEqual(manifest['recipe'], recipe.as_dict())
                self.assertEqual(manifest['registry']['path'], 'registry/studio-catalog.json')
                self.assertEqual(manifest['registry']['schema'], generator.CATALOG.schema_version)
                self.assertEqual(manifest['registry']['sha256'], generator.CATALOG.sha256)
                self.assertEqual(manifest['registry']['sha256'], hashlib.sha256(
                    (generator.ROOT / 'registry/studio-catalog.json').read_bytes()).hexdigest())
                self.assertIn('creation-time', manifest['registry']['scope'])
                self.assertIn('no compile, render or visual validation', manifest['registry']['scope'])
                self.assertEqual(manifest['package_compatibility'], 'not-validated-by-generator')

    def test_existing_generated_project_and_historical_snapshot_are_never_updated(self):
        project, _, _ = self.make('historical-project', language='english')
        manifest_before = (project / 'project.json').read_bytes()
        edited = (project / 'main.tex').read_text() + '% User-owned revision.\n'
        (project / 'main.tex').write_text(edited)
        with self.assertRaisesRegex(ValueError, 'destination already exists'):
            generator.create('paper', project, language='hebrew')
        self.assertEqual((project / 'main.tex').read_text(), edited)
        self.assertEqual((project / 'project.json').read_bytes(), manifest_before)

    def test_python_generator_package_iterables_keep_order_and_provenance(self):
        _, source, manifest = self.make('iterable-packages', kind='data-report',
                                       language='english',
                                       packages=(name for name in ['longtable', 'microtype',
                                                                  'longtable', 'amsmath']))
        self.assertEqual([p['name'] for p in manifest['package_selections']],
                         ['longtable', 'microtype', 'amsmath'])
        self.assertEqual(manifest['package_selections'][0]['loaded_by'], 'flow_tables.tex')
        self.assertEqual(source.count(r'\usepackage{microtype}'), 1)
        self.assertNotIn(r'\usepackage{longtable}', source)
        self.assertNotIn(r'\usepackage{amsmath}', source)

    def test_mutating_compatibility_query_does_not_drift_source_or_snapshot(self):
        with patch.dict(generator.REFERENCE_LAYOUTS['reference-compact'],
                        {'columns': 9, 'body_font_size': '7.777', 'math_font_size': '7.1'}):
            _, source, manifest = self.make('canonical-reference', kind='formula-sheet',
                                            language='english', layout='reference-compact')
        self.assertIn(r'\def\ReferenceColumnCount{3}', source)
        self.assertIn(r'\def\ReferenceBodyFontSize{6.3}', source)
        self.assertIn(r'\def\ReferenceMathFontSize{6.25}', source)
        self.assertEqual(manifest['layout']['columns'], 3)
        self.assertEqual(manifest['layout']['body_font_size'], '6.3')
        self.assertEqual(manifest['layout']['math_font_size'], '6.25')

    def test_layout_metadata_describes_owned_declarations_without_shadow_defaults(self):
        _, source, _ = self.make('reference-declarations', kind='formula-sheet',
                                 language='english', layout='reference-readable')
        edited = source.replace(r'\def\ReferenceColumnGap{5mm}',
                                r'\def\ReferenceColumnGap{6mm}')
        edited = edited.replace(r'\def\ReferenceColumnRule{0.3pt}',
                                 r'\def\ReferenceColumnRule{0.4pt}')
        edited = edited.replace('10pt,a4paper', '10pt,letterpaper')
        metadata = generator.declared_layout(edited, 'reference', 'reference-readable')
        self.assertEqual(metadata['column_gap'], '6mm')
        self.assertEqual(metadata['column_rule'], '0.4pt')
        self.assertEqual(metadata['expected_paper'], 'letter')
        with self.assertRaisesRegex(ValueError, 'conflicting paper'):
            generator.declared_layout(edited.replace('10pt,letterpaper',
                                                     '10pt,letterpaper,a4paper'),
                                      'reference', 'reference-readable')
        unknown = generator.declared_layout(r'\def\lakitclassoptions{11pt}', 'reader')
        self.assertIsNone(unknown['expected_paper'])

    def test_all_language_genre_theme_combinations_generate_valid_snapshots(self):
        modes = [('hebrew', None), ('english', None), ('hebrew-with-english', None),
                 ('english-with-hebrew', None), ('bilingual', 'hebrew'), ('bilingual', 'english')]
        for kind in generator.KINDS:
            for language, main in modes:
                for theme in generator.THEMES:
                    name = f'{kind}-{language}-{main}-{theme}'
                    with self.subTest(name=name):
                        dest, source, manifest = self.make(name, kind=kind, language=language,
                                                          main_language=main, theme=theme)
                        self.assertEqual(source.count(r'\begin{document}'), 1)
                        self.assertEqual(source.count(r'\end{document}'), 1)
                        self.assertEqual((dest / 'reader_theme.tex').exists(), theme == 'reader')
                        self.assertEqual((dest / 'academic_theme.tex').exists(), theme == 'academic')
                        self.assertEqual((dest / 'reference_theme.tex').exists(), theme == 'reference')
                        self.assertEqual((dest / 'theme.tex').exists(), theme == 'custom')
                        self.assertEqual((dest / 'flow_tables.tex').exists(), kind == 'data-report')
                        self.assertEqual((dest / 'deferred_notes.tex').exists(), kind == 'annotated-note')
                        for file, expected in manifest['initial_source_sha256'].items():
                            self.assertEqual(hashlib.sha256((dest / file).read_bytes()).hexdigest(), expected)

    def test_bilingual_deferred_notes_preserve_language_and_unique_keys(self):
        _, source, _ = self.make(kind='annotated-note', language='bilingual', main_language='english')
        self.assertIn(r'\DeclareDocNote[english]{scope}', source)
        self.assertIn(r'\DeclareDocNote[hebrew]{secondary-scope}', source)
        self.assertIn(r'\DocNoteMark{secondary-scope}', source)
        self.assertIn(r'\begin{hebrewprose}', source)
        self.assertIn(r'\begin{englishprose}', source)

    def test_mixed_supplement_is_reader_facing_prose_without_authoring_tutorial(self):
        cases = [('english-with-hebrew', 'hebrew', ('מסקנה', 'נתונים', 'הנחות', 'מידע')),
                 ('hebrew-with-english', 'english', ('conclusion', 'evidence', 'assumptions', 'information'))]
        tutorial_phrases = ('A short Hebrew term can appear inline',
                            'use a language block with its own direction',
                            'This is a short English note',
                            'The document shell remains Hebrew',
                            'מושג קצר באנגלית אפשר לכתוב כך',
                            'פסקה שלמה נכתבת בהקשר',
                            'זוהי הערה קצרה בעברית')
        for language, secondary, concepts in cases:
            with self.subTest(language=language):
                _, source, manifest = self.make('reader-supplement-' + language,
                                                kind='note', language=language)
                body = source.partition(r'\begin{document}')[2].rpartition(r'\end{document}')[0]
                # Authoring instructions may remain in comments, never in visible prose.
                active_body = re.sub(r'(?<!\\)%[^\n]*', '', body)
                self.assertEqual(manifest['recipe']['minority_composer_id'], 'append-note')
                supplements = re.findall(r'\\begin\{' + secondary + r'prose\}(.*?)'
                                         r'\\end\{' + secondary + r'prose\}', active_body, flags=re.S)
                self.assertEqual(len(supplements), 1)
                for concept in concepts:
                    self.assertIn(concept, supplements[0])
                for phrase in tutorial_phrases:
                    self.assertNotIn(phrase, active_body)

    def test_mixed_letter_request_belongs_before_closing_and_signature(self):
        cases = [('english-with-hebrew', 'hebrew', 'Thank you for your time', 'Sincerely,',
                  'אשמח לקבל אישור'),
                 ('hebrew-with-english', 'english', 'תודה על הזמן', 'בברכה,',
                  'Please confirm receipt')]
        for language, secondary, closing, signature, request in cases:
            for theme in (None, *generator.THEMES):
                with self.subTest(language=language, theme=theme):
                    _, source, manifest = self.make('letter-' + language + '-' + str(theme),
                        kind='letter', language=language, theme=theme)
                    self.assertEqual(source.count(r'\begin{' + secondary + 'prose}'), 1)
                    self.assertEqual(source.count(r'\end{' + secondary + 'prose}'), 1)
                    self.assertIn(request, source)
                    self.assertLess(source.index(request), source.index(closing))
                    self.assertLess(source.index(closing), source.index(signature))
                    self.assertNotIn(r'\section{', source)
                    self.assertEqual(source.count(signature), 1)
                    self.assertEqual(manifest['recipe']['minority_composer_id'],
                                     'letter-before-signature')
                    self.assertEqual(manifest['recipe']['recipe_revision'], 3)

    def test_complete_bilingual_standard_reports_open_translation_on_new_page(self):
        for kind in ('report', 'technical', 'formula-sheet', 'data-report'):
            for main in ('english', 'hebrew'):
                secondary = 'hebrew' if main == 'english' else 'english'
                for theme in (None, *generator.THEMES):
                    with self.subTest(kind=kind, main=main, theme=theme):
                        _, source, manifest = self.make(kind + '-paired-' + main + '-' + str(theme),
                            kind=kind, language='bilingual', main_language=main, theme=theme)
                        self.assertEqual(source.count(r'\clearpage'), 1)
                        self.assertNotIn(r'\bigskip', source)
                        self.assertIn(r'\end{' + main + 'prose}\n\\clearpage\n\\begin{' +
                                      secondary + 'prose}', source)
                        self.assertEqual(manifest['recipe']['composer_id'], 'paired-full-pages')
                        self.assertEqual(manifest['recipe']['recipe_revision'],
                                         6 if kind == 'data-report' else 3)

    def test_short_and_specialized_bilingual_bodies_retain_continuous_flow(self):
        for kind in ('note', 'general', 'letter', 'annotated-note'):
            for main in ('english', 'hebrew'):
                with self.subTest(kind=kind, main=main):
                    _, source, manifest = self.make(kind + '-flow-' + main, kind=kind,
                                                    language='bilingual', main_language=main)
                    self.assertEqual(source.count(r'\bigskip'), 1)
                    self.assertNotIn(r'\clearpage', source)
                    self.assertEqual(manifest['recipe']['composer_id'], 'paired-bodies')

    def test_letter_handler_rejects_unrecognized_owned_closing(self):
        for minority in ('hebrew', 'english'):
            with self.subTest(minority=minority), self.assertRaisesRegex(ValueError,
                                                                           'malformed letter'):
                generator.letter_minority_note('Unrecognized sample letter', minority)

    def test_unknown_content_handlers_fail_instead_of_silently_appending(self):
        with self.assertRaisesRegex(ValueError, 'unknown minority composer'):
            generator.compose_minority_body('body', 'english', 'extension', 'unknown')

    def test_bilingual_table_and_equation_references_resolve_distinct_sources(self):
        _, source, _ = self.make(kind='data-report', language='bilingual', main_language='hebrew')
        for label in ['eq:mean', 'secondary-eq:mean']:
            self.assertEqual(source.count('\\label{' + label + '}'), 1)
            self.assertEqual(source.count('\\eqref{' + label + '}'), 1)
        self.assertIn('{tab:measurements}', source)
        self.assertIn('{secondary-tab:measurements}', source)
        self.assertEqual(source.count(r'\autoref{secondary-tab:measurements}'), 1)
        self.assertEqual(source.count(r'\Needspace{10\baselineskip}'), 2)

    def test_invalid_language_combinations_fail_before_creating_directories(self):
        for kwargs in [dict(language='bilingual'), dict(language='english', main_language='hebrew'),
                       dict(language='hebrew-with-english', main_language='english'),
                       dict(language='unknown'), dict(main_language='french')]:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                generator.create('general', self.root / 'must-not-exist', **kwargs)
            self.assertFalse((self.root / 'must-not-exist').exists())

    def test_package_names_are_literal_and_existing_packages_are_not_reloaded(self):
        _, source, manifest = self.make(language='english', packages=['microtype', 'microtype', 'amsmath', 'hyperref'])
        self.assertEqual(source.count(r'\usepackage{microtype}'), 1)
        self.assertNotIn(r'\usepackage{amsmath}', source)
        self.assertNotIn(r'\usepackage{hyperref}', source)
        self.assertEqual([p['name'] for p in manifest['package_selections']], ['microtype', 'amsmath', 'hyperref'])
        self.assertEqual(manifest['package_selections'][1]['status'], 'already-provided')

    def observed_build(self, project, profile, contracts=None):
        """Run the generated Bash wrapper against the real configuration validator.

        The mock builder has no compiler/font dependency. It observes the value
        arriving from the wrapper and applies build.sh's established empty-value
        contract before invoking the actual validator.
        """
        mock_scripts = self.root / 'mock-skill' / 'scripts'
        mock_scripts.mkdir(parents=True, exist_ok=True)
        validator = Path(generator.ROOT) / 'scripts' / 'validate_build_config.py'
        (mock_scripts / 'build.sh').write_text('''#!/usr/bin/env bash
python3 - <<'PY'
import json, os, subprocess, sys
raw = os.environ.get('CONTENT_PROFILE')
effective = raw or 'generic'
result = subprocess.run([sys.executable, ''' + repr(str(validator)) + ''',
                         '--content-profile', effective], capture_output=True, text=True)
print(json.dumps({'raw': raw, 'effective': effective, 'validator_exit': result.returncode,
                  'contracts': {name: os.environ.get(name) for name in
                     ['EXPECTED_PAPER', 'PDF_FOLIO_LAYOUT', 'PDF_FOLIO_BAND',
                      'PDF_CAPTION_COLOR', 'PDF_CAPTION_LABEL_WEIGHT']},
                  'diagnostic': result.stdout + result.stderr}))
raise SystemExit(result.returncode)
PY
''')
        caller = self.root / 'unrelated-caller'
        caller.mkdir(exist_ok=True)
        env = dict(os.environ, HEBREW_LATEX_SKILL_ROOT=str(mock_scripts.parent))
        env.pop('CONTENT_PROFILE', None)
        if profile is not None:
            env['CONTENT_PROFILE'] = profile
        for name in ('EXPECTED_PAPER', 'PDF_FOLIO_LAYOUT', 'PDF_FOLIO_BAND',
                     'PDF_CAPTION_COLOR', 'PDF_CAPTION_LABEL_WEIGHT'):
            env.pop(name, None)
        env.update(contracts or {})
        result = subprocess.run(['bash', str(project / 'build.sh')], cwd=caller,
                                env=env, text=True, capture_output=True, timeout=30)
        self.assertTrue(result.stdout.strip(), result.stderr)
        return result.returncode, json.loads(result.stdout)

    def test_generated_wrapper_preserves_profile_overrides_and_empty_builder_default(self):
        project, _, _ = self.make('profile-wrapper', kind='report', language='english')
        cases = [(None, 'report', 'report', 0), ('generic', 'generic', 'generic', 0),
                 ('study-guide', 'study-guide', 'study-guide', 0),
                 ('exma', 'exma', 'exma', 2), ('', '', 'generic', 0)]
        for caller_value, raw, effective, expected_exit in cases:
            with self.subTest(caller_value=caller_value):
                exit_code, observed = self.observed_build(project, caller_value)
                self.assertEqual(exit_code, expected_exit)
                self.assertEqual(observed['raw'], raw)
                self.assertEqual(observed['effective'], effective)
                self.assertEqual(observed['validator_exit'], expected_exit)
                if expected_exit:
                    self.assertIn("got 'exma'", observed['diagnostic'])

    def test_paper_default_and_explicit_themes_remain_independent(self):
        for kind in generator.KINDS:
            with self.subTest(kind=kind):
                _, _, manifest = self.make('default-' + kind, kind=kind)
                self.assertEqual(manifest['theme'], 'academic' if kind == 'paper' else 'reader')
        for theme in generator.THEMES:
            with self.subTest(theme=theme):
                _, source, manifest = self.make('paper-' + theme, kind='paper',
                                                language='english', theme=theme)
                self.assertEqual(manifest['theme'], theme)
                self.assertEqual(source.count(r'\input{academic_theme.tex}'), theme == 'academic')
                self.assertEqual(source.count(r'\input{reader_theme.tex}'), theme == 'reader')
                self.assertIn(r'\def\lakitgeometryoptions{margin=2.7cm,headheight=14pt}', source)
                self.assertEqual(manifest['layout']['declared_hooks']['lakitdocumentclass'], 'article')
                self.assertEqual(manifest['layout']['declared_hooks']['lakitclassoptions'], '11pt,a4paper')
                self.assertEqual(manifest['layout']['declared_hooks']['lakitlinespread'], '1.08')
                self.assertEqual(manifest['layout']['expected_paper'], 'a4')
                self.assertIn('Latin Modern Roman' if theme in ('academic', 'reference') else 'language-profile',
                              manifest['layout']['font_policy'])

    def test_paper_bilingual_has_one_title_paired_abstracts_and_shared_bibliography(self):
        for main in ('english', 'hebrew'):
            with self.subTest(main=main):
                _, source, manifest = self.make('paired-' + main, kind='paper',
                                                language='bilingual', main_language=main)
                self.assertEqual(source.count(r'\maketitle'), 1)
                self.assertEqual(source.count(r'\title{'), 1)
                self.assertEqual(source.count(r'\clearpage'), 1)
                self.assertLess(source.index(r'\clearpage'), source.index(r'\label{secondary-eq:objective}'))
                self.assertEqual(source.count(r'\begin{abstract}'), 2)
                self.assertLess(source.rindex(r'\end{abstract}'), source.index(r'\section{'))
                self.assertEqual(source.count(r'\begin{thebibliography}'), 1)
                self.assertEqual(source.count(r'\phantomsection'), 1)
                self.assertEqual(source.count(r'\addcontentsline{toc}{section}{\refname}'), 1)
                self.assertEqual(source.count(r'\bibitem{boyd2004}'), 1)
                self.assertEqual(source.count(r'\cite{boyd2004}'), 2)
                self.assertEqual(len(manifest['templates']), 2)
                self.assertIn(r'\newtheorem{paperlemma}{\iflanguage{english}{Lemma}{למה}}', source)
                for label in ('eq:objective', 'eq:solution', 'eq:minimum-value',
                              'lem:minimum', 'tab:penalties', 'fig:quadratic'):
                    self.assertEqual(source.count(r'\label{' + label + '}'), 1)
                    self.assertEqual(source.count(r'\label{secondary-' + label + '}'), 1)
                self.assertIn(r'\noeqref{secondary-eq:minimum-value}', source)
                self.assertIn(r'\autoref{secondary-fig:quadratic}', source)
                self.assertIn(r'\author{}', source)
                self.assertIn(r'\date{}', source)

    def test_paper_numbers_cited_and_central_equations_and_leaves_working_unnumbered(self):
        for language in ('english', 'hebrew'):
            with self.subTest(language=language):
                _, source, _ = self.make('selective-' + language, kind='paper', language=language)
                self.assertIn(r'\begin{align*}', source)
                self.assertIn(r'\eqref{eq:objective}', source)
                self.assertIn(r'\eqref{eq:solution}', source)
                self.assertIn(r'\noeqref{eq:minimum-value}', source)
                self.assertNotIn(r'\eqref{eq:minimum-value}', source)
                self.assertNotIn(r'\tag{', source)
                self.assertIn('Cambridge University Press, 2004.', source)

    def test_mixed_paper_summary_precedes_its_single_bibliography(self):
        for language, secondary in [('english-with-hebrew', 'hebrew'),
                                    ('hebrew-with-english', 'english')]:
            with self.subTest(language=language):
                _, source, _ = self.make('mixed-' + language, kind='paper', language=language)
                self.assertEqual(source.count(r'\begin{thebibliography}'), 1)
                self.assertEqual(source.count(r'\bibitem{boyd2004}'), 1)
                self.assertLess(source.index(r'\begin{' + secondary + 'prose}'),
                                source.index(r'\begin{thebibliography}'))
                self.assertLess(source.rindex(r'\section{'), source.index(r'\begin{thebibliography}'))
                self.assertIn(r'\eqref{eq:solution}', source)

    def test_paper_and_academic_wrapper_defaults_preserve_explicit_contracts(self):
        paper, _, _ = self.make('paper-contract', kind='paper', language='english')
        _, observed = self.observed_build(paper, None)
        expected = {'EXPECTED_PAPER': 'a4', 'PDF_FOLIO_LAYOUT': 'center',
                    'PDF_FOLIO_BAND': 'footer', 'PDF_CAPTION_COLOR': '000000',
                    'PDF_CAPTION_LABEL_WEIGHT': 'normal'}
        self.assertEqual(observed['contracts'], expected)
        explicit = {'EXPECTED_PAPER': 'letter', 'PDF_FOLIO_LAYOUT': 'left',
                    'PDF_FOLIO_BAND': 'header', 'PDF_CAPTION_COLOR': '123456',
                    'PDF_CAPTION_LABEL_WEIGHT': 'bold'}
        _, observed = self.observed_build(paper, 'generic', explicit)
        self.assertEqual(observed['contracts'], explicit)
        empty = dict.fromkeys(explicit, '')
        _, observed = self.observed_build(paper, None, empty)
        self.assertEqual(observed['contracts'], empty)
        academic, _, _ = self.make('general-academic', theme='academic')
        _, observed = self.observed_build(academic, None)
        self.assertIsNone(observed['contracts']['EXPECTED_PAPER'])
        self.assertIsNone(observed['contracts']['PDF_FOLIO_LAYOUT'])
        self.assertEqual(observed['contracts']['PDF_CAPTION_COLOR'], '000000')
        self.assertEqual(observed['contracts']['PDF_CAPTION_LABEL_WEIGHT'], 'normal')
        legacy, _, _ = self.make('legacy-wrapper')
        _, observed = self.observed_build(legacy, None)
        self.assertEqual(observed['contracts'], dict.fromkeys(expected))

    def test_prior_generated_wrapper_masks_invalid_profile_negative_control(self):
        project, _, _ = self.make('prior-wrapper', kind='report', language='english')
        wrapper = project / 'build.sh'
        prior, replaced = re.subn(r'^export CONTENT_PROFILE=.*$',
                                  'export CONTENT_PROFILE="report"',
                                  wrapper.read_text(), count=1, flags=re.M)
        self.assertEqual(replaced, 1)
        self.assertNotEqual(prior, wrapper.read_text())
        wrapper.write_text(prior)
        exit_code, observed = self.observed_build(project, 'exma')
        self.assertEqual(exit_code, 0)
        self.assertEqual(observed['raw'], 'report')
        self.assertEqual(observed['effective'], 'report')
        self.assertEqual(observed['validator_exit'], 0)

    def test_component_packages_are_not_reloaded(self):
        _, source, manifest = self.make(kind='data-report', packages=['longtable'])
        self.assertNotIn(r'\usepackage{longtable}', source)
        self.assertEqual(manifest['package_selections'][0]['loaded_by'], 'flow_tables.tex')

    def test_package_names_may_start_with_digits_and_python_string_is_not_a_sequence(self):
        _, source, _ = self.make(packages=['2up'])
        self.assertIn(r'\usepackage{2up}', source)
        with self.assertRaisesRegex(ValueError, 'sequence'):
            generator.create('general', self.root / 'string-packages', packages='microtype')

    def test_unsafe_package_names_are_rejected_before_creating_paths(self):
        for package in ['../evil', 'foo.sty', 'foo,bar', '[draft]foo', r'foo}\input{evil',
                        'foo\nbar', '$(touch pwned)', '`touch pwned`', '', ' foo', 'a'*129]:
            with self.subTest(package=package), self.assertRaises(ValueError):
                generator.create('general', self.root / 'never', packages=[package])
            self.assertFalse((self.root / 'never').exists())

    def test_existing_empty_directory_and_dangling_symlink_are_preserved(self):
        dest = self.root / 'exists'; dest.mkdir()
        with self.assertRaises(ValueError): generator.create('general', dest)
        self.assertEqual(list(dest.iterdir()), [])
        link = self.root / 'link'; link.symlink_to(self.root / 'missing', target_is_directory=True)
        with self.assertRaises(ValueError): generator.create('general', link)
        self.assertTrue(link.is_symlink())

    def test_race_created_empty_directory_is_not_replaced(self):
        dest = self.root / 'raced'
        original = generator.publish_no_replace
        def race(stage, destination):
            destination.mkdir()
            original(stage, destination)
        with patch.object(generator, 'publish_no_replace', side_effect=race):
            with self.assertRaises(ValueError): generator.create('general', dest)
        self.assertEqual(list(dest.iterdir()), [])

    def test_failed_publication_does_not_delete_unrelated_files(self):
        stage = self.root / 'stage'; stage.mkdir()
        (stage / 'a').write_text('first')
        (stage / 'b').write_text('second')
        dest = self.root / 'dest'
        real_link = generator.os.link
        def fail_on_b(source, target):
            if source.name == 'b':
                (dest / 'user.txt').write_text('keep me')
                raise OSError('simulated failure')
            return real_link(source, target)
        with patch.object(generator.os, 'link', side_effect=fail_on_b):
            with self.assertRaises(OSError): generator.publish_no_replace(stage, dest)
        self.assertEqual((dest / 'user.txt').read_text(), 'keep me')
        self.assertFalse((dest / 'a').exists())
        self.assertTrue((stage / 'a').exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
