#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# Original project code; scope and terms: ../LICENSING.md.
# build.sh — compile a Hebrew LuaLaTeX document and run the mandatory checks.
# Usage: bash build.sh doc.tex
#
# Compiles to a fixed point. FAILS (exit 1) on any of:
#   - the compile itself failing (lualatex non-zero, or the PDF not regenerated
#     this run — catches a crash that the old script reported as "0 errors"),
#   - missing characters (silent tofu — the #1 Hebrew-LaTeX failure mode),
#   - LaTeX errors.
# Hyperref PDF-string defects, margin-breaking overflow (>15pt), source bidi
# findings, missing PyMuPDF, unexpected paper size, render defects and
# non-convergence are hard failures. Moderate hbox overflow and content-density
# findings are advisory. The canonical expected paper is A4; selecting another
# supported size requires an explicit EXPECTED_PAPER value.
# A clean build is NOT the end: always inspect the PDF visually afterwards —
# the checkers are a first pass, never a substitute for viewing every page.
set -uo pipefail

# v3.22 — DETERMINISTIC BUILDS. Without this, identical input produces a
# byte-different PDF every run (embedded dates + /ID), which is exactly the
# soil the 1-in-80 page-number-reversal class grew in and makes diffing
# impossible. Measured: with SOURCE_DATE_EPOCH set, repeat compiles of a
# 28-page doc are sha256-identical — but ONLY at the aux fixed point (see the
# convergence loop below; pre-convergence passes differ deterministically).
# Override by exporting your own value; set REPRO=1 to have this script PROVE
# reproducibility (extra confirmation pass + hash compare at the fixed point).
export SOURCE_DATE_EPOCH="${SOURCE_DATE_EPOCH:-1700000000}"
# PDF creation/modification dates must not depend on the caller's timezone.
# SOURCE_DATE_EPOCH fixes the instant; TZ fixes its serialized representation.
export TZ=UTC
# Keep the standalone skill tree immutable during normal builds. Python imports
# sibling checker modules; without this, a successful build leaves __pycache__
# inside scripts/ and the packaged tree is no longer byte-clean.
export PYTHONDONTWRITEBYTECODE=1
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BUNDLED_FONT_DIR="$SCRIPT_DIR/../assets/fonts"

if [ "$#" -ne 1 ]; then
  echo "usage: bash build.sh /absolute/path/to/doc.tex"
  exit 2
fi
INPUT_TEX="${1:?usage: bash build.sh doc.tex}"
[ -f "$INPUT_TEX" ] || { echo "❌ no such file: $INPUT_TEX"; exit 2; }

# v4.2.0 (adopted from the parallel iteration): preflight the SCRIPT bundle
# before compiling anything. Every gate below shells out to a sibling script;
# a partial copy of scripts/ used to surface as a bare "No such file or
# directory" halfway through a 4-pass build instead of one clear diagnosis up
# front. Environment failures exit 2; document/quality failures exit 1.
required_scripts=(
  verify_font_bundle.py resolve_tex_sources.py collect_fls_sources.py
  check_charset.py check_bidi_figures.py check_source_hazards.py
  check_content_density.py check_pdf_page_size.py check_pdf_render.py
  check_pdf_navigation.py tex_error_lines.sh hash_file.py build_contract.py
  validate_build_config.py atomic_replace.py hash_project_inputs.py preserve_output.py
  architecture_contract.py architecture_detection.py pdf_geometry.py pdf_folios.py heading_source.py pdf_string_source.py
  check_runtime_fonts.py font_paths.py language_context.py
)
missing_scripts=()
for required_script in "${required_scripts[@]}"; do
  [ -f "$SCRIPT_DIR/$required_script" ] || missing_scripts+=("$required_script")
done
if [ "${#missing_scripts[@]}" -ne 0 ]; then
  echo "❌ incomplete skill bundle: script(s) missing from $SCRIPT_DIR:"
  printf '   %s\n' "${missing_scripts[@]}"
  exit 2
fi

command -v python3 >/dev/null 2>&1 || {
  echo "❌ required command not found: python3"
  exit 2
}

# v4.3.1 — BUILD-CONTRACT PREFLIGHT. Configuration syntax is a tooling
# contract, not an advisory document finding. Validate it before LuaLaTeX and
# before any verified PDF can be published. Measured pre-fix:
# CONTENT_PROFILE=exma completed with rc=0 and "clean build" because argparse
# rejected the typo only in the final advisory stage and `|| true` swallowed it.
EXPECTED_PAPER="${EXPECTED_PAPER:-a4}"
DENSITY_PROFILE="${CONTENT_PROFILE:-generic}"
REPRO="${REPRO:-0}"
MAX_CROSS_PAGE_DESTINATIONS="${MAX_CROSS_PAGE_DESTINATIONS:-0}"
PDF_FOLIO_LAYOUT="${PDF_FOLIO_LAYOUT:-center}"
PDF_FOLIO_BAND="${PDF_FOLIO_BAND:-footer}"
PDF_CAPTION_COLOR="${PDF_CAPTION_COLOR:-000000}"
PDF_CAPTION_LABEL_WEIGHT="${PDF_CAPTION_LABEL_WEIGHT-normal}"
INDEX_PROCESSOR="${INDEX_PROCESSOR:-none}"
INDEX_STYLE="${INDEX_STYLE:-}"
if ! python3 "$SCRIPT_DIR/validate_build_config.py" \
    --content-profile "$DENSITY_PROFILE" \
    --expected-paper "$EXPECTED_PAPER" \
    --section-macros "${SECTION_MACROS:-}" \
    --repro "$REPRO" \
    --max-cross-page-destinations "$MAX_CROSS_PAGE_DESTINATIONS" \
    --folio-layout "$PDF_FOLIO_LAYOUT" \
    --folio-band "$PDF_FOLIO_BAND" \
    --caption-color "$PDF_CAPTION_COLOR" \
    --caption-label-weight "$PDF_CAPTION_LABEL_WEIGHT" \
    --index-processor "$INDEX_PROCESSOR" \
    --index-style "$INDEX_STYLE" \
    --source-date-epoch "$SOURCE_DATE_EPOCH"; then
  exit 2
fi

# Navigation integrity is universal; document-specific completeness is an
# explicit project contract. These options never infer a title, bookmark count,
# or hierarchy from the content profile.
PDF_NAVIGATION_ARGS=()
case "${PDF_REQUIRE_TITLE:-0}" in
  0) ;;
  1) PDF_NAVIGATION_ARGS+=(--require-title) ;;
  *)
    echo "❌ PDF_REQUIRE_TITLE must be 0 or 1."
    exit 2
    ;;
esac
for nav_setting in \
  "PDF_MIN_BOOKMARKS:--min-bookmarks" \
  "PDF_MIN_BOOKMARK_DEPTH:--min-bookmark-depth" \
  "PDF_WARN_NO_OUTLINE_AFTER:--warn-no-outline-after"; do
  nav_name="${nav_setting%%:*}"
  nav_flag="${nav_setting#*:}"
  nav_value="${!nav_name:-}"
  [ -z "$nav_value" ] && continue
  if [[ ! "$nav_value" =~ ^[0-9]+$ ]]; then
    echo "❌ $nav_name must be a non-negative integer."
    exit 2
  fi
  PDF_NAVIGATION_ARGS+=("$nav_flag" "$nav_value")
done

