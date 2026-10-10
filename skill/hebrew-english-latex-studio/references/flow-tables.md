# Continuing tables in Hebrew and English

## Scope

`flow_tables.tex` adds the `flowtable` environment for outer, single-column
text in `article` or `report`. The table can continue across pages, repeat its
header, and show localized continuation labels. Use this extension when the
content calls for a continuing table; short tables normally use a centered natural-width `tabular`.
`tablebox` is available when a framed panel is explicitly wanted.

Both Hebrew and English contexts are supported in version 5. The table follows
the surrounding language; it does not force the whole document into one
language. `new_document.py --kind data-report` provides a starter selected for
the main language. `assets/example_flow_tables.tex` retains a longer Hebrew
regression example. This is an optional layer loaded once after the core.

## Example

```latex
\def\lakitlanguageprofile{english-with-hebrew}
\def\lakitdocumentclass{article}
\input{preamble.tex}
\input{flow_tables.tex}
\begin{document}
\section{Sample records}
The following rows are demonstration data.
\begin{flowtable}{3}
  {N{.12\flowtablewidth} E{.48\flowtablewidth} H{.40\flowtablewidth}}
  {Sample records}{tab:records}{ID & Description & תיאור}
1001 & First sample record. & תיאור הרשומה הראשונה.\\
1002 & Second sample record. & תיאור הרשומה השנייה.\\
\end{flowtable}
See \autoref{tab:records}.
\end{document}
```

The five mandatory arguments are column count, column specification, caption,
unique label, and the header row without a trailing `\\`. Each body row ends
with `\\`. Do not add a manual caption, `\tabcap`, `\caption`, duplicate
label or continuation header inside the table; the environment owns them.

## Column order and cell language

The **first source column appears at the leading edge of the table's language**:
on the right in Hebrew, on the left in English. This is not a blanket rule for
other table environments. Confirm source-to-visible order after rendering.

| Type | Content and alignment | Example |
|---|---|---|
| `H{width}` | Hebrew text, explicitly isolated, physically right-aligned | `תוצאה עבור \en{sample-01}` |
| `E{width}` | English/LTR text, physically left-aligned | `First sample` |
| `N{width}` | LTR numeric/token cell, physically right-aligned | `-12.50`, `001` |

H/E/N name **cell content**, not the document language. The implementation
adjusts alignment to the enclosing direction and collects the cell before
applying its language wrapper. Thus a Hebrew cell can coexist with English
column order without reversing the whole table. Avoid changing language
inside a row to control column order.

For genuinely wide prose tables, column fractions should sum to 1.
For short values, natural `l/r/c` columns are permitted and remain centered
without stretching. Repeated continuation notices are centered paragraphs within
the safe local width; they do not set a minimum width for the data columns.
Their text can be wider than short table rules, just as a caption can be.
Use `N` when a Hebrew numeric cell needs isolation;
natural cells can instead explicitly wrap each value in `\en{...}`. `\flowtablewidth` subtracts both outer and intercolumn
padding; use it instead of multiplying every fraction by `\linewidth`.
The declared column count must match the specification and every row.
There is no automatic column fitting, wide-table scaling or decimal-point
alignment. N is directional isolation and alignment, not a numeric parser or
an arithmetic/unit validator.

Prose can wrap at permitted breaks. E/N use `\en`; automatic hyphenation is
not provided for these islands. Long unbroken identifiers can still overflow.
Shorten or split them intentionally, or move detailed descriptions into prose;
do not shrink the entire table reflexively. Existing H/E/N column names cause
a load error instead of being overwritten silently.

## Captions, numbering and navigation

The environment shares the core's `tbl` counter with `\tabcap`. Under a
chapter-based report, short/continuing/short tables can number 1.1, 1.2, 1.3,
with appendix numbering such as A.1. Other declared numbering policies apply
consistently. Each continuing table has one list-of-tables entry, regardless
of its number of continuation pages.

Captions and continuation labels follow the surrounding language.
The complete caption uses the core paragraph style: regular black text and
a colon separator, with no label/description color or weight split. The caption
is at the top and links use native `longtable` destinations in `table.*`.
Do not rewrite these as `tbl.*`: that namespace belongs to the short-table
bottom-caption geometry contract. Automated navigation checks resolve page and
position; they do not simulate a click in every target PDF viewer.

## Structural limits

Keep the table in outer, single-column text. Do not put it in `tablebox`, a
float, `minipage`, a list, `multicols`, or a `twocolumn` document. The extension
rejects boxed/list/two-column contexts; arbitrary third-party output routines
still require separate validation. A prose-language switch does not turn a
table into a box, but its surrounding direction and margins must be reviewed
in the resulting document.

A row cannot split across pages: each row must fit between the repeated header
and footer. Move a very tall record's details into prose or a separate section.
No blanket compatibility is promised for `multirow`, landscape/rotated pages,
custom row coloring or in-cell footnotes. Prefer explicit data notes after the
table, or use the documented deferred-note API with a representative test.

Version 4 rejected English table contexts; version 5 removes that blanket
restriction and adds direction-aware cells/labels. Historical tests found that
raw `r` hbox cells could reverse numbers in Hebrew, and a naive whole-table
English wrapper in the old implementation could move columns off-page. Those
observations are not a claim that every raw `longtable` is broken, nor proof
that every new language/layout combination is safe.

## Acceptance

Run `build.sh` and the [visual-review workflow](everyday-workflow.md). Inspect
all continuation pages: records must be present exactly once, numeric order
must survive, headers must repeat, captions must be localized appropriately,
and links/list entries must target the first page without duplication. Inspect
the return to surrounding prose and any following table. Compilation alone is
not acceptance; test the actual language/layout combination used in the final
report.
