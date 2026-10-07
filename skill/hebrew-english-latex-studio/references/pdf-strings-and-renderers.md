# PDF strings and explicit review renderers

## Keep layout commands out of PDF strings

The canonical hook makes a plain `\\` a space in a PDF string. It does not
consume the star or optional spacing argument. In a reproduced numbered title,
`\\*[2pt]` printed a valid two-line heading but wrote literal `*[2pt]` into its
bookmark. An explicit `pdftitle` with `\\[2pt]` had the same problem. Both
compiled successfully in the previous release.

Preserve the printed title while providing a separate, clean PDF string:

```latex
\section{\texorpdfstring{שורה ראשונה\\*[2pt]שורה שנייה}{שורה ראשונה שורה שנייה}}
\hypersetup{pdftitle={שורה ראשונה שורה שנייה}}
```

A clean optional short title is another route, but it also changes the text used
in the table of contents. Choose intentionally; the checker does not rewrite
text, remove layout, or alter bookmarks automatically.

The hard source flag `PDFSTRING-LINEBREAK-ARG` checks the selected short/long
argument of explicit unstarred standard headings and literal `hypersetup`
fields `pdftitle`, `pdfauthor`, `pdfsubject`, `pdfkeywords`. It projects the PDF
branch of `texorpdfstring`, including nested wrappers. Comments, literal code,
and bodies of uninvoked recognized macro definitions do not produce findings.
Plain breaks and legal layout in an explicitly separated typeset branch pass.

This is a conservative serialization-risk check: a heading is checked even if
its level is currently excluded by `tocdepth`. A finding is not proof that its
bookmark was actually emitted. Custom `pdfbookmark` / `addcontentsline`,
indirect metadata, arbitrary macros, catcode changes, conditionals and
cross-file expansion are not interpreted. Check the resulting bookmarks and
metadata as well as the source. No unrestricted global PDF-string macro parser
was added to the preamble.

## Explicit backend selection, never silent fallback

```bash
python3 scripts/render_review.py render main.pdf --output review-poppler --dpi 144
python3 scripts/render_review.py render main.pdf --output review-mupdf --renderer mupdf --dpi 144
python3 scripts/render_review.py render main.pdf --output sheet-mupdf --renderer mupdf --page-box mediabox
```

Poppler is still the default and still required by the full skill toolchain.
MuPDF is provided by the already-required, pinned PyMuPDF package. The MuPDF
route does not invoke Poppler or fetch any additional dependency. The PDF is
copied to a temporary location; MediaBox inspection changes only the in-memory
copy and never saves those changes to the source PDF.

Schema 3 records backend, version identity, DPI, page-box policy and pixel size.
The gallery header displays that provenance. `verify --rerender` replays that
backend, not the current default. Legacy schema 1 keeps its MediaBox/Poppler
meaning and schema 2 keeps its declared box/Poppler meaning. Do not migrate a
manifest by editing its fields; render and inspect the new evidence instead.
The manifest is editable and is not a signed or authenticated reviewer identity.
Fresh pixel replay uses the currently installed version of the recorded backend;
it does not authenticate the editable version stamp from the original render.

A local Poppler build ignored `UserUnit=2`, which makes a valid PDF physically
larger than its raw coordinate box. The existing geometry guard still rejects
that incorrect image. Explicit MuPDF rendering produces the requested physical
size in the reproduced case. This does not bless every scaled PDF or make
Poppler the wrong renderer in general. Cropping, rotation and nonzero origins
are tested independently. No failure switches engines, reduces DPI or publishes
partial output silently.

Before rasterization, requested page sizes are checked against a cap of
50,000,000 pixels per page. Choose a lower supported DPI or render a smaller
artifact if the cap is exceeded. This is a raster budget, not a total-memory
limit, PDF sandbox, or guarantee against every expensive vector document.

## Interpret evidence rather than pixels alone

Compare named content anchors and physical geometry across engines. Different
antialiasing, font rasterization or color behavior may change pixels without a
layout defect. Equality is only required for replay with the recorded backend
in a compatible local environment, not between Poppler and MuPDF. Report the
engine, version, DPI, box policy and any disagreement; inspect the actual source
and render before deciding whether to change the document.

Every new review starts pending. Record only pages actually inspected with
nonempty reviewer and notes. Pixel replay proves neither human inspection nor
accessibility, scientific correctness or behavior in Preview/Goodnotes.

## Reproduce the regression controls

```bash
python3 scripts/test_v4190.py
HLLPDF_419_EVIDENCE_DIR=/tmp/new-pdfstring-evidence python3 scripts/test_v4190_runtime.py
```

The first command covers source boundaries, renderer dispatch, all 24
unit/rotation/box combinations, eight nonzero-origin cases, legacy manifests,
geometry errors, partial-publication controls, and image substitution with an
updated hash. The second builds the original and repaired sources, checks six
bookmarks, metadata, navigation and unchanged printed pixels, then replays each
backend. The negative fixture intentionally bypasses the build gate to observe
the defect; it is not an example of an approved publication workflow.

## Primary documentation

Consulted 2026-09-21; the audit records the local tested executable versions.
The tests, not an assumption about the newest docs, establish local behavior.

- [Hyperref manual — PDF strings](https://tug.ctan.org/macros/latex/contrib/hyperref/doc/hyperref-doc.html)
- [PyMuPDF Page API — pixmaps and page boxes](https://pymupdf.readthedocs.io/en/latest/page.html)
