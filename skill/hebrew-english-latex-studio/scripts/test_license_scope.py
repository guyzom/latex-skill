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

sys.dont_write_bytecode = True
from check_license_scope import LICENSE_HASHES, ROOT, SPDX, validate


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

    def test_templates_and_generator_cannot_acquire_a_grant(self):
        for rel in ("assets/preamble.tex", "scripts/new_document.py"):
            with self.subTest(rel=rel):
                original = (self.root / "LICENSE-SCOPE.json").read_bytes()
                self.edit_manifest(lambda d: d["covered_files"].append(rel))
                self.rejects("scope includes excluded material")
                (self.root / "LICENSE-SCOPE.json").write_bytes(original)

    def test_wildcard_cannot_replace_explicit_paths(self):
        self.edit_manifest(lambda d: d["covered_files"].append("scripts/*"))
        self.rejects("scope path must be explicit")

    def test_notices_cannot_drift_from_manifest(self):
        path = self.root / "scripts/render_review.py"
        path.write_text(path.read_text().replace(SPDX, "# removed", 1))
        self.rejects("covered source notice missing")
        outside = self.root / "scripts/new_document.py"
        outside.write_text(SPDX + "\n" + outside.read_text())
        self.rejects("source notice outside explicit scope")

    def test_new_pymupdf_program_requires_explicit_review(self):
        (self.root / "scripts/unreviewed_probe.py").write_text("import fitz\n")
        self.rejects("PyMuPDF integration outside declared scope")

    def test_shared_import_edges_cannot_be_hidden(self):
        self.edit_manifest(lambda d: d["unresolved_local_imports"].clear())
        self.rejects("unresolved local import boundary differs")

    def test_new_unlisted_helper_and_build_support_are_detected(self):
        path = self.root / "scripts/render_review.py"
        path.write_text(path.read_text() + "\nimport new_document\n")
        self.rejects("unresolved local import boundary differs")
        path = self.root / "scripts/build.sh"
        path.write_text(path.read_text() + '\npython3 "$SCRIPT_DIR/new_document.py"\n')
        self.rejects("mandatory build support outside scope")

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
