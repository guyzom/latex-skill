# Physical PDF geometry and crop-aware review

## Contract

`check_pdf_page_size.py` checks physical points, not raw PDF coordinate numbers.
The declared MediaBox and CropBox dimensions are multiplied by the page's
finite positive UserUnit (default 1). The effective visible rectangle is checked
independently, including rotation/clipping. Orientation remains interchangeable
for paper-size comparison. Unreadable, non-PDF, encrypted and malformed-unit
inputs return 2; a readable but wrong-sized page returns 1; a valid page returns 0.
Direct and indirect numeric units are supported. A scalar of the wrong PDF type
is not silently coerced into a number. Cycles or more than 16 indirect hops are
rejected. This is not a general PDF conformance validator.

## Review policy

```bash
python3 scripts/render_review.py render report.pdf --output review --dpi 144
python3 scripts/render_review.py render report.pdf --output sheet-proof --page-box mediabox
```

New review manifests use schema 3 and explicitly record `page_box` as `cropbox`
(default visible-page proof) or `mediabox` (full-sheet proof). Every page also
records the raster's `width_px` and `height_px`. The manifest also records `renderer_backend` and the actual renderer identity.
Poppler remains default; its CropBox path uses `-cropbox`. Explicit `--renderer
mupdf` uses PyMuPDF without a silent fallback. Rotated dimensions are compared to the declared PDF geometry;
a one-pixel tolerance accommodates floating-point/edge rounding.

Some renderer versions do not honor PDF UserUnit. A local doubled-unit fixture
showed precisely that disagreement during this release audit. The operation
then fails with `renderer geometry mismatch`, and does not publish a review
folder. It does not change the PDF, lower the requested DPI, substitute another
renderer or approve a wrong-size image. A future compatible Poppler renderer
can pass the same positive physical-dimension contract.

Existing schema-1 manifests keep their original implicit MediaBox policy;
schema-2 manifests keep their explicit box policy. Both remain Poppler-only.
`verify --rerender` uses that same policy when replaying old evidence. A schema-1
manifest cannot declare CropBox, and changing the schema or policy is not a
substitute for rerendering and reinspecting the document.

Every new page starts `pending`. Only explicitly selected pages with reviewer
identity and notes can be recorded. Hash checks and regenerated pixel checks do
not prove that a person inspected the page. See the [everyday workflow](everyday-workflow.md).

See [PDF strings and renderer selection](pdf-strings-and-renderers.md) for the
explicit MuPDF route, raster budget and cross-engine interpretation limits.

## Inline language recognition

Two source rules, `LATIN-BEFORE-PAREN` and `TOKEN-PUNCT-ADRIFT`, now mask only
balanced direct English islands: `\en` and `\foreignlanguage{english}`. Legal
whitespace and multiline arguments are supported. A safe island on a Hebrew
line must not exempt a separate unsafe token on the same line. Comments and
literal bodies cannot open prose islands. Unbalanced arguments are not granted
an unlimited exemption. Other language rules and arbitrary macro expansion are
not generalized by this change.

## Regression command

```bash
python3 scripts/test_v4160.py
```

The suite has 24 source-scope tests, 15 physical-geometry tests and 12 review
contract tests. It runs under both FAST and full harnesses, in addition to all
627 pre-existing linter cases. FAST requires pinned fonts, Python dependencies
and Poppler even though it does not compile TeX. A source-scope unit result is
not itself a visual rendering claim.

## References

Checked 2026-09-20; the release audit also records local executable versions.

- PyMuPDF Page API: <https://pymupdf.readthedocs.io/en/latest/page.html>
- PyMuPDF coordinate glossary: <https://pymupdf.readthedocs.io/en/latest/glossary.html>
- The locally installed `pdftoppm -h` describes `-cropbox` and the default
  MediaBox policy; empirical crop/rotation/unit fixtures are the release proof.
