#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Original project code; scope and terms: ../LICENSING.md.
"""Catalog-derived build/render evidence and a separate human-review gate.

No engine success or generated raster is a human review. The run receipt stays
visual_claim=false. Sealing requires hash-bound primary observations and a fresh
same-backend replay. Build aliases share evidence only for exactly equal source,
wrapper, copied assets, settings and actual dependency/environment identities.
"""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
from contextlib import redirect_stdout, redirect_stderr
sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parent.parent
MATRIX_SCHEMA = 1
BACKENDS = ('mupdf', 'poppler')
DPI = 144
SEMANTIC_ENV = ('SOURCE_DATE_EPOCH', 'TZ', 'LANG', 'LC_ALL', 'LC_CTYPE',
                'TEXINPUTS', 'BIBINPUTS', 'BSTINPUTS', 'TEXMFHOME', 'TEXMFLOCAL',
                'TEXMFCONFIG', 'TEXMFDIST', 'TEXMF', 'TTFONTS', 'OSFONTDIR',
                'LUA_PATH', 'LUA_CPATH', 'openin_any', 'openout_any',
                'HEBREW_LATEX_FONT_DIR', 'PDF_FOLIO_LAYOUT', 'PDF_FOLIO_BAND',
                'PDF_CAPTION_COLOR', 'PDF_CAPTION_LABEL_WEIGHT', 'PDF_REQUIRE_TITLE',
                'PDF_MIN_BOOKMARKS', 'PDF_MIN_BOOKMARK_DEPTH', 'PDF_WARN_NO_OUTLINE_AFTER',
                'DIRECT_NAVIGATION_DESTINATIONS')


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def json_digest(value) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True,
                               indent=2, allow_nan=False) + '\n', encoding='utf-8')


def inventory(root: Path) -> dict:
    result = {}
    for path in sorted(root.rglob('*')):
        if path.is_symlink():
            raise ValueError(f'forbidden inventory symlink: {path.relative_to(root)}')
        if path.is_file():
            result[path.relative_to(root).as_posix()] = {
                'sha256': digest(path), 'mode': path.stat().st_mode & 0o777,
                'size': path.stat().st_size}
    return result


def confined(base: Path, relative: str) -> Path:
    if (not isinstance(relative, str) or not relative or '\\' in relative
            or any(ord(char) < 32 or ord(char) == 127 for char in relative)):
        raise ValueError('invalid evidence path')
    part = Path(relative)
    if part.as_posix() != relative or part.is_absolute() or any(item in ('', '.', '..') for item in part.parts):
        raise ValueError('unsafe evidence path')
    target = base / part
    if target.is_symlink() or any(p.is_symlink() for p in target.parents if p != base.parent):
        raise ValueError('symlink evidence is forbidden')
    if not target.resolve().is_relative_to(base.resolve()):
        raise ValueError('evidence escapes its directory')
    return target


def expected_requests(root: Path = ROOT, theme: str | None = None) -> list[dict]:
    from template_registry import load_catalog, iter_supported_requests
    catalog = load_catalog(root=root)
    rows = [row.as_dict() for row in iter_supported_requests(catalog=catalog, root=root)]
    if theme is not None:
        rows = [row for row in rows if row['theme'] == theme]
    keys = [json_digest(row) for row in rows]
    if not rows or len(keys) != len(set(keys)):
        raise ValueError('empty or duplicate supported catalog requests')
    return rows


def project_build_inputs(project: Path) -> dict:
    # project.json and README are historical provenance, not engine inputs.
    # Every other created file participates, including custom theme and figures.
    return {name: data for name, data in inventory(project).items()
            if name not in ('project.json', 'README.md')}


def build_fingerprint(inputs: dict, settings: dict, identity: dict) -> str:
    return json_digest({'complete_inputs': inputs, 'build_settings': settings,
                        'dependency_and_environment_identity': identity})


def command(argv: list[str], log: Path, *, env: dict, cwd: Path,
            timeout: int = 600) -> dict:
    started = time.monotonic()
    timed_out = False
    try:
        result = subprocess.run(argv, cwd=cwd, env=env, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, timeout=timeout)
        output = result.stdout
        actual_exit = result.returncode
    except subprocess.TimeoutExpired as exc:
        output = exc.stdout or b''
        timed_out = True
        actual_exit = None
    log.write_bytes(output)
    return {'argv': argv, 'actual_exit': actual_exit, 'timed_out': timed_out,
            'elapsed_seconds': round(time.monotonic() - started, 3),
            'log': log.name, 'log_sha256': digest(log)}


