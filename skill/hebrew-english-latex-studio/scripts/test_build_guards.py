#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Original project code; scope and terms: ../LICENSING.md.
"""Adversarial process tests for build.sh trust and path guards."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile


HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
BUILD = HERE / "build.sh"
sys.dont_write_bytecode = True
from font_paths import font_dir
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
    assert "untrusted external TeX input: /etc/passwd" in output, output
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
    ]
    for overrides, marker in cases:
        env = os.environ.copy()
        env["HEBREW_LATEX_FONT_DIR"] = str(FONTS)
        env.pop("HEBREW_LATEX_PROJECT_ROOT", None)
        for key in ["CONTENT_PROFILE", "EXPECTED_PAPER", "SECTION_MACROS",
                    "REPRO", "MAX_CROSS_PAGE_DESTINATIONS", "SOURCE_DATE_EPOCH"]:
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
        if not args.fast:
            run_late_pass_recorder_escape(root / "late-pass")
            run_prior_output_dependency(root / "prior-output")
            run_project_input_mutation_blocks_convergence(root / "mutating-input")
            run_configured_package_roots(root / "configured-package-roots")
    if args.fast:
        print("build guards: root + build-config preflight contracts pass (FAST; recorder mutation is full-only)")
    else:
        print("build guards: root/recorder/self-output/source-stability trust + build-config preflight contracts pass")


if __name__ == "__main__":
    main()
