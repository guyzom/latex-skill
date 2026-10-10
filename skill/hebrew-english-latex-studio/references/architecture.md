# Architecture and extension contracts

The public skill identifier is `hebrew-english-latex-studio`. Historical
`HEBREW_LATEX_*` environment variables and internal `hllpdf`/`lakit` identifiers
remain supported for existing projects. Its scope is general English, Hebrew
and bilingual LuaLaTeX documents. Language,
layout, presentation and document purpose are independent choices; no genre
needs its own copy of the direction/math mechanism.

## Independent document decisions

| Axis | Owner | Decisions | Does not decide |
|---|---|---|---|
| Language | Core pre-input hooks | Five language profiles, main language, localized document shell | Theme, genre, margins |
| Layout | Core pre-input hooks and optional layout extension | `article`/`report`, paper, margins, paragraph style, spacing, hierarchy depths; local column flow and body sizes | Translation, language policy, colors |
| Presentation | One selected theme or project overlay | Palette, typography, rules, boxes, declared numbering visibility | Semantic content, main language, build gates |
| Semantic features | Optional extensions | Exam helpers, source cards, deferred notes, continuing tables, reference blocks | Theme, global geometry |
| Page shell | Optional page-shell extension | Running headers, title shell, folios and local header dimensions | Main language policy, document class |
| Content intent | Author and `CONTENT_PROFILE` | Audience, purpose, content; advisory editorial checks | Runtime TeX or automatic redesign |
| Additional packages | Project composition | Needed functionality and documented load order | Replacing core ownership without validation |
| Verification | Build and visual review | Actual source, PDF, navigation, glyph and layout evidence | Invented content or visual approval |

Language is an authoring policy owned by the mechanism core, not a new file
layer. In particular, English is a native document main language, not a giant
`englishprose` block embedded in a Hebrew document. See
[Language and design decisions](language-design.md) for exact selection rules.

## Architecture roles

The canonical vocabulary lives in `scripts/architecture_contract.py`.

The declarative [template registry](../registry/studio-catalog.json) owns recipes,
starters, layout/theme defaults, declared composition strategies and acceptance
case IDs. [Its resolver](../scripts/template_registry.py) references the existing
language, architecture and build contracts. It does not create another runtime
component system. The generated [template catalog](template-catalog.md) displays
these same records and derives the component/hook inventory from this contract.
See [catalog development](catalog-development.md) for migration, revisions and
evidence boundaries, and the [glossary](glossary-he-en.md) for stable terminology.

| Role | Shipped owner(s) | Responsibility |
|---|---|---|
| `mechanism-core` | `assets/preamble.tex` | Language resolution, direction islands, math, caption/anchor mechanisms, baseline presentation and public shell hooks |
| `semantic-extension` | `exam_components.tex`, `document_components.tex`, `deferred_notes.tex`, `flow_tables.tex`, `reference_components.tex`, `study_components.tex`, `index_components.tex` | Meaningful document features independent of a theme |
| `layout-extension` | `reference_columns.tex` | Local column count, flow, gaps, body typography and wide-block boundaries |
| `page-shell-extension` | `topicrail.tex`, `reference_shell.tex` | Optional running headers, title shell and folios |
| `presentation-theme` | `clean_theme.tex`, `reader_theme.tex`, `academic_theme.tex`, `reference_theme.tex` | Optional shipped presentation policies |
| `compatibility-bundle` | `clean_variant.tex` | Generated legacy carrier of clean theme plus exam API |

Recommended composition is language/layout definitions, core, needed semantic
extensions, optional layout extension, optional page-shell extension, selected
theme, document content.
The optional pure layers depend on core, not on each other. Loading a theme
last establishes presentation precedence, not a theme-to-extension dependency.
The clean, reader, academic and reference themes deliberately conflict pairwise. The
legacy carrier conflicts with its embedded pure layers and with the reader
academic and reference themes. `reference_shell.tex` and `topicrail.tex` are
alternative page shells and conflict in both load orders.

