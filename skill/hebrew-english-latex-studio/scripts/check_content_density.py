#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Original project code; scope and terms: ../LICENSING.md.
"""Profile-aware advisory checks for document balance.

A heuristic guard on content BALANCE, pushing both ways:
  * against THIN output in opted-in teaching profiles — sparse content:
    long prose chapters, few numbered equations or exercises; and
  * against OVER-BOXED output — the page stuffed into colored boxes instead
    of free prose / standalone numbered equations / unframed tables. Two separate
    overuse advisories were calibrated from an earlier teaching corpus
    (v3.28). Those observations are not minimums or design targets:
    zero emphasis boxes is valid. EMPHASIS boxes
    (defbox/thmbox/notebox/warnbox/keybox) trigger
    [OVER-BOX-EMPHASIS] above 25%; exbox is exercise FORMAT,
    counted only toward the profile-specific combined wallpaper guard
    (>55%); optional table frames are neutral data containers, excluded from
    semantic emphasis counts;
  * and against CODE-FRICTION (v3.24) — a multi-token code expression embedded
    inline in a Hebrew prose sentence (\\code{lw $t1, -4($t0)} mid-sentence)
    zigzags the reader RTL<->LTR and, being an unbreakable island, line-breaks
    badly. Inline code is for single atoms; expressions get a \\codeline
    (content-style §5b).

This is NOT a hard gate. Universal reading-friction and emphasis-box checks run
for every profile; genre-specific structure/rhythm budgets run only when their
profile enables them.

Usage:
    python3 check_content_density.py --profile study-guide doc.tex [doc2.tex ...]
"""
import sys as _bytecode_sys
_bytecode_sys.dont_write_bytecode = True
import argparse
import os
import re
import sys

from build_contract import CONTENT_PROFILES as PROFILES, normalize_section_macros

# The generic profile deliberately avoids genre quotas. It still reports
# universal RTL/code/derivation friction and excessive use of semantic emphasis
# boxes. Explicit profiles opt into advisories suited to their purpose.
PROFILE_POLICY = {
    "generic":       dict(thin=False, exercises=False, rhythm=False, combined=False),
    "study-guide":   dict(thin=True,  exercises=True,  rhythm=True,  combined=True),
    "report":        dict(thin=True,  exercises=False, rhythm=True,  combined=True),
    "exam":          dict(thin=False, exercises=False, rhythm=False, combined=False),
    "formula-sheet": dict(thin=False, exercises=False, rhythm=False, combined=False),
    "review-sheet":  dict(thin=True,  exercises=False, rhythm=True,  combined=True),
}

# Targets calibrated on two real reference documents: a ~100-page Hebrew study
# anthology (prose + derivations, many numbered equations) and a 37-chapter
# computer-architecture formula sheet (formulas carried in tables/boxes). Both are
# dense on TOTAL structure (>2 mapped elements/chapter) though they differ wildly
# in numbered-equation count — hence the structure-based threshold below.
# "Thin" is measured on TOTAL mapped structure, not numbered equations alone — a
# formula sheet / reference card legitimately carries its formulas in tables and
# boxes, so counting only \begin{equation} would false-flag it as thin (it did:
# the 37-chapter reference formula sheet scores 0.46 numbered-eq/ch but 2.7 mapped
# elements/ch — dense). Count equations + tables + boxes together.
STRUCT_PER_CHAPTER_MIN = 1.2  # < ~1.2 (numbered eqs + tables + boxes)/chapter = thin
MAX_PROSE_PARAS_RUN = 4       # 4+ consecutive prose paras = WARN (guideline is 3;
                              # warn at 4 to avoid flagging legit intro/foundation
                              # chapters that are prose-heavy by design)
CHAPTERS_FOR_EXERCISE = 8     # docs with >= this many chapters should have exercises
# Balance guard — the checker must push BOTH ways (thin AND over-boxed):
BOX_CONTENT_FRAC_MAX = 0.55   # >55% of body content inside ANY colored box (incl.
                              # exbox) = wallpaper; exam collections peak ~36%
