#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Original project code; scope and terms: ../LICENSING.md.
r"""Resolve the literal local sources that contribute to a TeX document.

The resolver follows \input, \include, \subfile, \subfileinclude, import.sty-family commands,
and \lstinputlisting. Dynamic paths are rejected: a pre-build gate cannot
prove which file they select. Resolved paths must remain inside --project-root
(the root document's directory by default).

Primitive inputs and listings search import.sty's active import directory
first, then the build working directory. Top-level import/inputfrom/includefrom
paths are rooted at the build directory; their sub* forms extend the active
import directory.
Subfiles use the same active-directory behavior as \subimport and add their
argument's directory before the inherited input search paths.

Listing option text remains opaque to this literal source resolver. It does not
evaluate package keys or expand executable caption content; recorder validation
provides the post-build dependency truth.

Exit 0 means the graph is complete, 1 means an unsafe/missing dependency was
found, and 2 means bad usage or an unreadable root.
"""

from __future__ import annotations

import argparse
from collections import deque
from dataclasses import dataclass
from pathlib import Path
import re
import sys
from typing import Iterator

sys.dont_write_bytecode = True
from check_source_hazards import _inline_end, _option_end, mask_source


LITERAL_ENVS = ("lstlisting", "lstlisting*", "verbatim", "verbatim*",
                "Verbatim", "Verbatim*")
SIMPLE = re.compile(r"\\(?P<cmd>input|include|subfile|subfileinclude)\s*\{(?P<path>[^{}]+)\}")
LISTING = re.compile(r"\\lstinputlisting(?![A-Za-z])")
LISTING_PATH = re.compile(r"\s*\{(?P<path>[^{}]+)\}")
IMPORT = re.compile(
    r"\\(?P<cmd>import|subimport|inputfrom|subinputfrom|"
    r"includefrom|subincludefrom)\s*"
    r"\{(?P<directory>[^{}]+)\}\s*\{(?P<path>[^{}]+)\}"
)
BARE_INPUT = re.compile(r"\\input\s+(?P<path>[^\s%{}]+)")
DYNAMIC = re.compile(r"[\\#$]")
# With the ordinary TeX catcodes, a control word consumes all following letters;
# a control symbol consumes exactly the next character. A pair of backslashes
# is one control symbol; a third backslash starts a new control sequence.
CONTROL_SEQUENCE = re.compile(r"\\(?:[A-Za-z]+|[^A-Za-z])")
# Kpathsea's standard TeX-input suffixes suppress implicit .tex appending.
# Other suffixes are ordinary basename text: chapter.v1 searches chapter.v1.tex
# before chapter.v1. Include-family commands instead require a .tex filename.
TEX_INPUT_SUFFIXES = frozenset({
    ".tex", ".sty", ".cls", ".fd", ".aux", ".bbl", ".def", ".clo", ".ldf",
})


@dataclass(frozen=True)
class Dependency:
    path: Path
    kind: str  # "tex" or "literal"
    import_paths: tuple[Path, ...]


@dataclass(frozen=True)
class DependencyOccurrence:
    dependency: Dependency
    start: int
    end: int


@dataclass(frozen=True)
class _ListingCommand:
    start: int
    end: int
    path: str


def optional_argument_end(text: str, opening_position: int) -> int | None:
    """Close at the first unprotected ], respecting groups/control symbols."""
    if text[opening_position:opening_position + 1] != "[":
        return None
    return _option_end(text, opening_position)


def command_matches(
    pattern: re.Pattern[str], text: str, start: int = 0
) -> Iterator[re.Match[str]]:
    """Match only at actual TeX control-sequence starts, preserving offsets."""
    for token in CONTROL_SEQUENCE.finditer(text, start):
        match = pattern.match(text, token.start())
        # The match must consume the whole control word, not a name prefix.
        if match is not None and match.end() >= token.end():
            yield match


def listing_commands(text: str) -> Iterator[_ListingCommand]:
    for command in command_matches(LISTING, text):
        pos = command.end()
        while pos < len(text) and text[pos].isspace():
            pos += 1
        if text[pos:pos + 1] == "[":
            option_end = optional_argument_end(text, pos)
            if option_end is None:
                continue
            pos = option_end
        path = LISTING_PATH.match(text, pos)
        if path:
            yield _ListingCommand(command.start(), path.end(), path.group("path"))


def strip_comment(raw: str) -> str:
    line = list(raw)
    slash_run = 0
    for index, char in enumerate(raw):
        if char == "\\":
            slash_run += 1
            continue
        if char == "%" and slash_run % 2 == 0:
            line[index:] = " " * (len(raw) - index)
            break
        slash_run = 0
    return "".join(line)


