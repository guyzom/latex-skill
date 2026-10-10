#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Original project code; scope and terms: ../LICENSING.md.
# Additional output permission: ../LICENSES/Generated-Output-Permission.txt.
"""Validate and resolve the closed, declarative Studio template catalog.

This module selects owned assets and existing composition handlers. It executes
no catalog code, expands no arbitrary TeX, installs nothing, and writes nothing.
Creation-time declarations remain distinct from compile/render/visual evidence.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, fields
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat
import sys
from typing import Any, Iterator

sys.dont_write_bytecode = True
import architecture_contract as architecture
import build_contract as build

ROOT = Path(__file__).resolve().parent.parent
CATALOG_PATH = "registry/studio-catalog.json"
CATALOG_SCHEMA_VERSION = 2
BILINGUAL_COMPOSERS = ("paired-bodies", "paper-shared-frontmatter", "reference-paired-pages", "paired-full-pages")
MINORITY_COMPOSERS = ("append-note", "paper-summary", "reference-topic-note", "letter-before-signature")
SOURCE_HANDLERS = ("declare-note-language", "data-heading-guard")
OPTIONAL_SPECIMENS = ("study", "index")
OPTIONAL_SPECIMEN_APIS = {"study": architecture.STUDY_COMPONENT_SYMBOLS,
                          "index": architecture.INDEX_COMPONENT_SYMBOLS}
BUILD_DEFAULT_NAMES = ("EXPECTED_PAPER", "PDF_FOLIO_LAYOUT", "PDF_FOLIO_BAND", "PDF_CAPTION_COLOR", "PDF_CAPTION_LABEL_WEIGHT", "INDEX_PROCESSOR", "INDEX_STYLE")
IDENTIFIER = re.compile(r"[a-z][a-z0-9-]*\Z")
NUMBER = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?\Z")
DIMENSION = re.compile(r"([+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+))(pt|mm|cm|in|bp|pc|dd|cc|sp|em|ex)\Z")
GENERATED_DOCUMENTATION = ("references/template-catalog.md", "references/catalog-development.md")


class CatalogError(ValueError):
    """A catalog or recipe violates an explicit, closed contract."""


class Record:
    def as_dict(self) -> dict[str, Any]:
        def plain(value: Any) -> Any:
            if isinstance(value, tuple):
                return [plain(item) for item in value]
            if isinstance(value, dict):
                return {key: plain(item) for key, item in value.items()}
            return value
        return plain(asdict(self))


@dataclass(frozen=True)
class StarterSpec(Record):
    language: str
    asset_path: str
    sha256: str
    declared_hooks: tuple[tuple[str, str], ...]

    def as_dict(self) -> dict[str, Any]:
        return {"language": self.language, "asset_path": self.asset_path, "sha256": self.sha256,
                "declared_hooks": dict(self.declared_hooks)}


@dataclass(frozen=True)
class TemplateSpec(Record):
    id: str
    recipe_revision: int
    title: tuple[tuple[str, str], ...]
    use: str
    starters: tuple[StarterSpec, ...]
    content_profile: str
    default_layout: str
    default_theme: str | None
    bilingual_composer_id: str
    minority_composer_id: str
    source_handlers: tuple[str, ...]
    copy_extra: tuple[str, ...]
    build_defaults: tuple[tuple[str, str], ...]
    docs: tuple[str, ...]
    glossary_refs: tuple[str, ...]
    acceptance: tuple[str, ...]


@dataclass(frozen=True)
class HookOverride(Record):
    name: str
    value: str
    owner: str
    unit: str
    phase: str


@dataclass(frozen=True)
class LayoutSpec(Record):
    id: str
    recipe_revision: int
    title: tuple[tuple[str, str], ...]
    allowed_kinds: tuple[str, ...]
    starter_overrides: tuple[StarterSpec, ...]
    default_theme: str | None
    bilingual_composer_id: str | None
    minority_composer_id: str | None
    hook_overrides: tuple[HookOverride, ...]
    components: tuple[str, ...]
    build_defaults: tuple[tuple[str, str], ...]
    docs: tuple[str, ...]
    glossary_refs: tuple[str, ...]
    acceptance: tuple[str, ...]


@dataclass(frozen=True)
class ThemeSpec(Record):
    id: str
    title: tuple[tuple[str, str], ...]
    exposure: str
    mode: str
    asset_path: str | None
    copy_stage: str
    local_filename: str | None
    caption_contract: tuple[tuple[str, str], ...]
    build_defaults: tuple[tuple[str, str], ...]
    docs: tuple[str, ...]
    glossary_refs: tuple[str, ...]
    acceptance: tuple[str, ...]


@dataclass(frozen=True)
class ExampleSpec(Record):
    id: str
    asset_path: str
    architecture_assets: tuple[str, ...]
    language_profile: str
    docs: tuple[str, ...]
    glossary_refs: tuple[str, ...]
    acceptance: tuple[str, ...]


@dataclass(frozen=True)
class ComponentSpec(Record):
    """Explicit optional source integration; runtime ownership stays in ASSET_SPECS."""
    id: str
    title: tuple[tuple[str, str], ...]
    asset_path: str
    specimen_id: str
    supporting_files: tuple[str, ...]
    allowed_kinds: tuple[str, ...]
    allowed_layouts: tuple[str, ...]
    language_profiles: tuple[str, ...]
    build_defaults: tuple[tuple[str, str], ...]
    docs: tuple[str, ...]
    glossary_refs: tuple[str, ...]
    acceptance: tuple[str, ...]


@dataclass(frozen=True)
class StudioCatalog(Record):
    schema_version: int
    sha256: str
    language_contract: str
    asset_contract: str
    build_contract: str
    default_theme: str
    base_copy_plan: tuple[str, ...]
    required_glossary_terms: tuple[str, ...]
    templates: tuple[TemplateSpec, ...]
    layouts: tuple[LayoutSpec, ...]
    themes: tuple[ThemeSpec, ...]
    examples: tuple[ExampleSpec, ...]
    components: tuple[ComponentSpec, ...]

    def as_dict(self) -> dict[str, Any]:
        def record(item: Record) -> dict[str, Any]:
            result = item.as_dict()
            if hasattr(item, "title"):
                result["title"] = dict(item.title)
            if isinstance(item, (TemplateSpec, LayoutSpec)):
                field = "starters" if isinstance(item, TemplateSpec) else "starter_overrides"
                result[field] = [entry.as_dict() for entry in getattr(item, field)]
            if isinstance(item, ThemeSpec):
                result["caption_contract"] = dict(item.caption_contract)
            return result
        return {"schema_version": self.schema_version, "sha256": self.sha256,
                "language_contract": self.language_contract, "asset_contract": self.asset_contract,
                "build_contract": self.build_contract, "default_theme": self.default_theme,
                "base_copy_plan": list(self.base_copy_plan), "required_glossary_terms": list(self.required_glossary_terms),
                "templates": [record(item) for item in self.templates],
                "layouts": [record(item) for item in self.layouts],
            "themes": [record(item) for item in self.themes], "examples": [record(item) for item in self.examples],
            "components": [record(item) for item in self.components]}


@dataclass(frozen=True)
class RecipeRequest(Record):
    kind: str
    language: str = "hebrew"
    main_language: str | None = None
    theme: str | None = None
    layout: str = "standard"
    components: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        result = super().as_dict()
        if not self.components:
            del result["components"]
        return result


@dataclass(frozen=True)
class Resolution(Record):
    field: str
    value: str
    provenance: str


@dataclass(frozen=True)
class ResolvedHook(Record):
    name: str
    value: str
    owner: str
    provenance: str
    unit: str
    value_type: str
    value_kind: str = "literal"


@dataclass(frozen=True)
class ResolvedRecipe(Record):
    requested: RecipeRequest
    kind: str
    language_profile: str
    main_language: str
    theme: str
    layout: str
    content_profile: str
    components: tuple[str, ...]
    recipe_revision: int
    layout_revision: int
    catalog_sha256: str
    resolutions: tuple[Resolution, ...]
    starter_variants: tuple[tuple[str, str], ...]
    composer_id: str
    minority_composer_id: str
    source_handlers: tuple[str, ...]
    hooks: tuple[ResolvedHook, ...]
    preset_bindings: tuple[tuple[str, str], ...]
    copy_plan: tuple[str, ...]
    load_plan: tuple[str, ...]
    package_scan_plan: tuple[str, ...]
    build_defaults: tuple[tuple[str, str], ...]
    presentation_input: str | None
    caption_contract: tuple[tuple[str, str], ...]

    @property
    def main_starter(self) -> str:
        return Path(dict(self.starter_variants)[self.main_language]).name

    def as_dict(self) -> dict[str, Any]:
        result = super().as_dict()
        result["resolved"] = {name: getattr(self, name) for name in
                              ("kind", "language_profile", "main_language", "theme", "layout", "content_profile")}
        result["provenance"] = {entry.field: entry.provenance for entry in self.resolutions}
        result["status"] = "creation-time declarations; no compile, render or visual validation"
        return result


def _object(value: Any, keys: set[str], context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CatalogError(f"{context}: expected an object")
    unknown, missing = set(value) - keys, keys - set(value)
    if unknown or missing:
        raise CatalogError(f"{context}: unknown fields {sorted(unknown)}, missing fields {sorted(missing)}")
    return value


def _string(value: Any, context: str, *, empty: bool = False) -> str:
    if not isinstance(value, str) or (not empty and not value) or value.strip() != value:
        raise CatalogError(f"{context}: expected a literal string")
    return value


def _strings(value: Any, context: str, *, unique: bool = True) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise CatalogError(f"{context}: expected an array")
    result = tuple(_string(item, context) for item in value)
    if unique and len(result) != len(set(result)):
        raise CatalogError(f"{context}: duplicate values")
    return result


def _id(value: Any, context: str) -> str:
    text = _string(value, context)
    if not IDENTIFIER.fullmatch(text):
        raise CatalogError(f"{context}: invalid stable identifier {text!r}")
    return text


def safe_owned_path(root: Path, relative: Any, *, must_exist: bool = True) -> Path:
    """Reject absolute, traversing, ambiguous or symlinked catalog-owned paths."""
    text = _string(relative, "asset path")
    path = PurePosixPath(text)
    if (not re.fullmatch(r"[A-Za-z0-9_./-]+", text) or path.is_absolute()
            or path.as_posix() != text or any(part in ("", ".", "..") for part in text.split("/"))):
        raise CatalogError(f"unsafe owned path: {text!r}")
    root = Path(root).absolute()
    for ancestor in reversed((root,) + tuple(root.parents)):
        if ancestor.is_symlink():
            raise CatalogError(f"symlinked skill root or ancestor: {ancestor}")
    root = root.resolve()
    if not root.is_dir():
        raise CatalogError("skill root must be a directory")
    current = root
    for part in path.parts:
        current = current / part
        if current.is_symlink():
            raise CatalogError(f"symlinked owned path: {text!r}")
    if not current.resolve().is_relative_to(root):
        raise CatalogError(f"owned path leaves skill root: {text!r}")
    if must_exist and (not current.exists() or not stat.S_ISREG(current.stat().st_mode)):
        raise CatalogError(f"missing owned file: {text}")
    return current


def _pairs(value: Any, context: str) -> tuple[tuple[str, str], ...]:
    if not isinstance(value, list):
        raise CatalogError(f"{context}: expected an array of pairs")
    pairs = []
    for item in value:
        if not isinstance(item, list) or len(item) != 2:
            raise CatalogError(f"{context}: expected a name/value pair")
        pairs.append((_string(item[0], context), _string(item[1], context)))
    if len({name for name, _ in pairs}) != len(pairs):
        raise CatalogError(f"{context}: duplicate names")
    return tuple(pairs)


def finite_decimal(value: Any, context: str = "numeric hook") -> Decimal:
    """Validate ASCII lexical form and finiteness without rewriting literals."""
    text = _string(value, context)
    try:
        number = Decimal(text)
    except InvalidOperation as exc:
        raise CatalogError(f"{context}: invalid decimal {text!r}") from exc
    if not number.is_finite() or not NUMBER.fullmatch(text):
        raise CatalogError(f"{context}: requires a finite decimal literal")
    return number


def canonical_decimal(value: Decimal) -> str:
    """Storage spelling only; never use to rewrite a starter's source literal."""
    if not isinstance(value, Decimal) or not value.is_finite():
        raise CatalogError("canonical decimal requires a finite Decimal")
    return format(value.normalize(), "f") if value else "0"