# v3.28 (reader recalibration): emphasis boxes are a SEPARATE, much smaller
# budget. Measured across the ten shipped lakits: 5-16% of content lines,
# median ~12% — the old "~1/3 is balanced" figure lumped exercise boxes in and
# overstated it by 2-3x. Emphasis works by contrast; at a third of the page it
# is wallpaper and friction.
EMPH_BOX_FRAC_MAX = 0.25      # >25% inside defbox/thmbox/notebox/warnbox/keybox
                              # = [OVER-BOX-EMPHASIS] (advisory)


# CODE-FRICTION (v3.24): an inline \code{}/\texttt{} whose content has a space
# AND an operator/comma/paren and is at least this long is a multi-token
# expression, not an atom — it belongs on a \codeline (content-style §5b).
# Only Hebrew-prose lines are scanned: friction is an RTL<->LTR phenomenon;
# code inside an English/LTR context (tables in otherlanguage, listings) is fine.
# Calibrated on a real post-sweep lakit: 12+ chars keeps short judged atoms
# (register pairs `\$t0, \$t1`, tight bindings `power = 4`) silent; content
# with \dots is an elided REFERENCE to a listing line, not an expression.
CODE_FRICTION_MIN_LEN = 12
CODE_FRICTION_SHOWN_PER_FILE = 5


# BOX-FRICTION (v3.43): a colored box whose body is a PROSE WALL of inline
# technical islands — a component-time value list, a path chain, a sum —
# with NO structural element inside (center / display math / \codeline /
# tabular / itemize). Reader report #5, the lecture-times exbox: CONTENT
# density is the goal, SETTING density is friction — and inside a box it
# reads worst (narrower measure: ~18pt lost to inner margins + frame; a
# tinted background raises perceived texture; and every inline island is
# an RTL<->LTR saccade). The fix is vertical: each technical citizen
# (chain / sum / value list / code expression) gets its OWN display line,
# and the box grows a few lines — lines are cheap, friction is expensive
# (content-style §4 golden rule 2 + §5b). Advisory, like CODE-FRICTION.
# The wall SIGNATURE is inline STRUCTURE-CITIZENS, not island count: plain
# prose numbers ($14$, $2.5\%$) and term mentions (\en{AMAT}) are normal
# academic writing and stay silent (calibrated: a question box with 9 term
# islands and a תיקון-למקור note both read fine). What fires is a VALUE
# LIST (4+ unit-values like 2ns/512B/100ps), an ARROW CHAIN (3+ \to), or an
# inline SUM (3+ +/- operators in one math run) — crammed into box prose.
BOX_FRICTION_MIN_LINES = 3     # walls, not one-liners
BOX_FRICTION_MIN_UNITS = 4     # the reported box carries 6 (2ns..0.5ns)
BOX_FRICTION_MIN_ARROWS = 3
BOX_FRICTION_MIN_SUMOPS = 3
# Atomic reference cards are structural formats. They share the prose-wall
# advisory with existing boxes, but do not acquire an emphasis-color quota.
# referenceqaseries itself is an unframed sequence; its authored solution parts
# are the concrete frames counted here. Macro-generated frames are not guessed.
REFERENCE_BOX_NAMES = (
    "referencenote", "referencewarning", "referenceformula", "referenceqa",
    "referencesolutionpart",
)
BOX_NAMES = ("defbox", "thmbox", "notebox", "exbox", "warnbox", "keybox") + REFERENCE_BOX_NAMES
BOX_STRUCT_PAT = re.compile(
    r"\\begin\{(?:center|tabular\*?|itemize|enumerate|lstlisting|"
    r"align\*?|equation\*?|asmblock)\}|\\\[|\\codeline|\\\\")
