#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Original project code; scope and terms: ../LICENSING.md.
"""Positive and negative controls for catalog QA/evidence, without TeX engines."""
from __future__ import annotations
import copy
from contextlib import redirect_stdout
from dataclasses import replace
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.dont_write_bytecode = True
import studio_matrix as matrix
import catalog_coverage
from architecture_contract import ASSET_SPECS, HOOK_SPECS
from template_registry import load_catalog, iter_supported_requests


class AcceptanceContracts(unittest.TestCase):
    """Unit proof of the bridge; synthetic result rows are never engine evidence."""
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix='studio-acceptance-unit-')
        cls.root = matrix.ROOT
        cls.catalog = load_catalog(root=cls.root)
        cls.plan = matrix.prepare_cases(cls.root, Path(cls.temporary.name))
        cls.canonical = matrix.assign_aliases(cls.plan, {
            'unit_scope': 'source-only unit identity; no engines, renderers or review'})
        cls.results = [
            {'id': row['id'], 'build_fingerprint_sha256': row['build_fingerprint_sha256'],
             'build': {'actual_exit': 0, 'timed_out': False}, 'waivers': [],
             'changed_input_files': [], 'actual_use_contract': {'errors': []},
             'page_count': 1, 'pdf_sha256': 'a' * 64, 'visual_claim': False,
             'renders': {backend: {'actual_exit': 0, 'timed_out': False,
                                  'pages': [{'page': 1, 'sha256': 'b' * 64}]}
                         for backend in matrix.BACKENDS}}
            for row in cls.canonical]
        cls.reader_path = Path(cls.temporary.name) / 'reader-preview'
        cls.reader_preview = matrix.source_preview(cls.reader_path, theme='reader')
        cls.reader_plan = json.loads((cls.reader_path / 'case-plan.json').read_text())
        cls.reader_results = [{**copy.deepcopy(cls.results[0]), 'id': row['id'],
                               'build_fingerprint_sha256': row['build_fingerprint_sha256']}
                              for row in cls.reader_plan if row['id'] == row['canonical_case']]

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def bridge(self, *, plan=None, results=None, catalog=None, theme_filter=None):
        return catalog_coverage.acceptance_coverage(self.root, catalog or self.catalog,
            self.plan if plan is None else plan, results, theme_filter=theme_filter)

    def assert_blocked(self, report):
        self.assertEqual(report['status'], 'fail')
        self.assertFalse(report['all_acceptance_ids_pass'])
        self.assertTrue(report['errors'])
        self.assertFalse(report['visual_claim'])

    def test_all49_declarations_pin432_requests_and366_aliases_without_runtime_claim(self):
        report = self.bridge()
        self.assertEqual(report['errors'], [])
        self.assertEqual(report['status'], 'declared')
        self.assertEqual(report['declared_acceptance_ids'], 49)
        self.assertEqual(report['passed_acceptance_ids'], 0)
        self.assertFalse(report['all_acceptance_ids_pass'])
        self.assertFalse(report['visual_claim'])
        self.assertEqual(len(self.plan), 432)
        self.assertEqual(len(self.canonical), 366)
        self.assertEqual(sum(row['category'] == 'composition' for row in self.plan), 396)
        self.assertEqual(sum(row.get('request', {}).get('theme') is None
                             for row in self.plan if row['category'] == 'composition'), 66)
        for record in report['records']:
            self.assertTrue(record['bindings'], record['id'])
            self.assertEqual(record['executions'], [])
            for binding in record['bindings']:
                self.assertRegex(binding['input_inventory_sha256'], '^[0-9a-f]{64}$')
                self.assertRegex(binding['build_fingerprint_sha256'], '^[0-9a-f]{64}$')

    def test_actual_reader_preview_preserves102_cases_without_full_runtime_claim(self):
        preview = self.reader_preview
        self.assertEqual(preview['theme_filter'], 'reader')
        self.assertEqual(preview['requested_compositions'], 66)
        self.assertEqual(preview['declared_cases'], 102)
        self.assertEqual(preview['unique_source_build_inputs_estimate'], 102)
        self.assertTrue(preview['source_unchanged'])
        self.assertFalse(preview['engine_invoked'])
        self.assertFalse(preview['renderer_invoked'])
        report = preview['acceptance_coverage']
        self.assertEqual(report['errors'], [])
        self.assertEqual(report['coverage_scope'], 'explicit-theme-subset')
        self.assertEqual(report['theme_filter'], 'reader')
        self.assertEqual(report['declared_acceptance_ids'], 49)
        self.assertEqual(report['required_acceptance_ids'], 48)
        self.assertEqual(report['not_requested_acceptance_ids'], 1)
        self.assertEqual([row['id'] for row in report['records'] if not row['required']],
                         ['theme:reference:runtime'])
        self.assertTrue(all(row['status'] == 'not-requested' for row in report['records'] if not row['required']))
        self.assertFalse(report['scoped_acceptance_ids_pass'])
        self.assertFalse(report['all_acceptance_ids_pass'])

    def test_synthetic_reader_results_pass_local_scope_but_never_all49(self):
        report = self.bridge(plan=self.reader_plan, results=self.reader_results, theme_filter='reader')
        self.assertEqual(report['errors'], [])
        self.assertEqual(report['passed_acceptance_ids'], 48)
        self.assertTrue(report['scoped_acceptance_ids_pass'])
        self.assertFalse(report['all_acceptance_ids_pass'])
        self.assertFalse(report['visual_claim'])
        for ident in ('theme:core:runtime', 'theme:academic:runtime', 'theme:custom:runtime',
                      'theme:clean:runtime', 'theme:legacy-clean:runtime'):
            row = next(row for row in report['records'] if row['id'] == ident)
            self.assertTrue(row['required'])
            self.assertEqual(row['status'], 'pass')

    def test_subset_scope_cannot_waive_missing_requested_or_component_cases(self):
        populations = (
            self.reader_plan[1:],
            [row for row in self.reader_plan if row.get('family') != 'core'],
            [row for row in self.reader_plan if row.get('family') != 'legacy-clean'],
        )
        for plan in populations:
            with self.subTest(population=len(plan)):
                retained = {row['canonical_case'] for row in plan}
                results = [row for row in self.reader_results if row['id'] in retained]
                report = self.bridge(plan=plan, results=results, theme_filter='reader')
                self.assert_blocked(report)
                self.assertFalse(report['scoped_acceptance_ids_pass'])
                if not any(row.get('family') == 'core' for row in plan):
                    core = next(row for row in report['records'] if row['id'] == 'theme:core:runtime')
                    self.assertTrue(core['required'])
                    self.assertEqual(core['status'], 'blocked')
        results = copy.deepcopy(self.reader_results)
        results[0]['renders']['poppler']['actual_exit'] = 1
        self.assert_blocked(self.bridge(plan=self.reader_plan, results=results, theme_filter='reader'))

    def test_selected_core_and_reference_theme_ids_cannot_become_not_requested(self):
        for selected in ('core', 'reference'):
            with self.subTest(selected=selected):
                plan = [row for row in self.plan if row['category'] != 'composition'
                        or row['request']['theme'] == selected]
                retained = {row['canonical_case'] for row in plan}
                results = [row for row in self.results if row['id'] in retained]
                scoped = self.bridge(plan=plan, results=results, theme_filter=selected)
                self.assertEqual(scoped['errors'], [])
                self.assertTrue(scoped['scoped_acceptance_ids_pass'])
                self.assertFalse(scoped['all_acceptance_ids_pass'])
                missing = [row for row in plan if row['category'] != 'composition'
                           and row.get('family') != selected]
                retained = {row['canonical_case'] for row in missing}
                results = [row for row in results if row['id'] in retained]
                report = self.bridge(plan=missing, results=results, theme_filter=selected)
                self.assert_blocked(report)
                required = next(row for row in report['records'] if row['id'] == 'theme:' + selected + ':runtime')
                self.assertTrue(required['required'])
                self.assertEqual(required['status'], 'blocked')
                self.assertTrue(any('uncovered acceptance ID: theme:' + selected in error
                                    for error in report['errors']))

    def test_subset_cannot_change_its_theme_scope_or_become_complete_evidence(self):
        for scope in (None, 'core', 'reference', '', False, 0, [], 'unknown'):
            with self.subTest(scope=scope):
                report = self.bridge(plan=self.reader_plan, results=self.reader_results, theme_filter=scope)
                self.assert_blocked(report)
                self.assertFalse(report['scoped_acceptance_ids_pass'])
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            matrix.write_json(folder / 'matrix-result.json', {
                'scope': 'explicit-theme-subset', 'theme_filter': 'reader',
                'acceptance_coverage': self.bridge(plan=self.reader_plan,
                    results=self.reader_results, theme_filter='reader')})
            with patch.object(matrix, 'verify_matrix') as verify:
                with self.assertRaisesRegex(ValueError, 'complete catalog matrix'):
                    matrix.seal_matrix(folder, candidate_sha='a' * 64)
                verify.assert_not_called()
            self.assertFalse((folder / 'matrix-release-receipt.json').exists())

    def test_local_runner_uses_scoped_gate_with_unit_commands_and_no_engines(self):
        # Mock command/dependency rows exercise runner wiring only. Real sources
        # are generated, but these synthetic rows are never release evidence.
        def synthetic_execution(root, evidence, row, env):
            return {**copy.deepcopy(self.results[0]), 'id': row['id'],
                    'build_fingerprint_sha256': row['build_fingerprint_sha256']}
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary) / 'local-reader'
            with patch.object(matrix, 'collect_identity', return_value={'unit_scope': 'no actual dependencies'}), \
                 patch.object(matrix, 'execute_case', side_effect=synthetic_execution), redirect_stdout(io.StringIO()):
                actual_exit = matrix.run_matrix(folder, theme='reader')
            self.assertEqual(actual_exit, 0)
            runtime = json.loads((folder / 'matrix-result.json').read_text())
            self.assertEqual(runtime['declared_cases'], 102)
            self.assertEqual(runtime['unique_builds'], 102)
            self.assertTrue(runtime['all_builds_and_renders_pass'])
            self.assertTrue(runtime['acceptance_coverage']['scoped_acceptance_ids_pass'])
            self.assertFalse(runtime['acceptance_coverage']['all_acceptance_ids_pass'])

    def test_synthetic_results_gate_all49_without_claiming_visual_review(self):
        report = self.bridge(results=self.results)
        self.assertEqual(report['errors'], [])
        self.assertEqual(report['status'], 'pass')
        self.assertEqual(report['passed_acceptance_ids'], 49)
        self.assertTrue(report['all_acceptance_ids_pass'])
        self.assertFalse(report['visual_claim'])
        self.assertEqual(report['catalog_sha256'], self.catalog.sha256)
        self.assertEqual(report['case_plan_sha256'], matrix.json_digest(self.plan))
        indexed = {row['id']: row for row in self.results}
        for record in report['records']:
            for execution in record['executions']:
                self.assertEqual(execution['case_result_sha256'],
                    matrix.json_digest(indexed[execution['canonical_case']]))
        aliases = [row for row in self.plan if row['id'] != row['canonical_case']]
        bindings = [item for row in report['records'] for item in row['bindings']]
        self.assertTrue(all(any(item['case'] == alias['id']
                               and item['canonical_case'] == alias['canonical_case']
                               for item in bindings) for alias in aliases))

    def test_unknown_missing_or_misbound_acceptance_ids_are_rejected(self):
        first = self.catalog.templates[0]
        for acceptance in ((*first.acceptance, 'template:report:invented'),
                           first.acceptance[:-1],
                           ('template:wrong:native', *first.acceptance[1:])):
            with self.subTest(acceptance=acceptance):
                changed = replace(self.catalog, templates=(replace(first, acceptance=acceptance),
                                                          *self.catalog.templates[1:]))
                contract = catalog_coverage.acceptance_contract(changed)
                self.assertTrue(contract['errors'])
                self.assert_blocked(self.bridge(catalog=changed, results=self.results))

    def test_uncovered_id_cannot_pass_even_with_successful_existing_results(self):
        missing_kind = self.catalog.templates[0].id
        plan = [row for row in copy.deepcopy(self.plan)
                if row.get('request', {}).get('kind') != missing_kind]
        retained = {row['canonical_case'] for row in plan}
        results = [row for row in self.results if row['id'] in retained]
        report = self.bridge(plan=plan, results=results)
        self.assert_blocked(report)
        self.assertTrue(any('uncovered acceptance ID: template:' + missing_kind in error
                            for error in report['errors']))

    def test_missing_duplicate_extra_execution_population_rejects_all_ids(self):
        for results in (self.results[1:], [*self.results, self.results[0]],
                        [*self.results, {**self.results[0], 'id': 'not-a-canonical-case'}]):
            report = self.bridge(results=results)
            self.assert_blocked(report)
            self.assertEqual(report['passed_acceptance_ids'], 0)

    def test_failed_build_and_each_renderer_block_their_acceptance_ids(self):
        for target in ('build', 'mupdf', 'poppler'):
            with self.subTest(target=target):
                results = copy.deepcopy(self.results)
                command = results[0]['build'] if target == 'build' else results[0]['renders'][target]
                command['actual_exit'] = 1
                report = self.bridge(results=results)
                self.assert_blocked(report)
                self.assertLess(report['passed_acceptance_ids'], 49)
        results = copy.deepcopy(self.results)
        del results[0]['renders']['poppler']
        self.assert_blocked(self.bridge(results=results))

    def test_exit_timeout_contract_and_changed_input_failures_never_pass(self):
        mutations = (
            {'build': {'actual_exit': False, 'timed_out': False}},
            {'build': {'actual_exit': 0, 'timed_out': None}},
            {'build': {'actual_exit': 0, 'timed_out': True}},
            {'waivers': ['unit waiver']}, {'changed_input_files': ['main.tex']},
            {'contract_error': 'wrong PDF direction'},
            {'actual_use_contract': {'errors': ['fixture hook unused']}},
            {'build_fingerprint_sha256': 'f' * 64},
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                results = copy.deepcopy(self.results)
                results[0].update(mutation)
                self.assert_blocked(self.bridge(results=results))

    def test_actual_pdf_and_each_renderer_page_binding_are_required(self):
        for mutation in ({'page_count': True}, {'page_count': 0},
                         {'pdf_sha256': 'not-a-hash'}, {'pdf_sha256': 'A' * 64}):
            with self.subTest(mutation=mutation):
                results = copy.deepcopy(self.results)
                results[0].update(mutation)
                self.assert_blocked(self.bridge(results=results))
        for backend in matrix.BACKENDS:
            for pages in ([], [{'page': True, 'sha256': 'b' * 64}],
                          [{'page': 2, 'sha256': 'b' * 64}], [{'page': 1, 'sha256': 'bad'}]):
                with self.subTest(backend=backend, pages=pages):
                    results = copy.deepcopy(self.results)
                    results[0]['renders'][backend]['pages'] = pages
                    self.assert_blocked(self.bridge(results=results))

    def test_malformed_result_records_fail_closed_without_runtime_claim(self):
        for mutation in ({'build': None}, {'renders': []}, {'actual_use_contract': None},
                         {'renders': {'mupdf': None, 'poppler': None}}):
            with self.subTest(mutation=mutation):
                results = copy.deepcopy(self.results)
                results[0].update(mutation)
                self.assert_blocked(self.bridge(results=results))
        for pages in (None, [None]):
            results = copy.deepcopy(self.results)
            results[0]['renders']['mupdf']['pages'] = pages
            self.assert_blocked(self.bridge(results=results))

    def test_unknown_component_owner_cannot_read_or_claim_arbitrary_files(self):
        index = next(index for index, row in enumerate(self.plan)
                     if row.get('family') == 'clean')
        plan = copy.deepcopy(self.plan)
        plan[index]['architecture_assets'].append('/etc/passwd')
        report = self.bridge(plan=plan, results=self.results)
        self.assert_blocked(report)
        self.assertTrue(any('unknown acceptance source owner' in error for error in report['errors']))

    def test_pdf_or_renderer_hash_changes_change_preserved_bridge_fingerprint(self):
        baseline = self.bridge(results=self.results)
        for mutation in ('pdf', 'mupdf', 'poppler'):
            results = copy.deepcopy(self.results)
            if mutation == 'pdf':
                results[0]['pdf_sha256'] = 'c' * 64
            else:
                results[0]['renders'][mutation]['pages'][0]['sha256'] = 'c' * 64
            changed = self.bridge(results=results)
            self.assertEqual(changed['errors'], [])
            self.assertNotEqual(matrix.json_digest(baseline), matrix.json_digest(changed))

    def test_recipe_composer_snapshot_and_copied_owner_hash_cannot_drift(self):
        plan = copy.deepcopy(self.plan)
        plan[0]['creation_provenance']['recipe']['composer_id'] = 'invented'
        self.assert_blocked(self.bridge(plan=plan, results=self.results))
        plan = copy.deepcopy(self.plan)
        owner = next(name for name in plan[0]['input_inventory'] if name.endswith('preamble.tex'))
        plan[0]['input_inventory'][owner]['sha256'] = 'f' * 64
        self.assert_blocked(self.bridge(plan=plan, results=self.results))
        plan = copy.deepcopy(self.plan)
        plan[0]['request']['kind'] = 'unknown-kind'
        self.assert_blocked(self.bridge(plan=plan, results=self.results))

    def test_aliases_cannot_change_source_entrypoint_or_build_identity(self):
        index = next(index for index, row in enumerate(self.plan)
                     if row['id'] != row['canonical_case'])
        for mutation in ({'canonical_case': 'missing'}, {'canonical_case': self.plan[index]['id']},
                         {'build_fingerprint_sha256': 'f' * 64}, {'tex_name': 'other.tex'},
                         {'category': 'component'}, {'build_settings': {'UNDECLARED': 'value'}}):
            with self.subTest(mutation=mutation):
                plan = copy.deepcopy(self.plan)
                plan[index].update(mutation)
                self.assert_blocked(self.bridge(plan=plan, results=self.results))

    def test_examples_and_manual_themes_require_their_exact_declared_owners(self):
        example_index = next(index for index, row in enumerate(self.plan)
                             if row['category'] == 'example')
        plan = copy.deepcopy(self.plan)
        plan[example_index]['architecture_assets'] = []
        self.assert_blocked(self.bridge(plan=plan, results=self.results))
        clean_index = next(index for index, row in enumerate(self.plan)
                           if row.get('family') == 'clean')
        plan = copy.deepcopy(self.plan)
        plan[clean_index]['architecture_assets'] = []
        self.assert_blocked(self.bridge(plan=plan, results=self.results))


class MatrixContracts(unittest.TestCase):
    def test_all_native_fixture_metadata_survives_json_roundtrip(self):
        # The runtime plan is persisted as JSON and compared strictly with
        # freshly generated declarations at verification/sealing. Test the
        # actual fixture owner, rather than normalizing the comparison gate.
        from architecture_contract import SUPPORTED_MAIN_LANGUAGES
        from studio_matrix_fixtures import fixture_families, write_fixture
        families = fixture_families()
        observed = set()
        with tempfile.TemporaryDirectory(prefix='studio-fixture-json-') as temporary:
            folder = Path(temporary)
            for family in families:
                for language in SUPPORTED_MAIN_LANGUAGES:
                    with self.subTest(family=family, language=language):
                        project = folder / (family + '-' + language)
                        metadata = write_fixture(matrix.ROOT, project, family, language)
                        observed.add((family, language))
                        persisted = project.parent / (project.name + '.json')
                        matrix.write_json(persisted, metadata)
                        restored = json.loads(persisted.read_text(encoding='utf-8'))
                        self.assertEqual(metadata, restored,
                                         'fixture metadata must preserve strict JSON types')
                        self.assertEqual(restored['family'], family)
                        self.assertEqual(restored['language'], language)
                        self.assertTrue(restored['architecture_assets'])
                        if family == 'topicrail':
                            self.assertEqual(restored['indirect_public_usage'],
                                             {'assets/topicrail.tex': ['STdrawrail', 'STgetname']})
        self.assertEqual(observed, {(family, language) for family in families
                                    for language in SUPPORTED_MAIN_LANGUAGES})

    def test_complete_requests_derive_from_catalog_and_language_owner(self):
        catalog = load_catalog()
        expected = [row.as_dict() for row in iter_supported_requests(catalog)]
        self.assertEqual(matrix.expected_requests(), expected)
        self.assertEqual(len(expected), 396)
        self.assertEqual(sum(row['theme'] is None for row in expected), 66)
        self.assertEqual({row['language'] for row in expected},
                         {'english', 'hebrew', 'english-with-hebrew', 'hebrew-with-english', 'bilingual'})
        self.assertEqual({row['main_language'] for row in expected if row['language'] == 'bilingual'},
                         {'hebrew', 'english'})

    def test_legacy_explicit_theme_selection_preserves_all_routes(self):
        for theme in ('reader', 'core', 'custom', 'academic', 'reference'):
            rows = matrix.expected_requests(theme=theme)
            self.assertEqual(len(rows), 66)
            self.assertEqual({row['theme'] for row in rows}, {theme})
            self.assertEqual(len({(row['kind'], row['layout']) for row in rows}), 11)

    def test_all_assets_examples_and_owned_apis_receive_assignments(self):
        result = catalog_coverage.coverage_report()
        self.assertEqual(result['errors'], [])
        self.assertEqual(len(result['assets']), len(ASSET_SPECS))
        self.assertEqual(len(result['examples']), len(load_catalog().examples))
        self.assertIn('not execution', result['meaning'])

    def test_new_unmapped_asset_fails_coverage(self):
        changed = dict(catalog_coverage.ASSET_COVERAGE)
        changed.pop('assets/clean_variant.tex')
        with patch.object(catalog_coverage, 'ASSET_COVERAGE', changed):
            self.assertTrue(catalog_coverage.coverage_report()['errors'])

    def test_new_unmapped_public_api_fails_coverage(self):
        changed = dict(catalog_coverage.PUBLIC_API_COVERAGE)
        changed['assets/preamble.tex'] += ('inventedHook',)
        with patch.object(catalog_coverage, 'PUBLIC_API_COVERAGE', changed):
            self.assertTrue(catalog_coverage.coverage_report()['errors'])

    def test_every_hook_has_explicit_positive_negative_and_native_visual_case(self):
        rows = catalog_coverage.hook_coverage()
        self.assertEqual({row['name'] for row in rows}, {hook.name for hook in HOOK_SPECS})
        self.assertEqual(len(rows), 30)
        for row in rows:
            self.assertTrue(row['positive_controls'])
            self.assertTrue(row['negative_controls'])
            self.assertEqual(row['native_languages'], ['hebrew', 'english'])
            self.assertTrue(row['fixture_family'])
            self.assertIn('supplied separately', row['meaning'])

    def test_new_unmapped_configuration_hook_fails_coverage(self):
        changed = dict(catalog_coverage.HOOK_FAMILIES)
        changed.pop('ReferenceMathScriptScriptSize')
        with patch.object(catalog_coverage, 'HOOK_FAMILIES', changed):
            self.assertTrue(catalog_coverage.coverage_report()['errors'])

    def test_exact_fingerprint_changes_for_each_complete_build_input(self):
        inputs = {'main.tex': {'sha256': 'a' * 64, 'mode': 420, 'size': 7},
                  'build.sh': {'sha256': 'b' * 64, 'mode': 493, 'size': 9},
                  'preamble.tex': {'sha256': 'c' * 64, 'mode': 420, 'size': 13}}
        settings = {'CONTENT_PROFILE': 'report'}
        identity = {'tools': {'lualatex': 'd' * 64}, 'fonts': {'font.ttf': 'e' * 64},
                    'environment': {'REPRO': {'defined': False, 'value': None}}}
        baseline = matrix.build_fingerprint(inputs, settings, identity)
        for name in inputs:
            changed = copy.deepcopy(inputs)
            changed[name]['sha256'] = 'f' * 64
            self.assertNotEqual(baseline, matrix.build_fingerprint(changed, settings, identity))
        for name in ('tools', 'fonts', 'environment'):
            changed = copy.deepcopy(identity)
            changed[name] = {'different': True}
            self.assertNotEqual(baseline, matrix.build_fingerprint(inputs, settings, changed))
        self.assertNotEqual(baseline, matrix.build_fingerprint(inputs, {'CONTENT_PROFILE': 'generic'}, identity))

    def test_metadata_provenance_does_not_erase_alias_requests(self):
        inputs = {'main.tex': {'sha256': 'a' * 64, 'mode': 420, 'size': 1}}
        rows = [{'id': 'one', 'category': 'composition', 'input_inventory': inputs,
                 'build_settings': {}, 'tex_name': 'main.tex', 'request': {'theme': None}},
                {'id': 'two', 'category': 'composition', 'input_inventory': inputs,
                 'build_settings': {}, 'tex_name': 'main.tex', 'request': {'theme': 'reader'}}]
        canonical = matrix.assign_aliases(rows, {'identity': 'same'})
        self.assertEqual([row['id'] for row in canonical], ['one'])
        self.assertEqual([row['canonical_case'] for row in rows], ['one', 'one'])
        self.assertIsNone(rows[0]['request']['theme'])
        self.assertEqual(rows[1]['request']['theme'], 'reader')

    def test_different_entrypoint_or_managed_wrapper_never_aliases(self):
        base = {'id': 'one', 'category': 'composition', 'input_inventory': {},
                'build_settings': {}, 'tex_name': 'main.tex'}
        for change in ({'tex_name': 'other.tex'}, {'category': 'component'}):
            rows = [copy.deepcopy(base), {**copy.deepcopy(base), **change, 'id': 'two'}]
            self.assertEqual(len(matrix.assign_aliases(rows, {})), 2)

    def test_input_inventory_includes_extra_copied_assets_and_wrapper_modes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in ('main.tex', 'build.sh', 'theme.tex', 'README.md', 'project.json'):
                (root / name).write_text(name)
            (root / 'build.sh').chmod(0o755)
            actual = matrix.project_build_inputs(root)
            self.assertEqual(set(actual), {'main.tex', 'build.sh', 'theme.tex'})
            self.assertEqual(actual['build.sh']['mode'], 0o755)

    def test_source_inventory_detects_contents_mode_population_and_symlink(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            file = root / 'source.tex'
            file.write_text('original')
            original = matrix.inventory(root)
            file.chmod(0o755)
            self.assertNotEqual(original, matrix.inventory(root))
            file.write_text('changed')
            self.assertNotEqual(original, matrix.inventory(root))
            (root / 'link').symlink_to(file)
            with self.assertRaises(ValueError):
                matrix.inventory(root)

    def test_evidence_paths_reject_absolute_parent_and_symlink(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'source').write_text('safe')
            for value in ('../source', '/tmp/source', 'folder\\source', 'a//b', 'a/./b', 'a\nb'):
                with self.assertRaises(ValueError):
                    matrix.confined(root, value)
            (root / 'link').symlink_to(root / 'source')
            with self.assertRaises(ValueError):
                matrix.confined(root, 'link')
            self.assertEqual(matrix.confined(root, 'source'), root / 'source')

    def test_genuine_command_captures_actual_exit_log_and_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            row = matrix.command([sys.executable, '-c', 'print("actual output"); raise SystemExit(7)'],
                                 root / 'command.log', env={}, cwd=root, timeout=10)
            self.assertEqual(row['actual_exit'], 7)
            self.assertFalse(row['timed_out'])
            self.assertEqual((root / row['log']).read_text(), 'actual output\n')
            self.assertEqual(row['log_sha256'], matrix.digest(root / row['log']))

    def test_command_timeout_has_no_invented_actual_exit(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch('studio_matrix.subprocess.run', side_effect=subprocess.TimeoutExpired('fixture', 1, b'partial')):
                row = matrix.command(['fixture'], root / 'timeout.log', env={}, cwd=root, timeout=1)
            self.assertIsNone(row['actual_exit'])
            self.assertTrue(row['timed_out'])
            self.assertEqual((root / 'timeout.log').read_bytes(), b'partial')

    def test_compile_success_without_every_explicit_renderer_fails(self):
        row = {'build': {'actual_exit': 0, 'timed_out': False}, 'waivers': [],
               'changed_input_files': [], 'renders': {'mupdf': {'actual_exit': 0, 'timed_out': False}}}
        self.assertFalse(matrix.case_ok(row))
        row['renders']['poppler'] = {'actual_exit': 0, 'timed_out': False}
        self.assertTrue(matrix.case_ok(row))
        for mutation in ({'waivers': ['a waiver']}, {'changed_input_files': ['main.tex']},
                         {'contract_error': 'wrong PDF language'}):
            self.assertFalse(matrix.case_ok({**row, **mutation}))

    def test_boolean_exit_or_missing_timeout_proof_is_not_actual_success(self):
        row = {'build': {'actual_exit': 0, 'timed_out': False}, 'waivers': [],
               'changed_input_files': [], 'renders': {name: {'actual_exit': 0, 'timed_out': False}
                                                      for name in matrix.BACKENDS}}
        self.assertTrue(matrix.case_ok(row))
        for key in ('build', 'mupdf', 'poppler'):
            changed = copy.deepcopy(row)
            record = changed['build'] if key == 'build' else changed['renders'][key]
            record['actual_exit'] = False
            self.assertFalse(matrix.case_ok(changed))
            record['actual_exit'] = 0
            record['timed_out'] = None
            self.assertFalse(matrix.case_ok(changed))

    def test_unset_empty_and_effective_environment_values_do_not_alias(self):
        identities = [{'environment': {'PDF_CAPTION_LABEL_WEIGHT': value}}
                      for value in ({'defined': False, 'value': None},
                                    {'defined': True, 'value': ''},
                                    {'defined': True, 'value': 'normal'})]
        self.assertEqual(len({matrix.build_fingerprint({}, {}, identity) for identity in identities}), 3)

    def test_evidence_seal_has_no_self_hash_cycle(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'proof.json').write_text('{}')
            expected = matrix.evidence_pins(root)
            (root / 'matrix-release-receipt.json').write_text('{}')
            self.assertEqual(expected, matrix.evidence_pins(root))
            (root / 'proof.json').write_text('{"changed": true}')
            self.assertNotEqual(expected, matrix.evidence_pins(root))

    def test_sealing_requires_actual_exact_candidate_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(ValueError, 'exact candidate'):
                matrix.seal_matrix(Path(temporary))
        for value in ('', 'f' * 63, 'F' * 64, 'not-a-hash'):
            with self.assertRaises(ValueError):
                matrix.source_archive_identity(value)

    def test_seal_validator_rejects_missing_duplicate_or_misbound_replays(self):
        # Isolate the seal binding validator. These are temporary unit records,
        # never executed/compiled/reviewed evidence or a release acceptance claim.
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            folder = root / 'cases' / 'unit'
            primary = folder / 'review-mupdf'
            primary.mkdir(parents=True)
            pdf = folder / 'unit.pdf'
            pdf.write_bytes(b'unit binding bytes, not a PDF')
            review = primary / 'review.json'
            review.write_text('{"unit": true}')
            log = folder / 'replay-mupdf.log'
            log.write_text('unit binding log')
            case = {'id': 'unit', 'pdf': pdf.relative_to(root).as_posix(),
                    'pdf_sha256': matrix.digest(pdf), 'page_count': 1,
                    'renders': {'mupdf': {'review': review.relative_to(root).as_posix()}}}
            runtime = {'execution_source_root': str(matrix.ROOT), 'cases': [case]}
            matrix.write_json(root / 'matrix-result.json', runtime)
            common = {'status': 'pass', 'candidate_sha256': 'a' * 64,
                      'source_inventory_sha256': 'b' * 64, 'requested_compositions': 1,
                      'unique_builds': 1, 'unique_pdf_pages': 1, 'primary_reviewed_pages': 1,
                      'runtime_matrix_sha256': matrix.digest(root / 'matrix-result.json'), 'errors': [],
                      'declared_acceptance_ids': 49, 'passed_acceptance_ids': 49,
                      'acceptance_coverage_sha256': 'c' * 64}
            replay = {'case': 'unit', 'pdf_sha256': matrix.digest(pdf), 'review_sha256': matrix.digest(review),
                      'renderer_backend': 'mupdf', 'dpi': 144, 'page_count': 1, 'actual_replay_exit': 0,
                      'command': {'argv': [sys.executable, str(matrix.ROOT / 'scripts/render_review.py'), 'verify',
                                           str(pdf), '--review', str(review), '--rerender'],
                                  'actual_exit': 0, 'timed_out': False, 'log': log.name,
                                  'log_sha256': matrix.digest(log)}}
            original = {**common, 'primary_same_backend_replays': [replay],
                        'evidence_files': matrix.evidence_pins(root)}
            matrix.write_json(root / 'matrix-release-receipt.json', original)
            with patch.object(matrix, 'verify_matrix', side_effect=lambda *a, **kw: copy.deepcopy(common)):
                self.assertEqual(matrix.verify_seal(root)['errors'], [])
                for changed in ([], [replay, replay], [{**replay, 'case': 'wrong'}],
                                [{**replay, 'pdf_sha256': 'f' * 64}],
                                [{**replay, 'review_sha256': 'f' * 64}],
                                [{**replay, 'renderer_backend': 'poppler'}],
                                [{**replay, 'dpi': 72}], [{**replay, 'page_count': 2}],
                                [{**replay, 'actual_replay_exit': False}]):
                    matrix.write_json(root / 'matrix-release-receipt.json',
                                      {**original, 'primary_same_backend_replays': changed})
                    self.assertTrue(matrix.verify_seal(root)['errors'], changed)
                for field in ('declared_acceptance_ids', 'passed_acceptance_ids', 'acceptance_coverage_sha256'):
                    changed = {**original, field: None}
                    matrix.write_json(root / 'matrix-release-receipt.json', changed)
                    self.assertTrue(any('sealed receipt field differs: ' + field == error
                                        for error in matrix.verify_seal(root)['errors']))


if __name__ == '__main__':
    unittest.main()
