#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Original project code; scope and terms: ../LICENSING.md.
"""Static architecture contract for the standalone skill package.

The test protects ownership boundaries, not aesthetics.  It intentionally runs
under FAST=1 so a layer violation cannot hide behind skipped LuaLaTeX.
"""
from __future__ import annotations

from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from architecture_contract import (  # noqa: E402
    ARCHITECTURE_SCHEMA_VERSION,
    ASSET_SPECS,
    BUILD_ONLY_KEYS,
    CAP_EXAM_SEMANTIC_API,
    CAP_HIDE_SECTION_NUMBERING,
    CAP_SHOWONLYREFS,
    CAP_REFERENCE_COLUMNS,
    CAP_REFERENCE_SHELL,
    CAP_REFERENCE_SEMANTIC_API,
    CAP_REFERENCE_PRESENTATION,
    COMPATIBILITY_BUNDLES,
    EXAM_COMPONENT_SYMBOLS,
    LAYER_ASSETS,
    LANGUAGE_HOOK_DEFAULTS,
    LANGUAGE_HOOKS,
    LANGUAGE_PROFILES,
    LAYOUT_HOOK_DEFAULTS,
    PREFERRED_LAYER_ORDER,
    PUBLIC_TEX_SYMBOLS,
    REFERENCE_STYLE_HOOK_SPECS,
    ROLE_DEPENDENCIES,
    simulate_runtime_load,
    resolve_language_profile,
    SUPPORTED_DOCUMENT_CLASSES,
    all_architecture_assets,
    claimed_loaded_sentinels,
    density_exempt_basenames,
    maintenance_sync_basenames,
    validate_contract,
)
from architecture_detection import capabilities_from_text, provider_names_from_text  # noqa: E402
from render_compat_bundles import render as render_clean_compat  # noqa: E402
from render_architecture_guards import check_tree as check_architecture_guards  # noqa: E402
import architecture_contract as architecture_module  # noqa: E402


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def strip_tex_comments(text: str) -> str:
    out: list[str] = []
    for raw in text.splitlines():
        pos = None
        for i, ch in enumerate(raw):
            if ch != "%":
                continue
            # An odd number of immediately preceding backslashes escapes %.
            n = 0
            j = i - 1
            while j >= 0 and raw[j] == "\\":
                n += 1
                j -= 1
            if n % 2 == 0:
                pos = i
                break
        out.append(raw if pos is None else raw[:pos])
    return "\n".join(out)


errors: list[str] = []
PREAMBLE = read("assets/preamble.tex")
THEME = read("assets/clean_theme.tex")
EXAM = read("assets/exam_components.tex")
TOPICRAIL = read("assets/topicrail.tex")
COMPAT = read("assets/clean_variant.tex")
ARCH = read("references/architecture.md")
CONTRACT = read("scripts/build_contract.py")
DENSITY = read("scripts/check_content_density.py")
PAGE_SIZE = read("scripts/check_pdf_page_size.py")
VALIDATOR = read("scripts/validate_build_config.py")
EXAMPLE_EXAM = read("assets/example_exam.tex")
BUILD_SH = read("scripts/build.sh")
SYNC_SH = read("scripts/sync_preamble.sh")

# The declarative schema validates itself before file-specific assertions.
for schema_error in validate_contract():
    errors.append(f"architecture schema invalid: {schema_error}")
# A malformed generated-source declaration must produce a diagnostic rather
# than crashing validation with KeyError before the release can report it.
from dataclasses import replace
original_specs = architecture_module.ASSET_SPECS
try:
    architecture_module.ASSET_SPECS = tuple(
        replace(spec, generated_from=("assets/nonexistent.tex",)) if spec.generated_from else spec
        for spec in original_specs
    )
    invalid_errors = validate_contract()
    if not any("generated source not declared" in error for error in invalid_errors):
        errors.append("unknown generated source did not return a schema diagnostic")
finally:
    architecture_module.ASSET_SPECS = original_specs
if ARCHITECTURE_SCHEMA_VERSION != 5:
    errors.append(f"unexpected architecture schema version {ARCHITECTURE_SCHEMA_VERSION}; review consumer compatibility")
if not {"INDEX_PROCESSOR", "INDEX_STYLE"} <= set(BUILD_ONLY_KEYS):
    errors.append("managed index processor/style are missing from canonical build-only identity")
