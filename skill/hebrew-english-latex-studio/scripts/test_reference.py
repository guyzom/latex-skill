#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Original project code; scope and terms: ../LICENSING.md.
"""Creation and ownership controls for reusable reference-sheet layouts.

These no-engine tests verify independent layout/theme choices, fail-before-write
validation, and creation-time provenance. Actual column placement, mathematical
ink, navigation and page boundaries live in test_reference_runtime.py.
"""
from __future__ import annotations

from dataclasses import replace
import contextlib
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
import architecture_contract as contract
import check_content_density as density
import heading_source
import new_document

ROOT = Path(__file__).resolve().parent.parent
PROFILES = (('english', 'english'), ('hebrew', 'hebrew'),
            ('english-with-hebrew', 'english'), ('hebrew-with-english', 'hebrew'),
            ('bilingual', 'english'), ('bilingual', 'hebrew'))
REFERENCE_ASSETS = ('reference_columns.tex', 'reference_components.tex',
                    'reference_shell.tex', 'reference_theme.tex')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class ReferenceCreation(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='studio-reference-create-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def create(self, name, **kwargs):
        destination = self.root/name
        new_document.create('formula-sheet', destination, **kwargs)
        return destination, json.loads((destination/'project.json').read_text())

    def assert_local_topic_contract(self, source, body_count):
        """Check authored topic containment without depending on a TeX engine."""
        clean = heading_source.clean_source(source)
        headings = list(heading_source.headings(clean))
        self.assertEqual(len(headings), 16*body_count)
        self.assertEqual(sum(h.command == 'section' for h in headings), 12*body_count)
        self.assertEqual(sum(h.command == 'subsection' for h in headings), 4*body_count)
        self.assertTrue(all(h.command in ('section', 'subsection') and not h.starred
                            and h.depth == 2 and h.explicit for h in headings))
        self.assertNotRegex(clean, r'\\begin\s*\{referencewide\}')
        for name in ('lakitsecnumdepth', 'lakittocdepth'):
            self.assertEqual(re.findall(r'\\def\\'+name+r'\{([^{}]+)\}', clean), ['2'])

        entries, start = [], None
        for token in re.finditer(r'\\(begin|end)\s*\{referenceentry\}', clean):
            if token[1] == 'begin':
                self.assertIsNone(start, 'the default sample must not nest topic entries')
                start = token.end()
            else:
                self.assertIsNotNone(start, 'topic entry closed without a matching start')
                entries.append((start, token.start()))
                start = None
        self.assertIsNone(start, 'topic entry is left open')
        self.assertEqual(len(entries), 12*body_count)
        contained = []
        for begin, end in entries:
            local = [h for h in headings if begin <= h.offset < end]
            self.assertTrue(local, 'each atomic topic must include its native heading')
            self.assertEqual(local[0].command, 'section')
            self.assertTrue(all(h.command == 'subsection' for h in local[1:]),
                            'independent topics need separate entries')
            contained.extend(local)
        self.assertEqual(contained, headings, 'a heading escaped its atomic topic')

    def assert_default_note_locales(self, source, main, body_count):
        """Each scientific starter note belongs to its own body's prose locale."""
        clean = heading_source.clean_source(source)
        languages, notes = [], []
        for boundary, name in re.findall(
                r'\\(begin|end)\s*\{(englishprose|hebrewprose|referencenote|referencewarning)\}',clean):
            if name.endswith('prose'):
                locale = name[:-5]
                if boundary == 'begin':
                    languages.append(locale)
                else:
                    self.assertTrue(languages,'prose scope closed before it opened')
                    self.assertEqual(languages.pop(),locale,'prose scopes crossed')
            elif boundary == 'begin':
                notes.append(languages[-1] if languages else main)
        self.assertEqual(languages,[],'a prose-language scope leaked past its body')
        expected = [main] if body_count==1 else [main,
                    'hebrew' if main=='english' else 'english']
        self.assertEqual(notes,expected,'starter notes escaped their scientific body language')

    def assert_created_typography_contract(self, project, manifest):
        """Bind a real created project's local size hooks to its provenance."""
        source = (project/'main.tex').read_text()
        layout = manifest['layout']
        for macro, field in (
                ('ReferenceBodyFontSize', 'body_font_size'),
                ('ReferenceBodyBaseline', 'body_baseline'),
                ('ReferenceMathFontSize', 'math_font_size'),
                ('ReferenceMathScriptSize', 'math_script_size'),
                ('ReferenceMathScriptScriptSize', 'math_scriptscript_size')):
            self.assertEqual(re.findall(r'\\def\\'+macro+r'\{([^{}]+)\}', source),
                             [layout[field]], 'source and typography declarations disagree')
            if macro.startswith('ReferenceMath'):
                self.assertEqual(layout['declared_hooks'][macro], layout[field],
                                 'declared math hook and typography metadata disagree')
        self.assertEqual(manifest['initial_source_sha256']['main.tex'], digest(project/'main.tex'))
        for template in manifest['templates']:
            self.assertEqual(manifest['template_sha256'][template], digest(ROOT/'assets'/template))
        self.assertEqual(manifest['copied_assets']['reference_columns.tex'],
                         digest(project/'reference_columns.tex'))
        self.assertEqual(layout['font_policy'],
            'core Hebrew fonts; reference math uses scalable Computer Modern designs; ' +
            (manifest['theme']+' English uses Latin Modern Roman'
             if manifest['theme'] in ('academic', 'reference')
             else 'English follows core language-profile fonts'))

    def test_both_presets_preserve_all_language_profiles_and_asset_provenance(self):
        for layout, count, size, baseline, math_sizes in (
                ('reference-compact', 3, '6.3', '7.8', ('6.25', '4.375', '3.125')),
                ('reference-readable', 2, '9', '11', ('8.75', '6.125', '4.375'))):
            for profile, main in PROFILES:
                name = layout+'-'+profile+'-'+main
                with self.subTest(layout=layout, profile=profile, main=main):
                    project, manifest = self.create(name, layout=layout, language=profile,
                        main_language=main if profile == 'bilingual' else None)
                    self.assertEqual(manifest['theme'], 'reference')
                    self.assertEqual(manifest['language_profile'], profile)
                    self.assertEqual(manifest['main_language'], main)
                    self.assertEqual(manifest['base_direction'], 'rtl' if main == 'hebrew' else 'ltr')
                    self.assertEqual(manifest['layout']['preset'], layout)
                    self.assertEqual(manifest['layout']['columns'], count)
                    self.assertEqual(manifest['layout']['body_font_size'], size)
                    self.assertEqual(manifest['layout']['body_baseline'], baseline)
                    self.assertEqual(tuple(manifest['layout'][field] for field in
                        ('math_font_size', 'math_script_size', 'math_scriptscript_size')), math_sizes)
                    self.assertEqual(manifest['layout']['folio_layout'], 'center')
                    self.assertEqual(manifest['layout']['folio_band'], 'footer')
                    hooks = manifest['layout']['declared_hooks']
                    self.assertEqual(hooks['lakitsecnumdepth'], '2')
                    self.assertEqual(hooks['lakittocdepth'], '2')
                    geometry = dict(part.split('=', 1) for part in
                                    hooks['lakitgeometryoptions'].split(','))
                    self.assertEqual(geometry, {'left': '8mm', 'right': '8mm',
                        'top': '12mm', 'bottom': '16mm', 'headheight': '10pt',
                        'headsep': '3mm', 'footskip': '7mm'})
                    self.assertFalse(manifest['font_binaries_included'])
                    source = (project/'main.tex').read_text()
                    self.assertIn(r'\def\ReferenceColumnCount{'+str(count)+'}', source)
                    self.assertIn(r'\def\ReferenceBodyFontSize{'+size+'}', source)
                    self.assertIn(r'\def\ReferenceBodyBaseline{'+baseline+'}', source)
                    self.assertIn(r'\def\lakitlanguageprofile{'+profile+'}', source)
                    self.assert_created_typography_contract(project, manifest)
                    self.assert_local_topic_contract(source, 2 if profile == 'bilingual' else 1)
                    self.assert_default_note_locales(source,main,2 if profile=='bilingual' else 1)
                    # Reject structural regressions in the actual generated
                    # source with the same checks used for the valid project.
                    if profile == main:
                        for field, defect in (('math_font_size', 'incorrect source size'),
                                              ('math_script_size', 'incorrect script size'),
                                              ('math_scriptscript_size', 'incorrect nested script size')):
                            changed = {**manifest, 'layout': {**manifest['layout'], field: '1'}}
                            with self.subTest(rejected_typography_defect=defect), self.assertRaises(AssertionError):
                                self.assert_created_typography_contract(project, changed)
                        forged = {**manifest, 'initial_source_sha256':
                                  {**manifest['initial_source_sha256'], 'main.tex': '0'*64}}
                        with self.subTest(rejected_typography_provenance=True), self.assertRaises(AssertionError):
                            self.assert_created_typography_contract(project, forged)
                        forged = {**manifest, 'layout': {**manifest['layout'], 'declared_hooks':
                                  {**manifest['layout']['declared_hooks'], 'ReferenceMathFontSize': '1'}}}
                        with self.subTest(rejected_declared_math_hook=True), self.assertRaises(AssertionError):
                            self.assert_created_typography_contract(project, forged)
                        mutations = {
                            'missing atomic topic wrapper': source.replace(
                                r'\begin{referenceentry}', '', 1).replace(
                                r'\end{referenceentry}', '', 1),
                            'third heading level': source.replace(
                                r'\subsection{', r'\subsubsection{', 1),
                            'third numbering level': source.replace(
                                r'\def\lakitsecnumdepth{2}', r'\def\lakitsecnumdepth{3}', 1),
                            'third bookmark level': source.replace(
                                r'\def\lakittocdepth{2}', r'\def\lakittocdepth{3}', 1),
                            'default wide region': source.replace(
                                r'\begin{referencecolumns}',
                                r'\begin{referencewide}\end{referencewide}'+'\n'+
                                r'\begin{referencecolumns}', 1),
                        }
                        for defect, mutated in mutations.items():
                            with self.subTest(rejected_source_defect=defect), self.assertRaises(AssertionError):
                                self.assert_local_topic_contract(mutated, 1)
                        other = 'hebrew' if main=='english' else 'english'
                        wrong_locale = source.replace(r'\begin{referencenote}',
                            fr'\begin{{{other}prose}}\begin{{referencenote}}',1).replace(
                            r'\end{referencenote}',fr'\end{{referencenote}}\end{{{other}prose}}',1)
                        with self.subTest(rejected_note_locale=other), self.assertRaises(AssertionError):
                            self.assert_default_note_locales(wrong_locale,main,1)
                        with self.subTest(rejected_leaked_scope=other), self.assertRaises(AssertionError):
                            self.assert_default_note_locales(source+fr'\begin{{{other}prose}}',main,1)
                    # Actual mixed reference examples previously emitted these
                    # implementation instructions as an extra product page.
                    # The starter should teach its scientific subject in each
                    # language; language-container recipes belong in docs.
                    for leaked in ('A note in Hebrew', 'use a language block with its own direction',
                                   'זוהי הערה קצרה בעברית בתוך מסמך',
                                   'This is a short English note in a predominantly Hebrew document'):
                        self.assertNotIn(leaked, source)
                    for asset in REFERENCE_ASSETS:
                        self.assertEqual(manifest['copied_assets'][asset], digest(ROOT/'assets'/asset))
                        self.assertEqual(digest(project/asset), digest(ROOT/'assets'/asset))
                    for relative, expected in manifest['initial_source_sha256'].items():
                        self.assertEqual(digest(project/relative), expected)
                    self.assertIn('creation-time', manifest['hash_scope'])

    def test_explicit_theme_is_independent_of_reference_layout(self):
        for theme in ('reader', 'core', 'custom', 'academic'):
            with self.subTest(theme=theme):
                project, manifest = self.create('theme-'+theme, layout='reference-readable',
                                               language='english', theme=theme)
                self.assertEqual(manifest['theme'], theme)
                self.assertEqual(manifest['layout']['preset'], 'reference-readable')
                self.assertTrue((project/'reference_columns.tex').exists())
                self.assertTrue((project/'reference_components.tex').exists())
                self.assertTrue((project/'reference_shell.tex').exists())
                self.assertFalse((project/'reference_theme.tex').exists())
                source = (project/'main.tex').read_text()
                self.assertNotIn(r'\input{reference_theme.tex}', source)
                self.assert_created_typography_contract(project, manifest)
                self.assertEqual(manifest['caption_contract']['label_weight'],
                                 'normal')

    def test_legacy_formula_sheet_default_remains_standard_reader(self):
        project, manifest = self.create('legacy', language='english')
        self.assertEqual(manifest['theme'], 'reader')
        self.assertEqual(manifest['layout']['preset'], 'standard')
        self.assertFalse(any((project/asset).exists() for asset in REFERENCE_ASSETS))
        self.assertEqual(manifest['templates'], ['starter_formula_sheet_english.tex'])
        self.assertFalse(any(key.startswith('math_') for key in manifest['layout']))
        self.assertFalse(any(key.startswith('ReferenceMath') for key in manifest['layout']['declared_hooks']))
        self.assertNotIn('ReferenceMath', (project/'main.tex').read_text())

    def test_reference_theme_can_be_selected_without_column_layout(self):
        project, manifest = self.create('theme-only', language='hebrew', theme='reference')
        self.assertEqual(manifest['theme'], 'reference')
        self.assertEqual(manifest['layout']['preset'], 'standard')
        self.assertFalse((project/'reference_components.tex').exists())
        self.assertTrue((project/'reference_theme.tex').exists())
        self.assertFalse((project/'reference_columns.tex').exists())
        self.assertFalse((project/'reference_shell.tex').exists())
        self.assertFalse(any(key.startswith('math_') for key in manifest['layout']))
        self.assertFalse(any(key.startswith('ReferenceMath') for key in manifest['layout']['declared_hooks']))
        self.assertNotIn('ReferenceMath', (project/'main.tex').read_text())

    def test_invalid_layout_and_incompatible_kind_fail_before_directory_creation(self):
        cases = [('formula-sheet', 'reference-tiny'), ('paper', 'reference-compact'),
                 ('report', 'reference-readable'), ('general', 'reference-readable')]
        for index, (kind, layout) in enumerate(cases):
            destination = self.root/f'invalid-{index}'
            with self.subTest(kind=kind, layout=layout), self.assertRaises(ValueError):
                new_document.create(kind, destination, language='english', layout=layout)
            self.assertFalse(destination.exists())

    def test_cli_rejects_invalid_presets_and_language_conflict_without_outputs(self):
        for index, flags in enumerate((['--layout', 'reference-tiny'],
                ['--kind', 'paper', '--layout', 'reference-compact'],
                ['--layout', 'reference-readable', '--language', 'english', '--main-language', 'hebrew'],
                ['--layout', 'reference-readable', '--language', 'bilingual'])):
            destination = self.root/f'cli-invalid-{index}'
            result = subprocess.run([sys.executable, str(ROOT/'scripts/new_document.py'),
                '--kind', 'formula-sheet', '--directory', str(destination), *flags],
                text=True, capture_output=True, timeout=30)
            with self.subTest(flags=flags):
                self.assertEqual(result.returncode, 2, result.stdout+result.stderr)
                self.assertFalse(destination.exists())

    def test_existing_project_is_preserved_on_reference_creation_attempt(self):
        project, _ = self.create('existing', language='english')
        original = {p.name: p.read_bytes() for p in project.iterdir()}
        with self.assertRaisesRegex(ValueError, 'destination already exists'):
            new_document.create('formula-sheet', project, language='hebrew', layout='reference-compact')
        self.assertEqual({p.name: p.read_bytes() for p in project.iterdir()}, original)

    def test_column_package_selection_is_recorded_without_loading_twice(self):
        project, manifest = self.create('provided-package', language='english',
            layout='reference-readable', packages=['multicol', 'multicol'])
        self.assertEqual(manifest['package_selections'], [{'name': 'multicol',
            'loaded_by': 'reference_columns.tex', 'status': 'already-provided'}])
        self.assertNotIn(r'\usepackage{multicol}', (project/'main.tex').read_text())

    def test_build_wrapper_keeps_explicit_contract_values_authoritative(self):
        project, _ = self.create('wrapper', language='hebrew', layout='reference-compact')
        # Run the actual wrapper against a disposable observer instead of merely
        # matching shell text. Empty/invalid settings must reach the managed
        # builder rather than silently be replaced with permissive defaults.
        fake = self.root/'observer'
        (fake/'scripts').mkdir(parents=True)
        (fake/'scripts/build.sh').write_text('#!/usr/bin/env bash\n'
            'python3 - <<\'PY\'\nimport json,os\n'
            'print(json.dumps({k:os.environ.get(k) for k in '
            '["EXPECTED_PAPER","PDF_FOLIO_LAYOUT","PDF_FOLIO_BAND",'
            '"PDF_CAPTION_COLOR","PDF_CAPTION_LABEL_WEIGHT"]}))\nPY\n')
        import os
        default = dict(os.environ, HEBREW_LATEX_SKILL_ROOT=str(fake))
        keys = ('EXPECTED_PAPER', 'PDF_FOLIO_LAYOUT', 'PDF_FOLIO_BAND',
                'PDF_CAPTION_COLOR', 'PDF_CAPTION_LABEL_WEIGHT')
        for key in keys:
            default.pop(key, None)
        run = subprocess.run(['bash', str(project/'build.sh')], env=default,
                             text=True, capture_output=True, timeout=30)
        self.assertEqual(run.returncode, 0, run.stdout+run.stderr)
        self.assertEqual(json.loads(run.stdout), dict(zip(keys, ('a4','center','footer','000000','normal'))))
        explicit = dict(default, **dict(zip(keys, ('letter','','header','FF0011','invalid'))))
        run = subprocess.run(['bash', str(project/'build.sh')], env=explicit,
                             text=True, capture_output=True, timeout=30)
        self.assertEqual(run.returncode, 0, run.stdout+run.stderr)
        self.assertEqual(json.loads(run.stdout), {key: explicit[key] for key in keys})

    def advisory(self, source, profile='report'):
        path = self.root/'density.tex'
        path.write_text(source, encoding='utf-8')
        with contextlib.redirect_stdout(io.StringIO()) as capture:
            status = density.main([str(path)], profile=profile)
        self.assertEqual(status, 0, capture.getvalue())
        return capture.getvalue()

    def test_reference_structure_advisory_counts_real_frames_and_tables_once(self):
        source = r'''\section{First}
\begin{referencenote}A bounded note.\end{referencenote}
\begin{referencewarning}A bounded caution.\end{referencewarning}
\begin{referenceformula}A central formula.\end{referenceformula}
\begin{referenceqa}A question and its answer.\end{referenceqa}
\begin{referenceqaseries}
\referencequestion{The series itself is not an outer frame.}
\begin{referencesolutionpart}One actual step frame.\end{referencesolutionpart}
\end{referenceqaseries}
\begin{tabular}{ll}A&B\\\end{tabular}
\begin{tabular*}{100pt}{ll}A&B\\\end{tabular*}
\begin{tablebox}\begin{tabular}{ll}A&B\\\end{tabular}\end{tablebox}
\begin{flowtable}{ll}{Data}{tab:data}\begin{longtable}{ll}A&B\\\end{longtable}\end{flowtable}
\begin{tabular}{l}\begin{tabular}{l}Nested data.\end{tabular}\end{tabular}
\section{Second}
Outside prose.
% \begin{referencewarning}Commented frame.\end{referencewarning}
% \begin{tabular}{l}Commented table.\end{tabular}
\begin{verbatim}
\begin{referencenote}Literal frame.\end{referencenote}
\begin{tabular}{l}Literal table.\end{tabular}
\end{verbatim}
'''
        output = self.advisory(source)
        self.assertRegex(output, r'5 tables .*5 boxes ')
        self.assertNotIn('THIN:', output)
        self.assertNotIn('[OVER-BOX-EMPHASIS]', output)
        self.assertNotIn('OVER-BOX:', output)

    def test_reference_warning_prose_wall_keeps_reading_friction_advisory_live(self):
        wall = r'''\begin{referencewarning}
משך שלב ראשון הוא \en{2ns}, ושלב שני הוא \en{3ns}.
השלב השלישי הוא \en{4ns}, והשלב הרביעי הוא \en{5ns}.
הערכים כאן מוצגים כולם כחלק מפסקה צפופה ללא מבנה.
\end{referencewarning}
'''
        self.assertIn('[BOX-FRICTION]', self.advisory(wall, 'formula-sheet'))
        structured = wall.replace('הערכים כאן מוצגים כולם כחלק מפסקה צפופה ללא מבנה.',
                                  r'\[T=t_1+t_2+t_3+t_4\]')
        self.assertNotIn('[BOX-FRICTION]', self.advisory(structured, 'formula-sheet'))
        literal = '% '+wall.replace('\n', '\n% ')+'\n'+r'\begin{verbatim}'+'\n'+wall+r'\end{verbatim}'
        self.assertNotIn('[BOX-FRICTION]', self.advisory(literal, 'formula-sheet'))


class ReferenceOwnership(unittest.TestCase):
    def test_public_column_and_shell_interfaces_have_single_owners(self):
        owners = {symbol: spec.path for spec in contract.ASSET_SPECS for symbol in spec.public_symbols}
        self.assertEqual(owners['referencecolumns'], 'assets/reference_columns.tex')
        self.assertEqual(owners['referencewide'], 'assets/reference_columns.tex')
        self.assertEqual(owners['ReferenceColumnRule'], 'assets/reference_columns.tex')
        self.assertEqual(owners['makereferencetitle'], 'assets/reference_shell.tex')
        self.assertEqual(owners['referencefigure'], 'assets/reference_components.tex')
        self.assertEqual(owners['referencetable'], 'assets/reference_components.tex')
        self.assertEqual(owners['referenceentry'], 'assets/reference_components.tex')
        self.assertEqual(contract.validate_contract(), ())
        # A presentation layer claiming a physical layout or semantic API must
        # fail the real schema validator. This protects extensibility: it is not
        # a snapshot of private implementation strings.
        for symbol in ('ReferenceColumnCount', 'ReferenceColumnRule', 'referenceentry'):
            mutated = tuple(replace(spec, public_symbols=spec.public_symbols+(symbol,))
                            if spec.path == 'assets/reference_theme.tex' else spec
                            for spec in contract.ASSET_SPECS)
            with patch.object(contract, 'ASSET_SPECS', mutated):
                findings = contract.validate_contract()
            self.assertTrue(any(symbol in finding and 'multiple declared owners' in finding
                                for finding in findings), findings)



class ReferenceHeadingScope(unittest.TestCase):
    """The layout owns heading flow, without replacing theme section styles."""
    def test_heading_wrapper_preserves_native_arguments_and_precedes_title_consumer(self):
        source = heading_source.clean_source((ROOT/'assets/reference_columns.tex').read_text())
        wrapper = source.split(r'\newcommand{\hllpdf@referenceactivateheadings}',1)[1].split(
            r'\providecommand{\hllpdf@referencebodysetup}',1)[0]
        self.assertIn(r'\ifhllpdf@referenceheadingsactive\else',wrapper)
        self.assertIn(r'\let\hllpdf@referenceoriginalstartsection\@startsection',wrapper)
        self.assertIn(r'\hllpdf@referenceoriginalstartsection{##1}{##2}{##3}{##4}{##5}',wrapper)
        self.assertIn(r'{\hllpdf@referenceheadingsetup ##6}',wrapper)
        self.assertNotIn(r'{##6 \hllpdf@referenceheadingsetup}',wrapper,
                         'a theme may consume the title at the end of style argument 6')
        theme = heading_source.clean_source((ROOT/'assets/reference_theme.tex').read_text())
        self.assertIn(r'\color{black}\hllpdf@referencehead}',theme,
                      'the reference theme keeps its native title-consuming ruled style')

    def test_heading_activation_is_guarded_by_actual_reference_layout_scope(self):
        source = heading_source.clean_source((ROOT/'assets/reference_columns.tex').read_text())
        select = source.split(r'\newcommand{\ReferenceSelectBodyFont}',1)[1].split(
            r'\newcommand{\hllpdf@referenceoutercheck}',1)[0]
        self.assertEqual(select.count(r'\hllpdf@referenceactivateheadings'),2)
        self.assertRegex(select,re.escape(r'\ifhllpdf@referencecolumnsactive')+r'\s*'+
            re.escape(r'\hllpdf@referenceactivateheadings'))
        self.assertRegex(select,re.escape(r'\else\ifhllpdf@referencewideactive')+r'\s*'+
            re.escape(r'\hllpdf@referenceactivateheadings'))
        setup = source.split(r'\newcommand{\hllpdf@referenceheadingsetup}',1)[1].split(
            r'\newcommand{\hllpdf@referenceactivateheadings}',1)[0]
        self.assertIn(r'\raggedright',setup)
        self.assertIn(r'\hyphenpenalty=10000\relax',setup)
        self.assertNotIn(r'\exhyphenpenalty',setup,'authored compounds retain native break policy')
        for prohibited in (r'\raggedleft',r'\pardir',r'\bodydir',r'\global'):
            self.assertNotIn(prohibited,setup)


if __name__ == '__main__':
    unittest.main(verbosity=2)
