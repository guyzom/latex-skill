#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Original project code; scope and terms: ../LICENSING.md.
r"""Bounded, position-preserving heading analysis for the canonical TeX shell.

This is not macro expansion. Direct integer secnumdepth assignments and the
lakitsecnumdepth hook in the same source are evaluated in source order. Unknown
expressions are reported as unresolved, not promoted to a known numbered state.
Counter assignments are global (LaTeX); hook definitions obey explicit groups.
Input files are not executed: only canonical preamble/theme names are recognized.
"""
from __future__ import annotations
from dataclasses import dataclass
import re

COMMAND = re.compile(r"\\([A-Za-z@]+|[^\r\n])")
HEADINGS = {'part': -1, 'chapter': 0, 'section': 1, 'subsection': 2,
            'subsubsection': 3, 'paragraph': 4, 'subparagraph': 5}
LITERAL = re.compile(r'\\begin\s*\{(verbatim\*?|Verbatim\*?|lstlisting\*?|minted|alltt|comment)\}')
DEFS = {'def', 'gdef', 'edef', 'xdef', 'newcommand', 'renewcommand',
        'providecommand', 'DeclareRobustCommand', 'NewDocumentCommand',
        'RenewDocumentCommand', 'ProvideDocumentCommand', 'DeclareDocumentCommand',
        'newenvironment', 'renewenvironment', 'NewDocumentEnvironment',
        'RenewDocumentEnvironment'}


def blank(text: str) -> str:
    return ''.join('\n' if c == '\n' else ' ' for c in text)


def skip_space(text: str, pos: int) -> int:
    while pos < len(text) and text[pos].isspace():
        pos += 1
    return pos


def group(text: str, pos: int, opening: str = '{', closing: str = '}') -> tuple[int, int] | None:
    """Return body start and exclusive closing position; escaped braces are data."""
    pos = skip_space(text, pos)
    if text[pos:pos + 1] != opening:
        return None
    start, level, brace, i = pos + 1, 1, 0, pos + 1
    while i < len(text):
        if text[i] == '\\':
            m = COMMAND.match(text, i)
            i = m.end() if m else i + 1
            continue
        c = text[i]
        if opening == '[' and c == '{':
            brace += 1
        elif opening == '[' and c == '}':
            brace = max(0, brace - 1)
        elif brace == 0 and c == opening:
            level += 1
        elif brace == 0 and c == closing:
            level -= 1
            if level == 0:
                return start, i + 1
        i += 1
    return None


def _comment_end(text: str, start: int) -> int:
    match = re.search(r"[\r\n]", text[start:])
    return start + match.start() if match else len(text)


def _tex_space(text: str, pos: int) -> int:
    """Whitespace/comments where normal TeX argument scanning is active."""
    while pos < len(text):
        if text[pos].isspace():
            pos += 1
        elif text[pos] == "%":
            pos = _comment_end(text, pos)
        else:
            break
    return pos


def _option_end(text: str, pos: int) -> int | None:
    """Close an optional listing argument, honoring groups and comments."""
    braces, i = 0, pos + 1
    while i < len(text):
        if text[i] == "%":
            i = _comment_end(text, i)
            continue
        cmd = COMMAND.match(text, i)
        if cmd:
            i = cmd.end()
            continue
        if text[i] == "{":
            braces += 1
        elif text[i] == "}":
            if not braces:
                return None
            braces -= 1
        elif text[i] == "]" and braces == 0:
            return i + 1
        i += 1
    return None


def inline_literal_end(text: str, pos: int, command: str) -> int | None:
    """Only a completed, same-line literal receives an exemption.

    In ordinary source, verb uses the same character at both ends (even `{`);
    lstinline additionally accepts a `}` terminator for its braced form.
    Backslashes in the literal do not escape its delimiter. lstinline has no
    star modifier: `*` can itself be the delimiter. Arbitrary aliases, short
    inline definitions, category-code changes and listing escape modes are
    not interpreted. This acyclic base helper is shared by heading consumers,
    the source-hazard mask, and the source resolver's compatibility API.
    """
    # verb makes end-of-line active before looking for its delimiter.
    # Horizontal whitespace is ignored here, never an entire following line.
    while pos < len(text) and text[pos] in " \t":
        pos += 1
    if command == "verb" and text[pos:pos+1] == "*":
        pos += 1
        while pos < len(text) and text[pos] in " \t":
            pos += 1
    elif command == "lstinline" and text[pos:pos+1] == "[":
        end = _option_end(text, pos)
        if end is None:
            return None
        pos = _tex_space(text, end)
    if pos >= len(text) or text[pos] in "\r\n":
        return None
    delimiter = "}" if command == "lstinline" and text[pos] == "{" else text[pos]
    eol = _comment_end(text, pos)
    end = text.find(delimiter, pos + 1, eol)
    return end + 1 if end >= 0 else None


