#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Original project code; scope and terms: ../LICENSING.md.
# Additional output permission: ../LICENSES/Generated-Output-Permission.txt.
"""Lightweight canonical build-contract definitions.

This module deliberately has no third-party imports.  Build configuration must
be parseable before font discovery, PDF tooling or LuaLaTeX starts.  Checkers
that consume these values import them from here so the package has one source
of truth for supported content profiles, paper sizes and SECTION_MACROS syntax.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

sys.dont_write_bytecode = True

OUTPUT_PERMISSION_PATH = "LICENSES/Generated-Output-Permission.txt"
OUTPUT_PERMISSION_SHA256 = "db332369fe4fcb4a6d0f84499cc1c49a0b94f1ceaf063c884a84a36403dee5e1"
GENERATED_OUTPUT_PERMISSION_NAME = "GENERATED-OUTPUT-PERMISSION.txt"


def read_output_permission(root: Path) -> bytes:
    """Retain the approved permission before packaging or project creation."""
    try:
        content = (root / OUTPUT_PERMISSION_PATH).read_bytes()
    except OSError as exc:
        raise ValueError(f"generated output permission missing: {OUTPUT_PERMISSION_PATH}") from exc
    if hashlib.sha256(content).hexdigest() != OUTPUT_PERMISSION_SHA256:
        raise ValueError(f"generated output permission differs: {OUTPUT_PERMISSION_PATH}")
    return content

CONTENT_PROFILES = (
    "generic",
    "study-guide",
    "report",
    "exam",
    "formula-sheet",
    "review-sheet",
)

PAPERS_MM = {
    "a3": (297.0, 420.0),
    "a4": (210.0, 297.0),
    "a5": (148.0, 210.0),
    "letter": (215.9, 279.4),
    "legal": (215.9, 355.6),
}

# These contracts describe printed folios, independently of the document's
# language or theme. Custom geometry is deliberately an explicit manual-QA
# handoff; it must never be reported as verified numbering.
FOLIO_LAYOUTS = ("center", "left", "right", "outer", "inner", "none", "custom")
FOLIO_BANDS = ("footer", "header")
CAPTION_LABEL_WEIGHTS = ("bold", "normal")
INDEX_PROCESSORS = ("none", "makeindex")


def validate_index_style(value: str) -> str:
    """Validate a literal project-relative style path, without resolving it."""
    if not value:
        return value
    if (value.startswith("/") or "\\" in value
            or any(ord(char) < 32 or ord(char) == 127 for char in value)
            or any(part in {"", ".", ".."} for part in value.split("/"))
            or not value.endswith(".ist")):
        raise ValueError("INDEX_STYLE must be a project-relative .ist path without traversal")
    return value


def _index_processor_has_warnings(transcript: str) -> bool:
    """Match processor diagnostics/summaries rather than quoted filenames."""
    return bool(re.search(
        r"^##[ \t]+Warning\b|\bdone[ \t]+\(\d+ lines written,[ \t]+[1-9]\d* warnings?\)\.?[ \t]*$",
        transcript, re.MULTILINE | re.IGNORECASE))


def run_managed_index(base: Path, project_root: Path, style: str = "") -> tuple[int, int]:
    """Process this build's single index; exit zero alone is insufficient."""
    base = base.resolve()
    idx, ind, ilg = (Path(str(base) + suffix) for suffix in (".idx", ".ind", ".ilg"))
    if not idx.is_file():
        raise ValueError("managed index: no current .idx was produced; declare the index explicitly")
    text = idx.read_text(encoding="utf-8")
    entry_count = sum(bool(re.match(r"^\\indexentry\s*\{", line))
                      for line in text.splitlines())
    if entry_count == 0:
        raise ValueError("managed index: no index entries; refusing an empty index")
    style = validate_index_style(style)
    # TeX's restrictive openout_any rejects absolute output paths. Work inside
    # the private build directory and keep every output name relative.
    command = ["makeindex", "-o", ind.name, "-t", ilg.name]
    style_path = None
    style_hash = None
    if style:
        root = project_root.resolve()
        style_path = (root / style).resolve(strict=True)
        if not style_path.is_relative_to(root) or not style_path.is_file():
            raise ValueError("managed index: INDEX_STYLE escapes the project or is not a file")
        style_hash = hashlib.sha256(style_path.read_bytes()).digest()
        command.extend(["-s", str(style_path)])
    command.append(idx.name)
    # Neither a previous .ind nor a forged previous transcript can satisfy this run.
    for output in (ind, ilg):
        output.unlink(missing_ok=True)
    result = subprocess.run(command, cwd=base.parent, capture_output=True, text=True)
    if result.returncode != 0:
        raise ValueError(f"managed index: makeindex exited {result.returncode}: "
                         + (result.stderr or result.stdout).strip())
    if style_path and hashlib.sha256(style_path.read_bytes()).digest() != style_hash:
        raise ValueError("managed index: style changed during processing")
    transcript = ilg.read_text(encoding="utf-8", errors="replace") if ilg.is_file() else ""
    counts = re.findall(r"\((\d+) entries accepted, (\d+) rejected\)", transcript)
    if len(counts) != 1:
        raise ValueError("managed index: missing or ambiguous processor entry counts")
    accepted, rejected = map(int, counts[0])
    if rejected or accepted != entry_count:
        raise ValueError(f"managed index: {accepted}/{entry_count} accepted, {rejected} rejected")
    if _index_processor_has_warnings(transcript):
        raise ValueError("managed index: processor warnings require repair (including incomplete ranges)")
    if not ind.is_file() or not ind.read_text(encoding="utf-8").strip():
        raise ValueError("managed index: processor produced no readable index")
    return accepted, rejected


