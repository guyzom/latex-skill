#!/usr/bin/env python3
"""check_pdf_render.py (v4.0.1) — verify the RENDERED PDF, not the source.

Every hard bidi defect in this project's history (reversed Latin in TikZ
nodes, page-number digits flipping 18->81, invisible emphasis) compiled
clean, passed every source-level linter, and was only visible on the page.
This checker closes part of that gap by inspecting the compiled PDF itself.

Checks (all empirically validated against deliberately-broken fixtures):

  R1. REVERSED-LATIN-RUN — a Latin word rendered right-to-left. Fingerprint
      (measured): LuaLaTeX+bidi emits a correctly-ordered Latin run as ONE
      text span, but a reversed run (Latin inside \\h{} in a TikZ node) as
      FRAGMENTED spans whose visual left-to-right order is the mirror of the
      logical word. We group consecutive short Latin fragments sharing a line,
      read them left-to-right, and flag when that run is reversed relative to a
      Latin token found in the source .tex (strong), or when a fragmented run
      >= 4 chars exists at all (weak — fragmentation is itself the signature).

      v4.0.1 corrected two things here, both measured on the shipped
      tests/render_broken.tex fixture, which this rule had stopped firing on:
        - Fragment SIZE. The strong tier admits fragments of 1-3 chars, not
          single chars only. How finely the extractor splits a shattered run is
          a property of the FONT, not of the defect: under the v4 pinned bundle
          'Datapath' extracts as ['D','ata','p','at','h'] and a singles-only
          filter collected nothing, so R1 reported clean on the very fixture
          built to make it fire. The widening is confined to the strong tier,
          which demands an exact source-token match and is 0-FP by
          construction; letting it reach the weak tier cost 52 false findings
          fleet-wide ('was on Oct' glued into 'wasonOct') against a baseline of
          1. The weak tier therefore still takes singles only.
        - Reversal DIRECTION. Reversing the character string is correct only
          when every fragment is one glyph. Visual 'hatpataD' character-reversed
          is 'Dataptah', which matches no source token; reversing the FRAGMENT
          ORDER recovers 'Datapath' exactly. Both candidates are tested.
      The v3.65 gap threshold is unchanged in spirit but is now measured
      per-CHARACTER, since a per-fragment median inflates it once multi-char
      pieces are admitted and starts gluing adjacent real words together.

  R2. REVERSED-WHOLE-TOKEN — a whole extracted word that is NOT a source
      token but whose reverse IS (len >= 4). Catches reversals that the
      extractor happens to emit as one word.

  R3. page-number integrity — compare glyphs in declared folio geometry with explicit
      PDF PageLabels (decimal, Roman and Latin labels with ASCII prefixes).
      A mismatch is PAGE-NUMBER-ODD / PAGE-NUMBER-REVERSED. Unicode-encoded
      ASCII label strings are decoded as PDF strings, not read as raw hex.
      FOLIO-COVERAGE-LOW applies to measured layouts: labels alone prove nothing
      was printed. Custom/none explicitly report unmeasured printed numbering;
      malformed label declarations remain findings. The default is centered
      footer folios; side layouts and a header band may be declared independently.
      Without PageLabels the prior majority-offset Arabic rule is unchanged;
      it cannot infer mixed or arbitrary numbering. See pdf-folios.md.

  R4. MIRRORED-PAREN-DIGITS (v3.28.1) — a digit group rendered ")1(" instead
      of "(1)": the glyph geometrically LEFT of the digits is ')' and the one
      RIGHT of them is '('. This is the fingerprint of an inline \\eqref whose
      parens inherit the RTL base (the v3.24.1 \\maketag@@@ regression — every
      prose \\eqref since then; caught only on the page). Detection is purely
      geometric (char x-positions from the rawdict), so it is immune to the
      extraction-order scrambling of RTL lines. Correct rendering — in LTR
      *and* in RTL prose, mirrored-pair handling included — always puts '('
      at smaller x than its digits; measured on broken/fixed pairs.

  R6. DEST-LANDING (v3.80.0) — a \\figcap/\\tabcap hyperlink DESTINATION that
      lands below the top of the object it points at, i.e. following the
      reference scrolls the table/figure off the top of the viewport. BLD-37
      is exactly this class. v3.74 (figures) and v3.77+v3.79 (tables) fixed
      it, and every one of those fixes was verified by a hand-rolled one-off
      measurement script and gated by NOTHING: the sites they missed compiled
      clean, converged byte-identically, and passed build.sh + R1-R5. Two
      tiers, both hard, both 0-FP by construction:

        R6a DEST-INSIDE-TABLEBOX — a `tbl.` dest below the topmost INK of the
            tablebox frame its own caption lives in. The frame is the only
            self-identifying object in the PDF: \\newmdenv strokes it 0.9pt
            (LuaTeX emits 0.897) in cTblLine, and over 1875 fleet pages that
            width occurs with exactly the two cTblLine values and no third,
            so (width, colour) is an exact key. Ownership runs through the
            CAPTION — the frame that contains "טבלה N.M" IS that table's
            frame — never through "which frame encloses the dest", the
            broken rule that produced BOTH numbers of the v3.77 cycle: the
            false all-clear "305/306" (a sunk dest was matched against the
            NEXT frame down the page) and the over-correction "296/306" (six
            anchors sitting +32.0pt above their own frame top were condemned
            for falling inside the PRECEDING box). The pre-fix truth was
            302/306 in the measured regression corpus.

        R6b DEST-AT-CAPTION — any `tbl.`/`fig.` dest closer than
            CAPTION_FLOOR pt to the top of its own caption label. This is the
            reference for the objects that have NO frame to measure against:
            a \\tabcap hosted by an exbox, and every figure. Derived, not
            fitted: the preamble raises the anchor by (measured object height
            + 42pt) and the caption sits BELOW the object, so a healthy dest
            clears the caption top by >= 42 - (caption ascent ~8pt) = 34pt
            even for a zero-height object; when the measurement fails, the
            0pt sentinel makes \\figcap/\\tabcap fall back to the plain
            \\refstepcounter and hyperref drops the anchor ON the caption
            line — measured 12.9pt (deterministic), or 3.2pt when the caption
            broke to the next page.

        R6c DEST-CROSS-PAGE-CAPTION (v3.82, soft) — a dest that lands ABOVE
            its page's top edge, i.e. the caption broke to the page AFTER the
            object and the anchor's island-height raise carried it off the
            page. R6b cannot see these: the gap to the caption is then
            enormous and trivially passes. Measured fleet: 15, all `fig.`,
            -56.01..-286.75pt, 8 advanced-electronic-devices + 7 exam layer.
            Soft because the object is still reachable — the reader lands on
            the caption with the figure on the preceding page — but NAMED,
            because until v3.82 the population was invisible and could have
            grown from 15 to 20 with no signal anywhere (BLD-38).
            --max-cross-page N makes the population a hard budget, so a
            sweep that knows the fleet's count can assert it.

      A dest whose caption cannot be located is reported (soft
      DEST-CAPTION-NOT-FOUND), never skipped: a rule that silently goes blind
      is the exact failure this gate exists to prevent. Likewise a dest that
      could not be paired to a caption BY NUMBER now says so (soft
      DEST-PAIRED-BY-PROXIMITY) instead of quietly taking the nearest caption
      below it — 433 of 433 fleet dests pair by number since v3.82.

Exit status: 1 if any R1-strong/R2/reverse-folio/R4/R6 hit; 0 otherwise.
This is a REQUIRED gate after build.sh, but it still does not see content
correctness or layout aesthetics — the visual audit of rendered pages and
the source cross-check (SKILL.md step 4) remain mandatory.

Usage:
    python3 check_pdf_render.py doc.pdf [source.tex ...] [--max-cross-page N]
Requires: pymupdf  (pip install --break-system-packages pymupdf)
"""
import re
import argparse
import sys
import unicodedata
from collections import Counter
from itertools import combinations
sys.dont_write_bytecode = True

# v3.83 (R5c): what a stranded LIST LABEL looks like — (a) (1) [b] 3. iv. •
# Deliberately tight. Listing line numbers ARE bare digits, so bare digits are
# excluded: they are the fleet's largest legitimate left-protruding population
# (1084 of them), and a bare number left of the block is far more likely to be
# one than a label. A numbered list still trips this via its "3." form.
LABELISH = re.compile(r'^(?:[(\[][0-9a-zA-Z]{1,3}[)\].]?|[0-9]{1,3}\.'
                      r'|[a-zA-Z]\.|[•▪◦‣–—*])$')

try:
    import fitz  # PyMuPDF
except ImportError:
    print("check_pdf_render: pymupdf not installed — run:")
    print("  pip install --break-system-packages pymupdf")
    sys.exit(2)