def collect_identity(root: Path, evidence: Path, env: dict) -> dict:
    """Pin actual tools, declared TeX roots, format/config files and pinned fonts.

    This is intentionally stronger than hashing only top-level package names:
    transitive .sty/.def/.lua/font changes in the resolved trees invalidate aliases.
    Writable cache locations are operational paths, not dependency identities.
    """
    report_path = evidence / 'environment-report.json'
    result = command([sys.executable, str(root / 'scripts/environment_report.py'),
                      '--output', str(report_path)], evidence / 'environment-report.log',
                     env=env, cwd=root, timeout=180)
    if result['actual_exit'] != 0:
        raise ValueError('actual environment report did not complete successfully')
    report = json.loads(report_path.read_text(encoding='utf-8'))
    if report.get('status') != 'complete' or report.get('errors'):
        raise ValueError('incomplete actual dependency identity')
    roots = {}
    visited_roots = {}
    for variable in ('TEXMFDIST', 'TEXMFLOCAL', 'TEXMFHOME', 'TEXMFCONFIG'):
        process = subprocess.run(['kpsewhich', '-var-value=' + variable], env=env,
                                 cwd=root, capture_output=True, text=True, timeout=20)
        if process.returncode:
            raise ValueError('cannot resolve TeX dependency root: ' + variable)
        value = process.stdout.strip()
        # Unexpanded expressions or multiple search paths cannot be silently
        # treated as a complete tree. The supported runtime uses concrete roots.
        if '$' in value or '{' in value or ';' in value:
            raise ValueError('unresolved TeX dependency root: ' + variable)
        path = Path(value).expanduser() if value else None
        if path is not None and not path.is_absolute():
            path = root / path
        if path is not None and path.exists():
            resolved = str(path.resolve())
            if resolved in visited_roots:
                original = visited_roots[resolved]
                roots[variable] = {'path': resolved, 'alias_of': original,
                                   'sha256': roots[original]['sha256']}
                continue
            # TeX trees commonly contain distribution symlinks. Record their
            # target content rather than modifying or rejecting the toolchain.
            entries = {}
            for item in sorted(path.rglob('*')):
                if item.is_file():
                    entries[item.relative_to(path).as_posix()] = {
                        'sha256': digest(item), 'size': item.stat().st_size}
            roots[variable] = {'path': str(path.resolve()), 'files': entries,
                               'sha256': json_digest(entries)}
            visited_roots[resolved] = variable
        else:
            roots[variable] = {'path': str(path) if path else '', 'files': {},
                               'sha256': json_digest({})}
    from font_paths import font_dir
    fonts = inventory(font_dir())
    resolved_files = {}
    engine_version = report['commands']['lualatex']['version_lines'][0]
    format_engine = 'luahbtex' if 'LuaHBTeX' in engine_version else 'luatex' if 'LuaTeX' in engine_version else None
    if format_engine is None:
        raise ValueError('unrecognized actual LuaLaTeX engine identity')
    for name, options in (('lualatex.fmt', ['--engine=' + format_engine, '--format=fmt']),
                          ('texmf.cnf', ['--all'])):
        found = subprocess.run(['kpsewhich', *options, name], env=env, cwd=root,
                               capture_output=True, text=True, timeout=20)
        paths = [Path(line) for line in found.stdout.splitlines() if line.strip()]
        if found.returncode or not paths:
            raise ValueError('cannot pin actual resolved TeX dependency: ' + name)
        resolved_files[name] = [{'path': str(path.resolve()), 'sha256': digest(path),
                                 'size': path.stat().st_size} for path in paths]
    extra_lookup_roots = {}
    for variable in ('TEXINPUTS', 'BIBINPUTS', 'BSTINPUTS', 'OSFONTDIR', 'TTFONTS'):
        for raw in env.get(variable, '').split(os.pathsep):
            if not raw:
                continue
            name = raw.removeprefix('!!').rstrip('/')
            path = Path(name).expanduser()
            if '$' in name or '{' in name or not path.is_absolute():
                raise ValueError('unresolved or project-relative extra lookup root: ' + variable)
            if path.exists():
                entries = {item.relative_to(path).as_posix(): {'sha256': digest(item), 'size': item.stat().st_size}
                           for item in sorted(path.rglob('*')) if item.is_file()}
            else:
                entries = {}
            extra_lookup_roots.setdefault(variable, []).append({'path': str(path), 'files': entries,
                                                                'sha256': json_digest(entries)})
    import fitz
    version = subprocess.run(['pdftoppm', '-v'], capture_output=True, text=True,
                             env=env, timeout=20)
    if version.returncode:
        raise ValueError('cannot identify actual Poppler renderer')
    renderer_identities = {'mupdf': f'MuPDF {fitz.VersionFitz} / PyMuPDF {fitz.VersionBind}',
                           'poppler': (version.stdout + version.stderr).splitlines()[0]}
    binaries = {}
    for name in ('bash', 'python3'):
        executable = shutil.which(name)
        if not executable:
            raise ValueError('missing identity binary ' + name)
        binaries[name] = digest(Path(executable))
    from architecture_contract import BUILD_ONLY_KEYS
    value = {'schema': 1, 'environment_report_sha256': digest(report_path),
             'environment_report': report, 'tex_trees': roots, 'font_files': fonts,
             'resolved_format_and_configuration_files': resolved_files,
             'extra_lookup_roots': extra_lookup_roots,
             'semantic_environment': {key: {'defined': key in env, 'value': env.get(key)}
                                      for key in dict.fromkeys((*SEMANTIC_ENV, *BUILD_ONLY_KEYS))},
             'binaries': binaries,
             'renderers': renderer_identities}
    write_json(evidence / 'build-identity.json', value)
    return {'build_identity_sha256': digest(evidence / 'build-identity.json'),
            'source_inventory_sha256': json_digest(inventory(root))}


