#!/usr/bin/env python3
"""probe_lstnum.py — do a compiled PDF's listing lines carry MARGIN NUMBERS?

A measurement probe (not a linter — no selftest corpus, no FP budget over the
fleet): it answers ONE geometric question about a rendered page, so the
harness can PIN v3.78's in-exbox listing numbering instead of merely
compiling the file that demonstrates it. Before this probe existed, deleting
clean_theme.tex's three \\thelstnumber restore hooks left build.sh green and
test_all.sh at "63 passed / ALL TESTS PASS" with the feature gone (measured).

STRUCTURAL, not coordinate-hardcoded. Every test below reads a key that
preamble.tex's four `\\lstdefinestyle` blocks actually set — `numbers=left`,
`numberstyle=\\tiny\\color{cGray}`, `numbersep=8pt` — so the probe measures the
mechanism it is pinning:

  code_size    = smallest MONO font size on the page (the listing's basicstyle)
  code column  = the x0 of a mono span
  margin digit = an all-digit NON-mono span that is
                   (a) coloured cGray (#555555)   <- numberstyle's \\color
                   (b) SMALLER than code_size     <- numberstyle's \\tiny
                   (c) hanging LEFT of a code column, at most NUMSEP_MAX away
                                                  <- numbers=left's \\llap at
                                                     numbersep

v3.82 — WHAT v3.81's VERSION GOT WRONG, and how it was measured.
The old rule was "an all-digit non-mono span with x1 <= code_x whose vertical
centre falls inside a mono y-band", and its docstring asserted that inline
\\code{} "can never satisfy this" and that a page number "cannot either".
BOTH are false on a TOC page, and the y-band half was blind on a real page:

  * FALSE POSITIVES (6, measured on data-science-exams/src/final.pdf). pp.2-4
    are the TOC. Inline \\code{} in an entry title pushes the page's leftmost
    mono x0 out to 271.26 / 246.39 / 326.08, and the TOC's own ENTRY PAGE
    NUMBERS sit at x=65.20 — left of that, and on the same y-band as the
    \\code{} beside them. The old probe counted them: 16, 24, 72, 75, 118, 143.
  * FALSE NEGATIVES (6, same PDF). A numbered but BLANK code line puts no mono
    ink on its own y-band, so no band contains its number. p.17 renders 1..14
    and the old probe reported 9 (dropping 2, 6, 8, 10, 12); p.144's second
    listing renders 1..7 and it reported 6 (dropping 3).
  * The published "81 over the 7 pages" was therefore right by two errors
    cancelling: 75 real + 6 FP = 81, and the true count is 81 = 14+9+12+20+7+
    6+13. (The v3.81 audit put the false-negative count at 5; it is 6 — the
    p.144 site was missed.)
  * A third class the old rule never named: a plain black digit in a TABLE
    column that happens to sit left of a mono cell. computer-architecture
    scored 166 under the old rule against 72 real numbers.

The style tests (a)+(b) are what kill all three; they are load-bearing and
measured, not defensive decoration. Over the 13 built collections (1875 pages)
plus the two skill assets, 1109 margin digits are found and the ablations are:
drop (b) -> 1126 (+17 FP), drop (a) -> 1290 (+181 FP), drop both -> 2760.
All 1109 hang at gap 7.97pt — numbersep=8pt, to PDF rounding — with no second
value anywhere on the fleet, so NUMSEP_MAX below is belt-and-braces (16.0 and
30.0 and "no bound at all" all return the same 1109).

HONEST LIMITS (this repo documents them rather than pretending):
  * The probe reads numberstyle. Restyle the numbers to the code colour or to
    a size >= basicstyle and it goes BLIND — but blind means 0 hits, i.e.
    exit 1, a LOUD failure. It cannot go quietly green.
  * code_size is the page's smallest mono size. A page that also carries mono
    ink SMALLER than its listing numbers (a \\tiny \\code{} in a footnote) would
    suppress them. No such page exists on the fleet; if one appears the count
    drops and the probe fails loudly, it does not over-count.
  * It counts DIGITS on the page, not listing lines: a document that sets
    firstnumber or numberstyle per listing is still counted correctly, but the
    probe cannot say WHICH listing a digit belongs to. --anchor is the tool
    for that.

--anchor pins WHICH listing: only the page carrying that literal string is
scanned, so the count cannot be satisfied by some other listing elsewhere.

Exit codes are SPECIFIC (the v3.71 lesson — "any nonzero" hides crashes and
deleted fixtures):
  0  the expected number of margin digits is present
  1  FINDING: wrong count (0 = the numbering regressed)
  2  unusable: pymupdf missing, no such file, or the anchor is not in the PDF
     (the exemplar drifted — nothing was pinned, which is not a pass)

Usage:
  python3 scripts/probe_lstnum.py <pdf> --expect N [--anchor TEXT]
"""
import sys

