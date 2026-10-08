#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Original project code; scope and terms: ../LICENSING.md.
"""check_bidi_figures.py — catch the mixed-direction bug class BEFORE you build.

Scans LaTeX source for failure modes that compile cleanly (0 missing characters,
0 errors) but render WRONG and are invisible in the source, plus a few that throw
errors far from their real cause.

  1. Latin text inside \\h{...} that sits INSIDE a tikzpicture environment.
     babel's bidi reorders Latin correctly in prose and tables, but NOT inside
     TikZ nodes — there the Latin comes out reversed (Datapath -> htapataD,
     CPU -> UPC) and parentheses mirror. Fix: isolate the Latin with \\en{...}
     or \\code{...}, or use bare Latin (no \\h) in the LTR `tikzpic` island.

  2. ASCII LaTeX quotes ``...'' in the legacy Hebrew font context. For Hebrew
     use gershayim ( \u05f4 ). Explicit non-Hebrew profiles supply native English
     fonts; English spans there may use standard TeX quote/dash ligatures.

  3. \\texttt{...} directly touching math, e.g. \\texttt{ALUOp}$=10$ -> "10ALUOp".
     Fix: one unit, \\code{ALUOp=10}.

  4. A \\begin{axis} (pgfplots) with no matching \\end{axis} before
     \\end{tikzpicture} — throws "Extra }" that CASCADES past the figure close.

  5. Math ($...$) in a heading without \\texorpdfstring — garbles the bookmark.

  9. ISLAND-NEXT-TO-MATH (v3.8.2; colon variant v3.10) — an \\en{...}/\\code{...}
     LTR island IMMEDIATELY followed by inline math in RTL prose, e.g.
     \\en{hit time}$=1$ or \\code{Rt}$\\to$\\code{ForwardB}. The island and the
     math are separate LTR runs, so they REORDER under RTL: the value/arrow jumps
     to the wrong side ("=1hit time", "ForwardB->Rt"). v3.10 also catches the
     COLON form \\en{label}: $math$ (the colon orphans: "q=... :s-channel", the
     detector-stable bug). COMPILES CLEAN. Fix: make it ONE island with the math
     INSIDE -> \\en{hit time $=1$} / \\en{label: $math$}. (A plain space with no
     colon, \\en{word} $x$, is FINE and is NOT flagged. Not flagged once wrapped:
     the check skips an island already inside an outer \\en{}/\\mbox{}.)

  10. ADJACENT-LTR-ISLANDS (v3.10) — two \\en{}/\\code{} islands separated ONLY
     by a comma or slash REORDER in RTL: \\en{Griffiths}, \\en{Thomson} renders
     "Thomson, Griffiths"; \\en{Breit-Wigner} / \\en{Lorentzian} -> "Lorentzian /
     Breit-Wigner"; \\code{lw}, \\code{sw} -> "sw, lw". COMPILES CLEAN, invisible
     in source. Fix: merge into ONE island -> \\en{Griffiths, Thomson} /
     \\en{Breit-Wigner / Lorentzian} / \\en{\\code{lw}, \\code{sw}}. (The merged
     form — inner islands inside an outer \\en — is NOT flagged.)

  11. MATH-TEXT-EN-COLON (v3.10) — \\text{\\en{label}:} inside math/align: the
     colon sits OUTSIDE the \\en (in the RTL \\text base), so it ORPHANS to the
     wrong side (":s-channel" instead of "s-channel:"). The align label of the
     virtual-mass box hit this. Fix: put the colon INSIDE -> \\text{\\en{label:}}.

  11b. COLON-TRAPPED-IN-ISLAND (v3.27) — the PROSE mirror image of #11:
     \\en{Offset:} followed by Hebrew. In prose the base is RTL, so an
     island-FINAL colon (the island's right edge) is what the reader meets
     first — the label renders ":Offset" with an orphaned colon before the
     word (caught by a reader on a rendered page; item labels and figure
     labels are the common sites). Fix: colon OUTSIDE -> \\en{Offset}: .
     Context decides the side: prose (RTL base) = colon outside the island;
     \\text in math (LTR base) = colon inside (#11); MATH after the label =
     merge into one island per #9 (\\en{1a: $I_D$}). Islands with no Hebrew
     after them on the line, a '&' cell boundary in between, or islands
     inside \\text{..} are not flagged.

  -- text-inside-math checks (v3.8) -----------------------------------------
  6. LANG-RAW-IN-MATH — a bare \\h{...} or \\en{...} sitting directly in math
     ($...$, \\[...\\], align, a subscript). \\h/\\en are \\foreignlanguage, which
     is INVALID in math -> "\\rmfamily invalid in math mode". Wrap the run in
     \\text{...}: Hebrew -> \\text{\\h{...}}, Latin -> \\text{...} (or \\text{\\en{...}}
     when it has parens, see #7). This was the single hardest error to localise
     in the data-science build: \\en{Normal} written straight into $...$.

  6b. PUNCT-RAW-IN-MATH (v3.53) — a raw typographic-punct char (° … – — “ ” ‘ ’
     ־ ₪) sitting in math. It renders in TEXT (check_charset ALLOWS it) but the
     math font has NO glyph, so it is SILENTLY DROPPED in $...$ ($45°$ -> "45",
     0 errors). The charset gate is line-based, not math-aware, so it is blind to
     the context. Fix: ° -> ^\\circ, … -> \\dots, others -> \\text{...}. Exempt
     inside \\text{}/\\mbox{}/\\tag{} (there the text font renders the glyph).

  6c. HEBREW-IN-MONO (v3.56) — Hebrew inside \\texttt{}/\\code{}/\\codeline{}/
     \\mathtt{}. NOT "tofu" (as the docs claimed until v3.56) but a FATAL build
     failure: the tt family is DejaVu Sans Mono and the tt fallback is DejaVuSerif,
     BOTH with zero Hebrew, so LuaTeX dies with "there are no glyphs in the
     subset" — a message naming only a font file, never Hebrew or the source line.
     Non-local too: an unrelated Latin \\code{} elsewhere turns the fatal into a
     SILENT DELETION of the word. 0-FP by construction (a compiling document
     cannot contain it). Put Hebrew in normal text or \\h{}.

  7. TEXT-PARENS-IN-MATH — a \\text{...} in math whose Latin content has ( ) or
     [ ] but is NOT wrapped in \\en{...}. Plain \\text inherits the surrounding
     RTL base, so the parentheses MIRROR: \\text{Specificity (TNR)} renders
     "Specificity (TNR(" . This COMPILES CLEAN and is invisible in the source.
     Fix: \\text{\\en{Specificity (TNR)}} (the \\en forces LTR so parens stay put).
     For a function on a Hebrew/text argument keep the parens at MATH level:
     \\text{Entropy}(\\text{\\h{...}}), never \\text{Entropy(arg)}. (Parens around
     PURE Hebrew, e.g. \\text{\\h{(...)}} or ESS \\h{(...)}, are fine — not flagged.)
     v3.23.4 also catches the INVERSE — parens OUTSIDE an \\en island that wrap
     ONLY Latin: \\text{(\\en{weak})} renders ")weak(" (the parens sit in the RTL
     \\text base). Fix: parens INSIDE the island -> \\text{\\en{(weak)}}. Parens
     that also wrap Hebrew (\\text{(הספק ב־\\en{CMOS})}) are Hebrew-directional and
     stay fine — NOT flagged.

NOTE (v3.8.1): bare Hebrew inside \\text{...} in math (e.g. \\text{מהירות}, a
subscript/underbrace label) is FINE — it compiles and renders correctly under
this LuaLaTeX+babel(bidi=basic) pipeline; \\h is OPTIONAL there. (Verified
empirically: \\text{שלום} and \\text{\\h{שלום}} render identically.) An earlier
HEBREW-RAW-IN-MATH check was removed as a false positive. The \\rmfamily error
comes ONLY from a bare \\h/\\en used DIRECTLY in math (outside \\text) — that is
check #6 above, which stands.

False positives avoided: \\command names and already-isolated spans
(\\en/\\code/\\texttt, and for the math checks \\h{...}/\\en{...}) are stripped
before the Latin/paren tests; \\text{...}/\\mbox{...} groups are stripped
before the bare-\\h/\\en-in-math scan, so \\text{\\h{...}} and \\mbox{\\en{...}}
do NOT trip #6.

  -- v3.21 lint rules -------------------------------------------------------
  B1. TEXT-MATH-CARET — a bare ^ or _ inside \\text{...} in math. \\text is NOT
     math, so it throws "! Missing $ inserted" (seen: \\text{\\en{(linear
     45^\\circ)}}). Fix: keep the math OUTSIDE the \\text — (\\text{\\en{linear }}
     45^\\circ), not \\text{...45^\\circ}. (Escaped \\^ \\_ and nested $...$ are fine.)
  B2. HEBREW-DOUBLE-HYPHEN — a -- / --- run renders as literal hyphens, NOT an
     en/em-dash: Frank Ruhl has no tlig (verified — width identical with/without
     Ligatures=TeX). This holds next to Hebrew AND between Latin/digits
     (1990--2000, Hong--Ou--Mandel — v3.22 flags those too). Type — (U+2014) /
     – (U+2013) directly. A SINGLE hyphen (Hong-Ou-Mandel, a range like 3-5) is
     correct and is not flagged. Skipped: math (minus), \\code/\\texttt/\\url spans.
     !! DIGIT EXCEPTION (v3.57): between TWO NUMBERS do NOT follow the advice
     above. A typed – between digits REVERSES them under the RTL base
     (1990–2000 renders "2000–1990", measured), so replacing `--` with `–` turns
     a wrong-GLYPH bug into a wrong-ORDER one and this rule then goes silent.
     Keep the UNSPACED ASCII form (1990-2000), or merge the whole range into one
     island: \\en{1990–2000}. Enforced by RANGE-SEP-BETWEEN-DIGITS.
  B3. UNDEFINED-COMMON-MACRO — \\enquote (csquotes) and \\SI/\\qty/\\SIrange
     (siunitx, all forms): packages this preamble does not load, so they throw "Undefined
     control sequence" (both broke a real build). Load the package or rewrite
     (gershayim for quotes; plain math+unit). \\expval/\\ketbra are now provided.
  B4. PROVIDECOMMAND-PRIMITIVE (v3.23.6) — \\providecommand{\\ni}{n_i} is a SILENT
     no-op: \\ni/\\Re/\\Im/\\det/... are TeX primitives / kernel math commands, so
     the name is already defined and every use renders the PRIMITIVE ("np=∋²").
     Compiles clean; was caught only on a rendered page (DEFECTS BLD-9). Fix:
     \\renewcommand (explicit override) or a different macro name.

  13. TEXT-HEBREW-BETWEEN-ISLANDS (v3.23.6) — RAW Hebrew inside \\text{} flanked
     on BOTH sides by \\en/\\code/\\texttt islands, e.g. an align regime label
     \\text{\\en{(}תעלה רחבה\\en{)}}: the two LTR islands bite the RTL run from
     both ends and the Hebrew renders REVERSED with displaced parens (DEFECTS
     BIDI-16). Compiles clean, invisible in source. Fix: the whole Hebrew label
     as ONE unit — \\text{\\h{(תעלה רחבה)}}. Hebrew around a SINGLE island
     (\\text{(הספק ב־\\en{CMOS})}) is fine and is NOT flagged.

MULTI-LINE \\text (v3.23.5): a \\text{...} whose braces span a SOURCE LINE BREAK is
now handled — _text_content() joins the continuation lines before the B1/#7/#7b/
colon scans, so a split \\text{(\\en{weak})} is caught like a single-line one.

Usage:   python3 scripts/check_bidi_figures.py file1.tex [file2.tex ...]
Exit:    0 if clean, 1 if any issue found (so it can gate a build).

v5: language-dependent rules use the surrounding source position, including
nested English/Hebrew blocks and the five explicit language profiles. Lexical
context does not execute user macros or arbitrary TeX conditionals; the compiler
and rendered proof remain authoritative. Structural/math rules stay enabled.
"""
import os      # v3.82: filesystem-resolved alias scope (audit finding B)
from pathlib import Path
import re
import sys
sys.dont_write_bytecode = True
from heading_source import COMMAND, clean_source, group, inline_literal_end, label_findings
from language_context import LanguageContext, LanguageConfig, declared_config
from architecture_contract import (
    CAP_HIDE_SECTION_NUMBERING,
    CAP_SHOWONLYREFS,
    capabilities_for_provider_name,
)
from architecture_detection import capabilities_from_text
from resolve_tex_sources import Dependency, dependency_occurrence_at

# \h{...} with up to one level of nested braces.
H_PAT = re.compile(r'\\h\{((?:[^{}]|\{[^{}]*\})*)\}')
# Hebrew letters — used by HEBREW-IN-EN-ISLAND (the mirror of LATIN-IN-H-IN-TIKZ).
HEB_LETTER = re.compile(r'[\u0590-\u05FF]')
# Typographic-punct codepoints that render in TEXT (check_charset ALLOWS them) but
# TOFU in MATH — the math font (cmr) has no glyph, so they are silently dropped.
# Kept in lockstep with check_charset.ALLOWED_PUNCT (the non-ASCII marks). See the
# PUNCT-RAW-IN-MATH rule. Every one empirically compile-verified to drop in $..$.
_MATH_TOFU_PUNCT = '\u2013\u2014\u2026\u201c\u201d\u2018\u2019\u05be\u00b0\u20aa'
# ASCII LaTeX quotes.
QUOTE_PAT = re.compile(r"``|''")
# \texttt{...} directly touching math ($) — the "10ALUOp" jam in RTL prose.
TTMATH_PAT = re.compile(r'\\texttt\{[^{}]*\}\$|\$\\texttt\{')
# An \en{}/\code{} LTR island IMMEDIATELY followed by inline math, in RTL text.
# The island and the math are separate LTR runs -> they REORDER, so a trailing
# value lands on the wrong side: \en{hit time}$=1$ renders "=1hit time", and
# \code{Rt}$\to$\code{ForwardB} reverses to "ForwardB->Rt". Fix: ONE island with
# the math INSIDE it -> \en{hit time $=1$} / \en{\code{Rt}$\to$\code{ForwardB}}.
# v3.10: also catch the COLON variant \en{label}: $math$ — the colon ORPHANS to
# the wrong side (":s-channel q=..." / detector-stable). A plain SPACE with NO
# colon, \en{word} $x$, is FINE (verified) and is NOT matched here.
ISLAND_MATH_PAT = re.compile(
    r'\\(?:en|code)\{(?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*\}(?:\$| *: *\$)')
# v3.10: two LTR islands (\en/\code/\texttt) separated ONLY by a comma or slash
# REORDER in RTL: \en{Griffiths}, \en{Thomson} -> "Thomson, Griffiths"; \en{A} /
# \en{B} -> "B / A"; \code{lw}, \code{sw} -> "sw, lw"; and (since v3.7 made
# \texttt LTR-ISOLATED) even letter-only \texttt{lw}/\texttt{sw} -> "sw/lw". Fix:
# merge into ONE island -> \en{Griffiths, Thomson} / \en{A / B} / \texttt{lw/sw}
# / \en{\code{lw}, \code{sw}}. (An island already INSIDE an outer \en{}/\mbox{},
# i.e. the merged form, is skipped.)
# v3.29: DASH separators added — \en{A}--\en{B} / \en{A}–\en{B} swap exactly
# like the comma form (proven by render: a range typed as two islands displays
# "Beta–Alpha" even with a PROPER en-dash — merging is the only fix; ten such
# ranges shipped in eight lakits before the sweep). The -- form ALSO renders
# literal hyphens — that side is flagged by HEBREW-DOUBLE-HYPHEN (below).
ADJ_LTR_PAT = re.compile(
    r'\\(?:en|code|texttt|cite)\{(?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*\} *(?:[,/]|-{2,3}|–) *\\(?:en|code|texttt|cite)\{')
# Bare Latin identifier glued to an assignment math run, e.g.  op$=8$  ->  "op8".
# v3.46: also the \text- evasion — controlled$\text-(Z_1Z_2)=$ glues the bare
# word onto math that OPENS with a text hyphen; the hyphen/operator migrate
# across the seam (render-proven, qc-exams e20a_q2: "=controlled", dangling
# hyphen). Same fix as the base form: ONE island, \en{controlled-$(Z_1Z_2)$ = ...}.
BAREMATH_PAT = re.compile(r'(?<![\\A-Za-z])[A-Za-z]{2,}\$(?:=|\\text-)')
# MATH-WRAPPED-EQREF keeps references out of raw math. The v4.11 public
# reference isolation makes the measured text{eqref{key}} form safe. Exempt
# exactly that form, including whitespace/comments/newlines, not arbitrary
# text macros or all references in a display. Legacy raw-math controls remain.
EQREF_PAT = re.compile(r'\\eqref\b')
# v3.46: BOXED-HEBREW-SEGMENTS — \boxed{}/\finalans{} content is ONE math hbox;
# Hebrew \text{} segments inside it reorder against the math (render-proven,
# qc-exams reader report + 8-variant lab): >=2 Hebrew segments scramble
# wholesale; a leading/trailing space inside the \text is swallowed at the seam
# ("מספר הפעלותf=1"); an edge colon/comma orphans to the wrong side; a bare
# digit glued (spacing-only) to the Hebrew lands on its wrong side ("3 שערי" ->
# "שערי 3"); direct adjacency to math letters glues. SANCTIONED (render-proven):
# math-only content, or the WHOLE box being one \text{\h{...}} unit (nested
# $math$ inside it is fine), or a self-contained parenthesized annotation
# separated by real spacing (\quad\text{(קבוע בזמן)}).
BOXED_OPEN_PAT = re.compile(r'\\(?:finalans|boxed)\s*\{')
# v3.47: MATH_DHYPHEN / BRACE_DHYPHEN — the double-hyphen blind spot for a run
# flanked by "$" (between two inline-math islands: "$I_D$--$V_G$") or sitting
# inside a \text{}/\mbox{} group ("$0.3\text{--}3$", "$\tau\text{--}\theta$").
# Neither Hebrew-, Latin-, ref- nor island-adjacency fires (the neighbours are
# "$" / "{" / "}"), yet Frank Ruhl still prints two literal hyphens instead of
# the intended en-dash (render-proven at the codepoint level: "--"->U+002D U+002D
# vs a typed "–"->U+2013). Same flag/fix as the rest of the dash family: type
# – (U+2013) directly. -{2,3} only (a single hyphen is a real minus/range).
MATH_DHYPHEN_PAT = re.compile(r'\$\s*-{2,3}(?!-)\s*\$')
# only \text{--}/\mbox{--} (dashes as the WHOLE text content) — a bare "{--}" cell
# marker (\textcolor{cRed}{--} pipeline-bubble) is NOT the en-dash class. \textcolor
# is not matched: "\text" must be immediately followed by "{".
BRACE_DHYPHEN_PAT = re.compile(r'\\(?:text|mbox)\{\s*-{2,3}(?!-)\s*\}')
# v3.47: REDUNDANT-EQREF-PARENS — \eqref already emits "(N)", so wrapping it in
# literal parens, "(\eqref{..})", renders "((N))" (render-proven; two live
# instances). \ref (bare number, no parens) is NOT matched — "(\ref{..})" -> "(N)"
# is the correct single-paren idiom.
REDUNDANT_EQREF_PAREN_PAT = re.compile(r'\(\s*\\eqref\{[^{}]*\}\s*\)')
# v3.47: HEBREW-MATH-GLUED-OBJECT — a \text{Hebrew phrase} inside math that ENDS
# in a space or maqaf (־) and is immediately followed by its bound math object —
# a lone variable/atom ("\text{דחיית }H_0"), a (tuple) ("\text{צירופי }(m,d)"),
# or a number sandwiched before another \text ("\text{שעות ו־}6.67\ \text{דקות}").
# Math lays the atom out LTR, so it lands on the WRONG side of the RTL phrase
# (render-proven, glyph x-order: "H_0 דחיית" instead of "דחיית H_0"). This is the
# non-boxed sibling of BOXED-HEBREW-SEGMENTS. The atom must be followed by a
# CLOSING/SEPARATOR terminator (} ) ] . , ; : \mid \right \big \text …): a
# new-clause SUBJECT is instead followed by =/\to (e.g. "\text{ובאותו אופן }
# \bar\psi_R=…") and is deliberately NOT flagged. Sanctioned fix (render-proven):
# fold the phrase + its atom into ONE \text{\h{…$x$…}} unit (nested math allowed).
GLUED_MAQAF = '־'
_G_ATOM = (r'(?:\\[A-Za-z]+|[A-Za-z])'
           r'(?:_\{[^{}]*\}|\^\{[^{}]*\}|_[0-9A-Za-z]|\^[0-9A-Za-z]|\\[A-Za-z]+|\')*')
_G_SEP = r'(?:\\[ ,;:!]|~|\\quad|\\qquad|\s)*'
_G_TERM = re.compile(r'^' + _G_SEP + r'(?:[}\)\].,;:$]|\\\\|'
                     r'\\(?:mid|right|big|Big|bigg|Bigg|qquad|quad|text|h|label|end)\b|$)')
_G_VAR = re.compile(r'^(' + _G_ATOM + r')')
_G_TUPLE = re.compile(r'^\([^()=]{1,10}\)')
_G_NUM_TEXT = re.compile(r'^[0-9][0-9.,]*' + _G_SEP + r'\\text\{')
# v3.44: MATH-ENDS-IN-OP-BEFORE-ISLAND — the symmetric complement of
# ISLAND-NEXT-TO-MATH. An inline math run whose LAST token is a binary/
# relational operator, butted with NO space onto an \en/\code/\texttt island,
# is an ADJACENCY seam: the two LTR runs reorder in RTL and the operator+value
# land on the wrong side. Proven live (r03 exercise-4 solution):
# "לחסם $4(2^{15}{-}1)=$\code{0x0001FFFC}" rendered "0x0001FFFC4(2^15-1)=" —
# the bound scrambled. Deterministic (no wrappable space between the runs), so
# 0-FP; the layout-dependent SPACED form (\en{tag} $=25$, BIDI-24) is NOT this
# and stays doctrine. The CORRECT merged form — operator INSIDE an outer \en
# island, \en{\code{sub}$\to$\code{and}} — is exempt via wdepth>0, exactly like
# ISLAND-NEXT-TO-MATH. Longer alternatives are ordered first so \leq/\geq/\neq/
# \Rightarrow are not shadowed by \le/\ge/\ne/\to.
OP_MATH_ISLAND_PAT = re.compile(
    r'(?:[=<>+]|\\(?:Longrightarrow|Rightarrow|Leftarrow|leftarrow|mapsto'
    r'|leq|geq|neq|le|ge|ne|to|approx|equiv|cong|simeq|sim|propto|gg|ll'
    r'|oplus|otimes|pm|mp|cdot|times|div)) *\$(\\(?:en|code|texttt)\{)')
# Two \texttt{} runs joined by / or , where a run contains \$  (the $ misplaces).
TTPAIR_PAT = re.compile(r'\\texttt\{([^{}]*)\}[/,]\\texttt\{([^{}]*)\}')
# A Latin token immediately before an English "(Cap...)" in Hebrew text mirrors.
# v3.36: WIDENED from uppercase-acronyms-only ([A-Z]{2,} + uppercase after the
# paren) — "C (cstyle)" and "main (entry point)" break IDENTICALLY in the
# render (proven) but evaded on both counts. The precise breakage condition,
# established on a 4-case render matrix: bare Latin + "(Latin...)" breaks when
# the closing paren is NOT followed by more Latin — ")" between Latin and
# Hebrew/punct/EOL resolves RTL and mirrors, while "Model (v2) update" (Latin
# resumes) is ONE LTR run and renders correctly. Hence the negative lookahead.
# Guards at the firing site: math mask, TikZ lines, \texorpdfstring spans, and
# Hebrew-required-on-line (an all-English line has no RTL base — nothing can
# mirror; this also exempts multi-line english blocks without block tracking).
# The lookahead skips NEUTRALS (space/comma/period/dashes) before deciding:
# ") , AUC" resolves the paren between two Latin runs -> LTR -> fine (proven
# on the real "scraping (BeautifulSoup), AUC" corpus line), while "), ו..."
# and ")." at end-of-line resolve RTL and mirror.
# v4.14: WIDENED AGAIN, on render matrices totalling 63 rows read as GLYPH
# x-order (DEFECTS BIDI-79). The v3.36 rule demanded a LATIN LETTER as the
# FIRST character inside the paren ("\([A-Za-z]"), which is no part of the
# mechanism at all and let a whole family through -- every row below measured
# broken, glyphs "((" instead of "()":
#     Skill(/audit)   punctuation first   (the live one: booklet p.39)
#     npm(-g)         a dash first
#     f(2)  v(1,2)    a DIGIT first (W7 retypes EN as L after the Latin anchor,
#                     so the opening paren lands in the LTR run exactly as a
#                     letter would -- proven: "(2024)" with no Latin anchor is
#                     CORRECT, "v(1,2)" is broken)
# and one whole bracket family: array[0] / Skill[/audit] mirror identically
# ("[[", measured), yet only "(" was scanned.
# THE MECHANISM, stated once: a Latin letter immediately before the opening
# bracket drags that bracket (and, via W7, any digits behind it) into the LTR
# run, so it resolves L and does NOT mirror; the closing bracket, with Hebrew
# after it, resolves R by N2 and DOES. One pair, two levels, two identical
# glyphs. Everything the rule tests follows from that and nothing else:
#   * ANCHOR (Latin immediately before, or one space) -- without it BOTH
#     brackets resolve R and mirror together, which is correct Hebrew
#     parenthesis rendering: "(audit)", "(Claude Code)", "(v2.0)", "(2024)"
#     are all measured CORRECT and must never be flagged.
#   * TAIL lookahead (no Latin after the closing bracket, neutrals skipped) --
#     "Skill(/audit) more Latin" and "Skill(/audit), AUC" are one LTR run,
#     measured correct. Unchanged from v3.36.
#   * The post-filter at the firing site, not expressible here: the content must
#     hold an alphanumeric ("Skill()" is measured CORRECT -- with nothing strong
#     inside, the two brackets are adjacent neutrals and resolve R together),
#     and its FIRST strong character must not be Hebrew ("audit(עברית)" is
#     measured CORRECT -- Hebrew after "(" forces it R by N2, so the pair agrees
#     again). Both are directionality facts, not style.
# Fix, unchanged and measured on every broken row: one LTR island around the
# whole token -- \en{Skill(/audit)} / \code{Skill(/audit)}.
# v4.14.1: the ANCHOR moved out of the pattern into _latparen_anchored(), because
# it is a BACKWARD question and a regex prefix could not ask it. The v4.14.0 form
# ("[A-Za-z]+\s?", or "\textbf{Latin...}\s?") was still fitted to the example it
# was written from: it needed the Latin letter either bare or inside a \textbf
# whose content STARTS Latin, with at most one space before the bracket.
# Measured broken and missed by all of that (glyphs "((" again):
#     \textbf{גשר PCI} (PCI bridge)   anchor closes a group whose content is Hebrew-first
#     \emph{תג PCI} (PCI bridge)      any typeset wrapper, not only \textbf
#     \textbf{\emph{גשר PCI}} (…)     nested wrappers
#     \h{גשר PCI} (PCI bridge)        \h does NOT isolate -- it keeps the RTL base, so
#                                     the trailing Latin still anchors. \en DOES isolate
#                                     and is measured safe; that asymmetry is the whole
#                                     reason \h sits on the wrapper list and \en does not
#     \textbf{גשר PCI} —(PCI bridge)  an em-dash between anchor and bracket
#     \textbf{גשר PCI}: (PCI bridge)  a colon between them
# The first of those shipped on page 33 of computer-architecture.
# The backward scan encodes UBA N1 directly: everything between the last strong
# character and the bracket is neutral, so the bracket inherits that character's
# direction. Skip neutrals, step out of a TYPESET wrapper's closing brace, stop at
# anything else. The wrapper list is a WHITELIST, not "any }": \begin{exbox}[frame
# title={…}] also ends in "}" and its "[" is an optional ARGUMENT, not prose --
# measured, treating every "}" as transparent turns this rule into 1537 corpus
# hits, essentially all of them that shape.
_LATPAREN_TAIL = r'(?![\s,.;:!?—–־-]*[A-Za-z])'
LATPAREN_PAT = re.compile(
    r'(?:\(([^()\n]*)\)|\[([^\[\]\n]*)\])' + _LATPAREN_TAIL)
# Neutrals that carry no direction of their own and so cannot break the anchor.
_LATPAREN_SKIP = ' \t—–-:;,.!?*“”‘’'
# Groups whose closing brace is TYPESET-transparent: the run inside them is prose
# in the same direction context, so a Latin letter there still anchors.
_LATPAREN_WRAP = re.compile(
    r'\\(?:textbf|emph|textit|textsc|textmd|textrm|underline|mbox|h)\s*\{$')


def _match_brace_backward(s, close_idx):
    """s[close_idx] == '}'; return the index of the matching '{', or -1."""
    depth = 0
    for j in range(close_idx, -1, -1):
        if s[j] in '{}':
            k = j - 1
            while k >= 0 and s[k] == '\\':
                k -= 1
            if (j - 1 - k) % 2 == 1:
                continue                       # escaped brace: content, not a delimiter
        if s[j] == '}':
            depth += 1
        elif s[j] == '{':
            depth -= 1
            if depth == 0:
                return j
    return -1


def _latparen_anchored(text, pos, blanked, mask):
    """True when the last strong character before text[pos] is a Latin letter.

    `blanked` marks island spans (\\code/\\texttt/\\en/...). A language switch is a
    real run boundary, so the scan stops there instead of reading through it --
    measured: \\code{PCI} (PCI bridge) and \\en{MIPS} (32 ביט) render CORRECTLY.
    `mask` marks math and is a stopper for the same reason.
    """
    j = pos - 1
    while j >= 0:
        if blanked[j] or (j < len(mask) and mask[j]):
            return False
        ch = text[j]
        if ch in _LATPAREN_SKIP:
            j -= 1
            continue
        if ch == '}':
            opener = _match_brace_backward(text, j)
            if opener < 0 or not _LATPAREN_WRAP.search(text[:opener + 1]):
                return False
            j -= 1            # transparent brace: keep reading INSIDE the group
            continue
        if not (ch.isascii() and ch.isalpha()):
            return False
        # A CONTROL-SEQUENCE NAME is not prose. \item[..], \includegraphics[..]
        # and \begin{env}[..] all put a Latin letter immediately before the
        # bracket, and their bracket is an optional ARGUMENT that never reaches
        # the page. The v4.14.0 pattern excluded them with a (?<![\\A-Za-z])
        # lookbehind; the backward scan has to make the same test explicitly, and
        # 8 selftest cases caught the omission the moment it was dropped.
        k = j
        while k >= 0 and text[k].isascii() and text[k].isalpha():
            k -= 1
        return not (k >= 0 and text[k] == '\\')
    return False
# First strong character inside the bracket: a strong R there means the opening
# bracket resolves R too and the pair agrees (not a defect); an alphanumeric
# there means it resolves L while the closing one resolves R (the defect).
# Strong R is NOT just the alphabet א-ת: geresh/gershayim
# (bit (״Modified״)) and maqaf (bit (־Modified)) are bidi class R, and BOTH
# render CORRECTLY (measured) — so the class below is the Hebrew block's R-class
# range. Points and cantillation are NSM, not strong, and cannot open real
# content. Using HEB_LETTER ([א-ת]) here instead flagged a shipped-correct row.
LATPAREN_STRONG_R = '\u05be\u05c0\u05c3\u05c6\u05d0-\u05f4'
LATPAREN_FIRST_STRONG = re.compile('[A-Za-z0-9' + LATPAREN_STRONG_R + ']')
LATPAREN_HEB_FIRST = re.compile('[' + LATPAREN_STRONG_R + ']')

