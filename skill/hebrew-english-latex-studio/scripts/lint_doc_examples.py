#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Original project code; scope and terms: ../LICENSING.md.
"""lint_doc_examples.py (v4.7.1) — run the skill's own linters on the LaTeX
exemplar blocks inside its documentation.

Why this exists: the docs' few-shot exemplars are what document authors copy
verbatim, but as fenced ``` blocks inside .md files they were invisible to
every lint gate. Two real bugs shipped that way and were caught only by a
human reader on a rendered page (v3.27.0: a trapped label colon taught as
"verified"; v3.27.1: unmerged adjacent \\code islands in the pipeline-keybox
exemplar). This script closes the class: every ```latex block in SKILL.md and
references/*.md must pass check_bidi_figures, check_charset, and the source
hazard checker in strict-layout mode.

v3.39.2: a checker's nonzero EXIT CODE now fails the gate even when its
output has no bracketed [FLAG] token. Until then only [FLAG]-shaped lines
counted, and check_charset reports stray codepoints WITHOUT such a token —
so an exemplar whose \\begin/\\toprule/\\textbf were destroyed into raw
control bytes (0x08/0x09, a non-raw Python string write) sailed through
while charset was screaming into the filter (shipped in
figures-boxes-listings.md; caught by a reader).

v3.39.3: an adversarial pass on the v3.39.2 fix found the residual case —
a \\t-only corruption (block with \\toprule/\\textbf but no \\b... macro)
still passed, because TAB is a legitimately ALLOWED codepoint in
check_charset (real .tex uses tabs in listings). Curated doc exemplars
never contain raw C0 controls (0-FP: 59/59 blocks scanned clean), so the
gate itself now flags any C0 control except newline in a ```latex block:
RAW-CONTROL-CHAR.

Conventions the docs must follow (and the script enforces):
  - A block that demonstrates a DELIBERATELY broken pattern is fenced
    ```latex-bad (not ```latex) — it is skipped here, and the fence itself
    tells the reader it is a counter-example.
  - Inside a mixed good/bad block, lines from a comment containing ❌ up to
    the next comment containing ✅ are the counter-example region and are
    skipped.
  - The script errors if it finds suspiciously few ```latex blocks (the
    extraction regex silently matching nothing must never look like a pass).

Usage:  python3 scripts/lint_doc_examples.py [--min-blocks N] [--docs F.md ...]
(--docs overrides the scanned doc list — used by the harness to prove the
script FIRES on tests/doc_examples_broken.md; pair it with --min-blocks 1.)
Exit 0 = every exemplar clean; 1 = flags found (printed with doc line numbers).
"""
import sys as _bytecode_sys
_bytecode_sys.dont_write_bytecode = True
import io
import pathlib
import re
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout

import check_bidi_figures as bidi_checker
import check_charset as charset_checker
import check_source_hazards as hazard_checker

HERE = pathlib.Path(__file__).resolve().parent
SKILL = HERE.parent
BIDI = HERE / "check_bidi_figures.py"
CHARSET = HERE / "check_charset.py"

DOCS = [SKILL / "SKILL.md"] + sorted((SKILL / "references").glob("*.md"))
FENCE = re.compile(r"^```latex\n(.*?)^```", re.M | re.S)
FLAG_LINE = re.compile(r"\[[A-Z][A-Z-]+\]")

MIN_BLOCKS = 39  # canonical v4.0 corpus size; a drop is a regression


def strip_negative_regions(block: str) -> tuple[str, list[str]]:
    keep, skipping, errors = [], False, []
    for number, line in enumerate(block.split("\n"), 1):
        if "❌" in line:
            skipping = True
        if "✅" in line:
            skipping = False
        if not skipping:
            keep.append(line)
    if skipping:
        errors.append("unclosed ❌ region at end of block")
    return "\n".join(keep), errors