def validate_hook_value(name: str, value: Any) -> str:
    spec = next((item for item in architecture.HOOK_SPECS if item.name == name), None)
    if spec is None or not spec.preset_allowed:
        raise CatalogError(f"unsupported preset hook: {name}")
    text = _string(value, name)
    numeric: Decimal | None = None
    if spec.value_type == "enum":
        if text not in spec.allowed_values:
            raise CatalogError(f"{name}: unsupported value {text!r}")
    elif spec.value_type in ("decimal", "integer"):
        numeric = finite_decimal(text, name)
        if spec.value_type == "integer" and not re.fullmatch(r"[+-]?[0-9]+", text):
            raise CatalogError(f"{name}: requires an integer literal")
        if "e" in text.lower():
            raise CatalogError(f"{name}: TeX numeric hooks do not accept exponent notation")
    elif spec.value_type == "dimension":
        match = DIMENSION.fullmatch(text)
        if not match:
            raise CatalogError(f"{name}: requires a literal TeX dimension")
        numeric = finite_decimal(match.group(1), name)
    elif spec.value_type == "class-options":
        if not re.fullmatch(r"(?:10pt|11pt|12pt),(?:a4paper|letterpaper)", text):
            raise CatalogError(f"{name}: unsupported owned class options {text!r}")
    elif spec.value_type == "geometry-options":
        allowed = {"margin", "left", "right", "top", "bottom", "headheight", "headsep", "footskip"}
        seen = set()
        for item in text.split(","):
            key, separator, literal = item.partition("=")
            match = DIMENSION.fullmatch(literal)
            if not separator or key not in allowed or key in seen or not match:
                raise CatalogError(f"{name}: unsupported owned geometry declaration {text!r}")
            if finite_decimal(match.group(1), name) < 0:
                raise CatalogError(f"{name}: negative geometry dimension")
            seen.add(key)
    else:
        raise CatalogError(f"{name}: unsupported catalog value type")
    if numeric is not None and spec.minimum is not None:
        minimum = Decimal(spec.minimum)
        if numeric < minimum or (numeric == minimum and not spec.minimum_inclusive):
            raise CatalogError(f"{name}: value is below its declared minimum")
    return text


