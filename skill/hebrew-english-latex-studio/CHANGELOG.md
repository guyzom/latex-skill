# Hebrew English LaTeX Studio — release metadata

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
remains; data-report recipe revision 5 records the authoring guidance.
Frame/bare-table navigation and black caption links have real PDF
controls, including width/height failures and a displaced-anchor mutation.
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
