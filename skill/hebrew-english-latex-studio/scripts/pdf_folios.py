#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Original project code; scope and terms: ../LICENSING.md.
"""Compare printed folios in declared geometry with explicit PDF PageLabels.

The native PDF parser reads strings (including UTF-16 hex prefixes), instead of
trying to decode get_page_labels()'s serialized prefix strings. The installed
PyMuPDF 1.26.7 returns '<FEFF...>' for this package's hyperref prefixes. A small
object-boundary scanner only splits arrays; string decoding stays in MuPDF.
No source/PDF is modified. No OCR, arbitrary footer layout or semantic page-
numbering correctness is inferred. Unlabelled documents retain the R3 offset
rule, using the selected geometry. Custom/none are explicit caller handoffs.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
import sys
sys.dont_write_bytecode = True
import fitz
from build_contract import FOLIO_LAYOUTS, FOLIO_BANDS


class FolioError(ValueError):
    """Explicit PageLabels exist, but their contract cannot be read safely."""


_WS = '\x00\t\n\f\r '
_DELIMS = '()<>[]{}/%' + _WS
_REF = re.compile(r'\d+\s+\d+\s+R(?=$|[\s\[\]<>()/])')


def _space(raw: str, pos: int) -> int:
    while pos < len(raw):
        if raw[pos] in _WS:
            pos += 1
        elif raw[pos] == '%':
            while pos < len(raw) and raw[pos] not in '\r\n':
                pos += 1
        else:
            break
    return pos


def _object_end(raw: str, pos: int, depth: int = 0) -> int:
    """One serialized PDF object's extent, not a PDF interpreter."""
    if depth > 64 or pos >= len(raw):
        raise FolioError('truncated or over-nested label object')
    if raw[pos] == '(':
        level, i = 1, pos + 1
        while i < len(raw):
            if raw[i] == '\\':
                i += 2  # escaped delimiters, octal digits and line endings stay data
                continue
            if raw[i] == '(':
                level += 1
            elif raw[i] == ')':
                level -= 1
                if level == 0:
                    return i + 1
            i += 1
        raise FolioError('unterminated PDF literal string')
    if raw.startswith('<<', pos) or raw[pos] == '[':
        is_dict = raw.startswith('<<', pos)
        close, i = ('>>', pos + 2) if is_dict else (']', pos + 1)
        while True:
            i = _space(raw, i)
            if raw.startswith(close, i):
                return i + len(close)
            i = _object_end(raw, i, depth + 1)
    if raw[pos] == '<':
        end = raw.find('>', pos + 1)
        if end < 0:
            raise FolioError('unterminated PDF hex string')
        return end + 1
    ref = _REF.match(raw, pos)
    if ref:
        return ref.end()
    i = pos + (1 if raw[pos] == '/' else 0)
    while i < len(raw) and raw[i] not in _DELIMS:
        i += 1
    if i == pos:
        raise FolioError('unexpected delimiter in label array')
    return i


def _array_items(raw: str) -> list[str]:
    if not raw.startswith('['):
        raise FolioError('expected a label array')
    out, pos = [], 1
    while True:
        pos = _space(raw, pos)
        if pos >= len(raw):
            raise FolioError('unterminated label array')
        if raw[pos] == ']':
            if _space(raw, pos + 1) != len(raw):
                raise FolioError('trailing label array data')
            return out
        end = _object_end(raw, pos)
        out.append(raw[pos:end])
        pos = end


