#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Original project code; scope and terms: ../LICENSING.md.
"""Declared QA coverage, separate from measured execution and human review.

The catalog enumerates recipes; the architecture owns assets and public APIs.
This bridge attaches executable fixtures to those owners. A declaration is not
a test result. New owners/APIs must receive an explicit bridge before release.
"""
from __future__ import annotations
import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
import sys
sys.dont_write_bytecode = True
from architecture_contract import ASSET_SPECS, HOOK_SPECS, effective_public_symbols

ROOT = Path(__file__).resolve().parent.parent

# These are QA assignments, never another template or capability registry.
# A component loaded by a project is not automatically exercised by its body.
ASSET_COVERAGE = {
    'assets/preamble.tex': ('core', 'scripts/test_language_runtime.py', 'scripts/test_academic_runtime.py', 'scripts/test_paragraph_style.py'),
    'assets/exam_components.tex': ('exam-clean', 'scripts/test_language_runtime.py'),
    'assets/topicrail.tex': ('topicrail', 'scripts/test_v4310_runtime.py', 'scripts/test_topicrail_runtime.py'),
    'assets/clean_theme.tex': ('exam-clean', 'scripts/test_language_runtime.py'),
    'assets/reader_theme.tex': ('reader', 'scripts/test_generated_runtime.py'),
    'assets/academic_theme.tex': ('academic', 'scripts/test_academic_runtime.py'),
    'assets/reference_columns.tex': ('reference-all', 'scripts/test_reference_runtime.py', 'scripts/test_paragraph_style.py'),
    'assets/reference_shell.tex': ('reference-all', 'scripts/test_reference_runtime.py'),
    'assets/reference_components.tex': ('reference-all', 'scripts/test_reference_runtime.py'),
    'assets/reference_theme.tex': ('reference-all', 'scripts/test_reference_runtime.py', 'scripts/test_editorial_boxes.py'),
    'assets/document_components.tex': ('source-links', 'scripts/test_generated_runtime.py'),
    'assets/deferred_notes.tex': ('deferred-notes', 'scripts/test_deferred_notes_runtime.py'),
    'assets/flow_tables.tex': ('flow-tables', 'scripts/test_language_runtime.py'),
    'assets/clean_variant.tex': ('legacy-clean', 'scripts/test_language_runtime.py'),
}

# Explicit inventory means an added public hook cannot inherit an unexamined
# asset-wide assertion. Tests below validate that each named suite still exists.
PUBLIC_API_COVERAGE = {
    'assets/preamble.tex': ('doclang', 'englishprose', 'hebrewprose', 'lakitcaptionnumbering'),
    'assets/exam_components.tex': ('qlabel', 'pts', 'finalans', 'srcfig', 'srcfigdir'),
    'assets/topicrail.tex': ('STdirRTL', 'STdirLTR', 'STrailwidth', 'STrailangle', 'STnames', 'STgetname', 'STdrawrail'),
    'assets/reference_columns.tex': ('referencecolumns', 'referencewide', 'ReferenceColumnCount', 'ReferenceColumnGap', 'ReferenceColumnRule', 'ReferenceColumnSkip', 'ReferenceBodyFontSize', 'ReferenceBodyBaseline', 'ReferenceSelectBodyFont', 'ReferenceMathFontSize', 'ReferenceMathScriptSize', 'ReferenceMathScriptScriptSize'),
    'assets/reference_shell.tex': ('ReferenceTitle', 'ReferenceShortTitle', 'ReferenceSubtitle', 'ReferenceAuthor', 'ReferenceDate', 'makereferencetitle'),
    'assets/reference_components.tex': ('referenceentry', 'referencenote', 'referencewarning', 'referenceformula', 'referenceqa', 'referenceqaseries', 'referencesolutionpart', 'referencequestion', 'referencesolution', 'referencepurpose', 'referenceconditions', 'referencefigcap', 'referencetabcap', 'referencefigure', 'referencetable'),
    'assets/document_components.tex': ('sourcelink', 'glossaryentry', 'framedtable', 'semanticframedtable', 'framedtablewidth'),
    'assets/deferred_notes.tex': ('DeclareDocNote', 'DocNoteMark', 'PrintDocNotes'),
    'assets/flow_tables.tex': ('flowtable',),
}

