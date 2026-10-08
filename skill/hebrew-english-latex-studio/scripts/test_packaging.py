#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Original project code; scope and terms: ../LICENSING.md.
"""Mutation-test deterministic packaging and package-hygiene failure modes."""
from __future__ import annotations

import hashlib
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile

sys.dont_write_bytecode = True
from check_license_scope import LICENSE_HASHES

ROOT = Path(__file__).resolve().parent.parent
PACK = ROOT / "scripts" / "package_skill.py"
HYGIENE = ROOT / "scripts" / "check_package_hygiene.py"


def run_pack(root: Path, out: Path, *, replace_existing: bool = False) -> subprocess.CompletedProcess[str]:
    env = __import__("os").environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, str(root / "scripts" / "package_skill.py"),
         "--root", str(root), "--output", str(out)] + (["--replace-existing"] if replace_existing else []),
        text=True, capture_output=True, env=env, timeout=120,
    )

with tempfile.TemporaryDirectory() as td:
    temp = Path(td)
    a = temp / "checkout-one"
    b = temp / "renamed-checkout"
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo", "*.pdf", "*.aux", "*.toc", "*.out", "*.fls")
    shutil.copytree(ROOT, a, ignore=ignore)
    shutil.copytree(ROOT, b, ignore=ignore)
    out_a = temp / "a.skill"
    out_b = temp / "b.skill"
    legacy_temp = temp / "a.skill.tmp"
    legacy_temp.write_bytes(b"caller-owned sentinel\n")
    pa = run_pack(a, out_a)
    pb = run_pack(b, out_b)
    assert pa.returncode == 0, pa.stdout + pa.stderr
    assert legacy_temp.read_bytes() == b"caller-owned sentinel\n", "packager clobbered a predictable caller-owned temp path"
    assert pb.returncode == 0, pb.stdout + pb.stderr
    assert out_a.read_bytes() == out_b.read_bytes(), "archive depends on checkout directory name"
    digest = hashlib.sha256(out_a.read_bytes()).hexdigest()

    # Invoking the actual CLI without --output must use the public skill name.
    default_dir = temp / "default-output"
    default_dir.mkdir()
    default_pack = subprocess.run(
        [sys.executable, str(b / "scripts" / "package_skill.py"), "--root", str(b)],
        cwd=default_dir, text=True, capture_output=True, timeout=120,
    )
    assert default_pack.returncode == 0, default_pack.stdout + default_pack.stderr
    version = (b / "VERSION").read_text().strip()
    expected_default = default_dir / f"hebrew-english-latex-studio-v{version}.skill"
    assert expected_default.read_bytes() == out_b.read_bytes()
    assert sorted(p.name for p in default_dir.iterdir()) == [expected_default.name], \
        "default packaging published an obsolete or extra skill archive"

    # Default publication never replaces symlinks. An explicit replacement
    # still replaces the directory entry, never its target.
    outside = temp / "outside-sentinel.bin"
    outside.write_bytes(b"must stay unchanged\n")
    symlink_out = temp / "symlink-output.skill"
    symlink_out.symlink_to(outside)
    rejected = run_pack(b, symlink_out)
    assert rejected.returncode == 2 and symlink_out.is_symlink(), rejected.stdout + rejected.stderr
    assert outside.read_bytes() == b"must stay unchanged\n"
    ps = run_pack(b, symlink_out, replace_existing=True)
    assert ps.returncode == 0, ps.stdout + ps.stderr
    assert not symlink_out.is_symlink(), "packager followed the output symlink"
    assert hashlib.sha256(symlink_out.read_bytes()).hexdigest() == digest
    assert outside.read_bytes() == b"must stay unchanged\n"
    with zipfile.ZipFile(out_a) as zf:
        names = zf.namelist()
        assert names == sorted(names), "archive member order is not deterministic"
        assert "SKILL.md" in names and "VERSION" in names and "assets/preamble.tex" in names
        assert all(not n.startswith("/") and ".." not in Path(n).parts for n in names)
        assert not any("__pycache__" in n or n.endswith(".pyc") for n in names)
        # The standalone artifact must retain the exact grant and notices,
        # unmodified upstream texts, and every file receiving that grant.
        import json
        scope = json.loads(zf.read("LICENSE-SCOPE.json"))
        for rel in ["LICENSING.md", "NOTICE.md", "LICENSE-SCOPE.json", *LICENSE_HASHES,
                    *scope["covered_files"]]:
            assert zf.read(rel) == (ROOT / rel).read_bytes(), f"archive lost licensing/source bytes: {rel}"
        assert "assets/preamble.tex" not in scope["covered_files"]
        assert "scripts/new_document.py" not in scope["covered_files"]

    # Missing notices or scope must stop the actual packager, not just tests.
    for relative in ["LICENSING.md", "NOTICE.md", "LICENSE-SCOPE.json", *LICENSE_HASHES]:
        path = b / relative
        original = path.read_bytes()
        path.unlink()
        blocked_license = temp / "license-blocked.skill"
        result = run_pack(b, blocked_license)
        assert result.returncode == 2 and not blocked_license.exists(), result.stdout + result.stderr
        assert "license scope failed" in result.stderr, result.stdout + result.stderr
        path.write_bytes(original)

    before_stat = out_a.stat()
    repeated = run_pack(a, out_a)
    assert repeated.returncode == 0, repeated.stdout + repeated.stderr
    assert (out_a.stat().st_ino, out_a.stat().st_mtime_ns) == (before_stat.st_ino, before_stat.st_mtime_ns)
    original_bytes = out_a.read_bytes()
    harmless = a / "references" / "publication-probe.md"
    harmless.write_text("Publication mutation: deliberate, harmless source difference.\n", encoding="utf-8")
    collision = run_pack(a, out_a)
    assert collision.returncode == 2, collision.stdout + collision.stderr
    assert "previous output preserved" in collision.stderr
    assert out_a.read_bytes() == original_bytes
    assert not list(temp.glob(".a.skill.tmp.*")), "failed publish left temporary archives"
    replacement = run_pack(a, out_a, replace_existing=True)
    assert replacement.returncode == 0, replacement.stdout + replacement.stderr
    assert out_a.read_bytes() != original_bytes
    harmless.unlink()

    # Mutation proof: the packager itself is a release gate, not just a ZIP writer.
    release_bad = temp / "release-drift"
    shutil.copytree(ROOT, release_bad, ignore=ignore)
    (release_bad / "VERSION").write_text("9.9.9\n", encoding="utf-8")
    release_blocked = temp / "release-blocked.skill"
    pr = run_pack(release_bad, release_blocked)
    assert pr.returncode == 2 and not release_blocked.exists(), pr.stdout + pr.stderr
    assert "release contract failed" in (pr.stdout + pr.stderr)

    # Mutation proof: debris must stop both the hygiene checker and packager.
    cache = a / "scripts" / "__pycache__"
    cache.mkdir()
    (cache / "probe.pyc").write_bytes(b"bad")
    hp = subprocess.run([sys.executable, str(HYGIENE), str(a)], text=True, capture_output=True)
    assert hp.returncode == 1 and "__pycache__" in (hp.stdout + hp.stderr)
    blocked = temp / "blocked.skill"
    pp = run_pack(a, blocked)
    assert pp.returncode == 2 and not blocked.exists(), pp.stdout + pp.stderr

    # Mutation proof: ordinary TeX side products are release debris too. A
    # fixture named *.log.txt remains legal because only the final suffix is
    # classified as generated output.
    shutil.rmtree(cache)
    tex_log = a / "tests" / "accidental-build.log"
    tex_log.write_text("transient TeX log\n", encoding="utf-8")
    hp_log = subprocess.run([sys.executable, str(HYGIENE), str(a)], text=True, capture_output=True)
    assert hp_log.returncode == 1 and "accidental-build.log" in (hp_log.stdout + hp_log.stderr)
    assert (a / "tests" / "tex_errors_real.log.txt").is_file()
    tex_log.unlink()

    # The packager may not package its own output into the source tree.
    inside = b / "self.skill"
    pi = run_pack(b, inside)
    assert pi.returncode == 2 and not inside.exists(), pi.stdout + pi.stderr

print(f"✓ deterministic packaging + hygiene mutation contracts pass ({digest[:16]}…)")
