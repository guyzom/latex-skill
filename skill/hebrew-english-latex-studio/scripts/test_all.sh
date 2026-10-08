#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# Original project code; scope and terms: ../LICENSING.md.
# test_all.sh — the skill's regression harness. ONE command that proves:
#   T1. the linters fire on every known bug class (tests/lint_positives.tex ->
#       every flag in tests/expected_flags.txt) and stay silent on correct
#       patterns (tests/lint_negatives.tex),
#   T2. the charset gate rejects confusable codepoints and passes clean text,
#       custom section macros participate in density analysis, and source
#       hazards catch bare command words, Needspace-in-multicols and
#       compile-time pgfplots contours (BLD-70),
#   T2e4. the PDF navigation checker's unit suite passes — runtime-generated
#       direct/valid-named/unresolved-named twins plus metadata/outline
#       contract fixtures (v4.2.0; static, runs under FAST=1 too),
#   T3. all bundled example documents build clean end-to-end via build.sh
#       (which now includes the render gate),
#   T3c. the v3.78 listing line numbers are still ON THE RENDERED PAGE, both
#       halves — the in-exbox listing of example_exam.pdf and the pystyle/
#       htmlstyle listings of example_listings.pdf — each with a MUTATION of
#       the real shipped asset as its negative control (scripts/probe_lstnum.py),
#   T3d. an overfull box's CONTENT DUMP is not counted as a LaTeX error —
#       \to is cmsy slot 33 ("!"), so a wrapped dump line can open with
#       "!" — while all five real error openers still count (BLD-55), incl.
#       a "! Font \TU/…" error that itself quotes a selector (BLD-57), and
#       the --context record build.sh prints for a failed pass carries each
#       measured error's message and its l.N/<*> line (BLD-69),
#   T3e. a run that fails a GATE still exports its log, its PDF and its aux
#       next to the source, so the page numbers the gate names can be opened
#       (the PDF must be READABLE, not merely nonempty — BLD-71, v4.27.0)
#       and labels map through the failing run's own aux, and a clean run
#       leaves no .failed.* residue behind (BLD-56),
#   T4. the render checker catches a deliberately-reversed TikZ token
#       (tests/render_broken.tex) AND the pinned v3.24.1 \eqref-mirroring
#       regression (tests/render_eqref_broken.tex, rule R4), and is quiet on
#       a clean document,
#   T4b. the destination gate (R6) fires on tests/dest_broken.tex — naming
#       BOTH table shapes and the figure shape — and is silent on its
#       character-for-character twin tests/dest_ok.tex, which is therefore the
#       regression pin for the v3.79 \end{tablebox} anchor corrector,
#   T4c. R6c counts the cross-page caption destinations (BLD-38) instead of
#       leaving them invisible: on tests/dest_crosspage.tex it names the ONE
#       figure whose caption broke to the next page and stays silent on the
#       healthy same-page twin, and --max-cross-page turns that population
#       into a hard budget (0 -> exit 1, 1 -> exit 0),
#   T5. builds are reproducible (two compiles -> identical sha256),
#   T6. the docs police themselves: the ```latex exemplar blocks inside
#       SKILL.md + references/*.md pass
#       the linters (scripts/lint_doc_examples.py) — the docs must not teach
#       a bug — and the gate provably fires (tests/doc_examples_broken.md)
#       via the full standing probe matrix (v3.39.4): the broken fixture
#       must FAIL with every signal class present ([FLAG] lines, charset
#       exit code on control bytes AND invisible bidi chars,
#       RAW-CONTROL-CHAR on TAB), and the exempt fixture
#       (tests/doc_examples_exempt.md) must PASS — the ```latex-bad and
#       ❌→✅ skip conventions are load-bearing exemptions; and (v4.2.2)
#       every markdown link in the operative docs resolves to a file inside
#       the package and every #fragment to a real heading
#       (scripts/lint_doc_links.py — referential integrity, with broken/ok
#       fixture controls; CHANGELOG exempt as narrative).
#
# Run it after ANY change to the preamble, a checker, or an example file —
# a checker without a test that proves it fires is an assertion, not a check
# (the v3.19 box-chain checker was dropped for exactly this reason).
#
# Usage:  bash scripts/test_all.sh            # full run (compiles everything)
#         FAST=1 bash scripts/test_all.sh     # skip LuaLaTeX; still needs fonts + Poppler
# Full studio releases also require an exact candidate's sealed catalog matrix:
# HEBREW_LATEX_CATALOG_MATRIX_EVIDENCE and HEBREW_LATEX_CATALOG_CANDIDATE_SHA.
# Build/render with test_studio_matrix.py, actually inspect/record primary pages,
# and --seal them before FULL; FAST runs the catalog/documentation contracts only.
#         HEBREW_LATEX_CATALOG_VISUAL=routine bash scripts/test_all.sh
#             # v5.4.1: FULL that is not a release -- every check except the
#             # catalog visual release gate, and one check fewer. Never implied.
set -uo pipefail
INVOCATION_DIR="$(pwd)"
if [ -n "${HEBREW_LATEX_FONT_DIR:-}" ] \
   && [[ "$HEBREW_LATEX_FONT_DIR" != /* ]]; then
  HEBREW_LATEX_FONT_DIR="$INVOCATION_DIR/$HEBREW_LATEX_FONT_DIR"
fi
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$SKILL_ROOT"
# Prerequisites are not regression results. Abort once, before any test or
# cleanup trap, rather than cascading into misleading document failures.
# FAST intentionally checks only the Python QA baseline here; it does not
# acquire a new dependency on a live TeX engine.
case "${FAST:-0}" in
  0|1) ;;
  *) echo "❌ FAST must be 0 or 1"; exit 2 ;;
esac
export PYTHONDONTWRITEBYTECODE=1
if ! command -v python3 >/dev/null 2>&1; then
  echo "❌ python3 is required for harness preflight"
  exit 2
fi
if [ "${FAST:-0}" = "1" ]; then
  python3 "$SCRIPT_DIR/doctor.py" --qa-only
  PREFLIGHT_RC=$?
else
  python3 "$SCRIPT_DIR/doctor.py"
  PREFLIGHT_RC=$?
fi
if [ "$PREFLIGHT_RC" -ne 0 ]; then
  echo "❌ harness prerequisites failed; no regression tests ran"
  exit 2
fi
# Every harness run owns one private scratch directory. Fixed /tmp names make
# concurrent runs race and let a pre-existing symlink redirect log output.
HARNESS_TMP="$(mktemp -d "${TMPDIR:-/tmp}/hllpdf-test.XXXXXX")" || {
  echo "❌ cannot create harness scratch directory"
  exit 2
}
if [ -z "$HARNESS_TMP" ] || [ ! -d "$HARNESS_TMP" ]; then
  echo "❌ harness scratch allocator returned no usable directory"
  exit 2
fi
# BLD-58: the harness compiles into its OWN tree -- assets/example_*.pdf (12)
# and tests/ fixtures (28) -- and package_skill.py is not git-aware, so leaving
# them behind means the next run's hygiene gate (T2d7, which runs EARLY) rejects
# debris the previous run created. Measured: clean tree 163/0, immediate rerun
# 161/2, identical 40-file set both times. The sweep runs in the EXIT trap so an
# interrupted run cleans up too, and it derives its target set from
# check_package_hygiene.py, so it removes exactly what that gate rejects and is
# a provable no-op on a pristine checkout (asserted by T2d9, not assumed).
cleanup_harness_tmp() {
  rm -rf "$HARNESS_TMP"
  [ -f "$SCRIPT_DIR/clean_harness_artifacts.py" ] \
    && python3 "$SCRIPT_DIR/clean_harness_artifacts.py" "$SKILL_ROOT" --quiet >/dev/null 2>&1
  return 0
}
trap cleanup_harness_tmp EXIT
mkdir "$HARNESS_TMP/font-cache" || {
  echo "❌ cannot create private harness font cache"
  exit 2
}
export TEXMFCACHE="$HARNESS_TMP/font-cache"
export TEXMFVAR="$TEXMFCACHE"
trap 'exit 130' INT
trap 'exit 143' TERM HUP
# v4.0.1: the fixtures under tests/ \input ../assets/preamble.tex, and v4.0.0's
# source-graph gate resolves dependencies against PROJECT_ROOT — which defaults to
# the .tex file's own directory, i.e. tests/. Every tests/ build was therefore
# rejected with "dependency escapes project root", surfacing as the droplst
# FALSE-POSITIVE that failed this harness. The project here is the SKILL, not
# tests/; declaring it is what this variable is for, and the default is untouched,
# so a real collection (whose src/ is self-contained) keeps the tighter boundary.
export HEBREW_LATEX_PROJECT_ROOT="$SKILL_ROOT"
export SOURCE_DATE_EPOCH="${SOURCE_DATE_EPOCH:-1700000000}"
export PYTHONDONTWRITEBYTECODE=1
BUNDLED_FONT_DIR="$SCRIPT_DIR/../assets/fonts"
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
  # luaotfload/fontconfig discovery; TTFONTS also makes kpathsea/kpsewhich
  # prefer the VERIFIED bundle when TeX Live ships a same-named DejaVu face.
  # Without TTFONTS, kpsewhich can resolve the texmf copy first and build.sh
  # rejects its own pinned bundle on otherwise healthy hosts.
  export OSFONTDIR="$HEBREW_LATEX_FONT_DIR${OSFONTDIR:+:$OSFONTDIR}:"
  export TTFONTS="$HEBREW_LATEX_FONT_DIR${TTFONTS:+:$TTFONTS}:"
fi
PASS=0; FAIL=0
ok()   { echo "  ✓ $1"; PASS=$((PASS+1)); }
bad()  { echo "  ✗ $1"; FAIL=$((FAIL+1)); }

echo "═══ T1: lint golden tests ═══"
# v3.71: FLOOR assertion. T1 is data-driven off expected_flags.txt with no
# minimum — emptying that file used to yield "11 passed, 0 failed, ALL TESTS
# PASS" with 41 checks silently GONE (measured). The suite must know its own
# expected size.
NFLAGS=$(grep -c . tests/expected_flags.txt || true)
if [ "${NFLAGS:-0}" = "47" ]; then ok "expected_flags.txt carries exactly 47 flags"
else bad "expected_flags.txt carries ${NFLAGS:-0} flags (want exactly 47)"; fi
# v4.17.0: printed flags do not prove that a checker completed successfully.
# Finding fixtures must exit 1; clean fixtures must exit 0. A crash after
# printing all expected flags, or a silent tooling failure, must not pass.
if POS_OUT=$(python3 scripts/check_bidi_figures.py tests/lint_positives.tex 2>&1); then
  POS_RC=0
else
  POS_RC=$?
fi
while read -r flag; do
  [ -z "$flag" ] && continue
  if [ "$POS_RC" = "1" ] && grep -q "\[$flag\]" <<< "$POS_OUT"; then ok "fires: $flag"
  else bad "positive fixture: $flag missing or checker exit $POS_RC (want 1)"; fi
done < tests/expected_flags.txt
if NEG_OUT=$(python3 scripts/check_bidi_figures.py tests/lint_negatives.tex 2>&1); then
  NEG_RC=0
else
  NEG_RC=$?
fi
NEG_HITS=$(grep -c '^tests/.*\[' <<< "$NEG_OUT" || true)
if [ "$NEG_RC" = "0" ] && [ "${NEG_HITS:-0}" = "0" ]; then ok "silent on negatives (exit 0)"
else bad "negative fixture: checker exit $NEG_RC (want 0), $NEG_HITS finding(s)"; fi

echo "═══ T1b: checker selftest corpus (678 cases) ═══"
# v3.83: FLOOR assertion, the lesson T1 learned in v3.71 and this block never
# did. selftest.py fails only on `failures`, so emptying CASES/SCOPE_CASES
# printed "✓ selftest: all 0 cases pass" and this harness printed "✓ selftest
# corpus passes" with the suite's LARGEST body of evidence silently gone
# (measured). A corpus that does not know its own size cannot detect deletion.
NCASES=$(python3 -c "import sys; sys.path.insert(0,'scripts'); import selftest; print(len(selftest.CASES)+len(selftest.SCOPE_CASES))" 2>/dev/null || echo 0)
if [ "${NCASES:-0}" = "678" ]; then ok "selftest corpus carries exactly 678 cases"
else bad "selftest corpus carries ${NCASES:-0} cases (want exactly 678)"; fi
if python3 scripts/selftest.py >/dev/null 2>&1; then ok "selftest corpus passes"
else bad "selftest corpus DRIFTED (run: python3 scripts/selftest.py)"; fi
ARCH_TEX_FILES=()
while IFS= read -r architecture_rel || [ -n "$architecture_rel" ]; do
  [ -n "$architecture_rel" ] && ARCH_TEX_FILES[${#ARCH_TEX_FILES[@]}]="$architecture_rel"
done < <(python3 scripts/architecture_contract.py runtime-assets)
if [ "${#ARCH_TEX_FILES[@]}" -gt 0 ] && \
   python3 scripts/check_bidi_figures.py "${ARCH_TEX_FILES[@]}" >/dev/null 2>&1; then
  ok "all declared architecture TeX assets stay checker-clean"
else bad "checker false-positive or empty architecture asset query"; fi

echo "═══ T1c: v4.18 heading and short-code source contracts ═══"
if python3 scripts/test_v4180.py >"$HARNESS_TMP/v4180.log" 2>&1; then
  ok "v4.18 direct heading, source-gate and short-code contracts"
else
  cat "$HARNESS_TMP/v4180.log"
  bad "v4.18 direct source contracts failed"
fi
if [ "${FAST:-0}" != "1" ]; then
  if python3 scripts/test_v4180_runtime.py >"$HARNESS_TMP/v4180-runtime.log" 2>&1; then
    ok "v4.18 real-engine heading order, deep labels and code flow"
  else
    cat "$HARNESS_TMP/v4180-runtime.log"
    bad "v4.18 real-engine contracts failed"
  fi
fi

echo "═══ T1d: v4.19 PDF-string and explicit-renderer contracts ═══"
if python3 scripts/test_v4190.py >"$HARNESS_TMP/v4190.log" 2>&1; then
  ok "v4.19 PDF-string source and explicit renderer contracts"
else
  cat "$HARNESS_TMP/v4190.log"
  bad "v4.19 source/renderer contracts failed"
fi
if [ "${FAST:-0}" != "1" ]; then
  if python3 scripts/test_v4190_runtime.py >"$HARNESS_TMP/v4190-runtime.log" 2>&1; then
    ok "v4.19 real-engine PDF strings and pixel-preserving repair"
  else
    cat "$HARNESS_TMP/v4190-runtime.log"
    bad "v4.19 real-engine PDF-string contracts failed"
  fi
fi

echo "═══ T1e: v4.20 union, quote boundaries and starred references ═══"
if python3 scripts/test_v4200.py >"$HARNESS_TMP/v4200.log" 2>&1; then
  ok "v4.20 source boundaries, starred references and both inherited branches"
else
  cat "$HARNESS_TMP/v4200.log"
  bad "v4.20 source/union contracts failed"
fi
if [ "${FAST:-0}" != "1" ]; then
  if python3 scripts/test_v4200_runtime.py >"$HARNESS_TMP/v4200-runtime.log" 2>&1; then
    ok "v4.20 real-engine quote sweeps, pixel equivalence and starred references"
  else
    cat "$HARNESS_TMP/v4200-runtime.log"
    bad "v4.20 real-engine quote/reference contracts failed"
  fi
fi

echo "═══ T1f: v4.21 smart-quote listing contracts ═══"
if python3 scripts/test_v4210.py >"$HARNESS_TMP/v4210.log" 2>&1; then
  ok "v4.21 bounded glyph probe and codepoint registration contracts"
else
  cat "$HARNESS_TMP/v4210.log"
  bad "v4.21 source/probe contracts failed"
fi
if [ "${FAST:-0}" != "1" ]; then
  if python3 scripts/test_v4210_runtime.py >"$HARNESS_TMP/v4210-runtime.log" 2>&1; then
    ok "v4.21 listing order, overrides, scope and ASCII regression"
  else
    cat "$HARNESS_TMP/v4210-runtime.log"
    bad "v4.21 real-engine listing contracts failed"
  fi
fi

echo "═══ T1g: v4.22 observed canonical font resources ═══"
if python3 scripts/test_v4220.py >"$HARNESS_TMP/v422_unit.log" 2>&1; then
  ok "v4.22 path/hash/inventory and private-cache contracts"
else bad "v4.22 unit controls failed"; cat "$HARNESS_TMP/v422_unit.log"; fi
if [ "${FAST:-0}" != "1" ]; then
  if python3 scripts/test_v4220_runtime.py >"$HARNESS_TMP/v422_runtime.log" 2>&1; then
    ok "v4.22 real font selection, relocation and prior-output preservation"
  else bad "v4.22 runtime controls failed"; cat "$HARNESS_TMP/v422_runtime.log"; fi
fi

echo "═══ T1h: v4.23 lexical source-literal boundaries ═══"
if python3 scripts/test_v4230.py >"$HARNESS_TMP/v423_unit.log" 2>&1; then
  ok "v4.23 literal boundaries, live-math detection and CLI contracts"
else bad "v4.23 unit controls failed"; cat "$HARNESS_TMP/v423_unit.log"; fi
if [ "${FAST:-0}" != "1" ]; then
  if python3 scripts/test_v4230_runtime.py >"$HARNESS_TMP/v423_runtime.log" 2>&1; then
    ok "v4.23 printed literals, formula errors and pre-engine rejection"
  else bad "v4.23 runtime controls failed"; cat "$HARNESS_TMP/v423_runtime.log"; fi
fi

echo "═══ T1i: v4.24 declared and printed folios ═══"
if python3 scripts/test_v4240.py >"$HARNESS_TMP/v424_unit.log" 2>&1; then
  ok "v4.24 labels, footer geometry, legacy and dependency contracts"
else bad "v4.24 unit controls failed"; cat "$HARNESS_TMP/v424_unit.log"; fi
if [ "${FAST:-0}" != "1" ]; then
  if python3 scripts/test_v4240_runtime.py >"$HARNESS_TMP/v424_runtime.log" 2>&1; then
    ok "v4.24 Roman/mixed folios, real wrong footer and output preservation"
  else bad "v4.24 runtime controls failed"; cat "$HARNESS_TMP/v424_runtime.log"; fi
fi

echo "═══ T1j: native languages and general-document architecture ═══"
if python3 scripts/test_language_context.py >"$HARNESS_TMP/language_context.log" 2>&1; then
  ok "five language profiles, local context, source-part inheritance and legacy lint"
else bad "language context controls failed"; cat "$HARNESS_TMP/language_context.log"; fi
if python3 scripts/test_new_document.py >"$HARNESS_TMP/new_document.log" 2>&1; then
  ok "generator language/genre/theme matrix, package inputs and non-clobber publication"
else bad "new document controls failed"; cat "$HARNESS_TMP/new_document.log"; fi
if python3 scripts/test_folio_layouts.py >"$HARNESS_TMP/folio_layouts.log" 2>&1; then
  ok "declared folio layouts, rotated geometry and invalid checker inputs"
else bad "folio layout controls failed"; cat "$HARNESS_TMP/folio_layouts.log"; fi
if python3 scripts/test_caption_styles.py >"$HARNESS_TMP/caption_styles.log" 2>&1; then
  ok "native English captions, declared palette and body-reference negative controls"
else bad "caption style controls failed"; cat "$HARNESS_TMP/caption_styles.log"; fi
if python3 scripts/test_paragraph_style.py >"$HARNESS_TMP/paragraph_style.log" 2>&1; then
  ok "genre-owned paragraph policy, typed enum and starter timing controls"
else bad "paragraph style source controls failed"; cat "$HARNESS_TMP/paragraph_style.log"; fi
if python3 scripts/test_editorial_boxes.py >"$HARNESS_TMP/editorial_boxes.log" 2>&1; then
  ok "ordinary callout title/body source policy and background mutation controls"
else bad "ordinary callout source controls failed"; cat "$HARNESS_TMP/editorial_boxes.log"; fi
if [ "${FAST:-0}" != "1" ]; then
  if python3 scripts/test_language_runtime.py >"$HARNESS_TMP/language_runtime.log" 2>&1; then
    ok "native language runtime, localized shell, list geometry, real italics and flow tables"
  else bad "native language runtime controls failed"; cat "$HARNESS_TMP/language_runtime.log"; fi
  if python3 scripts/test_generated_runtime.py >"$HARNESS_TMP/generated_runtime.log" 2>&1; then
    ok "generated custom English and bilingual source projects build through all gates"
  else bad "generated project runtime controls failed"; cat "$HARNESS_TMP/generated_runtime.log"; fi
  if python3 scripts/test_paragraph_style.py --with-engine >"$HARNESS_TMP/paragraph_style_runtime.log" 2>&1; then
    ok "native mixed and bilingual letters, academic paragraph boundaries and reference scope geometry"
  else bad "paragraph style runtime controls failed"; cat "$HARNESS_TMP/paragraph_style_runtime.log"; fi
  if python3 scripts/test_editorial_boxes.py --with-engine >"$HARNESS_TMP/editorial_boxes_runtime.log" 2>&1; then
    ok "six ordinary callouts preserve pale title bands and white bodies across language and page flow"
  else bad "ordinary callout runtime controls failed"; cat "$HARNESS_TMP/editorial_boxes_runtime.log"; fi
fi

echo "═══ T1j3: canonical studio catalog, documentation and coverage ═══"
if python3 scripts/test_template_registry.py >"$HARNESS_TMP/template_registry.log" 2>&1; then
  ok "canonical catalog resolver, typed hooks, dependency plans and malformed-input controls"
else bad "canonical catalog controls failed"; cat "$HARNESS_TMP/template_registry.log"; fi
if python3 scripts/test_studio_docs.py >"$HARNESS_TMP/studio_docs.log" 2>&1; then
  ok "bilingual glossary, canonical catalog documentation and stale-document controls"
else bad "studio documentation controls failed"; cat "$HARNESS_TMP/studio_docs.log"; fi
if python3 scripts/generate_studio_docs.py --check >"$HARNESS_TMP/studio_docs_check.log" 2>&1; then
  ok "installed catalog and glossary match their canonical generated bytes"
else bad "catalog or glossary documentation is stale"; cat "$HARNESS_TMP/studio_docs_check.log"; fi
if python3 scripts/test_component_fixtures.py >"$HARNESS_TMP/component_fixtures.log" 2>&1; then
  ok "every architecture asset, public API and configuration hook has source-backed native fixtures"
else bad "component fixture provenance controls failed"; cat "$HARNESS_TMP/component_fixtures.log"; fi
if python3 scripts/test_topicrail.py >"$HARNESS_TMP/topicrail.log" 2>&1; then
  ok "topic rail direction and labels follow the resolved document language"
else bad "topic rail language source controls failed"; cat "$HARNESS_TMP/topicrail.log"; fi
if python3 scripts/test_studio_matrix_contracts.py >"$HARNESS_TMP/studio_matrix_contracts.log" 2>&1; then
  ok "catalog matrix population, exact build alias identity and evidence negative controls"
else bad "catalog matrix contract controls failed"; cat "$HARNESS_TMP/studio_matrix_contracts.log"; fi
if python3 scripts/catalog_coverage.py --output "$HARNESS_TMP/catalog_coverage.json" >"$HARNESS_TMP/catalog_coverage.log" 2>&1; then
  ok "catalog examples, all architectural owners and every public hook have explicit QA assignments"
else bad "catalog coverage declarations are incomplete"; cat "$HARNESS_TMP/catalog_coverage.log"; fi
if [ "${FAST:-0}" != "1" ]; then
  if python3 scripts/test_topicrail_runtime.py >"$HARNESS_TMP/topicrail_runtime.log" 2>&1; then
    ok "topic rail real-engine native defaults, explicit directions, local language and old-bug controls"
  else bad "topic rail runtime controls failed"; cat "$HARNESS_TMP/topicrail_runtime.log"; fi
  # v5.4.1 (repository line, DEFECTS BLD-73): the evidence is bound to the
  # exact candidate archive and to the reviewing machine's binaries, so no CI
  # runner and no working tree can hold it. A run that is not a release says
  # so explicitly; only this gate is left out, and the size check below expects
  # one check fewer. Evidence, when given, is always verified.
  if [ -n "${HEBREW_LATEX_CATALOG_VISUAL:-}" ] && [ "$HEBREW_LATEX_CATALOG_VISUAL" != "routine" ]; then
    bad "HEBREW_LATEX_CATALOG_VISUAL accepts only 'routine' (got '$HEBREW_LATEX_CATALOG_VISUAL')"
  elif [ "${HEBREW_LATEX_CATALOG_VISUAL:-}" = "routine" ] \
       && [ -z "${HEBREW_LATEX_CATALOG_MATRIX_EVIDENCE:-}" ] && [ -z "${HEBREW_LATEX_CATALOG_CANDIDATE_SHA:-}" ]; then
    CATALOG_ROUTINE=1
    echo "  · catalog visual release gate not run: HEBREW_LATEX_CATALOG_VISUAL=routine (a regression run, not a release)"
  elif [ -z "${HEBREW_LATEX_CATALOG_MATRIX_EVIDENCE:-}" ] || [ -z "${HEBREW_LATEX_CATALOG_CANDIDATE_SHA:-}" ]; then
    bad "complete catalog visual gate requires HEBREW_LATEX_CATALOG_MATRIX_EVIDENCE and HEBREW_LATEX_CATALOG_CANDIDATE_SHA"
    echo "    Build the retained catalog matrix, actually inspect and record every primary page, then --seal it before FULL."
  elif python3 scripts/test_studio_matrix.py --verify "$HEBREW_LATEX_CATALOG_MATRIX_EVIDENCE" \
       --require-visual --candidate-sha "$HEBREW_LATEX_CATALOG_CANDIDATE_SHA" \
       >"$HARNESS_TMP/catalog_matrix_gate.log" 2>&1; then
    ok "exact candidate complete catalog builds, dual renders, primary page observations and sealed fresh replay"
  else bad "complete catalog visual release gate failed"; cat "$HARNESS_TMP/catalog_matrix_gate.log"; fi
fi

echo "═══ T1j2: academic presentation and selective equation numbering ═══"
if python3 scripts/test_academic.py >"$HARNESS_TMP/academic.log" 2>&1; then
  ok "academic caption contracts and negative controls preserve legacy defaults"
else bad "academic presentation source controls failed"; cat "$HARNESS_TMP/academic.log"; fi
if [ "${FAST:-0}" != "1" ]; then
  if python3 scripts/test_academic_runtime.py >"$HARNESS_TMP/academic_runtime.log" 2>&1; then
    ok "native academic papers preserve selective equation numbers, language, captions and targets"
  else bad "academic paper runtime controls failed"; cat "$HARNESS_TMP/academic_runtime.log"; fi
fi

echo "═══ T1j3: reference sheets, local density and column flow ═══"
if python3 scripts/test_reference.py >"$HARNESS_TMP/reference.log" 2>&1; then
  ok "reference layout, component and generator contracts preserve standard defaults"
else bad "reference sheet source controls failed"; cat "$HARNESS_TMP/reference.log"; fi
if [ "${FAST:-0}" != "1" ]; then
  if python3 scripts/test_reference_runtime.py >"$HARNESS_TMP/reference_runtime.log" 2>&1; then
    ok "reference sheets preserve native column order, math, content and destinations"
  else bad "reference sheet runtime controls failed"; cat "$HARNESS_TMP/reference_runtime.log"; fi
fi

echo "═══ T1j: v4.26 failed passes named, compile-time contours rejected ═══"
# BLD-69/BLD-70. The static half needs no LuaLaTeX: canned real-log tails,
# mutation proofs for each branch of the record finder, and build.sh driven
# against a MOCK engine (ordering of what a failed pass prints; the contour
# rule stops the build before the engine). The runtime half asserts, on the
# real engine, the preconditions that make both defects real before it asserts
# the gate's answer to them.
if python3 scripts/test_v4260.py >"$HARNESS_TMP/v4260.log" 2>&1; then
  ok "v4.26 failed-pass records, inventory reasons and mock-engine ordering"
else bad "v4.26 static contracts failed"; tail -30 "$HARNESS_TMP/v4260.log"; fi
if [ "${FAST:-0}" != "1" ]; then
  if python3 scripts/test_v4260_runtime.py >"$HARNESS_TMP/v4260_runtime.log" 2>&1; then
    ok "v4.26 real fatal compiles named, stale contour files never reach the engine"
  else bad "v4.26 runtime controls failed"; tail -30 "$HARNESS_TMP/v4260_runtime.log"; fi
fi

echo "═══ T1k: v4.27 a truncated PDF is not exported as evidence ═══"
# BLD-71. The static half needs no LuaLaTeX: build.sh's own readable_pdf_pages()
# over finished, truncated and zero-page PDFs (each confirmed by MuPDF too), and
# build.sh driven against a MOCK engine that leaves a PDF whatever its exit
# code, through all three export branches. The runtime half proves on the real
# engine that a stop after a shipped page leaves an unreadable file before it
# asserts the gate withholds it, next to a finished twin that is still exported.
if python3 scripts/test_v4270.py >"$HARNESS_TMP/v4270.log" 2>&1; then
  ok "v4.27 evidence predicate and all three export branches against a mock engine"
else bad "v4.27 static contracts failed"; tail -30 "$HARNESS_TMP/v4270.log"; fi
if [ "${FAST:-0}" != "1" ]; then
  if python3 scripts/test_v4270_runtime.py >"$HARNESS_TMP/v4270_runtime.log" 2>&1; then
    ok "v4.27 real stop after a shipped page withholds the PDF; the finished twin exports it"
  else bad "v4.27 runtime controls failed"; tail -30 "$HARNESS_TMP/v4270_runtime.log"; fi
fi

echo "═══ T1l: v4.28 startup safety, portable names and bilingual codebox gutters ═══"
if python3 scripts/test_v4280.py >"$HARNESS_TMP/v4280.log" 2>&1; then
  ok "v4.28 14 startup/path controls preserve prior output and reject malformed configuration"
else bad "v4.28 static controls failed"; tail -40 "$HARNESS_TMP/v4280.log"; fi
if [ "${FAST:-0}" != "1" ]; then
  if python3 scripts/test_v4280_runtime.py >"$HARNESS_TMP/v4280_runtime.log" 2>&1; then
    ok "v4.28 four-style codebox geometry, negative mutation and unchanged Hebrew pixels"
  else bad "v4.28 runtime controls failed"; tail -40 "$HARNESS_TMP/v4280_runtime.log"; fi
fi

echo "═══ T1m: v4.29 nested code/table ownership and frame boundaries ═══"
if [ "${FAST:-0}" != "1" ]; then
  if python3 scripts/test_v4290_runtime.py >"$HARNESS_TMP/v4290_runtime.log" 2>&1; then
    ok "v4.29 10 real-engine tests: 144 nested codeboxes, four mutations and split/scope controls"
  else bad "v4.29 nested-container controls failed"; tail -50 "$HARNESS_TMP/v4290_runtime.log"; fi
fi

echo "═══ T1n: v4.30 technical-symbol fidelity and harness startup ═══"
if python3 scripts/test_v4300.py >"$HARNESS_TMP/v4300.log" 2>&1; then
  ok "v4.30 bounded registration and fail-fast startup controls"
else bad "v4.30 static/startup controls failed"; cat "$HARNESS_TMP/v4300.log"; fi
if [ "${FAST:-0}" != "1" ]; then
  if python3 scripts/test_v4300_runtime.py >"$HARNESS_TMP/v4300_runtime.log" 2>&1; then
    ok "v4.30 real technical-symbol order, overrides and replay"
  else bad "v4.30 runtime contracts failed"; cat "$HARNESS_TMP/v4300_runtime.log"; fi
fi

# v4.31: optional heads follow class, heading language and actual page; deep
# reference names follow the current language without changing destinations.
echo "═══ T1o: v4.31 running-head scope, timing and deep-reference language ═══"
if [ "${FAST:-0}" != "1" ]; then
  if python3 scripts/test_v4310_runtime.py >"$HARNESS_TMP/v4310_runtime.log" 2>&1; then
    ok "v4.31 actual headings, four defect controls, language switches and managed builds"
  else bad "v4.31 runtime contracts failed"; cat "$HARNESS_TMP/v4310_runtime.log"; fi
fi

# v4.32: a fixed document title keeps its own language; cleanup must never
# follow a linked harness root into unrelated files.
echo "═══ T1p: v4.32 fixed-title language and cleanup boundaries ═══"
if python3 scripts/test_v4320.py >"$HARNESS_TMP/v4320.log" 2>&1; then
  ok "v4.32 cleanup boundaries, preserved sources and disposable mutation"
else bad "v4.32 cleanup controls failed"; cat "$HARNESS_TMP/v4320.log"; fi
if [ "${FAST:-0}" != "1" ]; then
  if python3 scripts/test_v4320_runtime.py >"$HARNESS_TMP/v4320_runtime.log" 2>&1; then
    ok "v4.32 fixed-title language, metadata, mutations and managed replay"
  else bad "v4.32 runtime controls failed"; cat "$HARNESS_TMP/v4320_runtime.log"; fi
fi

# v5.3.5: the repository line's folio-face rule (BLD-67), dropped by the
# v5.2.0 rewrite, is restored as v4.25.0 had it -- the (font, size) pair, which
# six correct fleet pages need (BLD-72). Static half outside the FAST gate; the
# engine twin is the lifting-optimization p.17 construction, precondition first.
echo "═══ T1q: v5.3.5 the folio face is the (font, size) pair ═══"
if python3 scripts/test_v5350.py >"$HARNESS_TMP/v5350.log" 2>&1; then
  ok "v5.3.5 same-font runs at another size filtered; same-size, wrong-folio and both mutations hold"
else bad "v5.3.5 static folio-face controls failed"; tail -30 "$HARNESS_TMP/v5350.log"; fi
if [ "${FAST:-0}" != "1" ]; then
  if python3 scripts/test_v5350_runtime.py >"$HARNESS_TMP/v5350_runtime.log" 2>&1; then
    ok "v5.3.5 real eta_opt in the folio font: precondition, accepted, font-only mutation rejects"
  else bad "v5.3.5 runtime folio-face control failed"; tail -30 "$HARNESS_TMP/v5350_runtime.log"; fi
fi

# v5.4.1 (BLD-73): a routine FULL run declares itself. Static: it sources the
# real catalog-gate and size-check sections with python3 intercepted.
echo "═══ T1r: v5.4.1 a routine FULL run declares itself ═══"
if python3 scripts/test_v5410.py >"$HARNESS_TMP/v5410.log" 2>&1; then
  ok "v5.4.1 routine leaves only the visual gate out; undeclared, unknown and partial runs fail; evidence always verified"
else bad "v5.4.1 routine-run controls failed"; tail -30 "$HARNESS_TMP/v5410.log"; fi

echo "═══ T2: charset gate ═══"
# v3.71: exit-code-SPECIFIC. The old "if checker; then bad; else ok" passed on
# ANY nonzero exit — deleting the fixture or a checker crash (exit 2/3) still
# printed ✓ (measured with a sys.exit(3) stub). A finding is exit 1 exactly.
python3 scripts/check_charset.py tests/charset_positive.tex >/dev/null 2>&1; rc=$?
if [ "$rc" = "1" ]; then ok "rejects confusable codepoints (exit 1)"
else bad "charset gate on the positive fixture exited $rc (want 1 = finding)"; fi
if python3 scripts/check_charset.py tests/lint_negatives.tex >/dev/null 2>&1; then
  ok "passes clean Hebrew text"
else bad "charset gate false-positive on clean text"; fi
if python3 scripts/check_charset.py tests/charset_literal_ok.tex >/dev/null 2>&1; then
  ok "accepts rendered Unicode symbols covered by the pinned mono font in literal code"
else bad "charset gate rejected a covered monospace codepoint"; fi
python3 scripts/check_charset.py tests/charset_literal_bad.tex >/dev/null 2>&1; rc=$?
if [ "$rc" = "1" ]; then
  ok "rejects a literal-code glyph absent from the pinned mono font"
else bad "missing monospace glyph fixture exited $rc (want 1 = finding)"; fi

echo "═══ T2b: source graph and recorder semantics ═══"
if python3 scripts/test_source_graph.py >/dev/null 2>&1; then
  ok "source resolver and .fls collector pass adversarial unit tests"
else bad "source graph tests failed (run: python3 scripts/test_source_graph.py)"; fi

echo "═══ T2c: pinned font bundle ═══"
if python3 scripts/test_font_bundle.py >/dev/null 2>&1; then
  ok "canonical font bundle verifies and a one-byte mutation fails"
else bad "font bundle verification tests failed"; fi

echo "═══ T2d: build trust/path guards ═══"
BUILD_GUARD_ARGS=()
if [ "${FAST:-0}" = "1" ]; then BUILD_GUARD_ARGS+=(--fast); fi
if python3 scripts/test_build_guards.py ${BUILD_GUARD_ARGS[@]+"${BUILD_GUARD_ARGS[@]}"} >/dev/null 2>&1; then
  if [ "${FAST:-0}" = "1" ]; then
    ok "invalid project root and build configuration are hard pre-engine failures"
  else
    ok "invalid project root/config and pass-2 recorder escape are hard failures"
  fi
else bad "build guard tests failed (run: python3 scripts/test_build_guards.py ${BUILD_GUARD_ARGS[*]-})"; fi

echo "═══ T2d2: package architecture contract ═══"
if python3 scripts/test_architecture.py >/dev/null 2>&1; then
  ok "layout/theme/mechanism ownership boundaries and backward-compatible defaults hold"
else bad "architecture contract failed (run: python3 scripts/test_architecture.py)"; fi

if [ "${FAST:-0}" != "1" ]; then
  echo "═══ T2d2b: runtime architecture guards ═══"
  if python3 scripts/test_architecture_runtime.py >/dev/null 2>&1; then
    ok "engine rejects missing-core, duplicate-layer and legacy/pure conflict compositions"
  else bad "runtime architecture guards failed (run: python3 scripts/test_architecture_runtime.py)"; fi
fi

echo "═══ T2d2c: font trust, new projects and recorded visual review ═══"
if python3 scripts/test_v480.py >"$HARNESS_TMP/v480_unit.log" 2>&1; then
  ok "12 adversarial font/project/review tests pass without shipping font programs"
else bad "v4.8.0 unit contracts failed"; tail -20 "$HARNESS_TMP/v480_unit.log"; fi
if [ "${FAST:-0}" != "1" ]; then
  if python3 scripts/test_v480_runtime.py >"$HARNESS_TMP/v480_runtime.log" 2>&1; then
    ok "4 real-engine controls preserve code, reader edges, source links and glyph-aware parentheses"
  else bad "v4.8.0 runtime controls failed"; tail -25 "$HARNESS_TMP/v480_runtime.log"; fi
fi

echo "═══ T2d2d: flow tables and independently checked review images ═══"
if python3 scripts/test_v490.py >"$HARNESS_TMP/v490_unit.log" 2>&1; then
  ok "12 explicit-attestation/raster/project/density unit controls pass"
else bad "v4.9.0 unit contracts failed"; tail -25 "$HARNESS_TMP/v490_unit.log"; fi
if [ "${FAST:-0}" != "1" ]; then
  if python3 scripts/test_v490_runtime.py >"$HARNESS_TMP/v490_runtime.log" 2>&1; then
    ok "7 real-engine flow-table tests preserve rows, digits, headers, numbering and destinations"
  else bad "v4.9.0 runtime controls failed"; tail -30 "$HARNESS_TMP/v490_runtime.log"; fi
fi

echo "═══ T2d2e: citation identity and release-output boundaries ═══"
if python3 scripts/test_v491.py >"$HARNESS_TMP/v491_unit.log" 2>&1; then
  ok "12 output-alias/debris/review unit controls pass"
else bad "v4.9.1 unit contracts failed"; tail -25 "$HARNESS_TMP/v491_unit.log"; fi
if [ "${FAST:-0}" != "1" ]; then
  if python3 scripts/test_v491_runtime.py >"$HARNESS_TMP/v491_runtime.log" 2>&1; then
    ok "7 real-engine citation controls preserve keys, digits, notes and exact source targets"
  else bad "v4.9.1 runtime controls failed"; tail -30 "$HARNESS_TMP/v491_runtime.log"; fi
fi

echo "═══ T2d2f: deferred note identity and prior-output recovery ═══"
if python3 scripts/test_preserve_output.py >"$HARNESS_TMP/preserve_output.log" 2>&1; then
  ok "14 no-clobber prior-output recovery unit controls pass"
else bad "prior-output recovery unit controls failed"; tail -25 "$HARNESS_TMP/preserve_output.log"; fi
if [ "${FAST:-0}" != "1" ]; then
  if python3 scripts/test_deferred_notes_runtime.py >"$HARNESS_TMP/deferred_notes_runtime.log" 2>&1; then
    ok "21 real-engine note controls preserve counters, bodies, languages, links and prior PDF"
  else bad "deferred note runtime controls failed"; tail -30 "$HARNESS_TMP/deferred_notes_runtime.log"; fi
fi

echo "═══ T2d2g: bilingual reference identity and dependency fingerprints ═══"
if python3 scripts/test_environment_report.py >"$HARNESS_TMP/environment_report.log" 2>&1; then
  ok "10 environment-report unit controls reject partial evidence and publish atomically"
else bad "environment-report unit controls failed"; tail -25 "$HARNESS_TMP/environment_report.log"; fi
if [ "${FAST:-0}" != "1" ]; then
  if python3 scripts/test_references_runtime.py >"$HARNESS_TMP/references_runtime.log" 2>&1; then
    ok "13 real-engine reference controls preserve glyphs, locales, targets and tag state"
  else bad "bilingual reference runtime controls failed"; tail -35 "$HARNESS_TMP/references_runtime.log"; fi
fi

echo "═══ T2d2h: measured TOC and list geometry ═══"
if python3 scripts/test_toc_layout.py >"$HARNESS_TMP/toc_geometry.log" 2>&1; then
  ok "13 geometry controls measure RTL/LTR gaps and reject missing or ambiguous anchors"
else bad "TOC geometry unit controls failed"; tail -25 "$HARNESS_TMP/toc_geometry.log"; fi
if [ "${FAST:-0}" != "1" ]; then
  if python3 scripts/test_toc_layout.py --runtime >"$HARNESS_TMP/toc_runtime.log" 2>&1; then
    ok "10 real-engine TOC/list controls cover 8 combinations, a mixed-language list and a broken mutant"
  else bad "measured TOC runtime controls failed"; tail -40 "$HARNESS_TMP/toc_runtime.log"; fi
fi


echo "═══ T2d2j: release continuity / non-clobber packaging ═══"
if python3 scripts/test_v4170.py >"$HARNESS_TMP/v4170.log" 2>&1; then
  ok "v4.17.0 release continuity and publication controls"
else
  cat "$HARNESS_TMP/v4170.log"
  bad "release continuity/publication tests failed"
fi

echo "═══ T2d2k: harness failure coverage and verified font acquisition ═══"
if python3 scripts/test_harness_controls.py >"$HARNESS_TMP/harness_controls.log" 2>&1; then
  ok "failed codebox prerequisites preserve all four controls and the correct project root"
else
  cat "$HARNESS_TMP/harness_controls.log"
  bad "harness scope/failure coverage controls failed"
fi
if python3 scripts/test_download_fonts.py >"$HARNESS_TMP/download_fonts.log" 2>&1; then
  ok "verified font acquisition rejects corrupt inputs and reports installer timeouts"
else
  cat "$HARNESS_TMP/download_fonts.log"
  bad "verified font acquisition controls failed"
fi

echo "═══ T2d2i: inline English scope, physical PDF geometry and crop-aware review ═══"
if python3 scripts/test_v4160.py >"$HARNESS_TMP/v4160.log" 2>&1; then
  ok "52 inline-language/physical-size/crop-review controls pass"
else
  cat "$HARNESS_TMP/v4160.log"
  bad "v4.16.0 regression controls failed"
fi

echo "═══ T2d3: portable maintenance-tool contracts ═══"
if python3 scripts/test_maintenance_tools.py >/dev/null 2>&1; then
  ok "portable SHA-256 and fleet sync are non-vacuous, two-phase and path-safe"
else bad "maintenance-tool tests failed (run: python3 scripts/test_maintenance_tools.py)"; fi

echo "═══ T2d4: validated QA environment ═══"
if python3 scripts/doctor.py --qa-only >/dev/null 2>&1; then
  ok "Python QA dependencies match the exact release-validation pins"
else bad "QA baseline drifted (run: python3 scripts/doctor.py --qa-only)"; fi

echo "═══ T2d5: shell portability contract ═══"
if python3 scripts/test_shell_portability.py >/dev/null 2>&1; then
  ok "runtime + harness avoid Bash-4/GNU-only shell constructs"
else bad "shell portability contract failed (run: python3 scripts/test_shell_portability.py)"; fi

echo "═══ T2d6: release metadata contract ═══"
if python3 scripts/test_release_contract.py >/dev/null 2>&1; then
  ok "version, QA pins, immutable-build wiring and release files agree"
else bad "release metadata contract failed (run: python3 scripts/test_release_contract.py)"; fi

echo "═══ T2d7: package hygiene ═══"
if python3 scripts/check_package_hygiene.py >/dev/null 2>&1; then
  ok "standalone package contains no caches, generated PDFs, symlinks or path collisions"
else bad "package hygiene failed (run: python3 scripts/check_package_hygiene.py)"; fi

echo "═══ T2d9: the harness cleans up after itself (BLD-58) ═══"
# Static (no LuaLaTeX), so it lives OUTSIDE the FAST gate and runs in both modes.
# Four assertions inside the script: pristine no-op, *.log.txt evidence survives,
# the measured debris goes, and -- the one that stops this from being vacuous --
# the same planted tree WITHOUT the sweep fails the hygiene gate. Always 1 here.
if python3 scripts/test_harness_cleanup.py >/dev/null 2>&1; then
  ok "artifact sweep is a pristine no-op, clears the measured debris, and is what makes the gate pass"
else bad "harness cleanup contract failed (run: python3 scripts/test_harness_cleanup.py)"; fi

echo "═══ T2d8: deterministic .skill packaging ═══"
if python3 scripts/test_packaging.py >/dev/null 2>&1; then
  ok "packager is deterministic across checkout names and fails closed on debris/self-output"
else bad "deterministic packaging tests failed (run: python3 scripts/test_packaging.py)"; fi

echo "═══ T2e: content-density profile policy ═══"
DENSITY_STUDY=$(python3 scripts/check_content_density.py \
  --profile study-guide tests/density_profiles.tex 2>&1); density_rc=$?
if [ "$density_rc" = "0" ] \
   && grep -q "THIN:" <<< "$DENSITY_STUDY" \
   && grep -q "0 worked exercises" <<< "$DENSITY_STUDY"; then
  ok "study-guide profile enables thin-content and exercise guidance"
else bad "study-guide profile lost one of its genre checks"; fi
DENSITY_REPORT=$(python3 scripts/check_content_density.py \
  --profile report tests/density_profiles.tex 2>&1); density_rc=$?
if [ "$density_rc" = "0" ] \
   && grep -q "THIN:" <<< "$DENSITY_REPORT" \
   && ! grep -q "0 worked exercises" <<< "$DENSITY_REPORT"; then
  ok "report profile keeps structure guidance without an exercise quota"
else bad "report profile applies the wrong genre policy"; fi
DENSITY_EXAM=$(python3 scripts/check_content_density.py \
  --profile exam tests/density_profiles.tex 2>&1); density_rc=$?
if [ "$density_rc" = "0" ] \
   && ! grep -q "THIN:" <<< "$DENSITY_EXAM" \
   && ! grep -q "0 worked exercises" <<< "$DENSITY_EXAM"; then
  ok "exam profile suppresses study-guide quotas"
else bad "exam profile inherited an incompatible study-guide quota"; fi
python3 scripts/check_content_density.py --profile unknown \
  tests/density_profiles.tex >/dev/null 2>&1; density_rc=$?
if [ "$density_rc" = "2" ]; then ok "unknown content profile is rejected"
else bad "unknown content profile exited $density_rc (want argparse exit 2)"; fi
DENSITY_RHYTHM=$(python3 scripts/check_content_density.py \
  --profile report tests/density_literal_rhythm.tex 2>&1); density_rc=$?
if [ "$density_rc" = "0" ] \
   && [ "$(grep -c 'RHYTHM:' <<< "$DENSITY_RHYTHM")" = "1" ] \
   && grep -q 'RHYTHM: section #2' <<< "$DENSITY_RHYTHM" \
   && grep -q '2 sections' <<< "$DENSITY_RHYTHM" \
   && ! grep -q '2 chapters\|chapter #2' <<< "$DENSITY_RHYTHM"; then
  ok "literal code breaks prose rhythm, and article diagnostics use section terminology"
else bad "density rhythm miscounted literal code or mislabeled article sections"; fi

DENSITY_CUSTOM_OFF=$(python3 scripts/check_content_density.py \
  --profile formula-sheet tests/density_custom_sections.tex 2>&1); density_rc=$?
DENSITY_CUSTOM_ON=$(SECTION_MACROS=fssec python3 \
  scripts/check_content_density.py --profile formula-sheet \
  tests/density_custom_sections.tex 2>&1); custom_density_rc=$?
if [ "$density_rc" = "0" ] && [ "$custom_density_rc" = "0" ] \
   && grep -q 'no \\chapter and <2 sections' <<< "$DENSITY_CUSTOM_OFF" \
   && grep -q 'custom section macro(s): \\fssec' <<< "$DENSITY_CUSTOM_ON" \
   && grep -q '3 sections' <<< "$DENSITY_CUSTOM_ON"; then
  ok "SECTION_MACROS maps custom headings to section-level density units"
else bad "custom section macro declaration was ignored or counted its definition"; fi

echo "═══ T2e2: clean-compiling source hazards ═══"
HAZARD_OUT=$(python3 scripts/check_source_hazards.py \
  tests/source_hazards_broken.tex 2>&1); hazard_rc=$?
if [ "$hazard_rc" = "1" ] \
   && [ "$(grep -c '\[BARE-LATEX-COMMAND\]' <<< "$HAZARD_OUT")" = "3" ] \
   && grep -q "'qquad' appears as text" <<< "$HAZARD_OUT" \
   && grep -q "'frac' appears as text" <<< "$HAZARD_OUT" \
   && grep -q "'mathrm' appears as text" <<< "$HAZARD_OUT"; then
  ok "bare qquad/frac/mathrm words inside math are hard findings"
else bad "source hazard gate missed a visible command word (exit $hazard_rc)"; fi
NEEDSPACE_OUT=$(python3 scripts/check_source_hazards.py \
  tests/source_hazards_needspace_warn.tex 2>&1); needspace_rc=$?
python3 scripts/check_source_hazards.py --strict-layout \
  tests/source_hazards_needspace_warn.tex >/dev/null 2>&1; needspace_strict_rc=$?
if [ "$needspace_rc" = "0" ] && [ "$needspace_strict_rc" = "1" ] \
   && grep -q '\[NEEDSPACE-IN-MULTICOLS\]' <<< "$NEEDSPACE_OUT" \
   && grep -q '\\fssec expands to \\Needspace' <<< "$NEEDSPACE_OUT"; then
  ok "Needspace expansion inside multicols warns by default and is strict-testable"
else bad "Needspace-in-multicols warning or strict mode regressed"; fi
if python3 scripts/check_source_hazards.py \
    tests/source_hazards_ok.tex >/dev/null 2>&1; then
  ok "source hazard checker stays quiet on corrected commands and nopagebreak headings"
else bad "source hazard checker false-positive on corrected fixture"; fi
# v4.26.0, BLD-70: compile-time pgfplots contours. The stale-table form of
# contour gnuplot passed every later gate ("✓ clean build", old figure), so
# the source rule is the only line of defence: exit 1 and EXACTLY the three
# uses, at their own lines, in reading order.
CONTOUR_OUT=$(python3 scripts/check_source_hazards.py \
  tests/source_hazards_contour_broken.tex 2>&1); contour_rc=$?
CONTOUR_LINES=$(grep -o 'contour_broken.tex:[0-9]*: \[PGFPLOTS-CONTOUR-EXTERNAL\]' <<< "$CONTOUR_OUT" \
  | cut -d: -f2 | tr '\n' ' ')
if [ "$contour_rc" = "1" ] && [ "$CONTOUR_LINES" = "6 8 9 " ] \
   && grep -q "'contour gnuplot'" <<< "$CONTOUR_OUT" \
   && grep -q "'contour external'" <<< "$CONTOUR_OUT" \
   && grep -q "'contour lua'" <<< "$CONTOUR_OUT"; then
  ok "contour lua/gnuplot/external are hard findings at lines 6, 8, 9 (BLD-70)"
else bad "compile-time contour rule missed a use or over-fired (exit $contour_rc, lines: ${CONTOUR_LINES:-none})"; fi
if python3 scripts/check_source_hazards.py \
    tests/source_hazards_contour_ok.tex >/dev/null 2>&1; then
  ok "contour prepared/filled, surf, and prose/comment/listing mentions stay quiet"
else bad "compile-time contour rule false-positive on the ok fixture"; fi

echo "═══ T3d: LaTeX-error count vs overfull content dumps (v4.1.4) ═══"
# BLD-55. `grep -c '^!'` counted an overfull box's CONTENT DUMP as an error:
# \to is cmsy slot 33 = "!", so a line wrap before one starts the line with
# "!". Measured on data-science-exams: "LaTeX errors (^!): 1" over a clean
# compile, citing no source line, curable only by fixing an unrelated box.
# Asserted on CANNED logs, not end-to-end: whether the dump wraps at all is
# environment-dependent (same engine, same machine — 79 chars on a 425-page
# build, 659 on a one-page fixture), so an end-to-end fixture would rot into
# a vacuous pass. Both counts are EXACT: a rule that returns nothing would
# otherwise pass the negative half while gating nothing.
NREAL=$(bash "$SKILL_ROOT/scripts/tex_error_lines.sh" tests/tex_errors_real.log.txt 2>/dev/null | wc -l | tr -d ' ')
NDUMP=$(bash "$SKILL_ROOT/scripts/tex_error_lines.sh" tests/tex_errors_dump.log.txt 2>/dev/null | wc -l | tr -d ' ')
if [ "$NREAL" = "5" ]; then ok "error count keeps all 5 real openers (incl. '!  ==> Fatal error' and the selector-quoting '! Font …' of BLD-57)"
else bad "error discriminator returned $NREAL of 5 real error lines — a real error can now ship silently"; fi
if [ "$NDUMP" = "0" ]; then ok "error count ignores overfull content dumps (no phantom '^!')"
else bad "error discriminator counted $NDUMP dump line(s) as errors — the BLD-55 phantom is back"; fi
# v4.26.0, BLD-69: --context is what build.sh prints the moment a pass fails.
# Eight REAL log tails (tests/tex_errors_ctx_*.log.txt), chosen so that every
# branch of the record finder is load-bearing for at least one of them: a TeX
# "!" error; \directlua errors, which carry no "!" at all (a failed require,
# the same inside a pgfplots macro — contour lua, BLD-70 — a syntax error and
# a callback error, the last two with no traceback, so only the chunk-name
# opener finds them); an error raised in a Lua FILE, found only by the
# traceback after it; a runaway argument, whose text precedes the "!" line and
# whose base context is <*>, not l.N; and a \latelua error glued mid-line.
# Each record must carry the message AND, after it, TeX's base context line.
# Static, so both checks run under FAST=1 too.
ctx_in_order() {
  local out m b
  out=$(bash "$SKILL_ROOT/scripts/tex_error_lines.sh" --context "$1" 2>/dev/null)
  m=$(grep -nF -- "$2" <<< "$out" | head -1 | cut -d: -f1)
  b=$(grep -nF -- "$3" <<< "$out" | head -1 | cut -d: -f1)
  [ -n "$m" ] && [ -n "$b" ] && [ "$m" -lt "$b" ]
}
NCTX=0; CTX_MISSED=""
while IFS='|' read -r ctx_shape ctx_msg ctx_base; do
  [ -z "$ctx_shape" ] && continue
  if ctx_in_order "tests/tex_errors_ctx_$ctx_shape.log.txt" "$ctx_msg" "$ctx_base"; then
    NCTX=$((NCTX + 1))
  else CTX_MISSED="$CTX_MISSED $ctx_shape"; fi
done <<'CTXEOF'
undefined|! Undefined control sequence.|l.4 \undefinedmacroxyz
lua_require|[\directlua]:1: module 'no_such_module_xyz' not found:|l.4 \directlua{require("no_such_module_xyz")}
contour_lua|[\directlua]:1: module 'doc_contourtmp0' not found:|l.6 ...s={1,2}}, domain=-2:2, samples=21] {x^2+y^2};
lua_syntax|[\directlua]:1: unexpected symbol near '='.|l.4 \directlua{x = = 1}
lua_callback|warning  (node filter): error: [\directlua]:1: cb boom|l.5 x\par
lua_file|./mymod.lua:2: module failure xyz|l.4 \directlua{require("mymod")}
runaway|Runaway argument?|<*> s09_runaway.tex
latelua|[\latelua]:1: late boom|l.5 \end{document}
CTXEOF
if [ "$NCTX" = "8" ]; then ok "a failed pass is named: all 8 measured error shapes print their message, then their l.N/<*> line (BLD-69)"
else bad "--context lost the message or the base line for:$CTX_MISSED ($NCTX of 8) — a failed pass would be reported without its error"; fi
NCTXDUMP=$(bash "$SKILL_ROOT/scripts/tex_error_lines.sh" --context tests/tex_errors_dump.log.txt 2>/dev/null | wc -l | tr -d ' ')
if [ "$NCTXDUMP" = "0" ]; then ok "--context opens no record on overfull content dumps (BLD-55 phantoms stay filtered)"
else bad "--context printed $NCTXDUMP line(s) from overfull content dumps — a dump phantom can pose as the error"; fi

echo "═══ T2e4: functional PDF navigation and portability policy (v4.2.0) ═══"
# Adversarial, runtime-generated PDF twins (the T4d anti-rot pattern): direct,
# valid-named, and unresolved-named navigation triplets, plus metadata/outline
# contract fixtures. Static — fitz only, no LuaLaTeX — so it runs under FAST=1.
if python3 scripts/test_pdf_navigation.py >/dev/null 2>&1; then
  ok "internal actions resolve and targeted portability rejects named/direct regressions"
else bad "PDF navigation tests failed (run: python3 scripts/test_pdf_navigation.py)"; fi

echo "═══ T2f: checker CLI help ═══"
HELP_OK=1
for checker in check_charset.py check_bidi_figures.py check_pdf_render.py \
               check_pdf_page_size.py check_pdf_navigation.py \
               check_source_hazards.py; do
  python3 "scripts/$checker" --help >"$HARNESS_TMP/hll_checker_help.out" 2>&1 || HELP_OK=0
  grep -qi 'usage:' "$HARNESS_TMP/hll_checker_help.out" || HELP_OK=0
done
if [ "$HELP_OK" = "1" ]; then ok "standalone checkers expose conventional --help"
else bad "one or more standalone checkers treat --help as an input path"; fi

echo "═══ T2g: render-source comment parsing ═══"
if PYTHONDONTWRITEBYTECODE=1 python3 - <<'PYEOF'
import sys
sys.path.insert(0, "scripts")
from check_pdf_render import source_latin_tokens
raise SystemExit(1 if "datapath" in source_latin_tokens(["tests/render_comment_parity.tex"]) else 0)
PYEOF
then ok "render token allow-list ignores comments after an even backslash run"
else bad "render token parser treated \\\\% comment text as rendered source"; fi

echo "═══ T2h: A4 paper contract ═══"
PAPER_TMP="$(mktemp -d)"
python3 - "$PAPER_TMP" <<'PYEOF'
import fitz
import sys
from pathlib import Path

root = Path(sys.argv[1])
a4 = fitz.paper_rect("a4")
letter = fitz.paper_rect("letter")

doc = fitz.open()
doc.new_page(width=a4.width, height=a4.height)
doc.new_page(width=a4.height, height=a4.width)
doc.save(root / "a4-both-orientations.pdf")

doc = fitz.open()
doc.new_page(width=letter.width, height=letter.height)
doc.save(root / "letter-negative.pdf")

doc = fitz.open()
doc.new_page(width=a4.width, height=a4.height)
doc.new_page(width=letter.width, height=letter.height)
doc.save(root / "mixed-negative.pdf")
PYEOF
if python3 scripts/check_pdf_page_size.py \
    "$PAPER_TMP/a4-both-orientations.pdf" >/dev/null 2>&1; then
  ok "A4 gate accepts every A4 page in portrait and landscape"
else bad "A4 gate rejected a canonical A4 orientation"; fi
PAPER_OUT=$(python3 scripts/check_pdf_page_size.py \
  "$PAPER_TMP/letter-negative.pdf" 2>&1); paper_rc=$?
if [ "$paper_rc" = "1" ] \
   && grep -q 'PAGE-SIZE-MISMATCH' <<< "$PAPER_OUT"; then
  ok "A4 default rejects a Letter PDF with an explicit size finding"
else bad "A4 default failed to reject the Letter negative control (exit $paper_rc)"; fi
PAPER_OUT=$(python3 scripts/check_pdf_page_size.py \
  "$PAPER_TMP/mixed-negative.pdf" 2>&1); paper_rc=$?
if [ "$paper_rc" = "1" ] \
   && grep -q 'p.2 \[PAGE-SIZE-MISMATCH\]' <<< "$PAPER_OUT"; then
  ok "A4 gate checks every page, not only the first"
else bad "A4 gate missed the non-A4 second page (exit $paper_rc)"; fi
if python3 scripts/check_pdf_page_size.py --expected letter \
    "$PAPER_TMP/letter-negative.pdf" >/dev/null 2>&1; then
  ok "an explicitly requested alternate paper is validated, never inferred"
else bad "explicit expected-paper validation rejected its matching PDF"; fi
rm -rf -- "$PAPER_TMP"

if [ "${FAST:-0}" != "1" ]; then
  echo "═══ T3a: public layout API compiles as a real alternate shell ═══"
  LAYOUT_TMP="$(mktemp -d)"
  cp assets/preamble.tex tests/layout_api.tex "$LAYOUT_TMP/"
  if (cd "$LAYOUT_TMP" && HEBREW_LATEX_PROJECT_ROOT="$LAYOUT_TMP" EXPECTED_PAPER=a5 \
      bash "$SKILL_ROOT/scripts/build.sh" layout_api.tex >"$HARNESS_TMP/t3_layout_api.log" 2>&1); then
    ok "pre-preamble layout hooks produce a clean A5/article build without editing the mechanism core"
  else
    bad "public layout API failed its A5/article build contract"
    tail -16 "$HARNESS_TMP/t3_layout_api.log" 2>/dev/null | sed 's/^/        │ OUT: /'
  fi
  rm -rf -- "$LAYOUT_TMP"

  LAYOUT_BAD_TMP="$(mktemp -d)"
  cp assets/preamble.tex tests/layout_unsupported_class.tex "$LAYOUT_BAD_TMP/"
  (
    cd "$LAYOUT_BAD_TMP"
    HEBREW_LATEX_PROJECT_ROOT="$LAYOUT_BAD_TMP" \
      bash "$SKILL_ROOT/scripts/build.sh" layout_unsupported_class.tex \
      >"$HARNESS_TMP/t3_layout_bad.log" 2>&1
  ); layout_bad_rc=$?
  if [ "$layout_bad_rc" = "1" ] \
      && grep -q "unsupported class.*use report or article" \
          "$LAYOUT_BAD_TMP/layout_unsupported_class.failed.log" 2>/dev/null; then
    ok "unsupported document class fails before entering the report/article mechanism contract"
  else
    bad "unsupported layout class did not fail with the declared contract (rc=$layout_bad_rc)"
  fi
  rm -rf -- "$LAYOUT_BAD_TMP"

  echo "═══ T3: example documents build clean (incl. render gate) ═══"
  # v3.82 (G1): the target PDF is REMOVED before its build and the build's
  # result is RECORDED. Without both, a failed build leaves the previous
  # run's PDF on disk and every later check that reads it (T3c, T4's
  # quiet-on-clean) measures a stale artifact while reporting on the build
  # that never happened — a developer-machine false all-clear.
  BUILT_STATUS_DIR="$(mktemp -d)"
  for f in example_math example_figures example_tables example_boxes example_topicrail example_listings example_exam example_reader example_flow_tables example_bibliography example_notes example_references; do
    rm -f "assets/$f.pdf"
    # v4.0.1: KEEP the build output and print the decisive lines when it fails.
    # "BUILD FAILED: example_math" with the reason discarded forced a full CI
    # round-trip per diagnosis — measured, twice, on this very PR. A gate that
    # knows why it failed must say so.
    if (cd assets && bash ../scripts/build.sh "$f.tex" >"$HARNESS_TMP/t3_$f.log" 2>&1); then
      : >"$BUILT_STATUS_DIR/$f"
      ok "builds clean: $f"
    else
      bad "BUILD FAILED: $f (run: cd assets && bash ../scripts/build.sh $f.tex)"
      # v4.0.1b: print the TAIL VERBATIM, not a grep. The first attempt filtered
      # on patterns and cut the one line that mattered — it surfaced
      # "Fatal error occurred" while dropping the "! ..." line that says WHY.
      # A diagnostic that pre-decides which evidence is relevant reproduces the
      # problem it was added to solve.
      # v4.0.1c: read the ERROR from the .log itself, not from build.sh's stdout.
      # build.sh prints a short "Last log lines" tail, and on a capacity/late failure
      # the "! ..." line sits ABOVE that window — two rounds were spent looking at a
      # tail that structurally could not contain the answer. Print the real error
      # lines with context, plus the engine's capacity counters, which already showed
      # the environments diverging (86 fonts locally, 109 in CI).
      grep -nE "^! |^\\*\\* |c capacity exceeded|No room for|Fatal" "assets/$f.log" 2>/dev/null \
        | head -12 | sed 's/^/        │ LOG: /'
      grep -E "fonts using|multiletter control|words of node" "assets/$f.log" 2>/dev/null \
        | sed 's/^/        │ CAP: /'
      tail -12 "$HARNESS_TMP/t3_$f.log" 2>/dev/null | sed 's/^/        │ OUT: /'; fi
  done
  A4_OK=1
  for f in example_math example_figures example_tables example_boxes example_topicrail example_listings example_exam example_reader example_flow_tables example_bibliography example_notes example_references; do
    if [ ! -f "$BUILT_STATUS_DIR/$f" ] \
       || ! python3 scripts/check_pdf_page_size.py --expected a4 \
              "assets/$f.pdf" >/dev/null 2>&1; then
      A4_OK=0
    fi
  done
  if [ "$A4_OK" = "1" ]; then ok "all bundled examples use the A4 page default"
  else bad "one or more bundled examples are not A4"; fi

  echo "═══ T3b: droplst gate — code on the \\begin{lstlisting} line (v3.76) ═══"
  # proof-of-failure first: build.sh must FAIL the broken twin (the code line
  # is consumed by listings with only a warning; the PDF compiles green) and
  # PASS the canonical next-line twin. BLD-49.
  # v3.83: exit-code-SPECIFIC (the v3.71 T2 lesson, uncured here until now).
  # `else` accepted ANY nonzero: deleting the fixture gives rc=2 ("no such
  # file") and a missing lualatex also gives rc=2 — both printed ✓ while the
  # gate under test never ran. Measured: `rm tests/build_droplst_broken.tex`
  # -> "74 passed, 0 failed", exit 0. A finding is exit 1 exactly.
  (cd tests && bash ../scripts/build.sh build_droplst_broken.tex >/dev/null 2>&1); rcd=$?
  if [ "$rcd" = "1" ]; then ok "droplst gate fires: same-line listing code fails the build"
  else bad "droplst gate on the broken fixture exited $rcd (want 1 = finding; 2 = fixture/tooling missing)"; fi
  if (cd tests && bash ../scripts/build.sh build_droplst_ok.tex >/dev/null 2>&1); then
    ok "droplst gate quiet on the canonical next-line form"
  else bad "droplst gate FALSE-POSITIVE: canonical listing form failed the build"; fi

  echo "═══ T3e: failing runs export their log/PDF/aux evidence ═══"
  # BLD-56. The compile happens in a mktemp -d removed on exit; v4.0.1c saved
  # the log only when lualatex itself died, but the common failure is a GATE
  # failing over a compile that SUCCEEDED — and there both the log and the PDF
  # died. What stayed behind was the previous run's output, which looks current:
  # measured on data-science-exams, the stale neighbour PDF was 458 pages
  # against the failing run's 425, so rendering the page the gate named showed
  # an unrelated question and the stale .aux then named the wrong source file.
  rm -f tests/build_errcount_dump.failed.log tests/build_errcount_dump.failed.pdf \
        tests/build_errcount_dump.failed.aux
  (cd tests && bash ../scripts/build.sh build_errcount_dump.tex >/dev/null 2>&1); rce=$?
  if [ "$rce" = "1" ]; then ok "overfull fixture fails the build (exit 1 = finding)"
  else bad "overfull fixture exited $rce (want 1; 2 = fixture/tooling missing)"; fi
  if [ -s tests/build_errcount_dump.failed.log ]; then ok "gate failure preserves the log next to the source"
  else bad "gate failure left no .failed.log — the failing log died with the temp dir (BLD-56)"; fi
  # v4.27.0 (BLD-71): READABLE, not merely nonempty. A truncated file is
  # nonempty too, and -s is exactly the test that let one through as evidence.
  t3e_pages=$(pdfinfo tests/build_errcount_dump.failed.pdf 2>/dev/null \
    | awk '/^Pages:[[:space:]]*[0-9]+[[:space:]]*$/ { print $2; exit }')
  if [ "${t3e_pages:-0}" -ge 1 ]; then ok "gate failure preserves a READABLE failing PDF for page-accurate diagnosis"
  else bad "gate failure left no readable .failed.pdf — the gate names page numbers nobody can open (BLD-56/BLD-71)"; fi
  if [ -s tests/build_errcount_dump.failed.aux ]; then ok "gate failure preserves the aux — labels map through THIS run, not the stale neighbour (v4.2.1)"
  else bad "gate failure left no .failed.aux — label→file mapping goes through the stale neighbour aux (BLD-56)"; fi
  # End-to-end tie-in for T3d: this fixture's whole point is a dump full of
  # cmsy "!" glyphs, and the run must never call that a LaTeX error.
  if bash -c 'cd tests && bash ../scripts/build.sh build_errcount_dump.tex 2>&1' | grep -q 'LaTeX error(s)'; then
    bad "overfull fixture reported a phantom LaTeX error end-to-end (BLD-55)"
  else ok "overfull fixture reports the overfull box only, no phantom error"; fi
  # NEGATIVE: a clean build must not leave a .failed.* trio claiming otherwise.
  # Seed a STALE trio deliberately. The pre-v4.3.1 clean path removed only
  # log/pdf, leaving .failed.aux behind after the next success — a false failure
  # marker and the exact stale-label evidence BLD-56 was designed to eliminate.
  printf 'stale\n' > tests/build_droplst_ok.failed.log
  printf 'stale\n' > tests/build_droplst_ok.failed.pdf
  printf 'stale\n' > tests/build_droplst_ok.failed.aux
  (cd tests && bash ../scripts/build.sh build_droplst_ok.tex >/dev/null 2>&1)
  if [ ! -e tests/build_droplst_ok.failed.log ] && [ ! -e tests/build_droplst_ok.failed.pdf ] \
     && [ ! -e tests/build_droplst_ok.failed.aux ]; then
    ok "clean build leaves no .failed.* residue"
  else bad "clean build wrote .failed.* residue — a passing run now looks failed"; fi
  rm -f tests/build_errcount_dump.failed.log tests/build_errcount_dump.failed.pdf \
        tests/build_errcount_dump.failed.aux \
        tests/build_droplst_ok.failed.log tests/build_droplst_ok.failed.pdf \
        tests/build_droplst_ok.failed.aux

  echo "═══ T3c: listing line numbers survive on the page (v3.78 pin) ═══"
  # T3 only COMPILED example_exam.tex and example_listings.tex, so BOTH halves
  # of v3.78 shipped pinned by NOTHING. Measured on this tree: deleting
  # clean_theme.tex's three \thelstnumber restore hooks left build.sh
  # printing "✓ clean build" and this harness at "ALL TESTS PASS" with the
  # digits gone. No reflow gate can see it either — exactly 3 words vanish
  # from the PDF and 0 words move — and the one log signal it does emit (two
  # "ignoring duplicate destination" lines, both named 'lstnumber.') is
  # filtered out by build.sh's dupdest_bad grep BY DESIGN. So the assertion
  # has to read the RENDERED page: scripts/probe_lstnum.py counts digits that
  # hang strictly LEFT of the code column on a code line's own y-band.
  # Each half gets a MUTATION OF THE REAL SHIPPED FILE as its negative
  # control, never a committed simulated twin: a static "broken" fixture
  # would still pass after the mechanism was deleted, the mutation cannot —
  # there would be nothing left to strip, and the guard below says so out loud.
  # Both branches of each guard emit exactly one ok/bad, so this block is
  # ALWAYS 4 checks so the harness total remains structurally stable. BLD-16.
  #
  # v3.82 (G1): T3c used to read assets/example_exam.pdf whether or not T3's
  # build of it succeeded. It now refuses to measure a PDF whose build failed
  # — both branches still emit exactly one ok/bad, so the block stays 4.
  LSTPIN=(--expect 3 --anchor "probe(products):")
  if [ ! -f "$BUILT_STATUS_DIR/example_exam" ]; then
    bad "example_exam did not build in T3 — the in-exbox numbering pin cannot run (would have measured a stale PDF)"
    bad "example_exam did not build in T3 — its negative control cannot run either"
  else
  python3 scripts/probe_lstnum.py assets/example_exam.pdf "${LSTPIN[@]}" >/dev/null 2>&1; rc=$?
  if [ "$rc" = "0" ]; then ok "example_exam.pdf hangs 1..3 left of the in-exbox listing"
  else bad "in-exbox listing numbering LOST (probe exit $rc; run: python3 scripts/probe_lstnum.py assets/example_exam.pdf ${LSTPIN[*]})"; fi
  MUT=$(mktemp -d)
  cp assets/preamble.tex assets/clean_theme.tex assets/exam_components.tex assets/example_exam.tex "$MUT/"
  HOOK='AtBeginEnvironment.*thelstnumber'
  NHOOK=$(grep -c "$HOOK" "$MUT/clean_theme.tex" || true)
  sed "/$HOOK/d" "$MUT/clean_theme.tex" > "$MUT/clean_theme.mutated"
  mv "$MUT/clean_theme.mutated" "$MUT/clean_theme.tex"
  if [ "${NHOOK:-0}" != "3" ]; then
    bad "negative control is DEAD: found ${NHOOK:-0} \thelstnumber restore hooks in clean_theme.tex (want 3) — the source-of-truth mutation no longer reproduces the pre-v3.78 rendering"
  else
    (cd "$MUT" && lualatex -interaction=nonstopmode example_exam.tex >/dev/null 2>&1 \
                && lualatex -interaction=nonstopmode example_exam.tex >/dev/null 2>&1)
    python3 scripts/probe_lstnum.py "$MUT/example_exam.pdf" "${LSTPIN[@]}" >/dev/null 2>&1; rc=$?
    if [ "$rc" = "1" ]; then ok "pin fires: hook-stripped clean_theme renders it numberless (exit 1)"
    else bad "pin DID NOT FIRE on hook-stripped clean_theme (probe exit $rc, want 1) — the pure-theme numbering check is decoration"; fi
  fi
  rm -rf "$MUT"
  fi
  # v3.78 half (b): numbers=left on pystyle/htmlstyle. 16 digits on
  # example_listings.pdf = 4 asm + 6 cstyle + 3 pystyle + 3 htmlstyle, so the
  # mutation (strip numbers=left from the two styles defined at/after pystyle
  # — asm and cstyle are defined earlier and keep theirs) must drop it to 10.
  if [ ! -f "$BUILT_STATUS_DIR/example_listings" ]; then
    bad "example_listings did not build in T3 — the margin-digit pin cannot run (would have measured a stale PDF)"
    bad "example_listings did not build in T3 — its negative control cannot run either"
  else
  python3 scripts/probe_lstnum.py assets/example_listings.pdf --expect 16 >/dev/null 2>&1; rc=$?
  if [ "$rc" = "0" ]; then ok "example_listings.pdf carries all 16 margin digits (asm+cstyle+pystyle+htmlstyle)"
  else bad "listing numbering LOST in example_listings.pdf (probe exit $rc; run: python3 scripts/probe_lstnum.py assets/example_listings.pdf --expect 16)"; fi
  MUT=$(mktemp -d)
  cp assets/preamble.tex assets/example_listings.tex "$MUT/"
  NNUM=$(sed -n '/lstdefinestyle{pystyle}/,$p' "$MUT/preamble.tex" | grep -c "numbers=left" || true)
  sed -e '/lstdefinestyle{pystyle}/,$ {' -e '/numbers=left/d' -e '}' \
    "$MUT/preamble.tex" > "$MUT/preamble.mutated"
  mv "$MUT/preamble.mutated" "$MUT/preamble.tex"
  if [ "${NNUM:-0}" != "2" ]; then
    bad "negative control is DEAD: found ${NNUM:-0} numbers=left keys at/after pystyle in preamble.tex (want 2) — the mutation no longer reproduces the pre-v3.78 rendering"
  else
    (cd "$MUT" && lualatex -interaction=nonstopmode example_listings.tex >/dev/null 2>&1 \
                && lualatex -interaction=nonstopmode example_listings.tex >/dev/null 2>&1)
    python3 scripts/probe_lstnum.py "$MUT/example_listings.pdf" --expect 16 >/dev/null 2>&1; rc=$?
    if [ "$rc" = "1" ]; then ok "pin fires: pystyle/htmlstyle without numbers=left lose 6 digits (exit 1)"
    else bad "pin DID NOT FIRE on the numbers=left-stripped pystyle/htmlstyle (probe exit $rc, want 1) — the listing-style numbering check is decoration"; fi
  fi
  rm -rf "$MUT"
  fi
  rm -rf -- "$BUILT_STATUS_DIR"
fi

if [ "${FAST:-0}" != "1" ]; then
  echo "═══ T3f: codebox in-frame line numbers (v4.5.0) ═══"
  # codebox is the one framed box whose listing keeps its margin numbers. That
  # works only because the listing follows the BOX (resetmargins=false) and is
  # indented with xrightmargin — the RTL-mirrored key, the only one that carries
  # the \llap'ed number column with it. Counting digits cannot defend this: the
  # pre-v4.5.0 rendering emitted all five, drawn ON the rule. --inside-rule
  # asserts the geometry instead, and the mutation strips the one key that makes
  # it hold. Both branches report all four controls, including the style group
  # withheld when the base fixture fails, so a failure cannot shrink coverage.
  CBX=tests/codebox_numbers
  CBXPIN=(--expect 5 --anchor "boxed(items):" --inside-rule)
  HEBREW_LATEX_PROJECT_ROOT="$SKILL_ROOT" bash scripts/build.sh "$CBX.tex" >/dev/null 2>&1; rcb=$?
  if [ "$rcb" != "0" ]; then
    bad "codebox_numbers.tex did not build (exit $rcb) — in-frame numbering cannot be measured"
    bad "codebox_numbers.tex did not build — the unboxed control cannot run either"
    bad "codebox_numbers.tex did not build — its negative control cannot run either"
    bad "codebox_numbers.tex did not build — the four-style control is unmeasured"
  else
    python3 scripts/probe_lstnum.py "$CBX.pdf" "${CBXPIN[@]}" >/dev/null 2>&1; rc=$?
    if [ "$rc" = "0" ]; then ok "codebox keeps all 5 margin numbers, clear of its own frame"
    else bad "codebox numbering broken (probe exit $rc; run: python3 scripts/probe_lstnum.py $CBX.pdf ${CBXPIN[*]})"; fi
    python3 scripts/probe_lstnum.py "$CBX.pdf" --expect 5 --anchor "plain(items):" >/dev/null 2>&1; rc=$?
    if [ "$rc" = "0" ]; then ok "the same code unboxed still carries all 5 margin digits"
    else bad "unboxed numbering LOST (probe exit $rc) — the shared listing path regressed"; fi
    MUT=$(mktemp -d)
    mkdir -p "$MUT/assets" "$MUT/tests"
    NXR=$(grep -c "lstset{resetmargins=false,xrightmargin=26pt}" assets/preamble.tex || true)
    if [ "${NXR:-0}" != "1" ]; then
      bad "negative control is DEAD: found ${NXR:-0} codebox xrightmargin settings (want 1) — nothing left to strip"
    else
      sed 's/lstset{resetmargins=false,xrightmargin=26pt}/lstset{resetmargins=false}/' assets/preamble.tex > "$MUT/assets/preamble.tex"
      cp "$CBX.tex" "$MUT/tests/"
      (cd "$MUT/tests" && lualatex -interaction=nonstopmode codebox_numbers.tex >/dev/null 2>&1 \
                       && lualatex -interaction=nonstopmode codebox_numbers.tex >/dev/null 2>&1)
      python3 scripts/probe_lstnum.py "$MUT/tests/codebox_numbers.pdf" "${CBXPIN[@]}" >/dev/null 2>&1; rc=$?
      if [ "$rc" = "1" ]; then ok "pin fires: without xrightmargin the digits land back on the rule (exit 1)"
      else bad "pin DID NOT FIRE without xrightmargin (probe exit $rc, want 1) — in-frame numbering is undefended"; fi
    fi
    rm -rf "$MUT"
    # The docs promise codebox works with whichever style= the author passes,
    # so all four are measured, not just the one the first fixture used. Each
    # carries a different frame, background and xleftmargin; codebox
    # neutralises all of them at PreInit. One ok/bad for the group.
    HEBREW_LATEX_PROJECT_ROOT="$SKILL_ROOT" bash scripts/build.sh tests/codebox_styles.tex >/dev/null 2>&1; rcs=$?
    if [ "$rcs" != "0" ]; then
      bad "codebox_styles.tex did not build (exit $rcs) — the four-style promise is unmeasured"
    else
      styles_ok=1
      for probe in "asmProbe 2" "cProbe 3" "pyProbe 2" "htmlProbe 3"; do
        set -- $probe
        python3 scripts/probe_lstnum.py tests/codebox_styles.pdf --expect "$2" \
          --anchor "$1" --inside-rule >/dev/null 2>&1 || styles_ok=0
      done
      if [ "$styles_ok" = "1" ]; then ok "codebox numbers land clear of the frame under asm/cstyle/pystyle/htmlstyle"
      else bad "codebox numbering differs between listing styles (run: python3 scripts/probe_lstnum.py tests/codebox_styles.pdf --expect 2 --anchor pyProbe --inside-rule)"; fi
    fi
  fi
fi

echo "═══ T4: render checker (compiled-PDF gate) ═══"
if [ "${FAST:-0}" != "1" ]; then
if python3 -c "import fitz" 2>/dev/null; then
  # v3.83 (G1 twin): rm the target and CAPTURE the compile rc. v3.82 fixed
  # exactly this shape in T4b/T3c and left the identical hole here, one screen
  # above — measured: `rm tests/render_eqref_broken.tex` still printed 4 green
  # checks and "74 passed, 0 failed" off the PREVIOUS run's PDF, because the
  # &&-chain ran in a subshell whose status was discarded and the guard was a
  # bare [ -f ]. The `else bad "did not compile"` branch was unreachable.
  # Historical engine mutations can become correct in later LuaHBTeX releases.
  # Keep compiling those witnesses, but require independent physical-glyph
  # controls to trigger the named rules on every supported engine.
  python3 - "$HARNESS_TMP" <<'PYEOF'
from pathlib import Path
import sys
import fitz
root = Path(sys.argv[1])
with fitz.open() as doc:
    page = doc.new_page()
    chars = 'Datapath'
    widths = [fitz.get_text_length(char, fontsize=12) for char in chars]
    for i, char in enumerate(chars):
        page.insert_text((100+sum(widths[i+1:]), 100), char, fontsize=12)
    doc.save(root/'forced-reversed-latin.pdf')
with fitz.open() as doc:
    page = doc.new_page()
    page.insert_text((100, 100), ')1(', fontsize=12)
    doc.save(root/'forced-mirrored-reference.pdf')
PYEOF
  rm -f tests/render_broken.pdf
  (cd tests && lualatex -interaction=nonstopmode render_broken.tex >/dev/null 2>&1); rcb=$?
  if [ "$rcb" = "0" ] && [ -f tests/render_broken.pdf ]; then
    python3 scripts/check_pdf_render.py tests/render_broken.pdf tests/render_broken.tex >/dev/null 2>&1; rc=$?
    FORCED_OUT=$(python3 scripts/check_pdf_render.py "$HARNESS_TMP/forced-reversed-latin.pdf" tests/render_broken.tex 2>&1); forced_rc=$?
    if { [ "$rc" = "0" ] || [ "$rc" = "1" ]; } \
       && [ "$forced_rc" = "1" ] && grep -q 'REVERSED-LATIN-RUN' <<< "$FORCED_OUT"; then
      ok "catches deliberately reversed Latin glyph positions (historic witness exit $rc; forced exit 1)"
    else bad "reversed-Latin controls failed (historic exit $rc; forced exit $forced_rc: $FORCED_OUT)"; fi
  else bad "render_broken.tex did not compile"; fi
  # TWO passes — \eqref resolves only on the second (pass 1 prints "??", no
  # digits, nothing to mirror). A stale local .aux masked this: the check
  # passed on dev machines and went quiet on CI's fresh clone (PR #40 run 80).
  rm -f tests/render_eqref_broken.pdf
  (cd tests && rm -f render_eqref_broken.aux \
     && lualatex -interaction=nonstopmode render_eqref_broken.tex >/dev/null 2>&1 \
     && lualatex -interaction=nonstopmode render_eqref_broken.tex >/dev/null 2>&1); rce=$?
  if [ "$rce" = "0" ] && [ -f tests/render_eqref_broken.pdf ]; then
    python3 scripts/check_pdf_render.py tests/render_eqref_broken.pdf tests/render_eqref_broken.tex >/dev/null 2>&1; rc=$?
    FORCED_OUT=$(python3 scripts/check_pdf_render.py "$HARNESS_TMP/forced-mirrored-reference.pdf" 2>&1); forced_rc=$?
    if { [ "$rc" = "0" ] || [ "$rc" = "1" ]; } \
       && [ "$forced_rc" = "1" ] && grep -q 'MIRRORED-PAREN-DIGITS' <<< "$FORCED_OUT"; then
      ok "catches deliberately mirrored reference parens (R4; historic witness exit $rc; forced exit 1)"
    else bad "mirrored-reference controls failed (historic exit $rc; forced exit $forced_rc: $FORCED_OUT)"; fi
  else bad "render_eqref_broken.tex did not compile"; fi
  # v3.33.3: R4 must be SILENT on the superscript idiom "(x-1)^2(x-2)" — a
  # squared factor abutting another parenthesized factor is NOT a mirrored tag
  # (found as a hard-fail FP on a real Pareto-variance page).
  rm -f tests/render_super_ok.pdf
  (cd tests && lualatex -interaction=nonstopmode render_super_ok.tex >/dev/null 2>&1); rcs=$?
  if [ "$rcs" = "0" ] && [ -f tests/render_super_ok.pdf ]; then
    if python3 scripts/check_pdf_render.py tests/render_super_ok.pdf >/dev/null 2>&1; then
      ok "quiet on superscript (x-1)^2(x-2) — not a mirrored tag (R4)"
    else bad "render checker FALSE-POSITIVE on superscript (x-1)^2(x-2) (R4)"; fi
  else bad "render_super_ok.tex did not compile"; fi
  if [ -f assets/example_figures.pdf ]; then
    if python3 scripts/check_pdf_render.py assets/example_figures.pdf assets/example_figures.tex >/dev/null 2>&1; then
      ok "quiet on a clean rendered PDF"
    else bad "render checker false-positive on example_figures"; fi
  else
    # v3.71: this check used to VANISH silently when the PDF was absent
    # (44 -> 43 checks with no signal). Absence is now a failure.
    bad "assets/example_figures.pdf missing — the clean-PDF render check cannot run"
  fi
  # ═══ T4b: destination landing (R6, v3.80) ═══
  # PROOF-OF-FAILURE FIRST. tests/dest_broken.tex compiles clean, converges
  # byte-identically and passes build.sh + R1-R5 ("✓ clean build", "✓ render
  # check clean") with ALL THREE of its destinations wrong — that is the
  # blind spot BLD-37 kept re-opening through v3.74/v3.77/v3.79, each of them
  # verified by a one-off script and gated by nothing.
  #
  # FOUR checks, not one. "exit 1" alone would stay green with one of the
  # three shapes silently dead (the expected_flags.txt-floor lesson), so the
  # output must NAME both table shapes — an over-wide tabular and three
  # stacked tabulars, which fail through different mechanisms — and the
  # figure shape. Exit codes are exact (the v3.71 lesson): 1 is a finding, 2
  # is a crash or a missing fixture and must not read as a catch.
  echo "═══ T4b: destination landing gate (R6) ═══"
  # v3.82 (G1) — THE STALE-ARTIFACT HOLE, and why it is a hole.
  # The four compiles used to be one &&-chain whose exit status was thrown
  # away, the target PDFs were never removed, and the guard was mere
  # `[ -f ]`. So a compile FAILURE short-circuited the chain and left the
  # PREVIOUS run's dest_ok.pdf untouched — and the four checks below then ran
  # against it and printed four ✓. Measured on this tree: delete
  # \lakintabboxclose from assets/preamble.tex, and T4b prints "pins v3.79"
  # GREEN with v3.79 deleted (dest_ok.pdf's sha256 unchanged). CI was safe
  # only by accident — both fixtures are gitignored, so a fresh clone takes
  # the else-branch — which is precisely the shape of a false all-clear that
  # only a developer ever sees. Targets are removed FIRST and every compile's
  # rc is captured; a failed compile is a bad, not a silent skip.
  rm -f tests/dest_broken.pdf tests/dest_ok.pdf tests/dest_broken.aux tests/dest_ok.aux
  DESTBUILD=""
  for f in dest_broken dest_ok; do
    for p in 1 2; do            # two passes: \ref/hyperref resolve on the 2nd
      (cd tests && lualatex -interaction=nonstopmode "$f.tex" >/dev/null 2>&1); rc=$?
      [ "$rc" = "0" ] || DESTBUILD="${DESTBUILD:+$DESTBUILD; }$f.tex pass$p exited $rc"
    done
  done
  if [ -z "$DESTBUILD" ] && [ -f tests/dest_broken.pdf ] && [ -f tests/dest_ok.pdf ]; then
    R6OUT=$(python3 scripts/check_pdf_render.py tests/dest_broken.pdf 2>&1); rc=$?
    if [ "$rc" = "1" ]; then ok "destination gate fires on tests/dest_broken.pdf (exit 1)"
    else bad "destination gate on dest_broken exited $rc (want 1 = finding)"; fi
    NBOX=$(echo "$R6OUT" | grep -c "DEST-INSIDE-TABLEBOX" || true)
    if [ "${NBOX:-0}" -ge 2 ]; then ok "names BOTH table shapes ($NBOX DEST-INSIDE-TABLEBOX: over-wide tabular + stacked tabulars)"
    else bad "only ${NBOX:-0} DEST-INSIDE-TABLEBOX line(s) on dest_broken (want >=2) — one of the two table mechanisms is not caught"; fi
    if grep -q "DEST-AT-CAPTION" <<< "$R6OUT"; then ok "names the figure shape (DEST-AT-CAPTION on the un-measured \\begin{center})"
    else bad "no DEST-AT-CAPTION on dest_broken — the figure/frameless tier is dead"; fi
    # The SILENT twin carries the two table shapes character-for-character
    # with the v3.79 corrector ARMED, so this line is also the regression pin
    # for that mechanism: remove it from the preamble and this check goes red.
    # --max-cross-page 0 is carried here too, so "quiet" means quiet in R6c as
    # well — exit 0 alone would not notice a cross-page dest (R6c is soft).
    python3 scripts/check_pdf_render.py tests/dest_ok.pdf --max-cross-page 0 >/dev/null 2>&1; rc=$?
    if [ "$rc" = "0" ]; then ok "quiet on tests/dest_ok.pdf (same shapes, corrector armed — pins v3.79)"
    else
      # v3.82 (G2): this line used to read "destination gate FALSE-POSITIVE on
      # dest_ok", which points the reader at the CHECKER. dest_ok exists to pin
      # the MECHANISM, so on a preamble regression the checker is right and the
      # message was sending the next person to debug the wrong file.
      bad "v3.79 \\end{tablebox} anchor corrector REGRESSED (dest_ok now fails R6, exit $rc). Suspect FIRST, in order: \\lakintabboxclose in assets/preamble.tex, its startinnercode/endinnercode wiring on the tablebox \\newmdenv, the lakintab Lua; the checker only if all three are intact (run: python3 scripts/check_pdf_render.py tests/dest_ok.pdf)"; fi
  else
    bad "dest fixtures did not build (${DESTBUILD:-PDF missing after a successful compile}) — the destination gate is unproven"
    bad "dest fixtures unbuilt: both table shapes unchecked"
    bad "dest fixtures unbuilt: the figure shape unchecked"
    bad "dest fixtures unbuilt: the false-positive twin unchecked"
  fi

  echo "═══ T4c: cross-page caption destinations (R6c, BLD-38) ═══"
  # THE POPULATION THAT NO RULE WATCHED. 15 fleet dests land ABOVE their
  # page's top edge (-56.01..-286.75pt) because the caption broke to the page
  # after the figure. R6b cannot fail them even in principle — the worse the
  # break, the larger the dest-to-caption gap it measures — so the fleet could
  # have grown 15 -> 20 in silence. v3.81 left this open on purpose (BLD-38);
  # v3.82 closes it the honest way: the sites are not FIXED (they are real
  # layout, and the object is still reachable), they are COUNTED. Every one
  # now prints a ⚠ in the build that produces it, and --max-cross-page turns
  # the count into a hard budget for a fleet sweep.
  # Both branches emit exactly 4 ok/bad, so the block is always 4 checks.
  rm -f tests/dest_crosspage.pdf tests/dest_crosspage.aux
  XPBUILD=""
  for p in 1 2; do
    (cd tests && lualatex -interaction=nonstopmode dest_crosspage.tex >/dev/null 2>&1); rc=$?
    [ "$rc" = "0" ] || XPBUILD="${XPBUILD:+$XPBUILD; }dest_crosspage.tex pass$p exited $rc"
  done
  if [ -z "$XPBUILD" ] && [ -f tests/dest_crosspage.pdf ]; then
    XPOUT=$(python3 scripts/check_pdf_render.py tests/dest_crosspage.pdf 2>&1); rc=$?
    NXP=$(echo "$XPOUT" | grep -c "DEST-CROSS-PAGE-CAPTION" || true)
    # exactly ONE: the fixture also carries a healthy same-page figure, so a
    # rule that fired on every fig. dest would score 2 and fail here.
    if [ "${NXP:-0}" = "1" ] && [ "$rc" = "0" ]; then
      ok "R6c names the split caption and only it (1 DEST-CROSS-PAGE-CAPTION, healthy twin silent, soft: exit 0)"
    else bad "R6c on dest_crosspage: ${NXP:-0} DEST-CROSS-PAGE-CAPTION line(s) at exit $rc (want exactly 1 at exit 0) — the cross-page tier is dead or over-fires on the same-page twin"; fi
    python3 scripts/check_pdf_render.py tests/dest_crosspage.pdf --max-cross-page 0 >/dev/null 2>&1; rc=$?
    if [ "$rc" = "1" ]; then ok "--max-cross-page 0 turns the population into a HARD budget (exit 1)"
    else bad "--max-cross-page 0 exited $rc on a PDF with 1 cross-page dest (want 1 = finding) — the BLD-38 budget cannot fail, so it cannot gate"; fi
    python3 scripts/check_pdf_render.py tests/dest_crosspage.pdf --max-cross-page 1 >/dev/null 2>&1; rc=$?
    if [ "$rc" = "0" ]; then ok "--max-cross-page 1 accepts an accepted population (exit 0) — the budget is a count, not a ban"
    else bad "--max-cross-page 1 exited $rc with exactly 1 cross-page dest (want 0) — the budget is off by one and would red-flag the accepted fleet"; fi
    env -u MAX_CROSS_PAGE_DESTINATIONS \
      HEBREW_LATEX_PROJECT_ROOT="$SKILL_ROOT" bash scripts/build.sh \
      tests/dest_crosspage.tex >"$HARNESS_TMP/hll_t4c_build_default.log" 2>&1; rc=$?
    if [ "$rc" = "1" ] \
       && grep -q 'DEST-CROSS-PAGE-CAPTION' "$HARNESS_TMP/hll_t4c_build_default.log"; then
      ok "build.sh defaults to a zero cross-page budget; waivers must be explicit"
    else
      bad "build.sh default did not reject the split caption (exit $rc)"
    fi
  else
    bad "dest_crosspage.tex did not build (${XPBUILD:-PDF missing after a successful compile}) — R6c is unproven"
    bad "dest_crosspage unbuilt: the BLD-38 hard budget is unchecked"
    bad "dest_crosspage unbuilt: the budget's accept case is unchecked"
    bad "dest_crosspage unbuilt: build.sh default budget is unchecked"
  fi
else
  bad "pymupdf missing — render tests skipped (pip install --break-system-packages pymupdf)"
fi
else
  echo "  ↷ FAST=1: LuaLaTeX/render fixtures intentionally skipped"
fi

if [ "${FAST:-0}" != "1" ]; then
  echo "═══ T4d: R5c — list labels stranded in the LEFT margin (v3.83) ═══"
  # BIDI-70 shipped 216 choice labels 25.65pt into the left margin while every
  # layer printed clean, because R5b has only ever tracked the RTL RIGHT edge.
  # v3.82 documented that blindness; v3.83 closes it. The fixture carries the
  # measured pre-fix geometry and is GENERATED here, never committed, so it
  # cannot rot into a static file that still passes after the rule is deleted.
  if python3 -c "import fitz" 2>/dev/null; then
    rm -f tests/label_left_broken.pdf
    python3 - <<'PYEOF'
import fitz
d = fitz.open()
a4 = fitz.paper_rect("a4")
for _ in range(2):
    p = d.new_page(width=a4.width, height=a4.height)
    y = 100
    for lab in "abcd":
        p.insert_text((39.55, y), f"({lab})", fontsize=12)
        p.insert_text((65.2, y), "body text of the choice item", fontsize=12)
        y += 20
    for _ in range(20):
        p.insert_text((65.2, y), "ordinary body line at the block edge", fontsize=12)
        y += 15
d.save("tests/label_left_broken.pdf")
PYEOF
    if [ -f tests/label_left_broken.pdf ]; then
      N=$(python3 scripts/check_pdf_render.py tests/label_left_broken.pdf 2>&1 | grep -c 'LABEL-IN-LEFT-MARGIN')
      if [ "${N:-0}" -ge 8 ]; then ok "R5c names the stranded labels ($N found)"
      else bad "R5c found only ${N:-0} stranded labels on the pre-fix geometry (want >= 8)"; fi
    else bad "could not synthesize the R5c fixture"; fi
    # ...and it must stay silent on every SHIPPED artifact. A gate with a
    # four-digit FP count (1084 listing line numbers, 112 TOC leaders) is a
    # gate nobody runs, so this half is what keeps the rule narrow.
    FP=0
    CHECKED=0
    for f in assets/example_*.pdf ../../*/src/final.pdf ../../quantum-computing/src/main.pdf; do
      [ -f "$f" ] || continue
      CHECKED=$((CHECKED + 1))
      FP=$((FP + $(python3 scripts/check_pdf_render.py "$f" 2>&1 | grep -c 'LABEL-IN-LEFT-MARGIN')))
    done
    if [ "$CHECKED" -gt 0 ] && [ "$FP" = "0" ]; then
      ok "R5c silent on $CHECKED bundled/fleet PDF(s) (0 false positives)"
    elif [ "$CHECKED" = "0" ]; then
      bad "R5c negative corpus is empty — zero false positives would be vacuous"
    else bad "R5c raised $FP false positive(s) on $CHECKED bundled/fleet PDF(s)"; fi
  fi

  echo "═══ T4g: explicit-hyphen table safety without a bidi exception guard ═══"
  (cd tests && lualatex --no-shell-escape -interaction=nonstopmode \
    -halt-on-error tabular_hyphen.tex >/dev/null 2>&1)
  th=$?
  if [ "$th" = "0" ] \
     && grep -q 'BIDI-NIL-DISC-PROBE=OK' tests/tabular_hyphen.log 2>/dev/null \
     && grep -q 'TABULAR-EXHYPHENPENALTY=10000' tests/tabular_hyphen.log 2>/dev/null \
     && ! grep -q 'HEBLLP-BIDI-SKIP' tests/tabular_hyphen.log 2>/dev/null; then
    ok "nil-replacement disc and hyphenated table compile without an unreordered fallback"
  else
    bad "hyphenated-table safety failed (exit $th, hook/guard contract not met)"
  fi
  rm -f tests/tabular_hyphen.aux tests/tabular_hyphen.log \
        tests/tabular_hyphen.pdf tests/tabular_hyphen.out 2>/dev/null

  echo "═══ T4h: protected code headings and noise-free PDF strings ═══"
  # v4.8.0: protection changes the historical failure mode. Removing the PDF
  # string hook no longer crashes raw LuaLaTeX: it preserves this bookmark but
  # emits a Token-not-allowed warning. The REAL build must still reject it.
  # Two assertions: clean exact bookmark, and the measured warning/gate boundary.
  CH_DIR="$HARNESS_TMP/code_heading"
  mkdir -p "$CH_DIR"
  cp assets/preamble.tex "$CH_DIR/preamble.tex"
  sed 's/^\\pdfstringdefDisableCommands.*$/% hook removed by the T4h mutation/' \
      assets/preamble.tex > "$CH_DIR/preamble_nohook.tex"
  for variant in with without; do
    P=preamble.tex; [ "$variant" = without ] && P=preamble_nohook.tex
    printf '\\input{%s}\n\\begin{document}\n\\section{שימוש ב־\\code{grep} בקבצים}\nטקסט.\n\\end{document}\n' \
           "$P" > "$CH_DIR/h_$variant.tex"
  done
  ( cd "$CH_DIR" && for v in with without; do
      lualatex --no-shell-escape -interaction=nonstopmode "h_$v.tex" >/dev/null 2>&1
      lualatex --no-shell-escape -interaction=nonstopmode "h_$v.tex" >/dev/null 2>&1
    done ) >/dev/null 2>&1
  _heading_bookmark_exact() {
    PYTHONDONTWRITEBYTECODE=1 python3 - "$1" <<'PYEOF'
import sys
import fitz
with fitz.open(sys.argv[1]) as doc:
    toc = doc.get_toc()
sys.exit(0 if toc and toc[0][1] == "שימוש ב־grep בקבצים" else 1)
PYEOF
  }
  if [ -f "$CH_DIR/h_with.pdf" ] \
      && _heading_bookmark_exact "$CH_DIR/h_with.pdf" \
      && ! grep -q 'Token not allowed' "$CH_DIR/h_with.log"; then
    ok "protected code heading has an exact bookmark and no PDF-string warning"
  else bad "code heading failed its exact-bookmark / warning-free contract"; fi
  # Preserve the canonical preamble basename for the production source guards;
  # the negative control changes only the hook, not its architecture identity.
  CH_BAD="$CH_DIR/nohook_build"
  mkdir -p "$CH_BAD"
  cp "$CH_DIR/preamble_nohook.tex" "$CH_BAD/preamble.tex"
  cp "$CH_DIR/h_with.tex" "$CH_BAD/h_without.tex"
  ( cd "$CH_BAD" && HEBREW_LATEX_PROJECT_ROOT="$CH_BAD" \
      bash "$SCRIPT_DIR/build.sh" h_without.tex ) >"$CH_DIR/nohook_build.log" 2>&1
  CH_BAD_RC=$?
  if [ -f "$CH_DIR/h_without.pdf" ] \
      && _heading_bookmark_exact "$CH_DIR/h_without.pdf" \
      && grep -q 'Token not allowed' "$CH_DIR/h_without.log" \
      && [ "$CH_BAD_RC" = "1" ] \
      && grep -q 'hyperref PDF-string warning(s)' "$CH_DIR/nohook_build.log"; then
    ok "hook removal yields a raw-engine PDF with a warning; the real build rejects that warning"
  else
    bad "hook-removal control did not match the protected-macro warning/gate boundary (rc=$CH_BAD_RC)"
    tail -12 "$CH_DIR/nohook_build.log" | sed 's/^/        | OUT: /'
  fi

  echo "═══ T4i: a code title's punctuation must live INSIDE the island ═══"
  # pitfalls.md: a ';' after \code{}/\texttt{} in a frametitle jumps to the far
  # edge, because the neutral sits OUTSIDE the LTR island. The historical advice
  # ("use \code{} instead of \texttt{}") is a no-op: the preamble gives the two
  # macros byte-identical bodies. Geometry decides, not glyph counting. Always 3.
  SEMI_DIR="$HARNESS_TMP/semi_title"
  mkdir -p "$SEMI_DIR"
  cp assets/preamble.tex "$SEMI_DIR/preamble.tex"
  {
    printf '\\input{preamble.tex}\n\\begin{document}\n'
    printf '\\begin{exbox}[frametitle={הפקודה \\code{lw};}]\nא.\n\\end{exbox}\n'
    printf '\\begin{exbox}[frametitle={הפקודה \\code{lw;}}]\nב.\n\\end{exbox}\n'
    printf '\\begin{exbox}[frametitle={הפקודה \\texttt{lw};}]\nג.\n\\end{exbox}\n'
    printf '\\end{document}\n'
  } > "$SEMI_DIR/semi.tex"
  ( cd "$SEMI_DIR" && lualatex --no-shell-escape -interaction=nonstopmode semi.tex >/dev/null 2>&1 \
      && lualatex --no-shell-escape -interaction=nonstopmode semi.tex >/dev/null 2>&1 ) >/dev/null 2>&1
  SEMI_OUT="$(PYTHONDONTWRITEBYTECODE=1 python3 - "$SEMI_DIR/semi.pdf" 2>/dev/null <<'PYEOF'
import sys
import fitz
rows = {}
for blk in fitz.open(sys.argv[1])[0].get_text("rawdict")["blocks"]:
    for line in blk.get("lines", []):
        for span in line.get("spans", []):
            for ch in span.get("chars", []):
                if ch["c"].strip():
                    key = round((ch["bbox"][1] + ch["bbox"][3]) / 2)
                    rows.setdefault(key, []).append((ch["bbox"][0], ch["c"]))
titles = ["".join(c for _, c in sorted(v)) for _, v in sorted(rows.items())
          if "lw" in "".join(c for _, c in sorted(v))]
if len(titles) != 3:
    sys.exit(0)
outside, inside, texttt = titles
print("OUTSIDE_SPLIT" if outside.startswith(";") else "outside_ok")
print("INSIDE_OK" if inside.startswith("lw;") else "inside_bad")
print("SWAP_NOOP" if outside == texttt else "swap_differs")
PYEOF
)"
  case "$SEMI_OUT" in
    *OUTSIDE_SPLIT*) ok "a ';' outside the island is carried to the far edge of the title" ;;
    *) bad "could not reproduce the stranded ';' — the pitfalls row no longer describes the engine" ;;
  esac
  case "$SEMI_OUT" in
    *INSIDE_OK*) ok "merging the ';' into the island restores reading order" ;;
    *) bad "the documented fix (';' inside the island) did not restore reading order" ;;
  esac
  case "$SEMI_OUT" in
    *SWAP_NOOP*) ok "\\texttt -> \\code alone changes nothing (identical bodies, identical geometry)" ;;
    *) bad "\\texttt and \\code produced different titles — the no-op claim needs re-measuring" ;;
  esac

  echo "═══ T4j: FOLIO-COVERAGE-LOW is a hard gate with no waiver ═══"
  # recipe.md states this rule has no flag and no environment variable. That is
  # a claim about the gate's SURFACE, so it is tested behaviourally: a document
  # with suppressed folios must fail the real build, and must still fail with
  # every knob the pipeline exposes set. Always 2.
  FOLIO_DIR="$HARNESS_TMP/folio"
  mkdir -p "$FOLIO_DIR"
  cp assets/preamble.tex "$FOLIO_DIR/preamble.tex"
  printf '\\input{preamble.tex}\n\\pagestyle{empty}\n\\begin{document}\n\\section{פרק}\nא.\n\\clearpage\nב.\n\\clearpage\nג.\n\\end{document}\n' \
      > "$FOLIO_DIR/folio.tex"
  FOLIO_LOG="$HARNESS_TMP/folio_build.log"
  ( cd "$FOLIO_DIR" && HEBREW_LATEX_PROJECT_ROOT="$PWD" \
      bash "$SCRIPT_DIR/build.sh" folio.tex ) >"$FOLIO_LOG" 2>&1
  frc=$?
  if [ "$frc" != "0" ] && grep -q 'FOLIO-COVERAGE-LOW' "$FOLIO_LOG"; then
    ok "suppressed folios fail the real build and are named FOLIO-COVERAGE-LOW"
  else bad "suppressed folios did not fail the build with FOLIO-COVERAGE-LOW (exit $frc)"; fi
  if [ -f "$FOLIO_DIR/folio.failed.pdf" ]; then
    if ALLOW_FOLIO_COVERAGE_LOW=1 FOLIO_COVERAGE_LOW=allow SKIP_FOLIO_CHECK=1 \
       python3 scripts/check_pdf_render.py "$FOLIO_DIR/folio.failed.pdf" --max-cross-page 99 \
       >/dev/null 2>&1; then
      bad "a waiver path relaxed FOLIO-COVERAGE-LOW — recipe.md's 'no waiver' is wrong"
    else ok "no environment knob or CLI flag relaxes FOLIO-COVERAGE-LOW"; fi
  else bad "the folio fixture produced no PDF — the no-waiver half could not run"; fi

  echo "═══ T4k: protected code in math-alignment cells (v4.8.0) ═══"
  # v4.8.0: the former documented failure is now fixed at the macro level.
  # Preserve the four scope/discriminator checks; the new runtime suite also
  # removes the protection and proves the same source fails again.
  GUARD_DIR="$HARNESS_TMP/mmode_guard"
  mkdir -p "$GUARD_DIR"
  cp assets/preamble.tex "$GUARD_DIR/preamble.tex"
  printf '\\input{preamble.tex}\n\\begin{document}\n\\[\n\\begin{aligned}\n\\code{lw} &= 1\\\\\n\\code{sw} &= 2\n\\end{aligned}\n\\]\n\\end{document}\n' > "$GUARD_DIR/cell_bare.tex"
  printf '\\input{preamble.tex}\n\\begin{document}\n\\[\n\\begin{aligned}\n\\text{\\code{lw}} &= 1\\\\\n\\text{\\code{sw}} &= 2\n\\end{aligned}\n\\]\n\\end{document}\n' > "$GUARD_DIR/cell_text.tex"
  printf '\\input{preamble.tex}\n\\begin{document}\n\\[\n\\code{lw} + 1\n\\]\nבשורה $\\code{beq}$ ואז \\[\n\\begin{aligned}\nx &= \\code{lw}\\\\\ny &= \\code{sw}\n\\end{aligned}\n\\]\n\\end{document}\n' > "$GUARD_DIR/scope_safe.tex"
  printf '\\input{preamble.tex}\n\\begin{document}\n\\[\n\\begin{aligned}\n\\relax\\code{lw} &= 1\\\\\n\\relax\\code{sw} &= 2\n\\end{aligned}\n\\]\n\\end{document}\n' > "$GUARD_DIR/cell_relax_code.tex"
  printf '\\input{preamble.tex}\n\\begin{document}\n\\[\n\\begin{aligned}\n\\relax\\en{lw} &= 1\\\\\n\\relax\\en{sw} &= 2\n\\end{aligned}\n\\]\n\\end{document}\n' > "$GUARD_DIR/cell_relax_en.tex"
  _guard_rc() {
    ( cd "$GUARD_DIR" && lualatex --no-shell-escape -interaction=nonstopmode \
        -halt-on-error "$1.tex" >/dev/null 2>&1 )
    echo $?
  }
  GB_RC=$(_guard_rc cell_bare)
  if [ "$GB_RC" = "0" ]; then
    ok "protected \code opens an aligned cell without a wrapper"
  else
    bad "protected \code at an aligned cell start failed (exit $GB_RC)"
  fi
  GT_RC=$(_guard_rc cell_text)
  if [ "$GT_RC" = "0" ]; then
    ok "the legacy \\text{\\code{..}} wrapper remains supported at a cell start"
  else bad "the legacy text wrapper did not build (exit $GT_RC)"; fi
  GS_RC=$(_guard_rc scope_safe)
  if [ "$GS_RC" = "0" ]; then
    ok "\\code stays safe in plain display, inline math and a cell RHS (no rule may widen to it)"
  else bad "\\code failed OUTSIDE a cell opening (exit $GS_RC) — the row's scope is wrong"; fi
  # Legacy relax prefixes remain compatible with protected code. They are no
  # longer required, as the bare-cell assertion proves. Raw en remains invalid
  # in math regardless of a relax prefix; do not widen the code exception.
  GRC_RC=$(_guard_rc cell_relax_code)
  GRE_RC=$(_guard_rc cell_relax_en)
  if [ "$GRC_RC" = "0" ] && [ "$GRE_RC" != "0" ]; then
    ok "legacy relax prefixes remain compatible; raw en in math is still rejected"
  else
    bad "the \\relax discriminator broke (code=$GRC_RC en=$GRE_RC) — the compatibility boundary no longer holds"
  fi

  echo "═══ T4l: the part number stays at the RTL leading edge (v4.12.0) ═══"
  # BIDI-78. report/article compose the part TOC entry as ONE text stream
  # (\thepart\hspace{1em}#1); every other level goes through \numberline, which
  # boxes the number. A box cannot join a neighbouring bidi run -- a bare "II"
  # can, so a Latin-INITIAL part title merged with its own number into a single
  # LTR unit and printed the number on the wrong side. Asserted on GEOMETRY, not
  # on the .toc string: a string assertion would survive any re-break of the fix.
  # Keep the patch-removal witness, but do not require a newer engine to retain
  # its old defect. A second control deliberately moves only the Latin part's
  # visible number to the wrong edge of the actual positive PDF. Always 3.
  PTOC_DIR="$HARNESS_TMP/part_toc"
  mkdir -p "$PTOC_DIR/good" "$PTOC_DIR/bad"
  cp assets/preamble.tex "$PTOC_DIR/good/preamble.tex"
  sed 's/^\\@ifundefined{\(NR@part\|H@old@part\|@part\)}{}{\\lakin@parttocnum.*$/% patch removed by the T4l mutation/' \
      assets/preamble.tex > "$PTOC_DIR/bad/preamble.tex"
  for v in good bad; do
    printf '\\input{preamble.tex}\n\\begin{document}\n\\tableofcontents\n\\part{Hooks}\n\\chapter{פרק}\n\\part{הנדסה}\n\\chapter{פרק}\n\\end{document}\n' \
        > "$PTOC_DIR/$v/ptoc.tex"
    ( cd "$PTOC_DIR/$v" && for _ in 1 2 3; do \
        lualatex --no-shell-escape -interaction=nonstopmode ptoc.tex >/dev/null 2>&1; done ) >/dev/null 2>&1
  done
  # Prints one token per part row: LATIN_OK/LATIN_REVERSED and HEB_OK/HEB_REVERSED.
  # "OK" means the number sits to the RIGHT of the title, which is what the leading
  # edge of an RTL line is.
  _part_row_order() {
    PYTHONDONTWRITEBYTECODE=1 python3 - "$1" <<'PYEOF'
import sys
import fitz
rows = {}
for blk in fitz.open(sys.argv[1])[0].get_text("rawdict")["blocks"]:
    for line in blk.get("lines", []):
        for span in line.get("spans", []):
            for ch in span.get("chars", []):
                if ch["c"].strip():
                    rows.setdefault(round(ch["origin"][1]), []).append(
                        (ch["bbox"][0], ch["c"]))
def edge(row, number, title):
    nx = min(x for x, c in row if c in number)
    tx = min(x for x, c in row if c in title)
    return nx > tx
for key, row in sorted(rows.items()):
    text = "".join(c for _, c in sorted(row))
    if "Hooks" in text and "I" in text:
        print("LATIN_OK" if edge(row, "I", "Hks") else "LATIN_REVERSED")
    # PyMuPDF hands Hebrew back in VISUAL order, so match one letter, not a word.
    if "ד" in text and "I" in text:
        print("HEB_OK" if edge(row, "I", "הנדס") else "HEB_REVERSED")
PYEOF
  }
  PTOC_GOOD="$(_part_row_order "$PTOC_DIR/good/ptoc.pdf" 2>/dev/null)"
  PTOC_BAD="$(_part_row_order "$PTOC_DIR/bad/ptoc.pdf" 2>/dev/null)"
  python3 - "$PTOC_DIR/good/ptoc.pdf" "$PTOC_DIR/forced-wrong-edge.pdf" <<'PYEOF'