def _without_comments(source: str) -> str:
    # Scope is the skill's bounded literal starter grammar, not arbitrary TeX.
    return "\n".join(line.split("%", 1)[0] for line in source.splitlines())


def extract_owned_declarations(source: str) -> tuple[tuple[str, str], ...]:
    header, separator, _ = source.partition(r"\begin{document}")
    if not separator:
        raise CatalogError("owned starter lacks a document boundary")
    header = _without_comments(header)
    known = {hook.name: hook for hook in architecture.HOOK_SPECS if hook.preset_allowed}
    declarations = []
    for name, value in re.findall(r"\\def\\([A-Za-z]+)\{([^{}]*)\}", header):
        if name in known:
            if name in dict(declarations):
                raise CatalogError(f"owned starter declares {name} more than once")
            owner_input = r"\input{" + Path(known[name].owner).name + "}"
            owner_position = header.find(owner_input)
            declaration_position = header.find("\\def\\" + name + "{" + value + "}")
            if owner_position < 0 or declaration_position > owner_position:
                raise CatalogError(f"owned starter declares {name} after or without its owner")
            declarations.append((name, validate_hook_value(name, value)))
    return tuple(declarations)


def _validate_starter(spec: StarterSpec, root: Path) -> None:
    path = safe_owned_path(root, spec.asset_path)
    content = path.read_bytes()
    if hashlib.sha256(content).hexdigest() != spec.sha256:
        raise CatalogError(f"{spec.asset_path}: starter fingerprint drift; revise recipe explicitly")
    if dict(extract_owned_declarations(content.decode("utf-8"))) != dict(spec.declared_hooks):
        raise CatalogError(f"{spec.asset_path}: declared hook drift")


def _starter(value: Any, root: Path) -> StarterSpec:
    item = _object(value, {"language", "asset_path", "sha256", "declared_hooks"}, "starter")
    language = _string(item["language"], "starter language")
    if language not in architecture.SUPPORTED_MAIN_LANGUAGES:
        raise CatalogError("starter language must reference the language contract")
    path = _string(item["asset_path"], "starter path")
    if not re.fullmatch(r"assets/starter_[a-z_]+\.tex", path):
        raise CatalogError("starter must be an explicitly owned starter asset")
    fingerprint = _string(item["sha256"], "starter fingerprint")
    if not re.fullmatch(r"[a-f0-9]{64}", fingerprint):
        raise CatalogError("starter requires a SHA-256 fingerprint")
    hooks = item["declared_hooks"]
    if not isinstance(hooks, dict):
        raise CatalogError("declared_hooks must be a mapping")
    declarations = tuple((name, validate_hook_value(name, value)) for name, value in hooks.items())
    result = StarterSpec(language, path, fingerprint, declarations)
    _validate_starter(result, root)
    return result


