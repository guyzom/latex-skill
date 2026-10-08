#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Original project code; scope and terms: ../LICENSING.md.
# Additional output permission: ../LICENSES/Generated-Output-Permission.txt.
"""Validate and render the maintained Hebrew-English Studio glossary.

Records explain public vocabulary; they do not duplicate component ownership or
template recipes. This module uses only Python's standard library and executes
neither TeX nor rendering tools.
"""
from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
import re
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RECORDS_PATH = "references/glossary/terms.json"
MARKDOWN_PATH = "references/glossary-he-en.md"
GENERATED_PATHS = frozenset({"references/template-catalog.md", MARKDOWN_PATH})
GLOSSARY_SCHEMA_VERSION = 2
ID = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*\Z")
VERSION = re.compile(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\Z")
AUDIENCES = {"user": "משתמש", "developer": "מפתח", "both": "שניהם"}
STATUSES = {"existing": "קיים בסקיל", "general": "מושג מקצועי", "deprecated": "ממשק שיצא משימוש"}
TOP_KEYS = {"schema_version", "skill_version", "paths", "document", "sections", "terms"}
TERM_KEYS = {
    "id", "hebrew", "english", "definition", "example", "audience", "status",
    "related_ids", "source_refs", "section", "owner", "aliases", "introduced_in", "updated_in",
}


def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def require_text(value: Any, context: str, *, single_line: bool = True) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{context}: requires nonempty text")
    if single_line and any(char in value for char in "\r\n|"):
        raise ValueError(f"{context}: line breaks and table delimiters are not permitted")
    return value


def version_tuple(value: Any, context: str) -> tuple[int, int, int]:
    if not isinstance(value, str) or not VERSION.fullmatch(value):
        raise ValueError(f"{context}: requires a three-part release version")
    return tuple(int(part) for part in value.split("."))


def source_reference(root: Path, reference: str, context: str, *, allow_missing_generated: bool = False) -> None:
    path = PurePosixPath(reference)
    if (
        path.is_absolute() or ".." in path.parts or "\\" in reference
        or "#" in reference or ":" in reference or str(path) != reference
    ):
        raise ValueError(f"{context}: invalid relative source reference {reference}")
    target = root / reference
    probe = root
    for index, part in enumerate(path.parts):
        probe = probe / part
        if probe.is_symlink():
            raise ValueError(f"{context}: symlink source reference {reference}")
        if index < len(path.parts) - 1 and probe.exists() and not probe.is_dir():
            raise ValueError(f"{context}: invalid source reference ancestor {reference}")
    if not target.is_file():
        if allow_missing_generated and reference in GENERATED_PATHS and not target.exists():
            return
        raise ValueError(f"{context}: missing source reference {reference}")


def validate_records(data: Any, root: Path = ROOT, *, catalog: Any | None = None, allow_missing_generated: bool = False) -> None:
    """Validate maintained records, actual source paths and declared catalog coverage."""
    root = Path(root)
    if not isinstance(data, dict) or set(data) != TOP_KEYS:
        raise ValueError("glossary: missing or unknown top-level fields")
    if type(data["schema_version"]) is not int or data["schema_version"] != GLOSSARY_SCHEMA_VERSION:
        raise ValueError("unsupported glossary schema_version")
    release = version_tuple(data["skill_version"], "skill_version")
    actual_version = (root / "VERSION").read_text(encoding="utf-8").strip()
    if data["skill_version"] != actual_version:
        raise ValueError("glossary skill_version does not match VERSION")
    if data["paths"] != {"records": RECORDS_PATH, "markdown": MARKDOWN_PATH}:
        raise ValueError("glossary paths: unexpected installable paths")
    document = data["document"]
    if not isinstance(document, dict) or set(document) != {"intro_markdown", "afterword_markdown"}:
        raise ValueError("document: missing or unknown fields")
    for key, value in document.items():
        require_text(value, f"document.{key}", single_line=False)
        if "{{SKILL_VERSION}}" not in document["intro_markdown"]:
            raise ValueError("document.intro_markdown: requires current version placeholder")
    sections = data["sections"]
    if not isinstance(sections, list) or not sections:
        raise ValueError("sections: requires a nonempty list")
    section_ids: set[str] = set()
    for section in sections:
        if not isinstance(section, dict) or set(section) != {"id", "hebrew"}:
            raise ValueError("section: missing or unknown fields")
        section_id = require_text(section["id"], "section.id")
        if not ID.fullmatch(section_id):
            raise ValueError(f"invalid section id: {section_id}")
        if section_id in section_ids:
            raise ValueError(f"duplicate section id: {section_id}")
        section_ids.add(section_id)
        require_text(section["hebrew"], f"section.{section_id}.hebrew")
    terms = data["terms"]
    if not isinstance(terms, list) or not terms:
        raise ValueError("terms: requires a nonempty list")
    ids: set[str] = set()
    used_sections: set[str] = set()
    for term in terms:
        if not isinstance(term, dict) or set(term) != TERM_KEYS:
            raise ValueError("term: missing or unknown fields")
        term_id = require_text(term["id"], "term.id")
        if not ID.fullmatch(term_id):
            raise ValueError(f"invalid term id: {term_id}")
        if term_id in ids:
            raise ValueError(f"duplicate term id: {term_id}")
        ids.add(term_id)
        for field in ("hebrew", "english", "definition", "example", "owner"):
            require_text(term[field], f"{term_id}.{field}")
        if not re.search(r"[\u0590-\u05ff]", term["hebrew"]):
            raise ValueError(f"{term_id}.hebrew: Hebrew label required")
        if not re.search(r"[A-Za-z]", term["english"]):
            raise ValueError(f"{term_id}.english: English label required")
        for field, allowed in (("audience", AUDIENCES), ("status", STATUSES)):
            if not isinstance(term[field], str) or term[field] not in allowed:
                raise ValueError(f"{term_id}: unknown {field}")
        if not isinstance(term["section"], str) or term["section"] not in section_ids:
            raise ValueError(f"{term_id}: unknown section id")
        used_sections.add(term["section"])
        for field in ("related_ids", "source_refs", "aliases"):
            values = term[field]
            if not isinstance(values, list) or any(not isinstance(v, str) or not v.strip() for v in values):
                raise ValueError(f"{term_id}.{field}: expected a list of nonempty strings")
            if len(values) != len(set(values)):
                raise ValueError(f"{term_id}.{field}: duplicate values")
            for value in values:
                require_text(value, f"{term_id}.{field}")
        if not term["source_refs"]:
            raise ValueError(f"{term_id}.source_refs: at least one reference required")
        for reference in term["source_refs"]:
            source_reference(root, reference, term_id, allow_missing_generated=allow_missing_generated)
        introduced = version_tuple(term["introduced_in"], f"{term_id}.introduced_in")
        updated = version_tuple(term["updated_in"], f"{term_id}.updated_in")
        if not introduced <= updated <= release:
            raise ValueError(f"{term_id}: invalid glossary release chronology")
    if used_sections != section_ids:
        raise ValueError("empty glossary section")
    for term in terms:
        for related in term["related_ids"]:
            if related not in ids:
                raise ValueError(f"{term['id']}: unknown related id {related}")
            if related == term["id"]:
                raise ValueError(f"{term['id']}: self-reference is not useful")
    if catalog is not None:
        record = catalog.as_dict() if hasattr(catalog, "as_dict") else catalog
        if not isinstance(record, dict):
            raise ValueError("catalog glossary coverage: expected canonical catalog")
        required = record.get("required_glossary_terms")
        if not isinstance(required, list) or not required:
            raise ValueError("catalog glossary coverage: missing required_glossary_terms")
        requirements: set[str] = set()

        def walk(value: Any) -> None:
            if isinstance(value, dict):
                for key, item in value.items():
                    if key in {"glossary_refs", "required_glossary_terms"}:
                        if not isinstance(item, list) or not item or any(not isinstance(v, str) for v in item):
                            raise ValueError(f"catalog glossary coverage: invalid {key}")
                        requirements.update(item)
                    else:
                        walk(item)
            elif isinstance(value, list):
                for item in value:
                    walk(item)

        walk(record)
        missing = requirements - ids
        if missing:
            raise ValueError("catalog glossary coverage: unknown term ids " + ", ".join(sorted(missing)))


def load_records(root: Path = ROOT, *, catalog: Any | None = None, allow_missing_generated: bool = False) -> dict[str, Any]:
    root = Path(root)
    data = json.loads((root / RECORDS_PATH).read_text(encoding="utf-8"), object_pairs_hook=reject_duplicate_keys)
    validate_records(data, root, catalog=catalog, allow_missing_generated=allow_missing_generated)
    return data


def render_markdown(data: dict[str, Any]) -> str:
    """Render already-validated records without reading or mutating the source tree."""
    chunks = [
        "<!-- Generated by scripts/generate_studio_docs.py; edit references/glossary/terms.json. -->",
        data["document"]["intro_markdown"].replace("{{SKILL_VERSION}}", data["skill_version"]).rstrip(), "",
    ]
    number = 0
    for section in data["sections"]:
        chunks.extend([
            f"## {section['hebrew']}", "",
            "| # | מונח בעברית ובאנגלית | משמעות מדויקת | דוגמה מעשית | למי | מצב |",
            "|---|---|---|---|---|---|",
        ])
        for term in data["terms"]:
            if term["section"] != section["id"]:
                continue
            number += 1
            label = f"**{term['hebrew']} — {term['english']}**"
            chunks.append(
                f"| {number} | {label} | {term['definition']} | {term['example']} | "
                f"{AUDIENCES[term['audience']]} | {STATUSES[term['status']]} |"
            )
        chunks.append("")
    chunks.extend(["## Stable term references", "", "Stable English headings below support links independent of the translated label.", ""])
    by_id = {term["id"]: term for term in data["terms"]}
    for term in data["terms"]:
        chunks.extend([f"### term-{term['id']}", "", f"**{term['hebrew']} — {term['english']}**. בעל אחריות: {term['owner']}.", ""])
        sources = ", ".join(f"[{ref}](../{ref})" for ref in term["source_refs"])
        chunks.append(f"מקורות וחוזים: {sources}.")
        if term["related_ids"]:
            related = ", ".join(f"[{by_id[key]['english']}](#term-{key})" for key in term["related_ids"])
            chunks.append(f"מונחים קשורים: {related}.")
        if term["aliases"]:
            chunks.append("כינויים: " + ", ".join(term["aliases"]) + ".")
        chunks.extend([f"נוסף למילון ב־{term['introduced_in']}; משמעות נבדקה או עודכנה ב־{term['updated_in']}.", ""])
    chunks.append(data["document"]["afterword_markdown"].rstrip())
    return "\n".join(chunks) + "\n"
