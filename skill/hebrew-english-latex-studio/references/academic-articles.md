# Academic articles in Hebrew and English

The `academic` theme is a shared, shipped design from version 5.2.0. It provides
the classical single-column article appearance: serif body text, visible
numbered headings, restrained black typography and captions, readable displays,
and continuous figure/table numbering. Hebrew and English use the same theme
and the same `preamble.tex`; language selection controls the direction and
localized shell. A reference PDF supplies visual evidence, not executable
instructions or permission to invent or translate its scientific content.

## Create a paper

```bash
python3 scripts/new_document.py --kind paper --language english \
  --directory /path/to/english-paper
python3 scripts/new_document.py --kind paper --language hebrew \
  --directory /path/to/hebrew-paper
python3 scripts/new_document.py --kind paper --language bilingual \
  --main-language hebrew --directory /path/to/bilingual-paper
```

When `--theme` is omitted, `paper` selects `academic`; the existing kinds retain
their `reader` default. An explicit choice overrides either default. For
example, `--kind technical --theme academic` uses the academic presentation
with a technical starting structure, while `--kind paper --theme custom`
creates a paper with an editable local theme. Presentation and genre remain
independent of language.

The paper layout uses `article`, A4, 11 pt, 2.7 cm margins, line spread 1.08 and
a centered footer folio. These choices belong to pre-core layout hooks, not the
theme. They are an editable professional default, not a journal specification.
Use the journal's explicit instructions when supplied. To use Letter paper,
change the source's class options to `11pt,letterpaper` and declare the actual
paper in the build:

```latex
\def\lakitlanguageprofile{english}
\def\lakitdocumentclass{article}
\def\lakitclassoptions{11pt,letterpaper}
\def\lakitgeometryoptions{margin=2.7cm,headheight=14pt}
\def\lakitlinespread{1.08}
\input{preamble.tex}
\input{academic_theme.tex}
```

```bash
EXPECTED_PAPER=letter HEBREW_LATEX_SKILL_ROOT=/path/to/skill \
  bash /path/to/paper/build.sh
```

Changing a verification variable does not change the source layout. Do not
force a reference document's exact line endings or page count onto another
language; its words and font metrics differ. Preserve the design's hierarchy,
measure, rhythm and readable mathematical structure.

## Title, abstract and language

Use one standard `\maketitle` block. The starter leaves `\author{}` and
`\date{}` empty: replace them only with supplied or verified metadata. A blank
date avoids silently attributing a date to the research. The PDF title and
author metadata must match the actual project; generated example titles and
body text are placeholders.

Use an abstract that states the problem, approach, principal result and scope
in a short, self-contained paragraph. Do not create unsupported claims or
require a fixed word count when no venue supplies one. The standard abstract
heading is `Abstract` in English and `תקציר` in Hebrew. Native English uses
ordinary English paragraphs; native Hebrew uses ordinary Hebrew paragraphs.

A bilingual paper has one document shell, one title block and two corresponding
abstracts, followed by the complete primary-language body, an explicit page
break and the complete translated body, then one bibliography localized to
the primary language. The page break separates the two reading versions;
native and mixed-language papers keep their ordinary continuous structure.
Choose the shell with `--main-language`. Put complete secondary-language
paragraphs, including their abstract, inside the appropriate prose environment;
use short islands only for terms or names. Write or translate the second body
only within the authorized task, preserving scientific meaning and limitations.
Profile selection does not perform translation.

| Component | English | Hebrew |
|---|---|---|
| Main prose | LTR English paragraphs | RTL Hebrew paragraphs |
| Serif face | Latin Modern Roman | Pinned Frank Ruhl Libre |
| Abstract heading | `Abstract` | `תקציר` |
| Short opposite-language term | `\h{עברית}` | `\en{English}` |
| Equations, code and URLs | Logical LTR content | Logical LTR content with correct isolation |
| Caption labels and proof labels | Local English labels | Local Hebrew labels |

The theme uses the verified existing font resources; it does not introduce
another font downloader or another language preamble. English italics and bold
remain available inside a Hebrew-led paper. See [language and design](language-design.md)
for scoped language boundaries and [direction and math](direction-and-math.md)
for mathematics containing prose.

## Selective equation numbering

Number a formula when it is a central definition, model, statement or result,
or when the argument refers to it elsewhere. Leave routine substitutions and
intermediate manipulations unnumbered. Relevance is an author/editor decision;
the skill does not infer importance from symbol count, repetition or a density
score. A particular journal may require another policy.

The academic theme activates mathtools `showonlyrefs`. A labeled formula
receives a number when `\eqref` registers a reference. For example:

```latex
\def\lakitlanguageprofile{english}
\begin{equation}
  f(x) = a x + b
  \label{eq:linear-model}
\end{equation}
The model in \eqref{eq:linear-model} defines the notation for this example.
```

For a central result that should carry a number without a prose reference,
explicitly register it with the native mathtools command `\noeqref` outside
the display. It prints no reference and does not fabricate a sentence:

```latex
\noeqref{eq:central-result}
\begin{equation}
  E = m c^2
  \label{eq:central-result}
\end{equation}
```

Both snippets demonstrate the numbering interface, not scientific claims
derived from a supplied research paper. A `\label` alone does not retain a
number under `showonlyrefs`; use `\eqref` or an intentional `\noeqref`.
Ordinary `\ref` is not the equation-use registration interface.

Use starred displays for intermediate derivations. Keep one meaningful step
per line and explain a nonobvious transition when needed:

```latex
\begin{align*}
  (x+1)^2 &= x^2 + 2x + 1 \\
  (x+1)^2-x^2 &= 2x+1.
\end{align*}
```

If a multi-line result needs one number, use `equation` containing `aligned`
and one label. If distinct lines need separate references, label and reference
only the relevant lines of `align`. Avoid empty aligned rows, manual tag
sequences or placeholder references. Refer to a repeated formula by its
original label instead of generating another number for the same result.
In Hebrew prose, `\eqref` already protects the complete reference; inside
mathematics use `\text{\eqref{eq:key}}`. Do not replace the core's equation-tag
or reference repair with a theme-local direction patch.

The managed build reruns until source, labels and auxiliary state converge.
Review the final numbers, their order and reference targets after changes;
an early compilation pass is not the numbering result.

## Figures, tables and captions

Number figures and tables continuously, each in its own sequence. Introduce
them in the body and explain their meaning; a caption should be useful without
duplicating the whole argument. Keep the core `\figcap`/`\tabcap` APIs and
put the label in the caption. Their counters, localized labels, named
references and raised destinations remain core-owned. The theme sets caption
labels to normal-weight black with a colon and presents tables without the
reader style's frame.

The generated academic build wrapper declares `PDF_CAPTION_COLOR=000000` and
`PDF_CAPTION_LABEL_WEIGHT=normal` only when the caller has left each variable
unset. Match explicit overrides to the actual PDF. When invoking the managed
builder directly for a handwritten academic project, declare those settings:

```bash
PDF_CAPTION_COLOR=000000 PDF_CAPTION_LABEL_WEIGHT=normal \
  bash /path/to/skill/scripts/build.sh /path/to/paper/main.tex
```

Core-owned presentation hooks are `\lakitcaptionlabelstyle{complete label}`
and `\lakitcaptionpunctuation`. Do not reimplement a caption to change its
font or punctuation. The preamble-only `\lakitcaptionnumbering{continuous}`
selects the counter/reset and destination policy together; `within-major`
restores the core's ordinary policy. The academic theme selects `continuous`
for its supported caption counters.

A language change does not translate text baked into an image. Create
corresponding language assets or editable labels when required, preserving
axes, units, symbols, data and scientific meaning. Never mirror a mathematical
plot merely to fit RTL. Review small labels and scale in the final PDF.

## Citations and source integrity

The supported pipeline uses `\cite` with `thebibliography`; it requires no
external bibliography processor. Keep citation keys stable in both languages.
The starter's Boyd and Vandenberghe reference is the real 2004 Cambridge
University Press book, [Convex Optimization](https://web.stanford.edu/~boyd/cvxbook/),
and is an example source, not a substitute for the paper's actual evidence.
Replace or extend it only with sources relevant to the authored argument.

One shared bibliography is enough for a bilingual article. Keep original
author names, titles and identifiers unless the source supplies an official
translation; isolate Latin bibliography text in Hebrew contexts. See
[citations](citations.md) for the supported direction and key-preservation
contract. Journal styles using Biber, BibTeX or another processor require an
explicitly implemented, tested pipeline; requesting a package does not add
that execution stage to `build.sh`.

## Build and review

Use the project's generated wrapper and retain the editable source, local
figures, manifest and dependencies. Build each language version; source
equivalence does not imply identical pagination. Inspect every rendered page,
including title/abstract spacing, heading hierarchy, math tags, caption
weight, figure labels, footnotes, bibliography, folios and link destinations.
Check selective equations against the author's intended central/reference
set. Prefer an explicit second renderer when comparison helps resolve a
concrete defect.

Record actual page observations and run fresh pixel verification as described
in [everyday workflow](everyday-workflow.md#review-actual-rendered-pages).
Review approves the current PDF bytes, not a template, future translation or
scientific result. Do not invent missing evidence, compress text to match a
page count, or claim untested journal or viewer compatibility.