class _NumberTree:
    """Native typed reads of direct/indirect dictionaries, without editing input."""
    def __init__(self, doc: fitz.Document):
        self.doc = doc
        self.view = fitz.open()
        self.slot = self.view.get_new_xref()
        self.nodes = 0

    def close(self) -> None:
        self.view.close()

    def typed(self, raw: str) -> tuple[str, str]:
        self.view.update_object(self.slot, '<< /V ' + raw + ' >>')
        return self.view.xref_get_key(self.slot, 'V')

    def resolve(self, value: tuple[str, str]) -> tuple[str, str]:
        visited = set()
        kind, raw = value
        while kind == 'xref':
            ref = raw.split()
            if len(ref) != 3 or ref[2] != 'R':
                raise FolioError('malformed indirect label reference')
            xref = int(ref[0])
            if xref in visited or not 0 < xref < self.doc.xref_length():
                raise FolioError('cyclic or invalid indirect label reference')
            visited.add(xref)
            kind, raw = self.typed(self.doc.xref_object(xref, compressed=True))
        return kind, raw

    def field(self, dictionary: str, key: str) -> tuple[str, str]:
        self.view.update_object(self.slot, dictionary)
        return self.resolve(self.view.xref_get_key(self.slot, key))

    def walk(self, value: tuple[str, str], chain=()) -> list[tuple[int, str]]:
        self.nodes += 1
        if self.nodes > 4 * self.doc.page_count + 128 or len(chain) > 64:
            raise FolioError('label tree exceeds traversal bound')
        identity = value if value[0] == 'xref' else None
        if identity and identity in chain:
            raise FolioError('cyclic PageLabels number tree')
        kind, raw = self.resolve(value)
        if kind != 'dict':
            raise FolioError('PageLabels node is not a dictionary')
        nums, kids = self.field(raw, 'Nums'), self.field(raw, 'Kids')
        if (nums[0] == 'null') == (kids[0] == 'null'):
            raise FolioError('label node needs exactly one of Nums or Kids')
        if nums[0] != 'null':
            if nums[0] != 'array':
                raise FolioError('Nums is not an array')
            entries = _array_items(nums[1])
            if not entries or len(entries) % 2:
                raise FolioError('Nums needs index/dictionary pairs')
            result = []
            for index, rule in zip(entries[::2], entries[1::2]):
                ik, iv = self.resolve(self.typed(index))
                rk, rv = self.resolve(self.typed(rule))
                if ik != 'int' or rk != 'dict':
                    raise FolioError('label entry is not integer/dictionary')
                result.append((int(iv), rv))
            return result
        if kids[0] != 'array':
            raise FolioError('Kids is not an array')
        children = _array_items(kids[1])
        if not children:
            raise FolioError('empty label tree')
        result = []
        for child in children:
            result.extend(self.walk(self.typed(child), chain + (identity,)))
        return result


def _number(number: int, style: str) -> str:
    if style == 'D':
        return str(number)
    if style in ('a', 'A'):
        # PDF alphabetic sequence: a..z, aa..zz, aaa..zzz (NOT spreadsheet columns).
        q, r = divmod(number - 1, 26)
        if q >= 128:
            raise FolioError('alphabetic page label exceeds supported width')
        out = chr(ord('a') + r) * (q + 1)
        return out.upper() if style == 'A' else out
    if style in ('r', 'R'):
        if number > 3999:
            raise FolioError('Roman page labels above 3999 require separate validation')
        out = ''
        for value, letters in [(1000,'M'),(900,'CM'),(500,'D'),(400,'CD'),(100,'C'),
                               (90,'XC'),(50,'L'),(40,'XL'),(10,'X'),(9,'IX'),
                               (5,'V'),(4,'IV'),(1,'I')]:
            count, number = divmod(number, value)
            out += letters * count
        return out.lower() if style == 'r' else out
    if style == '':
        return ''
    raise FolioError('unsupported page-label numbering style: ' + repr(style))


