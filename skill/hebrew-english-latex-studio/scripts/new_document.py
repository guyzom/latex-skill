#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Original project code; scope and terms: ../LICENSING.md.
# Additional output permission: ../LICENSES/Generated-Output-Permission.txt.
"""Create a native Hebrew, English, or bilingual LuaLaTeX source project."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
from typing import Iterable

sys.dont_write_bytecode = True
from architecture_contract import LANGUAGE_PROFILES, SUPPORTED_MAIN_LANGUAGES, resolve_language_profile
from build_contract import GENERATED_OUTPUT_PERMISSION_NAME, read_output_permission
from template_registry import compatibility_tables, load_catalog, resolve_recipe, ResolvedRecipe

ROOT = Path(__file__).resolve().parent.parent
# The public compatibility surfaces preserve their historical order and shape.
# Only the registry chooses recipes; TeX assets retain runtime ownership.
CATALOG = load_catalog(root=ROOT)
KINDS, THEMES, LAYOUTS, REFERENCE_LAYOUTS = compatibility_tables(CATALOG, root=ROOT)
PACKAGE_NAME = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{0,127}\Z')
CUSTOM_THEME = r'''% Local presentation overlay: edit this file to match the document's purpose.
% Loaded AFTER preamble.tex and semantic components. No supplied theme is loaded.
% Keep language, direction, fonts, class, geometry, math and reference mechanics
% in their owning layers. Set layout hooks BEFORE preamble.tex in main.tex.
% Add optional packages in main.tex; verify dependencies and compatibility.
\ifdefined\hllpdfcoreloaded\else
  \errmessage{local theme.tex requires preamble.tex first}
  \expandafter\endinput
\fi
% A restrained starting palette; replace it freely with a coherent design.
\definecolor{cBlue}{HTML}{24445A}
\definecolor{cBlueBg}{HTML}{F3F7FA}
\definecolor{cRule}{HTML}{24445A}
% Local spacing, heading decoration, and mdframed presentation may be added here.
% Preserve semantic headings, anchor identities, and readable text sizes.
% Review every page in each language actually used, including callout edges.
'''
README = '''# Editable source project

`GENERATED-OUTPUT-PERMISSION.txt` preserves the additional permission for original
project text and code fragments emitted by the generator. Those fragments may be
reproduced, modified and distributed as part of normal generated output under
terms of your choice. The generator programs themselves remain under AGPLv3.
Copied templates, assets and third-party material retain their actual terms;
this permission does not grant rights in them. Tool use does not automatically
license original user document content or output PDFs under AGPL.

Edit `main.tex`, replace all sample content and metadata, and choose a design
appropriate to the audience. The language profile, genre, theme, and optional
packages are independent decisions. The English profile uses native English
body text, metadata, and document defaults. In bilingual mode, the main language
controls the shell and explicit language blocks control the actual prose.

`reader` uses the supplied restrained theme. `core` uses the core presentation.
`custom` creates a local `theme.tex` to edit. Presentation may change freely while
direction, mathematical notation, anchors, and content remain correct. Set page
layout hooks before `preamble.tex`; keep them out of a presentation overlay.
`academic` supplies a classic serif article presentation and selective equation
numbering. The `paper` genre defaults to this theme; other genres default to
`reader`. Explicit theme choices always take precedence. The paper's article,
A4, 11 pt, 2.7 cm margin and 1.08 line-spread settings belong to its source layout.
Its bilingual form has one combined title, paired abstracts and one shared
bibliography; the translated full body deliberately begins on a new page.
Only central equations or equations cited later should carry numbers. Use
`\\eqref{label}` for a real reference and `\\noeqref{label}` for a central equation
that deliberately needs a number; use starred displays for incidental working.
Do not add a reference merely to force a number. Replace sample exposition,
illustrative values and its actual background citation as appropriate.

`--layout reference-compact` creates a three-column formula sheet at 6.3 pt with
a 7.8 pt baseline; `reference-readable` creates two columns at 9 pt with an
11 pt baseline. Both presets require `--kind formula-sheet`, use an A4 article
with reserved running-header and footer space, and default to the `reference`
theme only when no theme is supplied. The default `standard` layout retains the
existing genre defaults. Explicit themes remain independent of these layouts.
The `reference` theme is also available on standard layouts without adding
columns. Reference math uses scalable Computer Modern 10/7/5 pt designs at
6.25/4.375/3.125 pt in the compact preset and 8.75/6.125/4.375 pt in the readable
preset. The declarations `\\ReferenceMathFontSize`, `\\ReferenceMathScriptSize`
and `\\ReferenceMathScriptScriptSize` belong to the reference layout, alongside
body size, column count, gap and page geometry; the theme controls presentation.
The math selection is local to `referencecolumns` and `referencewide` and leaves
the core math configuration outside these regions unchanged. Column order follows the document's
main language, including inside paragraphs in the other language. The default
sample uses ordinary equations and adjacent conditions inside atomic, unframed
`referenceentry` topics. Reserve formula frames for central referenced results;
use a question series with separate solution parts for a long worked solution.
An optional `referencewide` block belongs outside `referencecolumns`; split wide
equations meaningfully instead of shrinking them. Neither preset adds such a
block to the default sample. Both use 8 mm side margins, 12 mm at the top and
16 mm at the bottom, with a 7 mm footer offset.
The sample mathematical and physical content is illustrative and should be
replaced with the actual scope, definitions and source material.

Reference presets use exactly two numbered heading levels: independent
`\\section` topics and their `\\subsection` subtopics. Enclose each complete
short topic, including its native heading and any subtopics, in `referenceentry`
to keep the topic together within one column. Author a long topic as separate
semantic entries; do not shrink it or add another numbered level. Topic numbering
and PDF bookmark depth are both limited to two, independently of selective
equation numbering. The reference theme uses gray 0.3 pt column separators.
Set `\\ReferenceColumnRule` to `0pt` before loading the column extension when
separators are not wanted.

`project.json` records creation-time choices and hashes, not current validation.
Schema 3 adds the requested and resolved recipe, decision provenance, recipe
revision and the SHA-256 of the canonical studio catalog. The recipe records
declared hooks, the distinct copy and load plans, and unset-only build defaults.
These declarations describe the generated source; they do not certify a PDF.
Existing schema 2 projects remain editable and are never rewritten by creation.
Inspect supported recipes with `scripts/template_registry.py list --json`, or
resolve one with its read-only `resolve` command in the installed skill.
Its hashes become historical once a source is edited. Font programs are external
pinned dependencies; the generator does not install fonts or optional packages.
Selected extra packages load after the core. Packages already supplied by the core,
a selected component or a reference starter are recorded without being loaded
twice. Package options and packages that require earlier loading need a documented manual integration;
do not reload Babel/fontspec/geometry/hyperref with conflicting options. For a new
package, check its documentation, installed availability, load order and collisions
with direction, fonts, headings, references, tables, and the chosen theme. Record
manual changes in the project manifest, then compile and review the affected pages.

Optional semantic components require explicit selection. `--component study`
adds keyed exercises and solutions; `--component index` adds a language-local
index with authored six-digit sort ranks. Repeat the option to combine them.
Unselected projects copy and load neither component. The small emitted specimens
are original editing examples, not complete study material. Replace them with
your actual content. The index route copies `index.ist` and supplies unset-only
`INDEX_PROCESSOR=makeindex` / `INDEX_STYLE=index.ist` defaults; it does not infer
Hebrew collation or install optional dependencies. Review display order, locators,
links and every affected page after editing. See the component guides in the
installed skill for supported identities, index formats and limitations.

After installing the skill's pinned fonts and required TeX dependencies:

```bash
HEBREW_LATEX_SKILL_ROOT=/path/to/skill bash build.sh
python3 /path/to/skill/scripts/render_review.py render main.pdf --output review
```

The generated build script uses the genre's advisory content profile only when
`CONTENT_PROFILE` is unset. An explicit value is passed to the managed builder;
an empty value selects `generic`, and an invalid value fails configuration
validation before compilation. Paper and folio contracts are also passed through;
configure the matching layout in `main.tex` before declaring those build settings.
The paper, reference-layout and matching-theme wrappers supply unset-only defaults for their declared
paper/folio and caption contracts. Explicit caller settings remain authoritative
and must agree with the edited source; a mismatch can fail a build gate.

A mixed-language letter places its secondary-language request before the closing
and signature, without adding a numbered section. In bilingual standard reports,
data reports, technical documents and formula sheets, the complete translated
body starts on a new page. Short notes, general documents and letters retain
their continuous paired-body flow. The paper and reference layouts retain their
dedicated paired front-matter and page-opening rules.

Review every page at a readable scale. Build success is not visual sign-off,
scientific validation, accessibility certification, or a test of the target viewer.
Do not add unnecessary material or compress whitespace to satisfy a density hint.
'''


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def package_selections(packages: Iterable[str], assets: list[str]) -> list[dict[str, str]]:
    """Validate literal names and avoid explicitly reloading core/component packages.

    This does not certify installed availability or compatibility. No package name
    is executed by a shell and options are deliberately not accepted as names.
    """
    if isinstance(packages, (str, bytes)):
        raise ValueError('packages must be a sequence of names, not one string')
    provided: dict[str, str] = {}
    for asset in assets:
        source = '\n'.join(line.split('%', 1)[0] for line in (ROOT / 'assets' / asset).read_text().splitlines())
        for names in re.findall(r'\\(?:usepackage|RequirePackage)(?:\[[^\]]*\])?\{([^}]+)\}', source):
            for name in names.split(','):
                provided[name.strip()] = asset
    result = []
    seen: set[str] = set()
    for name in packages:
        if not isinstance(name, str) or not PACKAGE_NAME.fullmatch(name):
            raise ValueError(f'invalid TeX package name: {name!r}; use a literal name without options, paths, or .sty')
        if name not in seen:
            result.append({'name': name, 'loaded_by': provided.get(name, 'main.tex'),
                           'status': 'already-provided' if name in provided else 'extension-requires-validation'})
            seen.add(name)
    return result


def template_parts(kind: str, language: str, layout: str = 'standard', *,
                   recipe: ResolvedRecipe | None = None) -> tuple[str, str, str]:
    recipe = recipe or resolve_recipe(kind, language=language, layout=layout,
                                      root=ROOT, catalog=CATALOG)
    name = Path(dict(recipe.starter_variants)[language]).name
    source = (ROOT / 'assets' / name).read_text(encoding='utf-8')
    header, sep, rest = source.partition(r'\begin{document}')
    body, end, tail = rest.rpartition(r'\end{document}')
    if not sep or not end or tail.strip():
        raise ValueError(f'malformed starter template: {name}')
    # DeclareDocNote captures its language at declaration time, before the body.
    if 'declare-note-language' in recipe.source_handlers:
        header = header.replace(r'\DeclareDocNote{', '\\DeclareDocNote[' + language + ']{')
    # Keep the data heading with its longtable caption and initial rows. This
    # matters when the second language starts late on a bilingual page. The
    # historical Hebrew asset stays intact; the generated source gets the guard.
    if 'data-heading-guard' in recipe.source_handlers and language == 'hebrew':
        body = body.replace('\\section{נתונים}', '\\Needspace{10\\baselineskip}\n\\section{נתונים}')
    return name, header, body


def selected_theme(kind: str, theme: str | None, layout: str = 'standard') -> str:
    """Resolve a genre's default without restricting independent theme choices."""
    return resolve_recipe(kind, theme=theme, layout=layout, root=ROOT,
                          catalog=CATALOG).theme


