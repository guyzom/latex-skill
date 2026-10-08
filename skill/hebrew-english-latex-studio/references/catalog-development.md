# Catalog development and template maintenance

The catalog is the source of truth for document recipes. Runtime behavior
stays in the owning TeX assets, language choices stay in the language contract,
and managed compilation stays in the build contract. A recipe cannot grant
support for a document class or component combination the owners do not support.

למשתמש: [קטלוג התבניות](template-catalog.md) מסביר מה אפשר לבחור,
[מילון המושגים](glossary-he-en.md) מסביר את המונחים, ו[זרימת העבודה](everyday-workflow.md)
מסבירה יצירה, עריכה ובדיקה. המסמך הזה מיועד למפתח הסקיל.

## Sources of truth

| Information | Canonical owner | Derived consumers |
|---|---|---|
| Templates, native starter variants, layout/theme defaults, closed composer selection, examples and acceptance IDs | [studio-catalog.json](../registry/studio-catalog.json) | Resolver, generator, catalog Markdown, acceptance coverage |
| Schema validation and immutable resolution | [template_registry.py](../scripts/template_registry.py) | Read-only CLI, project generator, tests |
| Component roles, capabilities, public APIs, dependencies, conflicts and hook contracts | [architecture_contract.py](../scripts/architecture_contract.py) and each owning TeX asset | Runtime architecture guards, resolver validation, architecture documentation |
| Language profiles and resolution | `architecture_contract.LANGUAGE_PROFILE_SPECS` and the shared core | Registry, generator, runtime validation |
| Managed build configuration and checks | [build_contract.py](../scripts/build_contract.py) and [build.sh](../scripts/build.sh) | Recipe build defaults, generated wrapper, checks |
| Public terms and explanations | [glossary/terms.json](glossary/terms.json) | Generated Hebrew–English glossary |
| Release identity | [VERSION](../VERSION) | Skill metadata, generated docs, deterministic package |

Do not copy ownership tables into the registry. Refer to actual architecture
asset paths and let the owner validate their roles, dependencies and conflicts.
Likewise, reuse the language resolver and build keys rather than creating a
second list with different semantics. Generated catalog tables are views of
these owners; edit their source records instead of editing generated Markdown.

## Inspect and resolve without creating a project

Run from the actual extracted skill root:

```bash
python3 scripts/template_registry.py list --json
python3 scripts/template_registry.py validate --json
python3 scripts/template_registry.py resolve --kind paper --language english --json
python3 scripts/template_registry.py resolve --kind formula-sheet \
  --language bilingual --main-language hebrew --layout reference-readable --json
```

The Python entry point `load_catalog(root)` returns an immutable typed
`StudioCatalog`. Its `as_dict()` renders the canonical records for tools such as
the documentation generator. Resolution retains requested selections separately
from resolved choices and their provenance. It produces an immutable
`ResolvedRecipe`; it does not compile a document, install fonts or approve a PDF.

An explicitly requested theme takes precedence, then a non-null layout theme
default, then the template default, then the catalog default. Constraints still
apply: a reference layout requires `formula-sheet`, and `bilingual` requires an
explicit main language. Invalid selections are rejected before project creation.

Source paths are relative to the actual skill root. Registry data is declarative:
composer and handler IDs select a closed implementation dispatch in the
generator. They are not Python module names, shell commands or executable source.

## Add or revise a recipe

1. Choose a stable ID, Hebrew and English titles, purpose and advisory content
   profile. Select the supported layouts and presentation defaults. Keep genre,
   document class and language separate; the existing `report` kind still uses
   an `article` starter.
2. Provide the native Hebrew and English starters or reuse suitable existing
   sources. Record their exact hashes and owned literal hook declarations.
   Preserve meaningful language-specific layout differences. The loader inspects
   declared known hooks; it does not evaluate arbitrary TeX.
   Declare paragraph style according to genre, independently of theme and
   language. Use the core's pre-input `lakitparagraphstyle` hook rather than
   scattered `\noindent` patches. New non-paper starters use `block`; papers
   use `indented`. Reference environments own their local compact spacing.
3. Choose a supported content composer and any required source handler. Keep
   authored scientific content and translations in the starters. A new content
   composition strategy requires explicit implementation and tests; a registry
   string alone cannot create one.
4. Reference necessary architecture components and declare permitted hook
   overrides and managed build defaults. Copy plans identify project files;
   load plans identify TeX input order. Verify both, including dependencies and
   conflicts. Do not infer load order from copy order.
