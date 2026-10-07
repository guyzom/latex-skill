#!/usr/bin/env python3
"""Regression-test the package documentation linters without shell capture.

The FAST harness used to exercise these seven contracts through Bash command
substitutions. Each linter was individually fast, but the cumulative harness
could stall at that shell-capture boundary in constrained environments. Keep
the same seven semantic assertions in one Python process and emit one PASS line
per contract so test_all.sh preserves its exact check count.
"""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import io
from pathlib import Path
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import lint_doc_examples  # noqa: E402
import lint_doc_links  # noqa: E402


def capture_examples(args: list[str]) -> tuple[int, str]:
    old_argv = sys.argv[:]
    out = io.StringIO()
    err = io.StringIO()
    try:
        sys.argv = [str(ROOT / "scripts" / "lint_doc_examples.py"), *args]
        with redirect_stdout(out), redirect_stderr(err):
            try:
                rc = int(lint_doc_examples.main())
            except SystemExit as exc:
                rc = int(exc.code or 0)
    finally:
        sys.argv = old_argv
    return rc, out.getvalue() + err.getvalue()


def capture_links(args: list[str]) -> tuple[int, str]:
    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            rc = int(lint_doc_links.main(args))
        except SystemExit as exc:
            rc = int(exc.code or 0)
    return rc, out.getvalue() + err.getvalue()


def require(condition: bool, message: str, detail: str = "") -> None:
    if not condition:
        if detail:
            print(detail.rstrip(), file=sys.stderr)
        raise AssertionError(message)
    print(f"PASS\t{message}")


def main() -> int:
    try:
        rc, out = capture_examples(["--docs", "tests/doc_examples_broken.md", "--min-blocks", "1"])
        require(
            rc == 1
            and "[ADJACENT-LTR-ISLANDS]" in out
            and "U+0008 '" in out
            and out.count("RAW-CONTROL-CHAR] U+0009") >= 2
            and "U+200F" in out
            and "U+200D" in out,
            "doc exemplars: broken probe matrix fires via bidi + charset + raw-control + invisible-bidi paths",
            out,
        )

        rc, out = capture_examples(["--docs", "tests/doc_examples_exempt.md", "--min-blocks", "1"])
        require(rc == 0, "doc exemplars: documented exemption matrix stays quiet", out)

        rc, out = capture_examples(["--docs", "tests/doc_examples_unbalanced.md", "--min-blocks", "1"])
        require(
            rc == 1 and "UNBALANCED-EXAMPLE-MARKER" in out,
            "doc exemplars: unclosed negative region is rejected",
            out,
        )

        rc, out = capture_examples([])
        require(rc == 0, "doc exemplars: SKILL.md + references teach only clean LaTeX", out)

        rc, out = capture_links(["--docs", "tests/doc_links_broken.md"])
        require(
            rc == 1
            and "LINK-TARGET-MISSING" in out
            and "ANCHOR-MISSING" in out
            and "LINK-ESCAPES-PACKAGE" in out,
            "doc links: broken fixture fires on missing file + missing anchor + package escape",
            out,
        )

        rc, out = capture_links(["--docs", "tests/doc_links_ok.md"])
        require(rc == 0, "doc links: Hebrew anchors, dedupe suffixes, relatives and external URLs stay valid", out)

        rc, out = capture_links([])
        require(rc == 0, "doc links: every operative package link and anchor resolves", out)
    except AssertionError as exc:
        print(f"FAIL\t{exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