if "HLLPDF_INDEX_EVIDENCE_DIR" in BUILD_ONLY_KEYS:
    errors.append("diagnostic index export destination must not change semantic build identity")

# The new flow role and scoped style hooks have explicit boundaries. Mutated
# declarations must fail before executable layers or downstream consumers run.
schema_mutations = [
    ("reference flow requires core", tuple(
        replace(spec, runtime_requires=()) if spec.path == "assets/reference_columns.tex" else spec
        for spec in original_specs
    ), "runtime prerequisite roles"),
    ("reference theme conflicts are symmetric", tuple(
        replace(spec, conflicts_with=tuple(path for path in spec.conflicts_with
                                         if path != "assets/reference_theme.tex"))
        if spec.path == "assets/reader_theme.tex" else spec
        for spec in original_specs
    ), "is not symmetric"),
    ("reference flow public API has one owner", tuple(
        replace(spec, public_symbols=spec.public_symbols + ("referencecolumns",))
        if spec.path == "assets/reference_components.tex" else spec
        for spec in original_specs
    ), "multiple declared owners"),
]
for label, mutated, expected in schema_mutations:
    try:
        architecture_module.ASSET_SPECS = mutated
        if not any(expected in error for error in validate_contract()):
            errors.append(f"schema mutation accepted: {label}")
    finally:
        architecture_module.ASSET_SPECS = original_specs
original_style_hooks = architecture_module.REFERENCE_STYLE_HOOK_SPECS
for label, mutated, expected in [
    ("style hook may not override a semantic API", (replace(original_style_hooks[0], name="referencecolumns"),),
     "collides with an owned API"),
    ("style hook needs a semantic default owner", (replace(original_style_hooks[0], default_provider="assets/reference_theme.tex"),),
     "pure semantic default provider"),
    ("style hook override requires presentation role", (replace(original_style_hooks[0], overriding_providers=("assets/reference_columns.tex",)),),
     "pure presentation theme"),
    ("style hook must name known provider", (replace(original_style_hooks[0], overriding_providers=("assets/missing.tex",)),),
     "pure presentation theme"),
]:
    try:
        architecture_module.REFERENCE_STYLE_HOOK_SPECS = mutated
        if not any(expected in error for error in validate_contract()):
            errors.append(f"schema mutation accepted: {label}")
    finally:
        architecture_module.REFERENCE_STYLE_HOOK_SPECS = original_style_hooks
for guard_error in check_architecture_guards(ROOT):
    errors.append(f"generated runtime guard drift: {guard_error}")

# Capability detection is the public bridge from architecture to QA. Pure and
# legacy carriers must activate the same presentation policies, while the exam
# semantic extension remains independent.
clean_caps = capabilities_from_text(r"\input{clean_theme.tex}")
legacy_caps = capabilities_from_text(r"\input{clean_variant.tex}")
exam_caps = capabilities_from_text(r"\input{exam_components.tex}")
for cap in (CAP_SHOWONLYREFS, CAP_HIDE_SECTION_NUMBERING):
    if cap not in clean_caps or cap not in legacy_caps:
        errors.append(f"clean pure/legacy capability parity lost for {cap}")
    if cap in exam_caps:
        errors.append(f"exam semantic extension incorrectly activates presentation policy {cap}")
if CAP_EXAM_SEMANTIC_API not in exam_caps or CAP_EXAM_SEMANTIC_API not in legacy_caps:
    errors.append("exam semantic capability missing from pure/legacy providers")
if CAP_EXAM_SEMANTIC_API in clean_caps:
    errors.append("clean theme incorrectly provides exam semantic API")

