#!/usr/bin/env python3
"""v4.27.0 static contracts — no LuaLaTeX process.

BLD-71: a compile that stops after a page has shipped leaves LuaTeX's partial
PDF behind: page content, but no page tree, no fonts, no xref and no trailer.
The evidence export (BLD-56) asked only whether the file was nonempty, so it
published that file as ``*.failed.pdf`` with "diagnose page numbers from THIS
file" while no reader could open it. The export now requires Poppler to find a
page; otherwise any stale ``*.failed.pdf`` is removed and the gate says why.

build.sh is driven against a MOCK engine that leaves a chosen PDF behind
whatever its exit code, so all three branches of the export (readable,
truncated, nothing) run through the real cleanup() without a TeX installation.
The PDFs are built here, not checked in (``*.pdf`` is gitignored and the
package ships none). The two truncated shapes follow what LuaHBTeX 1.17.0 was
measured to leave; test_v4270_runtime.py proves the shape on the real engine.
Every fixture's readability is confirmed by a second reader (PyMuPDF), so the
verdicts below do not merely restate the Poppler predicate under test.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zlib

sys.dont_write_bytecode = True
import fitz
from font_paths import font_dir

ROOT = Path(__file__).resolve().parent.parent
TESTS = ROOT / "tests"
BUILD = ROOT / "scripts" / "build.sh"
HALTED_LOG = TESTS / "tex_errors_ctx_undefined.log.txt"
TRUNCATED = "no readable diagnostic PDF"
PRESERVED = "failing PDF preserved"
NOTHING = "no nonempty diagnostic PDF was produced by this failed run."
LUATEX_HEADER = b"%PDF-1.5\n%\xcc\xd5\xc1\xd4\xc5\xd8\xd0\xc4\xc6\n"


def complete_pdf(pages: int) -> bytes:
    """A finished PDF: catalog, page tree, xref and trailer, `pages` A4 pages."""
    kids = " ".join(f"{3 + i} 0 R" for i in range(pages))
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>",
               f"<< /Type /Pages /Kids [{kids}] /Count {pages} >>".encode()]
    objects += [b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595.276 841.89] >>"] * pages
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets)
    out += (f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref}\n%%EOF\n").encode()
    return bytes(out)


def halted_after_first_page() -> bytes:
    """What a stop on page 2 of a two-page document leaves (measured: 225
    bytes): the header and page 1's content stream, cut before `endstream`."""
    content = zlib.compress(b"BT /F1 10 Tf 72 770 Td <0102> Tj ET")
    return (LUATEX_HEADER + b"8 0 obj\n<< /Filter /FlateDecode /Length "
            + str(len(content)).encode() + b" >>        \nstream\n" + content)


def halted_mid_document(pages: int = 3) -> bytes:
    """What a stop deep in a long document leaves (measured on
    lifting-optimization, stopped on page 36: 196,856 bytes): whole content
    streams and an object stream of page dictionaries whose parent page tree
    and whose fonts were never written. Still no xref and no trailer."""
    out = bytearray(LUATEX_HEADER)
    for i in range(pages):
        content = zlib.compress(f"BT /F1 10 Tf 72 770 Td (p{i + 1}) Tj ET".encode())
        out += (f"{10 + i} 0 obj\n<< /Filter /FlateDecode /Length {len(content)} >>\n"
                "stream\n").encode() + content + b"\nendstream\nendobj\n"
    offsets, body = [], b""
    for i in range(pages):
        offsets.append(f"{20 + i} {len(body)}")
        body += (f"<< /Type /Page /Contents {10 + i} 0 R /Resources << /Font "
                 f"<< /F1 90 0 R >> >> /MediaBox [0 0 595.276 841.89] "
                 f"/Parent 99 0 R >>\n").encode()
    head = (" ".join(offsets) + "\n").encode()
    packed = zlib.compress(head + body)
    out += (f"5 0 obj\n<< /Type /ObjStm /N {pages} /First {len(head)} "
            f"/Filter /FlateDecode /Length {len(packed)} >>\nstream\n").encode()
    out += packed + b"\nendstream\nendobj\n"
    return bytes(out)


def mupdf_pages(path: Path) -> int:
    """The second, independent reader: PyMuPDF repairs what it can."""
    try:
        with fitz.open(path) as doc:
            return doc.page_count
    except Exception:  # noqa: BLE001 - an unopenable file has no pages
        return 0


def predicate(path: Path) -> str:
    """Run build.sh's own readable_pdf_pages(), extracted verbatim."""
    lines = BUILD.read_text(encoding="utf-8").splitlines()
    start = lines.index("readable_pdf_pages() {")
    end = lines.index("}", start)
    function = "\n".join(lines[start:end + 1])
    proc = subprocess.run(["bash", "-c", function + '\nreadable_pdf_pages "$1"', "_", str(path)],
                          text=True, capture_output=True, timeout=60)
    return proc.stdout.strip()


