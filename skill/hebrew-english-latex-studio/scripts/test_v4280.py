#!/usr/bin/env python3
"""Portable release names and build startup failure controls (no TeX engine)."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
from check_package_hygiene import validate
from clean_harness_artifacts import sweep
from font_paths import font_dir

ROOT = Path(__file__).resolve().parent.parent


class PortableNames(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="hllpdf428-names-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def check_name(self, name: str, bad: bool = True):
        p = self.root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("source", encoding="utf-8")
        errors = validate(self.root)
        p.unlink()
        if bad:
            self.assertTrue(any("nonportable path" in e for e in errors), (name, errors))
        else:
            self.assertEqual(errors, [], (name, errors))

    def test_01_reserved_device_names_including_extensions(self):
        for name in ("CON", "con.txt", "PrN.md", "AUX.tex", "NUL", "COM1.md", "LPT9", "COM¹.md", "LPT²", "LPT³.txt"):
            with self.subTest(name=name):
                self.check_name(name)

    def test_02_reserved_characters(self):
        for ch in '<>:"\\|?*':
            with self.subTest(character=ch):
                self.check_name(f"a{ch}b.txt")

    def test_03_trailing_period_or_space(self):
        for name in ("source.", "source ", "source.txt. "):
            with self.subTest(name=name):
                self.check_name(name)

    def test_04_directory_components_are_checked(self):
        (self.root / "NUL").mkdir()
        (self.root / "NUL" / "valid.txt").write_text("source")
        self.assertTrue(any("reserved device name" in e for e in validate(self.root)))

    def test_05_valid_unicode_and_near_matches(self):
        for name in ("עברית.tex", "café.md", "CONnection.txt", "COM10.md", "LPT0.txt", ".hidden", "space inside.md"):
            with self.subTest(name=name):
                self.check_name(name, bad=False)

    def test_06_missing_or_file_root_is_not_clean(self):
        self.assertTrue(validate(self.root / "absent"))
        f = self.root / "file"; f.write_text("source")
        self.assertTrue(validate(f))

    def test_07_cleanup_does_not_delete_nonportable_sources(self):
        d = self.root / "assets"; d.mkdir()
        f = d / "CON.txt"; f.write_text("preserve this source")
        self.assertEqual(sweep(self.root), [])
        self.assertTrue(f.is_file())
        self.assertTrue(validate(self.root))


class BuildStartup(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="hllpdf428-start-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.bin = self.root / "bin"; self.bin.mkdir()
        self.project = self.root / "project with spaces"; self.project.mkdir()
        self.tex = self.project / "doc.tex"
        self.tex.write_text("\\documentclass{article}\n\\begin{document}Test.\\end{document}\n")
        self.pdf = self.project / "doc.pdf"; self.pdf.write_bytes(b"previous deliverable")
        self.calls = self.root / "calls.txt"
        self.mock("mkdir", '#!/bin/sh\nprintf "mkdir:%s\\n" "$*" >> "$CALLS"\nexit 1\n')
        self.mock("lualatex", '#!/bin/sh\nprintf "engine\\n" >> "$CALLS"\nexit 99\n')
        self.env = {k: v for k, v in os.environ.items() if k not in {
            "HEBREW_LATEX_PROJECT_ROOT", "DIRECT_NAVIGATION_DESTINATIONS", "REPRO",
            "CONTENT_PROFILE", "EXPECTED_PAPER", "SECTION_MACROS", "PDF_REQUIRE_TITLE",
            "PDF_MIN_BOOKMARKS", "PDF_MIN_BOOKMARK_DEPTH", "PDF_WARN_NO_OUTLINE_AFTER",
            "MAX_CROSS_PAGE_DESTINATIONS"}}
        self.env.update(PATH=f"{self.bin}:{os.environ['PATH']}", CALLS=str(self.calls),
                        HEBREW_LATEX_FONT_DIR=str(font_dir()))

    def mock(self, name: str, body: str):
        f = self.bin / name; f.write_text(body); f.chmod(0o755)

    def run_build(self, allocator: str, navigation: str | None = None):
        self.mock("mktemp", '#!/bin/sh\nprintf "allocator\\n" >> "$CALLS"\n' + allocator)
        env = self.env.copy()
        if navigation is not None:
            env["DIRECT_NAVIGATION_DESTINATIONS"] = navigation
        p = subprocess.run(["bash", str(ROOT / "scripts/build.sh"), str(self.tex)],
                           env=env, text=True, capture_output=True, timeout=120)
        calls = self.calls.read_text() if self.calls.exists() else ""
        self.assertEqual(self.pdf.read_bytes(), b"previous deliverable")
        self.assertNotIn("engine", calls, p.stdout + p.stderr)
        return p, calls

    def test_08_failed_allocator_stops_before_path_derivation(self):
        p, calls = self.run_build('echo "simulated allocation failure" >&2\nexit 1\n')
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
        self.assertEqual(calls, "allocator\n")
        self.assertIn("cannot create private build directory", p.stdout)

    def test_09_success_without_a_path_is_rejected(self):
        p, calls = self.run_build("exit 0\n")
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
        self.assertEqual(calls, "allocator\n")
        self.assertIn("no usable directory", p.stdout)

    def test_10_nonexistent_allocator_path_is_rejected(self):
        self.env["ALLOCATED"] = str(self.root / "absent")
        p, calls = self.run_build('printf "%s\\n" "$ALLOCATED"\n')
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
        self.assertEqual(calls, "allocator\n")
        self.assertIn("no usable directory", p.stdout)

    def test_11_valid_path_with_spaces_reaches_private_cache(self):
        d = self.root / "valid scratch path"; d.mkdir()
        self.env["ALLOCATED"] = str(d)
        p, calls = self.run_build('printf "%s\\n" "$ALLOCATED"\n')
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
        self.assertIn(f"mkdir:{d}/font-cache", calls)
        self.assertNotIn("mkdir:/font-cache", calls)
        self.assertIn("cannot create private font cache", p.stdout)

    def test_12_trailing_empty_navigation_field_fails_early(self):
        p, calls = self.run_build("exit 1\n", "landing-*,")
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
        self.assertIn("non-empty destination globs", p.stdout)
        self.assertEqual(calls, "")

    def test_13_other_empty_navigation_fields_still_fail(self):
        for value in (",landing-*", "landing-*,,toc-*", "landing-*,  "):
            with self.subTest(value=value):
                p, calls = self.run_build("exit 1\n", value)
                self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
                self.assertEqual(calls, "")
                self.assertIn("non-empty destination globs", p.stdout)

    def test_14_valid_navigation_contract_is_not_rejected(self):
        p, calls = self.run_build("exit 1\n", " landing-* , toc-? ")
        self.assertEqual(p.returncode, 2, p.stdout + p.stderr)
        self.assertEqual(calls, "allocator\n")
        self.assertIn("cannot create private build directory", p.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