def source_archive_identity(candidate_sha: str | None) -> str | None:
    if candidate_sha is not None and not re.fullmatch(r'[0-9a-f]{64}', candidate_sha):
        raise ValueError('candidate SHA-256 must contain exactly 64 lowercase hexadecimal digits')
    return candidate_sha


def verify_dependency_identity(value: dict) -> list[str]:
    """Recheck actual tools/dependencies without engines, caches or host globals."""
    from font_paths import font_dir
    errors = []
    for name, record in value['environment_report']['commands'].items():
        executable = shutil.which(name)
        if executable is None or digest(Path(executable)) != record['binary_sha256']:
            errors.append('current actual tool binary differs: ' + name)
    for name, expected in value['binaries'].items():
        executable = shutil.which(name)
        if executable is None or digest(Path(executable)) != expected:
            errors.append('current actual runtime binary differs: ' + name)
    if inventory(font_dir()) != value['font_files']:
        errors.append('current actual external font files differ')
    for variable, tree in value['tex_trees'].items():
        if 'alias_of' in tree:
            continue
        path = Path(tree['path']) if tree['path'] else None
        current = ({item.relative_to(path).as_posix(): {'sha256': digest(item), 'size': item.stat().st_size}
                    for item in sorted(path.rglob('*')) if item.is_file()}
                   if path is not None and path.exists() else {})
        if current != tree['files'] or json_digest(current) != tree['sha256']:
            errors.append('actual TeX dependency tree differs: ' + variable)
    for name, entries in value['resolved_format_and_configuration_files'].items():
        for entry in entries:
            path = Path(entry['path'])
            if not path.is_file() or digest(path) != entry['sha256'] or path.stat().st_size != entry['size']:
                errors.append('actual resolved format/configuration differs: ' + name)
    for variable, trees in value['extra_lookup_roots'].items():
        for tree in trees:
            path = Path(tree['path'])
            current = {item.relative_to(path).as_posix(): {'sha256': digest(item), 'size': item.stat().st_size}
                       for item in sorted(path.rglob('*')) if item.is_file()} if path.exists() else {}
            if current != tree['files'] or json_digest(current) != tree['sha256']:
                errors.append('actual extra dependency lookup root differs: ' + variable)
    import fitz
    if value['renderers']['mupdf'] != f'MuPDF {fitz.VersionFitz} / PyMuPDF {fitz.VersionBind}':
        errors.append('current actual MuPDF identity differs')
    return errors


def prepare_cases(root: Path, evidence: Path, *, theme=None) -> list[dict]:
    from new_document import create
    from template_registry import load_catalog
    from studio_matrix_fixtures import fixture_families, write_fixture
    from architecture_contract import SUPPORTED_MAIN_LANGUAGES, resolve_language_profile
    rows = []
    cases = evidence / 'cases'
    cases.mkdir()
    requests = expected_requests(root, theme)
    for index, request in enumerate(requests, 1):
        ident = f'recipe-{index:04d}'
        folder = cases / ident
        folder.mkdir()
        project = folder / 'project'
        output = io.StringIO()
        with redirect_stdout(output), redirect_stderr(output):
            create(request['kind'], project, language=request['language'],
                   main_language=request['main_language'], theme=request['theme'],
                   layout=request['layout'])
        (folder / 'generation.log').write_text(output.getvalue(), encoding='utf-8')
        metadata = json.loads((project / 'project.json').read_text(encoding='utf-8'))
        rows.append({'id': ident, 'category': 'composition', 'request': request,
                     'creation_provenance': metadata, 'project': 'cases/' + ident + '/project',
                     'tex_name': 'main.tex', 'pdf_name': 'main.pdf',
                     'build_settings': {}, 'main_language': metadata.get('main_language', request['main_language'] or ('english' if request['language'].startswith('english') else 'hebrew')),
                     'generation_log_sha256': digest(folder / 'generation.log')})
    catalog = load_catalog(root=root)
    for example in catalog.examples:
        ident = 'example-' + example.id
        folder = cases / ident
        folder.mkdir()
        project = folder / 'project'
        project.mkdir()
        # The complete asset tree is retained as the example's source closure.
        # It contains only source assets in a clean installed candidate.
        shutil.copytree(root / 'assets', project / 'assets')
        tex = project / 'assets' / Path(example.asset_path).name
        authored = tex.read_text(encoding='utf-8')
        explicit_main = re.search(r'\\def\\lakitmainlanguage\{(hebrew|english)\}', authored)
        example_main = resolve_language_profile(example.language_profile,
                                               explicit_main.group(1) if explicit_main else None)
        rows.append({'id': ident, 'category': 'example', 'example_id': example.id,
                     'architecture_assets': list(example.architecture_assets),
                     'project': 'cases/' + ident + '/project',
                     'tex_name': 'assets/' + tex.name, 'pdf_name': 'assets/' + tex.with_suffix('.pdf').name,
                     'build_settings': {}, 'main_language': example_main})
    for family in fixture_families():
        for language in SUPPORTED_MAIN_LANGUAGES:
            ident = 'component-' + family + '-' + language
            folder = cases / ident
            folder.mkdir()
            project = folder / 'project'
            fixture = write_fixture(root, project, family, language)
            rows.append({'id': ident, 'category': 'component',
                         'project': 'cases/' + ident + '/project',
                         'tex_name': 'main.tex', 'pdf_name': 'main.pdf', **fixture})
    for row in rows:
        inputs = project_build_inputs(evidence / row['project'])
        row['input_inventory'] = inputs
        write_json(evidence / 'cases' / row['id'] / 'input-inventory.json', inputs)
    return rows