try:
    import fitz
except ImportError:
    print("probe_lstnum: pymupdf missing "
          "(pip install --break-system-packages pymupdf)")
    sys.exit(2)


# numberstyle=\tiny\color{cGray}; cGray is #555555 in preamble.tex (line 344)
# and clean_theme.tex (therefore the legacy bundle) does not redefine it.
NUM_COLOR = 0x555555
# numbersep=8pt in all four \lstdefinestyle blocks; measured 7.97pt at every
# one of the 1109 fleet sites (PDF rounding). 16.0 = 2x, with no competing
# value on the fleet at any distance.
NUMSEP_MAX = 16.0


def spans(page):
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            for s in line["spans"]:
                if s["text"].strip():
                    yield s


def margin_digits(page):
    """[(text, x0, code_x, y0, gap)] — every listing line number on this page."""
    mono, other = [], []
    for s in spans(page):
        (mono if "Mono" in s["font"] else other).append(s)
    if not mono:
        return []
    code_size = min(s["size"] for s in mono)
    code_xs = sorted({s["bbox"][0] for s in mono})
    hits = []
    for s in other:
        txt = s["text"].strip()
        if not txt.isdigit():
            continue
        # numberstyle: cGray, and \tiny -> strictly smaller than basicstyle.
        if s["color"] != NUM_COLOR or s["size"] >= code_size:
            continue
        x0, y0, x1, _y1 = s["bbox"]
        # numbers=left \llaps the number against the code box: the nearest
        # code column at or right of the digit must be within numbersep.
        col = next((c for c in code_xs if c >= x1 - 0.01), None)
        if col is None or col - x1 > NUMSEP_MAX:
            continue
        hits.append((txt, x0, col, y0, col - x1))
    return sorted(hits, key=lambda h: h[3])


def main(argv):
    if not argv or "--expect" not in argv:
        print(__doc__)
        return 2
    path = argv[0]
    expect = int(argv[argv.index("--expect") + 1])
    anchor = argv[argv.index("--anchor") + 1] if "--anchor" in argv else None
    try:
        doc = fitz.open(path)
    except Exception as exc:                      # missing / unreadable PDF
        print(f"probe_lstnum: cannot open {path}: {exc}")
        return 2
    with doc:
        pages, found = [], False
        for page in doc:
            if anchor is None:
                pages.append(page)
            elif any(anchor in s["text"] for s in spans(page)):
                pages.append(page)
                found = True
        if anchor is not None and not found:
            print(f"probe_lstnum: anchor {anchor!r} is not in {path} — the "
                  f"exemplar drifted, so nothing was pinned (not a pass)")
            return 2
        hits = [(page.number + 1, h) for page in pages
                for h in margin_digits(page)]
    print(f"{path}: {len(hits)} margin line-number(s) "
          f"(want {expect})" + (f" on the page carrying {anchor!r}" if anchor else ""))
    for pno, (txt, x0, code_x, lo, gap) in hits:
        print(f"  p.{pno} y={lo:.2f}  digit {txt!r} at x={x0:.2f} "
              f"< code_x={code_x:.2f} (numbersep gap {gap:.2f}pt)")
    if len(hits) != expect:
        print(f"probe_lstnum: FINDING — {len(hits)} margin digits, expected "
              f"{expect}" + (" (0 = the listing shipped numberless)"
                             if not hits else ""))
        return 1
    # --inside-rule (v4.5.0): counting digits is not enough for a listing inside
    # a FRAMED box. The pre-v4.5.0 defect rendered all five numbers — they were
    # simply drawn ON the box rule, half a digit either side of it, which every
    # count-based check reads as a pass. This asserts the geometry the count
    # cannot see: every margin digit sits strictly right of the leftmost
    # vertical rule on its page, with clearance to spare.
    if "--inside-rule" in argv:
        floor = 2.0
        with fitz.open(path) as doc:
            bad = []
            for pno, (txt, x0, code_x, lo, gap) in hits:
                page = doc[pno - 1]
                # The OUTER frame: the leftmost vertical rule on the page. A
                # digit drawn left of it, or on it, is the defect — and that is
                # exactly where the pre-v4.5.0 in-box numbers landed.
                verts = [d["rect"] for d in page.get_drawings()
                         if d["rect"].width < 3 and d["rect"].height > 15]
                if not verts:
                    continue
                rule = min(verts, key=lambda r: r.x0).x1
                if x0 - rule < floor:
                    bad.append((pno, txt, x0, rule))
            for pno, txt, x0, rule in bad:
                print(f"  p.{pno} digit {txt!r} at x={x0:.2f} sits on the rule "
                      f"at x={rule:.2f} (clearance {x0-rule:.2f}pt, floor {floor}pt)")
            if bad:
                print(f"probe_lstnum: FINDING — {len(bad)} margin digit(s) "
                      f"collide with the frame they sit inside")
                return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