# The exact names below are a QA coverage contract. Architectural ownership and
# types still come from HOOK_SPECS. Arbitrary content/style hooks do not acquire
# invented invalid TeX values: their negative control removes an authored hook
# and proves that the fixture may no longer claim it was exercised.
HOOK_FAMILIES = {
    **dict.fromkeys(('lakitdocumentclass', 'lakitclassoptions', 'lakitgeometryoptions',
                     'lakitlinespread', 'lakittocdepth', 'lakitsecnumdepth', 'lakitparagraphstyle'), 'core'),
    **dict.fromkeys(('lakitlanguageprofile', 'lakitmainlanguage'), 'core'),
    **dict.fromkeys(('ReferenceColumnCount', 'ReferenceColumnGap', 'ReferenceColumnRule',
                     'ReferenceColumnSkip', 'ReferenceBodyFontSize', 'ReferenceBodyBaseline',
                     'ReferenceMathFontSize', 'ReferenceMathScriptSize', 'ReferenceMathScriptScriptSize'), 'reference-all'),
    **dict.fromkeys(('ReferenceTitle', 'ReferenceShortTitle', 'ReferenceSubtitle',
                     'ReferenceAuthor', 'ReferenceDate'), 'reference-all'),
    **dict.fromkeys(('lakitcaptionstyle', 'lakitcaptionlabelstyle', 'lakitcaptionpunctuation'), 'core'),
    **dict.fromkeys(('referencenotestyle', 'referencewarningstyle', 'referenceformulastyle',
                     'referenceqastyle'), 'reference-all'),
}

def acceptance_contract(catalog) -> dict:
    """Closed meanings for catalog IDs; declarations alone are not execution."""
    records, errors, seen = [], [], set()
    for collection in ('templates', 'layouts', 'themes', 'examples'):
        for record in getattr(catalog, collection):
            modes = ('native', 'mixed', 'bilingual') if collection == 'templates' else ('runtime',)
            prefix = {'templates': 'template', 'layouts': 'layout',
                      'themes': 'theme', 'examples': 'example'}[collection]
            expected = tuple(f'{prefix}:{record.id}:{mode}' for mode in modes)
            if record.acceptance != expected:
                errors.append(f'{collection}:{record.id}: unknown or missing closed acceptance IDs')
            if collection == 'themes' and record.exposure != 'generator-supported' and record.id not in ('clean', 'legacy-clean'):
                errors.append(f'theme:{record.id}: no closed manual/legacy acceptance strategy')
            for ident, mode in zip(expected, modes):
                if ident in seen:
                    errors.append('duplicate acceptance ID: ' + ident)
                seen.add(ident)
                records.append({'id': ident, 'collection': collection,
                                'record_id': record.id, 'mode': mode})
    return {'schema': 1, 'meaning': 'closed declared IDs, not executed evidence',
            'records': records, 'errors': errors}