def assign_aliases(rows: list[dict], identity: dict) -> list[dict]:
    seen = {}
    for row in rows:
        # File location and managed command differ between examples/components.
        # Include these settings instead of falsely merging different entrypoints.
        settings = {'settings': row['build_settings'], 'tex_name': row['tex_name'],
                    'managed_wrapper': row['category'] == 'composition'}
        fingerprint = build_fingerprint(row['input_inventory'], settings, identity)
        row['build_fingerprint_sha256'] = fingerprint
        canonical = seen.setdefault(fingerprint, row['id'])
        row['canonical_case'] = canonical
    return [row for row in rows if row['canonical_case'] == row['id']]


def execute_case(root: Path, evidence: Path, row: dict, env: dict) -> dict:
    import fitz
    folder = evidence / 'cases' / row['id']
    project = evidence / row['project']
    local_env = dict(env, HEBREW_LATEX_SKILL_ROOT=str(root),
                     HEBREW_LATEX_PROJECT_ROOT=str(project), **row['build_settings'])
    if row['category'] == 'composition':
        argv = ['bash', str(project / 'build.sh')]
    else:
        argv = ['bash', str(root / 'scripts/build.sh'), str(project / row['tex_name'])]
    build = command(argv, folder / 'build.log', env=local_env, cwd=project)
    result = {'id': row['id'], 'build_fingerprint_sha256': row['build_fingerprint_sha256'],
              'build': build, 'waivers': [], 'renders': {}, 'visual_claim': False}
    if build['actual_exit'] == 0:
        pdf = project / row['pdf_name']
        with fitz.open(pdf) as document:
            result['page_count'] = len(document)
            result['pdf_lang'] = document.xref_get_key(document.pdf_catalog(), 'Lang')[1]
            required = row.get('expected_pdf', {})
            text = '\n'.join(page.get_text() for page in document)
            uris = {link['uri'] for page in document for link in page.get_links() if 'uri' in link}
            names = document.resolve_names()
            content_errors = []
            if len(document) < required.get('minimum_pages', 1):
                content_errors.append('actual-use fixture has fewer than declared minimum pages')
            for token in [*required.get('required_tokens', []), *required.get('numeric_row_ids', [])]:
                if token not in text:
                    content_errors.append('actual-use fixture token missing: ' + token)
            for uri in required.get('uri_links', []):
                if uri not in uris:
                    content_errors.append('actual-use fixture URI missing: ' + uri)
            for name in required.get('named_destinations', []):
                if name not in names:
                    content_errors.append('actual-use fixture named destination missing: ' + name)
            result['actual_use_contract'] = {'errors': content_errors,
                                             'declared_expectations': required}
            if content_errors:
                result['contract_error'] = '; '.join(content_errors)
        result['pdf'] = pdf.relative_to(evidence).as_posix()
        result['pdf_sha256'] = digest(pdf)
        expected_language = 'en' if row['main_language'] == 'english' else 'he'
        if not result['page_count'] or result['pdf_lang'] != expected_language:
            result['contract_error'] = 'native PDF language/page count contract failed'
        for backend in BACKENDS:
            review = folder / ('review-' + backend)
            args = [sys.executable, str(root / 'scripts/render_review.py'), 'render',
                    str(pdf), '--output', str(review), '--dpi', str(DPI), '--renderer', backend]
            rendered = command(args, folder / ('render-' + backend + '.log'),
                               env=local_env, cwd=project, timeout=180)
            result['renders'][backend] = rendered
            if rendered['actual_exit'] == 0:
                data = json.loads((review / 'review.json').read_text(encoding='utf-8'))
                rendered['review'] = (review / 'review.json').relative_to(evidence).as_posix()
                rendered['pages'] = data['pages']
                if any(page['status'] != 'pending' for page in data['pages']):
                    raise ValueError('renderer inferred a visual attestation')
    # Successful build exports aux/PDF only; compare every initial engine input.
    changed = [name for name, record in row['input_inventory'].items()
               if not (project / name).is_file() or digest(project / name) != record['sha256']
               or ((project / name).stat().st_mode & 0o777) != record['mode']]
    result['changed_input_files'] = changed
    write_json(folder / 'case-result.json', result)
    print(f"{row['id']}: {'PASS' if case_ok(result) else 'FAIL'}", flush=True)
    return result


