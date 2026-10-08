# Tables, captions and terminology

Choose the structure and width from the actual content, then inspect the PDF.
A width is a budget, not a target that every table must fill.
There is no required number of columns. Choose the number, widths, alignment,
headers, row hierarchy and order from the data and the reader's task. Two-,
four- and five-column examples below are demonstrations, not mandatory schemas.
A transposed table, several smaller tables, a list or prose may fit better.

| Content | Starting point | Width decision |
|---|---|---|
| Short numbers, symbols, lookup values | Centered `tabular`, `l/r/c`, `booktabs` | Natural content width |
| Short table with prose | Natural key/value columns plus authored `p/m` text columns | Enough space to wrap comfortably, within local `\linewidth` |
| Many rows crossing a page | `flowtable` in outer single-column text | Natural columns or balanced H/E/N prose widths |
| Genuinely wide comparative data | Wrapped columns at the available local width | Deduct all padding; give prose more room than IDs |
| Optional content-fit outer frame | `framedtable` from `document_components.tex` | Measure rows and caption, preserve active table-box padding; one complete page only |
| Optional semantic-width outer box | `semanticframedtable` from `document_components.tex` | Match the active semantic boxes' actual outer width and inset conventions; inner columns remain content-appropriate |
| Explicitly requested full-width framed panel | Existing `tablebox` | Keep padding and the caption inside; short enough to be atomic |

Do not use `tabular*`/`extracolsep{\fill}` or full-width `tabularx` as a blanket
short-table policy. They remain valid when a specified design needs them; they
are not loaded or rewritten by this toolkit. Do not scale a table, reduce its
font, or impose one arbitrary percentage on every table. Split content or choose
a suitable layout when wrapping and column balance cannot resolve overflow.
Booktabs rules with ordinary cell padding are the neutral default; retain grid
rules when reproducing an explicitly requested source template.

## Short table

```latex
\begin{center}
\begin{tabular}{rrl}
\toprule
ID & Value & State\\
\midrule
001 & -12.50 & Valid\\
002 & 0.00 & Observed\\
\bottomrule
\end{tabular}
\tabcap[Example records]{\label{tab:records}Example records.}
\end{center}
```

Use this English example in an English context. In Hebrew, isolate Latin values
and verify the physical key column at the right edge. Ordinary tabular and
longtable can have different direction behavior across contexts/backends; do
not infer column order from the prose language alone. A short table's natural
rule width need not equal the paragraph or caption width. A frame is optional.
`flowtable` deducts all outer/intercolumn padding from `\flowtablewidth`; its
natural-width specifications are centered. Do not put it inside a frame/float.

## Two optional frame modes

Load `document_components.tex` after `preamble.tex`. Both modes reuse the existing
box mechanism without changing the unframed default or the `tablebox` panel API.
`framedtable` follows the widest actual line of rows or caption up to the safe
local width. `semanticframedtable` follows the semantic boxes' actual width and
insets in the same document. That wide outer box does not stretch natural columns
or add fill glue between short values.

```latex
\begin{framedtable}[Compact records]{2}{rr}{Compact records.}{tab:framed}
\toprule
ID & Value\\
\midrule
001 & -12.50\\
002 & 0.00\\
\bottomrule
\end{framedtable}
```

For a comparison requiring five fields, a different natural structure is valid:

```latex
\begin{semanticframedtable}[Five selected fields]{5}{rrrrl}
  {Five selected fields.}{tab:semantic}
\toprule
ID & Count & Mean & Model & State\\
\midrule
001 & 12 & 1.25 & $x^2$ & Observed\\
002 & 8 & -0.50 & $x^3$ & Checked\\
\bottomrule
\end{semanticframedtable}
```

Both interfaces take optional short list text, the chosen positive column count, column specification,
caption and label. Do not add a second `tabcap` or `label`. Captions are captured
once, retain the normal counter/list/reference behavior and share one black
regular font style. The count describes the author's actual structure; it has
no prescribed value and must agree with the physical columns in the specification.
The content-fit mode inherits the active table box's geometry. The semantic-width
mode resolves the same mdframed width equation and shared style as real semantic
boxes, including external margins, inner padding and active border sides.
Caption text is captured once and remains breakable in the final paragraph.

Core callouts share `hllpdfsemanticgeometry`; reader, reference and academic
themes select their existing semantic styles. Changes to the active shared style
therefore affect both the semantic boxes and semantic-width tables. Per-box custom
options are not inferred from some earlier box: put a document-wide geometry
choice in the shared style when both objects must match. In the clean theme the
framed semantic reference is `defbox`/`thmbox`/`warnbox`, not the plain note text.
The reader's side-bar convention and academic frameless convention are preserved;
request a deliberate theme override when an outlined design is explicitly needed.

