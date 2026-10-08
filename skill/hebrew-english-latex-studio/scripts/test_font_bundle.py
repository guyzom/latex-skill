#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Original project code; scope and terms: ../LICENSING.md.
"""Regression tests for fail-closed pinned-font verification."""

from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
from font_paths import font_dir
FONTS = font_dir()
VERIFY = HERE / "verify_font_bundle.py"


def run(path):
    return subprocess.run(
        [sys.executable, str(VERIFY), str(path)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ).returncode


def main():
    if run(FONTS) != 0:
        print("canonical font bundle did not verify")
        return 1
    with tempfile.TemporaryDirectory() as tmp:
        clone = Path(tmp) / "fonts"
        shutil.copytree(FONTS, clone)
        face = clone / "FrankRuhlLibre-Regular.ttf"
        data = bytearray(face.read_bytes())
        data[-1] ^= 0x01
        face.write_bytes(data)
        if run(clone) != 1:
            print("mutated font did not fail with exit 1")
            return 1
    print("font bundle verification: canonical pass + mutation failure")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