def case_ok(case: dict) -> bool:
    return (type(case.get('build', {}).get('actual_exit')) is int
            and case['build']['actual_exit'] == 0
            and case['build'].get('timed_out') is False and not case.get('contract_error')
            and case.get('waivers') == [] and case.get('changed_input_files') == []
            and set(case.get('renders', {})) == set(BACKENDS)
            and all(type(row.get('actual_exit')) is int and row['actual_exit'] == 0 and row.get('timed_out') is False
                    for row in case['renders'].values()))


def run_matrix(evidence: Path, *, root=ROOT, jobs=1, theme=None,
               candidate_sha=None) -> int:
    from catalog_coverage import coverage_report, acceptance_coverage
    from template_registry import load_catalog
    candidate_sha = source_archive_identity(candidate_sha)
    if not 1 <= jobs <= 8:
        raise ValueError('jobs must be between one and eight')
    evidence = evidence.absolute()
    if evidence.is_relative_to(root.absolute()):
        raise ValueError('runtime matrix evidence must stay outside installable source')
    evidence.mkdir(parents=True, exist_ok=False)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    env.setdefault('SOURCE_DATE_EPOCH', '1700000000')
    if env.get('MAX_CROSS_PAGE_DESTINATIONS', '0') != '0':
        raise ValueError('catalog matrix does not permit cross-page destination waivers')
    before = inventory(root)
    write_json(evidence / 'source-before.json', before)
    coverage = coverage_report(root)
    write_json(evidence / 'coverage-contract.json', coverage)
    if coverage['errors']:
        raise ValueError('incomplete declared catalog/component coverage')
    identity = collect_identity(root, evidence, env)
    rows = prepare_cases(root, evidence, theme=theme)
    canonical = assign_aliases(rows, identity)
    catalog = load_catalog(root=root)
    declared_acceptance = acceptance_coverage(root, catalog, rows, theme_filter=theme)
    if declared_acceptance['errors']:
        raise ValueError('incomplete acceptance-ID declarations: ' + '; '.join(declared_acceptance['errors']))
    write_json(evidence / 'case-plan.json', rows)
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        results = list(pool.map(lambda row: execute_case(root, evidence, row, env), canonical))
    after = inventory(root)
    write_json(evidence / 'source-after.json', after)
    passed = sum(case_ok(case) for case in results)
    actual_acceptance = acceptance_coverage(root, catalog, rows, results, theme_filter=theme)
    result = {'schema': MATRIX_SCHEMA, 'scope': 'all-supported-compositions' if theme is None else 'explicit-theme-subset',
              'execution_source_root': str(root.absolute()),
              'theme_filter': theme, 'candidate_sha256': candidate_sha,
              'catalog_sha256': digest(root / 'registry/studio-catalog.json'),
              'source_inventory_sha256': json_digest(before),
              'source_unchanged': before == after, 'build_identity': identity,
              'requested_compositions': sum(row['category'] == 'composition' for row in rows),
              'declared_cases': len(rows), 'unique_builds': len(canonical),
              'passed_builds_and_renders': passed, 'failed_builds_and_renders': len(canonical) - passed,
              'unique_pdf_pages': sum(case.get('page_count', 0) for case in results),
              'renderer_backends': list(BACKENDS), 'dpi': DPI,
              'cases': results, 'visual_claim': False,
              'acceptance_coverage': actual_acceptance,
              'all_builds_and_renders_pass': passed == len(canonical) and before == after and actual_acceptance['scoped_acceptance_ids_pass']}
    write_json(evidence / 'matrix-result.json', result)
    print(f"Catalog matrix: {passed}/{len(canonical)} unique builds/renders; "
          f"{result['requested_compositions']} requested compositions; human review remains pending.")
    return int(not result['all_builds_and_renders_pass'])


def evidence_pins(evidence: Path) -> dict:
    # The seal itself is excluded to avoid a self-hash cycle. Render manifests
    # are pinned only after genuine observations have been recorded.
    return {name: record for name, record in inventory(evidence).items()
            if name not in ('matrix-release-receipt.json', 'matrix-verify.json')
            and not name.startswith('matrix-release-receipt.json.')}


