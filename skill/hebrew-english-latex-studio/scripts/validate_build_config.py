#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Original project code; scope and terms: ../LICENSING.md.
"""Validate build-time configuration before LuaLaTeX starts.

Configuration mistakes are environment/tooling failures (exit 2), not document
quality findings (exit 1) and not advisory density warnings.  Keeping this
preflight separate prevents a typo such as CONTENT_PROFILE=exma from producing
and publishing a PDF and only then being swallowed by the advisory checker.
"""
from __future__ import annotations

import sys as _bytecode_sys
_bytecode_sys.dont_write_bytecode = True

import argparse
import sys

from build_contract import (
    CONTENT_PROFILES as PROFILES,
    FOLIO_LAYOUTS,
    FOLIO_BANDS,
    CAPTION_LABEL_WEIGHTS,
    parse_rgb_hex,
    PAPERS_MM,
    normalize_section_macros,
)


def nonnegative_int(name: str, value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a non-negative integer (got {value!r})") from exc
    if parsed < 0:
        raise ValueError(f"{name} must be a non-negative integer (got {value!r})")
    return parsed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--content-profile", default="generic")
    parser.add_argument("--expected-paper", default="a4")
    parser.add_argument("--section-macros", default="")
    parser.add_argument("--repro", default="0")
    parser.add_argument("--max-cross-page-destinations", default="0")
    parser.add_argument("--source-date-epoch", default="1700000000")
    parser.add_argument("--folio-layout", default="center")
    parser.add_argument("--folio-band", default="footer")
    parser.add_argument("--caption-color", default="000000")
    parser.add_argument("--caption-label-weight", default="normal")
    args = parser.parse_args(argv)

    errors: list[str] = []
    if args.caption_label_weight not in CAPTION_LABEL_WEIGHTS:
        errors.append("PDF_CAPTION_LABEL_WEIGHT must be one of: "
                      + ", ".join(CAPTION_LABEL_WEIGHTS)
                      + f" (got {args.caption_label_weight!r})")
    try:
        parse_rgb_hex(args.caption_color)
    except ValueError as exc:
        errors.append(f"PDF_CAPTION_COLOR: {exc} (got {args.caption_color!r})")
    if args.folio_layout not in FOLIO_LAYOUTS:
        errors.append("PDF_FOLIO_LAYOUT must be one of: " + ", ".join(FOLIO_LAYOUTS)
                      + f" (got {args.folio_layout!r})")
    if args.folio_band not in FOLIO_BANDS:
        errors.append("PDF_FOLIO_BAND must be one of: " + ", ".join(FOLIO_BANDS)
                      + f" (got {args.folio_band!r})")
    if args.content_profile not in PROFILES:
        errors.append(
            "CONTENT_PROFILE must be one of: " + ", ".join(PROFILES)
            + f" (got {args.content_profile!r})"
        )
    if args.expected_paper not in PAPERS_MM:
        errors.append(
            "EXPECTED_PAPER must be one of: " + ", ".join(sorted(PAPERS_MM))
            + f" (got {args.expected_paper!r})"
        )
    try:
        normalize_section_macros(args.section_macros)
    except ValueError as exc:
        errors.append(f"SECTION_MACROS: {exc}")
    if args.repro not in {"0", "1"}:
        errors.append(f"REPRO must be 0 or 1 (got {args.repro!r})")
    try:
        nonnegative_int("MAX_CROSS_PAGE_DESTINATIONS", args.max_cross_page_destinations)
    except ValueError as exc:
        errors.append(str(exc))
    try:
        nonnegative_int("SOURCE_DATE_EPOCH", args.source_date_epoch)
    except ValueError as exc:
        errors.append(str(exc))

    if errors:
        for err in errors:
            print(f"❌ build configuration: {err}")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