# --- TOKEN-PUNCT-ADRIFT (v4.15.0, DEFECTS BIDI-80) -------------------------
# A BARE Latin token in Hebrew prose loses its own edge punctuation to the far
# side of the word. Measured on the page, glyph x-order, 21 rows:
#     /audit -> audit/      .claude -> claude.     @agent -> agent@
#     \#tag  -> tag#        -v      -> v-          *.tex  -> tex.*
#     +flag  -> flag+       commands/ -> /commands
# The punctuation is NEUTRAL, the Hebrew before it is R and the Latin after it
# is L, so N2 hands it the paragraph direction: it joins the RTL run and lands
# on the other side of the word it belongs to. Nothing warns — the source reads
# exactly as intended and the build is clean. Fix: one island around the WHOLE
# token, \code{/audit} or \en{/audit}, both measured correct.
#
# THREE EXEMPTIONS, every one of them measured, not argued:
#   * punctuation INSIDE a Latin token has L on both sides and stays put:
#     CLAUDE.md, and/or, Hong-Ou-Mandel, 0.5.
#   * punctuation after a HEBREW LETTER is the Hebrew connective, not the
#     token's: ב-LHC and ב־LHC both render with the hyphen on the Hebrew side,
#     and so does מבחן/CV. Flagging those would hit most of the corpus.
#   * a trailing slash followed by Hebrew is the same connective read the other
#     way: CV/מבחן is measured CORRECT, while commands/ before a space is not.
# A FOURTH exemption came out of the 0-FP sweep and is measured too: when the
# character before the punctuation belongs to a MATH run, an ISLAND, or any
# closing brace, the punctuation sits between two L runs and stays put —
# $p$-value, \\en{n}-type, \\code{n}-type and \\texorpdfstring{$k$}{k}-NN all
# render CORRECTLY, and all five of the sweep's hits were exactly that shape.
# Sentence punctuation is NOT this defect and is deliberately absent from the
# sets: "ראה audit." renders with the period on the Hebrew side, which is where
# an RTL sentence ends. Only ONE character is scanned on the trailing side, "/",
# because it is the only one measured to belong to the token rather than to the
# sentence.
TOKEN_PUNCT_LEAD_PAT = re.compile(r'([/.@#+*-])[A-Za-z]')
# Characters the backward test walks over before judging (see the loop). Every
# one of them is a NEUTRAL that can legitimately sit inside a Latin run, so
# finding one says nothing yet -- keep walking. Whitespace is deliberately
# absent: it is the signal itself. The ':' and the URL punctuation came from
# the harness, which caught `\sourcelink{https://example.org/reference}` in the
# skill's own documentation exemplar and in two bundled examples: walking over
# '//' stopped at the ':' and called a perfectly ordinary URL adrift.
_TOKEN_PUNCT_WALK = '/.@#+*-()[]:~?&=_'
TOKEN_PUNCT_TAIL_PAT = re.compile(r'(?<![A-Za-z0-9])[A-Za-z][A-Za-z0-9._-]*(/)')


def _token_punct_adrift(text, pos, blanked, mask):
    """True when text[pos] is punctuation glued to the LEFT edge of a token."""
    prev = pos - 1
    if prev >= 0 and text[prev] == '\\':
        # \# is a literal hash on the page. Every other \<punct> is a macro or
        # a typesetting escape — \- discretionary hyphen, \/ italic correction,
        # \@ spacing, \. accent — and prints no such character at all.
        if text[pos] != '#':
            return False
        prev -= 1
    # More punctuation to the left is not a second defect, it is the same one:
    # walk over it and judge by what it is attached to. Hong--Ou keeps its
    # hyphens (Latin on the left), Skill(/audit) keeps its slash (the paren sits
    # in the LTR run), *.tex does not (whitespace on the left). Whitespace is
    # NOT walked over — a space is exactly what detaches the punctuation from
    # the Hebrew and leaves it belonging to the Latin token alone.
    while prev >= 0 and text[prev] in _TOKEN_PUNCT_WALK:
        prev -= 1
    if prev < 0:
        return True
    if blanked[prev] or (prev < len(mask) and mask[prev]):
        return False                      # an island or a math run ends in L
    ch = text[prev]
    if ch in '$}':
        return False                      # math edge, or any group closing
    if ch.isascii() and ch.isalnum():
        return False                      # inside a token: CLAUDE.md, and/or
    if HEB_LETTER.match(ch):
        return False                      # Hebrew connective: ב-LHC, מבחן/CV
    return True


def _token_slash_adrift(text, pos, blanked, mask):
    """True when the trailing '/' at text[pos] is the token's, not a separator."""
    nxt = pos + 1
    if nxt >= len(text):
        return True
    if blanked[nxt] or (nxt < len(mask) and mask[nxt]):
        return False                      # an island or a math run begins in L
    ch = text[nxt]
    if ch in '${}':
        return False                      # math edge, or a group boundary
    if ch.isascii() and ch.isalnum():
        return False                      # and/or — a separator inside one run
    if HEB_LETTER.match(ch):
        return False                      # CV/מבחן — measured correct
    return True

# --- #12 Hebrew-flow / Hebrew-equation arrows (v3.14) ----------------------
# bidi does NOT mirror arrow glyphs. A rightward "flow/produces" arrow whose
# operands involve Hebrew points BACKWARD (against RTL reading). Two forms:
#   (a) bare arrow alone in inline math between Hebrew prose: שלב $\to$ עדכון
#   (b) arrow in a display/inline equation that carries a Hebrew \text OPERAND
#       (the Hebrew makes the whole equation RTL, flipping the arrow):
#       \text{חריגה ב־}EX \Rightarrow \text{בטל}... / \code{div}\Rightarrow ...=\text{מנה}
_HEBR = '\u0590-\u05ff'
HEB_CHAR2 = re.compile('[' + _HEBR + ']')
# v3.60 ISLAND-PAIR-REVERSED: two adjacent islands separated by space / nothing /
# period. The comma & slash separators are BIDI-2's ADJ_LTR_PAT; these three were
# wrongly documented as safe. Both groups are captured so the caller can require a
# Latin letter OUTSIDE math in each (exempting the derivation-arrow idiom).
_ISL_GRP = r'\\(?:en|code|texttt)\{((?:[^{}]|\{[^{}]*\})*)\}'
# SPACE or NOTHING only. A PERIOD separator was tried and REMOVED: `\en{MIPS}.
# \code{\$s0}` is overwhelmingly a SENTENCE BOUNDARY in this corpus, not a pair —
# an auto-fixer built on the period branch merged two separate sentences into one
# LTR island and swallowed the sentence-ending period (caught in review, reverted).
# A period between islands is therefore left alone; only true adjacency is flagged.
ISLAND_PAIR_PAT = re.compile(_ISL_GRP + r'([ \t]*)' + _ISL_GRP)


def _latin_outside_math(s: str) -> bool:
    """A Latin letter or digit that is NOT inside $...$ — the discriminator that
    keeps \\en{$x$} \\en{$\\Leftarrow$} (math-only islands, correct as separate flow
    items in the Hebrew stream) out of ISLAND-PAIR-REVERSED, while still catching a
    digit-run pair like \\code{1010}\\code{101} (measured: renders "1011010")."""
    return bool(re.search(r'[A-Za-z0-9]', re.sub(r'\$[^$]*\$', '', s)))
# v3.59: environments that do NOT provide LTR isolation — the DENY-list for
# LISTING-OUTSIDE-LTR-ISLAND. Anything NOT in here is treated as a possible
# wrapper, so a project-local `otherlanguage` alias (data-science-exams' `qeng`,
# defined in an un-\input-ed macros.tex) never false-positives. Deliberately does
# NOT include asmblock/otherlanguage/english — those ARE the isolation.
_RTL_CONTAINERS = frozenset({
    'document', 'exbox', 'notebox', 'defbox', 'thmbox', 'warnbox', 'keybox',
    'tablebox', 'itemize', 'enumerate', 'description', 'center', 'minipage',
    'figure', 'table', 'quote', 'quotation', 'flushleft', 'flushright',
})
# rightward / "produces" arrows that bidi does NOT mirror (leftward forms are fine)
RARROW_PAT = re.compile(
    r'\\(?:to|rightarrow|longrightarrow|Rightarrow|Longrightarrow'
    r'|xrightarrow|twoheadrightarrow|hookrightarrow|mapsto)(?![A-Za-z])')
# a \text{...} carrying Hebrew (an operand — unless it is a sub/superscript label)
# v4.7.4: this one STAYS brace-shallow ON PURPOSE — do NOT "fix" it the way
# _arrow_operand_hebrew was fixed. It feeds only the COARSE branch: an
# implication anywhere on a line that carries a Hebrew \text anywhere, with NO
# adjacency requirement. Adjacency is the whole thing keeping the precise branch
# honest, so widening what counts as "a Hebrew \text here" widens a rule that is
# already deliberately imprecise. Measured both ways over 19 collections: a
# depth-aware version finds 0 additional real sites — the nested form is already
# covered, precisely, by _arrow_operand_hebrew — while it newly false-fires on a
# Hebrew LABEL beside an all-math implication,
#   \[ \text{\h{נתון}}:\ x>0 \quad\Longrightarrow\quad y>0 \]
# which is correct as written. That shape is pinned as a negative in selftest.
HEB_TEXT_PAT = re.compile(r'\\text\{[^{}]*[' + _HEBR + r'][^{}]*\}')
# Hebrew LETTERS only (א-ת) — v3.23.7: the BIDI-16 probe uses this, not the full
# block: a lone maqaf/gershayim between two islands does NOT reorder (compiled,
# pixel-identical to the merged form); only Hebrew letters carry the RTL run.
HEB_LETTER = re.compile('[א-ת]')
# bare rightward arrow alone inside inline math:  $ \to $  ( \;,\, \quad spacing ok )
BARE_RARROW_DOLLAR_PAT = re.compile(
    r'\$(?:\s|\\[;,:!>| ]|\\quad|\\qquad)*'
    r'\\(?:to|rightarrow|longrightarrow|Rightarrow|Longrightarrow|mapsto)'
    r'(?:\s|\\[;,:!>| ]|\\quad|\\qquad)*\$')

# Heading commands (math in a bookmark must use \texorpdfstring).
HEADING_PAT = re.compile(
    r'\\(?:chapter|section|subsection|subsubsection|paragraph|part)\*?\{')

# v3.76: TOC geometry surgery in a document-layer file — the exact construct
# that rolled BLD-38's measured 3.2em back to 3.0em in 10 scaffold-copied
# main.tex files (last definition wins over the preamble's).
# v3.82 WIDENED (audit finding F): the v3.76 pattern knew only \renewcommand
# and \patchcmd, while the documented contract promised "any
# \l@chapter/section/subsection surgery". Proof-of-failure, measured before
# this line changed: \def\l@section#1#2{\@dottedtocline{1}{1.5em}{3.0em}{#1}{#2}}
# in a \begin{document} file reproduces BLD-38's rollback EXACTLY (TOC
# number<->title gap 30.65pt -> 28.25pt, delta 2.40pt = 0.2em at 12pt) and the
# checker printed "clean"; \gdef, \let and \RenewDocumentCommand evaded
# identically (4/4 probes silent, the \renewcommand control fired). \def inside
# \makeatletter is the most idiomatic TeX spelling of this patch, so the widest
# spelling was the one the rule could not see. \apptocmd/\pretocmd are
# deliberately NOT in the set: they APPEND to the existing definition and
# change no geometry (audit-measured non-vector). The target name must end
# there — (?![A-Za-z@]) keeps \l@sectionfoo out — and \let\old\l@section (the
# SAVE idiom, benign) does not match because \let must be followed directly by
# the \l@ name. Sweep after widening: 0 hits over all 335 CI-linted sources and
# all 12 assembled final.tex (0-FP re-derived, not inherited).
# HONEST LIMIT (v3.82, measured): the name must be written literally. An
# \expandafter\def\csname l@section\endcsname spelling builds the control
# sequence at expansion time and this pattern returns 0 on it — verified with a
# probe. Recorded rather than chased: the escape hatch is not idiomatic for a
# hand-patched TOC block, and the covered spellings are stated by name — in the
# pattern below and in the registry record — instead of promising "any".
TOC_OVERRIDE_PAT = re.compile(
    r'\\(?:(?:re)?newcommand\s*\*?\s*\{?'
    r'|g?def'
    r'|let'
    r'|(?:Renew|New|Declare|Provide)DocumentCommand\s*\{?'
    r'|patchcmd\s*\{)'
    r'\s*\\l@(?:chapter|subsection|section)(?![A-Za-z@])')

# v3.76: a project-local \newenvironment defined over otherlanguage IS an LTR
# island (data-science-exams' qeng, ca-exams' ctrltable).
# v3.82: the same-line lookahead became a brace-matched begin-code scan — see
# _collect_env_aliases. The v3.76 HONEST LIMIT ("a definition whose
# \begin{otherlanguage} sits on a later source line is not collected") is
# retired rather than restated: the live `choices` definition proved the limit
# hides real render defects, and the two dimensions must not drift apart.
LTR_ALIAS_INNER_PAT = re.compile(r'\\begin\{otherlanguage\}')

# v3.82 (audit finding A): the TWIN of LTR_ALIAS_INNER_PAT on the other axis.
# LIST-IN-LTR-ISLAND needs BOTH ends resolved — the island alias (qeng) AND
# the LIST alias. data-science-exams/src/macros.tex:63 defines `choices` as a
# \newenvironment over the LaTeX `list` primitive; v3.76 taught the rule to
# see through the island and left this dimension unhandled, so 60 uses of
# \begin{choices} inside \begin{qeng} were structurally invisible. Measured on
# the shipped 172-page data-science-exams/src/final.pdf: 216 (a)-(d) labels at
# x = 39.5 (108x) / 40.2 (54x) / 40.6 (54x) against a text-block left edge of
# 65.2 (1692 lines) — up to 25.7pt INTO the left margin, item bodies at 59.2.
LIST_ALIAS_INNER_PAT = re.compile(
    r'\\begin\{(?:list|itemize|enumerate|description)\}')

# --- math-mode detection (v3.8) --------------------------------------------
MATH_ENV_BEGIN = re.compile(
    r'\\begin\{(align\*?|gather\*?|equation\*?|multline\*?|eqnarray\*?'
    r'|flalign\*?|alignat\*?|aligned|gathered)\}')
MATH_ENV_END = re.compile(
    r'\\end\{(align\*?|gather\*?|equation\*?|multline\*?|eqnarray\*?'
    r'|flalign\*?|alignat\*?|aligned|gathered)\}')
# \h{...} or \en{...} with up to one nested-brace level (for stripping).
LANG_GROUP = re.compile(r'\\(?:h|en)\{(?:[^{}]|\{[^{}]*\})*\}')
# An LTR (Latin) island: \en / \code / \texttt with up to one level of nesting.
LATIN_ISLAND = re.compile(r'\\(?:en|code|texttt)\{(?:[^{}]|\{[^{}]*\})*\}')

# --- v3.21 lint rules ------------------------------------------------------
# B2 HEBREW-DOUBLE-HYPHEN — -- / --- adjacent to Hebrew renders as literal
#   hyphens, NOT an em-dash (Frank Ruhl lacks tlig; verified). Type — (U+2014)
#   directly. A hyphen run BETWEEN Latin tokens (Hong-Ou-Mandel, state-of-the-
#   art) is correct and is NOT matched (no Hebrew on either side). A SINGLE
#   hyphen (range 3-5) is not matched either — only runs of 2 or 3.
HEB_DHYPHEN_PAT = re.compile(
    r'[\u0590-\u05ff][ \t]*-{2,3}|-{2,3}[ \t]*[\u0590-\u05ff]')
# v3.22: the classic Latin/digit range idiom (1990--2000, Hong--Ou--Mandel) ALSO
# stays literal hyphens under Frank Ruhl (tlig never fires — verified). Letter or
# digit required on BOTH sides, so TikZ path ops ('(a) -- (b)', '--cycle', '--++')
# never match.
LAT_DHYPHEN_PAT = re.compile(r'[0-9A-Za-z]-{2,3}[0-9A-Za-z]')
# v3.57 RANGE-SEP-BETWEEN-DIGITS — a range separator between TWO NUMBERS reverses
# them under the RTL base: `2020–2023` renders "2023–2020", `15–17` -> "17–15"
# (glyph-geometry verified). Two shapes, both measured:
#   (a) the DASH CLASS – — ־ , regardless of spacing;
#   (b) ASCII - or / WITH A SPACE on either side (`5 - 10` -> "10-5",
#       `2020 / 2021` -> "2021/2020") — the unspaced `5-10` / `2020/2021` are
#       CORRECT (UAX#9 W4 fuses a Common Separator between two EN runs).
# A DIGIT is required on BOTH sides, which is what makes this 0-FP against the
# everyday Hebrew maqaf idioms (ה־21, כ־12, בית־ספר: letter, not digit, on the
# left) and against `2020 — שנה` (Hebrew, not a digit, on the right).
RANGE_SEP_PAT = re.compile(
    r'[0-9][0-9.,:/]*(?:\s?[\u2013\u2014\u05be]\s?|\s+[-/]\s*|\s*[-/]\s+)[0-9]')
# v3.57 REF-RANGE-REORDER — the same reversal for cross-reference ranges/lists:
# \ref{a}–\ref{b} renders "1.2–1.1", \eqref{a}–\eqref{b} renders "(1.2)–(1.1)".
# Separator taxonomy measured in the v3.57 regression corpus: – — ־ -- --- and a comma
# FOLLOWED BY A SPACE all reverse; a comma with NO space and a bare / are
# CORRECT and must be exempt. \autoref/\nameref are exempt too — their Hebrew
# category name anchors each unit (verified "סעיף 1.1 – סעיף 1.2"). The
# alternation below cannot match inside \autoref/\nameref (after the backslash
# it demands eq/page/nothing then literally `ref`).
# v3.69: \cite added. Each \cite is its own LTR isolate (the v3.54 \@cite
# wrap), so `\cite{a}–\cite{c}` lays out RIGHT-TO-LEFT — measured `[3]–[1]`,
# the exact visual of BIDI-45's reversed \eqref range; `\cite{a}, \cite{b}`
# shows `[2], [1]`. Correct forms: one \cite{a,b,c} ([1, 2, 3], v3.54) or
# \en{\cite{a}–\cite{c}} ([1]–[3], render-verified). 0 \cite in the corpus
# today, so the extension is measured-0-FP by construction.
REF_RANGE_PAT = re.compile(
    r'\\(?:(?:eq|page)?ref\*?|cite)(?:\[[^\]]*\])?\{[^{}]*\}\s*(?:[\u2013\u2014\u05be]|-{2,3}|,(?=\s))\s*'
    r'\\(?:(?:eq|page)?ref\*?|cite)(?:\[[^\]]*\])?\{')
# v3.25: -- between two \ref/\eqref commands ("(2.2)--(2.3)" range idiom) —
# at source level the run sits between } and \, so neither Hebrew- nor
# Latin-adjacency fires; renders as literal hyphens all the same.
REF_DHYPHEN_PAT = re.compile(r'\\(?:eq)?ref\{[^{}]*\}\s*-{2,3}')
# v3.29: the SAME between-} blind spot for islands — \en{p}--\en{n},
# \code{\$f0}--\code{\$f31}: the run sits between } and \ (or } and space),
# invisible to both adjacency patterns above; renders literal hyphens all the
# same (ten live instances shipped before the sweep). Skipped inside math
# (minus signs) and inside tikzpicture (node{...} braces already shield the
# path operator, but stay conservative).
ISLAND_DHYPHEN_PAT = re.compile(
    r'\\(?:en|code|texttt)\{(?:[^{}]|\{[^{}]*\})*\}\s*-{2,3}(?!-)')
# v3.25: an \en island whose ENTIRE content is brackets/punctuation
# (\en{(} ... \en{)}) — the isolated lone bracket swaps sides in the RTL flow
# and mirrors ()טבלת עמודים(). Plain parens around Hebrew are handled by the
# bidi algorithm and are the fix. \code is exempt (a code token like [] is
# legitimate content).
PAREN_ONLY_EN_PAT = re.compile(r'\\en\{\s*[()\[\]]+\s*\}')
# v4.7.7: an \mbox/\hbox whose body OPENS with a direction island. The rule
# body verifies the island is the box's WHOLE content before firing.
BOXED_ISLAND_PAT = re.compile(r'\\(?:mbox|hbox)\s*\{\s*\\(?:en|code|texttt)\s*\{')
# Exactly the characters carrying the Unicode bidi-mirroring property that this
# corpus can produce. Measured: . , : ; = + - * / ! ? % # $ _ | are UNCHANGED at
# a box edge, so widening this to "neutrals" would be unmeasured scope.
_MIRRORABLE = frozenset('[](){}<>')



def _boxed_island_edges(text: str):
    r"""Yield (box_start, box_end, inner) for every \mbox/\hbox whose WHOLE body
    is one \en/\code/\texttt island whose content starts or ends with a
    mirrorable bracket. Shared by the per-line and the paragraph pass so the
    two cannot drift apart."""
    for m in BOXED_ISLAND_PAT.finditer(text):
        ob = text.find('{', m.end() - 1)
        bo = text.find('{', m.start())
        if ob < 0 or bo < 0:
            continue
        iend = _match_brace(text, ob)
        bend = _match_brace(text, bo)
        # _match_brace returns the index JUST PAST the matching '}', so the
        # island's own '}' is at iend - 1 and must not be read as content — it
        # is itself in _MIRRORABLE, and reading it made this rule fire on every
        # boxed island during development.
        if iend < 0 or bend < 0 or iend != bend - 1:
            continue
        inner = text[ob + 1:iend - 1].strip()
        if inner and (inner[0] in _MIRRORABLE or inner[-1] in _MIRRORABLE):
            yield m.start(), bend, inner


def _inside_h_island(text: str, pos: int) -> bool:
    r"""True when pos sits inside an \h{...} group. An \h island flips the base
    back to RTL, so a boxed island inside one mirrors even when the surrounding
    block is \begin{otherlanguage}{english} (render-proven)."""
    for hm in re.finditer(r'\\h\s*\{', text):
        ho = text.find('{', hm.end() - 1)
        if ho < 0 or ho >= pos:
            continue
        hend = _match_brace(text, ho)
        if hend > pos:
            return True
    return False
# v3.26: a math island whose content STARTS with a relational operator, right
# after a Hebrew word — 'בלוק $=4$ בתים'. The operator sits at the LEFT edge
# of the LTR island, so the RTL reader meets the VALUE first: it renders as
# "בלוק 4 = בתים" (proven side-by-side vs the plain-text form, which the bidi
# algorithm gets right: 'בלוק = 4 בתים'). Fix: move the operator OUT of the
# island into Hebrew text (= stays plain text; \approx/\sim -> 'כ־';
# \ge -> 'לפחות'; \le -> 'לכל היותר'). A BARE operator island ($=$ alone,
# a symbol mention) has nothing to swap and stays silent.
# v3.29: the \(..\) inline-math form is caught too (the $-only pattern was a
# proven blind spot \u2014 same broken render, checker silent), and the bare-
# operator-mention exemption is kept for BOTH forms via the lookahead: after
# the operator there must be real content, not the closing $ / \).
HEB_OP_MATH_PAT = re.compile(
    r'[\u05d0-\u05ea]\s*(?:\$|\\\()\s*(?:=|<|>|\\(?:approx|le|ge|ne|sim|leq|geq)(?![A-Za-z]))'
    r'\s*(?!\$|\\\))[^\s]')
# v4.1.3: the SAME value-first break when what precedes the operator-initial
# math is an LTR ISLAND instead of a Hebrew word:
#     '\u05d0\u05d5\u05e8\u05da \u05d0\u05d7\u05e8\u05d9 \en{Flatten} $=H\cdot W\cdot C$'
# HEB_OP_MATH_PAT keys on a Hebrew LETTER, so a closing '}' before the math
# slipped past it \u2014 a measured blind spot, not a deliberate exemption. The
# mechanism does not care how the left operand was typed: the math is one LTR
# run, and an RTL reader moving leftward meets that run's RIGHT edge \u2014 the
# VALUE \u2014 before the operator. 'Flatten = H\u00b7W\u00b7C' is therefore scanned as
# 'Flatten C\u00b7W\u00b7H ='. Rendered side by side with the Hebrew-word form that the
# checker already flags, the two are indistinguishable (reader report on a
# shipped page, then reproduced in isolation).
# \code/\texttt are INCLUDED: the sibling island rule exempts them because a
# mono island may QUOTE an operator token, but here the operator lives in real
# math, so no mention-exemption applies.
# WHITESPACE between the island and the math is REQUIRED: the JAMMED form
# (\en{hit time}$=1$) is deterministic and already owned by
# ISLAND-NEXT-TO-MATH / TEXTTT-NEXT-TO-MATH — firing here too would double-flag
# one defect.
ISLAND_OP_MATH_PAT = re.compile(
    r'\\(?:en|code|texttt)\{(?:[^{}]|\{[^{}]*\})*\}\s+(?:\$|\\\()\s*'
    r'(?:=|<|>|\\(?:approx|le|ge|ne|sim|leq|geq)(?![A-Za-z]))'
    r'\s*(?!\$|\\\))[^\s]')
# v3.29: the same value-first break with NO math at all \u2014 an \en island whose
# content STARTS with the relational operator right after a Hebrew word
# ('\u05d1\u05dc\u05d5\u05e7 \en{= 4 bytes}'): the island is one LTR run, the operator is its left
# edge, and the RTL reader meets "bytes 4" before the "=" (proven by render;
# three '\en{= 8}' instances shipped in a reviewed lakit). Same fix, same
# flag. A bare-operator island (\en{=}) has nothing to swap. \code/\texttt
# are DELIBERATELY exempt \u2014 a mono island quoting an operator token
# (\code{==}, \code{>= 90}, \code{<p>}) is a code MENTION, and the sweep
# fired 9 false positives on shipped, reviewed pages vs 0 true ones.
HEB_OP_ISLAND_PAT = re.compile(
    r'[\u05d0-\u05ea]\s*\\en\{\s*(?:=|<|>|\\(?:approx|le|ge|ne|sim|leq|geq)(?![A-Za-z]))'
    r'\s*(?!\})[^\s]')
# v3.25: an \en island whose ENTIRE content is a rightward arrow —
# \en{$\to$} between Hebrew words. The island exemption below is for arrows
# with LATIN operands inside the island (the documented merge fix); an
# arrow-only island between Hebrew still points against the reading direction.
ARROW_ONLY_EN_PAT = re.compile(
    r'\\en\{\s*\$?\s*\\(?:to|rightarrow|Rightarrow|longrightarrow|Longrightarrow|implies)\b\s*\$?\s*\}')
# v3.27: an \en island whose content ENDS with a colon (\en{Offset:}) while
# Hebrew continues after it on the line. Inside the LTR island the colon is
# the LAST glyph, i.e. the island's RIGHT edge — which in the RTL flow is
# what the reader meets FIRST: the label renders ":Offset" with an orphaned
# colon hanging before the word (proven side-by-side; caught by a reader on
# a real page). Fix: move the colon OUT of the island — \en{Offset}: — where
# it takes the paragraph (RTL) direction and lands between the word and the
# content it introduces. An island with no Hebrew after it on the line (a
# standalone TikZ node label, an all-Latin table cell) reads pure LTR and
# stays silent; so does an internal colon (\en{Note: caching}).
# When MATH follows the label instead of Hebrew (איור \en{1a:} $I_D$), the
# colon-outside form trips ISLAND-NEXT-TO-MATH — there the fix is the #9
# merge: ONE island with the math inside, \en{1a: $I_D$} (verified: renders
# identically correct).
# v3.29: generalized within \en, all proven by render (same orphan mechanism,
# same fix): one nesting level is allowed ('\en{\code{Offset}:}' used to evade
# the [^{}]* content), and the trapped punctuation class covers ; ! ? too
# ('\en{halt;}' -> "הוראה; halt", '\en{why not RISC?}' -> the ? orphans onto
# the Hebrew, '\en{n?}' shipped mirrored in a reviewed lakit). Comma is NOT in
# the class (unproven). \code/\texttt are DELIBERATELY exempt — measured on
# the corpus: their trailing punctuation is token CONTENT (a C statement's ';',
# an asm label's ':', an island holding only ';' as a mention), and the sweep
# fired 8 false positives on shipped, human-reviewed pages vs 0 true ones.
EN_TRAILING_COLON_PAT = re.compile(
    r'\\en\{(?:[^{}]|\{[^{}]*\})*[:;!?]\s*\}')

# B3 UNDEFINED-COMMON-MACRO — macros from packages this preamble does NOT load,
#   so they throw "Undefined control sequence": \enquote (csquotes), \SI/\qty/
#   \SIrange (siunitx). (\expval and \ketbra ARE provided by the preamble as of
#   v3.21, so they are deliberately NOT listed here.)
UNDEF_MACRO_PAT = re.compile(
    r'\\(enquote|SIrange|SIlist|SI|si|qtyrange|qtylist|qtyproduct|qty'
    r'|numrange|numlist|num|ang|unit|DeclareSIUnit)(?![A-Za-z])')
# B4 (v3.23.6) PROVIDECOMMAND-PRIMITIVE — \providecommand{\ni}{n_{\mathrm i}} is
#   a SILENT NO-OP: \ni (the ∋ relation), \Re, \Im, \det ... are TeX primitives /
#   LaTeX-kernel math commands, so the name is already defined and \providecommand
#   does nothing. Every \ni then renders as ∋ ("np=∋²") — compiles clean, no
#   source signal; caught only on a rendered page in a real build (DEFECTS BLD-9).
#   Fix: \renewcommand (an explicit, loud override) or a different macro name.
#   v3.23.7 (adversarial review): single-letter KERNEL text commands added — the
#   classic shortcuts \d (differential), \i/\j (imaginary/dotless), \O (big-O),
#   \L/\l (Lagrangian/ell), \H (Hamiltonian), \S/\P (action/probability),
#   \b/\t/\v (bold/transpose/vector) are all kernel accents/glyphs (under-dot,
#   Ø, Ł, umlaut, §, ¶ ...), so \providecommand on them is the same silent no-op
#   with a DIFFERENT glyph than intended. Operators whose primitive meaning
#   equals the intended one (\arcsin, \angle) are deliberately NOT listed — the
#   no-op there renders exactly what was meant, no visual bug.
TEX_PRIMITIVE_SHADOW = (
    'ni|Re|Im|Pr|wp|top|bot|det|deg|gcd|hom|ker|dim|arg|exp|log|ln|lg'
    '|lim|limsup|liminf|min|max|sup|inf|sin|cos|tan|cot|sec|csc'
    '|sinh|cosh|tanh|coth|div|mod'
    '|d|i|j|O|L|l|H|S|P|b|t|v')
PROVIDE_PRIMITIVE_PAT = re.compile(
    r'\\providecommand\s*\*?\s*\{?\s*\\(?:' + TEX_PRIMITIVE_SHADOW + r')(?![A-Za-z])')


