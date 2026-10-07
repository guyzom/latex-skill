#!/usr/bin/env python3
r"""Bounded source-language context for the five-profile document contract.

This is lexical analysis, not TeX execution. Direct literal profile hook
definitions, language environments, scoped ``\selectlanguage``, and balanced
``\h``/``\en``/``\foreignlanguage`` arguments are understood. Literal braces and
TeX's ``\begingroup``/``\endgroup`` and ``\bgroup``/``\egroup`` scope language
switches. Comments,
literal examples and unexecuted macro definitions cannot change the context.
Unknown macros and dynamic language names inherit their surrounding context.
An unbalanced inline argument never grants an exemption through end of file.
"""
from __future__ import annotations

from dataclasses import dataclass
import bisect
import re
import sys

sys.dont_write_bytecode = True

from heading_source import COMMAND, clean_source, definition, group, skip_space
from resolve_tex_sources import optional_argument_end
from check_source_hazards import LITERAL_ENVS, mask_source

PROFILES = frozenset({'hebrew', 'english', 'hebrew-with-english',
                      'english-with-hebrew', 'bilingual'})
LANGUAGES = frozenset({'hebrew', 'english'})
LANGUAGE_ENVS = frozenset({'english', 'englishprose', 'hebrew', 'hebrewprose',
                          'otherlanguage', 'otherlanguage*'})
INCLUDE_COMMANDS = frozenset({'input', 'include', 'subfile', 'import', 'subimport',
                             'inputfrom', 'subinputfrom', 'includefrom',
                             'subincludefrom'})


def clean_language_source(raw: str) -> str:
    """Use the tested TeX inline-literal delimiters without masking live math.

    In particular, verb's opening brace is also its closing delimiter, and
    lstinline's braced form ends at the first closing brace, without balancing
    its literal payload. Pre-mask those complete forms before heading_source's
    extended literal/comment view; retain identical positions and newlines.
    """
    normalized = raw.replace('\r\n', '\n').replace('\r', '\n')
    return clean_source(mask_source(normalized, envs=LITERAL_ENVS))


def listing_arguments_end(text: str, pos: int) -> int:
    """Skip literal-file listing options/path without executing their tokens."""
    opening = skip_space(text, pos)
    if text[opening:opening + 1] == '[':
        option_end = optional_argument_end(text, opening)
        if option_end:
            pos = option_end
    path = group(text, pos)
    return path[1] if path else pos


def listing_text_ranges(text: str, pos: int) -> list[tuple[int, int]]:
    """Locate listings' caption/title text, excluding other option metadata.

    This is a bounded key-value scan, not listings key execution. Commas inside
    braced values are data; caption's optional short text remains in the span.
    """
    opening = skip_space(text, pos)
    option_end = optional_argument_end(text, opening) if text[opening:opening + 1] == '[' else None
    if not option_end:
        return []
    ranges = []
    i, stop = opening + 1, option_end - 1
    while i < stop:
        i = skip_space(text, i)
        key_start = i
        while i < stop and text[i] not in '=,':
            i += 1
        key = text[key_start:i].strip()
        if i >= stop:
            break
        if text[i] == ',':
            i += 1
            continue
        value_start = skip_space(text, i + 1)
        i = value_start
        while i < stop and text[i] != ',':
            nested = group(text, i)
            token = COMMAND.match(text, i)
            i = nested[1] if nested else token.end() if token else i + 1
        if key in {'caption', 'title'}:
            ranges.append((value_start, i))
        i += 1
    return ranges


@dataclass(frozen=True)
class LanguageConfig:
    profile: str = 'hebrew'
    main: str = 'hebrew'
    explicit: bool = False

    @property
    def native_english_font(self) -> bool:
        return self.explicit and self.profile != 'hebrew'


