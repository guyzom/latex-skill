#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Original project code; scope and terms: ../LICENSING.md.
"""lint_doc_links.py — referential integrity of the package's own docs.

WHAT THIS GUARDS (v4.2.2). Two real incidents, one round apart:
  - pitfalls' "Hebrew SENTENCE inside display" row said "Full note in
    references/figures-boxes-listings.md" while no such note existed in that
    file — a content pointer that dangled for as long as nothing checked it,
    caught by hand and by luck.
  - the package used to point readers at repo-level documents that do not
    travel in the zip (fixed as its own commit; this linter is what keeps
    that self-containment true instead of re-drifting).

THE INVARIANT — referential integrity, deliberately NOT semantic
completeness: every markdown link in the OPERATIVE package docs resolves to
a real file inside the package, and, when it names a #fragment, to a real
heading in that file. A heading whose body is one TODO line still passes;
whether the note under a heading is worth pointing at stays a human
judgment. The convention this enforces is therefore: a content pointer is
an anchor link, and if you are not writing the note, do not write the
pointer.

Scope: SKILL.md + references/*.md. CHANGELOG.md is exempt by charter — it
is the narrative of the repo the skill grew in and legitimately names
repo-level files that do not ship. External links (a URL scheme) are
recorded facts about the world, not package dependencies, and are ignored.

Anchor algorithm: GitHub's — the rendered heading text, lowercased
(ASCII-wise; Hebrew has no case), everything that is not a Unicode
letter/digit/space/hyphen dropped, spaces to hyphens, and "-N" suffixes for
repeated headings. Verified against every live TOC anchor already in the
package (content-style.md, figures-boxes-listings.md, optional-features.md,
recipe.md) — those TOCs are the algorithm's regression corpus, scanned on
every run because they are ordinary links here.

Exit: 0 = every link resolves, 1 = findings (one line each), 2 = usage.
"""
import argparse
import os
import re
import sys
import unicodedata

PKG_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DOCS = ["SKILL.md"] + sorted(
    os.path.join("references", f)
    for f in (os.listdir(os.path.join(PKG_ROOT, "references"))
              if os.path.isdir(os.path.join(PKG_ROOT, "references")) else [])
    if f.endswith(".md")
)

FENCE_RE = re.compile(r"^(```|~~~)")
# standard inline link/image: [text](target "title")  /  ![alt](target)
LINK_RE = re.compile(r"!?\[[^\]]*\]\(\s*([^)\s]+)(?:\s+\"[^\"]*\")?\s*\)")
SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")


def _strip_fences(lines):
    """Yield (lineno, line) outside fenced code blocks; inline code spans
    blanked (a literal `[x](y)` inside backticks is an example, not a link —
    and a `#` heading inside a fence is code, not a heading)."""
    in_fence = False
    for i, line in enumerate(lines, 1):
        if FENCE_RE.match(line.strip()):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        yield i, re.sub(r"`[^`]*`", lambda m: " " * len(m.group(0)), line)


def _slug(text):
    """GitHub anchor slug of a heading's rendered text."""
    t = re.sub(r"`([^`]*)`", r"\1", text)              # inline code: keep content
    t = re.sub(r"[*_]{1,3}([^*_]+)[*_]{1,3}", r"\1", t)  # bold/italic markers
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", t)     # links: keep text
    t = t.strip().lower()
    out = []
    for ch in t:
        cat = unicodedata.category(ch)
        if cat.startswith(("L", "N")) or ch in "- _":
            out.append(ch)
    return "".join(out).replace(" ", "-").replace("_", "-")


def heading_slugs(path):
    """All anchor slugs of a markdown file, with GitHub's -N dedupe."""
    with open(path, encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    slugs, seen = set(), {}
    in_fence = False
    for line in lines:
        if FENCE_RE.match(line.strip()):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = re.match(r"(#{1,6})\s+(.*)", line)
        if not m:
            continue
        base = _slug(m.group(2))
        n = seen.get(base, 0)
        seen[base] = n + 1
        slugs.add(base if n == 0 else f"{base}-{n}")
    return slugs


def lint_file(relpath, findings):
    path = os.path.join(PKG_ROOT, relpath)
    with open(path, encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    here = os.path.dirname(path)
    for lineno, code in _strip_fences(lines):
        for m in LINK_RE.finditer(code):
            target = m.group(1)
            if SCHEME_RE.match(target):
                continue                       # external: not a dependency
            frag = ""
            if "#" in target:
                target, frag = target.split("#", 1)
            if target == "":
                tpath = path                   # same-file #anchor
            else:
                tpath = os.path.normpath(os.path.join(here, target))
                if os.path.commonpath([PKG_ROOT, tpath]) != PKG_ROOT:
                    findings.append(
                        f"{relpath}:{lineno}  [LINK-ESCAPES-PACKAGE] "
                        f"{m.group(1)} resolves outside the package — it "
                        f"will dangle in every extracted zip")
                    continue
                if not os.path.isfile(tpath):
                    findings.append(
                        f"{relpath}:{lineno}  [LINK-TARGET-MISSING] "
                        f"{m.group(1)} — no such file in the package")
                    continue
            if frag:
                if not tpath.endswith(".md"):
                    continue                   # fragment on non-md: file is enough
                if frag not in heading_slugs(tpath):
                    findings.append(
                        f"{relpath}:{lineno}  [ANCHOR-MISSING] "
                        f"#{frag} — no heading in "
                        f"{os.path.relpath(tpath, PKG_ROOT)} produces this "
                        f"anchor")


def main(argv):
    ap = argparse.ArgumentParser(
        description="Referential-integrity lint for the package docs: every "
                    "markdown link resolves to a file inside the package, "
                    "and every #fragment to a real heading. External URLs "
                    "ignored; CHANGELOG.md exempt (narrative).")
    ap.add_argument("--docs", nargs="+", metavar="FILE",
                    help="package-relative docs to lint (default: SKILL.md + "
                         "references/*.md)")
    args = ap.parse_args(argv)
    docs = args.docs or DEFAULT_DOCS
    findings = []
    for rel in docs:
        if not os.path.isfile(os.path.join(PKG_ROOT, rel)):
            print(f"❌ no such doc: {rel}")
            return 2
        lint_file(rel, findings)
    for f in findings:
        print(f)
    if findings:
        print(f"✗ {len(findings)} dangling reference(s).")
        return 1
    print(f"✓ doc links resolve: {len(docs)} file(s), every internal link "
          f"and anchor lands on a real target.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
