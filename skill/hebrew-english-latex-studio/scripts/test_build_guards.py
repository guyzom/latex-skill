#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Original project code; scope and terms: ../LICENSING.md.
"""Adversarial process tests for build.sh trust and path guards."""

from __future__ import annotations

import argparse
from contextlib import nullcontext
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest import mock


HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
BUILD = HERE / "build.sh"
sys.dont_write_bytecode = True
from font_paths import font_dir
from build_contract import retain_index_evidence, run_managed_index, validate_index_style
FONTS = font_dir()


def run_invalid_project_root(project: Path) -> None:
    project.mkdir()
    tex = project / "doc.tex"
    tex.write_text("\\documentclass{article}\n", encoding="utf-8")
    env = os.environ.copy()
    env["HEBREW_LATEX_PROJECT_ROOT"] = str(project / "absent")
    proc = subprocess.run(
        ["bash", str(BUILD), str(tex)],
        text=True,
        capture_output=True,
        env=env,
    )
    output = proc.stdout + proc.stderr
    assert proc.returncode == 2, output
    assert "HEBREW_LATEX_PROJECT_ROOT is not a directory" in output, output


def run_late_pass_recorder_escape(project: Path) -> None:
    project.mkdir()
    tex = project / "doc.tex"
    tex.write_text(
        "\\documentclass{article}\n"
        "\\begin{document}\n"
        "שלום\n"
        "\\end{document}\n",
        encoding="utf-8",
    )
    mock_bin = project / "bin"
    mock_bin.mkdir()
    state = project / "pass-count"
    dummy_pdf = project / "dummy.pdf"
    dummy_pdf.write_bytes(b"%PDF-1.4\n%%EOF\n")

    kpse = mock_bin / "kpsewhich"
    kpse.write_text(
        "#!/bin/sh\n"
        "case \"$1\" in\n"
        "  -var-value=*) exit 0 ;;\n"
        "  *.ttf) printf '%s/%s\\n' \"$MOCK_FONT_DIR\" \"$1\" ;;\n"
        "  *) printf '/mock/%s\\n' \"$1\" ;;\n"
        "esac\n",
        encoding="utf-8",
    )
    latex = mock_bin / "lualatex"
    latex.write_text(
        "#!/bin/sh\n"
        "out=''\n"
        "last=''\n"
        "for arg in \"$@\"; do\n"
        "  case \"$arg\" in -output-directory=*) out=${arg#*=} ;; esac\n"
        "  last=$arg\n"
        "done\n"
        "stem=${last%.tex}\n"
        "n=0\n"
        "[ -f \"$MOCK_STATE\" ] && n=$(sed -n '1p' \"$MOCK_STATE\")\n"
        "n=$((n + 1))\n"
        "printf '%s\\n' \"$n\" >\"$MOCK_STATE\"\n"
        "cp \"$MOCK_PDF\" \"$out/$stem.pdf\"\n"
        ": >\"$out/$stem.log\"\n"
        "printf 'INPUT %s\\n' \"$MOCK_TEX\" >\"$out/$stem.fls\"\n"
        "if [ \"$n\" -ge 2 ]; then\n"
        "  printf 'INPUT /etc/passwd\\n' >>\"$out/$stem.fls\"\n"
        "fi\n"
        "exit 0\n",
        encoding="utf-8",
    )
    kpse.chmod(0o755)
    latex.chmod(0o755)

    env = os.environ.copy()
    # v4.0.1: HERMETIC. This case drives build.sh against a mock TeX in a temp dir
    # and asserts on the DEFAULT project root (the document's own directory). It
    # inherited HEBREW_LATEX_PROJECT_ROOT from the caller, so once test_all.sh
    # declared the skill root — which the tests/ fixtures need — this test silently
    # measured a different configuration than the one it asserts about, and failed
    # only inside the harness while passing standalone. A process test must pin the
    # environment it is testing, never borrow the ambient one.
    env.pop("HEBREW_LATEX_PROJECT_ROOT", None)
    env.update(
        {
            "PATH": f"{mock_bin}:{env['PATH']}",
            "HEBREW_LATEX_FONT_DIR": str(FONTS),
            "MOCK_FONT_DIR": str(FONTS),
            "MOCK_PDF": str(dummy_pdf),
            "MOCK_STATE": str(state),
            "MOCK_TEX": str(tex),
        }
    )
    proc = subprocess.run(
        ["bash", str(BUILD), str(tex)],
        text=True,
        capture_output=True,
        env=env,
    )
    output = proc.stdout + proc.stderr
    assert proc.returncode == 1, output
    assert "pass 2" in output, output
    # The recorder guard reports canonical paths: macOS resolves /etc through
    # /private/etc; Linux keeps /etc. The same external input must be rejected.
    rejected_input = Path("/etc/passwd").resolve()
    assert f"untrusted external TeX input: {rejected_input}" in output, output
    assert state.read_text(encoding="utf-8").strip() == "2", output