BOX_OPEN_PAT = re.compile(
    r"\\begin\{(" + "|".join(BOX_NAMES) + r")\}")
BOX_CLOSE_PAT = re.compile(
    r"\\end\{(?:" + "|".join(BOX_NAMES) + r")\}")
UNIT_VALUE_PAT = re.compile(r"^\d+(?:\.\d+)?\s*[A-Za-z]{1,4}$")


def box_friction(raw: str):
    """Yield (start_lineno, reason, body_lines) for prose-wall boxes."""
    hits = []
    cur = None          # (start_lineno, [body lines])
    for i, line in enumerate(mask_literal_blocks(raw, preserve_lines=True).splitlines(), 1):
        l = re.sub(r"(?<!\\)%.*$", "", line)
        if cur is None:
            m = BOX_OPEN_PAT.search(l)
            if m:
                rest = l[m.end():]
                # strip a frametitle/options header on the \begin line
                rest = re.sub(r"frametitle=\{(?:[^{}]|\{[^{}]*\})*\}", "", rest)
                rest = re.sub(r"^\s*\[[^\]]*\]?", "", rest.strip())
                cur = (i, [rest] if rest.strip() else [])
            continue
        if BOX_CLOSE_PAT.search(l):
            start, body = cur
            cur = None
            joined = " ".join(body)
            if (len(body) >= BOX_FRICTION_MIN_LINES
                    and not BOX_STRUCT_PAT.search(joined)
                    and re.search(r"[א-ת]", joined)):
                units = sum(1 for m2 in re.finditer(
                    r"\\en\{([^{}]*)\}", joined)
                    if UNIT_VALUE_PAT.match(m2.group(1).strip()))
                # a CHAIN is 3+ arrows in ONE math run — scattered single
                # arrows (reaction mentions, limits, merged 2-item units)
                # are normal prose and stay silent (calibrated)
                arrows = max((s.count("\\to")
                              for s in re.findall(r"\$([^$]+)\$", joined)),
                             default=0)
                # a NUMERIC sum (digit±digit runs), not particle charges
                # ($e^{+}e^{-}$) or sign superscripts — calibrated FP class
                sums = any(len(re.findall(r"\d\s*[+-]\s*\d", s))
                           >= BOX_FRICTION_MIN_SUMOPS
                           for s in re.findall(r"\$([^$]+)\$", joined))
                # inline NUMBERED items — (1)...(2)...(3) crammed into box
                # prose (reader report #5b: "גם דברים ממוספרים — אין סיבה
                # לא למשוך לעוד שורות"); the fix is an enumerate, one item
                # per line. 21 exercise boxes carried this in one lakit.
                numbered = len(set(re.findall(r"\\textbf\{\((\d)\)\}",
                                              joined)))
                reasons = []
                if units >= BOX_FRICTION_MIN_UNITS:
                    reasons.append(f"{units} inline unit-values")
                if arrows >= BOX_FRICTION_MIN_ARROWS:
                    reasons.append(f"a {arrows}-arrow chain")
                if sums:
                    reasons.append("an inline sum")
                if numbered >= 3:
                    reasons.append(f"{numbered} inline numbered items")
                if reasons:
                    hits.append((start, " + ".join(reasons), len(body)))
            continue
        if l.strip():
            cur[1].append(l)
    return hits


# DERIVATION-CHAIN (v3.26): a Hebrew prose line stringing SEVERAL distinct
# derivation steps — 2+ therefore-arrows (\Leftarrow) and 3+ inline math
# runs. Content density is information per PAGE, not claims per LINE: each
# step is a separate claim and reads far better on its own line (list /
# one-step-per-line). Advisory, like CODE-FRICTION.
DERIVATION_ARROWS_MIN = 2
DERIVATION_MATHS_MIN = 3