class Predicate(unittest.TestCase):
    """What counts as evidence: a page a reader can open, not a nonempty file."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="hllpdf4270-pred-")
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def fixture(self, name: str, data: bytes) -> Path:
        path = self.dir / name
        path.write_bytes(data)
        return path

    def test_01_finished_pdfs_are_readable(self):
        for pages in (1, 2):
            with self.subTest(pages=pages):
                path = self.fixture(f"finished-{pages}.pdf", complete_pdf(pages))
                self.assertEqual(mupdf_pages(path), pages, "fixture: MuPDF must agree")
                self.assertEqual(predicate(path), str(pages))

    def test_02_truncated_pdfs_are_not(self):
        for name, data in [("after-first-page", halted_after_first_page()),
                           ("mid-document", halted_mid_document())]:
            with self.subTest(shape=name):
                path = self.fixture(f"{name}.pdf", data)
                self.assertGreater(path.stat().st_size, 0, "fixture: the file is nonempty")
                self.assertEqual(mupdf_pages(path), 0, "fixture: MuPDF finds no page either")
                self.assertEqual(predicate(path), "")

    def test_03_a_page_is_required_not_just_a_trailer(self):
        # Poppler 24.02 refuses a finished zero-page file outright ("Invalid
        # page count 0", no Pages: line); another version may print Pages: 0.
        # Either way it is not a page anyone can diagnose from.
        path = self.fixture("no-pages.pdf", complete_pdf(0))
        self.assertEqual(mupdf_pages(path), 0, "fixture: MuPDF must agree")
        self.assertIn(predicate(path), {"", "0"})

    def test_04_non_pdf_bytes_and_missing_files_are_not_readable(self):
        # v4.26.0's mock engine left exactly this dummy, and cleanup() exported
        # it as "failing PDF preserved": the same defect in miniature.
        self.assertEqual(predicate(self.fixture("dummy.pdf", b"%PDF-1.4\n%%EOF\n")), "")
        self.assertEqual(predicate(self.dir / "absent.pdf"), "")


MOCK_KPSE = """#!/bin/sh
case "$1" in
  -var-value=*) exit 0 ;;
  *.ttf) printf '%s/%s\\n' "$MOCK_FONT_DIR" "$1" ;;
  *) printf '/mock/%s\\n' "$1" ;;
