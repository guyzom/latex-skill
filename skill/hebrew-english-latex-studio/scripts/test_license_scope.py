#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Original project code; scope and terms: ../LICENSING.md.
"""Mutation regressions for a scoped grant, without certifying compliance."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
from check_license_scope import GENERATOR_FILES, LICENSE_HASHES, PERMISSION_NOTICE, ROOT, SPDX, validate
from build_contract import GENERATED_OUTPUT_PERMISSION_NAME, OUTPUT_PERMISSION_PATH, OUTPUT_PERMISSION_SHA256


class LicenseScopeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="studio-license-scope-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "package"
        shutil.copytree(ROOT, self.root, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))

    def edit_manifest(self, change):
        path = self.root / "LICENSE-SCOPE.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        change(data)
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    def rejects(self, phrase):
        self.assertTrue(any(phrase in error for error in validate(self.root)), validate(self.root))

    def test_current_declared_boundary(self):
        self.assertEqual(validate(self.root), [])

    def test_each_license_text_is_required_and_unmodified(self):
        for rel in LICENSE_HASHES:
            with self.subTest(rel=rel):
                path = self.root / rel
                original = path.read_bytes()
                path.unlink()
                self.rejects("license text missing")
                path.write_bytes(original + b"changed\n")
                self.rejects("unmodified license text differs")
                path.write_bytes(original)

    def test_templates_and_input_data_cannot_acquire_a_grant(self):
        for rel in ("assets/preamble.tex", "registry/studio-catalog.json", "references/glossary/terms.json"):
            with self.subTest(rel=rel):
                original = (self.root / "LICENSE-SCOPE.json").read_bytes()
                self.edit_manifest(lambda d: d["covered_files"].append(rel))
                self.rejects("scope includes excluded material")
                (self.root / "LICENSE-SCOPE.json").write_bytes(original)

    def test_wildcard_cannot_replace_explicit_paths(self):
        self.edit_manifest(lambda d: d["covered_files"].append("scripts/*"))
        self.rejects("scope path must be explicit")

    def test_documented_grant_count_cannot_drift(self):
        path = self.root / "LICENSING.md"
        path.write_text(path.read_text().replace("138 individual paths", "139 individual paths", 1))
        self.rejects("documented grant count differs")

    def test_notices_cannot_drift_from_manifest(self):
        path = self.root / "scripts/render_review.py"
        path.write_text(path.read_text().replace(SPDX, "# removed", 1))
        self.rejects("covered source notice missing")
        outside = self.root / "scripts/independent_probe.py"
        outside.write_text(SPDX + "\n")
        self.rejects("source notice outside explicit scope")

    def test_new_pymupdf_program_requires_explicit_review(self):
        (self.root / "scripts/unreviewed_probe.py").write_text("import fitz\n")
        self.rejects("PyMuPDF integration outside declared scope")

    def test_unresolved_import_allowlist_cannot_return(self):
        self.edit_manifest(lambda d: d.update(unresolved_local_imports=[]))
        self.rejects("closed dependency boundary policy differs")

    def test_new_unlisted_helper_and_build_support_are_detected(self):
        (self.root / "scripts/unlicensed_helper.py").write_text("VALUE = 1\n")
        path = self.root / "scripts/render_review.py"
        original = path.read_text()
        path.write_text(original + "\nimport unlicensed_helper\n")
        self.rejects("local dependency outside scope")
        path.write_text(original)
        path = self.root / "scripts/build.sh"
        path.write_text(path.read_text() + '\npython3 "$SCRIPT_DIR/unlicensed_helper.py"\n')
        self.rejects("project script support outside scope")

    def test_reverse_shared_contract_import_is_detected(self):
        (self.root / "scripts/unlisted_caller.py").write_text("from build_contract import PAPERS_MM\n")
        self.rejects("unlisted caller imports covered code")

    def test_literal_dynamic_import_cannot_hide_dependency(self):
        (self.root / "scripts/dynamic_helper.py").write_text("VALUE = 1\n")
        path = self.root / "scripts/render_review.py"
        path.write_text(path.read_text() + "\n__import__('dynamic_helper')\n")
        self.rejects("local dependency outside scope")

    def test_generator_grants_and_output_permission_notices_are_required(self):
        data = json.loads((self.root / "LICENSE-SCOPE.json").read_text())
        self.assertEqual(len(data["covered_files"]), 138)
        self.assertTrue(GENERATOR_FILES <= set(data["covered_files"]))
        path = self.root / "scripts/new_document.py"
        path.write_text(path.read_text().replace(PERMISSION_NOTICE, "# removed", 1))
        self.rejects("generated output permission notice missing")

    def test_output_permission_text_and_manifest_cannot_be_omitted_or_changed(self):
        path = self.root / OUTPUT_PERMISSION_PATH
        original = path.read_bytes()
        path.unlink()
        self.rejects("generated output permission missing")
        path.write_bytes(original + b"changed\n")
        self.rejects("generated output permission differs")
        path.write_bytes(original)
        self.edit_manifest(lambda d: d["additional_permissions"].clear())
        self.rejects("generated output permission manifest differs")

    def test_permission_cannot_be_extended_to_extra_emitters(self):
        self.edit_manifest(lambda d: d["additional_permissions"][0]["emitting_programs"].append("scripts/render_review.py"))
        self.rejects("generated output permission manifest differs")

    def test_generated_project_retains_permission_and_input_terms(self):
        import hashlib
        import new_document
        destination = self.root.parent / "generated"
        with patch.object(new_document, "ROOT", self.root):
            new_document.create("general", destination, language="bilingual", main_language="hebrew", theme="custom")
        permission = destination / GENERATED_OUTPUT_PERMISSION_NAME
        self.assertEqual(permission.read_bytes(), (self.root / OUTPUT_PERMISSION_PATH).read_bytes())
        data = json.loads((destination / "project.json").read_text())
        self.assertEqual(data["initial_source_sha256"][permission.name], OUTPUT_PERMISSION_SHA256)
        for name, digest in data["copied_assets"].items():
            self.assertEqual(hashlib.sha256((destination / name).read_bytes()).hexdigest(), digest)
            self.assertEqual((destination / name).read_bytes(), (self.root / "assets" / name).read_bytes())
        self.assertNotIn("SPDX-License-Identifier: AGPL", (destination / "main.tex").read_text())
        self.assertNotIn("SPDX-License-Identifier: AGPL", (destination / "theme.tex").read_text())
        self.assertIn("this permission does not grant rights in them", (destination / "README.md").read_text())

    def test_generator_fails_before_writing_without_the_exact_permission(self):
        import new_document
        path = self.root / OUTPUT_PERMISSION_PATH
        original = path.read_bytes()
        parent = self.root.parent / "uncreated-parent"
        with patch.object(new_document, "ROOT", self.root):
            for altered in (None, original + b"changed\n"):
                with self.subTest(altered=altered is not None):
                    if altered is None:
                        path.unlink()
                    else:
                        path.write_bytes(altered)
                    with self.assertRaisesRegex(ValueError, "generated output permission"):
                        new_document.create("general", parent / "project", language="english")
                    self.assertFalse(parent.exists())
        path.write_bytes(original)

    def test_overbroad_claims_and_missing_output_caveat_are_detected(self):
        path = self.root / "LICENSING.md"
        path.write_text(path.read_text() + "\nThe entire skill is licensed under AGPL.\n")
        self.rejects("overbroad licensing claim")
        path.write_text(path.read_text().replace("does not automatically license", "licenses", 1))
        self.rejects("licensing documentation lost required statement")

    def test_template_license_claim_cannot_be_added(self):
        path = self.root / "NOTICE.md"
        path.write_text(path.read_text() + "\nTeX templates are licensed under MIT.\n")
        self.rejects("overbroad licensing claim")


if __name__ == "__main__":
    unittest.main()
