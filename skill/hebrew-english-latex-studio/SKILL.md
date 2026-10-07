---
name: hebrew-english-latex-studio
description: Create, edit, repair, and visually verify professional LuaLaTeX PDFs in native English, native Hebrew, English with Hebrew, Hebrew with English, or balanced bilingual text. Use for academic papers, compact or readable reference sheets, general documents, letters, briefs, reports, guides, academic notes, formula sheets, exams, math, tables, code, TikZ/pgfplots, and quantum circuits; also diagnose fonts, direction, layout, links, and PDF rendering. Choose language, page layout, design, and additional packages independently. Preserve another output format when explicitly requested.
---

# Hebrew English LaTeX Studio — סטודיו LaTeX עברית–אנגלית

Create a document that fits its purpose, preserves its sources, and passes automated and visual checks. Use `$hebrew-english-latex-studio`. Hebrew and English are first-class document languages; retain legacy internal environment variables for existing projects.

## 1. Decide before writing

Infer routine choices from the request. Ask only when missing information would materially change the result. Record independent decisions:

| Axis | Decision |
|---|---|
| Content | Purpose, audience, source of truth, scope, outputs |
| Language | One of five profiles below; base language for bilingual |
| Structure | Standard `article` or `report`; sections, chapters, numbering |
| Page layout | Paper, margins, spacing, columns, headers, folios |
| Design | Core, reader, academic, reference, custom, or deliberately selected exam theme |
| Extensions | Semantic components and additional packages actually needed |
| Verification | Paper/folio/navigation expectations and viewer constraints |

Choose a readable design when none is supplied. A4 is the default, not a constraint on authorized design work. Declare another paper size in both source and build configuration. Do not invent branding, authorship, evidence, or sources. Do not compress a document merely to eliminate a short or intentionally spacious page.

When text or mathematics appears flattened, inspect the actual PDF, embedded font design, declared sizes and rendering before changing the layout. Preserve each glyph's proportions; select and scale font designs uniformly rather than stretching text or mathematical expressions in a box. A screenshot alone does not establish geometric distortion. See [runtime typography](references/runtime-fonts.md).

| `--language` | Base | Use |
|---|---|---|
| `english` | English, LTR | Native English document |
| `hebrew` | Hebrew, RTL | Native Hebrew document; legacy default |
| `english-with-hebrew` | English, LTR | English body with Hebrew terms or blocks |
| `hebrew-with-english` | Hebrew, RTL | Hebrew body with English terms or blocks |
| `bilingual` | Explicit choice | Substantial sections in both languages |

For `bilingual`, supply `--main-language english` or `--main-language hebrew`. The base determines the shell and PDF language; it does not force every paragraph into that direction. Do not infer dominance from character counts or translate supplied content without a request. Profiles describe intent, not a quota or ban on quotations. Read [language and design](references/language-design.md) for scope and local language switches.

## 2. Start a project

Locate the actual skill root; do not assume the current directory is the skill. Use a fresh destination:

Read the generated [template catalog](references/template-catalog.md) to choose an existing recipe. Inspect the canonical registry without creating files:

```bash
python3 /path/to/skill/scripts/template_registry.py list
python3 /path/to/skill/scripts/template_registry.py resolve --kind paper \
  --language english --json
```

The resolver retains the request, resolved choices and their provenance. A declared acceptance case is a coverage requirement, not proof that the current PDF was built or reviewed. Use the [Hebrew–English glossary](references/glossary-he-en.md) for user and developer terminology.

```bash
python3 /path/to/skill/scripts/new_document.py --kind general \
  --language english --theme custom --directory /path/to/new-project
```

```bash
python3 /path/to/skill/scripts/new_document.py --kind report \
  --language bilingual --main-language hebrew --theme reader \
  --directory /path/to/bilingual-project
```

Choose `paper`, `note`, `technical`, `formula-sheet`, `data-report`, `annotated-note`, `general`, `letter`, or `report`. Choose `academic`, `reference`, `reader`, `core`, or `custom` independently of language. With the default `--layout standard`, omitting the theme selects `academic` for `paper` and preserves `reader` for the other kinds; an explicit theme always wins. Use `--package NAME` for additional packages; inspect availability and compatibility before relying on them. See [everyday workflow](references/everyday-workflow.md).

For a professional article, read [academic articles](references/academic-articles.md). Its shared academic theme works in all five language profiles:

