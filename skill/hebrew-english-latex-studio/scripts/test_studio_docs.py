#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Original project code; scope and terms: ../LICENSING.md.
"""Focused glossary/catalog documentation contracts; no engine or renderer."""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from io import StringIO
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True

from generate_studio_docs import CATALOG_MARKDOWN, generated_documents, main, render_catalog, write_document
from studio_glossary import MARKDOWN_PATH, RECORDS_PATH, ROOT, load_records, reject_duplicate_keys, render_markdown, validate_records
from template_registry import load_catalog


class GlossaryContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = load_catalog(ROOT)
        cls.records = load_records(ROOT, catalog=cls.catalog)

    def assert_invalid(self, mutate, message: str, *, catalog=None) -> None:
        changed = deepcopy(self.records)
        mutate(changed)
        with self.assertRaisesRegex(ValueError, message):
            validate_records(changed, ROOT, catalog=catalog)

    def test_current_records_cover_canonical_catalog(self) -> None:
        data = self.catalog.as_dict()
        ids = {term["id"] for term in self.records["terms"]}
        self.assertTrue(set(data["required_glossary_terms"]) <= ids)
        for collection in ("templates", "layouts", "themes", "examples", "components"):
            for record in data[collection]:
                with self.subTest(collection=collection, item=record["id"]):
                    self.assertTrue(set(record["glossary_refs"]) <= ids)
        self.assertEqual(self.records["skill_version"], (ROOT / "VERSION").read_text().strip())

    def test_duplicate_json_keys_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "duplicate JSON object key"):
            json.loads('{"id":"recipe","id":"template"}', object_pairs_hook=reject_duplicate_keys)

    def test_duplicate_ids_rejected(self) -> None:
        self.assert_invalid(lambda d: d["terms"].append(deepcopy(d["terms"][0])), "duplicate term id")
        self.assert_invalid(lambda d: d["sections"].append(deepcopy(d["sections"][0])), "duplicate section id")

    def test_unknown_related_and_self_links_rejected(self) -> None:
        self.assert_invalid(lambda d: d["terms"][0]["related_ids"].append("unknown-term"), "unknown related id")
        self.assert_invalid(lambda d: d["terms"][0]["related_ids"].append(d["terms"][0]["id"]), "self-reference")

    def test_bilingual_labels_required(self) -> None:
        for field, value, message in (("hebrew", "", "requires nonempty text"), ("hebrew", "Only English", "Hebrew label"), ("english", "עברית", "English label")):
            with self.subTest(field=field, value=value):
                self.assert_invalid(lambda d: d["terms"][0].update({field: value}), message)

    def test_unknown_fields_and_wrong_field_types_rejected(self) -> None:
        self.assert_invalid(lambda d: d.update(unknown=True), "top-level fields")
        self.assert_invalid(lambda d: d["terms"][0].update(unknown=True), "missing or unknown fields")
        self.assert_invalid(lambda d: d["terms"][0].pop("english"), "missing or unknown fields")
        self.assert_invalid(lambda d: d["terms"][0].update(related_ids="recipe"), "expected a list")
        self.assert_invalid(lambda d: d["terms"][0].update(aliases=["bad|alias"]), "table delimiters")

    def test_section_and_status_contracts_rejected(self) -> None:
        self.assert_invalid(lambda d: d["terms"][0].update(section="unknown-section"), "unknown section id")
        self.assert_invalid(lambda d: d["sections"].append({"id": "empty", "hebrew": "ריק"}), "empty glossary section")
        self.assert_invalid(lambda d: d["terms"][0].update(status="proposed"), "unknown status")
        self.assert_invalid(lambda d: d["terms"][0].update(audience="everyone"), "unknown audience")

    def test_uncontained_and_missing_sources_rejected(self) -> None:
        for path in ("../outside", "/tmp/outside", "references\\architecture.md", "references/architecture.md#unknown", "https://example.org", "references//architecture.md"):
            with self.subTest(path=path):
                self.assert_invalid(lambda d: d["terms"][0].update(source_refs=[path]), "invalid relative source reference")
        self.assert_invalid(lambda d: d["terms"][0].update(source_refs=["references/not-shipped.md"]), "missing source reference")
        self.assert_invalid(lambda d: d["terms"][0].update(source_refs=["SKILL.md/child.md"]), "invalid source reference ancestor")

    def test_symlink_source_escape_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="studio-glossary-links-") as directory:
            base = Path(directory)
            target = base / "outside.md"
            target.write_text("outside\n")
            root = base / "skill"
            root.mkdir()
            (root / "VERSION").write_text(self.records["skill_version"])
            (root / "escape.md").symlink_to(target)
            changed = deepcopy(self.records)
            changed["terms"][0]["source_refs"] = ["escape.md"]
            with self.assertRaisesRegex(ValueError, "symlink source reference"):
                validate_records(changed, root)

    def test_internal_symlinks_and_symlink_ancestors_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="studio-glossary-contained-links-") as directory:
            root = Path(directory)
            (root / "VERSION").write_text(self.records["skill_version"])
            (root / "real").mkdir()
            (root / "real" / "source.md").write_text("inside\n")
            (root / "link.md").symlink_to(root / "real" / "source.md")
            (root / "linked-dir").symlink_to(root / "real", target_is_directory=True)
            for reference in ("link.md", "linked-dir/source.md"):
                with self.subTest(reference=reference):
                    changed = deepcopy(self.records)
                    changed["terms"][0]["source_refs"] = [reference]
                    with self.assertRaisesRegex(ValueError, "symlink source reference"):
                        validate_records(changed, root)

    def test_current_version_and_chronology_enforced(self) -> None:
        self.assert_invalid(lambda d: d.update(skill_version="0.0.0"), "does not match VERSION")
        self.assert_invalid(lambda d: d.update(schema_version=True), "unsupported glossary schema_version")
        self.assert_invalid(lambda d: d.update(schema_version=1), "unsupported glossary schema_version")
        self.assert_invalid(lambda d: d["terms"][0].update(introduced_in="999.0.0"), "release chronology")
        self.assert_invalid(lambda d: d["terms"][0].update(updated_in="999.0.0"), "release chronology")
        self.assert_invalid(lambda d: d["terms"][0].update(updated_in="5.4"), "three-part release version")

    def test_required_catalog_terms_and_record_refs_enforced(self) -> None:
        data = self.catalog.as_dict()
        data["required_glossary_terms"].append("missing-required-term")
        with self.assertRaisesRegex(ValueError, "unknown term ids.*missing-required-term"):
            validate_records(self.records, ROOT, catalog=data)
        data = self.catalog.as_dict()
        data["templates"][0]["glossary_refs"].append("missing-record-term")
        with self.assertRaisesRegex(ValueError, "unknown term ids.*missing-record-term"):
            validate_records(self.records, ROOT, catalog=data)
        data = self.catalog.as_dict()
        data["required_glossary_terms"] = []
        with self.assertRaisesRegex(ValueError, "missing required_glossary_terms"):
            validate_records(self.records, ROOT, catalog=data)

    def test_rendering_deterministic_and_stable_term_anchors(self) -> None:
        before = deepcopy(self.records)
        first = render_markdown(self.records)
        self.assertEqual(first, render_markdown(self.records))
        self.assertEqual(self.records, before)
        for term in self.records["terms"]:
            self.assertIn(f"### term-{term['id']}\n", first)
        self.assertIn(self.records["skill_version"], first)
        self.assertNotIn("{{SKILL_VERSION}}", first)

    def test_catalog_uses_actual_records_and_preserves_literals(self) -> None:
        first = render_catalog(self.catalog, self.records["skill_version"])
        self.assertEqual(first, render_catalog(self.catalog, self.records["skill_version"]))
        for collection, prefix in (("templates", "Template"), ("layouts", "Layout"), ("themes", "Theme"), ("examples", "Example"), ("components", "Component")):
            for record in self.catalog.as_dict()[collection]:
                self.assertIn(f"### {prefix} {record['id']}\n", first)
        data = self.catalog.as_dict()
        for layout in data["layouts"]:
            for hook in layout["hook_overrides"]:
                self.assertIn(f"`{hook['value']}`", first)
                self.assertIn(f"`{hook['unit']}`", first)


