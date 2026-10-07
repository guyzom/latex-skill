#!/usr/bin/env python3
"""Pin the runtime/QA shell surface to Bash 3.2 + POSIX utility syntax."""
from __future__ import annotations

from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
SHELLS = [
    ROOT / "scripts" / "build.sh",
    ROOT / "scripts" / "test_all.sh",
    ROOT / "scripts" / "setup_fonts.sh",
    ROOT / "scripts" / "sync_preamble.sh",
]
BANNED = {
    r"\bmapfile\b": "mapfile requires Bash 4+ (macOS system Bash is 3.2)",
    r"\breadarray\b": "readarray requires Bash 4+",
    r"\bdeclare\s+-A\b": "associative arrays require Bash 4+",
    r"\bgrep\s+-(?:[A-Za-z]*P[A-Za-z]*)\b": "grep -P is GNU-specific",
    r"\breadlink\s+-f\b": "readlink -f is not portable to macOS",
    r"\bstat\s+-c\b": "stat -c is GNU-specific",
    r"\bsed\s+-r\b": "sed -r is not portable to BSD sed",
}

errors: list[str] = []
for path in SHELLS:
    text = path.read_text(encoding="utf-8")
    for pattern, message in BANNED.items():
        if re.search(pattern, text):
            errors.append(f"{path.relative_to(ROOT)}: {message}")
    proc = subprocess.run(["bash", "-n", str(path)], text=True, capture_output=True)
    if proc.returncode != 0:
        errors.append(f"{path.relative_to(ROOT)}: bash -n failed: {proc.stderr.strip()}")

# The regression harness must not share predictable /tmp log names across runs.
harness_text = (ROOT / "scripts" / "test_all.sh").read_text(encoding="utf-8")
if "HARNESS_TMP=" not in harness_text:
    errors.append("scripts/test_all.sh: missing per-run private scratch directory")
for fixed in ("/tmp/hll_", "/tmp/t3_"):
    if fixed in harness_text:
        errors.append(f"scripts/test_all.sh: predictable shared temp path remains: {fixed}")
if errors:
    for error in errors:
        print(f"✗ {error}")
    sys.exit(1)
print("✓ shell portability contract: no Bash-4/GNU-only constructs in runtime + harness scripts")