```bash
python3 /path/to/skill/scripts/new_document.py --kind paper \
  --language english --directory /path/to/new-paper
```

Use `--language hebrew` for a native Hebrew paper, or `bilingual` with an explicit main language. The starter uses one title block, localized abstract text, visible section numbers, serif typography, continuous figure/table numbers and selective equation numbers. The article layout defaults to A4, 11 pt, 2.7 cm margins and centered footer folios; change source and verification settings together for a journal or a Letter reference. Empty author/date fields require real project metadata rather than invented attribution. Replace the sample argument and bibliography before delivery.

For a reference sheet, select `--kind formula-sheet` with `--layout reference-readable` (two columns) or `reference-compact` (three columns). Both presets use the reference theme when no theme is supplied; an explicit theme overrides that presentation choice without supplying or removing the layout. Other kinds currently accept `standard` only. Read [reference sheets](references/reference-sheets.md) before using narrow-column components:

```bash
python3 /path/to/skill/scripts/new_document.py --kind formula-sheet \
  --language hebrew --layout reference-readable --directory /path/to/new-sheet
```

Use `--language english` for a native English sheet; both mixed profiles and `bilingual` with an explicit main language share the same components. Choose readable density unless a real space limit calls for compact density. Compact typography pairs 6.3/7.8 pt prose with 6.25 pt main mathematics; readable typography pairs 9/11 pt prose with 8.75 pt main mathematics. The reference layout uniformly scales Computer Modern optical designs, with separate script tiers, inside `referencecolumns` and `referencewide`; the reference theme does not select these fonts. Declare body and math-size overrides before loading the layout, as described in the guide. Preserve mathematical symbols, units and physical diagrams when adapting language. Never reduce text automatically to force a page count.

