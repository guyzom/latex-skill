#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Original project code; scope and terms: ../LICENSING.md.
"""Render a PDF for manual review and verify evidence tied to exact PDF/image bytes.

Rendering starts every page as pending. Verification never claims that a human
actually inspected a page, nor that accessibility or scientific content passed.
"""
from __future__ import annotations
import argparse
import hashlib
import html
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
import fitz
from atomic_replace import atomic_replace
from pdf_geometry import raster_dimensions
from render_backends import BACKENDS, check_backend, check_raster_budget, render_pages


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def page_count(pdf: Path) -> int:
    with fitz.open(pdf) as doc:
        if not doc.is_pdf or doc.needs_pass or len(doc) == 0:
            raise ValueError('expected a nonempty, unencrypted PDF')
        return len(doc)


def render(pdf: Path, output: Path, dpi: int = 144, *,
           page_box: str = "cropbox", backend: str = "poppler") -> None:
    if page_box not in ("cropbox", "mediabox"):
        raise ValueError("page box must be cropbox or mediabox")
    if type(dpi) is not int or not 72 <= dpi <= 300:
        raise ValueError('review DPI must be between 72 and 300')
    output = output.expanduser().absolute()
    if output.exists() or output.is_symlink():
        raise ValueError('output already exists; use a new review directory')
    check_backend(backend)
    count = page_count(pdf)
    pdf_hash = digest(pdf)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.hllpdf-review-', dir=output.parent) as td:
        stage = Path(td) / 'review'
        stage.mkdir()
        # A fixed source copy ensures a concurrent edit cannot mix input versions.
        source = Path(td) / 'source.pdf'
        shutil.copyfile(pdf, source)
        if digest(source) != pdf_hash:
            raise ValueError('PDF changed while preparing the review')
        with fitz.open(source) as document:
            expected_sizes = [raster_dimensions(p, page_box, dpi) for p in document]
        check_raster_budget(expected_sizes)
        renderer = render_pages(source, stage, dpi, page_box, backend, count)
        images = sorted(stage.glob('page-*.png'), key=lambda p: int(p.stem.split('-')[-1]))
        if len(images) != count or [int(p.stem.split('-')[-1]) for p in images] != list(range(1, count+1)):
            raise ValueError('renderer did not produce exactly one image for every PDF page')
        sizes = []
        with fitz.open(source) as document:
            for page, image in zip(document, images):
                expected = raster_dimensions(page, page_box, dpi)
                pix = fitz.Pixmap(str(image))
                actual = (pix.width, pix.height)
                if any(abs(a - b) > 1 for a, b in zip(actual, expected)):
                    raise ValueError(
                        f'page {page.number + 1}: renderer geometry mismatch: '
                        f'{actual} px; expected {expected} px for {page_box}. '
                        'The renderer may not honor PDF UserUnit; no review published.')
                sizes.append(actual)
        data = {'schema': 3, 'renderer_backend': backend,
                'page_box': page_box, 'pdf_name': pdf.name, 'pdf_sha256': pdf_hash,
                'page_count': count, 'dpi': dpi, 'renderer': renderer,
                'meaning': 'Recorded visual-review attestations, not automatic visual certification.',
                'pages': [{'page': i, 'image': image.name, 'sha256': digest(image),
                           'width_px': sizes[i-1][0], 'height_px': sizes[i-1][1],
                           'status': 'pending', 'reviewer': '', 'notes': ''}
                          for i, image in enumerate(images, 1)]}
        (stage / 'review.json').write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        figures = '\n'.join(f'<figure><figcaption>עמוד {i}</figcaption><a href="{html.escape(p.name)}"><img loading="lazy" src="{html.escape(p.name)}" alt="עמוד {i}"></a></figure>'
                            for i, p in enumerate(images, 1))
        document = '''<!doctype html><html lang="he" dir="rtl"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>בדיקה חזותית — '''+html.escape(pdf.name)+'''</title>
<style>body{font:18px/1.6 system-ui,sans-serif;max-width:1100px;margin:2rem auto;padding:0 1rem;background:#f2f3f4;color:#202b33}h1{line-height:1.2}figure{margin:2rem 0}figcaption{font-weight:bold;margin-bottom:.4rem}img{display:block;width:100%;height:auto;box-shadow:0 1px 8px #999}code{direction:ltr;unicode-bidi:isolate}aside{background:white;padding:1rem;border-right:4px solid #243f50}</style>
<h1>בדיקה חזותית</h1><p>מנוע: <code>'''+html.escape(renderer)+'''</code>; רזולוציה: <code>'''+str(dpi)+''' DPI</code>; אזור הרינדור: <code>'''+html.escape(page_box)+'''</code></p><aside>כל העמודים מתחילים במצב <code>pending</code>.
יש לפתוח כל תמונה ולבדוק אותה בגודל קריא; תמונות ממוזערות אינן מספיקות.
לאחר בדיקה ממשית בלבד, משתמשים בפקודת <code>record</code> עם מספרי
העמודים שנבדקו, זהות הבודק והערות. רק העמודים שנבחרו מסומנים <code>reviewed</code>.
האימות <code>verify --rerender</code> בודק גם התאמה לרינדור חדש של ה־PDF.
אין בכך הוכחה מי הסתכל בתמונות, אישור נגישות או בדיקת תוכן.</aside>
'''+figures+'\n</html>\n'
        (stage / 'index.html').write_text(document, encoding='utf-8')
        if digest(pdf) != pdf_hash:
            raise ValueError('PDF changed during rendering; refusing stale review output')
        if output.exists() or output.is_symlink():
            raise ValueError('output appeared during rendering')
        stage.rename(output)