def declared_labels(doc: fitz.Document, *, require_ascii: bool = True) -> list[str] | None:
    """Return validated ASCII labels, or None only when PageLabels is absent.

    A malformed/unsupported declaration is a finding, not permission to silently
    fall back to inference. ASCII scope covers canonical decimal/Roman/Latin
    folios and prefixes; Hebrew/custom glyph numbering requires separate QA.
    """
    root = doc.xref_get_key(doc.pdf_catalog(), 'PageLabels')
    if root[0] == 'null':
        return None
    tree = _NumberTree(doc)
    try:
        rows = tree.walk(root)
        starts = [s for s, _ in rows]
        if not starts or starts[0] != 0 or any(a >= b for a,b in zip(starts, starts[1:])):
            raise FolioError('label ranges must start at zero and strictly increase')
        if starts[-1] >= doc.page_count:
            raise FolioError('label range starts beyond the final PDF page')
        labels = []
        for i, (start, raw) in enumerate(rows):
            stop = starts[i + 1] if i + 1 < len(starts) else doc.page_count
            sk, sv = tree.field(raw, 'S')
            pk, pv = tree.field(raw, 'P')
            nk, nv = tree.field(raw, 'St')
            if sk not in ('name', 'null') or pk not in ('string', 'null') or nk not in ('int', 'null'):
                raise FolioError('invalid style, prefix or initial-number type')
            style = sv[1:] if sk == 'name' else ''
            prefix = pv if pk == 'string' else ''
            initial = int(nv) if nk == 'int' else 1
            if initial < 1:
                raise FolioError('initial page-label number must be positive')
            for offset in range(stop - start):
                label = prefix + _number(initial + offset, style)
                if len(label) > 128 or any(not c.isprintable() for c in label):
                    raise FolioError('page label outside the supported printable 128-character scope')
                if require_ascii and any(not ' ' <= c <= '~' for c in label):
                    raise FolioError('page label outside the supported printable ASCII scope')
                labels.append(label)
        return labels
    except FolioError:
        raise
    except Exception as exc:
        raise FolioError(f'cannot resolve PageLabels: {exc}') from exc
    finally:
        tree.close()


def folio_dimensions(page: fitz.Page) -> tuple[float, float]:
    """Dimensions in unrotated text-extraction coordinates, including UserUnit."""
    width, height = page.rect.width, page.rect.height
    if page.rotation % 180:
        width, height = height, width
    return width, height


def folio_alignment(layout: str, page_number: int) -> str:
    """Outer/inner use physical PDF parity: page 1 is a right-hand recto."""
    if layout == 'outer':
        return 'right' if page_number % 2 else 'left'
    if layout == 'inner':
        return 'left' if page_number % 2 else 'right'
    return layout


def _attached_script_numeral(glyph, line_glyphs) -> bool:
    """A small raised/lowered digit attached to larger ink in its source line.

    Baseline regrouping can turn a centred equation's exponent into a plausible
    standalone folio. Retain the original text line as a bounded context: the
    numeral must have a script-sized font, a script-sized baseline displacement
    and an adjacent larger non-digit glyph. A small footer, another row, distant
    running text or a neighbour that is itself a numeral cannot satisfy this.
    """
    x0, x1, baseline, size, char = glyph
    if not char.isdecimal():
        return False
    for other in line_glyphs:
        ox0, ox1, obaseline, osize, ochar = other
        if not ochar.strip() or ochar.isdigit() or size > .85 * osize:
            continue
        displacement = abs(baseline - obaseline)
        if not .18 * osize <= displacement <= .75 * osize:
            continue
        gap = max(0., x0 - ox1, ox0 - x1)
        if gap <= max(1.5, .25 * osize):
            return True
    return False