def _json_hash(value) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def acceptance_coverage(root: Path, catalog, plan: list[dict], results: list[dict] | None = None,
                        *, theme_filter: str | None = None) -> dict:
    """Bind declared IDs to generated inputs, canonical aliases and real results.

    Matrix verification owns regeneration, actual files/commands and dependency
    identity. This bridge pins those preserved declarations/results, reuses its
    gate predicate, and never interprets a declaration as a runtime pass.
    """
    from template_registry import resolve_recipe, iter_supported_requests
    from studio_matrix import case_ok
    from studio_matrix_fixtures import fixture_families
    from architecture_contract import SUPPORTED_MAIN_LANGUAGES
    root = Path(root)
    contract = acceptance_contract(catalog)
    errors = list(contract['errors'])
    by_id, tags, hashes = {}, {}, {}
    source_hashes = {}
    theme_by_id = {theme.id: theme for theme in catalog.themes}
    example_by_id = {example.id: example for example in catalog.examples}
    owned_sources = {spec.path for spec in ASSET_SPECS} | {example.asset_path for example in catalog.examples}
    generator_themes = {theme.id for theme in catalog.themes if theme.exposure == 'generator-supported'}
    valid_filter = theme_filter is None or isinstance(theme_filter, str) and theme_filter in generator_themes
    if not valid_filter:
        errors.append('acceptance theme filter must be None or a supported explicit generator theme')
    expected_requests = [request.as_dict() for request in iter_supported_requests(catalog)
                         if theme_filter is None or request.theme == theme_filter] if valid_filter else []
    if [row.get('request') for row in plan if isinstance(row, dict) and row.get('category') == 'composition'] != expected_requests:
        errors.append('acceptance composition population differs from the exact catalog/theme scope')
    if [row.get('example_id') for row in plan if isinstance(row, dict) and row.get('category') == 'example'] != [example.id for example in catalog.examples]:
        errors.append('acceptance example population differs from the exact catalog scope')
    expected_components = [(family, language) for family in fixture_families() for language in SUPPORTED_MAIN_LANGUAGES]
    component_themes = generator_themes.intersection(fixture_families())
    if [(row.get('family'), row.get('language')) for row in plan if isinstance(row, dict) and row.get('category') == 'component'] != expected_components:
        errors.append('acceptance component population differs from the exact native fixture scope')

    def owned_inputs(row, sources):
        if not isinstance(sources, (list, tuple)):
            errors.append(row['id'] + ': acceptance owner list differs')
            return
        for source in sources:
            if not isinstance(source, str) or source not in owned_sources:
                errors.append(row['id'] + ': unknown acceptance source owner')
                continue
            if source not in source_hashes:
                source_hashes[source] = hashlib.sha256((root / source).read_bytes()).hexdigest()
            # Generator/component projects use basenames; original examples
            # retain the assets/ directory. Both destinations are intentional.
            copied = row['input_inventory'].get(source, row['input_inventory'].get(Path(source).name, {}))
            if not isinstance(copied, dict) or copied.get('sha256') != source_hashes[source]:
                errors.append(row['id'] + ': acceptance source input differs: ' + source)

    for row in plan:
        if not isinstance(row, dict):
            errors.append('acceptance matrix case must be an object')
            continue
        ident = row.get('id')
        if not isinstance(ident, str) or not ident or ident in by_id:
            errors.append('missing or duplicate acceptance matrix case ID')
            continue
        by_id[ident] = row
        tags[ident] = set()
        inputs = row.get('input_inventory')
        if not isinstance(inputs, dict) or not inputs:
            errors.append(ident + ': acceptance requires generated input inventory')
            continue
        hashes[ident] = _json_hash(inputs)
        category = row.get('category')
        if category == 'composition':
            request = row.get('request', {})
            try:
                recipe = resolve_recipe(root=root, catalog=catalog, **request)
            except (ValueError, TypeError) as exc:
                errors.append(ident + ': invalid acceptance recipe request: ' + str(exc))
                continue
            metadata = row.get('creation_provenance', {})
            if (not isinstance(metadata, dict) or metadata.get('recipe') != recipe.as_dict()
                    or not isinstance(metadata.get('registry'), dict)
                    or metadata['registry'].get('sha256') != catalog.sha256):
                errors.append(ident + ': acceptance resolved recipe/composer snapshot differs')
            owned_inputs(row, recipe.copy_plan)
            profile = recipe.language_profile
            mode = ('native' if profile in ('hebrew', 'english') else
                    'bilingual' if profile == 'bilingual' else 'mixed')
            tags[ident].update({('templates', recipe.kind, mode),
                                ('layouts', recipe.layout, 'runtime'),
                                ('themes', recipe.theme, 'runtime')})
        elif category == 'example':
            example = example_by_id.get(row.get('example_id'))
            if (example is None or row.get('tex_name') != example.asset_path
                    or row.get('architecture_assets') != list(example.architecture_assets)):
                errors.append(ident + ': acceptance example source/owners differ')
                continue
            owned_inputs(row, (example.asset_path, *example.architecture_assets))
            tags[ident].add(('examples', example.id, 'runtime'))
        elif category == 'component':
            theme = theme_by_id.get(row.get('family'))
            if theme is not None:
                if theme.asset_path is not None and theme.asset_path not in row.get('architecture_assets', []):
                    errors.append(ident + ': acceptance theme owner is not exercised')
                owned_inputs(row, row.get('architecture_assets', []))
                if theme.id == 'custom' and 'theme.tex' not in inputs:
                    errors.append(ident + ': acceptance custom overlay input is missing')
                tags[ident].add(('themes', theme.id, 'runtime'))
        else:
            errors.append(ident + ': unknown acceptance case category')

    canonical = {}
    for ident, row in by_id.items():
        original = by_id.get(row.get('canonical_case'))
        if original is None or original.get('canonical_case') != original['id']:
            errors.append(ident + ': acceptance canonical alias is missing or chained')
            continue
        fingerprint = row.get('build_fingerprint_sha256')
        if (not isinstance(fingerprint, str) or not re.fullmatch('[0-9a-f]{64}', fingerprint)
                or fingerprint != original.get('build_fingerprint_sha256')
                or row.get('input_inventory') != original.get('input_inventory')
                or any(row.get(key) != original.get(key) for key in ('category', 'tex_name', 'build_settings'))):
            errors.append(ident + ': acceptance alias inputs/build identity differ')
        canonical[original['id']] = original

    observed = {}
    if results is not None:
        for result in results:
            if not isinstance(result, dict):
                errors.append('acceptance execution case must be an object')
                continue
            ident = result.get('id')
            if not isinstance(ident, str) or not ident or ident in observed:
                errors.append('missing or duplicate acceptance execution case ID')
                continue
            observed[ident] = result
        if set(observed) != set(canonical):
            errors.append('acceptance execution population differs from canonical cases')

    declaration_errors = bool(errors)
    def runtime_pass(ident):
        actual = observed.get(ident, {})
        count = actual.get('page_count')
        renders = actual.get('renders')
        use_contract = actual.get('actual_use_contract')
        if (not isinstance(actual.get('build'), dict) or not isinstance(renders, dict)
                or set(renders) != {'mupdf', 'poppler'}
                or not isinstance(use_contract, dict)
                or any(not isinstance(render, dict) or not isinstance(render.get('pages'), list)
                       or any(not isinstance(page, dict) for page in render['pages'])
                       for render in renders.values())):
            return False
        return (not declaration_errors and case_ok(actual) and actual.get('build_fingerprint_sha256') == canonical[ident]['build_fingerprint_sha256']
            and type(count) is int and count > 0
            and isinstance(actual.get('pdf_sha256'), str) and re.fullmatch('[0-9a-f]{64}', actual['pdf_sha256']) is not None
            and use_contract.get('errors') == []
            and all(len(actual['renders'][backend].get('pages', [])) == count
                    and [page.get('page') for page in actual['renders'][backend]['pages']] == list(range(1, count + 1))
                    and all(type(page.get('page')) is int and isinstance(page.get('sha256'), str)
                            and re.fullmatch('[0-9a-f]{64}', page['sha256']) is not None
                            for page in actual['renders'][backend]['pages'])
                    for backend in ('mupdf', 'poppler')))

    records = []
    for spec in contract['records']:
        tag = (spec['collection'], spec['record_id'], spec['mode'])
        matching = [row for ident, row in by_id.items() if tag in tags[ident]]
        not_requested = (valid_filter and theme_filter is not None and not matching
                         and spec['collection'] == 'themes' and spec['record_id'] in generator_themes
                         and spec['record_id'] != theme_filter and spec['record_id'] not in component_themes)
        if not matching and not not_requested:
            errors.append('uncovered acceptance ID: ' + spec['id'])
        bindings = [{'case': row['id'], 'canonical_case': row.get('canonical_case'),
                     'build_fingerprint_sha256': row.get('build_fingerprint_sha256'),
                     'input_inventory_sha256': hashes.get(row['id'])} for row in matching]
        originals = list(dict.fromkeys(row.get('canonical_case') for row in matching))
        executions = []
        if results is not None:
            for ident in originals:
                actual = observed.get(ident)
                passed = ident in canonical and runtime_pass(ident)
                executions.append({'canonical_case': ident, 'status': 'pass' if passed else 'blocked',
                    'case_result_sha256': _json_hash(actual) if actual is not None else None,
                    'pdf_sha256': actual.get('pdf_sha256') if actual is not None else None})
            if any(row['status'] != 'pass' for row in executions):
                errors.append('acceptance ID has missing/failed actual build/render results: ' + spec['id'])
        status = ('not-requested' if not_requested else 'declared' if results is None else
                  'pass' if matching and all(row['status'] == 'pass' for row in executions) else 'blocked')
        records.append({**spec, 'required': not not_requested, 'bindings': bindings, 'executions': executions, 'status': status})
    passed = sum(record['status'] == 'pass' for record in records)
    required = sum(record['required'] for record in records)
    scoped_pass = results is not None and not errors and passed == required
    return {'schema': 1, 'catalog_sha256': catalog.sha256, 'case_plan_sha256': _json_hash(plan),
            'theme_filter': theme_filter,
            'coverage_scope': 'all-supported-compositions' if theme_filter is None else 'explicit-theme-subset',
            'scope': 'declarations-only' if results is None else 'actual-build-render-results',
            'meaning': 'ID bindings do not replace complete matrix verification or primary human review',
            'visual_claim': False, 'records': records, 'declared_acceptance_ids': len(records),
            'required_acceptance_ids': required, 'not_requested_acceptance_ids': len(records) - required,
            'passed_acceptance_ids': passed, 'scoped_acceptance_ids_pass': scoped_pass,
            'all_acceptance_ids_pass': theme_filter is None and scoped_pass and passed == len(records),
            'status': 'fail' if errors else 'declared' if results is None else 'pass', 'errors': errors}