# Named GoTo destinations are valid PDF and remain accepted by default. Some
# mobile / embedded viewers have nevertheless mis-resolved specific custom
# routes in real documents. A project may therefore name only its critical
# destination families here; the PDF gate will require direct page arrays for
# matching actions without imposing direct destinations on the rest of the
# document. The value is a comma-separated list of shell-style globs.
if [ -n "${DIRECT_NAVIGATION_DESTINATIONS:-}" ]; then
  # read -a silently drops a trailing empty field. Reject it explicitly.
  if [[ "$DIRECT_NAVIGATION_DESTINATIONS" == *, ]]; then
    echo "❌ DIRECT_NAVIGATION_DESTINATIONS must contain only non-empty destination globs."
    exit 2
  fi
  IFS=',' read -r -a direct_navigation_patterns \
    <<< "$DIRECT_NAVIGATION_DESTINATIONS"
  if [ "${#direct_navigation_patterns[@]}" -eq 0 ]; then
    echo "❌ DIRECT_NAVIGATION_DESTINATIONS must contain a destination glob."
    exit 2
  fi
  for raw_pattern in "${direct_navigation_patterns[@]}"; do
    pattern="${raw_pattern#"${raw_pattern%%[![:space:]]*}"}"
    pattern="${pattern%"${pattern##*[![:space:]]}"}"
    if [ -z "$pattern" ]; then
      echo "❌ DIRECT_NAVIGATION_DESTINATIONS must be a comma-separated list"
      echo "   of non-empty destination globs."
      exit 2
    fi
    PDF_NAVIGATION_ARGS+=(--require-direct-named "$pattern")
  done
fi
TEX_ABS="$(cd "$(dirname "$INPUT_TEX")" && pwd)/$(basename "$INPUT_TEX")"
PROJECT_ROOT="${HEBREW_LATEX_PROJECT_ROOT:-$(dirname "$TEX_ABS")}"
if [ ! -d "$PROJECT_ROOT" ]; then
  echo "❌ HEBREW_LATEX_PROJECT_ROOT is not a directory: $PROJECT_ROOT"
  exit 2
fi
if ! PROJECT_ROOT="$(cd "$PROJECT_ROOT" && pwd)"; then
  echo "❌ cannot resolve HEBREW_LATEX_PROJECT_ROOT: $PROJECT_ROOT"
  exit 2
fi
if [ "$INDEX_PROCESSOR" = makeindex ]; then
  command -v makeindex >/dev/null 2>&1 || {
    echo "❌ makeindex is required by INDEX_PROCESSOR=makeindex."
    exit 2
  }
  if [ -n "$INDEX_STYLE" ]; then
    if ! python3 - "$PROJECT_ROOT" "$INDEX_STYLE" <<'PY'
from pathlib import Path
import sys
root = Path(sys.argv[1]).resolve()
try:
    path = (root / sys.argv[2]).resolve(strict=True)
    assert path.is_relative_to(root) and path.is_file()
except (OSError, AssertionError):
    print("INDEX_STYLE must exist inside the declared project root", file=sys.stderr)
    sys.exit(2)
PY
    then exit 2; fi
  fi
fi

# Font discovery is intentionally AFTER cheap syntax/path preflight. Invalid
# build configuration must fail quickly and must not pay font/toolchain setup.
if [ -z "${HEBREW_LATEX_FONT_DIR:-}" ]; then
  HEBREW_LATEX_FONT_DIR="$(python3 "$SCRIPT_DIR/font_paths.py")" || exit 2
fi
export HEBREW_LATEX_FONT_DIR
if [ -n "${HEBREW_LATEX_FONT_DIR:-}" ]; then
  if [ ! -d "$HEBREW_LATEX_FONT_DIR" ]; then
    echo "❌ HEBREW_LATEX_FONT_DIR is not a directory: $HEBREW_LATEX_FONT_DIR"
    exit 2
  fi
  if ! HEBREW_LATEX_FONT_DIR="$(cd "$HEBREW_LATEX_FONT_DIR" && pwd)"; then
    echo "❌ cannot resolve HEBREW_LATEX_FONT_DIR: $HEBREW_LATEX_FONT_DIR"
    exit 2
  fi
  # The trailing colon preserves the built-in search path. OSFONTDIR feeds
  # luaotfload/fontconfig discovery. These are lookup hints only; the
  # runtime inventory below verifies actual canonical paths and hashes.
  export OSFONTDIR="$HEBREW_LATEX_FONT_DIR${OSFONTDIR:+:$OSFONTDIR}:"
  export TTFONTS="$HEBREW_LATEX_FONT_DIR${TTFONTS:+:$TTFONTS}:"
fi
python3 "$SCRIPT_DIR/verify_font_bundle.py" \
  "${HEBREW_LATEX_FONT_DIR:-$BUNDLED_FONT_DIR}" || {
  echo "❌ pinned font bundle verification failed."
  exit 2
}

TEX="$(basename "$TEX_ABS")"
STEM="${TEX%.tex}"
TARGET_PDF="$(dirname "$TEX_ABS")/$STEM.pdf"
# Fail before deriving paths, installing cleanup, or touching previous output.
# With set -uo (not -e), unchecked mktemp failure produced /font-cache.
if ! BUILD_DIR="$(mktemp -d)"; then
  echo "✗ cannot create private build directory; compiler was not started."
  exit 2
fi
if [ -z "$BUILD_DIR" ] || [ ! -d "$BUILD_DIR" ]; then
  echo "✗ temporary-directory allocator returned no usable directory; compiler was not started."
  exit 2
fi
# v4.1.4: EXPORT THE EVIDENCE ON ANY UNPUBLISHED EXIT, not just a fatal one.
# v4.0.1c preserved the log when lualatex itself died — but the common failure
# is a GATE failing over a compile that succeeded, and on that path both the
# log and the PDF died with the mktemp dir. What stays behind next to the
# source is the PREVIOUS run's output, which looks current and is not.
# Measured on data-science-exams: the gate said "Overfull \hbox detected at
# line 10787" and "✗ p.231 [INK-OFF-PAPER]" with no log to read and no PDF to
# open at p.231; the stale neighbour PDF was 458 pages against the failing
# run's 425, so rendering "p.231" showed an unrelated question, and the stale
# .aux then named the wrong source file — a needspace fix landed in a file
# that had nothing to do with the defect before a fresh compile caught it.
# The failing PDF is published under .failed.pdf, never over $STEM.pdf: a
# failed build must still leave the last good deliverable untouched.
PUBLISHED=0
PRIOR_OUTPUT_STATE="$BUILD_DIR/prior-output"
# LuaHBTeX 1.18 was measured unlinking CWD/jobname.pdf on a pre-shipout
# hyperref failure, despite -output-directory. Preserve the existing directory
# entry without changing CWD, jobname, input paths or deterministic PDF bytes.
PRIOR_OUTPUT_READY=0
RECOVERY_FAILED=0
recover_prior_output() {
  [ "$PRIOR_OUTPUT_READY" = 1 ] || return 0
  if ! python3 "$SCRIPT_DIR/preserve_output.py" recover "$TARGET_PDF" "$PRIOR_OUTPUT_STATE"; then
    RECOVERY_FAILED=1
    echo "✗ recovery snapshot retained at: $PRIOR_OUTPUT_STATE"
    return 1
  fi
}
# v4.27.0 — BLD-71: A NONEMPTY FILE IS NOT A READABLE PDF. LuaTeX writes page
# content as pages ship, but the page tree, the fonts, the xref and the
# trailer only when it finishes the file. A compile that stops after a page
# has shipped ("no output PDF file produced!") leaves the rest out; the engine
# then deletes the partial file itself, but under -output-directory it removes
# CWD/jobname.pdf instead (measured on LuaHBTeX 1.17.0: without the flag no
# file is left; with it a 225-byte one is). Until v4.27.0 the export below
# asked only -s, and told the author to "diagnose page numbers from THIS
# file" while pdfinfo and pdftoppm rejected it ("Couldn't find trailer
# dictionary") and PyMuPDF repaired it to 0 pages. Measured on
# lifting-optimization, halted on page 36: 196,856 bytes, 32 page
# dictionaries with no page tree and not one font. Evidence is exported only
# when Poppler, the reader the visual check at the end uses, finds a page.
readable_pdf_pages() {
  pdfinfo "$1" 2>/dev/null \
    | awk '/^Pages:[[:space:]]*[0-9]+[[:space:]]*$/ { print $2; exit }'
}
cleanup() {
  local original_status=$?
  if [ "$PUBLISHED" != 1 ]; then
    recover_prior_output || true
  fi
  if [ "$PUBLISHED" != "1" ] && [ -n "${LOG:-}" ] && [ -f "$LOG" ]; then
    _fail_log="$(dirname "$TEX_ABS")/$STEM.failed.log"
    if python3 "$SCRIPT_DIR/atomic_replace.py" "$LOG" "$_fail_log" >/dev/null 2>&1; then
      echo "  ── full log preserved: $_fail_log"
    fi
    # v4.2.1: the aux too. It was the second half of the BLD-56 misdirection:
    # the log and PDF were exported, but mapping a page's \label back to its
    # source file went through the STALE aux next to the source — and sent a
    # fix into a file that had nothing to do with the defect (measured; a
    # fresh compile caught it). Honest limit: a \include-based document splits
    # labels into per-part aux files that still die with the temp dir — only
    # the root aux is exported. Every document this pipeline builds is a
    # single \input tree (the assembly convention), where the root aux
    # carries everything.
    if [ -f "$BUILD_DIR/$STEM.aux" ]; then
      _fail_aux="$(dirname "$TEX_ABS")/$STEM.failed.aux"
      if python3 "$SCRIPT_DIR/atomic_replace.py" "$BUILD_DIR/$STEM.aux" "$_fail_aux" >/dev/null 2>&1; then
        echo "  ── aux preserved: $_fail_aux (map labels through THIS file)"
      fi
    fi
    _fail_pdf_pages=""
    if [ -n "${PDF:-}" ] && [ -s "$PDF" ]; then
      _fail_pdf_pages="$(readable_pdf_pages "$PDF")"
    fi
    if [ "${_fail_pdf_pages:-0}" -ge 1 ]; then
      _fail_pdf="$(dirname "$TEX_ABS")/$STEM.failed.pdf"
      if python3 "$SCRIPT_DIR/atomic_replace.py" "$PDF" "$_fail_pdf" >/dev/null 2>&1; then
        echo "  ── failing PDF preserved: $_fail_pdf"
        echo "     (diagnose page numbers from THIS file)"
      fi
    else
      # A previous diagnostic PDF must not impersonate this failure, whether
      # the engine left nothing (zero pages) or a file no reader can open.
      if ! rm -f -- "$(dirname "$TEX_ABS")/$STEM.failed.pdf"; then
        echo "  ⚠ could not remove stale diagnostic PDF; use this run's log."
      fi
      if [ -n "${PDF:-}" ] && [ -s "$PDF" ]; then
        echo "  ── no readable diagnostic PDF: the compile stopped before LuaTeX finished"
        echo "     the file, and the truncated remainder (no page tree, fonts or trailer)"
        echo "     opens in no reader, so it was not exported. Diagnose from the log."
      else
        echo "  ── no nonempty diagnostic PDF was produced by this failed run."
      fi
    fi
    # Unchanged condition: the earlier deliverable is still the only PDF next
    # to the source when the truncated file is withheld, so it still warns.
    if [ -n "${PDF:-}" ] && [ -s "$PDF" ] && [ -f "$TARGET_PDF" ]; then
      echo "  ⚠ $TARGET_PDF is from an EARLIER run — its page numbers do not"
      echo "     match the failure above; do not diagnose from it."
    fi
  fi
  if [ "$RECOVERY_FAILED" != 1 ]; then
    rm -rf -- "$BUILD_DIR"
  fi
  if [ "$RECOVERY_FAILED" = 1 ]; then return 2; fi
  return "$original_status"
}
trap cleanup EXIT
# A shared OTF cache can retain an old installation path after relocation.
# Isolate this build without clearing the caller's cache or relaxing openout_any.
if ! mkdir "$BUILD_DIR/font-cache"; then
  echo "✗ cannot create private font cache; compiler was not started."
  exit 2
fi
export TEXMFCACHE="$BUILD_DIR/font-cache"
export TEXMFVAR="$TEXMFCACHE"
if ! python3 "$SCRIPT_DIR/preserve_output.py" snapshot "$TARGET_PDF" "$PRIOR_OUTPUT_STATE"; then
  echo "✗ cannot preserve prior output; compiler was not started."
  exit 2
fi
PRIOR_OUTPUT_READY=1
BASE="$BUILD_DIR/$STEM"
LOG="$BASE.log"
PDF="$BASE.pdf"
cd "$(dirname "$TEX_ABS")"

command -v lualatex >/dev/null 2>&1 || {
  echo "❌ lualatex not found — see references/recipe.md step 0"
  echo "   (apt-get install -y texlive-luatex; then scripts/setup_fonts.sh)."
  exit 2
}
command -v kpsewhich >/dev/null 2>&1 || {
  echo "❌ kpsewhich not found — install a complete TeX Live LuaLaTeX toolchain."
  exit 2
}
for required_command in python3 pdfinfo pdftoppm; do
  command -v "$required_command" >/dev/null 2>&1 || {
    echo "❌ required command not found: $required_command"
    exit 2
  }
done
python3 -c "import fitz" >/dev/null 2>&1 || {
  echo "❌ pymupdf is required for the mandatory rendered-PDF gate."
  echo "   Install it with: python3 -m pip install pymupdf"
  exit 2
}
for required_tex_file in \
  luaotfload-main.lua luatexbase.sty babel.sty babel-he.ini babel-en.ini fontspec.sty \
  lmroman10-regular.otf lmroman10-bold.otf lmroman10-italic.otf lmroman10-bolditalic.otf \
  lmsans10-regular.otf lmsans10-bold.otf lmsans10-oblique.otf lmsans10-boldoblique.otf \
  amsmath.sty amssymb.sty mathtools.sty amsthm.sty etoolbox.sty geometry.sty \
  xcolor.sty mdframed.sty listings.sty tikz.sty pgfplots.sty quantikz.sty \
  booktabs.sty array.sty float.sty enumitem.sty needspace.sty hyperref.sty \
  fancyhdr.sty graphicx.sty; do
  if [ -z "$(kpsewhich "$required_tex_file" 2>/dev/null)" ]; then
    echo "❌ incomplete LuaLaTeX toolchain: $required_tex_file was not found."
    echo "   Install texlive-luatex and the Hebrew babel language files."
    exit 2
  fi
done


# Resolve the complete trusted source graph. Dynamic paths, missing files and
# attempts to escape PROJECT_ROOT are hard failures.
SOURCE_LIST="$BUILD_DIR/sources.txt"
TEX_SOURCE_LIST="$BUILD_DIR/tex-sources.txt"
if ! python3 "$SCRIPT_DIR/resolve_tex_sources.py" \
    --project-root "$PROJECT_ROOT" "$TEX_ABS" >"$SOURCE_LIST"; then
  echo "✗ source dependency graph is incomplete or unsafe."
  exit 1
fi
if ! python3 "$SCRIPT_DIR/resolve_tex_sources.py" \
    --project-root "$PROJECT_ROOT" --mode tex "$TEX_ABS" >"$TEX_SOURCE_LIST"; then
  echo "✗ TeX source dependency graph is incomplete or unsafe."
  exit 1
fi
SOURCE_FILES=()
while IFS= read -r source_file || [ -n "$source_file" ]; do
  [ -n "$source_file" ] && SOURCE_FILES[${#SOURCE_FILES[@]}]="$source_file"
done <"$SOURCE_LIST"
TEX_SOURCE_FILES=()
while IFS= read -r source_file || [ -n "$source_file" ]; do
  [ -n "$source_file" ] && TEX_SOURCE_FILES[${#TEX_SOURCE_FILES[@]}]="$source_file"
done <"$TEX_SOURCE_LIST"

# 0) Source pre-checks (HARD gates, before compilation).
# Catches stray/confusable codepoints — esp. Arabic ر/ي masquerading as Hebrew
# resh/yod — that compile to silent tofu. See scripts/check_charset.py.
if [ -f "$SCRIPT_DIR/check_charset.py" ]; then
  if ! python3 "$SCRIPT_DIR/check_charset.py" "${SOURCE_FILES[@]}"; then
    echo "✗ stray codepoints (see above) — fix before building. BUILD NOT OK."
    exit 1
  fi
fi
if [ -f "$SCRIPT_DIR/check_bidi_figures.py" ]; then
  echo "▶ bidi / figure source gate:"
  if ! python3 "$SCRIPT_DIR/check_bidi_figures.py" "${TEX_SOURCE_FILES[@]}"; then
    echo "✗ bidi / figure source gate failed. BUILD NOT OK."
    exit 1
  fi
fi
if [ -f "$SCRIPT_DIR/check_source_hazards.py" ]; then
  echo "▶ source hazard gate:"
  if ! python3 "$SCRIPT_DIR/check_source_hazards.py" "${TEX_SOURCE_FILES[@]}"; then
    echo "✗ source hazard gate failed. BUILD NOT OK."
    exit 1
  fi
fi

# v3.23.3 — COMPILE TO THE FIXED POINT, not a fixed pass count. Measured on the
# 28-page example: from a clean state, pass 2 ships WRONG TOC page numbers
# (TOC insertion shifts content, so the .toc written by pass 2 differs from the
# one it read) — the document converges only at pass 3. We compile, then repeat
# (up to 5 passes) until two consecutive complete BUILD STATES are identical.
# PDF-only equality is insufficient: an aux change can leave pass N's PDF
# unchanged and alter pass N+1. The state digest covers the PDF plus every
# TeX-readable auxiliary family used by this pipeline.
LATEX=(lualatex --no-shell-escape -interaction=nonstopmode -halt-on-error -recorder
       -output-directory="$BUILD_DIR")
FLS="$BASE.fls"
ACTUAL_SOURCE_LIST="$BUILD_DIR/actual-sources.txt"
ACTUAL_TEX_SOURCE_LIST="$BUILD_DIR/actual-tex-sources.txt"
ACTUAL_PROJECT_INPUT_LIST="$BUILD_DIR/actual-project-inputs.txt"
PROJECT_INPUT_HASH=""
# v4.0.1: BUILD_DIR is an allowed root. The gate flags every .fls INPUT outside
# PROJECT_ROOT, and this build compiles inside a mktemp -d, so LaTeX's OWN
# generated files — .aux, .out, .toc — were reported as "untrusted external TeX
# input" and every build failed on pass 1 (measured: all 7 bundled examples).
# The build directory holds this run's own artifacts by construction; trusting it
# does not widen the boundary the gate exists to police, which is INPUT from
# outside the project.
ALLOW_ROOT_ARGS=(--allow-root "$HEBREW_LATEX_FONT_DIR" --allow-root "$BUILD_DIR")
FORBID_INPUT_ARGS=(
  --forbid-input "$TARGET_PDF"
  --forbid-input "$(dirname "$TEX_ABS")/$STEM.failed.pdf"
  --forbid-input "$(dirname "$TEX_ABS")/$STEM.failed.log"
  --forbid-input "$(dirname "$TEX_ABS")/$STEM.failed.aux"
)
GENERATED_INPUT_ARGS=()
if [ "$INDEX_PROCESSOR" = makeindex ]; then
  GENERATED_INPUT_ARGS+=(--generated-tex-input "$BASE.ind")
  # A previous adjacent index must not masquerade as this private build's output.
  FORBID_INPUT_ARGS+=(--forbid-input "$(dirname "$TEX_ABS")/$STEM.ind")
fi
for texmf_var in TEXMFROOT TEXMFSYSVAR TEXMFSYSCONFIG TEXMFVAR TEXMFCONFIG TEXMFHOME TEXMFLOCAL; do
  texmf_path="$(kpsewhich -var-value="$texmf_var" 2>/dev/null || true)"
  if [ -n "$texmf_path" ] && [ -d "$texmf_path" ]; then
    ALLOW_ROOT_ARGS+=(--allow-root "$texmf_path")
  fi
done
# v4.0.1c: /usr/share/fontconfig too. fontconfig ships its ruleset there and
# /etc/fonts/conf.d symlinks INTO it, so on a machine where those links are followed
# — measured on the CI runner, not reproducible here — luaotfload reads
# /usr/share/fontconfig/conf.avail/*.conf and the recorder logs 11 of them. They are
# font CONFIGURATION, read-only OS data in the same class as /etc/fonts, which was
# already trusted; the asymmetry was an oversight, not a decision. Their .conf
# suffix is not glyph data, so the deny-by-default suffix rule correctly refuses to
# exempt them — the root has to be named.
for system_font_root in /usr/share/fonts /etc/fonts /usr/share/fontconfig; do
  [ -d "$system_font_root" ] \
    && ALLOW_ROOT_ARGS+=(--allow-root "$system_font_root")
done

project_input_hash() {
  python3 "$SCRIPT_DIR/hash_project_inputs.py" \
    --project-root "$PROJECT_ROOT" "$ACTUAL_PROJECT_INPUT_LIST"
}

# The recorder is the authoritative record of what TeX actually read. It must
# be checked after EVERY pass: aux/TOC-driven conditionals can introduce a new
# dependency only on a later pass. Checking pass 1 alone leaves that path
# outside both the trust boundary and the bidi/charset gates.
check_recorded_sources() {
  local pass_label="$1"
  if [ ! -f "$FLS" ]; then
    echo "✗ lualatex did not produce a recorder (.fls) file on $pass_label."
    return 1
  fi
  python3 "$SCRIPT_DIR/collect_fls_sources.py" --project-root "$PROJECT_ROOT" \
    "${ALLOW_ROOT_ARGS[@]}" "${FORBID_INPUT_ARGS[@]}" \
    ${GENERATED_INPUT_ARGS[@]+"${GENERATED_INPUT_ARGS[@]}"} "$FLS" >"$ACTUAL_SOURCE_LIST" || return 1
  python3 "$SCRIPT_DIR/collect_fls_sources.py" --project-root "$PROJECT_ROOT" \
    "${ALLOW_ROOT_ARGS[@]}" "${FORBID_INPUT_ARGS[@]}" \
    ${GENERATED_INPUT_ARGS[@]+"${GENERATED_INPUT_ARGS[@]}"} --mode tex "$FLS" >"$ACTUAL_TEX_SOURCE_LIST" \
    || return 1
  python3 "$SCRIPT_DIR/collect_fls_sources.py" --project-root "$PROJECT_ROOT" \
    "${ALLOW_ROOT_ARGS[@]}" "${FORBID_INPUT_ARGS[@]}" --mode project-all "$FLS" >"$ACTUAL_PROJECT_INPUT_LIST" \
    || return 1
  if [ "$INDEX_PROCESSOR" = makeindex ] && [ -n "$INDEX_STYLE" ]; then
    printf '%s\n' "$PROJECT_ROOT/$INDEX_STYLE" >>"$ACTUAL_PROJECT_INPUT_LIST"
  fi
  PROJECT_INPUT_HASH="$(project_input_hash)" || return 1
  [ -n "$PROJECT_INPUT_HASH" ] || { echo "✗ recorder project-input manifest is empty on $pass_label."; return 1; }
  ACTUAL_SOURCE_FILES=()
  while IFS= read -r source_file || [ -n "$source_file" ]; do
    [ -n "$source_file" ] && ACTUAL_SOURCE_FILES[${#ACTUAL_SOURCE_FILES[@]}]="$source_file"
  done <"$ACTUAL_SOURCE_LIST"
  ACTUAL_TEX_SOURCE_FILES=()
  while IFS= read -r source_file || [ -n "$source_file" ]; do
    [ -n "$source_file" ] && ACTUAL_TEX_SOURCE_FILES[${#ACTUAL_TEX_SOURCE_FILES[@]}]="$source_file"
  done <"$ACTUAL_TEX_SOURCE_LIST"
  if [ "${#ACTUAL_SOURCE_FILES[@]}" -eq 0 ]; then
    echo "✗ recorder found no project-local source files on $pass_label."
    return 1
  fi
  python3 "$SCRIPT_DIR/check_charset.py" "${ACTUAL_SOURCE_FILES[@]}" || return 1
  python3 "$SCRIPT_DIR/check_bidi_figures.py" \
    "${ACTUAL_TEX_SOURCE_FILES[@]}" || return 1
  python3 "$SCRIPT_DIR/check_source_hazards.py" \
    "${ACTUAL_TEX_SOURCE_FILES[@]}" || return 1
  python3 "$SCRIPT_DIR/check_runtime_fonts.py" "$LOG" \
    --font-dir "$HEBREW_LATEX_FONT_DIR" --source-list "$ACTUAL_TEX_SOURCE_LIST" || return 1
  SOURCE_FILES=("${ACTUAL_SOURCE_FILES[@]}")
  TEX_SOURCE_FILES=("${ACTUAL_TEX_SOURCE_FILES[@]}")
}

build_state_hash() {
  python3 - "$BUILD_DIR" "$PROJECT_INPUT_HASH" <<'PY'
from pathlib import Path
import hashlib
import sys

root = Path(sys.argv[1])
project_input_hash = sys.argv[2].encode("ascii")
suffixes = {
    ".pdf", ".aux", ".toc", ".out", ".lof", ".lot", ".bbl", ".bcf",
    ".idx", ".ind", ".ilg", ".glo", ".gls", ".acn", ".acr", ".alg",
    ".nav", ".snm",
}
paths = sorted(
    p for p in root.rglob("*")
    if p.is_file() and (p.suffix in suffixes or p.name.endswith(".run.xml"))
)
h = hashlib.sha256()
h.update(b"project-inputs\0")
h.update(project_input_hash)
for path in paths:
    rel = path.relative_to(root).as_posix().encode("utf-8")
    data = path.read_bytes()
    h.update(len(rel).to_bytes(8, "big"))
    h.update(rel)
    h.update(len(data).to_bytes(8, "big"))
    h.update(data)
print(h.hexdigest() if paths else "")
PY
}

run_latex() {
  "${LATEX[@]}" "$TEX" >/dev/null 2>&1
  local compiler_status=$?
  recover_prior_output || exit 2
  return "$compiler_status"
}

run_index_stage() {
  if [ "$INDEX_PROCESSOR" = none ]; then
    # A current private .idx proves the document enabled its index writer.
    # Disabling both settings must not turn that requested index into a clean
    # PDF with no index, even when no entries were written.
    if [ -f "$BASE.idx" ]; then
      echo "✗ managed index: current .idx requires INDEX_PROCESSOR=makeindex."
      return 1
    fi
    return 0
  fi
  if ! python3 "$SCRIPT_DIR/build_contract.py" --index-base "$BASE" \
      --project-root "$PROJECT_ROOT" --index-style "$INDEX_STYLE"; then
    # Retain the processor's exact diagnostic in the normal failed-build log.
    if [ -f "$BASE.ilg" ]; then
      printf '\nManaged makeindex diagnostic:\n' >>"$LOG"
      cat "$BASE.ilg" >>"$LOG"
    fi
    return 1
  fi
}

# v4.26.0 — BLD-69: NAME THE ERROR THE MOMENT A PASS FAILS. Every pass is
# followed by the recorded-source gate, whose last step is the runtime font
# check, and the preamble writes that inventory only when LuaTeX finishes the
# PDF. A compile that died before the end of the document therefore failed
# the inventory check first, and the gate printed only
#   ✗ runtime fonts: missing runtime font inventory; synchronize preamble.tex
#   ✗ recorded-source gate failed on pass 1. BUILD NOT OK.
# Measured on three one-line documents (an undefined macro, a failed Lua
# require, pgfplots contour lua): no "!" line, no l.N, nothing about the
# cause — which sat in the preserved .failed.log — and the v4.0.1c
# "name the ERROR" block after the pass loop was never reached. So the record
# is printed here, before any recorded-source check, from the same
# discriminator the error count uses (tex_error_lines.sh, so a BLD-55 dump
# phantom can never pose as the error). A later pass that fails with the
# same record says so in one line instead of repeating it.
LAST_ENGINE_RECORD=""
report_engine_failure() {
  local pass_label="$1" compiler_status="$2" record
  [ "$compiler_status" -eq 0 ] && return 0
  echo "✗ lualatex exited $compiler_status on $pass_label: the compile stopped before the end of the document."
  record="$(bash "$SCRIPT_DIR/tex_error_lines.sh" --context "$LOG" | head -60)"
  if [ -n "$record" ] && [ "$record" = "$LAST_ENGINE_RECORD" ]; then
    echo "  (the same error as on the previous failing pass)"
  elif [ -n "$record" ]; then
    echo "  ── the error, with TeX's l.N source line ──"
    printf '%s\n' "$record" | sed 's/^/  │ /'
  else
    echo "  ── no error record in the log; its last 15 lines ──"
    tail -15 "$LOG" 2>/dev/null | sed 's/^/  │ /'
  fi
  LAST_ENGINE_RECORD="$record"
}
recorded_gate_failed() {
  local pass_label="$1" compiler_status="$2"
  if [ "$compiler_status" -ne 0 ]; then
    echo "✗ recorded-source gate failed on $pass_label, after the compile error above. BUILD NOT OK."
  else
    echo "✗ recorded-source gate failed on $pass_label. BUILD NOT OK."
  fi
}
echo "▶ pass 1 …"; run_latex; rc1=$?
report_engine_failure "pass 1" "$rc1"
if ! check_recorded_sources "pass 1"; then
  recorded_gate_failed "pass 1" "$rc1"
  exit 1
fi
run_index_stage || exit 1
rc2=$rc1
prev_state_hash=$(build_state_hash)
CONVERGED=0
for pass in 2 3 4 5; do
  echo "▶ pass $pass …"; run_latex; rc2=$?
  report_engine_failure "pass $pass" "$rc2"
  if ! check_recorded_sources "pass $pass"; then
    recorded_gate_failed "pass $pass" "$rc2"
    exit 1
  fi
  run_index_stage || exit 1
  cur_state_hash=$(build_state_hash)
  if [ -n "$prev_state_hash" ] && [ "$cur_state_hash" = "$prev_state_hash" ]; then
    CONVERGED=1
    break
  fi
  prev_state_hash=$cur_state_hash
done
if [ "$CONVERGED" = "1" ]; then
  if [ "$INDEX_PROCESSOR" = makeindex ]; then
    if ! python3 - "$FLS" "$BASE.ind" <<'PY'
from pathlib import Path
import sys
fls, expected = Path(sys.argv[1]), Path(sys.argv[2]).resolve()
lines = fls.read_text(encoding="utf-8").splitlines()
pwd = next((Path(line[4:]) for line in lines if line.startswith("PWD ")), fls.parent)
inputs = {((pwd / line[6:]) if not Path(line[6:]).is_absolute() else Path(line[6:])).resolve()
          for line in lines if line.startswith("INPUT ")}
if expected not in inputs:
    print("✗ managed index: current index was not included; use \\printindex", file=sys.stderr)
    sys.exit(1)
PY
    then exit 1; fi
  fi
  cur_pdf_hash=$(python3 "$SCRIPT_DIR/hash_file.py" "$PDF" 2>/dev/null)
  echo "✓ converged: passes $((pass-1)) and $pass have identical PDF+aux state ($cur_pdf_hash)"
else
  echo "✗ NOT CONVERGED after 5 passes — references/TOC may be stale."
fi

count() { local n; n=$(grep -c "$1" "$LOG" 2>/dev/null) || true; echo "${n:-0}"; }
miss=$(count "Missing character")
# v4.1.4: a "^!" line is NOT proof of an error. When TeX reports an overfull
# box it dumps the offending material, hard-wrapped at ~79 chars, with the
# fonts spelled out inline (\OT1/cmr/m/n/12 ...). Math-symbol glyphs print as
# their font SLOT, and cmsy slot 33 — which is what \to sets — is "!". So a
# wrap that lands just before a \to starts the continuation line with "!" and
# the old count booked it as a LaTeX error. Measured on data-science-exams:
# one overfull arrow chain produced `LaTeX errors (^!): 1` plus a bogus
# "✗ LaTeX error(s): ! ^^@\OT1/cmr/m/n/12 0..." — a phantom that survived
# until the *unrelated* overfull was fixed, i.e. the gate named the wrong
# defect and pointed at no source line.
# Whitelisting the real openers is not enough: they include "! Undefined
# control sequence." AND "!  ==> Fatal error occurred", so "^! [A-Za-z]"
# drops the fatal one. The discriminator is the CONTENT DUMP's own signature
# instead — an inline font selector, which no genuine error message carries.
# The rule itself lives in scripts/tex_error_lines.sh so it can be asserted
# against canned logs: reproducing the wrap end-to-end is environment-dependent
# (see that file), which is exactly the kind of fixture that rots.
errlines() { bash "$SCRIPT_DIR/tex_error_lines.sh" "$LOG"; }
errs=$(errlines | wc -l | tr -d ' ')
toks=$(count "Token not allowed")
# v3.58: REFERENCE INTEGRITY. Until now this was NOT gated anywhere — a typo'd
# \ref shipped as a literal "??" on the page while this script printed
# "✓ clean build" (verified: engine exits 0, no ^! line, and the ?? survives the
# byte-identical convergence loop, so the "converged" signal actively reassures).
# The render gate is blind too: ?? is neither reversed Latin nor a mirrored
# paren-digit group. The registry record for this class (BLD-3) had even
# claimed compilation itself catches multiply-defined/undefined — that gate did
# not exist anywhere until this version, and the record was corrected with it. Both strings below are unambiguous, 0-FP LaTeX summaries,
# and both mean the shipped PDF is WRONG: "??" for the first, a silently wrong
# number for the second.
undef=$(count "There were undefined references")
multi=$(count "There were multiply-defined labels")
# v3.60: DROPPED FOOTNOTE. A page-bottom \footnote uses \insert\footins, and inserts
# do NOT migrate out of a horizontal box — so a \footnote inside a bare tabular cell
# (any column type, incl. p{}), a \multicolumn cell, a TikZ node, a \parbox, or a
# \text{} in math prints its MARKER and silently loses the NOTE TEXT. Compiles clean,
# 0 missing characters, and all three source/render gates pass. LuaTeX does leave one
# unambiguous trace, which is what this counts. Measured 0-FP: 8/8 lossy contexts fire;
# 15/15 non-lossy contexts stay silent (prose, itemize, \figcap, \tabcap, all six
# colored boxes, tablebox+tabular, minipage, minipage>tabular, longtable, a footnote
# split across pages, \footnotemark+\footnotetext, …), and 147 real build logs from a
# corpus that genuinely uses footnotes produced ZERO hits.
dropfn=$(count "unreferenced destination with name 'Hfootnote")
# v3.76: DROPPED LISTING TEXT. Everything between \begin{lstlisting}(+options)
# and the end of that SOURCE LINE is consumed into \lst@dropped and never
# rendered — listings emits a WARNING, the compile exits 0, and the code line
# is simply absent from the PDF. Measured (probe, 3/3 shapes): bare code,
# code after [options], and a %-tail all drop; the canonical
# \begin{lstlisting}[style=...] with code on the NEXT line stays silent.
# The string is package-owned and emitted only in this case — 0-FP by
# construction (0 hits across the fleet's build logs today).
droplst=$(count "Text dropped after begin of listing")
# A bidi callback must never be converted into a successful build with an
# unreordered node list. Keep this sentinel as a hard gate even though the
# canonical preamble does not install such a guard.
bidi_skips=$(count "HEBLLP-BIDI-SKIP:")
fontwarn=$(count "LaTeX Font Warning")
# v3.70: OTHER destination warnings were invisible — the gate greps only the
# Hfootnote family. "ignoring duplicate destination" outside the benign
# lstnumber./lstlisting./page. families means two anchors CLAIMED THE SAME NAME
# and one link now lands on the wrong one. Warn tier for the benign families
# (the skill's own examples emit 5 of those); count the rest for the hard gate.
dupdest_all=$(count "ignoring duplicate destination")
dupdest_bad=$(grep "ignoring duplicate destination" "$LOG" 2>/dev/null | grep -cvE "name '(lstnumber|lstlisting|page)\." || true)
dupdest_bad=${dupdest_bad:-0}
pages=$(pdfinfo "$PDF" 2>/dev/null | awk '/^Pages:[[:space:]]*/ { print $2; found=1; exit } END { if (!found) print "?" }')
ovf_all=$(count "Overfull .hbox")
# v3.62: OVERFULL \vbox = CONTENT RAN OFF THE BOTTOM AND IS LOST. Until now this was
# counted nowhere: every counter here matched "Overfull .hbox" (and the >5pt/>15pt
# filters additionally required "too wide", which a vbox message never says). An
# unbreakable box taller than the text block — a tall tikzpicture inside tikzpic, a
# minipage, a \parbox — cannot be split and there are no float environments in this
# pipeline to move it, so LuaTeX writes it past the media box and the tail is simply
# absent from the PDF. Measured on three sites: 17, 26 and 25 of 45 rows LOST, with
# 0 errors, 0 missing characters, and all three source/render gates PASS. Hard fail:
# silent irreversible content loss on an otherwise green build is the worst class we
# track. Fix: cap the box (tikz `scale=`, \resizebox) or split it into two figures.
# CRITICAL — the phrase matters. A blanket "Overfull \vbox" count has a ~100-instance
# FALSE-POSITIVE floor: mdframed's split machinery emits bursts of
#   Overfull \vbox (Xpt too high) detected at line N
# whenever it declines to split a box and moves it whole to the next page. That is the
# BENIGN signal DEFECTS already documents (verified visually: zero clipping, the cost is
# white space). Measured on assets/example_tables.tex: 102 benign, max 103.9pt.
# The LOSS case is distinguished by the page builder being active:
#   Overfull \vbox (Xpt too high) has occurred while \output is active
# i.e. the box could not fit and was written past the media box. Measured on a tall
# tikzpicture: exactly 1, 810.3pt, 26 of 45 rows absent from the PDF. Gate on that
# phrase only — 1 true positive vs 102 benign correctly ignored.
ovf_vbox=$(count "Overfull .vbox (.*) has occurred while .output is active")
ovf_vis=$(grep -oE "Overfull .hbox \([0-9.]+pt too wide\)" "$LOG" 2>/dev/null | grep -oE "[0-9.]+pt" | sed 's/pt//' | awk '$1>5' | wc -l | tr -d ' ')
ovf_big=$(grep -oE "Overfull .hbox \([0-9.]+pt too wide\)" "$LOG" 2>/dev/null | grep -oE "[0-9.]+pt" | sed 's/pt//' | awk '$1>15' | wc -l | tr -d ' ')

echo "────────────────────────────────────────"
echo "  lualatex exit (final pass): $rc2"
echo "  missing characters     : $miss   (MUST be 0)"
echo "  LaTeX errors (^!)       : $errs"
echo "  hyperref PDF warnings   : $toks   (math in a heading without \\texorpdfstring?)"
echo "  undefined references    : $undef   (MUST be 0 — else '??' ships on the page)"
echo "  multiply-defined labels : $multi   (MUST be 0 — else \\ref prints a wrong number)"
echo "  dropped footnotes       : $dropfn   (MUST be 0 — note text lost from a box/cell)"
echo "  dropped listing text    : $droplst   (MUST be 0 — code on the \\begin line is lost)"
echo "  unreordered bidi boxes : $bidi_skips   (MUST be 0)"
echo "  font substitutions     : $fontwarn   (MUST be 0)"
echo "  pages                   : $pages"
echo "  overfull hboxes         : ${ovf_all:-0} total, ${ovf_vis:-0} visible (>5pt), ${ovf_big:-0} margin-breaking (>15pt)"
echo "  overfull VBOXES         : ${ovf_vbox:-0}   (MUST be 0 — content ran off the page BOTTOM and is LOST)"
echo "────────────────────────────────────────"

fail=0
if [ "$CONVERGED" != "1" ]; then
  fail=1
fi

# 1) Did the compile actually succeed AND (re)write the PDF this run?
if [ "${rc2:-1}" -ne 0 ]; then
  # v4.0.1c: name the ERROR, then PRESERVE the log. The compile happens in a
  # mktemp -d that is removed on exit, so the failing log was destroyed while a
  # stale copy next to the source stayed behind looking clean — four diagnostic
  # rounds were spent reading that stale copy. A 15-line tail also cannot reach the
  # error when the engine's end-of-run statistics fill the window, which is exactly
  # what happens on a capacity failure.
  # v4.26.0 (BLD-69): the naming moved to report_engine_failure, which runs
  # right after the failing pass — this block was unreachable for every
  # document on the canonical preamble, because the recorded-source gate
  # stopped the build first. Its raw "^! " grep could also print BLD-55 dump
  # phantoms; the record above uses the same discriminator as the count.
  echo "✗ lualatex exited non-zero ($rc2) on the final pass — build FAILED (the error is named above, at the pass that failed)."
  # v4.1.4: the copy itself moved to cleanup(), which now covers EVERY
  # unpublished exit rather than this one path; it prints the same
  # "── full log preserved:" line, so duplicating it here only doubled it.
  fail=1
fi
if [ ! -s "$PDF" ]; then
  echo "✗ no PDF produced ($PDF)."
  fail=1
fi

# 2) Missing glyphs = silent tofu. Hard fail.
if [ "$miss" != "0" ]; then
  echo "✗ $miss missing glyph(s) — sample:"
  grep "Missing character" "$LOG" | head -3
  echo "  → usually a missing [no-math] on fontspec, a missing Latin fallback,"
  echo "    or a body font with no Hebrew. See references/recipe.md."
  fail=1
fi

# 3) Hard LaTeX errors.
if [ "$errs" != "0" ]; then
  echo "✗ LaTeX error(s):"; errlines | head -5; fail=1
fi
if [ "$bidi_skips" != "0" ]; then
  echo "✗ $bidi_skips bidi callback failure(s) were converted to unreordered output."
  echo "  A box that bypassed bidi reordering is not deliverable; fix the source or toolchain."
  fail=1
fi
if [ "$fontwarn" != "0" ]; then
  echo "✗ $fontwarn LaTeX font warning(s): requested weight/style was substituted."
  grep -A2 "LaTeX Font Warning" "$LOG" | head -12
  echo "  Define the missing face (or an explicit synthetic face); silent substitution is not deliverable."
  fail=1
fi

# 3b) v3.58: reference integrity. A broken \ref is SILENT at every other gate —
# it renders "??" (or a wrong number) and the compile exits 0. Hard fail; the
# per-key warning lines name the exact label, so print those, not the summary.
if [ "$undef" != "0" ]; then
  echo "✗ undefined reference(s) — '??' is on the page:"
  # NB: match only up to the key. LaTeX hard-wraps log lines at ~79 chars, so the
  # trailing "undefined" is often split across two lines ("undef\nined") and a
  # pattern anchored on it silently matches nothing (measured).
  grep -E "LaTeX Warning: (Reference|Citation) \`" "$LOG" | head -5
  # v3.69: a missing BIBLIOGRAPHY is a different cause with the same summary line.
  # \bibliography{refs} expects a bibtex pass this pipeline never runs (and
  # biblatex/biber are not installed) — the key is perfectly fine, so the
  # label-typo advice below sent the author hunting for a typo that isn't there.
  if grep -qE "No file .*\.bbl|\\\\bibdata" "$LOG"; then
    echo "  → this document uses \\bibliography{...}: this pipeline NEVER runs bibtex."
    echo "    Use a thebibliography environment instead (see SKILL.md, bibliography)."
  else
    echo "  → fix the \\label/\\ref key (typo, or a \\label that moved between parts)."
  fi
  fail=1
fi
if [ "$multi" != "0" ]; then
  echo "✗ multiply-defined label(s) — \\ref will print a WRONG number:"
  grep -E "LaTeX Warning: Label .* multiply defined" "$LOG" | head -5
  echo "  → make each \\label unique; prefix keys per part."
  fail=1
fi

# 3c) v3.60: dropped footnote — the marker printed but the NOTE TEXT is gone.
if [ "$dropfn" != "0" ]; then
  echo "✗ $dropfn footnote(s) SILENTLY DROPPED — the marker prints, the text is lost:"
  grep "unreferenced destination with name 'Hfootnote" "$LOG" | head -5
  echo "  → a \\footnote inside a bare tabular cell (any column type), a \\multicolumn,"
  echo "    a TikZ node, a \\parbox or a \\text{} in math cannot migrate out of the box."
  echo "    Use \\footnotemark[n] in the cell + \\footnotetext[n]{...} after the box."
  echo "    NOTE: the UNNUMBERED \\footnotemark/\\footnotetext pair prints the same"
  echo "    number twice when there are two notes — always pass the [n]."
  fail=1
fi

# 3d) v3.76: dropped listing text — code written on the \begin{lstlisting} line
# is consumed by the package and absent from the PDF; the compile stays green.
if [ "${droplst:-0}" != "0" ]; then
  echo "✗ $droplst listing line(s) SILENTLY DROPPED — text on a \\begin{lstlisting}"
  echo "  line is consumed by the package and is NOT in the PDF:"
  grep "Text dropped after begin of listing" "$LOG" | head -5
  echo "  → put the code on the line AFTER \\begin{lstlisting}[...] — nothing may"
  echo "    follow the options bracket on that line, INCLUDING a '%' comment:"
  echo "    '%' eats its own newline, so the first body line is spliced onto the"
  echo "    \\begin line and THAT is the line that vanishes (the log then names"
  echo "    the body line, not the \\begin line). v3.82, compile-proven."
  fail=1
fi

# 4) Broken PDF strings make navigation wrong; this is a hard quality gate.
if [ "$toks" != "0" ]; then
  # v3.62: this used to assert the cause was "a heading with math". That is only ONE
  # cause, and it misdirected: the fleet's 70 corrupted bookmarks came from \en{} in a
  # heading, with no math anywhere, so an author who checked was sent hunting for
  # something that wasn't there. State the general cause and let the log name the token.
  echo "⚠ $toks hyperref PDF-string warning(s): a heading contains a command hyperref"
  echo "  cannot put in a PDF string (the log names it). Math needs a clean"
  echo "  \\texorpdfstring{...}{plain}. Bookmarks must be clean before delivery."
  fail=1
fi

# 4b) v3.62: overfull \vbox — an unbreakable box taller than the page. HARD fail:
# the tail of the box is not in the PDF at all. Fires on a tall tikzpicture in
# tikzpic, a minipage or a \parbox; measured 3/3 on those sites.
if [ "${dupdest_bad:-0}" != "0" ]; then
  echo "✗ ${dupdest_bad} duplicate destination NAME(s) outside the benign families —"
  echo "  two anchors claimed the same name; a link now lands on the WRONG one:"
  grep "ignoring duplicate destination" "$LOG" | grep -vE "name '(lstnumber|lstlisting|page)\." | head -3
  fail=1
fi
if [ "${ovf_vbox:-0}" != "0" ]; then
  echo "✗ ${ovf_vbox} overfull \\vbox(es) — CONTENT RAN OFF THE PAGE BOTTOM AND IS LOST:"
  grep -E "Overfull .vbox .* has occurred while .output is active" "$LOG" | head -5
  echo "  → an unbreakable box (tall tikzpicture in tikzpic, minipage, \\parbox) cannot"
  echo "    split, and this pipeline has no float environments to move it. Cap it with"
  echo "    tikz scale= / \\resizebox, or split it into two figures. The rows past the"
  echo "    break are ABSENT from the PDF, not merely clipped."
  # v3.67: a LONG MULTI-LINE DISPLAY is the other producer of this exact signal —
  # amsmath forbids page breaks inside align/gather by default, so a 40-row align
  # is one unbreakable vbox (measured: rows 34-40 absent, 229.6pt overfull while
  # \output active). The remedy above ("scale / split the figure") misdirects for
  # that cause; the correct fix is different and one line.
  echo "  → if the culprit is a LONG align/gather (not a figure): amsmath forbids"
  echo "    page breaks inside displays by default — add \\allowdisplaybreaks before"
  echo "    it (or \\\\* to protect specific rows), and it breaks cleanly across pages."
  fail=1
fi

# 5) Overfull hboxes = text past the margin/box. Never a hard fail (the PDF is
# valid), but VISIBLE ones (>5pt) are real friction; <3pt is a glyph touching
# the margin and is usually fine. MARGIN-BREAKING ones (>15pt) are called out
# separately: since v3.45.0 inline math is ATOMIC (cannot wrap), so a >15pt
# overflow is almost always a wide inline island that must move to a \[...\]
# display. See "חריגת שוליים" in figures-boxes-listings.md.
if [ "${ovf_vis:-0}" != "0" ]; then
  echo "⚠ ${ovf_vis} visible overfull hbox(es) (>5pt — text spills past the margin/box):"
  grep -oE "Overfull .hbox \([0-9.]+pt too wide\)( in paragraph at lines [0-9]+--[0-9]+| detected at line [0-9]+)" "$LOG" \
    | sort -t'(' -k2 -rn | head -6 | sed 's/^/    /'
  echo "  → usually a wide unbreakable LTR island. Fixes: a compact single island,"
  echo "    ONE item per line in step-boxes, an otherlanguage code column, or {\\small}"
  echo "    for a wide align*. Re-run after each fix; sub-3pt residues are acceptable."
  if [ "${ovf_big:-0}" != "0" ]; then
    echo "  ‼ ${ovf_big} of these are MARGIN-BREAKING (>15pt) — almost always a wide"
    echo "    inline-math island (atomic since v3.45.0, so it cannot wrap). Move the"
    echo "    wide result into a \\[...\\] display; do NOT try to force it inline."
    fail=1
  fi
fi

if [ "$fail" -ne 0 ]; then
  echo "✗ BUILD NOT OK — fix the above and rebuild."
  exit 1
fi

# v4.0.2 — PAPER-SIZE CONTRACT. TeX classes silently default to Letter when an
# author drops `a4paper`; a source declaration is therefore not proof of the
# delivered sheet. Validate BOTH MediaBox and CropBox on EVERY page. A different
# supported paper is permitted only when explicitly selected by the caller.
# EXPECTED_PAPER was validated by the build-contract preflight.
if [ ! -f "$SCRIPT_DIR/check_pdf_page_size.py" ]; then
  echo "✗ required page-size checker is missing: $SCRIPT_DIR/check_pdf_page_size.py"
  exit 2
fi
echo ""
echo "▶ page-size check (expected=$EXPECTED_PAPER):"
if ! python3 "$SCRIPT_DIR/check_pdf_page_size.py" \
    --expected "$EXPECTED_PAPER" "$PDF"; then
  echo "✗ PAGE-SIZE GATE FAILED — A4 is the default; use EXPECTED_PAPER only"
  echo "  when the requested deliverable explicitly requires another paper size."
  echo "  BUILD NOT OK."
  exit 1
fi

# v3.22 — RENDER GATE: inspect the compiled PDF itself (reversed Latin runs,
# flipped folio digits). This is a HARD gate — every historical bidi defect of
# this class compiled clean and passed every source-level check.
if [ -f "$SCRIPT_DIR/check_pdf_render.py" ]; then
  echo ""
  echo "▶ render check (compiled PDF):"
    # New documents default to zero split object/caption destinations. A legacy
    # document may opt into an explicit reviewed count with
    # MAX_CROSS_PAGE_DESTINATIONS=N; the waiver is never implicit.
    if ! python3 "$SCRIPT_DIR/check_pdf_render.py" --max-cross-page \
        "$MAX_CROSS_PAGE_DESTINATIONS" --folio-layout "$PDF_FOLIO_LAYOUT" \
        --folio-band "$PDF_FOLIO_BAND" --caption-color "$PDF_CAPTION_COLOR" \
        --caption-label-weight "$PDF_CAPTION_LABEL_WEIGHT" \
        "$PDF" "${SOURCE_FILES[@]}"; then
      # v3.65: this used to assert "the PDF contains reversed text" for EVERY
      # render-gate exit, including INK-OFF-PAPER (content off the sheet),
      # MIRRORED-PAREN-DIGITS, and exit 2 (unreadable PDF). Sending an author
      # hunting for reversed text when the real fault is a figure running off
      # the page wastes the diagnosis the gate just printed. Point at it instead.
      echo "✗ RENDER GATE FAILED — see the ✗ lines above for the specific rule."
      echo "  BUILD NOT OK."
      exit 1
    fi
fi

# v4.2.0 (adopted): metadata / outline / internal-navigation gate. The render
# gate proves the CAPTION destinations land correctly (R6); this one resolves
# EVERY bookmark and internal link annotation to a real page object, validates
# the outline hierarchy, and — only when the project declares the contract via
# PDF_REQUIRE_TITLE / PDF_MIN_BOOKMARKS / PDF_MIN_BOOKMARK_DEPTH /
# DIRECT_NAVIGATION_DESTINATIONS — enforces title and completeness. Measured
# motivation: the 426-page data-science anthology carried 661 internal actions
# and 134 bookmarks through every earlier gate while shipping with NO PDF
# title; nothing in the pipeline looked at metadata or the outline tree.
echo ""
echo "▶ PDF metadata / outline / navigation check:"
if ! python3 "$SCRIPT_DIR/check_pdf_navigation.py" \
    ${PDF_NAVIGATION_ARGS[@]+"${PDF_NAVIGATION_ARGS[@]}"} "$PDF"; then
  echo "✗ PDF NAVIGATION GATE FAILED — repair metadata/bookmarks before delivery."
  echo "  BUILD NOT OK."
  exit 1
fi

# v3.22 — font identity: several preamble rules are FONT-SPECIFIC facts about
# Frank Ruhl Libre (no tlig -> type — directly; no italic -> FakeSlant face).
# If the body font changed, those rules are silently wrong — say so.
if ! grep -qi "FrankRuhlLibre" "$LOG" 2>/dev/null; then
  echo "⚠ Frank Ruhl Libre not found in the log — the body font differs, so the"
  echo "  font-specific rules (em-dash, FakeSlant italics) may not apply as-is."
fi

# v3.23.3 — the convergence loop above already ends with two byte-identical
# consecutive passes (that IS the reproducibility proof, taken at the fixed
# point). REPRO=1 adds one independent confirmation pass on top; a mismatch
# here means genuine run-to-run flakiness, not TOC convergence.
if [ "$REPRO" = "1" ]; then
  h1=$(build_state_hash)
  run_latex
  repro_rc=$?
  report_engine_failure "the reproducibility pass" "$repro_rc"
  if ! check_recorded_sources "reproducibility pass"; then
    recorded_gate_failed "the reproducibility pass" "$repro_rc"
    exit 1
  fi
  run_index_stage || exit 1
  h2=$(build_state_hash)
  if [ "$repro_rc" -ne 0 ] || [ -z "$h1" ] || [ -z "$h2" ]; then
    echo "✗ reproducibility pass failed (lualatex exit $repro_rc)."
    exit 1
  elif [ "$h1" = "$h2" ]; then
    echo "✓ reproducible: extra pass has identical PDF+aux state ($h1)"
  else
    echo "✗ NOT reproducible AT THE FIXED POINT: $h1 != $h2"
    exit 1
  fi
fi

# Re-read the bytes of every project-local input consumed by the final pass.
# A source/image edit during the render/navigation gates must never let a stale
# PDF be published against a newer source tree.
FINAL_PROJECT_INPUT_HASH="$(project_input_hash)" || {
  echo "✗ project inputs became unreadable after the final compile. BUILD NOT OK."
  exit 1
}
if [ "$FINAL_PROJECT_INPUT_HASH" != "$PROJECT_INPUT_HASH" ]; then
  echo "✗ project inputs changed after the final LuaLaTeX pass — refusing to publish"
  echo "  a PDF that no longer matches the current source tree. Rebuild from a stable snapshot."
  exit 1
fi

# Recheck the final observation and installed bytes immediately before publication.
# The build requires trusted stable sources; this is not a concurrency boundary.
if ! python3 "$SCRIPT_DIR/verify_font_bundle.py" "$HEBREW_LATEX_FONT_DIR" || \
   ! python3 "$SCRIPT_DIR/check_runtime_fonts.py" "$LOG" \
       --font-dir "$HEBREW_LATEX_FONT_DIR" --source-list "$ACTUAL_TEX_SOURCE_LIST"; then
  echo "✗ runtime font gate failed before publication. BUILD NOT OK."
  exit 1
fi

# Publish atomically only after every hard gate has passed. The helper creates
# a unique same-directory temporary and replaces the destination entry itself,
# so a pre-existing symlink is never followed. A failed build leaves the
# previous deliverable untouched.
if ! python3 "$SCRIPT_DIR/atomic_replace.py" "$PDF" "$TARGET_PDF"; then
  echo "✗ cannot publish the verified PDF atomically: $TARGET_PDF"
  exit 2
fi
PUBLISHED=1
if [ "$INDEX_PROCESSOR" = makeindex ] && [ -n "${HLLPDF_INDEX_EVIDENCE_DIR:-}" ]; then
  if ! python3 "$SCRIPT_DIR/build_contract.py" --index-base "$BASE" \
      --project-root "$PROJECT_ROOT" --index-style "$INDEX_STYLE" \
      --index-evidence-dir "$HLLPDF_INDEX_EVIDENCE_DIR"; then
    echo "⚠ verified PDF published, but requested index evidence was not retained."
  fi
fi
# A clean run must not leave a stale .failed.* trio behind claiming otherwise.
rm -f "$(dirname "$TEX_ABS")/$STEM.failed.log" \
      "$(dirname "$TEX_ABS")/$STEM.failed.pdf" \
      "$(dirname "$TEX_ABS")/$STEM.failed.aux"
echo "✓ clean build: $TARGET_PDF"
echo "  VERIFY VISUALLY (not optional):"
echo "    pdftoppm -png -r 110 \"$TARGET_PDF\" page"

# Content-density heuristic — non-failing and profile-aware. Generic applies
# only universal friction/emphasis checks; opt into genre budgets with
# CONTENT_PROFILE=study-guide|report|exam|formula-sheet|review-sheet.
if [ -f "$SCRIPT_DIR/check_content_density.py" ]; then
  echo ""
  echo "▶ content-density check (profile=$DENSITY_PROFILE; informational):"
  # Architecture/runtime layers are infrastructure, not document content.
  # Query the canonical contract instead of hard-coding legacy carrier names:
  # v4.7.0 split clean_variant into clean_theme + exam_components, and the old
  # case-list immediately started feeding those new layers to the editorial
  # density heuristic. A role-aware filter makes future layer additions safe.
  DENSITY_EXEMPT_BASENAMES=()
  while IFS= read -r architecture_name || [ -n "$architecture_name" ]; do
    [ -n "$architecture_name" ] && DENSITY_EXEMPT_BASENAMES[${#DENSITY_EXEMPT_BASENAMES[@]}]="$architecture_name"
  done < <(python3 "$SCRIPT_DIR/architecture_contract.py" density-exempt-basenames)
  DENSITY_SOURCE_FILES=()
  for density_source in "${TEX_SOURCE_FILES[@]}"; do
    density_base="$(basename "$density_source")"
    density_is_arch=0
    for architecture_name in "${DENSITY_EXEMPT_BASENAMES[@]}"; do
      if [ "$density_base" = "$architecture_name" ]; then
        density_is_arch=1
        break
      fi
    done
    [ "$density_is_arch" -eq 1 ] && continue
    DENSITY_SOURCE_FILES[${#DENSITY_SOURCE_FILES[@]}]="$density_source"
  done
  if [ "${#DENSITY_SOURCE_FILES[@]}" -eq 0 ]; then
    DENSITY_SOURCE_FILES=("$TEX_ABS")
  fi
  python3 "$SCRIPT_DIR/check_content_density.py" \
    --profile "$DENSITY_PROFILE" "${DENSITY_SOURCE_FILES[@]}" || true
fi