import sys
import fitz
with fitz.open(sys.argv[1]) as doc:
    page = doc[0]
    rows = {}
    for block in page.get_text('rawdict')['blocks']:
        for line in block.get('lines', []):
            for span in line['spans']:
                for ch in span['chars']:
                    y = round(ch['origin'][1])
                    rows.setdefault(y, []).append((span, ch))
    matches = [chars for chars in rows.values()
               if 'Hooks' in ''.join(ch['c'] for _, ch in sorted(chars, key=lambda pair: pair[1]['origin'][0]))]
    assert len(matches) == 1, matches
    chars = matches[0]
    number = [(span, ch) for span, ch in chars if ch['c'] == 'I']
    assert len(number) == 1, number
    span, ch = number[0]
    title_x = min(c['origin'][0] for _, c in chars if c['c'] in 'Hks')
    assert ch['origin'][0] > title_x
    page.add_redact_annot(fitz.Rect(ch['bbox']), fill=(1, 1, 1))
    page.apply_redactions()
    page.insert_text((title_x-24, ch['origin'][1]), 'I', fontsize=span['size'])
    doc.save(sys.argv[2])
PYEOF
  PTOC_FORCED="$(_part_row_order "$PTOC_DIR/forced-wrong-edge.pdf" 2>/dev/null)"
  case "$PTOC_GOOD" in
    *LATIN_OK*) ok "a Latin-initial part title keeps its number at the RTL leading edge" ;;
    *) bad "the part number is NOT at the leading edge of a Latin-initial row (got: ${PTOC_GOOD:-nothing})" ;;
  esac
  if case "$PTOC_BAD" in *LATIN_OK*|*LATIN_REVERSED*) true ;; *) false ;; esac \
     && case "$PTOC_FORCED" in *LATIN_REVERSED*) true ;; *) false ;; esac; then
    ok "actual PDF geometry rejects a deliberately displaced Latin part number (historical witness: $PTOC_BAD)"
  else bad "part-number controls failed (historical: ${PTOC_BAD:-nothing}; forced: ${PTOC_FORCED:-nothing})"; fi
  if case "$PTOC_GOOD" in *HEB_OK*) true ;; *) false ;; esac \
     && case "$PTOC_BAD" in *HEB_OK*) true ;; *) false ;; esac \
     && case "$PTOC_FORCED" in *HEB_OK*) true ;; *) false ;; esac; then
    ok "a Hebrew-initial part row is unaffected either way (the fix is a no-op where it must be)"
  else
    bad "the Hebrew control row moved (good: ${PTOC_GOOD:-nothing} / bad: ${PTOC_BAD:-nothing})"
  fi

  echo "═══ T5: reproducibility ═══"
  # v4.0.1: each side must be at a FIXED POINT before it is hashed. This ran
  # lualatex ONCE per side, in assets/, so pass 1 wrote .aux/.toc and pass 2 read
  # them — comparing a pre-convergence PDF against a converged one. It passed on any
  # machine that already had a converged .aux lying in assets/ and failed on a fresh
  # clone, which is why CI reported the same two hashes on every run while this
  # machine stayed green. Same shape as the stale-artifact class the round has been
  # chasing: the test measured leftover state. Both sides now go through build.sh,
  # which compiles to a fixed point and is the path a user actually runs.
  rm -f assets/example_math.pdf assets/example_math.aux assets/example_math.toc \
        assets/example_math.out
  bash scripts/build.sh tests/false_convergence.tex \
    >"$HARNESS_TMP/hll_t5_false_convergence.log" 2>&1; fcrc=$?
  if [ "$fcrc" = "1" ] \
     && grep -q 'NOT CONVERGED after 5 passes' "$HARNESS_TMP/hll_t5_false_convergence.log"; then
    ok "aux-state drift cannot hide behind two byte-identical PDFs"
  else
    bad "PDF-only false-convergence probe exited $fcrc without the non-convergence gate"
  fi
  TZ=UTC bash scripts/build.sh assets/example_math.tex \
    > "$HARNESS_TMP/hll_t5_root_relative.log" 2>&1; rr1=$?
  if [ "$rr1" = "0" ] && [ -s assets/example_math.pdf ]; then
    if grep -q 'content-density check' "$HARNESS_TMP/hll_t5_root_relative.log" \
       && ! grep -q 'cd: scripts' "$HARNESS_TMP/hll_t5_root_relative.log"; then
      ok "root-relative build invocation reaches the advisory density stage"
    else
      bad "root-relative build skipped its final density stage or emitted a path error"
    fi
    H1=$(python3 scripts/hash_file.py assets/example_math.pdf)
    (cd assets && TZ=Asia/Jerusalem bash ../scripts/build.sh \
      example_math.tex >/dev/null 2>&1); rr2=$?
    if [ "$rr2" = "0" ] && [ -s assets/example_math.pdf ]; then
      H2=$(python3 scripts/hash_file.py assets/example_math.pdf)
      if [ -n "$H1" ] && [ -n "$H2" ] && [ "$H1" = "$H2" ]; then
        ok "fixed-point builds are byte-identical across caller timezones"
      else
        bad "successful builds are NOT reproducible (${H1:-missing} != ${H2:-missing})"
      fi
    else
      bad "reproducibility pass 2 failed or produced no PDF (lualatex exit $rr2)"
    fi
  else
    bad "reproducibility pass 1 failed or produced no PDF (lualatex exit $rr1)"
  fi
