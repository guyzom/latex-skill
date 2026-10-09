# Optional multilingual index

Use an index for locating explanations or exercises in a substantial document.
The table of contents remains the map of chapters and sections. An index entry
must point to the page that actually discusses its term; a valid PDF destination
alone does not prove this relationship.

Copy `index_components.tex` and `index.ist` next to the core assets, then load the
component after `preamble.tex`. This optional path supports the reviewed default
single-jobname `imakeidx` 2016/10/15 v1.3e route with Arabic page numbering. It
preserves the core's directional folios. Roman, alphabetic, custom formats,
`splitindex`, automatic shell execution and other processors require a separate
validated workflow; this component rejects the unsupported contracts.

```tex
\def\lakitindexcolumns{1} % Before the component; choose 1 or 2 from the content.
\input{preamble.tex}
\input{index_components.tex}
\begin{document}
\begin{otherlanguage}{english}
A locally English explanation.
\lakitindex{english}{010000}{API}
\end{otherlanguage}
הסבר בעברית.
\lakitindex{hebrew}{010000}{אינדקס}
\clearpage
\printindex
\end{document}
```

Build explicitly with the managed processor and its project-local style:

```bash
INDEX_PROCESSOR=makeindex INDEX_STYLE=index.ist bash scripts/build.sh main.tex
```

The default build has `INDEX_PROCESSOR=none`. Selecting the component in the
project generator supplies unset-only managed defaults; an explicit conflicting
setting must fail rather than silently omit the index. The processor never
requires shell escape and takes no arbitrary command or processor flags.

## Ordering and typography

Each entry declares `english` or `hebrew`, a **six-digit ASCII rank**, and its
independent display text. A rank must identify one exact display within its
language; repeated mentions and range endpoints reuse that pair. Equal-width ranks determine order within the E/H
language groups. Assign ranks from the intended alphabetic or subject ordering;
changing the display must not silently change collation. `makeindex` is not a
Hebrew Unicode collator on this path. No automatic Hebrew collation or final-form
normalization is claimed. If alphabetical Hebrew order is requested, review the
ranks against א–ת, treating ך/ם/ן/ף/ץ as their ordinary counterparts כ/מ/נ/פ/צ;
choose and document the policy for punctuation, niqqud and English-leading terms.
For a large index, use a separately tested Unicode collation workflow rather
than inventing ranks or relying on UTF-8 byte order.

English entries and their group heading align to the physical left edge of their
column; Hebrew entries and their heading align to the physical right edge.
Paragraph direction follows the declared entry language, independently of the
document base. Put minority-language fragments in `\h{...}` or `\en{...}` and
mathematics in an appropriate LTR island. Every locator sequence, including
commas and page ranges, is one LTR island. The normal body face, size and black
color are retained; command names do not automatically become bold or monospaced.
An explicitly requested term style can be authored in the display text.

One column is the default for a short index or long explanations. Set
`\def\lakitindexcolumns{2}` before loading the component when entry count and
line lengths support two readable columns. Text wraps with a hanging continuation;
there is no font shrinking, scaling, forced full-line stretch or mandatory width
percentage. Language group headings provide orientation without manufacturing a
heading for every letter in a small index.

Display text is serialized as literal TeX, so fragile `\en`/`\h` commands are not
expanded into index syntax. Makeindex syntax characters `@`, `!`, `|` and `"` have
special meanings: the component rejects literal occurrences in display arguments. A TeX display
command such as `\symbol{64}` can represent an at-sign without index syntax;
verify any such display in the rendered output. Prefer `\mid` to a bare
math `|`. Do not hide a malformed index behind a successful compiler exit.

## Ranges and verification

Use identical language, rank and display at both ends of a range:

```tex
\lakitindexrangebegin{hebrew}{010000}{אינדקס}
% Actual continuing explanation, possibly across pages.
\lakitindexrangeend{hebrew}{010000}{אינדקס}
```

The optional writer expands its separate raw locator at shipout. An indexed
float can therefore move from its authoring page to another page without keeping
an early page number. `\thepage`, native page links, index bookmarks and the
existing table of contents retain their roles.

Require zero rejected entries, an accepted count matching the generated input,
a nonempty freshly produced `.ind`, and evidence that TeX actually read that
exact managed output. An unchanged `.idx` hash alone does not prove the PDF read
its latest `.ind`; the PDF and auxiliary state must converge after processing.
Generated `.ind` TeX is trusted only through its exact managed provenance, then
subject to source checks; do not allow arbitrary `.ind` files as project source.

Render and inspect the affected index pages. Check local paragraph edges, long
wrapped terms, minority fragments, complete locator order, unchanged body font,
column boundaries and group headings. Decode PDF PageLabels and compare them
with printed folios; then resolve sampled locator links against the **actual term
explanation**, including a delayed float. An independent valid-but-wrong-page
control should fail the semantic check even when general navigation checks pass.
The synthetic `example_index.tex` demonstrates this optional style. Existing
documents require their own source migration and actual page review.

## Retain private processor evidence

For a private diagnostic review, set `HLLPDF_INDEX_EVIDENCE_DIR` to a new,
absolute directory before the managed build. The exporter validates and
atomically publishes one complete set of `.idx`, `.ind`, `.ilg`, recorder and
auxiliary files with hashes tied to the verified PDF. Existing destinations
are refused; choose a new directory for each build. Normal builds still publish
the PDF alone. If this optional export fails, the build reports that the verified
PDF was published but the requested evidence was not retained. Processor
evidence does not replace rendered page or semantic locator review.