5. Add real documentation paths, relevant stable glossary IDs and acceptance
   case IDs. Review the current glossary definitions and add terms only when
   they help users or developers understand a public concept.
6. Increase `recipe_revision` when intentionally changing the recipe's authored
   content, defaults or composition. Explain the before/after behavior in the
   release history and retain the expected difference in compatibility evidence.
   Data-only migration that preserves the generated source is a separate claim.
7. Regenerate documentation, check links and execute the relevant tests and
   current build/render/review coverage before freezing a release candidate.

Review starter content as an example an author may imitate. Keep
editing instructions in comments or documentation. A finished sample should
demonstrate appropriate paragraph rhythm and purposeful components, without
requiring a quota of callouts or duplicating ordinary prose in a frame. Component
galleries may deliberately exercise nesting, repeated styles and synthetic
inputs; label their demonstration role and do not make their density a genre
default. Authored bilingual bodies should retain equivalent meaning; mixed
profiles do not require an unsolicited complete translation. Check opening
titles, salutations, closings, signatures and the return from language blocks
in the actual rendered output, not only the hook declaration.

Do not reuse an existing stable ID for an unrelated recipe. Do not overwrite
edited user projects as part of migration. The generator continues to reject an
existing destination. Compatibility adapters for historical Python constants
and `create(...)` derive their values from the same catalog.

## Add a component or hook

Reuse an existing owner when the requested behavior already exists. A new
source structure may need only a starter; a new preset may need only declared
values. Add a semantic, layout, page-shell or presentation asset only when a new
runtime responsibility warrants it. Maintain one shared `preamble.tex`.

For a shipped component, declare its role, prerequisites, capabilities, public
symbols and conflicts in the architecture contract. Update generated guards and
any compatibility carrier from their owning sources. Test forbidden combinations
in both load orders where appropriate. A locally authored theme need not become
a shipped component simply to create one project.

A public hook needs an owner, declaration timing, effective scope, value type,
unit and default contract. Keep defaults literal when literal, and symbolic when
they depend on another hook; a symbolic default is not an observed numeric
value. Validate numerical values as finite and within the owner's allowed range.
Mathematical size hooks use TeX points, preserve authored decimal spelling, and
must remain positive and ordered. Body and math sizes remain independent.

Pre-input core hooks are defined before `preamble.tex`; reference layout hooks
are defined before `reference_columns.tex`. Presentation overrides belong to the
documented mutable presentation hooks. Local language and mathematical settings
must restore correctly when their scopes end. A theme cannot replace direction
primitives, repair logic, component semantics or build checks.

## Creation metadata and compatibility

Generated `project.json` schema 3 preserves the existing fields and adds
`recipe` and `registry`. The recipe records the immutable resolved description.
The registry snapshot records its relative path, schema and SHA-256; its scope
is creation-time provenance. These fields do not validate subsequent edits,
compile a project or approve its rendered appearance.

The generator does not migrate existing schema 2 project files or require
edited projects to be regenerated. Consumers that support older creation
snapshots must preserve their historical meaning; missing provenance is unknown,
not a default that can be invented later.

Skill version, architecture schema, catalog schema, project schema and recipe
revision are distinct identifiers. A hash or starter fingerprint binds the data
covered by its definition. It does not prove PDF equality, scientific accuracy,
font identity, accessibility or visual approval. Exact build comparison also
needs source files, copied assets, effective build configuration, environment,
tools, packages and observed font files.

## Documentation and glossary maintenance

```bash
python3 scripts/generate_studio_docs.py
python3 scripts/generate_studio_docs.py --check
python3 scripts/test_studio_docs.py
python3 scripts/lint_doc_links.py
python3 scripts/lint_doc_examples.py
```

`generate_studio_docs.py` loads the canonical typed catalog and glossary records.
It validates the current release version, stable IDs, bilingual labels, related
terms, real source references and all glossary references declared by the
catalog. It generates `template-catalog.md` and `glossary-he-en.md`; `--check`
compares exact bytes and writes nothing. Both files must travel with their
canonical source records. Regeneration replaces each file atomically; the two
files are not one atomic transaction.

The glossary uses schema 2. Preserve term IDs when correcting labels or wording.
`introduced_in` refers to the first distributed glossary record, and `updated_in` to the
latest intentional review or change of its meaning, example, ownership or
source contract. Set `skill_version` to `VERSION` when releasing; do not claim
every term was reviewed merely because a version changed. The renderer cannot
infer a new concept's correct definition from code.

