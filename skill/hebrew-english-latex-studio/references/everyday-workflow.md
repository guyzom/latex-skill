# Everyday documents: language, purpose, design, and review

The generator creates an editable source project. It does not require an academic
or exam format. Choose language, genre, design, and optional packages independently;
see [the language and design contract](language-design.md) for the architecture.
Existing `create(kind, destination)` Python callers and omitted language flags
retain the Hebrew default.

## Inspect the catalog

The generated [template catalog](template-catalog.md) lists existing document
recipes, supported layouts, theme availability, authored starter declarations
and maintained examples. The [Hebrew–English glossary](glossary-he-en.md) explains
the terms. Inspect a selection before creating a project:

```bash
python3 scripts/template_registry.py list
python3 scripts/template_registry.py resolve --kind paper --language english --json
```

These commands read the canonical registry and create no project. Resolution
shows what was requested, what was selected and where defaults came from;
it does not build or visually approve a PDF. For the implementation contract,
see [catalog development](catalog-development.md).

## Start with the intended reader

| Language profile | Main language | Use |
| --- | --- | --- |
| `hebrew` | Hebrew | Hebrew document; English remains available when needed. |
| `english` | English | Native English document, metadata, labels, and typography. |
| `hebrew-with-english` | Hebrew | Hebrew document with shorter English passages. |
| `english-with-hebrew` | English | English document with shorter Hebrew passages. |
| `bilingual` | Explicitly choose Hebrew or English | Both languages have substantial content. |

For `bilingual`, `--main-language` is required. It selects the shell: overall
reading direction and default document labels. Both language blocks are real
content, with distinct example reference and note identifiers. The profile does
not infer language percentages or prohibit the other language. A conflicting
`--main-language` is rejected. The single-language English template is ordinary
English source, not a Hebrew document enclosed in one English environment.

```bash
python3 scripts/new_document.py --kind general --language english \
  --theme custom --package microtype --directory /path/to/new-project
```

```bash
python3 scripts/new_document.py --kind report --language bilingual \
  --main-language hebrew --theme reader --directory /path/to/bilingual-report
```

The generator rejects an existing directory, including an empty directory or a
symlink. Publication reserves the destination with exclusive directory creation,
so a concurrently created empty directory cannot be overwritten. Staged files
are then linked without replacement. This is not a transactional multi-file
publish; on failure only the generator's own links are removed.

## Choose a genre and presentation

| Kind | Starting structure |
| --- | --- |
| `general` | Flexible purpose, context, details, and next step; default CLI kind. |
| `letter` | Recipient, subject, short body, and signature. |
| `report` | Summary, scope, findings, limitations, and proposed action. |
| `paper` | Title, localized abstract, argument, selective math references, figures/table and bibliography. |
| `note` | A short explanation with a practical implication. |
| `technical` | Question, derivation, example code, and validation. |
| `formula-sheet` | Equations, symbol definitions and conditions of use; optional compact/readable reference layout. |
| `data-report` | Data definitions and a multipage table. |
| `annotated-note` | Ordinary and deferred notes with shared numbering. |

These are starting points, not prescribed document structures. Replace sample
content, titles, metadata, and recipient details before delivery. All starter
kinds use a supported `article` shell; choose `report` in the document-class hook
if the actual document requires chapters. Genre and document class are separate.

| Theme | What is copied or created |
| --- | --- |
| `reader` | The supplied `reader_theme.tex`, with restrained callouts. |
| `academic` | Shared `academic_theme.tex`: classical serif black article styling, visible headings and selective equations. |
| `reference` | Shared `reference_theme.tex`: serif black ruled headings, gray reference blocks and selective equations; does not supply columns. |
| `core` | No overlay; the core presentation remains. |
| `custom` | An editable local `theme.tex` skeleton, with no other theme loaded. |

With `--layout standard` (the default), omitting `--theme` selects `academic`
for `paper` and preserves `reader` for every existing kind. Explicit choices
always override the default. For a
native paper in either language:

```bash
python3 scripts/new_document.py --kind paper --language english \
  --directory /path/to/english-paper
python3 scripts/new_document.py --kind paper --language hebrew \
  --directory /path/to/hebrew-paper
```

