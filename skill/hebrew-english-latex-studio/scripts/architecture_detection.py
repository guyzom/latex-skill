#!/usr/bin/env python3
"""Detect architecture capabilities activated by TeX source.

This is the bridge between the declarative architecture contract and source
checkers.  It deliberately detects *capabilities* (show-only-referenced
numbering, hidden section numbering, semantic exam API, ...), so callers do not
need to special-case clean_variant.tex or any future compatibility carrier.
"""
from __future__ import annotations

from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
from architecture_contract import (  # noqa: E402
    ASSET_SPECS,
    CAP_FLAT_TABLE_NUMBERING,
    CAP_HIDE_SECTION_NUMBERING,
    CAP_SHOWONLYREFS,
    capabilities_for_provider_name,
)


def strip_tex_comments(text: str) -> str:
    """Strip TeX comments while preserving escaped percent signs and newlines."""
    out: list[str] = []
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        cut = len(raw)
        for i, ch in enumerate(raw):
            if ch != "%":
                continue
            backslashes = 0
            j = i - 1
            while j >= 0 and raw[j] == "\\":
                backslashes += 1
                j -= 1
            if backslashes % 2 == 0:
                cut = i
                break
        out.append(raw[:cut])
    return "\n".join(out)


_INPUT_RE = re.compile(
    r"\\(?:input|include)\s*(?:\{\s*([^}\r\n]+?)\s*\}|([^\s%{}]+))",
    re.MULTILINE,
)


def provider_names_from_text(text: str) -> tuple[str, ...]:
    """Return exact shipped-provider basenames referenced by input/include.

    Matching the complete TeX argument avoids substring false positives such as
    ``\\input{myclean_theme.tex}`` accidentally activating ``clean_theme.tex``.
    Both braced and classic unbraced ``\\input foo.tex`` forms are supported.
    """
    out: list[str] = []
    known = {spec.basename for spec in ASSET_SPECS}
    known_stems = {
        spec.basename[:-4] if spec.basename.endswith(".tex") else spec.basename: spec.basename
        for spec in ASSET_SPECS
    }
    for match in _INPUT_RE.finditer(text):
        raw = (match.group(1) or match.group(2) or "").strip()
        if not raw:
            continue
        # Architecture assets use portable slash-separated paths. Only the final
        # basename matters to the package-level contract.
        base = raw.rsplit("/", 1)[-1]
        if base in known:
            out.append(base)
        elif base in known_stems:
            out.append(known_stems[base])
    return tuple(out)


def capabilities_from_text(text: str) -> frozenset[str]:
    """Capabilities explicitly activated/embedded in one TeX source string."""
    clean = strip_tex_comments(text)
    caps: set[str] = set()

    # Provider inputs: both pure layers and legacy generated carriers map to the
    # same capability vocabulary through architecture_contract.py.
    for provider in provider_names_from_text(clean):
        caps.update(capabilities_for_provider_name(provider))

    # Embedded/final assembled sources may contain layer bodies rather than an
    # \input token. Detect the semantic policy itself so checker behavior is
    # independent of assembly strategy.
    if re.search(r"\\mathtoolsset\s*\{[^}]*\bshowonlyrefs\s*=\s*true\b[^}]*\}", clean):
        caps.add(CAP_SHOWONLYREFS)
    if re.search(r"\\setcounter\s*\{secnumdepth\}\s*\{-\s*2\}", clean):
        caps.add(CAP_HIDE_SECTION_NUMBERING)
    if re.search(r"\\renewcommand\s*\{\\thetbl\}\s*\{\\arabic\s*\{tbl\}\}", clean):
        caps.add(CAP_FLAT_TABLE_NUMBERING)

    return frozenset(caps)


def capabilities_from_path(path: str | Path) -> frozenset[str]:
    p = Path(path)
    caps = set(capabilities_for_provider_name(p.name))
    try:
        caps.update(capabilities_from_text(p.read_text(encoding="utf-8")))
    except (OSError, UnicodeDecodeError):
        pass
    return frozenset(caps)


def capabilities_from_paths(paths: list[str] | tuple[str, ...]) -> frozenset[str]:
    caps: set[str] = set()
    for path in paths:
        caps.update(capabilities_from_path(path))
    return frozenset(caps)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: architecture_detection.py file.tex [file2.tex ...]", file=sys.stderr)
        raise SystemExit(2)
    for capability in sorted(capabilities_from_paths(sys.argv[1:])):
        print(capability)
