# Hebrew English LaTeX Studio — release metadata

## v5.4.9

The retained bilingual-reference example declares table order locally: the
Hebrew function input/key sits at the physical right without changing the
surrounding caption language or reference destination. Actual rendered row and
header geometry is checked against both Hebrew and English reading order;
independent wrong-order twins must fail while keeping their navigation intact.

Terminology paragraphs now scope the definition language independently of the
term, align Hebrew definitions to the physical right and English definitions
to the physical left, and wrap naturally around one spaced em dash. The
four term/definition language pairs are documented and exercised. Authored
sentence punctuation and existing table/caption behavior are retained.

Complete bibliography entries use `\bibentryprose` to preserve local English
or Hebrew paragraph edges, multipage wrapping and authored typography while
retaining native bibliography headings, labels, citation keys and destinations.
Current starters, examples, source-language lint and teaching instructions
follow this paragraph policy.

Optional study components freeze exercise identity and title when declared,
then reuse them in end-of-book solutions and explicit paired navigation.
Optional index components use language-local groups and authored sort keys;
the supported Arabic imakeidx writer keeps numerical locators valid at
shipout. An explicit managed makeindex stage rejects rejected, empty or
omitted index output even when the processor exits zero. Other processors
and numbering routes still require separately validated integration.
The Arabic formatter guard accepts both exact core macro forms produced by
legacy and current LaTeX kernels; Roman and custom numbering remain rejected.

Generator selection, current examples, catalog ownership and regression
controls accompany the new optional features. Actual-PDF checks include
local direction and line edges, long terms, source identity, paired targets
and index locators. The supported processor, numbering, authored-sort and
visual-review boundaries are documented with each component. The approved
scoped licensing remains unchanged.

## v5.4.8

Table examples now choose semantic column order, cell language and physical
alignment separately. Hebrew prose is right aligned, including wrapped final
lines, while English prose is left aligned. Hebrew notation keys sit at the
right; a paired local English example puts the key at the left even in an RTL
document. Mathematical, numerical and code cells retain their LTR reading order
and deliberate alignment. The gallery, exam sample, reference-sheet starters
and authoring instructions use these rules; both reference layout recipes are
revised with their starter fingerprints. Natural table widths, caption styling
and the enclosing-direction contract of flow-table H/E/N cells are preserved.

Focused actual-PDF checks cover Hebrew, English, mixed and bilingual contexts,
physical text edges, wrapped prose, semantic column order and independent bad
alignment/order controls. Visual review and full-suite coverage are reported
separately in each delivery. The existing scoped license is unchanged.

## v5.4.7

Parenthetical subcaption labels remain intact before digit-leading Hebrew text.
Their Latin direction is selected before constructing the label box, including
older Babel/LuaHBTeX where selecting the language inside an RTL box reverses
the drawn parentheses. CI retains focused caption PDFs for actual visual review.
Optional subcaption defaults are applied when the package loads, preserving
explicit package options and preamble styling. Default captions retain a smaller
local body size and baseline instead of enlarging compact reference typography.
Continuing-table notices no longer widen natural data columns. Mixed-language
figure/table lists preserve the list shell's number and page placement while
retaining each entry's language and navigation.
Density advisories recognize both optional table environments and describe
natural-width tables without encouraging gray panels as a default.
The navigation render gate matches caption labels to frames in both physical
axes, so a table in a neighboring reference column cannot own an open table's
anchor. Positive Hebrew reference fixtures keep comma-separated object references
in one Latin island; actual link positions and displaced-anchor controls verify
reading order and preserve detection of a jump inside its own frame.

Actual-engine regressions exercise wrapping, physical glyph/column geometry,
explicit style overrides, continuation rows and clickable destinations; historical
mutations must fail the corresponding checks. The existing scoped tooling license
and template/third-party exclusions remain unchanged.

## v5.4.6

Captions now use one regular black paragraph style and a colon separator in
all shipped themes, native captions and continuing tables. Short table samples
use natural numeric columns with authored prose widths; continuing tables keep
outer cell padding and center natural-width specifications. Glossary entries
use a spaced em dash without altering sentence punctuation. Regression controls
cover physical caption fragments, mixed direction, wrapping and navigation.
Optional content-fit `framedtable` and semantic-width `semanticframedtable` reuse
the existing frame mechanism and live theme geometry, keep captions and rows
together, wrap authored prose columns and reject page-tall content. Semantic
outer width/insets match real semantic boxes without stretching natural columns.
There is no fixed column count: varied RTL/LTR two-, four- and five-field examples
are adaptable choices, and other structures may fit better. The unframed default
remains prominent: redundant row-color/grid samples become English compact
and five-field wrapped open tables. Optional frames use neutral gray ink and
white fill, distinct from the semantic category palette; actual PDF paint
regressions reject the former blue tint. Data-report recipe revision 6 records
the unframed-default and neutral-frame authoring guidance.
Frame/bare-table navigation and black caption links have real PDF
controls, including width/height failures and a displaced-anchor mutation.
The short keyed-note gallery table also uses natural unframed columns with
explicit Hebrew key order; its note identities and repeated links are validated.
Nested-container regressions identify white table fills by their actual neutral
edges, preserving four-edge, missing-border and nearest-listing-scope controls.
Historical engine-specific reversal witnesses no longer assume that every newer
LuaHBTeX reproduces an old defect. Independent corrupt cell/reference formatters
must still fail actual PDF glyph checks while preserving valid navigation.
Listing mutations use portable sed output files, so both BSD/macOS and GNU/Linux
actually remove the hooks before their rendered negative controls run.
Render-gate and part-number controls retain their historical witnesses and also
require deliberately reversed physical Latin glyphs, mirrored parentheses and
a displaced part number to be detected independently of the engine version.
The recorder escape regression checks the canonical rejected path on both
Linux and macOS, preserving the same pass-two trust failure.

The 138-path tooling license scope and Generated Output Permission are retained;
no template or third-party license grant is added.

## v5.4.5

Standalone source package for English, Hebrew, and bilingual LuaLaTeX
documents. The public interfaces include a declarative recipe catalog,
document generator, genre-specific paragraph styles, composable TeX components,
source/PDF validators, reproducible build checks, and deterministic packaging.
Reference layouts own compact paragraph spacing and local heading alignment;
presentation themes control callout appearance independently of document genre.

`VERSION` identifies the source package. Python QA versions and external font
hashes are pinned in the package. Runtime and visual acceptance depend on the
environment and evidence described in the package documentation.
