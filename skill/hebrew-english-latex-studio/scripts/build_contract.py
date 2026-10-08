#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Original project code; scope and terms: ../LICENSING.md.
# Additional output permission: ../LICENSES/Generated-Output-Permission.txt.
"""Lightweight canonical build-contract definitions.

This module deliberately has no third-party imports.  Build configuration must
be parseable before font discovery, PDF tooling or LuaLaTeX starts.  Checkers
that consume these values import them from here so the package has one source
of truth for supported content profiles, paper sizes and SECTION_MACROS syntax.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import re

OUTPUT_PERMISSION_PATH = "LICENSES/Generated-Output-Permission.txt"
OUTPUT_PERMISSION_SHA256 = "db332369fe4fcb4a6d0f84499cc1c49a0b94f1ceaf063c884a84a36403dee5e1"
GENERATED_OUTPUT_PERMISSION_NAME = "GENERATED-OUTPUT-PERMISSION.txt"


def read_output_permission(root: Path) -> bytes:
    """Retain the approved permission before packaging or project creation."""
    try:
        content = (root / OUTPUT_PERMISSION_PATH).read_bytes()
    except OSError as exc:
        raise ValueError(f"generated output permission missing: {OUTPUT_PERMISSION_PATH}") from exc
    if hashlib.sha256(content).hexdigest() != OUTPUT_PERMISSION_SHA256:
        raise ValueError(f"generated output permission differs: {OUTPUT_PERMISSION_PATH}")
    return content

CONTENT_PROFILES = (
    "generic",
    "study-guide",
    "report",
    "exam",
    "formula-sheet",
    "review-sheet",
)

PAPERS_MM = {
    "a3": (297.0, 420.0),
    "a4": (210.0, 297.0),
    "a5": (148.0, 210.0),
    "letter": (215.9, 279.4),
    "legal": (215.9, 355.6),
}

# These contracts describe printed folios, independently of the document's
# language or theme. Custom geometry is deliberately an explicit manual-QA
# handoff; it must never be reported as verified numbering.
FOLIO_LAYOUTS = ("center", "left", "right", "outer", "inner", "none", "custom")
FOLIO_BANDS = ("footer", "header")
CAPTION_LABEL_WEIGHTS = ("bold", "normal")


def parse_rgb_hex(value: str) -> int:
    """An explicit PDF text color, encoded as exactly six RGB hex digits."""
    if not re.fullmatch(r"[0-9A-Fa-f]{6}", value):
        raise ValueError("caption color must be exactly six hexadecimal RGB digits (RRGGBB)")
    return int(value, 16)


def normalize_section_macros(spec: str) -> tuple[str, ...]:
    """Parse comma/space-separated TeX command names, without backslashes."""
    names: list[str] = []
    for raw in re.split(r"[\s,]+", spec.strip()):
        if not raw:
            continue
        name = raw.lstrip("\\")
        if not re.fullmatch(r"[A-Za-z@]+", name):
            raise ValueError(f"invalid section macro name: {raw!r}")
        if name not in names:
            names.append(name)
    return tuple(names)