def derivation_chains(raw: str):
    hits = []
    in_listing = False
    # v3.32: PARAGRAPH-scoped, not line-scoped — the rule's own broken
    # exemplar evaded it when the source line was wrapped (a source newline
    # is a space in TeX; the rendered overload is per paragraph). Lines are
    # accumulated into blank-line-delimited paragraphs; one hit per paragraph.
    para, para_start = [], None
    def flush():
        if not para:
            return
        joined = " ".join(para)
        if re.search("[א-ת]", joined):
            arrows = joined.count("\\Leftarrow")
            maths = len(re.findall(r"\$[^$]+\$", joined))
            if arrows >= DERIVATION_ARROWS_MIN and maths >= DERIVATION_MATHS_MIN:
                hits.append((para_start, arrows, maths))
        para.clear()
    for i, line in enumerate(raw.splitlines(), 1):
        if re.search(r"\\begin\{(lstlisting|verbatim)\}", line):
            in_listing = True
            flush(); para_start = None
            continue
        if re.search(r"\\end\{(lstlisting|verbatim)\}", line):
            in_listing = False
            continue
        if in_listing:
            continue
        l = re.sub(r"(?<!\\)%.*$", "", line)
        # itemize/enumerate items are the ADVISED form — each \item is its
        # own logical line, so item lines break the accumulation.
        if not l.strip() or re.match(r"\s*\\(?:item|begin|end)\b", l):
            flush(); para_start = None
            continue
        if para_start is None:
            para_start = i
        para.append(l)
    flush()
    return hits


def code_friction(raw: str):
    """Yield (lineno, content) for multi-token inline code in Hebrew prose lines.
    Skips lstlisting/verbatim bodies and lines that already use \\codeline."""
    hits = []
    in_listing = False
    for i, line in enumerate(raw.splitlines(), 1):
        if re.search(r"\\begin\{(lstlisting|verbatim)\}", line):
            in_listing = True
            continue
        if re.search(r"\\end\{(lstlisting|verbatim)\}", line):
            in_listing = False
            continue
        if in_listing:
            continue
        l = re.sub(r"(?<!\\)%.*$", "", line)
        if "\\codeline" in l:
            continue
        if not re.search(r"[א-ת]", l):
            continue
        for m in re.finditer(r"\\(?:code|texttt)\{([^{}]*)\}", l):
            c = m.group(1)
            c = c.strip()
            if (" " in c and re.search(r"[=,+\-()\[\]]", c)
                    and len(c) >= CODE_FRICTION_MIN_LEN
                    and "\\dots" not in c):
                hits.append((i, c))
    return hits


def strip_comment_line(line: str) -> str:
    """Drop a real TeX comment while respecting backslash parity."""
    for i, ch in enumerate(line):
        if ch != "%":
            continue
        backslashes = 0
        j = i - 1
        while j >= 0 and line[j] == "\\":
            backslashes += 1
            j -= 1
        if backslashes % 2 == 0:
            return line[:i]
    return line


LITERAL_OPEN_PAT = re.compile(
    r"\\begin\{((?:lstlisting|verbatim|Verbatim)\*?)\}"
)


def mask_literal_blocks(text: str, *, preserve_lines: bool = False) -> str:
    """Replace literal bodies with one structural marker for rhythm metrics.

    Blank lines inside a listing are code layout, not prose paragraphs. Keeping
    only the environment markers preserves the fact that the listing interrupts
    a prose run without letting its body create phantom paragraphs. Structure is
    detected only after comments are stripped, while an end marker is sought in
    the raw literal line because percent is rendered content there.
    preserve_lines keeps omitted literal lines blank for source diagnostics;
    the default continues to collapse them for paragraph-rhythm metrics.
    """
    out = []
    in_literal = None
    for raw in text.splitlines():
        if in_literal:
            end = re.search(r"\\end\{" + re.escape(in_literal) + r"\}", raw)
            if end:
                out.append(r"\end{lstlisting}"
                           + strip_comment_line(raw[end.end():]))
                in_literal = None
            elif preserve_lines:
                out.append("")
            continue

        line = strip_comment_line(raw)
        begin = LITERAL_OPEN_PAT.search(line)
        if not begin:
            out.append(line)
            continue

        env = begin.group(1)
        end = re.search(r"\\end\{" + re.escape(env) + r"\}", raw[begin.end():])
        prefix = line[:begin.start()]
        if end:
            cut = begin.end() + end.end()
            out.append(prefix + r"\begin{lstlisting}\end{lstlisting}"
                       + strip_comment_line(raw[cut:]))
        else:
            out.append(prefix + r"\begin{lstlisting}")
            in_literal = env
    return "\n".join(out)


