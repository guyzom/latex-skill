# Printed page numbers and PDF page labels

Choose page-number placement independently of language, content profile, or theme.
Declare the inspection contract before building. The checker observes glyph
geometry; it does not place, repair, or renumber anything in the PDF.

## Layout contract

| Build setting | Values | Default |
| --- | --- | --- |
| `PDF_FOLIO_LAYOUT` | `center`, `left`, `right`, `outer`, `inner`, `none`, `custom` | `center` |
| `PDF_FOLIO_BAND` | `footer`, `header` | `footer` |

- `center`: the candidate's horizontal center is within 12 PDF points of the page center.
- `left` / `right`: the candidate's center is in the left / right outer third.
- `outer`: right on odd physical PDF pages, left on even physical PDF pages.
- `inner`: left on odd physical PDF pages, right on even physical PDF pages.
- `footer` / `header`: bottom / top 10% of the page respectively.

Coordinates use the unrotated space returned by PDF text extraction, including
physical unit scaling. `/Rotate` does not swap the dimensions used for comparison.
Sideways text or unusual landscape placement can still require `custom`.
Physical PDF page 1 is treated as a right-hand recto for `outer` and `inner`.
Numbering resets and omitted covers do not redefine that parity. Use `custom`
when the actual design uses another parity or variable geometry.

```bash
PDF_FOLIO_LAYOUT=outer bash scripts/build.sh document.tex
PDF_FOLIO_LAYOUT=right PDF_FOLIO_BAND=header bash scripts/build.sh document.tex
python3 scripts/check_pdf_render.py --folio-layout right --folio-band header document.pdf document.tex
```

These settings do not configure LaTeX page styles. Configure the source first,
then declare what it actually prints. Invalid settings fail before compilation.
The default remains compatible with existing centered-footer documents.

## Intentional absence and custom designs

`none` declares intentional absence of printed page numbers, for example in a
letter or handout. `custom` declares a design beyond the measured geometry or
numbering scope, such as decorated page markers, complex running heads, Hebrew
labels, or image-based folios.

```bash
PDF_FOLIO_LAYOUT=none bash scripts/build.sh letter.tex
PDF_FOLIO_LAYOUT=custom bash scripts/build.sh designed-report.tex
```

Both produce `FOLIO-NOT-MEASURED`: printed numbering was **not verified**. These
are author declarations, not proof of absence or correctness. For `none`, visually
confirm intentional absence; for `custom`, review every printed number, numbering
reset, and intended blank page against the document plan. Record that review with
the ordinary visual QA. Do not use these modes merely to hide an unexpected
mismatch in an otherwise supported layout.

Only printed-folio measurement changes. Off-paper content, reversed Latin runs,
mirrored parentheses, destination checks, build errors, and navigation checks
remain active. Malformed PageLabels still fail. Printable Unicode prefixes are
accepted as metadata in `none`/`custom`, without claiming comparison against
visible glyph order.

## Numbering in the source

Change numbering after the previous page has finished:

```latex
\pagenumbering{roman}
\section*{Preface}
Opening text.
\clearpage
\pagenumbering{arabic}
\section{Introduction}
The main sequence starts here.
```

The canonical preamble and hyperref generate PDF `PageLabels`. Do not rewrite a
correct label to conceal a wrong printed number. The same numbering commands
apply to Hebrew documents; headings follow their selected language.

## Measurement and findings

When explicit PageLabels exist, every observed candidate in the declared geometry
is compared with its page's label. Decimal numbers, lower/uppercase Roman numbers,
Latin-letter numbering, ASCII prefixes, resets, and multiple ranges are supported.
PDF alphabetic numbering is `a … z, aa … zz`, not spreadsheet column lettering.
Direct/indirect number trees and ordinary/UTF-16 strings are read as typed PDF
objects. Physical glyph positions determine order; extraction stream order is not
assumed to be visual order. Neighboring fragments are joined by baseline and
proximity. Label whitespace is not a typography requirement.