def run_prior_output_dependency(project: Path) -> None:
    project.mkdir()
    tex = project / "doc.tex"
    tex.write_text(
        "\\documentclass{article}\n"
        "\\usepackage{graphicx}\n"
        "\\begin{document}\n"
        "\\includegraphics{doc.pdf}\n"
        "\\end{document}\n",
        encoding="utf-8",
    )
    prior = project / "doc.pdf"
    prior.write_bytes(b"%PDF-1.4\nprior-output\n%%EOF\n")
    mock_bin = project / "bin"
    mock_bin.mkdir()
    dummy_pdf = project / "dummy.pdf"
    dummy_pdf.write_bytes(b"%PDF-1.4\n%%EOF\n")

    kpse = mock_bin / "kpsewhich"
    kpse.write_text(
        "#!/bin/sh\n"
        "case \"$1\" in\n"
        "  -var-value=*) exit 0 ;;\n"
        "  *.ttf) printf '%s/%s\\n' \"$MOCK_FONT_DIR\" \"$1\" ;;\n"
        "  *) printf '/mock/%s\\n' \"$1\" ;;\n"
        "esac\n",
        encoding="utf-8",
    )
    latex = mock_bin / "lualatex"
    latex.write_text(
        "#!/bin/sh\n"
        "out=''\nlast=''\n"
        "for arg in \"$@\"; do\n"
        "  case \"$arg\" in -output-directory=*) out=${arg#*=} ;; esac\n"
        "  last=$arg\n"
        "done\n"
        "stem=${last%.tex}\n"
        "cp \"$MOCK_PDF\" \"$out/$stem.pdf\"\n"
        ": >\"$out/$stem.log\"\n"
        "printf 'INPUT %s\\n' \"$MOCK_TEX\" >\"$out/$stem.fls\"\n"
        "printf 'INPUT %s\\n' \"$MOCK_PRIOR\" >>\"$out/$stem.fls\"\n"
        "exit 0\n",
        encoding="utf-8",
    )
    kpse.chmod(0o755)
    latex.chmod(0o755)

    env = os.environ.copy()
    env.pop("HEBREW_LATEX_PROJECT_ROOT", None)
    env.update(
        {
            "PATH": f"{mock_bin}:{env['PATH']}",
            "HEBREW_LATEX_FONT_DIR": str(FONTS),
            "MOCK_FONT_DIR": str(FONTS),
            "MOCK_PDF": str(dummy_pdf),
            "MOCK_TEX": str(tex),
            "MOCK_PRIOR": str(prior),
        }
    )
    proc = subprocess.run(
        ["bash", str(BUILD), str(tex)],
        text=True, capture_output=True, env=env,
    )
    output = proc.stdout + proc.stderr
    assert proc.returncode == 1, output
    assert f"forbidden prior-build input: {prior}" in output, output
    assert prior.read_bytes() == b"%PDF-1.4\nprior-output\n%%EOF\n", (
        "failed build overwrote last good output"
    )