try:
    from pdf_folios import FolioError, declared_labels, labelled_folios, footer_candidates
    from build_contract import FOLIO_LAYOUTS, FOLIO_BANDS, CAPTION_LABEL_WEIGHTS, parse_rgb_hex
except ImportError as exc:
    print(f"check_pdf_render: required folio helper unavailable ({exc})", file=sys.stderr)
    sys.exit(2)

FOOTER_FRAC = 0.90          # words below 90% of page height = footer zone
MIN_RUN = 3                 # fragmented-run minimum length to consider
PALINDROME_SAFE = True      # skip palindromes (reverse == itself)


def is_latin_char(char):
    return (len(char) == 1 and unicodedata.category(char).startswith("L")
            and "LATIN" in unicodedata.name(char, ""))


def is_latin_word(token):
    token = unicodedata.normalize("NFC", token)
    return (len(token) >= 3 and is_latin_char(token[0])
            and all(is_latin_char(c) or c in "-‐‑–—" for c in token))


def latin_words(text):
    """Yield Unicode Latin words, including Latin-1/Extended letters."""
    text = unicodedata.normalize("NFC", text)
    current = []
    for char in text:
        if is_latin_char(char) or (char in "-‐‑–—" and current):
            current.append(char)
        else:
            token = "".join(current).strip("-‐‑–—")
            if is_latin_word(token):
                yield token
            current = []
    token = "".join(current).strip("-‐‑–—")
    if is_latin_word(token):
        yield token


def strip_tex_comment(line):
    r"""Blank a real TeX comment tail while respecting backslash parity.

    ``\%`` is a literal percent; ``\\%`` is a line-break command followed by
    a comment. The replacement keeps source positions stable.
    """
    i = 0
    while True:
        j = line.find("%", i)
        if j < 0:
            return line
        k = j - 1
        while k >= 0 and line[k] == "\\":
            k -= 1
        if (j - 1 - k) % 2 == 0:
            return line[:j] + " " * (len(line) - j)
        i = j + 1


def source_latin_tokens(paths):
    """Latin tokens from all contributing sources, lowercased."""
    toks = set()
    for source_path in paths:
        try:
            with open(source_path, encoding="utf-8", errors="replace") as source_file:
                text = source_file.read()
        except OSError as exc:
            raise ValueError(f"cannot read supplied source {source_path!r}: {exc}") from exc
        lines = [strip_tex_comment(ln) for ln in text.splitlines()]
        text = re.sub(r"\\[A-Za-z@]+", " ", "\n".join(lines))
        toks.update(token.lower() for token in latin_words(text))
    return toks


def line_key(w):
    """Cluster words into visual lines by their vertical midpoint."""
    return round((w[1] + w[3]) / 2.0, 1)


try:
    UNCLIPPED = fitz.INFINITE_RECT()
except AttributeError:                     # pre-1.19 pymupdf
    UNCLIPPED = fitz.Rect(-(1 << 30), -(1 << 30), 1 << 30, 1 << 30)


def offpage_words(page):
    """Words as seen WITHOUT the page-box cull — the input to the R5 media-box
    test. Plain get_text("words") must NOT be used for that test.

    v3.65 — the structured-text device DISCARDS any glyph lying entirely
    outside the visible box, so the default `words` view goes blind exactly
    when the MOST content is lost: R5's sensitivity was INVERTED. On the
    measured synthetic regression, a run that only straddled the edge was
    visible, while moving it wholly beyond the edge made it disappear from
    the default extraction and produced a false pass. A real 20-gate quantikz
    circuit likewise lost four gate labels past the media box. Passing an
    explicit oversized `clip` suppresses that cull and recovers true positions.

    Why not get_texttrace(), the other API that sees these glyphs: it is
    UNUSABLE here on two counts, both measured on this corpus.
      1. PyMuPDF 1.28.0 leaks a reference to None once per span, so
         sys.getrefcount(None) falls 12290 -> 5265 over 6777 spans and the
         INTERPRETER ABORTS ("deallocating None") partway through any
         real-sized document — turning the gate into a crash, not a verdict.
      2. It does not apply clipping paths, so a TikZ \\clip that deliberately
         hides text off-canvas would be reported as lost content. The `clip`
         argument here keeps MuPDF's clipper active: verified on a fixture
         whose \\clip discards a node at x=1068 — still correctly invisible.
    """
    return page.get_text("words", clip=UNCLIPPED)


def page_box(page):
    """The page's visible box in the coordinate space the text APIs use.

    v3.65 — page.rect is ROTATION-APPLIED while BOTH text APIs return
    UNROTATED coordinates. Measured on a clean rotated page: page.rect swaps
    width and height, yet get_text("words") still reports the footer in the
    unrotated coordinate space. Comparing those spaces made the old y-tier
    HARD-FAIL a perfectly good landscape page (pdflscape emits exactly this
    /Rotate). Un-swap so both sides speak one space.
    """
    pw, ph = page.rect.width, page.rect.height
    if page.rotation in (90, 270):
        pw, ph = ph, pw
    return pw, ph


def is_latin_word_fragment(token):
    """Every character Latin (or an intra-word hyphen) — a piece of a shattered
    Latin run, of any length. v4.0.1, see fragmented_runs."""
    return bool(token) and all(is_latin_char(c) or c in "-\u2010\u2011" for c in token)