Project-local themes and compatible packages are allowed. They do not have to
be added to `ASSET_SPECS` merely to create one document. That schema inventories
shipped assets and their generated guards, not every possible user design.
Promoting a project extension into the distributed skill requires a declared
owner, dependencies, guards, public symbols and focused regression evidence.

## Language contract

Define hooks **before** loading the core:

```latex
\def\lakitlanguageprofile{english-with-hebrew}
\input{preamble.tex}
```

| `lakitlanguageprofile` | Resolved `lakitmainlanguage` | Intent |
|---|---|---|
| `hebrew` | `hebrew` | Hebrew document |
| `english` | `english` | English document |
| `hebrew-with-english` | `hebrew` | Hebrew-led, with secondary English |
| `english-with-hebrew` | `english` | English-led, with secondary Hebrew |
| `bilingual` | Explicit `hebrew` or `english` required | Substantial content in both languages |

Omitting the profile preserves the historical Hebrew default. A matching
explicit main language is allowed in the first four profiles; a conflicting
one fails. Unknown values fail. Balanced bilingual content still needs one
stable main language for the document shell; it is not inferred from the first
paragraph or the amount of each language. Profiles express intent, not a
character whitelist or an automatic translator. Both languages remain usable.

`\h{...}` and `\en{...}` isolate short runs. `hebrewprose` and `englishprose`
scope complete paragraphs. `\doclang{...}` isolates inline document-shell text
in the resolved main language. It does not translate its argument and is not a
paragraph environment. Language belongs to the core; themes may not overwrite
these interfaces or change the selected profile.

The schema exposes `LANGUAGE_PROFILE_SPECS`, `LANGUAGE_PROFILES`,
`LANGUAGE_HOOKS`, and `resolve_language_profile(profile, main_language=None)`.
The resolver returns the resolved main-language string or raises `ValueError`.
The generator consumes it; runtime TeX validates the same rules for handwritten
sources. The log record `HLLLANG|<profile>|<main>` records the runtime choice.

Source lint uses `language_context.py` for bounded lexical context: literal
hook definitions, scoped `\selectlanguage`, language environments and short
islands. It ignores comments, literal examples and macro definitions. It does
not evaluate arbitrary macro expansion or conditionals; compilation is the
authority for such sources. Conflicting document profiles do not grant a
global lint exemption. A native-English font exception applies only in a
resolved English context under an explicit non-`hebrew` profile.

## Layout contract

Seven independent layout hooks retain the historical defaults for existing
sources. The paragraph-style hook explicitly names the native class policy:

```latex
\def\lakitdocumentclass{report}
\def\lakitclassoptions{12pt,a4paper}
\def\lakitgeometryoptions{margin=2.3cm,headheight=14pt}
\def\lakitlinespread{1.3}
\def\lakittocdepth{1}
\def\lakitsecnumdepth{2}
\def\lakitparagraphstyle{indented}
\input{preamble.tex}
```

Use `article` for short documents and `report` when chapters are useful. These
are the two tested classes; custom visual design does not imply arbitrary
class support. A new class needs a separately validated core integration.
Layout hooks must not redefine bidi primitives, captions or checkers.

`\lakitparagraphstyle` accepts only `indented` or `block`. Define it before
loading the core. `indented` leaves the selected class's paragraph dimensions
and first-paragraph-after-heading behavior intact; it does not insert manual
indentation. `block` sets a zero first-line indent and a modest paragraph gap
of `6pt plus 1pt minus 1pt`. These are ordinary scoped TeX lengths: an author
can adjust `\parindent` and `\parskip` after loading the core. The runtime log
records the selected style as `HLLPAR|<style>`.

The genre recipe chooses this policy independently of language and theme.
Managed letters, notes, reports and other non-paper starters use `block`;
paper starters explicitly use `indented`. Changing a language profile or a
theme must not change that choice. Local `englishprose` and `hebrewprose`
environments inherit the paragraph dimensions and restore the outer state.
Display mathematics within a continuing paragraph is not a new paragraph.
Manual document titles begin flush even if the author chooses indented prose.