def run_project_input_mutation_blocks_convergence(project: Path) -> None:
    project.mkdir()
    tex = project / "doc.tex"
    tex.write_text(
        "\\documentclass{article}\n\\begin{document}\nשלום\n\\end{document}\n",
        encoding="utf-8",
    )
    mock_bin = project / "bin"
    mock_bin.mkdir()
    state = project / "pass-count"
    dummy_pdf = project / "dummy.pdf"
    dummy_pdf.write_bytes(b"%PDF-1.4\n%%EOF\n")

    kpse = mock_bin / "kpsewhich"
    kpse.write_text(
        "#!/bin/sh\n"
        "case \"$1\" in\n"
        "  -var-value=*) exit 0 ;;\n"
        "  *.ttf) printf '%s/%s\\n' \"$MOCK_FONT_DIR\" \"$1\" ;;\n"
        "  *) printf '/mock/%s\\n' \"$1\" ;;\n"
        "esac\n",
        encoding="utf-8",
    )
    latex = mock_bin / "lualatex"
    latex.write_text(
        "#!/bin/sh\n"
        "out=''\nlast=''\n"
        "for arg in \"$@\"; do\n"
        "  case \"$arg\" in -output-directory=*) out=${arg#*=} ;; esac\n"
        "  last=$arg\n"
        "done\n"
        "stem=${last%.tex}\n"
        "n=0\n"
        "[ -f \"$MOCK_STATE\" ] && n=$(sed -n '1p' \"$MOCK_STATE\")\n"
        "n=$((n + 1))\n"
        "printf '%s\\n' \"$n\" >\"$MOCK_STATE\"\n"
        "cp \"$MOCK_PDF\" \"$out/$stem.pdf\"\n"
        ": >\"$out/$stem.log\"\n"
        "printf 'INPUT %s\\n' \"$MOCK_TEX\" >\"$out/$stem.fls\"\n"
        "printf '%% pass %s\\n' \"$n\" >>\"$MOCK_TEX\"\n"
        "exit 0\n",
        encoding="utf-8",
    )
    kpse.chmod(0o755)
    latex.chmod(0o755)

    env = os.environ.copy()
    env.pop("HEBREW_LATEX_PROJECT_ROOT", None)
    env.update(
        {
            "PATH": f"{mock_bin}:{env['PATH']}",
            "HEBREW_LATEX_FONT_DIR": str(FONTS),
            "MOCK_FONT_DIR": str(FONTS),
            "MOCK_PDF": str(dummy_pdf),
            "MOCK_STATE": str(state),
            "MOCK_TEX": str(tex),
        }
    )
    proc = subprocess.run(
        ["bash", str(BUILD), str(tex)],
        text=True, capture_output=True, env=env,
    )
    output = proc.stdout + proc.stderr
    assert proc.returncode == 1, output
    assert "NOT CONVERGED after 5 passes" in output, output
    assert state.read_text(encoding="utf-8").strip() == "5", output
    assert not (project / "doc.pdf").exists(), "mutating-source build published a PDF"


def run_invalid_build_config(project: Path) -> None:
    project.mkdir()
    tex = project / "doc.tex"
    tex.write_text("\\documentclass{article}\n", encoding="utf-8")
    cases = [
        ({"CONTENT_PROFILE": "exma"}, "CONTENT_PROFILE"),
        ({"EXPECTED_PAPER": "tabloid"}, "EXPECTED_PAPER"),
        ({"EXPECTED_PAPER": "A4"}, "EXPECTED_PAPER"),
        ({"SECTION_MACROS": "fssec,bad-name"}, "SECTION_MACROS"),
        ({"REPRO": "yes"}, "REPRO"),
        ({"MAX_CROSS_PAGE_DESTINATIONS": "-1"}, "MAX_CROSS_PAGE_DESTINATIONS"),
        ({"SOURCE_DATE_EPOCH": "not-an-epoch"}, "SOURCE_DATE_EPOCH"),
        ({"INDEX_PROCESSOR": "automatic"}, "INDEX_PROCESSOR"),
        ({"INDEX_PROCESSOR": "none", "INDEX_STYLE": "index.ist"}, "INDEX_STYLE"),
        ({"INDEX_PROCESSOR": "makeindex", "INDEX_STYLE": "../index.ist"}, "INDEX_STYLE"),
    ]
    for overrides, marker in cases:
        env = os.environ.copy()
        env["HEBREW_LATEX_FONT_DIR"] = str(FONTS)
        env.pop("HEBREW_LATEX_PROJECT_ROOT", None)
        for key in ["CONTENT_PROFILE", "EXPECTED_PAPER", "SECTION_MACROS",
                    "REPRO", "MAX_CROSS_PAGE_DESTINATIONS", "SOURCE_DATE_EPOCH",
                    "INDEX_PROCESSOR", "INDEX_STYLE"]:
            env.pop(key, None)
        env.update(overrides)
        proc = subprocess.run(
            ["bash", str(BUILD), str(tex)],
            text=True, capture_output=True, env=env,
        )
        output = proc.stdout + proc.stderr
        assert proc.returncode == 2, (overrides, output)
        assert marker in output, (overrides, output)
        assert not (project / "doc.pdf").exists(), (overrides, output)