fi

echo "═══ T6: documentation exemplars + links preserve their contracts ═══"
# v4.6.0: keep the seven documentation assertions in one Python process.
# Individually the old shell command substitutions were fast, but after a long
# FAST run the cumulative harness could stall at this capture boundary in
# constrained environments. The regression script emits exactly one PASS line
# per semantic contract, preserving the harness floor without shell-capture
# fragility.
T6_FILE="$(mktemp)"
T6_RC=0
python3 scripts/test_doc_contracts.py >"$T6_FILE" 2>&1 || T6_RC=$?
if [ "$T6_RC" -ne 0 ]; then
  cat "$T6_FILE"
  bad "documentation contract regression script failed (rc=$T6_RC)"
else
  T6_COUNT=0
  while IFS= read -r t6_line; do
    case "$t6_line" in
      PASS$'\t'*)
        ok "${t6_line#*$'\t'}"
        T6_COUNT=$((T6_COUNT + 1))
        ;;
      *)
        [ -n "$t6_line" ] && echo "    $t6_line"
        ;;
    esac
  done <"$T6_FILE"
  if [ "$T6_COUNT" -ne 7 ]; then
    bad "documentation regression emitted $T6_COUNT PASS records; expected exactly 7"
  fi
fi
rm -f -- "$T6_FILE"