Paper layout defaults to A4, 11 pt, 2.7 cm margins, 1.08 line spread and a
centered footer folio. Its author/date fields are empty, and a bilingual paper
uses one title block, paired abstracts and one bibliography. Replace the
example scientific argument with the actual source material. See
[academic articles](academic-articles.md) for the complete authoring policy,
including central or referenced equation numbering and a Letter alternative.

For a formula/reference sheet, choose its layout independently:

| `--layout` | Body | Default theme when omitted |
| --- | --- | --- |
| `standard` | Existing starter layout | `reader` for `formula-sheet`; unchanged defaults elsewhere |
| `reference-readable` | Two columns, 9 pt body / 11 pt baseline | `reference` |
| `reference-compact` | Three columns, 6.3 pt body / 7.8 pt baseline | `reference` |

The two reference presets currently require `--kind formula-sheet`; another
kind is rejected before project creation. Both use an A4 article 10 pt shell,
8 mm side margins, 12 mm top and 16 mm bottom margins and a 5 mm column gap.
Body and mathematical sizes are independent declarations, not an automatic
content-fit pass. Compact main/script/scriptscript mathematics is
6.25/4.375/3.125 pt; readable mathematics is 8.75/6.125/4.375 pt. The layout
uniformly scales Computer Modern optical designs and applies its mathematical
selection locally inside the reference environments. See
[reference typography](reference-sheets.md) for the three math-size hooks,
their validation and direct-input defaults.
The shell reserves header/footer space and prints every folio at the same
centered footer position.

The reference starters use two numbered heading levels, local ruled topics,
mostly unboxed math and sparse compact notes/Q&A. Keep each short topic's
heading and defining content together with `referenceentry`; a long topic
can flow normally or use authored short chunks. Full-width content remains
an explicit option rather than a default topic family. See
[reference sheets](reference-sheets.md).

```bash
python3 scripts/new_document.py --kind formula-sheet --language english \
  --layout reference-readable --directory /path/to/english-reference
python3 scripts/new_document.py --kind formula-sheet --language hebrew \
  --layout reference-compact --directory /path/to/hebrew-reference
```

Both mixed profiles and `bilingual` with either explicit main language use the
same layers. Columns flow according to the main page language; individual
opposite-language paragraphs keep their own text direction. A bilingual
starter supplies a combined title and a separate translated body beginning
on a new page. Scientific content still needs an authored translation and
independent checking.

Reference layouts copy `reference_components.tex`, `reference_columns.tex` and
`reference_shell.tex`. The `reference` theme copies `reference_theme.tex`
independently; selecting it with `standard` or another kind does not create
columns. An explicit `reader`, `academic`, `core` or `custom` theme can instead
accompany a reference layout. Read [reference sheets](reference-sheets.md) for
the title API, column boundaries, short/long blocks and wide content.

The author may choose typography emphasis, color, heading decoration, spacing,
and component appearance to suit the audience. Keep page layout in the hooks
before `preamble.tex`. Keep language, direction, fonts, math, and anchor semantics
in their owning layers; a theme must not silently replace them. The legacy
`clean_theme.tex` is a separate exam presentation policy and is not a general
reading default. Do not load incompatible themes together.

Callout edges depend on the rendered language context. With the supplied
Babel/mdframed implementation, the reader style's `leftline=true` paints the
leading edge: physical right in Hebrew, physical left in English. Verify the
actual geometry after changing a theme; do not infer it solely from an option name.

## Optional packages and content components

Repeat `--package NAME` for document-specific packages. A name is a literal TeX
package identifier, without paths, `.sty`, TeX syntax, or options. There is no
fixed allowlist of extensions. The generator does not install packages or
certify compatibility. Packages explicitly supplied by the core or a selected
component are recorded without a second load; other selections are inserted
after `preamble.tex` and recorded as requiring validation.

Check installed availability and official package documentation, then verify load
order, options, name collisions, and interaction with Babel, fontspec, geometry,
hyperref, headings, math, and tables. Packages needing an earlier load or special
options require an explicit manual integration. Do not solve an option clash by
reloading the core package with contradictory options. After a change, compile
and review affected pages in every language that the document actually uses.

Only `data-report` copies `flow_tables.tex`. See [multipage tables](flow-tables.md)
for column types, language direction, and restrictions. Only `annotated-note`
copies `deferred_notes.tex`; read [deferred notes](deferred-notes.md) before adding
notes inside components. These are independent capabilities, not fixed genres:
you may add either component to another document after following its contract.

