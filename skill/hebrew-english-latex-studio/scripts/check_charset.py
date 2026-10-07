#!/usr/bin/env python3
r"""check_charset.py — catch stray/confusable codepoints BEFORE you compile.

Prose and TeX syntax use a conservative house allow-list. Literal code blocks
may additionally use any printable codepoint covered by the pinned monospace
font; a symbol that is safe in code is not thereby approved for RTL prose.

The classic trap this catches: typing "סקרי" (scree) where the ר/י were
auto-"corrected" to the Arabic ر (U+0631) / ي (U+064A). It looks perfect on
screen, compiles, and renders two tofu boxes. `build.sh` runs this as a HARD
gate (like missing characters) because every hit is a guaranteed render bug.

Usage:  python3 check_charset.py file1.tex [file2.tex ...]
Exit:   0 = clean, 1 = stray codepoints found, 2 = bad usage.
"""
import sys as _bytecode_sys
_bytecode_sys.dont_write_bytecode = True
from pathlib import Path
import re
import sys
import unicodedata

from fontTools.ttLib import TTFont
from font_policy import (
    HEBREW_ALLOWED,
    LATIN_COMBINING_ALLOWED,
    LATIN_PRECOMPOSED_ALLOWED,
    TYPOGRAPHIC_ALLOWED,
)

# A codepoint inside a LaTeX comment cannot tofu (the comment is not rendered),
# so — like check_bidi_figures — blank the comment tail before scanning. Blank
# with spaces (not delete) so reported line:col stays exact for real code hits.
# v3.76: EXCEPT inside lstlisting/verbatim, where '%' is literal, RENDERED
# content — blanking there masked real page content from this HARD gate
# (measured: a stray after '30%' inside a pystyle listing passed "charset
# clean"; before the '%' it was flagged). The main loop is now verbatim-aware,
# porting v3.71's envline discipline from check_bidi_figures with the polarity
# inverted: bidi SKIPS its rules inside verbatim, charset must SCAN THE RAW
# LINE there (charset applies to literal content — that is the whole point).
def _strip_comment(line: str) -> str:
    r"""Blank the comment tail. Backslash-PARITY aware: \% is a literal percent,
    but \\% (table line-break then %) DOES start a comment."""
    i = 0
    while True:
        j = line.find('%', i)
        if j < 0:
            return line
        k = j - 1
        while k >= 0 and line[k] == '\\':
            k -= 1
        if (j - 1 - k) % 2 == 0:            # even backslash run -> real comment
            return line[:j] + ' ' * (len(line) - j)
        i = j + 1

# literal-content environments: '%' inside them is rendered text, not a comment
VERB_OPEN = re.compile(r'\\begin\{(lstlisting|verbatim|Verbatim)\*?\}')

_MONO_CMAP = None


def mono_cmap():
    """Codepoints covered by the exact bundled monospace face."""
    global _MONO_CMAP
    if _MONO_CMAP is None:
        from font_paths import font_dir
        path = font_dir() / "DejaVuSansMono.ttf"
        try:
            font = TTFont(path, lazy=True)
            _MONO_CMAP = set()
            for table in font["cmap"].tables:
                _MONO_CMAP.update(table.cmap)
            font.close()
        except (OSError, KeyError):
            _MONO_CMAP = set()
    return _MONO_CMAP


def allowed_in_literal(cp: int) -> bool:
    category = unicodedata.category(chr(cp))
    return cp in mono_cmap() and category not in {"Cc", "Cf", "Cs", "Co", "Cn"}

# --- allowed singletons (control + the typographic marks we actually use) ----
ALLOWED_SINGLE = {0x09, 0x0A, 0x0D, 0xA0}            # tab, LF, CR, nbsp
def allowed(cp: int) -> bool:
    if 0x20 <= cp <= 0x7E:            return True   # ASCII printable (LaTeX + Latin)
    # Names and prose may legitimately contain Latin-1/Extended letters
    # (Gödel, Schrödinger, José, Łódź). The bundled Latin fallback covers this
    # range; Greek/Cyrillic remain explicitly rejected below.
    if cp in LATIN_PRECOMPOSED_ALLOWED:
        return True
    if cp in HEBREW_ALLOWED:            return True
    if cp in ALLOWED_SINGLE:          return True
    if cp in TYPOGRAPHIC_ALLOWED:       return True
    return False

# blocks whose chars masquerade as Hebrew/Latin — name them explicitly
CONFUSABLE = [
    (0x0591, 0x05AF, "Hebrew CANTILLATION mark — tofu in Frank Ruhl (drop it, or switch to a font with te'amim)"),
    (0x200E, 0x200F, "bidi CONTROL mark (LRM/RLM) — invisible direction voodoo; use \\en{}/\\h{} isolation instead"),
    (0x202A, 0x202E, "bidi EMBEDDING mark — invisible direction voodoo; use \\en{}/\\h{} isolation instead"),
    (0xFB1D, 0xFB4F, "Hebrew PRESENTATION form — normalize to base letter + mark (NFC)"),
    (0x0600, 0x06FF, "ARABIC (ر/ي look like Hebrew resh/yod!)"),
    (0x0400, 0x04FF, "CYRILLIC (а/е/о/р/с look like Latin a/e/o/p/c)"),
    (0x0370, 0x03FF, "GREEK (type \\alpha, \\Omega … in math, not the raw glyph)"),
    # v3.32: raw arrows got the generic "will tofu" message though the fix is
    # specific — and direction-sensitive in RTL prose.
    (0x2190, 0x21FF, "ARROW glyph — type it as math; in Hebrew prose flow use "
                     "$\\leftarrow$ (a rightward arrow points against RTL "
                     "reading; see HEBREW-FLOW-ARROW)"),
    # v3.32: the advice must not pipe into a bidi flag — in HEBREW prose a
    # rightward arrow needs $\leftarrow$ (HEBREW-FLOW-ARROW) and a leading
    # relational op goes OUTSIDE the math (HEBREW-BEFORE-OP-MATH: 'לכל היותר $4$').
    (0x2200, 0x22FF, "MATH SYMBOL (type \\le \\in … in math — but in Hebrew "
                     "prose put the operator OUTSIDE the math and use "
                     "\\leftarrow for flow, per the bidi checker's hints)"),
]
def why(cp: int) -> str:
    if cp in LATIN_COMBINING_ALLOWED:
        return "decomposed Latin accent — normalize the source to NFC"
    for lo, hi, msg in CONFUSABLE:
        if lo <= cp <= hi:
            return msg
    return "outside the allow-list — tofu risk or house-style escape required"