# build.sh now exports .failed.log/.failed.pdf and, when available, the root
# .failed.aux on an unpublished exit, so a harness run — which deliberately
# fails a dozen fixtures — leaves that
# many diagnostic trios behind. They are gitignored, but SKILL.md §10 says the
# package carries no logs or scratch PDFs, and a stale trio next to a fixture
# is the very confusion BLD-56 set out to remove.
rm -f tests/*.failed.log tests/*.failed.pdf tests/*.failed.aux

echo "────────────────────────────────"
# The harness must know its own size in BOTH modes. FAST once asserted nothing,
# and a static check placed inside the LuaLaTeX-gated region silently vanished
# while "ALL TESTS PASS" stayed green. A run that does not know its own size
# cannot detect a silently missing check (T1's v3.71 lesson, applied to the
# harness itself). test_release_contract.py pins the declared release floors;
# each real run proves its own executed count against them below.
# v5.4.0 preserves all 212/124 prior groups and adds seven static catalog groups,
# one topic-rail engine group and one mandatory sealed catalog visual gate.
# v5.4.1 (repository line) carries v5.3.5's T1q (static + runtime) onto it and
# adds T1r (static). A routine run (CATALOG_ROUTINE) runs one check fewer.
# v5.4.5 preserves the repository regression groups and adds two static
# editorial groups and two engine groups. Routine runs omit only the sealed
# catalog visual release gate, as before.
EXPECTED_FULL=228
EXPECTED_FAST=135
if [ "$FAIL" -eq 0 ]; then
  _want=$EXPECTED_FULL; [ "${FAST:-0}" = "1" ] && _want=$EXPECTED_FAST
  [ "${CATALOG_ROUTINE:-0}" = "1" ] && _want=$((EXPECTED_FULL - 1))
  if [ "$PASS" -ne "$_want" ]; then
    echo "  ✗ ran $PASS checks; this mode must run exactly $_want — a check has silently left the run"
    echo "    (intentional structure change? update EXPECTED_FULL/EXPECTED_FAST and test_release_contract.py)"
    FAIL=1
  fi
fi
echo "  $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] && { echo "✓ ALL TESTS PASS"; exit 0; } || { echo "✗ HARNESS FAILED"; exit 1; }