def _match_brace(s: str, open_idx: int) -> int:
    r"""s[open_idx] == '{'; return the index just past the matching '}'.
    v3.32: backslash-parity aware — a literal \{ / \} is CONTENT, not a
    delimiter (proven: \section{... \} ... \code{x}} crashed unflagged
    because the escaped brace "closed" the scan window early; same class in
    \code{a\}_b})."""
    depth = 0
    for j in range(open_idx, len(s)):
        if s[j] in '{}':
            k = j - 1
            while k >= 0 and s[k] == '\\':
                k -= 1
            if (j - 1 - k) % 2 == 1:
                continue                       # odd backslash run: escaped brace
        if s[j] == '{':
            depth += 1
        elif s[j] == '}':
            depth -= 1
            if depth == 0:
                return j + 1
    return len(s)


def _match_square(s: str, open_idx: int) -> int:
    r"""Return just past a balanced LaTeX optional argument.

    Square brackets inside a brace group are payload, not delimiters. This is
    why a regex such as ``[^\]]*`` is unsound for
    ``[\code{arr[i]}]``.
    """
    square_depth = 0
    brace_depth = 0
    for j in range(open_idx, len(s)):
        if s[j] in "[]{}":
            k = j - 1
            while k >= 0 and s[k] == "\\":
                k -= 1
            if (j - 1 - k) % 2 == 1:
                continue
        if s[j] == "{":
            brace_depth += 1
        elif s[j] == "}":
            brace_depth = max(0, brace_depth - 1)
        elif brace_depth == 0 and s[j] == "[":
            square_depth += 1
        elif brace_depth == 0 and s[j] == "]":
            square_depth -= 1
            if square_depth == 0:
                return j + 1
    return len(s)


def _macro_definition_spans(text: str) -> list[tuple[int, int]]:
    r"""Balanced spans occupied by common TeX macro definitions.

    A ``\figcap`` inside the body of ``\newcommand{\srcfig}...`` is an
    implementation detail, not a document-body caption, and must not be
    subjected to the authoring adjacency rule.
    """
    spans: list[tuple[int, int]] = []
    command_def = re.compile(
        r"\\(?:newcommand|renewcommand|providecommand)\*?\s*")
    for match in command_def.finditer(text):
        i = match.end()
        if i < len(text) and text[i] == "{":
            i = _match_brace(text, i)
        else:
            cs = re.match(r"\\(?:[A-Za-z@]+|.)", text[i:])
            if not cs:
                continue
            i += cs.end()
        while True:
            i += len(text[i:]) - len(text[i:].lstrip())
            if i < len(text) and text[i] == "[":
                end = _match_square(text, i)
                if end == len(text) and text[-1:] != "]":
                    break
                i = end
                continue
            break
        i += len(text[i:]) - len(text[i:].lstrip())
        if i < len(text) and text[i] == "{":
            spans.append((match.start(), _match_brace(text, i)))

    primitive_def = re.compile(
        r"\\(?:long\s*)?\\(?:def|gdef|edef|xdef)\s*\\(?:[A-Za-z@]+|.)")
    for match in primitive_def.finditer(text):
        i = match.end()
        while i < len(text):
            if text[i] == "{":
                spans.append((match.start(), _match_brace(text, i)))
                break
            i += 1
    return spans


def _iter_figcap_calls(text: str):
    """Yield document-body ``\figcap`` call positions with balanced args."""
    definitions = _macro_definition_spans(text)
    for match in re.finditer(r"\\figcap(?![A-Za-z@])", text):
        if any(start <= match.start() < end for start, end in definitions):
            continue
        i = match.end()
        i += len(text[i:]) - len(text[i:].lstrip())
        if i < len(text) and text[i] == "[":
            end = _match_square(text, i)
            if end == len(text) and text[-1:] != "]":
                continue
            i = end
            i += len(text[i:]) - len(text[i:].lstrip())
        if i < len(text) and text[i] == "{":
            yield match.start()


def _collect_env_aliases(text: str, inner: 're.Pattern') -> set:
    r"""v3.82 (audit finding A): names of \newenvironment wrappers whose
    BEGIN-CODE opens an environment matching `inner`. Replaces v3.76's
    same-line lookahead, whose HONEST LIMIT turned out not to be academic:
    data-science-exams/src/macros.tex:63 defines `choices` over four source
    lines —
        \newenvironment{choices}{%
          \setcounter{chcnt}{0}\par\smallskip
          \begin{list}{}{...}%
        }{\end{list}\par\smallskip}
    — so a same-line collector still returns the empty set and all 54
    render-broken sites stay invisible. `text` must already be
    comment-stripped per line and re-joined. Precise rather than greedy: the
    optional [n][default] args are skipped and the FIRST brace group (the
    begin-code) is brace-matched, so an `inner` appearing only in the END
    code — where it closes an environment rather than opening one — is not
    collected."""
    out = set()
    for m in re.finditer(r'\\(?:re)?newenvironment\s*\*?\s*\{([A-Za-z@]+)\}',
                         text):
        i = m.end()
        while True:
            while i < len(text) and text[i] in ' \t\n':
                i += 1
            if i < len(text) and text[i] == '[':
                j = text.find(']', i)
                if j < 0:
                    break
                i = j + 1
                continue
            break
        if i < len(text) and text[i] == '{' and inner.search(
                text[i:_match_brace(text, i)]):
            out.add(m.group(1))
    return out


def _heading_fragile_defects(htxt: str) -> set[str]:
    r"""Return fragile/block constructs that are invalid in a heading.

    ``\code`` is deliberately absent: preamble.tex makes it robust and gives
    hyperref a plain-string expansion, so it is valid in numbered headings.
    ``\codeline`` is a paragraph/block command and remains invalid in any
    heading. An unprotected footnote remains a fragile moving argument.
    """
    defects: set[str] = set()
    if re.search(r'\\codeline\s*\{', htxt):
        defects.add("BLOCK-IN-HEADING")
    if re.search(r'(?<!\\protect)\\footnote\s*\{', htxt):
        defects.add("FOOTNOTE-IN-HEADING")
    return defects


def _heading_has_bare_math(htxt: str) -> bool:
    """True if a heading group's OWN text carries a bare $...$ that reaches the
    bookmark (BIDI-15 corruption). v3.49: mirrors the arg-scan CODE-IN-HEADING
    got in v3.31 — the old whole-line check FP'd a run-in `\\paragraph{X} prose
    with $x$` (the math is BODY, never in the moving argument). A
    \\texorpdfstring{$m$}{ascii} group is the sanctioned rescue (the ascii arg
    feeds the bookmark), so both its args are stripped before the test."""
    out, i = [], 0
    while True:
        m = re.search(r'\\texorpdfstring\s*\{', htxt[i:])
        if not m:
            out.append(htxt[i:])
            break
        out.append(htxt[i:i + m.start()])
        a1e = _match_brace(htxt, i + m.end() - 1)
        m2 = re.match(r'\s*\{', htxt[a1e:])
        i = a1e if not m2 else _match_brace(htxt, a1e + m2.end() - 1)
    return bool(re.search(r'(?<!\\)\$', ''.join(out)))


# Inline-comment strip, backslash-parity aware (same rule as the main scan loop).
_COMMENT_SUB = (r'(?<!\\)((?:\\\\)*)%.*', r'\1')


def _brace_group(s: str, brace_pos: int) -> str:
    """Content of the {..} group whose '{' is at s[brace_pos] (v3.46; string-
    local twin of _text_content for scanning INSIDE an already-extracted group,
    e.g. the \\text{..} segments inside a \\boxed/\\finalans body)."""
    depth = 0
    for j in range(brace_pos, len(s)):
        if s[j] == '{':
            depth += 1
        elif s[j] == '}':
            depth -= 1
            if depth == 0:
                return s[brace_pos + 1:j]
    return s[brace_pos + 1:]


def _text_content(lines, li: int, code: str, brace_pos: int) -> str:
    """Content inside a \\text{...} whose '{' is at code[brace_pos] (code = the
    comment-stripped source line at 0-based index `li`). If the group closes on
    this line, return that (fast path). If it SPANS a source line break, join the
    following comment-stripped lines and match there — closing the v3.23.5
    KNOWN-LIMITATION blind spot where a multi-line \\text hid its parens/caret/colon
    from the line-based scans (e.g. \\text{(\\en{weak})} split across two lines
    still mirrors to ")weak(" but used to evade #7/#7b/B1/MATH-TEXT-EN-COLON)."""
    depth = 0
    for j in range(brace_pos, len(code)):
        if code[j] == '{':
            depth += 1
        elif code[j] == '}':
            depth -= 1
            if depth == 0:
                return code[brace_pos + 1:j]            # closed on this line
    # spans lines: join the rest of the file (comment-stripped) and match
    # there. v3.33: a line ending in a REAL comment % EATS its newline (TeX
    # semantics) — join those with NO separator; a plain line break is a
    # space. Proven by render: \text{%⏎\en{(x)}} is CORRECT (was an FP of
    # the #7c whitespace rule) while \text{⏎\en{(x)}} mirrors.
    def _sep(raw_line):
        return '' if re.search(r'(?<!\\)(?:\\\\)*%', raw_line) else '\n'
    parts, seps = [code[brace_pos:]], []
    for k in range(li, len(lines) - 1):
        seps.append(_sep(lines[k]))
    tail = [re.sub(_COMMENT_SUB[0], _COMMENT_SUB[1], lines[k])
            for k in range(li + 1, len(lines))]
    combined = parts[0]
    for t, sep in zip(tail, seps):
        combined += sep + t
    d = 0
    for j in range(len(combined)):
        if combined[j] == '{':
            d += 1
        elif combined[j] == '}':
            d -= 1
            if d == 0:
                return combined[1:j]
    return combined[1:]                                 # unbalanced source


def _parens_wrap_only_latin(content: str) -> bool:
    """True if a ( ) or [ ] pair in the \\text{} BASE wraps ONLY a Latin island
    (\\en/\\code/\\texttt) — e.g. \\text{(\\en{weak})}. There the parens sit in the
    RTL \\text base, OUTSIDE the LTR island, so they MIRROR to ")weak(". The fix is
    to move the parens INSIDE the island: \\text{\\en{(weak)}}. Parens that also
    enclose Hebrew (\\text{(הספק ב־\\en{CMOS})}) render fine and are NOT flagged —
    those are Hebrew-directional parens. This is the blind spot of the plain #7
    scan, which strips \\en first and then sees only empty "()" (no Latin left)."""
    s = content
    s = s.replace(r'\(', '  ').replace(r'\)', '  ')   # escaped parens: literal
    s = s.replace(r'\[', '  ').replace(r'\]', '  ')
    s = re.sub(r'\$[^$]*\$', ' ', s)                  # nested $...$ math is fine
    s = LATIN_ISLAND.sub('\x01', s)                   # Latin island -> marker
    s = re.sub(r'\\h\{(?:[^{}]|\{[^{}]*\})*\}', '\x02', s)  # Hebrew island -> marker
    stack = []
    for i, ch in enumerate(s):
        if ch in '([':
            stack.append((ch, i))
        elif ch in ')]':
            if not stack:
                continue
            op, oi = stack.pop()
            if (op, ch) not in (('(', ')'), ('[', ']')):
                continue
            interior = s[oi + 1:i]
            if '\x01' not in interior:                # no Latin island inside
                continue
            if '\x02' in interior:                    # a Hebrew island inside -> fine
                continue
            if re.search(r'[\u0590-\u05ff]', interior):  # bare Hebrew inside -> fine
                continue
            # strip the Latin markers + neutral separators; anything left means the
            # parens also wrap non-Latin text (a function name etc.) — handled by #7.
            core = interior.replace('\x01', '')
            core = re.sub(r'[\s,.;:/+\-–—]', '', core)
            if core == '':                            # parens wrap ONLY Latin island(s)
                return True
    return False


def math_mask(code: str, state: dict):
    """Return (mask, state): mask[i] True iff code[i] is in math mode.

    state carries cross-line block math: {'display': bool, 'env': int}.
    Handles inline $...$, \\[ \\], and the display-math environments above.
    """
    n = len(code)
    mask = [False] * n
    # inline-$ state is carried ACROSS lines (a $...$ split over a line break is
    # legal); a blank line resets it (TeX itself errors on a blank line in math,
    # so this self-heals a stray unmatched $).
    if not code.strip():
        state['inline'] = False
        state['paren'] = False
    inline = state.get('inline', False)
    i = 0
    while i < n:
        # LaTeX line break  \\  (optionally \\[len]) — consume both backslashes
        # FIRST, so a following '[' is not misread as \[ (display-math open).
        if code.startswith('\\\\', i):
            cur = inline or state['display'] or state['env'] > 0
            mask[i] = cur
            mask[i + 1] = cur
            i += 2
            continue
        if not inline:
            m = MATH_ENV_BEGIN.match(code, i)
            if m:
                state['env'] += 1
                for k in range(i, m.end()):
                    mask[k] = True
                i = m.end()
                continue
            m = MATH_ENV_END.match(code, i)
            if m:
                for k in range(i, m.end()):
                    mask[k] = True
                state['env'] = max(0, state['env'] - 1)
                i = m.end()
                continue
            if code.startswith(r'\[', i):
                state['display'] = True
                mask[i] = mask[i + 1] = True
                i += 2
                continue
            if code.startswith(r'\]', i):
                mask[i] = mask[i + 1] = True
                state['display'] = False
                i += 2
                continue
        if code.startswith(r'\$', i):                 # escaped dollar (literal)
            cur = inline or state['display'] or state['env'] > 0 or state.get('paren', False)
            mask[i] = mask[i + 1] = cur
            i += 2
            continue
        # \( ... \) inline math (standard LaTeX; can span lines)
        if code.startswith(r'\(', i) and not inline:
            state['paren'] = True
            mask[i] = mask[i + 1] = True
            i += 2
            continue
        if code.startswith(r'\)', i):
            mask[i] = mask[i + 1] = True
            state['paren'] = False
            i += 2
            continue
        # $$ display toggle — treat the PAIR as one delimiter (plain-TeX display)
        if code.startswith('$$', i):
            state['display'] = not state['display']
            mask[i] = mask[i + 1] = True
            i += 2
            continue
        if code[i] == '$':
            inline = not inline
            mask[i] = True
            i += 1
            continue
        mask[i] = inline or state['display'] or state['env'] > 0 or state.get('paren', False)
        i += 1
    state['inline'] = inline
    return mask, state


_TEXT_OPEN = re.compile(r'\\(?:text|mbox|intertext|shortintertext)\{')


def _line_text_spans(code: str, carry_depth: int):
    """(v3.23.7) intext[i] = True where code[i] sits inside a \\text{...}/
    \\mbox{...} group — INCLUDING a group carried open from a previous line
    (carry_depth > 0). Returns (intext, new_carry_depth). This closes the
    LANG-RAW-IN-MATH false positive on the continuation lines of a multi-line
    \\text: an \\en{...} there is legitimately inside the \\text, but the
    line-based _blank_text_mbox cannot know that."""
    intext = [False] * len(code)
    depth = carry_depth
    starts = {m.end() - 1 for m in _TEXT_OPEN.finditer(code)}
    for i, ch in enumerate(code):
        if depth > 0:
            intext[i] = True
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
        elif i in starts:
            depth = 1
            intext[i] = True
    return intext, depth


def _blank_text_mbox(code: str) -> str:
    """Replace every \\text{...}/\\mbox{...}/\\tag{...} group (with content) by
    spaces, preserving length so positions still align with the math mask. Lets a
    \\h/\\en INSIDE such a group not count as 'bare in math'. v3.50: \\tag{}/\\tag*{}
    is included — its argument is TEXT mode (amsmath), so \\tag{\\h{א}} for a Hebrew
    equation label renders '(א)' cleanly, yet was a LANG-RAW-IN-MATH false positive
    (it sits in a math env, so mask is True and the old blank list missed it)."""
    out = list(code)
    for mm in re.finditer(r'\\(?:text|mbox|intertext|shortintertext|tag\*?)\{', code):
        b = mm.end() - 1                      # index of the '{'
        end = _match_brace(code, b)
        for k in range(mm.start(), end):
            out[k] = ' '
    return ''.join(out)


def _wrapper_depth(code: str):
    """depth[i] = how many \\en{...}/\\mbox{...} groups CONTAIN position i (inside
    the braces). Used so an island already wrapped in an outer LTR container
    (\\en{\\code{X}$\\to$Y}) is not flagged by the island-next-to-math check."""
    depth = [0] * len(code)
    for m in re.finditer(r'\\(?:en|mbox)\{', code):
        b = m.end() - 1                       # index of the '{'
        end = _match_brace(code, b)           # past the matching '}'
        for k in range(b + 1, end - 1):       # strictly inside the braces
            depth[k] += 1
    return depth


def _brackets_balanced(s: str) -> bool:
    """v3.51: True if the bracket-only string s is a BALANCED, properly-nested
    sequence of () and [] (non-empty). \\en{()}/\\en{[]} — empty function args,
    an empty list — are LTR-island balanced pairs that render correctly, unlike a
    LONE bracket (\\en{(}, the BIDI-17 mirror). Used to exempt the former."""
    st, pairs = [], {')': '(', ']': '['}
    for c in s:
        if c in '([':
            st.append(c)
        elif c in ')]':
            if not st or st[-1] != pairs[c]:
                return False
            st.pop()
    return not st and bool(s)


def latin_outside_isolation(inner: str) -> bool:
    """True if `inner` has real Latin once \\command names and isolated
    (\\en/\\code/\\texttt) spans are removed."""
    s = re.sub(r'\\(en|code|texttt)\{[^{}]*\}', '', inner)
    s = re.sub(r'\\[a-zA-Z]+', '', s)
    return bool(re.search(r'[A-Za-z]', s))


_VI_MATH_SEG = re.compile(r'(?<!\\)\$[^$]*\$|\\\((?:[^\\]|\\[^)])*?\\\)')
# v3.82 (audit finding L): the value side accepts a QUOTED value. The v3.42.0
# class excluded " and ', so `activation = "relu"` scored 0 pairs and
# \en{Dense layer (units = 100, activation = "relu")} — two pairs by the
# host collection's own ">=2 name = value -> block form" authoring rule —
# shipped as a single island four times, in the SAME commit that wrote the rule,
# in the same lists whose unquoted neighbours got the block form. Clean A/B
# measured before the change: the identical string with bare `relu` fires,
# with "relu" does not, with 'relu' does not. Which side is wrong is settled by
# the MECHANISM, not by taste: BIDI-26's tear is a line break at an INTERNAL
# SPACE inside the island, and a quote character does not remove the space,
# shorten the island, or change the RTL seam — so the doctrine is right and
# the regex was under-inclusive. Re-swept after widening: 0 new flags over the
# 335 CI sources + 12 final.tex beyond the 4 named sites (the quote must sit
# directly after `= `, so prose apostrophes and \code{s = ''} are untouched).
_VI_EQ_PAIR = re.compile(r'[\w\])] *(?<![=<>!])=(?!=) *[\w$\\("\'-]')


def _is_value_list_island(inner: str) -> bool:
    """True if an \\en{...} body is a BREAKABLE VALUE LIST — >=2 name=value
    PAIRS plus a space outside the math: render-proven (v3.42.0 empirical
    round) to tear at an internal space at the line end, orphaning a label
    from its value across the RTL seam. A PAIR is an inline-math segment
    ($..$/\\(..\\)) that CONTAINS '=', or a mathless "name = value".
    Calibration (v3.42.0, 0-FP on the corpus): segments WITHOUT '='
    (\\en{Si$(p)$ / Ge$(n)$}, \\en{$I_D$ or $g_D$}, \\en{$0.1$--$10$ MeV})
    are short MENTION islands — the documented adjacency-merge fix, not a
    value list; an escaped \\$ (register names \\code{\\$s0}) is not a math
    delimiter; and "=="/"<="/">="/"!=" are code-operator mentions."""
    segs = _VI_MATH_SEG.findall(inner)
    mathless = _VI_MATH_SEG.sub('', inner)
    pairs = sum(1 for s in segs if '=' in s) \
        + len(_VI_EQ_PAIR.findall(mathless))
    return pairs >= 2 and ' ' in mathless


# v4.16.0 (BIDI-81): a QUOTED LITERAL inside an LTR island.  BIDI-26's tear is
# a line break at an INTERNAL SPACE inside the island; the pairs requirement of
# BREAKABLE-VALUE-ISLAND is a property of the EXAMPLE it was found in, not of
# the mechanism.  Render-measured on a 26-offset sweep (one paragraph per page,
# glyph geometry identical over 4 clean compiles): an 8-word prose island tears
# at 10/26 line offsets, a 6-word one at 6/26, a 3-word one at 2/26, the
# value-list exemplar at 3/26 -- so the flag that existed fired on the RAREST
# shape and stayed silent on the most frequent one.  A single-word island and
# an \mbox'd island of ANY length tear at 0/26.
#
# The damage that is not taste: a quoted literal is EVIDENCE -- a terminal
# message, a shell argument, a commit message, a book title -- and the tear
# puts its opening mark at the left margin of one line and its closing mark at
# the right margin of the next, with a full line of Hebrew between them.  The
# reader cannot read it as one unit and cannot copy it at all.  Doctrine, in
# the shape of BIDI-26's "a list is a structure, not an island": a QUOTATION is
# a structure too -- \mbox for a literal that fits, \codeline / a listing /
# a display for one that would overflow the margin.
_QUOTE_PAIRS = (('“', '”'), ('„', '”'),
                ('‘', '’'), ('``', "''"), ('"', '"'))
# A straight apostrophe is a quote only when it does NOT sit inside a word:
# "Amdahl's Law", "don't", "users' data" must stay silent, `echo 'n is 3'` and
# `alias ll='ls -lh'` must fire.  Measured over the corpus below.
_APOS_LITERAL = re.compile(r"(?<![A-Za-z0-9])'([^'\n]{2,}?)'(?![A-Za-z0-9])")
_BOX_OPEN = re.compile(r'\\(?:mbox|hbox)\s*\{')
# v4.19.0: the island's THIRD spelling.  \en is *defined* as
# \foreignlanguage{english}{...} (preamble line 266), so the explicit form is
# the same rendered island and tears at the same internal space -- the package's
# own example_math.tex shipped a quoted citation title in it, unseen by the rule
# that already covered \en and \code.  Measured over the 598-file CI scan:
# 1 true positive (that asset), 0 false positives -- the preamble's own
# \foreignlanguage definitions take a parameter, never a literal.
_ISLAND_OPEN = r'\\(?:en|code)\s*\{|\\foreignlanguage\s*\{english\}\s*\{'


def _blank_boxes(s: str) -> str:
    r"""Replace a complete atomic box with a NON-space placeholder.

    Inventing a space here would claim a breakpoint that TeX cannot take, e.g.
    in \en{“alpha\mbox{ beta }gamma”}. Entire boxed quotes remain exempt.
    """
    out, i = [], 0
    while True:
        m = _BOX_OPEN.search(s, i)
        if not m:
            out.append(s[i:])
            return ''.join(out)
        j = _match_brace(s, m.end() - 1)
        out.append(s[i:m.start()])
        out.append('\ufffc')
        i = j


def _quoted_literal(inner: str):
    r"""Find any literal quote with a source-space outside atomic boxes/math.

    This is a bounded source risk detector, not TeX expansion or a prediction
    of the actual line breaks. The FIRST single-word quote must not conceal a
    later multi-word quote using the same marks. Math primes are not quotes.
    """
    s = _blank_boxes(_VI_MATH_SEG.sub('\ufffc', inner))
    for opening, closing in _QUOTE_PAIRS:
        pos = 0
        while True:
            i = s.find(opening, pos)
            if i < 0:
                break
            j = s.find(closing, i + len(opening))
            if j < 0:
                break
            body = s[i + len(opening):j]
            if any(c.isspace() for c in body.strip()):
                return body
            pos = j + len(closing)
    for m in _APOS_LITERAL.finditer(s):
        if any(c.isspace() for c in m.group(1).strip()):
            return m.group(1)
    return None


def _active_quote_command(text: str, pos: int) -> bool:
    """Reject the second slash of a control-symbol pair; keep a third slash."""
    n, i = 0, pos - 1
    while i >= 0 and text[i] == '\\':
        n += 1
        i -= 1
    return n % 2 == 0


def _quote_wrapper_depth(text: str) -> list[int]:
    r"""Containing islands/boxes for this rule only; includes source whitespace.

    Shared adjacency-rule depth semantics are intentionally left untouched.
    The complete paragraph keeps a box opened on the preceding source line.
    """
    delta = [0] * (len(text) + 1)
    for m in re.finditer(_ISLAND_OPEN + '|' + _BOX_OPEN.pattern, text):
        if not _active_quote_command(text, m.start()):
            continue
        end = _match_brace(text, m.end() - 1)
        if end == len(text) and text[-1:] != '}':
            continue
        delta[m.end()] += 1
        delta[end - 1] -= 1
    depth, active = [], 0
    for change in delta[:-1]:
        active += change
        depth.append(active)
    return depth


def _is_subsup_label(code: str, pos: int) -> bool:
    """True if the \\text{ starting at `pos` is a sub/superscript LABEL
    (\\underbrace{..}_{\\text{..}}, x^{\\text{..}}, \\xrightarrow{\\text{..}})
    rather than an operand — labels render RTL fine and are not the bug."""
    k = pos - 1
    while k >= 0 and code[k] == '{':
        k -= 1
    while k >= 0 and code[k] in ' \t':
        k -= 1
    return k >= 0 and code[k] in '_^'


def _skip_xarrow_args(code: str, k: int) -> int:
    """Skip an x-arrow's optional [below] and {above} arguments starting at k,
    so we can inspect the real operand that follows."""
    while k < len(code) and code[k] in '[{':
        opn = code[k]
        cls = ']' if opn == '[' else '}'
        depth = 1
        k += 1
        while k < len(code) and depth:
            if code[k] == opn:
                depth += 1
            elif code[k] == cls:
                depth -= 1
            k += 1
    return k


# v4.7.4: spacing an author may put between an arrow and its operand. `\s` alone
# is NOT enough — a LaTeX spacing MACRO is the house idiom around display arrows
# (`\ \Longrightarrow\ `, `\;\xrightarrow{..}\;`) and it kept the operand out of
# reach of the old `\s*` prefix. Same alphabet as BARE_RARROW_DOLLAR_PAT, which
# had already learned this lesson for form (a).
_ARROW_SPACE = r'(?:\s|\\[;,:!>| ]|\\quad|\\qquad)*'
_ARROW_SPACE_TAIL = re.compile(_ARROW_SPACE + r'$')
_ARROW_SPACE_HEAD = re.compile(_ARROW_SPACE)
# \text ONLY. The font-switching family (\textrm/\textbf/\textit/...) was tried
# and REMOVED. It bought nothing measurable — 230 of 230 detections over the
# corpus that motivated this rule came from \text{, none from any variant — and
# it put the matcher out of step with the rule as SKILL.md, pitfalls.md and
# direction-and-math.md all state it, which speak only of \text{עברית}. \text is
# the math-mode text escape; \textbf and friends are prose commands that merely
# also work in math, and treating prose bold as a math operand is a widening the
# evidence does not support.
_TEXT_CMD_PAT = re.compile(r'\\text\s*\{')


def _text_body_hebrew(code: str, tstart: int) -> int:
    r"""code[tstart:] starts with a \text-family command. Return the index just
    past its BALANCED body when that body carries a Hebrew letter, else -1.

    v4.7.4: the body scan must be brace-DEPTH aware. The previous `\text\{[^{}]*`
    form could not cross the '{' of an inner group, so `\text{\h{...}}` — the
    idiom every Hebrew collection in the fleet uses around an arrow — read as
    "no Hebrew here" and #12(b) went silent on it (measured: 0 hits over 19
    collections that between them carry the defect a dozen times)."""
    b = code.find('{', tstart)
    if b < 0:
        return -1
    end = _match_brace(code, b)
    return end if HEB_CHAR2.search(code[b:end]) else -1


def _arrow_operand_hebrew(code: str, i: int, j: int) -> bool:
    """The immediate left/right operand of an arrow spanning code[i:j] is a
    Hebrew \\text{...} block or raw Hebrew (so the arrow flips under RTL).

    "Immediate" is exact, not a fixed window: the operand must end (left) or
    begin (right) flush against the arrow once math spacing is stripped. A
    Hebrew \\text further out on the line is a different operand and stays
    silent — that is what keeps a pure-math arrow inside a Hebrew-annotated
    formula (`..+\\text{\\h{צ״מ}} \\xrightarrow{..} m_e=g_e v`) exempt."""
    # ---- right operand: skip an x-arrow's [below]{above} args, then spacing
    rstart = _skip_xarrow_args(code, j)
    rstart = _ARROW_SPACE_HEAD.match(code, rstart).end()
    m = _TEXT_CMD_PAT.match(code, rstart)
    if m and _text_body_hebrew(code, m.start()) > 0:
        return True
    if rstart < len(code) and HEB_CHAR2.match(code[rstart]):
        return True
    # ---- left operand: strip the spacing tail, then require a Hebrew \text
    # that CLOSES exactly there (or a bare Hebrew letter)
    lend = _ARROW_SPACE_TAIL.search(code, 0, i).start()
    if lend > 0 and HEB_CHAR2.match(code[lend - 1]):
        return True
    for t in _TEXT_CMD_PAT.finditer(code, 0, lend):
        if _text_body_hebrew(code, t.start()) != lend:
            continue
        # GLUED to the token before it => the \text is a TERM inside a larger
        # expression, and the EXPRESSION is the arrow's operand, not the Hebrew.
        # `\Lang_Y=..+\text{\h{צ״מ}} \xrightarrow{..} m_e=g_e v` is a derivation
        # between two equations; both operands are math and the LTR arrow is
        # right. Measured over the fleet: a left-operand Hebrew \text is preceded
        # ONLY by space, line start or '(' (97/30/15 of 142) — never by a math
        # token — so this guard costs no real detection and closes the class.
        if t.start() and code[t.start() - 1] not in ' \t([{$,;&':
            continue
        return True
    return False


def _glued_math_object(code: str):
    """v3.47 HEBREW-MATH-GLUED-OBJECT: yield the start index of each \\text{Hebrew
    phrase} (ending in space or maqaf) that is immediately followed by its bound
    math object — a lone atom + closing/separator terminator, a (tuple), or a
    number sandwiched before another \\text. New-clause subjects (atom then =/\\to)
    are excluded by the terminator whitelist. Line-local: the \\text and its
    object sit on one line in every render-proven case."""
    for tm in re.finditer(r'\\(?:text|mbox)\{', code):
        b = tm.end() - 1
        e = _match_brace(code, b)          # index JUST PAST the closing '}'
        if e >= len(code) and code[-1:] != '}':
            continue                        # unbalanced (ran to end without close)
        content = code[b + 1:e - 1]         # exclude the closing '}'
        if not re.search(r'[א-ת]', content):
            continue
        if not (content.endswith(' ') or content.endswith(GLUED_MAQAF)):
            continue
        after = code[e:]                    # right after the '}'
        rest = after[re.match(_G_SEP, after).end():]
        mv = _G_VAR.match(rest)
        if mv and _G_TERM.match(rest[mv.end():]):
            yield tm.start(); continue
        mt = _G_TUPLE.match(rest)
        if mt and _G_TERM.match(rest[mt.end():]):
            yield tm.start(); continue
        if _G_NUM_TEXT.match(rest):
            yield tm.start()


