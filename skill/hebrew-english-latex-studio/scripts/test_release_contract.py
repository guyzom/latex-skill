#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Original project code; scope and terms: ../LICENSING.md.
"""Cross-check release metadata, validated QA pins, and release-hygiene wiring."""
from __future__ import annotations

from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from doctor import EXPECTED_QA, REQUIRED_TEX_FILES  # noqa: E402
from architecture_contract import ARCHITECTURE_SCHEMA_VERSION, validate_contract  # noqa: E402

errors: list[str] = []
from check_license_scope import validate as validate_license_scope
errors.extend(validate_license_scope(ROOT))
try:
    from template_registry import load_catalog
    from generate_studio_docs import generated_documents
    from catalog_coverage import coverage_report
    load_catalog(ROOT)
    for relative, expected_bytes in generated_documents(ROOT).items():
        if (ROOT / relative).read_bytes() != expected_bytes:
            errors.append(f"canonical studio documentation is stale: {relative}")
    errors.extend(coverage_report(ROOT)["errors"])
except (ImportError, OSError, ValueError, TypeError, KeyError) as exc:
    errors.append(f"canonical catalog/glossary/coverage contract failed: {type(exc).__name__}: {exc}")
version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
if not re.fullmatch(r"\d+\.\d+\.\d+", version):
    errors.append(f"VERSION is not semver: {version!r}")
changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
match = re.search(r"^## v([^\s]+)", changelog, re.MULTILINE)
if not match or match.group(1) != version:
    errors.append(f"CHANGELOG latest version {match.group(1) if match else '<missing>'} != VERSION {version}")
skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
if not skill.startswith("---\nname: hebrew-english-latex-studio\n"):
    errors.append("SKILL.md frontmatter name drifted")

# Public identity must agree across the router and host metadata.
identity = (ROOT / "agents" / "openai.yaml").read_text(encoding="utf-8")
if 'display_name: "Hebrew English LaTeX Studio"' not in identity:
    errors.append("host display name does not describe the unified studio")
if "$hebrew-english-latex-studio" not in identity:
    errors.append("host default prompt invokes a different skill")

pins: dict[str, str] = {}
for raw in (ROOT / "requirements-qa.txt").read_text(encoding="utf-8").splitlines():
    raw = raw.strip()
    if not raw or raw.startswith("#"):
        continue
    if "==" not in raw:
        errors.append(f"requirements-qa.txt entry is not exact-pinned: {raw}")
        continue
    name, pin = raw.split("==", 1)
    pins[name.casefold()] = pin
expected = {name.casefold(): value for name, value in EXPECTED_QA.items()}
if pins != expected:
    errors.append(f"requirements-qa pins {pins!r} != doctor pins {expected!r}")
for dependency in ("longtable.sty", "collcell.sty"):
    if dependency not in REQUIRED_TEX_FILES:
        errors.append(f"doctor no longer checks flow-table dependency {dependency}")
if "multicol.sty" not in REQUIRED_TEX_FILES:
    errors.append("doctor no longer checks the reference-column dependency multicol.sty")
if "ctablestack.sty" not in REQUIRED_TEX_FILES:
    errors.append("doctor no longer checks the quantikz transitive dependency ctablestack.sty")

build = (ROOT / "scripts" / "build.sh").read_text(encoding="utf-8")
harness = (ROOT / "scripts" / "test_all.sh").read_text(encoding="utf-8")
packager = (ROOT / "scripts" / "package_skill.py").read_text(encoding="utf-8")
if "verify_release_contract(root)" not in packager or "test_release_contract.py" not in packager:
    errors.append("package_skill.py no longer fails closed on the package release/architecture contract")

