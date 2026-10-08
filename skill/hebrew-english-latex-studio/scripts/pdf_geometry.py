#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Original project code; scope and terms: ../LICENSING.md.
"""Physical page dimensions, without assuming one PDF user unit is one point.

This helper does not normalize, repair or write PDFs. Invalid numeric page
geometry is a tooling error rather than a successful paper-size comparison.
"""
from __future__ import annotations
import math
import re
import sys
sys.dont_write_bytecode = True
import fitz

_NUMBER = re.compile(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)\Z')
_REFERENCE = re.compile(r'(\d+)\s+\d+\s+R\Z')


def user_unit(page: fitz.Page) -> float:
    """Read a finite positive /UserUnit, including an indirect numeric object."""
    kind, value = page.parent.xref_get_key(page.xref, 'UserUnit')
    if kind == 'null':
        return 1.0
    if kind not in ('int', 'float', 'xref'):
        raise ValueError('PDF UserUnit must be a numeric scalar')
    seen: set[int] = set()
    while match := _REFERENCE.fullmatch(value.strip()):
        xref = int(match[1])
        if xref in seen or len(seen) >= 16:
            raise ValueError('cyclic or excessively indirect PDF UserUnit')
        seen.add(xref)
        value = page.parent.xref_object(xref, compressed=True).strip()
    if not _NUMBER.fullmatch(value):
        raise ValueError('PDF UserUnit must be a numeric scalar')
    result = float(value)
    if not math.isfinite(result) or result <= 0:
        raise ValueError('PDF UserUnit must be finite and positive')
    return result


def physical_boxes(page: fitz.Page) -> dict[str, tuple[float, float]]:
    """Return MediaBox, CropBox and effective visible dimensions in points.

    The raw two boxes are unrotated. VisibleBox follows MuPDF's effective
    rectangle, including rotation, clipping and unit scaling.
    """
    scale = user_unit(page)
    boxes = {
        'MediaBox': (page.mediabox.width * scale, page.mediabox.height * scale),
        'CropBox': (page.cropbox.width * scale, page.cropbox.height * scale),
        'VisibleBox': (page.rect.width, page.rect.height),
    }
    if any(not math.isfinite(x) or x <= 0 for dims in boxes.values() for x in dims):
        raise ValueError('PDF page dimensions must be finite and positive')
    return boxes


def raster_dimensions(page: fitz.Page, page_box: str, dpi: int) -> tuple[int, int]:
    boxes = physical_boxes(page)
    if page_box == 'cropbox':
        width, height = boxes['VisibleBox']
    elif page_box == 'mediabox':
        width, height = boxes['MediaBox']
        if page.rotation % 180:
            width, height = height, width
    else:
        raise ValueError('page box must be cropbox or mediabox')
    return math.ceil(width * dpi / 72), math.ceil(height * dpi / 72)