Author reference sheets with two native heading levels: `\section` for a topic and `\subsection` for its subtopics. The presets number and bookmark these two levels; do not add a third numbered hierarchy. A topic inside columns receives a local underline. Put most formulas directly in the text with nearby assumptions; reserve frames for a few central results, notes and short Q&A. Note and caution rules follow the local prose language: right in Hebrew/RTL, left in English/LTR, including minority-language blocks. Wrap a short topic or its defining opening in `referenceentry` when it must stay together; allow long topics to flow or divide them into authored chunks. Keep counters, labels and bookmarks native. Use `referencewide` only for genuinely full-width content, outside columns, with topic/subtopic grouping when needed. The default separator is a thin gray 0.3 pt rule; define `\ReferenceColumnRule` before loading the layout, using `0pt` to omit it. Equation numbering remains selective. See [reference hierarchy](references/reference-sheets.md#author-native-heading-hierarchy) and [short-entry boundaries](references/reference-sheets.md#keep-short-entries-and-blocks-atomic).

Replace sample text and metadata before delivery. Keep source, figures, and local styles together. The generator refuses an existing destination; inspect local customizations before updating an existing project.

For an existing source, place language and layout hooks before the core:

```latex
\def\lakitlanguageprofile{english-with-hebrew}
\def\lakitdocumentclass{article}
\def\lakitclassoptions{11pt,a4paper}
\def\lakitgeometryoptions{margin=2.2cm,headheight=14pt}
\input{preamble.tex}
\input{document_components.tex}
\input{reader_theme.tex}
\hypersetup{pdftitle={Project brief},pdfauthor={}}
\begin{document}
\section{Purpose}
Write native English here. Use \h{עברית} for a short Hebrew term.
\begin{hebrewprose}
זו פסקה עברית נפרדת, בכיוון קריאה מתאים.
\end{hebrewprose}
\end{document}
```

Do not wrap an entire English document in `englishprose`. Native English is the base for headings, captions, lists, typography, and metadata.

## 3. Compose without forking the core

Read [architecture](references/architecture.md) before modifying an interface. Use layout hooks for class, geometry, spacing, and numbering. Keep one `preamble.tex` as the shared direction/math mechanism; never create separate English, exam, or report preambles.

`registry/studio-catalog.json` owns template recipes and defaults; the architecture and build contracts retain their existing ownership. A new content structure usually needs a starter, and new preset values need a catalog record. Add a runtime component only for a new semantic, layout, page-shell or presentation responsibility. Follow [catalog development](references/catalog-development.md), update the relevant glossary terms and add current acceptance evidence with each public change.

Load semantic extensions only when needed: `document_components.tex` for source annotations; `exam_components.tex` for exam helpers; `flow_tables.tex` for supported multipage tables; `deferred_notes.tex` for deferred notes from boxes/tables; `reference_components.tex` for reference-sheet blocks. Column flow belongs to `reference_columns.tex`; reference-page title/header/folio presentation belongs to `reference_shell.tex`. Compose core, semantic extensions, layout extension, page shell and one theme in that order. `topicrail.tex` is an alternative running-header component, not a second shell to load alongside `reference_shell.tex`.

Select presentation separately. `reader_theme.tex` preserves heading semantics. `academic_theme.tex` keeps visible headings and uses selective equation numbering with regular black caption labels. `reference_theme.tex` supplies black ruled headings, gray reference notes, regular black caption labels and selective equations; selecting it alone does not create columns. `clean_theme.tex` intentionally hides section numbering and uses selective equation numbering. Choose one theme. `clean_variant.tex` is a generated legacy bundle; do not combine it with its source components or a competing theme.

Custom designs and additional packages are allowed. Keep them in local project files, respecting load order and avoiding option clashes. Pass options for already-loaded packages before core input when required; load compatible new packages after the core. Use documented APIs for palette, local typography, and box styling. A theme must not redefine direction primitives, equation-reference repair, font observation, or build checks. Arbitrary document classes and package combinations are not automatically supported: isolate a new combination in a representative document, build and render it, then integrate it.

Do not add needless packages. For an external processor such as Biber, BibTeX, indexing, or shell execution, arrange and validate that pipeline explicitly; `build.sh` does not run those processors. Never silently weaken a check to accommodate a package. See [recipe](references/recipe.md).

## 4. Write directionally correct content

Use the current paragraph's language to decide direction. English prose needs no Hebrew wrappers. Read relevant [pitfalls](references/pitfalls.md) before unfamiliar constructs (טבלת 82 הפגמים האמפיריים); use [direction and math](references/direction-and-math.md) for RTL details. Hebrew-specific rules apply to Hebrew contexts.

| Context | API |
|---|---|
| Latin term inside Hebrew | `\en{...}` |
| Hebrew term inside English or TikZ | `\h{...}` |
| Full English paragraphs | `englishprose` |
| Full Hebrew paragraphs | `hebrewprose` |
| Inline code | `\code{...}` |
| Text inside math | `\text{...}`; language wrapper inside the text |

End language blocks at paragraph boundaries. Do not use inline wrappers for whole pages, headings, lists, or tables. In RTL, keep one logical LTR sequence in one island; keep signs and numeric ranges together. Keep a whole Hebrew verbal statement in one `\text{...}` in a display. Never put `\h` or `\en` directly in math. Use `\eqref` in prose and `\text{\eqref{...}}` inside math.

Keep a symbolic heading expression in one math span; provide a plain bookmark alternative with `\texorpdfstring`. Put labels on numbered objects. In academic articles and reference-theme sheets, number central results and equations cited or reused later. With selective numbering, `\eqref` registers use; `\noeqref{eq:key}` retains the number of an author-designated central equation without printing a reference. Use `equation*`/`align*` for intermediate steps, and cite the original number instead of assigning another number to a repeated formula. Importance is an editorial choice, not a density score. See [the equation policy](references/academic-articles.md#selective-equation-numbering).

The source gate rejects `PGFPLOTS-CONTOUR-EXTERNAL`: precompute contours and plot their coordinates instead of compile-time `contour lua` / `contour gnuplot` — why, and the precomputed form: [precomputed contours](references/figures-boxes-listings.md#pgfplots-קווי-גובה-מחושבים-מראש). See also [technical symbols and preflight](references/technical-symbols-and-preflight.md).

Use `tikzpic`/`qcirc` as direction/centering wrappers; place an actual `tikzpicture`/`quantikz` environment inside. Put `\figcap{\label{...}...}` immediately after the object; use `\tabcap` for short tables. `flowtable` owns its caption and label. Put an actual `lstlisting` inside `asmblock`, with its code body starting on a new line; `asmblock` itself only switches language and does not typeset code. Use `codebox` for framed numbered code. Keep atomic `tablebox` shorter than a page. Do not shrink text into unreadability.

## 5. Build and inspect

Use complete LuaLaTeX, Python 3.10+, Poppler, and the verified external font bundle. Read [studio setup and migration](references/studio-setup.md) and [recipe](references/recipe.md) for installation. `requirements-qa.txt` pins the tested Python baseline; run `python3 scripts/doctor.py` before claiming a fully checked environment. Font binaries are not included in the skill. For explicit online setup, run `python3 scripts/download_fonts.py --destination /path/to/fonts`, then set `HEBREW_LATEX_FONT_DIR` to that directory. The downloader verifies official upstream files against this release's SHA-256 pins before installation. Legacy archives require matching pins; the old manifest is preserved in `references/legacy-font-pins.txt` for provenance only. Import matching fonts with `scripts/setup_fonts.sh --from-directory /path/to/fonts` or `--from-skill` using a supplied older archive that contains them. Do not silently substitute fonts.

Compile generated or inspected trusted TeX. LuaLaTeX can run Lua with shell escape disabled; that flag is not a sandbox. Keep local inputs inside the declared project root.

```bash
bash /path/to/skill/scripts/build.sh /absolute/path/to/project/main.tex
```

On failure, `*.failed.pdf` is diagnostic evidence only; only readable diagnostic PDFs (confirmed by `pdfinfo`) are exported; a truncated PDF is not evidence. See [output recovery](references/output-recovery.md).

The build validates configuration, dependencies, font identity, source hazards, actual recorder inputs, convergence, glyphs, references, overflow, paper geometry, and PDF destinations before atomic publication. Configure legitimate choices explicitly:

- `EXPECTED_PAPER=a3|a4|a5|letter|legal` must match source.
- `CONTENT_PROFILE=generic|study-guide|report|exam|formula-sheet|review-sheet` selects advisory editorial checks, not a template.
- `PDF_FOLIO_LAYOUT` and `PDF_FOLIO_BAND` declare folio placement; see [folios](references/pdf-folios.md) for coverage and limitations.
- `PDF_CAPTION_COLOR=RRGGBB` and `PDF_CAPTION_LABEL_WEIGHT=bold|normal` must match the actual caption labels (defaults `555555` and `bold`). Generated academic and reference-theme projects declare black (`000000`) labels of normal weight; explicit caller settings remain authoritative.
- `PDF_REQUIRE_TITLE`, `PDF_MIN_BOOKMARKS`, `PDF_MIN_BOOKMARK_DEPTH` express actual project requirements; do not invent quotas.
- `REPRO=1` adds exact-byte rebuilding under the same environment.
- `SECTION_MACROS` declares custom section macros for content analysis.
- `DIRECT_NAVIGATION_DESTINATIONS` targets specific navigation paths needing stricter viewer compatibility.

Diagnose failures. Do not label partial or skipped checks as passes. Document intentional exceptions and their scope. Checks do not prove source completeness, scientific correctness, accessibility, or every viewer's behavior.

Render all pages into a fresh directory:

```bash
python3 /path/to/skill/scripts/render_review.py render main.pdf --output review
```

View every page at readable resolution. Check content, language boundaries, headings, punctuation, math, tables, code, captions, page numbers, clipping, spacing, and hierarchy. Compare facts and structure against inputs. Sparse pages can be intentional. A contact sheet is an index, not full review. Record only pages actually viewed:

```bash
python3 /path/to/skill/scripts/render_review.py record main.pdf \
  --review review/review.json --pages 1 --reviewer "Reviewer" \
  --notes "Record concrete observations from the actual page."
python3 /path/to/skill/scripts/render_review.py verify main.pdf \
  --review review/review.json --rerender
```

Complete all pages and rerender after edits. Use `--renderer mupdf` for an explicit second renderer where useful. Pixel differences alone are not defects. Check critical navigation in target viewers when available; state untested viewer limits. `/Lang` metadata is not PDF tagging or PDF/UA compliance.

## 6. Deliver and maintain

Deliver PDF and editable TeX with required local assets. Record toolchain, external dependencies, customizations, and material limitations. Keep logs, temporary outputs, and test evidence out of the installable skill.

For skill maintenance, update `VERSION`, metadata, owning records, generated guards, compatibility assets and glossary terms before freezing. Run the existing regressions and relevant negative checks; never lower corpus counts to hide failures. Freeze a candidate outside the installable source, then build the complete retained catalog matrix:

```bash
python3 scripts/doctor.py
python3 scripts/template_registry.py validate --json
python3 scripts/generate_studio_docs.py --check
python3 scripts/test_download_fonts.py
python3 scripts/check_package_hygiene.py
python3 scripts/package_skill.py --output /path/to/candidate.skill
STUDIO_RELEASE_CANDIDATE_SHA="$(python3 scripts/hash_file.py /path/to/candidate.skill)"
python3 scripts/test_studio_matrix.py --jobs 4 \
  --evidence-dir /path/to/new-matrix-evidence \
  --candidate-sha "$STUDIO_RELEASE_CANDIDATE_SHA"
```

View every unique primary page from the matrix at readable resolution, and record concrete observations only after viewing. Its case records identify each PDF and `renders.mupdf.review` manifest; use the existing `render_review.py record` API. Compilation and rendering leave human review pending. After complete primary review, seal the evidence with a fresh same-renderer replay, then run FULL against that exact candidate and seal:

```bash
python3 scripts/test_studio_matrix.py --seal /path/to/new-matrix-evidence \
  --candidate-sha "$STUDIO_RELEASE_CANDIDATE_SHA"
HEBREW_LATEX_CATALOG_MATRIX_EVIDENCE=/path/to/new-matrix-evidence \
HEBREW_LATEX_CATALOG_CANDIDATE_SHA="$STUDIO_RELEASE_CANDIDATE_SHA" \
  bash scripts/test_all.sh
FAST=1 bash scripts/test_all.sh
python3 scripts/check_package_hygiene.py
python3 scripts/package_skill.py --output /path/to/release/hebrew-english-latex-studio.skill
python3 scripts/hash_file.py /path/to/release/hebrew-english-latex-studio.skill
```

The final archive must have the candidate's exact SHA-256. Keep source bytes, modes and file population unchanged after freezing; any source change requires a new candidate and affected evidence. FULL requires current sealed matrix evidence and its candidate identity; a selected-theme subset or source-only preview cannot satisfy it. A regression run that is not a release declares `HEBREW_LATEX_CATALOG_VISUAL=routine` and leaves out only that gate ([routine runs](references/catalog-development.md#release-workflow)). FAST checks contracts and is not runtime matrix approval. The deterministic packager checks static release contracts and refuses conflicting outputs; package creation alone does not prove that FULL, rendering or human review ran. Full tests need the TeX toolchain; FAST still needs fonts, Python QA dependencies, and Poppler. See [catalog development](references/catalog-development.md#release-workflow) for evidence paths and the complete release order.

## Reference routes

Read the guide relevant to the task, not the entire directory:

| Need | Reference |
|---|---|
| Language, design freedom, packages | [Language and design](references/language-design.md) |
| Layer ownership and hooks | [Architecture](references/architecture.md) |
| Available recipes, presets, themes and examples | [Template catalog](references/template-catalog.md) |
| Hebrew–English user and developer terminology | [Glossary](references/glossary-he-en.md) |
| Add a recipe, component or public hook | [Catalog development](references/catalog-development.md) |
| Setup, dependencies, failures | [Recipe](references/recipe.md) |
| Starter selection and daily use | [Everyday workflow](references/everyday-workflow.md) |
| Professional papers, selective math numbering | [Academic articles](references/academic-articles.md) |
| Compact or readable formula/reference sheets | [Reference sheets](references/reference-sheets.md) |
| RTL mechanics and known hazards | [Direction and math](references/direction-and-math.md), [pitfalls](references/pitfalls.md) |
| Figures, boxes, code, short tables | [Components](references/figures-boxes-listings.md) |
| Long tables and notes | [Flow tables](references/flow-tables.md), [notes](references/deferred-notes.md) |
| References and citations | [Bilingual references](references/bilingual-references.md), [citations](references/citations.md) |
| Headings, code, contents | [Headings](references/heading-and-short-code.md), [contents](references/measured-contents.md) |
| Content and optional features | [Content style](references/content-style.md), [features](references/optional-features.md) |
| Fonts and reproducibility | [Runtime fonts](references/runtime-fonts.md), [environment](references/environment-report.md) |
| Renderers, geometry, folios | [Renderers](references/pdf-strings-and-renderers.md), [geometry](references/pdf-geometry-review.md), [folios](references/pdf-folios.md) |
| Parsing edge cases | [Literal boundaries](references/literal-source-boundaries.md), [quotes](references/quote-source-boundaries.md), [listing quotes](references/listing-smart-quotes.md) |
| Preservation and releases | [Output recovery](references/output-recovery.md), [release continuity](references/release-continuity.md) |