# Release floors are part of the test contract. The harness proves the executed
# count at runtime; this check prevents an unreviewed edit to the declared floor.
# v4.21.0: retain the union and all 651 source cases / 47 golden flags;
# add the bounded glyph probe and smart-quote engine group.
# v4.26.0: T1j (static + runtime), two BLD-70 fixtures in T2e2 and two
# BLD-69 context checks in T3d; the selftest corpus gains twenty hazard cases.
# v4.27.0: T1k (static + runtime) for BLD-71; T3e keeps its count, now READABLE.
# v4.28.0: T1l adds startup/path controls and bilingual codebox geometry.
# v4.29.0: T1m adds the nested-container real-engine matrix and controls.
# v4.30.0: T1n adds technical symbols and startup; v4.31.0 adds T1o runtime heads.
# v4.32.0: T1p adds fixed-title runtime and cleanup-boundary controls.
# v5.2.0 adds one academic source/PDF contract group and one engine group;
# all 208/122 legacy groups and the 671-case source corpus remain present.
# v5.3.0 adds source and engine groups for reference components and column flow;
# all 210/123 v5.2.0 groups and the exact 671-case corpus remain present.
# v5.3.5 (repository line): T1q (static + runtime) for the folio face; seven
# LATIN-BEFORE-PAREN island-opener cases take the corpus to 678.
# v5.4.0 adds seven static catalog groups, one topic-rail engine group and one
# sealed catalog visual gate; v5.4.1 carries T1q forward onto them and adds the
# static T1r for routine runs, which run one check fewer.
# v5.4.5 adds two static paragraph/callout groups and their two engine groups.
for name, expected_floor in [("EXPECTED_FULL", 228), ("EXPECTED_FAST", 135)]:
    m = re.search(rf"^{name}=(\d+)$", harness, re.MULTILINE)
    if m is None or int(m.group(1)) != expected_floor:
        errors.append(
            f"test_all.sh {name}={m.group(1) if m else '<missing>'}; "
            f"release contract expects {expected_floor}"
        )

for added_suite in ["scripts/test_harness_controls.py", "scripts/test_download_fonts.py",
                    "scripts/test_academic.py", "scripts/test_academic_runtime.py",
                    "scripts/test_reference.py", "scripts/test_reference_runtime.py",
                    "scripts/test_v5350.py", "scripts/test_v5350_runtime.py",
                    "scripts/test_v5410.py", "scripts/test_paragraph_style.py",
                    "scripts/test_editorial_boxes.py"]:
    if added_suite not in harness or not (ROOT / added_suite).is_file():
        errors.append(f"release harness lost required studio control: {added_suite}")

for engine_suite in ["scripts/test_paragraph_style.py --with-engine",
                     "scripts/test_editorial_boxes.py --with-engine"]:
    if engine_suite not in harness:
        errors.append(f"release harness lost required editorial engine control: {engine_suite}")

for catalog_suite in ["scripts/test_template_registry.py", "scripts/test_studio_docs.py",
                      "scripts/generate_studio_docs.py --check", "scripts/test_component_fixtures.py",
                      "scripts/test_topicrail.py", "scripts/test_topicrail_runtime.py",
                      "scripts/test_studio_matrix_contracts.py", "scripts/catalog_coverage.py",
                      "scripts/test_studio_matrix.py --verify"]:
    if catalog_suite not in harness:
        errors.append(f"mandatory catalog release control missing: {catalog_suite}")
for matrix_binding in ["HEBREW_LATEX_CATALOG_MATRIX_EVIDENCE", "HEBREW_LATEX_CATALOG_CANDIDATE_SHA", "--require-visual"]:
    if matrix_binding not in harness:
        errors.append(f"mandatory catalog visual release binding missing: {matrix_binding}")

for label, text in [("build.sh", build), ("test_all.sh", harness)]:
    if "export PYTHONDONTWRITEBYTECODE=1" not in text:
        errors.append(f"{label} can dirty the package with __pycache__")
# BLD-58: a cleanup script nothing invokes is the defect wearing a fix's
# clothes. The sweep must be wired into the harness's EXIT trap -- not merely
# present in scripts/ -- or the next run fails on the previous run's debris
# again. test_harness_cleanup.py proves the sweep WORKS; this proves it RUNS.
if "clean_harness_artifacts.py" not in harness:
    errors.append("test_all.sh never invokes the harness artifact sweep (BLD-58)")
elif "cleanup_harness_tmp()" not in harness or "trap cleanup_harness_tmp EXIT" not in harness:
    errors.append("test_all.sh lost the EXIT trap that runs the artifact sweep")