def run_index_preflight(project: Path) -> None:
    """Style spelling and ownership fail before fonts or the engine are used."""
    project.mkdir()
    for value in ("", "index.ist", "styles/version.2 local.ist"):
        assert validate_index_style(value) == value
    for value in ("/absolute.ist", "../index.ist", "./index.ist", "styles/../index.ist",
                  "styles//index.ist", "styles/", "index.tex", "style\\index.ist",
                  "index\n.ist", "index\x00.ist", "index\x7f.ist"):
        try:
            validate_index_style(value)
        except ValueError as exc:
            assert "INDEX_STYLE" in str(exc), (value, exc)
        else:
            raise AssertionError(f"unsafe index style accepted: {value!r}")

    valid = subprocess.run([sys.executable, str(HERE / "validate_build_config.py"),
                            "--index-processor", "makeindex",
                            "--index-style", "styles/version.2 local.ist"],
                           capture_output=True, text=True)
    assert valid.returncode == 0, valid.stdout + valid.stderr
    tex = project / "doc.tex"
    tex.write_text("\\documentclass{article}\n", encoding="utf-8")
    outside = project.parent / "outside.ist"
    outside.write_text("% outside style\n", encoding="utf-8")
    (project / "outside-link.ist").symlink_to(outside)
    (project / "directory.ist").mkdir()
    for style in ("absent.ist", "outside-link.ist", "directory.ist"):
        env = os.environ.copy()
        env.pop("HEBREW_LATEX_PROJECT_ROOT", None)
        # A failure that reaches font discovery is a different failure and must
        # not satisfy this preflight control.
        env.update(INDEX_PROCESSOR="makeindex", INDEX_STYLE=style,
                   HEBREW_LATEX_FONT_DIR=str(project / "absent-fonts"))
        result = subprocess.run(["bash", str(BUILD), str(tex)], env=env,
                                capture_output=True, text=True)
        output = result.stdout + result.stderr
        assert result.returncode == 2, (style, output)
        assert "INDEX_STYLE must exist inside the declared project root" in output, output
        assert "▶ pass" not in output and "absent-fonts" not in output, output


def run_managed_index_controls(project: Path) -> None:
    """Exercise the real processor's zero-exit rejections and exact job stem."""
    project.mkdir()
    base = project / "part.2 sample"
    idx = Path(str(base) + ".idx")
    ind = Path(str(base) + ".ind")
    ilg = Path(str(base) + ".ilg")
    idx.write_text("\\indexentry{Alpha}{1}\n\\indexentry{Beta}{12}\n", encoding="utf-8")
    assert run_managed_index(base, project) == (2, 0)
    rendered = ind.read_text(encoding="utf-8")
    assert "Alpha" in rendered and "Beta" in rendered and "12" in rendered, rendered
    assert "(2 entries accepted, 0 rejected)" in ilg.read_text(), ilg.read_text()
    assert not (project / "part.ind").exists(), "dot/space job stem was truncated"
    cli = subprocess.run([sys.executable, str(HERE / "build_contract.py"),
                          "--index-base", str(base), "--project-root", str(project)],
                         capture_output=True, text=True)
    assert cli.returncode == 0 and "2 accepted, 0 rejected" in cli.stdout, cli.stdout + cli.stderr

    warning_name = project / "Warning.2 sample"
    warning_style = project / "Warning.2 local.ist"
    Path(str(warning_name) + ".idx").write_text("\\indexentry{Alpha}{1}\n")
    warning_style.write_text("headings_flag 0\n")
    assert run_managed_index(warning_name, project, warning_style.name) == (1, 0)
    assert "0 warnings" in Path(str(warning_name) + ".ilg").read_text()

    idx.write_text("\\indexentry{Malformed}{}\n" * 42, encoding="utf-8")
    raw = subprocess.run(["makeindex", "-o", ind.name, "-t", ilg.name, idx.name],
                         cwd=base.parent, capture_output=True, text=True)
    assert raw.returncode == 0, raw.stdout + raw.stderr
    assert "(0 entries accepted, 42 rejected)" in ilg.read_text(), ilg.read_text()
    # A superficially successful prior output/transcript must be removed before
    # the new processor invocation, not used to mask its rejected entries.
    ind.write_text("\\begin{theindex}\\item Forged, 1\\end{theindex}\n")
    ilg.write_text("done (42 entries accepted, 0 rejected).\n")
    try:
        run_managed_index(base, project)
    except ValueError as exc:
        assert "0/42 accepted, 42 rejected" in str(exc), exc
    else:
        raise AssertionError("makeindex's zero-exit 42-entry rejection was accepted")
    assert not ind.exists() or "Forged" not in ind.read_text(), (
        "stale successful index survived a rejected processor run")

    idx.write_text("\\indexentry{Alpha|(}{1}\n", encoding="utf-8")
    raw = subprocess.run(["makeindex", "-o", ind.name, "-t", ilg.name, idx.name],
                         cwd=base.parent, capture_output=True, text=True)
    assert raw.returncode == 0, raw.stdout + raw.stderr
    transcript = ilg.read_text()
    assert "(1 entries accepted, 0 rejected)" in transcript and "1 warning" in transcript, transcript
    try:
        run_managed_index(base, project)
    except ValueError as exc:
        assert "processor warnings require repair" in str(exc), exc
    else:
        raise AssertionError("unclosed index range with exit zero and valid counts was accepted")

    idx.write_text("", encoding="utf-8")
    for missing, marker in ((False, "no index entries"), (True, "no current .idx")):
        if missing:
            idx.unlink()
        with mock.patch("build_contract.subprocess.run") as processor:
            try:
                run_managed_index(base, project)
            except ValueError as exc:
                assert marker in str(exc), exc
            else:
                raise AssertionError(f"{marker} was accepted")
            processor.assert_not_called()