def _body_prose_lines(block, expected_label: str | None) -> set[int]:
    """Only positively connected multiline prose, before whitespace is lost.

    A single run, including a wrong folio, is never excluded. Multiword folio
    prefixes and their numeric/Roman/Latin suffixes also remain candidates;
    suffix values are not compared with the expected page number.
    """
    contexts = []
    for line in block.get('lines', []):
        chars = [char for span in line['spans'] for char in span['chars']]
        text = ''.join(char['c'] for char in chars).strip()
        words = re.findall(r"[A-Za-z]+(?:['-][A-Za-z]+)*", text)
        # Protect prefixed labels independently of their numeric value. Keep
        # short/wrong Latin sequences, Roman sequences and title-style literal
        # prefixes, rather than turning uncertain labels into absent evidence.
        terminal = re.search(r'([A-Za-z0-9]+)[._:/-]*$', text)
        token = terminal.group(1) if terminal else ''
        label_shape = (any(c.isdigit() for c in token)
                       or bool(re.fullmatch(r'[IVXLCDMivxlcdm]+', token))
                       or bool(re.fullmatch(r'[A-Za-z]{1,3}', token))
                       or bool(token and len(set(token)) == 1)
                       or bool(words and all(word[0].isupper() for word in words)))
        if expected_label and any(c.isspace() for c in expected_label):
            prefix = re.sub(r'(?:[0-9]+|[IVXLCDMivxlcdm]+)$', '', expected_label).strip()
            label_shape |= bool(prefix and text.startswith(prefix))
        prose = (len(words) >= 2 and not label_shape
                 and tuple(line.get('dir', (1, 0))) == (1.0, 0.0))
        size = max((span['size'] for span in line['spans']), default=0.)
        baseline = chars[0]['origin'][1] if chars else 0.
        contexts.append((prose, size, baseline, line['bbox']))
    connected = set()
    for i, (prose, size, baseline, box) in enumerate(contexts):
        if not prose or size <= 0:
            continue
        for j in (i-1, i+1):
            if not 0 <= j < len(contexts):
                continue
            other, osize, obaseline, obox = contexts[j]
            scale = max(size, osize)
            overlap = min(box[2], obox[2]) - max(box[0], obox[0])
            aligned = min(abs(box[0]-obox[0]), abs(box[2]-obox[2])) <= scale
            if (other and min(size, osize) >= .85 * scale
                    and .5 * scale <= abs(baseline-obaseline) <= 2 * scale
                    and aligned and overlap >= .5 * min(box[2]-box[0], obox[2]-obox[0])):
                connected.add(i)
                break
    return connected


def _literal_prefix_contract(page: fitz.Page) -> bool:
    """Read the actual numbering style; arbitrary literal labels are not prose.

    A prefix-only /PageLabels rule can be any supported ASCII string. Its wrong
    printed counterpart must remain measurable even if it resembles a paragraph.
    The existing typed number-tree reader avoids guessing the style from text.
    """
    doc = page.parent
    root = doc.xref_get_key(doc.pdf_catalog(), 'PageLabels')
    if root[0] == 'null':
        return False
    tree = _NumberTree(doc)
    try:
        rows = tree.walk(root)
        applicable = [raw for start, raw in rows if start <= page.number]
        if not applicable:
            return True
        rule = applicable[-1]
        kind, style = tree.field(rule, 'S')
        if kind == 'name' and style in ('/D', '/R', '/r', '/A', '/a'):
            return False
        if kind == 'null':
            pkind, prefix = tree.field(rule, 'P')
            # Hyperref also serializes ordinary folios as literal /P(1), with
            # no /S. Recognize complete counter tokens, never a numeric value
            # or a suffix inside an arbitrary multiword literal prefix.
            roman = r'M{0,3}(?:CM|CD|D?C{0,3})(?:XC|XL|L?X{0,3})(?:IX|IV|V?I{0,3})'
            roman_case = prefix == prefix.upper() or prefix == prefix.lower()
            counter = (bool(re.fullmatch(r'[0-9]+', prefix))
                       or bool(prefix and roman_case and re.fullmatch(roman, prefix.upper()))
                       or bool(re.fullmatch(r'([A-Za-z])\1*', prefix)))
            return pkind != 'string' or not counter
        return True
    except FolioError:
        return True  # malformed contracts cannot justify suppressing candidates
    finally:
        tree.close()