def box_balance(text: str):
    """Fractions of body content lines inside colored boxes, split (v3.28)
    into two observations: (emphasis_frac, combined_frac). Emphasis =
    defbox/thmbox/notebox/warnbox/keybox; combined also counts exbox
    (exercise format). These fractions have no minimum or recommended target;
    the caller applies separate overuse advisories. Table containers, including
    optional frames, are intentionally NOT counted in either — they hold data
    rather than semantic emphasis. See content-style §4.
    (A back-to-back box-CHAIN count was tried and dropped: on the reference doc
    it false-flagged legitimate patterns — a theorem→example→note unit and a
    series of exercise boxes — so it is not a reliable automated signal.)"""
    emph_names = r"defbox|thmbox|notebox|warnbox|keybox"
    emph_start = re.compile(r"\\begin\{(?:" + emph_names + r")\}")
    emph_end = re.compile(r"\\end\{(?:" + emph_names + r")\}")
    ex_start = re.compile(r"\\begin\{exbox\}")
    ex_end = re.compile(r"\\end\{exbox\}")
    # v3.29: count OPENS and CLOSES per line instead of continue-ing on the
    # first marker. The old shape had a proven double inversion: a one-line
    # \begin{notebox}...\end{notebox} incremented the depth and skipped the
    # \end (every later prose line counted as "inside a box" -> a 93% FP on an
    # exemplary page), while box content written ON the \begin line was never
    # counted at all (five fat one-line boxes measured 0% -> FN). A line's
    # content is inside a box if the box was already open OR opens on it; the
    # markers themselves (plus a leading [options] group) are not content.
    emph_depth = ex_depth = in_emph = in_any = total = 0
    opt_open = False   # inside a multi-line \begin{box}[ ... ] option header
    for line in text.split("\n"):
        e_open = len(emph_start.findall(line))
        e_close = len(emph_end.findall(line))
        x_open = len(ex_start.findall(line))
        x_close = len(ex_end.findall(line))
        in_e_here = emph_depth > 0 or e_open > 0
        in_x_here = ex_depth > 0 or x_open > 0
        emph_depth = max(0, emph_depth + e_open - e_close)
        ex_depth = max(0, ex_depth + x_open - x_close)
        s = emph_start.sub("", line)
        s = emph_end.sub("", s)
        s = ex_start.sub("", s)
        s = ex_end.sub("", s)
        # v3.32: a frametitle value may itself contain ']' (e.g. {מערך a[0]});
        # blank the brace-balanced group FIRST so the option strip below does
        # not stop early and leave a phantom "}]" content line.
        s = re.sub(r"frametitle=\{(?:[^{}]|\{[^{}]*\})*\}", "", s)
        s = re.sub(r"^\s*\[[^\]]*\]?", "", s.strip())  # \begin's [options...]
        # v3.32: a multi-line \begin{box}[ ... ] header — option lines up to
        # the closing ']' are syntax, not content (they inflated the emphasis
        # fraction 50%->64% on a probe).
        if opt_open:
            if "]" in line:
                opt_open = False
            s = ""
        elif (e_open or x_open) and re.search(r"\[[^\]]*$", line):
            opt_open = True
        if s.strip():  # comments already stripped -> blank
            total += 1
            if in_e_here:
                in_emph += 1
            if in_e_here or in_x_here:
                in_any += 1
    if not total:
        return 0.0, 0.0
    return in_emph / total, in_any / total