class GeneratedDocumentationContracts(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="studio-docs-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "source"
        shutil.copytree(ROOT, self.root, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))

    def run_cli(self, *args: str) -> tuple[int, str]:
        stdout, stderr = StringIO(), StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            result = main(["--root", str(self.root), *args])
        return result, stdout.getvalue() + stderr.getvalue()

    def snapshot(self) -> dict[str, tuple[bytes, int]]:
        return {str(path.relative_to(self.root)): (path.read_bytes(), path.stat().st_mtime_ns) for path in self.root.rglob("*") if path.is_file()}

    def test_committed_generated_docs_exact(self) -> None:
        expected = generated_documents(ROOT)
        self.assertEqual(set(expected), {CATALOG_MARKDOWN, MARKDOWN_PATH})
        for path, content in expected.items():
            self.assertEqual((ROOT / path).read_bytes(), content)

    def test_check_success_writes_nothing(self) -> None:
        before = self.snapshot()
        result, output = self.run_cli("--check")
        self.assertEqual(result, 0, output)
        self.assertEqual(self.snapshot(), before)
        self.assertIn("No files written", output)

    def test_stale_check_fails_without_repairing_either_file(self) -> None:
        for path in (CATALOG_MARKDOWN, MARKDOWN_PATH):
            with self.subTest(path=path):
                original = (self.root / path).read_bytes()
                (self.root / path).write_bytes(original + b"\nmanual stale edit\n")
                before = self.snapshot()
                result, output = self.run_cli("--check")
                self.assertEqual(result, 1)
                self.assertIn("generated documentation differs", output)
                self.assertEqual(self.snapshot(), before)
                (self.root / path).write_bytes(original)

    def test_missing_owned_outputs_regenerate_and_check_remains_read_only(self) -> None:
        for path in (CATALOG_MARKDOWN, MARKDOWN_PATH):
            with self.subTest(path=path):
                expected = (self.root / path).read_bytes()
                (self.root / path).unlink()
                before = self.snapshot()
                result, output = self.run_cli("--check")
                self.assertEqual(result, 1)
                self.assertIn("generated documentation differs", output)
                self.assertEqual(self.snapshot(), before)
                result, output = self.run_cli()
                self.assertEqual(result, 0, output)
                self.assertEqual((self.root / path).read_bytes(), expected)

    def test_missing_nongenerated_document_aborts_without_writes(self) -> None:
        (self.root / "references/catalog-development.md").unlink()
        before = self.snapshot()
        result, output = self.run_cli()
        self.assertEqual(result, 1)
        self.assertIn("missing source reference", output)
        self.assertEqual(self.snapshot(), before)

    def test_record_changes_require_fresh_generated_output(self) -> None:
        path = self.root / RECORDS_PATH
        data = json.loads(path.read_text(encoding="utf-8"))
        data["terms"][0]["definition"] += " נוסף הסבר מכוון."
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        result, output = self.run_cli("--check")
        self.assertEqual(result, 1)
        self.assertIn("generated documentation differs", output)
        result, output = self.run_cli()
        self.assertEqual(result, 0, output)
        result, output = self.run_cli("--check")
        self.assertEqual(result, 0, output)

    def test_canonical_registry_change_requires_catalog_regeneration(self) -> None:
        path = self.root / "registry/studio-catalog.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["templates"][0]["title"]["he"] += " — בדיקה"
        data["templates"][0]["title"]["en"] += " — inspection"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        before_glossary = (self.root / MARKDOWN_PATH).read_bytes()
        result, output = self.run_cli("--check")
        self.assertEqual(result, 1)
        self.assertIn(CATALOG_MARKDOWN, output)
        result, output = self.run_cli()
        self.assertEqual(result, 0, output)
        self.assertIn("inspection", (self.root / CATALOG_MARKDOWN).read_text(encoding="utf-8"))
        self.assertEqual((self.root / MARKDOWN_PATH).read_bytes(), before_glossary)
        result, output = self.run_cli("--check")
        self.assertEqual(result, 0, output)

    def test_invalid_records_abort_before_document_writes(self) -> None:
        path = self.root / RECORDS_PATH
        data = json.loads(path.read_text(encoding="utf-8"))
        data["terms"][0]["related_ids"].append("not-real")
        path.write_text(json.dumps(data, ensure_ascii=False) + "\n", encoding="utf-8")
        before = self.snapshot()
        result, output = self.run_cli()
        self.assertEqual(result, 1)
        self.assertIn("unknown related id", output)
        self.assertEqual(self.snapshot(), before)

    def test_duplicate_json_record_keys_abort(self) -> None:
        path = self.root / RECORDS_PATH
        text = path.read_text(encoding="utf-8")
        text = text.replace('"schema_version": 2,', '"schema_version": 2, "schema_version": 2,', 1)
        path.write_text(text, encoding="utf-8")
        before = self.snapshot()
        result, output = self.run_cli()
        self.assertEqual(result, 1)
        self.assertIn("duplicate JSON object key", output)
        self.assertEqual(self.snapshot(), before)

    def test_single_document_replacement_preserves_file_mode(self) -> None:
        path = self.root / "references" / "temporary-doc.md"
        path.write_bytes(b"old\n")
        path.chmod(0o640)
        write_document(path, b"new\n")
        self.assertEqual(path.read_bytes(), b"new\n")
        self.assertEqual(path.stat().st_mode & 0o777, 0o640)
        self.assertFalse(list(path.parent.glob(".studio-doc-*")))


if __name__ == "__main__":
    unittest.main(verbosity=2)