def verify_matrix(evidence: Path, *, root=ROOT, require_visual=False,
                  rerender=False, candidate_sha=None, require_complete=True) -> dict:
    import render_review
    candidate_sha = source_archive_identity(candidate_sha)
    evidence = evidence.absolute()
    result = json.loads((evidence / 'matrix-result.json').read_text(encoding='utf-8'))
    plan = json.loads((evidence / 'case-plan.json').read_text(encoding='utf-8'))
    before = json.loads((evidence / 'source-before.json').read_text(encoding='utf-8'))
    after = json.loads((evidence / 'source-after.json').read_text(encoding='utf-8'))
    errors = []
    if type(result.get('schema')) is not int or result['schema'] != MATRIX_SCHEMA or result.get('visual_claim') is not False:
        errors.append('runtime receipt schema/visual-claim contract differs')
    from catalog_coverage import coverage_report, acceptance_coverage
    from template_registry import load_catalog
    if json.loads((evidence / 'coverage-contract.json').read_text(encoding='utf-8')) != coverage_report(root):
        errors.append('current declared asset/API/example coverage contract differs')
    for field in ('requested_compositions', 'declared_cases', 'unique_builds',
                  'passed_builds_and_renders', 'failed_builds_and_renders', 'unique_pdf_pages', 'dpi'):
        if type(result.get(field)) is not int or result[field] < 0:
            errors.append('strict integer matrix field differs: ' + field)
    if require_complete and (result.get('scope') != 'all-supported-compositions' or result.get('theme_filter') is not None):
        errors.append('release requires the complete catalog matrix')
    if before != after or before != inventory(root) or result.get('source_inventory_sha256') != json_digest(before):
        errors.append('exact current candidate source does not match immutable matrix inventories')
    if result.get('source_unchanged') is not True:
        errors.append('matrix source changed')
    if result.get('catalog_sha256') != digest(root / 'registry/studio-catalog.json'):
        errors.append('catalog digest differs')
    if candidate_sha is not None and result.get('candidate_sha256') != candidate_sha:
        errors.append('candidate archive identity differs')
    requests = [row.get('request') for row in plan if row.get('category') == 'composition']
    if requests != expected_requests(root, result.get('theme_filter')):
        errors.append('matrix does not enumerate the exact catalog requests in order')
    # Regenerate all declared cases without engines to prove complete examples,
    # actual-use fixtures, recipe revisions, wrappers and copied assets as well.
    with tempfile.TemporaryDirectory(prefix='studio-matrix-plan-check-') as temporary:
        expected_plan = prepare_cases(root, Path(temporary), theme=result.get('theme_filter'))
    excluded = ('canonical_case', 'build_fingerprint_sha256')
    actual_declarations = [{key: value for key, value in row.items() if key not in excluded} for row in plan]
    if actual_declarations != expected_plan:
        errors.append('complete regenerated recipe/example/component declarations differ')
    if result.get('requested_compositions') != len(requests) or result.get('declared_cases') != len(plan):
        errors.append('matrix declared counts differ')
    ids = [row.get('id') for row in plan]
    if len(ids) != len(set(ids)):
        errors.append('duplicate matrix case IDs')
    identity = result.get('build_identity', {})
    if identity.get('build_identity_sha256') != digest(evidence / 'build-identity.json'):
        errors.append('build dependency/environment identity differs')
    if identity.get('source_inventory_sha256') != json_digest(before):
        errors.append('build identity source differs')
    pinned_identity = json.loads((evidence / 'build-identity.json').read_text(encoding='utf-8'))
    if (pinned_identity.get('environment_report', {}).get('status') != 'complete'
            or pinned_identity.get('environment_report', {}).get('errors')):
        errors.append('actual dependency report was incomplete')
    errors.extend(verify_dependency_identity(pinned_identity))
    expected_plan = json.loads(json.dumps(plan))
    canonical = assign_aliases(expected_plan, identity)
    if [(row.get('canonical_case'), row.get('build_fingerprint_sha256')) for row in plan] != [(row['canonical_case'], row['build_fingerprint_sha256']) for row in expected_plan]:
        errors.append('aliases do not represent exact source/build/dependency identity')
    cases = result.get('cases', [])
    if [row.get('id') for row in cases] != [row['id'] for row in canonical] or result.get('unique_builds') != len(canonical):
        errors.append('matrix unique-build population differs')
    actual_acceptance = acceptance_coverage(root, load_catalog(root=root), plan, cases,
                                           theme_filter=result.get('theme_filter'))
    errors.extend(actual_acceptance['errors'])
    if result.get('acceptance_coverage') != actual_acceptance:
        errors.append('exact acceptance-ID case/alias/execution bindings differ')
    reviewed_pages = 0
    replayed_reviews = []
    for row in plan:
        project = confined(evidence, row['project'])
        for name, item in row['input_inventory'].items():
            source = confined(project, name)
            if not source.is_file() or digest(source) != item['sha256'] or source.stat().st_mode & 0o777 != item['mode']:
                errors.append(row['id'] + ': generated engine input changed: ' + name)
        inventory_path = confined(evidence, 'cases/' + row['id'] + '/input-inventory.json')
        if json.loads(inventory_path.read_text(encoding='utf-8')) != row['input_inventory']:
            errors.append(row['id'] + ': original input inventory differs')
    by_id = {row['id']: row for row in canonical}
    execution_root = Path(result.get('execution_source_root', str(root)))
    for case in cases:
        if not case_ok(case):
            errors.append(case.get('id', '?') + ': actual engine/render gates did not pass')
            continue
        row = by_id[case['id']]
        folder = confined(evidence, 'cases/' + case['id'])
        case_file = json.loads((folder / 'case-result.json').read_text(encoding='utf-8'))
        if case_file != case:
            errors.append(case['id'] + ': case/result receipt differs')
        if case.get('build_fingerprint_sha256') != row['build_fingerprint_sha256']:
            errors.append(case['id'] + ': executed fingerprint differs')
        records = [case['build'], *case['renders'].values()]
        for record in records:
            log = confined(folder, record['log'])
            if digest(log) != record['log_sha256']:
                errors.append(case['id'] + ': actual command log differs')
        project = confined(evidence, row['project'])
        expected_build_command = (['bash', str(project / 'build.sh')] if row['category'] == 'composition'
                                  else ['bash', str(execution_root / 'scripts/build.sh'), str(project / row['tex_name'])])
        if case['build'].get('argv') != expected_build_command:
            errors.append(case['id'] + ': actual managed build invocation differs')
        pdf = confined(evidence, case['pdf'])
        if digest(pdf) != case['pdf_sha256']:
            errors.append(case['id'] + ': PDF digest differs')
        for backend in BACKENDS:
            render = case['renders'][backend]
            review = confined(evidence, render['review'])
            data = json.loads(review.read_text(encoding='utf-8'))
            expected_render_command = [sys.executable, str(execution_root / 'scripts/render_review.py'), 'render',
                                       str(pdf), '--output', str(review.parent), '--dpi', str(DPI), '--renderer', backend]
            if render.get('argv') != expected_render_command:
                errors.append(case['id'] + ': actual renderer invocation differs')
            if data.get('renderer_backend') != backend or data.get('dpi') != DPI:
                errors.append(case['id'] + ': explicit dual144 renderer contract differs')
            expected_pages = [{k: v for k, v in page.items() if k not in ('status', 'reviewer', 'notes')} for page in render['pages']]
            actual_pages = [{k: v for k, v in page.items() if k not in ('status', 'reviewer', 'notes')} for page in data['pages']]
            if expected_pages != actual_pages:
                errors.append(case['id'] + ': initial rendered page population differs')
            needs_attestation = require_visual and backend == 'mupdf'
            found = render_review.verify(pdf, review, require_attestations=needs_attestation,
                                          rerender=False)
            errors.extend(case['id'] + '/' + backend + ': ' + text for text in found)
            if needs_attestation and not found:
                reviewed_pages += data['page_count']
            if rerender and backend == 'mupdf' and not found:
                replay = command([sys.executable, str(root / 'scripts/render_review.py'), 'verify',
                                  str(pdf), '--review', str(review), '--rerender'],
                                 folder / 'replay-mupdf.log', env=dict(os.environ),
                                 cwd=project, timeout=max(180, 30 * case['page_count']))
                if replay['actual_exit'] != 0 or replay['timed_out']:
                    errors.append(case['id'] + ': genuine primary replay command failed')
                replayed_reviews.append({'case': case['id'], 'pdf_sha256': digest(pdf),
                                          'review_sha256': digest(review),
                                          'renderer_backend': backend, 'dpi': DPI,
                                          'page_count': data['page_count'], 'command': replay,
                                          'actual_replay_exit': replay['actual_exit']})
    if result.get('failed_builds_and_renders') != 0 or result.get('passed_builds_and_renders') != len(canonical) or result.get('all_builds_and_renders_pass') is not True:
        errors.append('matrix overall success/count contract differs')
    if result.get('unique_pdf_pages') != sum(case.get('page_count', 0) for case in cases):
        errors.append('unique PDF page population differs')
    return {'schema': MATRIX_SCHEMA, 'status': 'pass' if not errors else 'fail',
            'errors': errors, 'candidate_sha256': result.get('candidate_sha256'),
            'source_inventory_sha256': result.get('source_inventory_sha256'),
            'requested_compositions': len(requests), 'unique_builds': len(canonical),
            'unique_pdf_pages': result.get('unique_pdf_pages'),
            'primary_human_review_required': require_visual,
            'primary_reviewed_pages': reviewed_pages,
            'primary_same_backend_replays': replayed_reviews,
            'secondary_human_review_claim': False,
            'declared_acceptance_ids': actual_acceptance['declared_acceptance_ids'],
            'passed_acceptance_ids': actual_acceptance['passed_acceptance_ids'],
            'acceptance_coverage_sha256': json_digest(actual_acceptance),
            'runtime_matrix_sha256': digest(evidence / 'matrix-result.json')}