if "architecture_detection.py pdf_geometry.py" not in build:
    errors.append("build preflight no longer checks the physical-geometry dependency")

if "pdf_folios.py" not in build:
    errors.append("build preflight lost the printed-folio helper dependency")

if "pdf_string_source.py" not in build:
    errors.append("source preflight lost the PDF-string analyzer dependency")

for required_publish in [
    'atomic_replace.py" "$PDF" "$TARGET_PDF',
    'atomic_replace.py" "$LOG" "$_fail_log',
    '--forbid-input "$TARGET_PDF"',
    'preserve_output.py" snapshot "$TARGET_PDF"',
    'preserve_output.py" recover "$TARGET_PDF"',
    '[ -s "$PDF" ]',
    # BLD-71: evidence must be a PDF a reader opens, not merely a nonempty file.
    'readable_pdf_pages "$PDF"',
]:
    if required_publish not in build:
        errors.append(f"build.sh lost atomic/self-output publication contract: {required_publish}")

for writer in ["setup_fonts.sh", "sync_preamble.sh"]:
    writer_text = (ROOT / "scripts" / writer).read_text(encoding="utf-8")
    if "atomic_replace.py" not in writer_text:
        errors.append(f"{writer} bypasses the canonical atomic file publisher")

for required in [
    "scripts/download_fonts.py", "scripts/test_download_fonts.py", "scripts/test_studio_matrix.py", "references/studio-setup.md",
    "scripts/language_context.py", "scripts/test_language_context.py",
    "scripts/test_language_runtime.py", "scripts/test_generated_runtime.py",
    "scripts/test_new_document.py", "scripts/test_folio_layouts.py",
    "scripts/test_caption_styles.py", "references/language-design.md",
    "scripts/check_package_hygiene.py", "scripts/package_skill.py",
    "scripts/doctor.py", "scripts/test_shell_portability.py",
    "scripts/test_doc_contracts.py", "scripts/atomic_replace.py",
    "scripts/hash_project_inputs.py", "scripts/architecture_contract.py",
    "scripts/architecture_detection.py", "scripts/test_architecture.py",
    "scripts/test_architecture_runtime.py", "scripts/render_architecture_guards.py",
    "scripts/render_compat_bundles.py", "scripts/font_paths.py", "scripts/install_fonts.py",
    "scripts/new_document.py", "scripts/render_review.py", "scripts/test_v480.py",
    "scripts/test_v480_runtime.py", "assets/reader_theme.tex", "assets/document_components.tex",
    "assets/starter_note.tex", "assets/starter_technical.tex", "assets/starter_formula_sheet.tex",
    "assets/example_reader.tex", "references/everyday-workflow.md",
    "assets/academic_theme.tex", "references/academic-articles.md",
    "assets/reference_columns.tex", "assets/reference_shell.tex",
    "assets/reference_components.tex", "assets/reference_theme.tex",
    "assets/starter_reference_sheet.tex", "assets/starter_reference_sheet_english.tex",
    "references/reference-sheets.md",
    "assets/flow_tables.tex", "assets/starter_data_report.tex",
    "assets/example_flow_tables.tex", "references/flow-tables.md",
    "scripts/test_v490.py", "scripts/test_v490_runtime.py",
    "scripts/test_v491.py", "scripts/test_v491_runtime.py",
    "assets/example_bibliography.tex", "references/citations.md",
    "assets/deferred_notes.tex", "assets/example_notes.tex", "assets/starter_annotated_note.tex",
    "scripts/preserve_output.py", "scripts/test_preserve_output.py",
    "scripts/test_deferred_notes_runtime.py", "references/deferred-notes.md", "references/output-recovery.md",
    "scripts/environment_report.py", "scripts/test_environment_report.py", "scripts/test_references_runtime.py",
    "assets/example_references.tex", "references/bilingual-references.md", "references/environment-report.md",
    "assets/preamble.tex", "assets/clean_theme.tex", "assets/exam_components.tex", "assets/clean_variant.tex", "agents/openai.yaml",
    # BLD-58. The harness's EXIT trap guards the sweep with `[ -f ... ]` so an
    # odd extracted copy degrades instead of dying mid-teardown -- which means a
    # package that simply LOST the script would clean nothing and say nothing.
    # Requiring both files here is what turns that silent degrade into a release
    # failure; the trap keeps the soft landing for everyone else.
    "scripts/clean_harness_artifacts.py", "scripts/test_harness_cleanup.py",
    "scripts/pdf_geometry.py", "scripts/test_v4160.py", "references/pdf-geometry-review.md",
    "scripts/test_toc_layout.py", "scripts/toc_layout_probe.py", "references/measured-contents.md",
    "scripts/test_v4170.py", "references/release-continuity.md",
    "scripts/heading_source.py", "scripts/test_v4180.py", "scripts/test_v4180_runtime.py",
    "references/heading-and-short-code.md",
    "scripts/pdf_string_source.py", "scripts/render_backends.py",
    "scripts/test_v4190.py", "scripts/test_v4190_runtime.py",
    "references/pdf-strings-and-renderers.md",
    "scripts/test_v4200.py", "scripts/test_v4200_runtime.py",
    "references/quote-source-boundaries.md",
    "scripts/listing_text_probe.py", "scripts/test_v4210.py", "scripts/test_v4210_runtime.py",
    "references/listing-smart-quotes.md",
    "scripts/pdf_folios.py", "scripts/test_v4240.py", "scripts/test_v4240_runtime.py", "references/pdf-folios.md",
    "scripts/test_v4230.py", "scripts/test_v4230_runtime.py", "references/literal-source-boundaries.md",
    "scripts/test_v4260.py", "scripts/test_v4260_runtime.py",
    "scripts/test_v4270.py", "scripts/test_v4270_runtime.py",
    "scripts/test_v4280.py", "scripts/test_v4280_runtime.py", "references/startup-and-codebox.md",
    "scripts/test_v4290_runtime.py", "references/nested-container-scope.md",
    "scripts/test_v4300.py", "scripts/test_v4300_runtime.py", "references/technical-symbols-and-preflight.md",
    "scripts/test_v4310_runtime.py", "references/running-heads-and-deep-references.md",
    "scripts/test_v4320.py", "scripts/test_v4320_runtime.py", "references/fixed-title-and-cleanup-boundaries.md",
    "tests/source_hazards_contour_broken.tex", "tests/source_hazards_contour_ok.tex",
]:
    if not (ROOT / required).is_file():
        errors.append(f"release-required file missing: {required}")
