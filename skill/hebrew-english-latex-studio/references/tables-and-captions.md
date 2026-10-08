# Tables, captions and terminology

Choose the structure and width from the actual content, then inspect the PDF.
A width is a budget, not a target that every table must fill.

| Content | Starting point | Width decision |
|---|---|---|
| Short numbers, symbols, lookup values | Centered `tabular`, `l/r/c`, `booktabs` | Natural content width |
| Short table with prose | Natural key/value columns plus authored `p/m` text columns | Enough space to wrap comfortably, within local `\linewidth` |
| Many rows crossing a page | `flowtable` in outer single-column text | Natural columns or balanced H/E/N prose widths |
| Genuinely wide comparative data | Wrapped columns at the available local width | Deduct all padding; give prose more room than IDs |
| Explicitly requested framed panel | `tablebox` | Keep padding and the caption inside; short enough to be atomic |

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

## One caption paragraph

The core defaults to regular black text at one local small size, with a colon:
`Figure 1: Description`, `Table 1: Description`, `איור 1: תיאור`,
`טבלה 1: תיאור`. Number format still follows `within-major` or the existing
explicit `continuous` policy. The complete caption uses `\lakitcaptionstyle`;
`\lakitcaptionlabelstyle` is retained as an identity compatibility hook.
Choose a deliberate whole-paragraph override for a requested template rather
than styling its label independently. Preserve math fonts and appropriate
Hebrew/Latin faces within the same family/size policy.

Custom `\figcap` / `\tabcap` retain their counters, raised object destinations,
`nameref` metadata and optional short list entries. Put `\label` inside their
caption argument. Native `\caption` / `\captionof` use the caption package's
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