def _method_exists(root: Path, reference: str) -> bool:
    path, _, method = reference.partition(':')
    if not (root / path).is_file():
        return False
    tree = ast.parse((root / path).read_text(encoding='utf-8'))
    return any(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == method
               for node in ast.walk(tree))


def hook_coverage() -> list[dict]:
    result = []
    for hook in HOOK_SPECS:
        positive = ['scripts/test_component_fixtures.py:test_every_configuration_hook_is_declared_in_native_fixtures',
                    'scripts/test_template_registry.py:test_hook_inventory_all_30_have_explicit_owners_and_scopes']
        negative = ['scripts/test_component_fixtures.py:test_hook_claim_without_declaration_is_rejected']
        runtime = []
        if hook.scope == 'reference-layout':
            positive += ['scripts/test_reference_runtime.py:test_generated_reference_profiles_build_managed_with_native_column_balance']
            negative += ['scripts/test_reference_runtime.py:test_invalid_counts_geometry_and_nesting_fail_in_actual_engine']
            runtime += ['scripts/test_reference_runtime.py']
        elif hook.name in ('lakitlanguageprofile', 'lakitmainlanguage'):
            positive += ['scripts/test_language_runtime.py:test_every_profile_has_real_base_locale_and_restores_it']
            negative += ['scripts/test_language_runtime.py:test_bad_profiles_fail_before_document_loading']
            runtime += ['scripts/test_language_runtime.py']
        elif hook.name == 'lakitparagraphstyle':
            positive += ['scripts/test_paragraph_style.py:test_every_owned_starter_declares_its_genre_policy_before_the_core',
                         'scripts/test_paragraph_style.py:test_generated_native_mixed_and_bilingual_letters_have_flush_reading_edges',
                         'scripts/test_paragraph_style.py:test_indented_papers_preserve_native_heading_and_display_paragraph_boundaries']
            negative += ['scripts/test_paragraph_style.py:test_invalid_enum_is_rejected_instead_of_becoming_an_implicit_style',
                         'scripts/test_paragraph_style.py:test_restoring_the_old_indented_letter_is_detected_by_actual_geometry',
                         'scripts/test_paragraph_style.py:test_invalid_runtime_policy_fails_before_emitting_a_pdf',
                         'scripts/test_component_fixtures.py:test_paragraph_policy_claim_after_core_loading_is_rejected']
            runtime += ['scripts/test_paragraph_style.py']
        elif hook.scope == 'document':
            negative += ['scripts/test_template_registry.py:test_hook_owner_unit_and_phase_are_checked',
                         'scripts/test_template_registry.py:test_declared_starter_fingerprint_hook_and_timing_drift_rejected']
        elif hook.scope == 'reference-shell':
            positive += ['scripts/test_reference_runtime.py:test_localized_semantics_captions_running_heads_and_uniform_center_folios']
            runtime += ['scripts/test_reference_runtime.py']
        elif hook.scope == 'presentation':
            positive += ['scripts/test_caption_styles.py:test_custom_color_requires_exact_declared_style']
            negative += ['scripts/test_caption_styles.py:test_rgb_contract_and_api_bounds']
            runtime += ['scripts/test_academic_runtime.py']
        elif hook.scope == 'reference-presentation':
            runtime += ['scripts/test_reference_runtime.py']
        result.append({'name': hook.name, 'owner': hook.owner, 'scope': hook.scope,
                       'fixture_family': HOOK_FAMILIES.get(hook.name, ''),
                       'native_languages': ['hebrew', 'english'],
                       'positive_controls': positive, 'negative_controls': negative,
                       'runtime_suites': runtime,
                       'runtime_visual_case': 'component-' + HOOK_FAMILIES.get(hook.name, '') + '-{language}',
                       'visual_acceptance': 'actual primary page review and fresh same-backend replay required',
                       'meaning': 'declared controls; execution and observations must be supplied separately'})
    return result


