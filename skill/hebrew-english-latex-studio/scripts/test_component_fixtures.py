#!/usr/bin/env python3
"""Provenance locks for portable actual-use component gallery fixtures."""
from pathlib import Path
import re
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
from architecture_contract import ASSET_SPECS, HOOK_SPECS
from studio_matrix_fixtures import fixture_families, validate_fixture_source, write_fixture

ROOT = Path(__file__).resolve().parent.parent


class ComponentFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix='hll-component-fixtures-')
        cls.root = Path(cls.temporary.name)
        cls.fixtures = []
        for family in fixture_families():
            for language in ('hebrew', 'english'):
                project = cls.root / f'{family}-{language}'
                metadata = write_fixture(ROOT, project, family, language)
                cls.fixtures.append((metadata, (project / 'main.tex').read_text(encoding='utf-8')))

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_every_architectural_asset_has_native_hebrew_and_english_fixture(self):
        for spec in ASSET_SPECS:
            languages = {metadata['main_language'] for metadata, _ in self.fixtures
                         if spec.path in metadata['architecture_assets']}
            self.assertEqual(languages, {'hebrew', 'english'}, spec.path)

    def test_every_owned_api_has_source_backed_actual_use(self):
        for metadata, source in self.fixtures:
            self.assertEqual(validate_fixture_source(metadata, source), [], metadata['family'])
        for spec in ASSET_SPECS:
            covered = {symbol for metadata, _ in self.fixtures
                       for symbol in metadata['public_usage'].get(spec.path, ())}
            self.assertEqual(covered, set(spec.public_symbols), spec.path)

    def test_every_configuration_hook_is_declared_in_native_fixtures(self):
        for language in ('hebrew', 'english'):
            covered = {name for metadata, _ in self.fixtures if metadata['main_language'] == language
                       for name in metadata['configuration_hooks']}
            self.assertEqual(covered, {hook.name for hook in HOOK_SPECS})

    def test_loaded_source_link_without_call_is_rejected(self):
        metadata, source = next(item for item in self.fixtures
                                if item[0]['family'] == 'source-links' and item[0]['language'] == 'english')
        mutated = source.replace(r'\sourcelink', r'\RemovedSourceLink')
        self.assertIn('assets/document_components.tex:sourcelink: loaded-only API claim lacks actual use',
                      validate_fixture_source(metadata, mutated))

    def test_hook_claim_without_declaration_is_rejected(self):
        # This guards provenance for every declared hook. It deliberately
        # does not invent universally invalid TeX content/style values or
        # claim that a metadata mutation is a runtime layout assertion.
        for hook in HOOK_SPECS:
            for language in ('hebrew', 'english'):
                with self.subTest(hook=hook.name, language=language):
                    metadata, source = next(item for item in self.fixtures
                                            if hook.name in item[0]['configuration_hooks']
                                            and item[0]['language'] == language)
                    pattern = rf'(\\(?:def|newcommand|renewcommand|providecommand)\s*\{{?\\){hook.name}\b'
                    mutated, count = re.subn(pattern, lambda match: match.group(1) + 'RemovedHook', source)
                    self.assertGreater(count, 0, hook.name)
                    self.assertIn(f'{hook.name}: hook coverage lacks an authored declaration',
                                  validate_fixture_source(metadata, mutated))

    def test_header_callback_claim_without_active_shell_is_rejected(self):
        metadata, source = next(item for item in self.fixtures
                                if item[0]['family'] == 'topicrail' and item[0]['language'] == 'english')
        mutated = source.replace(r'\pagestyle{STtopic}', r'\pagestyle{empty}')
        self.assertIn('assets/topicrail.tex:STdrawrail: loaded-only API claim lacks actual use',
                      validate_fixture_source(metadata, mutated))


if __name__ == '__main__':
    unittest.main(verbosity=2)