def paper_frontmatter(body: str) -> tuple[str, str, str]:
    """Split the owned article starter without interpreting arbitrary TeX."""
    match = re.fullmatch(r'\s*\\maketitle\s*\\begin\{abstract\}(.*?)'
                         r'\\end\{abstract\}(.*?)'
                         r'(\\phantomsection\s*\\addcontentsline\{toc\}\{section\}\{\\refname\}\s*'
                         r'\\begin\{thebibliography\}\{9\}.*?\\end\{thebibliography\})\s*',
                         body, flags=re.S)
    if not match:
        raise ValueError('malformed paper starter front matter or bibliography')
    return match.group(1).strip(), match.group(2).strip(), match.group(3).strip()


def reference_minority_note(body: str, minority: str) -> str:
    """Insert original physics prose beside its topic in an owned starter."""
    heading = ('\\section{Quantum state and measurement}\n' if minority == 'hebrew' else
               '\\section{מצב קוונטי ומדידה}\n')
    preceding, found, section = body.partition(heading)
    introductory, formula, following = section.partition(r'\begin{referenceformula}')
    if not found or not formula:
        raise ValueError('malformed reference starter quantum-state section')
    note = {
        'hebrew': r'''
\begin{hebrewprose}
עבור מצב מנורמל, ההסתברויות במדידה בבסיס אורתונורמלי אינן שליליות וסכומן הוא 1.
האמפליטודות יכולות להיות מרוכבות; הנרמול מתייחס לסכום ריבועי הערכים המוחלטים שלהן.
\end{hebrewprose}
''',
        'english': r'''
\begin{englishprose}
For a normalized state, measurement probabilities in an orthonormal basis are
nonnegative and sum to one. The amplitudes may be complex; normalization concerns
the sum of their squared magnitudes.
\end{englishprose}
''',
    }[minority]
    return preceding + found + introductory + note + formula + following