def main(argv):
    files = argv[1:]
    if not files:
        print("usage: python3 check_charset.py file.tex [...]"); return 2
    hits = 0
    for path in files:
        try:
            try:
                # v3.71: split on \n only (after \r normalisation) — .splitlines()
                # also splits on U+2028/U+0085, CONSUMING the very stray codepoints
                # this gate exists to catch (measured: U+2028 passed "charset clean").
                lines = (open(path, encoding="utf-8").read()
                         .replace("\r\n", "\n").replace("\r", "\n").split("\n"))
            except UnicodeDecodeError as e:
                # v3.33.1: a non-UTF8 source IS a charset defect — report it
                # cleanly instead of a Python traceback (robustness audit).
                print(f"{path}: NOT valid UTF-8 ({e}). Re-encode the file; "
                      f"LaTeX sources in this pipeline are UTF-8 only.")
                hits += 1
                continue
        except OSError as e:
            print(f"❌ cannot read {path}: {e}"); hits += 1; continue
        in_verbatim = None      # env name while inside a literal-content block
        for ln, raw in enumerate(lines, 1):
            literal_mask = [False] * len(raw)
            if in_verbatim:
                # '%' is CONTENT here, so the end-marker is searched on the RAW
                # line (the engine finds the end-string even after a literal %)
                # and everything up to it is scanned raw. The tail after
                # \end{...} is normal TeX again — comment rules apply there
                # (the BLD-39 end-line-tail lesson).
                m = re.search(r'\\end\{' + re.escape(in_verbatim) + r'\*?\}', raw)
                if m:
                    literal_mask[:m.start()] = [True] * m.start()
                    line = raw[:m.end()] + _strip_comment(raw[m.end():])
                    in_verbatim = None
                else:
                    line = raw
                    literal_mask = [True] * len(raw)
            else:
                # structure detection on the comment-STRIPPED line (envline
                # discipline, BLD-41): a commented '% \begin{lstlisting}' in
                # prose must not poison state. The \begin line itself is
                # normal TeX — the listing starts on the NEXT line.
                line = _strip_comment(raw)      # ignore codepoints in comments
                m = VERB_OPEN.search(line)
                if m:
                    # v3.83 (BIDI-71 twin): a ONE-LINE block must not latch.
                    # v3.82 shipped the claim that this checker "had handled the
                    # same shape correctly since v3.76". It had not — it carried
                    # the identical latch, and on a HARDER gate: build.sh aborts
                    # on charset, so the consequence here is a false ALARM, not
                    # silence. Once latched, `line = raw` to EOF and comments are
                    # never stripped again, so any confusable codepoint inside a
                    # trailing `% TODO: fix the Ω` comment — unrendered, harmless
                    # — fails the build. Measured: two files differing only in
                    # `\begin{verbatim}x\end{verbatim}` vs plain prose exit 0 and
                    # 1. The end-marker is sought in RAW (the body is literal, so
                    # a `%` there is content); the tail after it is TeX again.
                    e = re.search(r'\\end\{' + re.escape(m.group(1)) + r'\*?\}',
                                  raw[m.end():])
                    if e:
                        body_end = m.end() + e.start()
                        literal_mask[m.end():body_end] = [True] * (body_end - m.end())
                        cut = m.end() + e.end()
                        line = raw[:cut] + _strip_comment(raw[cut:])
                    else:
                        literal_mask[m.end():] = [True] * (len(raw) - m.end())
                        in_verbatim = m.group(1)
            for col, ch in enumerate(line, 1):
                cp = ord(ch)
                literal_here = col - 1 < len(literal_mask) and literal_mask[col - 1]
                if allowed(cp) or (literal_here and allowed_in_literal(cp)):
                    continue
                hits += 1
                try:    name = unicodedata.name(ch)
                except ValueError: name = "?"
                ctx = raw.strip()[:60]
                print(f"{path}:{ln}:{col}: U+{cp:04X} {ch!r} ({name})")
                if literal_here:
                    print("    → absent from the pinned DejaVu Sans Mono cmap "
                          "or unsafe as an invisible/control codepoint")
                else:
                    print(f"    → {why(cp)}")
                print(f"    … {ctx}")
    print("-" * 60)
    if hits:
        print(f"✗ {hits} stray codepoint(s). Replace each with its ASCII/Hebrew")
        print("  equivalent (e.g. Arabic ر→Hebrew ר, Greek Ω→$\\Omega$).")
        return 1
    print("✓ charset clean: prose policy holds; literal code is covered by the pinned mono font.")
    return 0

if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] in {"-h", "--help"}:
        print(__doc__.strip())
        sys.exit(0)
    sys.exit(main(sys.argv))
