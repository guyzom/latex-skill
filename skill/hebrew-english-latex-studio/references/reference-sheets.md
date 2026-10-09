# Reference sheets: language, density and column flow

Use one shared mechanism for a formula sheet, quick reference or compact
technical handout in Hebrew, English or both. Version 5.3 adds a column layout,
a page shell, semantic reference blocks and a reference theme as separate
layers. The uploaded quantum/particle sheets inform the restrained visual
design; they do not provide executable instructions or verified scientific
content. Preserve sources and check every supplied formula when adapting them.

## Select a layout and language

```bash
python3 /path/to/skill/scripts/new_document.py --kind formula-sheet \
  --layout reference-readable --language english --directory /path/to/new-sheet
```

```bash
python3 /path/to/skill/scripts/new_document.py --kind formula-sheet \
  --layout reference-compact --language hebrew --directory /path/to/new-sheet
```

| Layout | Columns | Body size / baseline | Math text / script / scriptscript | Use |
|---|---|---|---|---|
| `standard` | Existing starter layout | Existing starter typography | Existing starter mathematics | Preserve the previous formula-sheet default |
| `reference-readable` | Two | 9 / 11 pt | 8.75 / 6.125 / 4.375 pt | Ordinary reference use and repeated reading |
| `reference-compact` | Three | 6.3 / 7.8 pt | 6.25 / 4.375 / 3.125 pt | A real space constraint with short entries |

The two reference presets currently require `formula-sheet`. They use an A4
article 10 pt class, 8 mm side margins, 12 mm top and 16 mm bottom margins,
a 5 mm column gap and reserved header/footer space. With the reference theme,
a thin 0.3 pt gray separator distinguishes adjacent columns. Body typography is an
explicit local selection under that shell; no content-based shrinking or
automatic page-count optimization occurs. Review compact text at actual print
size. Widen a block or choose the readable preset when its content needs room.