def letter_minority_note(body: str, minority: str) -> str:
    """Place a natural translated request before an owned letter's closing.

    This handler recognizes literal skill-owned starter content. It never
    interprets arbitrary user TeX or turns a letter into numbered note sections.
    """
    closing = {
        'hebrew': '\nThank you for your time and consideration.\\par\\medskip\n',
        'english': '\nתודה על הזמן ועל ההתייחסות.\\par\\medskip\n',
    }[minority]
    if body.count(closing) != 1:
        raise ValueError('malformed letter starter closing')
    preceding, marker, following = body.partition(closing)
    note = {
        'hebrew': r'''\begin{hebrewprose}
אשמח לקבל אישור שהפנייה התקבלה ולדעת מהו המועד הצפוי למענה.
\end{hebrewprose}
''',
        'english': r'''\begin{englishprose}
Please confirm receipt of this letter and let me know when I can expect a response.
\end{englishprose}
''',
    }[minority]
    return preceding.rstrip() + '\n\n' + note + marker + following


def compose_minority_body(body: str, minority: str, extension: str,
                          composer_id: str) -> str:
    """Dispatch a closed registry handler for skill-owned secondary prose."""
    if composer_id == 'paper-summary':
        _, _, bibliography = paper_frontmatter(body)
        return body.removesuffix(bibliography + '\n') + extension + bibliography + '\n'
    if composer_id == 'reference-topic-note':
        return reference_minority_note(body, minority)
    if composer_id == 'letter-before-signature':
        return letter_minority_note(body, minority)
    if composer_id == 'append-note':
        return body + extension
    raise ValueError(f'unknown minority composer: {composer_id!r}')


