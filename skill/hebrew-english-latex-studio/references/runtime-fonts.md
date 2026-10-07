# Runtime font identity and Hebrew–English typography

Use the managed build, not family-name lookup as proof of which files were
used. The preamble binds the canonical Hebrew serif/sans and monospaced
families, plus their fallbacks, to `HEBREW_LATEX_FONT_DIR` or the documented
XDG/HOME installation. Their hashes are those in the current release's
`assets/fonts/SHA256SUMS`; fonts are external dependencies, not archive payload.

## Language-dependent selection

The default and explicit `hebrew` profile retain the historical family-selection
policy using the current release's pinned font bytes. This is not a claim of
pixel identity with pre-5.1.0 documents; the font-baseline migration is documented
in [studio setup](studio-setup.md#font-provenance-and-compatibility).
The `english`, `english-with-hebrew`, `hebrew-with-english`, and `bilingual`
profiles assign English prose to **Latin Modern Roman** and **Latin Modern
Sans**, with the actual Latin font faces available in the TeX distribution.
Hebrew retains its canonical families and short code retains the canonical
monospaced family. Both language bindings are available even when one language
has only a small role in the document.

Latin Modern is a toolchain dependency, not part of the pinned external Hebrew
font bundle. A release should record its TeX installation and native-English
build evidence. Do not describe Latin Modern or an author-selected custom font
as release-pin verified merely because a document passes the canonical-font
gate. The original `hebrew` profile intentionally remains a compatibility
baseline, including its established English-island typography; choosing
`hebrew-with-english` opts into native English font treatment.

## Reference mathematics

The opt-in `reference_columns.tex` layout separates prose size and baseline
from main, script and scriptscript mathematical sizes. Generated compact
sheets use 6.3/7.8 pt prose and 6.25/4.375/3.125 pt mathematics; generated
readable sheets use 9/11 pt prose and 8.75/6.125/4.375 pt mathematics.
Use [the reference-sheet declarations](reference-sheets.md) for authored
overrides and the direct-input defaults.

Computer Modern's optical designs differ in width, spacing and glyph shape.
The small designs can look wider relative to their height even when a PDF
applies no anisotropic transformation. Reference primary mathematics uses
the 10 pt designs, uniformly scaled to the declared mathematical size; its
ordinary scripts and scriptscripts use the 7 pt and 5 pt designs at their
separate declared sizes. Extended symbols and auxiliary alphabets use
explicit scalable TeX-distribution faces. This is native font selection,
not an image or box whose height or width has been adjusted independently.
The supplied PDFs inform the typography without adding their font binaries
or introducing an OpenType mathematical backend.

The layout registers distinct normal/bold reference math versions without
replacing the core's mathematical families. It activates the reference
selection and local size bindings only in `referencecolumns` and
`referencewide`. Standard documents and outer mathematics retain their
configuration, and explicit custom math-version requests remain distinct.
Changing a reference theme alone does not activate this mathematical policy.
Mathematics in bold reference headings uses the matching local bold version
while the reference layout is active.
Inspect both normal and bold formulas, math alphabets, accents, fractions,
delimiters, nested scripts and language boundaries in actual rendered pages.

These Computer Modern resources belong to the TeX distribution and remain
outside the external canonical-family hash pins, like other toolchain
mathematical fonts. Record the actual toolchain and observed font resources;
do not describe them as release-pin verified. Font substitution and missing
glyph checks still apply. Preserve the existing canonical font manifest and
runtime observation; no font binary or cache is included in the skill.

When typography appears flattened, compare the actual PDF's glyph transforms
and embedded font outlines rather than judging from a viewer screenshot
alone. Inspect the declared optical design, point size, script hierarchy and
prose baseline. A mathematical font's design-size name is not proof of its
rendered point size. Correct a disproportioned transformation if one exists;
otherwise select a suitable optical design and explicit uniform font sizes.
Do not compensate by stretching mathematical expressions or suppressing the
font checks. Review at intended print size as well as an enlarged rendering.

## Observed resources and verification scope

The `finish_pdffile` observation hex-encodes registered font filenames in one
framed log inventory. `check_runtime_fonts.py` requires a complete frame and
three canonical family anchors. Each canonical entry must resolve to the
selected physical path and match its release SHA-256. The inventory reports
additional custom/math/toolchain fonts as `uncontrolled`; resources without a
filename are counted separately. These resources remain outside canonical hash
verification. Registered faces may be unused; embedded PDF subset bytes are
not checked by this gate.

The ordinary missing-glyph and font-substitution gates still apply to the whole
document. Passing those checks does not prove correct script coverage in a
face that the document never exercised. Inspect emphasis, weights, punctuation,
Hebrew/English transitions and font embedding for the actual content.

A private `TEXMFCACHE` and `TEXMFVAR` are created per managed build, reused
between passes and removed on cleanup. This prevents an old OTF cache filename
from masking relocated identical files. The caller's global cache is not
cleared or edited. Initial cache loading repeats per build; `openout_any`
restrictions are not relaxed.

The observation is checked after every compile, including `REPRO`, and again
before atomic publication. Missing observations, wrong canonical paths (even
with identical bytes), and hash mismatches are failures; the prior deliverable
remains intact. Exit 0 means verified or explicitly non-core/not-applicable,
1 means findings, and 2 means an input/tool failure. Not-applicable is not a
pinned-font claim.

A missing observation has three causes, and since 4.26.0 the checker names the
one the log proves. LuaTeX runs `finish_pdffile` only when it finishes a PDF
with at least one page, so a compile that stopped on an error has no inventory
even if pages had shipped: the log ends in the engine's fatal-error line, and
the message says the compile stopped before the end of the document.
`build.sh` has already printed that error, with TeX's `l.N` line, before this
check runs. An empty document compiles and logs "no pages of output"; the
message says so. Only a finished compile without the frame means an outdated
preamble, and only then does the message ask to synchronize `preamble.tex`.
The verdict is a failure in all three cases; only the reason differs.

## Custom typography

A project can add explicit language-specific `babelfont` overrides when its
design needs them. Record physical font files, versions, licenses and required
faces separately, and test representative content. Keep canonical pins intact;
a custom installation manifest cannot replace the skill's source of trust.
Do not disable runtime observation or weaken source/glyph checks to make a
font substitution pass. Read [language and design](language-design.md) for
package/load-order and supported-character boundaries.

Existing projects must inspect local modifications before synchronizing the
core. Raw engine experiments do not run the managed gates; use a fresh private
cache and invoke the checker explicitly if recording such evidence.

These checks require trusted, stable sources and toolchain. They are not a
sandbox, protection against malicious Lua/TeX, or a concurrent-mutation
security guarantee. Paths with spaces and Hebrew have regression coverage;
bracket/control-containing paths are rejected. No universal Windows/path
compatibility is claimed. Release/evidence archives must not include raw font
programs or font-cache tables.

The original font-identity regressions are `test_v4220.py` and
`test_v4220_runtime.py`; full QA runs both and FAST runs only the first.
`HLLPDF_422_EVIDENCE_DIR` retains diagnostic cases in a new external directory;
fonts/caches stay separate disposable data. Language-profile integration adds
native English evidence; it does not retroactively change the original tests'
scope.

Primary API reference: [fontspec file-based font selection](https://github.com/latex3/fontspec/blob/main/fontspec-doc-fontsel.tex).

Version 5.1.0 refreshes the font-byte baseline deliberately; see [studio setup](studio-setup.md) for immutable upstream sources and migration implications. Legacy pins are provenance only.
