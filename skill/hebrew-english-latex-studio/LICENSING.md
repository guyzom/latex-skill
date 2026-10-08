# Project tooling license scope

The original project code in the **138 individual paths** enumerated by
[`LICENSE-SCOPE.json`](LICENSE-SCOPE.json) is licensed under the GNU Affero
General Public License, version 3 only (`AGPL-3.0-only`), with the additional
Generated Output Permission described below. The grant covers those source files
in full, including their embedded fixture code. It does not extend to other
files by directory membership, packaging, or file extension. Existing third-party
notices and terms remain applicable to their respective material. This grant
does not establish the provenance or ownership of every line of code.

The unmodified GNU license text is in
[`LICENSES/AGPL-3.0-only.txt`](LICENSES/AGPL-3.0-only.txt). The tagged upstream
PyMuPDF license and attribution are preserved in
[`LICENSES/PyMuPDF-1.26.7-COPYING`](LICENSES/PyMuPDF-1.26.7-COPYING) and
[`NOTICE.md`](NOTICE.md). These texts, the additional permission, exact manifest,
and covered source ship in the standalone `.skill` archive. The archive does not
bundle PyMuPDF or MuPDF binaries or source; dependency installation is separate.

## Covered programs and supporting source

The manifest contains explicit paths in six groups:

- 12 PDF QA/review programs, including catalog review and environment diagnosis.
- 41 PyMuPDF-integrated regression programs.
- 28 build and shared-support files, including mandatory `build.sh` orchestration,
  source checks, configuration, fonts, hashing and publication helpers.
- 9 licensing and packaging files.
- 7 generator, catalog, documentation and maintenance programs:
  `new_document.py`, `template_registry.py`, `generate_studio_docs.py`,
  `studio_glossary.py`, `render_architecture_guards.py`,
  `render_compat_bundles.py` and `sync_preamble.sh` in `scripts/`.
- 41 additional QA regressions and support programs required by the harness,
  shared contracts, source resolution, documentation checks and font tooling.

The initial QA grant is extended to the seven named programs and the 41 explicit
QA/support paths. The additional permission and closure checks were added on
2026-10-08. The manifest records the source baseline before this extension.
No directory wildcard grants are used and future files require a deliberate
scope decision.

`render_backends.py` imports `fitz` even with the Poppler backend, and
`render_review.py` uses PyMuPDF for metadata and geometry. Choosing Poppler does
not remove the integration. `build.sh` requires `fitz` and runs mandatory PDF
checks after LuaLaTeX; its original source and called support are covered.

## Closed local source boundary

The manifest's `dependency_boundary` declares `closed_project_tooling`:
all project modules imported by covered Python programs are explicitly covered,
as are project callers of those modules. The shared `architecture_contract.py`
and `build_contract.py` modules now have covered callers in both generator and
QA code. The previous 13 imports into excluded generator/catalog/documentation
programs are covered by the explicit extension. The transitive
`generate_studio_docs.py` import of `studio_glossary.py` is also covered.
Architecture guard/bundle generation and maintenance consumers of the shared
contract are included, along with the regression harness and its support.

The checks inspect ordinary and literal dynamic Python imports, and fixed
references to existing project scripts in the covered source. They reject a
new import across the declared boundary in either direction, an unlisted
PyMuPDF importer, or unlisted script support. There is no allowlist of unresolved
project imports. These checks validate the current technical source boundary;
they do not establish ownership or decide every legal combined-work question.
External dependencies keep their upstream terms, and process boundaries alone
are not treated as proof of independence.

## Generated Output Permission

[`LICENSES/Generated-Output-Permission.txt`](LICENSES/Generated-Output-Permission.txt)
contains the additional permission under GNU AGPLv3 section 7. For original
project material the licensor is authorized to license, it permits reproduction,
modification and distribution of original text and code fragments emitted during
normal operation of the seven named programs, including fragments derived from
their original project support modules, as part of the specified outputs under
terms of the recipient's choice. An output need not be AGPL solely because it
contains those emitted fragments. Distribution of the programs themselves and
arbitrary copying of their source are outside this permission.

`new_document.py` verifies the exact permission text before creating a project,
copies it as `GENERATED-OUTPUT-PERMISSION.txt`, and includes that copy in
`project.json`'s creation-time source hashes. The generated README explains its
limited scope. The normal TeX, wrapper and structured-data generation algorithms
are preserved; no AGPL license is assigned to input templates or whole generated
documents by adding this permission copy. The installed package retains the
permission for catalog, glossary, architecture and maintenance operations too.

## Excluded input material and document output

Files absent from the manifest receive no new grant. TeX templates, themes,
components, examples and fixtures in `assets/` and `tests/`, catalog data in
`registry/`, glossary records in `references/glossary/terms.json`, other unlisted
documentation and repository material, fonts and their license texts are
excluded. No MIT or AGPL license is assigned to TeX assets by this grant.

Using these tools does not automatically license original user document content
or output PDFs under AGPL. GNU AGPL section 2 applies to output when its content
constitutes a covered work. Merely supplying TeX/PDF input to a checker is not a
license grant for that input. Copied source retains its actual license: the
additional permission covers only the specified original emitted fragments,
not copied input assets, records, fonts, PyMuPDF/MuPDF or other third-party
material. Their applicable terms and required notices remain. Absence of a
license notice is not permission to redistribute excluded material.

## Distribution obligations and verification

The explicit rights-holder grant and closed local source graph resolve the
identified project-source licensing gaps. They are distinct from a legal
certification of every distribution obligation or proof of all provenance.
GNU AGPL sections 1 and 5 address Corresponding Source and combined works;
section 5 also distinguishes independent aggregation. Preserve applicable
notices and provide required source when conveying covered software. Binary
redistribution and modified programs offered over a network need assessment
under sections 6 and 13. The package grant and source archive do not waive
upstream terms or certify those obligations. This is technical scope
documentation, not legal certification.

`python3 scripts/test_license_scope.py` mutation-tests the exact grant,
forward/reverse imports, script support, exclusion guards and additional
permission. `python3 scripts/test_packaging.py` checks the actual archive and
proves missing licensing files stop packaging. Generator regressions verify
permission retention, fail-before-write behavior and input/output exclusions.

## Sources

- [GNU AGPLv3 text](https://www.gnu.org/licenses/agpl-3.0.txt) and
  [sections 1, 2, 5, 6, 7 and 13](https://www.gnu.org/licenses/agpl-3.0.html).
- [GNU guidance on program output](https://www.gnu.org/licenses/gpl-faq.en.html#WhatCaseIsOutputGPL).
- [PyMuPDF 1.26.7 COPYING](https://github.com/pymupdf/PyMuPDF/blob/1.26.7/COPYING)
  and [README attribution](https://github.com/pymupdf/PyMuPDF/blob/1.26.7/README.md).