def declared_layout(source: str, theme: str, layout: str = 'standard', *,
                    recipe: ResolvedRecipe | None = None) -> dict[str, object]:
    """Creation-time source declarations, not an inferred or validated PDF layout."""
    hooks = {}
    for name in ('lakitdocumentclass', 'lakitclassoptions', 'lakitgeometryoptions',
                 'lakitlinespread', 'lakitparagraphstyle', 'lakittocdepth', 'lakitsecnumdepth'):
        match = re.search(r'\\def\\' + name + r'\{([^{}]*)\}', source)
        if match:
            hooks[name] = match.group(1)
    if layout != 'standard':
        for name in ('ReferenceMathFontSize', 'ReferenceMathScriptSize',
                     'ReferenceMathScriptScriptSize'):
            match = re.search(r'\\def\\' + name + r'\{([^{}]*)\}', source)
            if match:
                hooks[name] = match.group(1)
    recipe_hooks = {hook.name: hook.value for hook in recipe.hooks} if recipe else {}
    class_options = hooks.get('lakitclassoptions', recipe_hooks.get('lakitclassoptions', ''))
    declared_papers = [option.strip().removesuffix('paper') for option in class_options.split(',')
                       if option.strip() in ('a4paper', 'letterpaper')]
    if len(set(declared_papers)) > 1:
        raise ValueError('owned starter declares conflicting paper class options')
    expected_paper = declared_papers[0] if declared_papers else None
    result = {'preset': layout, 'declared_hooks': hooks, 'expected_paper': expected_paper,
            'folio_layout': 'center', 'folio_band': 'footer',
            'font_policy': ('core Hebrew and math fonts; ' + theme + ' English uses Latin Modern Roman'
                            if theme in ('academic', 'reference') else
                            'core language-profile fonts; math remains TeX math'),
            'status': 'creation-time declarations; verify PDF after edits'}
    if layout != 'standard':
        # Public compatibility dictionaries are query surfaces. Resolve this
        # snapshot from the canonical catalog rather than trusting a caller's
        # mutation of those historical mutable Python objects.
        reference_presets = compatibility_tables(CATALOG, root=ROOT)[3]
        reference_dimensions = {}
        for name, field in (('ReferenceColumnGap', 'column_gap'),
                            ('ReferenceColumnRule', 'column_rule')):
            value = recipe_hooks.get(name)
            if value is None:
                match = re.search(r'\\def\\' + name + r'\{([^{}]*)\}', source)
                if not match:
                    raise ValueError(f'owned reference starter is missing {name}')
                value = match.group(1)
            reference_dimensions[field] = value
        result.update({**reference_presets[layout],
                       **reference_dimensions,
                       'column_order': 'main-language page direction',
                       'wide_content': 'explicit referencewide outside referencecolumns'})
        result['font_policy'] = (
            'core Hebrew fonts; reference math uses scalable Computer Modern designs; ' +
            (theme + ' English uses Latin Modern Roman' if theme in ('academic', 'reference')
             else 'English follows core language-profile fonts'))
    return result


