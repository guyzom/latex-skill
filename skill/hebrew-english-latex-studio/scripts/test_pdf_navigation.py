#!/usr/bin/env python3
"""Adversarial tests for check_pdf_navigation.py."""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
import fitz


HERE = Path(__file__).resolve().parent
CHECKER = HERE / "check_pdf_navigation.py"
CRITICAL_NAME = "critical-section"


def make_pdf(path: Path, *, navigable: bool, action_mode: str = "direct") -> None:
    """Create direct, valid-named, or unresolved-named navigation twins."""
    if action_mode not in {"direct", "named", "unresolved"}:
        raise ValueError(action_mode)

    base = path if action_mode == "direct" else path.with_suffix(".base.pdf")
    doc = fitz.open()
    for page_no in range(24):
        page = doc.new_page()
        page.insert_text((72, 72), f"page {page_no + 1}")
    if navigable:
        doc.set_metadata({"title": "Reference document", "author": "Test author"})
        doc.set_toc([
            [1, "Section 1", 1],
            [2, "Item 1", 2],
            [2, "Item 2", 5],
            [1, "Section 2", 9],
            [2, "Item 3", 10],
            [2, "Item 4", 15],
        ])
        doc[0].insert_link({
            "kind": fitz.LINK_GOTO,
            "from": fitz.Rect(72, 90, 220, 112),
            "page": 4,
            "to": fitz.Point(72, 72),
        })
        # Keep the name tree in both twins. The corrected twin therefore proves
        # that direct actions are required, not that names must be deleted.
        target_xref = doc.page_xref(4)
        doc.xref_set_key(
            doc.pdf_catalog(),
            "Dests",
            f"<< /{CRITICAL_NAME} [ {target_xref} 0 R /XYZ 72 770 0 ] >>",
        )
    doc.save(base)
    doc.close()

    if action_mode == "direct":
        return

    destination = CRITICAL_NAME if action_mode == "named" else "absent-section"
    with fitz.open(base) as doc:
        link_xref = doc[0].get_links()[0]["xref"]
        doc.xref_set_key(
            link_xref,
            "A",
            f"<< /S /GoTo /D ({destination}) >>",
        )
        second_item = doc.get_toc(simple=False)[2]
        outline_xref = second_item[3]["xref"]
        doc.xref_set_key(
            outline_xref,
            "A",
            f"<< /S /GoTo /D ({destination}) >>",
        )
        doc.save(path)
    base.unlink()


def run(path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, str(CHECKER), *args, str(path)]
    return subprocess.run(command, text=True, capture_output=True)