def verify(pdf: Path, review_path: Path, *, require_attestations: bool = True,
           rerender: bool = False) -> list[str]:
    data = json.loads(review_path.read_text(encoding='utf-8'))
    if not isinstance(data, dict) or type(data.get('schema')) is not int or data['schema'] not in (1, 2, 3):
        raise ValueError('unsupported review schema')
    if data['schema'] == 3:
        backend = data.get('renderer_backend')
        if backend not in BACKENDS:
            raise ValueError('schema 3 requires an explicit renderer backend')
    else:
        # Legacy review artifacts were always produced by Poppler. A backend
        # field cannot retroactively convert them into another renderer's proof.
        if data.get('renderer_backend', 'poppler') != 'poppler':
            raise ValueError('legacy review schemas require the Poppler backend')
        backend = 'poppler'
    # Schema 1 predates explicit box policy and used Poppler's MediaBox.
    # Never reinterpret an old attestation as proof of a cropped render.
    if data['schema'] == 1:
        if data.get('page_box', 'mediabox') != 'mediabox':
            raise ValueError('legacy schema 1 cannot declare a different page box')
        page_box = 'mediabox'
    else:
        page_box = data.get('page_box')
        if page_box not in ('cropbox', 'mediabox'):
            raise ValueError('schema 2/3 requires an explicit cropbox or mediabox policy')
    errors: list[str] = []
    dpi = data.get('dpi')
    if type(dpi) is not int or not 72 <= dpi <= 300:
        raise ValueError('review DPI must be an integer between 72 and 300')
    if not isinstance(data.get('renderer'), str) or not data['renderer'].strip():
        raise ValueError('review renderer identity is required')
    if data['schema'] == 3:
        prefix = 'pdftoppm' if backend == 'poppler' else 'MuPDF '
        if not data['renderer'].startswith(prefix):
            raise ValueError('renderer identity disagrees with the declared backend')
    if data.get('pdf_sha256') != digest(pdf):
        errors.append('PDF digest differs: render and review the changed PDF again')
    count = page_count(pdf)
    if type(data.get('page_count')) is not int or data['page_count'] != count:
        errors.append('PDF page count differs from review')
    with fitz.open(pdf) as document:
        expected_sizes = [raster_dimensions(page, page_box, dpi) for page in document]
    pages = data.get('pages')
    if not isinstance(pages, list) or len(pages) != count:
        raise ValueError('review must contain exactly one record per PDF page')
    seen: set[int] = set()
    seen_images: set[str] = set()
    for item in pages:
        if not isinstance(item, dict):
            raise ValueError('page review entry must be an object')
        number = item.get('page')
        if type(number) is not int or not 1 <= number <= count or number in seen:
            raise ValueError('duplicate, missing or invalid page number')
        seen.add(number)
        name = item.get('image')
        if not isinstance(name, str) or not re.fullmatch(r'page-0*[1-9][0-9]*\.png', name):
            raise ValueError('unsafe or invalid image path')
        if int(name[5:-4]) != number or name in seen_images:
            raise ValueError('image filename does not identify its recorded page')
        seen_images.add(name)
        image = review_path.parent / name
        if image.is_symlink() or not image.is_file():
            errors.append(f'page {number}: missing image or forbidden symlink')
        elif item.get('sha256') != digest(image):
            errors.append(f'page {number}: image digest differs')
        if image.is_file() and not image.is_symlink():
            pix = fitz.Pixmap(str(image))
            actual_size = (pix.width, pix.height)
            if any(abs(a - b) > 1 for a, b in zip(actual_size, expected_sizes[number-1])):
                errors.append(f'page {number}: image geometry differs from the declared PDF page box')
            if data['schema'] >= 2:
                if (type(item.get('width_px')) is not int or
                    type(item.get('height_px')) is not int or
                    (item['width_px'], item['height_px']) != actual_size):
                    errors.append(f'page {number}: recorded pixel dimensions differ')
        if item.get('status') not in ('pending', 'reviewed'):
            raise ValueError(f'page {number}: unknown review status')
        if require_attestations and item.get('status') != 'reviewed':
            errors.append(f'page {number}: status is not reviewed')
        if require_attestations and (not isinstance(item.get('reviewer'), str) or not item['reviewer'].strip()):
            errors.append(f'page {number}: reviewer is required')
        if not isinstance(item.get('notes'), str):
            errors.append(f'page {number}: notes must be a string')
        elif item.get('status') == 'reviewed' and not item['notes'].strip():
            errors.append(f'page {number}: reviewed pages require nonempty notes')
    # Hashes alone bind the manifest to the supplied files, not the PNGs to
    # the PDF's page pixels. Re-rendering catches a swapped/wrong image even
    # when someone also updated its declared hash. No human-review proof follows.
    if rerender and not errors:
        with tempfile.TemporaryDirectory(prefix='hllpdf-recheck-') as td:
            fresh = Path(td) / 'fresh'
            render(pdf, fresh, dpi=dpi, page_box=page_box, backend=backend)
            new_data = json.loads((fresh / 'review.json').read_text(encoding='utf-8'))
            fresh_pages = {entry['page']: fresh / entry['image'] for entry in new_data['pages']}
            for item in pages:
                original = fitz.Pixmap(str(review_path.parent / item['image']))
                current = fitz.Pixmap(str(fresh_pages[item['page']]))
                if ((original.width, original.height, original.n) !=
                        (current.width, current.height, current.n)
                        or original.samples != current.samples):
                    errors.append(f"page {item['page']}: pixels differ from a fresh PDF render")
            if new_data['pdf_sha256'] != data['pdf_sha256'] or digest(pdf) != data['pdf_sha256']:
                errors.append('PDF changed during raster verification')
    return errors


