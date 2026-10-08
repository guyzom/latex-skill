#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Original project code; scope and terms: ../LICENSING.md.
# Additional output permission: ../LICENSES/Generated-Output-Permission.txt.
"""Render/check runtime architecture guards from the canonical schema.

The TeX layer bodies own document behavior. Dependency/conflict/duplicate-load
checks do not: those are derived mechanically from ``architecture_contract.py``
so the runtime graph cannot become a second hand-maintained architecture.
"""
from __future__ import annotations

from pathlib import Path
import argparse
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from architecture_contract import ASSET_SPECS, claimed_loaded_sentinels, runtime_guard_rules  # noqa: E402

START = "% <hllpdf:architecture-guard>\n"
END = "% </hllpdf:architecture-guard>"
READY_START = "% <hllpdf:architecture-ready>\n"
READY_END = "% </hllpdf:architecture-ready>"


def _err(asset: str, message: str) -> list[str]:
    return [
        rf"  \errmessage{{hllpdf: {asset} {message}}}",
        r"  \expandafter\endinput",
    ]


def render_guard(spec) -> str:
    """Return the exact guard region for one declared architecture asset."""
    lines: list[str] = []
    for rule in runtime_guard_rules(spec):
        if rule.expect_defined:
            lines.append(rf"\ifdefined\{rule.sentinel}")
        else:
            lines.append(rf"\ifdefined\{rule.sentinel}\else")
        lines.extend([
            rf"  \errmessage{{{rule.diagnostic}}}",
            r"  \expandafter\endinput",
            r"\fi",
        ])

    # Core readiness is deliberately delayed until the end of preamble.tex.
    if spec.runtime_requires or spec.generated_from:
        for sentinel in claimed_loaded_sentinels(spec):
            lines.append(rf"\def\{sentinel}{{1}}")

    return START + "\n".join(lines) + "\n" + END


def render_ready(spec) -> str:
    """Return the delayed readiness marker for the mechanism core."""
    if spec.runtime_requires or spec.generated_from:
        raise ValueError(f"{spec.path}: delayed ready marker is core-only")
    return READY_START + rf"\def\{spec.loaded_sentinel}{{1}}" + "\n" + READY_END


def _replace_region(text: str, start: str, end: str, replacement: str, *, label: str) -> str:
    if text.count(start) != 1 or text.count(end) != 1:
        raise ValueError(f"{label}: expected exactly one generated marker pair")
    before, rest = text.split(start, 1)
    _, after = rest.split(end, 1)
    return before + replacement + after


def expected_text(spec, current: str) -> str:
    text = _replace_region(current, START, END, render_guard(spec), label=spec.path)
    if not spec.runtime_requires and not spec.generated_from:
        text = _replace_region(text, READY_START, READY_END, render_ready(spec), label=spec.path)
    return text


def check_tree(root: Path = ROOT) -> tuple[str, ...]:
    errors: list[str] = []
    for spec in ASSET_SPECS:
        # Compatibility bundles are generated in full by render_compat_bundles.py;
        # that renderer consumes render_guard() directly, so it is checked there.
        if spec.generated_from:
            continue
        path = root / spec.path
        try:
            current = path.read_text(encoding="utf-8")
            expected = expected_text(spec, current)
        except (OSError, ValueError) as exc:
            errors.append(str(exc))
            continue
        if current != expected:
            errors.append(f"{spec.path}: runtime architecture guard drifted from schema")
    return tuple(errors)


def write_tree(root: Path = ROOT) -> None:
    for spec in ASSET_SPECS:
        if spec.generated_from:
            continue
        path = root / spec.path
        current = path.read_text(encoding="utf-8")
        path.write_text(expected_text(spec, current), encoding="utf-8")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true")
    group.add_argument("--write", action="store_true")
    args = p.parse_args()
    if args.write:
        write_tree()
        print("✓ wrote runtime architecture guards from canonical schema")
        return 0
    errors = check_tree()
    if errors:
        for error in errors:
            print(f"✗ {error}")
        return 1
    print("✓ runtime architecture guards match canonical schema")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
