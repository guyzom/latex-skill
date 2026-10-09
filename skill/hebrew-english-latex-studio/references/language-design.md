# Language, design and package selection

The [canonical template catalog](template-catalog.md) composes independent
choices; it does not own or duplicate language resolution. All five language
profiles use the same core, including both explicit bilingual bases. A catalog
recipe records native starter variants and a closed composition strategy rather
than translating arbitrary content or inferring the dominant language. Read
[catalog development](catalog-development.md) for ownership and the
[Hebrew–English glossary](glossary-he-en.md) for public terminology.

This is the decision guide for general documents: letters, notes, briefs,
reports, study material, technical explanations, instructions and bilingual
handouts, academic papers and reference sheets. Choose the language, document structure and design separately.
Preserve the user's content and explicit design requirements. When they leave
choices open, select a coherent composition and proceed without an unnecessary
approval round.

## 1. Record the document brief

Keep a compact project note or manifest entry with purpose, audience, source
of truth, language profile, main language, document class/paper, theme or custom
design, optional features and extra dependencies. This is authoring metadata;
do not put implementation details in the reader's document.

For example: an English project brief with a short Hebrew quotation can use
`english-with-hebrew`, `article`, a restrained custom design and no exam API.
A Hebrew technical report with English terminology can use
`hebrew-with-english`, `report`, reader styling and only the components needed
by its content. A bilingual handout can use either main shell, with explicit
language blocks for both halves. Genre does not determine language or theme.

## 2. Choose one of five native profiles

| Profile | Main language | Use |
|---|---|---|
| `hebrew` | Hebrew | A document written in Hebrew |
| `english` | English | A document written in English |
| `hebrew-with-english` | Hebrew | Hebrew prose with English terms, excerpts or sections |
| `english-with-hebrew` | English | English prose with Hebrew terms, excerpts or sections |
| `bilingual` | Explicit choice | Both languages have substantial roles |

A profile is intent, not a numerical quota. Technical symbols, URLs and names
do not automatically make a document bilingual. Do not guess a profile solely
from the user's chat language. A Hebrew request for an English letter produces
an English document. If output language is clear from the requested content,
choose it; clarify only if the missing choice materially changes the result.

These definitions precede core input:

```latex
% English-led document with secondary Hebrew.
\def\lakitlanguageprofile{english-with-hebrew}
\def\lakitdocumentclass{article}
\input{preamble.tex}
\input{document_components.tex} % only if needed
\input{reader_theme.tex}        % one optional design choice
\begin{document}
\section{Project brief}
The Hebrew name is \h{שם לדוגמה}.
\begin{hebrewprose}
זוהי פסקה בעברית. מונח לועזי קצר: \en{project brief}.
\end{hebrewprose}
English resumes here in the document's main language.
\end{document}
```

Balanced bilingual documents must choose their shell explicitly:

```latex
\def\lakitlanguageprofile{bilingual}
\def\lakitmainlanguage{english} % or hebrew; author makes this choice
\input{preamble.tex}
```

The first four profiles derive `lakitmainlanguage`; an explicit conflicting
value is an error. `bilingual` without `lakitmainlanguage` is also an error.
Omitting all language hooks remains Hebrew for old sources. Both languages
are registered in every profile, so a single-language profile does not prohibit
a properly isolated name or quotation.

## 3. Distinguish main language from local language

| Scope | Interface | Effect |
|---|---|---|
| Whole document | `lakitlanguageprofile`, `lakitmainlanguage` | Main prose direction and localized shell conventions |
| Complete Hebrew paragraphs | `hebrewprose` environment | Local Hebrew language and paragraph direction |
| Complete English paragraphs | `englishprose` environment | Local English language and paragraph direction |
| Short Hebrew island | `\h{...}` | Explicit short Hebrew run in another context |
| Short English/Latin island | `\en{...}` | Explicit short LTR run in Hebrew or diagram text |
| Short code | `\code{...}` | Code semantics and LTR isolation |
| Inline shell/title text | `\doclang{...}` | Uses the selected main language; does not translate text |

Keep full paragraphs out of `\h`, `\en` and `\doclang`; use the prose
environments. Their scope ends cleanly before surrounding text resumes. Nest
inline opposite-language islands only where necessary. A heading belongs to
the language of its section, while document shell conventions follow the
chosen main language. For mixed titles, isolate only the parts requiring it
and supply a plain bookmark alternative where PDF-string conversion requires
one. Test TOC, running marks and bookmarks on the actual result.

