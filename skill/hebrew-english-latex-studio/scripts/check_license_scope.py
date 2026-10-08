#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Original project code; scope and terms: ../LICENSING.md.
"""Check declared licensing boundaries, without deciding legal independence."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent.parent
SPDX = "# SPDX-License-Identifier: AGPL-3.0-only"
LICENSE_HASHES = {
    "LICENSES/AGPL-3.0-only.txt": "0d96a4ff68ad6d4b6f1f30f713b18d5184912ba8dd389f86aa7710db079abcb0",
    "LICENSES/PyMuPDF-1.26.7-COPYING": "57c8ff33c9c0cfc3ef00e650a1cc910d7ee479a8bc509f6c9209a7c2a11399d6",
}
EXCLUDED_FILES = {
    "scripts/new_document.py", "scripts/template_registry.py",
    "scripts/generate_studio_docs.py",
}
EXCLUDED_DIRS = ["assets/", "registry/", "tests/"]
REQUIRED_FILES = {
    "LICENSING.md", "NOTICE.md", "LICENSE-SCOPE.json", "requirements-qa.txt",
    "scripts/build.sh", "scripts/test_all.sh", "scripts/check_license_scope.py",
    "scripts/test_license_scope.py", "scripts/package_skill.py",
}
REQUIRED_DOCS = {
    "LICENSING.md": ("unresolved_local_imports", "does not automatically license",
                     "Copied source retains its actual", "not legal certification"),
    "SKILL.md": ("LICENSING.md", "LICENSE-SCOPE.json", "NOTICE.md"),
    "references/studio-setup.md": ("LICENSING.md", "NOTICE.md"),
    "references/pdf-strings-and-renderers.md": ("LICENSING.md", "NOTICE.md"),
}


def import_graph(root: Path) -> tuple[dict[str, set[str]], set[str]]:
    modules = {p.stem: p.relative_to(root).as_posix()
               for p in (root / "scripts").glob("*.py")}
    graph: dict[str, set[str]] = {}
    direct: set[str] = set()
    for rel in sorted(modules.values()):
        dependencies = set()
        for node in ast.walk(ast.parse((root / rel).read_text(encoding="utf-8"))):
            names = ([item.name for item in node.names] if isinstance(node, ast.Import)
                     else [node.module or ""] if isinstance(node, ast.ImportFrom) else [])
            for name in names:
                name = name.split(".")[0]
                if name in {"fitz", "pymupdf"}:
                    direct.add(rel)
                if name in modules:
                    dependencies.add(modules[name])
        graph[rel] = dependencies
    return graph, direct


def validate(root: Path) -> list[str]:
    """Validate an explicit grant, not the legal sufficiency of that grant."""
    errors: list[str] = []
    try:
        manifest = json.loads((root / "LICENSE-SCOPE.json").read_text(encoding="utf-8"))
        if manifest.get("schema") != 1 or manifest.get("license") != "AGPL-3.0-only":
            errors.append("unsupported license scope schema or license")
        files = manifest["covered_files"]
        if not isinstance(files, list) or not all(isinstance(x, str) for x in files):
            return errors + ["covered_files must be an explicit list of paths"]
        if files != sorted(set(files)):
            errors.append("covered_files must be sorted and unique")
        covered = set(files)
        grouped = [rel for group in manifest["file_groups"].values() for rel in group]
        if sorted(grouped) != files:
            errors.append("scope categories do not match exact covered file list")
        if not REQUIRED_FILES <= covered:
            errors.append("license scope lost required QA/support files")
        if manifest.get("excluded_directories") != EXCLUDED_DIRS:
            errors.append("excluded asset/catalog/fixture directories changed")
        if set(manifest.get("excluded_files", [])) != EXCLUDED_FILES:
            errors.append("excluded generator/catalog files changed")
        for rel in files:
            path = PurePosixPath(rel)
            if path.is_absolute() or ".." in path.parts or any(c in rel for c in "*?[]\\"):
                errors.append(f"scope path must be explicit and package-relative: {rel}")
                continue
            if rel in EXCLUDED_FILES or any(rel.startswith(x) for x in EXCLUDED_DIRS):
                errors.append(f"scope includes excluded material: {rel}")
            if not (root / rel).is_file():
                errors.append(f"covered source missing: {rel}")
                continue
            if rel.startswith("scripts/") or rel == "requirements-qa.txt":
                if SPDX not in (root / rel).read_text(encoding="utf-8").splitlines()[:5]:
                    errors.append(f"covered source notice missing: {rel}")
        for path in (root / "scripts").glob("*"):
            if path.suffix not in {".py", ".sh"}:
                continue
            rel = path.relative_to(root).as_posix()
            if SPDX in path.read_text(encoding="utf-8").splitlines()[:5] and rel not in covered:
                errors.append(f"source notice outside explicit scope: {rel}")

        for rel, digest in LICENSE_HASHES.items():
            if not (root / rel).is_file():
                errors.append(f"license text missing: {rel}")
            elif hashlib.sha256((root / rel).read_bytes()).hexdigest() != digest:
                errors.append(f"unmodified license text differs: {rel}")
        declared_hashes = {entry["path"]: entry["sha256"] for entry in manifest["license_texts"]}
        if declared_hashes != LICENSE_HASHES:
            errors.append("license text manifest differs from verified upstream copies")
        graph, direct = import_graph(root)
        for rel in sorted(direct - covered):
            errors.append(f"PyMuPDF integration outside declared scope: {rel}")
        actual_edges = {(source, target) for source in covered if source in graph
                        for target in graph[source] - covered}
        entries = manifest["unresolved_local_imports"]
        declared_edges = {(x["source"], x["target"]) for x in entries}
        if len(entries) != len(declared_edges) or declared_edges != actual_edges:
            errors.append("unresolved local import boundary differs from declared edges")
        build = (root / "scripts/build.sh").read_text(encoding="utf-8")
        for name in set(re.findall(r'\$SCRIPT_DIR/([\w.-]+\.(?:py|sh))', build)):
            if "scripts/" + name not in covered:
                errors.append(f"mandatory build support outside scope: {name}")
        for rel, required in REQUIRED_DOCS.items():
            text = " ".join((root / rel).read_text(encoding="utf-8").split())
            for phrase in required:
                if phrase not in text:
                    errors.append(f"licensing documentation lost required statement: {rel}: {phrase}")
        docs = [root / rel for rel in REQUIRED_DOCS] + [root / "NOTICE.md"]
        readme = root.parent.parent / "README.md"
        if readme.is_file():
            docs.append(readme)
        broad = re.compile(
            r"(?:the )?(?:entire|whole) (?:repository|repo|skill|package) "
            r"(?:is |has been )?(?:licensed|relicensed|available) under (?:GNU )?AGPL"
            r"|TeX templates (?:are |have been )?(?:licensed|relicensed|available) "
            r"under (?:GNU )?(?:AGPL|MIT)",
            re.IGNORECASE,
        )
        for path in docs:
            if broad.search(" ".join(path.read_text(encoding="utf-8").split())):
                errors.append(f"overbroad licensing claim: {path.name}")
    except (OSError, ValueError, SyntaxError, KeyError, TypeError) as exc:
        errors.append(f"license scope cannot be checked: {type(exc).__name__}: {exc}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    errors = validate(args.root.resolve())
    for error in errors:
        print(f"✗ {error}")
    if errors:
        return 1
    print("✓ explicit license scope, notices, exclusions and unresolved imports agree")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
