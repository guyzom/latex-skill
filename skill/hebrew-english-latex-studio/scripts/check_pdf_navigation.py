#!/usr/bin/env python3
"""Validate PDF metadata, outline hierarchy, and internal navigation actions.

Every internal outline item and link annotation is resolved to a physical page
and a real PDF page object. Named GoTo destinations remain valid by default,
but are checked independently against the PDF destination name tree. Repeated
``--require-direct-named`` globs add a targeted portability contract for
critical routes that must not rely on named destinations in mobile or embedded
viewers. Each selected concrete XYZ destination must have at least one direct action to
the same normalized position and zoom; a different heading on the same page
does not cover that route. Other critical view modes fail closed when their
exact semantics cannot be verified. Title and outline completeness are never inferred from a genre:
projects may require them explicitly with ``--require-title``,
``--min-bookmarks``, and ``--min-bookmark-depth``.

Exit 0 means clean (possibly with advisory warnings), exit 1 means a hard
navigation finding, and exit 2 means an unreadable PDF or usage error.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from fnmatch import fnmatchcase
import math
from pathlib import Path
import re
import sys
from urllib.parse import quote

try:
    import fitz
except ImportError:  # pragma: no cover - exercised by build preflight
    print("pymupdf is required: python3 -m pip install pymupdf", file=sys.stderr)
    raise SystemExit(2)


@dataclass(frozen=True)
class Finding:
    flag: str
    message: str
    warning: bool = False


@dataclass(frozen=True)
class InternalAction:
    """One parsed internal navigation action in the final PDF."""

    surface: str
    location: str
    target_page: int | None
    named_destination: str | None
    direct: bool
    target_point: tuple[float, float] | None = None
    target_zoom: float | None = None


POSITION_TOLERANCE_PT = 0.05
ZOOM_TOLERANCE = 0.000001
_PDF_NUMBER = r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)'
_XYZ_ARRAY = re.compile(
    r'\[\s*(\d+)\s+\d+\s+R\s*/XYZ\s+'
    rf'({_PDF_NUMBER})\s+({_PDF_NUMBER})\s+({_PDF_NUMBER}|null)\s*\]\Z'
)
_PDF_REFERENCE = re.compile(r'(\d+)\s+\d+\s+R\Z')


def finite_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) \
        and math.isfinite(value)


def direct_xyz_position(
    doc: fitz.Document, details: dict[str, object],
) -> tuple[tuple[float, float] | None, float | None]:
    """Read a concrete direct XYZ action without mistaking another view mode.

    MuPDF's parsed point includes crop, rotation and UserUnit normalization.
    Inspect the actual destination array first: /Fit and partial /XYZ can lose
    view semantics in the high-level point representation. These actions remain
    subject to the ordinary page checks, but cannot cover a concrete XYZ route.
    """
    xref = details.get('xref')
    if not is_page_number(xref) or xref <= 0:
        return None, None
    try:
        kind, value = doc.xref_get_key(xref, 'A/D')
        if kind == 'null':
            kind, value = doc.xref_get_key(xref, 'Dest')
        seen: set[int] = set()
        while kind == 'xref':
            reference = _PDF_REFERENCE.fullmatch(value.strip())
            if reference is None:
                return None, None
            reference_xref = int(reference[1])
            if reference_xref in seen or len(seen) >= 16:
                return None, None
            seen.add(reference_xref)
            value = doc.xref_object(reference_xref, compressed=True).strip()
            kind = 'xref' if _PDF_REFERENCE.fullmatch(value) else 'array'
        match = _XYZ_ARRAY.fullmatch(value.strip()) if kind == 'array' else None
        point, zoom = details.get('to'), details.get('zoom')
        target_page = details.get('page')
        if match is None or not is_page_number(target_page) \
                or int(match[1]) != doc.page_xref(target_page) \
                or not finite_number(zoom) or zoom < 0:
            return None, None
        coordinates = tuple(point)
        if len(coordinates) != 2 or not all(finite_number(v) for v in coordinates):
            return None, None
        if not all(math.isfinite(float(match[n])) for n in (2, 3)):
            return None, None
        raw_zoom = 0.0 if match[4] == 'null' else float(match[4])
        if not math.isfinite(raw_zoom) or raw_zoom < 0 \
                or not math.isclose(zoom, raw_zoom, abs_tol=ZOOM_TOLERANCE, rel_tol=0):
            return None, None
        return (float(coordinates[0]), float(coordinates[1])), float(zoom)
    except (AttributeError, TypeError, ValueError, RuntimeError, IndexError):
        return None, None


def critical_xyz_target(
    doc: fitz.Document, name: str, target: dict[str, object] | None,
) -> tuple[tuple[int, float, float, float] | None, str | None]:
    """Resolve an explicitly selected concrete XYZ route in MuPDF coordinates.

    resolve_names() exposes PDF bottom-up coordinates. resolve_link() supplies
    the same cropped/rotated physical coordinate system as parsed direct links
    and outlines. null left/top values and Fit* modes do not define the complete
    concrete position covered by this bounded portability contract.
    """
    if target is None or 'dest' in target or 'to' not in target:
        return None, 'only concrete XYZ destinations are supported by this critical-route contract'
    try:
        # A literal PDF destination name may contain URI delimiters such as
        # "page=1". Escape it so MuPDF does not interpret it as a page query.
        resolved = doc.resolve_link('#' + quote(name, safe=''))
        zoom = target.get('zoom')
        if len(resolved) != 3 or not is_page_number(resolved[0]) \
                or not 0 <= resolved[0] < doc.page_count \
                or resolved[0] != target.get('page') \
                or not all(finite_number(v) for v in resolved[1:]) \
                or not finite_number(zoom) or zoom < 0:
            return None, 'destination has no verifiable concrete XYZ page, coordinates and zoom'
        return (resolved[0], float(resolved[1]), float(resolved[2]), float(zoom)), None
    except (AttributeError, TypeError, ValueError, RuntimeError):
        return None, 'cannot resolve concrete XYZ coordinates through the PDF destination name'


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--require-title",
        action="store_true",
        help="fail when PDF title metadata is empty",
    )
    parser.add_argument(
        "--min-bookmarks",
        type=int,
        default=0,
        metavar="N",
        help="project-required minimum outline entry count (default: 0)",
    )
    parser.add_argument(
        "--min-bookmark-depth",
        type=int,
        default=0,
        metavar="N",
        help="project-required minimum outline depth (default: 0)",
    )
    parser.add_argument(
        "--warn-no-outline-after",
        type=int,
        default=20,
        metavar="PAGES",
        help="warn when a PDF at least this long has no outline; 0 disables",
    )
    parser.add_argument(
        "--require-direct-named",
        action="append",
        default=[],
        metavar="GLOB",
        help=(
            "require each matching concrete XYZ destination to have a direct "
            "action with the same page, position and zoom; unsupported critical "
            "view modes fail closed; repeat for multiple shell-style globs"
        ),
    )
    parser.add_argument("pdf", help="compiled PDF")
    args = parser.parse_args(argv)
    if any(not pattern for pattern in args.require_direct_named):
        parser.error("--require-direct-named patterns must not be empty")
    for name in ("min_bookmarks", "min_bookmark_depth", "warn_no_outline_after"):
        if getattr(args, name) < 0:
            parser.error(f"--{name.replace('_', '-')} must be non-negative")
    return args


def is_page_number(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def target_page_finding(
    doc: fitz.Document,
    action: InternalAction,
    page_count: int,
) -> Finding | None:
    page = action.target_page
    if not is_page_number(page) or not 0 <= page < page_count:
        shown = repr(page)
        return Finding(
            f"{action.surface.upper()}-TARGET-PAGE-INVALID",
            f"{action.location} resolves to page index {shown}; PDF has "
            f"{page_count} pages",
        )
    try:
        page_xref = doc.page_xref(page)
        is_page = page_xref > 0 and (
            not hasattr(doc, "xref_is_page") or doc.xref_is_page(page_xref)
        )
    except Exception as exc:  # noqa: BLE001
        return Finding(
            f"{action.surface.upper()}-TARGET-OBJECT-UNREADABLE",
            f"cannot resolve the page object for {action.location}: {exc}",
        )
    if not is_page:
        return Finding(
            f"{action.surface.upper()}-TARGET-OBJECT-INVALID",
            f"{action.location} resolves to physical page {page + 1}, but its "
            "PDF object is not a page object",
        )
    return None


def resolve_destination_names(
    doc: fitz.Document,
) -> tuple[dict[str, dict[str, object]] | None, str | None]:
    resolver = getattr(doc, "resolve_names", None)
    if resolver is None:
        return None, (
            "installed PyMuPDF cannot resolve PDF destination names; upgrade "
            "PyMuPDF before claiming functional navigation verification"
        )
    try:
        names = resolver()
    except Exception as exc:  # noqa: BLE001
        return None, f"cannot resolve the PDF destination name tree: {exc}"
    if not isinstance(names, dict):
        return None, "PyMuPDF returned a malformed destination-name mapping"
    return names, None


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    path = Path(args.pdf)
    try:
        doc = fitz.open(path)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: cannot open {path}: {exc}")
        return 2
    if doc.needs_pass:
        print(f"ERROR: cannot inspect encrypted PDF without a password: {path}")
        doc.close()
        return 2

    hard: list[Finding] = []
    warnings: list[Finding] = []
    actions: list[InternalAction] = []
    try:
        toc = doc.get_toc(simple=False)
        pages = doc.page_count
        metadata = doc.metadata or {}

        previous_level = 0
        previous_entry = None
        for index, entry in enumerate(toc, 1):
            if len(entry) < 3:
                hard.append(Finding(
                    "BOOKMARK-MALFORMED",
                    f"outline entry {index} has no level/title/page",
                ))
                continue
            level, title, simple_page = entry[:3]
            title = (title or "").strip()
            if not is_page_number(level) or level < 1 \
                    or (previous_level and level > previous_level + 1):
                hard.append(Finding(
                    "BOOKMARK-HIERARCHY-BROKEN",
                    f"outline entry {index} jumps from level {previous_level} "
                    f"to {level}",
                ))
            if not title:
                hard.append(Finding(
                    "BOOKMARK-TITLE-EMPTY",
                    f"outline entry {index} has an empty title",
                ))
            if not is_page_number(simple_page) or not 1 <= simple_page <= pages:
                hard.append(Finding(
                    "BOOKMARK-PAGE-INVALID",
                    f"outline entry {index} points to page {simple_page}, PDF has "
                    f"{pages} pages",
                ))
            current = (level, title, simple_page)
            if previous_entry == current:
                hard.append(Finding(
                    "BOOKMARK-DUPLICATE-ADJACENT",
                    f"outline entry {index} duplicates the preceding entry "
                    f"{current!r}",
                ))
            if "\ufffd" in title or "\x00" in title:
                hard.append(Finding(
                    "BOOKMARK-TITLE-CORRUPT",
                    f"outline entry {index} contains a replacement/control glyph",
                ))

            details = entry[3] if len(entry) >= 4 and isinstance(entry[3], dict) else {}
            kind = details.get("kind")
            target_page = details.get("page")
            named_destination = details.get("nameddest")
            location = f"outline entry {index} ({title!r})"
            if kind not in {fitz.LINK_GOTO, fitz.LINK_NAMED}:
                hard.append(Finding(
                    "BOOKMARK-ACTION-NONINTERNAL",
                    f"{location} has navigation kind {kind!r}, not an internal GoTo",
                ))
            else:
                if kind == fitz.LINK_NAMED and not named_destination:
                    hard.append(Finding(
                        "BOOKMARK-NAMED-DESTINATION-MISSING",
                        f"{location} has a named GoTo action without a destination name",
                    ))
                direct = kind == fitz.LINK_GOTO and named_destination is None
                point, zoom = direct_xyz_position(doc, details) if direct else (None, None)
                action = InternalAction(
                    surface="bookmark",
                    location=location,
                    target_page=target_page if is_page_number(target_page) else None,
                    named_destination=(
                        str(named_destination) if named_destination is not None else None
                    ),
                    direct=direct,
                    target_point=point,
                    target_zoom=zoom,
                )
                actions.append(action)
                finding = target_page_finding(doc, action, pages)
                if finding:
                    hard.append(finding)
                if is_page_number(simple_page) and is_page_number(target_page) \
                        and simple_page - 1 != target_page:
                    hard.append(Finding(
                        "BOOKMARK-ACTION-PAGE-MISMATCH",
                        f"{location} reports physical page {simple_page} in the "
                        f"outline but its action resolves to {target_page + 1}",
                    ))
            previous_level = level if is_page_number(level) else previous_level
            previous_entry = current

        for source_page in range(pages):
            try:
                links = doc[source_page].get_links()
            except Exception as exc:  # noqa: BLE001
                print(
                    f"ERROR: cannot inspect links on physical page "
                    f"{source_page + 1}: {exc}"
                )
                return 2
            for link_index, link in enumerate(links, 1):
                kind = link.get("kind")
                xref = link.get("xref")
                location = (
                    f"link {link_index} on physical page {source_page + 1} "
                    f"(xref {xref})"
                )
                named_destination = link.get("nameddest")
                if kind == fitz.LINK_NONE:
                    hard.append(Finding(
                        "LINK-ACTION-MISSING",
                        f"{location} has no readable action or destination",
                    ))
                    continue
                if kind == fitz.LINK_GOTO or named_destination is not None:
                    if named_destination is not None and kind != fitz.LINK_NAMED:
                        hard.append(Finding(
                            "LINK-ACTION-KIND-INCONSISTENT",
                            f"{location} exposes named destination "
                            f"{named_destination!r} with link kind {kind!r}",
                        ))
                    direct = kind == fitz.LINK_GOTO and named_destination is None
                    point, zoom = direct_xyz_position(doc, link) if direct else (None, None)
                    action = InternalAction(
                        surface="link",
                        location=location,
                        target_page=(
                            link.get("page") if is_page_number(link.get("page")) else None
                        ),
                        named_destination=(
                            str(named_destination) if named_destination is not None else None
                        ),
                        direct=direct,
                        target_point=point,
                        target_zoom=zoom,
                    )
                    actions.append(action)
                    finding = target_page_finding(doc, action, pages)
                    if finding:
                        hard.append(finding)

        named_actions = [action for action in actions if action.named_destination]
        destination_names: dict[str, dict[str, object]] = {}
        if named_actions or args.require_direct_named:
            resolved, resolver_error = resolve_destination_names(doc)
            if resolver_error:
                print(f"ERROR: {resolver_error}")
                return 2
            assert resolved is not None
            destination_names = resolved

            for action in named_actions:
                name = action.named_destination
                assert name is not None
                target = destination_names.get(name)
                if target is None:
                    hard.append(Finding(
                        "NAMED-DESTINATION-UNRESOLVED",
                        f"{action.location} refers to absent destination {name!r}",
                    ))
                    continue
                resolved_page = target.get("page")
                resolved_action = InternalAction(
                    surface=action.surface,
                    location=f"destination {name!r} used by {action.location}",
                    target_page=resolved_page if is_page_number(resolved_page) else None,
                    named_destination=name,
                    direct=False,
                )
                finding = target_page_finding(doc, resolved_action, pages)
                if finding:
                    hard.append(finding)
                if is_page_number(resolved_page) and action.target_page != resolved_page:
                    shown = (
                        action.target_page + 1
                        if is_page_number(action.target_page)
                        else action.target_page
                    )
                    hard.append(Finding(
                        "NAMED-DESTINATION-PAGE-MISMATCH",
                        f"{action.location} reports target {shown!r}, while "
                        f"destination {name!r} resolves to physical page "
                        f"{resolved_page + 1}",
                    ))

        if args.require_direct_named:
            candidate_names = set(destination_names)
            candidate_names.update(
                action.named_destination for action in named_actions
                if action.named_destination is not None
            )
            matched_names: set[str] = set()
            for pattern in dict.fromkeys(args.require_direct_named):
                matches = {name for name in candidate_names if fnmatchcase(name, pattern)}
                if not matches:
                    hard.append(Finding(
                        "DIRECT-NAMED-PATTERN-EMPTY",
                        f"direct-navigation pattern {pattern!r} matches no PDF "
                        "destination name",
                    ))
                matched_names.update(matches)

            for action in named_actions:
                if action.named_destination in matched_names:
                    hard.append(Finding(
                        "NAMED-DESTINATION-NONPORTABLE",
                        f"{action.location} still uses named destination "
                        f"{action.named_destination!r}; materialize a direct page "
                        "destination for this viewer-critical route",
                    ))

            for name in sorted(matched_names):
                target, reason = critical_xyz_target(doc, name, destination_names.get(name))
                if reason is not None:
                    hard.append(Finding(
                        "DIRECT-DESTINATION-UNVERIFIABLE",
                        f"viewer-critical destination {name!r}: {reason}; "
                        "use a concrete XYZ route or verify this view mode separately",
                    ))
                    continue
                assert target is not None
                target_page, x, y, zoom = target
                matching = [action for action in actions
                            if action.direct and action.target_page == target_page
                            and action.target_point is not None
                            and action.target_zoom is not None
                            and all(math.isclose(a, b, abs_tol=POSITION_TOLERANCE_PT, rel_tol=0)
                                    for a, b in zip(action.target_point, (x, y)))
                            and math.isclose(action.target_zoom, zoom,
                                             abs_tol=ZOOM_TOLERANCE, rel_tol=0)]
                if not matching:
                    hard.append(Finding(
                        "DIRECT-DESTINATION-COVERAGE-MISSING",
                        f"viewer-critical destination {name!r} resolves to physical page "
                        f"{target_page + 1}, XYZ ({x:.3f}, {y:.3f}), zoom {zoom:g}, "
                        "but no direct internal action reaches that same destination; "
                        "a different position on the same page does not cover the route",
                    ))

        title = (metadata.get("title") or "").strip()
        max_depth = max(
            (entry[0] for entry in toc if entry and is_page_number(entry[0])),
            default=0,
        )
        if args.require_title and not title:
            hard.append(Finding(
                "PDF-TITLE-MISSING",
                "the project navigation contract requires non-empty PDF title metadata",
            ))
        if len(toc) < args.min_bookmarks:
            hard.append(Finding(
                "BOOKMARKS-BELOW-MINIMUM",
                f"the project navigation contract requires at least "
                f"{args.min_bookmarks} outline entries; found {len(toc)}",
            ))
        if max_depth < args.min_bookmark_depth:
            hard.append(Finding(
                "BOOKMARK-DEPTH-BELOW-MINIMUM",
                f"the project navigation contract requires outline depth "
                f"{args.min_bookmark_depth}; found {max_depth}",
            ))
        if (args.warn_no_outline_after
                and pages >= args.warn_no_outline_after
                and not toc
                and args.min_bookmarks == 0):
            warnings.append(Finding(
                "BOOKMARKS-ABSENT-LONG-DOCUMENT",
                f"{pages}-page PDF has no outline; verify whether the project "
                "requires one",
                warning=True,
            ))

        for finding in hard + warnings:
            level = "WARN" if finding.warning else "ERROR"
            print(f"[{finding.flag}] {level}: {finding.message}")
        if hard:
            print(
                f"\u2717 PDF navigation gate: {len(hard)} hard finding(s), "
                f"{len(warnings)} warning(s)."
            )
            return 1
        direct_count = sum(action.direct for action in actions)
        print(
            f"\u2713 PDF navigation clean: pages={pages}, bookmarks={len(toc)}, "
            f"depth={max_depth}, internal-actions={len(actions)}, "
            f"direct-actions={direct_count}, named-actions={len(named_actions)}, "
            f"title={'set' if title else 'empty'}"
        )
        return 0
    finally:
        doc.close()


if __name__ == "__main__":
    raise SystemExit(main())