# Capability detection is a parser boundary, not a filename substring heuristic.
# Exact braced/unbraced inputs work; comments and lookalike filenames stay inert.
detection_cases = [
    (r"\input{clean_theme}", {CAP_SHOWONLYREFS, CAP_HIDE_SECTION_NUMBERING}, "extensionless clean input"),
    (r"\input ./assets/clean_theme.tex", {CAP_SHOWONLYREFS, CAP_HIDE_SECTION_NUMBERING}, "unbraced clean input"),
    (r"\include{nested/clean_theme.tex}", {CAP_SHOWONLYREFS, CAP_HIDE_SECTION_NUMBERING}, "nested clean include"),
    (r"% \input{clean_theme.tex}", set(), "commented provider"),
    (r"\input{myclean_theme.tex}", set(), "provider-prefix collision"),
    (r"\input{clean_theme_extra.tex}", set(), "provider-suffix collision"),
    (r"literal \% text % \input{clean_theme.tex}", set(), "escaped percent before comment"),
    (r"\input{reference_columns}", {CAP_REFERENCE_COLUMNS}, "reference flow extensionless input"),
    (r"\include{assets/reference_shell.tex}", {CAP_REFERENCE_SHELL}, "reference shell include"),
    (r"\input assets/reference_components.tex", {CAP_REFERENCE_SEMANTIC_API}, "reference semantic unbraced input"),
    (r"\input{reference_theme.tex}", {CAP_REFERENCE_PRESENTATION, CAP_SHOWONLYREFS}, "reference presentation input"),
    (r"% \input{reference_columns.tex}", set(), "commented reference flow provider"),
    (r"\input{myreference_theme.tex}", set(), "reference theme prefix collision"),
    (r"\input{reference_components_extra.tex}", set(), "reference semantic suffix collision"),
]
for source, required_caps, label in detection_cases:
    detected = set(capabilities_from_text(source))
    if required_caps and not required_caps.issubset(detected):
        errors.append(f"architecture capability detection lost {label}: {sorted(detected)!r}")
    if not required_caps and detected:
        errors.append(f"architecture capability detection false-positive for {label}: {sorted(detected)!r}")

embedded = capabilities_from_text(
    r"\mathtoolsset{showonlyrefs=true}\setcounter{secnumdepth}{-2}"
    r"\renewcommand{\thetbl}{\arabic{tbl}}"
)
for cap in (CAP_SHOWONLYREFS, CAP_HIDE_SECTION_NUMBERING):
    if cap not in embedded:
        errors.append(f"embedded presentation policy detection lost {cap}")

# Every declared layer asset exists, and no file is assigned to two owners.
seen: dict[str, str] = {}
for role, paths in LAYER_ASSETS.items():
    for rel in paths:
        if not (ROOT / rel).is_file():
            errors.append(f"declared architecture asset missing: {rel}")
        if rel in seen:
            errors.append(f"architecture asset {rel} has two owners: {seen[rel]}, {role}")
        seen[rel] = role
for rel in all_architecture_assets():
    if not (ROOT / rel).is_file():
        errors.append(f"architecture asset missing: {rel}")

# Runtime sentinels make the declared dependency/conflict graph executable, not
# merely documentary. Pure layers claim only themselves; a generated carrier also
# claims the pure layers it embeds so mixed legacy/pure composition fails early.
by_path_spec = {spec.path: spec for spec in ASSET_SPECS}
for spec in ASSET_SPECS:
    exec_text = strip_tex_comments(read(spec.path))
    own_def = rf"\def\{spec.loaded_sentinel}{{1}}"
    if own_def not in exec_text:
        errors.append(f"{spec.path} does not define its loaded sentinel \\{spec.loaded_sentinel}")
    if rf"\ifdefined\{spec.loaded_sentinel}" not in exec_text:
        errors.append(f"{spec.path} does not reject duplicate loading via \\{spec.loaded_sentinel}")
    for required in spec.runtime_requires:
        sentinel = by_path_spec[required].loaded_sentinel
        if rf"\ifdefined\{sentinel}" not in exec_text:
            errors.append(f"{spec.path} does not guard runtime prerequisite {required}")
    for conflict in spec.conflicts_with:
        sentinel = by_path_spec[conflict].loaded_sentinel
        if rf"\ifdefined\{sentinel}" not in exec_text:
            errors.append(f"{spec.path} does not guard conflict {conflict}")
    if spec.generated_from:
        for sentinel in claimed_loaded_sentinels(spec):
            if rf"\def\{sentinel}{{1}}" not in exec_text:
                errors.append(f"{spec.path} does not claim generated runtime sentinel \\{sentinel}")