def make_critical_routes(
    path: Path, *, coverage: str = 'all', two_names: bool = False,
    rotation: int = 0, cropped: bool = False, user_unit: float = 1,
    destination_mode: str = 'XYZ', first_name: str = 'critical-bottom',
) -> None:
    """One page with independently addressable XYZ routes and direct twins.

    Write matching raw PDF destinations so rotation/cropping/unit conversion is
    tested through actual MuPDF parsing, rather than reproducing that conversion
    in the fixture. Outline and annotation surfaces each exercise the contract.
    """
    doc = fitz.open()
    page = doc.new_page(width=595.276, height=841.89)
    if cropped:
        page.set_cropbox(fitz.Rect(40, 60, 560, 780))
    page.set_rotation(rotation)
    if user_unit != 1:
        doc.xref_set_key(page.xref, 'UserUnit', str(user_unit))
    doc.set_metadata({'title': 'Concrete critical navigation routes'})
    doc.set_toc([[1, 'Direct control', 1]])
    doc[0].insert_link({'kind': fitz.LINK_GOTO, 'from': fitz.Rect(80, 80, 220, 105),
                        'page': 0, 'to': fitz.Point(72, 72)})
    base = path.with_suffix('.base.pdf')
    doc.save(base)
    doc.close()
    with fitz.open(base) as doc:
        page_xref = doc.page_xref(0)
        first = f'[{page_xref} 0 R /XYZ 72 121.89 0]'
        second = f'[{page_xref} 0 R /XYZ 72 641.89 0]'
        if destination_mode == 'Fit':
            first = f'[{page_xref} 0 R /Fit]'
        elif destination_mode == 'partial-XYZ':
            first = f'[{page_xref} 0 R /XYZ null 121.89 0]'
        elif destination_mode == 'partial-top-XYZ':
            first = f'[{page_xref} 0 R /XYZ 72 null 0]'
        elif destination_mode == 'null-zoom':
            first = f'[{page_xref} 0 R /XYZ 72 121.89 null]'
        elif destination_mode == 'negative-zoom':
            first = f'[{page_xref} 0 R /XYZ 72 121.89 -1]'
        elif destination_mode != 'XYZ':
            raise ValueError(destination_mode)
        definitions = f'/{first_name} {first}'
        if two_names:
            definitions += f' /critical-middle {second}'
        doc.xref_set_key(doc.pdf_catalog(), 'Dests', f'<< {definitions} >>')
        wrong = f'[{page_xref} 0 R /XYZ 72 769.89 0]'
        zoom_wrong = f'[{page_xref} 0 R /XYZ 72 121.89 2]'
        zero_zoom = f'[{page_xref} 0 R /XYZ 72 121.89 0]'
        null_zoom = f'[{page_xref} 0 R /XYZ 72 121.89 null]'
        link_destination = wrong if coverage == 'wrong' else \
            zoom_wrong if coverage == 'zoom' else \
            zero_zoom if coverage == 'zero-zoom' else \
            null_zoom if coverage == 'null-zoom' else first
        outline_destination = second if two_names and coverage == 'all' else link_destination
        link_xref = doc[0].get_links()[0]['xref']
        outline_xref = doc.get_toc(simple=False)[0][3]['xref']
        doc.xref_set_key(link_xref, 'A', f'<< /S /GoTo /D {link_destination} >>')
        doc.xref_set_key(outline_xref, 'A', f'<< /S /GoTo /D {outline_destination} >>')
        doc.save(path)
    base.unlink()