def _starters(value: Any, root: Path, *, optional: bool = False) -> tuple[StarterSpec, ...]:
    if not isinstance(value, list):
        raise CatalogError("starters must be an array")
    result = tuple(_starter(item, root) for item in value)
    if optional and not result:
        return result
    if tuple(item.language for item in result) != architecture.SUPPORTED_MAIN_LANGUAGES:
        raise CatalogError("starter variants must explicitly list Hebrew then English exactly once")
    if len({item.asset_path for item in result}) != len(result):
        raise CatalogError("starter variants require distinct paths")
    return result


def _metadata(item: dict[str, Any], root: Path, *, allow_missing_generated_docs: bool = False) -> dict[str, Any]:
    title = _object(item["title"], {"he", "en"}, "title") if "title" in item else None
    metadata: dict[str, Any] = {}
    if title is not None:
        metadata["title"] = tuple((language, _string(title[language], "title")) for language in ("he", "en"))
    for name in ("docs", "glossary_refs", "acceptance"):
        metadata[name] = _strings(item[name], name)
        if not metadata[name]:
            raise CatalogError(f"catalog record requires {name}")
    for path in metadata["docs"]:
        safe_owned_path(root, path, must_exist=not (allow_missing_generated_docs and path in GENERATED_DOCUMENTATION))
        if not path.startswith("references/") or not path.endswith(".md"):
            raise CatalogError("documentation references must name owned reference Markdown files")
    for term in metadata["glossary_refs"]:
        _id(term, "glossary term")
    return metadata


def _revision(value: Any) -> int:
    if type(value) is not int or value < 1:
        raise CatalogError("recipe revision must be a positive integer")
    return value


def _build_defaults(value: Any) -> tuple[tuple[str, str], ...]:
    result = _pairs(value, "build defaults")
    if any(name not in BUILD_DEFAULT_NAMES for name, _ in result):
        raise CatalogError("unknown build default; build contracts remain with build_contract")
    allowed = {"EXPECTED_PAPER": tuple(build.PAPERS_MM), "PDF_FOLIO_LAYOUT": build.FOLIO_LAYOUTS,
               "PDF_FOLIO_BAND": build.FOLIO_BANDS, "PDF_CAPTION_LABEL_WEIGHT": build.CAPTION_LABEL_WEIGHTS,
               "INDEX_PROCESSOR": build.INDEX_PROCESSORS}
    for name, value in result:
        if name in allowed and value not in allowed[name]:
            raise CatalogError(f"invalid build default for {name}")
        if name == "PDF_CAPTION_COLOR":
            build.parse_rgb_hex(value)
        if name == "INDEX_STYLE":
            build.validate_index_style(value)
    if dict(result).get("INDEX_STYLE") and dict(result).get("INDEX_PROCESSOR") != "makeindex":
        raise CatalogError("index style requires the makeindex processor")
    return result


def _reject_constant(value: str) -> None:
    raise CatalogError(f"nonfinite JSON number: {value}")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise CatalogError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _architecture_assets(root: Path) -> dict[str, architecture.AssetSpec]:
    errors = architecture.validate_contract()
    if errors:
        raise CatalogError("invalid architecture contract: " + "; ".join(errors))
    assets = {spec.path: spec for spec in architecture.ASSET_SPECS}
    visiting: set[str] = set()
    visited: set[str] = set()
    def visit(path: str) -> None:
        if path in visiting:
            raise CatalogError(f"architecture dependency cycle at {path}")
        if path in visited:
            return
        visiting.add(path)
        for dependency in assets[path].runtime_requires:
            visit(dependency)
        visiting.remove(path)
        visited.add(path)
    for path in assets:
        safe_owned_path(root, path)
        visit(path)
    return assets