def _orphan_percent(line: str):
    """v3.48 UNESCAPED-PERCENT: a literal '%' that starts a comment glued to
    content silently EATS the rest of the line — content vanishes from the PDF
    with NO compile warning (proven: "30% מהמקרים" renders "30"). Fires on the
    two confident, 0-FP shapes: (A) a digit immediately before the comment '%'
    (a percent sign that needs \\%: "30%"), or (B) real content glued on BOTH
    sides ("word%word", "5%3"). A real comment (' % note', line-start '%', a
    '%%%%' rule, or the 'foo%' line-break-suppression idiom) has a SPACE before
    the '%' or nothing after it, and is left silent. Caller guarantees the line
    is not inside a verbatim/lstlisting block. Returns an evidence snippet or
    None."""
    # blank inline literal spans where '%' is NOT a comment (\verb|..|, code, url)
    s = re.sub(r'\\(?:verb\*?|lstinline)\s*(\|[^|\n]*\||![^!\n]*!)',
               lambda m: ' ' * len(m.group()), line)
    s = re.sub(r'\\(?:code|codeline|texttt|url|path|href|nolinkurl)\s*\{[^{}]*\}',
               lambda m: ' ' * len(m.group()), s)
    p = -1
    for m in re.finditer(r'%', s):
        i = m.start()
        k, bs = i - 1, 0
        while k >= 0 and s[k] == '\\':
            bs += 1
            k -= 1
        if bs % 2 == 0:        # not \%-escaped -> this is the comment start
            p = i
            break
    if p <= 0:                 # no comment, or a line-start comment (nothing eaten)
        return None
    before = s[p - 1]
    after = s[p + 1] if p + 1 < len(s) else ''
    if before.isdigit():                                   # (A) "30%" -> missing \%
        return line[max(0, p - 8):p + 8].strip()
    if (before not in ' \t'                                # (B) content%content glued
            and (after.isalnum() or '֐' <= after <= '׿')):
        return line[max(0, p - 8):p + 8].strip()
    return None


def _inline_literal_calls(text: str, *, skip_code=False):
    r"""Yield actual inline-literal command starts and completed boundaries.

    Control symbols consume their two characters, so even backslash runs do
    not turn the following literal word into a command. Delimiter semantics
    belong to the common heading helper. Incomplete literals receive no mask.
    The RTL detector additionally skips balanced, known code/path arguments;
    arbitrary macro bodies retain their existing bounded source treatment.
    """
    groups = clean_source(text) if skip_code else text
    i = 0
    while i < len(text):
        if text[i] == '%':
            end = text.find('\n', i)
            i = len(text) if end < 0 else end
            continue
        command = COMMAND.match(text, i)
        if not command:
            i += 1
            continue
        i = command.end()
        if skip_code and command[1] in {'code', 'codeline', 'texttt', 'url',
                                        'path', 'href', 'nolinkurl'}:
            body = group(groups, i)
            if body:
                i = body[1]
                continue
        if command[1] in {'verb', 'lstinline'}:
            stop = inline_literal_end(text, i, command[1])
            yield command.start(), stop
            if stop is not None:
                i = stop


def _blank_inline_literals(line: str) -> str:
    r"""Blank only completed, actual \verb/\lstinline calls; retain positions."""
    chars = list(line)
    for start, end in _inline_literal_calls(line):
        if end is not None:
            chars[start:end] = ['\n' if c == '\n' else ' ' for c in line[start:end]]
    return ''.join(chars)



def _english_inline_ranges(lines: list[str]) -> dict[int, list[tuple[int, int]]]:
    r"""Map explicit, balanced English islands to surviving source coordinates.

    Only direct \en and \foreignlanguage{english} calls are recognized. This
    is a bounded lexical mask, not macro expansion. Keep newlines/columns and
    ignore comments and literal bodies so examples cannot open prose islands.
    An unclosed argument is deliberately not granted a whole-file exemption.
    """
    clean = clean_source('\n'.join(lines))
    pattern = re.compile(
        r'(?<!\\)\\(?:en\s*\{|foreignlanguage\s*\{\s*english\s*\}\s*\{)')
    spans: list[tuple[int, int]] = []
    covered_to = 0
    for match in pattern.finditer(clean):
        if match.start() < covered_to:
            continue
        start = match.end() - 1
        depth = 0
        end = None
        i = start
        while i < len(clean):
            char = clean[i]
            if char == '\\':
                i += 2  # escaped braces and escaped backslashes are literals
                continue
            if char == '{':
                depth += 1
            elif char == '}':
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
            i += 1
        if end is not None:
            spans.append((match.start(), end))
            covered_to = end
    result: dict[int, list[tuple[int, int]]] = {}
    offset = 0
    span_index = 0
    for number, line in enumerate(clean.split('\n'), 1):
        stop = offset + len(line)
        while span_index < len(spans) and spans[span_index][1] <= offset:
            span_index += 1
        j = span_index
        while j < len(spans) and spans[j][0] < stop:
            first, last = spans[j]
            a, b = max(first, offset) - offset, min(last, stop) - offset
            if a < b:
                result.setdefault(number, []).append((a, b))
            j += 1
        offset = stop + 1
    return result