Source and verification must agree about paper. For example, set
`\lakitclassoptions{11pt,letterpaper}` with `\def`, and build with:

```bash
EXPECTED_PAPER=letter bash scripts/build.sh main.tex
```

The source determines layout; the build validates actual page boxes.

`HOOK_SPECS` records the owner, declaration timing, effective scope, value type,
unit and literal or symbolic default of public configuration hooks. It also
declares which hooks a catalog preset may configure. Language and presentation
hooks remain in their own contracts; a preset cannot overwrite their ownership.
Symbolic defaults are rules, not measured values. Reference math-size hooks are
part of the reference layout's public inventory, including the nested tier.
The generated [public hook inventory](template-catalog.md#public-hook-inventory)
lists current declarations directly from `HOOK_SPECS`.

## Layout extensions

`reference_columns.tex` owns the local `referencecolumns` and `referencewide`
environments, column count/gap/skip, separator width through
`\ReferenceColumnRule`, explicit body font-size/baseline hooks and separate
main/script/scriptscript mathematical-size hooks.
It requires the initialized core, not a particular theme or semantic extension.
It uses the core's resolved document main language for column progression in
both full bilingual bodies, including translated counterpart pages. Local
heading and paragraph language does not reverse that progression. It cannot
replace language setters, mathematical direction or the global page geometry.
The author still chooses class, paper and margins through pre-input hooks.
`\ReferenceSelectBodyFont` also selects zero first-line indentation and tight
local paragraph spacing (`0pt plus .5pt`) for reference content. Both column
and wide blocks use this layout policy even without a reference theme, and
their groups restore the surrounding paragraph style on exit. Compact
reference layout therefore does not inherit a letter's open paragraph gap or
an academic paper's first-line indentation.

The generator's nonstandard reference layouts currently apply only to
`formula-sheet`: `reference-compact` selects three columns at 6.3/7.8 pt;
`reference-readable` selects two at 9/11 pt. Both use an article 10 pt shell
and a 5 mm gap with a 0.3 pt separator, with explicit local body sizing rather
than automatic shrinking. Separator width is a nonnegative layout length;
zero disables it. Reference starters set numbering and bookmark depths to 2
through existing core hooks: topic and subtopic. This does not alter equation
numbering or remove generic deeper heading support from the core.
Body and mathematical-size overrides precede loading the extension. Generated
compact mathematics is 6.25/4.375/3.125 pt; readable mathematics is
8.75/6.125/4.375 pt. The extension registers separate scalable Computer Modern
optical families and normal/bold reference math versions, using 10 pt designs
for primary mathematics and 7/5 pt designs for its ordinary script tiers.
Font scaling is uniform; neither glyph outlines nor rendered boxes are
distorted. Auxiliary math alphabets and extended symbols use explicit
scalable TeX-distribution faces.

The reference environments select these math versions and size bindings
locally. Native normal/bold requests map to the reference variants while
explicit custom versions pass through; the surrounding math configuration is
restored on exit. The extension does not replace the core's families or global
`\DeclareMathSizes` settings. Main mathematics defaults to the declared body
size when the extension is used directly without explicit math overrides;
script tiers default to 70% and 50% of the mathematical size. Validate positive
sizes ordered as scriptscript <= script <= main, with no minimum 5 pt clamp.
The theme owns presentation, not the reference-body optical designs or
authored mathematical-tier sizes. This is an explicit local font contract,
not automatic content fitting or an exemption
from font substitution checks. See [runtime typography](runtime-fonts.md#reference-mathematics).
`--layout standard` preserves existing layouts. Loading a reference theme alone
does not load or enter columns. See [reference sheets](reference-sheets.md) for
wide content, language blocks and component boundaries.

## Semantic extensions

`exam_components.tex` owns `\qlabel`, `\pts`, `\finalans`, `\srcfig`, and
`\srcfigdir`. It neither selects exam styling nor activates `showonlyrefs`.
`document_components.tex` owns `\sourcelink`, `\glossaryentry`, and optional
`framedtable` and `semanticframedtable` with the local `\framedtablewidth` budget.
The former fits rows/caption; the latter matches the actual active semantic-box
width and inset conventions through shared live styles. Natural inner columns
are not stretched. Both reuse `tablebox` and reject page-tall content.
It does not change table defaults or provide framed multipage flow.
The glossary helper joins a term and definition with a spaced em dash and adds no period.
Neither helper is a bibliography system.
`deferred_notes.tex` owns `\DeclareDocNote`, `\DocNoteMark`, `\PrintDocNotes`.
`flow_tables.tex` owns `flowtable` and the documented H/E/N column convention;
existing column-name collisions are rejected rather than overwritten.
`reference_components.tex` owns short notes/warnings/formula blocks, short Q&A
and explicitly segmented long Q&A. Its unframed atomic `referenceentry`
container keeps a short complete topic or its heading and defining opening
together. The author chooses that boundary; long topics remain ordinary flow
or explicitly authored chunks. Entries retain native headings and counters,
allow contained `referencefigure`/`referencetable` objects through a distinct
private box, and reject nested or full-column-oversized entries. They add no
heading API, frame or automatic scaling. Its neutral styles do not require the
reference theme. The four reference style hooks have separately declared
mutable presentation ownership; styling them does not transfer the semantic
environments or labels to a theme.
Its `\referencefigcap` and `\referencetabcap` delegates preserve core caption
counters, labels, anchors and optional short entries, while inheriting the
local body size. They do not replace the core caption mechanism.
The neutral `referencefigure` and `referencetable` atomic containers keep the
complete object and its caption together at the actual local `\linewidth`.
They add no floats, frame, scaling or independent counters; an oversized
object requires an authored split or an appropriate wide-block transition.

Load only needed extensions after core. An extension can use universal core
primitives but cannot own theme palettes, global geometry, class, hierarchy
policy or verification gates. Read the specific extension reference before
using advanced components inside each other.

## Page-shell extensions

`topicrail.tex` may own its pagestyle, rail, private palette and local header
dimensions. It may not own `\documentclass`, global geometry, language/layout
hooks or `\h`/`\en`/`\code`. A page-shell component should obtain direction
from the selected document or its explicit local language context.
The topic rail's default order follows `\lakitmainlanguage` when the shell loads.
`\STdirRTL` and `\STdirLTR` override its order only; labels remain in the main
language through the existing `\doclang` wrapper even when a minority-language
paragraph ships out the page. Use `\en` or `\h` for minority terms inside
`\STnames`. Legacy projects without language declarations retain Hebrew and
RTL defaults.
`reference_shell.tex` owns the compact first-page title, running-title metadata
and uniform centered footer folios. It leaves author/date empty unless supplied
and uses the selected main language for shell direction. Load one of these
page shells, not both.

## Theme contract

The core provides a baseline; selecting a separate theme is optional.
`reader_theme.tex` preserves heading content, numbering and equation policy.
`clean_theme.tex` intentionally hides section numbering (`secnumdepth=-2`),
uses `showonlyrefs`, and provides flat table numbering. These are declared
presentation policies, not inevitable consequences of an exam genre.
`academic_theme.tex` preserves numbered headings, provides serif black
presentation, normal-weight black caption labels and continuous figure/table
numbering, and activates `showonlyrefs`. Its title and abstract presentation
uses standard class interfaces. It does not invent authors, translate content
or impose a page layout. See [academic articles](academic-articles.md).
`reference_theme.tex` uses serif black presentation, ruled headings, gray note
backgrounds, normal black captions, continuous figure/table numbers and
`showonlyrefs`. It sets no column count, body font size, margins or language.
It keeps an ordinary section column-local, with a compact black underline,
and presents an explicitly authored section within `referencewide` across
the full text width. Reference starters use native `\section` and
`\subsection` only; counters, starred forms, labels, contents entries and
bookmarks remain class-owned. Most math is authored unboxed; note and caution
rules follow the current prose language's reading edge: physical right for
Hebrew/RTL, physical left for English/LTR. Local minority-language blocks use
their own edge while page column order remains tied to the main language.
Compact Q&A uses a uniform pale gray
field with square corners and a thin closed border. The theme supplies the
gray column-rule color only within reference columns; the layout owns its
width. No parallel heading or numbering API is introduced.
The reference layouts and theme are independently selectable; explicit generator
theme choices remain authoritative.

The core owns the public presentation hooks
`\lakitcaptionstyle` for the complete paragraph, the compatibility hook
`\lakitcaptionlabelstyle{complete label}`, and `\lakitcaptionpunctuation`.
The defaults are regular black text at one local small size and a colon.
Native captions and continuing tables share the same style; label-only
formatting is an explicit project override rather than the default.
Themes may redefine those hooks without replacing `\figcap`, `\tabcap`,
their language labels, anchors or reference semantics. The preamble-only
`\lakitcaptionnumbering{continuous|within-major}` API changes reset edges,
printed counter values and destination identities together. Academic selects
`continuous`; the unchanged baseline is `within-major`.
The schema inventories mutable caption hooks as `PRESENTATION_HOOKS`,
separately from uniquely owned semantic API symbols. A theme's intentional
style override does not give it ownership of the caption mechanism.

`REFERENCE_STYLE_HOOK_SPECS` describes four scoped reference presentation hooks:
`\referencenotestyle`, `\referencewarningstyle`, `\referenceformulastyle` and
`\referenceqastyle`. `reference_components.tex` provides neutral defaults and
`reference_theme.tex` is the explicitly permitted shipped overriding provider.
These are mutable hook values, not duplicate ownership of the reference
semantic API. Keep every new style exception explicit in the schema.

Choose one theme or a project-local replacement. A custom theme may restyle
boxes without removing their content or silently translating labels. It must
not redefine semantic APIs or change language, global layout or build policy.
Put margin/class decisions in the pre-input layout hooks. Project fonts can be
selected explicitly in a typography overlay, with file/face provenance and
font coverage checked; shipped font pins remain valid only for pinned fonts.
A custom design does not inherit blanket visual certification from a shipped
theme. Test its actual composition and review every page.

## Capabilities contract

A role names code ownership; a capability names available behavior.
`architecture_detection.py` is the shared source-to-capability adapter for
checkers and the provider-edge parser used by architecture QA. It recognizes
complete `\input`/`\include` arguments and certain directly embedded policies;
filename substrings such as `myclean_theme.tex` do not activate clean policies.

| Capability | Pure provider | Legacy carrier |
|---|---|---|
| `mechanism-core`, `layout-hooks`, `language-profiles` | `preamble.tex` | — |
| `presentation.caption-hooks`, `policy.caption-numbering-api` | `preamble.tex` | — |
| `semantic.exam-api` | `exam_components.tex` | `clean_variant.tex` |
| `semantic.document-api` | `document_components.tex` | — |
| `semantic.deferred-note-api` | `deferred_notes.tex` | — |
| `semantic.flow-table-api` | `flow_tables.tex` | — |
| `semantic.reference-api` | `reference_components.tex` | — |
| `semantic.study-api` | `study_components.tex` | — |
| `semantic.index-api` | `index_components.tex` | — |
| `layout.reference-columns` | `reference_columns.tex` | — |
| `page-shell.topicrail` | `topicrail.tex` | — |
| `page-shell.reference` | `reference_shell.tex` | — |
| `presentation.clean`, `policy.showonlyrefs`, `policy.hide-section-numbering`, `policy.flat-table-numbering` | `clean_theme.tex` | `clean_variant.tex` |
| `presentation.reader` | `reader_theme.tex` | — |
| `presentation.academic`, `policy.showonlyrefs`, `policy.continuous-caption-numbering` | `academic_theme.tex` | — |
| `presentation.reference`, `policy.showonlyrefs`, `policy.continuous-caption-numbering` | `reference_theme.tex` | — |

`language-profiles` means support for choosing profiles; it does not assert a
particular active language. Active selection is a runtime/document property.
Detection is conservative source analysis, not arbitrary TeX evaluation.
A project-local feature that hides structural content or changes navigation
needs explicit verification; renaming an asset is not a way to bypass gates.

## Runtime layer contract

Every shipped asset is single-load. Pure optional assets require the core's
ready sentinel, emitted only after successful core initialization. Explicit
conflicts are symmetric. `AssetSpec` owns prerequisite/conflict rules, sentinel
names, capabilities, and public symbols. `render_architecture_guards.py`
generates the runtime guards from this schema; do not edit generated regions.

`ROLE_DEPENDENCIES` and `PREFERRED_LAYER_ORDER` express a one-way dependency
DAG. `validate_contract()` checks ownership, dependencies, cycles, conflicts,
capability parity and generated carriers. The static suite covers every
optional asset, every ordered pair and all pure-layer subsets (including
expected conflicts); it uses bounded whole-stack ordering rather than claiming
factorial exhaustive permutations. Runtime tests execute each declared guard
rule through real LuaLaTeX. FAST runs do not establish runtime engine evidence.

## Compatibility bundle

`clean_variant.tex` is a generated **compatibility bundle**, not a source of
truth. `render_compat_bundles.py` derives it from clean theme plus exam
components. It provides exactly their capability union and marks their loaded
sentinels. It may coexist with independent extensions but cannot be mixed with
its pure source carriers or reader theme in either order. Existing documents
can keep `\input{clean_variant.tex}` after core.

The academic and reference themes are also incompatible with the clean carrier,
in either load order; choose one presentation policy.

The architecture JSON schema is version **5**: optional study and index
semantic owners add keyed identities and explicit index-language/rank APIs,
including a pre-input index-column hook and local study-heading formatter.
Version 4 added typed configuration-hook contracts and reference mathematical-size
ownership. Version 5.3 introduced the layout-extension role and scoped reference
style-hook inventory; the existing language-policy and asset fields remain.
Consumers should read `schema_version`; do not confuse it with the skill
release version or a project's manifest schema. New shipped assets default to
no maintenance sync and no density exemption until explicitly declared.

## Build and configuration contracts

`build_contract.py` is the lightweight owner of accepted content profiles,
page sizes and section-macro parsing. `validate_build_config.py` rejects bad
configuration before the compiler runs. `CONTENT_PROFILE`, `SECTION_MACROS`,
`EXPECTED_PAPER`, `REPRO`, `MAX_CROSS_PAGE_DESTINATIONS`, and
`SOURCE_DATE_EPOCH`, `INDEX_PROCESSOR`, and `INDEX_STYLE` are build-only settings,
not TeX theme inputs. The index processor and style participate in the semantic
build identity. `HLLPDF_INDEX_EVIDENCE_DIR` is an optional diagnostic export
destination and does not change that identity.

`CONTENT_PROFILE` selects advisory density/rhythm checks. It does not select a
theme or translate prose. A sparse page can be intentional; never insert
material or shrink type just to improve a metric. Shipped runtime assets are
excluded from density via the schema. A custom theme is not automatically
excluded or granted a false clean bill of health.

`PDF_CAPTION_COLOR` and `PDF_CAPTION_LABEL_WEIGHT` describe the actual caption
label palette and weight for rendered destination checks. Defaults preserve
the core's `000000`/`normal` captions; generated academic and reference-theme wrappers declare
`000000`/`normal` when those variables are unset. These settings do not restyle
the PDF and do not waive missing or displaced caption destinations.

Verification has three distinct layers: hard build/PDF gates, advisory
editorial checks, and human visual/content review. No one layer replaces
the others. `new_document.py` creates a new project and records copied-asset
hashes; that snapshot does not claim the files remain unchanged after editing.
`render_review.py` ties page-review records to actual PDF/image bytes. Success
requires review of the current output, not reuse of stale approvals. See
[Everyday workflow](everyday-workflow.md).

Acceptance governance connects the catalog's 53 closed IDs (the existing 49 plus two optional components and their examples) to retained
execution evidence through [catalog_coverage.py](../scripts/catalog_coverage.py).
`acceptance_contract(catalog)` owns their allowed meanings;
`acceptance_coverage(root, catalog, plan, results=None, theme_filter=None)` binds
required declarations to derived requests, canonical cases/aliases,
input-inventory hashes and build fingerprints. The keyword-only theme filter
defaults to the complete catalog, where all 53 IDs are required. An explicit
supported theme preserves the local CLI subset: only unmatched, unselected
generator-theme IDs may be `not-requested`; examples and native components
remain required. Unknown or uncovered required IDs and invalid populations or
bindings fail. Runtime acceptance requires every requested mapped canonical
case to succeed in its actual managed build and both MuPDF/Poppler renders
with complete page evidence;
declarations without results remain `declared`, with no runtime pass. A local
subset may pass `scoped_acceptance_ids_pass` but cannot pass
`all_acceptance_ids_pass`; release verification and sealing require complete
coverage with `theme_filter=None`.
`studio_matrix.verify_matrix` recomputes the bridge rather than trusting its
stored counts or hash. Its `visual_claim=False` preserves primary human review
as a separate requirement, and project-creation metadata remains provenance.
A future acceptance ID needs an explicit closed-contract meaning, a concrete
case/alias mapping and meaningful negative controls for uncovered/unknown IDs,
binding drift, failed or missing execution, invalid filtered populations and
attempts to pass a local subset as complete release evidence. See
[catalog development](catalog-development.md#evidence-required-before-release).

The recorder identifies inputs actually consumed on each pass. Local source,
images and data are hashed for convergence and rechecked before publication;
changing an input invalidates the result. A document's final/failed outputs
cannot feed the next build. Verified PDF publication and failure evidence use
`atomic_replace.py`: replacement does not follow an existing destination
symlink. This is output recovery, not a substitute for backups.

## Runtime versus maintenance tools

| Surface | Contract |
|---|---|
| Runtime/build | Build/checker scripts, contracts and helper modules travel with the standalone package |
| QA | `doctor.py`, `selftest.py`, `test_all.sh`, focused tests and fixtures establish stated evidence |
| Release | `VERSION`, QA dependency pins, hygiene, guard/bundle renderers and `package_skill.py` define the distributable |
| Fleet maintenance | `sync_preamble.sh` uses schema-selected carriers under an explicit or detected fleet root; it does not overwrite project custom themes |

Font binaries are external dependencies. `assets/fonts/SHA256SUMS` is the
canonical trust manifest; a different directory's manifest cannot replace it.
`install_fonts.py` validates staging before publication. Additional fonts need
their own recorded provenance; runtime inventory distinguishes canonical
verified resources from uncontrolled resources.

Build/QA supports Bash 3.2 and avoids GNU-only shell utilities. Python owns
hashing; `cmp -s` handles byte comparison. Hygiene rejects caches, generated
PDF/aux/log debris, symlinks and nonportable filenames. `package_skill.py`
validates the release then writes deterministic archives outside the source
tree. Source changes must be committed and synced through the skill-management
workflow; an exported archive alone does not install/update the active skill.

## Backward compatibility and limits

An old document beginning only with `\input{preamble.tex}` retains Hebrew,
`report`, A4, 12 pt, 2.3 cm margins, 1.3 spacing and historical depths.
Historical internal macro/environment identifiers and the generated clean
carrier remain supported.
New documents should declare their intended language profile and use public
hooks instead of copying core code for every design.

Changing a global direction or caption mechanism requires focused regression
evidence across both main languages. This skill does not promise arbitrary
LaTeX class/package compatibility, automatic translation, complete PDF
accessibility, viewer-independent rendering, or correctness of substantive
claims. Record limitations relevant to the actual deliverable without turning
a successful build into a broader assurance.