def clean_source(raw: str) -> str:
    """Mask comments/literals in lexical order; preserve columns and newlines."""
    text = raw.replace('\r\n', '\n').replace('\r', '\n')
    chars = list(text)
    i = 0
    while i < len(text):
        if text[i] == '%':
            end = text.find('\n', i)
            end = len(text) if end < 0 else end
            chars[i:end] = blank(text[i:end]); i = end
            continue
        if text[i] == '\\':
            literal = LITERAL.match(text, i)
            if literal:
                closer = re.search(r'\\end\s*\{' + re.escape(literal[1]) + r'\}', text[literal.end():])
                if closer:
                    end = literal.end() + closer.end()
                    chars[i:end] = blank(text[i:end]); i = end
                    continue
            cmd = COMMAND.match(text, i)
            if cmd:
                end = cmd.end()
                if cmd[1] in {'verb', 'lstinline'}:
                    stop = inline_literal_end(text, end, cmd[1])
                    if stop is not None:
                        chars[i:stop] = blank(text[i:stop]); i = stop
                        continue
                i = end
                continue
        i += 1
    return ''.join(chars)


def definition(text: str, cmd: re.Match) -> tuple[str, str, int] | None:
    """Recognize direct macro definitions, skipping their unexecuted bodies."""
    name = cmd[1]
    if name not in DEFS: return None
    i = skip_space(text, cmd.end())
    if text[i:i+1] == '*': i = skip_space(text, i+1)
    named = group(text, i)
    if named:
        target = text[named[0]:named[1]-1].strip().lstrip('\\')
        i = named[1]
    else:
        m = COMMAND.match(text, i)
        if not m: return None
        target, i = m[1], m.end()
    if name in {'def', 'gdef', 'edef', 'xdef'}:
        start = text.find('{', i)
        if start < 0: return None
        # Parameter-bearing hook definitions are not numeric overrides.
        if text[i:start].strip(): target = ''
        i = start
    else:
        while True:
            opt = group(text, i, '[', ']')
            if not opt: break
            target = ''  # parameterized definitions are not layout constants
            i = opt[1]
        if 'Document' in name:
            signature = group(text, i)
            if not signature: return None
            if text[signature[0]:signature[1]-1].strip(): target = ''
            i = signature[1]
    body = group(text, i)
    if not body: return None
    end = body[1]
    if 'environment' in name.lower():
        second = group(text, end)
        if second: end = second[1]
    return target, text[body[0]:body[1]-1], end


@dataclass(frozen=True)
class Heading:
    command: str
    offset: int
    title_start: int
    title_end: int
    end: int
    starred: bool
    depth: int | None
    # True only when a literal declaration/provider determined the depth here.
    explicit: bool
    optional: tuple[int, int] | None = None
    english: bool = False


def integer(body: str, hook: int | None) -> int | None:
    s = body.strip()
    if s == r'\lakitsecnumdepth': return hook
    return int(''.join(s.split())) if re.fullmatch(r'[+-]?\s*\d+', s) else None


