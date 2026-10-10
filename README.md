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

Short tables use content widths; wide prose and continuing tables keep balanced
columns and safe cell padding. Captions default to one regular black paragraph
with a colon separator. Optional `framedtable` fits its content and caption;
`semanticframedtable` matches the active semantic boxes' outer width and insets
while natural inner columns stay compact. Both are atomic one-page choices.
Column counts, widths, headers and structure come from the content; the examples
are adaptable choices rather than required schemas. See [tables and captions](skill/hebrew-english-latex-studio/references/tables-and-captions.md).

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
custom classes need compatibility checks. The builder supports an explicit
single-index MakeIndex stage with `INDEX_PROCESSOR=makeindex`; selecting the
optional index component supplies that default. It does not run Biber, BibTeX,
or other external processors. Byte equality depends on the
same toolchain and fonts. Some engine-specific negative controls require
LuaHBTeX 1.18+ and report skips on older engines.

Compile trusted TeX only: disabling shell escape does not sandbox LuaLaTeX.
Automated checks do not establish scientific correctness, accessibility
compliance, visual quality on every page, or behavior in every PDF viewer.

## Licensing

The original PDF QA/review, generator, catalog and maintenance programs and
explicitly listed build, regression and packaging support have an AGPLv3-only
grant covering 138 individual paths. See the package's
[scope and local source boundary](skill/hebrew-english-latex-studio/LICENSING.md),
[exact file manifest](skill/hebrew-english-latex-studio/LICENSE-SCOPE.json), and
[dependency notices](skill/hebrew-english-latex-studio/NOTICE.md). The standalone
archive includes those files, the unmodified license texts, and the
[Generated Output Permission](skill/hebrew-english-latex-studio/LICENSES/Generated-Output-Permission.txt).

This grant excludes TeX templates, assets, fonts, and unlisted source. Using the
tools does not automatically license original user content or output PDFs under
AGPL; copied source retains its actual license. The additional permission allows
original fragments emitted by the seven named programs to be used in normal
generated output under terms of the recipient's choice. Generated projects retain
its exact text. It does not grant rights in copied inputs or third-party material.
The project import/support boundary is checked in both directions; no blanket
license, legal certification or complete provenance claim is made for the repository.

Run `python3 "$STUDIO_ROOT/scripts/test_license_scope.py"` and
`python3 "$STUDIO_ROOT/scripts/test_packaging.py"` to check scope consistency,
exclusions, and licensing-file inclusion in the actual archive.
