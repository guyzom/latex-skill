#!/usr/bin/env python3
"""Catch source defects that compile clean but render as visible mistakes.

Hard findings:
  * BARE-LATEX-COMMAND — command-like words such as ``qquad`` or ``frac``
    appear without an effective leading backslash inside math.

  * SPLIT-MATH-IN-HEADING — a symbolic Hebrew heading expression is split
    into separate inline math islands joined by a text connector.

Bare-command exemptions, both measured as fleet false positives at v4.1.0 adoption
(5 files, 8 spurious findings, 0 true ones):
  * reference-argument macros — a ``\\label{eq:quad}`` KEY sits inside the
    scanned math environment, and the word there is an identifier, not
    rendered output; the whole ref/label/tag/cite argument is masked.
  * ``tikzpicture`` bodies — plot expressions (``1/sqrt(2*pi)``) are
    plot-engine syntax, not TeX math, and a node label like ``...\\\\$x$``
    (line-break abutting the ``$``) flips the file-global single-``$``
    parity so every later "pair" straddles arbitrary content. Both the
    poison and the bite live inside pictures; picture bodies are masked.

  * PDFSTRING-LINEBREAK-ARG — a starred/optional-length line break
    leaks literal layout syntax into a bookmark or PDF metadata text.

  * PGFPLOTS-CONTOUR-EXTERNAL — pgfplots ``contour lua``, ``contour gnuplot``
    or their common base ``contour external`` computes contour lines at
    COMPILE time through a generated script the build gate cannot run, and a
    result left in the source directory by an earlier compile is read
    instead (v4.26.0, BLD-70). Only pgfkeys contexts are scanned: plot and
    axis options, and pgfplotsset/tikzset/pgfkeys arguments.

Advisory layout warning:
  * NEEDSPACE-IN-MULTICOLS — ``\\Needspace`` is used directly inside a
    ``multicols`` region, or through a custom macro expanded there.  The
    combination can force an almost-empty page under RTL column output.

Comments and verb/lstinline/block literals are masked in lexical source order.
Only the literal itself is exempt; surrounding live mathematics stays checked.

Exit 0 means no hard findings.  Layout warnings remain advisory unless
``--strict-layout`` is supplied.  Exit 1 means a finding; exit 2 means an
input/usage error.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
import sys
sys.dont_write_bytecode = True
from heading_source import (COMMAND as _CONTROL, split_math_findings,
                            inline_literal_end as _inline_end,
                            _comment_end, _tex_space, _option_end)
from pdf_string_source import linebreak_findings


LITERAL_ENVS = ("lstlisting", "lstlisting*", "verbatim", "verbatim*",
                "Verbatim", "Verbatim*")
MATH_ENVS = (
    "equation", "equation*", "align", "align*", "alignat", "alignat*",
    "gather", "gather*", "multline", "multline*", "flalign", "flalign*",
    "split", "aligned", "alignedat", "cases", "matrix", "pmatrix",
    "bmatrix", "Bmatrix", "vmatrix", "Vmatrix",
)
BARE_WORDS = (
    "qquad", "quad", "dfrac", "tfrac", "frac", "mathrm", "mathbf",
    "mathcal", "operatorname", "sqrt",
)
TEXT_IN_MATH_MACROS = (
    "text", "mbox", "textrm", "textnormal", "operatorname", "mathrm",
    "mathbf", "mathcal", "en", "h", "code",
)
# Arguments of these are identifiers/keys, never rendered words — masked like
# text macros so a \label{eq:quad} inside an equation cannot fire (measured
# fleet FP class 1).
REF_ARG_MACROS = (
    "label", "ref", "eqref", "autoref", "nameref", "pageref",
    "cref", "Cref", "tag", "cite",
)
# Environments whose BODY is engine syntax, not prose TeX (measured fleet FP
# class 2 — see the module docstring). Masked for every scan.
NON_PROSE_ENVS = ("tikzpicture",)


@dataclass(frozen=True)
class Finding:
    path: Path
    line: int
    flag: str
    message: str
    warning: bool = False


# Lexical masking must happen in source order. A percent inside a completed
# inline literal is data, not a comment; a dollar there must not change the
# math scanner's delimiter pairing. These helpers never rewrite the document.
def _blank(chars: list[str], start: int, end: int) -> None:
    for i in range(start, end):
        if chars[i] not in "\r\n":
            chars[i] = " "


def _nonprose_end(text: str, pos: int, env: str) -> int | None:
    """Find a normal-TeX environment end, not one merely named in a comment.

    TikZ is exempt engine syntax, but it is NOT verbatim: its comments and
    control symbols retain their ordinary meaning. A fake end marker in a
    comment must not expose a partial picture to the math scanner.
    """
    depth, i = 1, pos
    while i < len(text):
        if text[i] == "%":
            i = _comment_end(text, i)
            continue
        command = _CONTROL.match(text, i)
        if command is None:
            i += 1
            continue
        name = command[0][1:]
        end = command.end()
        if name in {"verb", "lstinline"}:
            literal_end = _inline_end(text, end, name)
            if literal_end is not None:
                i = literal_end
                continue
        if name in {"begin", "end"}:
            arg = _tex_space(text, end)
            match = re.match(r"\{" + re.escape(env) + r"\}", text[arg:])
            if match:
                depth += 1 if name == "begin" else -1
                end = arg + match.end()
                if depth == 0:
                    return end
        i = end
    return None


def mask_source(text: str, envs=LITERAL_ENVS + NON_PROSE_ENVS) -> str:
    """Mask comments and recognized literals once, preserving every offset.

    Only complete recognized literal regions are blanked. An unterminated
    inline/block form is left for the engine and other gates; it never hides
    the rest of the file. alltt is deliberately not a literal environment.
    This is a bounded lexical view, not macro expansion or TeX validation.
    """
    chars = list(text)
    i = 0
    while i < len(text):
        if text[i] == "%":
            end = _comment_end(text, i)
            _blank(chars, i, end)
            i = end
            continue
        match = _CONTROL.match(text, i)
        if match is None:
            i += 1
            continue
        name, end = match[0][1:], match.end()
        if name in {"verb", "lstinline"}:
            stop = _inline_end(text, end, name)
            if stop is not None:
                _blank(chars, i, stop)
                i = stop
                continue
        if name == "begin":
            arg_start = _tex_space(text, end)
            env = re.match(r"\{([A-Za-z]+\*?)\}", text[arg_start:])
            if env and env[1] in envs:
                # Existing block forms use their literal closing marker.
                # A percent in their body does not comment out the marker.
                body_start = arg_start + env.end()
                if env[1] in NON_PROSE_ENVS:
                    stop = _nonprose_end(text, body_start, env[1])
                else:
                    marker = r"\end{" + env[1] + "}"
                    at = text.find(marker, body_start)
                    stop = at + len(marker) if at >= 0 else None
                if stop is not None:
                    _blank(chars, i, stop)
                    i = stop
                    continue
        # Consume control words/symbols together, respecting backslash parity:
        # \% is data, while \\% is a line break followed by a comment.
        i = end
    return "".join(chars)


def line_number(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def balanced_close(text: str, open_pos: int) -> int | None:
    depth = 0
    for i in range(open_pos, len(text)):
        if text[i] == "{" and (i == 0 or text[i - 1] != "\\"):
            depth += 1
        elif text[i] == "}" and (i == 0 or text[i - 1] != "\\"):
            depth -= 1
            if depth == 0:
                return i
    return None


def mask_text_macros(math: str) -> str:
    """Blank prose and reference-key arguments inside math — words in either
    are not rendered commands."""
    chars = list(math)
    names = "|".join(re.escape(n)
                     for n in TEXT_IN_MATH_MACROS + REF_ARG_MACROS)
    pat = re.compile(r"\\(?:" + names + r")\*?\s*\{")
    pos = 0
    while True:
        match = pat.search(math, pos)
        if not match:
            break
        open_pos = match.end() - 1
        close_pos = balanced_close(math, open_pos)
        if close_pos is None:
            break
        for i in range(open_pos + 1, close_pos):
            if chars[i] not in "\r\n":
                chars[i] = " "
        pos = close_pos + 1
    return "".join(chars)


def math_bodies(text: str):
    """Yield non-overlapping ``(start, body)`` math regions."""
    envs = "|".join(re.escape(e) for e in MATH_ENVS)
    patterns = [
        (re.compile(r"\\begin\{(" + envs + r")\}(.*?)\\end\{\1\}", re.S), 2),
        (re.compile(r"\\\[(.*?)\\\]", re.S), 1),
        (re.compile(r"\\\((.*?)\\\)", re.S), 1),
        (re.compile(r"\$\$(.*?)\$\$", re.S), 1),
        (re.compile(r"(?<![\\$])\$(?!\$)(.*?)(?<!\\)\$(?!\$)", re.S), 1),
    ]
    candidates = []
    for pattern, group in patterns:
        for match in pattern.finditer(text):
            candidates.append((match.start(group), match.end(group), match.group(group)))
    candidates.sort(key=lambda item: (item[0], -(item[1] - item[0])))
    accepted = []
    for start, end, body in candidates:
        if any(start >= a and end <= b for a, b, _ in accepted):
            continue
        accepted.append((start, end, body))
    yield from sorted(accepted)


def bare_command_findings(path: Path, text: str) -> list[Finding]:
    findings = []
    word_pat = re.compile(r"\b(?:" + "|".join(BARE_WORDS) + r")\b")
    for start, _end, body in math_bodies(text):
        masked = mask_text_macros(body)
        for match in word_pat.finditer(masked):
            slashes = 0
            j = match.start() - 1
            while j >= 0 and masked[j] == "\\":
                slashes += 1
                j -= 1
            # An odd run leaves an effective command backslash.  An even run
            # (including zero) leaves a visible word after TeX consumes \\.
            if slashes % 2 == 1:
                continue
            absolute = start + match.start()
            word = match.group(0)
            findings.append(Finding(
                path, line_number(text, absolute), "BARE-LATEX-COMMAND",
                f"'{word}' appears as text inside math; did you mean \\{word}?",
            ))
    return findings


# v4.26.0 — BLD-70: COMPILE-TIME CONTOURS. pgfplots' `contour lua` and
# `contour gnuplot` are both styles over `contour external`: at the end of the
# plot it writes <job>_contourtmp<N>.dat and a script into the OUTPUT
# directory, runs the script, and reads back <job>_contourtmp<N>.table.
#   * lua: \directlua{require("<job>_contourtmp0")}. require() searches kpse
#     (the working directory and TEXMF), never -output-directory, so on a clean
#     tree the gated compile dies with "module ... not found" (and until
#     v4.26.0 was reported as a font problem, BLD-69). Worse, a module left in
#     the SOURCE directory by an earlier plain compile IS found, and it opens
#     the .dat there by a relative path: measured, after changing x^2+y^2 at
#     levels {1,2} to x^2+4*y^2 at {3}, the table the compile wrote was
#     byte-identical (MD5) to the old one and lualatex exited 0 — the old
#     circles on the page where the source asks for an ellipse. Through the
#     gate only a U+0060 that pgfplots leaks into nullfont stopped it.
#   * gnuplot / external: the script runs through shell escape, which the gate
#     disables. On a clean tree the table is missing (loud); with a table left
#     by an earlier shell-escape run the gate printed "✓ clean build" and
#     published that table's contour instead of the document's (measured).
# No gate after the compile can tell a stale contour from a correct one, so the
# rule is lexical and hard: the key itself, used where pgfkeys reads it.
# `contour prepared` (precomputed data) and `contour filled` (drawn by TeX) are
# not in the family and stay silent; a key PATH such as `contour lua/.style`
# (a redefinition) is not a use.
CONTOUR_EXTERNAL = re.compile(
    r"(?<![A-Za-z@\\])contour\s+(lua|gnuplot|external)(?![A-Za-z@/])\s*(?=[=,\]}])")
# Where pgfkeys reads plot keys: the options of \addplot / \addplot3 (with or
# without +), of an axis-like environment, \nextgroupplot and tikzpicture/scope,
# and the argument of pgfplotsset/tikzset/pgfkeys/pgfqkeys. Prose that merely
# NAMES the key (\code{contour lua}) is outside every one of them.
_KEY_BRACKETS = re.compile(
    r"\\(?:addplot3?\s*\+?|nextgroupplot"
    r"|begin\s*\{(?:[A-Za-z]*axis|groupplot|smithchart|tikzpicture|scope)\})\s*\[")
_KEY_BRACES = re.compile(r"\\(?:pgfplotsset|tikzset|pgfkeys)\s*\{|\\pgfqkeys\s*\{[^{}]*\}\s*\{")


def pgfkeys_spans(text: str):
    """Yield (start, end) of every pgfkeys option list or key argument.

    ``end`` is just past the closing delimiter, so a key written last in the
    list (``[contour lua]``) still sees its terminator.
    """
    for match in _KEY_BRACKETS.finditer(text):
        end = _option_end(text, match.end() - 1)
        if end is not None:
            yield match.end(), end
    for match in _KEY_BRACES.finditer(text):
        close = balanced_close(text, match.end() - 1)
        if close is not None:
            yield match.end(), close + 1


def contour_external_findings(path: Path, text: str) -> list[Finding]:
    """``text`` is masked for comments and literals but NOT for tikzpicture."""
    uses = {}
    for start, end in pgfkeys_spans(text):
        for match in CONTOUR_EXTERNAL.finditer(text, start, end):
            uses[match.start()] = match.group(1)
    findings = []
    for pos in sorted(uses):
        key = "contour " + uses[pos]
        findings.append(Finding(
            path, line_number(text, pos), "PGFPLOTS-CONTOUR-EXTERNAL",
            f"pgfplots '{key}' computes the contours at compile time with a "
            "generated script that the build gate cannot run (require() does "
            "not search the output directory; shell escape is off), and a "
            "result left in the source directory by an earlier compile is "
            "read instead, silently. Precompute the coordinates (e.g. with "
            "contourpy) and draw them with \\addplot coordinates/table or "
            "'contour prepared'.",
        ))
    return findings


def command_bodies(text: str) -> dict[str, str]:
    """Return simple new/renew/providecommand bodies keyed by macro name."""
    result = {}
    pat = re.compile(
        r"\\(?:newcommand|renewcommand|providecommand)\*?\s*"
        r"(?:\{\\([A-Za-z@]+)\}|\\([A-Za-z@]+))\s*"
        r"(?:\[[^\]]*\]\s*)?(?:\[[^\]]*\]\s*)?\{")
    for match in pat.finditer(text):
        name = match.group(1) or match.group(2)
        open_pos = match.end() - 1
        close_pos = balanced_close(text, open_pos)
        if close_pos is not None:
            result[name] = text[open_pos + 1:close_pos]
    return result


def multicol_regions(text: str):
    token_pat = re.compile(r"\\(begin|end)\{multicols\*?\}")
    stack = []
    for match in token_pat.finditer(text):
        if match.group(1) == "begin":
            stack.append(match)
        elif stack:
            begin = stack.pop()
            if not stack:
                yield begin.start(), match.end()


def needspace_findings(path: Path, text: str,
                       hazardous_macros: set[str]) -> list[Finding]:
    findings = []
    direct_pat = re.compile(r"\\(?:Needspace|needspace)\b")
    for start, end in multicol_regions(text):
        region = text[start:end]
        for match in direct_pat.finditer(region):
            absolute = start + match.start()
            findings.append(Finding(
                path, line_number(text, absolute), "NEEDSPACE-IN-MULTICOLS",
                "\\Needspace inside multicols can force a sparse RTL page; "
                "prefer a local \\nopagebreak[4] or verify the rendered flow.",
                warning=True,
            ))
        for name in sorted(hazardous_macros):
            invoke = re.compile(r"\\" + re.escape(name) + r"(?![A-Za-z@])")
            for match in invoke.finditer(region):
                absolute = start + match.start()
                findings.append(Finding(
                    path, line_number(text, absolute),
                    "NEEDSPACE-IN-MULTICOLS",
                    f"\\{name} expands to \\Needspace inside multicols; "
                    "prefer a heading macro based on \\nopagebreak[4] and "
                    "verify column flow.", warning=True,
                ))
    return findings


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--strict-layout", action="store_true",
        help="treat advisory layout warnings as findings (useful in tests/CI)")
    parser.add_argument("paths", nargs="+", help="UTF-8 TeX source files")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    sources = []
    raw_sources = {}
    read_errors = 0
    for raw_path in args.paths:
        path = Path(raw_path)
        try:
            raw = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            print(f"ERROR: cannot read {path}: {exc}")
            read_errors += 1
            continue
        clean = mask_source(raw)
        sources.append((path, clean))
        raw_sources[path] = raw
    if read_errors:
        return 2

    hazardous_macros = set()
    for _path, text in sources:
        for name, body in command_bodies(text).items():
            if re.search(r"\\(?:Needspace|needspace)\b", body):
                hazardous_macros.add(name)

    hard = []
    warnings = []
    for path, text in sources:
        hard.extend(bare_command_findings(path, text))
        # Plots live inside tikzpicture, which the view above blanks as engine
        # syntax; this rule needs a view that masks only comments and literals.
        hard.extend(contour_external_findings(
            path, mask_source(raw_sources[path], envs=LITERAL_ENVS)))
        hard.extend(Finding(path, line, flag, message)
                    for line, flag, message in split_math_findings(raw_sources[path]))
        hard.extend(Finding(path, line, flag, message)
                    for line, flag, message in linebreak_findings(raw_sources[path]))
        warnings.extend(needspace_findings(path, text, hazardous_macros))

    for finding in hard + warnings:
        level = "WARN" if finding.warning else "ERROR"
        print(f"{finding.path}:{finding.line}: [{finding.flag}] {level}: "
              f"{finding.message}")

    if hard:
        print(f"✗ source hazard gate: {len(hard)} hard finding(s), "
              f"{len(warnings)} layout warning(s).")
        return 1
    if warnings:
        print(f"⚠ source hazard gate: {len(warnings)} advisory layout warning(s); "
              "render every page and inspect column flow.")
        return 1 if args.strict_layout else 0
    print("✓ source hazard gate clean: no bare command words, split heading math, "
          "PDF-string line-break arguments, compile-time pgfplots contours, "
          "or Needspace-in-multicols expansion.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