def main_source(kind: str, language: str, main_language: str, theme: str,
                selections: list[dict[str, str]], layout: str = 'standard', *,
                recipe: ResolvedRecipe | None = None) -> tuple[str, list[str]]:
    recipe = recipe or resolve_recipe(kind, language=language, main_language=main_language,
                                      theme=theme, layout=layout, root=ROOT, catalog=CATALOG)
    name, header, body = template_parts(kind, main_language, layout, recipe=recipe)
    templates = [name]
    header = re.sub(r'(?m)^\\def\\lakit(?:languageprofile|mainlanguage)\{[^}]+\}\s*\n?', '', header)
    header = header.replace('\\input{reader_theme.tex}\n', '')
    header = header.replace('\\input{academic_theme.tex}\n', '')
    header = header.replace('\\input{reference_theme.tex}\n', '')
    for macro, value in recipe.preset_bindings:
        header = re.sub(r'\\def\\' + macro + r'\{[^}]+\}',
                        lambda _: '\\def\\' + macro + '{' + value + '}', header)
    extension_lines = ''.join('\\usepackage{' + p['name'] + '}\n'
                              for p in selections if p['loaded_by'] == 'main.tex')
    header = header.replace('\\input{preamble.tex}\n', '\\input{preamble.tex}\n' + extension_lines)
    theme_line = ('\\input{' + recipe.presentation_input + '}\n'
                  if recipe.presentation_input else '')
    selected_components = {item.id: item for item in CATALOG.components}
    header += ''.join('\\input{' + Path(selected_components[name].asset_path).name + '}\n'
                      for name in recipe.components)
    header += theme_line
    hooks = f'\\def\\lakitlanguageprofile{{{language}}}\n\\def\\lakitmainlanguage{{{main_language}}}\n'
    if language == 'bilingual':
        secondary = 'english' if main_language == 'hebrew' else 'hebrew'
        second_name, second_header, second_body = template_parts(kind, secondary, layout,
                                                                 recipe=recipe)
        templates.append(second_name)
        # Keep counterpart sample IDs distinct, including deferred note keys.
        def qualify(match: re.Match[str]) -> str:
            return match.group(1) + 'secondary-' + match.group(2) + '}'
        pattern = r'(\\(?:label|ref|eqref|noeqref|autoref|pageref|nameref|DocNoteMark|DeclareDocNote)(?:\[[^\]]*\])?\{)([^}]+)\}'
        second_body = re.sub(pattern, qualify, second_body)
        second_header = re.sub(pattern, qualify, second_header)
        # flowtable's label is a positional argument, not a \label call.
        second_body = second_body.replace('{tab:measurements}', '{secondary-tab:measurements}')
        for line in second_header.splitlines():
            if line.startswith(r'\DeclareDocNote'):
                header += line + '\n'
        if recipe.composer_id == 'reference-paired-pages':
            title_pattern = r'(?m)^\\def\\ReferenceTitle\{([^{}]+)\}$'
            second_title = re.search(title_pattern, second_header)
            if not second_title:
                raise ValueError('malformed translated reference title')
            marker = '\\h{' if secondary == 'hebrew' else '\\en{'
            header = re.sub(title_pattern,
                            lambda m: '\\def\\ReferenceTitle{' + m.group(1) +
                            '\\\\[0.25em]{\\normalsize ' + marker +
                            second_title.group(1) + '}}}', header, count=1)
            second_body = second_body.replace('\\makereferencetitle\n', '', 1)
            body = (body.rstrip() + '\n\\clearpage\n' +
                    f'\\begin{{{secondary}prose}}\n' + second_body.strip() +
                    f'\n\\end{{{secondary}prose}}\n')
        elif recipe.composer_id == 'paper-shared-frontmatter':
            primary_abstract, body, bibliography = paper_frontmatter(body)
            secondary_abstract, second_body, _ = paper_frontmatter(second_body)
            header = re.sub(r'\\newtheorem\{paperlemma\}\{[^{}]+\}',
                            lambda _: r'\newtheorem{paperlemma}{\iflanguage{english}{Lemma}{למה}}',
                            header, count=1)
            # A standard article has one title and one shared bibliography. Both
            # abstracts precede the paired bodies; references share the real key.
            # Preserve each starter entry's explicit local paragraph scope;
            # ending the secondary body must not turn English continuations RTL.
            title_pattern = r'(?m)^\\title\{([^{}]+)\}$'
            second_title = re.search(title_pattern, second_header)
            if not second_title:
                raise ValueError('malformed translated paper title')
            title_marker = '\\h{' if secondary == 'hebrew' else '\\en{'
            header = re.sub(title_pattern,
                            lambda m: '\\title{' + m.group(1) + '\\\\[0.4em]{\\large ' +
                            title_marker + second_title.group(1) + '}}}', header, count=1)
            abstracts = ''.join(f'\\begin{{{locale}prose}}\n\\begin{{abstract}}\n' + text +
                                f'\n\\end{{abstract}}\n\\end{{{locale}prose}}\n'
                                for locale, text in [(main_language, primary_abstract),
                                                     (secondary, secondary_abstract)])
            body = ('\n\\maketitle\n' + abstracts +
                    f'\\begin{{{main_language}prose}}\n' + body +
                    f'\n\\end{{{main_language}prose}}\n\\clearpage\n' +
                    f'\\begin{{{secondary}prose}}\n' + second_body +
                    f'\n\\end{{{secondary}prose}}\n' + bibliography + '\n')
        elif recipe.composer_id in ('paired-bodies', 'paired-full-pages'):
            separation = ('\n\\clearpage\n' if recipe.composer_id == 'paired-full-pages'
                          else '\n\\bigskip\n')
            body = (f'\n\\begin{{{main_language}prose}}\n' + body.strip() +
                    f'\n\\end{{{main_language}prose}}' + separation +
                    f'\\begin{{{secondary}prose}}\n' + second_body.strip() +
                    f'\n\\end{{{secondary}prose}}\n')
        else:
            raise ValueError(f'unknown bilingual composer: {recipe.composer_id!r}')
    elif language == 'english-with-hebrew':
        extension = r'''
% A supplementary reader-facing note; language-wrapper guidance belongs in
% comments and documentation, not in the generated document's visible prose.
\section{Further review}
\begin{hebrewprose}
לפני הסקת מסקנה, כדאי לבדוק שהנתונים וההנחות תואמים לשאלה הנבחנת.
אם חסר מידע, יש לציין מה נדרש כדי להשלים את הבדיקה.
\end{hebrewprose}
'''
        if recipe.minority_composer_id == 'paper-summary':
            extension = r'''
\section{A Hebrew summary}
Regularization (\h{רגולריזציה}) has a precise algebraic effect in this model:
\begin{hebrewprose}
במודל הריבועי שהוגדר כאן, הגדלת מקדם הענישה מקרבת את נקודת המינימום לאפס.
הנוסחה שבמשוואה~\eqref{eq:solution} מתארת קשר זה במדויק; היא אינה קובעת
איזה מקדם ענישה מתאים לנתונים אמיתיים.
\end{hebrewprose}
'''
        body = compose_minority_body(body, 'hebrew', extension, recipe.minority_composer_id)
    elif language == 'hebrew-with-english':
        extension = r'''
% A supplementary reader-facing note, with an explicit local prose language.
\section{בדיקה נוספת}
\begin{englishprose}
Before drawing a conclusion, check that the evidence and assumptions address
the question being considered. If information is missing, state what is needed
to complete the review.
\end{englishprose}
'''
        if recipe.minority_composer_id == 'paper-summary':
            extension = r'''
\section{סיכום באנגלית}
\begin{englishprose}
For the quadratic defined here, increasing the regularization penalty moves
the minimizer toward zero. Equation~\eqref{eq:solution} gives the exact relation.
It does not determine which penalty is appropriate for real observations.
\end{englishprose}
'''
        body = compose_minority_body(body, 'english', extension, recipe.minority_composer_id)
    body += optional_component_body(tuple(selected_components[name].specimen_id for name in recipe.components), main_language)
    return hooks + header + '\\begin{document}\n' + body.lstrip() + '\\end{document}\n', templates


