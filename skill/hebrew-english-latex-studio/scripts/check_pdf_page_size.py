#!/usr/bin/env python3
"""Verify that every visible PDF page has the explicitly expected paper size.

The canonical pipeline expects A4. A different supported size is valid only
when the caller selects it explicitly with --expected; this prevents a missing
LaTeX paper option from silently falling back to Letter.
"""

from __future__ import annotations

import sys as _bytecode_sys
_bytecode_sys.dont_write_bytecode = True

import argparse
import sys

from build_contract import PAPERS_MM

try:
    import fitz  # PyMuPDF
    from pdf_geometry import physical_boxes
except ImportError:
    print("check_pdf_page_size: pymupdf not installed — run:")
    print("  python3 -m pip install pymupdf")
    raise SystemExit(2)


PT_PER_MM = 72.0 / 25.4
TOLERANCE_PT = 1.0


def expected_points(name: str) -> tuple[float, float]:
    width_mm, height_mm = PAPERS_MM[name]
    return width_mm * PT_PER_MM, height_mm * PT_PER_MM


def same_paper(
    actual: tuple[float, float], expected: tuple[float, float]
) -> bool:
    """Compare dimensions independent of portrait/landscape orientation."""
    aw, ah = sorted(actual)
    ew, eh = sorted(expected)
    return abs(aw - ew) <= TOLERANCE_PT and abs(ah - eh) <= TOLERANCE_PT


def check(pdf_path: str, expected_name: str = "a4") -> int:
    if expected_name not in PAPERS_MM:
        print(f"ERROR: unsupported expected paper: {expected_name!r}")
        return 2
    expected = expected_points(expected_name)
    mismatches: list[tuple[int, str, float, float]] = []
    try:
        with fitz.open(pdf_path) as doc:
            if not doc.is_pdf or doc.needs_pass or doc.page_count == 0:
                raise ValueError("expected a nonempty, unencrypted PDF")
            count = doc.page_count
            for page_number, page in enumerate(doc, start=1):
                for box_name, actual in physical_boxes(page).items():
                    if not same_paper(actual, expected):
                        mismatches.append((page_number, box_name, *actual))
    except Exception as exc:
        print(f"ERROR: {pdf_path} is not a readable PDF with valid page geometry ({exc}).")
        return 2

    expected_width, expected_height = expected
    for page_number, box_name, width, height in mismatches:
        print(
            f"  ✗ p.{page_number} [PAGE-SIZE-MISMATCH] {box_name} is "
            f"{width:.3f}×{height:.3f} pt; expected "
            f"{expected_name.upper()} "
            f"{expected_width:.3f}×{expected_height:.3f} pt "
            "(portrait or landscape)"
        )
    if mismatches:
        return 1

    print(
        f"  ✓ page-size check clean ({count} page(s): every physical MediaBox "
        f"and CropBox, plus the effective visible page, is {expected_name.upper()})"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify every PDF MediaBox and CropBox against a paper size."
    )
    parser.add_argument("pdf", help="PDF to inspect")
    parser.add_argument(
        "--expected",
        type=str.lower,
        choices=sorted(PAPERS_MM),
        default="a4",
        help="expected paper size (default: a4)",
    )
    args = parser.parse_args(argv)
    return check(args.pdf, args.expected)


if __name__ == "__main__":
    sys.exit(main())
