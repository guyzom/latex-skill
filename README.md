# Hebrew English LaTeX Studio

A standalone LuaLaTeX toolkit for English, Hebrew, and bilingual documents.
It combines document generation, reusable TeX components, and source/PDF
validation for papers, reports, notes, letters, and reference sheets.

## Architecture

The package lives in [`skill/hebrew-english-latex-studio`](skill/hebrew-english-latex-studio).
One shared preamble handles language, text direction, mathematics, and anchors.
Semantic components, column layouts, page shells, and presentation themes are
separate layers. A JSON registry defines document recipes; Python scripts
resolve recipes, generate projects, and check source and PDF contracts. The
Bash builder compiles to convergence and publishes output atomically.

See the [architecture](skill/hebrew-english-latex-studio/references/architecture.md)
and [template catalog](skill/hebrew-english-latex-studio/references/template-catalog.md).

## Setup and run

Requirements: Bash, Python 3.10+, TeX Live 2023+ with LuaLaTeX, Poppler, and
the pinned Python QA dependencies. On Debian/Ubuntu:

```bash
sudo apt-get install texlive-luatex texlive-lang-other texlive-pictures \
  texlive-latex-extra texlive-latex-recommended texlive-science \
  texlive-fonts-recommended poppler-utils fontconfig
python3 -m venv .venv
source .venv/bin/activate
STUDIO_ROOT="$PWD/skill/hebrew-english-latex-studio"
python3 -m pip install -r "$STUDIO_ROOT/requirements-qa.txt"
export HEBREW_LATEX_FONT_DIR="$PWD/.fonts"
bash "$STUDIO_ROOT/scripts/setup_fonts.sh" "$HEBREW_LATEX_FONT_DIR" \
  --from-directory "$PWD/assets/fonts"
python3 "$STUDIO_ROOT/scripts/doctor.py"
```

The external font directory contains the pinned Frank Ruhl Libre, Heebo, and
DejaVu files with upstream licenses. The package verifies their SHA-256 hashes.
For a separate installation, see the [setup guide](skill/hebrew-english-latex-studio/references/studio-setup.md).

Generate a project in a new directory, build its PDF, and render pages for review:

```bash
python3 "$STUDIO_ROOT/scripts/new_document.py" --kind technical \
  --language english-with-hebrew --directory /tmp/latex-skill-demo
HEBREW_LATEX_SKILL_ROOT="$STUDIO_ROOT" REPRO=1 \
  bash /tmp/latex-skill-demo/build.sh
python3 "$STUDIO_ROOT/scripts/render_review.py" render \
  /tmp/latex-skill-demo/main.pdf --output /tmp/latex-skill-review
```

Other language profiles are `english`, `hebrew`, `hebrew-with-english`, and
`bilingual`; the last requires `--main-language english` or `hebrew`.
Replace sample content and review every rendered page before using the PDF.

## Tests

Run from the repository root after setup:

```bash
(
  cd "$STUDIO_ROOT"
  python3 scripts/selftest.py
  python3 scripts/test_source_graph_runtime.py
  FAST=1 bash scripts/test_all.sh
  HEBREW_LATEX_CATALOG_VISUAL=routine bash scripts/test_all.sh
)
```

Successful commands exit with status 0. Source fixtures compare actual flags
with expected results; positive and negative cases cover direction boundaries,
literal code, malformed configuration, unsupported recipes, and source paths.
Source-resolution tests compare dependency paths with LuaLaTeX recorder output
and verify byte equality across clean builds. The runtime suite also checks
glyphs, navigation, layout, output recovery, and repeated-build equality in the
same environment.

`FAST` runs the static contract suite. Routine mode also runs compilation and
PDF regressions; it omits the release-only catalog visual attestation.
The [release workflow](skill/hebrew-english-latex-studio/references/catalog-development.md#release-workflow)
requires separate reviewed and sealed catalog evidence.

## Limitations

The tested document classes are `article` and `report`. Extra packages and
custom classes need compatibility checks. The builder does not run Biber,
BibTeX, indexing, or other external processors. Byte equality depends on the
same toolchain and fonts. Some engine-specific negative controls require
LuaHBTeX 1.18+ and report skips on older engines.

Compile trusted TeX only: disabling shell escape does not sandbox LuaLaTeX.
Automated checks do not establish scientific correctness, accessibility
compliance, visual quality on every page, or behavior in every PDF viewer.