def optional_component_body(components: tuple[str, ...], main_language: str) -> str:
    """Small original editable specimens, emitted only by explicit selection."""
    if any(name not in ('study', 'index') for name in components):
        raise ValueError('unknown closed optional specimen composer')
    body = ''
    if 'study' in components:
        title = 'A worked derivative' if main_language == 'english' else 'נגזרת לדוגמה'
        question = 'Find the derivative of $f(x)=x^2$.' if main_language == 'english' else 'מצאו את הנגזרת של $f(x)=x^2$.'
        solution = "Apply the power rule: $f'(x)=2x$." if main_language == 'english' else "לפי כלל החזקה: $f'(x)=2x$."
        lead = 'Exercise and solution' if main_language == 'english' else 'תרגיל ופתרון'
        body += ('\n\\clearpage\n\\section{' + lead + '}\n'
                 + '\\begin{studyexercise}{starter-derivative}{' + title + '}\n'
                 + question + '\n\\end{studyexercise}\n'
                 + '\\begin{studysolution}{starter-derivative}\n' + solution + '\n\\end{studysolution}\n')
    if 'index' in components:
        lead = 'Index specimen' if main_language == 'english' else 'דוגמת מפתח'
        body += ('\n\\clearpage\n\\section{' + lead + '}\n'
                 + '\\begin{englishprose}\nCompiler\\lakitindex{english}{000001}{Compiler} translates source code.\n\\end{englishprose}\n'
                 + '\\begin{hebrewprose}\nמהדר\\lakitindex{hebrew}{000001}{מהדר} מתרגם קוד מקור.\n\\end{hebrewprose}\n'
                 + '\\printindex\n')
    return body