def scan_file(path: str, extra_ltr_aliases=frozenset(),
              extra_list_aliases=frozenset(), active_capabilities=frozenset(),
              active_language=None, *, language_context=None):
    issues = []
    try:
        # v3.71: NOT .splitlines() — Python also splits on U+2028/U+2029/U+0085,
        # which LuaTeX does NOT treat as line endings. A pasted U+2028 was
        # consumed as a separator: it appeared in NO line the gates saw, and
        # every later line number shifted by one. Normalise \r\n/\r, split on
        # \n only — LuaTeX's actual line model.
        with open(path, encoding='utf-8') as source_file:
            lines = (source_file.read()
                     .replace('\r\n', '\n').replace('\r', '\n').split('\n'))
        # Architecture policy is capability-driven, not filename-driven.
        # v4.7.1: pure composition moved clean presentation to clean_theme.tex
        # while clean_variant.tex remains only a generated legacy carrier. A
        # checker that keys on the legacy filename silently disconnects from
        # new documents. Scope capabilities are collected across the resolved
        # source set by main(); direct policy tokens are also recognized for
        # assembled/generated one-file sources. exam_components.tex alone does
        # NOT imply either policy.
        source_caps = set(active_capabilities)
        source_caps.update(capabilities_from_text('\n'.join(lines)))
        policy_hide_section_numbering = CAP_HIDE_SECTION_NUMBERING in source_caps
        policy_showonlyrefs = CAP_SHOWONLYREFS in source_caps
        # v3.76: is this a DOCUMENT-layer file? Keys TOC-OVERRIDE-IN-DOCUMENT
        # so preamble.tex (which legitimately owns \l@section) stays exempt —
        # it carries no \begin{document}; main.tex and final.tex both do.
        # Computed on comment-STRIPPED lines (envline discipline): the
        # preamble's own header shows '\begin{document}' inside a usage
        # COMMENT, which armed the raw-line version against the very file
        # that owns the BLD-38 fix (caught in this rule's 0-FP sweep).
        has_document = any(
            '\\begin{document}' in re.sub(_COMMENT_SUB[0], _COMMENT_SUB[1], _l)
            for _l in lines)
    except (OSError, UnicodeDecodeError) as e:
        return [(0, 'READ-ERROR', str(e))]

    # v4.18: evaluate heading numbering at the call, not a fixed depth=2.
    issues.extend(label_findings('\n'.join(lines)))
    english_inline_ranges = _english_inline_ranges(lines)
    language = language_context or LanguageContext('\n'.join(lines), active_language)
    inline_calls_by_line = {}
    raw_source = '\n'.join(lines)
    for start, _ in _inline_literal_calls(raw_source, skip_code=True):
        number = raw_source.count('\n', 0, start) + 1
        column = start - (raw_source.rfind('\n', 0, start) + 1)
        inline_calls_by_line.setdefault(number, []).append(column)
    in_tikz = False
    in_verbatim = False        # env NAME while inside a literal block (falsy = prose)
    # v3.83: one alternation, used by BOTH the opener and the closer, so the two
    # can never drift apart. v3.82 covered only the three unstarred names, so
    # `verbatim*`, `minted` and `alltt` bodies were scanned as PROSE and raised
    # QUOTES / UNESCAPED-PERCENT on literal content (false alarms). `comment` is
    # here for the same reason — its body is dead source, not TeX.
    _LIT = r'(verbatim\*?|lstlisting|Verbatim\*?|minted|alltt|comment)'
    _vb_open_ln = 0            # line where the currently-open literal block began
    in_bracket_disp = False    # v3.67: inside a (?<!\\)\\[ ... \\] display, cross-line
    center_depth = 0           # v3.41.1: display context for BREAKABLE-VALUE-ISLAND
    axis_stack = []
    # UNDEFINED-COMMON-MACRO: if the document actually loads the package, the
    # macros are defined — drop them from the blacklist for this file.
    _src = '\n'.join(lines)
    _has_siunitx = bool(re.search(r'\\usepackage(\[[^\]]*\])?\{[^}]*siunitx', _src))
    _has_csquotes = bool(re.search(r'\\usepackage(\[[^\]]*\])?\{[^}]*csquotes', _src))
    # v3.23 (merged design): FIRST PASS collects macros the document defines
    # itself — those are never flagged, without skipping the whole line (a
    # definition line may still USE another undefined macro in its body).
    user_defined = set()
    _DEF_PAT = re.compile(
        r'\\(?:(?:re)?newcommand|providecommand|DeclareRobustCommand'
        r'|NewDocumentCommand|def)\s*\*?\s*\{?\\([A-Za-z@]+)')
    for _l in lines:
        for _m in _DEF_PAT.finditer(re.sub(r'(?<!\\)((?:\\\\)*)%.*', r'\1', _l)):
            user_defined.add(_m.group(1))
    # v3.76: LTR-ISLAND ALIAS RESOLUTION. The two allow-list island rules
    # (LIST-IN-LTR-ISLAND, CAPTION-INSIDE-LTR-ISLAND) could not see through a
    # project-local wrapper — the definition lives in macros.tex, which the
    # scanned artifact only \input's, and this checker never follows \input.
    # Blinded this way, 17 render-proven broken sites (14 zero-indent lists,
    # 3 flipped captions) shipped in data-science-exams inside its qeng
    # alias. Two resolution paths: (a) definitions in THIS file (covers an
    # assembled final.tex with macros embedded, and single-file runs);
    # (b) extra_ltr_aliases passed by main(), which shares each collection's
    # aliases across its own /src/ files — CI lints macros.tex and the parts
    # in one invocation. Hard-coding alias names was rejected: a name
    # collision in another collection would arm rules there (scoping in
    # main() prevents exactly that).
    # v3.82 (audit finding A): the SAME two paths now resolve LIST-wrapper
    # aliases (\newenvironment over list/itemize/enumerate/description). Both
    # ends of LIST-IN-LTR-ISLAND are aliasable, and resolving only one of them
    # is what let 54 `choices`-inside-`qeng` sites ship behind a green checker.
    _defsrc = '\n'.join(re.sub(r'(?<!\\)((?:\\\\)*)%.*', r'\1', _l)
                        for _l in lines)
    # Exact source positions of the supported text-mode reference form.
    # _defsrc has comments removed without changing surviving line positions.
    # Refuse macro-bearing/nested keys and wrapper content beyond whitespace;
    # this is a bounded authoring exception, not a general TeX interpreter.
    safe_text_eqrefs = set()
    for _tm in re.finditer(r'(?<!\\)\\text\s*\{\s*(\\eqref\s*\{[^{}\\\n]+\})\s*\}', _defsrc):
        _off = _tm.start(1)
        safe_text_eqrefs.add((_defsrc.count('\n', 0, _off) + 1,
                              _off - (_defsrc.rfind('\n', 0, _off) + 1)))
    ltr_alias = set(extra_ltr_aliases) | _collect_env_aliases(
        _defsrc, LTR_ALIAS_INNER_PAT)
    list_alias = set(extra_list_aliases) | _collect_env_aliases(
        _defsrc, LIST_ALIAS_INNER_PAT)

    def _unsafe_ltr_container(env):
        # Diagram/code wrappers remain unsuitable for captions and lists in
        # every locale. A modern englishprose block is ordinary localized
        # document content: localized captions and Babel layout=lists geometry
        # are runtime-tested. Undeclared/explicit-hebrew legacy source retains
        # its original conservative rule; diagram/code wrappers never qualify.
        if env in {'tikzpic', 'qcirc', 'asmblock'}:
            return True
        # The core's Hebrew prose environment wraps otherlanguage{hebrew}.
        # Generic project alias discovery sees the same otherlanguage primitive
        # used by English wrappers, but that does not make this owned RTL prose
        # an LTR container. Keep checking every enclosing diagram/code wrapper.
        if env == 'hebrewprose':
            return False
        if language.config.main != 'hebrew':
            return False
        if env == 'englishprose' and language.config.native_english_font:
            return False
        return env == 'otherlanguage' or env in ltr_alias
    # v3.82: the LIST-IN-LTR-ISLAND trigger, resolved ONCE per file — the four
    # list environments plus every list-wrapper alias in scope. `list` is the
    # LaTeX primitive the others are built on and was missing from the v3.76
    # literal alternation; `choices` (data-science-exams) is the live alias.
    _list_begin_re = re.compile(
        r'\\begin\{(' + '|'.join(
            ['itemize', 'enumerate', 'description', 'list']
            + sorted(re.escape(a) for a in list_alias)) + r')\}')
    mstate = {'display': False, 'env': 0, 'inline': False, 'paren': False}  # cross-line math state
    text_carry = 0        # open \text{}/\mbox{} depth carried across lines (v3.23.7)
    code_carry = 0        # v3.33: open \code/\texttt group brace depth carried
                          # across lines — its content is token text (backticks in
                          # a cross-line \code{} FP'd QUOTES; render-proven mono)
    nc_lines = []         # per-line comment-stripped code ('' for verbatim lines)
    tikz_flags = []       # v3.29: per-line "inside tikzpicture" state (paragraph pass)
    hard_breaks = []      # v3.31: True = a REAL paragraph boundary (blank source
                          # line / verbatim). A comment-only line strips to '' but
                          # TeX does NOT end the paragraph there — treating it as a
                          # boundary hid cross-line adjacency bugs (proven by render).
    env_stack = []   # v3.59: enclosing environment names, for the listing rule
    for n, line in enumerate(lines, 1):
        # Direction is position-sensitive: an inline English island cannot
        # exempt Hebrew elsewhere on the same line, and nested Hebrew blocks
        # remain checked in an English document.
        def _rtl(pos):
            return not language.is_english(n, pos)

        def _hebrew_font(pos):
            return not (language.config.native_english_font
                        and language.is_english(n, pos))

        in_english_block = language.line_all_english(n)
        # v3.71: ENVIRONMENT DETECTION MUST IGNORE COMMENTS. Every structural
        # trigger below used to test the RAW line, so one editorial comment —
        #   % TODO: replace \begin{verbatim} with lstlisting
        # set in_verbatim=True and the checker skipped EVERY rule to EOF while
        # printing an affirmative "✓ clean" (measured: 4 real defects lost).
        # The same poisoning hit in_tikz (a commented \begin{tikzpicture} both
        # false-fired LATIN-IN-H-IN-TIKZ and killed the whole paragraph pass —
        # tikz_flags is a hard paragraph boundary) and env_stack (a commented
        # \begin{qeng} disarmed LISTING-OUTSIDE-LTR-ISLAND permanently).
        # envline strips comments for STRUCTURE detection only; rules that need
        # the raw % (UNESCAPED-PERCENT) keep reading `line`. Inside verbatim the
        # raw line is kept — % is literal content there.
        # Inline literal commands are content, not TeX structure or linter
        # syntax. Record the one context-specific defect before blanking them:
        # they are not direction-isolated in Hebrew prose.
        envline = (line if in_verbatim else re.sub(
            r'(?<!\\)((?:\\\\)*)%.*', r'\1',
            _blank_inline_literals(line)
        ))
        if not in_verbatim and HEB_CHAR2.search(envline):
            for start in inline_calls_by_line.get(n, []):
                if _rtl(start):
                    issues.append((n, 'VERB-IN-RTL-PROSE', line[start:start + 34]))
                    break
        # v3.59: maintain the environment stack BEFORE any rule reads it. Done
        # for every line (including verbatim delimiters) so the stack stays
        # balanced; lstlisting/verbatim themselves are not pushed.
        if not in_verbatim:
            for _em in re.finditer(r'\\(begin|end)\{([A-Za-z@*]+)\}', envline):
                _kind, _env = _em.group(1), _em.group(2)
                if _env in ('lstlisting', 'verbatim', 'Verbatim'):
                    continue
                if _kind == 'begin':
                    env_stack.append(_env)
                elif env_stack and env_stack[-1] == _env:
                    env_stack.pop()
                elif _env in env_stack:          # tolerate a crossed/unbalanced pair
                    env_stack.reverse()
                    env_stack.remove(_env)
                    env_stack.reverse()
        # verbatim/listing blocks: content is literal (never executed/typeset as
        # macros) — skip every rule, including comment-stripping (% is literal).
        if in_verbatim:
            # v3.83: name-EXACT. It was name-ANY, so a `\end{lstlisting}` sitting
            # inside a verbatim BODY (literal text, not a real closer) ended the
            # block early and the remaining body was scanned as prose.
            _vm = re.search(r'\\end\{' + re.escape(in_verbatim) + r'\}', line)
            if _vm:
                in_verbatim = False
                # v3.66: the TAIL after the closing delimiter is real code again,
                # and the stack-maintenance loop above skipped this whole line.
                # Without this, `\end{lstlisting}\end{asmblock}` on ONE line —
                # the corpus's standard asmblock idiom — leaves asmblock STUCK on
                # the stack forever. Measured: 8 phantom asmblocks piled up in
                # r04.tex, which (a) made the new LIST-IN-LTR-ISLAND rule flag a
                # list that is NOT in an island, and (b) silently DISARMED
                # LISTING-OUTSIDE-LTR-ISLAND for the rest of the file, since
                # `all(e in _RTL_CONTAINERS)` is false once a phantom asmblock
                # is present — a false-NEGATIVE generator sitting in the very
                # rule built to catch unwrapped listings.
                for _em in re.finditer(
                        r'\\(begin|end)\{([A-Za-z@*]+)\}',
                        re.sub(r'(?<!\\)((?:\\\\)*)%.*', r'\1',
                               line[_vm.end():])):
                    _kind, _env = _em.group(1), _em.group(2)
                    if _env in ('lstlisting', 'verbatim', 'Verbatim'):
                        continue
                    if _kind == 'begin':
                        env_stack.append(_env)
                    elif env_stack and env_stack[-1] == _env:
                        env_stack.pop()
                    elif _env in env_stack:
                        env_stack.reverse()
                        env_stack.remove(_env)
                        env_stack.reverse()
            nc_lines.append('')
            tikz_flags.append(in_tikz)
            hard_breaks.append(True)
            continue
        # v3.59: LISTING-OUTSIDE-LTR-ISLAND. An lstlisting with no enclosing LTR
        # island silently scrambles the WHOLE block: token order reverses, {} and
        # [] mirror, and `>=` renders `=<` — a SEMANTIC INVERSION. Measured against
        # the same listing inside asmblock, which renders perfectly. All four gates
        # AND build.sh are blind by construction: this checker blanks listing
        # content (below), and the render gate's R1/R2 look for per-word reversal
        # while here each token is individually correct and only their ORDER is
        # wrong; R4 needs parens around DIGITS. The wrapper rule is stated as
        # doctrine in assets/example_listings.tex ("THE ONE RULE") but was never
        # enforced across the corpus's 381 listing sites.
        # POLARITY MATTERS — an allow-list of {asmblock, otherlanguage} would fire
        # FALSE POSITIVES: this checker never follows \input, and data-science-exams
        # defines its `qeng` wrapper in macros.tex, so scanning final.tex cannot see
        # that qeng IS an otherlanguage. Hence a DENY-list: flag only when every
        # ancestor is a KNOWN RTL container (or there is none), and treat any
        # UNRECOGNISED ancestor as a possible wrapper. Measured 0-FP on all 381
        # sites, and it still catches lstlisting placed directly inside exbox.
        if re.search(r'\\begin\{lstlisting\}', envline):
            _listing_start = envline.find(r'\begin{lstlisting}')
            if _rtl(_listing_start) and all(e in _RTL_CONTAINERS or e == 'hebrewprose'
                                           for e in env_stack):
                issues.append((n, 'LISTING-OUTSIDE-LTR-ISLAND',
                               'enclosing: '
                               + ('>'.join(env_stack) if env_stack else '(none)')))
        # v3.66: LIST-IN-LTR-ISLAND. A list opened inside an LTR wrapper
        # (otherlanguage{english} / asmblock / tikzpic / qcirc) applies its 30pt
        # \leftmargin on the READING (right) edge, leaves the body flush at the
        # physical left with ZERO indentation, and hangs the label 13-17pt into
        # the left margin — a wide \item[label] goes fully OFF THE SHEET
        # (measured: 'Wide' at x=[-34.2,-3.6], wholly left of the sheet). The
        # off-paper
        # form is hard-failed by the render gate's INK-OFF-PAPER; the sub-lethal
        # zero-indent form passes EVERY gate, which is why this source rule
        # exists. No in-island form renders correctly (bug is in the babel list
        # geometry, not the authoring) — the fix is to close the island first.
        # POLARITY: opposite of LISTING-OUTSIDE-LTR-ISLAND, and safely so. That
        # rule needs a deny-list because an UNRECOGNISED wrapper might BE an LTR
        # island (\input-blindness -> FP). Here an unrecognised wrapper merely
        # fails to fire the rule (FN), never flags correct code — an allow-list
        # of KNOWN LTR wrappers is exact.
        # v3.82 (audit finding A) — BOTH ENDS ARE ALIASABLE. The v3.76 trigger
        # was the literal alternation (itemize|enumerate|description), which
        # structurally EXCLUDED every broken site from its own denominator, so
        # the old in-code claim "Measured 0 live hits over the corpus's 539
        # lists" is WITHDRAWN, not carried forward — it is also not
        # reproducible against this tree under any counting (301 raw / 273
        # comment-stripped list openings across all 345 tracked .tex).
        # `list` (the LaTeX primitive `choices` is built on) is now in the
        # trigger, and list-wrapper aliases are resolved exactly the way
        # island aliases are — same collector, same per-scope sharing through
        # main(). RE-DERIVED, both sweeps run after the change:
        #   CI set (335 tracked */src/ + skill assets/ .tex): 329 list
        #     openings in trigger scope = 268 itemize/enumerate/description
        #     + 1 bare \begin{list} + 60 `choices`; 60 FIRE.
        #   all 12 assembled final.tex: 315 openings = 260 + 1 + 54; 54 FIRE.
        # Every hit is one shape — \begin{choices} inside \begin{qeng}, all in
        # data-science-exams; 0 in the other 12 collections, and the bare
        # \begin{list} (inside the `choices` definition itself, no island on
        # the stack) correctly stays silent. These are REAL sites for the
        # content layer to close, not FPs: the rule's polarity (allow-list of
        # KNOWN LTR wrappers) still makes an unrecognised wrapper an FN, never
        # an FP. Ground truth for the 54: the shipped 172-page PDF renders
        # their 216 (a)-(d) labels at x=39.5/40.2/40.6 against a text block
        # starting at x=65.2 — 24.6 to 25.7pt into the left margin.
        _lm = _list_begin_re.search(envline)
        if _lm and any(_unsafe_ltr_container(e) for e in env_stack[:-1] if env_stack):
            issues.append((n, 'LIST-IN-LTR-ISLAND',
                           _lm.group(1) + ' inside: '
                           + '>'.join(env_stack[:-1])))
        _vb = re.search(r'\\begin\{' + _LIT + r'\}', envline)
        if _vb:
            # v3.76: LISTING-SAME-LINE-DROPPED — everything between
            # \begin{lstlisting}(+options) and the end of the SOURCE LINE is
            # consumed by the package ("Text dropped after begin of listing"
            # warning, exit 0) and is ABSENT from the PDF. Measured 3/3
            # shapes: bare code, code after [options], and a %-tail.
            #
            # v3.82 (audit finding H) — THE %-TAIL SHAPE WAS DOCUMENTED
            # BACKWARDS HERE. This comment used to say "'%' there is dropped
            # content, not a comment". It is a comment, and that is exactly
            # why it is dangerous. Compile-proven with this repo's own preamble
            # (4 shapes: '[opts] % tail', '[opts]%', '[opts] %', and no-options
            # ' % tail' — all four identical):
            #     \begin{lstlisting}[style=pystyle] % tail   <- source line 6
            #     ALPHA = 1                                  <- source line 7
            #     BETA  = 2
            # rc=0, the package warns on input line **7**, BETA renders and
            # **ALPHA is absent from the PDF**. The '%' is tokenised before
            # listings switches catcodes, so it is an ordinary comment that
            # eats its own NEWLINE; line 7 is then spliced onto the \begin line
            # and IT becomes the same-line tail listings drops. The casualty is
            # the author's FIRST BODY LINE, not the tail they can see.
            # The boundary is whether the tail's first non-space char is '%':
            # with real code before it ('[opts] ALPHA = 1 % tail') the warning
            # lands on line 6, ALPHA is the casualty, and line 7 survives —
            # the ordinary shape. Following the ordinary shape's advice on a
            # tail that CONTAINS a '%' converts it into the '%'-first shape, so
            # the advice printed at the summary must name the '%' itself.
            # The tail is still checked on the RAW line — necessary, since a
            # comment-stripped line shows an empty tail and the rule would go
            # silent on precisely the shape that eats a line of real code.
            #
            # An UNCLOSED '[' on the line = options spanning
            # lines -> stay silent (honest limit, options are TeX until the
            # bracket closes). lstlisting only: the drop + warning are
            # listings-package behavior; verbatim keeps its same-line text.
            if _vb.group(1) == 'lstlisting':
                _tail = line[_vb.end():]
                _ts = _tail.lstrip(' \t')
                if _ts.startswith('['):
                    _rb = _ts.find(']')
                    _ts = '' if _rb < 0 else _ts[_rb + 1:]
                if _ts.strip():
                    issues.append((n, 'LISTING-SAME-LINE-DROPPED',
                                   line.strip()[:56]))
            # v3.82 (audit finding C) — DO NOT LATCH ON A ONE-LINE BLOCK.
            # The closing-delimiter scan lives behind `if in_verbatim:` above,
            # so it first runs on the NEXT line: a legal one-liner
            # (\begin{verbatim}text\end{verbatim} — compile-proven rc=0, the
            # text present in the PDF) set the flag forever and every rule
            # from there to EOF was skipped behind an affirmative "clean".
            # Proof-of-failure before this branch existed: a file whose lines
            # 3-5 carry render-proven QUOTES + UNESCAPED-PERCENT +
            # CODE-IN-HEADING reported "0 issues, exit 0"; the byte-identical
            # file with the verbatim spread over two lines reported all 3.
            # ci.yml runs this checker with no `|| true`, so rc=0 IS the pass
            # signal — a hard gate lying about a file. Same class as BLD-41.
            # The end marker is searched on the RAW line, not on `envline`:
            # inside a verbatim body '%' is literal content, so
            # \begin{verbatim}100% off\end{verbatim} must still be seen as
            # closed. v3.82's note here credited check_charset.py with having
            # had this discipline since v3.76 — it did NOT; it carried the
            # identical latch until v3.83 (see that file). Nothing was ported;
            # the shape was fixed independently in two places.
            # The line is BLANKED either way (nc_lines '') exactly like the
            # v3.66 closing-tail handler: content after \end{...} is real TeX
            # again for the ENV STACK (already maintained above, this line was
            # never in verbatim), but it is not re-scanned for prose rules —
            # HONEST LIMIT, and the FP-safe direction.
            # re.escape: `verbatim*` carries a regex quantifier in its own name.
            if re.search(r'\\end\{' + re.escape(_vb.group(1)) + r'\}',
                         line[_vb.end():]) is None:
                in_verbatim = _vb.group(1)
                _vb_open_ln = n
            nc_lines.append('')
            tikz_flags.append(in_tikz)
            hard_breaks.append(True)
            continue
        # strip inline comment — backslash-PARITY aware: an even run of
        # backslashes before % (e.g. table line-break \\%) still starts a comment.
        code = envline
        nc_lines.append(code)
        hard_breaks.append(not line.strip())

        # v3.48: UNESCAPED-PERCENT — a comment '%' glued to content eats the rest
        # of the line SILENTLY (no compile warning; content vanishes from the PDF).
        # Uses the RAW line (the '%' is the thing under test). Not in verbatim here.
        _op = _orphan_percent(line)
        if _op is not None:
            issues.append((n, 'UNESCAPED-PERCENT', _op))

        # v3.76: TOC-OVERRIDE-IN-DOCUMENT — a document-layer file re-defining
        # \l@chapter/\l@section/\l@subsection shadows the preamble's measured
        # TOC geometry (BLD-38's 3.2em rolled back to 3.0em by a hand-patch
        # that predated v3.70, scaffold-copied into 10 main.tex files, and
        # silently won over every later preamble fix — last definition wins).
        # The preamble owns TOC geometry; a copied asset cannot see main.tex,
        # so this is the only gate on the pattern returning.
        if has_document and TOC_OVERRIDE_PAT.search(code):
            issues.append((n, 'TOC-OVERRIDE-IN-DOCUMENT', code.strip()[:56]))

        # math mask for this line (advances cross-line block state)
        mask, mstate = math_mask(code, mstate)
        # v3.23.7: cross-line \text{} state — a blank line self-heals unbalanced
        # braces (TeX itself errors on a blank line inside \text), like math_mask.
        if not code.strip():
            text_carry = 0
            code_carry = 0
        intext, text_carry = _line_text_spans(code, text_carry)

        # pgfplots axis balance — walk tokens IN ORDER (an \end before a
        # \begin on the same line is a stray end + a new unclosed begin)
        for am in re.finditer(r'\\(begin|end)\{axis\}', code):
            if am.group(1) == 'begin':
                axis_stack.append(n)
            elif axis_stack:
                axis_stack.pop()
            else:
                issues.append((n, 'AXIS-EXTRA-END',
                               r'\end{axis} with no matching \begin{axis}'))
        # math in a heading without \texorpdfstring — scan the heading's OWN brace
        # group, not the whole line (v3.49: the whole-line check FP'd a run-in
        # \paragraph{X} whose body carries $x$; mirrors CODE-IN-HEADING's v3.31 fix).
        _mhm = re.search(r'\\(?:chapter|section|subsection|subsubsection'
                         r'|paragraph|part)\s*\{', code)
        if _mhm:
            _mhtxt = code[_mhm.end() - 1:_match_brace(code, _mhm.end() - 1)]
            if _heading_has_bare_math(_mhtxt):
                issues.append((n, 'MATH-IN-HEADING', line.strip()[:90]))
        # Block commands and fragile footnotes are invalid in a moving heading.
        # Plain \code is safe: preamble.tex supplies robust PDF-string handling.
        _hm = re.search(r'\\(?:chapter|section|subsection|subsubsection'
                        r'|paragraph|part)\s*\{', code)
        if _hm:
            _htxt = code[_hm.end() - 1:_match_brace(code, _hm.end() - 1)]
            for _defect in sorted(_heading_fragile_defects(_htxt)):
                issues.append((n, _defect, line.strip()[:90]))
        # v3.68: quantikz added — the LATIN-IN-H-IN-TIKZ rule (and everything else
        # keyed on in_tikz) never fired inside a quantikz matrix because only
        # \begin{tikzpicture} set the flag. Measured: the identical \h{Latin} node
        # fires 2 hits in a tikzpicture control and 0 inside quantikz, while the
        # render gate hard-fails BOTH — the cheap pre-build detector was blind on
        # the headline circuit environment. quantikz IS a tikzpicture (it wraps a
        # tikz matrix), so every in_tikz-keyed rule applies unchanged.
        if r'\begin{tikzpicture}' in envline or r'\begin{quantikz}' in envline:
            in_tikz = True
        tikz_flags.append(in_tikz)     # v3.29: per-line tikz state (paragraph pass)
        # Native English is now a document profile as well as a local block.
        # Rules use exact source positions below; this broad flag is retained
        # only for legacy checks whose public contract is language-neutral.
        english_ctx = in_english_block
        # v3.30: QUOTES fires in ENGLISH context too — the english_ctx guard
        # was a proven blind spot: ``...'' needs the tlig ligatures that Frank
        # Ruhl does not have, so it renders LITERAL backticks in English text
        # exactly as next to Hebrew (shipped broken in the skill's own
        # example_math citation, caught by a reader). Fix by context: Hebrew ->
        # gershayim ״; English -> typed curly quotes “ ” (render-verified).
        # v3.31 (adversarial audit): \code/\texttt spans are masked FIRST —
        # `\code{s = ''}` (empty string) and `\code{``x``}` (markdown syntax)
        # are token content that renders exactly as intended (proven); math is
        # masked too ($f''$ double-prime renders as primes — the documented FP,
        # now closed); and a SINGLE backtick is flagged as well: tlig never
        # runs, so `word' ships a literal U+0060 grave accent (proven).
        # v3.32: the mask walks groups with _match_brace — the one-level regex
        # died on 2-level braces (`\code{m = {{0}} `x`}` FP'd; proven correct
        # render).
        _qnc = list(code)
        _pos = 0
        if code_carry:                       # continuation of a cross-line group
            _d = code_carry
            for _qi, _ch in enumerate(code):
                _k = _qi - 1
                while _k >= 0 and code[_k] == '\\':
                    _k -= 1
                _esc = (_qi - 1 - _k) % 2 == 1
                if _ch == '{' and not _esc:
                    _d += 1
                elif _ch == '}' and not _esc:
                    _d -= 1
                _qnc[_qi] = ' '
                if _d == 0:
                    _pos = _qi + 1
                    break
            else:
                _pos = len(code)
            code_carry = _d if _d > 0 else 0
        for _qg in re.finditer(r'\\(?:code|texttt|url|path|href)\{', code):
            if _qg.start() < _pos:
                continue
            _qend = _match_brace(code, _qg.end() - 1)
            for _qi in range(_qg.start(), _qend):
                _qnc[_qi] = ' '
            if _qend >= len(code):
                # group did not close on this line: carry its open depth
                _d = 0
                for _qi in range(_qg.end() - 1, len(code)):
                    if code[_qi] in '{}':
                        _k = _qi - 1
                        while _k >= 0 and code[_k] == '\\':
                            _k -= 1
                        if (_qi - 1 - _k) % 2 == 1:
                            continue
                        _d += 1 if code[_qi] == '{' else -1
                if _d > 0:
                    code_carry = _d
        _qnc = ''.join(_qnc)
        for _qm in re.finditer(r"`|''", _qnc):
            if not mask[_qm.start()] and _hebrew_font(_qm.start()):
                issues.append((n, 'QUOTES', line.strip()[:90]))
                break
        # v3.33: PRIME-AFTER-MATH — an apostrophe typed immediately AFTER the
        # closing $ / \) ships a literal U+0027 apostrophe glyph, not the
        # U+2032 prime of $f'$ (glyph-dump proven; compiles clean, invisible
        # at every gate). English possessive $X$'s is fine — a Latin letter
        # after the run exempts it (0 FP over the whole corpus, measured).
        for _pm in re.finditer(r"(?:(?<=\$)|(?<=\\\)))'+(?![A-Za-z])", code):
            if _pm.start() > 0 and mask[_pm.start() - 1] and not mask[_pm.start()]:
                issues.append((n, 'PRIME-AFTER-MATH',
                               code[max(0, _pm.start() - 14):_pm.end() + 8].strip()))
                break
        # v3.34: MANUAL-FIG-CAPTION — a hand-written gray figure caption
        # {\centering\small\textcolor{cGray}{איור ...}} has no \refstepcounter,
        # so a \label inside it binds to the AMBIENT counter (the last equation
        # / section) and \ref prints the WRONG number (measured on a shipped
        # page: "איור 48" where 48 is equation 48). Use \figcap{...} — the
        # \tabcap twin — which steps a real \c@fig counter first. The preamble's
        # own \figcap definition writes \textcolor{cGray}{\textbf{איור~\thefig}}
        # (a \textbf group before איור), so the macro is NOT matched; only the
        # manual idiom (איור directly after the brace) fires.
        if re.search(r'\\textcolor\{cGray\}\{\s*איור', code):
            issues.append((n, 'MANUAL-FIG-CAPTION', line.strip()[:90]))
        # v4.8.0: distinguish an OUTSIDE text atom adjacent to math from a
        # texttt atom already INSIDE math. The old regex treated both '$' edges
        # identically and blocked the public API it documented as math-safe.
        if not english_ctx:
            for match in TTMATH_PAT.finditer(code):
                macro_pos = match.start() + (1 if match.group().startswith('$') else 0)
                if not mask[macro_pos] and _rtl(macro_pos):
                    issues.append((n, 'TEXTTT-NEXT-TO-MATH', line.strip()[:90]))
                    break
        if any(_rtl(m.start()) for m in BAREMATH_PAT.finditer(code)):
            issues.append((n, 'BARE-IDENT-NEXT-TO-MATH', line.strip()[:90]))
        if not english_ctx:
            for m in TTPAIR_PAT.finditer(code):
                if _rtl(m.start()) and ('\\$' in m.group(1) or '\\$' in m.group(2)):
                    issues.append((n, 'DOLLAR-CODE-SPLIT', line.strip()[:90]))
                    break
        # v3.36 guards (see LATPAREN_PAT comment): Hebrew must be present on
        # the line (no RTL base -> nothing mirrors; exempts english blocks),
        # TikZ lines are LTR islands ("at (axis cs:..." is not prose), math
        # positions are masked, code islands are masked (the QUOTES-block _qnc
        # already blanks \code/\texttt/\url spans — \code{f(x)} is
        # direction-safe by the \texttt redefinition and must not fire), and
        # \texorpdfstring's args are bookmark/math payloads, not typeset prose.
        # v4.14: the old guard was `not english_ctx`, which is TRUE for a line
        # that merely CONTAINS an \en{} island — so a broken bare-Latin bracket
        # ELSEWHERE on such a line was never scanned. Measured: two live
        # "ה־Data (32 ביט)" rows in computer-architecture part07 sat in that
        # shadow. A BLOCK of English still exempts the whole line (no RTL base,
        # nothing can mirror); an INLINE island now blanks only itself, which is
        # both necessary (to see the rest of the line) and sufficient (the
        # sanctioned fixes \en{Skill(/audit)} and \en{MIPS} (32 ביט) lose their
        # anchor with the island and stay silent — render-verified, F5/F8/F10).
        _en_block = in_english_block
        if (not _en_block and ' & ' not in line
                and not line.lstrip().startswith('%') and not in_tikz
                and re.search(r'[א-ת]', code)):
            _txp_spans = []
            for _tm in re.finditer(r'\\texorpdfstring\s*\{', code):
                _e1 = _match_brace(code, _tm.end() - 1)
                _e2 = _e1
                if _e1 < len(code) and code.startswith('{', _e1):
                    _e2 = _match_brace(code, _e1)
                _txp_spans.append((_tm.start(), _e2))
            _lpsrc = list(_qnc)
            # v4.14.1: track WHICH positions were blanked. A blanked span is an
            # island -- a real run boundary -- so the backward anchor scan must
            # stop there rather than read a Latin letter out of it.
            _lpblank = [a != b for a, b in zip(code, _qnc)]
            # v4.16: mask only balanced explicit English islands, including
            # whitespace and multiline argument forms, never the whole line.
            # v5.3.5 (BIDI-84): the language model gives an island's OPENER --
            # `\en{`, `\foreignlanguage{english}{` -- the surrounding language,
            # because the switch takes effect at the body. Masking only the
            # English positions left the command's own letters ("en") inside a
            # parenthesis, read as a strong Latin character: four fleet lines,
            # all correct on the page, failed as LATIN-BEFORE-PAREN. Mask the
            # opener with the body; a nested \h{} stays Hebrew, as v5.1.1 meant.
            for _ea, _eb in english_inline_ranges.get(n, []):
                _stop = min(_eb, len(_lpsrc))
                _body = next((_ei for _ei in range(_ea, _stop)
                              if language.is_english(n, _ei)), _stop)
                for _ei in range(_ea, _stop):
                    if _ei < _body or language.is_english(n, _ei):
                        _lpsrc[_ei] = ' '
                        _lpblank[_ei] = True
            _lpsrc = ''.join(_lpsrc)
            for _lm in LATPAREN_PAT.finditer(_lpsrc):
                _p = _lm.start()
                if not _rtl(_p) or (_p < len(mask) and mask[_p]):
                    continue
                if any(_a <= _p < _b for _a, _b in _txp_spans):
                    continue
                # v4.14 post-filter — see LATPAREN_PAT. With nothing strong
                # inside (Skill()) or a strong R first (bit (״Modified״),
                # MIPS (עשרות סיביות)) the two brackets resolve alike and the
                # row renders CORRECTLY — measured on the page.
                _inner = _lm.group(1) if _lm.group(1) is not None else _lm.group(2)
                _strong = LATPAREN_FIRST_STRONG.search(_inner)
                if _strong is None or LATPAREN_HEB_FIRST.match(_strong.group()):
                    continue
                if not _latparen_anchored(_lpsrc, _p, _lpblank, mask):
                    continue
                issues.append((n, 'LATIN-BEFORE-PAREN', line.strip()[:90]))
                break
            # v4.15.0 TOKEN-PUNCT-ADRIFT — the same guard block, because the
            # preconditions are identical: an RTL base on the line, no TikZ, no
            # English block, and islands already blanked in _lpsrc (an island is
            # the fix, so a token inside one must stay silent).
            _adrift = False
            for _tm in TOKEN_PUNCT_LEAD_PAT.finditer(_lpsrc):
                _tp = _tm.start(1)
                if not _rtl(_tp) or (_tp < len(mask) and mask[_tp]) or _lpblank[_tp]:
                    continue
                if any(_a <= _tp < _b for _a, _b in _txp_spans):
                    continue
                if _token_punct_adrift(_lpsrc, _tp, _lpblank, mask):
                    issues.append((n, 'TOKEN-PUNCT-ADRIFT',
                                   _lpsrc[max(0, _tp - 12):_tp + 18].strip()))
                    _adrift = True
                    break
            if not _adrift:
                for _tm in TOKEN_PUNCT_TAIL_PAT.finditer(_lpsrc):
                    _tp = _tm.start(1)
                    if not _rtl(_tp) or (_tp < len(mask) and mask[_tp]) or _lpblank[_tp]:
                        continue
                    if any(_a <= _tp < _b for _a, _b in _txp_spans):
                        continue
                    if _token_slash_adrift(_lpsrc, _tp, _lpblank, mask):
                        issues.append((n, 'TOKEN-PUNCT-ADRIFT',
                                       _lpsrc[max(0, _tp - 18):_tp + 12].strip()))
                        break
        # B2 (v3.21/.22): -- / --- renders as LITERAL hyphens under Frank Ruhl —
        #   next to Hebrew AND in the classic Latin/digit range idiom (1990--2000,
        #   Hong--Ou--Mandel): tlig never fires in this pipeline (verified).
        #   Skips: math (there - is a minus) EXCEPT inside \text{}/\mbox{} whose
        #   interior is text mode; \code/\texttt/\url/\path/\href spans (literal).
        code_nc = re.sub(r'\\(?:code|texttt|url|path|href)\{(?:[^{}]|\{[^{}]*\})*\}',
                         lambda mm: ' ' * len(mm.group()), code)
        _tspans = []
        for _tm in re.finditer(r'\\(?:text|mbox)\{', code_nc):
            _b = _tm.end() - 1
            _tspans.append((_b + 1, _match_brace(code_nc, _b) - 1))
        def _textmode(pos):
            return (not mask[pos]) or any(a <= pos < b for a, b in _tspans)
        _dash_done = False
        for m in HEB_DHYPHEN_PAT.finditer(code_nc):
            if _textmode(m.start()) and _hebrew_font(m.start()):
                issues.append((n, 'HEBREW-DOUBLE-HYPHEN',
                               code[max(0, m.start() - 6):m.start() + 12].strip()))
                _dash_done = True
        if not _dash_done:
            for m in LAT_DHYPHEN_PAT.finditer(code_nc):
                if _textmode(m.start() + 1) and _hebrew_font(m.start() + 1):
                    issues.append((n, 'HEBREW-DOUBLE-HYPHEN',
                                   code[max(0, m.start() - 6):m.start() + 14].strip()))
                    break
        # v3.25: the ref-range idiom \eqref{a}--\eqref{b} — at source level the
        # run sits between } and \, invisible to both adjacency patterns above.
        for m in REF_DHYPHEN_PAT.finditer(code_nc):
            if _textmode(m.end() - 1) and _hebrew_font(m.end() - 1):
                issues.append((n, 'HEBREW-DOUBLE-HYPHEN',
                               code[max(0, m.start()):m.end() + 10].strip()))
                _dash_done = True
                break
        # v3.60: ISLAND-PAIR-REVERSED — two adjacent LTR islands separated by a
        # SPACE, by NOTHING, or by a PERIOD also reverse. ADJACENT-LTR-ISLANDS
        # (BIDI-2) only ever matched a comma/slash/dash separator, and the skill's
        # own reference asserted the rest were safe — figures-boxes-listings.md said
        # a period "does NOT reverse" and that "only comma/slash are the triggers —
        # all empirically verified". Measured on the page, that is FALSE:
        #   \en{CSV} \en{(Comma-Separated Values)} -> "(Comma-Separated Values)CSV"
        #   \en{Alpha}.\en{Beta}                   -> "Beta.Alpha"
        #   \code{1010}\code{101}                  -> "1011010"
        # and the inter-island SPACE is swallowed at the seam. That false assurance
        # is why 49 instances shipped across 25 files — acronym+expansion pairs like
        # \en{RAM} \en{(Random Access Memory)} render expansion-first in production
        # PDFs. Fix: merge into ONE island, \en{RAM (Random Access Memory)}.
        # GATE: both islands must carry a Latin LETTER OUTSIDE math. That is what
        # keeps the ~20 live derivation-arrow pairs (\en{$x$} \en{$\Leftarrow$})
        # exempt — those are separate items in the Hebrew flow and read correctly,
        # and their islands hold only math. \mbox{} is NOT a fix here (measured:
        # the reversal is unchanged) — it is a line-break remedy only.
        if not in_english_block:
            for m in ISLAND_PAIR_PAT.finditer(code):
                if mask[m.start()]:
                    continue
                if (_rtl(m.start()) and _latin_outside_math(m.group(1))
                        and _latin_outside_math(m.group(3))):
                    issues.append((n, 'ISLAND-PAIR-REVERSED', m.group()[:56]))
                    break
        # v3.59: VERB-IN-RTL-PROSE — \verb / \lstinline are NOT direction-isolated.
        # The preamble's LTR fix (lines ~232-234) redefines \texttt and defines
        # \code; \verb uses \ttfamily directly and \lstinline has its own hook, so
        # NEITHER is wrapped in \foreignlanguage{english}. Measured in Hebrew prose:
        #   \verb|arr[i]|          -> "[arr[i"   (closing ] MIRRORED and moved)
        #   \verb|lw $t0, 0($s0)|  -> "(lw $t0, 0($s0"
        #   \verb|\punit|          -> "punit\"   (backslash on the wrong side)
        #   \lstinline|x = a[i];|  -> ";[i]a=x"  (whole run reversed)
        # while the \code{} equivalents render correctly in the same compile. All
        # four gates are blind (compiles clean, 0 missing chars, render gate PASS).
        # This is NOT BLD-11: that is catcode damage INSIDE \code; this is the
        # direction of a different, uncovered macro. \verb also cannot be rescued by
        # wrapping — \en{\verb|..|} dies with a misleading "! Missing } inserted"
        # pointing past a balanced brace (the real cause: \verb is illegal in a
        # command argument). Fix: use \code{} with escapes, or an
        # \begin{otherlanguage}{english} block.
        # Detection happens before inline-literal blanking near envline setup.
        # v3.59: ITEM-EATEN-BRACKET — an \item whose BODY starts with `[` has that
        # group SILENTLY EATEN as the item's optional label. TeX's \item is
        # \@ifnextchar[\@item{...} (latex.ltx:12908) and \@ifnextchar SKIPS
        # whitespace and newlines, so `\item [11:4] ...` and `\item` + newline +
        # `[11:4]` are indistinguishable from a deliberate `\item[label]`.
        # Measured: the brackets VANISH from the PDF, the bullet/number is
        # DESTROYED, and downstream items renumber — compiles clean, zero
        # warnings, all four gates green. Everyday payloads in this corpus: a bit
        # range `[15:0]`, an interval `[10,20]`, a Hebrew tag `[רמז]`.
        # 0-FP on the corpus BY MEASUREMENT: 0 spaced/newline forms against 1265
        # legitimate glued `\item[...]` labels. HONEST LIMIT: the GLUED form
        # `\item[11:4]` is formally identical to the sanctioned `\item[2.1.]`, so
        # this rule cannot cover it — say so rather than imply full coverage.
        # Fix: brace it (`\item {[11:4]}`) or make it math (`\item $[10,20]$`).
        for m in re.finditer(r'\\item(?![A-Za-z])[ \t]+\[', code):
            issues.append((n, 'ITEM-EATEN-BRACKET', code[m.start():m.start() + 30]))
        if re.search(r'\\item(?![A-Za-z])[ \t]*$', code):
            _nxt = lines[n] if n < len(lines) else ''
            if re.match(r'\s*\[', _nxt):
                issues.append((n, 'ITEM-EATEN-BRACKET',
                               r'\item then next line opens with [: '
                               + _nxt.strip()[:24]))
        # v4.7.1: NONEQREF-UNDER-SHOWONLYREFS — under the showonlyrefs policy mathtools'
        # showonlyrefs registers ONLY \eqref/\refeq, so an equation reached by
        # \ref/\autoref is never numbered: measured, \ref printed an EMPTY
        # number ("משוואה ."), \autoref printed "פרק" (the anchor collapsed
        # onto the enclosing chapter), and the v3.58 undef gate never fires —
        # the label IS defined, just empty. Bind: SKILL.md used to prescribe
        # \ref{a},\ref{b} as the range remedy, which is exactly the broken
        # form here. Only flagged when the showonlyrefs flag is set —
        # everywhere else \ref to an equation is legitimate.
        if policy_showonlyrefs:
            for _rm in re.finditer(r'\\(?:auto)?ref\{(eq:[^{}]*)\}', code):
                issues.append((n, 'NONEQREF-UNDER-SHOWONLYREFS',
                               '\\ref{' + _rm.group(1)
                               + '} — under showonlyrefs only \\eqref numbers'))
            # v3.73: REF-TO-HEADING-UNDER-EXAM-LAYER — secnumdepth=-2 means
            # \chapter steps NO counter, so a heading \label captured whatever
            # stepped last: measured, \ref to question 2 printed the preceding
            # FIGURE's number (1), or an empty string. 92 such labels are armed
            # in the fleet with 0 pulls — flag the PULL, not the arm (the armed
            # label renders fine as long as nobody references it). Remedies:
            # \nameref / \hyperref[]{} (both measured correct), or \qlabel.
            # v4.7.1: keyed on the hidden-section-numbering capability, NOT showonlyrefs — a bare
            # showonlyrefs document keeps normal heading numbers, and keying
            # both rules on one flag made ca-recitations a latent FP site.
            if policy_hide_section_numbering:
                for _rm in re.finditer(r'\\(?:auto)?ref\{(ch:[^{}]*)\}', code):
                    issues.append((n, 'REF-TO-HEADING-UNDER-EXAM-LAYER',
                                   '\\ref{' + _rm.group(1)
                                   + '} — use \\nameref/\\hyperref or \\qlabel'))
        # v3.70: BOOKMARK-DROPS-HEBREW — \texorpdfstring whose TYPESET arg contains
        # Hebrew while the PDF-STRING arg contains none. BIDI-15's sanctioned
        # pattern is FRAGMENT-level ({$math$}{plain}); applied WHOLE-HEADING with an
        # English translation it ships an English navigation pane for a Hebrew
        # document — measured live: 27 sites in one collection produced 22 English
        # bookmarks ('Error count and why five qubits' for 'מניין השגיאות...').
        # Verified 0-FP on the other 12 collections and the skill's own tests
        # (a {\code{grep}}{grep} fragment has no Hebrew in arg1 — silent).
        # Heading context ONLY: a \texorpdfstring in an mdframed frametitle
        # (keybox etc.) never reaches a bookmark, so its pdf-string arg is inert
        # — one live keybox site with Hebrew-arg1/Latin-arg2 is CORRECT output
        # and must stay silent (measured; that was this rule's one corpus FP).
        for _tm2 in re.finditer(r'\\texorpdfstring\s*(\{)', code):
            _head = code[:_tm2.start()]
            if not re.search(r'\\(chapter|section|subsection|subsubsection'
                             r'|paragraph|part|addcontentsline)\*?\s*[\[{]'
                             r'[^\n]*$', _head):
                continue
            _a1 = _brace_group(code, _tm2.end(1) - 1)
            _rest = code[_tm2.end(1) - 1 + len(_a1) + 2:].lstrip()
            if _rest.startswith('{') and HEB_LETTER.search(_a1) \
                    and not HEB_LETTER.search(_brace_group(_rest, 0)):
                issues.append((n, 'BOOKMARK-DROPS-HEBREW',
                               'Hebrew heading, non-Hebrew bookmark: '
                               + _a1[:30]))
        # v3.69: BIBITEM-LATIN-TAIL — a journal-style reference under the RTL base.
        # Two measured forms, both silent to all four gates:
        #   \bibitem{k} A. Einstein, ... 891 (1905).   -> body stays LTR (UBA W7)
        #     but the trailing ').' migrates to the line's far LEFT and the paren
        #     MIRRORS: reader sees '.( A. Einstein ... 891 (1905' — "(1905" is
        #     visually unclosed. R4 is blind (the mirrored paren sits next to a
        #     period, not a digit run); LATIN-BEFORE-PAREN requires Hebrew on the
        #     line and a pure-Latin entry has none.
        #   \bibitem{k} \en{P. Shor ... (1997)}.       -> the period OUTSIDE the
        #     island orphans to the far left. Unlike prose (BIDI-28's "Hebrew
        #     always follows" escape), a bibliography entry structurally ENDS with
        #     the island, so the escape does not exist here.
        # Correct form, render-verified: ONE \en{...} island INCLUDING the
        # terminal punctuation. 0 \bibitem in the corpus today -> 0 FP measured.
        if 'thebibliography' in env_stack:
            _bm2 = re.search(r'\\bibitem(?:\[[^\]]*\])?\{[^{}]*\}\s*(.*)', code)
            if _bm2 and _rtl(_bm2.start()):
                _entry = _bm2.group(1)
                if (re.search(r'[A-Za-z]', _entry)
                        and not HEB_LETTER.search(_entry)
                        and not re.match(r'\\en\s*\{', _entry)):
                    issues.append((n, 'BIBITEM-LATIN-TAIL',
                                   'Latin reference outside \\en{}: '
                                   + _entry[:40]))
            _bib_tail = re.search(r'\\en\s*\{(?:[^{}]|\{[^{}]*\})*\}\s*[.,;]\s*$', code)
            if _bib_tail and _rtl(_bib_tail.start()):
                issues.append((n, 'BIBITEM-LATIN-TAIL',
                               'terminal punctuation OUTSIDE the \\en{} island'))
        # v3.68: CAPTION-INSIDE-LTR-ISLAND — \figcap/\tabcap INSIDE tikzpic/qcirc
        # is typeset under the island's LTR paragraph base: the "איור N.M." label
        # migrates to the visual LEFT end of the line and the sentence-final period
        # flips side. Measured, same circuit twice:
        #   inside island : L->R '1רויא.הדיד מם עדרמד הלגעמ'  (label at LEFT edge)
        #   after \end    : L->R 'הדיד מם עדרמד הלגעמ.2רויא'  (label at RIGHT — ok)
        # \h{} inside the caption does NOT immunize it — the label and the paragraph
        # base are outside the author's argument (measured byte-identical broken
        # geometry). Primed by the universal LaTeX habit of \caption inside the
        # figure env. 0-FP by construction (a Hebrew caption never belongs inside
        # an English island); 0 live corpus sites.
        if r'\figcap' in code or r'\tabcap' in code or r'\srcfig' in code:
            # v3.72: otherlanguage/asmblock added — the tables agent measured the
            # identical scramble for \tabcap inside otherlanguage{english} (label
            # 'טבלה 1.' at the far LEFT, x=205.3, even with the \mbox), against a
            # correct control outside. 0 hits across 438 \tabcap sites vs 282
            # otherlanguage blocks — 0-FP measured.
            # v3.76: \srcfig added to the trigger — it EXPANDS to \figcap
            # (exam_components.tex; legacy clean_variant embeds it) so the literal grep never matched it; the
            # one in-island \srcfig rendered '1איור.' flipped at the left
            # edge (measured p.8). 25/26 fleet uses are outside islands —
            # 0-FP. Island set extended with the file's resolved aliases
            # (qeng et al.) — see LTR-ISLAND ALIAS RESOLUTION above.
            _isl = next((e for e in env_stack if _unsafe_ltr_container(e)), None)
            if _isl:
                issues.append((n, 'CAPTION-INSIDE-LTR-ISLAND',
                               '\\figcap/\\tabcap inside ' + _isl
                               + ' — move it AFTER \\end{' + _isl + '}'))
        # v3.68: LANG-IN-GATE-ARG — quantikz cell macros' arguments are MATH mode:
        # \gate{\h{מדידה}} is FATAL with "! LaTeX Error: Command \rmfamily invalid
        # in math mode" pointing at \end{quantikz}, lines away from the offending
        # cell (quantikz typesets its matrix at \end; in a 20-line circuit the
        # misdirection is 20 lines, and the message names a token that appears
        # nowhere in the source). The identical defect in prose math is caught by
        # LANG-RAW-IN-MATH; inside quantikz the math is invisible to that rule.
        # \code{}/\texttt{} are exempt BY OMISSION — \code's \ifmmode branch makes
        # it safe in a gate (render-verified 'CNOT' correct). Correct Hebrew form:
        # \gate{\text{\h{...}}} (render-verified 'מדידה'/'תוצאה' correct RTL).
        for _gm in re.finditer(
                r'\\(gate|meter|phase|control|targ|push)\s*(?:\[[^\]]*\])?\{\s*'
                r'\\(h|en)\s*\{', code):
            issues.append((n, 'LANG-IN-GATE-ARG',
                           '\\' + _gm.group(1) + '{\\' + _gm.group(2)
                           + '{..}} is math — use \\'
                           + _gm.group(1) + '{\\text{\\h{..}}}'))
        # v3.67: H-OPENS-WITH-LTR-GROUP — inside math, an \h{} group whose content
        # BEGINS with a nested box/math group ($..$, \(..\), \en{}, \code{},
        # \texttt{}, \mbox{}) suppresses bidi reordering for the WHOLE group: every
        # Hebrew letter renders in LOGICAL order on the page — gibberish. Measured:
        #   \text{\h{$f$ קבועה}}  -> L->R 'קבועה'  (reads "העובק")   REVERSED
        #   \text{\h{קבועה $f$}}  -> L->R 'העובק'  (reads "קבועה")   correct
        # A leading CHARACTER (paren, comma, digit, Latin letter, maqaf) is
        # harmless; Hebrew-first is harmless; dropping \h{} entirely is harmless.
        # NO gate can see this: R1/R2 fingerprint reversed LATIN runs only, R4
        # only paren-digit groups — reversed HEBREW has no detector anywhere. And
        # BIDI-31/33 doctrine actively prescribes "fold into ONE \text{\h{...}}
        # unit" without mentioning the order constraint, so the trap is primed.
        # Fix: Hebrew first, or move the island out (\text{$f$\h{ קבועה}}), or
        # drop the \h. 0-FP: 0 of the corpus's 154 \text{\h{}}/\mbox{\h{}} sites
        # open with an island (the 40 island-first \h{} sites in the fleet are
        # TikZ nodes / table cells / Hebrew-free, none inside \text{}).
        for m in re.finditer(r'\\(?:text|mbox)\s*\{\s*\\h\s*(\{)', code):
            _hbody = _brace_group(code, m.end(1) - 1)
            _lead = re.sub(r'^(?:[~ \t]|\\ )+', '', _hbody)
            if (re.match(r'\$|\\\(|\\(?:en|code|texttt|mbox)\s*\{', _lead)
                    and HEB_LETTER.search(_hbody)):
                issues.append((n, 'H-OPENS-WITH-LTR-GROUP',
                               code[m.start():m.start() + 44]))
        # v3.67: LABEL-IN-UNNUMBERED-DISPLAY — the 4th member of the BLD-13 /
        # BIDI-50 / BIDI-56 family, and the likeliest in a math-heavy document.
        # A \label inside a STARRED display or \[...\] binds to whatever
        # \refstepcounter last ran: \eqref prints "()" (align*/alignat* leave
        # \@currentlabel EMPTY) or the enclosing SECTION number (equation*/
        # gather*/\[..\]) — measured: 'הפניות: () וגם (7)' where 7 is \thesection.
        # The v3.58 undef gate is BYPASSED because the label IS defined. 0-FP by
        # construction (an unnumbered display carries no number). NB a scan for
        # \[ must anchor (?<!\\) — a first sweep "found" 13 live sites that were
        # all \\[2pt] row-spacing matches.
        _UNNUM_DISP = ('align*', 'gather*', 'equation*', 'multline*',
                       'alignat*', 'flalign*', 'eqnarray*')
        if '\\label{' in code:
            if any(e in _UNNUM_DISP for e in env_stack):
                issues.append((n, 'LABEL-IN-UNNUMBERED-DISPLAY',
                               '\\label in ' + next(e for e in env_stack
                                                    if e in _UNNUM_DISP)))
            elif in_bracket_disp and not re.search(
                    r'(?<!\\)\\\[.*\\label', code):
                issues.append((n, 'LABEL-IN-UNNUMBERED-DISPLAY',
                               '\\label in \\[..\\]'))
        for _bm in re.finditer(r'(?<!\\)\\(\[|\])', code):
            in_bracket_disp = _bm.group(1) == '['
            if (_bm.group(1) == '['
                    and re.search(r'\\label\{',
                                  code[_bm.end():
                                       (code.find('\\]', _bm.end())
                                        if '\\]' in code[_bm.end():] else len(code))])):
                issues.append((n, 'LABEL-IN-UNNUMBERED-DISPLAY',
                               '\\label in \\[..\\]'))
        # v3.67: TRAILING-CR-IN-DISPLAY — a trailing \\ before \end{align|gather|
        # multline|alignat|flalign|eqnarray} mints a PHANTOM row: unstarred, that
        # row takes a REAL equation number, so a stray "(3)" prints alone at the
        # margin and every later equation number in the document shifts by one;
        # starred, it is a cosmetic blank row. Measured: align -> phantom (3) at
        # y=142.2 with the next equation numbered (4). The exclusion is
        # LOAD-BEARING: tabular/array/matrix/cases/aligned/gathered/split are
        # measured INERT under a trailing \\ (identical glyph y-positions), and
        # the corpus carries 53 live trailing-\\ tabular rows — keying the rule
        # on the \end name keeps those silent (0 FP measured with it; 53 without).
        _tm = re.search(
            r'\\\\\s*(?:\[[^\]]*\])?\s*(?:%.*)?'
            r'\\end\{(align|gather|multline|alignat|flalign|eqnarray)(\*?)\}',
            code)
        if _tm:
            issues.append((n, 'TRAILING-CR-IN-DISPLAY',
                           'trailing \\\\ before \\end{' + _tm.group(1)
                           + _tm.group(2) + '}'))
        elif re.search(r'\\\\\s*(?:\[[^\]]*\])?\s*$', code):
            _nx = lines[n] if n < len(lines) else ''
            _nm2 = re.match(
                r'\s*\\end\{(align|gather|multline|alignat|flalign|eqnarray)(\*?)\}',
                _nx)
            if _nm2:
                issues.append((n, 'TRAILING-CR-IN-DISPLAY',
                               'trailing \\\\ before \\end{' + _nm2.group(1)
                               + _nm2.group(2) + '}'))
        # v3.66: ITEM-OPENS-WITH-BLOCK — an \item whose body OPENS with a block
        # environment strands its own label: LaTeX defers the \@labels box until
        # the next \everypar, and this skill's wrappers fire that \everypar inside
        # a paragraph that is LTR or box-internal. Measured (correct label x is
        # 522.9-534.3): asmblock -> label at x=71.2 (the PHYSICAL LEFT margin);
        # tikzpic -> x=253.3 (dragged into the centred line, mid-page); defbox ->
        # x=457.8 INSIDE the coloured box. The number prints, so nothing is
        # "missing" — it is attached to the wrong thing, in the wrong place, and
        # every gate passes. Fix: give the item one word of introducing text
        # before the environment, or \leavevmode. NB \codeline is deliberately
        # NOT flagged: v3.66's \if@inlabel\leavevmode\fi in the preamble makes
        # `\item \codeline{...}` render correctly, and a rule must never flag
        # correct output. Plain-LaTeX orphan forms (\[, center, nested list) are
        # also not flagged — standard LaTeX behaviour, label on its own line.
        # 0-FP by measurement: 0 corpus \item body opens with a block env.
        # v3.83: the denominator published here as 2021 does not re-derive
        # (independent count: 1264 raw \item bodies over 346 tracked .tex).
        # The 0 is the load-bearing half and reproduces; the population it
        # was taken over is withdrawn rather than restated at a new value,
        # because no counting rule recovering 2021 could be reconstructed.
        # Formerly: 0 of the corpus's 2021 \item bodies open with a
        # block environment (934 Hebrew, 630 \textbf, 130 $, 126 Latin, ...).
        # HONEST LIMIT: `\item \begin{asmblock}\begin{lstlisting}` ALL on one
        # line is invisible — the verbatim-open check `continue`s before this
        # rule runs. The same-line asmblock+lstlisting idiom is covered when the
        # listing starts on the next line (the corpus's universal layout).
        _BLOCK_OPENERS = ('asmblock', 'tikzpic', 'qcirc', 'exbox', 'notebox',
                          'defbox', 'thmbox', 'warnbox', 'keybox', 'tablebox')
        _im = re.match(
            r'.*\\(?:h)?item(?![A-Za-z])'
            r'(?:\s*\[(?:[^\[\]]|\[[^\[\]]*\])*\]|\{[^{}]*\}\{[^{}]*\})?'
            r'\s*(?:\\begin\{(' + '|'.join(_BLOCK_OPENERS) + r')\}|$)', code)
        if _im:
            if _im.group(1):
                issues.append((n, 'ITEM-OPENS-WITH-BLOCK',
                               r'\item body opens with ' + _im.group(1)))
            else:
                _nxt2 = lines[n] if n < len(lines) else ''
                _nm = re.match(r'\s*\\begin\{(' + '|'.join(_BLOCK_OPENERS) + r')\}',
                               _nxt2)
                if _nm and re.search(r'\\(?:h)?item(?![A-Za-z])', code):
                    issues.append((n, 'ITEM-OPENS-WITH-BLOCK',
                                   r'\item then next line opens '
                                   + _nm.group(1)))
        # v3.59: LABEL-IN-EXPLICIT-ITEM — a \label in an item with an EXPLICIT
        # \item[...] label binds to the AMBIENT \@currentlabel, so \ref prints the
        # enclosing chapter/section number where the item letter belongs. Proven in
        # the kernel: latex.ltx:12964 puts \refstepcounter INSIDE \if@noitemarg —
        #   \if@noitemarg \@noitemargfalse \if@nmbrlist \refstepcounter\@listctr \fi \fi
        # and \item[...] never sets that flag, so the list counter is never stepped
        # and \@currentlabel is never touched. Confirmed in the .aux:
        #   \newlabel{it:alef}{{1}{...}{פרק ראשון}{chapter.1}{}}   <- chapter!
        # Same family as BLD-13 (a \label binding to the ambient counter), at a site
        # MANDATED by this skill: SKILL.md tells authors to use \item[(\textbf{א})]
        # because automatic Hebrew list labels fail silently — so the trap is
        # self-inflicted and grows with every new \item[...]. Fix: \hitem{letter}{key}
        # (preamble, v3.59) which sets \@currentlabel + \@currentlabelname and calls
        # \phantomsection so the HYPERLINK lands on the item, not the chapter head.
        for m in re.finditer(r'\\item\s*\[', code):
            _tail = code[m.start():]
            if re.match(r'\\item\s*\[(?:[^\[\]]|\[[^\[\]]*\])*\][^%]*?\\label\{', _tail):
                issues.append((n, 'LABEL-IN-EXPLICIT-ITEM',
                               _tail[:52].replace('\n', ' ')))
                break
        # v3.57: RANGE-SEP-BETWEEN-DIGITS / REF-RANGE-REORDER — the two forms of
        # the SAME defect: two European-number runs joined by a neutral separator
        # lay out right-to-left under the RTL base, so the reader sees the range
        # BACKWARDS. Measured on the page, not inferred: `2020–2023` -> "2023–2020",
        # `\eqref{a}–\eqref{b}` -> "(1.2)–(1.1)". Every gate was blind: the charset
        # gate ALLOWS – — ־, the dash rules above need Hebrew/Latin/island on a
        # side (never two bare digits, and never between `}` and `\`), and the
        # render gate fingerprints mirrored parens `)N(`, not a swapped pair.
        # Aggravating: HEBREW-DOUBLE-HYPHEN's own advice says "type – directly",
        # which converts a wrong-GLYPH bug into a wrong-ORDER bug — so both
        # messages below now carry the digit/ref exception.
        # \en{...} spans are blanked first: wrapping the whole range in ONE island
        # is the documented fix and must never be flagged.
        # NOTE code_nc blanks \code/\texttt/\url/\path/\href but NOT \codeline —
        # measured FPs on real MIPS operands (`\codeline{lw \$t1, -4(\$t0)}`,
        # `\codeline{addi \$a0, \$a0, -1}`, `\codeline{Tag = 5 - 1 - 2 = 2}`), so
        # blank \codeline and the verbatim-ish spans here too.
        _rng_nc = re.sub(r'\\(?:codeline|lstinline|verb)\*?\{(?:[^{}]|\{[^{}]*\})*\}',
                         lambda mm: ' ' * len(mm.group()), code_nc)
        if not in_tikz and not in_english_block:
            for m in RANGE_SEP_PAT.finditer(_rng_nc):
                if _textmode(m.start()) and _rtl(m.start()):
                    issues.append((n, 'RANGE-SEP-BETWEEN-DIGITS',
                                   m.group().strip()))
                    break
        if not in_english_block:
            for m in REF_RANGE_PAT.finditer(_rng_nc):
                if _textmode(m.start()) and _rtl(m.start()):
                    issues.append((n, 'REF-RANGE-REORDER', m.group().strip()[:56]))
                    break
        # v3.29: the island-range idiom \en{p}--\en{n} / \code{\$f0}--\code{\$f31}
        # — the same between-} blind spot as the ref idiom (literal hyphens on
        # the page). code_nc blanks \code/\texttt spans, so scan the raw code;
        # skip math (minus) and tikz (path-op safety), and don't double-report
        # a line the dash family already flagged.
        if not _dash_done and not in_tikz:
            for m in ISLAND_DHYPHEN_PAT.finditer(code):
                if not mask[m.end() - 1] and _hebrew_font(m.end() - 1):
                    issues.append((n, 'HEBREW-DOUBLE-HYPHEN',
                                   code[max(0, m.start()):m.end() + 10].strip()))
                    _dash_done = True
                    break
        # v3.47: -- flanked by "$" (between inline-math islands "$I_D$--$V_G$") or
        # inside a \text{}/\mbox{} group ("$0.3\text{--}3$") — invisible to every
        # adjacency pattern above (neighbours are $/{/}). code_nc has \code/\texttt
        # spans blanked; skip tikz for path-op safety. The dash sits in TEXT mode
        # in both forms (between two $..$, or inside \text), so it is a real defect.
        if not _dash_done and not in_tikz:
            for m in MATH_DHYPHEN_PAT.finditer(code_nc):
                if not _hebrew_font(m.start()):
                    continue
                issues.append((n, 'HEBREW-DOUBLE-HYPHEN',
                               code[max(0, m.start()):m.end() + 8].strip()))
                _dash_done = True
                break
        if not _dash_done and not in_tikz:
            for m in BRACE_DHYPHEN_PAT.finditer(code_nc):   # \text{--}: interior is text mode
                if not _hebrew_font(m.start()):
                    continue
                issues.append((n, 'HEBREW-DOUBLE-HYPHEN',
                               code[max(0, m.start()):m.end() + 4].strip()))
                break
        # B3 (v3.21): macros from packages the preamble does not load.
        #   Skip lines that DEFINE the macro (\providecommand{\SI}... is the
        #   user supplying it themselves — not an error). Known tradeoff: a
        #   definition line that also USES another unloaded macro is skipped too.
        for m in UNDEF_MACRO_PAT.finditer(code):
            name = m.group(1)
            if name in user_defined:
                continue                      # the document defines it itself
            if name == 'enquote' and _has_csquotes:
                continue                      # csquotes actually loaded
            if name != 'enquote' and _has_siunitx:
                continue                      # siunitx actually loaded
            pre = code[max(0, m.start() - 40):m.start()]
            if re.search(r'\\(?:(?:re)?newcommand|providecommand'
                         r'|DeclareRobustCommand|NewDocumentCommand|def)'
                         r'\s*\*?\s*\{?\s*$', pre):
                continue                      # this IS the definition site
            issues.append((n, 'UNDEFINED-COMMON-MACRO', m.group()))
        # B4 (v3.23.6): \providecommand on a TeX primitive / kernel command is a
        # silent no-op — the primitive keeps rendering (\ni -> ∋, not n_i).
        for m in PROVIDE_PRIMITIVE_PAT.finditer(code):
            issues.append((n, 'PROVIDECOMMAND-PRIMITIVE', m.group().strip()))
        # v3.30: CODE-UNSAFE-CHAR — \code{}/\codeline{} are NOT verbatim: an
        # unescaped # & _ ^ $ kills the compile (catcode errors far from the
        # cause), an unescaped % comments out the rest of the line INCLUDING
        # the closing brace, and ~ VANISHES silently (an active-char space:
        # \code{cd ~/x} ships as "cd /x" with zero warnings at any gate).
        # Exactly the payloads these macros exist for (shell lines, C tokens,
        # asm comments). Scan the RAW line (comment-stripping would eat the
        # in-group %); a group that starts after a real comment is skipped.
        # Escapes are the fix and are render-verified: \# \& \_ \$ \% ,
        # ^ -> \^{} , ~ -> \textasciitilde .
        # Two measured exemptions (sweep: 12 FPs on shipped, reviewed pages):
        # BALANCED $...$ pairs inside \code are the live math-in-code idiom
        # (\code{Q$_0$} subscripts — compiles and renders correctly), so
        # paired spans are stripped (with their ^/_, legal in math) and only a
        # LEFTOVER unpaired $ is flagged; and #<digit> is a macro-definition
        # parameter (\code{#1} in the preamble's own \codeline body), not a
        # literal hash.
        # v3.31 (adversarial audit): the group is extracted with _match_brace,
        # not a one-nesting-level regex — `\code{m = {{~0, 0}}}` (a C nested
        # initializer) never MATCHED the old pattern, so its ~ vanished with
        # zero flags (proven: ships `m = 0, 0`, bitwise-NOT silently inverted).
        # And a balanced $...$ span is scanned for [&#%] BEFORE being stripped:
        # only ^ _ are math-legal — `\code{$a&b$}` crashes (proven).
        _cmt = re.search(r'(?<!\\)(?:\\\\)*(%)', line)
        _cmt_pos = _cmt.start(1) if _cmt else len(line)
        for m in re.finditer(r'\\code(?:line)?\{', line):
            if m.start() > _cmt_pos:
                break                              # the group sits inside a comment
            _gend = _match_brace(line, m.end() - 1)
            inner = line[m.end():_gend - 1].replace(r'\$', '\x00')  # escaped $ aside
            bad = set()
            for _sp in re.finditer(r'\$[^$]*\$', inner):            # balanced math spans
                bad.update(b.group() for b in
                           re.finditer(r'(?<!\\)(?:[&%~]|#(?![0-9]))', _sp.group()))
            inner = re.sub(r'\$[^$]*\$', ' ', inner)
            bad.update(b.group() for b in
                       re.finditer(r'(?<!\\)(?:[&_^~%]|\$|#(?![0-9]))', inner))
            # v3.49: a Windows DRIVE-PATH pasted into \code is an undefined-control-
            # sequence FATAL crash (\code is NOT verbatim): \code{C:\Users\data} ->
            # "! Undefined control sequence \Users", the diagnostic far from the
            # source. The drive-letter signature [A-Za-z]:\ is 0-FP BY CONSTRUCTION —
            # a working document can't already contain it (it would crash), and legit
            # control words in code (\dots, \ldots, \char, the \text... escapes —
            # measured in the corpus) never match. Broader backslash crashes (math
            # commands, C-string \n/\t) stay under BLD-11's "\code is not verbatim".
            if re.search(r'[A-Za-z]:\\', inner):
                bad.add(r'\(win-path)')
            if bad:
                issues.append((n, 'CODE-UNSAFE-CHAR',
                               f"{''.join(sorted(bad))} in {line[m.start():_gend][:60]}"))
        # v3.56: HEBREW-IN-MONO — Hebrew inside a MONOSPACE span is not "tofu"
        # (as SKILL.md and the preamble both claimed until v3.56); it is a FATAL
        # build failure with a diagnostic that names a FONT FILE and never
        # mentions Hebrew, \texttt or the source line:
        #   ! error: (file .../DejaVuSansMono.ttf) (type 2):
        #            there are no glyphs in the subset
        #   ! ==> Fatal error occurred, no output PDF file produced!
        # Cause: \texttt and \code both route to \origtexttt (preamble 232-233),
        # i.e. the tt family = DejaVu Sans Mono, which has ZERO Hebrew; and the
        # tt fallback list is `hebfb` = DejaVuSerif, which also has ZERO Hebrew
        # (measured), so nothing can rescue it. Worse, coupling: add an unrelated
        # Latin \code{} elsewhere in the document and the fatal becomes a SILENT
        # DELETION of the Hebrew word instead. 0-FP BY CONSTRUCTION — a document
        # that compiles cannot already contain this. Fix: Hebrew belongs in normal
        # text (or \h{}); put only Latin/code inside \texttt/\code.
        for m in re.finditer(r'\\(?:code(?:line)?|texttt|mathtt)\{', line):
            if m.start() > _cmt_pos:
                break
            _he = line[m.end():_match_brace(line, m.end() - 1) - 1]
            if re.search(r'[\u0590-\u05FF]', _he):
                issues.append((n, 'HEBREW-IN-MONO',
                               line[m.start():m.start() + 46]))
        # \en{}/\code{} island glued to inline math in TEXT -> reorders in RTL
        # (a trailing value/arrow lands on the wrong side). Independent of
        # english_ctx (this check is ABOUT \en/\code). Skip if it's in math, or
        # already wrapped in an outer \en{}/\mbox{} (the correct merged form).
        wdepth = _wrapper_depth(code)
        for m in ISLAND_MATH_PAT.finditer(code):
            if _rtl(m.start()) and not mask[m.start()] and wdepth[m.start()] == 0:
                issues.append((n, 'ISLAND-NEXT-TO-MATH',
                               code[m.start():m.start() + 42].strip()))
        # v3.44: the SYMMETRIC complement — a math run ending in an operator
        # butted onto an island (op$\code{}). Guard on the ISLAND position:
        # the operator sits in math (mask True) and the island in text (mask
        # False); wdepth>0 exempts the correct merged form \en{...$op$\code}.
        for m in OP_MATH_ISLAND_PAT.finditer(code):
            op_pos, isl_pos = m.start(), m.start(1)
            if _rtl(isl_pos) and mask[op_pos] and not mask[isl_pos] and wdepth[isl_pos] == 0:
                issues.append((n, 'MATH-ENDS-IN-OP-BEFORE-ISLAND',
                               code[op_pos:isl_pos + 24].strip()))
        # v3.10: two \en/\code islands separated only by a comma/slash REORDER in
        # RTL text. Skip if in math (would be a bare-in-math error, caught below)
        # or if the first island is already inside an outer \en{}/\mbox{} (the
        # correct merged form, e.g. \en{\code{a}, \code{b}}). v3.50: skip inside a
        # multi-line english BLOCK — LTR base, so "\code{lw}, \code{sw}" does not
        # reorder (render-proven). Guard on in_english_block, NOT english_ctx: the
        # latter is True on ANY line with an \en{, which this rule requires by
        # definition (it would suppress every \en-pair — the whole rule).
        if not in_english_block:
            for m in ADJ_LTR_PAT.finditer(code):
                if _rtl(m.start()) and not mask[m.start()] and wdepth[m.start()] == 0:
                    issues.append((n, 'ADJACENT-LTR-ISLANDS',
                                   code[m.start():m.start() + 48].strip()))

        # v3.41.1: BREAKABLE-VALUE-ISLAND — a VALUE-LIST island in RTL prose
        # (an \en{...} holding >=3 inline-math segments plus a space outside
        # them, e.g. \en{rd $=2$, rs $=2$, rt $=3$}) can LINE-BREAK at an
        # internal space; the continuation fragment lands on the wrong side
        # of the seam and reads value-first ("3 =" opening the next line —
        # reader report #3, e18Bb). binoppenalty=9999 does NOT apply (the
        # break is at a SPACE, a legal word breakpoint). A blanket \mbox'd
        # \en was A/B-measured and REJECTED (14 overfulls, worst 170.3pt,
        # baseline 2 tiny) — so this is a source rule + doctrine, not a
        # preamble fix. Exemptions: display context (center lines do not
        # auto-wrap) and an explicit \mbox{\en{...}} (unbreakable by intent).
        # Fix (content-style §5b "רשימה = מבנה, לא אי"): a control TABLE, a
        # display line, or \mbox{} for a genuinely short island.
        # v3.42.0 (empirical audit round, each form render-proven to tear):
        # threshold >=3 -> >=2 pairs (a 2-pair island tears the same way —
        # probe classes F2/F5 — and the doctrine already says 2+ pairs =
        # structure); \(..\) segments count like $..$ (probe class C tears
        # identically); and a MATHLESS name = value list (probe class D,
        # the worst: bare "=" is a breakable space on both sides) counts
        # by its "=" pairs ("==" code mentions exempt).
        # A tabular ROW ('&' cell boundary, like the colon rule's guard) is
        # exempt: an l/c cell never wraps, and a cell is its own bidi context
        # (v3.42.0 calibration FP: a conversion chain in a table cell).
        _line_opens_center = bool(re.search(r'\\begin\{center\}', code))
        if center_depth == 0 and not _line_opens_center \
                and not re.search(r'(?<!\\)&', code):
            for m in re.finditer(r'\\en\{', code):
                if not _rtl(m.start()) or mask[m.start()] or wdepth[m.start()] > 0:
                    continue
                _gend = _match_brace(code, m.end() - 1)
                if _gend == len(code) and (not code or code[_gend - 1] != '}'):
                    continue          # island continues on the next source
                    # line: the paragraph pass owns it (probe class B)
                inner = code[m.end():_gend - 1]
                # v4.7.7: the \mbox exemption is about UNBREAKABILITY, and it
                # used to be carried only by wdepth — which sees \mbox{\en{..}}
                # and not \en{\mbox{..}}. v4.7.7 makes the latter the required
                # order (BOXED-ISLAND-EDGE-BRACKET: a box edge mirrors a bracket),
                # so without this the two rules contradict each other — fixing one
                # fires the other. An island whose whole body is one box is just
                # as unbreakable, so it is exempt in either nesting order.
                if re.fullmatch(r'\s*\\(?:mbox|hbox)\s*\{.*\}\s*', inner,
                                re.S) and _match_brace(
                                    inner, inner.find('{')) == len(inner.rstrip()):
                    continue
                if _is_value_list_island(inner):
                    issues.append((n, 'BREAKABLE-VALUE-ISLAND',
                                   code[m.start():_gend][:60].strip()))

        center_depth += len(re.findall(r'\\begin\{center\}', code)) \
            - len(re.findall(r'\\end\{center\}', code))
        if center_depth < 0:
            center_depth = 0

        # v3.25: PAREN-ONLY-ISLAND — an \en{} whose whole content is brackets
        # (\en{(}טבלת עמודים\en{)}): the isolated lone bracket swaps sides and
        # mirrors in the RTL flow. Fix: plain (...) around Hebrew content;
        # brackets INSIDE the island when the content is Latin (\en{(TLB)}).
        # NB: no english_ctx guard — that heuristic is true on ANY line with
        # \en{, which this rule requires by definition; the Hebrew-nearby
        # requirement below is the actual context filter.
        for m in PAREN_ONLY_EN_PAT.finditer(code):
            if not _rtl(m.start()) or mask[m.start()] or wdepth[m.start()] > 0:
                continue
            # v3.51: a BALANCED bracket pair in ONE island (\en{()}, \en{[]} — empty
            # args / empty list) renders correctly (LTR, nothing mirrors); only a
            # LONE bracket (\en{(}, \en{)}) is the BIDI-17 defect. Exempt the pair.
            _brk = re.search(r'\{\s*([()\[\]]+)\s*\}', m.group())
            if _brk and _brackets_balanced(_brk.group(1)):
                continue
            if HEB_CHAR2.search(code[max(0, m.start() - 30):m.end() + 30]):
                issues.append((n, 'PAREN-ONLY-ISLAND',
                               code[max(0, m.start() - 12):m.end() + 12].strip()))
        # v4.7.7: BOXED-ISLAND-EDGE-BRACKET — \mbox{\en{...]}} prints the edge
        # bracket MIRRORED (I[23:20] -> "I[23:20["). \mbox/\hbox END the bidi run
        # at the box boundary, so a mirrorable bracket sitting FIRST or LAST in
        # the box has no strong LTR neighbour INSIDE the box on its outer side and
        # resolves to the paragraph's RTL base, where ] ( } > mirror. Measured:
        #   \mbox{\en{I[23:20]}}      -> I[23:20[   (broken)
        #   \mbox{\en{(rs = I9)}}     -> )rs=I9(    (both edges)
        #   \mbox{\en{I[23:20] ok}}   -> correct    (a strong LTR char follows)
        #   \mbox{\en{I[23:20]}} next -> broken     (what follows the BOX is
        #                                            irrelevant — the box edge is
        #                                            the run edge)
        #   \en{\mbox{I[23:20]}}      -> correct    (THE FIX: island outside box)
        # Only mirrorable characters are affected: . , : ; = + - measured
        # unchanged, so the set is exactly []{}()<>, not "neutrals".
        # Two guards, both MEASURED, not assumed:
        #   math    — $\mbox{\en{I[9:0]}}$ and the display form both render
        #             CORRECTLY (math establishes an LTR context; nothing mirrors)
        #   in_english_block — inside \begin{otherlanguage}{english} the base is
        #             LTR and the same box renders correctly
        # NO english_ctx guard and NO Hebrew-proximity guard: english_ctx is true
        # on ANY line carrying \en{, which this rule requires by definition (the
        # PAREN-ONLY-ISLAND reasoning), and the \chh choice items in the exams
        # carry NO Hebrew on their own line yet sit in an RTL list — render-proven
        # broken ("]35.027.5[").
        for _bs, _be, _inner in _boxed_island_edges(code):
            if mask[_bs]:
                continue              # math is LTR; measured correct
            if not _rtl(_bs):
                continue              # LTR base; measured correct
            issues.append((n, 'BOXED-ISLAND-EDGE-BRACKET',
                           code[_bs:_be][:60].strip()))
        # v3.26: HEBREW-BEFORE-OP-MATH — see HEB_OP_MATH_PAT above.
        for m in HEB_OP_MATH_PAT.finditer(code):
            if wdepth[m.start()] > 0:
                continue  # inside an \en island all runs are LTR and merge fine
            issues.append((n, 'HEBREW-BEFORE-OP-MATH',
                           code[max(0, m.start() - 16):m.end() + 20].strip()))
        # v3.29: the operator-initial ISLAND form (בלוק \en{= 4 bytes}) — same
        # value-first break with no math at all; same flag, same fix.
        for m in HEB_OP_ISLAND_PAT.finditer(code):
            if mask[m.start()] or wdepth[m.start()] > 0:
                continue
            issues.append((n, 'HEBREW-BEFORE-OP-MATH',
                           code[max(0, m.start() - 16):m.end() + 20].strip()))
        # v4.1.3: LTR island (not a Hebrew word) before operator-initial math —
        # see ISLAND_OP_MATH_PAT above. Same defect, same fix, own flag so a
        # fleet sweep can tell the two shapes apart.
        for m in ISLAND_OP_MATH_PAT.finditer(code):
            # An all-English block has LTR as its BASE direction, so island and
            # math are one run and nothing swaps (selftest 'eng50-ok').
            if not _rtl(m.start()):
                continue
            if mask[m.start()] or wdepth[m.start()] > 0:
                continue
            issues.append((n, 'ISLAND-BEFORE-OP-MATH',
                           code[max(0, m.start() - 16):m.end() + 20].strip()))

        # v3.27: COLON-TRAPPED-IN-ISLAND — see EN_TRAILING_COLON_PAT above.
        # Hebrew must FOLLOW on the line (that is what puts the island in RTL
        # flow); a '&' between island and Hebrew means the Hebrew is in the
        # next table cell — a separate bidi context — and stays silent.
        # Inside \text{..} the OPPOSITE recipe applies (MATH-TEXT-EN-COLON:
        # math context is LTR, the colon belongs INSIDE the island) — those
        # spans are excluded so the correct math form is never flagged.
        _text_spans = [(t.start(), t.end()) for t in
                       re.finditer(r'\\text\{(?:[^{}]|\{[^{}]*\})*\}', code)]
        # v3.29: an island inside a frametitle={...} renders in the box's TITLE
        # BAR — a separate physical line from the Hebrew body that follows in
        # the source, so no adjacency exists (measured FP: a title ending '!'
        # flagged against the first body word). \item labels are NOT excluded:
        # the label and the body share a rendered line — the original v3.27 site.
        _title_spans = [(t.start(), t.end()) for t in
                        re.finditer(r'frametitle=\{(?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*\}', code)]
        for m in EN_TRAILING_COLON_PAT.finditer(code):
            if not _rtl(m.start()) or mask[m.start()] or wdepth[m.start()] > 0:
                continue
            if any(s <= m.start() < e for s, e in _text_spans + _title_spans):
                continue
            after = code[m.end():m.end() + 40]
            heb = HEB_CHAR2.search(after)
            # v3.33: a mid-line \par between the island and the Hebrew is a
            # paragraph boundary — the Hebrew starts a NEW output line
            # (render-proven), same class as the & cell boundary.
            if (heb and '&' not in after[:heb.start()]
                    and r'\par' not in after[:heb.start()]):
                issues.append((n, 'COLON-TRAPPED-IN-ISLAND',
                               code[max(0, m.start() - 12):m.end() + 16].strip()))

        # v3.25: an arrow-ONLY \en island between Hebrew still points against
        # the reading direction — the wdepth exemption in #12(a) below is for
        # arrows with Latin operands INSIDE the island (the documented merge
        # fix, \en{\code{Rt}$\to$\code{ForwardB}}), not for a bare wrapped arrow.
        for m in ARROW_ONLY_EN_PAT.finditer(code):
            if not _rtl(m.start()) or mask[m.start()] or wdepth[m.start()] > 0:
                continue
            if (HEB_CHAR2.search(code[max(0, m.start() - 30):m.start()])
                    and HEB_CHAR2.search(code[m.end():m.end() + 30])):
                issues.append((n, 'HEBREW-FLOW-ARROW',
                               code[max(0, m.start() - 18):m.end() + 18].strip()))

        # #12 HEBREW-FLOW-ARROW / HEBREW-EQUATION-ARROW (v3.14) — a rightward
        # arrow whose operands involve Hebrew renders BACKWARD under RTL (bidi
        # does not mirror arrow glyphs). NOT flagged: pure-math/code arrows
        # (s\to\infty, f:A\to B, x\mapsto y, \code{lw}\to\code{add}); Hebrew that
        # is only a sub/superscript LABEL (\underbrace{}_{\text{..}}) is ignored.
        # (a) bare arrow alone in inline math with Hebrew prose on a side
        for m in BARE_RARROW_DOLLAR_PAT.finditer(code):
            if not _rtl(m.start()) or wdepth[m.start()] > 0:
                continue  # inside \en{...}: the wrapped arrow is the DOCUMENTED fix
            if (HEB_CHAR2.search(code[max(0, m.start() - 30):m.start()])
                    or HEB_CHAR2.search(code[m.end():m.end() + 30])):
                issues.append((n, 'HEBREW-FLOW-ARROW',
                               code[max(0, m.start() - 18):m.end() + 18].strip()))
        # (b) math arrow with a Hebrew operand, OR an implication \Rightarrow on a
        # line carrying a (non-label) Hebrew \text operand (Hebrew -> RTL equation)
        line_heb_text = any(not _is_subsup_label(code, t.start())
                            for t in HEB_TEXT_PAT.finditer(code))
        for m in RARROW_PAT.finditer(code):
            if not mask[m.start()]:
                continue
            is_impl = m.group().startswith(('\\Rightarrow', '\\Longrightarrow'))
            if _arrow_operand_hebrew(code, m.start(), m.end()) or (is_impl and line_heb_text):
                issues.append((n, 'HEBREW-EQUATION-ARROW',
                               code[max(0, m.start() - 18):m.start() + 26].strip()))

        # Public eqref alone in math remains outside the authoring contract.
        # Only the exact text-mode form measured against the engine is exempt.
        for m in EQREF_PAT.finditer(code):
            if mask[m.start()] and (n, m.start()) not in safe_text_eqrefs:
                issues.append((n, 'MATH-WRAPPED-EQREF',
                               code[max(0, m.start() - 12):m.end() + 16].strip()))
                break

        # v3.47: REDUNDANT-EQREF-PARENS — "(\eqref{..})" renders "((N))" because
        # \eqref already supplies its own parens. \ref (bare number) is exempt.
        for m in REDUNDANT_EQREF_PAREN_PAT.finditer(code):
            issues.append((n, 'REDUNDANT-EQREF-PARENS', m.group(0).strip()))
            break

        # v3.47: HEBREW-MATH-GLUED-OBJECT — a \text{Hebrew phrase ending in space
        # or maqaf} in math immediately followed by its bound object (lone atom,
        # (tuple), or sandwiched number). See _glued_math_object.
        for _gs in _glued_math_object(code):
            issues.append((n, 'HEBREW-MATH-GLUED-OBJECT',
                           code[max(0, _gs):_gs + 40].strip()))
            break

        # v3.46: BOXED-HEBREW-SEGMENTS — see BOXED_OPEN_PAT. Evidence-calibrated:
        # fires only on the four render-proven breakage shapes; the sanctioned
        # single-\text{\h{..}}-unit box and the spaced parenthesized annotation
        # stay silent (both render-proven correct).
        for bm in BOXED_OPEN_PAT.finditer(code):
            bc = _text_content(lines, n - 1, code, bm.end() - 1)
            # nested alignment envs (cases/aligned/array/pmatrix...) isolate
            # their cells — Hebrew labels in DIFFERENT cells do not reorder
            # (render-proven: the message=\begin{cases} box is correct). Blank
            # them so cell labels are not miscounted as adjacent segments.
            bc = re.sub(r'\\begin\{(\w+\*?)\}.*?\\end\{\1\}', ' ', bc, flags=re.S)
            if not HEB_CHAR2.search(bc):
                continue
            trimmed = re.sub(r'^(?:\s|\\[;,! ]|~)+|(?:\s|\\[;,! ]|~)+$', '', bc)
            if trimmed.startswith('\\text{\\h{'):
                g0 = _brace_group(trimmed, 5)
                if '\\text{' + g0 + '}' == trimmed:
                    continue                      # sanctioned: one \h unit is the box
            heb_groups = []
            for tm in re.finditer(r'\\text\{', bc):
                g = _brace_group(bc, tm.end() - 1)
                if HEB_CHAR2.search(g):
                    heb_groups.append((tm.start(), tm.end() + len(g), g))
            fired = None
            if len(heb_groups) >= 2:
                fired = '>=2 Hebrew \\text segments'
            else:
                for gs, ge, g in heb_groups:
                    inner = g[3:-1] if g.startswith('\\h{') and g.endswith('}') else g
                    if re.match(r'\s|\\ ', g) or re.search(r'(?:\s|\\ )$', g):
                        fired = 'edge space inside \\text (swallowed at seam)'
                    elif re.match(r'[:;,]', inner.strip()) or re.search(r'[:;,]$', inner.strip()):
                        fired = 'edge punctuation orphans'
                    elif re.search(r'\d(?:\s|\\[ ,;!]|~)*$', bc[:gs]):
                        fired = 'bare digit glued to Hebrew unit'
                    else:
                        # DIRECT adjacency (no spacing) to math letters/digits
                        # on either side of the \text group glues at the seam.
                        # A trailing control word (\quad, \; ...) is SPACING,
                        # not a glyph — its final letters must not count.
                        before, after = bc[:gs], bc[ge + 1:]
                        if ((re.search(r'[A-Za-z0-9)]$', before)
                             and not re.search(r'\\[A-Za-z]+$', before))
                                or re.match(r'[A-Za-z0-9(]', after)):
                            fired = 'Hebrew \\text butted onto math'
                    if fired:
                        break
            if fired:
                issues.append((n, 'BOXED-HEBREW-SEGMENTS',
                               fired + ': ' + bc[:60].replace('\n', ' ')))
                break

        # -- text-inside-math checks (v3.8) ---------------------------------
        # #6 bare \h{ / \en{ in math (NOT inside \text/\mbox) -> rmfamily error
        blanked = _blank_text_mbox(code)
        for m in re.finditer(r'\\(?:h|en)\{', blanked):
            # v3.23.7: `intext` also covers a \text{} carried OPEN from a
            # previous line — an \en on a continuation line is inside the \text.
            if mask[m.start()] and not intext[m.start()]:
                issues.append((n, 'LANG-RAW-IN-MATH',
                               code[m.start():m.start() + 32]))
        # #6b PUNCT-RAW-IN-MATH (v3.53): a raw typographic-punct char sitting in
        # math tofus — the math font (cmr) has NO glyph for it, so it is SILENTLY
        # DROPPED (empirically verified: ° … – — “ ” ‘ ’ ־ ₪ all vanish inside
        # $..$). These render FINE in TEXT (check_charset ALLOWS them), so the
        # charset gate — line-based, not math-aware — waves them through: a genuine
        # blind spot ($45°$ compiles clean, 0 errors, and prints "45"). Exempt
        # inside \text{}/\mbox{}/\tag{} (already blanked) — \text{°} switches back
        # to the text font and renders. Fix: ° -> ^\circ, … -> \dots, others ->
        # wrap in \text{…}. Set is exactly check_charset's non-ASCII ALLOWED_PUNCT.
        for mi, pch in enumerate(blanked):
            if pch in _MATH_TOFU_PUNCT and mask[mi] and not intext[mi]:
                issues.append((n, 'PUNCT-RAW-IN-MATH',
                               'U+%04X %r in math: %s' % (
                                   ord(pch), pch, code[max(0, mi - 6):mi + 6])))
                break                      # one hit per line is signal enough
        # #7/#8 inspect each \text{...} that lives in math
        for mm in re.finditer(r'\\text\{', code):
            if not mask[mm.start()]:
                continue
            # v3.23.5: content is now MULTILINE-AWARE — if the \text{} group spans a
            # source line break, _text_content joins the following lines so the
            # paren/caret/colon checks still fire (the old code truncated at EOL).
            content = _text_content(lines, n - 1, code, mm.end() - 1)
            _disp = content[:48].replace('\n', ' ')
            bare = LANG_GROUP.sub('', content)         # drop \h{..}/\en{..}
            bare = re.sub(r'\\\(.*?\\\)', '', bare)     # nested \(..\) math is fine
            bare = re.sub(r'\$[^$]*\$', '', bare)       # v3.50: nested $..$ math too —
            #   \text{אם $g(x) > 0$} has its parens INSIDE real math (they don't mirror);
            #   the old code stripped only \(..\), so g(x)'s parens were a false positive.
            # #7 Latin + parens/brackets, not isolated by \en -> parens mirror.
            # (Bare Hebrew in \text is NOT flagged — it renders fine; \h optional.)
            # #7b (v3.23.4): the mirror also happens when the Latin IS in an \en but
            # the parens sit OUTSIDE it — \text{(\en{weak})} -> ")weak(". #7 misses
            # this (stripping \en leaves an empty "()", no Latin); _parens_wrap_only_latin
            # catches parens that wrap ONLY a Latin island. Skip if #7 already fired.
            if _rtl(mm.start()) and re.search(r'[A-Za-z]', bare) and re.search(r'[()\[\]]', bare):
                issues.append((n, 'TEXT-PARENS-IN-MATH',
                               '\\text{' + _disp + '}'))
            elif _rtl(mm.start()) and _parens_wrap_only_latin(content):
                issues.append((n, 'TEXT-PARENS-IN-MATH',
                               '\\text{' + _disp + '}'))
            # #7c (v3.32, geometric proof): LEADING WHITESPACE inside \text
            # before the \en re-breaks the isolation — \text{ \en{(weak)}}
            # renders ")weak(" pixel-identical to the unwrapped form, while
            # \text{\en{(weak)}} is correct. Passed every gate before this.
            # v3.33: also escaped-space \\  and tie ~ before the \\en — both
            # render-proven mirrored ()charlie(, )delta( in the audit probes).
            elif _rtl(mm.start()) and re.match(r'(?:\s|\\ |~)+\\en\{(?:[^{}]|\{[^{}]*\})*[()\[\]]',
                          content):
                issues.append((n, 'TEXT-PARENS-IN-MATH',
                               '\\text{ \\en{...' + _disp[:32] + '}'))
            # v3.10: \text{\en{label}:} in math/align — the colon sits OUTSIDE the
            # \en (in the RTL \text), so it ORPHANS to the wrong side (":s-channel"
            # instead of "s-channel:"). Fix: put the colon INSIDE -> \en{label:}.
            # v3.51: a colon FLANKED by \en on BOTH sides (\en{signal}:\en{noise} —
            # a ratio) is NOT orphaned — a neutral between two L-runs resolves L
            # (deterministic, render-proven "signal:noise"); the negative lookahead
            # exempts it while a colon before Hebrew/EOL still fires.
            if _rtl(mm.start()) and re.search(r'\\en\{(?:[^{}]|\{[^{}]*\})*\}:(?!\s*\\en\{)', content):
                issues.append((n, 'MATH-TEXT-EN-COLON',
                               '\\text{' + _disp + '}'))
            # B1 (v3.21): a bare ^ or _ inside \text{} — text mode is not math,
            #   so it throws "! Missing $ inserted". Escaped \^ \_ are literal
            #   (fine); a nested $...$ inside \text is math (fine) — both stripped.
            _c = content.replace('\\$', '  ')            # escaped \$ is NOT a delimiter
            _c = re.sub(r'\$[^$]*\$', '', _c)             # nested $...$ math is fine
            content_nomath = re.sub(r'\\\(.*?\\\)', '', _c)   # nested \(...\) math too
            if re.search(r'(?<!\\)[\^_]', content_nomath):
                issues.append((n, 'TEXT-MATH-CARET',
                               '\\text{' + _disp + '}'))
            # BIDI-16 (v3.23.6): RAW Hebrew inside \text{} flanked on BOTH sides
            # by LTR islands (\en/\code/\texttt) — the two islands bite the RTL
            # run from both ends and the Hebrew renders REVERSED with displaced
            # parens: \text{\en{(}תעלה רחבה\en{)}} -> "הבחר הלעת". Compiles
            # clean; was caught only on the rendered page (PROCESS §8.6). Fix:
            # the whole label as ONE unit — \text{\h{(תעלה רחבה)}}. Hebrew
            # around a SINGLE island (\text{(הספק ב־\en{CMOS})}) renders fine
            # and stays silent; \h-wrapped Hebrew is an explicit RTL island and
            # is stripped before the test.
            # v3.23.7: nested $...$/\(..\) inside the \text is its OWN math
            # context — an island in there does not flank the outer Hebrew
            # (compiled: rendering identical with/without it). Strip it first,
            # exactly as _parens_wrap_only_latin does. And probe Hebrew LETTERS
            # only — a lone maqaf between islands does not reorder (compiled).
            s16 = re.sub(r'\$[^$]*\$', ' ', content)
            s16 = re.sub(r'\\\(.*?\\\)', ' ', s16, flags=re.S)
            s16 = re.sub(r'\\h\{(?:[^{}]|\{[^{}]*\})*\}', ' ', s16)
            isl16 = [i16.span() for i16 in LATIN_ISLAND.finditer(s16)]
            if len(isl16) >= 2:
                for h16 in HEB_LETTER.finditer(s16):
                    p16 = h16.start()
                    if (any(e <= p16 for _b, e in isl16)
                            and any(b > p16 for b, _e in isl16)):
                        issues.append((n, 'TEXT-HEBREW-BETWEEN-ISLANDS',
                                       '\\text{' + _disp + '}'))
                        break

        # Latin-in-\h — only inside tikz
        if in_tikz:
            for m in H_PAT.finditer(code):
                if latin_outside_isolation(m.group(1)):
                    issues.append((n, 'LATIN-IN-H-IN-TIKZ',
                                   '\\h{' + m.group(1)[:60] + '}'))

        # HEBREW-IN-EN-ISLAND — the exact mirror of the rule above, and the one
        # direction that had no gate. \en is \foreignlanguage{english}{...}, so
        # its whole body takes LTR as the BASE direction: Hebrew inside it is a
        # right-to-left run nested in a left-to-right paragraph, and the
        # surrounding punctuation resolves against the wrong base. Measured on a
        # shipped four-row table (data-science-exams ex03 q10, final.pdf p.45):
        # the (a)-(d) labels landed at the far end of every cell, "(שימוש ב-+0.01"
        # printed with an unmatched paren and the number as "0.01+-", and the
        # prefix in "מ-sex" was torn from its word. Nothing in the toolchain said
        # a word — it compiles clean, every glyph is present, and the charset and
        # render gates both pass.
        #
        # \h{...} INSIDE \en{...} is the sanctioned way back (it switches the
        # language again, and the fleet uses it deliberately — e.g. an English
        # call-chain ending in \h{עלה}), so those spans are masked out before the
        # scan. Only RAW Hebrew is flagged.
        for m in re.finditer(r'\\en\{', code):
            end = _match_brace(code, m.end() - 1)
            # Same unterminated-island convention the \en pass above uses: a
            # scan that ran to end-of-line WITHOUT landing on a brace means the
            # island continues on the next source line, and the paragraph pass
            # owns it.
            if end == len(code) and (not code or code[end - 1] != '}'):
                continue
            body = code[m.end():end - 1]
            masked = H_PAT.sub(lambda mm: ' ' * len(mm.group(0)), body)
            if HEB_LETTER.search(masked):
                issues.append((n, 'HEBREW-IN-EN-ISLAND',
                               '\\en{' + body[:60] + '}'))
        if r'\end{tikzpicture}' in envline or r'\end{quantikz}' in envline:
            in_tikz = False

    # v3.83: NEVER end with an affirmative "clean" while the literal-block state
    # is still latched. This is the general cure for the whole BIDI-71 class,
    # which v3.82 closed one SHAPE of (the one-liner) rather than closing the
    # class. Two survivors were found by adversarial probe and compile-proven:
    #   * dead source arms it — `\iffalse \begin{verbatim} \fi` is never executed
    #     by TeX, but the scanner sees the \begin, latches, and goes silent to
    #     EOF. Measured on a compiling file: rc=0, "clean", while `50% off today`
    #     really did lose its tail on the rendered page.
    #   * a name-MISMATCHED closer — `\begin{verbatim}x\end{Verbatim}` — leaves
    #     the block open forever.
    # Parsing \iffalse/\ifx nesting properly is a TeX-complete problem and not
    # worth it; what matters is that silence is never reported as health. An
    # unterminated block is either a real runaway (a genuine defect) or a
    # scanner limit — both deserve to be seen, and the message says which.
    if in_verbatim:
        issues.append((_vb_open_ln, 'UNTERMINATED-LITERAL-BLOCK',
                       '\\begin{' + in_verbatim + '} opened here is never closed '
                       'by a matching \\end{' + in_verbatim + '} — every rule was '
                       'disabled from this line to end of file. If the \\begin is '
                       'inside \\iffalse/\\begin{comment}, move it out or delete '
                       'the dead source; if the \\end names a different '
                       'environment, fix the name'))

    # v3.23.7: a definition split across source lines (\providecommand<newline>
    # {\ni}) evades the per-line B4 scan — rescan the joined comment-stripped
    # source once, reporting only matches that actually span a line break.
    joined = '\n'.join(nc_lines)
    # \figcap raises its destination by the most recently measured figure
    # height. Intervening material shifts that destination by the same amount,
    # so the caption-gap geometry can look healthy while the link lands below
    # the figure. Lexical adjacency is therefore a hard source invariant.
    for figcap_pos in _iter_figcap_calls(joined):
        prefix = joined[:figcap_pos]
        # A caption still inside an LTR figure island is diagnosed by the more
        # specific CAPTION-INSIDE-LTR-ISLAND rule. Do not pile the downstream
        # adjacency symptom onto the same authoring error.
        island_tokens = list(re.finditer(
            r'\\(?P<side>begin|end)\{(?P<env>tikzpic|qcirc)\}', prefix))
        if island_tokens:
            depth = 0
            for token in island_tokens:
                depth += 1 if token.group("side") == "begin" else -1
                depth = max(0, depth)
            if depth:
                continue
        if re.search(r'\\end\{(?:tikzpic|qcirc)\}\s*\Z', prefix):
            continue
        ln = joined.count('\n', 0, figcap_pos) + 1
        evidence = " ".join(prefix[-100:].split())[-70:]
        issues.append((ln, 'FIGCAP-NOT-ADJACENT', evidence))
    for m in PROVIDE_PRIMITIVE_PAT.finditer(joined):
        if '\n' in m.group():
            ln = joined.count('\n', 0, m.start()) + 1
            issues.append((ln, 'PROVIDECOMMAND-PRIMITIVE',
                           m.group().replace('\n', ' ').strip()))
    for ln in axis_stack:
        issues.append((ln, 'AXIS-NO-END',
                       r'\begin{axis} with no \end{axis} before \end{tikzpicture}'))
    # v3.42.0: per-line center context for the paragraph pass (a value list
    # inside a centered display legitimately spans source lines and must not
    # FP there — center lines never auto-wrap)
    center_flags, _cd = [], 0
    for _code in nc_lines:
        center_flags.append(_cd > 0 or '\\begin{center}' in _code)
        _cd += _code.count('\\begin{center}') - _code.count('\\end{center}')
        if _cd < 0:
            _cd = 0
    issues.extend(_paragraph_pass(nc_lines, tikz_flags, hard_breaks,
                                  center_flags, language))
    issues.extend(_display_prose_pass(nc_lines))
    issues.sort(key=lambda t: t[0])
    return issues