def declared_config(raw: str, inherited: LanguageConfig | None = None) -> LanguageConfig:
    r"""Read literal hook definitions; ``providecommand`` cannot replace a value.

    Document-local definitions win over an inherited project declaration.
    Calls to the hook are not setters: the public contract uses pre-input
    ``\def\lakitlanguageprofile{english}`` (or a literal newcommand).
    """
    text = clean_language_source(raw)
    values: dict[str, str] = {}
    i = 0
    while i < len(text):
        m = COMMAND.match(text, i)
        if not m:
            i += 1
            continue
        i = m.end()
        if m[1] == 'lstinputlisting':
            i = listing_arguments_end(text, i)
            continue
        d = definition(text, m)
        if not d:
            continue
        target, body, i = d
        if target not in {'lakitlanguageprofile', 'lakitmainlanguage'}:
            continue
        value = body.strip()
        allowed = PROFILES if target == 'lakitlanguageprofile' else LANGUAGES
        if value not in allowed:
            continue  # compiler owns unsupported/dynamic configuration errors
        if m[1] in {'providecommand', 'ProvideDocumentCommand', 'newcommand',
                    'NewDocumentCommand'} and target in values:
            continue
        values[target] = value
    base = inherited or LanguageConfig()
    profile = values.get('lakitlanguageprofile', base.profile)
    explicit = 'lakitlanguageprofile' in values or base.explicit
    if profile == 'bilingual':
        main = values.get('lakitmainlanguage', base.main)
    else:
        main = 'english' if profile in {'english', 'english-with-hebrew'} else 'hebrew'
    return LanguageConfig(profile, main, explicit)