def blank_inline_literals(line: str) -> str:
    r"""Blank \verb, \verb*, and \lstinline spans with arbitrary delimiters."""
    chars = list(line)
    start = 0
    pattern = re.compile(r'\\(?P<cmd>verb|lstinline)(?![A-Za-z])')
    while True:
        match = next(command_matches(pattern, line, start), None)
        if not match:
            break
        end = _inline_end(line, match.end(), match.group("cmd"))
        if end is not None:
            chars[match.start():end] = " " * (end - match.start())
        start = end if end is not None else match.end()
    return "".join(chars)


def strip_comments_and_literals(text: str) -> str:
    """Preserve line/column positions while blanking comments and literals."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    # Share the proven TeX delimiter scanner; grant only the resolver's known
    # literal forms an exemption, not TikZ/math or arbitrary macro expansion.
    return mask_source(normalized, envs=LITERAL_ENVS)


def literal_path(raw: str, base: Path, suffix: str | None, project_root: Path,
                 *, force_suffix: bool = False) -> Path:
    value = raw.strip()
    if not value or DYNAMIC.search(value):
        raise ValueError(f"dynamic path {value!r}")
    path = Path(value)
    if not path.is_absolute():
        path = base / path
    candidates = [path]
    if suffix and force_suffix and path.suffix != suffix:
        candidates = [Path(str(path) + suffix)]
    elif suffix and not force_suffix and path.suffix not in TEX_INPUT_SUFFIXES:
        candidates = [Path(str(path) + suffix), path]
    first = None
    for candidate in candidates:
        candidate = candidate.resolve()
        try:
            candidate.relative_to(project_root)
        except ValueError as exc:
            raise ValueError(
                f"dependency escapes project root {project_root}: {candidate}"
            ) from exc
        if first is None:
            first = candidate
        if candidate.is_file():
            return candidate
    return first


def searched_path(
    raw: str,
    import_paths: tuple[Path, ...],
    project_root: Path,
    suffix: str | None,
    *,
    force_suffix: bool = False,
) -> Path:
    """Mirror import.sty's ordered active input path."""
    first = None
    for base in import_paths:
        candidate = literal_path(raw, base, suffix, project_root,
                                 force_suffix=force_suffix)
        if first is None:
            first = candidate
        if candidate.is_file():
            return candidate
    return first


def _with_import_directory(directory: Path, import_paths: tuple[Path, ...]) -> tuple[Path, ...]:
    """Prepend an active import directory without growing repeated contexts."""
    # Keep the compilation directory last, even when it is also active.
    return ((directory,) + tuple(path for path in import_paths[:-1] if path != directory)
            + (import_paths[-1],))


def _dependency_occurrences(
    source: Path, project_root: Path, import_paths: tuple[Path, ...],
    command_start: int | None = None,
) -> list[DependencyOccurrence]:
    text = strip_comments_and_literals(source.read_text(encoding="utf-8"))
    found: list[DependencyOccurrence] = []
    imports = list(command_matches(IMPORT, text))
    listings = list(listing_commands(text))
    occupied: list[tuple[int, int]] = []
    # Reserve outer argument spans before resolving any family or requested
    # offset. Package option text can contain control words as literal data.
    spans = [match.span() for match in imports]
    spans.extend((listing.start, listing.end) for listing in listings)
    for span in sorted(spans, key=lambda item: (item[0], -item[1])):
        if not any(start <= span[0] < end for start, end in occupied):
            occupied.append(span)

    for match in imports:
        if any(start < match.start() < end for start, end in occupied):
            continue
        if command_start is not None and match.start() != command_start:
            continue
        command = match.group("cmd")
        directory_base = import_paths[0] if command.startswith("sub") else import_paths[-1]
        directory = literal_path(
            match.group("directory"), directory_base, None, project_root
        )
        target = literal_path(
            match.group("path"), directory, ".tex", project_root,
            force_suffix="include" in command,
        )
        child_paths = _with_import_directory(directory, import_paths)
        found.append(DependencyOccurrence(
            Dependency(target, "tex", child_paths), *match.span()
        ))

    for listing in listings:
        if any(start < listing.start < end for start, end in occupied):
            continue
        if command_start is not None and listing.start != command_start:
            continue
        found.append(
            DependencyOccurrence(Dependency(searched_path(
                listing.path, import_paths, project_root, None
            ), "literal", import_paths), listing.start, listing.end)
        )

    for match in command_matches(SIMPLE, text):
        if command_start is not None and match.start() != command_start:
            continue
        if any(start <= match.start() < end for start, end in occupied):
            continue
        command = match.group("cmd")
        if command in {"subfile", "subfileinclude"}:
            value = match.group("path").strip()
            requested = Path(value)
            if not requested.name or value.endswith("/"):
                raise ValueError(f"subfile path has no filename: {value!r}")
            # subfiles.sty splits the argument and delegates to subimport (or
            # subincludefrom). The directory belongs to that literal argument,
            # not the real target's parent when the target is a symlink.
            directory = literal_path(str(requested.parent), import_paths[0], None, project_root)
            target = literal_path(requested.name, directory, ".tex", project_root,
                                  force_suffix=command == "subfileinclude")
            found.append(DependencyOccurrence(
                Dependency(target, "tex", _with_import_directory(directory, import_paths)),
                *match.span(),
            ))
            continue
        found.append(
            DependencyOccurrence(Dependency(searched_path(
                match.group("path"), import_paths, project_root, ".tex",
                force_suffix=match.group("cmd") == "include",
            ), "tex", import_paths), *match.span())
        )

    for match in command_matches(BARE_INPUT, text):
        if command_start is not None and match.start() != command_start:
            continue
        if any(start <= match.start() < end for start, end in occupied):
            continue
        found.append(
            DependencyOccurrence(Dependency(searched_path(
                match.group("path"), import_paths, project_root, ".tex"
            ), "tex", import_paths), *match.span())
        )
    return found


