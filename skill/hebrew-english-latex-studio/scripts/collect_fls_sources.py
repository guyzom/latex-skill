#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Original project code; scope and terms: ../LICENSING.md.
"""List project-local textual inputs recorded by a TeX .fls file."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


TEXT_SUFFIXES = {
    ".tex", ".ltx", ".sty", ".cls", ".bib", ".csv", ".tsv", ".txt",
    ".py", ".c", ".cc", ".cpp", ".h", ".hpp", ".java", ".js", ".ts",
    ".sh", ".asm", ".s", ".v", ".sv", ".html", ".css", ".json", ".yaml",
    ".yml", ".xml", ".md",
}
TEX_SUFFIXES = {".tex", ".ltx", ".sty", ".cls"}

# v4.0.1: DENY BY DEFAULT, with one narrow exemption. Anything the engine reads
# from outside the project is untrusted — including a suffix-less file such as
# /etc/passwd, which the adversarial guard tests pin — EXCEPT pure glyph/metric
# data. LuaTeX reads .otf/.ttf/.pfb/.tfm as font data, never as code.
#
# Measured defect this fixes: the escape check ran before the suffix filter the rest
# of this function respects, so on a COLD luaotfload cache — where the engine scans
# and therefore RECORDS every font file instead of reading its .luc cache — the gate
# reported /usr/share/texmf/.../lmroman12-regular.otf and ~/.fonts/*.ttf as
# "untrusted external TeX input" and failed the build. Warm cache: those files are
# never touched and the gate passes. A gate whose verdict depends on cache state is
# not a gate, and it failed precisely on a fresh machine — CI, or a new developer.
# Reproduced locally by moving the cache aside; the same build then failed here too.
#
# A first attempt inverted this into an allow-list of source suffixes and was wrong:
# /etc/passwd has no suffix, so it stopped being flagged and test_build_guards went
# red. That test earned its keep.
FONT_DATA_SUFFIXES = {
    ".otf", ".ttf", ".ttc", ".otc", ".pfb", ".pfa", ".afm", ".tfm", ".vf",
    ".enc", ".map", ".luc", ".otl", ".pk",
}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("fls", type=Path)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument(
        "--allow-root", action="append", default=[], type=Path,
        help="trusted external input root (repeatable)",
    )
    parser.add_argument("--mode", choices=("all", "tex", "project-all"), default="all")
    parser.add_argument(
        "--forbid-input", action="append", default=[], type=Path,
        help="input path that must never be consumed (repeatable)",
    )
    parser.add_argument(
        "--generated-tex-input", action="append", default=[], type=Path,
        help="this build's exact managed .ind input to scan as TeX (repeatable)",
    )
    args = parser.parse_args(argv[1:])
    if not args.fls.is_file():
        print(f"missing recorder file: {args.fls}", file=sys.stderr)
        return 2

    root = args.project_root.resolve()
    allowed_roots = [path.resolve() for path in args.allow_root]
    forbidden_inputs = {path.resolve() for path in args.forbid_input}
    generated_inputs = {path.resolve() for path in args.generated_tex_input}
    if any(path.suffix != ".ind" or not any(_is_relative_to(path, allowed_root)
                                           for allowed_root in allowed_roots)
           for path in generated_inputs):
        print("generated TeX input must be an exact .ind inside an allowed build root", file=sys.stderr)
        return 2
    seen: set[Path] = set()
    unsafe: set[Path] = set()
    fls_lines = args.fls.read_text(encoding="utf-8", errors="replace").splitlines()
    # v4.0.1: relative INPUT paths in a .fls are relative to the COMPILATION
    # directory, which the recorder itself states on its PWD line — not to
    # project_root. Resolving them against project_root silently produced paths
    # one directory too high and reported files that DO exist inside the project as
    # "untrusted external TeX input": measured on this skill's own fixtures, where
    # `\input{../assets/preamble.tex}` compiled from tests/ was reported as
    # <skill>/../assets/preamble.tex. The two bases coincide whenever the build runs
    # from the project root, which is why every collection passed and the bug stayed
    # invisible.
    fls_pwd = next((Path(l[4:]) for l in fls_lines if l.startswith("PWD ")), None)
    input_base = fls_pwd if fls_pwd and fls_pwd.is_dir() else root
    for line in fls_lines:
        if not line.startswith("INPUT "):
            continue
        path = Path(line[6:])
        if not path.is_absolute():
            path = (input_base / path).resolve()
        else:
            path = path.resolve()
        if path in forbidden_inputs:
            unsafe.add(path)
            continue
        if path in generated_inputs:
            if path.is_file() and path not in seen and args.mode != "project-all":
                seen.add(path)
                print(path)
            continue
        try:
            path.relative_to(root)
        except ValueError:
            if (path.suffix.lower() not in FONT_DATA_SUFFIXES
                    and not any(
                        _is_relative_to(path, allowed_root)
                        for allowed_root in allowed_roots
                    )):
                unsafe.add(path)
            continue
        if not path.is_file() or path in seen:
            continue
        if args.mode == "project-all":
            seen.add(path)
            print(path)
            continue
        suffixes = TEX_SUFFIXES if args.mode == "tex" else TEXT_SUFFIXES
        if path.suffix.lower() not in suffixes:
            continue
        seen.add(path)
        print(path)
    if unsafe:
        for path in sorted(unsafe):
            if path in forbidden_inputs:
                print(f"forbidden prior-build input: {path}", file=sys.stderr)
            else:
                print(f"untrusted external TeX input: {path}", file=sys.stderr)
        return 1
    return 0


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