def load_catalog(root: Path = ROOT, *, allow_missing_generated_docs: bool = False) -> StudioCatalog:
    root = Path(root)
    payload = safe_owned_path(root, CATALOG_PATH).read_bytes()
    try:
        raw = json.loads(payload, object_pairs_hook=_unique_object, parse_float=Decimal, parse_constant=_reject_constant)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise CatalogError(f"invalid catalog JSON: {exc}") from exc
    keys = {"schema_version", "language_contract", "asset_contract", "build_contract", "default_theme",
            "base_copy_plan", "required_glossary_terms", "templates", "layouts", "themes", "examples", "components"}
    raw = _object(raw, keys, "catalog")
    if type(raw["schema_version"]) is not int or raw["schema_version"] != CATALOG_SCHEMA_VERSION:
        raise CatalogError("unsupported catalog schema")
    for field, expected in (("language_contract", "architecture_contract.LANGUAGE_PROFILE_SPECS"),
                            ("asset_contract", "architecture_contract.ASSET_SPECS"), ("build_contract", "build_contract")):
        if raw[field] != expected:
            raise CatalogError(f"{field}: contract ownership cannot be redefined")
    assets = _architecture_assets(root)
    def paths(value: Any, context: str) -> tuple[str, ...]:
        result = _strings(value, context)
        for path in result:
            safe_owned_path(root, path)
            if path not in assets:
                raise CatalogError(f"{context}: unknown architecture asset {path}")
        return result
    templates = []
    for value in raw["templates"] if isinstance(raw["templates"], list) else [None]:
        item = _object(value, {field.name for field in fields(TemplateSpec)}, "template")
        if item["bilingual_composer_id"] not in BILINGUAL_COMPOSERS or item["minority_composer_id"] not in MINORITY_COMPOSERS:
            raise CatalogError("unknown closed content composer")
        handlers = _strings(item["source_handlers"], "source handlers")
        if any(handler not in SOURCE_HANDLERS for handler in handlers):
            raise CatalogError("unknown closed source handler")
        profile = _string(item["content_profile"], "content profile")
        if profile not in build.CONTENT_PROFILES:
            raise CatalogError("unknown advisory content profile")
        templates.append(TemplateSpec(id=_id(item["id"], "template id"), recipe_revision=_revision(item["recipe_revision"]),
            use=_string(item["use"], "template use"), starters=_starters(item["starters"], root), content_profile=profile,
            default_layout=_id(item["default_layout"], "default layout"),
            default_theme=None if item["default_theme"] is None else _id(item["default_theme"], "default theme"),
            bilingual_composer_id=item["bilingual_composer_id"], minority_composer_id=item["minority_composer_id"],
            source_handlers=handlers, copy_extra=paths(item["copy_extra"], "template copy assets"),
            build_defaults=_build_defaults(item["build_defaults"]), **_metadata(item, root, allow_missing_generated_docs=allow_missing_generated_docs)))
    layouts = []
    specs = {hook.name: hook for hook in architecture.HOOK_SPECS}
    for value in raw["layouts"] if isinstance(raw["layouts"], list) else [None]:
        item = _object(value, {field.name for field in fields(LayoutSpec)}, "layout")
        overrides = []
        if not isinstance(item["hook_overrides"], list):
            raise CatalogError("hook overrides must be an array")
        for value in item["hook_overrides"]:
            declaration = _object(value, {field.name for field in fields(HookOverride)}, "hook override")
            name = _string(declaration["name"], "hook name")
            literal = validate_hook_value(name, declaration["value"])
            spec = specs[name]
            if declaration["owner"] != spec.owner or declaration["unit"] != spec.unit or declaration["phase"] != "before-owner":
                raise CatalogError(f"{name}: wrong owner, unit or definition phase")
            overrides.append(HookOverride(name, literal, spec.owner, spec.unit, "before-owner"))
        if len({hook.name for hook in overrides}) != len(overrides):
            raise CatalogError("duplicate hook overrides")
        if item["bilingual_composer_id"] not in (None,) + BILINGUAL_COMPOSERS or item["minority_composer_id"] not in (None,) + MINORITY_COMPOSERS:
            raise CatalogError("unknown closed layout content composer")
        default_theme = item["default_theme"]
        if default_theme is not None:
            default_theme = _id(default_theme, "layout default theme")
        layouts.append(LayoutSpec(id=_id(item["id"], "layout id"), recipe_revision=_revision(item["recipe_revision"]),
            allowed_kinds=_strings(item["allowed_kinds"], "allowed kinds"), starter_overrides=_starters(item["starter_overrides"], root, optional=True),
            default_theme=default_theme, bilingual_composer_id=item["bilingual_composer_id"], minority_composer_id=item["minority_composer_id"],
            hook_overrides=tuple(overrides), components=paths(item["components"], "layout components"),
            build_defaults=_build_defaults(item["build_defaults"]), **_metadata(item, root, allow_missing_generated_docs=allow_missing_generated_docs)))
    themes = []
    for value in raw["themes"] if isinstance(raw["themes"], list) else [None]:
        item = _object(value, {field.name for field in fields(ThemeSpec)}, "theme")
        exposure, mode, stage = item["exposure"], item["mode"], item["copy_stage"]
        if exposure not in ("generator-supported", "manual-supported", "legacy"):
            raise CatalogError("unknown theme exposure")
        if mode not in ("asset", "none", "local-file") or stage not in ("before-layout", "after-layout", "none"):
            raise CatalogError("unknown theme mode or copy phase")
        asset = item["asset_path"]
        if mode == "asset":
            asset = _string(asset, "theme asset path")
            if asset not in assets or assets[asset].role not in ("presentation-theme", "compatibility-bundle"):
                raise CatalogError("theme must reference an owned presentation asset")
            if item["local_filename"] is not None or (exposure == "generator-supported" and stage == "none"):
                raise CatalogError("asset theme has an invalid local filename or copy phase")
        elif asset is not None or stage != "none" or item["local_filename"] != ("theme.tex" if mode == "local-file" else None):
            raise CatalogError("none/local theme may not claim an architecture asset")
        caption = _object(item["caption_contract"], {"label_color", "label_weight"}, "caption contract")
        if not isinstance(caption["label_color"], str) or caption["label_weight"] not in build.CAPTION_LABEL_WEIGHTS:
            raise CatalogError("invalid caption contract")
        build.parse_rgb_hex(caption["label_color"])
        themes.append(ThemeSpec(id=_id(item["id"], "theme id"), exposure=exposure, mode=mode, asset_path=asset,
            copy_stage=stage, local_filename=item["local_filename"], caption_contract=tuple(caption.items()),
            build_defaults=_build_defaults(item["build_defaults"]), **_metadata(item, root, allow_missing_generated_docs=allow_missing_generated_docs)))
    components = []
    for value in raw["components"] if isinstance(raw["components"], list) else [None]:
        item = _object(value, {field.name for field in fields(ComponentSpec)}, "optional component")
        asset = _string(item["asset_path"], "component asset path")
        if asset not in assets or assets[asset].role != "semantic-extension" or assets[asset].legacy:
            raise CatalogError("optional component must reference an owned semantic extension")
        supporting = _strings(item["supporting_files"], "supporting files")
        for path in supporting:
            safe_owned_path(root, path)
            if not re.fullmatch(r"assets/[a-z][a-z0-9_-]*\.ist", path):
                raise CatalogError("component supporting files must be flat owned index style assets")
        if item["specimen_id"] not in OPTIONAL_SPECIMENS:
            raise CatalogError("unknown closed optional specimen composer")
        if not set(OPTIONAL_SPECIMEN_APIS[item["specimen_id"]]) <= set(architecture.effective_public_symbols(assets[asset])):
            raise CatalogError("optional specimen requires its semantic owner's public API")
        components.append(ComponentSpec(id=_id(item["id"], "component id"), asset_path=asset, specimen_id=item["specimen_id"],
            supporting_files=supporting, allowed_kinds=_strings(item["allowed_kinds"], "component kinds"),
            allowed_layouts=_strings(item["allowed_layouts"], "component layouts"),
            language_profiles=_strings(item["language_profiles"], "component language profiles"),
            build_defaults=_build_defaults(item["build_defaults"]),
            **_metadata(item, root, allow_missing_generated_docs=allow_missing_generated_docs)))
    examples = []
    for value in raw["examples"] if isinstance(raw["examples"], list) else [None]:
        item = _object(value, {field.name for field in fields(ExampleSpec)}, "example")
        path = _string(item["asset_path"], "example path")
        safe_owned_path(root, path)
        if not re.fullmatch(r"assets/example_[a-z_]+\.tex", path):
            raise CatalogError("example must reference an owned example asset")
        if item["language_profile"] not in architecture.LANGUAGE_PROFILES:
            raise CatalogError("example language profile is unknown")
        example_assets = paths(item["architecture_assets"], "example architecture assets")
        actual = tuple("assets/" + name for name in re.findall(r"\\input\{([^{}]+)\}", _without_comments((root / path).read_text())))
        if actual != example_assets:
            raise CatalogError(f"{path}: example architecture input drift")
        _validate_load_plan(example_assets, assets)
        examples.append(ExampleSpec(id=_id(item["id"], "example id"), asset_path=path,
            architecture_assets=example_assets, language_profile=item["language_profile"], **_metadata(item, root, allow_missing_generated_docs=allow_missing_generated_docs)))
    for name, collection in (("templates", templates), ("layouts", layouts), ("themes", themes), ("examples", examples), ("components", components)):
        if not collection or len({item.id for item in collection}) != len(collection):
            raise CatalogError(f"{name}: empty collection or duplicate IDs")
    catalog = StudioCatalog(schema_version=CATALOG_SCHEMA_VERSION, sha256=hashlib.sha256(payload).hexdigest(),
        language_contract=raw["language_contract"], asset_contract=raw["asset_contract"], build_contract=raw["build_contract"],
        default_theme=_id(raw["default_theme"], "catalog default theme"), base_copy_plan=paths(raw["base_copy_plan"], "base copy plan"),
        required_glossary_terms=_strings(raw["required_glossary_terms"], "required glossary terms"),
        templates=tuple(templates), layouts=tuple(layouts), themes=tuple(themes), examples=tuple(examples), components=tuple(components))
    kinds = {item.id for item in templates}
    layout_ids = {item.id for item in layouts}
    public_themes = {item.id for item in themes if item.exposure == "generator-supported"}
    if catalog.default_theme not in public_themes:
        raise CatalogError("catalog default theme must be generator-supported")
    for template in templates:
        if template.default_layout not in layout_ids or (template.default_theme is not None and template.default_theme not in public_themes):
            raise CatalogError(f"{template.id}: unknown or unsupported default")
        default_layout = next(item for item in layouts if item.id == template.default_layout)
        if template.id not in default_layout.allowed_kinds:
            raise CatalogError(f"{template.id}: default layout forbids its own template kind")
    for layout in layouts:
        if not layout.allowed_kinds or not set(layout.allowed_kinds) <= kinds:
            raise CatalogError(f"{layout.id}: empty or unknown allowed kinds")
        if layout.default_theme is not None and layout.default_theme not in public_themes:
            raise CatalogError(f"{layout.id}: unsupported default theme")
    for component in components:
        if not component.allowed_kinds or not set(component.allowed_kinds) <= kinds:
            raise CatalogError(f"{component.id}: empty or unknown component kinds")
        if not component.allowed_layouts or not set(component.allowed_layouts) <= layout_ids:
            raise CatalogError(f"{component.id}: empty or unknown component layouts")
        if not component.language_profiles or not set(component.language_profiles) <= set(architecture.LANGUAGE_PROFILES):
            raise CatalogError(f"{component.id}: empty or unknown component language profiles")
        defaults = dict(component.build_defaults)
        if component.specimen_id == "index" and (defaults.get("INDEX_PROCESSOR") != "makeindex" or not defaults.get("INDEX_STYLE")):
            raise CatalogError(f"{component.id}: index specimen requires managed makeindex and an owned style default")
        if defaults.get("INDEX_STYLE") and "assets/" + defaults["INDEX_STYLE"] not in component.supporting_files:
            raise CatalogError(f"{component.id}: index style default is missing from supporting files")
    known_starters = {entry.asset_path for template in templates for entry in template.starters}
    known_starters.update(entry.asset_path for layout in layouts for entry in layout.starter_overrides)
    if known_starters != {path.relative_to(root).as_posix() for path in (root / "assets").glob("starter_*.tex")}:
        raise CatalogError("catalog starter inventory must match all owned starter files")
    if {example.asset_path for example in examples} != {path.relative_to(root).as_posix() for path in (root / "assets").glob("example_*.tex")}:
        raise CatalogError("catalog example inventory must match all owned example files")
    # Validate every supported route in both source variants, not only defaults.
    for layout in catalog.layouts:
        for kind in layout.allowed_kinds:
            for language in architecture.SUPPORTED_MAIN_LANGUAGES:
                for theme in public_themes:
                    resolve_recipe(kind, language=language, theme=theme, layout=layout.id, root=root, catalog=catalog)
    return catalog