esac
"""
# Unlike v4.26.0's mock, this engine leaves MOCK_PDF behind WHATEVER its exit
# code, as LuaTeX does under -output-directory, and can leave a root aux.
MOCK_LATEX = """#!/bin/sh
out=''
last=''
for arg in "$@"; do
  case "$arg" in -output-directory=*) out=${arg#*=} ;; esac
  last=$arg
done
stem=${last%.tex}
cp "$MOCK_LOG" "$out/$stem.log"
printf 'INPUT %s\\n' "$MOCK_TEX" >"$out/$stem.fls"
printf 'INPUT %s\\n' "$MOCK_PREAMBLE" >>"$out/$stem.fls"
[ -n "${MOCK_AUX:-}" ] && printf '%s\\n' "$MOCK_AUX" >"$out/$stem.aux"
[ -n "${MOCK_PDF:-}" ] && cp "$MOCK_PDF" "$out/$stem.pdf"
exit "$MOCK_RC"
"""


class MockEngine(unittest.TestCase):
    """The three export branches of cleanup(), through the real build.sh."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="hllpdf4270-mock-")
        base = Path(self.tmp.name)
        self.project = base / "project"
        self.project.mkdir()
        bin_dir = base / "bin"
        bin_dir.mkdir()
        for name, body in [("kpsewhich", MOCK_KPSE), ("lualatex", MOCK_LATEX)]:
            (bin_dir / name).write_text(body, encoding="utf-8")
            (bin_dir / name).chmod(0o755)
        tex = self.project / "doc.tex"
        tex.write_text("\\input{preamble.tex}\n\\begin{document}\nשלום.\n\\end{document}\n",
                       encoding="utf-8")
        # The canonical-core marker makes the runtime font inventory mandatory,
        # so every run below fails the recorded-source gate after pass 1 and
        # leaves through cleanup() with the engine's output still in place.
        (self.project / "preamble.tex").write_text(
            "\\def\\hllpdfcoreloaded{1}\n\\documentclass{article}\n", encoding="utf-8")
        self.env = {k: v for k, v in os.environ.items()
                    if k not in {"HEBREW_LATEX_PROJECT_ROOT", "REPRO", "MOCK_PDF", "MOCK_AUX"}}
        self.env.update({
            "PATH": f"{bin_dir}:{os.environ['PATH']}",
            "HEBREW_LATEX_FONT_DIR": str(font_dir()),
            "MOCK_FONT_DIR": str(font_dir()),
            "MOCK_TEX": str(tex),
            "MOCK_PREAMBLE": str(self.project / "preamble.tex"),
        })
        self.failed_pdf = self.project / "doc.failed.pdf"

    def tearDown(self):
        self.tmp.cleanup()

    def build(self, *, pdf: bytes | None, log_text: str, rc: int, aux: str = ""):
        env = dict(self.env, MOCK_RC=str(rc), MOCK_AUX=aux)
        log = Path(self.tmp.name) / "canned.log"
        log.write_text(log_text, encoding="utf-8")
        env["MOCK_LOG"] = str(log)
        if pdf is not None:
            left = Path(self.tmp.name) / "engine-output.pdf"
            left.write_bytes(pdf)
            env["MOCK_PDF"] = str(left)
        proc = subprocess.run(["bash", str(BUILD), str(self.project / "doc.tex")], text=True,
                              capture_output=True, env=env, timeout=300)
        return proc.returncode, proc.stdout + proc.stderr

    def seed_stale_evidence(self):
        # A readable PDF from an earlier failure: exactly what must not survive
        # to impersonate this run.
        self.failed_pdf.write_bytes(complete_pdf(1))

    def assert_in_order(self, output: str, *needles: str):
        positions = []
        for needle in needles:
            self.assertIn(needle, output)
            positions.append(output.index(needle))
        self.assertEqual(positions, sorted(positions), needles)

    def test_05_a_truncated_pdf_is_not_exported_and_stale_evidence_goes(self):
        self.seed_stale_evidence()
        (self.project / "doc.pdf").write_bytes(complete_pdf(1))  # an earlier deliverable
        halted = HALTED_LOG.read_text(encoding="utf-8")
        rc, out = self.build(pdf=halted_after_first_page(), log_text=halted, rc=1,
                             aux="\\relax")
        self.assertEqual(rc, 1, out)
        self.assertFalse(self.failed_pdf.exists(), out)
        self.assertNotIn(PRESERVED, out)
        # v4.26.0 warned about the earlier deliverable here (inside its -s
        # branch); withholding the truncated file must not drop that warning.
        self.assert_in_order(out, "✗ lualatex exited 1 on pass 1",
                             "── full log preserved:", "── aux preserved:", TRUNCATED,
                             "is from an EARLIER run")
        # The log and aux exports are unchanged: this run's own files.
        self.assertEqual((self.project / "doc.failed.log").read_text(encoding="utf-8"), halted)
        self.assertEqual((self.project / "doc.failed.aux").read_text(encoding="utf-8"),
                         "\\relax\n")

    def test_06_a_later_stop_is_not_exported_either(self):
        rc, out = self.build(pdf=halted_mid_document(),
                             log_text=HALTED_LOG.read_text(encoding="utf-8"), rc=1)
        self.assertEqual(rc, 1, out)
        self.assertFalse(self.failed_pdf.exists(), out)
        self.assertIn(TRUNCATED, out)
        self.assertNotIn(PRESERVED, out)

    def test_07_a_finished_pdf_that_fails_a_gate_is_still_exported(self):
        # The BLD-56 case this export exists for: the compile finished and a
        # gate failed. The exported file is the engine's, byte for byte.
        finished = complete_pdf(2)
        rc, out = self.build(pdf=finished, rc=0,
                             log_text="Output written on doc.pdf (2 pages, 900 bytes).\n")
        self.assertEqual(rc, 1, out)
        self.assertIn(PRESERVED, out)
        self.assertIn("(diagnose page numbers from THIS file)", out)
        self.assertNotIn(TRUNCATED, out)
        self.assertEqual(self.failed_pdf.read_bytes(), finished)

    def test_08_nothing_left_keeps_its_own_message(self):
        for label, pdf in [("zero bytes", b""), ("no file", None)]:
            with self.subTest(engine_left=label):
                self.seed_stale_evidence()
                rc, out = self.build(pdf=pdf, log_text=HALTED_LOG.read_text(encoding="utf-8"),
                                     rc=1)
                self.assertEqual(rc, 1, out)
                self.assertIn(NOTHING, out)
                self.assertNotIn(TRUNCATED, out)
                self.assertFalse(self.failed_pdf.exists(), out)


class Documentation(unittest.TestCase):
    def test_09_the_rule_travels_with_the_package(self):
        recovery = (ROOT / "references" / "output-recovery.md").read_text(encoding="utf-8")
        self.assertIn("pdfinfo", recovery)
        self.assertIn("trailer", recovery)
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("*.failed.pdf", skill)


if __name__ == "__main__":
    unittest.main(verbosity=2)