def footer_candidates(page: fitz.Page, footer_frac: float = .90,
                      expected_label: str | None = None, *, layout: str = 'center',
                      band: str = 'footer') -> list[str]:
    """Physical LTR glyph runs inside the declared header/footer geometry.

    Combine fragments by baseline and horizontal proximity. A distant running
    footer does not get glued to the folio. Center uses a 12pt window; side
    layouts use the corresponding outer third. Header/footer use the outer
    10% of the unrotated page. This does not prove glyph
    visibility (OCR), semantic pagination, or support arbitrary footer layouts.
    """
    return [text for text, _ in _styled_candidates(page, footer_frac, expected_label,
                                                   layout=layout, band=band)]


def _styled_candidates(page: fitz.Page, footer_frac: float = .90,
                       expected_label: str | None = None, *, layout: str = 'center',
                       band: str = 'footer'
                       ) -> list[tuple[str, frozenset[tuple[str, float]]]]:
    """footer_candidates, plus the (font, size) set each run is printed in."""
    if layout not in FOLIO_LAYOUTS or band not in FOLIO_BANDS:
        raise FolioError('invalid folio geometry contract')
    if layout in ('none', 'custom'):
        return []
    width, height = folio_dimensions(page)
    alignment = folio_alignment(layout, page.number + 1)
    literal_prefix = _literal_prefix_contract(page)
    lines: list[list[tuple[float, float, float, float, str, bool, bool, str]]] = []
    for block in page.get_text('rawdict')['blocks']:
        prose_lines = set() if literal_prefix else _body_prose_lines(block, expected_label)
        for source_line, line in enumerate(block.get('lines', [])):
            if tuple(line.get('dir', (1, 0))) != (1.0, 0.0):
                continue
            # Save context before the band/baseline filters split mathematical
            # scripts away from their base. The context never crosses a source
            # text line, and only the connected script candidate is vetoed.
            line_glyphs = [(char['bbox'][0], char['bbox'][2], char['origin'][1],
                            span['size'], char['c'])
                           for span in line['spans'] for char in span['chars']]
            for span in line['spans']:
                for char in span['chars']:
                    x0, y0, x1, y1 = char['bbox']
                    ymid = (y0 + y1) / 2
                    if ((band == 'footer' and ymid <= footer_frac * height)
                            or (band == 'header' and ymid >= (1-footer_frac) * height)):
                        continue
                    c = char['c']
                    if not c.strip():
                        continue
                    baseline = char['origin'][1]
                    glyph = (x0, x1, baseline, span['size'], c)
                    # Subset tags (ABCDEF+) differ between embeddings; the face does not.
                    record = (*glyph, _attached_script_numeral(glyph, line_glyphs),
                              source_line in prose_lines, span['font'].split('+')[-1])
                    row = next((r for r in lines if abs(r[0][2] - baseline) <= .8), None)
                    if row is None:
                        lines.append([record])
                    else:
                        row.append(record)
    result = []
    # A centred equation or a table continuation is not a footer label merely
    # because it enters the bottom band. Admit Latin letters/digits and normal
    # label separators, plus literal punctuation explicitly declared by this
    # page's label. Do NOT filter by equality with the expected string: a wrong
    # Roman/digit sequence must remain visible to the mismatch test.
    alphabet = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._:/-')
    if expected_label is not None:
        alphabet.update(c for c in expected_label if not c.isspace())
    mid = width / 2
    for row in lines:
        groups: list[list] = []
        for char in sorted(row):
            if not groups or char[0] - groups[-1][-1][1] > max(3., .75 * char[3]):
                groups.append([char])
            else:
                groups[-1].append(char)
        for group in groups:
            left, right = min(c[0] for c in group), max(c[1] for c in group)
            xmid = (left + right) / 2
            selected = ((alignment == 'center' and abs(xmid - mid) <= 12)
                        or (alignment == 'left' and xmid < width / 3)
                        or (alignment == 'right' and xmid > 2 * width / 3))
            if selected:
                if any(c[5] for c in group):
                    continue
                if all(c[6] for c in group):
                    continue
                text = ''.join(c[4] for c in group)
                if text and all(c in alphabet for c in text):
                    result.append((text, frozenset((c[7], round(c[3], 1)) for c in group)))
    return result