def section_invocation_pattern(custom_macros=()) -> re.Pattern:
    """Match real section invocations, not ``\\newcommand{\\name}``."""
    alternatives = [r"section\*?"]
    alternatives.extend(re.escape(name) + r"\*?" for name in custom_macros)
    return re.compile(
        r"\\(?:" + "|".join(alternatives) + r")\s*"
        r"(?:\[[^\]]*\]\s*)?\{")


def structural_container_counts(text: str):
    """Count literal cards and tables in comment/literal-masked source.

    Semantic table wrappers retain their historical count. A bare tabular is a
    table only when it is outside a semantic table or another tabular, so an
    implementation nested in an optional frame/flowtable is not counted twice. This is
    an advisory source scan, not TeX macro expansion or a rendered frame count.
    """
    table_wrappers = {"tablebox", "framedtable", "semanticframedtable", "flowtable"}
    tabular_names = {"tabular", "tabular*"}
    table_ancestors = table_wrappers | tabular_names
    stack = []
    tables = boxes = 0
    for match in re.finditer(r"\\(begin|end)\{([^{}]+)\}", text):
        action, environment = match.groups()
        if action == "begin":
            if environment in table_wrappers:
                tables += 1
            elif (environment in tabular_names
                  and not any(parent in table_ancestors for parent in stack)):
                tables += 1
            if environment in BOX_NAMES:
                boxes += 1
            stack.append(environment)
        elif environment in stack:
            # Recover conservatively from an unmatched intermediate marker;
            # the compiler, rather than this advisory, owns syntax validity.
            del stack[len(stack) - 1 - stack[::-1].index(environment):]
    return tables, boxes