def headings(text: str):
    """Walk direct commands; caller must supply clean_source(raw)."""
    depth, hook, explicit = 2, 2, False
    hook_defined = False
    hooks: list[tuple[int | None, bool, bool]] = []
    english = False
    i = 0
    while i < len(text):
        if text[i] == '{': hooks.append((hook, hook_defined, english)); i += 1; continue
        if text[i] == '}':
            if hooks: (hook, hook_defined, english) = hooks.pop()
            i += 1; continue
        m = COMMAND.match(text, i)
        if not m: i += 1; continue
        cmd, i = m[1], m.end()
        defn = definition(text, m)
        if defn:
            target, body, i = defn
            if target == 'lakitsecnumdepth':
                if cmd in {'providecommand', 'ProvideDocumentCommand'} and hook_defined:
                    continue
                hook, hook_defined = integer(body, hook), True
                if cmd in {'gdef', 'xdef'}:
                    hooks = [(hook, True, lang) for _, _, lang in hooks]
            continue
        if cmd in {'begingroup', 'bgroup'}: hooks.append((hook, hook_defined, english)); continue
        if cmd in {'endgroup', 'egroup'}:
            if hooks: (hook, hook_defined, english) = hooks.pop()
            continue
        # Do not execute a deferred hook/conditional during lexical analysis.
        # A numeric declaration after the unknown region restores knowledge.
        if cmd in {'AtBeginDocument', 'AtEndDocument', 'AddToHook'}:
            arg = group(text, i)
            if cmd == 'AddToHook' and arg: arg = group(text, arg[1])
            if arg:
                body = text[arg[0]:arg[1]-1]
                if 'secnumdepth' in body: depth, explicit = None, True
                i = arg[1]
            continue
        if cmd.startswith('if'):
            # We do not infer which branch runs. Skip balanced conditional text.
            level, stop = 1, i
            for token in COMMAND.finditer(text, i):
                if token[1].startswith('if'): level += 1
                elif token[1] == 'fi':
                    level -= 1
                    if level == 0: stop = token.end(); break
            if stop > i:
                if 'secnumdepth' in text[i:stop]: depth, hook, explicit = None, None, True
                i = stop
            continue
        if cmd in {'setcounter', 'addtocounter'}:
            counter = group(text, i)
            value = group(text, counter[1]) if counter else None
            if counter and value:
                if text[counter[0]:counter[1]-1].strip() == 'secnumdepth':
                    n = integer(text[value[0]:value[1]-1], hook)
                    depth = n if cmd == 'setcounter' else (depth+n if depth is not None and n is not None else None)
                    explicit = True
                i = value[1]
            continue
        if cmd in {'input', 'include'}:
            arg = group(text, i)
            if arg:
                filename, i = text[arg[0]:arg[1]-1].strip(), arg[1]
            else:
                bare = re.match(r'\s+([^\s{}%]+)', text[i:])
                if not bare: continue
                filename, i = bare[1], i + bare.end()
            stem = filename.rsplit('/', 1)[-1].removesuffix('.tex')
            if stem == 'preamble':
                depth, explicit, hook_defined = hook, True, True
            elif stem in {'clean_theme', 'clean_variant'}: depth, explicit = -2, True
            continue
        if cmd == 'selectlanguage':
            arg = group(text, i)
            if arg:
                english = text[arg[0]:arg[1]-1].strip() == 'english'
                i = arg[1]
            continue
        if cmd in {'begin', 'end'}:
            env = group(text, i)
            if env:
                name = text[env[0]:env[1]-1].strip()
                if cmd == 'begin': hooks.append((hook, hook_defined, english))
                elif hooks: (hook, hook_defined, english) = hooks.pop()
                i = env[1]
                if cmd == 'begin' and name in {'english', 'englishprose'}: english = True
                if cmd == 'begin' and name in {'otherlanguage', 'otherlanguage*'}:
                    arg = group(text, i)
                    if arg:
                        english = text[arg[0]:arg[1]-1].strip() == 'english'
                        i = arg[1]
            continue
        if cmd not in HEADINGS: continue
        i = skip_space(text, i)
        starred = text[i:i+1] == '*'
        if starred: i += 1
        optional = group(text, i, '[', ']')
        if optional: i = optional[1]
        title = group(text, i)
        if not title: continue
        yield Heading(cmd, m.start(), title[0], title[1]-1, title[1], starred, depth, explicit, optional, english)
        i = title[1]


# v4.19.0: the references that PRINT A NUMBER.  \pageref and \nameref do not
# and are correct on an unnumbered heading -- measured under secnumdepth=-2:
# \ref printed the EMPTY string, while \pageref gave 1 and \nameref the title.
NUMBER_REF = re.compile(r'\\(?:ref|autoref|Autoref|cref|Cref|eqref)\s*\*?\s*\{([^}]*)\}')