@dataclass(frozen=True)
class FolioResult:
    findings: list[tuple[int, str, str]]
    observed: int
    expected: int


def labelled_folios(doc: fitz.Document, labels: list[str], *,
                    layout: str = 'center', band: str = 'footer') -> FolioResult:
    """Check observed folios under an explicit, supported geometry contract."""
    if len(labels) != doc.page_count:
        raise FolioError('label/page count disagreement')
    if layout not in FOLIO_LAYOUTS or band not in FOLIO_BANDS:
        raise FolioError('invalid folio geometry contract')
    if layout in ('none', 'custom'):
        raise FolioError('unmeasured layouts require an explicit caller handoff')
    findings, observed = [], 0
    styled = [_styled_candidates(page, expected_label=labels[i], layout=layout, band=band)
              for i, page in enumerate(doc)]
    # v4.25.0 (BLD-67), restored in v5.3.5: a page style prints every folio in
    # ONE typeface. Learn the document's folio faces only from pages whose SOLE
    # run in the declared geometry equals the declared label; then, on a page
    # with several runs, keep the runs printed in a learned face. Measured on 22
    # collections (2,473 pages): every folio is FrankRuhlLibre 12pt, and 194 body
    # glyphs -- script digits (CMR6-12), math letters (CMMI), delimiters (CMEX),
    # a plot's axis label -- dip into the band near the centre on 89 pages whose
    # folio was correct. The script-numeral veto above removes only attached
    # digits; letters, delimiters and axis labels need this rule. Filtering is by
    # FACE, never by text, so a wrong folio in the folio face survives to the
    # mismatch test. A sole candidate is never filtered; a document with no clean
    # page learns nothing; two runs in the same face stay ambiguous. The face is
    # the (font, size) pair, as in v4.25.0, and not the font alone: the v5.3.5
    # adoption measured six correct pages (lifting-optimization 17,
    # computer-architecture-exams 11/38/55/74, particles-nuclei-exams 29) whose
    # second run is in the folio's own font at another size -- body text at
    # 10.9pt, a text subscript and a fraction's denominator at 8pt -- and a
    # font-only face keeps them ambiguous.
    faces = set()
    for i, runs in enumerate(styled):
        if len(runs) == 1 and runs[0][0] == ''.join(labels[i].split()):
            faces |= runs[0][1]
    for i, page in enumerate(doc):
        runs = styled[i]
        if len(runs) > 1 and faces:
            in_face = [run for run in runs if run[1] <= faces]
            if in_face:
                runs = in_face
        candidates = [text for text, _ in runs]
        if len(candidates) > 1:
            findings.append((i + 1, 'FOLIO-AMBIGUOUS',
                             f'{len(candidates)} {layout} {band} runs; cannot choose a folio'))
        elif len(candidates) == 1:
            actual = candidates[0]
            expected = ''.join(labels[i].split())
            # Empty labels do not create observations or waive required coverage.
            if expected:
                observed += 1
            if actual != expected:
                reverse = actual == expected[::-1]
                flag = 'PAGE-NUMBER-REVERSED' if reverse else 'PAGE-NUMBER-ODD'
                findings.append((i + 1, flag,
                                 f'{band} prints {actual!r}; PageLabels declares {labels[i]!r}'))
    if len(doc) >= 3:
        required = max(2, (len(doc) + 1) // 2)
        if observed < required:
            findings.append((0, 'FOLIO-COVERAGE-LOW',
                             f'found {layout} {band} labelled folios on only {observed}/{len(doc)} '
                             f'pages; need at least {required}'))
    return FolioResult(findings, observed, len(doc))