def main() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        broken = root / "broken.pdf"
        direct = root / "direct.pdf"
        named = root / "named.pdf"
        unresolved = root / "unresolved.pdf"
        make_pdf(broken, navigable=False)
        make_pdf(direct, navigable=True, action_mode="direct")
        make_pdf(named, navigable=True, action_mode="named")
        make_pdf(unresolved, navigable=True, action_mode="unresolved")

        default_unstructured = run(broken)
        default_output = default_unstructured.stdout + default_unstructured.stderr
        assert default_unstructured.returncode == 0, default_output
        assert "[BOOKMARKS-ABSENT-LONG-DOCUMENT]" in default_output, default_output

        strict = run(
            broken,
            "--require-title",
            "--min-bookmarks", "5",
            "--min-bookmark-depth", "2",
        )
        strict_output = strict.stdout + strict.stderr
        assert strict.returncode == 1, strict_output
        for flag in (
            "PDF-TITLE-MISSING",
            "BOOKMARKS-BELOW-MINIMUM",
            "BOOKMARK-DEPTH-BELOW-MINIMUM",
        ):
            assert flag in strict_output, strict_output

        good = run(
            direct,
            "--require-title",
            "--min-bookmarks", "5",
            "--min-bookmark-depth", "2",
        )
        good_output = good.stdout + good.stderr
        assert good.returncode == 0, good_output
        assert "internal-actions=7" in good_output, good_output
        assert "direct-actions=7" in good_output, good_output

        named_default = run(named)
        named_default_output = named_default.stdout + named_default.stderr
        assert named_default.returncode == 0, named_default_output
        assert "named-actions=2" in named_default_output, named_default_output

        named_portable = run(named, "--require-direct-named", "critical-*")
        named_portable_output = named_portable.stdout + named_portable.stderr
        assert named_portable.returncode == 1, named_portable_output
        assert "[NAMED-DESTINATION-NONPORTABLE]" in named_portable_output, (
            named_portable_output
        )
        assert "[DIRECT-DESTINATION-COVERAGE-MISSING]" in named_portable_output, (
            named_portable_output
        )

        direct_portable = run(direct, "--require-direct-named", "critical-*")
        assert direct_portable.returncode == 0, (
            direct_portable.stdout + direct_portable.stderr
        )

        unresolved_result = run(unresolved)
        unresolved_output = unresolved_result.stdout + unresolved_result.stderr
        assert unresolved_result.returncode == 1, unresolved_output
        assert "[NAMED-DESTINATION-UNRESOLVED]" in unresolved_output, unresolved_output

        empty_contract = run(direct, "--require-direct-named", "absent-*")
        empty_output = empty_contract.stdout + empty_contract.stderr
        assert empty_contract.returncode == 1, empty_output
        assert "[DIRECT-NAMED-PATTERN-EMPTY]" in empty_output, empty_output

        wrong_point = root / 'critical-wrong-same-page.pdf'
        make_critical_routes(wrong_point, coverage='wrong')
        result = run(wrong_point, '--require-direct-named', 'critical-*')
        output = result.stdout + result.stderr
        assert result.returncode == 1 and '[DIRECT-DESTINATION-COVERAGE-MISSING]' in output, output

        one_missing = root / 'critical-one-of-two.pdf'
        make_critical_routes(one_missing, coverage='first', two_names=True)
        result = run(one_missing, '--require-direct-named', 'critical-*')
        output = result.stdout + result.stderr
        assert result.returncode == 1 and "'critical-middle'" in output, output
        assert "'critical-bottom'" not in output, output

        wrong_zoom = root / 'critical-wrong-zoom.pdf'
        make_critical_routes(wrong_zoom, coverage='zoom')
        result = run(wrong_zoom, '--require-direct-named', 'critical-*')
        output = result.stdout + result.stderr
        assert result.returncode == 1 and '[DIRECT-DESTINATION-COVERAGE-MISSING]' in output, output

        for rotation, cropped, unit in [(0, False, 1), (0, True, 1),
                                        (90, True, 1), (180, True, 1),
                                        (270, True, 1), (90, True, 2)]:
            matching = root / f'critical-matched-{rotation}-{cropped}-{unit}.pdf'
            make_critical_routes(matching, two_names=True, rotation=rotation,
                                 cropped=cropped, user_unit=unit)
            result = run(matching, '--require-direct-named', 'critical-*')
            output = result.stdout + result.stderr
            assert result.returncode == 0, output
            assert 'direct-actions=2' in output, output

        for mode in ('Fit', 'partial-XYZ', 'partial-top-XYZ', 'negative-zoom'):
            unsupported = root / f'critical-unsupported-{mode}.pdf'
            make_critical_routes(unsupported, destination_mode=mode)
            result = run(unsupported, '--require-direct-named', 'critical-*')
            output = result.stdout + result.stderr
            assert result.returncode == 1 and '[DIRECT-DESTINATION-UNVERIFIABLE]' in output, output

        for name_mode, coverage in [('null-zoom', 'zero-zoom'), ('XYZ', 'null-zoom')]:
            retained_zoom = root / f'critical-retain-zoom-{name_mode}.pdf'
            make_critical_routes(retained_zoom, destination_mode=name_mode, coverage=coverage)
            result = run(retained_zoom, '--require-direct-named', 'critical-*')
            assert result.returncode == 0, result.stdout + result.stderr

        # The normalized-coordinate boundary must reject either nonfinite axis.
        # Partial-XYZ CLI controls above exercise real NaN positions; these
        # resolver doubles cover +/-infinity without relying on invalid PDF
        # numeric syntax that MuPDF might repair differently across versions.
        from check_pdf_navigation import critical_xyz_target
        class NonfiniteResolver:
            page_count = 1
            def __init__(self, point):
                self.point = point
            def resolve_link(self, _name):
                return (0, *self.point)
        for point in [(float('nan'), 72), (72, float('nan')),
                      (float('inf'), 72), (72, -float('inf'))]:
            target, reason = critical_xyz_target(NonfiniteResolver(point), 'critical-bottom',
                                                {'page': 0, 'to': (72, 770), 'zoom': 0})
            assert target is None and reason is not None, (point, target, reason)

        reserved_name = root / 'critical-uri-delimiter-name.pdf'
        make_critical_routes(reserved_name, first_name='page=1')
        result = run(reserved_name, '--require-direct-named', 'page=*')
        assert result.returncode == 0, result.stdout + result.stderr

    print(
        "PDF navigation: explicit metadata/outline contracts are enforced; every "
        "internal action resolves; targeted portability distinguishes named/direct twins "
        "and requires each concrete XYZ position/zoom, including rotated/cropped pages"
    )


if __name__ == "__main__":
    main()