def _paragraph_pass(nc_lines, tikz_flags, hard_breaks, center_flags, language=None):
    """(v3.29) The recurring line-scanner failure class, closed at the root for
    the ADJACENCY rules: a TeX paragraph is ONE logical unit (a source newline
    is just a space), so \\en{A},<newline>\\en{B} renders exactly as broken as
    the same-line form — which the per-line scan catches and this one used to
    miss (proven by render: 26 cross-line instances shipped in 8 lakits, one of
    them meaning-inverting). Each paragraph (blank-line-delimited, comment-
    stripped, verbatim/tikz lines act as boundaries) is re-joined with spaces
    and re-scanned with the same patterns and guards as the per-line pass;
    matches that sit entirely inside ONE source line are skipped (the per-line
    pass owns them), so nothing is double-reported. Paragraphs are math-closed
    (a blank line inside math is a TeX error), so a fresh math mask per
    paragraph is sound."""
    out = []
    # build paragraphs: runs of consecutive non-blank, non-tikz lines.
    # v3.31: only a REAL blank/verbatim line (hard_breaks) or tikz ends a
    # paragraph — a comment-only line strips to '' but TeX keeps the paragraph
    # open across it (proven: the reorder renders byte-identical with and
    # without an interleaved editor comment); it is skipped from the join.
    # v3.32: \par and sectioning commands are paragraph boundaries too — a
    # prose line followed by \section{...} was joined and FP'd adjacency rules
    # (proven: renders byte-identical to the blank-line form). A sectioning
    # line CLOSES the previous paragraph but STARTS a new one (multi-line
    # headings must stay scannable by pass (d)).
    _PARB = re.compile(r'\s*\\par\b\s*$')
    _SECB = re.compile(r'\s*\\(?:part|chapter|section|subsection'
                       r'|subsubsection|paragraph)\*?\s*[\[{]')
    paras, cur = [], []
    for idx, code in enumerate(nc_lines):
        if hard_breaks[idx] or tikz_flags[idx] or _PARB.match(code):
            if cur:
                paras.append(cur)
            cur = []
        elif _SECB.match(code):
            if cur:
                paras.append(cur)
            cur = [idx]
        elif code.strip():
            cur.append(idx)
    if cur:
        paras.append(cur)
    for idxs in paras:
        joined_parts, starts = [], []
        pos = 0
        for i in idxs:
            starts.append(pos)
            joined_parts.append(nc_lines[i])
            pos += len(nc_lines[i]) + 1          # +1 for the joining space
        joined = ' '.join(joined_parts)

        def line_of(p):
            lo = 0
            for k, s in enumerate(starts):
                if s <= p:
                    lo = k
            return lo

        def _rtl_at(pos):
            if language is None:
                return True
            which = line_of(pos)
            return not language.is_english(idxs[which] + 1, pos - starts[which])

        def span_lines(a, b):
            return line_of(a), line_of(max(a, b - 1))

        mask, _ = math_mask(joined, {'display': False, 'env': 0,
                                     'inline': False, 'paren': False})
        wdepth = _wrapper_depth(joined)
        text_spans = [(t.start(), t.end()) for t in
                      re.finditer(r'\\text\{(?:[^{}]|\{[^{}]*\})*\}', joined)]
        text_spans += [(t.start(), t.end()) for t in
                       re.finditer(r'frametitle=\{(?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*\}', joined)]

        # (a) ADJACENT-LTR-ISLANDS across a line break
        for m in ADJ_LTR_PAT.finditer(joined):
            la, lb = span_lines(m.start(), m.end())
            if la == lb:
                continue                          # per-line pass owns it
            if not _rtl_at(m.start()) or mask[m.start()] or wdepth[m.start()] > 0:
                continue
            out.append((idxs[la] + 1, 'ADJACENT-LTR-ISLANDS',
                        joined[m.start():m.start() + 48].strip()))
        # (a2) BOXED-ISLAND-EDGE-BRACKET across a line break — \en{out-of-bag
        # (OOB)} inside an \mbox splits the island over two source lines, so the
        # per-line pass cannot close the brace and skips it.
        for _bs, _be, _inner in _boxed_island_edges(joined):
            la, lb = span_lines(_bs, _be)
            if la == lb:
                continue                          # per-line pass owns it
            if not _rtl_at(_bs) or mask[_bs]:
                continue
            out.append((idxs[la] + 1, 'BOXED-ISLAND-EDGE-BRACKET',
                        joined[_bs:_be][:60].strip()))
        # (b) HEBREW-BEFORE-OP-MATH across a line break (both math forms + island)
        for pat in (HEB_OP_MATH_PAT, HEB_OP_ISLAND_PAT):
            for m in pat.finditer(joined):
                la, lb = span_lines(m.start(), m.end())
                if la == lb:
                    continue
                if wdepth[m.start()] > 0:
                    continue
                if pat is HEB_OP_ISLAND_PAT and mask[m.start()]:
                    continue
                out.append((idxs[la] + 1, 'HEBREW-BEFORE-OP-MATH',
                            joined[max(0, m.start() - 16):m.end() + 20].strip()))
        # (b2) v4.1.3: the island form of the same defect across a line break.
        # This is the shape the reader report actually arrived on — the island
        # ended one source line and the operator-initial math opened the next
        # ('\en{Flatten}\n$=H\cdot W\cdot C$.'), so the per-line pass could not
        # see the pair at all. A source newline is just a space to TeX: the two
        # runs land on one output line and break exactly as they do when typed
        # together, which makes this the EASIER shape to ship unnoticed.
        for m in ISLAND_OP_MATH_PAT.finditer(joined):
            la, lb = span_lines(m.start(), m.end())
            if la == lb:
                continue                    # the per-line pass owns it
            if not _rtl_at(m.start()) or mask[m.start()] or wdepth[m.start()] > 0:
                continue
            out.append((idxs[la] + 1, 'ISLAND-BEFORE-OP-MATH',
                        joined[max(0, m.start() - 16):m.end() + 20].strip()))
        # (c) COLON-TRAPPED-IN-ISLAND with the Hebrew continuation on the next
        # line. Same guards as the per-line pass, plus a row-boundary guard:
        # '&' or '\\' between the island and the Hebrew = a separate bidi
        # context (table cell / new row), stays silent.
        for m in EN_TRAILING_COLON_PAT.finditer(joined):
            if not _rtl_at(m.start()) or mask[m.start()] or wdepth[m.start()] > 0:
                continue
            if any(s <= m.start() < e for s, e in text_spans):
                continue
            after = joined[m.end():m.end() + 40]
            heb = HEB_CHAR2.search(after)
            if not heb:
                continue
            la, lb = span_lines(m.start(), m.end() + heb.start() + 1)
            if la == lb:
                continue                          # same-line: per-line pass owns it
            between = after[:heb.start()]
            if '&' in between or '\\\\' in between or r'\par' in between:
                continue
            out.append((idxs[la] + 1, 'COLON-TRAPPED-IN-ISLAND',
                        joined[max(0, m.start() - 12):m.end() + 16].strip()))
        # (e) v3.42.0: BREAKABLE-VALUE-ISLAND across a line break — an island
        # whose brace group is split over source lines is the SAME rendered
        # island (the newline is a space) and tears identically; the per-line
        # scan cannot even brace-match it (empirical probe class B).
        for m in re.finditer(r'\\en\{', joined):
            if not _rtl_at(m.start()) or mask[m.start()] or wdepth[m.start()] > 0:
                continue
            _gend = _match_brace(joined, m.end() - 1)
            la, lb = span_lines(m.start(), _gend)
            if la == lb:
                continue                          # per-line pass owns it
            if any(center_flags[idxs[k]] for k in range(la, lb + 1)):
                continue
            if any(re.search(r'(?<!\\)&', nc_lines[idxs[k]])
                   for k in range(la, lb + 1)):
                continue                          # tabular row: cell context
            if _is_value_list_island(joined[m.end():_gend - 1]):
                out.append((idxs[la] + 1, 'BREAKABLE-VALUE-ISLAND',
                            joined[m.start():_gend][:60].strip()))
        # (e2) v4.20.0: sole owner of BREAKABLE-QUOTED-ISLAND, including
        # single-line paragraphs. Wrappers and arguments can span source lines.
        # Other paragraph rules retain their per-line ownership checks.
        # Source-line wrapping must not change the classification. This pass
        # owns single and multi-line islands, avoiding duplicate findings and
        # recognizing an enclosing box opened on a preceding source line.
        quote_depth = _quote_wrapper_depth(joined)
        for m in re.finditer(_ISLAND_OPEN, joined):
            if not _active_quote_command(joined, m.start()):
                continue
            if not _rtl_at(m.start()) or mask[m.start()] or quote_depth[m.start()] > 0:
                continue
            _gend = _match_brace(joined, m.end() - 1)
            if _gend == len(joined) and joined[-1:] != '}':
                continue
            la, lb = span_lines(m.start(), _gend)
            if any(center_flags[idxs[k]] for k in range(la, lb + 1)):
                continue
            if any(re.search(r'(?<!\\)&', nc_lines[idxs[k]])
                   for k in range(la, lb + 1)):
                continue                          # existing tabular-row policy
            _inner = joined[m.end():_gend - 1]
            if _quoted_literal(_inner) is not None:
                out.append((idxs[la] + 1, 'BREAKABLE-QUOTED-ISLAND',
                            joined[m.start():_gend][:60].strip()))

        # (d) heading defects across a source-line break.
        for hm in re.finditer(r'\\(?:chapter|section|subsection|subsubsection'
                              r'|paragraph|part)\s*\{', joined):
            hend = _match_brace(joined, hm.end() - 1)
            htxt = joined[hm.end() - 1:hend]
            _defects = _heading_fragile_defects(htxt)
            if not _defects:
                continue
            la, lb = span_lines(hm.start(), hend)
            # per-line pass owns it if the defect is already visible on the
            # heading's FIRST source line alone (same detection, same window)
            first = nc_lines[idxs[la]]
            fm = re.search(r'\\(?:chapter|section|subsection|subsubsection'
                           r'|paragraph|part)\s*\{', first)
            if fm and _heading_fragile_defects(
                    first[fm.end() - 1:_match_brace(first, fm.end() - 1)]):
                continue
            for _defect in sorted(_defects):
                out.append((idxs[la] + 1, _defect,
                            joined[hm.start():hm.start() + 70].strip()))
        # (d2) v3.71: MATH-IN-HEADING across a line break — the identical wrap
        # that motivated pass (d) hides bare $..$ from the per-line scan, and
        # the bookmark damage is identical (measured: wrapped and unwrapped
        # forms produce byte-identical corrupted bookmarks 'כותרת ובה x2').
        # Same window, same first-line-ownership rule as (d).
        for hm in re.finditer(r'\\(?:chapter|section|subsection|subsubsection'
                              r'|paragraph|part)\s*\{', joined):
            hend = _match_brace(joined, hm.end() - 1)
            htxt = joined[hm.end() - 1:hend]
            if not _heading_has_bare_math(htxt):
                continue
            la, lb = span_lines(hm.start(), hend)
            first = nc_lines[idxs[la]]
            fm = re.search(r'\\(?:chapter|section|subsection|subsubsection'
                           r'|paragraph|part)\s*\{', first)
            if fm and _heading_has_bare_math(
                    first[fm.end() - 1:_match_brace(first, fm.end() - 1)]):
                continue
            out.append((idxs[la] + 1, 'MATH-IN-HEADING',
                        joined[hm.start():hm.start() + 70].strip()))
        # (e) v3.31: CODE-UNSAFE-CHAR when the \code group spans source lines —
        # the per-line scan needs the closing brace on the same line (proven:
        # \code{some_long<newline>identifier} crashes unflagged). Comment
        # content is already stripped here, so an in-group % is invisible to
        # this pass — the per-line scan owns the % class.
        for m in re.finditer(r'\\code(?:line)?\{', joined):
            gend = _match_brace(joined, m.end() - 1)
            la, lb = span_lines(m.start(), gend - 1)
            if la == lb:
                continue                          # per-line pass owns it
            inner = joined[m.end():gend - 1].replace(r'\$', '\x00')
            bad = set()
            for sp in re.finditer(r'\$[^$]*\$', inner):
                bad.update(b.group() for b in
                           re.finditer(r'(?<!\\)(?:[&%~]|#(?![0-9]))', sp.group()))
            inner = re.sub(r'\$[^$]*\$', ' ', inner)
            bad.update(b.group() for b in
                       re.finditer(r'(?<!\\)(?:[&_^~$]|#(?![0-9]))', inner))
            if bad:
                out.append((idxs[la] + 1, 'CODE-UNSAFE-CHAR',
                            f"{''.join(sorted(bad))} in {joined[m.start():gend][:60]}"))
    return out