def _validate_load_plan(plan: tuple[str, ...], assets: dict[str, architecture.AssetSpec]) -> None:
    state: frozenset[str] = frozenset()
    owners: dict[str, str] = {}
    themes = 0
    for path in plan:
        if path == "theme.tex":
            themes += 1
            continue
        if path not in assets:
            raise CatalogError(f"unknown load-plan asset: {path}")
        spec = assets[path]
        themes += spec.role == "presentation-theme"
        diagnostic, state = architecture.simulate_runtime_load(path, state)
        if diagnostic:
            raise CatalogError(f"invalid asset load plan: {diagnostic}")
        for symbol in architecture.effective_public_symbols(spec):
            if symbol in owners:
                raise CatalogError(f"multiple semantic owners for {symbol}")
            owners[symbol] = path
    if themes > 1:
        raise CatalogError("recipe may select only one theme")


def resolve_recipe(kind: str, *, language: str = "hebrew", main_language: str | None = None,
                   theme: str | None = None, layout: str = "standard", components: tuple[str, ...] | list[str] = (), root: Path = ROOT,
                   catalog: StudioCatalog | None = None) -> ResolvedRecipe:
    root = Path(root)
    catalog = load_catalog(root) if catalog is None else catalog
    for name, value in (("kind", kind), ("language", language), ("layout", layout)):
        if not isinstance(value, str):
            raise CatalogError(f"{name}: expected a string selection")
    for name, value in (("theme", theme), ("main_language", main_language)):
        if value is not None and not isinstance(value, str):
            raise CatalogError(f"{name}: expected a string selection or None")
    templates = {item.id: item for item in catalog.templates}
    layouts = {item.id: item for item in catalog.layouts}
    if kind not in templates:
        raise CatalogError(f"unknown document kind: {kind!r}")
    if layout not in layouts:
        raise CatalogError(f"unknown layout: {layout!r}")
    template, layout_spec = templates[kind], layouts[layout]
    if kind not in layout_spec.allowed_kinds:
        raise CatalogError("reference layouts require the formula-sheet document kind" if layout.startswith("reference-") else f"{layout}: kind is not allowed")
    resolved_theme = theme or layout_spec.default_theme or template.default_theme or catalog.default_theme
    themes = {item.id: item for item in catalog.themes if item.exposure == "generator-supported"}
    if resolved_theme not in themes or theme == "":
        raise CatalogError(f"unknown theme: {theme!r}")
    theme_spec = themes[resolved_theme]
    base = architecture.resolve_language_profile(language, main_language)
    if not isinstance(components, (tuple, list)) or any(not isinstance(item, str) for item in components):
        raise CatalogError("components: expected a sequence of literal component IDs")
    components = tuple(components)
    if len(set(components)) != len(components):
        raise CatalogError("duplicate optional component selection")
    component_by_id = {item.id: item for item in catalog.components}
    chosen_components = []
    for name in components:
        if name not in component_by_id:
            raise CatalogError(f"unknown optional component: {name!r}")
        component = component_by_id[name]
        if kind not in component.allowed_kinds or layout not in component.allowed_layouts or language not in component.language_profiles:
            raise CatalogError(f"{name}: optional component does not support this kind, layout or language profile")
        chosen_components.append(component)
    source_specs = layout_spec.starter_overrides or template.starters
    for spec in source_specs:
        _validate_starter(spec, root)
    selected = next(spec for spec in source_specs if spec.language == base)
    variants = tuple((spec.language, spec.asset_path) for spec in source_specs)
    provenance = "explicit" if theme is not None else "layout-default" if layout_spec.default_theme else "template-default" if template.default_theme else "catalog-default"
    resolutions = (Resolution("kind", kind, "explicit"), Resolution("layout", layout, "requested-or-cli-default"),
                   Resolution("theme", resolved_theme, provenance), Resolution("language_profile", language, "requested-or-cli-default"),
                   Resolution("main_language", base, "explicit" if main_language is not None else "language-contract"))
    if components:
        resolutions += (Resolution("components", ",".join(components), "explicit"),)
    copied = list(catalog.base_copy_plan)
    if theme_spec.copy_stage == "before-layout":
        copied.append(theme_spec.asset_path)
    copied.extend(layout_spec.components)
    if theme_spec.copy_stage == "after-layout":
        copied.append(theme_spec.asset_path)
    copied.extend(template.copy_extra)
    for component in chosen_components:
        copied.extend((component.asset_path, *component.supporting_files))
    if len(copied) != len(set(copied)):
        raise CatalogError("copy plan repeats an architecture asset")
    assets = {spec.path: spec for spec in architecture.ASSET_SPECS}
    support_files = {path for component in chosen_components for path in component.supporting_files}
    for path in copied:
        safe_owned_path(root, path)
        if path in support_files:
            continue
        if path not in assets:
            raise CatalogError(f"unknown copied architecture asset: {path}")
        if not set(assets[path].runtime_requires) <= set(copied):
            raise CatalogError(f"copy plan lacks dependency closure for {path}")
        if set(assets[path].conflicts_with).intersection(copied):
            raise CatalogError(f"copy plan contains conflicting assets for {path}")
    header = _without_comments((root / selected.asset_path).read_text().partition(r"\begin{document}")[0])
    loaded = ["assets/" + name for name in re.findall(r"\\input\{([^{}]+)\}", header)]
    loaded = [path for path in loaded if path not in assets or assets[path].role != "presentation-theme"]
    loaded.extend(component.asset_path for component in chosen_components)
    presentation = Path(theme_spec.asset_path).name if theme_spec.asset_path else theme_spec.local_filename
    if presentation:
        loaded.append(theme_spec.asset_path or presentation)
    for path in loaded:
        if path != "theme.tex" and path not in copied:
            raise CatalogError(f"loaded asset is missing from copy plan: {path}")
    _validate_load_plan(tuple(loaded), assets)
    resolved_hooks = []
    literal = dict(selected.declared_hooks)
    overrides = {item.name: item for item in layout_spec.hook_overrides}
    for spec in architecture.HOOK_SPECS:
        if not spec.preset_allowed or spec.owner not in loaded:
            continue
        if spec.name in overrides:
            item = overrides[spec.name]
            if item.owner != spec.owner or item.unit != spec.unit or item.phase != "before-owner":
                raise CatalogError(f"{spec.name}: wrong hook contract")
            value, origin, value_kind = validate_hook_value(spec.name, item.value), "layout-preset:" + layout, "literal"
        elif spec.name in literal:
            value, origin, value_kind = literal[spec.name], "starter:" + selected.asset_path, "literal"
        else:
            value, origin, value_kind = spec.default, "owner-default:" + spec.owner, spec.default_kind
        if value_kind == "literal":
            validate_hook_value(spec.name, value)
        resolved_hooks.append(ResolvedHook(spec.name, value, spec.owner, origin, spec.unit, spec.value_type, value_kind))
    values = {hook.name: hook for hook in resolved_hooks}
    if any(name not in values or values[name].owner not in loaded for name in overrides):
        raise CatalogError("preset hook owner is not loaded by this recipe")
    math_names = ("ReferenceMathFontSize", "ReferenceMathScriptSize", "ReferenceMathScriptScriptSize")
    body_names = ("ReferenceBodyFontSize", "ReferenceBodyBaseline")
    if all(name in values and values[name].value_kind == "literal" for name in body_names):
        body, baseline = (finite_decimal(values[name].value, name) for name in body_names)
        if baseline < body:
            raise CatalogError("reference baseline must not be smaller than body font size")
    if all(name in values and values[name].value_kind == "literal" for name in math_names):
        main, script, scriptscript = (finite_decimal(values[name].value, name) for name in math_names)
        if not Decimal(0) < scriptscript <= script <= main:
            raise CatalogError("reference math sizes require 0 < scriptscript <= script <= main")
    defaults = list(template.build_defaults)
    defaults.extend(layout_spec.build_defaults)
    defaults.extend(theme_spec.build_defaults)
    for component in chosen_components:
        defaults.extend(component.build_defaults)
    merged = {}
    for name, value in defaults:
        if name in merged and merged[name] != value:
            raise CatalogError(f"conflicting build defaults: {name}")
        merged[name] = value
    return ResolvedRecipe(requested=RecipeRequest(kind, language, main_language, theme, layout, components), kind=kind,
        language_profile=language, main_language=base, theme=resolved_theme, layout=layout,
        content_profile=template.content_profile, components=components, recipe_revision=template.recipe_revision,
        layout_revision=layout_spec.recipe_revision, catalog_sha256=catalog.sha256, resolutions=resolutions,
        starter_variants=variants, composer_id=layout_spec.bilingual_composer_id or template.bilingual_composer_id,
        minority_composer_id=layout_spec.minority_composer_id or template.minority_composer_id,
        source_handlers=template.source_handlers, hooks=tuple(resolved_hooks),
        preset_bindings=tuple((item.name, item.value) for item in layout_spec.hook_overrides),
        copy_plan=tuple(copied), load_plan=tuple(loaded),
        package_scan_plan=tuple(path for path in copied if path in assets) + ((selected.asset_path,) if layout_spec.starter_overrides else ()),
        build_defaults=tuple(merged.items()), presentation_input=presentation, caption_contract=theme_spec.caption_contract)


