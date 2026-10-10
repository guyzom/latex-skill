#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Original project code; scope and terms: ../LICENSING.md.
"""Regression tests for the doctor and portable maintenance tools."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
sys.dont_write_bytecode = True
import tempfile
from unittest import mock

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
sys.path.insert(0, str(HERE))
from architecture_contract import maintenance_sync_basenames  # noqa: E402
import doctor  # noqa: E402
from font_paths import font_dir
HASH = HERE / "hash_file.py"
SYNC = HERE / "sync_preamble.sh"
SETUP_FONTS = HERE / "setup_fonts.sh"
ATOMIC = HERE / "atomic_replace.py"


def run_doctor_dependency_tests() -> None:
    """Reject missing Lua runtime, core, reference-starter and index dependencies."""
    completed = subprocess.CompletedProcess([], 0, "", "")
    for missing in (
        "lualibs.lua", "lua-uni-case.lua", "lua-uni-normalize.lua", "lua-uni-parse.lua",
        "ctablestack.sty", "caption.sty", "colortbl.sty", "imakeidx.sty",
    ):
        with (
            mock.patch.object(doctor.shutil, "which", return_value="/mock/tool"),
            mock.patch.object(
                doctor,
                "_kpsewhich",
                side_effect=lambda name: "" if name == missing else "/mock/tex-file",
            ),
            mock.patch.object(doctor.subprocess, "run", return_value=completed),
        ):
            errors = doctor._check_toolchain()
        assert errors == [f"TeX dependency not found: {missing}"], errors

    with (
        mock.patch.object(doctor.shutil, "which", return_value="/mock/tool"),
        mock.patch.object(doctor, "_kpsewhich", return_value="/mock/tex-file"),
        mock.patch.object(doctor.subprocess, "run", return_value=completed),
    ):
        errors = doctor._check_toolchain()
    assert errors == [], errors

    # FAST preflight must remain usable without a live TeX installation.
    with (
        mock.patch.object(doctor, "_check_qa", return_value=[]),
        mock.patch.object(doctor, "_check_toolchain", side_effect=AssertionError("TeX probe in QA-only mode")),
        mock.patch("builtins.print"),
    ):
        assert doctor.main(["--qa-only"]) == 0


def run_hash_test(root: Path) -> None:
    p = root / "sample.bin"
    p.write_bytes(b"hebrew-lualatex-pdf\x00portable\n")
    expected = hashlib.sha256(p.read_bytes()).hexdigest()
    proc = subprocess.run(["python3", str(HASH), str(p)], text=True, capture_output=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert proc.stdout.strip() == expected, proc.stdout



def run_atomic_replace_tests(root: Path) -> None:
    source = root / "verified.pdf"
    source.write_bytes(b"verified bytes\n")
    external = root / "outside.txt"
    external.write_bytes(b"must stay unchanged\n")
    destination = root / "doc.pdf"
    destination.symlink_to(external)
    proc = subprocess.run(
        ["python3", str(ATOMIC), str(source), str(destination)],
        text=True, capture_output=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert not destination.is_symlink(), "destination symlink was followed instead of replaced"
    assert destination.read_bytes() == source.read_bytes()
    assert external.read_bytes() == b"must stay unchanged\n"
    assert not list(root.glob(".doc.pdf.tmp.*")), "atomic stage leaked beside destination"

    missing_parent = root / "absent" / "doc.pdf"
    proc = subprocess.run(
        ["python3", str(ATOMIC), str(source), str(missing_parent)],
        text=True, capture_output=True,
    )
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert not missing_parent.parent.exists(), "failed atomic publish created a destination directory"



def run_font_setup_symlink_test(root: Path) -> None:
    fontdir = root / "installed-fonts"
    fontdir.mkdir()
    external = root / "external-sentinel.ttf"
    external.write_bytes(b"outside must stay unchanged\n")
    link = fontdir / "Heebo-Regular.ttf"
    link.symlink_to(external)
    mock_bin = root / "font-tools-bin"
    mock_bin.mkdir()
    for name in ("fc-cache", "luaotfload-tool"):
        tool = mock_bin / name
        tool.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        tool.chmod(0o755)
    env = __import__("os").environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PATH"] = f"{mock_bin}:{env['PATH']}"
    proc = subprocess.run(
        ["bash", str(SETUP_FONTS), str(fontdir)],
        text=True, capture_output=True, env=env, timeout=120,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert not link.is_symlink(), "font installer followed an existing symlink"
    assert external.read_bytes() == b"outside must stay unchanged\n"
    assert link.read_bytes() == (font_dir() / "Heebo-Regular.ttf").read_bytes()


def make_fake_repo(root: Path, with_collection: bool) -> tuple[Path, Path | None]:
    # Build a standalone skill-shaped copy; fleet root is supplied explicitly.
    skill = root / "tools" / "hebrew-lualatex-pdf"
    (skill / "scripts").mkdir(parents=True)
    (skill / "assets").mkdir()
    shutil.copy2(SYNC, skill / "scripts" / "sync_preamble.sh")
    shutil.copy2(HASH, skill / "scripts" / "hash_file.py")
    shutil.copy2(ATOMIC, skill / "scripts" / "atomic_replace.py")
    shutil.copy2(HERE / "architecture_contract.py", skill / "scripts" / "architecture_contract.py")
    for name in maintenance_sync_basenames():
        shutil.copy2(SKILL / "assets" / name, skill / "assets" / name)
    if not with_collection:
        return skill, None
    coll = root / "course-a" / "src"
    coll.mkdir(parents=True)
    for name in maintenance_sync_basenames():
        (coll / name).write_text(f"stale {name}\n", encoding="utf-8")
    (coll / "build.sh").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    return skill, coll


def run_sync_tests(root: Path) -> None:
    skill, _ = make_fake_repo(root / "empty", with_collection=False)
    script = skill / "scripts" / "sync_preamble.sh"
    # A standalone/non-git package must not guess ../../.. as a fleet root.
    proc = subprocess.run(["bash", str(script)], text=True, capture_output=True)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "cannot determine fleet root" in (proc.stdout + proc.stderr), proc.stdout + proc.stderr
    # A destructive fleet operation must never accept the filesystem root.
    proc = subprocess.run(["bash", str(script), "--root", "/"],
                          text=True, capture_output=True)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "refusing filesystem root" in (proc.stdout + proc.stderr), proc.stdout + proc.stderr

    # Even an explicit root with zero carriers is not a vacuous green result.
    proc = subprocess.run(["bash", str(script), "--root", str(root / "empty")],
                          text=True, capture_output=True)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "no collection copies found" in (proc.stdout + proc.stderr), proc.stdout + proc.stderr
    # Typos in a maintenance command are configuration errors, never report mode.
    proc = subprocess.run(["bash", str(script), "--aply"], text=True, capture_output=True)
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "unknown argument" in (proc.stdout + proc.stderr), proc.stdout + proc.stderr

    # --apply is two-phase: a missing canonical layer is detected BEFORE any
    # carrier is modified.  The old one-pass loop could update preamble first
    # and then die when a later canonical layer was missing.
    partial_skill, partial_coll = make_fake_repo(root / "partial", with_collection=True)
    assert partial_coll is not None
    partial_script = partial_skill / "scripts" / "sync_preamble.sh"
    before = (partial_coll / "preamble.tex").read_bytes()
    (partial_skill / "assets" / "exam_components.tex").unlink()
    proc = subprocess.run(
        ["bash", str(partial_script), "--root", str(root / "partial"), "--apply"],
        text=True, capture_output=True,
    )
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "asset not found" in (proc.stdout + proc.stderr), proc.stdout + proc.stderr
    assert (partial_coll / "preamble.tex").read_bytes() == before, proc.stdout + proc.stderr

    # A carrier symlink is never followed by --apply: otherwise a fleet-shaped
    # path could overwrite a file outside the selected root.
    link_skill, link_coll = make_fake_repo(root / "link-fleet", with_collection=True)
    assert link_coll is not None
    external = root / "outside-preamble.tex"
    external.write_text("outside must stay unchanged\n", encoding="utf-8")
    (link_coll / "preamble.tex").unlink()
    (link_coll / "preamble.tex").symlink_to(external)
    proc = subprocess.run(
        ["bash", str(link_skill / "scripts" / "sync_preamble.sh"),
         "--root", str(root / "link-fleet"), "--apply"],
        text=True, capture_output=True,
    )
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "must not be a symlink" in (proc.stdout + proc.stderr), proc.stdout + proc.stderr
    assert external.read_text(encoding="utf-8") == "outside must stay unchanged\n"

    skill, coll = make_fake_repo(root / "fleet", with_collection=True)
    script = skill / "scripts" / "sync_preamble.sh"
    fleet_root = root / "fleet"
    proc = subprocess.run(["bash", str(script), "--root", str(fleet_root)],
                          text=True, capture_output=True)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "DRIFT" in proc.stdout, proc.stdout
    proc = subprocess.run(["bash", str(script), "--root", str(fleet_root), "--apply"],
                          text=True, capture_output=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert coll is not None
    for name in maintenance_sync_basenames():
        assert (coll / name).read_bytes() == (skill / "assets" / name).read_bytes()
    proc = subprocess.run(["bash", str(script), "--root", str(fleet_root)],
                          text=True, capture_output=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "match the skill assets" in proc.stdout, proc.stdout


def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        run_doctor_dependency_tests()
        run_hash_test(root)
        run_atomic_replace_tests(root)
        run_font_setup_symlink_test(root)
        run_sync_tests(root)
    print("maintenance tools: doctor dependency and QA-only probes + portable SHA-256 + symlink-safe atomic replace/font install + explicit-root/non-vacuous/two-phase/path-safe sync contracts pass")


if __name__ == "__main__":
    main()
