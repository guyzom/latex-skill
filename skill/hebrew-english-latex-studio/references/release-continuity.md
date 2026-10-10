# Release continuity: two 4.16.0 builds, one 4.17.0

The recovery below is historical. Current releases use the unified public
identifier `hebrew-english-latex-studio`; the publication safeguards continue
to apply. Use the authoritative [release workflow](catalog-development.md#release-workflow).

## Observed problem and recovery

Two different development paths were delivered as `hebrew-lualatex-pdf-v4.16.0.skill`.
The first changed measured contents columns; the last changed source masking,
physical page checks and review cropping, but used v4.15.0 as its base. The last
archive therefore did not include the first fix. A version string alone was
not proof that all previously described changes were present.

v4.17.0 uses the last archive as its base and restores the first path's exact
patch from its evidence archive. Both sets of unit and runtime regressions are
wired into one harness and required by the release contract. No earlier test
counts are simply added to claim a new full pass: the combined final source
must be tested afresh.

Observed input hashes (SHA-256):

- v4.15.0 source archive: `a4976685866924768715f6b4121a88f8c39546c8469af49fa99a01120c8e6410`
- Last v4.16.0 source archive: `7c23bdbc7d79bf07b40e2a5fc31f8cf7a07629a937ba39d375d0af11a8252750`
- First v4.16.0 evidence archive: `469cf0f45bdb578f76920bb5e690b4d1aa250507d61669192f5eb096554fe878`

These identify the actual local input bytes, not a remote registry. The first
source archive itself was not available under a distinct preserved pathname;
recovery used its recorded source patch and the original v4.15.0 archive.

## Publication contract

`package_skill.py` retains deterministic ZIP ordering, timestamps and modes,
source-tree hygiene checks, and release validation. Publication changes:

1. A missing output is created atomically without replacing another entry.
2. An existing regular file with identical bytes is an idempotent no-op.
3. Different bytes, a symlink or a directory cause a conflict; the prior entry
   stays untouched. A file appearing after preparation is also not overwritten.
4. `--replace-existing` explicitly restores atomic replacement for scratch
   workflows; it replaces a symlink entry, never its target.

The temporary archive is created in the destination directory. Default
publication uses the filesystem's hard-link primitive for atomic no-replace
semantics; if unsupported, the tool fails rather than silently falling back to
an overwriting rename. Temporary files are removed on success or failure.

For a real new release, update `VERSION`, add the first matching CHANGELOG
heading and choose a fresh output directory and new versioned pathname. Follow
the [release workflow](catalog-development.md#release-workflow) for candidate
creation, complete matrix execution, actual primary-page review, evidence
sealing and candidate-bound FULL verification. Keep source bytes, modes and
file population unchanged after freezing; the final archive must match the
candidate's SHA-256. Any source change requires a new candidate and renewed
affected evidence. A routine FULL run or FAST pass is not release approval.

Intentional scratch replacement only:

```bash
python3 scripts/package_skill.py --output /tmp/draft.skill --replace-existing
```

This is not a global version reservation, an authentication system, or a
sandbox. Two different paths or external upload/copy tools can still carry the
same version. Release preparation assumes a trusted single-writer source tree.
Record the final archive SHA-256 and an exact source inventory in release
evidence; test a fresh extraction and compare it with that inventory.

## Coverage ownership

- `test_v4160.py`: 52 language/physical-size/review controls from the last build.
- `test_toc_layout.py`: 13 geometry controls; `--runtime` runs 13 real-engine
  controls, including native mixed-language caption lists and historical
  layout/direction mutations alongside the retained fixture variants.
- `test_v4170.py`: 21 publication, golden-process-status and cross-path continuity controls.
- `test_packaging.py`: real CLI archive creation, identical retry, changed-source
  conflict, explicit replacement, cleanup, and earlier hygiene mutations.

A static marker is not a visual correctness proof. Engine fixtures measure
number/title clearance and link destinations. Rendered pages still require
actual visual inspection, separately recorded for the exact PDF/image bytes.

## Golden tests must check process status

The old T1 block discarded the positive checker return code and only counted
printed lines for the clean fixture. A process that printed all expected flags
and then exited 2 could pass the positive block; a silent exit 2 could pass
the clean block. This was reproduced with harmless local stubs, not by breaking
the real checker or inferring a failure from its source alone.

The current block requires positive exit 1 and clean exit 0, in addition to
the expected flags and absence of unexpected findings. Six controls execute
that exact shell block in a temporary fixture project. They do not validate
all other shell blocks automatically; other gates retain their own tests.