Candidate construction retains the original extracted line whitespace and
paragraph context before separating runs by geometry. A run belonging to
positively connected, adjacent multiline Latin prose in the same extracted
block is excluded from folio candidates only when the lines also agree in
alignment, font scale and leading. This prevents body sentences near a column
foot from becoming page-number evidence merely because an isolated word falls
inside the selected region. A standalone run, a wrong or duplicate folio and
supported prefixed labels remain eligible; the expected number is never used
to discard a conflicting observation. Uncertain runs still reach the ordinary
ambiguity and mismatch checks.

A measured document of at least three pages must expose folios on at least half
its pages, rounded up and with a minimum of two. This permits an unnumbered title
page, but does not prove that every unobserved page is intentionally unnumbered.
Empty labels do not create observations or relax this coverage floor.

Without PageLabels, the legacy decimal rule infers a stable majority offset
between physical page index and printed number. It cannot infer mixed numbering
or arbitrary resets. Add correct labels or use an explicitly reviewed custom
contract when that inference is inapplicable.

| Finding | Meaning |
| --- | --- |
| `PAGE-NUMBER-REVERSED` | Observed characters reverse the expected label. |
| `PAGE-NUMBER-ODD` | Another observed/expected mismatch. |
| `FOLIO-AMBIGUOUS` | Multiple candidate runs in the selected region. |
| `FOLIO-COVERAGE-LOW` | Too few observations for a measured layout. |
| `FOLIO-SEQUENCE-UNINFERABLE` | Unlabelled decimal folios lack a stable offset. |
| `FOLIO-LABELS-INVALID` | Invalid or unsupported label metadata. |
| `FOLIO-NOT-MEASURED` | Explicit `none`/`custom` handoff; numbering remains unverified. |

## Limits

Side regions can contain running text as well as numbers. After the narrow
exclusions for attached mathematical scripts and connected body prose,
multiple eligible runs remain intentionally ambiguous. Complex layouts need a
targeted external check or
the documented custom visual review, rather than more permissive heuristics.
The measured label scope is printable ASCII, Roman values up to 3999, and labels
up to 128 characters. Explicit label punctuation is supported. Unicode metadata
accepted by the manual route does not add Unicode visual-order measurement.
Control characters, malformed trees, unsupported styles, and invalid initial
values remain findings.

This is not OCR, an accessibility test, a full PDF validator, or an external-viewer
click test. Metadata and printed numbers can agree while both contradicting the
author's intent. Compare the sequence to the document plan and inspect the target
viewer when its behavior matters.

## Regressions and evidence

```bash
python3 scripts/test_v4240.py
python3 scripts/test_folio_layouts.py
HLLPDF_FOLIO_EVIDENCE=/path/to/new-empty-evidence python3 scripts/test_v4240_runtime.py
```

The original suite covers PDF objects, Roman/decimal/mixed sequences, reversals,
corrupt metadata, actual glyph placement, and the managed build gate. The layout
suite adds all horizontal positions in both bands, wrong-position controls,
preserved mismatch detection, rotations, explicit manual handoffs, missing
supplied sources, and invalid configuration.

The parser uses typed `xref_get_key` values because the pinned PyMuPDF
`get_page_labels()` can expose a UTF-16 prefix as serialized hex text. A temporary
PDF view decodes typed values; the inspected PDF is never edited.

- [PyMuPDF page labels](https://pymupdf.readthedocs.io/en/latest/document.html#Document.set_page_labels)
- [PyMuPDF page label lookup](https://pymupdf.readthedocs.io/en/latest/page.html#Page.get_label)
- [hyperref manual](https://ctan.math.utah.edu/ctan/tex-archive/macros/latex/contrib/hyperref/doc/hyperref-doc.html)

Online documentation may describe another version. Compatibility claims come
from the pinned environment and actual tests, not the newest online version.