_DISP_OPEN_ENV = re.compile(
    r'\\begin\{(equation|align|alignat|flalign|gather|multline)(\*?)\}')
_DISP_OPEN_BRK = re.compile(r'(?<!\\)\\\[')   # BIDI-62's anchor: \\[2pt] is
_DISP_CLOSE_BRK = re.compile(r'(?<!\\)\\\]')  # a line break, not a display
_DISP_ROW_SEP = re.compile(r'\\\\(?:\[[^\]]*\])?')
# spacing / punctuation-only gap between sibling \text groups. Order-bearing
# separators (, ;) are what turns physical reversal into semantic harm.
_DISP_GAP_OK = re.compile(r'^(?:\s|~|[;,.:]|\\[;,! ]|\\q?quad\b)*$')


def _display_prose_pass(nc_lines):
    """SPLIT-HEBREW-IN-DISPLAY (v4.2.1, BIDI-75). Display math is laid out
    LTR, so a Hebrew sentence or ordered list split across SEVERAL sibling
    \\text{} blocks in one display row renders with its segments in reversed
    reading order. Render-proven twice: the minimal probe (two sentence
    halves joined by ";\\qquad") put the FIRST half at x=200 and the second
    at x=312 — an RTL reader meets them backwards — and a shipped collection
    printed an answer tuple (עולה, יורדת, לא ידוע) in the OPPOSITE physical
    order from the same list in the question's own RTL prose one page
    earlier. The doctrine fix (pitfalls: "Hebrew SENTENCE inside display"):
    ONE \\text{} block for the whole verbal statement — internally RTL, so
    it renders in reading order — or a center/prose line with inline math.

    Evidence-calibrated to the corpus (5 live sites at rule-writing time,
    3 render-broken + 2 render-reviewed chain shapes): fires ONLY when consecutive Hebrew
    \\text siblings in the same visual row are separated by
    spacing/punctuation alone AND the gap carries a comma or semicolon —
    the shape of all three broken sites and of the probe. Deliberately
    silent, each an honest limit with measured or render-reviewed grounds:
      - colon label pairs (k \\text{קטן}:\\ \\text{גמישות}↑ → …) — the
        render-reviewed arrow-chain shape (opens with a math atom, so
        display lays it left-to-right and the arrows point along the
        reading direction);
      - pure-spacing gaps (no , or ;) — the reversal is physical but no
        corpus instance shows semantic harm;
      - sibling \\boxed{} units (their gap carries braces, so it is not
        spacing-only) — within-ONE-box shapes are BOXED-HEBREW-SEGMENTS';
      - nested alignment envs (cases/aligned/array/matrix…) are blanked
        before scanning — cells isolate, the BOXED rule's render-proven
        exemption;
      - inline $…$ — the class doctrine and both proofs are display-only.
    One finding per display body: the fix (merging the segments) is a
    body-level rewrite, so siblings of the first pair add noise, not
    information."""
    out = []
    body_parts = None      # [(line_idx, fragment)] while inside a display
    env_name = None        # env to \end{}; None while inside \[ ... \]
    for idx, code in enumerate(nc_lines):
        pos = 0
        while pos <= len(code):
            if body_parts is None:
                m_env = _DISP_OPEN_ENV.search(code, pos)
                m_brk = _DISP_OPEN_BRK.search(code, pos)
                cands = [m for m in (m_env, m_brk) if m]
                if not cands:
                    break
                m = min(cands, key=lambda x: x.start())
                env_name = (m.group(1) + m.group(2)) if m is m_env else None
                body_parts = []
                pos = m.end()
            else:
                if env_name is None:
                    m = _DISP_CLOSE_BRK.search(code, pos)
                    span = (m.start(), m.end()) if m else None
                else:
                    m = re.search(
                        r'\\end\{' + re.escape(env_name) + r'\}', code[pos:])
                    span = (pos + m.start(), pos + m.end()) if m else None
                if span:
                    body_parts.append((idx, code[pos:span[0]]))
                    out.extend(_split_hebrew_display(body_parts))
                    body_parts, env_name = None, None
                    pos = span[1]
                else:
                    body_parts.append((idx, code[pos:]))
                    break
    return out