The source checker also understands Babel's `\foreignlanguage[options]{language}{text}`,
`\foreignlanguage*{language}{paragraph}` and `otherlanguage*` with its optional
options argument. Only the nonstar `\foreignlanguage` form takes `[options]`.
Balanced nesting restores the surrounding language; comments, verbatim examples
and unexecuted macro definitions do not change it.

Literal local inputs inherit the language at their callsite, including nested
inputs and the import family. The root document still owns the profile and font
configuration. A file included once in English and once in Hebrew is checked in
both contexts. A direct, unscoped `\selectlanguage` in a child carries back to
the caller; balanced child groups and caller groups restore their own entry
language. Keep each language environment and brace/primitive group balanced
within one source file. A concrete dynamic input, input cycle or scope crossing
that the bounded analysis cannot determine raises `LANGUAGE-CONTEXT-UNRESOLVED`.
Arbitrary macro expansion and conditional execution still require the real
compiler and rendered proof; ordinary unknown macros are not language setters.
For `\lstinputlisting`, option metadata and the literal filename do not execute
language/input tokens during this analysis. Its `caption` and `title` text is
checked in its own nested language context. An executable input in that text
is unresolved under the literal-listing graph contract; do not silently treat
such a caption as a verified local dependency or a language exemption. The
checker does not evaluate arbitrary listings key definitions.

A complete native `thebibliography` entry uses the document component's
`\bibentryprose{english|hebrew}{entry}` immediately after `\bibitem`. It
selects the local paragraph direction and preserves the outer list's pending
label geometry; a prose environment after `\bibitem` alone can overlap that
label when its direction differs from the bibliography shell. See
[citations](citations.md). Keep an explicitly requested journal style intact.

The current core supports ordinary `enumerate`, `itemize` and `description`
lists inside either prose environment, including a minority-language section.
Babel's `layout=lists` adapts list indentation to the paragraph direction;
without it, a successful compilation could leave the list body flush with the
text edge and its numbers outside the text block. Nested lists are covered in
both directions. Keep language switches at paragraph boundaries, preserve
intentional custom list settings, and inspect any custom label widths or
indentation. Declare the mixed/bilingual profile for new mixed documents;
legacy fragments without that declaration retain conservative source warnings.

Mathematical expressions remain LTR logical expressions even in Hebrew prose.
Do not reverse an equation merely because the paragraph is RTL. Conversely,
Hebrew prose inside math is not magically LTR: use the established math/text
interfaces and follow [Direction and math](direction-and-math.md).

A balanced document may be sequential (one language then the other), alternate
sections, or pair short blocks. None implies automatic two-column typesetting.
Use a complete translated counterpart only when it serves the authorized task.
Mixed-language profiles need meaningful minority-language content, not a second
copy of the entire document. Starter translations demonstrate the available
compositions; remove unused bodies rather than reproducing them mechanically.
Choose the structure for readability. The explicit reference-sheet column
extension provides bounded flowing columns; selecting `bilingual` alone never
activates it. Its column progression follows the document's resolved main
language throughout, including the complete translated counterpart on later
pages. Hebrew headings and paragraphs remain RTL and English ones remain LTR;
a local language switch does not reverse the column progression. For example,
an English-main bilingual sheet reads its columns left to right in both full
bodies, while the Hebrew body retains Hebrew prose direction. A Hebrew-main
sheet retains right-to-left columns in both bodies. More complex paired or
paragraph-spanning layouts need their own fixture and visual inspection.

The bilingual `paper` starter uses paired front matter, then the full primary
body and, after an explicit page break, the full translated body, followed by
one primary-language bibliography. Standard bilingual reports, technical
documents, formula sheets and data reports likewise begin their full translated
body on a new page. Notes, general documents, letters and annotated notes
retain continuous paired-body flow; mixed-profile letters place the minority
request before the closing and signature.
The reference-sheet starter instead combines the authored primary/secondary
titles and places its translated body after an explicit page break. Keep each
language body in its own column run; do not make translations alternate
arbitrarily across narrow columns.

## 4. Design is a separate authoring choice

The author may choose a shipped theme, retain baseline styling, or create a
project-local theme when the user leaves the design open. Select a limited
palette, a coherent type hierarchy, appropriate spacing and consistent tables.
Keep source fidelity, readability and navigation above ornamental density.
Sparse pages are acceptable when they serve the document; do not fill them
artificially or reduce type automatically.