def coverage_report(root: Path = ROOT, *, catalog=None) -> dict:
    from template_registry import load_catalog
    catalog = catalog or load_catalog(root=root)
    acceptance = acceptance_contract(catalog)
    errors = list(acceptance['errors'])
    if set(HOOK_FAMILIES) != {hook.name for hook in HOOK_SPECS}:
        errors.append('configuration hook coverage inventory differs from HOOK_SPECS')
    hooks = hook_coverage()
    for hook in hooks:
        for reference in hook['positive_controls'] + hook['negative_controls']:
            if not _method_exists(root, reference):
                errors.append('missing declared hook control: ' + reference)
    specs = {spec.path: spec for spec in ASSET_SPECS}
    if set(ASSET_COVERAGE) != set(specs):
        errors.append('architecture asset coverage assignments differ from ASSET_SPECS')
    expected_apis = {spec.path: tuple(spec.public_symbols) for spec in ASSET_SPECS if spec.public_symbols}
    if expected_apis != PUBLIC_API_COVERAGE:
        errors.append('public API coverage inventory differs from architectural owners')
    assets = []
    for spec in ASSET_SPECS:
        assignment = ASSET_COVERAGE.get(spec.path, ())
        suites = [name for name in assignment if name.startswith('scripts/')]
        for suite in suites:
            path = root / suite
            if not path.is_file():
                errors.append(f'missing component QA suite: {suite}')
            else:
                try:
                    ast.parse(path.read_text(encoding='utf-8'))
                except (SyntaxError, UnicodeError):
                    errors.append(f'invalid component QA suite: {suite}')
        assets.append({'asset': spec.path, 'role': spec.role,
                       'fixture_family': assignment[0] if assignment else '',
                       'runtime_suites': suites,
                       'owned_public_apis': list(spec.public_symbols),
                       'reexported_public_apis': list(effective_public_symbols(spec))})
    examples = []
    for example in catalog.examples:
        asset = example.asset_path
        if not (root / asset).is_file():
            errors.append(f'missing catalog example fixture: {asset}')
        unknown = set(example.architecture_assets) - set(specs)
        if unknown:
            errors.append(f'{example.id}: unknown architecture assets {sorted(unknown)}')
        examples.append({'example': example.id, 'source': asset,
                         'assets': list(example.architecture_assets),
                         'runtime_fixture': 'catalog-example:' + example.id})
    declared = {example.asset_path for example in catalog.examples}
    actual = {path.relative_to(root).as_posix() for path in (root / 'assets').glob('example_*.tex')}
    if declared != actual:
        errors.append('catalog examples do not exactly cover bundled example_*.tex')
    return {'schema': 1, 'meaning': 'QA assignments, not execution or visual attestations',
            'assets': assets, 'examples': examples, 'configuration_hooks': hooks,
            'acceptance_ids': acceptance['records'],
            'public_api_count': sum(len(spec.public_symbols) for spec in ASSET_SPECS),
            'errors': errors, 'status': 'complete' if not errors else 'incomplete'}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    result = coverage_report()
    text = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        args.output.write_text(text, encoding='utf-8')
    else:
        print(text, end='')
    return int(bool(result['errors']))


if __name__ == '__main__':
    raise SystemExit(main())