# Executable architecture-to-architecture inputs must follow the declared role
# graph. Today pure layers are intentionally flat (all depend only on core), so
# an accidental theme -> exam or extension -> theme input is a hard violation.
by_basename = {Path(spec.path).name: spec for spec in ASSET_SPECS}
for spec in ASSET_SPECS:
    exec_text = strip_tex_comments(read(spec.path))
    for target_name in provider_names_from_text(exec_text):
        target = by_basename[target_name]
        if target.role not in ROLE_DEPENDENCIES.get(spec.role, ()):
            errors.append(
                f"{spec.path} has undeclared architecture dependency on {target.path} "
                f"({spec.role} -> {target.role})"
            )

# All assets, not one representative per role, participate. A role->path dict
# silently discarded multiple semantic extensions and themes in v4.24, hiding
# both coverage gaps and the clean/reader conflict. All compatible subsets are
# exercised in both directions, and every pair is checked in both orders.
import itertools
core_path = next(spec.path for spec in ASSET_SPECS if spec.role == "mechanism-core")
pure_optional = [spec.path for spec in ASSET_SPECS if not spec.legacy and spec.path != core_path]
legacy_path = next(spec.path for spec in ASSET_SPECS if spec.legacy)

def check_sequence(sequence: tuple[str, ...]) -> str | None:
    active = frozenset()
    for path in sequence:
        diag, active = simulate_runtime_load(path, active)
        if diag is not None:
            return diag
    return None


# Pure siblings remain independent except for explicitly declared conflicts.
for length in range(len(pure_optional) + 1):
    for subset in itertools.combinations(pure_optional, length):
        conflicts = any(other in by_path_spec[path].conflicts_with for path, other in itertools.combinations(subset, 2))
        # All permutations for <=3 layers; two whole-stack orders for larger
        # subsets plus exhaustive pair checks below avoid factorial growth.
        orders = itertools.permutations(subset) if length <= 3 else (subset, tuple(reversed(subset)))
        for order in orders:
            sequence = (core_path,) + order
            diag = check_sequence(sequence)
            if conflicts and (diag is None or "conflicts with" not in diag):
                errors.append(f"conflicting pure composition accepted/misdiagnosed: {sequence!r}: {diag}")
            elif not conflicts and diag is not None:
                errors.append(f"valid pure composition rejected: {sequence!r}: {diag}")

for first, second in itertools.permutations([spec.path for spec in ASSET_SPECS if spec.path != core_path], 2):
    diag = check_sequence((core_path, first, second))
    conflicts = second in by_path_spec[first].conflicts_with
    if conflicts and (diag is None or "conflicts with" not in diag):
        errors.append(f"conflicting layer pair accepted/misdiagnosed: {(first, second)!r}: {diag}")
    elif not conflicts and diag is not None:
        errors.append(f"compatible layer pair rejected: {(first, second)!r}: {diag}")

# The legacy carrier is valid after core and can coexist with topicrail in both
# sibling orders, but cannot coexist with either pure source layer.
rail_path = next(spec.path for spec in ASSET_SPECS if spec.role == "page-shell-extension")
for seq in [
    (core_path, legacy_path),
    (core_path, legacy_path, rail_path),
    (core_path, rail_path, legacy_path),
]:
    active = frozenset()
    for path in seq:
        diag, active = simulate_runtime_load(path, active)
        if diag is not None:
            errors.append(f"valid legacy composition rejected: {seq!r}: {diag}")
            break
for pure_source in next(spec.generated_from for spec in ASSET_SPECS if spec.path == legacy_path):
    for seq in [(core_path, legacy_path, pure_source), (core_path, pure_source, legacy_path)]:
        active = frozenset()
        diag = None
        for path in seq:
            diag, active = simulate_runtime_load(path, active)
            if diag is not None:
                break
        if diag is None or "conflicts with" not in diag:
            errors.append(f"legacy/pure conflict composition accepted or misdiagnosed: {seq!r}: {diag!r}")

# Every asset is single-load, including the core and generated carrier.
for spec in ASSET_SPECS:
    active = frozenset()
    prefix = () if spec.path == core_path else (core_path,)
    for path in prefix + (spec.path, spec.path):
        diag, active = simulate_runtime_load(path, active)
        if diag is not None:
            break
    if diag is None or "loaded more than once" not in diag:
        errors.append(f"duplicate composition did not fail for {spec.path}: {diag!r}")