Paragraph style is a genre/layout decision shared by both prose languages.
Declare `\lakitparagraphstyle` before the core as `block` or `indented`.
`block` uses zero first-line indent and a modest paragraph gap for standard
body prose; `indented`, the compatibility default, retains the class's ordinary
paragraph dimensions and heading behavior. New non-paper starters choose
`block`, while paper starters choose `indented`. A Hebrew paragraph follows
the same declared policy as an English paragraph; its reading edge changes
with its local language. Reference columns and wide bands independently own
their tight local paragraph spacing. A theme does not choose a new paragraph
genre merely because it changes headings or callout colors. See
[paragraphs and emphasis](content-style.md#paragraph-style-and-purposeful-emphasis).

Within `referencecolumns` and `referencewide`, headings align at their local
language's reading edge with a ragged opposite edge and no automatic word
hyphenation. The layout owns this local policy across themes; body paragraphs,
outer headings and main-language column progression retain their own behavior.
See [reference sheets](reference-sheets.md) for wrapping and scope boundaries.

Use layout hooks before core for class, paper, margins, spacing and hierarchy
depths. Load semantic extensions, then any local-flow layout extension and
page-shell extension, then a theme after core for presentation. Keep semantic
features in separate extensions. Suggested local composition:

```latex
\def\lakitlanguageprofile{english}
\def\lakitdocumentclass{article}
\def\lakitclassoptions{11pt,a4paper}
\def\lakitgeometryoptions{margin=2.1cm,headheight=14pt}
\def\lakitlinespread{1.12}
\input{preamble.tex}
\input{document_components.tex}
\input{project_theme.tex} % locally authored and reviewed
```

`project_theme.tex` is an illustrative project filename, not a shipped asset.
Do not load a custom replacement alongside two competing shipped themes.
If layering a small override on one shipped theme, make that relationship
explicit and preserve its semantic content. `clean_theme.tex` has intentional
exam-oriented numbering policies; do not select it unknowingly for a general
report that needs visible numbering. `reader_theme.tex` preserves visible
section numbering and ordinary equation numbering. `academic_theme.tex`
preserves visible heading numbers with classical serif black styling,
continuous figure/table numbers and selective equations. It is available for
all language profiles; neither presentation determines the language or page
layout. Read [academic articles](academic-articles.md) for title, abstract,
equation and citation policy.
`reference_theme.tex` supplies black ruled serif headings, restrained gray
blocks, continuous captions and selective equations. It is independent of
`reference_columns.tex` and does not select a body size or activate columns.
The `reference-readable` and `reference-compact` generator layouts currently
apply only to formula sheets, preserve one shared core and support all five
language profiles. See [reference sheets](reference-sheets.md).

Use two columns at 9/11 pt for ordinary reference use; choose three at
6.3/7.8 pt for an actual space constraint. Both presets have a 5 mm gap and
explicit local body typography under an article 10 pt shell. Review at printed
size as well as zoomed resolution. The compact size is an explicit authored
preset informed by the supplied sheets; no font shrinking or page-count
optimization runs behind the author's back. Reference starters use only topic
and subtopic numbering, mostly unboxed math and short-entry boundaries.
Compact main/script/scriptscript mathematics is explicitly
6.25/4.375/3.125 pt; readable mathematics is 8.75/6.125/4.375 pt. The layout
uniformly scales Computer Modern 10/7/5 pt optical designs for primary
mathematics and its ordinary script tiers, preserving the glyph proportions.
Separate authored body and mathematical-size hooks precede layout input.
The reference normal/bold math variants are local to `referencecolumns` and
`referencewide`; outer mathematics and the shared core retain their
configuration, while explicit custom math-version requests pass through.
The same mathematical policy serves every
language profile. The reference theme supplies presentation independently of
these font choices. See [reference typography](reference-sheets.md) and
[runtime fonts](runtime-fonts.md#reference-mathematics); local font selection
does not authorize silent substitution or weaker font/glyph checks.

An accent following the reading edge belongs on the physical right in RTL and
the physical left in LTR. Reference note and caution rules follow the local
prose language, including inside a sheet with the opposite main language.
An English note in a Hebrew-led sheet therefore has a left rule; a Hebrew note
in an English-led sheet has a right rule. The main page language still sets
column order. Component option names are not proof of physical placement under
Babel. Inspect actual rendered geometry in native and minority-language blocks.
The alternative `topicrail` shell similarly takes its default rail order and
label language from the stable main language. Its direction overrides change
order, while local prose switches do not change running-label language.
Changing the main language must not
force a new content genre, replace prose, or silently rename semantic boxes.

The rendered destination checker recognizes canonical Hebrew `איור`/`טבלה`
and English `Figure`/`Table` caption labels by the complete label, declared
weight and exact declared color. Its defaults are `000000` and `normal`, matching
the complete core caption paragraph. All shipped themes use the same defaults;
generated academic/reference wrappers retain explicit unset-only declarations.
When a custom theme changes the label style, declare the matching settings in
the build environment. For example, a theme using `\renewcommand{\lakitcaptionstyle}{\normalfont\small\color{cGray}}`
with `\definecolor{cGray}{HTML}{536570}` must build with:

```bash
PDF_CAPTION_COLOR=536570 bash scripts/build.sh document.tex
python3 scripts/check_pdf_render.py --caption-color 536570 document.pdf document.tex
```

These settings describe the existing label appearance; they do not restyle
the PDF. Color requires exactly `RRGGBB` without a leading hash, and
`PDF_CAPTION_LABEL_WEIGHT` accepts `bold` or `normal`. Invalid values fail
before compilation. Preserve the complete recognizable label when using this
detector. The declared `normal` contract requires a leading native label,
number and colon, with one matching caption for each named figure/table target;
missing or duplicate matching captions are hard failures. The legacy `bold`
contract retains its caption-not-found advisory: the destination was not
measured, not established correct. Several different caption colors/weights
or unconventional labels need a separate explicit inspection method. Custom
table-frame color/width can also fall outside the baseline frame locator; the
caption-to-destination distance remains checked, but visual object/frame review
is still required. Do not silently describe these cases as complete coverage.

Page-number position is a separate declaration: see
[Printed page numbers](pdf-folios.md) for header/footer, side, unnumbered and
custom contracts. Custom geometry does not require changing document language.

## 5. Packages and fonts are extensible, with explicit limits

The shipped stack is a tested baseline, not an exhaustive package allowlist.
An author may choose compatible installed LuaLaTeX packages for a real content
need, inspect their official documentation when needed, and add project-local
configuration. Record the package names, relevant options, load order and any
additional runtime tools or local resources needed to rebuild.

Before adding a package, inspect the preamble to avoid duplicate loading and
option clashes. Pass options before core input when a package is already loaded
and supports that mechanism; put compatible new packages after core when their
load-order contract allows it. Do not load an alternative bidi/language engine
over Babel, replace math ownership casually, or redefine protected caption/
anchor APIs to force a build through. These require an explicit core
integration and regression work, not a cosmetic theme override.

The current `build.sh` runs LuaLaTeX and its documented checks. It does not
promise an orchestration stage for arbitrary external tools. Packages that
require Biber, external code execution, SVG conversion or shell escape need
resources generated beforehand or an explicitly implemented and tested build
integration. `-no-shell-escape` is retained. Never imply such a package works
end-to-end merely because its `.sty` file exists.

Typography can use language-specific `\babelfont[english]{rm}` or
`\babelfont[hebrew]{rm}` overrides after core when needed. Verify real files,
weights, italics, script coverage and embedding; record their provenance and
licenses. Do not change `assets/fonts/SHA256SUMS` to bless arbitrary local font
substitutions. The runtime inventory verifies pinned canonical resources and
lists additional resources as uncontrolled; it does not certify a custom font.
The source charset policy remains a separate supported-character boundary.
A new font alone does not authorize unsupported characters or bypass a checker.

For every new package/design combination, create the smallest representative
fixture that exercises the feature in the chosen language, then build and
inspect it. Cross-language components need both directions. Once the concrete
risk is resolved, proceed with the document; do not construct an unnecessary
unbounded package compatibility suite.

## 6. Verify what the reader sees

Build success establishes only the implemented hard gates. Inspect all pages
of the current PDF at readable scale, including mixed punctuation, links,
headings, lists, table cells, callout sides, page boundaries and reference
labels. A language change can expose shell bugs absent from body prose; cover
captions, contents, references, running marks and proof labels when used.

Record the renderer and version. Poppler and MuPDF can differ; a mismatch is a
finding to investigate, not evidence that either is always correct. Check the
target viewer when practical and never call a page reviewed without actually
opening it. Rebuild after repairs, rerender changed output and invalidate stale
review evidence. Deliver editable source and the actual dependencies selected
for the project, alongside the final PDF and a concise statement of material
remaining limits.

## Migration from version 4

Old Hebrew sources keep working without new hooks. For a native English
conversion, set `english` or `english-with-hebrew` before core and replace a
whole-document English wrapper with ordinary main-language prose. Review titles,
metadata, captions and authored labels; profile selection does not translate
them. Convert long opposite-language quotations to the matching prose
environment. Keep language and design choices in the project manifest and
preserve the original source when making a substantial conversion.
