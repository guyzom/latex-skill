#!/usr/bin/env python3
"""Static API and layer-boundary regressions for the topic navigation shell."""
from pathlib import Path
import re
import sys
import unittest

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent.parent


class TopicRailContractTests(unittest.TestCase):
    def test_default_uses_resolved_document_language(self):
        source = (ROOT / "assets/topicrail.tex").read_text(encoding="utf-8")
        self.assertIn(r"\ifdefstring{\lakitmainlanguage}{english}{\STrtlfalse}{\STrtltrue}", source)
        # Navigation order may not follow the currently selected body locale.
        self.assertNotRegex(source, r"\\(?:if[a-z]*|edef|def)[^\n]*\\languagename")

    def test_labels_use_existing_shell_language_api(self):
        source = (ROOT / "assets/topicrail.tex").read_text(encoding="utf-8")
        self.assertEqual(source.count(r"{\doclang{\STgetname{\i}}}"), 2)
        self.assertNotIn(r"\h{\STgetname", source)
        self.assertIn(r"\newcommand{\STdirRTL}{\STrtltrue}", source)
        self.assertIn(r"\newcommand{\STdirLTR}{\STrtlfalse}", source)

    def test_shell_does_not_fork_direction_or_font_mechanisms(self):
        source = (ROOT / "assets/topicrail.tex").read_text(encoding="utf-8")
        for primitive in ("babelprovide", "babelfont", "setmainfont", "setsansfont", "setmathfont"):
            self.assertNotRegex(source, rf"\\{primitive}\b")
        for public_core in ("doclang", "h", "en", "englishprose", "hebrewprose"):
            self.assertNotRegex(source, rf"\\(?:renewcommand|newcommand|def)\s*\{{?\\{public_core}\b")


if __name__ == "__main__":
    unittest.main(verbosity=2)