class LanguageContext:
    """Source-position lookup with one-based line and zero-based column APIs."""

    def __init__(self, raw: str, inherited: LanguageConfig | None = None, *,
                 entry_language: str | None = None,
                 document_config: LanguageConfig | None = None,
                 include_callback=None, in_document: bool = False):
        """Keep document font/profile policy separate from an included locale.

        A bounded include callback receives (offset, command, locale,
        in_document) and may return (argument_end, child_exit_locale), with an
        optional third value for the child's final document-body state. It is
        called only at executable lexical tokens, outside definitions/literals.
        The callback owns file resolution; ordinary callers need no callback.
        """
        self.text = clean_language_source(raw)
        self.config = document_config or declared_config(raw, inherited)
        self.entry_language = self.config.main if entry_language is None else entry_language
        if self.entry_language not in LANGUAGES:
            raise ValueError('entry_language must be english or hebrew')
        self.include_callback = include_callback
        self.entry_in_document = in_document
        self.has_document = False
        self.boundary_errors: list[tuple[int, str]] = []
        self.starts = [0] + [m.end() for m in re.finditer('\n', self.text)]
        self.english = bytearray(len(self.text))
        self._parse()

    def _parse(self) -> None:
        text = self.text
        lang = self.entry_language
        in_document = self.entry_in_document
        # Environment and brace scopes both restore a local language switch.
        stack: list[tuple[str, str, str]] = []
        i = 0
        while i < len(text):
            start = i
            before = lang
            overlays = []
            m = COMMAND.match(text, i)
            if m:
                cmd, i = m[1], m.end()
                d = definition(text, m)
                if d:
                    i = d[2]  # definitions are data until called
                elif cmd == 'lstinputlisting':
                    for first, last in listing_text_ranges(text, i):
                        def caption_include(offset, command, language, body, first=first):
                            result = self.include_callback(first + offset, command, language, body)
                            if result:
                                return (result[0] - first, *result[1:])
                            return None
                        caption = LanguageContext(
                            text[first:last], entry_language=lang, document_config=self.config,
                            include_callback=caption_include if self.include_callback else None,
                            in_document=in_document)
                        overlays.append((first, last, caption.english))
                    i = listing_arguments_end(text, i)
                elif cmd in INCLUDE_COMMANDS and self.include_callback:
                    result = self.include_callback(start, cmd, lang, in_document)
                    if result:
                        i, lang = result[:2]
                        if len(result) == 3:
                            in_document = result[2]
                elif cmd in {'begin', 'end'}:
                    g = group(text, i)
                    if g:
                        env, i = text[g[0]:g[1] - 1].strip(), g[1]
                        if cmd == 'end' and env == 'document':
                            in_document = False
                        if cmd == 'begin':
                            if env == 'document':
                                self.has_document = in_document = True
                            target = {'english': 'english', 'englishprose': 'english',
                                      'hebrew': 'hebrew', 'hebrewprose': 'hebrew'}.get(env)
                            if env in {'otherlanguage', 'otherlanguage*'}:
                                argpos = i
                                if env == 'otherlanguage*':
                                    opt = group(text, argpos, '[', ']')
                                    if opt:
                                        argpos = opt[1]
                                arg = group(text, argpos)
                                if arg:
                                    candidate, i = text[arg[0]:arg[1] - 1].strip(), arg[1]
                                    if candidate in LANGUAGES:
                                        target = candidate
                            stack.append(('env', env, lang))
                            if target:
                                lang = target
                        elif stack and stack[-1][:2] == ('env', env):
                            lang = stack.pop()[2]
                        elif env in LANGUAGE_ENVS:
                            self.boundary_errors.append((start, 'language environment closes outside this file'))
                elif cmd in {'begingroup', 'bgroup'}:
                    # TeX's primitive group commands scope language assignments
                    # like literal braces, including inside language environments.
                    stack.append(('group', '', lang))
                elif cmd in {'endgroup', 'egroup'}:
                    if stack and stack[-1][0] == 'group':
                        lang = stack.pop()[2]
                    else:
                        self.boundary_errors.append((start, 'primitive group closes outside this file'))
                elif cmd == 'selectlanguage':
                    g = group(text, i)
                    if g:
                        target, i = text[g[0]:g[1] - 1].strip(), g[1]
                        if target in LANGUAGES:
                            lang = target
                elif cmd in {'h', 'en', 'texthebrew', 'textenglish', 'foreignlanguage'}:
                    target = {'h': 'hebrew', 'en': 'english', 'texthebrew': 'hebrew',
                              'textenglish': 'english'}.get(cmd)
                    argpos = i
                    if cmd == 'foreignlanguage':
                        # Babel's star form takes {language}{paragraph}; only
                        # the nonstar form accepts [options] before {language}.
                        argpos = skip_space(text, argpos)
                        if text[argpos:argpos + 1] == '*':
                            argpos += 1
                        else:
                            opt = group(text, argpos, '[', ']')
                            if opt:
                                argpos = opt[1]
                        spec = group(text, argpos)
                        if spec:
                            candidate = text[spec[0]:spec[1] - 1].strip()
                            argpos = spec[1]
                            if candidate in LANGUAGES:
                                target = candidate
                    body = group(text, argpos)
                    if target and body:
                        stack.append(('group', '', lang))
                        i, lang = body[0], target
            else:
                i += 1
                if text[start] == '{':
                    stack.append(('group', '', lang))
                elif text[start] == '}' and stack and stack[-1][0] == 'group':
                    lang = stack.pop()[2]
                elif text[start] == '}':
                    self.boundary_errors.append((start, 'brace group closes outside this file'))
            self.english[start:i] = bytes([before == 'english']) * (i - start)
            for first, last, english in overlays:
                self.english[first:last] = english
        self.exit_language = lang
        self.exit_in_document = in_document
        if any(kind == 'group' or name in LANGUAGE_ENVS for kind, name, _ in stack):
            self.boundary_errors.append((len(text), 'language or group scope remains open at file end'))

    def is_english(self, line: int, column: int = 0) -> bool:
        if not 1 <= line <= len(self.starts):
            return self.entry_language == 'english'
        offset = self.starts[line - 1] + max(0, column)
        if offset >= len(self.english):
            return self.exit_language == 'english'
        return bool(self.english[offset])

    def line_all_english(self, line: int) -> bool:
        """Only use for optional broad guards; match guards use exact positions."""
        start = self.starts[line - 1]
        stop = self.starts[line] - 1 if line < len(self.starts) else len(self.text)
        return all(self.english[i] for i in range(start, stop)
                   if not self.text[i].isspace())

    def line_column(self, offset: int) -> tuple[int, int]:
        index = bisect.bisect_right(self.starts, offset) - 1
        return index + 1, offset - self.starts[index]