# Public pre-preamble hooks and exact backward-compatible defaults remain owned
# by preamble.tex. The vocabulary is centralized here instead of duplicated in
# the test body.
for name, default in LAYOUT_HOOK_DEFAULTS:
    pat = rf"\\ifdefined\\{name}\\else\\def\\{name}\{{{re.escape(default)}\}}\\fi"
    if not re.search(pat, PREAMBLE, re.MULTILINE):
        errors.append(f"missing layout contract: \\{name} default={default}")

for name, default in LANGUAGE_HOOK_DEFAULTS:
    pat = (rf"\\ifdefined\\{name}\\else\\def\\{name}\{{{re.escape(default)}\}}\\fi"
           rf"|\\providecommand\{{\\{name}\}}\{{{re.escape(default)}\}}")
    if not re.search(pat, PREAMBLE, re.MULTILINE):
        errors.append(f"missing language contract: \\{name} default={default}")
for name in LANGUAGE_HOOKS:
    if "\\" + name not in PREAMBLE:
        errors.append(f"preamble lost language hook \\{name}")
for profile in LANGUAGE_PROFILES:
    if profile not in PREAMBLE:
        errors.append(f"preamble does not implement language profile {profile}")
for profile, expected in [("hebrew", "hebrew"), ("english", "english"),
                          ("hebrew-with-english", "hebrew"), ("english-with-hebrew", "english")]:
    if resolve_language_profile(profile) != expected or resolve_language_profile(profile, expected) != expected:
        errors.append(f"language profile default resolution drift: {profile}")
for base in ("hebrew", "english"):
    if resolve_language_profile("bilingual", base) != base:
        errors.append(f"bilingual explicit main language rejected: {base}")
for profile, base in [("bilingual", None), ("english", "hebrew"), ("hebrew", "english"),
                      ("hebrew-with-english", "english"), ("english-with-hebrew", "hebrew"),
                      ("unknown", None), ("bilingual", "arabic"), ("english", "")]:
    try:
        resolve_language_profile(profile, base)
    except ValueError:
        pass
    else:
        errors.append(f"invalid language selection accepted: {(profile, base)!r}")

for pat, label in [
    (r"\\documentclass\[\\lakitclassoptions\]\{\\lakitdocumentclass\}", "documentclass hook"),
    (r"\\usepackage\[\\lakitgeometryoptions\]\{geometry\}", "geometry hook"),
    (r"\\linespread\{\\lakitlinespread\}", "line-spacing hook"),
    (r"\\setcounter\{tocdepth\}\{\\lakittocdepth\}", "toc-depth hook"),
    (r"\\setcounter\{secnumdepth\}\{\\lakitsecnumdepth\}", "numbering-depth hook"),
]:
    if not re.search(pat, PREAMBLE, re.MULTILINE):
        errors.append(f"preamble no longer consumes public {label}")
if not all(name in PREAMBLE for name in SUPPORTED_DOCUMENT_CLASSES):
    errors.append("supported document-class diagnostic drifted from architecture contract")

# The mechanism core must not load optional architecture layers. The same exact
# provider parser used by capability detection enforces dependency edges here.
pre_exec = strip_tex_comments(PREAMBLE)
for target_name in provider_names_from_text(pre_exec):
    if target_name != "preamble.tex":
        errors.append(f"mechanism core loads optional layer {target_name}; dependency direction reversed")

# Public extension APIs have one declared owner across ALL pure architecture
# layers. Generated compatibility carriers are allowed to re-export symbols only
# when the owning pure source is one of their declared generated_from inputs.
def _defines_command(text: str, symbol: str) -> bool:
    return bool(re.search(
        rf"\\(?:newcommand|renewcommand|providecommand|DeclareRobustCommand|NewDocumentCommand|RenewDocumentCommand|ProvideDocumentCommand|DeclareDocumentCommand)\*?\s*\{{?\\{re.escape(symbol)}(?:\}}|\s|\[)",
        text,
    ) or re.search(
        rf"\\(?:newenvironment|renewenvironment|NewDocumentEnvironment|RenewDocumentEnvironment|ProvideDocumentEnvironment|DeclareDocumentEnvironment)\*?\s*\{{{re.escape(symbol)}\}}",
        text,
    ))

