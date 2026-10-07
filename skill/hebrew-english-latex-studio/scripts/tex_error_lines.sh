#!/usr/bin/env bash
# tex_error_lines.sh [--context] LOGFILE — print the GENUINE LaTeX error lines of a log.
#
# WHY THIS IS NOT `grep '^!'` (v4.1.4). When TeX reports an overfull box it
# dumps the offending material with the fonts spelled out inline, e.g.
#
#     \OT1/cmr/m/n/12 B :  +0\OML/cmm/m/it/12 :\OT1/cmr/m/n/12 009 \OMS/cmsy/...
#
# Math-symbol glyphs print as their font SLOT, and cmsy slot 33 — which is what
# \to sets — is "!". The dump is hard-wrapped (max_print_line, 79 by default,
# but NOT applied uniformly: measured on this machine the same engine wrapped a
# 425-page document's dump at ~79 and left a one-page fixture's at 659 chars),
# so a wrap landing just before a \to starts the continuation line with "!".
# `grep -c '^!'` then books a phantom error. Measured on data-science-exams:
# build.sh printed `LaTeX errors (^!): 1` and
# `✗ LaTeX error(s): ! ^^@\OT1/cmr/m/n/12 0...` while the compile was clean —
# the gate named the wrong defect, cited no source line, and the phantom only
# went away when an UNRELATED overfull box was fixed.
#
# Whitelisting the real openers does not work: they include both
# "! Undefined control sequence." and "!  ==> Fatal error occurred", so
# `^! [A-Za-z]` silently drops the fatal one — the single most important line
# in the file. The discriminator is therefore the CONTENT DUMP's own signature:
# an inline font selector <ENC>/<family>/<series>/<shape>/<size>, which no
# genuine error message carries... almost (v4.2.1, BLD-57): a FONT error
# quotes the selector of the font it failed to load, e.g.
#     ! Font \TU/FrankRuhlLibre(0)/m/n/10.95=... at 10.95pt not loadable
# and the v4.1.4 rule filtered it — measured: the count said 0 over a compile
# whose only error was exactly that line (build.sh's -halt-on-error rc path
# still failed the build, but this counter named "0 errors" over it). The fix
# is a NARROW rescue, not a general opener whitelist: a closed list of openers
# that a wrapped dump physically cannot forge — after the cmsy-"!" glyph, any
# font CHANGE prints its selector immediately, so dumped material can never
# continue as a bare English word like "Font" or "LaTeX". Selector-bearing
# lines that match a rescued opener count; all other selector-bearing lines
# remain dump noise.
#
# --context (v4.26.0, BLD-69) prints each error as a RECORD: its opening line
# through TeX's own source context, ending at the base-level line — "l.<N>
# <source text up to the error>" (plus the rest of that line, which TeX prints
# indented underneath) or "<*>" when the error happened past the end of the
# file. build.sh calls it the moment a pass exits non-zero, BEFORE any
# recorded-source check: a halted compile never writes the runtime font
# inventory, and the inventory check used to be the only thing it printed.
# The default mode is unchanged: the same discriminator, one line per error,
# which is what the build summary counts.
#
# A record opens on a genuine "!" line (the discriminator above, so a BLD-55
# dump phantom never opens one) or on the two openers LuaTeX gives no "!":
#   * an uncaught Lua error from \directlua/\latelua, printed as
#     "[\directlua]:<n>: <message>" — sometimes glued to the end of earlier
#     output (measured: a \latelua error behind "{…/pdftex.map}"), so it is
#     matched anywhere in a line that is not a tab-indented traceback frame;
#   * an error raised inside a Lua FILE ("<file>.lua:<n>: <message>"), which
#     has no fixed shape of its own and is recognised by the
#     "stack traceback:" line that follows it; the held message is replayed.
# "Runaway argument?" (and its siblings) open a record too: TeX prints the
# runaway text ABOVE the "!" line it belongs to.
# Measured on 18 real fatal logs (undefined macro at top level and inside a
# macro, LaTeX/package errors, missing $, runaway argument, \begin without
# \end, unknown pgfkeys key, Lua run-time/syntax/file/require/callback
# errors, \latelua at shipout, a context truncated with "..."): every record
# carries its message and its base-level line. Blank and whitespace-only lines
# are not printed; a record stops at the engine's end-of-run statistics
# ("Here is how much of …"), and prints at most 40 lines before its base line.
set -uo pipefail

MODE=lines
if [ "${1:-}" = "--context" ]; then
  MODE=context
  shift
fi
LOG="${1:-}"
if [ -z "$LOG" ] || [ ! -f "$LOG" ]; then
  exit 0   # no log = no errors to report; callers gate on the count.
fi

awk -v mode="$MODE" '
function genuine(s) {
  if (s !~ /^!/) return 0
  if (s ~ /^! (Font |LaTeX Error|Package [0-9A-Za-z@]+ Error|Class [0-9A-Za-z@]+ Error)/) return 1
  return s !~ /\\(OT1|OML|OMS|OMX|OT2|T1|T2A|T3|TS1|TU|U|LGR)\/[^\/]*\/[^\/]+\/[^\/]+\//
}
function lua_opener(s) {
  return s !~ /^\t/ && s ~ /[[]\\(directlua|latelua)[]]:[0-9]+: /
}
function opener(s) {
  return genuine(s) || lua_opener(s) || s ~ /^Runaway (argument|definition|preamble|text)[?]$/
}
mode == "lines" {
  if (genuine($0)) print
  next
}
{
  line = $0
  if (cont) {
    cont = 0
    if (line ~ /^ /) {
      if (line ~ /[^ \t]/) print line
      next
    }
  }
  if (inrec) {
    if (line ~ /^Here is how much of /) { inrec = 0; held = ""; next }
    if (line ~ /^l[.][0-9]+ / || line ~ /^<[*]> /) {
      print line
      inrec = 0; cont = 1; held = ""
      next
    }
    if (line ~ /[^ \t]/) {
      if (n < 40) print line
      else if (n == 40) print "[... record truncated at 40 lines ...]"
      n++
    }
    next
  }
  if (opener(line)) {
    print line
    inrec = 1; n = 1; held = ""
    next
  }
  if (line ~ /^stack traceback:$/ && held != "") {
    print held
    print line
    tmp = held
    inrec = 1; n = gsub(/\n/, "", tmp) + 2; held = ""
    next
  }
  if (line ~ /^\t/) {
    if (held != "") held = held "\n" line
  } else {
    held = line
  }
}
' "$LOG" 2>/dev/null || true