def run_index_output_controls(project: Path) -> None:
    """Reject stale, absent, ambiguous and incomplete output despite exit zero."""
    project.mkdir()
    base = project / "doc"
    idx, ind, ilg = (Path(str(base) + suffix) for suffix in (".idx", ".ind", ".ilg"))
    idx.write_text("\\indexentry{Alpha}{1}\n\\indexentry{Beta}{2}\n")
    cases = (
        (None, None, 0, "missing or ambiguous processor entry counts"),
        ("(2 entries accepted, 0 rejected)", None, 0, "no readable index"),
        ("(2 entries accepted, 0 rejected)", " \n", 0, "no readable index"),
        ("(1 entries accepted, 0 rejected)", "current index", 0, "1/2 accepted"),
        ("(2 entries accepted, 1 rejected)", "current index", 0, "1 rejected"),
        ("(2 entries accepted, 0 rejected)\n(2 entries accepted, 0 rejected)",
         "current index", 0, "missing or ambiguous processor entry counts"),
        ("(2 entries accepted, 0 rejected)\ndone (5 lines written, 2 warnings).",
         "current index", 0, "processor warnings require repair"),
        (None, None, 7, "makeindex exited 7"),
    )
    for transcript, contents, status, marker in cases:
        ind.write_text("stale index must not satisfy a current invocation\n")
        ilg.write_text("(2 entries accepted, 0 rejected)\n")

        def process(command, **kwargs):
            assert not ind.exists() and not ilg.exists(), "stale index outputs were retained"
            assert (Path(kwargs["cwd"]) / command[-1]).resolve() == idx.resolve(), command
            assert kwargs["cwd"] == base.parent.resolve(), kwargs
            if transcript is not None:
                ilg.write_text(transcript)
            if contents is not None:
                ind.write_text(contents)
            return subprocess.CompletedProcess(command, status, "", "processor diagnostic")

        with mock.patch("build_contract.subprocess.run", side_effect=process) as processor:
            try:
                run_managed_index(base, project)
            except ValueError as exc:
                assert marker in str(exc), (marker, exc)
            else:
                raise AssertionError(f"incomplete current output accepted: {marker}")
            processor.assert_called_once()

    style = project / "index.ist"
    style.write_text("headings_flag 1\n")

    def mutate_style(command, **kwargs):
        style.write_text("headings_flag 0\n")
        ilg.write_text("(2 entries accepted, 0 rejected)")
        ind.write_text("current output")
        return subprocess.CompletedProcess(command, 0, "", "")

    with mock.patch("build_contract.subprocess.run", side_effect=mutate_style):
        try:
            run_managed_index(base, project, "index.ist")
        except ValueError as exc:
            assert "style changed during processing" in str(exc), exc
        else:
            raise AssertionError("mutating index style was accepted")


