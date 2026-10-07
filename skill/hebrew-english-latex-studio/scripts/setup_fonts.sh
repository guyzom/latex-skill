#!/usr/bin/env bash
# Import and verify external fonts. install_fonts.py uses atomic_replace.py,
# preserving symlink-safe publication. No font binaries ship in this package.
# Usage: bash scripts/setup_fonts.sh [DEST] [--from-skill PRIOR.skill]
#        bash scripts/setup_fonts.sh [DEST] [--from-directory FONT_DIR]
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
command -v python3 >/dev/null 2>&1 || { echo 'python3 is required.' >&2; exit 2; }
exec python3 "$SCRIPT_DIR/install_fonts.py" "$@"