def label_findings(raw: str) -> list[tuple[int, str, str]]:
    """Adjacent deep labels, plus explicitly lowered shallow numbered levels."""
    text = clean_source(raw)
    numbered = {k.strip() for m in NUMBER_REF.finditer(text)
                for k in m.group(1).split(',') if k.strip()}
    out = []
    for h in headings(text):
        # Preserve legacy policy for starred shallow anchors (often nameref).
        if HEADINGS[h.command] < 3 and (h.starred or not h.explicit): continue
        tail = text[h.end:]
        lbl = re.match(r'\s*\\label\s*\{([^}]*)\}', tail)
        if not lbl: continue
        # v4.19.0, measured on the fleet: an explicit lowering makes EVERY
        # shallow heading unnumbered, and four collections anchor 203 chapters
        # that way on purpose -- 216 of those labels are read by \pageref, the
        # rest by nothing.  Only a number-printing reference turns the anchor
        # into damage, so the shallow class needs one.  The deep class (level
        # >= 3 under the default depth 2) keeps firing on the label alone: v3.64
        # measured it printing a WRONG number, which is worse than an empty one.
        if (HEADINGS[h.command] < 3 and not h.starred
                and lbl.group(1).strip() not in numbered):
            continue
        if h.starred or (h.depth is not None and HEADINGS[h.command] > h.depth):
            flag = 'LABEL-ON-UNNUMBERED-HEADING'
            why = 'starred heading' if h.starred else f'level {HEADINGS[h.command]} exceeds secnumdepth={h.depth}'
        elif h.depth is None:
            flag, why = 'HEADING-DEPTH-UNRESOLVED', 'dynamic numbering is not resolved; use a direct integer assignment and verify the PDF/aux target'
        else:
            continue
        out.append((text.count('\n',0,h.offset)+1, flag, f'\\{h.command}: {why}'))
    return out


def typeset_heading(text: str) -> str:
    """Keep texorpdfstring's first arg; mask metadata and complete LTR islands."""
    chars = list(text)
    i = 0
    while i < len(text):
        m = COMMAND.match(text, i)
        if not m: i += 1; continue
        i = m.end()
        if m[1] == 'texorpdfstring':
            first = group(text, i); second = group(text, first[1]) if first else None
            if first and second:
                chars[m.start():first[0]] = blank(text[m.start():first[0]])
                chars[first[1]-1:second[1]] = blank(text[first[1]-1:second[1]])
                # Scan its typeset arg for nested wrappers too.
                i = first[0]
        elif m[1] in {'en', 'foreignlanguage', 'code', 'texttt'}:
            arg = group(text, i)
            if m[1] == 'foreignlanguage':
                if not arg or text[arg[0]:arg[1]-1].strip() != 'english': continue
                arg = group(text, arg[1])
            if arg:
                chars[m.start():arg[1]] = blank(text[m.start():arg[1]])
                i = arg[1]
    return ''.join(chars)


def split_math_findings(raw: str) -> list[tuple[int, str, str]]:
    """Detect a symbolic heading unit torn into inline math/text/math islands.

Only Hebrew-bearing direct headings, $...$ and \\(...\\), and explicit symbolic
connectors are recognized. No inference from prose conjunctions or arbitrary
macro expansion. A complete explicit English island is already a valid unit.
"""
    text = clean_source(raw)
    out = []
    inline = re.compile(r'(?<![\\$])\$(?!\$)(?:\\[^\n]|[^$])*?(?<!\\)\$(?!\$)|\\\(.*?\\\)', re.S)
    for h in headings(text):
        if h.english: continue
        ranges = [(h.title_start, h.title_end)]
        if h.optional: ranges.append((h.optional[0], h.optional[1]-1))
        for start, end in ranges:
            projected = typeset_heading(text[start:end])
            if not re.search('[א-ת]', projected): continue
            maths = list(inline.finditer(projected))
            for a, b in zip(maths, maths[1:]):
                gap = projected[a.end():b.start()].strip()
                if re.fullmatch(r'[-−–+=/<>]+', gap):
                    out.append((text.count('\n',0,start+a.start())+1,
                                'SPLIT-MATH-IN-HEADING',
                                'symbolic heading expression crosses separate math islands; put the complete expression in one math island inside texorpdfstring'))
                    break
    return out