## Evidence required before release

| Change or claim | Required evidence |
|---|---|
| Registry schema or resolver | Positive/negative data and code tests, including duplicate keys/IDs, unknown fields, paths, references, finite values, constraint failures and immutable results |
| Compatibility migration | Fresh baseline/candidate generated-source, wrapper and copied-asset comparisons across the declared historical selection space; explicit allowed metadata differences |
| Intentional recipe change | Recipe revision, focused behavior tests and a reviewed list of semantic differences from the baseline |
| Runtime component or hook | Representative current engine fixtures, assertions on actual output and scope restoration where applicable |
| Template or visible component | Current managed build, every page rendered and individually viewed at readable resolution; actual observations tied to the PDF and rendered image hashes |
| Release package | Exact frozen candidate, successful current FULL and FAST runs, current catalog/example/component coverage, generated docs check, hygiene and deterministic archive verification |

Every declared acceptance ID needs actual coverage in the release evidence.
The current catalog has 49 closed acceptance IDs. Their allowed meanings are
owned by `catalog_coverage.acceptance_contract(catalog)`, and
`acceptance_coverage(root, catalog, plan, results=None, theme_filter=None)` binds
each required ID to the derived matrix requests and their canonical cases or
aliases. `theme_filter` is a keyword-only argument. Each binding records
`case`, `canonical_case`, `input_inventory_sha256` and
`build_fingerprint_sha256`; matching an ID string alone is insufficient.
Unknown IDs, uncovered required declarations, invalid aliases and changed
source/input identities fail coverage.

The default `theme_filter=None` requires the complete catalog and all 49 IDs.
The preserved `--theme` CLI option selects an exact subset of generated recipe
requests for local work; maintained examples and native component fixtures
remain mandatory. Only an unmatched, unselected generator-theme ID may be
marked `required=False` with `not-requested` status. Other missing cases remain
failures. The bridge records `coverage_scope`, `theme_filter`,
`required_acceptance_ids` and `not_requested_acceptance_ids` alongside the full
declaration count. A successful local subset may set
`scoped_acceptance_ids_pass=True`; `all_acceptance_ids_pass` stays false. Such
evidence cannot satisfy release verification or sealing, which require the
complete scope with no theme filter.

Without execution results, the bridge reports `declarations-only` scope and
`declared` status, with no runtime pass; unrequested IDs retain `not-requested`.
With results, every requested canonical case mapped to a required ID must pass
the actual managed build and both MuPDF and Poppler renders, retain the
expected input/build identity, and account for every
rendered page and its hash. The matrix result retains `acceptance_coverage`;
its declaration/pass counts and `acceptance_coverage_sha256` also bind the
release seal. `studio_matrix.verify_matrix` independently recomputes that
coverage and rejects a mismatch. This bridge keeps `visual_claim=False` and
does not replace actual primary-page review, replay or complete matrix
verification. Creation-time `project.json` metadata remains provenance only.

Adding an acceptance ID requires an intentional meaning in the closed contract,
a concrete mapping to the derived canonical cases and aliases, and meaningful
negative controls. Prove that an unknown or uncovered required ID, a changed
input or alias binding, missing or failed build/render results, and an invalid
or incomplete filtered population cannot produce a pass. Prove that a valid
local subset cannot claim complete acceptance or seal a release. A new
declaration cannot inherit acceptance from an unrelated passing case. The
canonical catalog, bridge, maintained tests and release evidence
must change together; extend their finite supported scope explicitly.

A declared case, a test fixture, a passing data check, a rendered PNG and a
human visual observation are different things. Count each honestly. A contact
sheet indexes pages and does not replace full-size page inspection. Extra
renderer comparisons should retain their own tool versions and evidence.

Do not relabel baseline PDFs, old receipts or partial tests as current candidate
evidence. Freeze the candidate before final tests; evidence must identify that
candidate and actual commands, exit codes, toolchain and outputs. A source
change after freezing needs a new candidate and renewed affected evidence.
Retain failures as diagnostics outside accepted evidence; do not hide them by
lowering a corpus count, skipping a gate or editing a successful receipt.

Build logs, PDFs, PNGs, review records and release evidence remain outside the
installable skill. Ship maintained sources, canonical records, generated docs
and executable tests. Scientific correctness, content completeness, PDF/UA and
untested viewer behavior are not implied by these checks.

## Release workflow