def fragmented_runs(words, wide=False):
    """Group consecutive SHORT Latin fragments sharing a line into runs; yield
    (visual_string_left_to_right, page_y) for runs >= MIN_RUN.

    v4.0.1: fragments of 1-3 chars, not single chars only. The rule's fingerprint
    is that a reversed run is emitted as FRAGMENTS, and how finely the extractor
    splits them is a property of the font, not of the defect. Measured on the
    shipped tests/render_broken.tex: with the v4 pinned font bundle the deliberate
    reversal extracts as ['D', 'ata', 'p', 'at', 'h'] — visibly 'Datapath' shattered
    — and a singles-only filter collected NOTHING, so R1 reported clean on the very
    fixture built to make it fire. That is how the harness's T4 went red in CI while
    passing here on the old system fonts: same PDF content, different span
    granularity. The 0.5x-median gap split from v3.65 is unchanged, which is what
    keeps the 29 false positives (MIPS 'F D E M W' rows) out."""
    max_len = 3 if wide else 1
    singles = [w for w in words
               if 1 <= len(w[4]) <= max_len and is_latin_word_fragment(w[4])]
    by_line = {}
    for w in singles:
        by_line.setdefault(line_key(w), []).append(w)
    for y, ws in by_line.items():
        ws.sort(key=lambda w: w[0])
        # split on horizontal gaps > 2.5x median glyph width
        # v4.0.1: median per-CHARACTER width, not per-fragment. Once fragments of
        # 1-3 chars are admitted, a per-fragment median inflates the threshold and
        # the 0.5x gap test starts gluing ADJACENT REAL WORDS together — measured:
        # 86 soft findings appeared fleet-wide, e.g. 'was on Oct' reported as
        # 'wasonOct'. Dividing by the character count restores a true glyph width,
        # so the v3.65 discrimination holds: a shattered run has 0.00pt gaps while
        # separate words sit >= 11.95pt apart.
        widths = [(w[2] - w[0]) / max(1, len(w[4])) for w in ws] or [1]
        med = sorted(widths)[len(widths) // 2] or 1
        run = [ws[0]]
        for prev, cur in zip(ws, ws[1:]):
            # v3.65: 2.5x the median glyph width was far too permissive and left a
            # PERMANENT 29-warning floor across 3 documents (FDEMW, FFDEMW, FEDCB —
            # MIPS pipeline tables whose per-row 'F D E M W' is CORRECT left to
            # right). The two populations separate cleanly, so this is a threshold
            # bug, not an ambiguity: in the true positive 'htapataD' every
            # inter-glyph gap is 0.00pt, while every false positive has gaps of at
            # least 11.95pt = 1.37x the median glyph width. 0.5x keeps the catch and
            # removes all 29, with 0 new hits over 1874 pages. The floor mattered:
            # it desensitised readers to the same soft tier that carries
            # PAGE-NUMBER-ODD and INK-PAST-TEXT-BLOCK.
            if cur[0] - prev[2] > 0.5 * med:
                if len(run) >= MIN_RUN:
                    yield ("".join(w[4] for w in run),
                           "".join(w[4] for w in reversed(run)), y)
                run = [cur]
            else:
                run.append(cur)
        if len(run) >= MIN_RUN:
            yield ("".join(w[4] for w in run),
                   "".join(w[4] for w in reversed(run)), y)


def _visible_parenthesis_overrides(page):
    """Resolve parentheses through the actual embedded glyph, not ToUnicode alone.

    Babel may mirror the GLYPH while retaining the logical Unicode character in
    the PDF text map. In that case sorting extracted ')' and '(' by x creates
    an imaginary visual defect. Only substitute when a TrueType/OpenType cmap
    and the renderer's glyph ID give unambiguous evidence. Unsupported fonts,
    ambiguous subsets and missing cmaps retain the original conservative check.
    No OCR, raster shape guessing, system fonts or language-based exemption.
    """
    import io
    from fontTools.ttLib import TTFont
    candidates = {}
    for record in page.get_fonts(full=True):
        xref, ext, _type, base_name = record[:4]
        if ext not in {"ttf", "otf"}:
            continue
        try:
            payload = page.parent.extract_font(xref)[-1]
            with TTFont(io.BytesIO(payload), lazy=True) as font:
                cmap = font.getBestCmap() or {}
                if 40 not in cmap or 41 not in cmap:
                    continue
                pair = {font.getGlyphID(cmap[40]): "(", font.getGlyphID(cmap[41]): ")"}
                if len(pair) != 2:
                    continue
            name = base_name.split("+", 1)[-1]
            candidates.setdefault(name, []).append(pair)
        except Exception:  # font metadata failure: keep the conservative original check
            # Parsing a font is advisory; it must never turn a PDF problem into
            # a successful bypass. The original Unicode check remains active.
            continue
    overrides = {}
    for span in page.get_texttrace():
        options = candidates.get(span["font"].split("+", 1)[-1], [])
        if not options:
            continue
        for codepoint, glyph_id, origin, _bbox in span["chars"]:
            if codepoint not in (40, 41):
                continue
            meanings = {mapping.get(glyph_id) for mapping in options}
            if len(meanings) != 1 or None in meanings:
                continue
            key = (codepoint, round(origin[0], 3), round(origin[1], 3))
            overrides[key] = next(iter(meanings))
    return overrides


def mirrored_paren_digits(page):
    """R4: yield visual strings ')N(' — a digit run whose immediate left
    neighbor glyph is ')' and immediate right neighbor is '('. Geometric:
    chars are clustered into visual lines by y-midpoint and sorted by x, so
    the RTL extraction order (which scrambles logical order) is irrelevant.
    Neighbor gaps are bounded by 0.6x the run's glyph height — measured: the
    kern inside a rendered "(1)"/")1(" is <= ~3pt at 12pt (height ~8pt),
    while a word space is wider than the bound, so spaced text never pairs."""
    visible_parens = _visible_parenthesis_overrides(page)
    chars = []
    for block in page.get_text("rawdict").get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                for ch in span.get("chars", []):
                    c = ch["c"]
                    if c in "()":
                        origin = ch.get("origin", (0, 0))
                        c = visible_parens.get((ord(c), round(origin[0], 3), round(origin[1], 3)), c)
                    if not c.strip():
                        continue
                    x0, y0, x1, y1 = ch["bbox"]
                    chars.append(((y0 + y1) / 2.0, x0, x1, y1 - y0, c, y1))
    chars.sort(key=lambda t: (t[0], t[1]))
    line, prev_y = [], None
    lines = []
    for t in chars:
        if prev_y is not None and abs(t[0] - prev_y) > 2.0:
            lines.append(line)
            line = []
        line.append(t)
        prev_y = t[0]
    if line:
        lines.append(line)
    for ln in lines:
        ln.sort(key=lambda t: t[1])
        i = 0
        while i < len(ln):
            # v3.65: the run may START with an ASCII LETTER, not only a digit.
            # The digit-only scan missed every non-numeric tag shape. Re-applying
            # the \maketag@@@ regression produced ')1(', ')2a(' and ')A.1(' on one
            # page and only ')1(' was caught: for ')A.1(' the scan skipped the 'A',
            # landed on the '1', and found '.' — not ')' — to its left; for ')2a('
            # the right neighbour was 'a', not '('. An APPENDIX document rendering
            # ')A.1(' therefore reported "✓ render check clean", exit 0. 8 of the
            # 13 collections combine \appendix with numbered equations, against
            # 331 \eqref sites.
            #
            # ASCII ONLY, and gated on TAG SHAPE — both are load-bearing. Using
            # str.isalnum() to widen the run yields 26 FALSE POSITIVES on the real
            # corpus, because Hebrew letters are alnum and a CORRECT RTL
            # parenthetical legitimately lays out as ')text(' in x-order. Even
            # ASCII-only still catches '(mod 4)' and '(RAID)'. The shape gate is
            # what separates an equation tag from ordinary parenthesised prose:
            # R4's narrowness is a design constraint, not an oversight.
            if not _ASCII_TAG_CHAR(ln[i][4]):
                i += 1
                continue
            j = i  # extend the tag run while glyphs stay adjacent
            while (j + 1 < len(ln) and _ASCII_TAG_CHAR(ln[j + 1][4])
                   and ln[j + 1][1] - ln[j][2] <= 0.6 * ln[j][3]):
                j += 1
            while j > i and ln[j][4] == '.':
                j -= 1
            if not _TAG_SHAPE.match("".join(ln[k][4] for k in range(i, j + 1))):
                i = j + 1
                continue
            gap = 0.6 * max(ln[k][3] for k in range(i, j + 1))
            left = ln[i - 1] if i > 0 else None
            right = ln[j + 1] if j + 1 < len(ln) else None
            if (left and right
                    and left[4] == ')' and ln[i][1] - left[2] <= gap
                    and right[4] == '(' and right[1] - ln[j][2] <= gap):
                # v3.33.3: a REAL mirrored tag digit shares the flanking
                # parens' height AND baseline; a SUPERSCRIPT/subscript digit
                # (the math idiom "(x-1)^2(x-2)" — a squared factor abutting
                # another parenthesized factor) is smaller AND vertically
                # offset. Measured: tag digit h/paren h = 1.00, baseline
                # offset 0; superscript = 0.67 and offset 0.44x paren height.
                # Require full-size AND baseline-aligned to flag (both scale-
                # invariant ratios). Closes a hard-fail FP found on a real
                # Pareto-variance page.
                paren_h = min(left[3], right[3])
                run_h = max(ln[k][3] for k in range(i, j + 1))
                run_y1 = max(ln[k][5] for k in range(i, j + 1))
                paren_y1 = max(left[5], right[5])
                if not (paren_h > 0
                        and run_h >= 0.80 * paren_h
                        and abs(run_y1 - paren_y1) <= 0.30 * paren_h):
                    i = j + 1
                    continue
                run = "".join(ln[k][4] for k in range(i, j + 1))
                yield f"){run}("
            i = j + 1


_TAG_SHAPE = re.compile(r'^(?:[A-Za-z]\.)?[0-9]+(?:\.[0-9]+)*[a-z]?$')


def _ASCII_TAG_CHAR(ch):
    """One glyph that may belong to an equation-tag run: ASCII alnum or a dot.

    Deliberately NOT str.isalnum() — Hebrew letters satisfy that, and a correct
    RTL parenthetical renders ')text(' in x-order, which produced 26 false
    positives when measured on the corpus.
    """
    return len(ch) == 1 and (ch == '.' or ('0' <= ch <= '9')
                             or ('a' <= ch <= 'z') or ('A' <= ch <= 'Z'))


# ----------------------------------------------------------------- R6 -------
# tablebox frame identity (preamble constants, measured on the fleet).
# \newmdenv[...linecolor=cTblLine,linewidth=0.9pt...]{tablebox}; cTblLine is
# #B9C4D2 in preamble.tex and #C8C8C8 in clean_theme.tex. Measured over 1875
# fleet pages: stroke width 0.897 occurs with exactly those two colours (1092 +
# 128 segments) and with no third one, so (width, colour) is an exact key for
# "this stroke is a tablebox edge".
FRAME_W = 0.897
FRAME_W_TOL = 0.02
FRAME_COLORS = {(0.725, 0.769, 0.824), (0.784, 0.784, 0.784)}
CAP_COLOR = 0x555555            # cGray — the \figcap/\tabcap label colour
CAP_WORD = {"טבלה": "tbl", "איור": "fig"}
EN_CAP_WORD = {"Table": "tbl", "Figure": "fig"}
EN_CAP_LABEL = re.compile(r"^(Table|Figure)([A-Za-z]?\.?\d+(?:\.\d+)*)\.?$")
NUMPAT = re.compile(r"^[A-Za-z]?\.?\d+(?:\.\d+)*$")
DESTPAT = re.compile(r"^(tbl|fig)\.")
FRAME_TOL = 0.5                 # pt, PDF coordinate slack
# 30pt: 17pt above the deterministic failure value (12.9pt), 4pt below the
# theoretical minimum for a healthy site (34pt), and 61.8pt below the smallest
# healthy site measured over all 13 built collections — 91.8pt for tbl and
# 106.3pt for fig (advanced-electronic-devices fig.58.2 p.142, a single site).
#
# The tbl minimum is a THREE-WAY TIE, all in computer-architecture-recitations:
# tbl.15.1 p.40 (91.83274), tbl.74.2 p.162 (91.83170), tbl.74.6 p.164
# (91.83275); next distinct value 98.305pt (10 sites). v3.80.0/v3.81.0 named
# tbl.74.2 alone. Both readings come from the same numbers and that is the
# point: sorted by raw float tbl.74.2 IS the unique minimum — by 0.001pt,
# 1/1000 of a point, three orders of magnitude below anything a page can
# express — so a script that ranks floats reports one site and a script that
# rounds to the published 0.1pt reports three. Three independent audits split
# 1/2/3 on exactly this. Corrected in v3.82.0 to "three sites at 91.83pt";
# quote the tie, never the float ranking.
#
# v3.80.0 also published 84.0pt for the tbl minimum. That value is NOT the
# healthy minimum, but it IS re-derivable, and v3.81.0's "could not re-derive
# that value from any built PDF" was too strong (corrected in v3.82.0). It is
# broken computer-architecture tbl.14.1 p.49's own caption gap in the PRE-repair
# build — a real site's real number taken from the wrong population, because
# v3.80's sweep minimised over ALL sites including the three broken ones.
# Re-derived from today's shipped PDF plus the pre-fix offset this file's own
# history records (v3.79 moved that dest from -46.45pt BELOW its frame top to
# +31.98pt above): cap.y0 = 569.855, today's dest_y = 407.384 (gap 162.47);
# pre-fix dest_y = frame_top 439.365 + 46.45 = 485.82, so the pre-fix gap is
# 569.855 - 485.82 = 84.0pt. The other two broken sites give 105.2 (tbl.30.5)
# and 151.4 (tbl.B.1), so 84.0 was the fleet minimum then — of a population
# that included its own defects.
# The floor is unchanged at 30pt.
CAPTION_FLOOR = 30.0
HEB = ("֐", "ת")
# babel-hebrew's \@Alph prints the appendix chapter letter in HEBREW, while
# hyperref names the destination with \@Alph's Latin form — so a caption
# reading "טבלה א.1" belongs to the dest tbl.A.1. The 22-letter alphabet, in
# counter order (final forms are never used for a counter).
HEB_ALPH = "אבגדהוזחטיכלמנסעפצקרשת"


def _norm_num(num):
    """Caption/dest number in ONE spelling, so 433 of 433 pair by number.

    Two divergences exist on the fleet and both are naming, not geometry:
      * the clean (chapter-less) layer prints \\thetbl as "1" while hyperref
        names the dest tbl.0.1 — \\thechapter is 0;  strip a leading "0.".
      * an appendix table's caption prints the Hebrew letter (א.1) while its
        dest is tbl.A.1 — transliterate by alphabet index.
    Applied to BOTH sides, so a document that really does print "0.1" still
    matches its own tbl.0.1.
    """
    if num is None:
        return None
    num = "".join(f"{chr(ord('A') + HEB_ALPH.index(c))}" if c in HEB_ALPH
                  else c for c in num)
    return num[2:] if num.startswith("0.") and len(num) > 2 else num


def _frame_segments(page):
    segs = []
    for dr in page.get_drawings():
        w, c = dr.get("width"), dr.get("color")
        if not w or c is None or abs(w - FRAME_W) > FRAME_W_TOL:
            continue
        if tuple(round(v, 3) for v in c) not in FRAME_COLORS:
            continue
        r = fitz.Rect(dr["rect"])
        if r.height < 0.01:                      # horizontal edge: add the
            r.y0 -= w / 2.0                      # stroke's own half-width, so
            r.y1 += w / 2.0                      # the rect is the INK, not the
        if r.width < 0.01:                       # path
            r.x0 -= w / 2.0
            r.x1 += w / 2.0
        segs.append(r)
    return segs


def frames(page, tol=2.0):
    """Whole tablebox frames on the page, as INK rects, top-down.

    mdframed emits the four edges as four separate stroke paths (roundcorner=4pt
    keeps them from being one rectangle), so they are clustered by adjacency.

    The reference edge is the OUTER one (c - w/2, added in _frame_segments):
    the invariant being asserted is "after the jump no pixel of the object is
    above the viewport top", and only the outermost ink makes that literally
    true. The choice is deliberately NOT load-bearing — centreline and inner
    edge move every verdict by <= 0.9pt against a 32pt separation, and the
    whole-fleet verdict is identical under all three conventions (measured).
    """
    segs = _frame_segments(page)
    n = len(segs)
    parent = list(range(n))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for i in range(n):
        for j in range(i + 1, n):
            a, b = segs[i], segs[j]
            if (a.x0 - tol <= b.x1 and b.x0 - tol <= a.x1
                    and a.y0 - tol <= b.y1 and b.y0 - tol <= a.y1):
                parent[find(i)] = find(j)
    groups = {}
    for i, r in enumerate(segs):
        groups.setdefault(find(i), []).append(r)
    out = []
    for g in groups.values():
        u = fitz.Rect(g[0])
        for r in g[1:]:
            u |= r
        out.append(u)
    out.sort(key=lambda r: r.y0)
    return out


def _normal_caption_sites(page, caption_color):
    """Declared regular caption labels, with an explicit leading colon label.

    Academic captions share their color and weight with body prose, so a whole
    styled-line match is no longer possible. Require a leading native label,
    number and colon on one PDF line, and return only that prefix's glyph box.
    Destination ownership is exact and unique in ``dest_landing``; there is no
    proximity fallback for this contract. This does not infer prose semantics.
    """
    out = []
    for block in page.get_text("rawdict").get("blocks", []):
        for line in block.get("lines", []):
            chars = []
            for span in line.get("spans", []):
                if (span["color"] != caption_color or "Bold" in span["font"]
                        or span.get("flags", 0) & 16):
                    continue
                chars.extend((ch["c"], fitz.Rect(ch["bbox"]))
                             for ch in span.get("chars", []))
            if not chars:
                continue
            ltr = sorted(chars, key=lambda item: item[1].x0)
            text = "".join(c for c, _ in ltr)
            match = re.match(r"^\s*(Table|Figure)\s+([A-Za-z]?\.?\d+(?:\.\d+)*)\s*:(?=\s|$)", text)
            if match:
                selected = ltr[:match.end()]
                kind, number = EN_CAP_WORD[match[1]], _norm_num(match[2])
            else:
                rtl = sorted(chars, key=lambda item: -item[1].x0)
                text = "".join(c for c, _ in rtl)
                # LuaTeX's native Hebrew label commonly omits both space
                # characters from ToUnicode. The real label's mbox/enspace
                # separation must then be measured from glyph geometry.
                match = re.match(r"^\s*(טבלה|איור)\s*([A-Za-zא-ת0-9.\s]+?)\s*:", text)
                if not match:
                    continue
                selected = rtl[:match.end()]
                following = next((glyph for c, glyph in rtl[match.end():] if c.strip()), None)
                colon = selected[-1][1]
                if following is not None and colon.x0-following.x1 < 1.0:
                    continue
                number_chars = rtl[match.start(2):match.end(2)]
                numeric = "".join(c for c, _ in sorted(number_chars, key=lambda item: item[1].x0)
                                  if c.strip() and not HEB[0] <= c <= HEB[1])
                appendix = "".join(c for c, _ in number_chars if c in HEB_ALPH)
                if appendix:
                    numeric = appendix + "." + numeric.lstrip(".")
                number = _norm_num(numeric)
                if not NUMPAT.fullmatch(number):
                    continue
                kind = CAP_WORD[match[1]]
            rect = fitz.Rect(selected[0][1])
            for _, glyph in selected[1:]:
                rect |= glyph
            out.append((kind, number, rect))
    return out


def caption_sites(page, caption_color=CAP_COLOR, caption_label_weight='bold'):
    """[(kind, number, rect)] — every \\figcap/\\tabcap LABEL on the page.

    Identified by the macro's own rendering, never by prose: the label is
    \\textcolor{cGray}{\\mbox{\\textbf{טבלה~\\thetbl.}}}, so it is the only
    bold run in the declared caption color carrying the literal Hebrew or
    English caption label. A normal body reference has another color/weight.

    CHARACTER level, not span level: span segmentation is unstable across the
    fleet — an appendix letter is emitted inside the Hebrew span on one page
    ('טבלהA' + '.5') and inside the DejaVu span on another ('טבלה' + 'B.1').
    A span-level reader silently loses 11 of one collection's 23 table captions
    (measured), and a caption the gate cannot see is a destination it cannot
    judge.
    """
    if caption_label_weight not in CAPTION_LABEL_WEIGHTS:
        raise ValueError('invalid caption label weight contract')
    if caption_label_weight == 'normal':
        return _normal_caption_sites(page, caption_color)
    chars = []
    for b in page.get_text("rawdict").get("blocks", []):
        for ln in b.get("lines", []):
            for s in ln.get("spans", []):
                if s["color"] != caption_color or "Bold" not in s["font"]:
                    continue
                for ch in s.get("chars", []):
                    if ch["c"].strip():
                        chars.append((ch["c"], fitz.Rect(ch["bbox"])))
    chars.sort(key=lambda t: ((t[1].y0 + t[1].y1) / 2, t[1].x0))
    lines, cur, prev = [], [], None
    for c in chars:
        mid = (c[1].y0 + c[1].y1) / 2
        if prev is not None and abs(mid - prev) > 3.0:
            lines.append(cur)
            cur = []
        cur.append(c)
        prev = mid
    if cur:
        lines.append(cur)

    out = []
    for ln in lines:
        # English labels use native LTR order. Match the complete styled run,
        # not a substring of body prose such as "See Table 1.1". The weight
        # and declared-color requirements above remain in effect.
        latin = ''.join(c for c, _ in sorted(ln, key=lambda t: t[1].x0))
        english = EN_CAP_LABEL.fullmatch(latin)
        if english:
            r = fitz.Rect(ln[0][1])
            for _, rr in ln[1:]:
                r |= rr
            out.append((EN_CAP_WORD[english[1]], _norm_num(english[2]), r))
            continue
        # Hebrew reads right-to-left, the number reads left-to-right, and the
        # sentence period lands LEFT of the number under the RTL base.
        heb = "".join(c for c, _ in sorted(ln, key=lambda t: -t[1].x0)
                      if HEB[0] <= c <= HEB[1])
        word = next((w for w in CAP_WORD if heb.startswith(w)), None)
        if word is None:
            continue
        kind = CAP_WORD[word]
        num = "".join(c for c, _ in sorted(ln, key=lambda t: t[1].x0)
                      if not (HEB[0] <= c <= HEB[1])).strip(".")
        # v3.82: the appendix chapter letter is a HEBREW glyph and lives in the
        # Hebrew run, so dropping every Hebrew char used to reduce "טבלה א.1"
        # to "1" — the caption then failed to pair with its own dest tbl.A.1
        # and fell through to the nearest-caption-below fallback (G4).
        rest = heb[len(word):]
        if len(rest) == 1 and rest in HEB_ALPH:
            num = f"{rest}.{num}"
        num = _norm_num(num)
        r = fitz.Rect(ln[0][1])
        for _, rr in ln[1:]:
            r |= rr
        out.append((kind, num if NUMPAT.match(num) else None, r))
    return out


def caption_dests(doc):
    """{name: (page_index, x, y_topdown)} for every tbl./fig. destination."""
    out = {}
    try:
        names = doc.resolve_names()
    except Exception:
        return out
    for name, info in names.items():
        if not DESTPAT.match(name):
            continue
        pno, to = info.get("page"), info.get("to")
        if pno is None or to is None or not (0 <= pno < doc.page_count):
            continue
        page = doc[pno]
        # dest coordinates are PDF user space (y up, unrotated); the text and
        # drawing APIs are top-down and also unrotated, so convert through the
        # UNROTATED box, never through page.rect (which is rotation-applied and
        # would mis-place every dest on a pdflscape page).
        box = page.cropbox
        out[name] = (pno, to[0], box.y1 - to[1])
    return out


def dest_landing(doc, hard, soft, caption_color=CAP_COLOR, caption_label_weight='bold'):
    """R6 — append every destination-landing finding to hard/soft.

    Doc-level (one resolve_names) plus a per-page pass that touches ONLY the
    pages hosting a caption dest, so the cost is ~0.4s on the fleet's largest
    198-page collection.
    """
    dests = caption_dests(doc)
    caps_cache, frame_cache = {}, {}
    for name in sorted(dests):
        kind = name.split(".", 1)[0]
        pno, _dx, dy = dests[name]
        page = doc[pno]
        if pno not in caps_cache:
            caps_cache[pno] = caption_sites(page, caption_color=caption_color,
                                           caption_label_weight=caption_label_weight)
        # This dest's caption, BY NUMBER, anywhere on the page — including
        # above the dest. That case is worse than a dest at its caption, and
        # pairing only downwards would answer it with a warn ("no caption
        # below") instead of a hard failure; the rule must not go blind on the
        # worst input it can get.
        #
        # v3.81 paired 397 of 433 exactly and sent the other 36 to a "nearest
        # same-kind caption at or below the dest" fallback. Both divergences
        # were spelling, not geometry (chapter-less tbl.0.N vs a printed "N",
        # and an appendix caption's HEBREW letter vs the dest's Latin one), and
        # _norm_num now bridges both: measured 433 of 433 exact, 0 fallback, on
        # all 13 collections. That matters because six sites legitimately sit
        # inside the PRECEDING box whose caption is BELOW the dest — the
        # fallback could therefore pair a dest with the wrong table, which is
        # exactly the wrong-ownership class that produced v3.77's false
        # all-clear (BLD-51). The fallback is kept as a last resort so a new
        # naming scheme still gets checked, but it can no longer be SILENT: it
        # now reports itself, because "the gate paired this by proximity" is a
        # fact the reader has to have.
        same = [c for c in caps_cache[pno] if c[0] == kind]
        want = _norm_num(name.split(".", 1)[1])
        exact = [c for c in same if c[1] and c[1] == want]
        if caption_label_weight == 'normal' and len(exact) != 1:
            code = 'DEST-CAPTION-AMBIGUOUS' if exact else 'DEST-CAPTION-NOT-FOUND'
            hard.append((pno + 1, code,
                         f"'{name}' requires exactly one regular caption label numbered {want!r} "
                         f"in the declared color on this page; found {len(exact)}. "
                         "Regular captions require a leading native label, number and colon; "
                         "destination ownership cannot be inferred by proximity."))
            continue
        below = sorted([c for c in same if c[2].y1 >= dy - 1],
                       key=lambda c: c[2].y0)
        cap = (exact or below or [None])[0]
        if cap is None:
            soft.append((pno + 1, "DEST-CAPTION-NOT-FOUND",
                         f"'{name}' has no \\figcap/\\tabcap label at or below "
                         f"it on this page — the destination cannot be checked "
                         f"(caption split to another page?)"))
            continue
        if not exact:
            soft.append((pno + 1, "DEST-PAIRED-BY-PROXIMITY",
                         f"'{name}' has no caption numbered {want!r} on this "
                         f"page (page carries {[c[1] for c in same]}), so it was "
                         f"paired with the nearest {kind} caption BELOW it — "
                         f"ownership is assumed, not proved. Teach _norm_num "
                         f"the new \\the{kind} spelling instead of trusting "
                         f"this: a dest can legitimately land inside the "
                         f"PRECEDING box, and pairing by proximity is how "
                         f"v3.77 shipped a false all-clear"))
        crect = cap[2]

        # --- R6c: the caption broke to the FOLLOWING page (BLD-38). The
        # anchor is raised by the island's measured height, so when the
        # caption starts a new page the dest lands ABOVE that page's top edge
        # and R6b's gap test is trivially satisfied — the site was invisible.
        # Measured on the fleet: 15 such dests, all fig, -56.01..-286.75pt,
        # 8 advanced-electronic-devices + 7 in the exam layer; every tbl dest
        # is at +32.0pt, so a tbl here would be new. Reported (soft) rather
        # than failed: the object IS reachable, the reader just lands on the
        # caption's page with the figure on the page before. --max-cross-page
        # turns the population into a hard budget for a fleet sweep.
        if dy < 0:
            soft.append((pno + 1, "DEST-CROSS-PAGE-CAPTION",
                         f"'{name}' lands {-dy:.1f}pt ABOVE the top of its own "
                         f"page — its caption broke to the page after the "
                         f"{'table' if kind == 'tbl' else 'figure'}, so the "
                         f"anchor's island-height raise carries it off the "
                         f"page. Following the reference shows the caption "
                         f"with the object on the PRECEDING page. Fix by "
                         f"keeping caption and island together "
                         f"(\\needspace / a manual break), or accept it — but "
                         f"it is counted now, not silent (BLD-38)"))

        # --- R6b: distance to the caption (works with or without a frame)
        gap = crect.y0 - dy
        if gap < CAPTION_FLOOR:
            where = (f"{gap:.1f}pt above" if gap >= 0
                     else f"{-gap:.1f}pt BELOW the top of")
            hard.append((pno + 1, "DEST-AT-CAPTION",
                         f"'{name}' lands {where} its own caption "
                         f"(floor {CAPTION_FLOOR:.0f}pt) — the anchor is on the "
                         f"CAPTION line, so following the reference scrolls the "
                         f"whole {'table' if kind == 'tbl' else 'figure'} off "
                         f"the top of the viewport. The height measurement "
                         f"returned the 0pt sentinel and "
                         f"\\{'tab' if kind == 'tbl' else 'fig'}cap fell back to "
                         f"the plain \\refstepcounter: a figure must sit in a "
                         f"MEASURED island — tikzpic/qcirc, or exam_components' "
                         f"\\srcfig, which calls the same grab since v3.80; a "
                         f"bare \\begin{{center}} is not measured — and a "
                         f"table's \\tabcap must follow the tabular directly"))
            continue

        # --- R6a: the tablebox frame that hosts the CAPTION owns this dest
        if pno not in frame_cache:
            frame_cache[pno] = frames(page)
        host = None
        for fr in frame_cache[pno]:
            if fr.y0 <= (crect.y0 + crect.y1) / 2 <= fr.y1:
                host = fr                      # innermost/last wins
        if host is None:
            continue                           # frameless: R6b already judged it
        delta = dy - host.y0
        if delta > FRAME_TOL:
            hard.append((pno + 1, "DEST-INSIDE-TABLEBOX",
                         f"'{name}' lands {delta:.1f}pt BELOW the top of its own "
                         f"tablebox (frame ink starts at y={host.y0:.1f}, dest at "
                         f"y={dy:.1f}) — following the reference hides the top "
                         f"{delta:.1f}pt of the table. Causes measured on the "
                         f"fleet: (a) the tabular is WIDER than the box's "
                         f"\\linewidth, so the paragraph breaks after it and the "
                         f"raised anchor lands on the next line — look for a "
                         f"sub-5pt 'Overfull \\hbox' at this tablebox, which "
                         f"build.sh does not print; (b) the tablebox stacks "
                         f"SEVERAL tabulars and only the last one is measured — "
                         f"split it into one tablebox per tabular"))
    return len(dests)


def _proven_column_right_margin(doc):
    """Calibrate only a positively established two/three-column body grid.

    Joint source-line starts/ends, repeated gutters and shared vertical support
    are required. Nested indents, short tables and isolated right-margin ink do
    not prove columns. Ambiguous geometry retains the prior document-wide mode.
    """
    pages, proofs = [], []
    for page in doc:
        lines, pairs = [], {}
        for block in page.get_text('dict')['blocks']:
            for line in block.get('lines', []):
                if tuple(line.get('dir', (1, 0))) != (1., 0.):
                    continue
                text = ''.join(span['text'] for span in line['spans'])
                if len(text.split()) < 3:
                    continue
                left, top, right, bottom = line['bbox']
                if right-left < 50 or left < 0 or right > page_box(page)[0]+.5:
                    continue
                row = (left, right, top, bottom)
                lines.append(row)
                pair = (round(left*2)/2, round(right*2)/2)
                pairs.setdefault(pair, []).append(top)
        pages.append(lines)
        anchors = [(left, right, ys) for (left, right), ys in pairs.items()
                   if len(ys) >= 5 and max(ys)-min(ys) >= 100]
        if len(anchors) > 16:
            continue  # complex grids cannot justify a bounded column inference
        valid = []
        for count in (3, 2):
            for chosen in combinations(anchors, count):
                lanes = sorted(chosen)
                widths = [right-left for left, right, _ in lanes]
                if max(widths)-min(widths) > .05*max(widths):
                    continue
                gutters = [b[0]-a[1] for a, b in zip(lanes, lanes[1:])]
                if any(not 3 <= gap <= .2*min(widths) for gap in gutters):
                    continue
                if max(gutters)-min(gutters) > 2:
                    continue
                low = max(min(ys) for _, _, ys in lanes)
                high = min(max(ys) for _, _, ys in lanes)
                if high-low < 100 or any(sum(low <= y <= high for y in ys) < 3
                                        for _, _, ys in lanes):
                    continue
                # A repeated lane outside the claimed grid makes a two-lane
                # submodel of a real three-column page incomplete, not proof.
                if any((left < lanes[0][0]-1 or right > lanes[-1][1]+1)
                       and min(high, max(ys))-max(low, min(ys)) >= 100
                       for left, right, ys in anchors):
                    continue
                if any(low <= top <= high and left < a[1]-1 and right > b[0]+1
                       for left, right, top, _ in lines
                       for a, b in zip(lanes, lanes[1:])):
                    continue  # ordinary paragraph ink crosses an internal gutter
                valid.append((count, lanes[-1][0], lanes[-1][1]))
            if valid:
                break
        if valid:
            outer = {(left, right) for _, left, right in valid}
            if max(x[0] for x in outer)-min(x[0] for x in outer) > 1:
                return None
            if max(x[1] for x in outer)-min(x[1] for x in outer) > 1:
                return None
            proofs.append(next(iter(sorted(outer))))
    if not proofs:
        return None
    if (max(x[0] for x in proofs)-min(x[0] for x in proofs) > 1
            or max(x[1] for x in proofs)-min(x[1] for x in proofs) > 1):
        return None
    left, right = proofs[0]
    edges = [round(end*2)/2 for lines in pages for start, end, _, _ in lines
             if abs(start-left) <= 1]
    counts = Counter(edges)
    if not counts:
        return None
    margin = max(counts, key=lambda edge: (counts[edge], edge))
    return margin if counts[margin] >= 5 and abs(margin-right) <= 1 else None


def check(pdf_path, source_paths=None, max_cross_page=None, *,
          folio_layout='center', folio_band='footer', caption_color=CAP_COLOR,
          caption_label_weight='bold'):
    if not isinstance(caption_color, int) or not 0 <= caption_color <= 0xFFFFFF:
        print('ERROR: caption_color must be an RGB integer between 0 and 0xFFFFFF.')
        return 2
    if caption_label_weight not in CAPTION_LABEL_WEIGHTS:
        print('ERROR: caption_label_weight must be bold or normal.')
        return 2
    if folio_layout not in FOLIO_LAYOUTS or folio_band not in FOLIO_BANDS:
        print('ERROR: invalid folio layout/band contract.')
        return 2
    if max_cross_page is not None and (not isinstance(max_cross_page, int) or max_cross_page < 0):
        print('ERROR: max-cross-page must be a non-negative integer.')
        return 2
    try:
        src = source_latin_tokens(source_paths or [])
    except ValueError as exc:
        print(f'ERROR: {exc}')
        return 2
    try:
        doc = fitz.open(pdf_path)
        if not doc.is_pdf or doc.needs_pass or doc.page_count == 0:
            raise ValueError("expected a nonempty, unencrypted PDF")
    except Exception as e:
        # v3.33.1: a non-PDF/corrupt input gets a clean message, not a
        # traceback (robustness audit).
        print(f"ERROR: {pdf_path} is not a readable PDF ({e}).")
        sys.exit(2)
    hard, soft = [], []

    # Explicit PDF labels are a cross-check against the printed glyphs, not a
    # substitute for observing a footer. Invalid labels must not silently fall
    # back to the weaker inference path. Unlabelled PDFs retain legacy R3.
    labels, label_error = None, False
    try:
        if folio_layout in ('none', 'custom'):
            labels = declared_labels(doc, require_ascii=False)
        else:
            labels = declared_labels(doc)
    except FolioError as exc:
        label_error = True
        hard.append((0, "FOLIO-LABELS-INVALID", str(exc)))

    folios = []  # legacy (page_index0, printed_int)
    page_lines = {}  # v3.58 R5: {page_no: {line_key: max_x}} for the margin pass
    page_lmin = {}   # v3.83 R5c: {page_no: {line_key: min_x}} — the LEFT mirror
    left_words = {}  # v3.83 R5c: candidate words near the left edge, per page
    for pno, page in enumerate(doc):
        words = page.get_text("words")

        # --- R4: mirrored parens around a digit group (")1(" — inline \eqref
        # under the RTL base). Purely geometric; hard-fails.
        for vis in mirrored_paren_digits(page):
            hard.append((pno + 1, "MIRRORED-PAREN-DIGITS",
                         f"renders '{vis}' (should be "
                         f"'({vis[1:-1]})') — un-isolated \\eqref/tag in RTL prose"))

        # --- R1: fragmented Latin runs (see the module docstring)
        # v4.0.1: the WIDE pass (fragments up to 3 chars) feeds the STRONG tier
        # only. Strong requires the fragment-order reversal to match a source token
        # exactly, so it is 0-FP by construction. Letting the wide pass reach the
        # SOFT tier cost 52 false findings fleet-wide — adjacent short real words
        # glued into 'wasonOct' — against a baseline of 1. Soft keeps singles only,
        # which is the population v3.65 tuned to 0 false positives.
        seen_strong = set()
        for vis, frag_rev, _y in fragmented_runs(words, wide=True):
            if not src or vis.lower() in src:
                continue
            if frag_rev.lower() in src and vis.lower() != frag_rev.lower():
                hard.append((pno + 1, "REVERSED-LATIN-RUN",
                             f"renders '{vis}' (should be '{frag_rev}')"))
                seen_strong.add(vis)
        for vis, frag_rev, _y in fragmented_runs(words):
            if vis in seen_strong:
                continue
            # v4.0.1: two reversal candidates. Reversing the CHARACTER string is
            # only right when every fragment is one glyph; once the extractor emits
            # multi-char pieces it scrambles them — measured on render_broken.tex,
            # visual 'hatpataD' character-reversed to 'Dataptah', which matches no
            # source token, so the strong tier missed a reversal the weak tier could
            # see. Reversing the FRAGMENT ORDER recovers 'Datapath' exactly. Both
            # candidates are tested; the fragment-order one is the general case.
            rev = vis[::-1]
            if PALINDROME_SAFE and vis.lower() == rev.lower() and frag_rev == vis:
                continue
            if src and frag_rev.lower() in src and vis.lower() not in src:
                hard.append((pno + 1, "REVERSED-LATIN-RUN",
                             f"renders '{vis}' (should be '{frag_rev}')"))
            elif src and rev.lower() in src and vis.lower() not in src:
                hard.append((pno + 1, "REVERSED-LATIN-RUN",
                             f"renders '{vis}' (should be '{rev}')"))
            elif len(vis) >= 4:
                soft.append((pno + 1, "FRAGMENTED-LATIN-RUN",
                             f"fragmented Latin run '{vis}' — likely reversed "
                             f"(reads '{rev}' logically)"))

        # --- R2: whole-token reversals
        if src:
            for w in words:
                t = unicodedata.normalize("NFC", w[4].strip(".,;:()[]"))
                if is_latin_word(t) and len(t) >= 4:
                    tl, rl = t.lower(), t[::-1].lower()
                    if tl not in src and rl in src and tl != rl:
                        hard.append((pno + 1, "REVERSED-WHOLE-TOKEN",
                                     f"renders '{t}' (source has '{t[::-1]}')"))

        # --- R5 (v3.58): ink OUTSIDE the paper, and ink past the text block.
        # Motivating measurement: an \item[<long Hebrew bold label>] pushes its
        # label box rightward past the sheet edge, with the leading glyphs absent
        # from the page content entirely — and TeX reports NO Overfull, because
        # \@item sets the label in
        # \hb@xt@\labelwidth{...\hss} and \hss has infinite shrink. So the whole
        # margin-bleed / off-paper class had no detector at all (grep confirmed:
        # no margin/protrusion rule existed in this gate).
        # Tier 1 (HARD, 0-FP by construction): a glyph physically outside the
        # media box cannot be printed — it is lost content, no judgment needed.
        # Tier 2 (SOFT): a line whose right edge overshoots the inferred text-block
        # edge. Under RTL, body lines are flush RIGHT, so the MODAL per-line
        # max-x IS the right margin — a strong, self-calibrating signal that needs
        # no hardcoded geometry. Soft, because a deliberate full-bleed rule or an
        # author-chosen protrusion is conceivable.
        # v3.62: the media-box test runs on BOTH axes. The x-only version missed a
        # whole content-loss class: an unbreakable box taller than the text block
        # (a tall tikzpicture inside tikzpic, a minipage, a \parbox) cannot split,
        # and with no float environments in this pipeline nothing moves it — so
        # LuaTeX writes it past the media box and the tail is ABSENT from the PDF.
        # Measured: 17/45, 26/45 and 25/45 rows lost on three such sites while
        # every gate passed. (build.sh's Overfull-\vbox gate is the primary
        # detector; this one is the independent confirmation on the page itself.)
        # v3.65: the media-box test reads offpage_words() — the UNCULLED view —
        # because plain `words` silently drops exactly the glyphs this tier exists
        # to catch (see offpage_words for the calibration). It also compares
        # against page_box(), not page.rect, so a landscape /Rotate page no longer
        # hard-fails on a coordinate-space mismatch.
        pw, ph = page_box(page)
        for w in offpage_words(page):
            if not w[4].strip():
                continue
            if w[2] > pw + 0.5 or w[0] < -0.5:
                hard.append((pno + 1, "INK-OFF-PAPER",
                             f"'{w[4][:18]}' spans x=[{w[0]:.1f},{w[2]:.1f}] "
                             f"but the page is 0..{pw:.1f} — content is off the "
                             f"sheet and cannot print"))
            elif w[3] > ph + 0.5 or w[1] < -0.5:
                hard.append((pno + 1, "INK-OFF-PAPER",
                             f"'{w[4][:18]}' spans y=[{w[1]:.1f},{w[3]:.1f}] "
                             f"but the page is 0..{ph:.1f} — content ran off the "
                             f"page BOTTOM/TOP and is lost, not merely clipped"))

        # R5b's text-block tier keeps using the CULLED `words`: it infers the RTL
        # right margin from the modal line edge, a statistic that must be taken
        # over on-page body lines only.
        for w in words:
            if not w[4].strip():
                continue
            k = round(w[1] / 3.0)
            page_lines.setdefault(pno + 1, {})
            page_lines[pno + 1][k] = max(page_lines[pno + 1].get(k, 0.0), w[2])
            # v3.83 (R5c): the MIRROR statistic. R5b has only ever tracked the
            # RIGHT edge, so LEFT protrusion was invisible to this gate by
            # construction — that is how BIDI-70 shipped 216 choice labels
            # 25.65pt into the left margin with every layer printing clean.
            # v3.82 documented the blindness and did not close it; a synthesized
            # PDF carrying the exact pre-fix geometry still passed at exit 0.
            # Under LaTeX both edges are flush (justified), so the modal
            # per-line MIN-x is as sharp as the max: measured 414-1684 line
            # starts at exactly 65.0 in all 13 collections.
            page_lmin.setdefault(pno + 1, {})
            page_lmin[pno + 1][k] = min(page_lmin[pno + 1].get(k, 1e9), w[0])
            if w[0] < 200.0:
                left_words.setdefault(pno + 1, []).append(w)

        # --- collect footer folios for R3
        # v3.65: require the number to be HORIZONTALLY CENTRED. "Any digit in the
        # footer band, and only if there is exactly one" was wrong in both
        # directions on the real corpus:
        #   FALSE POSITIVE — computer-architecture p.6 warned "footer prints 135,
        #     expected -2". That 135 is a table-of-contents page number sitting
        #     233.7pt off-centre; the real folio was never even considered.
        #   FALSE NEGATIVE — 154 of 1874 pages have more than one digit-word in the
        #     band (a TOC page yields ['29','72','2']) and were dropped WHOLE, so a
        #     reversed folio there was invisible: exactly what R3 exists to catch.
        # This pipeline centres its folio, and the measurement is decisive: all
        # 1698 genuine folios sit at offset EXACTLY 0.00pt from the page centre.
        # A 12pt window is therefore generous. Measured effect: the FP disappears,
        # folio coverage rises 1699 -> 1825 pages, ambiguous pages fall 154 -> 24,
        # and the sweep over all 13 PDFs reports 0 new lines.
        cands = [text for text in footer_candidates(page, layout=folio_layout,
                                                    band=folio_band)
                 if text.isascii() and text.isdigit()]
        if len(cands) == 1:
            folios.append((pno, int(cands[0])))

    # --- R5b (v3.58): ink past the text block, calibrated DOCUMENT-WIDE.
    # The text-block edge is a document constant, so it must be inferred globally.
    # A first attempt inferred it PER PAGE and produced 28 false positives on a
    # healthy 119-page build: on pages dominated by short lines (display math,
    # lists, the title page) the per-page mode lands BELOW the true margin
    # (measured 536.5 / 477.5 / 276.5 against a real margin of 546.8), so every
    # genuine full-width line looked like an overshoot. Pooling every line in the
    # document fixes that — across a real document the overwhelming majority of
    # body lines end flush at the RTL right margin, making the mode sharp.
    # Requires a reasonable sample, else stay silent rather than guess.
    all_edges = [round(v * 2) / 2 for lines in page_lines.values() for v in lines.values()]
    if len(all_edges) >= 40:
        # Equal support can describe valid separate columns. Prefer the outer
        # right edge on a tie; a rarer line beyond that edge still warns below.
        margin = max(sorted(set(all_edges)), key=lambda edge: (all_edges.count(edge), edge))
        column_margin = _proven_column_right_margin(doc)
        if column_margin is not None:
            margin = column_margin
        for pg in sorted(page_lines):
            for v in sorted(page_lines[pg].values(), reverse=True):
                if v > margin + 2.0:
                    soft.append((pg, "INK-PAST-TEXT-BLOCK",
                                 f"a line reaches x={v:.1f}, {v - margin:.1f}pt past "
                                 f"the text block ({margin:.1f}) — a wide "
                                 f"\\item[label], an unbreakable island, or an "
                                 f"overfull box (TeX does NOT warn for an \\item "
                                 f"label: \\hss has infinite shrink)"))
                    break

    # --- R5c: list labels stranded in the LEFT margin (v3.83, BIDI-70's gate)
    # Deliberately NARROW. A plain mirror of R5b fires on 1084 listing line
    # numbers and 112 TOC dot-leaders across the fleet — both legitimate, both
    # by design — and a gate with a four-digit false-positive count is a gate
    # nobody runs. So this asks the one question that separates the defect from
    # the design: is a short LABEL-shaped token sitting left of the text block
    # while real body text on its own line starts at the block edge? That is
    # precisely the \item-label-outside-the-list geometry, and it is what the
    # 216 shipped labels looked like. Measured on all 13 shipped PDFs: 0 hits.
    all_lmin = [round(v * 2) / 2 for lines in page_lmin.values()
                for v in lines.values() if v < 1e8]
    if len(all_lmin) >= 40:
        ledge = min(sorted(set(all_lmin)), key=lambda e: -all_lmin.count(e))
        for pg in sorted(left_words):
            for w in left_words[pg]:
                if w[0] >= ledge - 2.0:
                    continue
                tok = w[4].strip()
                if not LABELISH.match(tok):
                    continue
                k = round(w[1] / 3.0)
                body = [u for u in left_words[pg]
                        if round(u[1] / 3.0) == k and u[0] >= ledge - 2.0]
                if not body:
                    continue        # nothing at the block edge: a folio or a note
                soft.append((pg, "LABEL-IN-LEFT-MARGIN",
                             f"'{tok}' starts at x={w[0]:.1f}, {ledge - w[0]:.1f}pt "
                             f"left of the text block ({ledge:.1f}), with body text "
                             f"on the same line at the block edge — a list label "
                             f"rendered OUTSIDE its list. Under an RTL base this is "
                             f"the signature of a list opened inside an LTR island "
                             f"(see LIST-IN-LTR-ISLAND); TeX does not warn"))

    # --- R3: declared labels and actual centred glyphs (v4.24.0).
    folio_note = "folio sequence not inferred"
    if folio_layout in ('none', 'custom'):
        # A selected design can omit page numbers or use geometry outside this
        # detector. Be explicit about the unmeasured population; all other
        # rendered-PDF gates remain active, and bad label metadata still fails.
        reason = ('the document contract intentionally omits printed folios'
                  if folio_layout == 'none' else
                  'the document contract uses custom folios; verify every folio visually')
        soft.append((0, 'FOLIO-NOT-MEASURED', reason + '; printed numbering was not verified'))
        folio_note = 'printed numbering not verified'
    elif labels is not None:
        result = labelled_folios(doc, labels, layout=folio_layout, band=folio_band)
        hard.extend(result.findings)
        folio_note = (f"{result.observed}/{result.expected} {folio_layout} {folio_band} folios "
                      "compared with PDF PageLabels")
    elif not label_error:
        # --- R3: folio sequence and coverage. A sequence rule that observes no
        # folios cannot honestly report "consistent".
        if doc.page_count >= 3:
            required = max(2, (doc.page_count + 1) // 2)
            if len(folios) < required:
                hard.append((0, "FOLIO-COVERAGE-LOW",
                             f"found {folio_layout} {folio_band} Arabic folios on only {len(folios)}/"
                             f"{doc.page_count} pages; need at least {required} to "
                             "verify the sequence"))
        if len(folios) >= 3:
            offsets = [printed - idx for idx, printed in folios]
            # sorted() -> deterministic tie-break (max over a raw set breaks ties
            # by opaque iteration order — a nondeterminism inside the determinism gate)
            common = max(sorted(set(offsets)), key=offsets.count)
            if offsets.count(common) >= max(3, (len(folios) + 1) // 2):
                for (idx, printed), off in zip(folios, offsets):
                    if off == common:
                        continue
                    expected = idx + common
                    if str(printed) == str(expected)[::-1] and printed != expected:
                        hard.append((idx + 1, "PAGE-NUMBER-REVERSED",
                                     f"footer prints {printed}, expected {expected} "
                                     f"(digit-reversal — the known bidi glitch)"))
                    else:
                        hard.append((idx + 1, "PAGE-NUMBER-ODD",
                                     f"footer prints {printed}, expected {expected}"))
            else:
                hard.append((0, "FOLIO-SEQUENCE-UNINFERABLE",
                             f"{len(folios)} {folio_layout} {folio_band} folios do not share a stable "
                             "page-number offset"))

        folio_note = (f"{len(folios)}/{len(doc)} Arabic folios observed; "
                      "legacy sequence inferred" if len(folios) >= 3 else
                      f"{len(folios)}/{len(doc)} Arabic folios observed; "
                      "too few to infer a sequence")

    # --- R6: destination landing (post-loop; see dest_landing()).
    ndest = dest_landing(doc, hard, soft, caption_color=caption_color,
                        caption_label_weight=caption_label_weight)
    # BLD-38 budget. The cross-page population is reported per site above; a
    # sweep that knows the fleet's number can make it a HARD count assertion,
    # so the population cannot grow without a signal. No default budget: the
    # per-site ⚠ is the always-on signal, and check() must stay usable on a
    # document nobody has counted yet.
    ncross = sum(1 for _pg, code, _m in soft if code == "DEST-CROSS-PAGE-CAPTION")
    if max_cross_page is not None and ncross > max_cross_page:
        hard.append((0, "DEST-CROSS-PAGE-BUDGET",
                     f"{ncross} cross-page caption destination(s), budget "
                     f"{max_cross_page} — the BLD-38 population GREW. Either "
                     f"fix the new site(s) named above or raise the budget "
                     f"deliberately, in the same commit that records why"))

    # page 0 = a DOCUMENT-level finding (a population budget); it has no page.
    def _where(pg):
        return f"p.{pg} " if pg else "whole document "
    for pg, code, msg in hard:
        print(f"  ✗ {_where(pg)}[{code}] {msg}")
    for pg, code, msg in soft:
        print(f"  ⚠ {_where(pg)}[{code}] {msg}")
    if not hard and not soft:
        # The destination clause names the POPULATION it judged. A document
        # with no \figcap/\tabcap gets no clause at all rather than "all 0
        # destinations are fine" — a clean line that asserts something about
        # an empty set is how a silently-blind rule reads as a pass.
        dest_note = (f", and all {ndest} \\figcap/\\tabcap destinations land "
                     f"at or above the object they point at"
                     if ndest > 1 else
                     ", and the one \\figcap/\\tabcap destination lands at or "
                     "above the object it points at" if ndest == 1 else "")
        print(f"  ✓ render check clean ({len(doc)} pages: no reversed Latin "
              f"runs, no mirrored paren-digit groups, {folio_note}{dest_note})")
    doc.close()
    return 1 if hard else 0


def main(argv=None):
    parser = argparse.ArgumentParser(description='Inspect PDF glyph geometry, numbering and object destinations.')
    parser.add_argument('pdf')
    parser.add_argument('sources', nargs='*')
    parser.add_argument('--max-cross-page', type=int)
    parser.add_argument('--folio-layout', choices=FOLIO_LAYOUTS, default='center')
    parser.add_argument('--folio-band', choices=FOLIO_BANDS, default='footer')
    parser.add_argument('--caption-color', type=parse_rgb_hex, default=CAP_COLOR,
                        help='exact RGB caption-label color as RRGGBB (default: 555555)')
    parser.add_argument('--caption-label-weight', choices=CAPTION_LABEL_WEIGHTS, default='bold',
                        help='declared label weight; normal requires a leading colon caption label')
    args = parser.parse_args(argv)
    if args.max_cross_page is not None and args.max_cross_page < 0:
        parser.error('--max-cross-page must be a non-negative integer')
    return check(args.pdf, args.sources, args.max_cross_page,
                 folio_layout=args.folio_layout, folio_band=args.folio_band,
                 caption_color=args.caption_color, caption_label_weight=args.caption_label_weight)


if __name__ == '__main__':
    sys.exit(main())
