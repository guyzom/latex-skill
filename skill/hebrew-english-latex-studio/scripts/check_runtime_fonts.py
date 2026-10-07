#!/usr/bin/env python3
"""Verify registered canonical font paths/hashes, not font-name lookup.

The core emits a framed hex inventory from finish_pdffile. Registered resources
can include unused faces. This is not verification of PDF subset bytes or an
adversarial sandbox. Sources, fonts and toolchain must remain trusted and stable.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
sys.dont_write_bytecode = True
from font_paths import MANIFEST_DIR, font_dir

PREFIX = 'HLLFONT|'
ANCHORS = {'FrankRuhlLibre-Regular.ttf', 'Heebo-Regular.ttf', 'DejaVuSansMono.ttf'}

class InventoryError(ValueError):
    """Missing or partial evidence cannot pass the runtime gate."""

# v4.26.0 (BLD-69): the preamble writes the inventory from finish_pdffile, and
# LuaTeX runs that callback only when it finishes a PDF with at least one
# page. So a log WITHOUT an inventory has three causes, and "synchronize
# preamble.tex" is right for only one of them. Measured with the canonical
# preamble: a run halted by an error (an undefined macro, a failed Lua
# require, pgfplots contour lua) has no inventory even when a page had
# already shipped, and its log ends "!  ==> Fatal error occurred, no output
# PDF file produced!"; an empty document compiles with exit 0, logs
# "no pages of output", and has none either. The old message sent both to
# re-sync a fleet-synced file that was byte-identical to the asset.
HALTED = re.compile(r'^!  ==> Fatal error occurred|^! Emergency stop', re.M)
NO_PAGES = re.compile(r'no pages of output', re.I)

def missing_inventory_reason(text: str) -> str:
    if HALTED.search(text):
        return ('missing runtime font inventory: the compile stopped before the end of '
                'the document, and the preamble writes the inventory only when the PDF '
                'is finished. Fix the LaTeX error first (build.sh names it above, with '
                'its l.N line); here the missing inventory does not mean that '
                'preamble.tex is out of sync')
    if NO_PAGES.search(text):
        return ('missing runtime font inventory: the run produced no pages, so no PDF '
                'was finished and the preamble never wrote the inventory')
    return 'missing runtime font inventory; synchronize preamble.tex'

def parse_inventory(text: str) -> tuple[list[str], int]:
    lines = [line for line in text.splitlines() if line.startswith(PREFIX)]
    if not lines:
        raise InventoryError(missing_inventory_reason(text))
    if lines[0] != 'HLLFONT|BEGIN|1':
        raise InventoryError('missing runtime font inventory; synchronize preamble.tex')
    paths: list[str] = []
    i = 1
    while i < len(lines) and lines[i].startswith('HLLFONT|FILE|'):
        match = re.fullmatch(r'HLLFONT\|FILE\|([1-9][0-9]*)\|([1-9][0-9]*)', lines[i])
        if match is None or int(match[1]) != len(paths) + 1:
            raise InventoryError('invalid runtime font entry index')
        count = int(match[2]); i += 1
        if count > 4096 or i + count > len(lines):
            raise InventoryError('invalid or truncated runtime font path')
        chunks: list[str] = []
        for line in lines[i:i+count]:
            chunk = re.fullmatch(r'HLLFONT\|HEX\|([0-9a-f]{2,48})', line)
            if chunk is None or len(chunk[1]) % 2:
                raise InventoryError('invalid font path hex encoding')
            chunks.append(chunk[1])
        i += count
        try:
            name = bytes.fromhex(''.join(chunks)).decode('utf-8')
        except (ValueError, UnicodeDecodeError) as exc:
            raise InventoryError('invalid UTF-8 font filename') from exc
        if not name or any(ord(c) < 32 for c in name) or name in paths:
            raise InventoryError('empty, control-containing or duplicate font filename')
        paths.append(name)
    if i != len(lines) - 1:
        raise InventoryError('incomplete, duplicate or unexpected runtime inventory records')
    end = re.fullmatch(r'HLLFONT\|END\|([0-9]+)\|([0-9]+)', lines[i])
    if end is None or int(end[1]) != len(paths) or not paths:
        raise InventoryError('missing, empty or count-mismatched font inventory footer')
    return paths, int(end[2])

def canonical_pins() -> dict[str, str]:
    pins: dict[str, str] = {}
    for raw in (MANIFEST_DIR/'SHA256SUMS').read_text(encoding='utf-8').splitlines():
        if not raw.strip():
            continue
        match = re.fullmatch(r'([0-9a-f]{64})  ([A-Za-z0-9_.-]+)', raw)
        if match is None:
            raise ValueError('invalid release font manifest')
        if match[2].lower().endswith(('.ttf','.otf')):
            if match[2] in pins:
                raise ValueError('duplicate release font pin')
            pins[match[2]] = match[1]
    if not ANCHORS <= pins.keys():
        raise ValueError('release manifest is missing canonical family anchors')
    return pins

def has_core(source_list: Path) -> bool:
    """Conservative detection on recorder-derived TeX files, not macro evaluation."""
    for raw in source_list.read_text(encoding='utf-8').splitlines():
        if raw and re.search(r'\\def\s*\\hllpdfcoreloaded\b',Path(raw).read_text(encoding='utf-8')):
            return True
    return False

def audit(log: Path, root: Path, *, source_list: Path | None = None) -> dict:
    text = log.read_text(encoding='utf-8',errors='replace')
    if source_list is not None and not has_core(source_list) and PREFIX not in text:
        return {'schema':1,'status':'not-applicable','scope':'no-canonical-core',
                'verified':[],'uncontrolled':[],'errors':[]}
    result = {'schema':1,'status':'failed','scope':'registered-canonical-font-resources',
              'log_sha256':hashlib.sha256(log.read_bytes()).hexdigest(),
              'verified':[],'uncontrolled':[],'errors':[]}
    try:
        paths, unnamed = parse_inventory(text)
    except InventoryError as exc:
        result['errors'].append(str(exc));return result
    result['resources_without_filename'] = unnamed
    result['raw_resources'] = len(paths)
    pins = canonical_pins();root = root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError('font root is not a directory')
    seen: set[str] = set()
    for raw in paths:
        filename = raw.removeprefix('harfloaded:');p = Path(filename)
        if p.name not in pins:
            result['uncontrolled'].append(raw);continue
        if filename in seen:
            continue
        seen.add(filename)
        if not p.is_absolute():
            result['errors'].append(f'{p.name}: engine did not report an absolute path');continue
        try:
            actual = p.resolve(strict=True);target = (root/p.name).resolve(strict=True)
            if actual != target:
                result['errors'].append(f'{p.name}: runtime path {actual} differs from {target}');continue
            digest = hashlib.sha256(actual.read_bytes()).hexdigest()
            if digest != pins[p.name]:
                result['errors'].append(f'{p.name}: runtime SHA-256 differs from release pin');continue
            result['verified'].append({'file':p.name,'path':str(actual),'sha256':digest})
        except OSError as exc:
            result['errors'].append(f'{p.name}: cannot read runtime font ({type(exc).__name__})')
    present = {row['file'] for row in result['verified']}
    for name in sorted(ANCHORS-present):
        result['errors'].append(f'{name}: no verified runtime family anchor')
    result['verified'].sort(key=lambda row:row['file'])
    result['status'] = 'verified' if not result['errors'] else 'failed'
    return result

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('log',type=Path)
    parser.add_argument('--font-dir',type=Path,default=font_dir())
    parser.add_argument('--source-list',type=Path,help='recorder-derived TeX list; non-core builds explicitly not applicable')
    parser.add_argument('--json',action='store_true')
    args=parser.parse_args(argv)
    try:
        result=audit(args.log,args.font_dir,source_list=args.source_list)
    except (OSError,ValueError) as exc:
        print(f'runtime font checker error: {type(exc).__name__}: {exc}',file=sys.stderr);return 2
    if args.json:
        print(json.dumps(result,ensure_ascii=False,indent=2))
    elif result['status']=='not-applicable':
        print('runtime font check: not applicable (no canonical core; no pinned-font claim)')
    elif result['status']=='verified':
        print(f"✓ runtime fonts: {len(result['verified'])} canonical files match paths AND release hashes")
    else:
        for error in result['errors']:print('✗ runtime fonts: '+error)
    return 1 if result['errors'] else 0

if __name__=='__main__':
    raise SystemExit(main())
