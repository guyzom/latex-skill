#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Original project code; scope and terms: ../LICENSING.md.
"""Explicit review raster backends. No fallback, repair, or visual verdict.

MuPDF is supplied by the already-required PyMuPDF dependency. Page-box changes
are made only in a disposable, in-memory document; source PDFs are never saved.
"""
from __future__ import annotations
from pathlib import Path
import shutil
import subprocess
import sys
sys.dont_write_bytecode = True
import fitz

BACKENDS = ('poppler', 'mupdf')
# Raster guard, not a total-memory guarantee: an A3 page at 300 DPI is ~17.4M.
MAX_PAGE_PIXELS = 50_000_000


def check_backend(backend: str) -> None:
    if backend not in BACKENDS:
        raise ValueError('renderer backend must be poppler or mupdf')
    if backend == 'poppler' and not shutil.which('pdftoppm'):
        raise ValueError('pdftoppm is required for Poppler; no silent renderer substitution')


def check_raster_budget(sizes: list[tuple[int, int]]) -> None:
    for number, (width, height) in enumerate(sizes, 1):
        if width * height > MAX_PAGE_PIXELS:
            raise ValueError(
                f'page {number}: requested raster exceeds {MAX_PAGE_PIXELS:,} pixels; '
                'choose a lower review DPI. No review published.')


def render_pages(source: Path, stage: Path, dpi: int, page_box: str,
                 backend: str, count: int) -> str:
    """Write page-N.png files and return the actual renderer version identity."""
    check_backend(backend)
    if backend == 'poppler':
        command = ['pdftoppm', '-r', str(dpi), '-png']
        if page_box == 'cropbox':
            command.append('-cropbox')
        result = subprocess.run(command + [str(source), str(stage / 'page')],
                                capture_output=True, text=True,
                                timeout=max(120, 30 * count))
        if result.returncode:
            raise ValueError(f'pdftoppm failed: {result.stderr[-2000:]}')
        version = subprocess.run(['pdftoppm', '-v'], capture_output=True,
                                 text=True, timeout=10).stderr.splitlines()
        return version[0] if version else 'pdftoppm'
    with fitz.open(source) as document:
        for number, page in enumerate(document, 1):
            if page_box == 'mediabox':
                # Reapplying the unchanged raw MediaBox removes the other boxes.
                # Unlike set_cropbox(page.mediabox), this also handles nonzero
                # PDF MediaBox origins correctly. Rotation is retained.
                page.set_mediabox(page.mediabox)
            pixmap = page.get_pixmap(dpi=dpi, colorspace=fitz.csRGB,
                                    alpha=False, annots=True)
            pixmap.save(stage / f'page-{number}.png')
            del pixmap
    return f'MuPDF {fitz.VersionFitz} / PyMuPDF {fitz.VersionBind}'
