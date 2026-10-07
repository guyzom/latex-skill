#!/usr/bin/env python3
"""Lightweight canonical build-contract definitions.

This module deliberately has no third-party imports.  Build configuration must
be parseable before font discovery, PDF tooling or LuaLaTeX starts.  Checkers
that consume these values import them from here so the package has one source
of truth for supported content profiles, paper sizes and SECTION_MACROS syntax.
"""
from __future__ import annotations

import re

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