Body and mathematical sizes are independent authored declarations. Main
mathematics uses the Computer Modern 10 pt optical designs, while the ordinary
script and scriptscript tiers use the 7 pt and 5 pt designs, respectively,
uniformly scaled to the sizes in the table. The script sizes are 70% and 50%
of the main mathematical size; they are no longer both clamped to 5 pt.
Small optical designs have different proportions from the 10 pt designs:
scaling a 6 pt design is not equivalent to scaling a 10 pt design. The
reference layout selects the latter for primary mathematics rather than
geometrically narrowing or height-adjusting an expression. Extended symbols
and auxiliary mathematical alphabets retain explicitly scalable TeX
distribution faces. See [runtime typography](runtime-fonts.md#reference-mathematics).

These fixed declarations do not depend on content length or a page quota.
Uniform font scaling preserves each design's glyph proportions; it is not
permission for font substitution warnings or anisotropic box scaling.

The default composition follows the supplied sheets' compact grammar:
numbered local topics with a black underline, a second subtopic level, mostly
unboxed mathematical displays with adjacent conditions, and a few short gray
notes or Q&A fields. Central results can use a compact frame. The starters
present twelve independent topics; covariance stays with probability rather
than appearing under a separate dynamics family. Do not manufacture a
full-width parent solely to demonstrate the wide-block API.
Two heading levels are the requested authoring policy; the supplied particle
sheet also contains deeper headings. Preserve the requested topic/subtopic
limit when adapting that source.

Inside `referencecolumns` and `referencewide`, the layout aligns headings to
their local reading edge: left for English and right for Hebrew, with the
opposite edge ragged. Heading lines wrap between words without stretching
word spaces or automatically splitting words with hyphens. This scoped
policy belongs to `reference_columns.tex`, independently of the chosen theme;
it retains authored hyphen characters, numbering, mathematical content and
theme presentation. Body paragraph alignment and hyphenation remain unchanged,
and headings outside these environments retain their surrounding behavior.
The document's main language still determines column progression. If a title
contains an unbreakable item wider than its available line, revise the wording
or use a suitable wider block rather than compressing the type.

Omitting `--layout` means `standard` and preserves existing defaults. Omitting
`--theme` on either reference preset selects `reference`; an explicit theme
always wins. Selecting `--theme reference` on a standard document gives its
presentation without activating columns. Other kinds currently accept only
the `standard` generator layout; the theme itself remains independently usable.

Use `hebrew-with-english` or `english-with-hebrew` when appropriate. For
`bilingual`, explicitly supply `--main-language hebrew` or `english`. The
starter uses one combined title and separately authored primary/translated
bodies, with the translated body beginning on a new page. A language profile
never translates text or establishes the correctness of a translation.

Column progression follows the document's resolved main language: right to
left for Hebrew and left to right for English. This applies to both complete
language bodies of a bilingual sheet, including the translated counterpart
after its page break. A Hebrew counterpart in an English-main sheet therefore
retains left-to-right column progression while its headings and paragraphs
read RTL; an English counterpart in a Hebrew-main sheet retains right-to-left
columns while its prose reads LTR. A minority-language paragraph likewise
changes its prose direction without reversing the columns. Keep mathematical
expressions and units in their logical mathematical order. Keep physical axes, arrows and
quantum-wire meanings intact; adapt labels through the core language APIs
rather than mirroring a diagram. See [language and design](language-design.md)
and [direction and math](direction-and-math.md).

## Compose the four independent layers

| File | Role | Owns |
|---|---|---|
| `reference_components.tex` | Semantic extension | Short entry boundaries, notes, warnings, central formulas, Q&A and atomic objects/captions |
| `reference_columns.tex` | Layout extension | Local column flow, gaps, separator width, body size, scoped mathematical typography and reading-edge heading alignment without automatic word splitting |
| `reference_shell.tex` | Page-shell extension | First title, running title and uniform centered folios |
| `reference_theme.tex` | Presentation theme | Serif black rules, restrained gray backgrounds and numbering visibility |

All require the initialized `preamble.tex`; none requires another optional
layer. The recommended composition is core, semantic components, layout,
page shell, then one theme. Never create a Hebrew or English reference preamble.
`reference_shell.tex` conflicts with `topicrail.tex`; select one page shell.
The reference theme conflicts with the reader, academic and clean themes and
the legacy clean carrier. See [architecture](architecture.md).

The reference theme reuses Frank Ruhl Libre for Hebrew and Latin Modern Roman
for English. Mathematical typography belongs to the opt-in layout and uses
Computer Modern faces already available in the TeX distribution. The supplied
PDFs' font choices are not new installation dependencies. No font
binary is added to the skill; the existing verified external font setup
remains required. See [studio setup](studio-setup.md).

## Set metadata and enter columns

Title fields are value macros, not setters with arguments. Define them before
loading the shell: `\ReferenceTitle`, `\ReferenceShortTitle`,
`\ReferenceSubtitle`, `\ReferenceAuthor` and `\ReferenceDate`. The short
title defaults to the full title; subtitle, author and date default to empty.
Provide actual attribution only. Keep the short title small enough for the
running header. Call `\makereferencetitle` once in outer text before columns.
The shell supports `article`, uses a centered 11/13 pt first-page title, an
8/10 pt gray running header and an 8/10 pt centered footer on every page.
The starter leaves subtitle, author and date empty. Adding metadata is an
authored choice, not a row reserved by default.

This is a readable Hebrew composition with an authored title and a central
formula. Copy the named assets into the project before compiling it:

```latex
\def\lakitlanguageprofile{hebrew}
\def\lakitdocumentclass{article}
\def\lakitclassoptions{10pt,a4paper}
\def\lakitgeometryoptions{left=8mm,right=8mm,top=12mm,bottom=16mm,headheight=10pt,headsep=3mm,footskip=7mm}
\def\lakitlinespread{1}
\def\lakittocdepth{2}
\def\lakitsecnumdepth{2}
\def\ReferenceColumnCount{2}
\def\ReferenceColumnGap{5mm}
\def\ReferenceColumnRule{.3pt}
\def\ReferenceBodyFontSize{9}
\def\ReferenceBodyBaseline{11}
\def\ReferenceMathFontSize{8.75}
\def\ReferenceMathScriptSize{6.125}
\def\ReferenceMathScriptScriptSize{4.375}
\def\ReferenceTitle{דף נוסחאות: אנרגיה ותנע}
\def\ReferenceShortTitle{אנרגיה ותנע}
\input{preamble.tex}
\input{reference_components.tex}
\input{reference_columns.tex}
\input{reference_shell.tex}
\input{reference_theme.tex}
\hypersetup{pdftitle={דף נוסחאות: אנרגיה ותנע},pdfauthor={}}
\begin{document}
\makereferencetitle
\begin{referencecolumns}
\begin{referenceentry}
\section{אנרגיה קינטית}
לתנועה לא יחסותית של גוף בעל מסה חיובית וקבועה:
\begin{equation}
  E_k=\frac{p^2}{2m}
  \label{eq:kinetic}
\end{equation}
לשימוש בנוסחה \eqref{eq:kinetic}, שמור על יחידות עקביות.
\begin{referencenote}
בדוק את תנאי הקירוב לפני הצבת ערכים.
\end{referencenote}
\end{referenceentry}
\end{referencecolumns}
\end{document}
```

Build this reference-theme source with matching declarations:

```bash
EXPECTED_PAPER=a4 PDF_FOLIO_LAYOUT=center PDF_FOLIO_BAND=footer \
  PDF_CAPTION_COLOR=000000 PDF_CAPTION_LABEL_WEIGHT=normal \
  bash /path/to/skill/scripts/build.sh /absolute/path/to/project/main.tex
```

Generated wrappers declare these preset values only when the variables are
unset. Explicit caller settings remain authoritative and are validated.
Changing the source paper or shell also requires matching verification settings.

Define body font-size, baseline and mathematical-size overrides before loading
`reference_columns.tex`, preferably alongside the other pre-input layout
declarations. `\ReferenceMathFontSize`, `\ReferenceMathScriptSize` and
`\ReferenceMathScriptScriptSize` are bare point numbers, independently
authored from `\ReferenceBodyFontSize` and `\ReferenceBodyBaseline`. The
generated presets supply all five values explicitly. When the layout is
loaded directly without math overrides, main mathematics defaults to the
declared body size; the two script tiers default to 70% and 50% of that
mathematical size. The layout requires
`0 < scriptscript <= script <= main math`, a positive body size and a baseline
at least as large as that body size. There is no 5 pt script floor.

The layout registers separate reference math versions and scalable optical
families. The layout activates them locally inside `referencecolumns` and
`referencewide`, with matching normal/bold variants. Native `\boldmath`,
`\unboldmath` and `\boldsymbol` retain their meaning there; an explicit
custom math-version request passes through. Local heading sizes and
amsmath's smaller text preserve the declared main/script ratios. Leaving
the environment restores the surrounding mathematical configuration. Merely
loading the layout does not activate these versions or replace global
`\DeclareMathSizes` declarations. The reference theme retains its established
standalone heading-size declarations; selecting it alone does not activate
the new reference math versions.

An independently authored custom math version owns its font-shape and size
declarations, including fractional text sizes reached by nested mathematics
or `\text`. Verify those declarations for the actual content and keep the
ordinary font-substitution checks enabled.

Do not alter these configured sizes late in a column run. Choose authored
sizes, then build and render representative formulas, accents, nested scripts,
fractions, delimiters and mixed-language text. An override still has to pass
actual font-shape and glyph checks; do not scale a rendered equation to make
it fit a column.

`referencecolumns` defaults to `\ReferenceColumnCount`; its optional argument
accepts only `2` or `3`. Defaults are count 2, gap 5 mm, separator 0.3 pt,
skip 6 pt, body size 9 and baseline 11. Without math overrides its mathematical
sizes are 9, 6.3 and 4.5 pt; the generated readable preset explicitly selects
the 8.75, 6.125 and 4.375 pt values above. Font-size/baseline macro values are
bare point numbers; gap, separator and skip are TeX lengths. Define
`\ReferenceColumnRule` before loading the layout; use `0pt` to omit separators
or another nonnegative length to change their width. The reference theme
supplies their gray color independently of the layout. `\ReferenceSelectBodyFont` applies the declared local
font selection. Positive font size and gap, baseline at least the size and
nonnegative separator width and skip are required. Ordinary paragraphs and lists within columns
retain the core's language handling. For an authored topic break, finish its
paragraph and use `\par\columnbreak` (or a blank paragraph followed by
`\columnbreak`). Native `\columnbreak` within a paragraph marks the end of
the current line; it is not a word-level break and does not separate two
topics that share that line. Ordinary balancing remains active.

Column flow preserves each atomic block's natural height. If the blocks
cannot fit in a balanced ending, the layout can continue onto another page
while preserving their size and spacing. Allow that extra page when the
content needs it; the presets provide no fixed page limit or guaranteed
single-page balance.

## Author native heading hierarchy

Use two native heading levels in either language: `\section` for a topic
and `\subsection` for a subtopic. Reference presets set `secnumdepth=2` and
`tocdepth=2`, exposing these two numbered heading and PDF bookmark levels
without adding a printed table of contents. Use ordinary bold inline text
for a further local distinction instead of adding a third numbered level.
Heading depth does not change the separate selective equation policy. Other
document designs retain the core's generic heading-depth hooks.

Inside an active reference layout, mathematics in a topic or subtopic heading
follows that heading's bold type through the local reference bold version.
Selecting the reference theme alone retains its existing mathematical policy
without activating these local reference versions.

An ordinary `\section` inside `referencecolumns` is local to that column and
keeps its compact ruled presentation. For a parent topic that governs the
following columns, close the column run, place its native `\section` inside
`referencewide`, close the wide block and resume columns. With the reference
theme, that heading and its rule span the available text width, so the topic
visibly governs the following columns. Its children use `\subsection` only.
Use this structure for a genuine common parent, not for unrelated topics or
to make the default sheet look fuller:

```latex
\end{referencecolumns}
\begin{referencewide}
\section{Physics}
\label{sec:physics}
\end{referencewide}
\begin{referencecolumns}
\subsection{Quantum mechanics}
\label{sec:quantum}
Describe the state and its assumptions here.
\subsection{Particles}
Describe the next child topic here.
```

If six sections precede this parent, LaTeX supplies `7`, `7.1`, `7.2`
and subsequent child numbers from the actual source hierarchy. Never
type those numbers into the heading text or reset counters merely to match
the example. Use Hebrew titles for a Hebrew sheet; the same commands retain
the hierarchy and align the headings at the right reading edge.
Keep `\label` immediately after a numbered heading and use native `\ref` to
cite it. Native contents entries, PDF bookmarks and destinations remain tied
to the heading. Starred headings such as `\section*` remain unnumbered and
retain the ordinary class behavior for contents entries and bookmarks.

## Keep short entries and blocks atomic

Use `referenceentry` to keep a short complete topic or its defining opening
together without a frame, float or new heading interface. Put native
`\section`/`\subsection` commands, adjacent scope text and the first defining
display inside it; labels, references and bookmarks keep their native owners.
For example:

```latex
\begin{referenceentry}
\section{Momentum}
For a particle of constant mass in nonrelativistic motion:
\[
  p=mv.
\]
\subsection{At rest}
When $v=0$, the momentum vanishes.
\end{referenceentry}
```

The entry may contain short reference blocks and `referencefigure` or
`referencetable` objects, including their captions. Its private saved box is
distinct from the objects' box, preserving nested object/caption content.
Short entries retain a small natural gap between topics. The reference theme
keeps their ordinary word spacing and alignment at the paragraph's reading
edge, including inside the entry container.
Nested `referenceentry` environments and entries taller than a full column
are errors. Keep the authored entry short: a long topic must flow normally,
keep only its defining opening atomic, or use meaningful short chunks.
Do not place every arbitrary section in an indivisible box, force column
breaks to fill a page, or shrink an oversized entry. Later prose may continue
between columns; mark an authored continuation clearly when needed.

`referencenote[Title]` and `referencewarning[Title]` default to Note/Caution or
הערה/זהירות according to the surrounding language. `referenceformula[Title]`
contains ordinary mathematical displays plus optional
`\referencepurpose{...}` and `\referenceconditions{...}` fields. Short
`referenceqa[Topic]` contains `\referencequestion{...}` and
`\referencesolution{...}`. Frames are atomic: each must fit in one full column.

```latex
\begin{referenceqa}[Momentum at rest]
\referencequestion{What is the momentum when the velocity vanishes?}
\referencesolution{For a massive particle at rest, $p=0$.}
\end{referenceqa}
```

For a longer solution, use `referenceqaseries[Topic]` with a question and
several `referencesolutionpart[Step title]` environments. The series has no
outer frame, so its parts can flow between columns/pages while each step
remains intact. Split an oversized part at a meaningful derivation boundary;
do not nest one long solution inside an atomic frame or scale its text down.
The optional series topic belongs to the first question frame. An individual
block taller than a full column fails with a request to divide the content;
the component does not silently break or shrink that block.

```latex
\begin{referenceqaseries}[A short classical derivation]
\referencequestion{How do momentum and kinetic energy relate?}
\begin{referencesolutionpart}[Define momentum]
For constant positive mass, $p=mv$.
\end{referencesolutionpart}
\begin{referencesolutionpart}[Substitute]
\[
  E_k=\frac12 mv^2=\frac{p^2}{2m}.
\]
\end{referencesolutionpart}
\end{referenceqaseries}
```

The four mutable styles `\referencenotestyle`, `\referencewarningstyle`,
`\referenceformulastyle` and `\referenceqastyle` contain local `mdframed`
options. The components supply neutral defaults; the reference theme supplies
gray notes and cautions with a single rule at the local reading edge,
compact central-formula frames and one uniform pale gray Q&A field with
square corners and a closed 0.6 pt border. Q&A's bold Question/Solution labels
appear inline on the same background. Note and caution rules appear on the
physical right for Hebrew/RTL prose and on the physical left for English/LTR
prose. The surrounding block language determines the edge, not the document's
main language: an English note in a Hebrew-led sheet has a left rule; a Hebrew
note in an English-led sheet has a right rule. Page column order still follows
the main language. Restyling must preserve content, language and the authored
atomic boundary.

Within `referencefigure`, the reference theme keeps diagram and caption spacing
relative to the actual local body baseline. It changes only the local vertical
glue, retaining the core direction wrapper and measured caption anchor. Keep
the diagram and caption in the same atomic container. Unit and dimension
columns may be centered while quantity labels retain their local reading edge;
under Babel, do not infer a cell's physical alignment from `l` or `r` alone.

Prefer ordinary unboxed displays with short assumptions immediately nearby.
The optional purpose/conditions fields remain available for content that
benefits from them; repeating both on every formula is not the default sheet
grammar. Reserve central-formula frames for a few results worth emphasizing.

## Handle equations, diagrams and wide content explicitly

Number central results and equations cited or reused later, using the shared
selective-numbering policy. `\eqref` registers use; `\noeqref{eq:key}` retains
an author-designated central result without an in-text citation. Use
`equation*`, `align*` or `\[...\]` for intermediate steps. Repeated use cites
the original label. See [academic equation policy](academic-articles.md#selective-equation-numbering).

Use `\linewidth` for the actual local available width. Place nonfloating
tables and core-wrapped TikZ/quantum diagrams in columns only when they fit;
write a readable multiline mathematical derivation when appropriate. Native
floats, margin notes, `longtable` and `flowtable` are unsupported inside a
column run. Keep captions immediately with their object and keep the declared
normal black caption contract when using the reference theme.

Keep a complete diagram and its caption together inside `referencefigure`,
or a short table and its caption inside `referencetable`. These neutral,
nonfloating atomic containers take no arguments and use the current
`\linewidth`; they add no frame or automatic scaling. Keeping both elements
inside the same container prevents column flow from separating the object
from its caption and measured destination. An object taller than a full
column fails explicitly: shorten or split it meaningfully, or use a genuinely
wide block when width is the constraint.

Use `\referencefigcap[short list entry]{caption}` and
`\referencetabcap[short list entry]{caption}` immediately after the object
inside its container. Put `\label{...}` first inside the full caption. These
thin core delegates retain the actual counters, destinations, reference text
and optional list entries, while inheriting the local body size. The core default
also caps its small preset at a smaller local body size, so optional framed tables
inside columns do not enlarge their captions. Keep a table caption immediately after
`\end{tabular}` while the same centering context is still active, so the core
can locate the table itself. For example:

```latex
\begin{referencefigure}
\begin{tikzpic}
\begin{tikzpicture}
\draw[->] (0,0) -- (2.4,0) node[right] {$p$};
\draw[->] (0,0) -- (0,1.3) node[above] {$E_k$};
\draw[domain=0:2,samples=32] plot (\x,{0.22*\x*\x});
\end{tikzpicture}
\end{tikzpic}
\referencefigcap[Energy curve]{\label{fig:energy}Kinetic energy as a function of momentum.}
\end{referencefigure}

\begin{referencetable}
\begin{center}
\begin{tabular}{cc}
\toprule
Quantity & Unit \\
\midrule
Momentum & $\mathrm{kg\,m\,s^{-1}}$ \\
\bottomrule
\end{tabular}
\referencetabcap[Units]{\label{tab:units}Consistent units for energy and momentum.}
\end{center}
\end{referencetable}
```

For a wide formula or diagram, close columns, enter `referencewide`, then
start a new column run. A wide block does not silently interrupt or restart
the preceding columns:

```latex
\end{referencecolumns}
\begin{referencewide}
\[
  \Psi(x,t)=\sum_{n=1}^{N} c_n\phi_n(x)\exp(-iE_nt/\hbar).
\]
\end{referencewide}
\begin{referencecolumns}
```

For a continuing table, close columns and use the separately loaded
`flow_tables.tex` contract in outer text; then resume columns. A wide block
preserves ordinary full-width flow and the declared body typography, not an
automatic resize. Neither columns nor wide blocks may be nested, placed in
a box/minipage/float, started inside a list or combined with class-level
`twocolumn`. A wide block may not occur inside an active column run.

## Build, render and review the current pages

Replace all sample text and check formula conditions, notation, units and
sources. Build through the generated wrapper or the skill's build script;
retain its hard source, font, overflow, geometry, caption and navigation gates.
Density checks remain advisory and do not judge scientific completeness.

Render every page into a fresh directory. Inspect each page at readable
resolution and at print size: column order, minority-language text, section
two-level hierarchy, complete short-topic openings, any authored full-width
grouping, column separators, section rules,
mathematical tags, narrow tables, physical diagrams, frame boundaries,
note/caution reading-edge rules in both native and minority-language blocks,
running headers and centered folios. A contact sheet is only an index.
Record only pages actually viewed, then run `render_review.py verify` with
`--rerender`; rebuild and repeat after fixes. Use an explicit second renderer
for representative native-language sheets when useful. See
[everyday workflow](everyday-workflow.md#review-actual-rendered-pages).

Deliver the PDF, editable project and its external dependency instructions.
Keep transient builds and visual evidence outside the installable skill.
Regression counts, successful compilation and recorded page observations are
distinct evidence; none authorizes claiming another unviewed document is
visually approved.
