#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Original project code; scope and terms: ../LICENSING.md.
"""Compare a declared LTR code glyph stream with its expected source.

This bounded probe selects spans by an explicit font-name fragment, sorts
visible characters by page, baseline and x, and compares NON-WHITESPACE Unicode
codepoints without normalization. It does not verify indentation, execute code,
read logical PDF order, or claim to discover arbitrary listings in a document.
Use full-page inspection and raster comparisons alongside it.
Exit 0: match; 1: glyph-order/content mismatch; 2: bad input/extraction/tool error.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any
sys.dont_write_bytecode = True


def compact(text: str) -> str:
    return ''.join(c for c in text if not c.isspace())


def order_glyphs(glyphs: list[dict[str, Any]], tolerance: float = 0.5) -> list[dict[str, Any]]:
    """Group by baseline before sorting x; never rely on PDF object order."""
    if not 0 < tolerance <= 1:
        raise ValueError('baseline tolerance must be in (0,1] PDF points')
    ordered: list[dict[str, Any]] = []
    for page in sorted({g['page'] for g in glyphs}):
        rows: list[list[dict[str, Any]]] = []
        for g in sorted((x for x in glyphs if x['page'] == page), key=lambda x: (x['origin'][1], x['origin'][0])):
            if not rows or abs(g['origin'][1] - rows[-1][0]['origin'][1]) > tolerance:
                rows.append([])
            rows[-1].append(g)
        for row in rows:
            ordered.extend(sorted(row, key=lambda g: g['origin'][0]))
    return ordered


def probe(pdf_path: Path, lines: list[str], font_contains: str = 'DejaVuSansMono') -> dict[str, Any]:
    if not isinstance(lines, list) or not lines or not all(isinstance(x, str) for x in lines):
        raise ValueError('lines must be a nonempty list of source strings')
    expected = compact('\n'.join(lines))
    if not expected:
        raise ValueError('expected source has no visible characters')
    if not isinstance(font_contains, str) or not font_contains.strip():
        raise ValueError('font_contains must be a nonempty font-name fragment')
    import fitz
    glyphs: list[dict[str, Any]] = []
    with fitz.open(pdf_path) as doc:
        if doc.needs_pass or not len(doc):
            raise ValueError('PDF must be readable without a password and have pages')
        pages = len(doc)
        for page_index, page in enumerate(doc, 1):
            for block in page.get_text('rawdict')['blocks']:
                for line in block.get('lines', []):
                    for span in line['spans']:
                        if font_contains not in span['font']:
                            continue
                        for ch in span['chars']:
                            if ch['c'].isspace():
                                continue
                            glyphs.append({'c': ch['c'], 'page': page_index,
                                           'origin': list(ch['origin']), 'bbox': list(ch['bbox']),
                                           'font': span['font']})
    if not glyphs:
        raise ValueError('no glyphs matched the declared font; cannot verify code')
    ordered = order_glyphs(glyphs)
    actual = ''.join(ch['c'] for ch in ordered)
    first = next((i for i, (a, b) in enumerate(zip(actual, expected)) if a != b), None)
    if first is None and len(actual) != len(expected):
        first = min(len(actual), len(expected))
    return {'schema': 1, 'pdf_sha256': hashlib.sha256(pdf_path.read_bytes()).hexdigest(),
            'pages': pages, 'font_contains': font_contains, 'expected_lines': len(lines),
            'comparison': 'non-whitespace Unicode codepoints; page/baseline/x order; no normalization',
            'expected': expected, 'actual': actual, 'match': actual == expected,
            'first_mismatch': first, 'glyphs': ordered}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('pdf', type=Path)
    p.add_argument('--expected', type=Path, required=True, help='JSON: {"lines": [...], "font_contains": "..."}')
    p.add_argument('--output', type=Path, help='optional NEW JSON evidence file, never overwrite')
    args = p.parse_args(argv)
    try:
        config = json.loads(args.expected.read_text(encoding='utf-8'))
        if not isinstance(config, dict) or set(config) - {'lines', 'font_contains'} or 'lines' not in config:
            raise ValueError('expected JSON must contain lines and optional font_contains only')
        result = probe(args.pdf, config['lines'], config.get('font_contains', 'DejaVuSansMono'))
        result['expected_sha256'] = hashlib.sha256(args.expected.read_bytes()).hexdigest()
        if args.output:
            with args.output.open('x', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
                f.write('\n')
        print(('PASS' if result['match'] else 'MISMATCH') + ': declared code glyph stream; indentation not checked')
        return 0 if result['match'] else 1
    except (OSError, ValueError, TypeError, ImportError, RuntimeError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
