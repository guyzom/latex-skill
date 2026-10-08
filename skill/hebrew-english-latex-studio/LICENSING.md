# PDF QA tooling license scope

The original project code in the exact files enumerated by
[`LICENSE-SCOPE.json`](LICENSE-SCOPE.json) is licensed under the GNU Affero
General Public License, version 3 only (`AGPL-3.0-only`). The grant covers those
files in full, including their embedded QA fixture code. It does not extend to
other files by directory membership, packaging, or file extension. Existing
third-party notices and terms remain applicable to their respective material.
This grant does not establish the provenance or ownership of every line of code.
The scoped licensing notices and package checks were added on 2026-10-08.

The unmodified GNU license text is in
[`LICENSES/AGPL-3.0-only.txt`](LICENSES/AGPL-3.0-only.txt). The tagged upstream
PyMuPDF license and dependency attribution are preserved in
[`LICENSES/PyMuPDF-1.26.7-COPYING`](LICENSES/PyMuPDF-1.26.7-COPYING) and
[`NOTICE.md`](NOTICE.md). These files, the scope manifest, and the covered source
ship in the standalone `.skill` archive. The archive does not bundle PyMuPDF or
MuPDF binaries or source; installing the dependency is a separate operation.

## Covered source and build support

The manifest lists individual paths without wildcard grants. Its categories
cover:

- PDF checks, geometry, folios, navigation, raster review, PDF probes, environment
  diagnosis, and catalog review orchestration that directly import PyMuPDF.
- PyMuPDF-integrated Python regression programs and the shell regression harness.
- The mandatory QA builder `scripts/build.sh`, its source checks, configuration,
  font verification, source resolution, hashing, and output publication helpers.
- Shared modules imported by those programs, plus packaging and license checks
  and the pinned QA dependency specification.

In particular, `check_pdf_render.py` imports `build_contract.py` and
`pdf_folios.py`; `check_pdf_page_size.py` imports `build_contract.py` and
`pdf_geometry.py`; `render_review.py` imports `atomic_replace.py`,
`pdf_geometry.py`, and `render_backends.py`. Those supporting modules are
explicitly covered. `render_backends.py` imports `fitz` even with the Poppler
backend, and review metadata and geometry also use PyMuPDF. Choosing Poppler
does not remove this integration. `build.sh` requires `fitz` and runs the PDF
checks after LuaLaTeX; the scoped grant includes this build orchestration and
its original supporting code rather than treating every subprocess as an
independent licensing boundary.

The covered shell regression harness also invokes unlisted static tests and
TeX fixtures. Those calls are not a determination that the unlisted programs
are independent works or that the archive is solely an aggregate.

## Excluded material and document output

Files absent from the manifest receive no new license grant from this change.
In particular, TeX templates, themes, components, examples, and fixtures in
`assets/` and `tests/`, catalog data in `registry/`, font programs and their
license texts, other documentation, and unrelated repository material are
excluded. No MIT or AGPL license is assigned to the TeX assets by this grant.
The generator `scripts/new_document.py`, the catalog resolver
`scripts/template_registry.py`, and documentation generator
`scripts/generate_studio_docs.py` are also excluded.

Using these tools does not automatically license original user document content
or output PDFs under AGPL. GNU AGPL section 2 applies to output only when its
content constitutes a covered work. Merely supplying TeX or PDF input to a
checker is not a license grant for that input. Copied source retains its actual
license: copying a template, component, covered program, or embedded fixture
does not erase its applicable terms. Output that includes covered source or
other protected material requires its own assessment. Absence of a license
notice is not permission to redistribute excluded material.

## Shared-code boundaries that remain unresolved

The manifest's `unresolved_local_imports` records the exact import edges from
covered programs to excluded project modules. These are present in the current
architecture, not hypothetical integration points:

- `studio_matrix.py` imports and calls `new_document.create` in the same Python
  program as its PyMuPDF review operations; it also uses `template_registry.py`.
  `studio_matrix_fixtures.py` calls the same generator.
- `test_generated_runtime.py`, `test_paragraph_style.py`,
  `test_reference_runtime.py`, `test_v480.py`, and `test_v490.py` import the
  generator while also using PyMuPDF. Paragraph-style tests also import the
  catalog resolver.
- `catalog_coverage.py` imports the catalog resolver. `test_release_contract.py`
  imports the resolver, generator, and `generate_studio_docs.py` while validating
  a package that contains the integrated tooling.
- The excluded generator imports `architecture_contract.py` and
  `template_registry.py`; the resolver imports `architecture_contract.py` and
  `build_contract.py`. The two shared contract modules are covered here. This
  generator dependency chain contains no PyMuPDF import, but shared code still
  requires analysis. The generator copies TeX assets and emits a wrapper that
  invokes the covered builder; those facts do not automatically license the
  copied assets or the wrapper under this grant.

GNU AGPL sections 1 and 5 address Corresponding Source and combined works;
section 5 also distinguishes independent aggregation. A path list describes
the explicit grant but cannot decide whether the combined programs require a
broader license or additional Corresponding Source. In-process imports and
shared modules are concrete unresolved boundaries here; a process boundary
alone would not prove independence either. Resolving them may require permission
for a broader grant over the generator/catalog code, a justified separation of
the programs, or an appropriate upstream commercial license. The current scoped
grant does not resolve those choices, certify AGPL compliance for the complete
skill, or establish rights to all bundled material. Exclusions do not override
any obligations imposed by upstream terms or applicable law.

When conveying covered software, preserve applicable notices and provide the
source required by the license. Binary redistribution and modified programs
offered over a network need assessment under sections 6 and 13 respectively;
the source archive and dependency pin alone are not a certification of those
obligations. This is technical scope documentation, not legal certification.

## Sources and maintenance

- [GNU AGPLv3 text](https://www.gnu.org/licenses/agpl-3.0.txt) and
  [sections 1, 2, 5, 6, and 13](https://www.gnu.org/licenses/agpl-3.0.html).
- [PyMuPDF 1.26.7 COPYING](https://github.com/pymupdf/PyMuPDF/blob/1.26.7/COPYING)
  and [README license and attribution](https://github.com/pymupdf/PyMuPDF/blob/1.26.7/README.md).

`python3 scripts/test_license_scope.py` checks the explicit manifest, source
notices, direct PyMuPDF imports, documented unresolved imports, and exclusion
guards. `python3 scripts/test_packaging.py` additionally checks the actual
archive and proves missing licensing files stop packaging. These are regression
checks for the declared boundary, not a legal analysis. New imports or paths
must receive a deliberate scope review; the checks never license files
automatically.
