#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Original project code; scope and terms: ../LICENSING.md.
"""Engine regressions for every declared runtime architecture guard rule."""
from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
sys.path.insert(0, str(ROOT / "scripts"))
from architecture_contract import ASSET_SPECS, runtime_guard_rules, simulate_runtime_load  # noqa: E402


def _state_for_rule(spec, index: int) -> set[str]:
    """Construct sentinel state that reaches and triggers exactly rule ``index``."""
    active: set[str] = set()
    rules = runtime_guard_rules(spec)
    for prior in rules[:index]:
        if prior.expect_defined:
            active.discard(prior.sentinel)
        else:
            active.add(prior.sentinel)
    target = rules[index]
    if target.expect_defined:
        active.add(target.sentinel)
    else:
        active.discard(target.sentinel)
    return active


def run_case(name: str, asset: str, active: set[str], expected: str) -> None:
    engine = shutil.which("lualatex")
    if engine is None:
        raise RuntimeError("lualatex not found")
    setup = "".join(rf"\def\{sentinel}{{1}}" + "\n" for sentinel in sorted(active))
    with tempfile.TemporaryDirectory(prefix="hllpdf_arch_") as td:
        work = Path(td)
        source = work / "case.tex"
        source.write_text(
            setup + rf"\input{{{(ASSETS / asset).as_posix()}}}" + "\n\\end\n",
            encoding="utf-8",
        )
        proc = subprocess.run(
            [engine, "-interaction=nonstopmode", "-halt-on-error", source.name],
            cwd=work,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=20,
        )
        if proc.returncode == 0:
            raise AssertionError(f"{name}: architecture violation compiled successfully")
        if expected not in proc.stdout:
            tail = "\n".join(proc.stdout.splitlines()[-30:])
            raise AssertionError(f"{name}: expected diagnostic {expected!r} not found\n{tail}")


def main() -> int:
    # Every declared guard must have an executable engine case. New flow,
    # semantic, shell and theme siblings receive the same treatment as existing
    # layers, including the reverse guards added to older conflicting carriers.
    rules_by_asset = {spec.path: runtime_guard_rules(spec) for spec in ASSET_SPECS}
    for name in ("columns", "shell", "components", "theme"):
        path = f"assets/reference_{name}.tex"
        rules = rules_by_asset.get(path)
        if not rules or not any(rule.kind == "requires" for rule in rules):
            raise AssertionError(f"{path}: reference extension lost its core prerequisite guard")
        if not any(rule.kind == "duplicate" for rule in rules):
            raise AssertionError(f"{path}: reference extension lost its single-load guard")
    theme_conflicts = {rule.target_path for rule in rules_by_asset["assets/reference_theme.tex"]
                      if rule.kind == "conflict"}
    if theme_conflicts != {"assets/reader_theme.tex", "assets/academic_theme.tex",
                           "assets/clean_theme.tex", "assets/clean_variant.tex"}:
        raise AssertionError(f"reference theme conflict coverage drifted: {theme_conflicts!r}")
    for target in theme_conflicts:
        if not any(rule.kind == "conflict" and rule.target_path == "assets/reference_theme.tex"
                   for rule in rules_by_asset[target]):
            raise AssertionError(f"{target}: missing reverse reference theme conflict guard")
    for first, second in (("reference_shell", "topicrail"), ("topicrail", "reference_shell")):
        if not any(rule.kind == "conflict" and rule.target_path == f"assets/{second}.tex"
                   for rule in rules_by_asset[f"assets/{first}.tex"]):
            raise AssertionError(f"{first}: missing mutually exclusive page-shell guard")
    count = 0
    for spec in ASSET_SPECS:
        for index, rule in enumerate(runtime_guard_rules(spec)):
            active = _state_for_rule(spec, index)
            # The pure-Python state machine and rendered TeX must agree on the
            # first diagnostic for this constructed architecture state.
            simulated, unchanged = simulate_runtime_load(spec.path, active)
            if simulated != rule.diagnostic or unchanged != frozenset(active):
                raise AssertionError(
                    f"{spec.path} rule {index}: simulator mismatch: {simulated!r}, {unchanged!r}"
                )
            run_case(
                f"{spec.basename}:{rule.kind}:{Path(rule.target_path).name}",
                spec.basename,
                active,
                rule.diagnostic,
            )
            count += 1
    print(f"✓ runtime architecture guards: {count}/{count} schema-derived rules fail with exact diagnostics")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