pure_specs = [spec for spec in ASSET_SPECS if not spec.legacy]
for rel, symbols in PUBLIC_TEX_SYMBOLS.items():
    owner_exec = strip_tex_comments(read(rel))
    for symbol in symbols:
        if not _defines_command(owner_exec, symbol):
            errors.append(f"{rel} lost declared public TeX API \\{symbol}")
        definitions = [spec.path for spec in pure_specs if _defines_command(strip_tex_comments(read(spec.path)), symbol)]
        if definitions != [rel]:
            errors.append(f"public TeX API \\{symbol} pure-owner set {definitions!r}; want [{rel!r}]")
        for legacy in [spec for spec in ASSET_SPECS if spec.legacy]:
            legacy_defines = _defines_command(strip_tex_comments(read(legacy.path)), symbol)
            should_reexport = rel in legacy.generated_from
            if legacy_defines != should_reexport:
                errors.append(
                    f"{legacy.path} public API re-export mismatch for \\{symbol}: "
                    f"defines={legacy_defines}, owner-source={should_reexport}"
                )

# Scoped component styles deliberately permit only their semantic default owner
# and the declared visual override. This exception cannot allow additional API
# owners, core changes or a theme that replaces semantic environments.
for hook in REFERENCE_STYLE_HOOK_SPECS:
    carriers = [spec.path for spec in pure_specs
                if _defines_command(strip_tex_comments(read(spec.path)), hook.name)]
    expected = [spec.path for spec in pure_specs
                if spec.path == hook.default_provider or spec.path in hook.overriding_providers]
    if carriers != expected:
        errors.append(f"scoped style hook \\{hook.name} carrier set {carriers!r}; want {expected!r}")
    owner = strip_tex_comments(read(hook.default_provider))
    if not re.search(rf"\\providecommand\s*\{{\\{re.escape(hook.name)}\}}", owner):
        errors.append(f"{hook.default_provider} must provide the neutral default for \\{hook.name}")
    for provider in hook.overriding_providers:
        override = strip_tex_comments(read(provider))
        for command in ("providecommand", "renewcommand"):
            if not re.search(rf"\\{command}\s*\{{\\{re.escape(hook.name)}\}}", override):
                errors.append(f"{provider} lost order-independent {command} for \\{hook.name}")

# Pure theme: presentation/presentation-policy only. Its one hierarchy exception
# is explicit and pinned; semantic helper APIs and page-shell ownership are banned.
theme_exec = strip_tex_comments(THEME)
for pat, label in [
    (r"\\documentclass", "document class"),
    (r"\\geometry\s*\{", "geometry"),
    (r"\\(?:usepackage|RequirePackage)\s*\[[^\]]*\]\s*\{geometry\}", "geometry package"),
    (r"\\linespread\s*\{", "line spacing"),
    (r"\\setcounter\s*\{tocdepth\}", "TOC depth"),
    (r"\\setlength\s*\{\\(?:headheight|headsep|textwidth|textheight)\}", "page-shell dimensions"),
    (r"\\(?:def|gdef|newcommand|renewcommand)\s*\{?\\lakit(?:documentclass|classoptions|geometryoptions|linespread|tocdepth|secnumdepth)", "layout hooks"),
]:
    if re.search(pat, theme_exec):
        errors.append(f"clean_theme.tex owns {label}; theme/layout boundary broken")
for symbol in EXAM_COMPONENT_SYMBOLS:
    if re.search(rf"\\(?:newcommand|renewcommand|providecommand)\s*\{{\\{symbol}\}}", theme_exec):
        errors.append(f"clean_theme.tex defines exam semantic API \\{symbol}")
secnum = re.findall(r"\\setcounter\s*\{secnumdepth\}\s*\{([^}]*)\}", theme_exec)
if secnum != ["-2"]:
    errors.append(f"clean theme secnumdepth policy drifted: {secnum!r} (want exactly ['-2'])")
if "\\mathtoolsset{showonlyrefs=true}" not in theme_exec:
    errors.append("clean theme lost declared showonlyrefs presentation policy")

# Exam semantic extension: owns helper API only; it cannot recolor the system,
# redefine semantic boxes or take page-shell ownership.
exam_exec = strip_tex_comments(EXAM)
for symbol in EXAM_COMPONENT_SYMBOLS[:-1]:
    if not re.search(rf"\\(?:newcommand|providecommand)\s*\{{\\{symbol}\}}", exam_exec):
        errors.append(f"exam_components.tex lost public helper \\{symbol}")
