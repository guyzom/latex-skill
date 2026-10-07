# Startup and bilingual codebox contracts

## Scope of v4.28

This release extends the uploaded v4.27 lineage. It retains the canonical A4
paper default, external pinned fonts, separate architecture layers, existing
failed-PDF readability checks, and the 671-case source corpus. It does not
introduce an English-only document mode or change the six semantic callouts.

## Codebox gutter direction

`codebox` and `asmblock` express different boundaries. The box may begin in
Hebrew or in `englishprose`; the listing content itself is always left-to-right.
The physical number gutter depends on the outer box context. Snapshot that
context at entry, before `asmblock` selects English. For the English context,
apply `xleftmargin=26pt,xrightmargin=0pt` in a locally gated listing `PreInit` hook,
after the selected style has resolved. The original Hebrew branch is retained. Register this hook once: `listings`
uses global hook registration. Local box/language flags prevent the frame,
background and margins from leaking into subsequent unboxed listings.

The runtime regression renders all four bundled styles with line numbers
998, 999 and 1000, under Hebrew, English, and Hebrew again. It checks every
number against its own frame, not a distant leftmost stroke. Restoring the
old executable codebox setup must reproduce the Python/HTML English collision
and the lost frame on the following unboxed listing. The Hebrew frame crops before
and after the English box must remain pixel-identical to that mutation.

This is bounded evidence, not an unlimited digit-width promise. Narrow columns,
custom styles, five-or-more-digit labels, split boxes and unusually deep nesting
still require document-specific geometry and visual checks. A successful
compiler or geometry test is not a record of someone inspecting the pages.

## Nested containers since v4.29

The v4.28 standalone geometry and negative-control suite remains. Since v4.29,
all codebox margin overrides run inside the listing's `PreInit` scope, not the
outer codebox scope, and the nearest semantic callout suspends codebox styling
locally. Nested codeboxes restore the formatter saved by an outer semantic
callout. See [nested-container scope](nested-container-scope.md) for the added
matrix, explicit author overrides, split control, and bounded guarantees.

## Startup failures

`build.sh` deliberately uses `set -uo pipefail`. An unchecked command
substitution can therefore fail without stopping the script. Temporary-directory
allocation must be checked explicitly, and the resulting path must be nonempty
and name a directory before a cleanup trap or a derived path is used.

The static regression replaces `mktemp` and `mkdir` with harmless logging mocks.
It never attempts to create `/font-cache`. It proves the old PDF remains intact,
no engine is called, and a valid path containing spaces reaches the intended
private-cache branch. A valid allocation with a failing cache is a distinct
failure from an invalid allocation.

`DIRECT_NAVIGATION_DESTINATIONS` remains an optional comma-separated list of
nonempty shell-style globs. Empty leading, middle, trailing or whitespace-only
fields are rejected before runtime/font setup. Trailing commas need an explicit
check because Bash array reads discard their final empty field.

## Portable package paths

The release hygiene gate rejects reserved Windows device names (including
extensions and superscript-number forms), reserved path-component characters,
and trailing periods/spaces. Existing control-character, case/Unicode collision,
symlink, nested archive, font, credential-like and build-debris checks remain.
Unicode and Hebrew filenames are supported; no arbitrary global path-length
limit is imposed. A missing package directory is an error, not an empty package.

These checks follow Microsoft's [file naming rules](https://learn.microsoft.com/en-us/windows/win32/fileio/naming-a-file).
They are not a universal filesystem or secret audit. Crucially, the cleanup
sweeper still deletes only the narrowly defined generated artifacts; an unsafe
source filename is reported for a maintainer to rename, not automatically deleted.

## Run the regressions

```bash
python scripts/test_v4280.py
python scripts/test_v4280_runtime.py
FAST=1 bash scripts/test_all.sh
bash scripts/test_all.sh
```

The two direct suites use 14 and five unittest methods respectively. The full
harness includes both; FAST includes only the startup/path suite. These are
coverage definitions. Report actual run totals from the observed logs, not the
configured floor. Record renderer, DPI, exact PDF hash and inspected page range
separately with `render_review.py`.