def main(paths, profile="generic", section_macros=()):
    policy = PROFILE_POLICY[profile]
    print(f"INFO: content profile = {profile} (advisory).")
    text = ""
    friction_total = 0
    read_failures = 0
    for p in paths:
        try:
            with open(p, encoding="utf-8") as f:
                raw = f.read()
        except (OSError, UnicodeDecodeError) as e:
            # v3.33.1: unreadable input must NOT exit 0 — a typo'd path used
            # to "pass" silently (robustness audit).
            print(f"ERROR: cannot read {p}: {e}")
            read_failures += 1
            continue
        text += "\n" + raw
        hits = code_friction(raw)
        friction_total += len(hits)
        for i, c in hits[:CODE_FRICTION_SHOWN_PER_FILE]:
            print(f"{p}:{i}: [CODE-FRICTION] multi-token code inline in Hebrew "
                  f"prose: \\code{{{c}}} — give the expression its own "
                  f"\\codeline (content-style §5b); inline code is for atoms.")
        if len(hits) > CODE_FRICTION_SHOWN_PER_FILE:
            print(f"{p}: [CODE-FRICTION] ... and {len(hits) - CODE_FRICTION_SHOWN_PER_FILE} more in this file.")
        for i, reason, blines in box_friction(raw):
            print(f"{p}:{i}: [BOX-FRICTION] a box body of {blines} prose lines "
                  f"cramming {reason} inline, with no display/list/table "
                  f"inside — give each chain/sum/value-list its own line "
                  f"(center / \\codeline / table); lines are cheap, friction "
                  f"is expensive (content-style §4 rule 2, §5b).")
        for i, arrows, maths in derivation_chains(raw):
            print(f"{p}:{i}: [DERIVATION-CHAIN] {arrows} therefore-arrows and "
                  f"{maths} math runs in ONE prose paragraph — distinct "
                  f"derivation steps read better one-per-line, as an itemize "
                  f"with bold labels (content-style §5d).")
    text = mask_literal_blocks(text)

    section_pat = section_invocation_pattern(section_macros)
    if section_macros:
        rendered = ", ".join("\\" + name for name in section_macros)
        print(f"INFO: custom section macro(s): {rendered}.")

    chapters = len(re.findall(r"\\chapter\b", text))
    # numbered equations only (equation / align, not starred / not display \[ \])
    numbered_eq = len(re.findall(r"\\begin\{(equation|align|gather|multline)\}", text))
    tables, boxes = structural_container_counts(text)
    exercises = len(re.findall(r"\\begin\{exbox\}\[[^\]]*frametitle=\{?\s*תרגיל", text))
    parts = len(re.findall(r"\\part\b", text))

    warns = []

    # v3.33: an article doc maps the chapter rhythm 1:1 onto sections
    # (SKILL.md step 1) — so the density gate maps with it instead of
    # self-disabling (the newly-recommended article route silently lost the
    # thin-output guard; found by the article E2E audit).
    sec_unit = False
    if chapters == 0:
        sections = len(section_pat.findall(text))
        if sections >= 2:
            chapters = sections
            sec_unit = True
            print(f"INFO: no \\chapter — article doc; density measured "
                  f"per-section ({sections} sections).")
    if chapters == 0:
        print("INFO: no \\chapter and <2 sections — chapter-level checks skipped.")
    else:
        unit = "section" if sec_unit else "chapter"
        units = "sections" if sec_unit else "chapters"
        unit_short = "sec" if sec_unit else "ch"
        eq_ratio = numbered_eq / chapters
        tbl_ratio = tables / chapters
        box_ratio = boxes / chapters
        struct_ratio = (numbered_eq + tables + boxes) / chapters
        print(f"INFO: {parts} parts, {chapters} {units}, {numbered_eq} numbered "
              f"equations ({eq_ratio:.2f}/{unit_short}), {tables} tables "
              f"({tbl_ratio:.2f}/{unit_short}), {boxes} boxes "
              f"({box_ratio:.2f}/{unit_short}), {exercises} exercises.")
        print(f"INFO: {struct_ratio:.2f} mapped structural elements per {unit} "
              f"(equations + tables + boxes; advisory reference {STRUCT_PER_CHAPTER_MIN}).")
        if policy["thin"] and struct_ratio < STRUCT_PER_CHAPTER_MIN:
            warns.append(f"THIN: only {struct_ratio:.2f} mapped elements/{unit} "
                         f"(numbered eqs + tables + boxes; heuristic reference {STRUCT_PER_CHAPTER_MIN}). "
                         f"Review whether the genre and content need additional structure. "
                         f"Choose equations, tables or callouts only when they help the reader; "
                         f"prose and zero callouts can be appropriate.")
        if (policy["exercises"] and chapters >= CHAPTERS_FOR_EXERCISE
                and exercises == 0):
            warns.append(f"DENSITY: {chapters} {units} but 0 worked exercises. A "
                         f"study guide should have a solved-exercises Part "
                         f"(exbox titled 'תרגיל N --- ...').")

    # Balance: OVER-boxing is as real a failure as thin content (content-style §4).
    # Runs for every doc type (article too), independent of chapter count.
    emph_frac, box_frac = box_balance(text)
    print(f"INFO: {100*emph_frac:.0f}% of body content sits inside EMPHASIS boxes "
          f"(def/thm/note/warn/key; descriptive only, no minimum or target), "
          f"{100*box_frac:.0f}% incl. exbox; the rest = free prose / numbered "
          f"eqs / tables (unframed by default) / neutral reference cards.")
    if emph_frac > EMPH_BOX_FRAC_MAX:
        # path-prefixed like the per-line flags, so the regression harness
        # (selftest run_case filters on the path) can lock this rule too;
        # document-level metric -> anchored to the first input file.
        print(f"{paths[0]}: [OVER-BOX-EMPHASIS] {100*emph_frac:.0f}% of content "
              f"is in emphasis boxes (>{100*EMPH_BOX_FRAC_MAX:.0f}%). "
              f"Use boxes only for distinct reader needs — move discussion into prose, "
              f"keep key formulas as standalone numbered equations. "
              f"See content-style §4.")
        warns.append(f"OVER-BOX-EMPHASIS: emphasis-box fraction "
                     f"{100*emph_frac:.0f}% (see line above).")
    if policy["combined"] and box_frac > BOX_CONTENT_FRAC_MAX:
        warns.append(f"OVER-BOX: {100*box_frac:.0f}% of content is in colored boxes "
                     f"incl. exbox (>{100*BOX_CONTENT_FRAC_MAX:.0f}%). Boxes are for "
                     f"emphasis/format, not the default — move discussion into prose "
                     f"and keep key formulas as standalone numbered equations. "
                     f"See content-style §4.")

    # consecutive-prose-paragraph runs, scanned per chapter body
    if policy["rhythm"]:
        chunks = (section_pat.split(text)[1:] if sec_unit else
                  re.split(r"\\chapter\b", text)[1:])
    else:
        chunks = []
    # v3.32: tablebox added — a dense-tables appendix (content-style §7's own
    # prescription) tripped RHYTHM because its tableboxes counted as prose.
    structural = re.compile(
        r"\\begin\{(equation|align|gather|multline|defbox|thmbox|notebox|exbox|"
        r"warnbox|keybox|tablebox|framedtable|semanticframedtable|flowtable|tabular\*?|"
        + "|".join(REFERENCE_BOX_NAMES) + r"|enumerate|itemize|qcirc|tikzpic|center|"
        r"asmblock|lstlisting|verbatim|Verbatim)\}|\\\[|\$\$|"
        + section_pat.pattern + r"|\\subsection\b|\\codeline\b")
    for ci, chunk in enumerate(chunks, 1):
        paras = re.split(r"\n\s*\n", chunk)
        run = 0
        worst = 0
        for para in paras:
            if para.strip() and not structural.search(para):
                run += 1
                worst = max(worst, run)
            else:
                run = 0
        if worst >= MAX_PROSE_PARAS_RUN:
            rhythm_unit = "section" if sec_unit else "chapter"
            warns.append(f"RHYTHM: {rhythm_unit} #{ci} has a run of {worst} consecutive "
                         f"prose paragraphs with no mapped equation/table/list/callout. "
                         f"Review paragraph grouping and headings for this genre; "
                         f"add a component only when the content benefits from it.")

    if friction_total:
        warns.append(f"CODE-FRICTION: {friction_total} multi-token inline code "
                     f"expression(s) embedded in Hebrew prose — give each its own "
                     f"\\codeline (content-style §5b); inline \\code{{}} is for atoms.")

    if warns:
        print("\n--- CONTENT WARNINGS (heuristic; not a hard failure) ---")
        for w in warns:
            print("  • " + w)
        print("See references/content-style.md for the density spec and exemplars.")
    else:
        print("OK: no content advisories for the selected profile.")
    return 2 if read_failures else 0


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--profile",
        choices=PROFILES,
        default="generic",
        help="document genre; generic applies only universal checks",
    )
    parser.add_argument(
        "--section-macros",
        default=os.environ.get("SECTION_MACROS", ""),
        help="comma/space-separated custom commands equivalent to \\section; "
             "may also be set with SECTION_MACROS",
    )
    parser.add_argument("paths", nargs="+", help="UTF-8 TeX source files")
    args = parser.parse_args(argv)
    try:
        args.section_macros = normalize_section_macros(args.section_macros)
    except ValueError as exc:
        parser.error(str(exc))
    return args


if __name__ == "__main__":
    args = parse_args(sys.argv[1:])
    sys.exit(main(args.paths, args.profile, args.section_macros))
