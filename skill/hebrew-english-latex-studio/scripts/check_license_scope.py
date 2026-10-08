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
from build_contract import OUTPUT_PERMISSION_PATH, OUTPUT_PERMISSION_SHA256, read_output_permission
ROOT = Path(__file__).resolve().parent.parent
SPDX = "# SPDX-License-Identifier: AGPL-3.0-only"
LICENSE_HASHES = {
    "LICENSES/AGPL-3.0-only.txt": "0d96a4ff68ad6d4b6f1f30f713b18d5184912ba8dd389f86aa7710db079abcb0",
    "LICENSES/PyMuPDF-1.26.7-COPYING": "57c8ff33c9c0cfc3ef00e650a1cc910d7ee479a8bc509f6c9209a7c2a11399d6",
}
GENERATOR_FILES = {
    "scripts/new_document.py", "scripts/template_registry.py",
    "scripts/generate_studio_docs.py", "scripts/studio_glossary.py",
    "scripts/render_architecture_guards.py", "scripts/render_compat_bundles.py",
    "scripts/sync_preamble.sh",
}
PERMISSION_SOURCE_FILES = GENERATOR_FILES | {
    "scripts/architecture_contract.py", "scripts/build_contract.py",
}
PERMISSION_NOTICE = "# Additional output permission: ../LICENSES/Generated-Output-Permission.txt."
EXCLUDED_DATA_FILES = {"references/glossary/terms.json"}
EXCLUDED_DIRS = ["assets/", "registry/", "tests/"]
REQUIRED_FILES = {
    "LICENSING.md", "NOTICE.md", "LICENSE-SCOPE.json", "requirements-qa.txt",
    "scripts/build.sh", "scripts/test_all.sh", "scripts/check_license_scope.py",
    "scripts/test_license_scope.py", "scripts/package_skill.py",
} | GENERATOR_FILES
SHELL_ENTRY_POINTS = ["scripts/build.sh", "scripts/setup_fonts.sh",
                      "scripts/sync_preamble.sh", "scripts/test_all.sh"]
REQUIRED_DOCS = {
    "LICENSING.md": ("closed_project_tooling", "does not automatically license",
                     "Copied source retains its actual", "not legal certification",
                     "Generated-Output-Permission.txt", "138 individual paths"),
    "SKILL.md": ("LICENSING.md", "LICENSE-SCOPE.json", "NOTICE.md", "Generated-Output-Permission.txt"),
    "references/studio-setup.md": ("LICENSING.md", "NOTICE.md", "Generated-Output-Permission.txt"),
    "references/pdf-strings-and-renderers.md": ("LICENSING.md", "NOTICE.md", "Generated-Output-Permission.txt"),
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
            if isinstance(node, ast.Call) and node.args and isinstance(node.args[0], ast.Constant):
                if ((isinstance(node.func, ast.Name) and node.func.id == "__import__") or
                        (isinstance(node.func, ast.Attribute) and node.func.attr == "import_module")):
                    if isinstance(node.args[0].value, str):
                        names.append(node.args[0].value)
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
        if manifest.get("schema") != 2 or manifest.get("license") != "AGPL-3.0-only":
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
        if manifest.get("excluded_files") != [] or set(manifest.get("excluded_data_files", [])) != EXCLUDED_DATA_FILES:
            errors.append("excluded input data boundary changed")
        expected_boundary = {"policy": "closed_project_tooling", "local_imports": "both_directions",
                             "shell_entry_points": SHELL_ENTRY_POINTS}
        if manifest.get("dependency_boundary") != expected_boundary or "unresolved_local_imports" in manifest:
            errors.append("closed dependency boundary policy differs")
        for rel in files:
            path = PurePosixPath(rel)
            if path.is_absolute() or ".." in path.parts or any(c in rel for c in "*?[]\\"):
                errors.append(f"scope path must be explicit and package-relative: {rel}")
                continue
            if rel in EXCLUDED_DATA_FILES or any(rel.startswith(x) for x in EXCLUDED_DIRS):
                errors.append(f"scope includes excluded material: {rel}")
            if not (root / rel).is_file():
                errors.append(f"covered source missing: {rel}")
                continue
            if rel.startswith("scripts/") or rel == "requirements-qa.txt":
                if SPDX not in (root / rel).read_text(encoding="utf-8").splitlines()[:5]:
                    errors.append(f"covered source notice missing: {rel}")
            if rel in PERMISSION_SOURCE_FILES and PERMISSION_NOTICE not in (root / rel).read_text().splitlines()[:6]:
                errors.append(f"generated output permission notice missing: {rel}")
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
        expected_permission = [{"path": OUTPUT_PERMISSION_PATH, "sha256": OUTPUT_PERMISSION_SHA256,
                                "emitting_programs": sorted(GENERATOR_FILES),
                                "source_notice_files": sorted(PERMISSION_SOURCE_FILES)}]
        if manifest.get("additional_permissions") != expected_permission:
            errors.append("generated output permission manifest differs")
        try:
            read_output_permission(root)
        except ValueError as exc:
            errors.append(str(exc))
        graph, direct = import_graph(root)
        for rel in sorted(direct - covered):
            errors.append(f"PyMuPDF integration outside declared scope: {rel}")
        for source, dependencies in graph.items():
            for target in sorted(dependencies):
                if source in covered and target not in covered:
                    errors.append(f"local dependency outside scope: {source} -> {target}")
                elif source not in covered and target in covered:
                    errors.append(f"unlisted caller imports covered code: {source} -> {target}")
        # Fixed project script paths include command wrappers, test harness
        # entries, and their copied/inspected support. These references require
        # review too; process boundaries do not establish license independence.
        local_reference = re.compile(r'(?:\$SCRIPT_DIR/|scripts/)([\w.-]+\.(?:py|sh))')
        for rel in sorted(covered):
            if not rel.startswith("scripts/"):
                continue
            for name in set(local_reference.findall((root / rel).read_text())):
                # Mutation fixtures can mention hypothetical filenames that
                # are not project source. Check references to actual files.
                if (root / "scripts" / name).is_file() and "scripts/" + name not in covered:
                    errors.append(f"project script support outside scope: {rel} -> scripts/{name}")
        for rel, required in REQUIRED_DOCS.items():
            text = " ".join((root / rel).read_text(encoding="utf-8").split())
            for phrase in required:
                if phrase not in text:
                    errors.append(f"licensing documentation lost required statement: {rel}: {phrase}")
            if rel == "LICENSING.md" and f"{len(files)} individual paths" not in text:
                errors.append("documented grant count differs from exact manifest")
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
    print("✓ explicit license scope, closed project dependencies, output permission and exclusions agree")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
