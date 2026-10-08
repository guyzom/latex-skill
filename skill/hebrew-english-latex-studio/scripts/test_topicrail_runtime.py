#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Original project code; scope and terms: ../LICENSING.md.
"""Real PDF regressions for topic-rail order, shell locale and font selection.

Builds native Hebrew/English defaults, both explicit order choices under each
base, and the legacy no-language-hook case through build.sh. Minority prose is
shipped while that locale is active; navigation must retain its declared order
and document-language labels. Actual known-defect engine mutations verify that
the geometry/locale assertions reject both historical bugs.

Use --evidence-dir NEW_PATH to preserve actual projects and the receipt. Add
--render to render every accepted page at 144 dpi with MuPDF and Poppler. This
does not assert human visual review; record that separately with render_review.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
import fitz

ROOT = Path(__file__).resolve().parent.parent
EVIDENCE_DIR: Path | None = None
RENDER = False


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fixture(main: str, direction: str | None = None, *, legacy: bool = False,
            short: bool = False, record_path: Path | None = None) -> str:
    other = "hebrew" if main == "english" else "english"
    labels = (("Start RONE", "Method RTWO", "Finish REND") if main == "english"
              else (r"ראשית \en{RONE}", r"שיטה \en{RTWO}", r"סיום \en{REND}"))
    heading = "Native topic" if main == "english" else "נושא מקומי"
    final = "Final native section" if main == "english" else "סעיף מקומי מסכם"
    caption = "Synthetic final diagram" if main == "english" else "תרשים מסכם סינתטי"
    minority = "פסקה בעברית מקומית" if other == "hebrew" else "A local English paragraph."
    hooks = "" if legacy else rf"\def\lakitlanguageprofile{{{main}}}" + "\n"
    if record_path is not None and any(char in str(record_path) for char in '{}\\"\n\r%#'):
        raise ValueError("measurement destination contains unsupported TeX path characters")
    recorder = ((r'\newwrite\RailRecord\immediate\openout\RailRecord="' + str(record_path) + r'"\relax' + "\n"
                 + r"\newcommand{\RailRecordLine}[1]{\immediate\write\RailRecord{#1}}" + "\n")
                if record_path is not None else r"\newcommand{\RailRecordLine}[1]{\typeout{#1}}" + "\n")
    source = (hooks + r"\def\lakitdocumentclass{report}\def\lakitclassoptions{11pt,a4paper}" + "\n"
              + r"\def\lakitlinespread{1.08}\input{preamble.tex}\input{topicrail.tex}" + "\n"
              + r"\STrailwidth{12}\STrailangle{40}" + "\n"
              + (rf"\STdir{direction}" + "\n" if direction else "")
              + recorder
              + r"\newcommand{\RailLabel}[2]{\RailRecordLine{ST-LABEL|#1|\languagename|\fontname\font}#2}" + "\n"
              + r"\STnames{" + ",".join(rf"\RailLabel{{{i}}}{{{label}}}" for i, label in enumerate(labels, 1)) + "}\n"
              + r"\hypersetup{pdftitle={Topic rail synthetic controls},pdfauthor={}}" + "\n"
              + r"\begin{document}\pagestyle{STtopic}\setcounter{part}{1}" + "\n"
              + rf"\chapter{{{heading}}}" + "\n"
              + r"\RailRecordLine{ST-STATE|native|\ifSTrtl RTL\else LTR\fi|\languagename}" + "\n"
              + r"\noindent\en{NATIVEPAGE} $E=\frac{1}{2}mv^2$.\par" + "\n")
    if short:
        return source + r"\end{document}" + "\n"
    return (source + r"\clearpage\setcounter{part}{2}" + "\n"
            + rf"\begin{{{other}prose}}" + "\n"
            + rf"\section{{{minority}}}" + "\n"
            + r"\RailRecordLine{ST-STATE|minority|\ifSTrtl RTL\else LTR\fi|\languagename}" + "\n"
            + r"\noindent\en{MINORITYPAGE} " + minority + r"\par\clearpage" + "\n"
            + rf"\end{{{other}prose}}\setcounter{{part}}{{3}}" + "\n"
            + rf"\section{{{final}}}" + "\n"
            + r"\RailRecordLine{ST-STATE|restored|\ifSTrtl RTL\else LTR\fi|\languagename}" + "\n"
            + r"\noindent\en{FINALPAGE} $x_{n+1}=x_n+1$.\par" + "\n"
            + r"\begin{tikzpic}\begin{tikzpicture}\node[draw] (a) at(0,0){$x$};"
            + r"\node[draw] (b) at(3,0){$f(x)$};\draw[->] (a)--(b);\end{tikzpicture}\end{tikzpic}" + "\n"
            + rf"\figcap{{\label{{fig:final}}{caption}}}" + "\n"
            + r"\end{document}" + "\n")


def assert_measurements(record: dict, main: str, expected_direction: str,
                        *, short: bool = False) -> None:
    expected_pages = 1 if short else 3
    if len(record["pages"]) != expected_pages:
        raise AssertionError(f"expected {expected_pages} physical pages, got {record['pages']!r}")
    for index, page in enumerate(record["pages"], 1):
        centers = page["rail_token_centers"]
        if set(centers) != {"RONE", "RTWO", "REND"}:
            raise AssertionError(f"page {index}: rail labels missing or duplicated: {centers!r}")
        xs = [centers[name] for name in ("RONE", "RTWO", "REND")]
        correct_order = xs[0] > xs[1] > xs[2] if expected_direction == "RTL" else xs[0] < xs[1] < xs[2]
        if not correct_order:
            raise AssertionError(f"page {index}: rail order {xs!r} does not match {expected_direction}")
        if page["rail_primary_locale"] != main:
            raise AssertionError(f"page {index}: rail label locale {page['rail_primary_locale']!r} != {main!r}")
        if page["active_labels"] != [index]:
            raise AssertionError(f"page {index}: current topic is not emphasized exactly once")
        # v5.4.1: luaotfload names the face "LatinModernSans/B" or "Latin Modern
        # Sans" depending on its version; compare the family without spaces.
        expected_family = "Heebo" if main == "hebrew" else "Latin Modern Sans"
        if not all(expected_family.replace(" ", "").lower() in item["font"].replace(" ", "").lower()
                   for item in page["label_logs"]):
            raise AssertionError(f"page {index}: unexpected document-language label fonts {page['label_logs']!r}")
    expected_states = [("native", expected_direction, main)]
    if not short:
        expected_states.extend([("minority", expected_direction, "hebrew" if main == "english" else "english"),
                                ("restored", expected_direction, main)])
    if record["states"] != expected_states:
        raise AssertionError(f"local body language/restoration or explicit rail state changed: {record['states']!r}")


class TopicRailRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if EVIDENCE_DIR is None:
            cls.temporary = tempfile.TemporaryDirectory(prefix="hll-topicrail-runtime-")
            cls.root = Path(cls.temporary.name)
        else:
            cls.temporary = None
            cls.root = EVIDENCE_DIR.expanduser().absolute()
            cls.root.mkdir(parents=True, exist_ok=False)
        cls.records = []

    @classmethod
    def tearDownClass(cls):
        if EVIDENCE_DIR is not None:
            (cls.root / "measurements.json").write_text(json.dumps({
                "schema": 1, "scope": "Executed topicrail component regressions only; no visual sign-off claim",
                "source_topicrail_sha256": sha(ROOT / "assets/topicrail.tex"),
                "driver_sha256": sha(Path(__file__)), "render_dpi": 144 if RENDER else None,
                "cases": cls.records,
            }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if cls.temporary is not None:
            cls.temporary.cleanup()

    def build(self, name: str, main: str, direction: str | None = None,
              *, legacy: bool = False, mutation: str | None = None) -> dict:
        project = self.root / name
        project.mkdir()
        for filename in ("preamble.tex", "topicrail.tex"):
            shutil.copy2(ROOT / "assets" / filename, project / filename)
        if mutation:
            path = project / "topicrail.tex"
            text = path.read_text(encoding="utf-8")
            if mutation == "old-order":
                old = r"\ifdefstring{\lakitmainlanguage}{english}{\STrtlfalse}{\STrtltrue}"
                self.assertEqual(text.count(old), 1)
                text = text.replace(old, r"\STrtltrue")
            elif mutation == "old-labels":
                self.assertEqual(text.count(r"\doclang{\STgetname{\i}}"), 2)
                text = text.replace(r"\doclang{\STgetname{\i}}", r"\h{\STgetname{\i}}")
            else:
                raise AssertionError(f"unknown mutation {mutation}")
            path.write_text(text, encoding="utf-8")
        measurement_path = project / "actual-engine-measurements.txt"
        (project / "main.tex").write_text(fixture(main, direction, legacy=legacy, short=bool(mutation),
                                               record_path=measurement_path), encoding="utf-8")
        # v5.4.1: the recorder writes an ABSOLUTE path, and TeX Live's default
        # openout_any=p admits one only under TEXMFOUTPUT. Without this every
        # build died at \openout ("I can't write on file") on a standard TeX
        # Live, CI's included. Scoped to this project; openout_any stays as is.
        env = dict(os.environ, HEBREW_LATEX_SKILL_ROOT=str(ROOT), HEBREW_LATEX_PROJECT_ROOT=str(project),
                   CONTENT_PROFILE="generic", EXPECTED_PAPER="a4", TEXMFOUTPUT=str(project))
        proc = subprocess.run(["bash", str(ROOT / "scripts/build.sh"), str(project / "main.tex")],
                              cwd=project, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              text=True, timeout=300)
        (project / "build-output.log").write_text(proc.stdout, encoding="utf-8")
        self.assertEqual(proc.returncode, 0, f"{name}:\n{proc.stdout[-14000:]}")
        log = measurement_path.read_text(encoding="utf-8")
        labels = [(int(i), locale, font) for i, locale, font in re.findall(r"ST-LABEL\|(\d+)\|([^|\n]+)\|([^\n]+)", log)]
        states = [(stage, direction, locale) for stage, direction, locale in re.findall(
            r"ST-STATE\|([^|\n]+)\|(RTL|LTR)\|([^\n]+)", log)]
        with fitz.open(project / "main.pdf") as doc:
            pages = []
            self.assertEqual(len(labels), len(doc) * 3, f"{name}: emitted label log count")
            for index, page in enumerate(doc):
                chunks = labels[index * 3:(index + 1) * 3]
                centers = {}
                for token in ("RONE", "RTWO", "REND"):
                    boxes = page.search_for(token, quads=True)
                    self.assertEqual(len(boxes), 1, f"{name} page {index+1}: token {token}")
                    centers[token] = float(boxes[0].rect.x0 + boxes[0].rect.x1) / 2
                label_logs = [{"id": i, "locale": locale, "font": font} for i, locale, font in chunks]
                pages.append({"physical_page": index + 1, "rail_token_centers": centers,
                              "rail_primary_locale": chunks[0][1], "label_logs": label_logs,
                              "active_labels": [i for i, _, font in chunks if "/B:" in font or "Bold" in font],
                              "rail_pdf_fonts": sorted({span['font'] for span in page.get_texttrace()
                                                        if span['bbox'][3] < 100}),
                              "text": page.get_text()})
            record = {"id": name, "main_language": main, "explicit_direction": direction,
                      "legacy_no_language_hooks": legacy, "mutation": mutation, "states": states,
                      "pages": pages, "pdf_sha256": sha(project / "main.pdf"),
                      "source_sha256": sha(project / "main.tex"), "topicrail_sha256": sha(project / "topicrail.tex"),
                      "engine_measurements_sha256": sha(measurement_path),
                      "build_log_sha256": sha(project / "build-output.log"), "renders": []}
        if RENDER and not mutation:
            for renderer in ("mupdf", "poppler"):
                output = project / f"review-{renderer}"
                run = subprocess.run([sys.executable, str(ROOT / "scripts/render_review.py"), "render",
                                      str(project / "main.pdf"), "--output", str(output), "--dpi", "144",
                                      "--renderer", renderer], env=env, stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT, text=True, timeout=120)
                (project / f"render-{renderer}.log").write_text(run.stdout, encoding="utf-8")
                self.assertEqual(run.returncode, 0, f"{name}/{renderer}: {run.stdout}")
                record["renders"].append({"renderer": renderer, "dpi": 144,
                                          "review_sha256": sha(output / "review.json")})
        self.records.append(record)
        return record

    def test_native_defaults_and_both_explicit_directions(self):
        for main in ("english", "hebrew"):
            for direction in (None, "LTR", "RTL"):
                with self.subTest(main=main, direction=direction):
                    record = self.build(f"{main}-{direction or 'default'}", main, direction)
                    assert_measurements(record, main, direction or ("RTL" if main == "hebrew" else "LTR"))
                    self.assertIn("FINALPAGE", record["pages"][-1]["text"])
                    self.assertNotIn("??", "".join(page["text"] for page in record["pages"]))
                    # A final ordinary heading and caption remain native after
                    # local-language prose and actual header shipout.
                    if main == "english":
                        self.assertIn("Final native section", record["pages"][-1]["text"])
                        self.assertIn("Synthetic final diagram", record["pages"][-1]["text"])
                    else:
                        self.assertRegex(record["pages"][-1]["text"], r"[\u0590-\u05ff]")

    def test_legacy_no_language_hook_remains_hebrew_rtl(self):
        record = self.build("legacy-hebrew-default", "hebrew", legacy=True)
        assert_measurements(record, "hebrew", "RTL")

    def test_known_old_order_mutation_is_rejected(self):
        record = self.build("negative-old-english-order", "english", mutation="old-order")
        with self.assertRaisesRegex(AssertionError, "rail order"):
            assert_measurements(record, "english", "LTR", short=True)
        record["expected_measurement_rejection"] = "rail order"

    def test_known_old_label_locale_mutation_is_rejected(self):
        record = self.build("negative-old-english-labels", "english", mutation="old-labels")
        with self.assertRaisesRegex(AssertionError, "rail label locale"):
            assert_measurements(record, "english", "LTR", short=True)
        record["expected_measurement_rejection"] = "rail label locale"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--evidence-dir", type=Path)
    parser.add_argument("--render", action="store_true")
    args, remaining = parser.parse_known_args()
    EVIDENCE_DIR, RENDER = args.evidence_dir, args.render
    unittest.main(argv=[sys.argv[0], *remaining], verbosity=2)