# All genre/language starter assets are part of the public generator API.
from new_document import KINDS
for starter, _profile in KINDS.values():
    for filename in (starter, starter.removesuffix(".tex") + "_english.tex"):
        if not (ROOT / "assets" / filename).is_file():
            errors.append(f"generator template missing from release: assets/{filename}")

# Regression paths from both v4.16.0 and v4.19.0 pairs must remain wired.
for test_entry in ["scripts/test_language_context.py", "scripts/test_language_runtime.py", "scripts/test_generated_runtime.py", "scripts/test_new_document.py", "scripts/test_folio_layouts.py", "scripts/test_caption_styles.py", "scripts/test_v4320.py", "scripts/test_v4320_runtime.py", "scripts/test_v4310_runtime.py", "scripts/test_v4300.py", "scripts/test_v4300_runtime.py", "scripts/test_v4290_runtime.py", "scripts/test_v4280.py", "scripts/test_v4280_runtime.py", "scripts/test_v4270.py", "scripts/test_v4270_runtime.py", "scripts/test_v4260.py", "scripts/test_v4260_runtime.py", "scripts/test_v4240.py", "scripts/test_v4240_runtime.py", "scripts/test_v4230.py", "scripts/test_v4230_runtime.py", "scripts/test_v4160.py", "scripts/test_toc_layout.py", "scripts/test_toc_layout.py --runtime", "scripts/test_v4170.py", "scripts/test_v4180.py", "scripts/test_v4180_runtime.py", "scripts/test_v4190.py", "scripts/test_v4190_runtime.py", "scripts/test_v4200.py", "scripts/test_v4200_runtime.py", "scripts/test_v4210.py", "scripts/test_v4210_runtime.py"]:
    if test_entry not in harness:
        errors.append(f"release continuity regression not wired into harness: {test_entry}")