for pat, label in [
    (r"\\definecolor", "theme colors"),
    (r"\\renewenvironment\s*\{(?:exbox|keybox|notebox|defbox|thmbox|warnbox)\}", "semantic-box presentation"),
    (r"\\documentclass", "document class"),
    (r"\\geometry\s*\{", "geometry"),
    (r"\\linespread\s*\{", "line spacing"),
    (r"\\setcounter\s*\{(?:tocdepth|secnumdepth)\}", "hierarchy policy"),
    (r"\\setlength\s*\{\\(?:headheight|headsep|textwidth|textheight)\}", "page-shell dimensions"),
]:
    if re.search(pat, exam_exec):
        errors.append(f"exam_components.tex owns {label}; semantic-extension boundary broken")

# topicrail is explicitly a page-shell extension. It may own its header styles,
# headheight/headsep and its private ST* palette, but not the document shell,
# global geometry hooks or core bidi API.
rail_exec = strip_tex_comments(TOPICRAIL)
for pat, label in [
    (r"\\documentclass", "document class"),
    (r"\\geometry\s*\{", "geometry"),
    (r"\\(?:def|gdef|newcommand|renewcommand)\s*\{?\\lakit", "global layout hooks"),
    (r"\\(?:newcommand|renewcommand|providecommand)\s*\{\\(?:h|en|code)\}", "core bidi API"),
]:
    if re.search(pat, rail_exec):
        errors.append(f"topicrail.tex owns {label}; page-shell extension boundary broken")

# Build-only configuration may not leak into any TeX runtime layer.
for rel in seen:
    tex = strip_tex_comments(read(rel))
    for key in BUILD_ONLY_KEYS:
        if key in tex:
            errors.append(f"{rel} reads build-only key {key}; build/runtime boundary broken")

# Language ownership applies to every shipped sibling, not only the first
# theme or exam extension. Project-local themes are intentionally not a fixed
# registry: these checks protect the distributed architecture's actual assets.
for spec in pure_specs:
    if spec.role == "mechanism-core":
        continue
    layer_exec = strip_tex_comments(read(spec.path))
    for name in LANGUAGE_HOOKS:
        pat = rf"\\(?:def|gdef|edef|xdef|newcommand|renewcommand|providecommand)\*?\s*\{{?\\{name}\b"
        if re.search(pat, layer_exec):
            errors.append(f"{spec.path} owns language hook \\{name}; core/language boundary broken")
    if spec.role in ("semantic-extension", "presentation-theme", "layout-extension"):
        for pat, label in [
            (r"\\documentclass\b", "document class"),
            (r"\\geometry\s*\{", "global geometry"),
            (r"\\linespread\s*\{", "global line spacing"),
            (r"\\setcounter\s*\{tocdepth\}", "TOC depth"),
        ]:
            if re.search(pat, layer_exec):
                errors.append(f"{spec.path} owns {label}; layer/layout boundary broken")
    if spec.path.startswith("assets/reference_"):
        for pat, label in [
            (r"\\(?:usepackage|RequirePackage)(?:\s*\[[^\]]*\])?\s*\{(?:babel|fontspec|unicode-math|geometry)\}", "core-owned package"),
            (r"\\(?:setmainfont|setsansfont|setmathfont|babelprovide)\b", "language/font mechanism"),
            (r"\\(?:def|gdef|edef|xdef|newcommand|renewcommand|providecommand)\*?\s*\{?\\lakit(?:documentclass|classoptions|geometryoptions|linespread|tocdepth|secnumdepth)\b", "pre-input global layout hook"),
        ]:
            if re.search(pat, layer_exec):
                errors.append(f"{spec.path} owns {label}; reference/core boundary broken")
        # A serif English face is visual policy, matching the academic theme.
        # Only this exact existing-language face selection is allowed; the
        # Hebrew faces, fallback definitions and Babel direction stay in core.
        font_calls = re.findall(r"\\babelfont\s*\[([^\]]+)\]\s*\{([^}]+)\}", layer_exec)
        expected_font_calls = [("english", "rm")] if spec.path == "assets/reference_theme.tex" else []
        if font_calls != expected_font_calls:
            errors.append(f"{spec.path} owns undeclared language font selection: {font_calls!r}")
        if font_calls and not re.search(
            r"\\babelfont\[english\]\{rm\}\[Ligatures=TeX,RawFeature=\{fallback=hebfb\},\s*"
            r"BoldFeatures=\{RawFeature=\{fallback=hebfbbf\}\},\s*"
            r"BoldItalicFeatures=\{RawFeature=\{fallback=hebfbbf\}\}\]\{Latin Modern Roman\}",
            layer_exec,
        ):
            errors.append(f"{spec.path} changed the declared English serif or core fallback identities")
        if spec.role != "page-shell-extension":
            if re.search(r"\\(?:fancypagestyle|fancyhead|fancyfoot|pagestyle|thispagestyle)\b", layer_exec):
                errors.append(f"{spec.path} owns page-shell behavior outside page-shell-extension")

