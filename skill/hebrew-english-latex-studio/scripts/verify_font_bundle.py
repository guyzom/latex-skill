#!/usr/bin/env python3
"""Verify hashes, font identity, styles, and required glyph coverage."""

from __future__ import annotations

import sys as _bytecode_sys
_bytecode_sys.dont_write_bytecode = True

import hashlib
from pathlib import Path
import sys

from font_paths import MANIFEST_DIR

from font_policy import (
    HEBREW_ALLOWED,
    LATIN_PRECOMPOSED_ALLOWED,
    TYPOGRAPHIC_ALLOWED,
)

try:
    from fontTools.ttLib import TTFont
except ImportError:
    print("fontTools is required: python3 -m pip install fonttools", file=sys.stderr)
    raise SystemExit(2)


EXPECTED = {
    "FrankRuhlLibre-Regular.ttf": ("Frank Ruhl Libre", "Regular", True),
    "FrankRuhlLibre-Medium.ttf": ("Frank Ruhl Libre Medium", "Regular", True),
    "FrankRuhlLibre-Bold.ttf": ("Frank Ruhl Libre", "Bold", True),
    "Heebo-Regular.ttf": ("Heebo", "Regular", True),
    "Heebo-Bold.ttf": ("Heebo", "Bold", True),
    "DejaVuSerif.ttf": ("DejaVu Serif", "Book", False),
    "DejaVuSerif-Bold.ttf": ("DejaVu Serif", "Bold", False),
    "DejaVuSans.ttf": ("DejaVu Sans", "Book", False),
    "DejaVuSans-Bold.ttf": ("DejaVu Sans", "Bold", False),
    "DejaVuSansMono.ttf": ("DejaVu Sans Mono", "Book", False),
}
LATIN_PROBE = set(map(ord, "Data123-()"))


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: verify_font_bundle.py FONT_DIR", file=sys.stderr)
        return 2
    root = Path(argv[1]).resolve()
    manifest = root / "SHA256SUMS"
    if not manifest.is_file():
        print(f"missing font manifest: {manifest}", file=sys.stderr)
        return 1

    def parse_manifest(path: Path) -> dict[str, str]:
        import re
        result: dict[str, str] = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            match = re.fullmatch(r"([0-9a-f]{64})  ([A-Za-z0-9_.-]+)", line)
            if match is None or match.group(2) in result:
                raise ValueError(f"malformed or duplicate manifest entry: {line!r}")
            result[match.group(2)] = match.group(1)
        return result

    try:
        hashes = parse_manifest(MANIFEST_DIR / "SHA256SUMS")
        declared = parse_manifest(manifest)
        if declared != hashes:
            raise ValueError("external manifest differs from canonical release pins")
    except (OSError, ValueError) as exc:
        print(f"✗ font manifest invalid: {exc}")
        return 1
    failures = []
    cmaps = {}
    for name, (family, style, _needs_hebrew) in EXPECTED.items():
        path = root / name
        if not path.is_file():
            failures.append(f"{name}: missing")
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if hashes.get(name) != digest:
            failures.append(f"{name}: SHA-256 mismatch")
            continue
        try:
            font = TTFont(path)
            actual_family = font["name"].getDebugName(1)
            actual_style = font["name"].getDebugName(2)
            cmap = set(font.getBestCmap())
            cmaps[name] = cmap
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{name}: unreadable font ({exc})")
            continue
        if actual_family != family or actual_style != style:
            failures.append(
                f"{name}: identity {actual_family!r}/{actual_style!r}, "
                f"expected {family!r}/{style!r}"
            )
        missing = LATIN_PROBE - cmap
        if missing:
            failures.append(
                f"{name}: missing " + ", ".join(
                    f"U+{cp:04X}" for cp in sorted(missing)
                )
            )
    required_text = (
        set(HEBREW_ALLOWED) | set(LATIN_PRECOMPOSED_ALLOWED)
        | set(TYPOGRAPHIC_ALLOWED) | LATIN_PROBE
    )
    stacks = {
        "rm regular": ("FrankRuhlLibre-Regular.ttf", "DejaVuSerif.ttf"),
        "rm bold": ("FrankRuhlLibre-Bold.ttf", "DejaVuSerif-Bold.ttf"),
        "rm italic": ("FrankRuhlLibre-Regular.ttf", "DejaVuSerif.ttf"),
        "rm bold italic": ("FrankRuhlLibre-Bold.ttf", "DejaVuSerif-Bold.ttf"),
        "sf regular": ("Heebo-Regular.ttf", "DejaVuSans.ttf"),
        "sf bold": ("Heebo-Bold.ttf", "DejaVuSans-Bold.ttf"),
    }
    for label, names in stacks.items():
        coverage = set().union(*(cmaps.get(name, set()) for name in names))
        missing = required_text - coverage
        if missing:
            failures.append(
                f"{label} stack missing " + ", ".join(
                    f"U+{cp:04X}" for cp in sorted(missing)
                )
            )
    for license_name in (
        "FrankRuhlLibre-OFL.txt", "Heebo-OFL.txt", "DejaVu-LICENSE.txt"
    ):
        path = root / license_name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != hashes.get(license_name):
            failures.append(f"{license_name}: missing or SHA-256 mismatch")
    if failures:
        for failure in failures:
            print(f"✗ {failure}")
        return 1
    print(f"✓ verified {len(EXPECTED)} pinned font faces and 3 licenses")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