Loading `document_components.tex` provides a source annotation:

```latex
\sourcelink{https://example.org/reference}{Reference title}{What this source contains and why it appears here.}
```

The URL above is only a placeholder. Use verified actual sources. For Hebrew
inline text in an English paragraph use `\h{...}`; for English inline terms in
Hebrew use `\en{...}`. Full paragraphs belong in `hebrewprose` or `englishprose`.
The annotation's role label follows the surrounding language. It does not replace
claim-level citations or an academic bibliography.

## Build and retain provenance

```bash
HEBREW_LATEX_SKILL_ROOT=/path/to/skill bash /path/to/new-project/build.sh
```

The generated script supplies the genre's advisory `CONTENT_PROFILE` only when
the variable is unset. Choose another profile explicitly when it suits the actual
content, for example:

```bash
CONTENT_PROFILE=generic HEBREW_LATEX_SKILL_ROOT=/path/to/skill \
  bash /path/to/new-project/build.sh
```

Explicit values reach the managed builder unchanged. An empty value uses its
`generic` default; an invalid value fails configuration validation before the
compiler starts. Paper and folio settings are also forwarded: configure the
source layout first, then declare matching `EXPECTED_PAPER`, `PDF_FOLIO_LAYOUT`
and `PDF_FOLIO_BAND` values. A declared contract does not alter the source layout.

A wrapper selecting the academic or reference theme also supplies `PDF_CAPTION_COLOR=000000` and
`PDF_CAPTION_LABEL_WEIGHT=normal` only when those variables are unset.
Other themes retain the managed builder's gray/bold baseline unless explicitly
configured. When customizing captions, match verification settings to the
actual label style; the variables do not recolor or change the PDF.

`project.json` records the skill version, independent choices, selected packages,
source template hashes, copied asset hashes, and initial project source hashes.
Schema 3 also records the resolved recipe and its registry snapshot, keeping
requested selections separate from effective choices and their provenance.
Existing projects and their earlier metadata are not rewritten automatically.
This is a creation-time snapshot, not proof that an edited project is unchanged.
Record intentional modifications and regenerate build/review evidence after edits.
Font binaries remain external pinned dependencies. The project does not bundle a
compiler, fonts, or optional package dependencies.

A short technical starter can receive a `THIN` density hint. That is an editorial
observation, not a reason to invent content. Spacious pages are acceptable. Do
not add unnecessary equations, boxes, or section numbers, or reduce every font
size merely to fill a page or improve a density score.

## Review actual rendered pages

```bash
python3 scripts/render_review.py render main.pdf --output review
```

The result includes an image per page, an HTML index, and `review.json`. Pages
start as `pending`; compilation and rendering do not approve them. Inspect every
page at a readable scale. Record only pages actually reviewed, for example:

```bash
python3 scripts/render_review.py record main.pdf --review review/review.json \
  --pages 1 --reviewer "Reviewer name" --notes "Actual findings on this page"
```

An explicit range such as `1,3-5` is allowed; pages must exist. There is no `all`
shortcut. The reviewer name and notes must be nonempty. Recording checks PDF and
image hashes and updates the evidence atomically. This is a single-writer process,
not collaborative locking or authentication of the reviewer.

After reviewing every page:

```bash
python3 scripts/render_review.py verify main.pdf --review review/review.json --rerender
```

Without `--rerender`, verification checks matching hashes and review status.
With it, the recorded renderer regenerates each page and compares pixels. Pixel
comparison does not depend on PNG compression or nonvisual image metadata.
Poppler is the default. Explicit `--renderer mupdf` creates separate renderer
provenance; there is no silent substitution. Changed renderer versions can change
pixels and require a new render/review cycle. Historical schema 1 and 2 evidence
remains Poppler evidence; schema 3 records the selected renderer.

This evidence does not certify scientific correctness, accessibility, reviewer
identity, or behavior in the target viewer. Check actual link behavior in Preview,
Safari, Goodnotes, or the viewer the reader will use when that behavior matters.

## A failed build is not a new output

An earlier PDF can be preserved or restored after failure. It does not represent
the edited source. Check the exit code and `*.failed.log`, not just whether a PDF
exists. [Output recovery](output-recovery.md) explains the local engine's bounded
protection; it is not a substitute for a backup.
