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


def inactive_claims(fragment):
    return ('% ' + fragment + '\n', r'\verb|' + fragment + '|\n',
            r'\begin{verbatim}' + '\n' + fragment + '\n' + r'\end{verbatim}' + '\n')


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

    def test_paragraph_policy_claim_after_core_loading_is_rejected(self):
        # A late definition mentions the public hook but cannot configure the
        # class policy already selected by the core. Both native fixtures must
        # reject that false coverage claim before any engine runs.
        declaration = r'\def\lakitparagraphstyle{block}'
        owner = r'\input{preamble.tex}'
        for language in ('hebrew', 'english'):
            with self.subTest(language=language):
                metadata, source = next(item for item in self.fixtures
                                        if item[0]['family'] == 'core'
                                        and item[0]['language'] == language)
                self.assertEqual(source.count(declaration), 1)
                self.assertLess(source.index(declaration), source.index(owner))
                mutated = source.replace(declaration, '', 1).replace(owner, owner + '\n' + declaration, 1)
                self.assertIn('lakitparagraphstyle: authored hook declaration does not precede its owner',
                              validate_fixture_source(metadata, mutated))

    def test_inactive_precore_declaration_cannot_hide_a_real_late_policy(self):
        declaration = r'\def\lakitparagraphstyle{block}'
        owner = r'\input{preamble.tex}'
        for language in ('hebrew', 'english'):
            metadata, source = next(item for item in self.fixtures
                                    if item[0]['family'] == 'core'
                                    and item[0]['language'] == language)
            late = source.replace(declaration, '', 1).replace(owner, owner+'\n'+declaration, 1)
            for inactive in inactive_claims(declaration):
                with self.subTest(language=language, inactive=inactive):
                    self.assertIn('lakitparagraphstyle: authored hook declaration does not precede its owner',
                                  validate_fixture_source(metadata, inactive+late))

    def test_inactive_owner_mentions_do_not_precede_a_valid_policy(self):
        for language in ('hebrew', 'english'):
            metadata, source = next(item for item in self.fixtures
                                    if item[0]['family'] == 'core'
                                    and item[0]['language'] == language)
            for inactive in inactive_claims(r'\input{preamble.tex}'):
                with self.subTest(language=language, inactive=inactive):
                    self.assertEqual(validate_fixture_source(metadata, inactive+source), [])

    def test_inactive_input_cannot_claim_a_missing_architectural_asset(self):
        owner = r'\input{preamble.tex}'
        for language in ('hebrew', 'english'):
            metadata, source = next(item for item in self.fixtures
                                    if item[0]['family'] == 'core'
                                    and item[0]['language'] == language)
            removed = source.replace(owner, '')
            for inactive in inactive_claims(owner):
                with self.subTest(language=language, inactive=inactive):
                    self.assertIn('assets/preamble.tex: declared architectural asset is not input by the actual fixture',
                                  validate_fixture_source(metadata, inactive+removed))

    def test_inactive_api_mention_cannot_claim_actual_source_link_use(self):
        for language in ('hebrew', 'english'):
            metadata, source = next(item for item in self.fixtures
                                    if item[0]['family'] == 'source-links'
                                    and item[0]['language'] == language)
            removed = source.replace(r'\sourcelink', r'\RemovedSourceLink')
            for inactive in inactive_claims(r'\sourcelink{https://example.org}{Source}'):
                with self.subTest(language=language, inactive=inactive):
                    self.assertIn('assets/document_components.tex:sourcelink: loaded-only API claim lacks actual use',
                                  validate_fixture_source(metadata, inactive+removed))

    def test_hidden_control_characters_are_rejected_even_in_inactive_source(self):
        metadata, source = next(item for item in self.fixtures
                                if item[0]['family'] == 'core' and item[0]['language'] == 'english')
        for character in ('\x00', '\x08', '\x0b'):
            for inactive in inactive_claims(character):
                with self.subTest(character=ord(character), inactive=inactive):
                    self.assertIn('fixture contains an unintended control character',
                                  validate_fixture_source(metadata, inactive+source))

    def test_header_callback_claim_without_active_shell_is_rejected(self):
        metadata, source = next(item for item in self.fixtures
                                if item[0]['family'] == 'topicrail' and item[0]['language'] == 'english')
        mutated = source.replace(r'\pagestyle{STtopic}', r'\pagestyle{empty}')
        self.assertIn('assets/topicrail.tex:STdrawrail: loaded-only API claim lacks actual use',
                      validate_fixture_source(metadata, mutated))


if __name__ == '__main__':
    unittest.main(verbosity=2)