For prose, replace `rr` with, for example,
`r>{\raggedright\arraybackslash}p{\framedtablewidth-2cm}` in an English context.
The same `\framedtablewidth` budget works in either mode. It deducts the actual
border, external margins, inner frame padding and all standard cell padding;
the count must match the columns. Choose a key-column allowance from its actual
content. For Hebrew-primary content, declare table order explicitly and use
right-aligned wrapped Hebrew cell islands. `framedtable` gives columns explicit
English order, with the first declared column physically leftmost; place the
Hebrew key last. Gallery patterns 13–15 show compact two-field data, five-field
comparisons and four-field wrapped prose/numeric/math content in RTL and LTR.
Adapt those counts, widths, headers and orders freely; do not copy a schema merely
because it is illustrated. Preserve font size and inspect both caption and rows.

Both environments capture an atomic table and reject widths beyond the safe
budget or total height beyond one page. It may move as a whole to the next page.
It does not promise framed multipage tables: split the content or use `flowtable`
outside a frame. Explicit `@{}`/vertical-rule column specifications change cell
padding; budget those deliberately rather than assuming the standard count.

## One caption paragraph

The core defaults to regular black text at one local small size, with a colon:
`Figure 1: Description`, `Table 1: Description`, `איור 1: תיאור`,
`טבלה 1: תיאור`. Number format still follows `within-major` or the existing
explicit `continuous` policy. The complete caption uses `\lakitcaptionstyle`;
`\lakitcaptionlabelstyle` is retained as an identity compatibility hook.
Caption hyperlinks keep their actions while inheriting the paragraph color;
the local default also sets hyperlink colors to black.
Choose a deliberate whole-paragraph override for a requested template rather
than styling its label independently. Preserve math fonts and appropriate
Hebrew/Latin faces within the same family/size policy.

Custom `\figcap` / `\tabcap` retain their counters, raised object destinations,
`nameref` metadata and optional short list entries. Put `\label` inside their
caption argument. Frameless tables target the measured table top; the historical
frame cushion applies only within `tablebox`. Check that a reference lands at its
own table rather than above the preceding heading. Native `\caption` / `\captionof` use the caption package's
own counters and anchors; optional subcaption inherits the paragraph font.
Do not manually synchronize counters or duplicate labels/list entries.
`flowtable` shares the custom table counter but retains its native top anchor.

Long captions wrap normally. Avoid manual line breaks, label-only colors,
incidental `\textbf`/`\sffamily` or a second size in the description. Explicit
mathematical notation, links and user-requested emphasis remain semantic choices.
Check `ref`, `autoref`, `nameref`, lists and PDF destinations after any override.
Set `PDF_CAPTION_COLOR` and `PDF_CAPTION_LABEL_WEIGHT` to the actual custom style.
The checker defaults are `000000` and `normal`. The historical gray/bold/period
style is only supported as an explicitly declared compatibility override.

## Terminology paragraphs

```latex
\input{document_components.tex}
```

After the document begins, in an English context:

```latex
\glossaryentry{Compiler}{Translates source code into another representation.}
\glossaryentry{\h{מהדר}}{The Hebrew term for a compiler.}
```

Use `\en{Compiler}` in a Hebrew glossary. The helper joins the term and definition
with a spaced em dash; it inserts no dot after the term. Author sentence
punctuation in the definition. Native `description` lists remain available and
are not globally restyled. Distinguish sentence punctuation, decimal points,
numbering and URL dots from relation separators; never replace periods globally.

## Review scope and older material

The retained TeX galleries are current sources, rebuilt by the regression
harness. No rendered gallery/PDF is shipped in the source package. New generated
projects copy the current preamble and starters; existing user projects need an
explicit reviewed refresh of their local assets. Old screenshots, archived PDFs
and former releases are historical evidence, not current style references.
The external computer-engineering glossary screenshot has no editable source in
this repository; the terminology helper fixes the authoring policy without
claiming to have regenerated that other document.

Render and view affected pages at readable resolution: short/wide/continuing
tables, Hebrew/English/mixed captions, long wrapped text, terminology paragraphs,
math and minority-language terms. Check cell padding, column order, clipping,
line collisions, full paragraph typography, numbering and navigation. Compilation
and glyph tests do not constitute visual review or PDF/UA certification.
