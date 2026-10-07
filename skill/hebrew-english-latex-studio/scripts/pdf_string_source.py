#!/usr/bin/env python3
r"""Bounded source checks for layout syntax leaking into PDF strings.

The canonical PDF-string hook maps a plain \\ to a space, but does not consume
its star/optional length. Inspect the selected short-or-long unstarred title and
literal hypersetup text fields. This is not macro expansion or a PDF parser.
"""
from __future__ import annotations
import re
import sys
sys.dont_write_bytecode = True
from heading_source import COMMAND, blank, clean_source, definition, group, headings, skip_space

PDF_FIELDS = {'pdftitle', 'pdfauthor', 'pdfsubject', 'pdfkeywords'}
FLAG = 'PDFSTRING-LINEBREAK-ARG'


def pdf_projection(text: str) -> str:
    """Keep texorpdfstring's PDF branch; preserve diagnostic source offsets."""
    chars = list(text)
    i = 0
    while i < len(text):
        match = COMMAND.match(text, i)
        if not match:
            i += 1
            continue
        i = match.end()
        if match[1] == 'texorpdfstring':
            first = group(text, i)
            second = group(text, first[1]) if first else None
            if first and second:
                chars[match.start():second[0]] = blank(text[match.start():second[0]])
                chars[second[1]-1:second[1]] = ' '
                i = second[0]  # also inspect a nested PDF branch
        elif match[1] in {'label', 'href', 'url', 'nolinkurl', 'path', 'detokenize'}:
            arg = group(text, i)
            if arg:
                # For href, only the destination is masked; its visible label
                # is still scanned. The others are identifiers or literal text.
                chars[match.start():arg[1]] = blank(text[match.start():arg[1]])
                i = arg[1]
    return ''.join(chars)


def literal_metadata_regions(text: str):
    """Yield literal text-field ranges; skip uninvoked macro definitions."""
    i = 0
    while i < len(text):
        match = COMMAND.match(text, i)
        if not match:
            i += 1
            continue
        i = match.end()
        defined = definition(text, match)
        if defined:
            i = defined[2]
            continue
        if match[1] != 'hypersetup':
            continue
        arg = group(text, i)
        if not arg:
            continue
        i = arg[1]
        start, stop = arg[0], arg[1] - 1
        # Split only commas at brace depth zero; escaped commas are tokens.
        boundaries = []
        pos, left = start, start
        while pos < stop:
            token = COMMAND.match(text, pos)
            if token:
                pos = token.end()
                continue
            if text[pos] == '{':
                nested = group(text, pos)
                if nested and nested[1] <= stop:
                    pos = nested[1]
                    continue
            if text[pos] == ',':
                boundaries.append((left, pos))
                left = pos + 1
            pos += 1
        boundaries.append((left, stop))
        for left, right in boundaries:
            key = re.match(r'\s*([A-Za-z]+)\s*=\s*', text[left:right])
            if key and key[1] in PDF_FIELDS:
                yield left + key.end(), right, key[1]


def linebreak_findings(raw: str) -> list[tuple[int, str, str]]:
    """Flag explicit star/optional-length breaks in candidate PDF-string fields.

A safe short heading or texorpdfstring PDF branch is not rejected because its
printed title uses legal spacing. Starred headings have no automatic bookmark;
custom addcontentsline/pdfbookmark commands remain outside this bounded check.
Heading sources are checked conservatively even if tocdepth currently excludes
them. This is a serialization-risk guard, not proof that a bookmark was emitted.
"""
    text = clean_source(raw)
    regions = []
    for heading in headings(text):
        if heading.starred:
            continue
        if heading.optional:
            start, end = heading.optional[0], heading.optional[1] - 1
        else:
            start, end = heading.title_start, heading.title_end
        regions.append((start, end, 'bookmark'))
    regions.extend(literal_metadata_regions(text))
    findings = []
    for start, end, role in regions:
        projected = pdf_projection(text[start:end])
        for token in COMMAND.finditer(projected):
            if token[1] != '\\':
                continue
            next_pos = skip_space(projected, token.end())
            if projected[next_pos:next_pos + 1] not in {'*', '['}:
                continue
            line = text.count('\n', 0, start + token.start()) + 1
            findings.append((line, FLAG,
                f'{role}: a starred/optional-length line break can leak layout syntax '
                'into the PDF string; provide a clean short title, a texorpdfstring '
                'PDF branch, or plain metadata text'))
    return findings
