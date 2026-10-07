#!/usr/bin/env python3
"""Measure specified PDF number/title pairs; this is not an automatic TOC detector.

Coordinates are PDF points, obtained from embedded text geometry (not OCR).
A positive gap means separation. A negative gap means bounding-box overlap.
The caller supplies the expected page, exact label, title anchor and direction.
"""
from __future__ import annotations
import argparse
from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path
import re
import sys
import fitz


def checked_box(value):
    if len(value) != 4 or not all(math.isfinite(float(v)) for v in value):
        raise ValueError('expected four finite coordinates')
    x0, y0, x1, y1 = map(float, value)
    if x1 <= x0 or y1 <= y0:
        raise ValueError('expected a nonempty, ordered bounding box')
    return x0, y0, x1, y1


def horizontal_gap(label_box, title_box, direction='rtl') -> float:
    a, b = checked_box(label_box), checked_box(title_box)
    if direction == 'rtl':
        return a[0] - b[2]
    if direction == 'ltr':
        return b[0] - a[2]
    raise ValueError('direction must be rtl or ltr')


@dataclass(frozen=True)
class Measurement:
    label: str
    title: str
    direction: str
    gap_pt: float
    label_box: tuple
    title_box: tuple
    physical_label: str


def measure(page, label: str, title: str, direction='rtl') -> Measurement:
    if not label or not title:
        raise ValueError('label and title must be nonempty')
    if direction not in ('rtl', 'ltr'):
        raise ValueError('direction must be rtl or ltr')
    # MuPDF can return one search rectangle PER HEBREW GLYPH. Locate the
    # logical anchor in raw line characters and union its glyphs instead of
    # mistaking those fragments for duplicate titles. Fail on real ambiguity.
    lines = [[c for span in line['spans'] for c in span['chars']]
             for block in page.get_text('rawdict')['blocks']
             for line in block.get('lines', [])]
    hits = []
    for chars in lines:
        text = ''.join(c['c'] for c in chars)
        for match in re.finditer(re.escape(title), text):
            run = chars[match.start():match.end()]
            rect = fitz.Rect(run[0]['bbox'])
            for char in run[1:]:
                rect |= fitz.Rect(char['bbox'])
            hits.append(tuple(rect))
    if len(hits) != 1:
        raise ValueError(f'title anchor {title!r}: expected one hit, got {len(hits)}')
    title_box = checked_box(hits[0])
    candidates = []
    pattern = re.compile(r'(?<![\d.])' + re.escape(label) + r'(?![\d.])')
    for block in page.get_text('rawdict')['blocks']:
        for line in block.get('lines', []):
            chars = [c for span in line['spans'] for c in span['chars']]
            text = ''.join(c['c'] for c in chars)
            for match in pattern.finditer(text):
                run = chars[match.start():match.end()]
                rect = fitz.Rect(run[0]['bbox'])
                for char in run[1:]:
                    rect |= fitz.Rect(char['bbox'])
                # Matching the title's baseline allows different fonts/weights
                # but excludes the same digits on other rows or in the folio.
                if not title_box[1] <= run[0]['origin'][1] <= title_box[3]:
                    continue
                if rect.y1 <= title_box[1] or rect.y0 >= title_box[3]:
                    continue
                # A chapter label can equal the page number on the SAME row.
                # Select the number/title side, not the far page-number column.
                centre = (rect.x0 + rect.x1) / 2
                title_centre = (title_box[0] + title_box[2]) / 2
                if (direction == 'rtl' and centre <= title_centre) or (direction == 'ltr' and centre >= title_centre):
                    continue
                candidates.append((tuple(rect), ''.join(c['c'] for c in
                                                       sorted(run, key=lambda c: c['origin'][0]))))
    if len(candidates) != 1:
        raise ValueError(f'label {label!r} on title row {title!r}: expected one hit, got {len(candidates)}')
    box, physical = candidates[0]
    return Measurement(label, title, direction, horizontal_gap(box, title_box, direction),
                       box, title_box, physical)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pdf', type=Path)
    parser.add_argument('--rows', type=Path, required=True,
                        help='JSON array: page (1-based), label, title, direction, min_gap_pt')
    args = parser.parse_args(argv)
    try:
        specs = json.loads(args.rows.read_text(encoding='utf-8'))
        if not isinstance(specs, list) or not specs:
            raise ValueError('rows must be a nonempty JSON array')
        findings = []
        with fitz.open(args.pdf) as doc:
            for spec in specs:
                page = spec['page']
                if type(page) is not int or not 1 <= page <= len(doc):
                    raise ValueError('page is outside this PDF')
                threshold = float(spec.get('min_gap_pt', 3))
                if not math.isfinite(threshold) or threshold < 0:
                    raise ValueError('min_gap_pt must be finite and nonnegative')
                item = asdict(measure(doc[page-1], spec['label'], spec['title'], spec.get('direction', 'rtl')))
                item.update(page=page, min_gap_pt=threshold,
                            passed=item['gap_pt'] >= threshold and item['physical_label'] == spec['label'])
                findings.append(item)
        print(json.dumps({'pdf': str(args.pdf), 'rows': findings,
                          'passed': all(item['passed'] for item in findings)}, ensure_ascii=False, indent=2))
        return 0 if all(item['passed'] for item in findings) else 1
    except (OSError, ValueError, KeyError, TypeError, fitz.FileDataError) as exc:
        parser.exit(2, f'Cannot measure requested rows: {exc}\n')


if __name__ == '__main__':
    raise SystemExit(main())
