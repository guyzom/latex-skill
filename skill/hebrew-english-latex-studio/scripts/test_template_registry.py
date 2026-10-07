#!/usr/bin/env python3
"""Meaningful source-only acceptance and rejection tests for the Studio catalog."""
from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
import architecture_contract as architecture
import build_contract as build
import template_registry as registry

ROOT = Path(__file__).resolve().parent.parent


class RegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = registry.load_catalog(ROOT)

    def fixture(self):
        temporary = tempfile.TemporaryDirectory(prefix="studio-catalog-test-")
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        for name in ("assets", "references", "registry"):
            shutil.copytree(ROOT / name, root / name)
        return root

    def invalid(self, mutate, message=None):
        root = self.fixture()
        path = root / registry.CATALOG_PATH
        data = json.loads(path.read_text())
        mutate(data)
        path.write_text(json.dumps(data, ensure_ascii=False) + "\n")
        context = self.assertRaisesRegex(ValueError, message) if message else self.assertRaises(ValueError)
        with context:
            registry.load_catalog(root)

    def test_owned_inventory_and_historical_query_order(self):
        kinds, themes, layouts, presets = registry.compatibility_tables(self.catalog)
        self.assertEqual(tuple(kinds), ("note", "general", "letter", "report", "technical", "formula-sheet", "data-report", "annotated-note", "paper"))
        self.assertEqual(themes, ("reader", "core", "custom", "academic", "reference"))
        self.assertEqual(layouts, ("standard", "reference-compact", "reference-readable"))
        self.assertEqual(kinds["report"], ("starter_report.tex", "report"))
        self.assertEqual(presets["reference-readable"], {"columns": 2, "body_font_size": "9", "body_baseline": "11", "math_font_size": "8.75", "math_script_size": "6.125", "math_scriptscript_size": "4.375"})
        self.assertEqual(len({starter.asset_path for item in self.catalog.templates for starter in item.starters}.union({starter.asset_path for item in self.catalog.layouts for starter in item.starter_overrides})), 20)
        self.assertEqual(len(self.catalog.examples), 12)

    def test_every_supported_request_resolves_with_original_requests(self):
        requests = tuple(registry.iter_supported_requests(self.catalog))
        self.assertEqual(len(requests), 396)
        self.assertEqual(len({(r.kind, r.layout) for r in requests}), 11)
        self.assertEqual(sum(request.theme is None for request in requests), 66)
        for request in requests:
            recipe = registry.resolve_recipe(**request.as_dict(), catalog=self.catalog)
            self.assertEqual(recipe.requested, request)
            self.assertEqual(recipe.catalog_sha256, self.catalog.sha256)
            self.assertEqual(recipe.main_language, architecture.resolve_language_profile(request.language, request.main_language))

    def test_explicit_theme_precedence_and_distinct_default_provenance(self):
        paper = registry.resolve_recipe("paper", catalog=self.catalog)
        compact = registry.resolve_recipe("formula-sheet", layout="reference-compact", catalog=self.catalog)
        explicit = registry.resolve_recipe("formula-sheet", layout="reference-compact", theme="core", catalog=self.catalog)
        self.assertEqual((paper.theme, compact.theme, explicit.theme), ("academic", "reference", "core"))
        self.assertEqual(dict((item.field, item.provenance) for item in paper.resolutions)["theme"], "template-default")
        self.assertEqual(dict((item.field, item.provenance) for item in compact.resolutions)["theme"], "layout-default")
        self.assertEqual(dict((item.field, item.provenance) for item in explicit.resolutions)["theme"], "explicit")
        self.assertIsNone(compact.requested.theme)

    def test_catalog_global_theme_fallback_and_valid_template_layout_default(self):
        root = self.fixture()
        path = root / registry.CATALOG_PATH
        data = json.loads(path.read_text())
        data["templates"][0]["default_theme"] = None
        path.write_text(json.dumps(data))
        catalog = registry.load_catalog(root)
        recipe = registry.resolve_recipe("note", root=root, catalog=catalog)
        self.assertEqual(recipe.theme, "reader")
        self.assertEqual(dict((item.field, item.provenance) for item in recipe.resolutions)["theme"], "catalog-default")
        self.invalid(lambda data: data["templates"][0].update(default_layout="reference-compact"), "default layout forbids")

    def test_copy_plan_is_distinct_from_actual_load_plan(self):
        hebrew = registry.resolve_recipe("formula-sheet", language="hebrew", catalog=self.catalog)
        english = registry.resolve_recipe("formula-sheet", language="english", catalog=self.catalog)
        self.assertIn("assets/document_components.tex", hebrew.copy_plan)
        self.assertNotIn("assets/document_components.tex", hebrew.load_plan)
        self.assertIn("assets/document_components.tex", english.load_plan)
        self.assertEqual(hebrew.copy_plan, english.copy_plan)
        compact = registry.resolve_recipe("formula-sheet", layout="reference-compact", theme="reference", catalog=self.catalog)
        self.assertEqual(compact.package_scan_plan, compact.copy_plan + ("assets/starter_reference_sheet.tex",))

    def test_recipe_nested_state_is_immutable_and_serialization_detached(self):
        recipe = registry.resolve_recipe("formula-sheet", layout="reference-readable", catalog=self.catalog)
        for item, field, value in ((recipe, "theme", "reader"), (recipe.requested, "theme", "reader"), (recipe.hooks[0], "value", "bad"), (self.catalog.templates[0].starters[0], "asset_path", "bad")):
            with self.assertRaises(FrozenInstanceError):
                setattr(item, field, value)
        self.assertIsInstance(recipe.copy_plan, tuple)
        self.assertIsInstance(recipe.build_defaults, tuple)
        detached = recipe.as_dict()
        detached["hooks"][0]["value"] = "bad"
        detached["requested"]["theme"] = "bad"
        self.assertNotEqual(recipe.hooks[0].value, "bad")
        self.assertIsNone(recipe.requested.theme)

    def test_hook_inventory_all_28_have_explicit_owners_and_scopes(self):
        self.assertEqual(len(architecture.HOOK_SPECS), 28)
        self.assertFalse(architecture.validate_contract())
        owners = {item.path for item in architecture.ASSET_SPECS}
        for hook in architecture.HOOK_SPECS:
            self.assertIn(hook.owner, owners)
            self.assertIn(hook.default_kind, ("literal", "symbolic"))
            self.assertTrue(hook.scope)
            if hook.preset_allowed and hook.default_kind == "literal":
                registry.validate_hook_value(hook.name, hook.default)
            if not hook.preset_allowed:
                with self.assertRaises(ValueError):
                    registry.validate_hook_value(hook.name, "arbitrary")
        for name in ("ReferenceMathFontSize", "ReferenceMathScriptSize", "ReferenceMathScriptScriptSize"):
            self.assertIn(name, architecture.PUBLIC_TEX_SYMBOLS["assets/reference_columns.tex"])

    def test_declared_literals_and_symbolic_defaults_are_not_measurements(self):
        recipe = registry.resolve_recipe("formula-sheet", layout="reference-readable", catalog=self.catalog)
        hooks = {item.name: item for item in recipe.hooks}
        self.assertEqual(hooks["ReferenceBodyFontSize"].value, "9")
        self.assertEqual(hooks["ReferenceMathFontSize"].value, "8.75")
        self.assertEqual(hooks["ReferenceMathFontSize"].unit, "TeX-pt")
        owner_default = next(item for item in architecture.HOOK_SPECS if item.name == "ReferenceMathScriptSize")
        self.assertEqual(owner_default.default_kind, "symbolic")
        self.assertEqual(owner_default.default, "0.7 * ReferenceMathFontSize")
        self.assertIn("no compile", recipe.as_dict()["status"])
        self.assertEqual(registry.canonical_decimal(Decimal("9.00")), "9")
        self.assertEqual(registry.validate_hook_value("ReferenceBodyFontSize", "9.00"), "9.00")

    def test_build_defaults_reuse_build_owner_and_order(self):
        recipe = registry.resolve_recipe("paper", catalog=self.catalog)
        self.assertEqual(recipe.build_defaults, (("EXPECTED_PAPER", "a4"), ("PDF_FOLIO_LAYOUT", "center"), ("PDF_FOLIO_BAND", "footer"), ("PDF_CAPTION_COLOR", "000000"), ("PDF_CAPTION_LABEL_WEIGHT", "normal")))
        self.assertEqual(dict(recipe.caption_contract), {"label_color": "000000", "label_weight": "normal"})
        self.assertIn(recipe.content_profile, build.CONTENT_PROFILES)
        self.assertIn(dict(recipe.build_defaults)["EXPECTED_PAPER"], build.PAPERS_MM)

    def test_source_geometry_is_preserved_per_language(self):
        hebrew = registry.resolve_recipe("technical", language="hebrew", catalog=self.catalog)
        english = registry.resolve_recipe("technical", language="english", catalog=self.catalog)
        self.assertEqual({h.name: h.value for h in hebrew.hooks}["lakitgeometryoptions"], "margin=2.1cm,headheight=14pt")
        self.assertEqual({h.name: h.value for h in english.hooks}["lakitgeometryoptions"], "margin=2.2cm,headheight=14pt")
        report = registry.resolve_recipe("report", catalog=self.catalog)
        self.assertEqual({h.name: h.value for h in report.hooks}["lakitdocumentclass"], "article")

    def test_manual_and_legacy_themes_are_not_cli_selections(self):
        self.assertEqual({theme.id: theme.exposure for theme in self.catalog.themes}["clean"], "manual-supported")
        self.assertEqual({theme.id: theme.exposure for theme in self.catalog.themes}["legacy-clean"], "legacy")
        for theme in ("clean", "legacy-clean"):
            with self.assertRaisesRegex(ValueError, "unknown theme"):
                registry.resolve_recipe("general", theme=theme, catalog=self.catalog)

    def test_unknown_top_level_and_nested_fields_are_rejected(self):
        self.invalid(lambda data: data.update(execute="shell"), "unknown fields")
        self.invalid(lambda data: data["templates"][0].update(python="exec"), "unknown fields")
        self.invalid(lambda data: data["templates"][0]["title"].update(fr="bad"), "unknown fields")
        self.invalid(lambda data: data["layouts"][1]["hook_overrides"][0].update(expression="bad"), "unknown fields")

    def test_duplicate_json_keys_and_ids_are_rejected(self):
        root = self.fixture()
        path = root / registry.CATALOG_PATH
        path.write_text(path.read_text().replace('"schema_version": 1,', '"schema_version": 1,"schema_version": 1,', 1))
        with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
            registry.load_catalog(root)
        self.invalid(lambda data: data["templates"].append(data["templates"][0]), "duplicate IDs")

    def test_nonfinite_json_numbers_and_string_numeric_hooks_rejected(self):
        for constant in ("NaN", "Infinity", "-Infinity"):
            root = self.fixture()
            path = root / registry.CATALOG_PATH
            path.write_text(path.read_text().replace('"schema_version": 1', '"schema_version": ' + constant, 1))
            with self.assertRaisesRegex(ValueError, "nonfinite JSON number"):
                registry.load_catalog(root)
        for literal in ("NaN", "Infinity", "-Infinity", "1e3", "nan", "inf"):
            with self.assertRaises(ValueError):
                registry.validate_hook_value("ReferenceMathFontSize", literal)
        with self.assertRaises(ValueError):
            registry.canonical_decimal(Decimal("NaN"))

    def test_bool_and_unhashable_request_selections_are_rejected(self):
        for key in ("kind", "language", "main_language", "theme", "layout"):
            for value in (False, 0, [], {}):
                kwargs = {"kind": "general", key: value, "catalog": self.catalog}
                with self.assertRaisesRegex(ValueError, "string selection"):
                    registry.resolve_recipe(**kwargs)
        with self.assertRaisesRegex(ValueError, "unknown theme"):
            registry.resolve_recipe("general", theme="", catalog=self.catalog)

    def test_bool_revision_and_numeric_hook_values_are_rejected(self):
        self.invalid(lambda data: data["templates"][0].update(recipe_revision=True), "positive integer")
        for value in (False, 0, 6.25):
            self.invalid(lambda data: data["layouts"][1]["hook_overrides"][3].update(value=value), "literal string")

    def test_language_and_kind_layout_constraints_rejected(self):
        for kwargs in ({"kind": "general", "language": "bilingual"}, {"kind": "general", "language": "english", "main_language": "hebrew"}, {"kind": "paper", "layout": "reference-readable"}):
            with self.assertRaises(ValueError):
                registry.resolve_recipe(**kwargs, catalog=self.catalog)
        self.assertEqual(registry.resolve_recipe("general", language="bilingual", main_language="english", catalog=self.catalog).main_language, "english")

    def test_closed_handler_and_unknown_asset_rejections(self):
        self.invalid(lambda data: data["templates"][0].update(bilingual_composer_id="exec-python"), "closed content composer")
        self.invalid(lambda data: data["templates"][0]["source_handlers"].append("eval-tex"), "closed source handler")
        self.invalid(lambda data: data["layouts"][1]["components"].append("assets/starter_note.tex"), "unknown architecture asset")

    def test_paths_reject_absolute_parent_ambiguous_and_missing_files(self):
        for path in ("/etc/passwd", "../VERSION", "assets/../VERSION", "assets//preamble.tex", "assets/./preamble.tex", "assets\\preamble.tex", "assets/missing.tex"):
            with self.assertRaises(ValueError):
                registry.safe_owned_path(ROOT, path)
        root = self.fixture()
        (root / "assets/preamble.tex").unlink()
        with self.assertRaisesRegex(ValueError, "missing owned file"):
            registry.load_catalog(root)

    def test_symlinked_assets_root_and_ancestors_rejected(self):
        root = self.fixture()
        original = root / "assets/preamble.tex"
        original.unlink()
        original.symlink_to(ROOT / "assets/preamble.tex")
        with self.assertRaisesRegex(ValueError, "symlinked owned path"):
            registry.load_catalog(root)
        outside = self.fixture()
        link = outside / "alias"
        link.symlink_to(ROOT, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlinked skill root or ancestor"):
            registry.load_catalog(link)
        parent_alias = outside / "parent-alias"
        parent_alias.symlink_to(ROOT.parent, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlinked skill root or ancestor"):
            registry.load_catalog(parent_alias / ROOT.name)

    def test_non_regular_owned_file_rejected(self):
        root = self.fixture()
        path = root / "assets/preamble.tex"
        path.unlink()
        path.mkdir()
        with self.assertRaisesRegex(ValueError, "missing owned file"):
            registry.load_catalog(root)

    def test_missing_docs_strict_and_narrow_explicit_bootstrap(self):
        root = self.fixture()
        (root / "references/template-catalog.md").unlink()
        with self.assertRaisesRegex(ValueError, "missing owned file"):
            registry.load_catalog(root)
        registry.load_catalog(root, allow_missing_generated_docs=True)
        (root / "references/architecture.md").unlink()
        with self.assertRaisesRegex(ValueError, "missing owned file"):
            registry.load_catalog(root, allow_missing_generated_docs=True)
        self.invalid(lambda data: data["templates"][0]["docs"].append("references/arbitrary-missing.md"), "missing owned file")

    def test_hook_owner_unit_and_phase_are_checked(self):
        for key, value in (("owner", "assets/preamble.tex"), ("unit", "bp"), ("phase", "after-owner")):
            self.invalid(lambda data: data["layouts"][1]["hook_overrides"][3].update({key: value}), "wrong owner, unit or definition phase")

    def test_hook_dimension_integer_enum_and_geometry_grammar(self):
        for name, value in (("ReferenceColumnGap", "NaNmm"), ("ReferenceColumnRule", "-1pt"), ("ReferenceColumnCount", "4"), ("lakittocdepth", "1.0"), ("lakitdocumentclass", "beamer"), ("lakitclassoptions", "11pt,a4paper,shell"), ("lakitgeometryoptions", "margin=2cm,margin=3cm"), ("lakitgeometryoptions", "execute=shell"), ("lakitlinespread", "0")):
            with self.assertRaises(ValueError):
                registry.validate_hook_value(name, value)
        self.assertEqual(registry.validate_hook_value("ReferenceColumnRule", ".3pt"), ".3pt")

    def test_tex_numeric_literals_require_ascii_digits(self):
        for name, value in (("ReferenceMathFontSize", "٩"), ("ReferenceMathFontSize", "９"),
                            ("ReferenceColumnGap", "٥mm"), ("lakittocdepth", "١"),
                            ("lakitgeometryoptions", "margin=٢cm")):
            with self.assertRaises(ValueError):
                registry.validate_hook_value(name, value)
        with self.assertRaises(ValueError):
            registry.finite_decimal("٩")
        self.invalid(lambda data: data["layouts"][1]["hook_overrides"][3].update(value="٩"), "finite decimal")
        for name, value in (("ReferenceMathFontSize", "6.25"), ("ReferenceColumnGap", "5mm"), ("lakittocdepth", "2")):
            self.assertEqual(registry.validate_hook_value(name, value), value)

    def test_math_sizes_must_be_positive_and_ordered(self):
        self.invalid(lambda data: data["layouts"][1]["hook_overrides"][4].update(value="20"), "scriptscript.*script.*main")
        self.invalid(lambda data: data["layouts"][1]["hook_overrides"][5].update(value="0"), "minimum")
        self.invalid(lambda data: data["layouts"][1]["hook_overrides"].append(data["layouts"][1]["hook_overrides"][0]), "duplicate hook overrides")

    def test_reference_gap_and_body_baseline_match_runtime_owner_constraints(self):
        with self.assertRaisesRegex(ValueError, "minimum"):
            registry.validate_hook_value("ReferenceColumnGap", "0mm")
        self.invalid(lambda data: data["layouts"][1]["hook_overrides"][2].update(value="5"), "baseline.*body font size")

    def test_dependency_closure_conflicts_cycles_and_multiple_ownership(self):
        self.invalid(lambda data: data["base_copy_plan"].remove("assets/preamble.tex"), "dependency closure")
        self.invalid(lambda data: data["templates"][0]["copy_extra"].append("assets/clean_theme.tex"), "conflicting assets")
        core = architecture.ASSET_SPECS[0]
        cycle = replace(core, runtime_requires=("assets/reference_columns.tex",))
        with patch.object(architecture, "ASSET_SPECS", (cycle,) + architecture.ASSET_SPECS[1:]), patch.object(architecture, "validate_contract", return_value=()):
            with self.assertRaisesRegex(ValueError, "dependency cycle"):
                registry.load_catalog(ROOT)
        duplicate = replace(architecture.ASSET_SPECS[-2], public_symbols=("sourcelink",))
        specs = tuple(duplicate if item.path == duplicate.path else item for item in architecture.ASSET_SPECS)
        with patch.object(architecture, "ASSET_SPECS", specs):
            with self.assertRaisesRegex(ValueError, "multiple declared owners"):
                registry.load_catalog(ROOT)

    def test_declared_starter_fingerprint_hook_and_timing_drift_rejected(self):
        root = self.fixture()
        source = root / "assets/starter_note.tex"
        source.write_text(source.read_text() + "% changed sample\n")
        with self.assertRaisesRegex(ValueError, "fingerprint drift"):
            registry.load_catalog(root)
        text = source.read_text().replace(r"\def\lakitlinespread{1.18}", r"\def\lakitlinespread{1.19}")
        source.write_text(text)
        path = root / registry.CATALOG_PATH
        data = json.loads(path.read_text())
        data["templates"][0]["starters"][0]["sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
        path.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, "declared hook drift"):
            registry.load_catalog(root)
        with self.assertRaisesRegex(ValueError, "after or without its owner"):
            registry.extract_owned_declarations('\\input{preamble.tex}\n\\def\\lakitlinespread{1.18}\n\\begin{document}\n')

    def test_cached_recipe_revalidates_starter_before_any_destination_work(self):
        root = self.fixture()
        catalog = registry.load_catalog(root)
        starter = root / "assets/starter_general.tex"
        starter.write_text(starter.read_text() + "% source edited after loading\n")
        with self.assertRaisesRegex(ValueError, "fingerprint drift"):
            registry.resolve_recipe("general", root=root, catalog=catalog)

    def test_build_contract_and_theme_asset_shape_rejections(self):
        self.invalid(lambda data: data["templates"][0]["build_defaults"].append(["SHELL", "execute"]), "unknown build default")
        self.invalid(lambda data: data["themes"][3]["build_defaults"][1].__setitem__(1, "heavy"), "invalid build default")
        self.invalid(lambda data: data["themes"][3]["caption_contract"].update(label_color="bad"), "six hexadecimal")
        self.invalid(lambda data: data["themes"][0].update(asset_path=[]), "literal string")
        self.invalid(lambda data: data.update(language_contract="local-language-table"), "ownership cannot be redefined")

    def test_cli_queries_are_read_only_and_truthful(self):
        root = self.fixture()
        before = {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob("*") if p.is_file()}
        for command in (("validate", "--json"), ("list", "--json"), ("resolve", "--kind", "paper", "--language", "english")):
            result = subprocess.run([sys.executable, str(ROOT / "scripts/template_registry.py"), *command, "--root", str(root)], check=True, text=True, capture_output=True, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
            self.assertIsInstance(json.loads(result.stdout), dict)
        after = {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob("*") if p.is_file()}
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