Complete deliberate source changes and focused regressions first. Update release
metadata, catalog revisions, generated guards, compatibility carriers and
glossary definitions before freezing. Regenerate and check documentation,
validate the catalog, and check the toolchain and source hygiene. Then create a
deterministic candidate outside the source tree:

```bash
python3 scripts/doctor.py
python3 scripts/template_registry.py validate --json
python3 scripts/generate_studio_docs.py --check
python3 scripts/check_package_hygiene.py
python3 scripts/package_skill.py --output /path/to/candidate.skill
STUDIO_RELEASE_CANDIDATE_SHA="$(python3 scripts/hash_file.py /path/to/candidate.skill)"
python3 scripts/test_studio_matrix.py --evidence-dir /path/to/new-matrix-evidence \
  --jobs 4 --candidate-sha "$STUDIO_RELEASE_CANDIDATE_SHA"
```

Keep all candidate source bytes, modes and file population unchanged throughout
the remaining work. A disposable exact extraction may be used for tests; its
source inventory must still match the archive. The matrix's default mode covers
the complete declared compositions, maintained examples and manual component
fixtures. `--theme` selects a useful subset for local work, and `--plan-only`
generates a source preview; neither satisfies the complete release requirement.

The retained matrix includes `case-plan.json`, `matrix-result.json`, source and
input inventories, managed build logs, output hashes and per-renderer manifests.
`matrix-result.json` identifies each unique case's PDF and renderer outputs.
Equivalent requests may share one build only when their effective sources,
copied assets, wrapper, build configuration and environment identity match.
The alias mapping must retain every covered request; request/provenance metadata
is retained even when it does not change the effective build. A case count is
not an engine invocation count or an approved-page count.

Open every unique primary MuPDF page at readable resolution. Primary manifests
are `cases/<id>/review-mupdf/review.json`; their images live in the same directory.
Use the paths in each case record rather than guessing case IDs. Record actual
observations with the existing API, repeating for the pages you viewed:

```bash
python3 scripts/render_review.py record /path/to/case/main.pdf \
  --review /path/to/case/review-mupdf/review.json --pages 1 \
  --reviewer "Reviewer name" --notes "Concrete observations from the actual page"
```

Pages start pending. Do not create a blanket approval or infer human review
from successful rendering. Poppler pages are separately rendered and pinned;
the presence of those images is not a claim that a reviewer viewed every
secondary page. Keep any additional human observations tied to their own
renderer, PDF and image hashes.

When all primary pages have actual review, seal the evidence. Sealing runs a
fresh primary same-backend replay and writes `matrix-release-receipt.json`
only after successful current verification:

```bash
python3 scripts/test_studio_matrix.py --seal /path/to/new-matrix-evidence \
  --candidate-sha "$STUDIO_RELEASE_CANDIDATE_SHA"
python3 scripts/test_studio_matrix.py --verify /path/to/new-matrix-evidence \
  --require-visual --candidate-sha "$STUDIO_RELEASE_CANDIDATE_SHA"
HEBREW_LATEX_CATALOG_MATRIX_EVIDENCE=/path/to/new-matrix-evidence \
HEBREW_LATEX_CATALOG_CANDIDATE_SHA="$STUDIO_RELEASE_CANDIDATE_SHA" \
  bash scripts/test_all.sh
FAST=1 bash scripts/test_all.sh
python3 scripts/check_package_hygiene.py
python3 scripts/package_skill.py --output /path/to/release/hebrew-english-latex-studio.skill
python3 scripts/hash_file.py /path/to/release/hebrew-english-latex-studio.skill
```

The read-only `--verify --require-visual` checks the existing seal without
creating new evidence files. FULL fails its catalog runtime gate when required
evidence or the exact candidate identity is missing.

A FULL run that is not a release declares itself with
`HEBREW_LATEX_CATALOG_VISUAL=routine`. Only the catalog visual gate is left
out, and the harness expects exactly one check fewer; every other FULL check
runs. The declaration is never implied: without it FULL fails as above, any
other value is rejected, partial evidence still fails, and complete evidence
is always verified. A routine run makes no claim about catalog pages and is not
release evidence. FAST checks source and
data contracts rather than approving the runtime matrix. Retain actual logs,
exit codes and full/fast receipts outside the source. Package creation checks
static contracts, not those execution receipts; verify them separately.

The final archive's SHA-256 must equal the candidate's. Check final archive
members, CRC and modes against the candidate, and retain the compatibility and
intentional-revision evidence as part of the reviewable release. If a source
change is needed after freezing, create a new candidate and renew affected
evidence instead of changing the identity on an older receipt.
