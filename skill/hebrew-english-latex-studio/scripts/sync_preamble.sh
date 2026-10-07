#!/usr/bin/env bash
# sync_preamble.sh — push the shared preamble LAYERS out to every collection copy.
#
# WHY THIS EXISTS. The collections do not \input the skill's preamble; each carries
# its OWN COPY at <collection>/src/preamble.tex. That was recorded as DEFECTS BLD-25
# after eleven preamble fixes (v3.52-v3.62) turned out to be INERT in every shipped
# PDF. The one-time sync fixed those — and then the very next preamble change
# (v3.63's \mbox on the caption label) was inert again, because a manual sync is a
# step you forget. So: run this after ANY edit to assets/preamble.tex, and rebuild.
#
# Architecture assets are synchronized carrier-by-carrier from the canonical
# architecture_contract.py maintenance set. Legacy fleets may carry only a
# subset (for example preamble.tex + clean_variant.tex); newer fleets may carry
# pure themes/extensions/page-shell assets. Only files already present in a
# collection are updated; the tool never opts a collection into a new layer.
#
# Historical note: clean_variant.tex first joined the sync in v4.2.1 because:
# four collections carry src/clean_variant.tex copies, the audit has guarded
# their identity (CLEANVARIANT-DRIFT) — but the fix tool only pushed the
# preamble, so closing a clean_variant drift meant hand-copying to every
# carrier, the exact "step you forget" this script exists to delete. Only
# collections that already carry a copy receive it; none is added.
#
# Usage:
#   bash scripts/sync_preamble.sh                         # git-root, report only
#   bash scripts/sync_preamble.sh --apply                 # git-root, apply
#   bash scripts/sync_preamble.sh --root /path/to/fleet   # explicit fleet root
#   HEBREW_LATEX_FLEET_ROOT=/path bash scripts/sync_preamble.sh
#
# Exit: 0 = in sync/applied, 1 = drift found, 2 = tooling/config misuse.
set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ATOMIC_REPLACE="$SCRIPT_DIR/atomic_replace.py"
ARCHITECTURE_CONTRACT="$SCRIPT_DIR/architecture_contract.py"
command -v python3 >/dev/null 2>&1 || { echo "❌ required command not found: python3"; exit 2; }
[ -f "$ATOMIC_REPLACE" ] || { echo "❌ maintenance helper missing: $ATOMIC_REPLACE"; exit 2; }
[ -f "$ARCHITECTURE_CONTRACT" ] || { echo "❌ architecture contract missing: $ARCHITECTURE_CONTRACT"; exit 2; }
command -v cmp >/dev/null 2>&1 || { echo "❌ required POSIX command not found: cmp"; exit 2; }

APPLY=0
ROOT_ARG=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --apply) APPLY=1; shift ;;
    --root)
      [ "$#" -ge 2 ] || { echo "❌ --root requires a directory"; exit 2; }
      ROOT_ARG="$2"; shift 2 ;;
    -h|--help)
      sed -n '1,28p' "$0"; exit 0 ;;
    *) echo "❌ unknown argument: $1"; exit 2 ;;
  esac
done

ROOT="${ROOT_ARG:-${HEBREW_LATEX_FLEET_ROOT:-}}"
if [ -z "$ROOT" ]; then
  if command -v git >/dev/null 2>&1; then
    ROOT=$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null || true)
  fi
fi
if [ -z "$ROOT" ]; then
  echo "❌ cannot determine fleet root from this standalone/non-git package"
  echo "   pass --root /path/to/repo or set HEBREW_LATEX_FLEET_ROOT."
  exit 2
fi
[ -d "$ROOT" ] || { echo "❌ fleet root is not a directory: $ROOT"; exit 2; }
ROOT="$(cd -P "$ROOT" && pwd)"
[ "$ROOT" != "/" ] || { echo "❌ refusing filesystem root as fleet root"; exit 2; }

