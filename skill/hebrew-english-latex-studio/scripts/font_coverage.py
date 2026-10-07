#!/usr/bin/env python3
"""font_coverage.py — what does a font actually contain?

A font compiling without error does NOT mean it has the glyphs you need. Two
distinct traps this catches:

 1. NO HEBREW. On some systems DejaVu Serif ships with Latin but ZERO Hebrew,
    so it silently renders all Hebrew as tofu. Never trust a body font unchecked.

 2. NO DIGITS / NO LOWERCASE. A subset font can contain a token Latin glyph
    while missing normal prose, numbers or punctuation. The checker probes
    complete policy classes rather than treating a single `A` as evidence.

    A missing class requires a verified, weight-matched fallback; otherwise
    emphasis can silently disappear even when no tofu is emitted.

Usage:
    python3 font_coverage.py /path/to/font.ttf [more.ttf ...]

Exit: 0 = every font covers Hebrew, 1 = a font is unusable as a Hebrew body
font, 2 = bad usage. A missing digit/lowercase class is reported as a WARNING
(the font is still usable as a body font WITH a fallback), not a hard failure.
"""
import sys as _bytecode_sys
_bytecode_sys.dont_write_bytecode = True
import sys
from font_policy import HEBREW_ALLOWED

try:
    from fontTools.ttLib import TTFont
except ImportError:
    sys.exit("fontTools not installed:  pip install --break-system-packages fonttools")

# Probe a SET per class, not one codepoint — a subset font can carry a token
# member of a class (the 'A' trap above) while missing the rest of it.
CLASSES = [
    # v3.75: final forms + the charset-gate parity marks added. The old 3-probe
    # set had NO final forms and none of the marks check_charset explicitly
    # blesses (maqaf, geresh/gershayim, ₪) — a body font lacking maqaf passed
    # every class while the charset gate green-lights maqaf into tofu.
    ("hebrew",    sorted(HEBREW_ALLOWED),              "all allowed Hebrew codepoints"),
    ("hebmarks",  [0x05BE, 0x05F3, 0x05F4, 0x20AA],          "maqaf/geresh/gershayim/₪"),
    ("uppercase", [0x41, 0x4D, 0x5A],                 "Latin A-Z"),
    ("lowercase", [0x61, 0x6D, 0x7A],                 "Latin a-z"),
    ("digits",    [0x30, 0x35, 0x39],                 "digits 0-9"),
    ("punct",     [0x28, 0x29, 0x2C, 0x2E, 0x2D],     "( ) , . -"),
]
# Which classes, if absent, mean emphasis silently stops applying to that class.
EMPHASIS_CRITICAL = {"lowercase", "digits", "punct", "uppercase"}


def main(argv):
    if len(argv) < 2:
        # v3.75: docstring promises exit 2 for bad usage; sys.exit(str) exits 1 —
        # indistinguishable from "font unusable" (measured).
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    worst = 0
    for path in argv[1:]:
        try:
            cmap = TTFont(path).getBestCmap()
        except Exception as e:  # noqa: BLE001
            print(f"{path}\n    ERROR: {e}")
            worst = max(worst, 1)
            continue
        present, missing, partial = {}, [], []
        for key, cps, label in CLASSES:
            have = [c for c in cps if c in cmap]
            present[key] = len(have)
            if not have:
                missing.append((key, label))
            elif len(have) < len(cps):
                partial.append((key, label, len(have), len(cps)))

        total = len(cmap)
        print(f"{path}\n    codepoints: {total}   " + "   ".join(
            f"{k}:{'yes' if present[k] == len(c) else ('PARTIAL' if present[k] else 'NO')}"
            for k, c, _l in CLASSES))
        heb_required = len(CLASSES[0][1])
        if present["hebrew"] < heb_required:
            # v3.75: PARTIAL Hebrew is now a HARD FAIL too. A crafted font with a
            # single א used to get "✓ full coverage" + exit 0 — the BLD-26 false
            # all-clear pattern reborn inside the rewritten script, and worse:
            # missing Hebrew in the BODY font is real tofu (the fallback has no
            # Hebrew at all, cmap-verified).
            print("    ✗ HEBREW INCOMPLETE — usable ONLY as a fallback, never as the body font")
            worst = max(worst, 1)
        gaps = [k for k, _l in missing] + [k for k, _l, _h, _t in partial]
        emph = [g for g in gaps if g in EMPHASIS_CRITICAL]
        if emph:
            print(f"    ⚠ missing/partial: {', '.join(gaps)}")
            print(f"      → those characters come from the FALLBACK font, which means")
            print(f"        \\textbf and \\emph SILENTLY DO NOT APPLY to them unless a")
            print(f"        bold/italic fallback list is registered too (see preamble")
            print(f"        hebfb / hebfbbf, v3.56). Prefer a full-coverage family.")
        elif present["hebrew"] == heb_required and not gaps:
            print("    ✓ full coverage — Hebrew, Latin, digits and punctuation all present")
        elif present["hebrew"] == heb_required:
            # v3.75: never print "full coverage" with a non-empty gap list.
            print(f"    ⚠ Hebrew complete but gaps remain: {', '.join(gaps)}")
    return worst


if __name__ == "__main__":
    sys.exit(main(sys.argv))