core = (ROOT / "assets" / "preamble.tex").read_text(encoding="utf-8")
if "% <hllpdf:measured-toc>" not in core or r"\hllpdf@tocmeasure{#1}" not in core:
    errors.append("measured contents mechanism lost during release reconciliation")
if "--replace-existing" not in packager or "publish_archive(temp, output" not in packager:
    errors.append("package publisher lost its explicit non-clobber contract")

for phrase in ["requirements-qa.txt", "scripts/doctor.py", "scripts/package_skill.py"]:
    if phrase not in skill:
        errors.append(f"SKILL.md does not expose release/runtime contract: {phrase}")

# The pitfalls count is user-facing release metadata, not decorative prose.
# Count the contiguous rows in the canonical Symptom/Cause/Fix table and make
# both public claims follow the table rather than memory.
pitfalls = (ROOT / "references" / "pitfalls.md").read_text(encoding="utf-8")
pit_lines = pitfalls.splitlines()
try:
    table_start = next(i for i, line in enumerate(pit_lines) if line.startswith("| Symptom |"))
except StopIteration:
    errors.append("references/pitfalls.md canonical table header is missing")
else:
    rows = []
    for line in pit_lines[table_start + 2:]:
        if not line.startswith("|"):
            break
        rows.append(line)
    actual = len(rows)
    pit_claim = re.search(r"טבלת המלכודות המצטברת של הסקיל:\s*(\d+)\s+שורות", pitfalls)
    skill_claim = re.search(r"טבלת\s+(\d+)\s+הפגמים האמפיריים", skill)
    if pit_claim is None or int(pit_claim.group(1)) != actual:
        errors.append(f"pitfalls.md claims {pit_claim.group(1) if pit_claim else '<missing>'} rows; table has {actual}")
    if skill_claim is None or int(skill_claim.group(1)) != actual:
        errors.append(f"SKILL.md claims {skill_claim.group(1) if skill_claim else '<missing>'} pitfalls; table has {actual}")

# Any Python entrypoint that imports a sibling module must suppress bytecode
# itself, not rely only on build.sh/test_all.sh. Users invoke checkers directly.
import ast
script_paths = sorted((ROOT / "scripts").glob("*.py"))
local_modules = {path.stem for path in script_paths}
for path in script_paths:
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(path))
    imports_local = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports_local |= any(alias.name.split(".")[0] in local_modules for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports_local |= node.module.split(".")[0] in local_modules
    if imports_local and "dont_write_bytecode = True" not in text:
        errors.append(f"{path.relative_to(ROOT)} imports sibling modules but can write __pycache__")
# Architecture schema validity is a release invariant, not only an optional
# architecture-test concern. A package with an invalid role/capability graph
# must never be considered releasable.
if ARCHITECTURE_SCHEMA_VERSION != 4:
    errors.append(f"architecture schema version {ARCHITECTURE_SCHEMA_VERSION} requires release-consumer review")
for architecture_error in validate_contract():
    errors.append(f"architecture schema invalid at release: {architecture_error}")

# Architecture compatibility bundles are derived release artifacts, never
# independent sources of truth.
import subprocess
architecture = subprocess.run(
    [sys.executable, str(ROOT / "scripts" / "test_architecture.py")],
    text=True, capture_output=True,
)
if architecture.returncode != 0:
    errors.append("static architecture implementation contract failed: " + (architecture.stdout + architecture.stderr).strip())

compat = subprocess.run(
    [sys.executable, str(ROOT / "scripts" / "render_compat_bundles.py"), "--check"],
    text=True, capture_output=True,
)
if compat.returncode != 0:
    errors.append("generated compatibility bundle drift: " + (compat.stdout + compat.stderr).strip())

if errors:
    for error in errors:
        print(f"✗ {error}")
    sys.exit(1)
print(f"✓ release contract: v{version}, exact QA pins, valid architecture schema, immutable build/harness, deterministic packager wiring")