def run_generated_index_recorder(project: Path) -> None:
    """Only the exact managed .ind gains TeX scanning; outside inputs stay denied."""
    project.mkdir()
    src, build, outside = (project / name for name in ("source", "build", "outside"))
    for directory in (src, build, outside):
        directory.mkdir()
    tex = src / "doc.tex"
    tex.write_text("\\documentclass{article}\n")
    ind = build / "part.2 sample.ind"
    # This finding compiles as visibly broken text. The generated extension
    # must participate in the actual source gates, not only a path inventory.
    ind.write_text("\\begin{theindex}\n\\item $frac{1}{2}$, 1\n\\end{theindex}\n")
    fls = build / "doc.fls"
    fls.write_text(f"PWD {src}\nINPUT {tex}\nINPUT {ind}\nINPUT {ind}\n")
    command = [sys.executable, str(HERE / "collect_fls_sources.py"), str(fls),
               "--project-root", str(src), "--allow-root", str(build),
               "--generated-tex-input", str(ind)]
    for mode in ("all", "tex", "project-all"):
        result = subprocess.run(command + ["--mode", mode], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        paths = result.stdout.splitlines()
        assert paths.count(str(tex)) == 1, paths
        assert paths.count(str(ind)) == (0 if mode == "project-all" else 1), paths
    result = subprocess.run(command + ["--mode", "tex"], capture_output=True, text=True)
    gate = subprocess.run([sys.executable, str(HERE / "check_source_hazards.py"),
                           *result.stdout.splitlines()], capture_output=True, text=True)
    assert gate.returncode == 1 and "BARE-LATEX-COMMAND" in gate.stdout, gate.stdout + gate.stderr

    unapproved = outside / "unapproved.ind"
    unapproved.write_text("\\begin{theindex}\\end{theindex}\n")
    fls.write_text(f"PWD {src}\nINPUT {tex}\nINPUT {ind}\nINPUT {unapproved}\n")
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 1, result.stdout + result.stderr
    assert f"untrusted external TeX input: {unapproved}" in result.stderr, result.stderr
    result = subprocess.run(command + ["--forbid-input", str(ind)], capture_output=True, text=True)
    assert result.returncode == 1 and f"forbidden prior-build input: {ind}" in result.stderr, result.stderr
    for invalid in (tex, unapproved):
        invalid_command = command[:-1] + [str(invalid)]
        result = subprocess.run(invalid_command, capture_output=True, text=True)
        assert result.returncode == 2, result.stdout + result.stderr
        assert "exact .ind inside an allowed build root" in result.stderr, result.stderr


def run_index_evidence_controls(project: Path) -> None:
    """Publish a complete new evidence set or leave every prior set untouched."""
    project = project.resolve()
    project.mkdir()
    base = project / "Warning.2 review"
    idx = Path(str(base) + ".idx")
    idx.write_text("\\indexentry{Alpha}{1}\n\\indexentry{Beta}{2}\n")
    assert run_managed_index(base, project) == (2, 0)
    Path(str(base) + ".aux").write_text("% synthetic auxiliary carrier\n")
    Path(str(base) + ".log").write_text("synthetic engine log; not a LaTeX build\n")
    Path(str(base) + ".fls").write_text(f"PWD {project}\nINPUT {base.name}.ind\n")
    # A real readable one-page PDF carrier, assembled without an engine. This
    # tests export validation and hashes, not typography or visual approval.
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, body in enumerate((b"<< /Type /Catalog /Pages 2 0 R >>",
                                   b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
                                   b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] >>"), 1):
        offsets.append(len(pdf))
        pdf.extend(f"{number} 0 obj\n".encode() + body + b"\nendobj\n")
    xref = len(pdf)
    pdf.extend(b"xref\n0 4\n0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode())
    pdf.extend(f"trailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    Path(str(base) + ".pdf").write_bytes(pdf)
    style = project / "index.ist"
    style.write_text("% synthetic style carrier\n")
    sources = {Path(str(base) + suffix): Path(str(base) + suffix).read_bytes()
               for suffix in (".idx", ".ind", ".ilg", ".fls", ".aux", ".log", ".pdf")}
    sources[style] = style.read_bytes()

    def restore():
        for source, contents in sources.items():
            source.write_bytes(contents)

    destination = project / "fresh-evidence"
    retain_index_evidence(base, project, "index.ist", destination)
    evidence = json.loads((destination / "index-evidence.json").read_text())
    expected_names = {base.name + suffix for suffix in (".idx", ".ind", ".ilg", ".fls", ".aux", ".log")}
    assert set(evidence["artifacts"]) == expected_names, evidence
    assert {path.name for path in destination.iterdir()} == expected_names | {"index-evidence.json"}
    for name in expected_names:
        assert (destination / name).read_bytes() == sources[project / name]
        assert hashlib.sha256((destination / name).read_bytes()).hexdigest() == evidence["artifacts"][name]
    assert evidence["pdf_sha256"] == hashlib.sha256(pdf).hexdigest() and evidence["pdf_pages"] == 1, evidence
    assert evidence["style_sha256"] == hashlib.sha256(sources[style]).hexdigest(), evidence
    assert (evidence["accepted"], evidence["rejected"], evidence["managed_ind_consumed"]) == (2, 0, True)
    assert all(path.read_bytes() == contents for path, contents in sources.items())
    assert not Path(str(base) + ".index-evidence.json").exists(), "export dirtied the build input directory"

    cli_destination = project / "fresh-cli-evidence"
    cli = subprocess.run([sys.executable, str(HERE / "build_contract.py"),
                          "--index-base", str(base), "--project-root", str(project),
                          "--index-style", "index.ist", "--index-evidence-dir", str(cli_destination)],
                         capture_output=True, text=True)
    assert cli.returncode == 0 and "index evidence retained" in cli.stdout, cli.stdout + cli.stderr
    assert json.loads((cli_destination / "index-evidence.json").read_text()) == evidence

    def reject(destination, marker, selected_style="index.ist", prevalidation=True):
        context = mock.patch("tempfile.mkdtemp") if prevalidation else nullcontext()
        with context as staging:
            try:
                retain_index_evidence(base, project, selected_style, destination)
            except (ValueError, OSError, UnicodeError) as exc:
                assert marker in str(exc), (marker, exc)
            else:
                raise AssertionError(f"invalid evidence accepted: {marker}")
            if prevalidation:
                staging.assert_not_called()
        assert not destination.exists(), (destination, marker)
        assert not list(destination.parent.glob(f".{destination.name}.tmp.*")), "partial staged evidence survived"

    # Failed exports cannot change a successful previous set or its manifest.
    old_set = {path.name: path.read_bytes() for path in destination.iterdir()}
    Path(str(base) + ".fls").write_text(f"PWD {project}\nINPUT unrelated.ind\n")
    try:
        retain_index_evidence(base, project, "index.ist", destination)
    except ValueError as exc:
        assert "destination already exists" in str(exc), exc
    else:
        raise AssertionError("existing evidence destination was overwritten")
    assert {path.name: path.read_bytes() for path in destination.iterdir()} == old_set
    restore()
    empty_existing = project / "existing-empty"
    empty_existing.mkdir()
    inode = empty_existing.stat().st_ino
    try:
        retain_index_evidence(base, project, "index.ist", empty_existing)
    except ValueError as exc:
        assert "destination already exists" in str(exc), exc
    else:
        raise AssertionError("an existing empty directory was replaced")
    assert empty_existing.stat().st_ino == inode and not list(empty_existing.iterdir())

    for suffix in (".idx", ".ind", ".ilg", ".fls", ".aux", ".log", ".pdf"):
        Path(str(base) + suffix).unlink()
        reject(project / ("missing-" + suffix[1:]), "artifact missing")
        restore()
    corruptions = (
        (".idx", b"", "missing or ambiguous processor entry counts"),
        (".ilg", b"missing processor summary", "missing or ambiguous processor entry counts"),
        (".ilg", b"(2 entries accepted, 0 rejected)\n(2 entries accepted, 0 rejected)", "missing or ambiguous"),
        (".ilg", b"(1 entries accepted, 0 rejected)", "1/2 accepted"),
        (".ilg", b"(2 entries accepted, 1 rejected)", "1 rejected"),
        (".ilg", b"(2 entries accepted, 0 rejected)\ndone (5 lines written, 1 warning).", "processor warnings"),
        (".ind", b" \n", "no readable index"),
        (".fls", f"PWD {project}\nINPUT other.ind\n".encode(), "was not consumed"),
        (".pdf", b"%PDF-1.4\nnot a readable PDF\n%%EOF\n", "PDF is unreadable"),
    )
    for number, (suffix, contents, marker) in enumerate(corruptions):
        Path(str(base) + suffix).write_bytes(contents)
        reject(project / f"malformed-{number}", marker)
        restore()
    reject(project / "missing-style", "absent.ist", "absent.ist")
    reject(Path("relative-index-evidence-unit"), "must be absolute")
    (project / "actual-parent").mkdir()
    (project / "linked-parent").symlink_to(project / "actual-parent", target_is_directory=True)
    reject(project / "linked-parent" / "evidence", "symlink ancestors")
    outside = project.parent / "outside-evidence-style.ist"
    outside.write_text("% outside the project\n")
    (project / "outside-style.ist").symlink_to(outside)
    reject(project / "outside-style-evidence", "INDEX_STYLE escapes", "outside-style.ist")

    # A change after snapshot validation must not publish the staged old bytes.
    original_mkdtemp = tempfile.mkdtemp
    for target in (Path(str(base) + ".ind"), style):
        def mutate_snapshot(*args, **kwargs):
            staging = original_mkdtemp(*args, **kwargs)
            target.write_bytes(target.read_bytes() + b"% changed during export\n")
            return staging

        with mock.patch("tempfile.mkdtemp", side_effect=mutate_snapshot):
            reject(project / ("mutated-" + target.suffix[1:]), "changed during export", prevalidation=False)
        restore()
    with mock.patch("os.rename", side_effect=OSError("publication denied")):
        reject(project / "failed-publish", "publication denied", prevalidation=False)
    with mock.patch("os.fsync", side_effect=OSError("staging write denied")):
        reject(project / "failed-staging", "staging write denied", prevalidation=False)
    assert all(path.read_bytes() == contents for path, contents in sources.items())


def run_configured_package_roots(project: Path) -> None:
    """Configured user/local trees pass; an adjacent unconfigured tree fails."""
    project.mkdir()
    for variable in ('TEXMFHOME', 'TEXMFLOCAL'):
        case = project / variable
        case.mkdir()
        src = case / 'project'
        src.mkdir()
        tex = src / 'doc.tex'
        tex.write_text('\\documentclass{article}\n\\begin{document}\nTrusted package test.\n\\end{document}\n')
        trusted = case / 'configured-texmf'
        trusted.mkdir()
        package = trusted / 'package.sty'
        package.write_text('% configured package\n')
        outside = case / 'adjacent-texmf'
        outside.mkdir()
        rejected = outside / 'package.sty'
        rejected.write_text('% unconfigured sibling\n')
        bin_dir = case / 'bin'
        bin_dir.mkdir()
        state = case / 'pass-count'
        kpse = bin_dir / 'kpsewhich'
        kpse.write_text(
            '#!/bin/sh\n'
            'if [ "$1" = "-var-value=$MOCK_TEXMF_VARIABLE" ]; then\n'
            '  printf "%s\\n" "$MOCK_TRUST_ROOT"\n'
            'else\n'
            '  case "$1" in\n'
            '    -var-value=*) exit 0 ;;\n'
            '    *.ttf) printf "%s/%s\\n" "$MOCK_FONT_DIR" "$1" ;;\n'
            '    *) printf "/mock/%s\\n" "$1" ;;\n'
            '  esac\n'
            'fi\n')
        latex = bin_dir / 'lualatex'
        latex.write_text(
            '#!/bin/sh\n'
            'out=""\nlast=""\n'
            'for arg in "$@"; do\n'
            '  case "$arg" in -output-directory=*) out=${arg#*=} ;; esac\n'
            '  last=$arg\n'
            'done\n'
            'stem=${last%.tex}\nn=0\n'
            '[ -f "$MOCK_STATE" ] && n=$(sed -n "1p" "$MOCK_STATE")\n'
            'n=$((n + 1))\nprintf "%s\\n" "$n" >"$MOCK_STATE"\n'
            'printf "%%PDF-1.4\\n%%%%EOF\\n" >"$out/$stem.pdf"\n'
            ': >"$out/$stem.log"\n'
            'printf "INPUT %s\\nINPUT %s\\n" "$MOCK_TEX" "$MOCK_PACKAGE" >"$out/$stem.fls"\n'
            'if [ "$n" -ge 2 ]; then\n'
            '  printf "INPUT %s\\n" "$MOCK_REJECTED" >>"$out/$stem.fls"\n'
            'fi\n')
        kpse.chmod(0o755)
        latex.chmod(0o755)
        env = os.environ.copy()
        env.pop('HEBREW_LATEX_PROJECT_ROOT', None)
        env.update(PATH=f'{bin_dir}:{env["PATH"]}', HEBREW_LATEX_FONT_DIR=str(FONTS),
                   MOCK_FONT_DIR=str(FONTS), MOCK_STATE=str(state), MOCK_TEX=str(tex),
                   MOCK_TEXMF_VARIABLE=variable, MOCK_TRUST_ROOT=str(trusted),
                   MOCK_PACKAGE=str(package), MOCK_REJECTED=str(rejected))
        proc = subprocess.run(['bash', str(BUILD), str(tex)], env=env,
                              text=True, capture_output=True)
        output = proc.stdout + proc.stderr
        assert proc.returncode == 1, output
        assert state.read_text().strip() == '2', output
        assert f'untrusted external TeX input: {rejected}' in output, output
        assert f'untrusted external TeX input: {package}' not in output, output
        assert not (src / 'doc.pdf').exists(), output

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fast", action="store_true",
        help="run only pre-engine path/config contracts; skip the full build orchestration mutation",
    )
    args = parser.parse_args(argv)
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        run_invalid_project_root(root / "invalid-root")
        run_invalid_build_config(root / "invalid-config")
        run_index_preflight(root / "index-preflight")
        if not args.fast:
            run_late_pass_recorder_escape(root / "late-pass")
            run_prior_output_dependency(root / "prior-output")
            run_project_input_mutation_blocks_convergence(root / "mutating-input")
            run_configured_package_roots(root / "configured-package-roots")
            run_managed_index_controls(root / "managed-index")
            run_index_output_controls(root / "index-output")
            run_generated_index_recorder(root / "generated-index-recorder")
            run_index_evidence_controls(root / "index-evidence")
    if args.fast:
        print("build guards: root + build-config/index-style preflight contracts pass (FAST; processors and recorder mutation are full-only)")
    else:
        print("build guards: root/recorder/self-output/source-stability trust + index preflight/processor/output/generated-input/atomic-evidence contracts pass")


if __name__ == "__main__":
    main()