def parse_pages(expression: str, count: int) -> list[int]:
    """Parse an explicit, bounded one-based selection such as 1,3-5."""
    selected: set[int] = set()
    for token in expression.split(','):
        match = re.fullmatch(r'([1-9][0-9]*)(?:-([1-9][0-9]*))?', token.strip())
        if match is None:
            raise ValueError('pages must be an explicit selection such as 1,3-5')
        first = int(match[1]); last = int(match[2] or match[1])
        if not 1 <= first <= last <= count:
            raise ValueError(f'page selection is outside 1..{count}')
        block = set(range(first, last + 1))
        if selected & block:
            raise ValueError('page selection contains duplicate pages')
        selected.update(block)
    return sorted(selected)


def record(pdf: Path, review_path: Path, selection: str, reviewer: str, notes: str) -> list[int]:
    """Record the caller's explicit attestation for selected already-inspected pages.

    This is a single-writer workflow, not an authentication system. Never infers
    that inspection occurred; no hash or page binding is editable through it.
    """
    if not reviewer.strip() or not notes.strip():
        raise ValueError('nonempty reviewer and page-review notes are required')
    if review_path.is_symlink():
        raise ValueError('refusing to edit a symlinked review manifest')
    original_hash = digest(review_path)
    errors = verify(pdf, review_path, require_attestations=False)
    if errors:
        raise ValueError('stale or invalid review evidence: ' + '; '.join(errors))
    data = json.loads(review_path.read_text(encoding='utf-8'))
    selected = parse_pages(selection, data['page_count'])
    for item in data['pages']:
        if item['page'] in selected:
            item.update(status='reviewed', reviewer=reviewer.strip(), notes=notes.strip())
    with tempfile.TemporaryDirectory(prefix='.hllpdf-attest-', dir=review_path.parent) as td:
        stage = Path(td) / 'review.json'
        stage.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
        stage.chmod(review_path.stat().st_mode & 0o777)
        if review_path.is_symlink() or digest(review_path) != original_hash:
            raise ValueError('review manifest changed while recording; reload before retrying')
        # Recheck the source immediately before publishing the changed status.
        if digest(pdf) != data['pdf_sha256']:
            raise ValueError('PDF changed while recording; render and review again')
        atomic_replace(stage, review_path)
    return selected


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    r = sub.add_parser('render')
    r.add_argument('pdf', type=Path)
    r.add_argument('--output', type=Path, required=True)
    r.add_argument('--dpi', type=int, default=144)
    r.add_argument('--renderer', dest='backend', choices=BACKENDS, default='poppler',
                   help='explicit engine; Poppler remains default; no fallback')
    r.add_argument('--page-box', choices=('cropbox', 'mediabox'), default='cropbox',
                   help='visible CropBox by default; MediaBox is an explicit sheet proof')
    v = sub.add_parser('verify')
    v.add_argument('pdf', type=Path)
    v.add_argument('--review', type=Path, required=True)
    v.add_argument('--rerender', action='store_true',
                   help='compare review images to a fresh render with the recorded backend, not hashes alone')
    a_record = sub.add_parser('record', help='record explicit inspection of selected pages')
    a_record.add_argument('pdf', type=Path)
    a_record.add_argument('--review', type=Path, required=True)
    a_record.add_argument('--pages', required=True, help='one-based selection, e.g. 1,3-5')
    a_record.add_argument('--reviewer', required=True)
    a_record.add_argument('--notes', required=True)
    a = p.parse_args()
    try:
        if a.command == 'render':
            render(a.pdf, a.output, a.dpi, page_box=a.page_box, backend=a.backend)
            print(f'✓ rendered for inspection; every page is PENDING: {a.output}')
        elif a.command == 'record':
            selected = record(a.pdf, a.review, a.pages, a.reviewer, a.notes)
            print('✓ recorded caller attestation for pages: ' + ', '.join(map(str, selected)))
        else:
            errors = verify(a.pdf, a.review, rerender=a.rerender)
            if errors:
                print('\n'.join('✗ '+e for e in errors), file=sys.stderr)
                return 1
            scope = 'PDF/image hashes, same-backend fresh-render pixels' if a.rerender else 'PDF/image hashes'
            print(f'✓ {scope} and recorded page attestations match; this is not visual certification')
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print(f'✗ review operation failed: {exc}', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