# The legacy bundle is generated, not a second source of truth.
if COMPAT != render_clean_compat():
    errors.append("clean_variant.tex is not the generated compatibility bundle")
for dest, sources in COMPATIBILITY_BUNDLES.items():
    if dest != "assets/clean_variant.tex" or tuple(sources) != (
        "assets/clean_theme.tex", "assets/exam_components.tex"
    ):
        errors.append("compatibility bundle declaration drifted")

# New examples exercise the pure composition, not the compatibility bundle.
if "\\input{exam_components.tex}" not in EXAMPLE_EXAM or "\\input{clean_theme.tex}" not in EXAMPLE_EXAM:
    errors.append("example_exam.tex does not exercise pure semantic-extension + theme composition")
if "\\input{clean_variant.tex}" in EXAMPLE_EXAM:
    errors.append("example_exam.tex uses legacy compatibility bundle instead of pure layers")

# Build-contract vocabulary has one lightweight owner.
if "CONTENT_PROFILES = (" not in CONTRACT or "PAPERS_MM = {" not in CONTRACT:
    errors.append("build_contract.py lost canonical profile/paper definitions")
if "from build_contract import CONTENT_PROFILES as PROFILES, normalize_section_macros" not in DENSITY:
    errors.append("content-density checker no longer consumes canonical build contract")
if "from build_contract import PAPERS_MM" not in PAGE_SIZE:
    errors.append("page-size checker no longer consumes canonical build contract")
if "from build_contract import (" not in VALIDATOR:
    errors.append("build-config validator no longer consumes canonical build contract")
if re.search(r"^PROFILES\s*=", DENSITY, re.MULTILINE):
    errors.append("content-density checker redeclared PROFILES")
if re.search(r"^PAPERS_MM\s*=", PAGE_SIZE, re.MULTILINE):
    errors.append("page-size checker redeclared PAPERS_MM")

# Shell consumers query the contract instead of maintaining shadow lists.
if 'architecture_contract.py" density-exempt-basenames' not in BUILD_SH:
    errors.append("build.sh density filtering no longer queries architecture contract")
if re.search(r"preamble\.tex\|clean_variant\.tex\|topicrail\.tex", BUILD_SH):
    errors.append("build.sh reintroduced a legacy hard-coded architecture basename list")
if 'architecture_contract.py"' not in SYNC_SH or 'maintenance-basenames' not in SYNC_SH:
    errors.append("sync_preamble.sh no longer queries canonical maintenance layer list")
for basename in density_exempt_basenames():
    if basename not in maintenance_sync_basenames():
        errors.append(f"runtime architecture asset {basename} is density-exempt but not maintenance-syncable")

# Documentation is a public architecture surface.
for phrase in [
    "Architecture roles",
    "Language contract",
    "Layout contract",
    "Theme contract",
    "Capabilities contract",
    "Runtime layer contract",
    "Semantic extensions",
    "Page-shell extensions",
    "compatibility bundle",
    "Build and configuration contracts",
    "Runtime versus maintenance tools",
    "Backward compatibility",
]:
    if phrase not in ARCH:
        errors.append(f"architecture.md lost required contract section: {phrase}")
for role in PREFERRED_LAYER_ORDER:
    if role not in ARCH:
        errors.append(f"architecture.md does not name canonical role {role}")

if errors:
    for error in errors:
        print(f"✗ {error}")
    raise SystemExit(1)
print("✓ architecture contract: self-validating roles/capabilities/runtime guards, public API ownership, contract-driven consumers, generated legacy bundle, and one-way dependencies hold")
