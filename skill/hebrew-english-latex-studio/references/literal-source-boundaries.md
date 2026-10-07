# Literal source boundaries — 4.23.0

The source-hazard gate now masks comments and literal regions in one lexical
pass, preserving character offsets and line breaks. It does not edit TeX, its
math, or the rendered PDF.

## Two measured failure classes

A literal code example containing `$sqrt$` used to trigger
`BARE-LATEX-COMMAND`, even though the letters and dollar signs were intentionally
printed as code. Conversely, a literal `%` was mistaken for a comment marker,
and a literal `$` changed the math scanner's delimiter pairing. In both cases
an actual bare `sqrt` later in the same source line could escape the check.
The exemption now ends with the literal, not with the paragraph or source file.

The following is a correct source example. Inline literal commands are in an
English paragraph, not inside an argument to `en` or in an RTL paragraph.

```latex
\begin{englishprose}
\verb|$sqrt$| is literal source, not a formula.
\par
\verb|%| is a printed character; the formula is $\sqrt{x}$.
\end{englishprose}
```

A deliberately incorrect case for regression tests, not an authoring example:

```latex-bad
\begin{englishprose}
\verb|%| $sqrt{x}$
\end{englishprose}
```

This is a missing command backslash. The mathematical correction is explicit:
`$\sqrt{x}$`. The gate must not silently repair or infer scientific intent.

## Supported lexical forms

The mask recognizes completed same-line `verb` / `verb*` literals, and
`lstinline` with a delimiter or a braced body and an optional key list. Literal
backslashes do not escape a delimiter. For ordinary source, a `{` delimiter of
`verb` closes with another `{`; the braced `lstinline` form ends at `}`.
The `*` in `lstinline*code*` is a delimiter, not a star modifier.

Existing `verbatim`, `verbatim*`, `Verbatim`, `Verbatim*`, `lstlisting` and
`lstlisting*` block exemptions are retained, as is the existing TikZ non-prose
policy. TikZ remains ordinary TeX rather than verbatim: a closing marker
inside a comment is ignored, normal whitespace in the real end is supported,
and the picture is masked as a complete unit. A controlled draft regression
with a multiline node and a following PGF `sqrt` expression is covered both
by real-engine compilation and by mutation of the actual terminator handler.
Whitespace or a real comment before the opening environment argument
is recognized; literal block closing markers retain their exact spelling.
Unclosed forms do not blanket-mask the rest of the file. Their validity still
belongs to the compiler, not to this bounded mask.

The actual source line/file is retained in diagnostics. The masking is confined
to the bare-command and Needspace analysis; other gates and all 651 standing
bidi cases are unchanged. Since 4.26.0 the same pass also feeds
`PGFPLOTS-CONTOUR-EXTERNAL`, in a view that masks comments and literals but not
TikZ bodies, where plots live: a contour key quoted in a listing or a comment is
data, one in a plot's options is a use. A safe literal does not waive the requirement for an
LTR context, font coverage, successful compilation or visual inspection.

## Limits

This is not macro expansion or complete TeX lexical semantics. Custom literal
aliases, short-inline definitions, category-code changes, listings escape modes,
macro-generated environments, and commands embedded in previously tokenized
arguments are not interpreted. The `alltt` environment is deliberately NOT
blanket-exempted: it may contain active commands and mathematics. Existing
TikZ/body and text-in-math exemptions are not broadened or proved universal.

## Reproduction

```bash
python3 scripts/test_v4230.py
python3 scripts/test_v4230_runtime.py
```

The first command includes counterexamples that disable the actual inline
handler and reproduce both missed live math and false code alarms. The second
builds real LuaLaTeX fixtures, checks printed literal data and malformed math,
and counts engine calls during managed builds. Corrected sources compile;
failing sources stop before the engine and retain a distinct previous PDF.
Set `HLLPDF_423_EVIDENCE_DIR` to a NEW external directory to retain evidence.
The retained deliberately wrong raw PDFs are controls, never approved output.

Primary syntax references (runtime versions remain those recorded locally):
- LaTeX kernel, verbatim and verb implementation: https://github.com/latex3/latex2e/blob/main/base/ltmiscen.dtx
- Listings package and documentation: https://ctan.org/pkg/listings

No font programs are distributed by these tests or by the release package.
