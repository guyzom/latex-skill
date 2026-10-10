#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Original project code; scope and terms: ../LICENSING.md.
# Additional output permission: ../LICENSES/Generated-Output-Permission.txt.
"""Canonical architectural schema for the Hebrew LuaLaTeX skill.

The schema is intentionally declarative: TeX assets own runtime behavior, while
build/checker/maintenance tools consume this module so file names, roles,
dependency direction and cross-layer capabilities cannot drift independently.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from collections import defaultdict


@dataclass(frozen=True)
class AssetSpec:
    path: str
    role: str
    requires_roles: tuple[str, ...] = ()
    provides: tuple[str, ...] = ()
    public_symbols: tuple[str, ...] = ()
    generated_from: tuple[str, ...] = ()
    runtime_requires: tuple[str, ...] = ()
    conflicts_with: tuple[str, ...] = ()
    loaded_sentinel: str = ""
    maintenance_sync: bool = False
    density_exempt: bool = False
    legacy: bool = False

    @property
    def basename(self) -> str:
        return Path(self.path).name


@dataclass(frozen=True)
class GuardRule:
    """One executable runtime-architecture check in deterministic order."""
    kind: str
    target_path: str
    sentinel: str
    expect_defined: bool
    diagnostic: str


ARCHITECTURE_SCHEMA_VERSION = 5


@dataclass(frozen=True)
class LanguageProfile:
    """Authoring intent, independent of genre, page layout and presentation.

    ``main_language=None`` means the author must choose the document shell;
    it does not mean direction can be inferred from the first paragraph.
    Both languages remain available in every profile, including single-language
    profiles: these express intent and defaults, not a character whitelist.
    """
    name: str
    main_language: str | None
    composition: str


LANGUAGE_PROFILE_SPECS = (
    LanguageProfile("hebrew", "hebrew", "single-language"),
    LanguageProfile("english", "english", "single-language"),
    LanguageProfile("hebrew-with-english", "hebrew", "dominant-with-secondary"),
    LanguageProfile("english-with-hebrew", "english", "dominant-with-secondary"),
    LanguageProfile("bilingual", None, "balanced"),
)
LANGUAGE_PROFILES = tuple(profile.name for profile in LANGUAGE_PROFILE_SPECS)
SUPPORTED_MAIN_LANGUAGES = ("hebrew", "english")
LANGUAGE_HOOK_DEFAULTS = (("lakitlanguageprofile", "hebrew"),)
LANGUAGE_HOOKS = ("lakitlanguageprofile", "lakitmainlanguage")
LANGUAGE_PUBLIC_SYMBOLS = ("doclang", "englishprose", "hebrewprose")


def resolve_language_profile(profile: str = "hebrew", main_language: str | None = None) -> str:
    """Validate language intent and return the document's main language.

    The generator and schema use this contract. The TeX runtime validates the
    equivalent pre-input hooks, so handwritten documents receive the same rules.
    """
    by_name = {item.name: item for item in LANGUAGE_PROFILE_SPECS}
    if profile not in by_name:
        raise ValueError(f"unknown language profile {profile!r}; choose one of {', '.join(LANGUAGE_PROFILES)}")
    if main_language is not None and main_language not in SUPPORTED_MAIN_LANGUAGES:
        raise ValueError(f"unknown main language {main_language!r}; choose hebrew or english")
    declared = by_name[profile].main_language
    if declared is None:
        if main_language is None:
            raise ValueError("bilingual requires an explicit main language: hebrew or english")
        return main_language
    if main_language is not None and main_language != declared:
        raise ValueError(f"language profile {profile!r} requires main language {declared!r}")
    return declared


LAYOUT_HOOK_DEFAULTS: tuple[tuple[str, str], ...] = (
    ("lakitdocumentclass", "report"),
    ("lakitclassoptions", "12pt,a4paper"),
    ("lakitgeometryoptions", "margin=2.3cm,headheight=14pt"),
    ("lakitlinespread", "1.3"),
    ("lakitparagraphstyle", "indented"),
    ("lakittocdepth", "1"),
    ("lakitsecnumdepth", "2"),
)
SUPPORTED_DOCUMENT_CLASSES = ("report", "article")
BUILD_ONLY_KEYS = (
    "CONTENT_PROFILE",
    "SECTION_MACROS",
    "EXPECTED_PAPER",
    "REPRO",
    "MAX_CROSS_PAGE_DESTINATIONS",
    "SOURCE_DATE_EPOCH",
    "PDF_CAPTION_LABEL_WEIGHT",
    "INDEX_PROCESSOR",
    "INDEX_STYLE",
)

# Capability names describe behavior that other tools may need to reason about.
# Consumers must ask for a capability, not special-case a legacy file name.
CAP_MECHANISM_CORE = "mechanism-core"
CAP_LAYOUT_HOOKS = "layout-hooks"
CAP_LANGUAGE_PROFILES = "language-profiles"
CAP_CANONICAL_PRESENTATION = "presentation.canonical"
CAP_PRESENTATION_HOOKS = "presentation.caption-hooks"
CAP_CAPTION_NUMBERING_API = "policy.caption-numbering-api"
CAP_EXAM_SEMANTIC_API = "semantic.exam-api"
CAP_TOPICRAIL = "page-shell.topicrail"
CAP_CLEAN_PRESENTATION = "presentation.clean"
CAP_SHOWONLYREFS = "policy.showonlyrefs"
CAP_HIDE_SECTION_NUMBERING = "policy.hide-section-numbering"
CAP_FLAT_TABLE_NUMBERING = "policy.flat-table-numbering"
CAP_ACADEMIC_PRESENTATION = "presentation.academic"
CAP_CONTINUOUS_CAPTION_NUMBERING = "policy.continuous-caption-numbering"
CAP_REFERENCE_COLUMNS = "layout.reference-columns"
CAP_REFERENCE_SHELL = "page-shell.reference"
CAP_REFERENCE_SEMANTIC_API = "semantic.reference-api"
CAP_REFERENCE_PRESENTATION = "presentation.reference"

# Mutable presentation hooks are distinct from uniquely owned semantic APIs:
# the core supplies their defaults and a theme may deliberately redefine them.
PRESENTATION_HOOKS = ("lakitcaptionstyle", "lakitcaptionlabelstyle", "lakitcaptionpunctuation")

EXAM_COMPONENT_SYMBOLS = ("qlabel", "pts", "finalans", "srcfig", "srcfigdir")
TOPICRAIL_PUBLIC_SYMBOLS = (
    "STdirRTL",
    "STdirLTR",
    "STrailwidth",
    "STrailangle",
    "STnames",
    "STgetname",
    "STdrawrail",
)
REFERENCE_COLUMN_SYMBOLS = (
    "referencecolumns", "referencewide", "ReferenceColumnCount",
    "ReferenceColumnGap", "ReferenceColumnRule", "ReferenceColumnSkip", "ReferenceBodyFontSize",
    "ReferenceBodyBaseline", "ReferenceSelectBodyFont",
    "ReferenceMathFontSize", "ReferenceMathScriptSize", "ReferenceMathScriptScriptSize",
)
REFERENCE_SHELL_SYMBOLS = (
    "ReferenceTitle", "ReferenceShortTitle", "ReferenceSubtitle",
    "ReferenceAuthor", "ReferenceDate", "makereferencetitle",
)
REFERENCE_COMPONENT_SYMBOLS = (
    "referenceentry",
    "referencenote", "referencewarning", "referenceformula", "referenceqa",
    "referenceqaseries", "referencesolutionpart", "referencequestion",
    "referencesolution", "referencepurpose", "referenceconditions",
    "referencefigcap", "referencetabcap",
    "referencefigure", "referencetable",
)
STUDY_COMPONENT_SYMBOLS = (
    "studyexercise", "studysolution", "studyexerciseref", "studysolutionref",
    "studyheadingstyle",
)
INDEX_COMPONENT_SYMBOLS = (
    "lakitindex", "lakitindexrangebegin", "lakitindexrangeend", "lakitindexcolumns",
)


@dataclass(frozen=True)
class StyleHookSpec:
    """A scoped visual default with explicitly permitted presentation overrides.

    A semantic component owns the neutral default without forcing callers to
    load a theme. The theme may provide the same default when loaded first and
    override its value. This is a mutable hook, not a shared semantic API owner.
    """
    name: str
    default_provider: str
    overriding_providers: tuple[str, ...]


REFERENCE_STYLE_HOOK_SPECS = tuple(
    StyleHookSpec(name, "assets/reference_components.tex", ("assets/reference_theme.tex",))
    for name in (
        "referencenotestyle", "referencewarningstyle",
        "referenceformulastyle", "referenceqastyle",
    )
)
REFERENCE_PRESENTATION_HOOKS = tuple(hook.name for hook in REFERENCE_STYLE_HOOK_SPECS)


@dataclass(frozen=True)
class HookSpec:
    """A public configuration declaration, independent of its runtime value.

    Symbolic defaults describe the owning TeX implementation; the registry does
    not expand TeX or claim that a declared size is a measured PDF size.
    Presentation/content hooks are inventoried but are not preset operations.
    """
    name: str
    owner: str
    define_before: str
    scope: str
    value_type: str
    unit: str
    default: str
    default_kind: str = "literal"
    allowed_values: tuple[str, ...] = ()
    minimum: str | None = None
    minimum_inclusive: bool = True
    preset_allowed: bool = True


HOOK_SPECS: tuple[HookSpec, ...] = (
    HookSpec("lakitdocumentclass", "assets/preamble.tex", "assets/preamble.tex",
             "document", "enum", "", "report", allowed_values=SUPPORTED_DOCUMENT_CLASSES),
    HookSpec("lakitclassoptions", "assets/preamble.tex", "assets/preamble.tex",
             "document", "class-options", "", "12pt,a4paper"),
    HookSpec("lakitgeometryoptions", "assets/preamble.tex", "assets/preamble.tex",
             "document", "geometry-options", "mixed", "margin=2.3cm,headheight=14pt"),
    HookSpec("lakitlinespread", "assets/preamble.tex", "assets/preamble.tex",
             "document", "decimal", "ratio", "1.3", minimum="0", minimum_inclusive=False),
    HookSpec("lakitparagraphstyle", "assets/preamble.tex", "assets/preamble.tex",
             "document", "enum", "", "indented", allowed_values=("indented", "block")),
    HookSpec("lakittocdepth", "assets/preamble.tex", "assets/preamble.tex",
             "document", "integer", "", "1", minimum="-1"),
    HookSpec("lakitsecnumdepth", "assets/preamble.tex", "assets/preamble.tex",
             "document", "integer", "", "2", minimum="-1"),
    HookSpec("lakitlanguageprofile", "assets/preamble.tex", "assets/preamble.tex",
             "document", "enum", "", "hebrew", allowed_values=LANGUAGE_PROFILES,
             preset_allowed=False),
    HookSpec("lakitmainlanguage", "assets/preamble.tex", "assets/preamble.tex",
             "document", "enum", "", "language-profile.main-language",
             default_kind="symbolic", allowed_values=SUPPORTED_MAIN_LANGUAGES,
             preset_allowed=False),
    HookSpec("ReferenceColumnCount", "assets/reference_columns.tex", "assets/reference_columns.tex",
             "reference-layout", "enum", "columns", "2", allowed_values=("2", "3")),
    HookSpec("ReferenceColumnGap", "assets/reference_columns.tex", "assets/reference_columns.tex",
             "reference-layout", "dimension", "TeX-dimension", "5mm", minimum="0", minimum_inclusive=False),
    HookSpec("ReferenceColumnRule", "assets/reference_columns.tex", "assets/reference_columns.tex",
             "reference-layout", "dimension", "TeX-dimension", ".3pt", minimum="0"),
    HookSpec("ReferenceColumnSkip", "assets/reference_columns.tex", "assets/reference_columns.tex",
             "reference-layout", "dimension", "TeX-dimension", "6pt", minimum="0"),
    HookSpec("ReferenceBodyFontSize", "assets/reference_columns.tex", "assets/reference_columns.tex",
             "reference-layout", "decimal", "TeX-pt", "9", minimum="0", minimum_inclusive=False),
    HookSpec("ReferenceBodyBaseline", "assets/reference_columns.tex", "assets/reference_columns.tex",
             "reference-layout", "decimal", "TeX-pt", "11", minimum="0", minimum_inclusive=False),
    HookSpec("ReferenceMathFontSize", "assets/reference_columns.tex", "assets/reference_columns.tex",
             "reference-layout", "decimal", "TeX-pt", "ReferenceBodyFontSize", default_kind="symbolic",
             minimum="0", minimum_inclusive=False),
    HookSpec("ReferenceMathScriptSize", "assets/reference_columns.tex", "assets/reference_columns.tex",
             "reference-layout", "decimal", "TeX-pt", "0.7 * ReferenceMathFontSize", default_kind="symbolic",
             minimum="0", minimum_inclusive=False),
    HookSpec("ReferenceMathScriptScriptSize", "assets/reference_columns.tex", "assets/reference_columns.tex",
             "reference-layout", "decimal", "TeX-pt", "0.5 * ReferenceMathFontSize", default_kind="symbolic",
             minimum="0", minimum_inclusive=False),
) + tuple(
    HookSpec(name, "assets/reference_shell.tex", "assets/reference_shell.tex", "reference-shell",
             "content", "", "ReferenceTitle" if name == "ReferenceShortTitle" else "",
             default_kind="symbolic" if name == "ReferenceShortTitle" else "literal", preset_allowed=False)
    for name in ("ReferenceTitle", "ReferenceShortTitle", "ReferenceSubtitle", "ReferenceAuthor", "ReferenceDate")
) + tuple(
    HookSpec(name, "assets/preamble.tex", "", "presentation", "tex-style", "", "owner-runtime-default",
             default_kind="symbolic", preset_allowed=False)
    for name in PRESENTATION_HOOKS
) + tuple(
    HookSpec(hook.name, hook.default_provider, "", "reference-presentation", "tex-style", "",
             "owner-runtime-default", default_kind="symbolic", preset_allowed=False)
    for hook in REFERENCE_STYLE_HOOK_SPECS
)+ (
    HookSpec("lakitindexcolumns", "assets/index_components.tex", "assets/index_components.tex",
             "index-layout", "enum", "columns", "1", allowed_values=("1", "2"), preset_allowed=False),
    HookSpec("studyheadingstyle", "assets/study_components.tex", "", "study-presentation", "tex-style", "",
             "owner-runtime-default", default_kind="symbolic", preset_allowed=False),
)

# Every shipped TeX architecture asset has one owner and an explicit dependency
# edge. The compatibility bundle is generated and therefore marked legacy; it
# provides the union of the pure layers it embeds, but is never a source of truth.
ASSET_SPECS: tuple[AssetSpec, ...] = (
    AssetSpec(
        "assets/preamble.tex",
        "mechanism-core",
        provides=(CAP_MECHANISM_CORE, CAP_LAYOUT_HOOKS, CAP_LANGUAGE_PROFILES, CAP_CANONICAL_PRESENTATION,
                  CAP_PRESENTATION_HOOKS, CAP_CAPTION_NUMBERING_API),
        public_symbols=LANGUAGE_PUBLIC_SYMBOLS + ("lakitcaptionnumbering",),
        maintenance_sync=True,
        density_exempt=True,
        loaded_sentinel="hllpdfcoreloaded",
    ),
    AssetSpec(
        "assets/exam_components.tex",
        "semantic-extension",
        requires_roles=("mechanism-core",),
        provides=(CAP_EXAM_SEMANTIC_API,),
        public_symbols=EXAM_COMPONENT_SYMBOLS,
        runtime_requires=("assets/preamble.tex",),
        conflicts_with=("assets/clean_variant.tex",),
        maintenance_sync=True,
        density_exempt=True,
        loaded_sentinel="hllpdfexamcomponentsloaded",
    ),
    AssetSpec(
        "assets/topicrail.tex",
        "page-shell-extension",
        requires_roles=("mechanism-core",),
        provides=(CAP_TOPICRAIL,),
        public_symbols=TOPICRAIL_PUBLIC_SYMBOLS,
        runtime_requires=("assets/preamble.tex",),
        conflicts_with=("assets/reference_shell.tex",),
        maintenance_sync=True,
        density_exempt=True,
        loaded_sentinel="hllpdftopicrailloaded",
    ),
    AssetSpec(
        "assets/clean_theme.tex",
        "presentation-theme",
        requires_roles=("mechanism-core",),
        provides=(
            CAP_CLEAN_PRESENTATION,
            CAP_SHOWONLYREFS,
            CAP_HIDE_SECTION_NUMBERING,
            CAP_FLAT_TABLE_NUMBERING,
        ),
        runtime_requires=("assets/preamble.tex",),
        conflicts_with=("assets/clean_variant.tex", "assets/reader_theme.tex", "assets/academic_theme.tex",
                        "assets/reference_theme.tex"),
        maintenance_sync=True,
        density_exempt=True,
        loaded_sentinel="hllpdfcleanthemeloaded",
    ),
    AssetSpec(
        "assets/reader_theme.tex",
        "presentation-theme",
        requires_roles=("mechanism-core",),
        provides=("presentation.reader",),
        runtime_requires=("assets/preamble.tex",),
        conflicts_with=("assets/clean_theme.tex", "assets/clean_variant.tex", "assets/academic_theme.tex",
                        "assets/reference_theme.tex"),
        maintenance_sync=True,
        density_exempt=True,
        loaded_sentinel="hllpdfreaderthemeloaded",
    ),
    AssetSpec(
        "assets/academic_theme.tex",
        "presentation-theme",
        requires_roles=("mechanism-core",),
        provides=(CAP_ACADEMIC_PRESENTATION, CAP_SHOWONLYREFS, CAP_CONTINUOUS_CAPTION_NUMBERING),
        runtime_requires=("assets/preamble.tex",),
        conflicts_with=("assets/reader_theme.tex", "assets/clean_theme.tex", "assets/clean_variant.tex",
                        "assets/reference_theme.tex"),
        maintenance_sync=True,
        density_exempt=True,
        loaded_sentinel="hllpdfacademicthemeloaded",
    ),
    AssetSpec(
        "assets/reference_columns.tex",
        "layout-extension",
        requires_roles=("mechanism-core",),
        provides=(CAP_REFERENCE_COLUMNS,),
        public_symbols=REFERENCE_COLUMN_SYMBOLS,
        runtime_requires=("assets/preamble.tex",),
        maintenance_sync=True,
        density_exempt=True,
        loaded_sentinel="hllpdfreferencecolumnsloaded",
    ),
    AssetSpec(
        "assets/reference_shell.tex",
        "page-shell-extension",
        requires_roles=("mechanism-core",),
        provides=(CAP_REFERENCE_SHELL,),
        public_symbols=REFERENCE_SHELL_SYMBOLS,
        runtime_requires=("assets/preamble.tex",),
        conflicts_with=("assets/topicrail.tex",),
        maintenance_sync=True,
        density_exempt=True,
        loaded_sentinel="hllpdfreferenceshellloaded",
    ),
    AssetSpec(
        "assets/reference_components.tex",
        "semantic-extension",
        requires_roles=("mechanism-core",),
        provides=(CAP_REFERENCE_SEMANTIC_API,),
        public_symbols=REFERENCE_COMPONENT_SYMBOLS,
        runtime_requires=("assets/preamble.tex",),
        maintenance_sync=True,
        density_exempt=True,
        loaded_sentinel="hllpdfreferencecomponentsloaded",
    ),
    AssetSpec(
        "assets/reference_theme.tex",
        "presentation-theme",
        requires_roles=("mechanism-core",),
        provides=(CAP_REFERENCE_PRESENTATION, CAP_SHOWONLYREFS,
                  CAP_CONTINUOUS_CAPTION_NUMBERING),
        runtime_requires=("assets/preamble.tex",),
        conflicts_with=("assets/reader_theme.tex", "assets/academic_theme.tex",
                        "assets/clean_theme.tex", "assets/clean_variant.tex"),
        maintenance_sync=True,
        density_exempt=True,
        loaded_sentinel="hllpdfreferencethemeloaded",
    ),
    AssetSpec(
        "assets/document_components.tex",
        "semantic-extension",
        requires_roles=("mechanism-core",),
        provides=("semantic.document-api",),
        public_symbols=("sourcelink", "glossaryentry", "bibentryprose", "framedtable", "semanticframedtable", "framedtablewidth"),
        runtime_requires=("assets/preamble.tex",),
        maintenance_sync=True,
        density_exempt=True,
        loaded_sentinel="hllpdfdocumentcomponentsloaded",
    ),
    AssetSpec(
        "assets/deferred_notes.tex",
        "semantic-extension",
        requires_roles=("mechanism-core",),
        provides=("semantic.deferred-note-api",),
        public_symbols=("DeclareDocNote", "DocNoteMark", "PrintDocNotes"),
        runtime_requires=("assets/preamble.tex",),
        maintenance_sync=True,
        density_exempt=True,
        loaded_sentinel="hllpdfdeferrednotesloaded",
    ),
    AssetSpec(
        "assets/flow_tables.tex",
        "semantic-extension",
        requires_roles=("mechanism-core",),
        provides=("semantic.flow-table-api",),
        public_symbols=("flowtable",),
        runtime_requires=("assets/preamble.tex",),
        maintenance_sync=True,
        density_exempt=True,
        loaded_sentinel="hllpdfflowtablesloaded",
    ),
    AssetSpec(
        "assets/study_components.tex",
        "semantic-extension",
        requires_roles=("mechanism-core",),
        provides=("semantic.study-api",),
        public_symbols=STUDY_COMPONENT_SYMBOLS,
        runtime_requires=("assets/preamble.tex",),
        maintenance_sync=True,
        density_exempt=True,
        loaded_sentinel="hllpdfstudycomponentsloaded",
    ),
    AssetSpec(
        "assets/index_components.tex",
        "semantic-extension",
        requires_roles=("mechanism-core",),
        provides=("semantic.index-api",),
        public_symbols=INDEX_COMPONENT_SYMBOLS,
        runtime_requires=("assets/preamble.tex",),
        maintenance_sync=True,
        density_exempt=True,
        loaded_sentinel="hllpdfindexcomponentsloaded",
    ),
    AssetSpec(
        "assets/clean_variant.tex",
        "compatibility-bundle",
        requires_roles=("presentation-theme", "semantic-extension"),
        provides=(
            CAP_CLEAN_PRESENTATION,
            CAP_SHOWONLYREFS,
            CAP_HIDE_SECTION_NUMBERING,
            CAP_FLAT_TABLE_NUMBERING,
            CAP_EXAM_SEMANTIC_API,
        ),
        generated_from=("assets/clean_theme.tex", "assets/exam_components.tex"),
        runtime_requires=("assets/preamble.tex",),
        conflicts_with=("assets/clean_theme.tex", "assets/exam_components.tex", "assets/reader_theme.tex",
                        "assets/academic_theme.tex", "assets/reference_theme.tex"),
        maintenance_sync=True,
        density_exempt=True,
        loaded_sentinel="hllpdfcleanvariantloaded",
        legacy=True,
    ),
)

# Role-level graph is public architecture, not an incidental test detail.
ROLE_DEPENDENCIES: dict[str, tuple[str, ...]] = {
    "mechanism-core": (),
    "semantic-extension": ("mechanism-core",),
    "layout-extension": ("mechanism-core",),
    "page-shell-extension": ("mechanism-core",),
    "presentation-theme": ("mechanism-core",),
    "compatibility-bundle": ("presentation-theme", "semantic-extension"),
}

# Project-local preferred composition order. Layout hooks are definitions before
# mechanism-core input, not another file layer. Optional semantic/flow/page-shell
# extensions remain independent siblings; theme is applied after them so visual
# policy can intentionally override canonical presentation without owning their
# semantic APIs.
PREFERRED_LAYER_ORDER = (
    "mechanism-core",
    "semantic-extension",
    "layout-extension",
    "page-shell-extension",
    "presentation-theme",
)

# Compatibility mapping retained as a computed query surface for consumers;
# ownership itself lives only on AssetSpec.public_symbols.
PUBLIC_TEX_SYMBOLS: dict[str, tuple[str, ...]] = {
    spec.path: spec.public_symbols for spec in ASSET_SPECS if spec.public_symbols
}



def _group_by_role() -> dict[str, tuple[str, ...]]:
    grouped: dict[str, list[str]] = defaultdict(list)
    for spec in ASSET_SPECS:
        grouped[spec.role].append(spec.path)
    return {role: tuple(paths) for role, paths in grouped.items()}


LAYER_ASSETS: dict[str, tuple[str, ...]] = _group_by_role()
COMPATIBILITY_BUNDLES: dict[str, tuple[str, ...]] = {
    spec.path: spec.generated_from for spec in ASSET_SPECS if spec.generated_from
}
CAPABILITY_PROVIDERS: dict[str, tuple[str, ...]] = {}
for _spec in ASSET_SPECS:
    for _cap in _spec.provides:
        CAPABILITY_PROVIDERS.setdefault(_cap, tuple())
        CAPABILITY_PROVIDERS[_cap] = CAPABILITY_PROVIDERS[_cap] + (_spec.path,)


def all_architecture_assets() -> tuple[Path, ...]:
    return tuple(Path(spec.path) for spec in ASSET_SPECS)


def architecture_asset_basenames(*, include_legacy: bool = True) -> tuple[str, ...]:
    return tuple(
        spec.basename for spec in ASSET_SPECS if include_legacy or not spec.legacy
    )


def maintenance_sync_basenames() -> tuple[str, ...]:
    return tuple(spec.basename for spec in ASSET_SPECS if spec.maintenance_sync)


def density_exempt_basenames() -> tuple[str, ...]:
    return tuple(spec.basename for spec in ASSET_SPECS if spec.density_exempt)


def capabilities_for_provider_name(name: str) -> frozenset[str]:
    """Capabilities implied by a shipped provider path/basename."""
    base = Path(name).name
    caps: set[str] = set()
    for spec in ASSET_SPECS:
        if name == spec.path or base == spec.basename:
            caps.update(spec.provides)
    return frozenset(caps)


def providers_for_capability(capability: str) -> tuple[str, ...]:
    return CAPABILITY_PROVIDERS.get(capability, ())


def effective_public_symbols(spec: AssetSpec) -> tuple[str, ...]:
    """Public TeX API exposed by this asset, including generated re-exports."""
    by_path = {item.path: item for item in ASSET_SPECS}
    symbols = list(spec.public_symbols)
    for source in spec.generated_from:
        symbols.extend(effective_public_symbols(by_path[source]))
    return tuple(dict.fromkeys(symbols))


def claimed_loaded_sentinels(spec: AssetSpec) -> tuple[str, ...]:
    """Sentinels that become active after this asset loads successfully."""
    by_path = {item.path: item for item in ASSET_SPECS}
    claims = [spec.loaded_sentinel]
    claims.extend(by_path[source].loaded_sentinel for source in spec.generated_from)
    return tuple(dict.fromkeys(claims))


def runtime_guard_rules(spec: AssetSpec) -> tuple[GuardRule, ...]:
    """Return the canonical runtime checks in user-visible diagnostic order."""
    by_path = {item.path: item for item in ASSET_SPECS}
    rules: list[GuardRule] = []
    for required in spec.runtime_requires:
        other = by_path[required]
        rules.append(GuardRule(
            "requires", other.path, other.loaded_sentinel, False,
            f"hllpdf: {spec.basename} requires {other.basename} first",
        ))

    # Preserve historical invalid-state diagnostic precedence. Generated legacy
    # carriers report duplicate-load before pure-source conflicts; pure assets
    # report conflict before duplicate-load. Valid compositions are unaffected.
    if spec.generated_from:
        rules.append(GuardRule(
            "duplicate", spec.path, spec.loaded_sentinel, True,
            f"hllpdf: {spec.basename} loaded more than once",
        ))

    for conflict in spec.conflicts_with:
        other = by_path[conflict]
        rules.append(GuardRule(
            "conflict", other.path, other.loaded_sentinel, True,
            f"hllpdf: {spec.basename} conflicts with {other.basename}",
        ))

    if not spec.generated_from:
        rules.append(GuardRule(
            "duplicate", spec.path, spec.loaded_sentinel, True,
            f"hllpdf: {spec.basename} loaded more than once",
        ))
    return tuple(rules)


def simulate_runtime_load(
    asset_path: str, active_sentinels: frozenset[str] | set[str] | tuple[str, ...]
) -> tuple[str | None, frozenset[str]]:
    """Apply one asset load to sentinel state using the same rules TeX renders.

    Returns ``(diagnostic, state)``. A non-None diagnostic leaves state unchanged;
    a successful load claims the asset's own sentinel plus any pure-layer
    sentinels represented by a generated compatibility carrier.
    """
    by_path = {item.path: item for item in ASSET_SPECS}
    if asset_path not in by_path:
        raise KeyError(asset_path)
    spec = by_path[asset_path]
    active = frozenset(active_sentinels)
    for rule in runtime_guard_rules(spec):
        is_defined = rule.sentinel in active
        if is_defined == rule.expect_defined:
            return rule.diagnostic, active
    return None, frozenset(set(active).union(claimed_loaded_sentinels(spec)))


def validate_contract() -> tuple[str, ...]:
    """Return schema errors; empty tuple means the architecture graph is valid."""
    errors: list[str] = []
    paths = [spec.path for spec in ASSET_SPECS]
    if len(paths) != len(set(paths)):
        errors.append("architecture asset path is declared more than once")
    by_path = {spec.path: spec for spec in ASSET_SPECS}

    sentinels = [spec.loaded_sentinel for spec in ASSET_SPECS]
    if any(not sentinel for sentinel in sentinels):
        errors.append("every architecture asset must declare a loaded_sentinel")
    if len(sentinels) != len(set(sentinels)):
        errors.append("architecture loaded_sentinel must be unique per asset")
    for spec in ASSET_SPECS:
        for required in spec.runtime_requires:
            if required not in by_path:
                errors.append(f"{spec.path}: unknown runtime prerequisite {required}")
            if required == spec.path:
                errors.append(f"{spec.path}: cannot require itself at runtime")
        for conflict in spec.conflicts_with:
            if conflict not in by_path:
                errors.append(f"{spec.path}: unknown conflict asset {conflict}")
            elif spec.path not in by_path[conflict].conflicts_with:
                errors.append(f"{spec.path}: conflict with {conflict} is not symmetric")
            if conflict == spec.path:
                errors.append(f"{spec.path}: cannot conflict with itself")

    # Runtime prerequisites are concrete edges; role dependencies are abstract
    # ownership edges. Pure assets must agree on the role set. Generated carriers
    # inherit the concrete prerequisites of the pure layers they embed.
    for spec in ASSET_SPECS:
        runtime_roles = {by_path[path].role for path in spec.runtime_requires if path in by_path}
        if not spec.generated_from:
            if runtime_roles != set(spec.requires_roles):
                errors.append(
                    f"{spec.path}: runtime prerequisite roles {sorted(runtime_roles)!r} "
                    f"!= declared role dependencies {sorted(spec.requires_roles)!r}"
                )
        else:
            inherited: set[str] = set()
            for source in spec.generated_from:
                if source in by_path:
                    inherited.update(by_path[source].runtime_requires)
            if set(spec.runtime_requires) != inherited:
                errors.append(
                    f"{spec.path}: runtime prerequisites {sorted(spec.runtime_requires)!r} "
                    f"!= inherited generated-source prerequisites {sorted(inherited)!r}"
                )

    roles = set(ROLE_DEPENDENCIES)
    nonlegacy_roles = {spec.role for spec in ASSET_SPECS if not spec.legacy}
    if len(PREFERRED_LAYER_ORDER) != len(set(PREFERRED_LAYER_ORDER)) or set(PREFERRED_LAYER_ORDER) != nonlegacy_roles:
        errors.append(
            "preferred layer order must name every non-legacy role exactly once: "
            f"order={PREFERRED_LAYER_ORDER!r}, roles={sorted(nonlegacy_roles)!r}"
        )

    providers_by_role: dict[str, int] = defaultdict(int)
    for spec in ASSET_SPECS:
        providers_by_role[spec.role] += 1
        if len(spec.provides) != len(set(spec.provides)):
            errors.append(f"{spec.path}: duplicate capability declaration")
        if any(not cap or cap.strip() != cap for cap in spec.provides):
            errors.append(f"{spec.path}: invalid empty/whitespace capability")
        if spec.role not in roles:
            errors.append(f"{spec.path}: unknown role {spec.role}")
        if tuple(spec.requires_roles) != tuple(ROLE_DEPENDENCIES.get(spec.role, ())):
            errors.append(
                f"{spec.path}: requires_roles {spec.requires_roles!r} != role contract "
                f"{ROLE_DEPENDENCIES.get(spec.role, ())!r}"
            )
        for source in spec.generated_from:
            if source not in paths:
                errors.append(f"{spec.path}: generated source not declared: {source}")
        if spec.generated_from and not spec.legacy:
            errors.append(f"{spec.path}: generated artifact must be marked legacy/derived")

    for role, deps in ROLE_DEPENDENCIES.items():
        if role != "compatibility-bundle" and providers_by_role.get(role, 0) == 0:
            errors.append(f"role {role}: no concrete non-generated provider")
        for dep in deps:
            if dep not in roles:
                errors.append(f"role {role}: unknown dependency role {dep}")
            elif providers_by_role.get(dep, 0) == 0:
                errors.append(f"role {role}: dependency role {dep} has no provider")

    if len(providers_for_capability(CAP_MECHANISM_CORE)) != 1:
        errors.append("mechanism-core capability must have exactly one provider")
    if len(providers_for_capability(CAP_LAYOUT_HOOKS)) != 1:
        errors.append("layout-hooks capability must have exactly one provider")
    if len(providers_for_capability(CAP_LANGUAGE_PROFILES)) != 1:
        errors.append("language-profiles capability must have exactly one provider")
    for capability in (CAP_PRESENTATION_HOOKS, CAP_CAPTION_NUMBERING_API):
        if providers_for_capability(capability) != ("assets/preamble.tex",):
            errors.append(f"{capability} must be owned solely by the mechanism core")
    if len(PRESENTATION_HOOKS) != len(set(PRESENTATION_HOOKS)) or any(not name for name in PRESENTATION_HOOKS):
        errors.append("presentation hooks may not contain empty or duplicate names")
    if set(PRESENTATION_HOOKS).intersection(LANGUAGE_HOOKS + tuple(name for name, _ in LAYOUT_HOOK_DEFAULTS)):
        errors.append("mutable presentation hooks may not own language or page layout")
    if len(LANGUAGE_PROFILES) != len(set(LANGUAGE_PROFILES)):
        errors.append("language profile names must be unique")
    for profile in LANGUAGE_PROFILE_SPECS:
        if profile.main_language is not None and profile.main_language not in SUPPORTED_MAIN_LANGUAGES:
            errors.append(f"{profile.name}: invalid main language {profile.main_language!r}")
    if set(LANGUAGE_HOOKS).intersection(name for name, _ in LAYOUT_HOOK_DEFAULTS):
        errors.append("language hooks may not be owned by the layout axis")

    # Cycle detection over role dependencies.
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(role: str, trail: tuple[str, ...]) -> None:
        if role in visiting:
            errors.append("role dependency cycle: " + " -> ".join(trail + (role,)))
            return
        if role in visited:
            return
        visiting.add(role)
        for dep in ROLE_DEPENDENCIES.get(role, ()):
            visit(dep, trail + (role,))
        visiting.remove(role)
        visited.add(role)

    for role in roles:
        visit(role, ())

    # Preferred order must be a valid topological order for non-legacy layers.
    order = {role: i for i, role in enumerate(PREFERRED_LAYER_ORDER)}
    for role in PREFERRED_LAYER_ORDER:
        if role not in roles:
            errors.append(f"preferred layer order names unknown role {role}")
    for role in PREFERRED_LAYER_ORDER:
        for dep in ROLE_DEPENDENCIES.get(role, ()):
            if dep in order and order[dep] >= order[role]:
                errors.append(f"preferred layer order violates dependency {dep} -> {role}")

    # A generated bundle must provide exactly the union of the pure layers it
    # embeds. Missing capabilities under-report legacy behavior; extra capabilities
    # invent behavior that cannot exist in a mechanically generated carrier.
    for spec in ASSET_SPECS:
        if not spec.generated_from:
            continue
        source_caps: set[str] = set()
        for source in spec.generated_from:
            if source in by_path:
                source_caps.update(by_path[source].provides)
        declared = set(spec.provides)
        missing = source_caps.difference(declared)
        extra = declared.difference(source_caps)
        if missing:
            errors.append(
                f"{spec.path}: generated bundle missing source capabilities {sorted(missing)!r}"
            )
        if extra:
            errors.append(
                f"{spec.path}: generated bundle declares capabilities not owned by its sources "
                f"{sorted(extra)!r}"
            )
        if any(by_path[source].legacy for source in spec.generated_from if source in by_path):
            errors.append(f"{spec.path}: generated bundle may not derive from another legacy carrier")
        missing_conflicts = set(spec.generated_from).difference(spec.conflicts_with)
        if missing_conflicts:
            errors.append(
                f"{spec.path}: generated bundle must conflict with its pure source carriers "
                f"{sorted(missing_conflicts)!r}"
            )

    symbol_owners: dict[str, list[str]] = defaultdict(list)
    for spec in ASSET_SPECS:
        symbols = spec.public_symbols
        if len(symbols) != len(set(symbols)) or any(not symbol for symbol in symbols):
            errors.append(f"{spec.path}: invalid/duplicate public TeX symbol declaration")
        if spec.generated_from and symbols:
            errors.append(f"{spec.path}: generated carrier may not own public symbols directly")
        for symbol in symbols:
            symbol_owners[symbol].append(spec.path)
    for symbol, owners in symbol_owners.items():
        if len(owners) != 1:
            errors.append(f"public TeX symbol \\{symbol} has multiple declared owners: {owners!r}")

    # Scoped style hooks deliberately permit neutral defaults plus a visual
    # override. Their carrier set must be explicit and may not acquire semantic,
    # language or global layout ownership through that exception.
    hook_names = [hook.name for hook in REFERENCE_STYLE_HOOK_SPECS]
    if len(hook_names) != len(set(hook_names)) or any(not name for name in hook_names):
        errors.append("reference presentation hooks contain empty or duplicate names")
    forbidden_hooks = set(symbol_owners).union(
        LANGUAGE_HOOKS, (name for name, _ in LAYOUT_HOOK_DEFAULTS), PRESENTATION_HOOKS,
    )
    for hook in REFERENCE_STYLE_HOOK_SPECS:
        if hook.name in forbidden_hooks:
            errors.append(f"reference presentation hook \\{hook.name} collides with an owned API")
        owner = by_path.get(hook.default_provider)
        if owner is None or owner.role != "semantic-extension" or owner.legacy:
            errors.append(f"reference presentation hook \\{hook.name} requires a pure semantic default provider")
        if not hook.overriding_providers or len(hook.overriding_providers) != len(set(hook.overriding_providers)):
            errors.append(f"reference presentation hook \\{hook.name} requires unique explicit theme overrides")
        for provider in hook.overriding_providers:
            override = by_path.get(provider)
            if override is None or override.role != "presentation-theme" or override.legacy:
                errors.append(f"reference presentation hook \\{hook.name} override must be a pure presentation theme")

    config_names = [hook.name for hook in HOOK_SPECS]
    if len(config_names) != len(set(config_names)):
        errors.append("configuration hooks must have unique names")
    for hook in HOOK_SPECS:
        if hook.owner not in by_path:
            errors.append(f"configuration hook {hook.name}: unknown owner {hook.owner}")
        if hook.define_before and hook.define_before != hook.owner:
            errors.append(f"configuration hook {hook.name}: timing must refer to its owner")
        if hook.default_kind not in ("literal", "symbolic"):
            errors.append(f"configuration hook {hook.name}: unknown default kind")
        if hook.scope == "reference-layout" and hook.name not in REFERENCE_COLUMN_SYMBOLS:
            errors.append(f"configuration hook {hook.name}: missing public layout ownership")
    if {hook.name for hook in HOOK_SPECS if hook.scope == "document" and hook.preset_allowed} != {
        name for name, _ in LAYOUT_HOOK_DEFAULTS
    }:
        errors.append("configuration hook inventory must cover every core layout hook")

    return tuple(dict.fromkeys(errors))


def _main() -> int:
    """Small stable query surface for shell maintenance/build consumers."""
    import argparse
    import json

    p = argparse.ArgumentParser(description="query the canonical architecture contract")
    p.add_argument(
        "query",
        choices=(
            "runtime-assets",
            "runtime-basenames",
            "maintenance-basenames",
            "density-exempt-basenames",
            "json",
            "validate",
        ),
    )
    args = p.parse_args()

    if args.query == "runtime-assets":
        for spec in ASSET_SPECS:
            print(spec.path)
    elif args.query == "runtime-basenames":
        for name in architecture_asset_basenames():
            print(name)
    elif args.query == "maintenance-basenames":
        for name in maintenance_sync_basenames():
            print(name)
    elif args.query == "density-exempt-basenames":
        for name in density_exempt_basenames():
            print(name)
    elif args.query == "json":
        print(
            json.dumps(
                {
                    "schema_version": ARCHITECTURE_SCHEMA_VERSION,
                    "assets": [
                        {
                            "path": spec.path,
                            "role": spec.role,
                            "requires_roles": spec.requires_roles,
                            "provides": spec.provides,
                            "public_symbols": spec.public_symbols,
                            "effective_public_symbols": effective_public_symbols(spec),
                            "generated_from": spec.generated_from,
                            "runtime_requires": spec.runtime_requires,
                            "conflicts_with": spec.conflicts_with,
                            "loaded_sentinel": spec.loaded_sentinel,
                            "claims_loaded_sentinels": claimed_loaded_sentinels(spec),
                            "maintenance_sync": spec.maintenance_sync,
                            "density_exempt": spec.density_exempt,
                            "legacy": spec.legacy,
                        }
                        for spec in ASSET_SPECS
                    ],
                    "preferred_layer_order": PREFERRED_LAYER_ORDER,
                    "role_dependencies": ROLE_DEPENDENCIES,
                    "public_tex_symbols": PUBLIC_TEX_SYMBOLS,
                    "presentation_hooks": PRESENTATION_HOOKS,
                    "reference_presentation_hooks": [
                        {"name": hook.name, "default_provider": hook.default_provider,
                         "overriding_providers": hook.overriding_providers}
                        for hook in REFERENCE_STYLE_HOOK_SPECS
                    ],
                    "layout_hook_defaults": dict(LAYOUT_HOOK_DEFAULTS),
                    "configuration_hooks": [
                        {"name": hook.name, "owner": hook.owner, "define_before": hook.define_before,
                         "scope": hook.scope, "value_type": hook.value_type, "unit": hook.unit,
                         "default": hook.default, "default_kind": hook.default_kind,
                         "allowed_values": hook.allowed_values, "minimum": hook.minimum,
                         "minimum_inclusive": hook.minimum_inclusive, "preset_allowed": hook.preset_allowed}
                        for hook in HOOK_SPECS
                    ],
                    "language_hooks": LANGUAGE_HOOKS,
                    "language_hook_defaults": dict(LANGUAGE_HOOK_DEFAULTS),
                    "supported_main_languages": SUPPORTED_MAIN_LANGUAGES,
                    "language_profiles": [
                        {"name": profile.name, "main_language": profile.main_language,
                         "composition": profile.composition}
                        for profile in LANGUAGE_PROFILE_SPECS
                    ],
                    "supported_document_classes": SUPPORTED_DOCUMENT_CLASSES,
                    "build_only_keys": BUILD_ONLY_KEYS,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
    else:
        errors = validate_contract()
        if errors:
            for error in errors:
                print(f"✗ {error}")
            return 1
        print("✓ architecture schema valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
