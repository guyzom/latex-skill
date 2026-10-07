# Nested container scope

## Author-facing contract

A `codebox` is a numbered-code container even when placed inside `defbox`,
`thmbox`, `notebox`, `exbox`, `warnbox`, or `keybox`. A listing directly inside
one of those semantic containers retains that container's policy, including
its theme overrides. A semantic child of a codebox owns its own listing
presentation; code later in the outer codebox regains the outer presentation.
The nearest relevant container wins without changing siblings or following
unboxed code.

`codebox` and `tablebox` default to four frame edges, independently of an
outer reader-theme callout's single leading edge. Explicit per-instance frame
options still win. This is not a request to surround every paragraph with a
box, change the color palette, or add titles where they convey no information.

```latex
\begin{exbox}[frametitle={בדיקת קלט}]
המסגרת הפנימית מציגה קוד ממוספר בתוך דוגמה.
\begin{codebox}[frametitle={\code{parser.py}}]
\begin{asmblock}
\begin{lstlisting}[style=pystyle,firstnumber=998]
alpha = 10
beta = 20
result = alpha + beta
\end{lstlisting}
\end{asmblock}
\end{codebox}
\end{exbox}
```

Explicit `numbers=none` remains unnumbered. A user-defined `\thelstnumber`, such
as a Q-prefixed Arabic counter, survives semantic nesting and remains in effect
after the enclosing callout. This repair does not renumber lines or alter code
content. An explicitly empty user formatter remains empty; it is not replaced
with an invented default.

## Local implementation

Semantic callouts save the current number formatter only at the first masking
boundary in their local chain. A nested codebox restores that saved formatter
and suspends the mask locally. The state is ordinary TeX group-local state;
no global redefinition is needed to undo a child.

The once-registered `listings` `PreInit` hook reads local codebox/language flags.
Margin, frame and background overrides apply inside the listing group, after
style selection. The six semantic callouts locally clear the codebox flag, so
a parent's code presentation cannot leak into a child callout's listing. On
exit TeX restores the parent state. State declarations are separate from the
older v4.28 mutation block so that its independent regression remains runnable.

Explicit four-edge defaults on the two neutral containers prevent inherited
mdframed options from removing sides. The implementation leaves local optional
arguments in control. In Hebrew, the backend's `leftline` can correspond to a
physical right edge; geometry tests measure physical sides rather than assuming
that an option name has an invariant screen direction.

## Regressions and negative controls

```bash
python scripts/test_v4290_runtime.py
python scripts/test_v4280_runtime.py
FAST=1 bash scripts/test_all.sh
bash scripts/test_all.sh
```

The v4.29 suite contains ten unittest methods. It requires the actual LuaLaTeX
engine, pinned fonts, Poppler, and the pinned Python QA environment. It is wired
into the full harness, not FAST. To retain compiled sources, logs, PDFs and
renderer replay manifests outside the skill:

```bash
HLLPDF_429_EVIDENCE_DIR=/tmp/nested-review-new python scripts/test_v4290_runtime.py
```

The destination must not already exist and must be outside the skill tree. No
font programs are copied. Temporary evidence is otherwise cleaned automatically.

The core, reader and clean themes each exercise six callouts in Hebrew and
English, with all four bundled listing styles. Each of the resulting 144
codeboxes must contain all three labels, 998, 999 and 1000, and its own four
border edges. Measurements are tied to the matching filled rectangle, not a
nearby unrelated stroke; color comparison distinguishes the very similar
reader slate and purple fills.

Four independently compiled mutations remove the formatter restoration, remove
code-frame edge defaults, remove table-frame edge defaults, and keep the outer
codebox flag active inside a semantic child. Each corresponding defect must
reappear. A checker that accepts only the fixed case is insufficient.

Additional sources exercise double nesting, custom formatter scope, explicit
number suppression, explicit two-edge frames, distinct nested/standalone table
links, and a two-page split with every label from 998 through 1027 exactly once.
The three-page stress source and two-page split source are replayed by explicit
Poppler and MuPDF backends. These are machine checks, not visual attestations.

## What still needs per-document review

This finite matrix does not prove arbitrary deep nesting, very narrow columns,
all custom listing styles, five-or-more-digit gutters, long lines, or every
interaction between nested and multi-page containers. The split control is a
standalone codebox crossing one page boundary; it is not proof that deeply
nested oversized boxes split correctly. `nobreak=true` is used only on short
bounded matrix fixtures, not as a blanket recommendation for real documents.

Inspect every output page in the actual target document. Record renderer,
version, resolution, exact PDF hash, page range, and any disagreement. A sparse
page is not itself a failure, and differences between rasterizers are not proof
that the underlying PDF is defective. Preview, iOS, Goodnotes, screen-reader
reading order, tagged-PDF accessibility, and PDF/UA require separate validation.