def publish_no_replace(stage: Path, destination: Path) -> None:
    """Reserve the destination atomically; never replace a race-created directory.

    Files are staged first, then hard-linked on the same filesystem with exclusive
    creation. Publication is not a transactional multi-file rename. On failure only
    links created by this call are removed; unrelated files are never deleted.
    """
    try:
        destination.mkdir()
    except FileExistsError as exc:
        raise ValueError(f'destination already exists; choose a new directory: {destination}') from exc
    created: list[Path] = []
    try:
        for source in sorted(stage.iterdir()):
            target = destination / source.name
            os.link(source, target)
            created.append(target)
    except BaseException:
        for target in reversed(created):
            # Remove only the original hard link, not a concurrently replaced file.
            original = stage / target.name
            try:
                if target.lstat().st_ino == original.stat().st_ino and not target.is_symlink():
                    target.unlink()
            except FileNotFoundError:
                pass
        try:
            destination.rmdir()
        except OSError:
            pass
        raise


def create(kind: str, destination: Path, *, language: str = 'hebrew',
           main_language: str | None = None, theme: str | None = None,
           packages: Iterable[str] = (), layout: str = 'standard', components: tuple[str, ...] | list[str] = ()) -> None:
    recipe = resolve_recipe(kind, language=language, main_language=main_language,
                            theme=theme, layout=layout, components=components, root=ROOT, catalog=CATALOG)
    theme = recipe.theme
    main_language = recipe.main_language
    destination = Path(destination).expanduser().absolute()
    if destination.exists() or destination.is_symlink():
        raise ValueError(f'destination already exists; choose a new directory: {destination}')
    output_permission = read_output_permission(ROOT)
    assets = [Path(path).name for path in recipe.copy_plan]
    selection_assets = [Path(path).name for path in recipe.package_scan_plan]
    selections = package_selections(packages, selection_assets)
    source, templates = main_source(kind, language, main_language, theme, selections, layout,
                                    recipe=recipe)
    profile = recipe.content_profile
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.hllpdf-project-', dir=destination.parent) as td:
        stage = Path(td) / 'project'
        stage.mkdir()
        for name in assets:
            shutil.copyfile(ROOT / 'assets' / name, stage / name)
        (stage / 'main.tex').write_text(source, encoding='utf-8')
        if theme == 'custom': (stage / 'theme.tex').write_text(CUSTOM_THEME, encoding='utf-8')
        contract_defaults = ''
        for environment, value in recipe.build_defaults:
            contract_defaults += ('export ' + environment + '="${' + environment +
                                  '-' + value + '}"\n')
        script = '''#!/usr/bin/env bash
set -euo pipefail
: "${HEBREW_LATEX_SKILL_ROOT:?Set HEBREW_LATEX_SKILL_ROOT to the installed skill directory}"
HERE="$(cd "$(dirname "$0")" && pwd)"
export CONTENT_PROFILE="${CONTENT_PROFILE-'''+profile+'''}"
'''+contract_defaults+'''
exec bash "$HEBREW_LATEX_SKILL_ROOT/scripts/build.sh" "$HERE/main.tex"
'''
        (stage / 'build.sh').write_text(script, encoding='utf-8')
        (stage / 'build.sh').chmod(0o755)
        (stage / 'README.md').write_text(README, encoding='utf-8')
        (stage / GENERATED_OUTPUT_PERMISSION_NAME).write_bytes(output_permission)
        manifest = {'schema': 3, 'skill_version': (ROOT / 'VERSION').read_text().strip(),
                    'kind': kind, 'content_profile': profile,
                    'language_profile': language, 'main_language': main_language,
                    'base_direction': 'rtl' if main_language == 'hebrew' else 'ltr',
                    'theme': theme, 'package_selections': selections,
                    'layout': declared_layout(source, theme, layout, recipe=recipe),
                    'caption_contract': dict(recipe.caption_contract),
                    'package_compatibility': 'not-validated-by-generator',
                    'templates': templates,
                    'template_sha256': {name: digest(ROOT / 'assets' / name) for name in templates},
                    'font_binaries_included': False,
                    'font_manifest_sha256': digest(ROOT / 'assets/fonts/SHA256SUMS'),
                    'copied_assets': {name: digest(stage / name) for name in assets},
                    'initial_source_sha256': {p.name: digest(p) for p in sorted(stage.iterdir())},
                    'hash_scope': 'creation-time snapshot; regenerate evidence after edits'}
        manifest['recipe'] = recipe.as_dict()
        manifest['registry'] = {
            'path': 'registry/studio-catalog.json',
            'sha256': CATALOG.sha256,
            'schema': CATALOG.schema_version,
            'scope': 'creation-time snapshot; no compile, render or visual validation'}
        (stage / 'project.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
        publish_no_replace(stage, destination)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--kind', choices=sorted(KINDS), default='general')
    p.add_argument('--directory', type=Path, required=True)
    p.add_argument('--language', choices=LANGUAGE_PROFILES, default='hebrew')
    p.add_argument('--main-language', choices=SUPPORTED_MAIN_LANGUAGES,
                   help='required for bilingual; otherwise must agree with the language profile')
    p.add_argument('--theme', choices=THEMES,
                   help='presentation overlay; defaults to reference for reference layouts, academic for paper, reader otherwise')
    p.add_argument('--layout', choices=LAYOUTS, default='standard',
                   help='page layout; reference presets require formula-sheet; standard preserves genre defaults')
    p.add_argument('--package', action='append', default=[], metavar='NAME',
                   help='optional TeX package name; repeat for several; no options or paths')
    p.add_argument('--component', action='append', default=[], metavar='ID',
                   help='explicit optional semantic component; repeat to combine')
    a = p.parse_args()
    try:
        create(a.kind, a.directory, language=a.language, main_language=a.main_language,
               theme=a.theme, packages=a.package, layout=a.layout, components=a.component)
    except (OSError, ValueError) as exc:
        print(f'✗ project creation failed: {exc}', file=sys.stderr)
        return 2
    print(f'✓ new {a.kind} project ({a.language}, {selected_theme(a.kind, a.theme, a.layout)}): {a.directory.expanduser().absolute()}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
