#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Original project code; scope and terms: ../LICENSING.md.
"""Verify the validated QA baseline and, optionally, the LuaLaTeX toolchain.

The exact Python package versions are the release-validation baseline.  The
runtime build may work with other compatible versions, but a release claim must
be reproduced against this file's pins before being described as fully tested.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True
from font_paths import font_dir

ROOT = Path(__file__).resolve().parent.parent
FONTS = font_dir()
EXPECTED_QA = {
    "PyMuPDF": "1.26.7",
    "fonttools": "4.63.0",
}
REQUIRED_COMMANDS = ("lualatex", "kpsewhich", "pdfinfo", "pdftoppm")
REQUIRED_TEX_FILES = (
    # Luaotfload unconditionally loads these external Lua libraries during
    # startup; finding its entrypoint alone does not prove they are installed.
    "lualibs.lua", "lua-uni-case.lua", "lua-uni-normalize.lua", "lua-uni-parse.lua",
    "luaotfload-main.lua", "luatexbase.sty", "babel.sty", "babel-he.ini",
    "babel-en.ini", "lmroman10-regular.otf", "lmroman10-bold.otf",
    "lmroman10-italic.otf", "lmroman10-bolditalic.otf",
    "lmsans10-regular.otf", "lmsans10-bold.otf",
    "lmsans10-oblique.otf", "lmsans10-boldoblique.otf",
    "fontspec.sty", "amsmath.sty", "amssymb.sty", "mathtools.sty",
    "amsthm.sty", "etoolbox.sty", "geometry.sty", "xcolor.sty",
    "mdframed.sty", "listings.sty", "tikz.sty", "pgfplots.sty",
    "quantikz.sty", "ctablestack.sty", "booktabs.sty", "array.sty", "float.sty",
    "enumitem.sty", "needspace.sty", "hyperref.sty", "fancyhdr.sty",
    "graphicx.sty", "caption.sty", "longtable.sty", "collcell.sty", "multicol.sty",
    # Full studio validation includes the shipped reference starters and index
    # component. The build checks the optional makeindex command when selected.
    "colortbl.sty", "imakeidx.sty",
)


def _qa_versions() -> tuple[dict[str, str], list[str]]:
    versions: dict[str, str] = {}
    errors: list[str] = []
    try:
        import fitz
        versions["PyMuPDF"] = str(fitz.VersionBind)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"PyMuPDF unavailable: {exc}")
    try:
        import fontTools
        versions["fonttools"] = str(fontTools.__version__)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"fonttools unavailable: {exc}")
    return versions, errors


def _check_qa() -> list[str]:
    errors: list[str] = []
    if sys.version_info < (3, 10):
        errors.append(
            f"Python {sys.version_info.major}.{sys.version_info.minor} is too old; "
            "Python 3.10+ is required"
        )
    versions, import_errors = _qa_versions()
    errors.extend(import_errors)
    for package, expected in EXPECTED_QA.items():
        actual = versions.get(package)
        if actual is not None and actual != expected:
            errors.append(
                f"{package} {actual} installed; validated release baseline is {expected}"
            )
    return errors


def _kpsewhich(name: str) -> str:
    proc = subprocess.run(
        ["kpsewhich", name], text=True, capture_output=True, timeout=20
    )
    return proc.stdout.strip() if proc.returncode == 0 else ""


def _check_toolchain() -> list[str]:
    errors: list[str] = []
    for command in REQUIRED_COMMANDS:
        if shutil.which(command) is None:
            errors.append(f"required command not found: {command}")
    if shutil.which("kpsewhich") is not None:
        for tex_file in REQUIRED_TEX_FILES:
            if not _kpsewhich(tex_file):
                errors.append(f"TeX dependency not found: {tex_file}")
    # Reuse the package's own authoritative font-bundle verifier instead of
    # reimplementing font identity/hash/coverage here.
    verifier = ROOT / "scripts" / "verify_font_bundle.py"
    if verifier.is_file():
        proc = subprocess.run(
            [sys.executable, str(verifier), str(FONTS)],
            text=True,
            capture_output=True,
            timeout=60,
            env={**__import__("os").environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        if proc.returncode != 0:
            errors.append("pinned font bundle verification failed: " + (proc.stdout + proc.stderr).strip() + "\n  run scripts/setup_fonts.sh --from-skill PRIOR.skill, or set HEBREW_LATEX_FONT_DIR")
    else:
        errors.append("verify_font_bundle.py missing")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--qa-only", action="store_true",
        help="check only Python version and exact release-validation QA pins",
    )
    args = parser.parse_args(argv)
    errors = _check_qa()
    if not args.qa_only:
        errors.extend(_check_toolchain())
    if errors:
        for error in errors:
            print(f"✗ {error}")
        if any("validated release baseline" in e for e in errors):
            print("  install the pinned baseline with: python3 -m pip install -r requirements-qa.txt")
        return 2
    scope = "QA baseline" if args.qa_only else "QA baseline + LuaLaTeX toolchain"
    print(f"✓ doctor: {scope} verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