def seal_matrix(evidence: Path, *, root=ROOT, candidate_sha=None) -> dict:
    if candidate_sha is None:
        raise ValueError('sealing requires the exact candidate archive SHA-256')
    if (evidence / 'matrix-release-receipt.json').exists():
        raise ValueError('matrix is already sealed; refuse replacement')
    runtime = json.loads((evidence / 'matrix-result.json').read_text(encoding='utf-8'))
    if runtime.get('scope') != 'all-supported-compositions' or runtime.get('theme_filter') is not None:
        raise ValueError('sealing requires the complete catalog matrix; explicit theme subsets remain local evidence')
    result = verify_matrix(evidence, root=root, require_visual=True,
                           rerender=True, candidate_sha=candidate_sha)
    if result['errors']:
        raise ValueError('matrix cannot be sealed: ' + '; '.join(result['errors']))
    result['evidence_files'] = evidence_pins(evidence)
    result['meaning'] = 'Actual build/render gates; primary page attestations and fresh pixel replay; secondary rendered only.'
    write_json(evidence / 'matrix-release-receipt.json', result)
    return result


def source_preview(evidence: Path, *, root=ROOT, theme=None) -> dict:
    from catalog_coverage import acceptance_coverage
    from template_registry import load_catalog
    evidence = evidence.absolute()
    if evidence.is_relative_to(root.absolute()):
        raise ValueError('matrix source preview must stay outside source')
    evidence.mkdir(parents=True, exist_ok=False)
    before = inventory(root)
    rows = prepare_cases(root, evidence, theme=theme)
    canonical = assign_aliases(rows, {'scope': 'source-only-preview; dependency identity not collected'})
    declared_acceptance = acceptance_coverage(root, load_catalog(root=root), rows, theme_filter=theme)
    if declared_acceptance['errors']:
        raise ValueError('incomplete acceptance-ID declarations: ' + '; '.join(declared_acceptance['errors']))
    result = {'schema': 1, 'scope': 'source-only-preview', 'visual_claim': False,
              'theme_filter': theme,
              'engine_invoked': False, 'renderer_invoked': False,
              'requested_compositions': sum(row['category'] == 'composition' for row in rows),
              'declared_cases': len(rows), 'unique_source_build_inputs_estimate': len(canonical),
              'acceptance_coverage': declared_acceptance,
              'source_unchanged': before == inventory(root)}
    write_json(evidence / 'case-plan.json', rows)
    write_json(evidence / 'source-preview.json', result)
    return result