def dependency_occurrences(
    source: Path, project_root: Path, import_paths: tuple[Path, ...]
) -> list[DependencyOccurrence]:
    """Return every literal dependency callsite in source order, including repeats."""
    return sorted(_dependency_occurrences(source, project_root, import_paths),
                  key=lambda occurrence: occurrence.start)


def dependency_occurrence_at(
    source: Path, command_start: int, project_root: Path,
    import_paths: tuple[Path, ...],
) -> DependencyOccurrence | None:
    """Resolve only the actual command at an offset; ignore other callsites."""
    occurrences = _dependency_occurrences(
        source, project_root, import_paths, command_start=command_start
    )
    return occurrences[0] if occurrences else None


def dependencies(
    source: Path, project_root: Path, import_paths: tuple[Path, ...]
) -> list[Dependency]:
    # Preserve the existing family order for the conservative graph resolver.
    return [occurrence.dependency for occurrence in
            _dependency_occurrences(source, project_root, import_paths)]


def resolve(
    root: Path, project_root: Path
) -> tuple[list[Dependency], list[str]]:
    queue: deque[Dependency] = deque([
        # v4.0.1: the root document's relative \input resolves against ITS OWN
        # DIRECTORY, which is what TeX does (cwd = the source dir), not against
        # project_root. The two coincide whenever project_root is the default, so
        # every collection built fine and the bug stayed invisible; they diverge
        # the moment project_root is declared higher up — measured on this skill's
        # own tests/, where `\input{../assets/preamble.tex}` resolved to
        # <skill>/../assets/preamble.tex and the gate rejected a dependency that
        # exists. The trust boundary is not a TeX search directory. Keep the
        # compilation directory last in every imported search path so top-level
        # imports always remain relative to it, even inside a nested import.
        Dependency(root.resolve(), "tex", (root.parent,))
    ])
    seen: set[Dependency] = set()
    ordered: list[Dependency] = []
    errors: list[str] = []

    while queue:
        dep = queue.popleft()
        if dep in seen:
            continue
        seen.add(dep)
        if not dep.path.is_file():
            errors.append(f"missing {dep.kind} source: {dep.path}")
            continue
        ordered.append(dep)
        if dep.kind != "tex":
            continue
        try:
            queue.extend(dependencies(dep.path, project_root, dep.import_paths))
        except UnicodeDecodeError as exc:
            errors.append(f"not UTF-8: {dep.path}: {exc}")
        except (OSError, ValueError) as exc:
            errors.append(f"cannot resolve {dep.path}: {exc}")
    return ordered, errors


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument(
        "--project-root",
        type=Path,
        help="trusted source boundary (default: root document directory)",
    )
    parser.add_argument(
        "--mode",
        choices=("all", "tex", "literal"),
        default="all",
        help="which dependency paths to print",
    )
    args = parser.parse_args(argv[1:])

    if not args.root.is_file():
        print(f"root source does not exist: {args.root}", file=sys.stderr)
        return 2
    root = args.root.resolve()
    project_root = (
        args.project_root.resolve() if args.project_root else root.parent
    )
    try:
        root.relative_to(project_root)
    except ValueError:
        print(
            f"root source is outside project root: {root} not under {project_root}",
            file=sys.stderr,
        )
        return 2

    files, errors = resolve(root, project_root)
    printed: set[Path] = set()
    for dep in files:
        if args.mode == "all" or dep.kind == args.mode:
            if dep.path not in printed:
                print(dep.path)
                printed.add(dep.path)
    for error in errors:
        print(error, file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