# Print the rebuild command for EVERY collection, resolving each one's own entry
# point. Do not paper over this with a glob: `for b in */src/build.sh` matches 12
# of the 13 and SILENTLY SKIPS quantum-computing, whose script is fullbuild.sh
# (main.tex, not final.tex) — and that is the flagship 80-page collection SKILL.md
# cites. A fleet operation that quietly misses a member is the whole reason BLD-25
# existed; this loop is what stops the fix from re-opening the same hole.
emit_rebuild() {
  local d name entry
  for d in "$ROOT"/*/src; do
    [ -d "$d" ] || continue
    name=$(basename "$(dirname "$d")")
    entry=""
    for cand in build.sh fullbuild.sh; do
      [ -f "$d/$cand" ] && { entry="$cand"; break; }
    done
    if [ -z "$entry" ]; then
      echo "      ⚠ $name — NO BUILD SCRIPT FOUND (would be skipped silently)"
    else
      echo "      (cd $name/src && bash $entry)"
    fi
  done
}

# Two-phase maintenance preflight.  Validate the COMPLETE canonical layer set
# and every discovered carrier before mutating anything.  The older one-pass
# loop could sync preamble.tex and only then discover that clean_variant.tex was
# missing — a partial fleet update caused by the repair tool itself.
layers=()
while IFS= read -r layer || [ -n "$layer" ]; do
  [ -n "$layer" ] && layers[${#layers[@]}]="$layer"
done < <(python3 "$ARCHITECTURE_CONTRACT" maintenance-basenames)
[ "${#layers[@]}" -gt 0 ] || { echo "❌ architecture contract returned no maintenance layers"; exit 2; }
assets=()
for layer in "${layers[@]}"; do
  asset="$SCRIPT_DIR/../assets/$layer"
  [ -f "$asset" ] || { echo "❌ asset not found: $asset"; exit 2; }
  assets+=("$asset")
done

target_assets=()
target_copies=()
total=0
for idx in "${!layers[@]}"; do
  layer="${layers[$idx]}"
  asset="${assets[$idx]}"
  for copy in "$ROOT"/*/src/$layer; do
    # Unmatched globs remain literal in Bash; a broken symlink is still a
    # carrier-shaped object and must be rejected rather than skipped.
    if [ ! -e "$copy" ] && [ ! -L "$copy" ]; then continue; fi
    if [ -L "$copy" ]; then
      echo "❌ carrier must not be a symlink: ${copy#$ROOT/}"
      echo "   sync refuses links because an apply could write outside the fleet."
      exit 2
    fi
    [ -f "$copy" ] || {
      echo "❌ carrier is not a regular file: ${copy#$ROOT/}"
      exit 2
    }
    resolved_dir="$(cd -P "$(dirname "$copy")" 2>/dev/null && pwd)" || {
      echo "❌ cannot resolve carrier directory: $(dirname "$copy")"
      exit 2
    }
    case "$resolved_dir/" in
      "$ROOT"/*) ;;
      *)
        echo "❌ carrier resolves outside fleet root: ${copy#$ROOT/}"
        echo "   resolved directory: $resolved_dir"
        exit 2
        ;;
    esac
    target_assets+=("$asset")
    target_copies+=("$copy")
    total=$((total+1))
  done
done

# A fleet-maintenance command must never report a vacuous green result. In a
# standalone ZIP there are intentionally no sibling collections; saying
# "all 0 copies match" looks like a successful sync while proving nothing.
if [ "$total" = "0" ]; then
  echo "❌ no collection copies found under fleet root: $ROOT"
  echo "   verify --root / HEBREW_LATEX_FLEET_ROOT; a zero-member fleet is not"
  echo "   accepted as an in-sync result."
  exit 2
fi

drift=0
drift_assets=()
drift_copies=()
for idx in "${!target_copies[@]}"; do
  asset="${target_assets[$idx]}"
  copy="${target_copies[$idx]}"
  rel="${copy#$ROOT/}"
  if cmp -s "$asset" "$copy"; then
    continue
  fi
  drift=$((drift+1))
  drift_assets+=("$asset")
  drift_copies+=("$copy")
  if [ "$APPLY" != "1" ]; then
    echo "  DRIFT   $rel"
  fi
done

if [ "$APPLY" = "1" ]; then
  # Preflight every destination BEFORE the first write. This cannot make a
  # multi-directory fleet transaction crash-atomic, but it prevents predictable
  # partial applies from missing assets, symlink escapes and unwritable targets.
  for copy in "${drift_copies[@]}"; do
    dir="$(dirname "$copy")"
    [ -w "$copy" ] || { echo "❌ carrier is not writable: ${copy#$ROOT/}"; exit 2; }
    [ -w "$dir" ] || { echo "❌ carrier directory is not writable: ${dir#$ROOT/}"; exit 2; }
  done
  for idx in "${!drift_copies[@]}"; do
    asset="${drift_assets[$idx]}"
    copy="${drift_copies[$idx]}"
    python3 "$ATOMIC_REPLACE" "$asset" "$copy" || {
      echo "❌ failed to sync atomically: ${copy#$ROOT/}"
      exit 2
    }
    # Verify the write; success is byte identity, not merely cp exit status.
    cmp -s "$asset" "$copy" || {
      echo "❌ post-copy verification failed: ${copy#$ROOT/}"
      exit 2
    }
    echo "  synced  ${copy#$ROOT/}"
  done
fi

if [ "$APPLY" = "1" ]; then
  echo "✓ synced $drift of $total collection preamble-layer copies"
  echo "  → now REBUILD the affected collections; a preamble fix does not reach a"
  echo "    shipped PDF until its collection is recompiled. Exact commands:"
  emit_rebuild
  exit 0
fi

if [ "$drift" = "0" ]; then
  echo "✓ all $total collection preamble-layer copies match the skill assets"
  exit 0
fi
echo "✗ $drift of $total collection preamble-layer copies are STALE — every fix is"
echo "  INERT in those collections until you run:  bash $0 --apply"
exit 1