def retain_index_evidence(base: Path, project_root: Path, style: str, destination: Path) -> None:
    """Validate a stable snapshot, then publish one complete private evidence set.

    The destination must be new. Like the managed build, this is a trusted
    single-writer workflow rather than a hostile filesystem concurrency boundary.
    """
    import os
    import shutil
    import stat
    import tempfile

    base = base.resolve()
    if not destination.is_absolute():
        raise ValueError("index evidence directory must be absolute")
    if any(part.is_symlink() for part in (destination, *destination.parents)):
        raise ValueError("index evidence directory must not have symlink ancestors")
    if destination.exists():
        raise ValueError("index evidence destination already exists; choose a new directory")

    sources, payloads = {}, {}
    for suffix in (".idx", ".ind", ".ilg", ".fls", ".aux", ".log", ".pdf"):
        source = Path(str(base) + suffix)
        if (not source.is_file() or source.is_symlink()
                or not stat.S_ISREG(source.stat().st_mode)):
            raise ValueError(f"index evidence artifact missing or not a regular file: {source.name}")
        sources[source.name] = source
        payloads[source.name] = source.read_bytes()

    entry_count = sum(bool(re.match(r"^\\indexentry\s*\{", line))
                      for line in payloads[base.name + ".idx"].decode("utf-8").splitlines())
    transcript = payloads[base.name + ".ilg"].decode("utf-8")
    counts = re.findall(r"\((\d+) entries accepted, (\d+) rejected\)", transcript)
    if entry_count == 0 or len(counts) != 1:
        raise ValueError("index evidence: missing or ambiguous processor entry counts")
    accepted, rejected = map(int, counts[0])
    if rejected or accepted != entry_count:
        raise ValueError(f"index evidence: {accepted}/{entry_count} accepted, {rejected} rejected")
    if _index_processor_has_warnings(transcript):
        raise ValueError("index evidence: processor warnings require repair")
    if not payloads[base.name + ".ind"].decode("utf-8").strip():
        raise ValueError("index evidence: processor produced no readable index")

    fls = payloads[base.name + ".fls"].decode("utf-8").splitlines()
    pwd = next((Path(line[4:]) for line in fls if line.startswith("PWD ")), base.parent)
    inputs = {(pwd / line[6:]).resolve() for line in fls if line.startswith("INPUT ")}
    managed_ind = Path(str(base) + ".ind")
    if managed_ind not in inputs:
        raise ValueError("index evidence: current managed .ind was not consumed")

    style = validate_index_style(style)
    style_path, style_payload = None, None
    project_root = project_root.resolve()
    if style:
        style_path = (project_root / style).resolve(strict=True)
        if not style_path.is_relative_to(project_root) or not style_path.is_file():
            raise ValueError("index evidence: INDEX_STYLE escapes the project or is not a file")
        style_payload = style_path.read_bytes()

    # pdfinfo is already mandatory for the managed build. Keep PDF tooling out
    # of cheap configuration imports and refuse an unreadable/zero-page carrier.
    pdf_check = subprocess.run(["pdfinfo", str(sources[base.name + ".pdf"])],
                               capture_output=True, text=True,
                               env={**os.environ, "LC_ALL": "C"})
    pages = re.search(r"^Pages:\s+([1-9]\d*)\s*$", pdf_check.stdout, re.MULTILINE)
    if pdf_check.returncode or pages is None:
        raise ValueError("index evidence: PDF is unreadable or has no pages")

    evidence = {"schema": 1, "processor": "makeindex", "style": style,
                "scope": "retained managed processor artifacts; build success and visual/semantic review are separate",
                "artifacts": {}, "accepted": accepted, "rejected": rejected,
                "managed_ind_original_path": str(managed_ind), "managed_ind_consumed": True,
                "pdf_sha256": hashlib.sha256(payloads[base.name + ".pdf"]).hexdigest(),
                "pdf_pages": int(pages[1])}
    for suffix in (".idx", ".ind", ".ilg", ".fls", ".aux", ".log"):
        name = base.name + suffix
        evidence["artifacts"][name] = hashlib.sha256(payloads[name]).hexdigest()
    if style:
        evidence["style_sha256"] = hashlib.sha256(style_payload).hexdigest()

    def verify_snapshot() -> None:
        for name, source in sources.items():
            if source.is_symlink() or source.read_bytes() != payloads[name]:
                raise ValueError(f"index evidence artifact changed during export: {name}")
        if style_path is not None and (
                (project_root / style).resolve(strict=True) != style_path
                or style_path.read_bytes() != style_payload):
            raise ValueError("index evidence style changed during export")

    verify_snapshot()
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{destination.name}.tmp.", dir=destination.parent))
    try:
        for name in evidence["artifacts"]:
            with (staging / name).open("wb") as output:
                output.write(payloads[name])
                output.flush()
                os.fsync(output.fileno())
        with (staging / "index-evidence.json").open("w", encoding="utf-8") as output:
            output.write(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n")
            output.flush()
            os.fsync(output.fileno())
        verify_snapshot()
        if destination.exists() or destination.is_symlink():
            raise ValueError("index evidence destination already exists; choose a new directory")
        if any(part.is_symlink() for part in destination.parents):
            raise ValueError("index evidence directory must not have symlink ancestors")
        os.rename(staging, destination)
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def parse_rgb_hex(value: str) -> int:
    """An explicit PDF text color, encoded as exactly six RGB hex digits."""
    if not re.fullmatch(r"[0-9A-Fa-f]{6}", value):
        raise ValueError("caption color must be exactly six hexadecimal RGB digits (RRGGBB)")
    return int(value, 16)


def normalize_section_macros(spec: str) -> tuple[str, ...]:
    """Parse comma/space-separated TeX command names, without backslashes."""
    names: list[str] = []
    for raw in re.split(r"[\s,]+", spec.strip()):
        if not raw:
            continue
        name = raw.lstrip("\\")
        if not re.fullmatch(r"[A-Za-z@]+", name):
            raise ValueError(f"invalid section macro name: {raw!r}")
        if name not in names:
            names.append(name)
    return tuple(names)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run the explicit managed single-index stage")
    parser.add_argument("--index-base", required=True, type=Path)
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--index-style", default="")
    parser.add_argument("--index-evidence-dir", type=Path)
    args = parser.parse_args()
    try:
        if args.index_evidence_dir:
            retain_index_evidence(args.index_base, args.project_root, args.index_style,
                                  args.index_evidence_dir)
            print(f"✓ index evidence retained: {args.index_evidence_dir}")
            sys.exit(0)
        accepted, rejected = run_managed_index(args.index_base, args.project_root, args.index_style)
    except (ValueError, OSError, UnicodeError) as exc:
        print(f"✗ {exc}", file=sys.stderr)
        sys.exit(1)
    print(f"✓ managed index: {accepted} accepted, {rejected} rejected")
