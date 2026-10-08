#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Original project code; scope and terms: ../LICENSING.md.
"""Unit tests for conservative preflight resolution and .fls truth."""

from __future__ import annotations

import sys as _bytecode_sys
_bytecode_sys.dont_write_bytecode = True

import contextlib
import io
from pathlib import Path
import tempfile
import unittest

import collect_fls_sources
import hash_project_inputs
import resolve_tex_sources


class SourceGraphTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def resolved(self, root):
        deps, errors = resolve_tex_sources.resolve(root, self.root)
        return {(d.kind, d.path) for d in deps}, errors

    def test_primitive_input_uses_build_root(self):
        main = self.write("main.tex", r"\input{sub/a}")
        self.write("sub/a.tex", r"\input{b}")
        actual = self.write("b.tex", "ROOT")
        self.write("sub/b.tex", "WRONG")
        deps, errors = self.resolved(main)
        self.assertFalse(errors)
        self.assertIn(("tex", actual), deps)
        self.assertNotIn(("tex", self.root / "sub/b.tex"), deps)

    def test_import_family_uses_including_directory(self):
        main = self.write("main.tex", r"\import{sub/}{a}")
        nested = self.write("sub/a.tex", r"\subimport{deep/}{b}")
        leaf = self.write("sub/deep/b.tex", "ok")
        deps, errors = self.resolved(main)
        self.assertFalse(errors)
        self.assertTrue({("tex", nested), ("tex", leaf)} <= deps)

    def test_plain_input_inside_import_uses_active_import_path(self):
        main = self.write("main.tex", r"\import{sub/}{a}")
        imported = self.write("sub/a.tex", r"\input{b}")
        leaf = self.write("sub/b.tex", "IMPORTED")
        self.write("b.tex", "ROOT")
        deps, errors = self.resolved(main)
        self.assertFalse(errors)
        self.assertTrue({("tex", imported), ("tex", leaf)} <= deps)
        self.assertNotIn(("tex", self.root / "b.tex"), deps)

    def test_subfile_children_use_the_subfile_directory_before_cwd(self):
        for command in ("subfile", "subfileinclude"):
            with self.subTest(command=command):
                main = self.write("document/main.tex", fr"\{command}{{parts/child}}")
                child = self.write("document/parts/child.tex", r"\input{leaf}")
                leaf = self.write("document/parts/leaf.tex", "EXPECTED")
                self.write("document/leaf.tex", "WRONG CWD")
                self.write("parts/child.tex", "WRONG TRUST ROOT")
                self.write("leaf.tex", "WRONG TRUST ROOT")
                deps, errors = self.resolved(main)
                self.assertFalse(errors)
                self.assertEqual(deps, {("tex", main), ("tex", child), ("tex", leaf)})

    def test_nested_subfiles_extend_the_active_subfile_directory(self):
        main = self.write("main.tex", r"\subfile{parts/child}")
        child = self.write("parts/child.tex", r"\subfile{deep/grandchild}")
        grandchild = self.write("parts/deep/grandchild.tex", r"\input{leaf}")
        leaf = self.write("parts/deep/leaf.tex", "EXPECTED")
        self.write("deep/grandchild.tex", "WRONG CWD")
        self.write("parts/leaf.tex", "WRONG PARENT")
        self.write("leaf.tex", "WRONG CWD")
        deps, errors = self.resolved(main)
        self.assertFalse(errors)
        self.assertEqual(deps, {("tex", path) for path in (main, child, grandchild, leaf)})

    def test_subfile_under_import_uses_active_import_not_callsite_directory(self):
        main = self.write("main.tex", r"\import{outer/}{parent}")
        parent = self.write("outer/parent.tex", r"\input{nested/caller}")
        caller = self.write("outer/nested/caller.tex", r"\subfile{sub/child}")
        child = self.write("outer/sub/child.tex", r"\input{leaf}")
        leaf = self.write("outer/sub/leaf.tex", "EXPECTED")
        self.write("outer/nested/sub/child.tex", "WRONG CALLSITE DIRECTORY")
        self.write("sub/child.tex", "WRONG CWD")
        deps, errors = self.resolved(main)
        self.assertFalse(errors)
        self.assertEqual(deps, {("tex", path) for path in (main, parent, caller, child, leaf)})

    def test_subfile_children_fall_back_to_prior_import_then_compilation_directory(self):
        main = self.write("document/main.tex", r"\subfile{parts/child}")
        child = self.write("document/parts/child.tex", r"\subfile{deep/grandchild}")
        grandchild = self.write("document/parts/deep/grandchild.tex", r"\input{leaf}")
        parent_leaf = self.write("document/parts/leaf.tex", "PARENT FALLBACK")
        cwd_leaf = self.write("document/leaf.tex", "CWD FALLBACK")
        self.write("leaf.tex", "WRONG TRUST ROOT")
        deps, errors = self.resolved(main)
        self.assertFalse(errors)
        self.assertEqual(deps, {("tex", path) for path in (main, child, grandchild, parent_leaf)})
        parent_leaf.unlink()
        deps, errors = self.resolved(main)
        self.assertFalse(errors)
        self.assertEqual(deps, {("tex", path) for path in (main, child, grandchild, cwd_leaf)})

    def test_subfile_explicit_target_does_not_fall_back_to_cwd(self):
        main = self.write("main.tex", r"\import{outer/}{parent}")
        parent = self.write("outer/parent.tex", r"\subfile{missing}")
        self.write("missing.tex", "WRONG CWD DECOY")
        deps, errors = self.resolved(main)
        self.assertEqual(deps, {("tex", main), ("tex", parent)})
        self.assertEqual(errors, [f"missing tex source: {self.root / 'outer/missing.tex'}"])

    def test_subfile_missing_child_dependency_does_not_use_trust_root_decoy(self):
        main = self.write("document/main.tex", r"\subfile{parts/child}")
        child = self.write("document/parts/child.tex", r"\input{missing}")
        self.write("missing.tex", "WRONG TRUST ROOT")
        deps, errors = self.resolved(main)
        self.assertEqual(deps, {("tex", main), ("tex", child)})
        self.assertEqual(errors, [f"missing tex source: {self.root / 'document/parts/missing.tex'}"])

    def test_subfile_child_listing_uses_active_subfile_directory(self):
        main = self.write("main.tex", r"\subfile{parts/child}")
        child = self.write("parts/child.tex", r"\lstinputlisting{code.py}")
        listing = self.write("parts/code.py", "EXPECTED")
        self.write("code.py", "WRONG CWD")
        deps, errors = self.resolved(main)
        self.assertFalse(errors)
        self.assertEqual(deps, {("tex", main), ("tex", child), ("literal", listing)})

    def test_subfileinclude_preserves_include_extension_rules(self):
        main = self.write("main.tex", r"\subfileinclude{parts/child.sty}")
        child = self.write("parts/child.sty.tex", "EXPECTED")
        self.write("parts/child.sty", "WRONG EXACT FILE")
        deps, errors = self.resolved(main)
        self.assertFalse(errors)
        self.assertEqual(deps, {("tex", main), ("tex", child)})

    def test_subfile_invalid_and_escaping_paths_are_rejected(self):
        for command in ("subfile", "subfileinclude"):
            for argument in (r"\dynamic", "../outside", "parts/"):
                with self.subTest(command=command, argument=argument):
                    main = self.write("main.tex", fr"\{command}{{{argument}}}")
                    deps, errors = self.resolved(main)
                    self.assertEqual(deps, {("tex", main)})
                    self.assertEqual(len(errors), 1)
                    self.assertIn("cannot resolve", errors[0])

    def test_subfile_preferred_target_symlink_escape_is_rejected(self):
        with tempfile.TemporaryDirectory() as external:
            outside = Path(external) / "outside.tex"
            outside.write_text("OUTSIDE", encoding="utf-8")
            main = self.write("main.tex", r"\subfile{parts/child.v1}")
            self.write("parts/child.v1", "SAFE BUT NOT SELECTED")
            (self.root / "parts/child.v1.tex").symlink_to(outside)
            deps, errors = self.resolved(main)
            self.assertEqual(deps, {("tex", main)})
            self.assertEqual(len(errors), 1)
            self.assertIn("dependency escapes project root", errors[0])

    def test_subfile_target_symlink_keeps_literal_argument_directory(self):
        main = self.write("main.tex", r"\subfile{parts/child}")
        actual = self.write("elsewhere/actual.tex", r"\input{leaf}")
        leaf = self.write("parts/leaf.tex", "EXPECTED LITERAL DIRECTORY")
        (self.root / "parts/child.tex").symlink_to(actual)
        self.write("elsewhere/leaf.tex", "WRONG SYMLINK TARGET DIRECTORY")
        self.write("leaf.tex", "WRONG CWD")
        deps, errors = self.resolved(main)
        self.assertFalse(errors)
        self.assertEqual(deps, {("tex", main), ("tex", actual), ("tex", leaf)})

    def test_subfile_cycle_preserves_finite_import_context(self):
        main = self.write("main.tex", r"\subfile{parts/child}")
        child = self.write("parts/child.tex", r"\subfile{../main}")
        deps, errors = resolve_tex_sources.resolve(main, self.root)
        self.assertFalse(errors)
        self.assertEqual({dep.path for dep in deps}, {main, child})
        self.assertLessEqual(len(deps), 4)

    def test_nested_subimport_falls_back_through_parent_import_path(self):
        main = self.write("main.tex", r"\import{sub/}{a}")
        self.write("sub/a.tex", r"\subimport{deep/}{c}")
        self.write("sub/deep/c.tex", r"\input{b}")
        parent = self.write("sub/b.tex", "PARENT")
        self.write("b.tex", "ROOT")
        deps, errors = self.resolved(main)
        self.assertFalse(errors)
        self.assertIn(("tex", parent), deps)
        self.assertNotIn(("tex", self.root / "b.tex"), deps)

    def test_nested_main_imports_use_compilation_directory_not_trust_boundary(self):
        for command in ("import", "inputfrom", "includefrom"):
            with self.subTest(command=command):
                main = self.write("document/main.tex", fr"\{command}{{parts/}}{{a}}")
                part = self.write("document/parts/a.tex", r"\input{fallback}")
                fallback = self.write("document/fallback.tex", "EXPECTED")
                self.write("parts/a.tex", "WRONG TRUST-ROOT IMPORT")
                self.write("fallback.tex", "WRONG TRUST-ROOT FALLBACK")
                deps, errors = self.resolved(main)
                self.assertFalse(errors)
                self.assertEqual(deps, {("tex", main), ("tex", part),
                                        ("tex", fallback)})

    def test_nested_main_import_missing_source_does_not_use_trust_root_file(self):
        main = self.write("document/main.tex", r"\import{parts/}{missing}")
        self.write("parts/missing.tex", "WRONG")
        deps, errors = self.resolved(main)
        self.assertEqual(deps, {("tex", main)})
        self.assertEqual(errors, [f"missing tex source: {self.root / 'document/parts/missing.tex'}"])

    def test_nested_top_level_import_keeps_previous_input_fallbacks(self):
        main = self.write("document/main.tex", r"\import{outer/}{parent}")
        parent = self.write("document/outer/parent.tex", r"\import{child/}{leaf}")
        leaf = self.write("document/child/leaf.tex", r"\input{shared}")
        shared = self.write("document/outer/shared.tex", "EXPECTED")
        deps, errors = self.resolved(main)
        self.assertFalse(errors)
        self.assertEqual(deps, {("tex", path) for path in (main, parent, leaf, shared)})

    def test_repeated_top_level_import_cycle_has_finite_search_context(self):
        main = self.write("document/main.tex", r"\import{outer/}{a}")
        a = self.write("document/outer/a.tex", r"\import{inner/}{b}")
        b = self.write("document/inner/b.tex", r"\import{outer/}{a}")
        deps, errors = resolve_tex_sources.resolve(main, self.root)
        self.assertFalse(errors)
        self.assertEqual({dep.path for dep in deps}, {main, a, b})
        self.assertLessEqual(len(deps), 4)

    def test_valid_import_relative_input_does_not_validate_unused_escaping_fallback(self):
        main = self.write("main.tex", r"\import{parts/}{a}")
        part = self.write("parts/a.tex", r"\input{../shared}")
        shared = self.write("shared.tex", "EXPECTED")
        deps, errors = self.resolved(main)
        self.assertFalse(errors)
        self.assertEqual(deps, {("tex", main), ("tex", part), ("tex", shared)})

    def test_dotted_input_names_prefer_appended_tex_and_follow_its_dependencies(self):
        for command in ("input", "include", "subfile"):
            with self.subTest(command=command):
                main = self.write("main.tex", fr"\{command}{{chapter.v1}}")
                preferred = self.write("chapter.v1.tex", r"\input{leaf}")
                leaf = self.write("leaf.tex", "EXPECTED")
                self.write("chapter.v1", r"\input{wrong-raw-dependency}")
                deps, errors = self.resolved(main)
                self.assertFalse(errors)
                self.assertEqual(deps, {("tex", main), ("tex", preferred), ("tex", leaf)})

    def test_input_unknown_extensions_and_extensionless_names_allow_exact_fallback(self):
        for name in ("chapter.v2", "chapter"):
            with self.subTest(name=name):
                main = self.write("main.tex", r"\input{" + name + "}")
                exact = self.write(name, "EXPECTED")
                deps, errors = self.resolved(main)
                self.assertFalse(errors)
                self.assertEqual(deps, {("tex", main), ("tex", exact)})

    def test_input_known_tex_extensions_remain_exact_and_do_not_fallback(self):
        for suffix in ("tex", "sty", "cls", "fd", "aux", "bbl", "def", "clo", "ldf"):
            with self.subTest(suffix=suffix):
                name = "exact." + suffix
                main = self.write("main.tex", r"\input{" + name + "}")
                exact = self.write(name, "EXPECTED")
                self.write(name + ".tex", "WRONG APPENDED FILE")
                deps, errors = self.resolved(main)
                self.assertFalse(errors)
                self.assertEqual(deps, {("tex", main), ("tex", exact)})
                exact.unlink()
                deps, errors = self.resolved(main)
                self.assertEqual(deps, {("tex", main)})
                self.assertEqual(errors, [f"missing tex source: {exact}"])

    def test_include_extensions_append_tex_unless_already_tex(self):
        for name in ("chapter.sty", "chapter.v3", "chapter"):
            with self.subTest(name=name):
                main = self.write("main.tex", r"\include{" + name + "}")
                exact = self.write(name, "WRONG RAW FILE")
                preferred = self.write(name + ".tex", "EXPECTED")
                deps, errors = self.resolved(main)
                self.assertFalse(errors)
                self.assertEqual(deps, {("tex", main), ("tex", preferred)})
                preferred.unlink()
                deps, errors = self.resolved(main)
                self.assertEqual(deps, {("tex", main)})
                self.assertEqual(errors, [f"missing tex source: {preferred}"])

    def test_import_family_preserves_input_and_include_extension_rules(self):
        for command in ("import", "subimport", "inputfrom", "subinputfrom",
                        "includefrom", "subincludefrom"):
            for name in ("chapter.v4", "chapter.sty"):
                with self.subTest(command=command, name=name):
                    main = self.write("main.tex", fr"\{command}{{parts/}}{{{name}}}")
                    raw = self.write("parts/" + name, "RAW")
                    appended = self.write("parts/" + name + ".tex", "APPENDED")
                    expected = raw if name.endswith(".sty") and "include" not in command else appended
                    deps, errors = self.resolved(main)
                    self.assertFalse(errors)
                    self.assertEqual(deps, {("tex", main), ("tex", expected)})

    def test_listing_dotted_names_never_add_tex_extension(self):
        main = self.write("main.tex", r"\lstinputlisting{chapter.v5}")
        literal = self.write("chapter.v5", "EXPECTED")
        self.write("chapter.v5.tex", "WRONG")
        deps, errors = self.resolved(main)
        self.assertFalse(errors)
        self.assertEqual(deps, {("tex", main), ("literal", literal)})

    def test_preferred_dotted_input_symlink_escape_is_rejected_without_safe_fallback(self):
        with tempfile.TemporaryDirectory() as external:
            outside = Path(external) / "outside.tex"
            outside.write_text("OUTSIDE", encoding="utf-8")
            main = self.write("main.tex", r"\input{chapter.v6}")
            self.write("chapter.v6", "SAFE BUT NOT SELECTED BY TEX")
            (self.root / "chapter.v6.tex").symlink_to(outside)
            deps, errors = self.resolved(main)
            self.assertEqual(deps, {("tex", main)})
            self.assertEqual(len(errors), 1)
            self.assertIn("dependency escapes project root", errors[0])

    def test_all_import_command_names(self):
        commands = (
            "import", "subimport", "inputfrom", "subinputfrom",
            "includefrom", "subincludefrom",
        )
        for command in commands:
            self.write(f"d/{command}.tex", "ok")
        main = self.write(
            "main.tex",
            "\n".join(fr"\{c}{{d/}}{{{c}}}" for c in commands),
        )
        deps, errors = self.resolved(main)
        self.assertFalse(errors)
        for command in commands:
            self.assertIn(("tex", self.root / f"d/{command}.tex"), deps)

    def dependency_command_cases(self):
        cases = [
            ("input", "input{leaf}", "tex", "leaf.tex"),
            ("bare-input", "input leaf", "tex", "leaf.tex"),
            ("include", "include{leaf}", "tex", "leaf.tex"),
            ("subfile", "subfile{leaf}", "tex", "leaf.tex"),
            ("subfileinclude", "subfileinclude{leaf}", "tex", "leaf.tex"),
            ("listing", "lstinputlisting[language=Python]{leaf.py}",
             "literal", "leaf.py"),
        ]
        cases.extend(
            (command, f"{command}{{d/}}{{leaf}}", "tex", "d/leaf.tex")
            for command in (
                "import", "subimport", "inputfrom", "subinputfrom",
                "includefrom", "subincludefrom",
            )
        )
        return cases

    def test_backslash_runs_follow_control_sequence_tokens(self):
        for name, command, kind, target in self.dependency_command_cases():
            leaf = self.write(target, "leaf")
            for count in (2, 3, 4):
                with self.subTest(command=name, backslashes=count):
                    body = "\\" * count + command
                    main = self.write("main.tex", body)
                    deps, errors = self.resolved(main)
                    self.assertFalse(errors)
                    expected = {("tex", main)}
                    if count == 3:
                        expected.add((kind, leaf))
                    self.assertEqual(deps, expected)
                    occurrences = resolve_tex_sources.dependency_occurrences(
                        main, self.root, (self.root,)
                    )
                    if count == 3:
                        self.assertEqual(len(occurrences), 1)
                        occurrence = occurrences[0]
                        self.assertEqual(occurrence.dependency.path, leaf)
                        self.assertEqual(occurrence.dependency.kind, kind)
                        self.assertEqual((occurrence.start, occurrence.end),
                                         (2, len(body)))
                    else:
                        self.assertEqual(occurrences, [])

    def test_real_command_after_linebreak_still_rejects_missing_sources(self):
        for name, command, _kind, _target in self.dependency_command_cases():
            with self.subTest(command=name):
                main = self.write("main.tex", "\\" * 3 + command)
                _deps, errors = self.resolved(main)
                self.assertEqual(len(errors), 1)
                self.assertIn("missing", errors[0])

    def test_literal_openers_obey_control_sequence_tokens(self):
        for command in ("verb|", "verb*|", "lstinline[language=TeX]|"):
            for count in (2, 3, 4):
                with self.subTest(command=command, backslashes=count):
                    main = self.write(
                        "main.tex", "\\" * count + command
                        + r"\input{missing}|",
                    )
                    _deps, errors = self.resolved(main)
                    self.assertEqual(bool(errors), count != 3)
        for count in (2, 3, 4):
            with self.subTest(environment="verbatim", backslashes=count):
                main = self.write(
                    "main.tex", "\\" * count + "begin{verbatim}"
                    + r"\input{missing}\end{verbatim}",
                )
                _deps, errors = self.resolved(main)
                self.assertEqual(bool(errors), count != 3)

    def test_extended_literal_command_names_do_not_hide_real_input(self):
        for command in (r"\verbx", r"\lstinlineX"):
            with self.subTest(command=command):
                main = self.write("main.tex", command + r" \input{missing}")
                _deps, errors = self.resolved(main)
                self.assertTrue(errors)

    def test_occurrences_preserve_lexical_order_repeated_calls_and_context(self):
        body = (
            "% \\input{ignored-comment}\n"
            "\\input{leaf}\n"
            "\\lstinputlisting{leaf.py}\n"
            "\\import{d/}{leaf}\n"
            "\\input leaf\n"
            "\\verb|\\input{ignored-literal}|\n"
        )
        main = self.write("main.tex", body)
        self.write("leaf.tex", "leaf")
        self.write("leaf.py", "literal")
        self.write("d/leaf.tex", "imported")
        occurrences = resolve_tex_sources.dependency_occurrences(
            main, self.root, (self.root,)
        )
        commands = [r"\input{leaf}", r"\lstinputlisting{leaf.py}",
                    r"\import{d/}{leaf}", r"\input leaf"]
        self.assertEqual(
            [(item.start, item.end) for item in occurrences],
            [(body.index(command), body.index(command) + len(command))
             for command in commands],
        )
        self.assertEqual(
            [item.dependency.path for item in occurrences],
            [self.root / "leaf.tex", self.root / "leaf.py",
             self.root / "d/leaf.tex", self.root / "leaf.tex"],
        )
        self.assertEqual(occurrences[2].dependency.import_paths,
                         (self.root / "d", self.root))
        # The existing graph helper retains its established family order.
        self.assertEqual(
            [item.path for item in resolve_tex_sources.dependencies(
                main, self.root, (self.root,)
            )],
            [self.root / "d/leaf.tex", self.root / "leaf.py",
             self.root / "leaf.tex", self.root / "leaf.tex"],
        )

    def test_occurrence_at_resolves_only_the_requested_actual_token(self):
        body = (
            r"\newcommand{\unused}{\input{\dynamic}}" + "\n"
            + "\\" * 2 + "input{missing}\n"
            + "\\" * 3 + "input{leaf}\n"
            + r"\input{\laterDynamic}"
        )
        main = self.write("main.tex", body)
        leaf = self.write("leaf.tex", "leaf")
        command_start = body.index("\\" * 3) + 2
        occurrence = resolve_tex_sources.dependency_occurrence_at(
            main, command_start, self.root, (self.root,)
        )
        self.assertIsNotNone(occurrence)
        self.assertEqual(occurrence.dependency.path, leaf)
        self.assertEqual(occurrence.start, command_start)
        # The second backslash of a control symbol is not a command start.
        escaped_start = body.index("\\" * 2 + "input{missing}") + 1
        self.assertIsNone(resolve_tex_sources.dependency_occurrence_at(
            main, escaped_start, self.root, (self.root,)
        ))
        # A dynamic path at the requested command remains unsafe.
        with self.assertRaisesRegex(ValueError, "dynamic path"):
            resolve_tex_sources.dependency_occurrence_at(
                main, body.index(r"\input{\laterDynamic}"),
                self.root, (self.root,),
            )

    def test_selective_lookup_preserves_outer_listing_argument_span(self):
        listing_command = r"\lstinputlisting[morekeywords={\input{missing}}]{demo.py}"
        following_command = r"\input{actual}"
        body = listing_command + "\n" + following_command
        main = self.write("main.tex", body)
        listing = self.write("demo.py", "literal")
        actual = self.write("actual.tex", "actual")
        deps, errors = self.resolved(main)
        self.assertFalse(errors)
        self.assertEqual(deps, {("tex", main), ("literal", listing), ("tex", actual)})
        occurrences = resolve_tex_sources.dependency_occurrences(
            main, self.root, (self.root,)
        )
        self.assertEqual([item.dependency.path for item in occurrences],
                         [listing, actual])
        self.assertIsNone(resolve_tex_sources.dependency_occurrence_at(
            main, body.index(r"\input{missing}"), self.root, (self.root,),
        ))
        outer = resolve_tex_sources.dependency_occurrence_at(
            main, 0, self.root, (self.root,),
        )
        self.assertEqual(outer.dependency.kind, "literal")
        self.assertEqual(outer.dependency.path, listing)
        self.assertEqual((outer.start, outer.end), (0, len(listing_command)))
        following = resolve_tex_sources.dependency_occurrence_at(
            main, body.index(following_command), self.root, (self.root,),
        )
        self.assertEqual(following.dependency.path, actual)

    def test_listing_metadata_reserves_all_nested_dependency_families(self):
        self.write("demo.py", "literal")
        actual = self.write("actual.tex", "actual")
        for name, command, _kind, _target in self.dependency_command_cases():
            with self.subTest(command=name):
                inner = "\\" + command
                listing_command = r"\lstinputlisting[morekeywords={" + inner + r"}]{demo.py}"
                body = listing_command + "\n" + r"\input{actual}"
                main = self.write("main.tex", body)
                deps, errors = self.resolved(main)
                self.assertFalse(errors)
                self.assertEqual(deps, {("tex", main),
                                       ("literal", self.root / "demo.py"),
                                       ("tex", actual)})
                self.assertIsNone(resolve_tex_sources.dependency_occurrence_at(
                    main, body.index(inner), self.root, (self.root,),
                ))
                self.assertEqual(
                    [item.dependency.path for item in
                     resolve_tex_sources.dependency_occurrences(
                         main, self.root, (self.root,)
                     )],
                    [self.root / "demo.py", actual],
                )

    def test_listing_option_closes_at_first_unprotected_bracket(self):
        listing = self.write("demo.py", "literal")
        actual = self.write("actual.tex", "actual")
        for options in (
            "morekeywords={a]b}",
            r"morekeywords=\{a\]b\}",
            "morekeywords=a[b",
            "morekeywords=a" + "\\" * 2,
        ):
            with self.subTest(options=options):
                listing_command = r"\lstinputlisting[" + options + "]{demo.py}"
                body = listing_command + "\n" + r"\input{actual}"
                main = self.write("main.tex", body)
                deps, errors = self.resolved(main)
                self.assertFalse(errors)
                self.assertEqual(deps, {("tex", main), ("literal", listing),
                                       ("tex", actual)})
                outer = resolve_tex_sources.dependency_occurrence_at(
                    main, 0, self.root, (self.root,),
                )
                self.assertEqual((outer.start, outer.end), (0, len(listing_command)))
                self.assertEqual(outer.dependency.path, listing)

    def test_one_line_literal_does_not_create_dependency(self):
        main = self.write(
            "main.tex",
            r"\begin{verbatim}\input{missing}\end{verbatim}",
        )
        deps, errors = self.resolved(main)
        self.assertFalse(errors)
        self.assertEqual(deps, {("tex", main)})

    def test_dependency_after_literal_end_on_same_line_is_seen(self):
        main = self.write(
            "main.tex",
            "\\begin{verbatim}\nignored\n\\end{verbatim}\\input{actual}",
        )
        actual = self.write("actual.tex", "tail")
        deps, errors = self.resolved(main)
        self.assertFalse(errors)
        self.assertIn(("tex", actual), deps)

    def test_spaced_literal_openers_mask_body_and_preserve_live_tail(self):
        leaf = self.write("leaf.tex", "leaf")
        for environment in ("verbatim", "lstlisting", "Verbatim"):
            for separator in (" ", "\n", "% opener comment\n"):
                with self.subTest(environment=environment, separator=separator):
                    body = ("\\begin" + separator + "{" + environment + "}\n"
                            + r"\input{missing}" + "\n"
                            + "\\end{" + environment + "}\n" + r"\input{leaf}")
                    main = self.write("main.tex", body)
                    deps, errors = self.resolved(main)
                    self.assertFalse(errors)
                    self.assertEqual(deps, {("tex", main), ("tex", leaf)})
                    self.assertIsNone(resolve_tex_sources.dependency_occurrence_at(
                        main, body.index(r"\input{missing}"), self.root, (self.root,),
                    ))
                    actual = resolve_tex_sources.dependency_occurrence_at(
                        main, body.index(r"\input{leaf}"), self.root, (self.root,),
                    )
                    self.assertEqual(actual.dependency.path, leaf)

    def test_math_and_tikz_environments_do_not_hide_dependencies(self):
        leaf = self.write("leaf.tex", "leaf")
        for environment in ("equation", "tikzpicture"):
            with self.subTest(environment=environment):
                main = self.write(
                    "main.tex", "\\begin{" + environment + "}"
                    + r"\input{leaf}" + "\\end{" + environment + "}",
                )
                deps, errors = self.resolved(main)
                self.assertFalse(errors)
                self.assertEqual(deps, {("tex", main), ("tex", leaf)})

    def test_inline_literal_commands_do_not_create_dependencies(self):
        main = self.write(
            "main.tex",
            "\n".join([
                r"\verb|\input{missing-a}|",
                r"\verb*+\input{missing-b}+",
                r"\lstinline[language=TeX]!\input{missing-c}!",
            ]),
        )
        deps, errors = self.resolved(main)
        self.assertFalse(errors)
        self.assertEqual(deps, {("tex", main)})

    def test_percent_inside_inline_literal_does_not_hide_tail(self):
        main = self.write(
            "main.tex",
            r"\verb|%|\input{resolver_percent_tail}",
        )
        tail = self.write("resolver_percent_tail.tex", "tail")
        deps, errors = self.resolved(main)
        self.assertFalse(errors)
        self.assertIn(("tex", tail), deps)

    def test_real_input_after_inline_literal_delimiters_is_preserved(self):
        literal_prefixes = (
            r"\verb{literal{",
            r"\verb*{literal{",
            r"\lstinline{{literal}",
            r"\lstinline*literal*",
            r"\lstinline[language=Python]{literal}",
            r"\verb|literal\|",
            r"\lstinline|literal\|",
            r"\verb[\input[",
        )
        leaf = self.write("leaf.tex", "leaf")
        for prefix in literal_prefixes:
            with self.subTest(literal=prefix):
                body = prefix + r" \input{leaf}"
                main = self.write("main.tex", body)
                deps, errors = self.resolved(main)
                self.assertFalse(errors)
                self.assertEqual(deps, {("tex", main), ("tex", leaf)})
                occurrence = resolve_tex_sources.dependency_occurrence_at(
                    main, body.rindex(r"\input{leaf}"), self.root, (self.root,),
                )
                self.assertEqual(occurrence.dependency.path, leaf)
        for unsafe in ("missing", "../outside", r"\dynamic"):
            with self.subTest(unsafe=unsafe):
                main = self.write("main.tex", r"\verb{literal{ \input{" + unsafe + "}")
                _deps, errors = self.resolved(main)
                self.assertTrue(errors)

    def test_listing_is_literal_not_tex(self):
        main = self.write("main.tex", r"\lstinputlisting{src/demo.py}")
        listing = self.write("src/demo.py", r"\input{not-tex}")
        deps, errors = self.resolved(main)
        self.assertFalse(errors)
        self.assertIn(("literal", listing), deps)
        self.assertEqual(sum(kind == "tex" for kind, _ in deps), 1)

    def test_escape_and_dynamic_paths_fail(self):
        outside = self.root.parent / "outside.tex"
        outside.write_text("x", encoding="utf-8")
        for body in (r"\input{../outside}", r"\input{\jobname}"):
            main = self.write("main.tex", body)
            _deps, errors = self.resolved(main)
            self.assertTrue(errors)

    def test_cycle_is_finite(self):
        main = self.write("main.tex", r"\input{a}")
        self.write("a.tex", r"\input{main}")
        deps, errors = self.resolved(main)
        self.assertFalse(errors)
        self.assertEqual(len(deps), 2)

    def test_fls_filters_to_project_text(self):
        main = self.write("main.tex", "ok")
        code = self.write("src/demo.py", "print('ok')")
        self.write("image.png", "not really png")
        fls = self.write(
            "build/doc.fls",
            "\n".join([
                f"INPUT {main}",
                f"INPUT {code}",
                f"INPUT {self.root / 'image.png'}",
                "INPUT /usr/share/texmf/system.sty",
            ]),
        )
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = collect_fls_sources.main([
                "collect_fls_sources.py", str(fls),
                "--project-root", str(self.root),
                "--allow-root", "/usr/share/texmf",
            ])
        self.assertEqual(rc, 0)
        self.assertEqual(set(out.getvalue().splitlines()), {str(main), str(code)})

    def test_project_input_hash_is_order_and_checkout_independent(self):
        a = self.write("src/a.tex", "alpha")
        b = self.write("fig/b.bin", "beta")
        m1 = self.write("m1.txt", f"{b}\n{a}\n{a}\n")
        m2 = self.write("m2.txt", f"{a}\n{b}\n")
        h1 = hash_project_inputs.manifest_hash(m1, self.root)
        h2 = hash_project_inputs.manifest_hash(m2, self.root)
        self.assertEqual(h1, h2)

        # Same relative paths+bytes under another checkout name hash identically.
        other_parent = Path(tempfile.mkdtemp())
        try:
            other = other_parent / "renamed-checkout"
            (other / "src").mkdir(parents=True)
            (other / "fig").mkdir()
            (other / "src/a.tex").write_text("alpha", encoding="utf-8")
            (other / "fig/b.bin").write_text("beta", encoding="utf-8")
            om = other / "manifest.txt"
            om.write_text(f"{other / 'fig/b.bin'}\n{other / 'src/a.tex'}\n", encoding="utf-8")
            self.assertEqual(h1, hash_project_inputs.manifest_hash(om, other))
            (other / "fig/b.bin").write_text("changed", encoding="utf-8")
            self.assertNotEqual(h1, hash_project_inputs.manifest_hash(om, other))
        finally:
            __import__("shutil").rmtree(other_parent)

    def test_fls_project_all_includes_binary_project_inputs(self):
        main = self.write("main.tex", "ok")
        image = self.root / "figure.png"
        image.write_bytes(b"not-really-a-png")
        fls = self.write(
            "build/doc.fls",
            f"INPUT {main}\nINPUT {image}\n",
        )
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = collect_fls_sources.main([
                "collect_fls_sources.py", str(fls),
                "--project-root", str(self.root),
                "--mode", "project-all",
            ])
        self.assertEqual(rc, 0)
        self.assertEqual(set(out.getvalue().splitlines()), {str(main), str(image)})

    def test_fls_rejects_forbidden_prior_output_even_when_pdf(self):
        main = self.write("main.tex", "ok")
        prior = self.root / "main.pdf"
        prior.write_bytes(b"%PDF-1.4\n%%EOF\n")
        fls = self.write(
            "build/doc.fls",
            f"INPUT {main}\nINPUT {prior}\n",
        )
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            rc = collect_fls_sources.main([
                "collect_fls_sources.py", str(fls),
                "--project-root", str(self.root),
                "--forbid-input", str(prior),
            ])
        self.assertEqual(rc, 1)
        self.assertIn("forbidden prior-build input", err.getvalue())

    def test_fls_rejects_untrusted_external_input(self):
        main = self.write("main.tex", "ok")
        fls = self.write(
            "build/doc.fls",
            f"INPUT {main}\nINPUT /etc/passwd\n",
        )
        with contextlib.redirect_stderr(io.StringIO()):
            rc = collect_fls_sources.main([
                "collect_fls_sources.py", str(fls),
                "--project-root", str(self.root),
            ])
        self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