def main() -> int:
    min_blocks = MIN_BLOCKS
    if "--min-blocks" in sys.argv:
        min_blocks = int(sys.argv[sys.argv.index("--min-blocks") + 1])
    docs = DOCS
    if "--docs" in sys.argv:
        docs = []
        for a in sys.argv[sys.argv.index("--docs") + 1:]:
            if a.startswith("--"):
                break
            docs.append(pathlib.Path(a))
    total_blocks, bad = 0, 0
    for doc in docs:
        text = doc.read_text(encoding="utf-8")
        for m in FENCE.finditer(text):
            total_blocks += 1
            snippet, marker_errors = strip_negative_regions(m.group(1))
            if marker_errors:
                bad += len(marker_errors)
                line_no = text[: m.start()].count("\n") + 1
                rel = doc.relative_to(SKILL) if doc.is_relative_to(SKILL) else doc
                for error in marker_errors:
                    print(f"✗ {rel}:{line_no} [UNBALANCED-EXAMPLE-MARKER] "
                          f"{error}")
            # RAW-CONTROL-CHAR (v3.39.3): C0 controls are never legitimate
            # in a curated exemplar — TAB is charset-allowed (real listings
            # tab), so a \t-only corruption has no other signal. Scanned on
            # the stripped snippet, same contract as the checkers (❌→✅
            # counter-example regions and ```latex-bad fences stay exempt).
            ctl = sorted({c for c in snippet if ord(c) < 32 and c != "\n"})
            if ctl:
                bad += len(ctl)
                line_no = text[: m.start()].count("\n") + 1
                rel = doc.relative_to(SKILL) if doc.is_relative_to(SKILL) else doc
                print(f"✗ {rel}:{line_no} exemplar block:")
                for c in ctl:
                    print(f"    [RAW-CONTROL-CHAR] U+{ord(c):04X} in a "
                          f"```latex block — a \\b/\\t/\\\\ eaten by a "
                          f"non-raw string write?")
            with tempfile.NamedTemporaryFile(
                    "w", suffix=".tex", delete=False, encoding="utf-8") as f:
                f.write(snippet)
                path = f.name
            try:
                # v4.3.1: invoke the exact checker entrypoints in-process.
                # The old implementation spawned 3 fresh interpreters for every
                # documentation block (39+ blocks), making a static FAST gate
                # disproportionately expensive. T1/T2e2 and the standing broken
                # fixtures still exercise the checker CLIs; this loop tests the
                # exemplar corpus, not Python process startup.
                checkers = (
                    # Exemplars are partial snippets with illustrative local
                    # paths, not a materialized project dependency graph.
                    (lambda argv: bidi_checker.main(argv, resolve_includes=False),
                     [str(BIDI), path]),
                    (charset_checker.main, [str(CHARSET), path]),
                    (hazard_checker.main, ["--strict-layout", path]),
                )
                for checker_main, checker_argv in checkers:
                    stdout = io.StringIO()
                    stderr = io.StringIO()
                    try:
                        with redirect_stdout(stdout), redirect_stderr(stderr):
                            rc = checker_main(checker_argv)
                    except SystemExit as exc:
                        rc = int(exc.code or 0)
                    checker_out = stdout.getvalue()
                    flags = [l for l in checker_out.splitlines()
                             if FLAG_LINE.search(l)]
                    n_findings = len(flags)
                    if rc != 0 and not flags:
                        # the checker failed without a bracketed [FLAG]
                        # (check_charset's stray-codepoint report) — the
                        # exit code is the signal; surface its findings,
                        # but count the FAILURE as one (context lines are
                        # not findings — v3.39.5, a review caught "20
                        # flags" reported for ~8 real ones)
                        n_findings = 1
                        flags = [l for l in checker_out.splitlines()
                                 if l.strip() and not set(l.strip()) <= {"-"}][:8]
                    if rc != 0 or flags:
                        bad += max(n_findings, 1)
                        line_no = text[: m.start()].count("\n") + 1
                        rel = doc.relative_to(SKILL) if doc.is_relative_to(SKILL) else doc
                        print(f"✗ {rel}:{line_no} exemplar block:")
                        for fl in flags:
                            print(f"    {fl.strip()}")
            finally:
                pathlib.Path(path).unlink(missing_ok=True)
    if total_blocks < min_blocks:
        print(f"✗ extractor found only {total_blocks} ```latex blocks "
              f"(expected >= {min_blocks}) — the fence regex or docs moved")
        return 1
    if bad:
        print(f"✗ {bad} flag(s) in documentation exemplars — the docs are "
              "teaching a bug (fix the exemplar, or fence a deliberate "
              "counter-example as ```latex-bad)")
        return 1
    print(f"✓ doc exemplars clean: {total_blocks} ```latex blocks pass "
          "bidi + charset + source hazards")
    return 0


if __name__ == "__main__":
    sys.exit(main())