def verify_seal(evidence: Path, *, root=ROOT, candidate_sha=None) -> dict:
    receipt = json.loads((evidence / 'matrix-release-receipt.json').read_text(encoding='utf-8'))
    result = verify_matrix(evidence, root=root, require_visual=True,
                           rerender=False, candidate_sha=candidate_sha)
    if receipt.get('evidence_files') != evidence_pins(evidence):
        result['errors'].append('sealed evidence population or digest differs')
    for field in ('status', 'candidate_sha256', 'source_inventory_sha256', 'requested_compositions',
                  'unique_builds', 'unique_pdf_pages', 'primary_reviewed_pages', 'runtime_matrix_sha256',
                  'declared_acceptance_ids', 'passed_acceptance_ids', 'acceptance_coverage_sha256'):
        if receipt.get(field) != result.get(field):
            result['errors'].append('sealed receipt field differs: ' + field)
    runtime = json.loads((evidence / 'matrix-result.json').read_text(encoding='utf-8'))
    replays = receipt.get('primary_same_backend_replays', [])
    if (not isinstance(replays, list) or len(replays) != result['unique_builds']
            or [row.get('case') for row in replays] != [case['id'] for case in runtime['cases']]):
        result['errors'].append('sealed actual primary replay population differs')
    else:
        execution_root = Path(runtime.get('execution_source_root', str(root)))
        for replay, case in zip(replays, runtime['cases']):
            primary = case['renders']['mupdf']
            review = confined(evidence, primary['review'])
            folder = review.parent.parent
            expected_command = [sys.executable, str(execution_root / 'scripts/render_review.py'), 'verify',
                                str(confined(evidence, case['pdf'])), '--review', str(review), '--rerender']
            observed = replay.get('command', {})
            if (replay.get('pdf_sha256') != case['pdf_sha256']
                    or replay.get('review_sha256') != digest(review)
                    or replay.get('renderer_backend') != 'mupdf' or type(replay.get('dpi')) is not int or replay['dpi'] != DPI
                    or type(replay.get('page_count')) is not int or replay['page_count'] != case['page_count']
                    or type(replay.get('actual_replay_exit')) is not int or replay['actual_replay_exit'] != 0
                    or type(observed.get('actual_exit')) is not int or observed['actual_exit'] != 0
                    or observed.get('timed_out') is not False or observed.get('argv') != expected_command
                    or digest(confined(folder, observed.get('log'))) != observed.get('log_sha256')):
                result['errors'].append(case['id'] + ': sealed genuine primary replay identity differs')
    result['status'] = 'pass' if not result['errors'] else 'fail'
    return result
