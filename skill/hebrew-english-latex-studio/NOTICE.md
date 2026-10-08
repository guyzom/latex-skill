# Dependency notices

## PyMuPDF 1.26.7 and MuPDF

`requirements-qa.txt` pins PyMuPDF 1.26.7, imported as `fitz` by the PDF QA and
review programs. PyMuPDF provides Python bindings and abstractions for MuPDF.
The upstream 1.26.7 README attributes maintenance and development of both
projects to Artifex Software, Inc., and identifies Jorj X. McKie as the original
PyMuPDF author. Preserve the upstream copyright and other notices supplied with
the installed dependency.

The [tagged upstream README](https://github.com/pymupdf/PyMuPDF/blob/1.26.7/README.md)
offers PyMuPDF under GNU AGPL or an Artifex commercial agreement. The installed
1.26.7 wheel metadata describes its license as GNU Affero GPL 3.0 or Artifex
Commercial License. No commercial agreement is supplied by this package.

The unmodified tagged upstream `COPYING` file is retained as
[`LICENSES/PyMuPDF-1.26.7-COPYING`](LICENSES/PyMuPDF-1.26.7-COPYING), sourced from
[PyMuPDF 1.26.7](https://raw.githubusercontent.com/pymupdf/PyMuPDF/1.26.7/COPYING).
The standalone archive contains dependency specifications and integration code,
not a redistributed PyMuPDF/MuPDF implementation or binary. If a distribution
adds those components, preserve their own notices and assess their source and
redistribution obligations; this notice does not supply their Corresponding
Source. [`LICENSING.md`](LICENSING.md) describes the explicit local tooling grant
and closed project-source boundary.

The project's [Generated Output Permission](LICENSES/Generated-Output-Permission.txt)
applies only to original material the project licensor can license. It does not
grant rights in PyMuPDF, MuPDF or other third-party material, and does not change
their license or notice obligations.

## Other dependencies and fonts

The fontTools requirement and external LuaLaTeX and Poppler tools retain their
upstream licenses. Licensing the original integration and font-verification
code does not relicense these dependencies or any fonts.

Existing bundled font notices remain unchanged in `assets/fonts/`:

- `FrankRuhlLibre-OFL.txt` and `Heebo-OFL.txt`: SIL Open Font License texts.
- `DejaVu-LICENSE.txt`: the existing DejaVu/Bitstream notices and conditions.
- `SHA256SUMS`: the existing pinned font and notice hashes.

The standalone archive contains these font notices and hash manifest, not font
binaries. The repository's separate font files retain their existing terms.
No claim of complete provenance for code, templates, assets, or dependencies is
made by this notice.
