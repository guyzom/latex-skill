#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Original project code; scope and terms: ../LICENSING.md.
"""Verify source-resolution fixtures against LuaLaTeX's recorder and PDF bytes.

Each successful fixture builds in two separate clean directories, with three
passes per directory. Expected authored inputs must match both the resolver and
the actual .fls file, and the final PDFs must have identical SHA-256 hashes.
Missing-input fixtures must fail both resolution and compilation. All source
files, decoys and symlinks belong to isolated temporary directories.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
import resolve_tex_sources


@dataclass(frozen=True)
class Case:
    name: str
    main: str
    files: dict[str, str]
    expected: frozenset[str]
    links: dict[str, str] = field(default_factory=dict)
    missing: str | None = None


def document(body: str, packages: str = "") -> str:
    return (r"\pdfvariable suppressoptionalinfo 512\relax\documentclass{article}"
            + (r"\usepackage{" + packages + "}" if packages else "")
            + r"\begin{document}" + body + r"\end{document}")


def subdocument(body: str, main: str = "../main.tex") -> str:
    return r"\documentclass[" + main + r"]{subfiles}\begin{document}" + body + r"\end{document}"


def fixtures() -> list[Case]:
    cases = []
    for command in ("import", "inputfrom", "includefrom"):
        cases.append(Case("nested_main_" + command, "document/main.tex", {
            "document/main.tex": document(fr"\{command}{{parts/}}{{a}}", "import"),
            "document/parts/a.tex": r"\input{fallback}",
            "document/fallback.tex": "Expected compilation-directory fallback.",
            "parts/a.tex": "Incorrect trust-root import.",
            "fallback.tex": "Incorrect trust-root fallback.",
        }, frozenset({"document/main.tex", "document/parts/a.tex", "document/fallback.tex"})))
    cases.append(Case("nested_top_level_import_fallback", "document/main.tex", {
        "document/main.tex": document(r"\import{outer/}{a}", "import"),
        "document/outer/a.tex": r"\import{child/}{b}",
        "document/child/b.tex": r"\input{shared}",
        "document/outer/shared.tex": "Expected previous import-directory fallback.",
    }, frozenset({"document/main.tex", "document/outer/a.tex", "document/child/b.tex",
                  "document/outer/shared.tex"})))
    cases.append(Case("unused_escaping_fallback", "main.tex", {
        "main.tex": document(r"\import{parts/}{a}", "import"),
        "parts/a.tex": r"\input{../shared}",
        "shared.tex": "Expected project-local relative input.",
    }, frozenset({"main.tex", "parts/a.tex", "shared.tex"})))
    for command in ("input", "include", "subfile"):
        cases.append(Case("dotted_" + command + "_preference", "main.tex", {
            "main.tex": document(fr"\{command}{{chapter.v1}}", "subfiles"),
            "chapter.v1": "Incorrect exact fallback.",
            "chapter.v1.tex": r"\input{leaf}",
            "leaf.tex": "Expected appended-name source and child.",
        }, frozenset({"main.tex", "chapter.v1.tex", "leaf.tex"})))
    for command in ("input", "include"):
        selected = "chapter.sty" if command == "input" else "chapter.sty.tex"
        cases.append(Case("known_extension_" + command, "main.tex", {
            "main.tex": document(fr"\{command}{{chapter.sty}}"),
            "chapter.sty": "Exact known suffix source.",
            "chapter.sty.tex": "Appended include source.",
        }, frozenset({"main.tex", selected})))
    for filename in ("chapter.v2", "chapter"):
        cases.append(Case("exact_fallback_" + filename.replace(".", "_"), "main.tex", {
            "main.tex": document(r"\input{" + filename + "}"),
            filename: "Expected exact-name fallback when appended source is absent.",
        }, frozenset({"main.tex", filename})))
    for command in ("subfile", "subfileinclude"):
        cases.append(Case("nested_main_" + command, "document/main.tex", {
            "document/main.tex": document(fr"\{command}{{parts/child}}", "subfiles"),
            "document/parts/child.tex": subdocument(r"\input{leaf}"),
            "document/parts/leaf.tex": "Expected child-relative input.",
            "document/leaf.tex": "Incorrect compilation-directory input.",
            "parts/child.tex": "Incorrect trust-root subfile.",
            "leaf.tex": "Incorrect trust-root leaf.",
        }, frozenset({"document/main.tex", "document/parts/child.tex", "document/parts/leaf.tex"})))
        cases.append(Case("nested_" + command, "main.tex", {
            # LaTeX forbids include inside include; a subfile can contain either
            # command and preserves the nested source-directory semantics.
            "main.tex": document(r"\subfile{parts/child}", "subfiles"),
            "parts/child.tex": subdocument(fr"\{command}{{deep/grandchild}}"),
            "parts/deep/grandchild.tex": subdocument(r"\input{leaf}", "../../main.tex"),
            "parts/deep/leaf.tex": "Expected grandchild-relative input.",
            "deep/grandchild.tex": "Incorrect compilation-directory subfile.",
            "parts/leaf.tex": "Incorrect parent input.",
            "leaf.tex": "Incorrect compilation-directory input.",
        }, frozenset({"main.tex", "parts/child.tex", "parts/deep/grandchild.tex", "parts/deep/leaf.tex"})))
    cases.append(Case("subfile_under_active_import", "main.tex", {
        "main.tex": document(r"\import{outer/}{parent}", "subfiles"),
        "outer/parent.tex": r"\input{nested/caller}",
        "outer/nested/caller.tex": r"\subfile{sub/child}",
        "outer/sub/child.tex": subdocument(r"\input{leaf}", "../../main.tex"),
        "outer/sub/leaf.tex": "Expected active-import subfile directory.",
        "outer/nested/sub/child.tex": "Incorrect callsite directory.",
        "sub/child.tex": "Incorrect compilation-directory subfile.",
    }, frozenset({"main.tex", "outer/parent.tex", "outer/nested/caller.tex",
                  "outer/sub/child.tex", "outer/sub/leaf.tex"})))
    for fallback in ("parent", "cwd"):
        files = {
            "document/main.tex": document(r"\subfile{parts/child}", "subfiles"),
            "document/parts/child.tex": subdocument(r"\subfile{deep/grandchild}"),
            "document/parts/deep/grandchild.tex": subdocument(r"\input{leaf}", "../../main.tex"),
            "document/leaf.tex": "Expected compilation-directory fallback.",
            "leaf.tex": "Incorrect trust-root fallback.",
        }
        selected = "document/leaf.tex"
        if fallback == "parent":
            selected = "document/parts/leaf.tex"
            files[selected] = "Expected prior subfile-directory fallback."
        cases.append(Case("subfile_" + fallback + "_fallback", "document/main.tex", files,
                          frozenset({"document/main.tex", "document/parts/child.tex",
                                     "document/parts/deep/grandchild.tex", selected})))
    cases.append(Case("subfile_literal_listing", "main.tex", {
        "main.tex": document(r"\subfile{parts/child}", "subfiles,listings"),
        "parts/child.tex": subdocument(r"\lstinputlisting{code.py}"),
        "parts/code.py": "print('Expected subfile-directory listing')\n",
        "code.py": "print('Incorrect compilation-directory listing')\n",
    }, frozenset({"main.tex", "parts/child.tex", "parts/code.py"})))
    cases.append(Case("subfile_symlink_literal_directory", "main.tex", {
        "main.tex": document(r"\subfile{parts/child}", "subfiles"),
        "elsewhere/actual.tex": subdocument(r"\input{leaf}"),
        "parts/leaf.tex": "Expected literal subfile directory.",
        "elsewhere/leaf.tex": "Incorrect symlink-target directory.",
        "leaf.tex": "Incorrect compilation-directory input.",
    }, frozenset({"main.tex", "elsewhere/actual.tex", "parts/leaf.tex"}),
       links={"parts/child.tex": "elsewhere/actual.tex"}))
    cases.append(Case("subfileinclude_known_suffix", "main.tex", {
        "main.tex": document(r"\subfileinclude{parts/child.sty}", "subfiles"),
        "parts/child.sty": "Incorrect exact-suffix file.",
        "parts/child.sty.tex": subdocument("Expected include .tex suffix."),
    }, frozenset({"main.tex", "parts/child.sty.tex"})))
    cases.append(Case("subfile_missing_target_with_cwd_decoy", "main.tex", {
        "main.tex": document(r"\import{outer/}{parent}", "subfiles"),
        "outer/parent.tex": r"\subfile{missing}",
        "missing.tex": subdocument("Incorrect compilation-directory subfile."),
    }, frozenset({"main.tex", "outer/parent.tex"}), missing="outer/missing.tex"))
    cases.append(Case("subfile_missing_leaf_with_trust_root_decoy", "document/main.tex", {
        "document/main.tex": document(r"\subfile{parts/child}", "subfiles"),
        "document/parts/child.tex": subdocument(r"\input{missing}"),
        "missing.tex": "Incorrect trust-root input.",
    }, frozenset({"document/main.tex", "document/parts/child.tex"}), missing="document/parts/missing.tex"))
    return cases


class SourceGraphRuntimeTests(unittest.TestCase):
    def check_case(self, case: Case) -> None:
        hashes = []
        for repeat in range(2):
            with self.subTest(clean_build=repeat + 1), tempfile.TemporaryDirectory(prefix="tex-source-graph-") as temp:
                root = Path(temp).resolve()
                for relative, content in case.files.items():
                    path = root / relative
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(content, encoding="utf-8")
                for relative, target in case.links.items():
                    path = root / relative
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.symlink_to(root / target)
                main = root / case.main
                cache = root / "font-cache"
                cache.mkdir()
                env = dict(os.environ, SOURCE_DATE_EPOCH="1700000000", TZ="UTC",
                           TEXMFCACHE=str(cache), TEXMFVAR=str(cache))
                for _ in range(1 if case.missing else 3):
                    run = subprocess.run(["lualatex", "--no-shell-escape", "-interaction=nonstopmode",
                                          "-halt-on-error", "-recorder", main.name], cwd=main.parent,
                                         env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                         stdin=subprocess.DEVNULL, text=True, timeout=60)
                    if case.missing:
                        self.assertNotEqual(run.returncode, 0, "Missing input unexpectedly compiled")
                    else:
                        self.assertEqual(run.returncode, 0, run.stdout[-4000:])
                recorded = set()
                for line in main.with_suffix(".fls").read_text(encoding="utf-8").splitlines():
                    if not line.startswith("INPUT "):
                        continue
                    path = Path(line[6:])
                    path = (main.parent / path).resolve() if not path.is_absolute() else path.resolve()
                    try:
                        relative = path.relative_to(root).as_posix()
                    except ValueError:
                        continue
                    if relative in case.files:
                        recorded.add(relative)
                self.assertEqual(recorded, case.expected, "Unexpected authored files in LuaLaTeX recorder")
                dependencies, errors = resolve_tex_sources.resolve(main, root)
                resolved = {dependency.path.relative_to(root).as_posix() for dependency in dependencies}
                self.assertEqual(resolved, case.expected, "Resolver differs from actual authored inputs")
                if case.missing:
                    self.assertEqual(errors, [f"missing tex source: {root / case.missing}"])
                else:
                    self.assertFalse(errors)
                    hashes.append(hashlib.sha256(main.with_suffix(".pdf").read_bytes()).hexdigest())
        if not case.missing and len(hashes) == 2:
            self.assertEqual(hashes[0], hashes[1], "PDF bytes differ between clean builds")


CASES = fixtures()
for _case in CASES:
    def _test(self, case=_case):
        self.check_case(case)
    setattr(SourceGraphRuntimeTests, "test_" + _case.name, _test)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    for command in ("lualatex", "kpsewhich"):
        if shutil.which(command) is None:
            parser.error(f"required command is missing: {command}")
    for package in ("article.cls", "import.sty", "subfiles.sty", "listings.sty"):
        run = subprocess.run(["kpsewhich", package], capture_output=True, text=True, timeout=10)
        if run.returncode or not run.stdout.strip():
            parser.error(f"required TeX file is missing: {package}")
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(SourceGraphRuntimeTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