def _split_hebrew_display(body_parts):
    """Analyze one display body for SPLIT-HEBREW-IN-DISPLAY (see above)."""
    frags, starts, pos = [], [], 0
    for line_idx, frag in body_parts:
        starts.append((pos, line_idx))
        frags.append(frag)
        pos += len(frag) + 1
    body = '\n'.join(frags)

    def line_of(p):
        lo = body_parts[0][0] if body_parts else 0
        for s, li in starts:
            if s <= p:
                lo = li
        return lo

    # nested envs isolate their cells — blank them, length-preserving so
    # every offset still maps to its true source line.
    body = re.sub(r'\\begin\{(\w+\*?)\}.*?\\end\{\1\}',
                  lambda m: ' ' * len(m.group(0)), body, flags=re.S)
    row_edges = [0]
    for m in _DISP_ROW_SEP.finditer(body):
        row_edges += [m.start(), m.end()]
    row_edges.append(len(body))
    for rs, re_ in zip(row_edges[::2], row_edges[1::2]):
        groups = []
        for tm in re.finditer(r'\\text\s*\{', body[rs:re_]):
            gpos = rs + tm.end() - 1
            g = _brace_group(body, gpos)       # content WITHOUT the braces
            if g and HEB_CHAR2.search(g):
                groups.append((rs + tm.start(), gpos + len(g) + 2))
        for (a_s, a_e), (b_s, _b_e) in zip(groups, groups[1:]):
            gap = body[a_e:b_s]
            if _DISP_GAP_OK.match(gap) and re.search(r'[;,]', gap):
                return [(line_of(a_s) + 1, 'SPLIT-HEBREW-IN-DISPLAY',
                         body[a_s:b_s + 24].replace('\n', ' ')[:60])]
    return []


def _alias_scope(path):
    """v3.82 (audit finding B): a file's ALIAS SCOPE, resolved from the
    FILESYSTEM rather than from the argv string. The v3.76 rule was
    `if '/src/' not in path: continue` — a substring test on whatever the
    caller happened to type. Measured consequences on the pre-fix tree: the
    CI shape (macros.tex + parts, repo-relative paths) found 18 sites, the
    one-file-at-a-time loop that every authoring guide in the host repo
    prescribed at the time (three separate documents, checked) found 0 with
    exit 0 on 70/70 files, and running from a build_<id>/ directory found 0
    even with every file passed explicitly, because no path contained
    '/src/'. Scope = the nearest `src` ancestor directory (the collection's
    source root, so a sibling collection's identically-named wrapper can
    never arm rules here), or the file's own directory when there is none —
    which is exactly what makes the build_<id>/ shape work."""
    # v3.83: realpath, not abspath. abspath does NOT resolve symlinks, so a
    # symlinked .tex scoped to the LINK's directory, found no macros.tex there,
    # and reported a byte-identical file clean while the real path exited 1
    # (measured on data-science-exams/src/parts/ex05_2024b_q1.tex). The
    # documented authoring loop symlinks `figs`, so links are idiomatic here.
    d = os.path.dirname(os.path.realpath(path))
    parts = d.replace('\\', '/').rstrip('/').split('/')
    for i in range(len(parts) - 1, -1, -1):
        if parts[i] == 'src':
            return '/'.join(parts[:i + 1])
    return '/'.join(parts)


def _alias_sources(path):
    """v3.82 (audit finding B): the on-disk files whose alias definitions
    govern `path`, ingested whether or not the caller passed them in argv.
    SKILL.md:714 has always described sibling sharing as a property of the
    filesystem layout ("a sibling macros.tex in the same src/ shares its
    aliases with every scanned file") — before this it was a property of the
    command line. Looked up: macros.tex beside the file, one directory up
    (the parts/ -> src/ hop), and at the scope root. Missing files are simply
    skipped; nothing here can fail a scan."""
    d = os.path.dirname(os.path.realpath(path)).replace('\\', '/')  # v3.83: symlinks
    out = []
    # v3.83: preamble.tex too. 15 of the 16 alias-defining files in this repo
    # are preamble.tex, not macros.tex, so the single-file authoring loop was
    # blind to every alias defined there — finding B was one filename short of
    # being closed.
    cands = []
    for base in (d, os.path.dirname(d), _alias_scope(path)):
        cands += [base + '/macros.tex', base + '/preamble.tex']
    for c in cands:
        if c not in out and os.path.isfile(c):
            out.append(c)
    return out


def document_language_contexts(root: Path, project_root: Path | None = None):
    """Evaluate bounded literal include callsites without expanding TeX macros.

    The document profile owns fonts; each visit carries its caller's prose
    locale. Repeated files retain every distinct visit, so an English visit
    cannot exempt a Hebrew visit. Language/group scopes must balance within
    each file; a concrete dynamic operand or crossing scope is unresolved.
    Pre-document providers are inspected with the frozen document config but
    cannot replace the document's body locale with their fallback declarations.
    """
    root = root.resolve()
    boundary = (project_root or root.parent).resolve()
    contexts: dict[Path, list[LanguageContext]] = {}
    findings: dict[Path, list[tuple[int, str, str]]] = {}
    active: set[Path] = set()

    def unresolved(path, raw, offset, detail):
        line = raw.count('\n', 0, offset) + 1
        finding = (line, 'LANGUAGE-CONTEXT-UNRESOLVED', detail)
        if finding not in findings.setdefault(path, []):
            findings[path].append(finding)

    try:
        raw = root.read_text(encoding='utf-8')
        root.relative_to(boundary)
    except (OSError, UnicodeDecodeError, ValueError) as error:
        unresolved(root, '', 0, str(error))
        return contexts, findings
    config = declared_config(raw)

    def visit(dependency, entry_language, in_document):
        path = dependency.path.resolve()
        raw = path.read_text(encoding='utf-8')
        active.add(path)
        include_offsets = []

        def include(offset, command, language, body):
            include_offsets.append(offset)
            try:
                occurrence = dependency_occurrence_at(
                    path, offset, boundary, dependency.import_paths)
                if occurrence is None:
                    raise ValueError('include operand is not a supported literal path')
                child = occurrence.dependency
                if child.path.resolve() in active:
                    raise ValueError('literal include cycle has no bounded language context')
                child_context = visit(child, language, body)
            except (OSError, UnicodeDecodeError, ValueError) as error:
                unresolved(path, raw, offset, f'\\{command}: {error}')
                return None
            if child_context.boundary_errors:
                unresolved(path, raw, offset,
                           f'\\{command}: included file crosses a language/group scope boundary')
            # Provider setup may contain lexical switches in conditionals. The
            # contract's begin-document locale is owned by the root profile.
            exit_language = (child_context.exit_language if (body or child_context.has_document)
                             and not child_context.boundary_errors else language)
            return occurrence.end, exit_language, child_context.exit_in_document

        try:
            context = LanguageContext(raw, entry_language=entry_language,
                                      document_config=config,
                                      include_callback=include,
                                      in_document=in_document)
        finally:
            active.remove(path)
        contexts.setdefault(path, []).append(context)
        if context.boundary_errors and (path != root or include_offsets):
            for offset, detail in context.boundary_errors:
                unresolved(path, raw, offset, detail)
        return context

    visit(Dependency(root, 'tex', (root.parent,)), config.main, False)
    return contexts, findings


def main(argv, *, resolve_includes=True):
    """Check source files; partial teaching snippets may disable file resolution."""
    files = argv[1:]
    if not files:
        print(__doc__)
        return 2
    # v3.76: per-COLLECTION alias sharing — CI lints macros.tex and the parts
    # in one invocation, so a cheap first pass collects each scope's
    # island-alias definitions and every file is then scanned with its own
    # collection's aliases (and no other's — scoping keeps a name collision
    # in another collection from arming rules here).
    # v3.82 (audit finding B): the scope is now RESOLVED from the file's
    # absolute directory (see _alias_scope) and each scope additionally
    # ingests its macros.tex FROM DISK (see _alias_sources), so the
    # one-file-at-a-time authoring loop the repo's own docs prescribe, and a
    # run from inside build_<id>/, both see what CI sees. Single-file
    # invocations remain self-sufficient too: scan_file still collects the
    # scanned file's own definitions (build.sh on an assembled final.tex).
    # v3.82 also collects LIST-wrapper aliases (finding A) on the same pass.
    scope_ltr, scope_list, scope_caps, scope_languages, scope_documents, _seen = (
        {}, {}, {}, {}, {}, set())
    prepared_documents = {}

    def _ingest_language(p, scope):
        try:
            with open(p, encoding='utf-8') as source:
                raw = source.read()
        except (OSError, UnicodeDecodeError):
            return
        ctx = LanguageContext(raw)
        owns_document = ctx.has_document
        # A literal child may hold begin{document}; main.tex still owns its
        # profile. The first explicit CLI file is the build graph's root too.
        if (resolve_includes and not owns_document
                and (os.path.basename(p) == 'main.tex'
                     or os.path.realpath(p) == os.path.realpath(files[0]))):
            explicit_root = os.environ.get('HEBREW_LATEX_PROJECT_ROOT')
            prepared = document_language_contexts(
                Path(p), Path(explicit_root) if explicit_root else None)
            if any(context.has_document for visits in prepared[0].values()
                   for context in visits):
                owns_document = True
                prepared_documents[Path(p).resolve()] = prepared
        # Only an actual document owns the profile for sibling source parts;
        # the preamble provider's fallback must not override a document hook.
        if owns_document:
            scope_documents.setdefault(scope, set()).add(Path(p).resolve())
            if ctx.config.explicit:
                scope_languages.setdefault(scope, set()).add(ctx.config)

    def _ingest(p, scope):
        _key = (scope, os.path.abspath(p))
        if _key in _seen:
            return
        _seen.add(_key)
        try:
            with open(p, encoding='utf-8') as source:
                _txt = (source.read().replace('\r\n', '\n')
                        .replace('\r', '\n').split('\n'))
        except (OSError, UnicodeDecodeError):
            return
        _raw = '\n'.join(_txt)
        scope_caps.setdefault(scope, set()).update(
            capabilities_for_provider_name(os.path.basename(p)))
        scope_caps.setdefault(scope, set()).update(capabilities_from_text(_raw))
        _cl = '\n'.join(re.sub(r'(?<!\\)((?:\\\\)*)%.*', r'\1', _l)
                        for _l in _txt)
        scope_ltr.setdefault(scope, set()).update(
            _collect_env_aliases(_cl, LTR_ALIAS_INNER_PAT))
        scope_list.setdefault(scope, set()).update(
            _collect_env_aliases(_cl, LIST_ALIAS_INNER_PAT))

    for path in files:
        _sc = _alias_scope(path)
        _ingest(path, _sc)
        _ingest_language(path, _sc)
        _dir = os.path.dirname(os.path.realpath(path))
        for _base in {_dir, os.path.dirname(_dir), _sc}:
            _ingest_language(os.path.join(_base, 'main.tex'), _sc)
        for _mp in _alias_sources(path):
            _ingest(_mp, _sc)
    language_contexts, language_findings = {}, {}
    documents = (set().union(*scope_documents.values())
                 if resolve_includes and scope_documents else set())
    prepared_all = {}
    for document in sorted(documents):
        explicit_root = os.environ.get('HEBREW_LATEX_PROJECT_ROOT')
        prepared_all[document] = prepared_documents.get(document) or document_language_contexts(
            document, Path(explicit_root) if explicit_root else None)
    # A child carrying a document boundary is still a visit of the root. It
    # must not create an independent default-Hebrew/font-policy interpretation.
    included_documents = {path for document, (contexts, _) in prepared_all.items()
                          for path in contexts if path != document and path in documents
                          and document not in prepared_all[path][0]}
    documents -= included_documents
    if resolve_includes:
        scope_languages = {scope: {declared_config(document.read_text(encoding='utf-8'))
                                  for document in roots & documents}
                           for scope, roots in scope_documents.items()}
    for document in sorted(documents):
        contexts, findings = prepared_all[document]
        for path, visits in contexts.items():
            language_contexts.setdefault(path, []).extend(visits)
        for path, issues in findings.items():
            language_findings.setdefault(path, set()).update(issues)
    total = 0
    printed = set()
    for path in files:
        _scope = _alias_scope(path)
        _languages = scope_languages.get(_scope, set())
        # Ambiguous sibling documents do not grant a project-wide exemption.
        # Each document still reads its own literal declaration in scan_file.
        _language = next(iter(_languages)) if len(_languages) == 1 else None
        resolved_path = Path(path).resolve()
        visits = language_contexts.get(resolved_path, [None])
        issues = set(language_findings.pop(resolved_path, ()))
        for context in visits:
            issues.update(scan_file(path,
                                    frozenset(scope_ltr.get(_scope, ())),
                                    frozenset(scope_list.get(_scope, ())),
                                    frozenset(scope_caps.get(_scope, ())),
                                    _language, language_context=context))
        for n, kind, text in sorted(issues):
            key = (resolved_path, n, kind, text)
            if key in printed:
                continue
            printed.add(key)
            total += 1
            print(f"{path}:{n}: [{kind}] {text}")
    # A single-file authoring check must still reject a concrete unresolved
    # include in a discovered child, even when that child was not an argv file.
    for path, issues in sorted(language_findings.items()):
        for n, kind, text in sorted(issues):
            total += 1
            print(f"{path}:{n}: [{kind}] {text}")
    print('-' * 60)
    if total:
        print(f"\u2717 {total} issue(s) found.")
        print("  LATIN-IN-H-IN-TIKZ -> wrap the Latin in \\en{...} or \\code{...}")
        print("                       (or use bare Latin in the tikzpic island).")
        print("  HEBREW-IN-EN-ISLAND -> raw Hebrew inside \\en{} takes LTR as its BASE")
        print("                        direction: labels land at the wrong end and")
        print("                        parens/prefixes mirror. Keep the Hebrew OUTSIDE")
        print("                        the island (\\en{(b)} \u05d7\u05d9\u05e9\u05d5\u05d1 \u05e0\u05db\u05d5\u05df), or, when it")
        print("                        must sit inside, wrap it: \\en{... \\h{\u05e2\u05dc\u05d4}}.")
        print("  QUOTES             -> `` '' and single ` need a font with TeX ligatures.")
        print("                        The legacy Hebrew font lacks them. Hebrew -> gershayim \u05f4 ;")
        print("                        English -> typed curly quotes \u201c \u201d .")
        print("                        (Inside \\code{}/math they are content \u2014 exempt.)")
        print("  PRIME-AFTER-MATH   -> $f$' typesets an APOSTROPHE (U+0027), not a")
        print("                        prime — the ' landed OUTSIDE the math. Move it")
        print("                        inside: $f'$ (U+2032). A possessive $X$'s is")
        print("                        fine (not flagged); for ordinals prefer $i$-th.")
        print("  BARE-IDENT-NEXT-TO-MATH -> a bare Latin identifier glued to $math$")
        print("                        reorders in RTL; wrap both as one island:")
        print("                        \\en{name $=v$} (see ISLAND-NEXT-TO-MATH).")
        print("  BOXED-HEBREW-SEGMENTS -> Hebrew \\text{} mixed with math inside")
        print("                        \\boxed/\\finalans reorders (segments scramble,")
        print("                        edge colon orphans, edge space swallowed, glued")
        print("                        digit flips). Box = math only, or ONE")
        print("                        \\text{\\h{...}} unit (nested $math$ inside is fine).")
        print("  MATH-WRAPPED-EQREF -> a prose reference must be bare: \\eqref{..}.")
        print("                        Inside math, use \\text{\\eqref{..}} with the")
        print("                        current preamble, not a raw math-mode reference.")
        print("  SPLIT-HEBREW-IN-DISPLAY -> a Hebrew sentence/list split across")
        print("                        sibling \\text{} blocks in ONE display row lays")
        print("                        out LTR — segments read in reversed order. Merge")
        print("                        into ONE \\text{} (internally RTL) or move the")
        print("                        verbal statement to a center/prose line.")
        print("  TEXTTT-NEXT-TO-MATH -> combine into one unit: \\code{name=val},")
        print("                        not \\texttt{name}$=val$ (it jams in RTL).")
        print("  ISLAND-NEXT-TO-MATH -> \\en{x}$=v$ / \\code{x}$\\to$y reorder in RTL")
        print("                        (\"=v\" jumps before x). Merge the math INSIDE")
        print("                        the island: \\en{x $=v$} / \\en{\\code{x}$\\to$y}.")
        print("                        Also \\en{label}: $math$ -> colon ORPHANS; merge:")
        print("                        \\en{label: $math$}. (A plain space \\en{x} $m$ is fine.)")
        print("  BREAKABLE-VALUE-ISLAND -> a value-list island (\\en{a $=1$, b $=2$,")
        print("                        c $=3$}) in RTL prose can line-break at an")
        print("                        internal SPACE; the fragment reads value-first")
        print("                        ('3 =' opening the next line). Restructure to a")
        print("                        table / display line / list; \\mbox{} a SHORT one.")
        print("  BREAKABLE-QUOTED-ISLAND -> a QUOTED LITERAL inside an island")
        print("                        (\\en{}, \\code{}, \\foreignlanguage{english}{})")
        print("                        (\\en{\u201cno such file\u201d}, \\code{pkill -f 'sleep 1'})")
        print("                        tears at the same internal space: the opening")
        print("                        mark ends one line and the closing mark opens")
        print("                        the next, with a line of Hebrew between them.")
        print("                        A quotation is a STRUCTURE: \\mbox{} one that")
        print("                        fits, \\codeline / listing / display otherwise.")
        print("  RANGE-SEP-BETWEEN-DIGITS -> a range separator between two NUMBERS")
        print("                        reverses them: 2020–2023 renders \"2023–2020\".")
        print("                        Fires on – — ־ (any spacing) and on SPACED - or /")
        print("                        (5 - 10 -> \"10-5\"). Unspaced 5-10 / 2020/2021 are")
        print("                        CORRECT. Fix: unspaced ASCII, or \\en{2020–2023}.")
        print("  REF-RANGE-REORDER  -> \\ref{a}–\\ref{b} renders \"1.2–1.1\" and")
        print("                        \\eqref{a}–\\eqref{b} renders \"(1.2)–(1.1)\". A comma")
        print("                        WITH a space reverses too; comma-no-space and / are")
        print("                        fine. Merge: \\en{\\eqref{a}–\\eqref{b}}, or \\autoref.")
        print("  ADJACENT-LTR-ISLANDS -> \\en{A}, \\en{B} / \\en{A} / \\en{B} reorder to")
        print("                        \"B, A\" / \"B / A\". Merge into ONE island:")
        print("                        \\en{A, B} / \\en{A / B} / \\en{\\code{a}, \\code{b}}.")
        print("  HEBREW-BEFORE-OP-MATH -> Hebrew then $=value$: the operator lands")
        print("                        at the island's far edge. Write it OUTSIDE the")
        print("                        math: 'בלוק = $4$', 'כ־$85$', 'לפחות $m$'.")
        print("  ISLAND-BEFORE-OP-MATH -> same defect with an LTR ISLAND as the left")
        print("                        operand: '\\en{Flatten} $=H\\cdot W\\cdot C$' is")
        print("                        SCANNED 'Flatten C·W·H ='. Put the relation in")
        print("                        Hebrew ('\\en{Flatten} הוא $H\\cdot W\\cdot C$',")
        print("                        'שווה ל־$..$'), or make it a display.")
        print("  PAREN-ONLY-ISLAND -> an \\en{} holding ONLY brackets (\\en{(}..\\en{)})")
        print("                        swaps/mirrors in RTL; plain (..) around Hebrew,")
        print("                        or brackets INSIDE the island for Latin.")
        print("  BOXED-ISLAND-EDGE-BRACKET -> \\mbox{\\en{..]}}: the box ENDS the bidi")
        print("                        run, so a bracket first/last INSIDE the box takes")
        print("                        the RTL base and MIRRORS (I[23:20] -> 'I[23:20[').")
        print("                        Fix: island OUTSIDE the box, \\en{\\mbox{..}}.")
        print("  HEBREW-FLOW-ARROW  -> a rightward arrow between Hebrew prose points")
        print("                        BACKWARD in RTL (שלב $\\to$ שלב). Use $\\leftarrow$")
        print("                        / $\\Leftarrow$ (points to the next step/conclusion).")
        print("  HEBREW-EQUATION-ARROW -> a rightward/implication arrow in an equation that")
        print("                        holds a Hebrew \\text OPERAND flips (the Hebrew makes")
        print("                        the eq RTL). Rewrite with a colon or Hebrew connective")
        print("                        (\\text{אם} ... \\text{אז}, \\text{גורר}), or use \\Leftarrow.")
        print("                        Pure math (s\\to\\infty, \\code{lw}\\to\\code{add}) is fine.")
        print("  MATH-TEXT-EN-COLON -> \\text{\\en{label}:} in align orphans the colon")
        print("                        (\":label\"). Put it inside: \\text{\\en{label:}}.")
        print("  COLON-TRAPPED-IN-ISLAND -> \\en{Offset:} in PROSE before Hebrew: the")
        print("                        island-final colon is the island's RIGHT edge, so")
        print("                        it renders \":Offset\". Move it OUT: \\en{Offset}:.")
        print("                        If MATH follows instead of Hebrew, MERGE per #9:")
        print("                        \\en{1a: $I_D$}. (In math \\text{} the recipe is")
        print("                        the OPPOSITE — see MATH-TEXT-EN-COLON above.)")
        print("  DOLLAR-CODE-SPLIT  -> combine into one unit: \\code{\\$a/\\$b},")
        print("                        not \\texttt{\\$a}/\\texttt{\\$b} (the $ misplaces).")
        print("  TOKEN-PUNCT-ADRIFT -> a BARE Latin token loses its own edge")
        print("                        punctuation to the far side of the word:")
        print("                        /audit prints 'audit/', .claude prints")
        print("                        'claude.', commands/ prints '/commands'.")
        print("                        Island the WHOLE token: \\code{/audit}.")
        print("                        (ב-LHC and מבחן/CV are the Hebrew")
        print("                        connective and are correct as they are.)")
        print("  LATIN-BEFORE-PAREN -> a Latin word immediately before '(' or '['")
        print("                        drags THAT bracket into the LTR run while its")
        print("                        partner stays RTL, so the pair prints '((':")
        print("                        Skill(/audit), f(2), array[0], MIPS (32 ביט).")
        print("                        Island the whole token, \\en{Skill(/audit)}, or")
        print("                        just the anchor, \\en{MIPS} (32 ביט).")
        print("  LANG-RAW-IN-MATH   -> \\h/\\en are invalid bare in math. Wrap in")
        print("                        \\text{...}: \\text{\\h{..}} / \\text{\\en{..}}.")
        print("  HEBREW-IN-MONO     -> Hebrew in \\texttt/\\code/\\mathtt is FATAL")
        print("                        ('no glyphs in the subset' — names a font")
        print("                        file, not your line). Hebrew -> normal text.")
        print("  PUNCT-RAW-IN-MATH  -> ° … – — “ ” ‘ ’ ־ ₪ have no math-font glyph")
        print("                        and DROP silently in $..$. ° -> ^\\circ,")
        print("                        … -> \\dots, else wrap in \\text{...}.")
        print("  TEXT-PARENS-IN-MATH -> \\text{Eng (parens)} mirrors parens in RTL;")
        print("                        use \\text{\\en{Eng (parens)}} (\\en forces LTR).")
        print("                        f(Hebrew): \\text{f}(\\text{\\h{..}}) — parens at")
        print("                        math level, NOT inside the \\text box.")
        print("  AXIS-NO-END        -> add \\end{axis} before \\end{tikzpicture}. A")
        print("                        missing one throws 'Extra }' that CASCADES to the")
        print("                        next \\end{otherlanguage}/island close.")
        print("  AXIS-EXTRA-END     -> stray \\end{axis} with no \\begin{axis}.")
        print("  MATH-IN-HEADING    -> wrap heading math: \\texorpdfstring{$..$}{ascii}")
        print("                        (ascii arg free of $ ^ _), else bookmark garbles.")
        print("  BLOCK-IN-HEADING   -> \\codeline{} is a paragraph/block command and")
        print("                        cannot appear in a heading. Use inline \\code{}.")
        print("  FOOTNOTE-IN-HEADING -> an unprotected \\footnote{} is fragile in a")
        print("                        moving heading. Use \\protect\\footnote{} or move it.")
        print("  FIGCAP-NOT-ADJACENT -> \\figcap must immediately follow")
        print("                        \\end{tikzpic}/\\end{qcirc}; intervening material")
        print("                        moves the hyperlink destination.")
        print("  LISTING-SAME-LINE-DROPPED -> code on the \\begin{lstlisting} line is")
        print("                        consumed by the package (warning only) and is")
        print("                        NOT in the PDF. Put it on the NEXT line after")
        print("                        \\begin{lstlisting}[...] — and if the flagged tail")
        print("                        is a '%' COMMENT, DELETE IT: '%' eats its own")
        print("                        newline, so your FIRST BODY LINE is spliced onto")
        print("                        the \\begin line and that is what vanishes")
        print("                        (compile-proven; relocating code does not help,")
        print("                        the code is already on the next line).")
        print("  TOC-OVERRIDE-IN-DOCUMENT -> \\renewcommand\\l@section (etc.) in a file")
        print("                        that has \\begin{document} shadows the preamble's")
        print("                        measured TOC geometry. Delete it — the preamble")
        print("                        owns \\l@*; its values arrive via \\input.")
        print("  CODE-UNSAFE-CHAR   -> \\code{}/\\codeline{} are NOT verbatim: unescaped")
        print("                        # & _ ^ $ crash the compile, % eats the line, and ~")
        print("                        SILENTLY VANISHES. Escape: \\# \\& \\_ \\$ \\% , ^ -> \\^{},")
        print("                        ~ -> \\textasciitilde (all render-verified).")
        print("  HEBREW-DOUBLE-HYPHEN -> a -- / --- run stays literal hyphens (no tlig in")
        print("                        Frank Ruhl) — next to Hebrew AND between Latin/digits")
        print("                        (1990--2000, Hong--Ou--Mandel). Type — (U+2014) /")
        print("                        – (U+2013) directly. SINGLE hyphens (Hong-Ou-Mandel) fine.")
        print("                        !! NOT between DIGITS: a typed – there REVERSES the")
        print("                        numbers (1990–2000 -> \"2000–1990\"). Keep 1990-2000")
        print("                        unspaced, or merge: \\en{1990–2000}.")
        print("                        EXCEPTION: a range between TWO islands (\\en{p}--\\en{n})")
        print("                        needs a MERGE — \\en{p–n}; a typed – between separate")
        print("                        islands still swaps (see ADJACENT-LTR-ISLANDS).")
        print("                        v3.47 also catches -- flanked by $ (\"$I_D$--$V_G$\") or")
        print("                        inside \\text{} (\"$0.3\\text{--}3$\") — same fix, type –.")
        print("  HEBREW-MATH-GLUED-OBJECT -> \\text{Hebrew phrase ending in space/maqaf} in")
        print("                        math, then its bound object (a lone atom H_0, a (tuple),")
        print("                        or a sandwiched number): math lays the atom LTR so it")
        print("                        lands on the WRONG side (\"H_0 דחיית\"). Fold phrase+atom")
        print("                        into ONE \\text{\\h{..$x$..}} unit. (Non-boxed sibling of")
        print("                        BOXED-HEBREW-SEGMENTS; a new-clause subject \"..}x=..\" is")
        print("                        exempt.)")
        print("  REDUNDANT-EQREF-PARENS -> \"(\\eqref{..})\" renders \"((N))\" — \\eqref already")
        print("                        emits its own parens. Drop the literal parens (\\ref is")
        print("                        exempt: it prints a bare number).")
        print("  UNESCAPED-PERCENT  -> a literal '%' glued to content STARTS A COMMENT and")
        print("                        SILENTLY eats the rest of the line (no warning): \"30%")
        print("                        מהמקרים\" renders \"30\". Type \\% for a percent sign.")
        print("                        (A real ' % comment', line-start '%', '%%' rule, or the")
        print("                        'foo%' line-break-suppression idiom stay silent.)")
        print("  UNDEFINED-COMMON-MACRO -> \\enquote/\\SI/\\qty need csquotes/siunitx, which")
        print("                        this preamble does not load. Load the package, or")
        print("                        rewrite: gershayim ״..״ for quotes; plain math+unit.")
        print("  TEXT-MATH-CARET    -> ^ or _ inside \\text{} throws 'Missing $' (text is")
        print("                        not math). Move the math OUT: (\\text{..}45^\\circ),")
        print("                        not \\text{..45^\\circ}.")
        print("  PROVIDECOMMAND-PRIMITIVE -> \\providecommand on a TeX primitive (\\ni, \\Re,")
        print("                        \\Im, \\det...) is a SILENT no-op — the primitive keeps")
        print("                        rendering (\\ni -> ∋). Use \\renewcommand or another name.")
        print("  TEXT-HEBREW-BETWEEN-ISLANDS -> raw Hebrew between two \\en{} islands inside")
        print("                        \\text{} renders REVERSED. Make the label ONE unit:")
        print("                        \\text{\\h{(תעלה רחבה)}}, not \\en{(}עברית\\en{)}.")
        return 1
    print("\u2713 clean: no Latin-in-\\h-in-TikZ, quotes, code-next-to-math, split-$,")
    print("  Latin-before-paren, raw \\h/\\en or mirrored-parens in math,")
    print("  unbalanced axis, or unwrapped heading math.")
    print("  (Still verify visually: pdftoppm -png -r 110 doc.pdf page)")
    return 0


if __name__ == '__main__':
    if len(sys.argv) == 2 and sys.argv[1] in {'-h', '--help'}:
        print(__doc__.strip())
        print("\nUsage: python3 check_bidi_figures.py file1.tex [file2.tex ...]")
        sys.exit(0)
    sys.exit(main(sys.argv))