def compatibility_tables(catalog: StudioCatalog | None = None, *, root: Path = ROOT) -> tuple[dict[str, tuple[str, str]], tuple[str, ...], tuple[str, ...], dict[str, dict[str, Any]]]:
    catalog = load_catalog(root) if catalog is None else catalog
    kinds = {item.id: (Path(item.starters[0].asset_path).name, item.content_profile) for item in catalog.templates}
    themes = tuple(item.id for item in catalog.themes if item.exposure == "generator-supported")
    layouts = tuple(item.id for item in catalog.layouts)
    keys = ("columns", "body_font_size", "body_baseline", "math_font_size", "math_script_size", "math_scriptscript_size")
    names = ("ReferenceColumnCount", "ReferenceBodyFontSize", "ReferenceBodyBaseline", "ReferenceMathFontSize", "ReferenceMathScriptSize", "ReferenceMathScriptScriptSize")
    presets = {}
    for layout in catalog.layouts:
        if layout.starter_overrides:
            values = {item.name: item.value for item in layout.hook_overrides}
            if set(names) - set(values):
                raise CatalogError("reference compatibility preset lacks required bindings")
            presets[layout.id] = {key: int(values[name]) if key == "columns" else values[name] for key, name in zip(keys, names)}
    return kinds, themes, layouts, presets


def iter_supported_requests(catalog: StudioCatalog | None = None, *, include_explicit_themes: bool = True,
                            include_default_theme: bool = True, root: Path = ROOT) -> Iterator[RecipeRequest]:
    catalog = load_catalog(root) if catalog is None else catalog
    themes: tuple[str | None, ...] = tuple(item.id for item in catalog.themes if item.exposure == "generator-supported") if include_explicit_themes else ()
    if include_default_theme:
        themes += (None,)
    for layout in catalog.layouts:
        for kind in layout.allowed_kinds:
            for profile in architecture.LANGUAGE_PROFILE_SPECS:
                bases = architecture.SUPPORTED_MAIN_LANGUAGES if profile.main_language is None else (None,)
                for base in bases:
                    for theme in themes:
                        yield RecipeRequest(kind, profile.name, base, theme, layout.id)


get_catalog = load_catalog


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("list", "validate", "resolve"))
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--kind", default="general")
    parser.add_argument("--language", default="hebrew")
    parser.add_argument("--main-language")
    parser.add_argument("--theme")
    parser.add_argument("--layout", default="standard")
    parser.add_argument("--component", action="append", default=[], help="explicit optional component; repeat to combine")
    args = parser.parse_args()
    try:
        catalog = load_catalog(args.root)
        if args.command == "resolve":
            result = resolve_recipe(args.kind, language=args.language, main_language=args.main_language,
                                    theme=args.theme, layout=args.layout, components=args.component, root=args.root, catalog=catalog).as_dict()
            print(json.dumps(result, ensure_ascii=False, indent=2))
        elif args.command == "list":
            if args.json:
                print(json.dumps(catalog.as_dict(), ensure_ascii=False, indent=2))
            else:
                for name in ("templates", "layouts", "themes", "examples", "components"):
                    print(name + ": " + ", ".join(item.id for item in getattr(catalog, name)))
        elif args.json:
            print(json.dumps({"status": "valid", "schema_version": catalog.schema_version, "sha256": catalog.sha256,
                              "templates": len(catalog.templates), "layouts": len(catalog.layouts),
                              "themes": len(catalog.themes), "examples": len(catalog.examples), "components": len(catalog.components),
                              "scope": "declarations and source contracts only; no PDF validation"}, indent=2))
        else:
            print("✓ Studio catalog valid; declarations only, no PDF validation")
    except (OSError, ValueError) as exc:
        print(f"✗ catalog validation failed: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
