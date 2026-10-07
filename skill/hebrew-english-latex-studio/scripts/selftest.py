#!/usr/bin/env python3
"""selftest.py — regression lock for the skill's checkers (v4.7.1).

Runs check_bidi_figures.py, check_charset.py and check_content_density.py
(the CODE-FRICTION advisory) against an embedded corpus of
known-good and known-bad patterns, every one of which was verified against a
REAL compile/render during the v3.20→v3.23 hardening. Run this after ANY edit
to the checkers (or the preamble macros they assume): a failure means you
reintroduced a bug class that was already paid for. Since v4.26.0 the corpus
also drives check_source_hazards.py ('hazards' cases, the BLD-70 contour
rule), whose other rules keep their dedicated unit suites.

Usage:  python3 scripts/selftest.py          (exit 0 = all pass, 1 = drift)
"""
import sys as _bytecode_sys
_bytecode_sys.dont_write_bytecode = True
import io, os, re, sys, tempfile
from contextlib import redirect_stderr, redirect_stdout

import check_bidi_figures as bidi_checker
import check_charset as charset_checker
import check_content_density as density_checker
import check_source_hazards as hazard_checker

HERE = os.path.dirname(os.path.abspath(__file__))
BIDI = os.path.join(HERE, 'check_bidi_figures.py')
CHARSET = os.path.join(HERE, 'check_charset.py')
DENSITY = os.path.join(HERE, 'check_content_density.py')

# Each case: (name, source, checker, set-of-rule-names-that-MUST-fire (empty = must be clean))
# Sources are single snippets; multiline via \n.
CASES = [
    # v4.11 exact text-mode reference exception; preserve all legacy cases.
    ('eqref411: text in align', '\\begin{align}x&=\\text{\\eqref{a}}\\end{align}', "bidi", set()),
    ('eqref411: text in equation', '\\begin{equation}x=\\text{\\eqref{a}}\\end{equation}', "bidi", set()),
    ('eqref411: text in brackets', '\\[x=\\text{\\eqref{a}}\\]', "bidi", set()),
    ('eqref411: spaces', '\\[x=\\text { \\eqref {a} }\\]', "bidi", set()),
    ('eqref411: multiline', '\\[x=\\text{\n\\eqref{a}\n}\\]', "bidi", set()),
    ('eqref411: real comment', '\\[x=\\text{% note\n\\eqref{a}% note\n}\\]', "bidi", set()),
    ('eqref411: inline text', 'ערך $x=\\text{\\eqref{a}}$ כאן.', "bidi", set()),
    ('eqref411: raw sibling', '\\[x=\\text{\\eqref{a}}+\\eqref{b}\\]', "bidi", {'MATH-WRAPPED-EQREF'}),
    ('eqref411: nested math not exempt', '\\[x=\\text{$\\eqref{a}$}\\]', "bidi", {'MATH-WRAPPED-EQREF'}),
    ('eqref411: comment cannot exempt', '\\[x= % \\text{\n\\eqref{a}\\]', "bidi", {'MATH-WRAPPED-EQREF'}),
    ('eqref411: other macro no exception', '\\[x=\\mbox{\\eqref{a}}\\]', "bidi", {'MATH-WRAPPED-EQREF'}),
    ('eqref411: following line outside', '\\[x=\\text{\\eqref{a}}\n+\\eqref{b}\\]', "bidi", {'MATH-WRAPPED-EQREF'}),
    # v4.8.0 — math membership, not the spelling of the adjacent dollar.
    ('ttmath-ok: whole inline', r'בדיקה $\texttt{A}$ תקינה.', 'bidi', set()),
    ('ttmath-ok: inline tail', r'בדיקה $x+\texttt{A}$ תקינה.', 'bidi', set()),
    ('ttmath-ok: inline head', r'בדיקה $\texttt{A}+x$ תקינה.', 'bidi', set()),
    ('ttmath-ok: multiline', 'בדיקה $x+\n\\texttt{A}$ תקינה.', 'bidi', set()),
    ('ttmath-bad: before math', r'בדיקה \texttt{x}$=1$ כאן.', 'bidi', {'TEXTTT-NEXT-TO-MATH'}),
    ('ttmath-bad: after math', r'בדיקה $x=1$\texttt{y} כאן.', 'bidi', {'TEXTTT-NEXT-TO-MATH'}),

    # ---- HEBREW-DOUBLE-HYPHEN: true positives ------------------------------
    ('dash: Hebrew spaced ---',       'טקסט עברי --- עוד עברית.',                       'bidi', {'HEBREW-DOUBLE-HYPHEN'}),
    ('dash: frametitle --- + code',   '\\begin{exbox}[frametitle={דוגמה --- \\code{foo}}]', 'bidi', {'HEBREW-DOUBLE-HYPHEN'}),
    ('dash: digit range 1990--2000',  'בשנים 1990--2000 חלה עלייה.',                    'bidi', {'HEBREW-DOUBLE-HYPHEN'}),
    ('dash: Latin--Latin run',        'הניסוי של Hong--Ou--Mandel המפורסם.',            'bidi', {'HEBREW-DOUBLE-HYPHEN'}),
    ('dash: inside \\text in math',   '\\[ x=1 \\quad \\text{טווח -- עולם} \\]',        'bidi', {'HEBREW-DOUBLE-HYPHEN'}),
    ('dash: Hebrew TikZ node text',   '\\begin{tikzpicture}\n\\node {\\h{שלב א --- שלב ב}};\n\\end{tikzpicture}', 'bidi', {'HEBREW-DOUBLE-HYPHEN'}),
    # ---- HEBREW-DOUBLE-HYPHEN: must stay clean -----------------------------
    ('dash-ok: single hyphens',       'מונח \\en{Hong-Ou-Mandel} וטווח 3-5 ומילה דו-רמתית.', 'bidi', set()),
    ('dash-ok: TikZ path ops',        '\\begin{tikzpicture}\n\\draw (0,0) -- (1,1) node[above] {\\h{שלום}};\n\\draw (a) -- (b) --cycle;\n\\end{tikzpicture}', 'bidi', set()),
    ('dash-ok: --flag in \\code',     'הדגל \\code{--break-system-packages} חשוב.',     'bidi', set()),
    ('dash-ok: comment rule',         'טקסט תקין.\n%---------------------------',        'bidi', set()),
    ('dash-ok: math minus',           'ביטוי $a--b$ במתמטיקה (מינוס כפול).',            'bidi', set()),
    ('dash-ok: \\url with --',        'קישור \\url{http://x.com/a--b} כאן.',            'bidi', set()),
    # ---- TEXT-MATH-CARET ----------------------------------------------------
    ('caret: bare ^ in \\text',       '\\begin{equation}a \\text{\\en{(linear 45^\\circ)}}\\end{equation}', 'bidi', {'TEXT-MATH-CARET'}),
    ('caret: \\(..\\) math form',     'נניח \\(\\theta = \\text{linear 45^\\circ}\\) בקיטוב.', 'bidi', {'TEXT-MATH-CARET'}),
    ('caret: $$..$$ form',            '$$ E = \\text{energy 2^n} $$',                    'bidi', {'TEXT-MATH-CARET'}),
    ('caret: between escaped \\$',    '$v = \\text{price \\$5^k\\$ approx}$',            'bidi', {'TEXT-MATH-CARET'}),
    ('caret-ok: escaped \\_',         '\\begin{equation}b=\\text{file\\_name}\\end{equation}', 'bidi', set()),
    ('caret-ok: nested $..$',         '\\begin{equation}c=\\text{ערך $x^2$ כאן}\\end{equation}', 'bidi', set()),
    ('caret-ok: nested \\(..\\)',     '$f = \\text{term \\(x^2\\) here}$',               'bidi', set()),
    # ---- TEXT-PARENS-IN-MATH: parens OUTSIDE an \en island (v3.23.4) ---------
    ('parens: (\\en{}) only-Latin',    '\\begin{equation}\\alpha\\quad\\text{(\\en{weak})}\\end{equation}', 'bidi', {'TEXT-PARENS-IN-MATH'}),
    ('parens: [\\en{}] brackets',      '$T_{\\text{[\\en{RAID}]}}$',                     'bidi', {'TEXT-PARENS-IN-MATH'}),
    ('parens: (\\en, \\en) list',      '$\\text{(\\en{a}, \\en{b})}$',                   'bidi', {'TEXT-PARENS-IN-MATH'}),
    ('parens: bare Latin+paren (#7)',  '\\begin{equation}\\text{Spec (TNR)}\\end{equation}', 'bidi', {'TEXT-PARENS-IN-MATH'}),
    ('parens-ok: \\en{(weak)} inside', '\\begin{equation}\\alpha\\quad\\text{\\en{(weak)}}\\end{equation}', 'bidi', set()),
    ('parens-ok: (Hebrew \\en) mixed', '\\begin{equation}P\\quad\\text{(הספק ב־\\en{CMOS})}\\end{equation}', 'bidi', set()),
    ('parens-ok: pure Hebrew parens',  '\\begin{equation}\\text{\\h{(שארית)}}\\end{equation}', 'bidi', set()),
    ('parens-ok: \\en no parens',      '\\begin{equation}\\text{\\en{weak}}\\end{equation}', 'bidi', set()),
    # -- multiline \text{}: the scan joins continuation lines (v3.23.5) --------
    ('ml: paren bug across lines',     '\\begin{equation}\\alpha\\quad\\text{(\\en{weak})%\n}\\end{equation}', 'bidi', {'TEXT-PARENS-IN-MATH'}),
    ('ml: paren bug (no %)',           '$\\text{(\\en{strong})\n} x$',                   'bidi', {'TEXT-PARENS-IN-MATH'}),
    ('ml: caret bug across lines',     '\\begin{equation}x=\\text{val\n2^n}\\end{equation}', 'bidi', {'TEXT-MATH-CARET'}),
    ('ml: colon bug across lines',     '\\begin{equation}\\text{\\en{s-channel}:\n} q\\end{equation}', 'bidi', {'MATH-TEXT-EN-COLON'}),
    ('ml-ok: correct across lines',    '\\begin{equation}\\text{\\en{(weak)}\n} x\\end{equation}', 'bidi', set()),
    ('ml-ok: Hebrew across lines',     '\\begin{equation}\\text{שלום\nעולם}\\end{equation}', 'bidi', set()),
    # ---- PROVIDECOMMAND-PRIMITIVE (v3.23.6, DEFECTS BLD-9) -------------------
    ('prim: \\providecommand{\\ni}',  '\\providecommand{\\ni}{n_{\\mathrm i}}',           'bidi', {'PROVIDECOMMAND-PRIMITIVE'}),
    ('prim: unbraced \\providecommand\\Re', '\\providecommand\\Re{\\operatorname{Re}}',   'bidi', {'PROVIDECOMMAND-PRIMITIVE'}),
    ('prim-ok: \\renewcommand{\\ni}', '\\renewcommand{\\ni}{n_{\\mathrm i}}',             'bidi', set()),
    ('prim-ok: non-primitive name',   '\\providecommand{\\ketbra}[2]{|#1\\rangle\\langle#2|}\n\\providecommand{\\niv}{n_{iv}}', 'bidi', set()),
    # ---- TEXT-HEBREW-BETWEEN-ISLANDS (v3.23.6, DEFECTS BIDI-16) --------------
    ('heb-isl: \\en{(}עברית\\en{)}',  '\\begin{align}I_D &\\propto V_{GS} && \\text{\\en{(}תעלה רחבה\\en{)}}\\end{align}', 'bidi', {'TEXT-HEBREW-BETWEEN-ISLANDS'}),
    ('heb-isl: multiline \\text',     '$\\text{\\en{(}תעלה רחבה\n\\en{)}} x$',            'bidi', {'TEXT-HEBREW-BETWEEN-ISLANDS'}),
    ('heb-isl-ok: \\h one unit',      '\\begin{align}I_D &\\propto V_{GS} && \\text{\\h{(תעלה רחבה)}}\\end{align}', 'bidi', set()),
    ('heb-isl-ok: single island',     '\\begin{equation}\\text{רוחב \\en{W} גדול}\\end{equation}', 'bidi', set()),
    # -- v3.23.7 hardening (adversarial review of the two new rules) -----------
    ('prim: definition split lines',  '\\providecommand\n{\\ni}{n_{\\mathrm i}}',        'bidi', {'PROVIDECOMMAND-PRIMITIVE'}),
    ('prim: single-letter \\d',       '\\providecommand{\\d}{\\mathrm{d}}',              'bidi', {'PROVIDECOMMAND-PRIMITIVE'}),
    ('prim-ok: \\dd differential',    '\\providecommand{\\dd}{\\mathrm{d}}',             'bidi', set()),
    ('heb-isl-ok: nested $..$ island','$y = \\text{שלום $a_{\\text{\\en{on}}}$ עולם \\en{X}}$', 'bidi', set()),
    ('heb-isl-ok: maqaf between isl', '$\\text{\\en{A}־\\en{B}}$',                       'bidi', set()),
    ('ml-ok: island continuation',    '$\\text{שלום\n\\en{ok}} x$',                      'bidi', set()),
    # ---- UNDEFINED-COMMON-MACRO ---------------------------------------------
    ('undef: enquote',                'כתב \\enquote{שלום} כאן.',                        'bidi', {'UNDEFINED-COMMON-MACRO'}),
    ('undef: SI',                     'מרחק \\SI{5}{\\meter} נמדד.',                     'bidi', {'UNDEFINED-COMMON-MACRO'}),
    ('undef: qtyrange form',          'טווח \\qtyrange{10}{20}{\\kilo\\meter} כאן.',     'bidi', {'UNDEFINED-COMMON-MACRO'}),
    ('undef: unit form',              'יחידות \\unit{\\meter\\per\\second} כאן.',        'bidi', {'UNDEFINED-COMMON-MACRO'}),
    ('undef-ok: definition line',     '\\providecommand{\\SI}[2]{#1\\,#2}',              'bidi', set()),
    ('undef: inside macro body',      '\\newcommand{\\myqty}{\\SI{5}{\\meter} בקירוב}',  'bidi', {'UNDEFINED-COMMON-MACRO'}),
    ('undef-ok: defined then used',   '\\providecommand{\\SI}[2]{#1\\,#2}\nמרחק \\SI{5}{\\meter} נמדד.', 'bidi', set()),
    ('undef-ok: package loaded',      '\\usepackage{siunitx}\nמרחק \\SI{5}{\\meter} נמדד.', 'bidi', set()),
    ('undef-ok: lookalikes',          'נוסחה $\\sin\\theta+\\sigma_x\\sim\\angle$ ו-\\sgn.', 'bidi', set()),
    ('undef-ok: verbatim body',       '\\begin{verbatim}\n\\SI{5}{\\meter} \\enquote{x}\n\\end{verbatim}', 'bidi', set()),
    # v3.59: wrapped in asmblock — the listing body is still what this case tests
    # (a macro inside a listing is exempt from UNDEFINED-COMMON-MACRO), but an
    # UNWRAPPED listing is itself a defect now (LISTING-OUTSIDE-LTR-ISLAND), so the
    # fixture is made doctrine-conformant rather than the new rule suppressed.
    ('undef-ok: lstlisting body',     '\\begin{asmblock}\n\\begin{lstlisting}\n# uses \\SI{5}{m} literally\n\\end{lstlisting}\n\\end{asmblock}', 'bidi', set()),
    # ---- legacy rules: the v3.22 repro set ----------------------------------
    ('legacy: \\en island + math',    'ולכן \\en{hit time}$=1$ מתקבל.',                  'bidi', {'ISLAND-NEXT-TO-MATH'}),
    ('legacy-ok: documented arrow fix', 'העבר את \\en{\\code{Rt}$\\to$\\code{ForwardB}} בצנרת.', 'bidi', set()),
    ('legacy: bare \\h in \\(..\\)',  'נגדיר את הגודל \\(\\h{מהירות}\\) ונמשיך.',        'bidi', {'LANG-RAW-IN-MATH'}),
    ('legacy-ok: \\h in intertext',   '\\begin{align}\nx &= 1\\\\\n\\intertext{\\h{הנחת היסוד} כאן}\ny &= 2\n\\end{align}', 'bidi', set()),
    ('legacy-ok: comment after \\\\%', 'אחד & שתיים \\\\% TODO ``old quotes`` and \\SI{5}{m}\nשלוש & ארבע \\\\', 'bidi', set()),
    ('legacy-ok: escaped \\$ heading', '\\section{עלות התוכנית ב-\\$ לחודש}',            'bidi', set()),
    ('legacy: math in heading',       '\\section{פעימת $\\pi$ כאן}',                     'bidi', {'MATH-IN-HEADING'}),
    ('legacy: axis end-then-begin',   '\\begin{tikzpicture}\n\\end{axis}\\begin{axis}[w]\n\\end{tikzpicture}', 'bidi', {'AXIS-EXTRA-END', 'AXIS-NO-END'}),
    ('legacy: 2-level island nesting', 'ולכן \\en{\\textbf{\\code{hit}}}$=1$ מיד.',      'bidi', {'ISLAND-NEXT-TO-MATH'}),
    # ---- v3.44: MATH-ENDS-IN-OP-BEFORE-ISLAND (r03 exercise-4, adjacency) ----
    ('opisl: math-ends-= then code',  'משווים לחסם $4(2^{15}{-}1)=$\\code{0x0001FFFC}; עוד.', 'bidi', {'MATH-ENDS-IN-OP-BEFORE-ISLAND'}),
    ('opisl: arrow then code',        'ההקשר \\code{Rt}$\\to$\\code{ForwardB} מחייב עצירה.', 'bidi', {'MATH-ENDS-IN-OP-BEFORE-ISLAND', 'HEBREW-FLOW-ARROW', 'ISLAND-NEXT-TO-MATH'}),
    ('opisl-ok: fixed, code first',   'משווים לחסם \\code{0x0001FFFC}, שהוא $4(2^{15}{-}1)$; עוד.', 'bidi', set()),
    ('opisl-ok: merged, op in \\en',  'הסיכון \\en{\\code{sub}$\\to$\\code{and}} שאינה קיימת.', 'bidi', set()),
    # v4.1.3: DECISION REVERSED. This shape was 'ok' because BIDI-24 judged it
    # layout-dependent (the same pattern rendered correctly elsewhere), so a
    # checker was rejected and the ban lived in guidance only. Guidance did not
    # hold: the first sweep after writing the rule found 14 live sites in 4
    # collections, and a reader hit one in shipped output. The rule does not
    # claim 'this always tears' — it enforces a shape the repo already forbids
    # ('לעולם אל תפתח מתמטיקה ב־= אחרי תווית') and whose fix is free.
    ('opisl: spaced island then =',  'נניח \\en{hit time} $=1$ מחזור בלבד.',   'bidi', {'ISLAND-BEFORE-OP-MATH'}),
    ('opisl-ok: eq after gloss',      'האי-כיוונון \\en{(detuning)} $\\Delta=\\omega-\\omega_0$ קטן.', 'bidi', set()),
    # ---- v3.46: MATH-WRAPPED-EQREF (qc-exams pp.41-43, render-gate R4 catch) ----
    ('eqref: $-wrapped in prose',     'הצבה במשוואה $\\eqref{eq:a}$ נותנת תוצאה.',       'bidi', {'MATH-WRAPPED-EQREF'}),
    ('eqref: \\(..\\)-wrapped',       'הצבה במשוואה \\(\\eqref{eq:a}\\) נותנת תוצאה.',   'bidi', {'MATH-WRAPPED-EQREF'}),
    ('eqref: inside display body',    '\\[ x=1 \\quad \\eqref{eq:a} \\]',                'bidi', {'MATH-WRAPPED-EQREF'}),
    ('eqref-ok: bare in prose',       'הצבה במשוואה \\eqref{eq:a} נותנת תוצאה.',         'bidi', set()),
    ('eqref-ok: after closed math',   'נציב $x=2$ ואת \\eqref{eq:a} יחד.',               'bidi', set()),
    # ---- v3.46: BARE-IDENT \text- evasion (qc-exams e20a_q2) -------------------
    ('barext: word$\\text- glued',    'שקולה לשער controlled$\\text-(Z_1Z_2)=$ הלאה.',   'bidi', {'BARE-IDENT-NEXT-TO-MATH'}),
    ('barext: second form',           'שער controlled$\\text-Z_1$ בודד.',                'bidi', {'BARE-IDENT-NEXT-TO-MATH'}),
    ('barext-ok: merged island',      'שער \\en{controlled-$(Z_1Z_2)$ = controlled-$Z_1$} כאן.', 'bidi', set()),
    # ---- v3.46: BOXED-HEBREW-SEGMENTS (qc-exams reader report + 8-variant lab) --
    ('boxheb: two segments',          '\\[ \\finalans{\\;\\text{עבור }X:\\ \\text{מזהה שגיאה}\\;} \\]', 'bidi', {'BOXED-HEBREW-SEGMENTS', 'HEBREW-MATH-GLUED-OBJECT'}),
    ('boxheb: trailing space',        '\\[ \\finalans{\\text{מספר הפעלות }f = 1} \\]',   'bidi', {'BOXED-HEBREW-SEGMENTS'}),
    ('boxheb: edge colon',            '\\[ \\finalans{\\;\\text{שני קיוביטי עזר:}\\ a_1\\to S_Z\\;} \\]', 'bidi', {'BOXED-HEBREW-SEGMENTS'}),
    ('boxheb: digit glued',           '\\[ \\finalans{\\;X=Y \\quad 3\\ \\text{שערים}\\;} \\]', 'bidi', {'BOXED-HEBREW-SEGMENTS'}),
    ('boxheb: butted, no space',      '\\[ \\boxed{\\text{מספר הפעלות}f = 1} \\]',       'bidi', {'BOXED-HEBREW-SEGMENTS'}),
    ('boxheb-ok: one \\h unit',       '\\[ \\finalans{\\text{\\h{מזהה שגיאה בודדת, מתקן אפס}}} \\]', 'bidi', set()),
    ('boxheb-ok: nested math in \\h', '\\[ \\finalans{\\text{\\h{מספר ההפעלות של $f$: אחת}}} \\]', 'bidi', set()),
    ('boxheb-ok: math only',          '\\[ \\finalans{\\;a_1\\to S_Z=Z_1Z_2\\;} \\]',    'bidi', set()),
    ('boxheb-ok: spaced annotation',  '\\[ \\finalans{\\;P(n,t)=P(n,0)\\quad\\text{(קבוע בזמן)}\\;} \\]', 'bidi', set()),
    ('boxheb-ok: cases cells',        '$\\finalans{\\text{\\en{msg}}=\\begin{cases}0&\\text{כל זהים}\\\\1&\\text{יש שונות}\\end{cases}}$', 'bidi', set()),
    # ---- v3.47: HEBREW-MATH-GLUED-OBJECT (non-boxed sibling of BOXED-HEBREW) ------
    #      render-proven: a \text{Hebrew ...} in math glued to its bound atom lands
    #      on the wrong side. 4 of these were MISSED by every gate before v3.47.
    ('glued: var after \\text',       '\\[ \\alpha=\\Pr(\\text{דחיית }H_0 \\mid H_0) \\]', 'bidi', {'HEBREW-MATH-GLUED-OBJECT'}),
    ('glued: tuple after \\text',     '\\[ 15 \\quad\\text{צירופי }(m,d). \\]',            'bidi', {'HEBREW-MATH-GLUED-OBJECT'}),
    ('glued: maqaf + var',            '\\[ \\underbrace{15}_{\\text{שונות רמת־}X} \\]',    'bidi', {'HEBREW-MATH-GLUED-OBJECT'}),
    ('glued: sandwiched number',      '\\[ 21\\ \\text{שעות ו־}6.67\\ \\text{דקות} \\]',   'bidi', {'HEBREW-MATH-GLUED-OBJECT'}),
    ('glued: arrow-label var',        '\\[ \\underbrace{B}_{\\uparrow\\text{ עם }r} \\]',  'bidi', {'HEBREW-MATH-GLUED-OBJECT'}),
    ('glued-ok: new-clause subject',  '\\[ \\text{ובאותו אופן }\\ \\bar\\psi_{R}=\\bar\\psi P_L \\]', 'bidi', set()),
    ('glued-ok: arrow subject',       '\\[ \\text{ובאותו אופן }\\ \\bar\\psi_{L}\\ \\to\\ Q \\]', 'bidi', set()),
    ('glued-ok: sanctioned \\h unit', '\\[ \\Pr(\\text{\\h{דחיית $H_0$}} \\mid H_0) \\]',  'bidi', set()),
    ('glued-ok: maqaf+terminal num',  '$x=\\text{ב־}3$',                                   'bidi', set()),
    ('glued-ok: number before text',  '$3\\ \\text{מילים}$',                               'bidi', set()),
    # ---- v3.47: HEBREW-DOUBLE-HYPHEN — $-flanked and \text{--} blind spots --------
    ('dash: $..$--$..$ islands',      'עקומת $I_D$--$V_G$ נמדדת.',                          'bidi', {'HEBREW-DOUBLE-HYPHEN'}),
    ('dash: \\text{--} in math',      '$0.3\\text{--}3\\times10^{-10}$',                   'bidi', {'HEBREW-DOUBLE-HYPHEN'}),
    ('dash-ok: {--} cell marker',     '\\texttt{and} & \\textcolor{cRed}{--} & IF',        'bidi', set()),
    ('dash-ok: single $-$ between',   'עקומת $I_D$-$V_G$ נמדדת.',                           'bidi', set()),
    # ---- v3.47: REDUNDANT-EQREF-PARENS -------------------------------------------
    ('eqrefp: (\\eqref{}) double',    'ויעילות (\\eqref{eq:x}) אך מאריכה.',                'bidi', {'REDUNDANT-EQREF-PARENS'}),
    ('eqrefp-ok: bare \\eqref',       'ראה \\eqref{eq:x} להלן.',                           'bidi', set()),
    ('eqrefp-ok: (\\ref{}) single',   'ראה (\\ref{fig:y}) לעיל.',                          'bidi', set()),
    # ---- v3.48: UNESCAPED-PERCENT — a comment '%' glued to content eats the rest
    #      of the line SILENTLY (content vanishes from the PDF; no compile warning) --
    ('pct: digit% eats content',      'שיעור ההצלחה הוא 30% מהמקרים שנבדקו.',              'bidi', {'UNESCAPED-PERCENT'}),
    ('pct: glued %  5%3',             'הערך שלנו 5%3 בקירוב סופי.',                        'bidi', {'UNESCAPED-PERCENT'}),
    ('pct-ok: escaped \\%',           'שיעור ההצלחה הוא 30\\% מהמקרים שנבדקו.',            'bidi', set()),
    ('pct-ok: real comment (space)',  'טקסט תקין % הערה אמיתית כאן.',                      'bidi', set()),
    ('pct-ok: line-start comment',    '% שורת הערה שלמה מתחילת השורה.',                    'bidi', set()),
    ('pct-ok: foo% line-break',       'סוף פסקה עם השהיית־רווח foo%',                      'bidi', set()),
    ('legacy: adjacent islands',      'ספרים: \\en{Griffiths}, \\en{Thomson} כאן.',      'bidi', {'ADJACENT-LTR-ISLANDS'}),
    ('legacy-ok: merged island',      'ספרים: \\en{Griffiths, Thomson} כאן.',            'bidi', set()),
    ('legacy: quotes',                'ציטוט ``שגוי`` כאן.',                             'bidi', {'QUOTES'}),
    ('legacy-ok: gershayim',          'ציטוט ״נכון״ כאן.',                               'bidi', set()),
    # ---- charset -------------------------------------------------------------
    ('charset: Arabic confusable',    'מילה עם ر ערבית.',                                'charset', {'STRAY'}),
    ('charset: cantillation tofu',    'טעם ל֑א כאן.',                                    'charset', {'STRAY'}),
    ('charset: bidi control mark',    'סימן ‏ נסתר.',                               'charset', {'STRAY'}),
    ('charset-ok: degree+sheqel',     'זווית 45° ומחיר 100₪.',                           'charset', set()),
    ('charset-ok: maqaf+gershayim',   'אור־חומר ו״ציטוט״ וגרש ג׳יינס וניקוד קָמָץ.',      'charset', set()),
    ('charset-ok: dashes',            'קו — ארוך ו-– טווח.',                             'charset', set()),
    ('charset-ok: comment glyph',     'טקסט תקין. % הערה עם ★ בפנים',                    'charset', set()),
    # ---- v3.25: PAREN-ONLY-ISLAND / arrow-only \en / \eqref range ------------
    ('paren-island: \\en{(}heb\\en{)}', 'חומרה \\en{(TLB)} ותוכנה \\en{(}טבלת עמודים\\en{)}, בעמודים.', 'bidi', {'PAREN-ONLY-ISLAND'}),
    ('paren-island-ok: plain parens',  'חומרה \\en{(TLB)} ותוכנה (טבלת עמודים), בעמודים.', 'bidi', set()),
    ('arrow-island: \\en{$\\to$} between Hebrew', 'הוא ״בדוק סיבית \\en{$\\to$} הזז״ וממשיך.', 'bidi', {'HEBREW-FLOW-ARROW'}),
    ('arrow-island-ok: operands inside', 'העברה \\en{\\code{Rt}$\\to$\\code{ForwardB}} תקינה כאן.', 'bidi', set()),
    ('refdash: \\eqref{}--\\eqref{}',  'הזמן, לפי \\eqref{eq:a}--\\eqref{eq:b} עם ערכים:', 'bidi', {'HEBREW-DOUBLE-HYPHEN', 'REF-RANGE-REORDER'}),
    # v3.57 CORRECTION: this case used to expect CLEAN for the typed en-dash form,
    # i.e. it asserted the bug was correct — the same wrong assertion that sat in
    # tests/lint_negatives.tex:24. Measured by glyph geometry, the bare form
    # renders "(1.2)–(1.1)": the numbers REVERSED. Typing – only silenced
    # HEBREW-DOUBLE-HYPHEN; it did not fix anything. The merged island is the fix.
    ('refdash: en-dash typed REVERSES', 'הזמן, לפי \\eqref{eq:a}–\\eqref{eq:b} עם ערכים:', 'bidi', {'REF-RANGE-REORDER'}),
    ('refdash-ok: merged island',      'הזמן, לפי \\en{\\eqref{eq:a}–\\eqref{eq:b}} עם ערכים:', 'bidi', set()),
    # ---- v3.26: HEBREW-BEFORE-OP-MATH / DERIVATION-CHAIN ---------------------
    ('opmath: heb then $=4$',         'בלוק $=4$ בתים במטמון.',                        'bidi', {'HEBREW-BEFORE-OP-MATH'}),
    ('opmath: heb then approx',       'בטמפרטורה גבוהה מוסיף $\\approx85$ מעלות.',    'bidi', {'HEBREW-BEFORE-OP-MATH'}),
    ('opmath-ok: plain-text =',       'בלוק = $4$ בתים, מוסיף כ־$85$ ולפחות $m$ תצפיות.', 'bidi', set()),
    ('opmath-ok: bare $=$ / x=4',     'הסימן $=$ מציין שוויון; נוסחה $x=4$ מתחילה במשתנה.', 'bidi', set()),
    ('chain: 2 arrows 3 maths',       'בלוק = $4$ $\\Leftarrow$ היסט $2$ ביט $\\Leftarrow$ נותר $8$ ביט.', 'density', {'DERIVATION-CHAIN'}),
    ('chain-ok: one step',            'בלוק = $4$ בתים ולכן ההיסט $2$ ביט — עובדה אחת בשורה.', 'density', set()),
    # ---- v3.28: OVER-BOX-EMPHASIS (emphasis boxes are a ~10-15% budget) ------
    ('overbox: mostly emphasis boxes', '\\begin{defbox}[frametitle={מושג}]\nהגדרה.\nעוד הרחבה בקופסה.\n\\end{defbox}\nשורת פרוזה.', 'density', {'OVER-BOX-EMPHASIS'}),
    ('overbox-ok: exbox is format',    '\\begin{exbox}[frametitle={תרגיל}]\nשאלה.\nפתרון מלא.\n\\end{exbox}\nמשפט סיום.', 'density', set()),
    ('overbox-ok: boxes are minority', '\\begin{keybox}[frametitle={רעיון}]\nשורה.\n\\end{keybox}\nפרוזה א.\nפרוזה ב.\nפרוזה ג.\nפרוזה ד.', 'density', set()),
    # v3.43.0 — BOX-FRICTION (reader report #5: the crammed lecture-times box).
    # The wall SIGNATURE is inline structure-citizens: a unit-value list, an
    # arrow CHAIN in one math run, or a numeric sum — with no display inside.
    ('boxfric: unit-values+chain+sum', '\\begin{exbox}[frametitle={דוגמה}]\nזמני הרכיבים סומנו: פקודות \\en{2ns}, אוגרים \\en{3ns}, חישוב \\en{2ns},\nנתונים \\en{3ns}, בורר \\en{1ns} וגם \\en{0.5ns} קידום. המסלול הארוך:\n$A \\to B \\to C \\to D$, בסכום\n$0.5+2+3+2 = 7.5$ ובקירוב.\n\\end{exbox}', 'density', {'BOX-FRICTION'}),
    ('boxfric: inline numbered items', '\\begin{exbox}[frametitle={תרגיל}]\nנתונים שלושה מעבדים עם תדרים שונים למדידה.\n\\textbf{(1)} לאיזה מעבד הביצועים הטובים ביותר? \\textbf{(2)} מה זמן\nהריצה של כל מעבד? \\textbf{(3)} כמה מחזורים לוקח לכל מעבד?\n\\end{exbox}', 'density', {'BOX-FRICTION'}),
    ('boxfric-ok: enumerate items',    '\\begin{exbox}[frametitle={תרגיל}]\nנתונים שלושה מעבדים עם תדרים שונים למדידה.\n\\begin{enumerate}\n\\item[(\\textbf{1})] לאיזה מעבד הביצועים הטובים ביותר?\n\\item[(\\textbf{2})] מה זמן הריצה של כל מעבד?\n\\item[(\\textbf{3})] כמה מחזורים לוקח לכל מעבד?\n\\end{enumerate}\n\\end{exbox}', 'density', set()),
    ('boxfric-ok: display inside',     '\\begin{exbox}[frametitle={דוגמה}]\nזמני הרכיבים סומנו:\n\\begin{center}\n\\en{IMEM 2ns,\\quad Reg 3ns,\\quad ALU 2ns,\\quad MEM 3ns,\\quad mux 1ns,\\quad PC 0.5ns}\n\\end{center}\nהמסלול הארוך:\n\\begin{center}\n$A \\to B \\to C \\to D$\\\\[3pt]\n$0.5+2+3+2 = 7.5$\n\\end{center}\nולכן זמן המחזור נקבע כאן.\n\\end{exbox}', 'density', set()),
    ('boxfric-ok: prose w/ scattered arrows', '\\begin{notebox}[frametitle={תיקון}]\nבמקור נכתב $r=v/u$ אך אגף ימין הוא מהירות. בגבול $\\mu\\to\\infty$\nמתקבל $v\\to u$ ולכן $r\\to 1$, כנדרש בתנועה בליסטית מלאה, וזה\nמתקן את אי־העקביות ביחידות של השקף המקורי.\n\\end{notebox}\nפרוזה מדללת שורה 1 לשמירת יחס הקופסאות מתחת לתקציב.\nפרוזה מדללת שורה 2 לשמירת יחס הקופסאות מתחת לתקציב.\nפרוזה מדללת שורה 3 לשמירת יחס הקופסאות מתחת לתקציב.\nפרוזה מדללת שורה 4 לשמירת יחס הקופסאות מתחת לתקציב.\nפרוזה מדללת שורה 5 לשמירת יחס הקופסאות מתחת לתקציב.\nפרוזה מדללת שורה 6 לשמירת יחס הקופסאות מתחת לתקציב.\nפרוזה מדללת שורה 7 לשמירת יחס הקופסאות מתחת לתקציב.\nפרוזה מדללת שורה 8 לשמירת יחס הקופסאות מתחת לתקציב.\nפרוזה מדללת שורה 9 לשמירת יחס הקופסאות מתחת לתקציב.\nפרוזה מדללת שורה 10 לשמירת יחס הקופסאות מתחת לתקציב.', 'density', set()),
    ('boxfric-ok: charges not a sum',  '\\begin{notebox}[frametitle={הערה}]\nהתהליך $e^{+}e^{-}\\to\\mu^{+}\\mu^{-}$ שקול בסימנים לתהליך המצומד,\nוסימני המטען כאן הם כתביות־על ולא אופרטורים של סכום מספרי,\nולכן הקופסה הזו קוראת כפרוזה תקינה לגמרי בעברית.\n\\end{notebox}\nפרוזה מדללת שורה 1 לשמירת יחס הקופסאות מתחת לתקציב.\nפרוזה מדללת שורה 2 לשמירת יחס הקופסאות מתחת לתקציב.\nפרוזה מדללת שורה 3 לשמירת יחס הקופסאות מתחת לתקציב.\nפרוזה מדללת שורה 4 לשמירת יחס הקופסאות מתחת לתקציב.\nפרוזה מדללת שורה 5 לשמירת יחס הקופסאות מתחת לתקציב.\nפרוזה מדללת שורה 6 לשמירת יחס הקופסאות מתחת לתקציב.\nפרוזה מדללת שורה 7 לשמירת יחס הקופסאות מתחת לתקציב.\nפרוזה מדללת שורה 8 לשמירת יחס הקופסאות מתחת לתקציב.\nפרוזה מדללת שורה 9 לשמירת יחס הקופסאות מתחת לתקציב.\nפרוזה מדללת שורה 10 לשמירת יחס הקופסאות מתחת לתקציב.', 'density', set()),
    # ---- v3.29: box_balance one-line-box fix (proven double inversion: a
    # one-line box left the depth counter stuck -> 93%-style FP on exemplary
    # pages; content written on the \begin line was never counted -> 0% FN)
    ('overbox-ok: one-line box not sticky', '\\begin{notebox}[frametitle={x}]הערה קצרה.\\end{notebox}\nפרוזה א.\nפרוזה ב.\nפרוזה ג.\nפרוזה ד.\nפרוזה ה.\nעוד פרוזה ו.\nעוד פרוזה ז.\nעוד פרוזה ח.', 'density', set()),
    ('overbox: content on begin lines', '\\begin{defbox}[frametitle={א}]כל תוכן ההגדרה יושב כאן בשורת הפתיחה.\n\\end{defbox}\n\\begin{keybox}[frametitle={ב}]וגם כאן כל התוכן דחוס בקופסה עצמה.\n\\end{keybox}\nשורת פרוזה בודדת.', 'density', {'OVER-BOX-EMPHASIS'}),
    # ---- v3.27: COLON-TRAPPED-IN-ISLAND (prose mirror of MATH-TEXT-EN-COLON) -
    ('trapped-colon: item label',     '\\item[\\textbf{\\en{Offset:}}] בלוק = $4$ בתים.',  'bidi', {'COLON-TRAPPED-IN-ISLAND'}),
    ('trapped-colon: mid-prose',      'איור \\en{1a:} העקומה הלינארית חותכת בציר.',        'bidi', {'COLON-TRAPPED-IN-ISLAND'}),
    ('trapped-colon-ok: colon outside', '\\item[\\textbf{\\en{Offset}:}] בלוק = $4$ בתים.', 'bidi', set()),
    ('trapped-colon-ok: internal colon', 'ראו \\en{Note: caching} בהמשך הפרק.',             'bidi', set()),
    ('trapped-colon-ok: no Hebrew after', 'node {\\en{Total:}}',                            'bidi', set()),
    ('trapped-colon-ok: cell boundary',  '\\en{Total:} & ערך בתא נפרד \\\\',                'bidi', set()),
    ('trapped-colon-ok: math text form', '$x \\quad \\text{\\en{rate:}} y$ מופיע בעברית.',  'bidi', set()),
    # ---- v3.29: the paragraph pass — cross-line forms of the adjacency rules -
    # (a source newline is a space in TeX; every positive here renders exactly
    # as broken as its same-line twin — proven on compiled pages, 26 instances
    # shipped in 8 lakits before the sweep)
    ('xline: adjacent islands',       'הקבצים נקראים \\en{Alpha},\n\\en{Beta} ושניהם נטענים.', 'bidi', {'ADJACENT-LTR-ISLANDS'}),
    ('xline: adjacent code islands',  'ערכים \\code{a=1},\n\\code{b=2} בהתאמה.',         'bidi', {'ADJACENT-LTR-ISLANDS'}),
    ('xline: heb before op-math',     'גודל של בלוק\n$=4$ בתים בדיוק.',                  'bidi', {'HEBREW-BEFORE-OP-MATH'}),
    ('xline: trapped colon',          'השדה \\en{Offset:}\nמספר הבתים מתחילת הבלוק.',    'bidi', {'COLON-TRAPPED-IN-ISLAND'}),
    ('xline-ok: Hebrew between islands', 'קובץ \\en{Alpha},\nוגם קובץ \\en{Beta} נטען.',  'bidi', set()),
    ('xline-ok: math starts with var', 'הערך המתקבל הוא\n$x=4$ בקירוב.',                 'bidi', set()),
    ('xline-ok: leftarrow flow',      'שלב ראשון\n$\\leftarrow$ עדכון המשקלים.',          'bidi', set()),
    ('xline-ok: colon then Latin',    '\\en{Offset:}\nEnglish continues here only.',      'bidi', set()),
    ('xline-ok: row boundary',        'תא ראשון \\en{Total:} \\\\\nעברית בשורה הבאה \\\\', 'bidi', set()),
    ('xline-ok: blank line = new paragraph', 'רשימה עם \\en{Alpha},\n\nפסקה חדשה \\en{Beta} כאן.', 'bidi', set()),
    # ---- v3.29: trapped-punctuation family (proven by render: ; ! ? orphan
    # exactly like the colon; \code/\texttt behave like \en; one nesting level)
    ('punct: semicolon in island',    'ההוראה \\en{halt;} עוצרת את המעבד.',              'bidi', {'COLON-TRAPPED-IN-ISLAND'}),
    ('punct: question in island',     'השאלה \\en{why not RISC?} נענית בפרק.',           'bidi', {'COLON-TRAPPED-IN-ISLAND'}),
    ('punct: nested island colon',    'השדה \\en{\\code{Offset}:} מספר הבתים.',          'bidi', {'COLON-TRAPPED-IN-ISLAND'}),
    ('punct-ok: internal punctuation', 'ראו \\en{Note: caching; details} בהמשך הפרק.',   'bidi', set()),
    ('punct-ok: trailing comma unproven', 'ההוראות \\code{add,} וגם אחרות משנות מצב.',   'bidi', set()),
    # \code/\texttt exempt by measurement: their trailing punct is token content
    # (a C statement's ';', an asm label's ':') — 8 FPs on reviewed pages, 0 TPs
    ('punct-ok: code statement semicolon', 'הקוד \\code{A = B + E; C = B + F;} כאשר מתורגם.', 'bidi', set()),
    ('punct-ok: code asm label colon',     'התווית \\code{loop:} מסמנת את תחילת הלולאה.',     'bidi', set()),
    ('opisland-ok: code operator mention', 'הסף הוא \\code{>= 90} ולא \\code{==} כמצופה.',    'bidi', set()),
    # frametitle content renders in the TITLE BAR — no adjacency with the body
    ('punct-ok: island in frametitle', '\\begin{notebox}[frametitle={\\en{Nothing can fix it!}}] אופטימיזציות בהמשך.', 'bidi', set()),
    # ---- v3.29: HEBREW-BEFORE-OP-MATH extensions — \(..\) form + op-initial island
    ('opmath: paren-math form',       'גודל בלוק \\(=4\\) בתים.',                        'bidi', {'HEBREW-BEFORE-OP-MATH'}),
    ('opmath-ok: bare paren-math op', 'הסימן \\(=\\) מציין שוויון בלבד.',                'bidi', set()),
    ('opisland: leading = in island', 'גודל בלוק \\en{= 4 bytes} בדיוק.',                'bidi', {'HEBREW-BEFORE-OP-MATH'}),
    ('opisland-ok: bare op island',   'הסימן \\en{=} מציין שוויון.',                     'bidi', set()),
    # ---- v3.29: island--island dash ranges (literal hyphens + the swap) ------
    ('islanddash: en--en',            'צומת \\en{p}--\\en{n} קבורה.',                    'bidi', {'HEBREW-DOUBLE-HYPHEN', 'ADJACENT-LTR-ISLANDS'}),
    ('islanddash: endash still swaps', 'חלקים \\en{V}–\\en{VI} קובעים.',                 'bidi', {'ADJACENT-LTR-ISLANDS'}),
    ('islanddash: code range',        'רגיסטרים \\code{\\$f0}--\\code{\\$f31} בזוגות.',  'bidi', {'HEBREW-DOUBLE-HYPHEN', 'ADJACENT-LTR-ISLANDS'}),
    ('islanddash-ok: merged range',   'חלקים \\en{VI–VIII} קובעים את הכיוון.',           'bidi', set()),
    ('islanddash-ok: island then em-dash', 'המושג \\en{pipeline} — צנרת — מרכזי כאן.',   'bidi', set()),
    # ---- heading robustness: inline \code is safe; block/fragile content is not
    ('codehead-ok: \\section + \\code', '\\section{הפקודה \\code{grep} בשימוש}',          'bidi', set()),
    ('codehead: \\subsection + \\codeline', '\\subsection{שורת \\codeline{make all} כאן}', 'bidi', {'BLOCK-IN-HEADING'}),
    ('codehead-ok: starred heading',   '\\subsection*{הפקודה \\code{grep} בשימוש}',       'bidi', set()),
    ('codehead-ok: texorpdfstring',    '\\section{הפקודה \\texorpdfstring{\\code{grep}}{grep} בשימוש}', 'bidi', set()),
    ('codehead-ok: optional arg',      '\\section[grep]{הפקודה \\code{grep} בשימוש}',     'bidi', set()),
    ('codehead-ok: texttt survives',   '\\section{הפקודה \\texttt{grep} בשימוש}',         'bidi', set()),
    # ---- v3.30: CODE-UNSAFE-CHAR (\code is NOT verbatim; ~ vanishes SILENTLY)
    ('codechar: unescaped ~ and &',    'הרץ \\code{cd ~/proj && make} ואז המשך.',         'bidi', {'CODE-UNSAFE-CHAR'}),
    ('codechar: % eats the brace',     'ההערה \\code{x = 1; % init} בשורה.',              'bidi', {'CODE-UNSAFE-CHAR'}),
    ('codechar: unpaired $ and _',     'המשתנה \\code{$PATH_DIR} בסביבה.',                'bidi', {'CODE-UNSAFE-CHAR'}),
    ('codechar: #define literal',      'המאקרו \\code{#define MAX} בכותרת.',              'bidi', {'CODE-UNSAFE-CHAR'}),
    ('codechar-ok: escaped forms',     'הרץ \\code{cd \\textasciitilde/proj \\&\\& make \\$5 a\\_b \\^{}2 100\\%} כעת.', 'bidi', set()),
    ('codechar-ok: balanced math idiom', 'הקיוביט \\code{Q$_0$} והקיוביט \\code{Q$_{1}$} בזוג.', 'bidi', set()),
    ('codechar-ok: macro param #1',    '\\newcommand{\\myline}[1]{\\codeline{#1}}',       'bidi', set()),
    ('codechar-ok: group in comment',  'טקסט תקין כאן. % TODO: \\code{cd ~/x} later',     'bidi', set()),
    # ---- v3.30: QUOTES also fires in English context (tlig never fires ->
    # literal backticks in ANY font context; measured in example_math citation)
    ('quotes: english context',        '\\begin{otherlanguage}{english}\nSee ``Quantum Computer Science'' (2007).\n\\end{otherlanguage}', 'bidi', {'QUOTES'}),
    ('quotes: same line as \\en',      'הספר \\en{``Feynman Lectures``} מומלץ.',          'bidi', {'QUOTES'}),
    ('quotes-ok: typed curly quotes',  '\\begin{otherlanguage}{english}\nSee “Quantum Computer Science” (2007).\n\\end{otherlanguage}', 'bidi', set()),
    # ---- v3.31: adversarial-audit lock — 9 FN + 4 FP, each proven by compile/
    # render BEFORE the checker changed (scratchpad audit2/evasion fixtures)
    ('codehead31-ok: heading wraps line', '\\section{הקדמה לפונקציית\nה־\\code{malloc} בשפת סי}', 'bidi', set()),
    ('codehead31-ok: texorpdf plus code', '\\section{\\texorpdfstring{$O(n)$}{O(n)} והפונקציה \\code{qsort}}', 'bidi', set()),
    ('codehead31-ok: space before brace', '\\section {הפונקציה \\code{main} בסי}',           'bidi', set()),
    ('codehead31-ok: run-in paragraph', '\\paragraph{דוגמה} הפונקציה \\code{free} משחררת זיכרון.', 'bidi', set()),
    ('codehead31-ok: code after closed heading', '\\section{מבוא} ראשית נגדיר את \\code{main} כנקודת הכניסה.', 'bidi', set()),
    ('codechar31: group spans lines',  'טקסט עברי עם \\code{some_long\nidentifier} בפנים ועוד טקסט.', 'bidi', {'CODE-UNSAFE-CHAR'}),
    ('codechar31: 2-level nested ~',   'אתחול המסכות: \\code{m = {{~0, 0}}} וזה הכול.',    'bidi', {'CODE-UNSAFE-CHAR'}),
    ('codechar31: & inside $span$',    'הביטוי \\code{$a&b$} מופיע בקוד.',                 'bidi', {'CODE-UNSAFE-CHAR'}),
    ('quotes31: single backtick',      'העברית משתמשת במונח \\en{the `word idiom} בטקסט.', 'bidi', {'QUOTES'}),
    ('quotes31-ok: empty string in code', "מאתחלים מחרוזת ריקה: \\code{s = ''} וממשיכים.", 'bidi', set()),
    ('quotes31-ok: md backticks in code', 'בתחביר מרקדאון כותבים \\code{``kwargs``} לסימון.', 'bidi', set()),
    ('quotes31-ok: math double-prime', "הנגזרת השנייה $f''(x)$ חיובית בקטע.",              'bidi', set()),
    ('xline31: comment-only line does not split paragraph', 'ההוראות \\en{Alpha},\n% הערת עורך: לוודא סדר\n\\en{Beta} מופיעות ברצף.', 'bidi', {'ADJACENT-LTR-ISLANDS'}),
    ('xline31-ok: blank line still splits', 'ההוראות \\en{Alpha},\n\n\\en{Beta} מופיעות ברצף.', 'bidi', set()),
    # ---- v3.34: MANUAL-FIG-CAPTION (\ref binds to ambient counter, prints the
    # wrong number — "איור 48" = equation 48; proven on a shipped page). Use
    # \figcap{} (the \tabcap twin).
    ('figcap34: manual gray caption',   '{\\centering\\small\\textcolor{cGray}{איור: \\label{fig:x}דיאגרמת פסים}\\par}', 'bidi', {'MANUAL-FIG-CAPTION'}),
    ('figcap34: manual numbered caption', 'ואז {\\small\\textcolor{cGray}{איור 3: חתך הערוץ}\\par} בהמשך.', 'bidi', {'MANUAL-FIG-CAPTION'}),
    ('figcap34-ok: \\figcap macro',     '\\end{tikzpic}\n\\figcap{\\label{fig:ok}דיאגרמת פסים של חתך לרוחב הערוץ}', 'bidi', set()),
    ('figcap34-ok: preamble \\thefig def', '{\\centering\\small\\textcolor{cGray}{\\textbf{איור~\\thefig.}}\\enspace תיאור}', 'bidi', set()),
    # ---- v3.36: LATIN-BEFORE-PAREN widened. The old rule required [A-Z]{2,}
    # + uppercase after the paren; "C (cstyle)" and "main (entry point)" broke
    # identically in the render and evaded. Precise condition (4-case render
    # matrix + 2 real corpus lines): breaks iff no Latin resumes after ")".
    ('latparen36: single letter',      'הסגנון C (cstyle) צבעוני מאוד.',                  'bidi', {'LATIN-BEFORE-PAREN'}),
    ('latparen36: lowercase word',     'הפונקציה main (entry point) רצה.',                'bidi', {'LATIN-BEFORE-PAREN'}),
    ('latparen36: comma then Hebrew',  'הסגנון C (cstyle), וממשיכים הלאה.',               'bidi', {'LATIN-BEFORE-PAREN'}),
    ('latparen36: sentence-final',     'ראה את הסגנון C (cstyle).',                        'bidi', {'LATIN-BEFORE-PAREN'}),
    ('latparen36-ok: Latin resumes',   'המודל Model (v2) update ממשיך בעברית.',           'bidi', set()),
    ('latparen36-ok: comma then Latin','פייתון ו-web scraping (BeautifulSoup), AUC, בהמשך.', 'bidi', set()),
    ('latparen36-ok: \\en-wrapped',    'הסגנון \\en{C (cstyle)} צבעוני.',                  'bidi', set()),
    ('latparen36-ok: no Hebrew (english block line)', 'You are performing Gradient Boosted Trees (GBT) with stumps.', 'bidi', set()),
    ('latparen36-ok: tikz coords',     '\\begin{tikzpicture}\n\\node at (axis cs:2.2,45){\\h{לינארי}};\n\\end{tikzpicture}', 'bidi', set()),
    ('latparen36-ok: texorpdfstring arg', '\\section{האם \\texorpdfstring{$\\sigma(u)=|u|$}{sigma(u)=|u|} אקטיבציה בעברית}', 'bidi', set()),
    ('latparen36-ok: inside code',     'הבנייה \\code{pd.DataFrame(data)} יוצרת טבלה.',    'bidi', set()),
    # ---- v4.14: LATIN-BEFORE-PAREN widened a second time (DEFECTS BIDI-79).
    # The v3.36 rule still demanded a LATIN LETTER as the first character inside
    # the paren, and scanned "(" only. Every POSITIVE below was measured on the
    # page first (glyph x-order: the pair prints "((" / "[[" instead of "()"),
    # and every NEGATIVE prints a correct "()" — the fix and the shapes that
    # were never broken are held apart by measurement, not by argument.
    ('latparen414: punctuation first', 'הסוכן מדווח Skill(/audit) ואז ממשיך.',            'bidi', {'LATIN-BEFORE-PAREN'}),
    ('latparen414: the shipped row',   'הסוכן מדווח “Skill(/audit)” ו־“Successfully loaded skill” כאן.', 'bidi', {'LATIN-BEFORE-PAREN'}),
    ('latparen414: dash first',        'ההתקנה npm(-g) היא גלובלית.',                     'bidi', {'LATIN-BEFORE-PAREN'}),
    ('latparen414: digit first',       'הפונקציה f(2) מחזירה ערך.',                        'bidi', {'LATIN-BEFORE-PAREN'}),
    ('latparen414: digits and comma',  'הנקודה v(1,2) נמצאת במישור.',                     'bidi', {'LATIN-BEFORE-PAREN'}),
    ('latparen414: square bracket',    'האיבר array[0] הוא הראשון.',                       'bidi', {'LATIN-BEFORE-PAREN'}),
    ('latparen414: bracket, punct first', 'הסוכן טוען Skill[/audit] כסקיל.',               'bidi', {'LATIN-BEFORE-PAREN'}),
    ('latparen414: digits then Hebrew','שלושת פורמטי ההוראה של MIPS (32 סיביות) כאן.',     'bidi', {'LATIN-BEFORE-PAREN'}),
    ('latparen414: textbf anchor',     'הסוכן מדווח \\textbf{Skill}(/audit) כאן.',          'bidi', {'LATIN-BEFORE-PAREN'}),
    ('latparen414: math inside parens','להוראות R-type ($\\text{ALUOp}=10$) — עבור זה.',    'bidi', {'LATIN-BEFORE-PAREN'}),
    ('latparen414: island elsewhere on the line', 'שדה ה־\\en{Index} בוחר שורה, ושדה ה־Data (32 ביט) מוחזר.', 'bidi', {'LATIN-BEFORE-PAREN'}),
    ('latparen414-ok: empty parens',   'הסוכן מדווח Skill() כאן.',                         'bidi', set()),
    ('latparen414-ok: Hebrew first inside', 'הסוכן מדווח audit(עברית) כאן.',               'bidi', set()),
    ('latparen414-ok: gershayim first','משתמשים ב־dirty bit (״Modified״) ב־PTE.',          'bidi', set()),
    ('latparen414-ok: maqaf first',    'משתמשים ב־bit (־Modified) כאן.',                   'bidi', set()),
    ('latparen414-ok: no Latin anchor','הכלי (Claude Code) פועל כאן.',                     'bidi', set()),
    ('latparen414-ok: no anchor, digits', 'המהדורה (2024) יצאה כאן.',                      'bidi', set()),
    ('latparen414-ok: no anchor, version', 'המהדורה (v2.0) יצאה כאן.',                     'bidi', set()),
    ('latparen414-ok: island holds the token', 'הסוכן מדווח \\en{Skill(/audit)} כאן.',      'bidi', set()),
    ('latparen414-ok: code island',    'הסוכן מדווח \\code{Skill(/audit)} כאן.',            'bidi', set()),
    ('latparen414-ok: island on the anchor', 'פורמטי ההוראה של \\en{MIPS} (32 סיביות) כאן.', 'bidi', set()),
    ('latparen414-ok: parens inside math', 'להוראות R-type $(\\text{ALUOp}=10)$ ועוד עברית.', 'bidi', set()),
    ('latparen414-ok: graphics option','טקסט עברי \\includegraphics[width=5cm]{fig} בהמשך.', 'bidi', set()),
    ('latparen414-ok: float placement','\\begin{figure}[htbp]\n\\centering טקסט עברי כאן.\n\\end{figure}', 'bidi', set()),
    # ---- v4.14.1: the ANCHOR was still fitted to its example. v4.14.0 required
    # the Latin letter bare or inside a \textbf whose content STARTS Latin, with
    # at most one space before the bracket. Every positive below was measured
    # broken on the page ("((" again) and evaded all of that; the first of them
    # shipped on page 33 of computer-architecture.
    ('latparen4141: textbf, Hebrew first', 'א \\textbf{גשר PCI} (PCI bridge) ואל זה.',     'bidi', {'LATIN-BEFORE-PAREN'}),
    ('latparen4141: emph wrapper',      'א \\emph{תג PCI} (PCI bridge) ואל זה.',            'bidi', {'LATIN-BEFORE-PAREN'}),
    ('latparen4141: h wrapper',         'א \\h{גשר PCI} (PCI bridge) ואל זה.',              'bidi', {'LATIN-BEFORE-PAREN'}),
    ('latparen4141: nested wrappers',   'א \\textbf{\\emph{גשר PCI}} (PCI bridge) ואל זה.', 'bidi', {'LATIN-BEFORE-PAREN'}),
    ('latparen4141: em-dash between',   'א \\textbf{גשר PCI} —(PCI bridge) ואל זה.',        'bidi', {'LATIN-BEFORE-PAREN'}),
    ('latparen4141: colon between',     'א \\textbf{גשר PCI}: (PCI bridge) ואל זה.',        'bidi', {'LATIN-BEFORE-PAREN'}),
    ('latparen4141-ok: island on the anchor', 'א \\textbf{גשר \\en{PCI}} (PCI bridge) ואל זה.', 'bidi', set()),
    ('latparen4141-ok: island on the aside',  'א \\textbf{גשר PCI} \\en{(PCI bridge)} ואל זה.', 'bidi', set()),
    ('latparen4141-ok: Hebrew anchor',  'א \\textbf{גשר} (PCI bridge) ואל זה.',             'bidi', set()),
    ('latparen4141-ok: code island anchor', 'א \\code{PCI} (PCI bridge) ואל זה.',           'bidi', set()),
    # ---- v5.3.5 (DEFECTS BIDI-84): v5.1.1 masked only the positions its
    # language model calls English, and the model gives an island's opener the
    # outer language. The command's own letters ("en") were left inside the
    # parenthesis as a strong Latin character. The four -ok rows are the fleet
    # lines that failed, each rendered correct on the page; the two positives
    # keep the rule: raw Latin inside, and Latin after the island inside.
    ('latparen535: raw Latin inside',   'שגיאת OOB (out-of-bag): כל עץ מחמיץ.',            'bidi', {'LATIN-BEFORE-PAREN'}),
    ('latparen535: Latin after the island', 'שגיאת OOB (\\en{out}-of-bag): כל עץ מחמיץ.',  'bidi', {'LATIN-BEFORE-PAREN'}),
    ('latparen535-ok: island fills the parens', 'שגיאת OOB (\\en{out-of-bag}): כל עץ מחמיץ.', 'bidi', set()),
    ('latparen535-ok: escaped underscore', 'ו-listing (\\en{write\\_listing}) נכתב.',      'bidi', set()),
    ('latparen535-ok: island with a comma', 'באסמבלי של SIMP (\\en{summat.asm, clock.asm}). קבצים.', 'bidi', set()),
    ('latparen535-ok: island of digits', 'רשתות ו\\en{-}PCA (\\en{8–10}) לומדות משקלים.',  'bidi', set()),
    ('latparen535-ok: foreignlanguage opener', 'שגיאת OOB (\\foreignlanguage{english}{out-of-bag}): כל עץ.', 'bidi', set()),
    ('latparen4141-ok: env optional arg', '\\begin{exbox}[frametitle={דוגמה — מצב שלושה קיוביטים}]\nטקסט עברי כאן.\n\\end{exbox}', 'bidi', set()),
    # ---- v4.15.0 TOKEN-PUNCT-ADRIFT (DEFECTS BIDI-80). A bare Latin token in
    # Hebrew prose loses its own edge punctuation to the far side of the word:
    # /audit prints "audit/", commands/ prints "/commands". Every positive was
    # read off the rendered page (glyph x-order AND a crop), and every negative
    # was read off the same page as CORRECT — the exemptions are measurements,
    # not judgement calls.
    ('adrift80: slash command',       'א ראה /audit כאן.',                    'bidi', {'TOKEN-PUNCT-ADRIFT'}),
    ('adrift80: dotfile',             'א ראה .claude כאן.',                   'bidi', {'TOKEN-PUNCT-ADRIFT'}),
    ('adrift80: at sign',             'א ראה @agent כאן.',                    'bidi', {'TOKEN-PUNCT-ADRIFT'}),
    ('adrift80: escaped hash',        'א ראה \\#tag כאן.',                     'bidi', {'TOKEN-PUNCT-ADRIFT'}),
    ('adrift80: short flag',          'א הדגל -v כאן.',                       'bidi', {'TOKEN-PUNCT-ADRIFT'}),
    ('adrift80: glob',                'א ראה *.tex כאן.',                     'bidi', {'TOKEN-PUNCT-ADRIFT'}),
    ('adrift80: plus flag',           'א ראה +flag כאן.',                     'bidi', {'TOKEN-PUNCT-ADRIFT'}),
    ('adrift80: trailing slash',      'א ראה commands/ כאן.',                 'bidi', {'TOKEN-PUNCT-ADRIFT'}),
    ('adrift80: inside parens',       'א ראה (/audit) כאן.',                  'bidi', {'TOKEN-PUNCT-ADRIFT'}),
    ('adrift80-ok: code island',      'א ראה \\code{/audit} כאן.',             'bidi', set()),
    ('adrift80-ok: en island',        'א ראה \\en{/audit} כאן.',               'bidi', set()),
    ('adrift80-ok: ascii connective', 'א הפרוטונים ב-LHC כאן.',               'bidi', set()),
    ('adrift80-ok: maqaf connective', 'א הפרוטונים ב־LHC כאן.',               'bidi', set()),
    ('adrift80-ok: Hebrew then slash','א שגיאת מבחן/CV כאן.',                 'bidi', set()),
    ('adrift80-ok: slash then Hebrew','א הערך CV/מבחן כאן.',                  'bidi', set()),
    ('adrift80-ok: sentence period',  'א ראה audit. כאן.',                    'bidi', set()),
    ('adrift80-ok: dotted filename',  'א הקובץ CLAUDE.md כאן.',               'bidi', set()),
    ('adrift80-ok: hyphenated name',  'א הניסוי Hong-Ou-Mandel כאן.',         'bidi', set()),
    ('adrift80-ok: decimal',          'א הערך 0.5 כאן.',                      'bidi', set()),
    ('adrift80-ok: and/or',           'א הביטוי and/or כאן.',                 'bidi', set()),
    ('adrift80-ok: Hebrew slash',     'א הביטוי ו/או כאן.',                   'bidi', set()),
    ('adrift80-ok: discretionary hyphen', 'א המילה Register\\-ing כאן.',       'bidi', set()),
    ('adrift80-ok: graphics path',    'א טקסט \\includegraphics[width=5cm]{figs/name} כאן.', 'bidi', set()),
    ('adrift80-ok: input path',       'א טקסט \\input{parts/p1} כאן.',         'bidi', set()),
    ('adrift80-ok: starred heading',  '\\section*{כותרת עברית כאן}',           'bidi', set()),
    ('adrift80-ok: English line',     'See /audit and commands/ here.',        'bidi', set()),
    ('adrift80-ok: math then hyphen', 'א הרגישות ב-$k$-NN כאן.',              'bidi', set()),
    ('adrift80-ok: math then word',   'א הערך $p$-value כאן.',                'bidi', set()),
    ('adrift80-ok: island then hyphen','א הרובד \\en{n}-type כאן.',            'bidi', set()),
    ('adrift80-ok: code then hyphen', 'א הרובד \\code{n}-type כאן.',           'bidi', set()),
    ('adrift80-ok: texorpdfstring heading', '\\chapter{פשרה ב-\\texorpdfstring{$k$}{k}-NN כאן}', 'bidi', set()),
    ('adrift80-ok: frametitle islands', '\\begin{notebox}[frametitle={\\en{n}-type מול \\en{p}-type}]\nטקסט עברי כאן.\n\\end{notebox}', 'bidi', set()),
    # ---- v3.32: round-3 adversarial lock — every case proven by compile /
    # glyph geometry before the checker changed (audit3 fixtures)
    ('codehead32-ok: escaped brace in heading', '\\section{סוגריים \\} ואז \\code{x}}', 'bidi', set()),
    ('codehead32-ok: code in texorpdf 2nd arg', '\\section{כותרת \\texorpdfstring{Y}{\\code{y}}}', 'bidi', set()),
    ('codehead32-ok: 2-level braces in 1st arg', '\\section{\\texorpdfstring{\\code{a{b}c}}{abc}}', 'bidi', set()),
    ('codechar32: escaped brace in group',  'הקוד \\code{a\\}_b} כאן.',                'bidi', {'CODE-UNSAFE-CHAR'}),
    ('codechar32: ~ inside $span$',         'הקוד \\code{Q$a~b$} כאן.',                'bidi', {'CODE-UNSAFE-CHAR'}),
    ('quotes32-ok: 2-level braces + backticks in code', 'טקסט \\code{m = {{0}} `x`} סוף.', 'bidi', set()),
    ('xline32-ok: \\section is a paragraph boundary', 'טקסט מקדים \\en{note:}\n\\section{כותרת עברית}', 'bidi', set()),
    ('xline32-ok: \\par is a paragraph boundary', 'טקסט \\en{Note:}\n\\par\nהמשך עברי כאן.', 'bidi', set()),
    ('parens32: leading space in \\text before \\en', 'צימוד $g \\text{ \\en{(weak coupling)}}$ כאן.', 'bidi', {'TEXT-PARENS-IN-MATH'}),
    ('parens32-ok: no space, exact form',   'צימוד $g\\ \\text{\\en{(weak coupling)}}$ כאן.', 'bidi', set()),
    ('charset32: hebrew-block tofu points', 'סימן ׯ וגם ׅ בטקסט.',                    'charset', {'STRAY'}),
    ('charset32-ok: qamats qatan + ligature', 'קָמָץ ׇ וליגטורה װ תקינים.',            'charset', set()),
    ('chain32: wrapped source line still one paragraph', 'בלוק = $4$ $\\Leftarrow$ היסט $2$ ביט. מספר $16/4=4$\n$\\Leftarrow$ נותר $8$ ביט וגם $x$ ועוד $y$.', 'density', {'DERIVATION-CHAIN'}),
    ('chain32-ok: itemize advised form',    '\\begin{itemize}\n\\item[\\textbf{\\en{Offset}:}] בלוק = $4$ בתים $\\Leftarrow$ $2$ ביט.\n\\item[\\textbf{\\en{Index}:}] מספר $16/4=4$ $\\Leftarrow$ $2$ ביט.\n\\end{itemize}', 'density', set()),
    # ---- v3.33: round-4 adversarial lock (audit4 probes, all render/compile-proven)
    ('prime33: apostrophe after $..$',  "נגזרת: $f$' וגם המשך.",                    'bidi', {'PRIME-AFTER-MATH'}),
    ('prime33: after \\(..\\)',           "נגזרת: \\(f\\)' וגם המשך.",                'bidi', {'PRIME-AFTER-MATH'}),
    ('prime33-ok: possessive $X$\'s',   "variable $X$'s values are here.",          'bidi', set()),
    ('prime33-ok: prime inside math',   "נגזרת: $f'$ נכונה.",                       'bidi', set()),
    ('codehead33-ok: rescue split across lines', '\\section{\\texorpdfstring{\\code{ls}}\n{ls} רשימה}', 'bidi', set()),
    ('quotes33-ok: backticks in cross-line code', 'טקסט רגיל \\code{git log\n`HEAD`} עוד טקסט.', 'bidi', set()),
    ('colon33-ok: mid-line par boundary', '\\en{Offset:} \\par עברית ממשיכה כאן.', 'bidi', set()),
    ('parens33: escaped space before en', 'שלוש $y = \\text{\\ \\en{(charlie)}}$ סוף', 'bidi', {'TEXT-PARENS-IN-MATH'}),
    ('parens33: tie before en',           'ארבע $y = \\text{~\\en{(delta)}}$ סוף',   'bidi', {'TEXT-PARENS-IN-MATH'}),
    ('parens33: newline after text brace', 'חמש $y = \\text{\n\\en{(echo)}}$ סוף',  'bidi', {'TEXT-PARENS-IN-MATH'}),
    ('parens33-ok: percent continuation', 'שש $y = \\text{%\n\\en{(foxtrot)}}$ סוף', 'bidi', set()),
    # ---- v3.49: round-1 LaTeX-skill audit (G1 backslash-in-code, F4 heading arg-scan)
    ('codechar49: backslash Windows path', 'הקובץ בנתיב \\code{C:\\Users\\data} נמצא.', 'bidi', {'CODE-UNSAFE-CHAR'}),
    ('codechar49-ok: escaped percent',     'הקוד \\code{width=50\\%} כאן.',            'bidi', set()),
    ('codechar49-ok: escaped underscore',  'המשתנה \\code{a\\_b} תקין.',               'bidi', set()),
    ('codechar49-ok: legit \\dots in code', 'הפקודה \\code{sll \\dots, 1} כאן.',       'bidi', set()),
    ('codechar49-ok: legit \\ldots in code', 'הרשימה \\code{a, b, \\ldots, z} כאן.',   'bidi', set()),
    ('codechar49-ok: \\textbackslash escape', 'התו \\code{\\textbackslash n} כאן.',    'bidi', set()),
    ('mathhead49: real math in section arg', '\\section{הסיבוכיות $O(n)$ של האלגוריתם}', 'bidi', {'MATH-IN-HEADING'}),
    ('mathhead49-ok: paragraph run-in body math', '\\paragraph{טענה} לכל $x$ מתקיים $x^2 \\ge 0$.', 'bidi', set()),
    ('mathhead49-ok: texorpdfstring rescue', '\\section{הסיבוכיות \\texorpdfstring{$O(n)$}{O(n)} כאן}', 'bidi', set()),
    # ---- v3.50: round-1 audit FP fixes (F1 english block, F2 nested-$ in text, F3 \tag)
    ('tag50-ok: \\h in \\tag label',        '\\begin{equation} E=mc^2 \\tag{\\h{א}} \\end{equation}', 'bidi', set()),
    ('tag50: bare \\h in real math fires',  '\\[ x = \\h{ביטוי} + 1 \\]',               'bidi', {'LANG-RAW-IN-MATH'}),
    ('parens50-ok: nested $..$ in \\text',   '\\[ \\text{אם $g(x) > 0$} \\]',            'bidi', set()),
    ('parens50: real text-parens latin',    '\\[ z = \\text{Specificity (TNR)} \\]',    'bidi', {'TEXT-PARENS-IN-MATH'}),
    ('parens50: latin parens after nested $', '\\[ w = \\text{$f$ (function)} \\]',     'bidi', {'TEXT-PARENS-IN-MATH'}),
    ('eng50-ok: islands in multiline english', '\\begin{otherlanguage}{english}\nThe \\code{lw}, \\code{sw} pair and \\texttt{ALUOp}$=10$ run.\n\\end{otherlanguage}', 'bidi', set()),
    ('eng50: same islands in hebrew prose fire', 'המעבד \\code{lw}, \\code{sw} מהזיכרון.', 'bidi', {'ADJACENT-LTR-ISLANDS'}),
    ('eng50: hebrew after block still fires', '\\begin{otherlanguage}{english}\nThe \\code{a}, \\code{b} pair.\n\\end{otherlanguage}\nבעברית \\code{add}, \\code{sub} מיד.', 'bidi', {'ADJACENT-LTR-ISLANDS'}),
    # ---- v3.51: round-2 audit checker-FP fixes (B7 balanced brackets, B11 en:en ratio)
    ('paren51-ok: en{()} empty args',       'פונקציה מקבלת \\en{()} ריקים בעברית כאן.',  'bidi', set()),
    ('paren51-ok: en{[]} empty list',       'רשימה ריקה \\en{[]} בעברית כאן.',           'bidi', set()),
    ('paren51: lone \\en{(} still mirrors',  'ראו \\en{(}טבלת עמודים\\en{)} בעברית.',     'bidi', {'PAREN-ONLY-ISLAND'}),
    ('encolon51-ok: en:en ratio',           '$k = \\text{\\en{signal}:\\en{noise}}$ במערכת.', 'bidi', set()),
    ('encolon51: en{label}: then hebrew fires', '$x = \\text{\\en{Offset}: ערך}$ כאן.', 'bidi', {'MATH-TEXT-EN-COLON'}),
    # ---- PUNCT-RAW-IN-MATH (v3.53): text-only typographic punct tofus in math -
    # ° … – — “ ” ‘ ’ ־ ₪ render in text (charset ALLOWS them) but the math font
    # (cmr) has no glyph, so they SILENTLY DROP in $..$. Rule flags the raw char in
    # math; exempt inside \text{} and when the proper math command is used.
    ('punct53: raw ° in math',        'הזווית היא $45°$ מעלות בעברית.',            'bidi', {'PUNCT-RAW-IN-MATH'}),
    ('punct53: raw … in math',        'הטור $a_1+…+a_n$ מתכנס בעברית.',            'bidi', {'PUNCT-RAW-IN-MATH'}),
    ('punct53: raw ₪ in math',        'המחיר $x=5₪$ בשקלים בעברית.',              'bidi', {'PUNCT-RAW-IN-MATH'}),
    ('punct53-ok: ^\\circ',           'הזווית היא $45^\\circ$ מעלות בעברית.',      'bidi', set()),
    ('punct53-ok: \\dots',            'הטור $a_1+\\dots+a_n$ מתכנס בעברית.',       'bidi', set()),
    ('punct53-ok: ° inside \\text',   'הטמפרטורה $30\\text{°}C$ במעבדה בעברית.',   'bidi', set()),
    ('punct53-ok: ° in text mode',    'הזווית 45° מעלות בפרוזה עברית רגילה.',      'bidi', set()),
    # ---- HEBREW-IN-MONO (v3.56): Hebrew in a mono span is FATAL, not tofu ----
    # \texttt/\code -> \origtexttt = DejaVu Sans Mono (zero Hebrew), and the tt
    # fallback hebfb = DejaVuSerif (also zero Hebrew), so the build dies with
    # "there are no glyphs in the subset" naming only a font file.
    ('mono56: \\code{Hebrew}',        'הפקודה \\code{עברית} כאן בפרוזה.',          'bidi', {'HEBREW-IN-MONO'}),
    ('mono56: \\texttt{Hebrew}',      'הערך \\texttt{שלום} מופיע כאן.',            'bidi', {'HEBREW-IN-MONO'}),
    ('mono56-ok: Latin in \\code',    'הפקודה \\code{lw \\$t0, 4} תקינה בעברית.',  'bidi', set()),
    ('mono56-ok: Hebrew BETWEEN code','הערך \\code{x} ו־\\code{y} בעברית כאן.',    'bidi', set()),
    ('mono56-ok: in a comment',       '% \\code{עברית} בתוך הערה בלבד',            'bidi', set()),
    # ---- v3.57 range/ref reversal. Separator taxonomy MEASURED on the page: ----
    # – — ־ (any spacing) and ", " reverse; unspaced "," and "/" are CORRECT;
    # \autoref anchors each unit with its Hebrew name; \en{} merge is the fix.
    ('rng57: en-dash years',          'המחקר נערך בשנים 2020–2023 בישראל.',        'bidi', {'RANGE-SEP-BETWEEN-DIGITS'}),
    ('rng57: en-dash pages',          'ראו עמודים 15–17 בספר הזה.',                'bidi', {'RANGE-SEP-BETWEEN-DIGITS'}),
    ('rng57: maqaf between digits',   'בשנים 2020־2023 היו שינויים רבים.',         'bidi', {'RANGE-SEP-BETWEEN-DIGITS'}),
    ('rng57: spaced hyphen',          'טווח של 5 - 10 מילים בכל שורה.',            'bidi', {'RANGE-SEP-BETWEEN-DIGITS'}),
    ('rng57: spaced slash',           'רוחב 8 / 16 סיביות בהתאמה כאן.',            'bidi', {'RANGE-SEP-BETWEEN-DIGITS'}),
    ('rng57-ok: unspaced ascii',      'טווח של 5-10 מילים ובשנים 2020-2023 כאן.',  'bidi', set()),
    ('rng57-ok: unspaced slash',      'רוחב 8/16/32 סיביות בהתאמה כאן.',           'bidi', set()),
    ('rng57-ok: maqaf after letter',  'המאה ה־21 שלנו, כ־12 תאים, בית־ספר גדול.',  'bidi', set()),
    ('rng57-ok: digit one side only', 'בשנת 2020 — היה טוב מאוד בארץ.',            'bidi', set()),
    ('rng57-ok: merged island',       'המחקר נערך בשנים \\en{2020–2023} בישראל.',   'bidi', set()),
    ('rng57-ok: in math',             'החישוב $5-3$ וגם $a-b$ נכונים בעברית.',     'bidi', set()),
    ('rng57-ok: codeline operand',    '\\codeline{lw \\$t1, -4(\\$t0)} בעברית כאן.', 'bidi', set()),
    ('ref57: eqref en-dash range',    'ראו משוואות \\eqref{a}–\\eqref{b} בהמשך.',   'bidi', {'REF-RANGE-REORDER'}),
    ('ref57: ref double-hyphen',      'ראו סעיפים \\ref{a}--\\ref{b} בהמשך הפרק.',  'bidi', {'HEBREW-DOUBLE-HYPHEN', 'REF-RANGE-REORDER'}),
    ('ref57: comma WITH space',       'ראו סעיפים \\ref{a}, \\ref{b} וגם אחרים.',   'bidi', {'REF-RANGE-REORDER'}),
    ('ref57-ok: comma no space',      'ראו סעיפים \\ref{a},\\ref{b} וגם אחרים.',    'bidi', set()),
    ('ref57-ok: slash separator',     'ראו סעיפים \\ref{a}/\\ref{b} וגם אחרים.',    'bidi', set()),
    ('ref57-ok: autoref range',       'ראו \\autoref{a}–\\autoref{b} בהמשך הפרק.',  'bidi', set()),
    ('ref57-ok: hebrew word between', 'ראו סעיף \\ref{a} עד סעיף \\ref{b} כאן.',    'bidi', set()),
    ('ref57-ok: merged island',       'ראו \\en{\\eqref{a}–\\eqref{b}} בהמשך הפרק.', 'bidi', set()),
    # ---- v3.59 round-3 batch (all four survived an adversarial skeptic) --------
    # ITEM-EATEN-BRACKET: \item body opening with [ is eaten as the optional label
    # (\@ifnextchar skips whitespace AND newlines) — brackets and bullet vanish.
    ('item59: spaced bracket body',   '\\item [11:4] הביטים הרלוונטיים כאן.',       'bidi', {'ITEM-EATEN-BRACKET'}),
    ('item59: hebrew tag body',       '\\item [רמז] נסה להשתמש בזהות כאן.',         'bidi', {'ITEM-EATEN-BRACKET'}),
    ('item59: newline bracket body',  '\\item\n[10,20] הקטע הרלוונטי כאן.',         'bidi', {'ITEM-EATEN-BRACKET'}),
    ('item59-ok: braced',             '\\item {[11:4]} הביטים הרלוונטיים כאן.',     'bidi', set()),
    ('item59-ok: math',               '\\item $[10,20]$ הקטע הרלוונטי כאן.',        'bidi', set()),
    ('item59-ok: real label',         '\\item[2.1.] סעיף ממוספר ידנית כאן.',        'bidi', set()),
    ('item59-ok: \\itemsep not \\item', '\\itemsep2pt והגדרה עברית כאן.',            'bidi', set()),
    # LABEL-IN-EXPLICIT-ITEM: \item[..] never steps the counter (\refstepcounter
    # sits inside \if@noitemarg), so \label binds to the ambient chapter/section.
    ('lbl59: label in explicit item', '\\item[(\\textbf{א})]\\label{it:a} הסעיף הראשון.', 'bidi', {'LABEL-IN-EXPLICIT-ITEM'}),
    ('lbl59-ok: no label',            '\\item[(\\textbf{א})] הסעיף הראשון כאן.',    'bidi', set()),
    # LABEL-ON-UNNUMBERED-HEADING (v3.64): secnumdepth=2 leaves \subsubsection and
    # below unnumbered, so they never \refstepcounter and a \label there binds to
    # the last NUMBERED ancestor. Measured: \ref to either printed the SUBSECTION's
    # number 1.1.1. Numbered levels must stay silent — that is the whole rule.
    ('lbl64: label on subsubsection', '\\subsubsection{תת־תת}\\label{x:a}',        'bidi', {'LABEL-ON-UNNUMBERED-HEADING'}),
    ('lbl64: label on paragraph',     '\\paragraph{פסקה}\\label{x:b}',              'bidi', {'LABEL-ON-UNNUMBERED-HEADING'}),
    ('lbl64: label on subparagraph',  '\\subparagraph{תת־פסקה}\\label{x:c}',       'bidi', {'LABEL-ON-UNNUMBERED-HEADING'}),
    ('lbl64-ok: numbered subsection', '\\subsection{תת־סעיף}\\label{ok:a}',        'bidi', set()),
    ('lbl64-ok: numbered section',    '\\section{סעיף}\\label{ok:b}',               'bidi', set()),
    ('lbl64-ok: numbered chapter',    '\\chapter{פרק}\\label{ok:c}',                'bidi', set()),
    ('lbl64-ok: heading, no label',   '\\subsubsection{תת־תת} וטקסט רגיל אחריו.',  'bidi', set()),
    # LIST-IN-LTR-ISLAND (v3.66): a list opened inside an LTR wrapper applies its
    # \leftmargin on the READING edge and hangs the label into (or off) the LEFT
    # margin. Allow-list polarity is safe here: an unrecognised wrapper only fails
    # to fire, never flags correct code (inverse of the LISTING rule's hazard).
    ('lst66: list in otherlanguage',  '\\begin{otherlanguage}{english}\n\\begin{itemize}\n\\item First.\n\\end{itemize}\n\\end{otherlanguage}', 'bidi', {'LIST-IN-LTR-ISLAND'}),
    ('lst66: list in asmblock',       '\\begin{asmblock}\n\\begin{enumerate}\n\\item x\n\\end{enumerate}\n\\end{asmblock}', 'bidi', {'LIST-IN-LTR-ISLAND'}),
    ('lst66-ok: list in exbox',       '\\begin{exbox}\n\\begin{itemize}\n\\item פריט בעברית.\n\\end{itemize}\n\\end{exbox}', 'bidi', set()),
    ('lst66-ok: list after island',   '\\begin{otherlanguage}{english}\nEnglish text.\n\\end{otherlanguage}\n\\begin{itemize}\n\\item פריט.\n\\end{itemize}', 'bidi', set()),
    # ITEM-OPENS-WITH-BLOCK (v3.66): the pending \@labels box waits for \everypar,
    # and the skill's block wrappers fire it inside an LTR/centred/box paragraph —
    # the item number prints at the physical left margin / mid-page / inside the box.
    ('itm66: item opens asmblock',    '\\begin{enumerate}\n\\item \\begin{asmblock}x\\end{asmblock}\n\\end{enumerate}', 'bidi', {'ITEM-OPENS-WITH-BLOCK'}),
    ('itm66: item then tikzpic line', '\\begin{enumerate}\n\\item\n\\begin{tikzpic}x\\end{tikzpic}\n\\end{enumerate}', 'bidi', {'ITEM-OPENS-WITH-BLOCK'}),
    ('itm66-ok: intro text first',    '\\begin{enumerate}\n\\item הפקודה הבאה:\n\\begin{asmblock}x\\end{asmblock}\n\\end{enumerate}', 'bidi', set()),
    ('itm66-ok: codeline is fixed',   '\\begin{enumerate}\n\\item \\codeline{lw \\$t0}\n\\end{enumerate}', 'bidi', set()),
    # v3.66 stack fix: \\end{lstlisting}\\end{asmblock} on ONE line used to leave a
    # phantom asmblock on the env stack, DISARMING the LISTING rule for the rest of
    # the file (measured: 8 phantoms in r04.tex). The bare listing after the
    # one-line close must flag; the closed asmblock must not leak into it.
    ('stk66: bare lst after 1-line close', '\\begin{asmblock}\\begin{lstlisting}\nx\n\\end{lstlisting}\\end{asmblock}\nטקסט.\n\\begin{lstlisting}\ny\n\\end{lstlisting}', 'bidi', {'LISTING-OUTSIDE-LTR-ISLAND'}),
    # H-OPENS-WITH-LTR-GROUP (v3.67): an \h{} group in math that OPENS with a
    # nested island suppresses bidi for the whole group — Hebrew prints in
    # logical order (gibberish). Hebrew-first / island-outside / no-\h are fine.
    ('hop67: math-first \\h in \\text',  '$x = \\text{\\h{$f$ קבועה}}$',              'bidi', {'H-OPENS-WITH-LTR-GROUP'}),
    ('hop67: en-first \\h in \\mbox',    '$y = \\mbox{\\h{\\en{f} רציפה}}$',          'bidi', {'H-OPENS-WITH-LTR-GROUP'}),
    ('hop67: code-first \\h',            '$z = \\text{\\h{\\code{ax} אוגר}}$',        'bidi', {'H-OPENS-WITH-LTR-GROUP'}),
    ('hop67-ok: hebrew first',           '$x = \\text{\\h{קבועה $f$}}$',              'bidi', set()),
    ('hop67-ok: island outside \\h',     '$x = \\text{$f$\\h{ קבועה}}$',              'bidi', set()),
    ('hop67-ok: no hebrew inside',       '$x = \\text{\\h{$f$ ok}}$',                 'bidi', set()),
    ('hop67-ok: leading paren',          '$x = \\text{\\h{(קבועה) $f$}}$',            'bidi', set()),
    # LABEL-IN-UNNUMBERED-DISPLAY (v3.67): 4th member of the BLD-13/BIDI-50/56
    # family. \eqref prints "()" (align*) or the SECTION number (equation*/\[..\]).
    # The v3.58 undef gate is bypassed — the label IS defined.
    ('lbl67: label in align*',           '\\begin{align*}\na &= 1 \\label{L:a}\n\\end{align*}', 'bidi', {'LABEL-IN-UNNUMBERED-DISPLAY'}),
    ('lbl67: label in equation*',        '\\begin{equation*}\nc = 3 \\label{L:c}\n\\end{equation*}', 'bidi', {'LABEL-IN-UNNUMBERED-DISPLAY'}),
    ('lbl67: label in bracket display',  '\\[\ng = 7 \\label{L:g}\n\\]',              'bidi', {'LABEL-IN-UNNUMBERED-DISPLAY'}),
    ('lbl67: same-line bracket',         '\\[ h = 8 \\label{L:h} \\]',                'bidi', {'LABEL-IN-UNNUMBERED-DISPLAY'}),
    ('lbl67-ok: label in align',         '\\begin{align}\na &= 1 \\label{eq:ok}\n\\end{align}', 'bidi', set()),
    ('lbl67-ok: rowspace not display',   'טקסט ראשון \\\\[2pt] המשך עם \\label{t:ok} בפרוזה.', 'bidi', set()),
    # TRAILING-CR-IN-DISPLAY (v3.67): a trailing \\ before \end{align...} mints a
    # PHANTOM numbered row and shifts every later equation number. The exclusion
    # is load-bearing: tabular/matrix/cases are measured INERT (53 live corpus
    # trailing-\\ tabular rows must stay silent).
    ('tcr67: trailing in align',         '\\begin{align}\nb &= 2 \\\\\n\\end{align}', 'bidi', {'TRAILING-CR-IN-DISPLAY'}),
    ('tcr67: same-line gather*',         '\\begin{gather*}\nc = 3 \\\\ \\end{gather*}', 'bidi', {'TRAILING-CR-IN-DISPLAY'}),
    ('tcr67-ok: no trailing',            '\\begin{align}\nb &= 2\n\\end{align}',      'bidi', set()),
    ('tcr67-ok: tabular is inert',       '\\begin{tabular}{cc}\nא & ב \\\\\n\\end{tabular}', 'bidi', set()),
    ('tcr67-ok: pmatrix is inert',       '$\\begin{pmatrix} 1 & 2 \\\\ \\end{pmatrix}$', 'bidi', set()),
    # CAPTION-INSIDE-LTR-ISLAND (v3.68): a \figcap/\tabcap inside tikzpic/qcirc
    # is typeset under the island's LTR base — the label migrates to the visual
    # LEFT and the final period flips. Outside the island it must stay silent.
    ('cap68: figcap in qcirc',           '\\begin{qcirc}\n\\begin{quantikz}\n\\gate{H}\n\\end{quantikz}\n\\figcap{מעגל}\n\\end{qcirc}', 'bidi', {'CAPTION-INSIDE-LTR-ISLAND'}),
    ('cap68: tabcap in tikzpic',         '\\begin{tikzpic}\n\\begin{tikzpicture}\\node{A};\\end{tikzpicture}\n\\tabcap{טבלה}\n\\end{tikzpic}', 'bidi', {'CAPTION-INSIDE-LTR-ISLAND'}),
    ('cap68-ok: figcap after island',    '\\begin{qcirc}\n\\begin{quantikz}\n\\gate{H}\n\\end{quantikz}\n\\end{qcirc}\n\\figcap{מעגל}', 'bidi', set()),
    ('figadj: prose before caption',     '\\end{tikzpic}\nטקסט ביניים\n\\figcap{כיתוב}', 'bidi', {'FIGCAP-NOT-ADJACENT'}),
    ('figadj: vspace before caption',    '\\end{qcirc}\n\\vspace{1em}\n\\figcap[קצר]{כיתוב}', 'bidi', {'FIGCAP-NOT-ADJACENT'}),
    ('figadj: nested optional gap',      '\\end{tikzpic}\n\\vspace{1em}\n\\figcap[\\code{arr[i]}]{כיתוב}', 'bidi', {'FIGCAP-NOT-ADJACENT'}),
    ('figadj-ok: immediate caption',     '\\end{tikzpic}\n\\figcap{כיתוב}', 'bidi', set()),
    ('figadj-ok: prior captionless figure', '\\end{tikzpic}\nטקסט\n\\begin{tikzpic}\n\\end{tikzpic}\n\\figcap{כיתוב}', 'bidi', set()),
    ('figadj-ok: macro implementation',  '\\newcommand{\\srcfig}[1]{\\begin{center}X\\end{center}\\figcap{#1}}', 'bidi', set()),
    ('cap72: tabcap in otherlanguage',   '\\begin{otherlanguage}{english}\nEnglish text.\n\\tabcap{כיתוב בפנים}\n\\end{otherlanguage}', 'bidi', {'CAPTION-INSIDE-LTR-ISLAND'}),
    # LANG-IN-GATE-ARG (v3.68): quantikz cell args are MATH — \gate{\h{..}} is
    # fatal with "\rmfamily invalid in math mode" pointing at \end{quantikz}.
    # \gate{\text{\h{..}}} and \gate{\code{..}} are render-verified correct.
    ('gate68: \\h in \\gate',            '\\begin{quantikz}\n\\gate{\\h{מדידה}} & \\qw\n\\end{quantikz}', 'bidi', {'LANG-IN-GATE-ARG'}),
    ('gate68: \\en in \\meter',          '\\begin{quantikz}\n\\meter{\\en{out}} & \\qw\n\\end{quantikz}', 'bidi', {'LANG-IN-GATE-ARG'}),
    ('gate68-ok: \\text{\\h{}} in gate', '\\begin{quantikz}\n\\gate{\\text{\\h{מדידה}}} & \\qw\n\\end{quantikz}', 'bidi', set()),
    ('gate68-ok: \\code in gate',        '\\begin{quantikz}\n\\gate{\\code{CNOT}} & \\qw\n\\end{quantikz}', 'bidi', set()),
    # in_tikz now covers quantikz (v3.68): \h{Latin} inside quantikz must fire
    # the same LATIN-IN-H-IN-TIKZ that a tikzpicture control fires.
    # BOOKMARK-DROPS-HEBREW (v3.70): whole-heading \texorpdfstring with an
    # English translation ships an English nav pane (22 live bookmarks measured).
    # Fragment-level use and non-heading contexts (frametitle) must stay silent.
    ('bmk70: whole-heading translation', '\\chapter{\\texorpdfstring{מניין השגיאות}{Error count}}', 'bidi', {'BOOKMARK-DROPS-HEBREW'}),
    ('bmk70-ok: fragment level',         '\\chapter{אלגוריתם עם \\texorpdfstring{$k$}{k} פתרונות}', 'bidi', set()),
    ('bmk70-ok: frametitle inert',       '\\begin{keybox}[frametitle={\\texorpdfstring{עברית מול $x$}{Latin only}}]', 'bidi', set()),
    # v4.7.1 policy rules: legacy clean_variant still activates showonlyrefs=true,
    # secnumdepth=-2, exactly like pure clean_theme; \ref/\autoref to an equation prints an EMPTY number and
    # \ref to a heading label prints the ambient counter. Keyed on the layer
    # marker — the identical constructs are LEGITIMATE in normal collections
    # and must stay silent there.
    ('exm73: ref to eq under layer',   '\\input{clean_variant.tex}\nמשוואה \\ref{eq:a} כאן.', 'bidi', {'NONEQREF-UNDER-SHOWONLYREFS'}),
    ('exm73: autoref eq under layer',  '\\mathtoolsset{showonlyrefs=true}\nראו \\autoref{eq:b} כאן.', 'bidi', {'NONEQREF-UNDER-SHOWONLYREFS'}),
    ('exm73: ref to heading',          '\\input{clean_variant.tex}\nראה שאלה \\ref{ch:q2} לעיל.', 'bidi', {'REF-TO-HEADING-UNDER-EXAM-LAYER'}),
    ('exm73-ok: same refs no layer',   'משוואה \\ref{eq:a} ושאלה \\ref{ch:q2} בלקט רגיל.', 'bidi', set()),
    ('exm73-ok: eqref under layer',    '\\input{clean_variant.tex}\nהפניה \\eqref{eq:a} תקינה.', 'bidi', set()),
    ('exm73-ok: nameref under layer',  '\\input{clean_variant.tex}\nראו \\nameref{ch:q1} כאן.', 'bidi', set()),
    # v4.7.1 architecture capabilities: pure clean_theme must activate the
    # same numbering policies as the legacy generated clean_variant, while the
    # semantic exam extension by itself must not. This prevents checker behavior
    # from depending on a compatibility filename.
    ('arch471: clean theme eq policy', '\\input{clean_theme.tex}\nמשוואה \\ref{eq:a} כאן.', 'bidi', {'NONEQREF-UNDER-SHOWONLYREFS'}),
    ('arch471: clean theme heading policy', '\\input{clean_theme.tex}\nראה שאלה \\ref{ch:q2} לעיל.', 'bidi', {'REF-TO-HEADING-UNDER-EXAM-LAYER'}),
    ('arch471-ok: exam helpers alone', '\\input{exam_components.tex}\nראה שאלה \\ref{ch:q2} ומשוואה \\ref{eq:a}.', 'bidi', set()),
    # v3.71 checker-robustness round. (1) Three rules had ZERO positive coverage
    # — a mutation disabling any of them passed all 403 cases (mutation-proven).
    ('ttm71: texttt next to math',     'ההגדרה \\texttt{size}$=8$ בעברית כאן.',      'bidi', {'TEXTTT-NEXT-TO-MATH'}),
    ('dcs71: dollar split code pair',  'הצמד \\texttt{a\\$},\\texttt{t0} בעברית.',   'bidi', {'DOLLAR-CODE-SPLIT', 'ADJACENT-LTR-ISLANDS'}),
    ('arr71: hebrew equation arrow',   'נובע $x=1 \\Rightarrow \\text{המשוואה נכונה}$ כאן.', 'bidi', {'HEBREW-EQUATION-ARROW'}),
    # v4.7.4: arr71 is the FLAT \text{עברית} form, and it was the rule's ONLY
    # coverage — so #12(b) passed the whole suite while being blind to
    # \text{\h{...}}, the nested form every Hebrew collection actually writes,
    # and to the LaTeX spacing macros authors put around a display arrow. A
    # fleet sweep found 465 live sites over three collections that the rule saw
    # as clean. Render-measured (144 dpi, span x-positions): the rightward form
    # lays out LTR — ראשון x=265, → x=297, שני x=315 — so a reader entering the
    # display from the RIGHT meets the conclusion first with the arrow pointing
    # away; the \leftarrow rewrite puts them back in reading order (שני x=265,
    # ← x=286, ראשון x=304). Positives below cover the nesting and each spacing
    # shape; negatives pin the documented fix and every sanctioned exemption.
    ('arr474: nested h operands',      '\\[\n\\text{\\h{ראשון}}\\ \\to\\ \\text{\\h{שני}}\n\\]', 'bidi', {'HEBREW-EQUATION-ARROW'}),
    ('arr474: spacing macro quad',     '\\[\n\\text{\\h{ראשון}}\\quad\\Longrightarrow\\quad\\text{\\h{שני}}\n\\]', 'bidi', {'HEBREW-EQUATION-ARROW'}),
    ('arr474: right operand only',     '\\[\n\\sum A_1=\\sum A_2\n\\ \\Longrightarrow\\ \\text{\\h{האיבר מתקזז}}\n\\]', 'bidi', {'HEBREW-EQUATION-ARROW'}),
    # the documented fix must go silent — otherwise the rule is unfixable
    ('arr474-ok: leftward rewrite',    '\\[\n\\text{\\h{שני}}\\ \\leftarrow\\ \\text{\\h{ראשון}}\n\\]', 'bidi', set()),
    ('arr474-ok: pure math arrows',    '\\[\nf:A\\to B,\\qquad s\\to\\infty\n\\]', 'bidi', set()),
    # the Hebrew \text is GLUED to '+': it is a TERM inside the left equation,
    # so both operands of the arrow are math and the LTR arrow is correct
    ('arr474-ok: glued hebrew term',   '\\[\n\\mathcal{L}=-g\\,\\bar L\\,\\Phi\\,e_R+\\text{\\h{צ״מ}}\\;\\xrightarrow{\\ v\\ }\\;m=g v\n\\]', 'bidi', set()),
    ('arr474-ok: xarrow hebrew label', '\\[\nA\\ \\xrightarrow{\\text{\\h{תווית}}}\\ B\n\\]', 'bidi', set()),
    # The COARSE branch (implication + a Hebrew \text ANYWHERE on the line, no
    # adjacency) must stay brace-SHALLOW — the opposite call from the precise
    # branch above, and the reason HEB_TEXT_PAT is deliberately NOT depth-aware.
    # A Hebrew LABEL beside an all-math implication is correct as written; make
    # HEB_TEXT_PAT depth-aware and this case false-fires. Mutation-proven.
    ('arr474-ok: hebrew label, math implication', '\\[\n\\text{\\h{נתון}}:\\ x>0 \\quad\\Longrightarrow\\quad y>0\n\\]', 'bidi', set()),
    # v4.7.7 BOXED-ISLAND-EDGE-BRACKET. \mbox/\hbox END the bidi run at the box
    # boundary, so a mirrorable bracket FIRST or LAST inside the box has no
    # strong LTR neighbour on its outer side and takes the paragraph's RTL base,
    # where ] ) } > mirror. Render-proven: \mbox{\en{I[23:20]}} prints "I[23:20[".
    ('brk477: trailing bracket',       'מקבל את \\mbox{\\en{rs $=$ I[23:20]}}; וזהו.', 'bidi', {'BOXED-ISLAND-EDGE-BRACKET'}),
    ('brk477: both edges',             'ראה \\mbox{\\en{(3 sw + 3 lw)}} בטבלה.', 'bidi', {'BOXED-ISLAND-EDGE-BRACKET'}),
    ('brk477: code island in box',     'הפלט \\mbox{\\code{[35.0 27.5]}} מתקבל.', 'bidi', {'BOXED-ISLAND-EDGE-BRACKET'}),
    ('brk477: hbox is the same box',   'ראה \\hbox{\\en{Inst[15:0]}} בשדה.', 'bidi', {'BOXED-ISLAND-EDGE-BRACKET'}),
    # an \h{} inside an english block flips the base back to RTL, so the box
    # mirrors there too — measured, and the reason the block guard is not blanket
    ('brk477: h island re-flips base', '\\begin{otherlanguage}{english}\n\\h{\\mbox{\\en{\\{PC[31:28], addr\\}}}: x}\n\\end{otherlanguage}', 'bidi', {'BOXED-ISLAND-EDGE-BRACKET'}),
    # the documented fix — island OUTSIDE the box — must go silent
    ('brk477-ok: island outside box',  'מקבל את \\en{\\mbox{rs $=$ I[23:20]}}; וזהו.', 'bidi', set()),
    ('brk477-ok: code outside box',    'הפלט \\code{\\mbox{[35.0 27.5]}} מתקבל.', 'bidi', set()),
    # a strong LTR char after the bracket resolves it INSIDE the box (measured)
    ('brk477-ok: strong char follows', 'ראה \\mbox{\\en{I[23:20] ok}} בשדה.', 'bidi', set()),
    # no mirrorable char at either edge: . , : ; = + - measured UNCHANGED, so
    # widening the set to "neutrals" would be unmeasured scope
    ('brk477-ok: non-mirrorable edge', 'ראה \\mbox{\\en{RegSrc=0, RegWrite=1}} בטבלה.', 'bidi', set()),
    ('brk477-ok: plain word island',   'ראה \\mbox{\\en{Sign extend}} בשדה.', 'bidi', set()),
    # math is an LTR context: the same box renders CORRECTLY there (measured)
    ('brk477-ok: inside math',         'ערך $\\mbox{\\en{I[9:0]}}$ נשמר.', 'bidi', set()),
    # LTR base inside a real english block, with no \h to flip it back
    ('brk477-ok: english block base',  '\\begin{otherlanguage}{english}\nvalue \\mbox{\\en{I[9:0]}} kept\n\\end{otherlanguage}', 'bidi', set()),
    # the island is NOT the whole box body -> the edge is not the box edge
    ('brk477-ok: island not whole box','ראה \\mbox{x \\en{I[23:20]} y} בשדה.', 'bidi', set()),
    # v4.7.7: the BREAKABLE-VALUE-ISLAND \mbox exemption must survive the new
    # nesting order, or fixing one rule fires the other (caught in the fleet scan)
    ('brk477-ok: unbreakable either order', 'ראה \\en{\\mbox{(opcode $=0$, funct $=100000$)}} בטבלה.', 'bidi', set()),
    # (2) comment-poisoning: a %-comment naming \begin{verbatim} used to disable
    # EVERY rule to EOF with an affirmative "✓ clean"; a commented tikzpicture
    # both false-fired LATIN-IN-H-IN-TIKZ and killed the paragraph pass.
    ('psn71: commented verbatim',      '% TODO: החלף \\begin{verbatim} כאן\nשלום ``ציטוט\'\' כאן.', 'bidi', {'QUOTES'}),
    ('psn71-ok: commented tikz no FP', '% \\begin{tikzpicture}\nטקסט עם \\h{Datapath} כאן.', 'bidi', set()),
    ('psn71: real defect after comment tikz', '% \\begin{tikzpicture}\nעוד טקסט CPI (Cycles Per Instruction) כאן.', 'bidi', {'LATIN-BEFORE-PAREN'}),
    # (3) cross-line MATH-IN-HEADING — the wrap that motivated pass (d) hid it.
    ('mih71: wrapped heading math',    '\\section{כותרת ארוכה\n  ובה $x^2$ מתמטיקה}', 'bidi', {'MATH-IN-HEADING'}),
    # (4) an unprotected \footnote remains fragile in a moving heading.
    ('fnh71: footnote in heading',     '\\section{כותרת עם הערה\\footnote{הערת שוליים.}}', 'bidi', {'FOOTNOTE-IN-HEADING'}),
    ('fnh71-ok: protected footnote',   '\\section{כותרת מוגנת\\protect\\footnote{הערה תקינה.}}', 'bidi', set()),
    # (5) U+2028 used to be CONSUMED by .splitlines() — the charset gate never
    # saw it ("charset clean") while LuaTeX renders it as tofu.
    ('u2028-71: line separator',       'שורה ראשונה\u2028המשך השורה.',               'charset', {'STRAY'}),
    ('latin-ok: accented names',       'Gödel, Schrödinger, naïve, café, José, Łódź.', 'charset', set()),
    ('latin: decomposed source',       'Go\u0308del',                                     'charset', {'STRAY'}),
    ('latin: unsupported extended',    'ƀ',                                            'charset', {'STRAY'}),
    ('latin: unsupported combining',   'a\u0350',                                      'charset', {'STRAY'}),
    # v3.69 bibliography: each \cite is its own LTR isolate, so a range/pair
    # lays out right-to-left ([3]–[1] measured); a bare-Latin \bibitem's trailing
    # ').' migrates left and mirrors; a period OUTSIDE the \en{} island orphans.
    ('cit69: cite range',              'טווח \\cite{a}–\\cite{c} כאן.',           'bidi', {'REF-RANGE-REORDER', 'ADJACENT-LTR-ISLANDS'}),
    ('cit69-ok: single cite',          'מקור \\cite{a} בפרוזה עברית כאן.',           'bidi', set()),
    ('cit69-ok: multi-key cite',       'מקורות \\cite{a,b,c} בפרוזה עברית.',         'bidi', set()),
    ('bib69: bare latin entry',        '\\begin{thebibliography}{9}\n\\bibitem{a} A. Einstein, Ann. Phys. 17 (1905).\n\\end{thebibliography}', 'bidi', {'BIBITEM-LATIN-TAIL'}),
    ('bib69: period outside island',   '\\begin{thebibliography}{9}\n\\bibitem{a} \\en{P. Shor, SIAM 26 (1997)}.\n\\end{thebibliography}', 'bidi', {'BIBITEM-LATIN-TAIL'}),
    ('bib69-ok: period inside island', '\\begin{thebibliography}{9}\n\\bibitem{a} \\en{M. Nielsen, QC (2000).}\n\\end{thebibliography}', 'bidi', set()),
    ('bib69-ok: hebrew entry',         '\\begin{thebibliography}{9}\n\\bibitem{a} כהן, מבוא לפיזיקה, 2019.\n\\end{thebibliography}', 'bidi', set()),
    ('qtz68: latin in \\h in quantikz',  '\\begin{quantikz}\n\\lstick{\\h{קלט Output}} & \\qw\n\\end{quantikz}', 'bidi', {'LATIN-IN-H-IN-TIKZ'}),
    # ISLAND-BEFORE-OP-MATH (v4.1.3) — HEBREW-BEFORE-OP-MATH keyed on a Hebrew
    # LETTER, so an LTR island before operator-initial math slipped through. The
    # reader meets the run's right edge (the VALUE) first either way.
    ('isloop: island then =expr',   'אורך אחרי \\en{Flatten} $=H\\cdot W\\cdot C$ כאן.', 'bidi', {'ISLAND-BEFORE-OP-MATH'}),
    ('isloop: code island then =',  'הפרמטר \\code{n\\_out} $=64$ כאן.',        'bidi', {'ISLAND-BEFORE-OP-MATH'}),
    ('isloop: across a line break', 'אורך אחרי \\en{Flatten}\n$=H\\cdot W\\cdot C$.',   'bidi', {'ISLAND-BEFORE-OP-MATH'}),
    ('isloop: \\sim after label',    'האפשרות \\en{(c)} $\\sim\\!67$ מעלות.',      'bidi', {'ISLAND-BEFORE-OP-MATH'}),
    # ok: the relation moved into Hebrew, or no leading operator at all.
    ('isloop-ok: הוא before math',  'אורך אחרי \\en{Flatten} הוא $H\\cdot W\\cdot C$.',  'bidi', set()),
    ('isloop-ok: שווה ל־ form',     'אורך אחרי \\en{Flatten} שווה ל־$H\\cdot W\\cdot C$.', 'bidi', set()),
    ('isloop-ok: no leading op',    'המודל \\en{OLS} עם $\\lambda$ קטן.',        'bidi', set()),
    ('isloop-ok: bare op mention',  'הסימן \\en{eq} הוא $=$ בלבד.',            'bidi', set()),
    # HEBREW-IN-EN-ISLAND — the mirror of the rule above. Measured on a shipped
    # table (data-science-exams ex03 q10): labels at the far end of every cell,
    # mirrored parens, torn prefixes, with a clean compile and clean charset.
    ('heben: hebrew prose in \\en',   'הטבלה: \\en{(b) חישוב נכון}',          'bidi', {'HEBREW-IN-EN-ISLAND'}),
    ('heben: hebrew label in \\en',   '\\section*{\\en{(א)} \\en{Direct Mapped}}', 'bidi', {'HEBREW-IN-EN-ISLAND'}),
    ('heben: nested \\en with hebrew', 'טור: \\en{(c) התעלמות מ-\\en{age} וגם}',  'bidi', {'HEBREW-IN-EN-ISLAND'}),
    ('heben: hebrew connector in range', 'הדיוק \\en{$0\\%$ ל-$1.3\\%$} בלבד.',  'bidi', {'HEBREW-IN-EN-ISLAND'}),
    # ok: \h{} inside \en{} is the sanctioned way back to Hebrew — the fleet
    # uses it deliberately for an English call-chain that ends in a Hebrew word.
    ('heben-ok: \\h escape inside \\en', 'המסלול \\en{\\code{f(6)} to \\code{f(5)} \\h{עלה}}.', 'bidi', set()),
    ('heben-ok: hebrew outside island',  'הטבלה: \\en{(b)} חישוב נכון בעברית.',   'bidi', set()),
    ('heben-ok: pure latin island',      'המודל \\en{Random Forest} בפרוזה.',      'bidi', set()),
    # VERB-IN-RTL-PROSE: \verb/\lstinline are not LTR-isolated (only \texttt/\code).
    ('verb59: \\verb in hebrew',       'המערך \\verb|arr[i]| כאן בפרוזה עברית.',     'bidi', {'VERB-IN-RTL-PROSE'}),
    ('verb59: \\lstinline in hebrew',  'הביטוי \\lstinline|x = a[i];| כאן בעברית.',  'bidi', {'VERB-IN-RTL-PROSE'}),
    ('verb59-ok: \\code instead',      'המערך \\code{arr[i]} כאן בפרוזה עברית.',     'bidi', set()),
    ('verb59-ok: no hebrew on line',  'A Latin-only line with \\verb|arr[i]| here.', 'bidi', set()),
    # LISTING-OUTSIDE-LTR-ISLAND: deny-list polarity — an UNRECOGNISED ancestor is
    # treated as a possible wrapper so a project-local otherlanguage alias is safe.
    ('lst59: no wrapper',             'טקסט.\n\\begin{lstlisting}\nint x=1;\n\\end{lstlisting}', 'bidi', {'LISTING-OUTSIDE-LTR-ISLAND'}),
    ('lst59: RTL container only',     'טקסט.\n\\begin{exbox}\n\\begin{lstlisting}\nint x=1;\n\\end{lstlisting}\n\\end{exbox}', 'bidi', {'LISTING-OUTSIDE-LTR-ISLAND'}),
    ('lst59-ok: asmblock',            'טקסט.\n\\begin{asmblock}\n\\begin{lstlisting}\nint x=1;\n\\end{lstlisting}\n\\end{asmblock}', 'bidi', set()),
    ('lst59-ok: unknown wrapper',     'טקסט.\n\\begin{exbox}\n\\begin{qeng}\n\\begin{lstlisting}\nint x=1;\n\\end{lstlisting}\n\\end{qeng}\n\\end{exbox}', 'bidi', set()),
    # ---- v3.60 ISLAND-PAIR-REVERSED: space/zero separators reverse too ---------
    # The reference doc asserted a period "does NOT reverse" and that only
    # comma/slash were triggers, "all empirically verified" — measured FALSE.
    ('ipair60: space separator',      'ראו \\en{CSV} \\en{(Comma-Separated Values)} בעברית.', 'bidi', {'ISLAND-PAIR-REVERSED'}),
    ('ipair60: zero separator',       'הביטים \\code{1010}\\code{101} בעברית כאן.',   'bidi', {'ISLAND-PAIR-REVERSED'}),
    ('ipair60: mixed macros',         'האות \\code{RegWrite} \\en{stuck-at-0} בעברית.', 'bidi', {'ISLAND-PAIR-REVERSED'}),
    ('ipair60-ok: merged island',     'ראו \\en{CSV (Comma-Separated Values)} בעברית.', 'bidi', set()),
    ('ipair60-ok: nested merge',      'האות \\en{\\code{RegWrite} stuck-at-0} בעברית.', 'bidi', set()),
    # the derivation-arrow idiom: islands hold ONLY math -> separate flow items,
    # render correctly, must stay exempt (this is what the alnum-outside-math gate buys)
    ('ipair60-ok: arrow idiom',       'נקבל \\en{$x$} \\en{$\\Leftarrow$} בעברית כאן.', 'bidi', set()),
    # a PERIOD between islands is a sentence boundary, never flagged (v3.60 decision)
    ('ipair60-ok: sentence boundary', 'לאסמבלי \\en{MIPS}. \\code{\\$s0} מחזיק את זה.', 'bidi', set()),
    ('ipair60-ok: island then math',  'טקסט \\en{word} $x$ בעברית כאן.',              'bidi', set()),
    # ---- CODE-FRICTION (v3.24, advisory; content-style §5b) ------------------
    ('friction: instr inline',        'הכתובת נטענת ב־\\code{lw \\$t1, -4(\\$t0)} ואז ממשיכים.', 'density', {'CODE-FRICTION'}),
    ('friction-ok: atoms + tight',    'הרגיסטר \\code{\\$s0} ומנמוניק \\code{sll} וביטוי \\code{arr[i]} בשורה.', 'density', set()),
    ('friction-ok: codeline itself',  '\\codeline{lw \\$t1, -4(\\$t0)}',            'density', set()),
    ('friction-ok: listing exempt',   'טקסט עברי.\n\\begin{lstlisting}\nlw $t1, -4($t0)\n\\end{lstlisting}', 'density', set()),
    # ---- v3.41.1: BREAKABLE-VALUE-ISLAND (reader report #3, e18Bb) -----------
    # A value-list island (>=3 math segments + internal space) in RTL prose can
    # line-break at a space; the fragment reads value-first. Display context
    # (center) and short/single-value islands are exempt.
    ('breakisl: rd/rs/rt in prose',   'המילה היא \\en{rd $=2$, rs $=2$, rt $=3$} כלומר.', 'bidi', {'BREAKABLE-VALUE-ISLAND'}),
    ('breakisl: control values',      'ההוראה מקבלת \\en{A $=0$, B $=1$, C $=1$, D $=1$} בלבד.', 'bidi', {'BREAKABLE-VALUE-ISLAND'}),
    ('breakisl-ok: short label',      'ולכן \\en{tag $=25$} ביטים בדיוק.',           'bidi', set()),
    ('breakisl-ok: inside center',    '\\begin{center}\\en{rd $=2$, rs $=2$, rt $=3$}\\end{center}', 'bidi', set()),
    # v3.42.0 — empirical audit round: every flagged form below was RENDER-
    # PROVEN to tear at an internal space (probe classes B/C/D/F), and every
    # -ok form is a calibrated corpus FP class that must stay silent.
    ('breakisl: paren-math form',     'המילה היא \\en{rd \\(=2\\), rs \\(=2\\), rt \\(=3\\)} כלומר.', 'bidi', {'BREAKABLE-VALUE-ISLAND'}),
    ('breakisl: two pairs tear too',  'האותות הם \\en{RegWrite $=1$, MemToReg $=0$} ולכן מחזור אחד.', 'bidi', {'BREAKABLE-VALUE-ISLAND'}),
    ('breakisl: mathless equals',     'האותות הם \\en{InstSRC = 0, RegWrite = 1} ולכן מחזור אחד.', 'bidi', {'BREAKABLE-VALUE-ISLAND'}),
    ('breakisl: island across lines', 'האותות המפוענחים כאן הם \\en{rd $=2$, rs $=2$,\nrt $=3$} וההמשך של המשפט.', 'bidi', {'BREAKABLE-VALUE-ISLAND'}),
    ('breakisl-ok: mention island',   'הצומת \\en{Si$(p)$ / Ge$(n)$} מוליך היטב בטמפרטורת החדר.', 'bidi', set()),
    ('breakisl-ok: escaped dollars',  'נשמרים \\en{\\code{\\$s0}, \\code{\\$ra}, \\code{\\$a0}} במחסנית.', 'bidi', set()),
    ('breakisl-ok: == is a mention',  'הבדיקה \\en{x == 1, y == 2} היא השוואה ולא הצבה.', 'bidi', set()),
    ('breakisl-ok: tabular cell',     '\\en{1 record = 1 byte = 8 bits} & תא בטבלה \\\\', 'bidi', set()),
    ('breakisl-ok: mbox wrapped',     'ולכן (\\mbox{\\en{RegDst=1, ALUSrc=0}}) במחזור בודד.', 'bidi', set()),
    # v3.76 — code-listings + TOC-ownership round. LISTING-SAME-LINE-DROPPED:
    # everything after \begin{lstlisting}(+options) on the SOURCE LINE is
    # consumed by the package (compile-proven: 3/3 shapes warn "Text dropped
    # after begin of listing" and the text is absent from the PDF).
    ('lstdrop76: code after [opts]',  '\\begin{asmblock}\\begin{lstlisting}[style=asm] li t0, 5\n\\end{lstlisting}\\end{asmblock}', 'bidi', {'LISTING-SAME-LINE-DROPPED'}),
    ('lstdrop76: bare code, no opts', '\\begin{asmblock}\\begin{lstlisting} x = 1\n\\end{lstlisting}\\end{asmblock}', 'bidi', {'LISTING-SAME-LINE-DROPPED'}),
    ('lstdrop76: %-tail drops too',   '\\begin{asmblock}\\begin{lstlisting}[style=pystyle] % tail\n\\end{lstlisting}\\end{asmblock}', 'bidi', {'LISTING-SAME-LINE-DROPPED'}),
    ('lstdrop76-ok: canonical form',  '\\begin{asmblock}\\begin{lstlisting}[style=asm]\nli t0, 5\n\\end{lstlisting}\\end{asmblock}', 'bidi', set()),
    ('lstdrop76-ok: opts span lines', '\\begin{asmblock}\\begin{lstlisting}[style=asm,\n  firstnumber=1]\nli t0, 5\n\\end{lstlisting}\\end{asmblock}', 'bidi', set()),
    ('lstdrop76-ok: commented begin', 'טקסט.\n% \\begin{lstlisting} x = 1\nעוד טקסט.', 'bidi', set()),
    # TOC-OVERRIDE-IN-DOCUMENT: a document-layer \l@* redefinition shadows the
    # preamble's measured TOC geometry (the 10-file BLD-38 rollback).
    ('toc76: l@section in document',  '\\makeatletter\n\\renewcommand*\\l@section{\\@dottedtocline{1}{1.5em}{3.0em}}\n\\makeatother\n\\begin{document}\nתוכן עברי.\n\\end{document}', 'bidi', {'TOC-OVERRIDE-IN-DOCUMENT'}),
    ('toc76: patchcmd l@chapter',     '\\begin{document}\n\\makeatletter\\patchcmd{\\l@chapter}{\\bfseries}{\\bfseries\\boldmath}{}{}\\makeatother\n\\end{document}', 'bidi', {'TOC-OVERRIDE-IN-DOCUMENT'}),
    ('toc76-ok: preamble owns l@',    '\\renewcommand*\\l@section{\\@dottedtocline{1}{1.5em}{3.2em}}', 'bidi', set()),
    ('toc76-ok: doc only in comment', '%   \\begin{document}  ...  \\end{document}\n\\renewcommand*\\l@section{\\@dottedtocline{1}{1.5em}{3.2em}}', 'bidi', set()),
    # charset v4.0.1: '%' inside lstlisting is CONTENT — the tail is scanned
    # raw, but printable glyphs covered by the pinned mono face are valid code.
    ('charset76-ok: covered star after % in listing', '\\begin{lstlisting}[style=pystyle]\nx = 1  % tail ★\n\\end{lstlisting}', 'charset', set()),
    ('charset76-ok: covered star before same-line end', '\\begin{lstlisting}\nx = 1 # ★ כאן \\end{lstlisting}', 'charset', set()),
    ('charset76-ok: clean %-tail in listing', '\\begin{lstlisting}[style=asm]\nli t0, 5  # clean 100%\n\\end{lstlisting}', 'charset', set()),
    ('charset76-ok: commented begin no poison', 'טקסט.\n% \\begin{lstlisting}\n% הערה עם ★ בפנים\nעוד.', 'charset', set()),
    ('charset76-ok: prose comment after end tail', '\\begin{lstlisting}\nx = 1\n\\end{lstlisting} % הערה עם ★\nטקסט.', 'charset', set()),
    # v3.76 — LTR-island ALIAS resolution: a same-file \newenvironment over
    # otherlanguage (data-science-exams' qeng) arms the two island rules that
    # were blind to it (17 render-proven sites shipped). Definitions in a
    # sibling macros.tex are shared per-collection by main() — that path is
    # exercised by the cross-file unit below the CASES table.
    ('alias76: list in qeng fires',   '\\newenvironment{qeng}{\\par\\begin{otherlanguage}{english}}{\\end{otherlanguage}\\par}\nטקסט עברי.\n\\begin{qeng}\n\\begin{itemize}\n\\item \\en{alpha}\n\\end{itemize}\n\\end{qeng}', 'bidi', {'LIST-IN-LTR-ISLAND'}),
    ('alias76: tabcap in qeng fires', '\\newenvironment{qeng}{\\par\\begin{otherlanguage}{english}}{\\end{otherlanguage}\\par}\n\\begin{qeng}\n\\begin{tablebox}\n\\tabcap{\\en{Latin caption.}}\n\\end{tablebox}\n\\end{qeng}', 'bidi', {'CAPTION-INSIDE-LTR-ISLAND'}),
    ('alias76: srcfig in island fires', '\\begin{otherlanguage}{english}\n\\srcfig{0.6}{img}{\\en{A caption.}}\n\\end{otherlanguage}', 'bidi', {'CAPTION-INSIDE-LTR-ISLAND'}),
    ('alias76-ok: list after island', '\\newenvironment{qeng}{\\par\\begin{otherlanguage}{english}}{\\end{otherlanguage}\\par}\n\\begin{qeng}\ntext\n\\end{qeng}\n\\begin{itemize}\n\\item \\en{alpha}\n\\end{itemize}', 'bidi', set()),
    ('alias76-ok: non-island wrapper', '\\newenvironment{mybox}{\\par\\small}{\\par}\n\\begin{mybox}\n\\begin{itemize}\n\\item \\en{alpha}\n\\end{itemize}\n\\end{mybox}', 'bidi', set()),
    # v4.7.1 — capability split: bare showonlyrefs keeps
    # normal heading numbers, so it must NOT arm the headings rule.
    ('exm76-ok: showonly does not arm ch-rule', '\\mathtoolsset{showonlyrefs=true}\nראה שאלה \\ref{ch:q2} לעיל.', 'bidi', set()),
    # ---- v3.82 (audit finding A): LIST-IN-LTR-ISLAND sees LIST-wrapper
    # aliases, not only ISLAND aliases. v3.76 resolved one end of the rule and
    # left the twin dimension literal (itemize|enumerate|description), so
    # data-science-exams' `choices` — a \newenvironment over the `list`
    # primitive, used 60x and ALWAYS inside \begin{qeng} — was structurally
    # invisible, and the shipped 172-page PDF puts its 216 (a)-(d) labels
    # 24.6-25.7pt into the left margin (x=39.5/40.2/40.6 vs a text block at
    # x=65.2) behind an affirmative "clean".
    ('lstal82: bare \\begin{list} in island', '\\begin{otherlanguage}{english}\n\\begin{list}{}{\\setlength{\\leftmargin}{2.2em}}\n\\item[(a)] alpha\n\\end{list}\n\\end{otherlanguage}', 'bidi', {'LIST-IN-LTR-ISLAND'}),
    ('lstal82: same-line list alias',  '\\newenvironment{qeng}{\\par\\begin{otherlanguage}{english}}{\\end{otherlanguage}\\par}\n\\newenvironment{choices}{\\par\\begin{list}{}{}}{\\end{list}\\par}\n\\begin{qeng}\n\\begin{choices}\n\\item[(a)] alpha\n\\end{choices}\n\\end{qeng}', 'bidi', {'LIST-IN-LTR-ISLAND'}),
    # THE LIVE SHAPE: macros.tex:63 spreads the definition over four lines, so
    # a same-line collector (v3.76's lookahead, and the obvious port of it)
    # still returns nothing and all 54 built sites stay invisible. This case
    # is the one that fails if the collector is narrowed back.
    ('lstal82: multi-line list alias', '\\newenvironment{qeng}{\\par\\begin{otherlanguage}{english}}{\\end{otherlanguage}\\par}\n\\newenvironment{choices}{%\n  \\setcounter{chcnt}{0}\\par\\smallskip\n  \\begin{list}{}{\\setlength{\\leftmargin}{2.2em}}%\n}{\\end{list}\\par\\smallskip}\n\\begin{qeng}\n\\begin{choices}\n\\item[(a)] alpha\n\\end{choices}\n\\end{qeng}', 'bidi', {'LIST-IN-LTR-ISLAND'}),
    ('lstal82-ok: list alias outside island', '\\newenvironment{choices}{\\par\\begin{list}{}{}}{\\end{list}\\par}\n\\begin{choices}\n\\item[(a)] alpha\n\\end{choices}', 'bidi', set()),
    # the collector reads the BEGIN code only: a wrapper whose list appears in
    # its END group opens no list at \begin time and must not be collected.
    ('lstal82-ok: list only in END code', '\\newenvironment{qeng}{\\par\\begin{otherlanguage}{english}}{\\end{otherlanguage}\\par}\n\\newenvironment{tailer}{\\par\\small}{\\begin{itemize}\\item x\\end{itemize}}\n\\begin{qeng}\n\\begin{tailer}\ntext\n\\end{tailer}\n\\end{qeng}', 'bidi', set()),
    # ---- v3.82 (audit finding C): a ONE-LINE \begin{verbatim}..\end{verbatim}
    # used to latch in_verbatim and skip every rule to EOF behind "✓ clean",
    # exit 0 — with ci.yml running this gate without `|| true`, rc=0 IS the
    # pass signal. The closing scan lived only behind `if in_verbatim:`, so it
    # first ran on the NEXT line. Same class as BLD-41. The positives below
    # each carry a render-proven defect AFTER the one-liner.
    ('vb82: one-line verbatim no latch', 'טקסט.\n\\begin{verbatim}literal text\\end{verbatim}\nציטוט ``שגוי`` כאן.', 'bidi', {'QUOTES'}),
    # the end marker is searched on the RAW line: '%' is literal CONTENT inside
    # a verbatim body, so comment-stripping would hide the \end and re-latch.
    ('vb82: %-in-body one-liner closes', '\\begin{verbatim}100% off\\end{verbatim}\nציטוט ``שגוי`` כאן.', 'bidi', {'QUOTES'}),
    ('vb82: one-line lstlisting no latch', '\\begin{asmblock}\n\\begin{lstlisting} x = 1\\end{lstlisting}\n\\end{asmblock}\nציטוט ``שגוי`` כאן.', 'bidi', {'LISTING-SAME-LINE-DROPPED', 'QUOTES'}),
    # the BODY is still literal — not latching must not mean scanning it.
    ('vb82-ok: one-line body not scanned', '\\begin{verbatim}``literal``\\end{verbatim}\nטקסט תקין.', 'bidi', set()),
    ('vb82-ok: multi-line verbatim exempt', '\\begin{verbatim}\n``literal`` \\SI{5}{\\meter}\n\\end{verbatim}\nטקסט תקין.', 'bidi', set()),
    # ---- v3.82 (audit finding F): TOC-OVERRIDE-IN-DOCUMENT widened to the
    # spellings the documented contract already promised ("any
    # \l@chapter/section/subsection surgery"). \def inside \makeatletter is
    # the most idiomatic form of the patch and reproduces BLD-38's rollback
    # exactly (TOC number<->title gap 30.65 -> 28.25pt) while the v3.76
    # pattern printed clean.
    ('toc82: \\def l@section',        '\\begin{document}\n\\makeatletter\n\\def\\l@section#1#2{\\@dottedtocline{1}{1.5em}{3.0em}{#1}{#2}}\n\\makeatother\n\\end{document}', 'bidi', {'TOC-OVERRIDE-IN-DOCUMENT'}),
    ('toc82: \\let l@subsection',     '\\begin{document}\n\\makeatletter\\let\\l@subsection\\l@section\\makeatother\n\\end{document}', 'bidi', {'TOC-OVERRIDE-IN-DOCUMENT'}),
    ('toc82: \\RenewDocumentCommand', '\\begin{document}\n\\makeatletter\n\\RenewDocumentCommand{\\l@section}{mm}{\\@dottedtocline{1}{1.5em}{3.0em}{#1}{#2}}\n\\makeatother\n\\end{document}', 'bidi', {'TOC-OVERRIDE-IN-DOCUMENT'}),
    # the preamble legitimately OWNS this geometry — the rule is keyed on
    # \begin{document} and must stay silent one layer down.
    ('toc82-ok: \\def in preamble',   '\\makeatletter\n\\def\\l@section#1#2{\\@dottedtocline{1}{1.5em}{3.2em}{#1}{#2}}\n\\makeatother', 'bidi', set()),
    # \let\<save>\l@section stores the original; it changes no geometry.
    ('toc82-ok: \\let save idiom',    '\\begin{document}\n\\makeatletter\\let\\lakinoldsection\\l@section\\makeatother\n\\end{document}', 'bidi', set()),
    # ---- v3.82 (audit finding L): BREAKABLE-VALUE-ISLAND counts a QUOTED
    # value. Four items shipped in the same commit that wrote the host
    # collection's ">=2 name = value pairs -> block form" authoring rule,
    # because the value-side class
    # excluded " and '. Direction settled by render, not taste: compiled in a
    # forced-wrap minipage with the repo preamble, \en{Dense layer (units =
    # 100, activation = "relu")} and its unquoted twin tear at the SAME place
    # — both break after "(units = 100," and orphan "activation = ...)" onto
    # the next line. The quote does not remove the internal space, so the
    # doctrine was right and the regex was under-inclusive.
    ('brkq82: double-quoted value',   'ההגדרה \\en{Dense layer (units = 100, activation = "relu")} כאן.', 'bidi', {'BREAKABLE-VALUE-ISLAND'}),
    ('brkq82: single-quoted value',   "ההגדרה \\en{Dense layer (units = 100, activation = 'relu')} כאן.", 'bidi', {'BREAKABLE-VALUE-ISLAND'}),
    # one pair is a MENTION island (BIDI-28's documented limit) — the >=2
    # threshold is unchanged, only the character class widened.
    ('brkq82-ok: one quoted pair',    'ההגדרה \\en{activation = "relu"} בלבד.', 'bidi', set()),
    ('brkq82-ok: empty string in code', "מאתחלים מחרוזת ריקה: \\code{s = ''} וממשיכים.", 'bidi', set()),
    # ---- v4.16.0 (BIDI-81): BREAKABLE-QUOTED-ISLAND -------------------------
    # BIDI-26's mechanism is a line break at an INTERNAL SPACE inside an LTR
    # island; the "name = value pairs" requirement was a property of the
    # EXAMPLE, not of the mechanism. Render-measured (26-offset sweep, one
    # paragraph per page, glyph geometry identical over 4 clean compiles):
    # an 8-word prose island tears at 10/26 line offsets, a 6-word one at
    # 6/26, a 3-word one at 2/26 and the value-list exemplar at 3/26 — so the
    # rule that existed fired on the RAREST shape. \mbox'd islands of ANY
    # length and single-word islands tear at 0/26.
    # Every positive below was found LIVE and confirmed on the page: the rr
    # message (missing-semester p97, the reader report), the Kernighan
    # epigraph (p94 — "…coupled with judiciously" / ".Brian Kernighan —
    # placed print statements”", the attribution reading BEFORE the end of
    # the quote), and \code{pkill -f 'sleep 12345'} (p41, split into
    # "pkill -f 'sleep" / "12345'" — an uncopyable command).
    # Every -ok form is a measured corpus class that must stay silent.
    ('brkq: terminal message',       'ההרצה נכשלה: \\en{“Unable to open performance counter with \'perf\\_event\\_open\'”} ולכן.', 'bidi', {'BREAKABLE-QUOTED-ISLAND'}),
    ('brkq: shell arg in code',      'והרוג עם \\code{pkill -f \'sleep 12345\'} בלי מספר תהליך.', 'bidi', {'BREAKABLE-QUOTED-ISLAND'}),
    ('brkq: double-quoted shell arg','כדי לבקש אחת בשם אחד: \\code{ls "My Photos"} בדיוק.', 'bidi', {'BREAKABLE-QUOTED-ISLAND'}),
    ('brkq: title inside citation',  'מבוסס על \\en{Patterson, “Computer Organization and Design” (5th ed.)} בלבד.', 'bidi', {'BREAKABLE-QUOTED-ISLAND'}),
    # TeX-style quotes are already banned in prose by QUOTES; the pair is
    # recognised here too so the rule does not depend on which mark an author
    # reached for. Both flags fire, and that is the documented interaction.
    ('brkq: TeX quote ligatures',    'הספר \\en{``Structured Computer Organization\'\'} הוא המקור.', 'bidi', {'BREAKABLE-QUOTED-ISLAND', 'QUOTES'}),
    ('brkq: short quoted phrase',    'למה \\en{“most likely”} ולא משהו חזק יותר.', 'bidi', {'BREAKABLE-QUOTED-ISLAND'}),
    ('brkq: island across lines',    'ההודעה שהתקבלה היא \\en{“Unable to open performance\ncounter”} וההמשך של המשפט.', 'bidi', {'BREAKABLE-QUOTED-ISLAND'}),
    # the cure, in both nesting orders (v4.7.7) and partial (\mbox on the
    # QUOTE only, so a long citation keeps its natural break points)
    ('brkq-ok: whole body boxed',    'ההרצה נכשלה: \\en{\\mbox{“Unable to open performance counter”}} ולכן.', 'bidi', set()),
    ('brkq-ok: mbox outside island', 'הקובץ מכיל \\mbox{\\en{“hello world”}} ותו לא.', 'bidi', set()),
    ('brkq-ok: only the quote boxed','מבוסס על \\en{Patterson, \\mbox{“Computer Organization”} (5th ed.)} בלבד.', 'bidi', set()),
    ('brkq-ok: codeline is display', 'ההרצה נכשלה:\n\\codeline{Unable to open performance counter}', 'bidi', set()),
    # measured-correct classes: no internal space, a possessive/contraction
    # apostrophe, a math prime, a table cell, display context, and a plain
    # multi-word term (BIDI-29 — guidance, deliberately not this flag)
    ('brkq-ok: no space in quotes',  'ולא \\en{“always”} אלא לפעמים.',            'bidi', set()),
    ('brkq-ok: possessive',          'הכלל הוא \\en{Amdahl\'s Law} ותו לא.',            'bidi', set()),
    ('brkq-ok: contraction',         'ההערה אומרת \\en{do not overfit} וזהו.',          'bidi', set()),
    ('brkq-ok: plural possessive',   'מדובר ב\\en{users\' data and servers\' logs} בלבד.', 'bidi', set()),
    ('brkq-ok: math prime',          'הנגזרות \\en{$f\'(x)$ and $g\'(y)$} חיוביות.',     'bidi', set()),
    ('brkq-ok: tabular cell',        "\\code{'Wireless Headphones'} & תא בטבלה \\\\", 'bidi', set()),
    ('brkq-ok: inside center',       '\\begin{center}\\en{“hello world”}\\end{center}', 'bidi', set()),
    ('brkq-ok: unquoted term',       'המטמון הוא \\en{Direct Mapped} בלבד.',            'bidi', set()),

    # v4.19.0: the island's third spelling. \en expands to exactly this, so the
    # rule was blind to a literal written the long way -- including one in the
    # package's own example_math.tex.
    ('brkq: explicit foreignlanguage', 'ההרצה נכשלה: \\foreignlanguage{english}{“Unable to open counter”} ולכן.', 'bidi', {'BREAKABLE-QUOTED-ISLAND'}),
    ('brkq: foreignlanguage citation', 'מבוסס על \\foreignlanguage{english}{N. D. Mermin, “Quantum Computer Science” (2007)} בלבד.', 'bidi', {'BREAKABLE-QUOTED-ISLAND'}),
    ('brkq-ok: foreignlanguage boxed', 'מבוסס על \\foreignlanguage{english}{N. D. Mermin, \\mbox{“Quantum Computer Science”} (2007)} בלבד.', 'bidi', set()),
    ('brkq-ok: foreignlanguage possessive', 'הכלל הוא \\foreignlanguage{english}{Amdahl\'s Law} ותו לא.', 'bidi', set()),
    ('brkq-ok: other language island', 'המונח \\foreignlanguage{french}{“tour de force”} כאן.', 'bidi', set()),

    # ---- v3.83: the BIDI-71 class, closed as a CLASS (round-10 audit) --------
    # v3.82 fixed ONE shape (the one-liner). Adversarial probe found the latch
    # alive through dead source and through a name-mismatched closer, both
    # behind an affirmative "clean"; the \iffalse variant was compile-proven to
    # lose live rendered content. The cure is the EOF guard: silence is never
    # reported as health.
    ('vb83-iffalse: begin-verbatim in dead source -> must be REPORTED',
     '\u05d8\u05e7\u05e1\u05d8.\n\\iffalse \\begin{verbatim} \\fi\nHe said ``hi\'\' to me.\n',
     'bidi', {'UNTERMINATED-LITERAL-BLOCK'}),
    ('vb83-mismatch: end names a different env -> must be REPORTED',
     '\u05d8\u05e7\u05e1\u05d8.\n\\begin{verbatim}x\\end{Verbatim}\nHe said ``hi\'\' to me.\n',
     'bidi', {'UNTERMINATED-LITERAL-BLOCK'}),
    ('vb83-ok: properly closed verbatim leaves no residue',
     '\u05d8\u05e7\u05e1\u05d8.\n\\begin{verbatim}\nq = ``x\'\'\n\\end{verbatim}\n\u05e1\u05d5\u05e3.\n',
     'bidi', set()),
    ('vb83-ok: minted body is literal, not prose (was a QUOTES false alarm)',
     '\u05d8\u05e7\u05e1\u05d8.\n\\begin{minted}{python}\nq = ``x\'\'\n\\end{minted}\n\u05e1\u05d5\u05e3.\n',
     'bidi', set()),
    ('vb83-ok: verbatim-star body is literal too',
     '\u05d8\u05e7\u05e1\u05d8.\n\\begin{verbatim*}\n50% literal\n\\end{verbatim*}\n\u05e1\u05d5\u05e3.\n',
     'bidi', set()),
    ('vb83-ok: a foreign end inside a body does not close it early',
     '\u05d8\u05e7\u05e1\u05d8.\n\\begin{verbatim}\ntext \\end{lstlisting} more\nq = ``x\'\'\n\\end{verbatim}\n\u05e1\u05d5\u05e3.\n',
     'bidi', set()),
    ('vb83-ok: one-line verbatim still releases (v3.82 pin, kept)',
     '\u05d8\u05e7\u05e1\u05d8.\n\\begin{verbatim}x\\end{verbatim}\n\u05e2\u05d1\u05e8\u05d9\u05ea --- \u05e2\u05d5\u05d3.\n',
     'bidi', {'HEBREW-DOUBLE-HYPHEN'}),
    # ---- SPLIT-HEBREW-IN-DISPLAY (v4.2.1, BIDI-75) --------------------------
    # Display math is LTR; a Hebrew sentence/list split across sibling \text{}
    # blocks in ONE row renders its segments in reversed reading order.
    # Render-proven: probe halves at x=200/x=312, and a shipped answer tuple
    # printed opposite to the question's own RTL presentation of the same
    # list. Fires only on ,/; punct-only gaps \u2014 the three real sites' shape;
    # the colon chain register and pure-spacing gaps are sanctioned/unproven.
    ('shd: probe two halves ;\\qquad',
     '\\[\n\\text{\u05d4\u05d5\u05d0 \u05d7\u05dc\u05e7 \u05de\u05d4\u05e0\u05ea\u05d5\u05e0\u05d9\u05dd};\n\\qquad\n\\text{\u05d4\u05d5\u05d0 \u05d0\u05d9\u05e0\u05d5 \u05d9\u05d3\u05e2 \u05de\u05d5\u05e7\u05d3\u05dd.}\n\\]',
     'bidi', {'SPLIT-HEBREW-IN-DISPLAY'}),
    ('shd: shipped comma tuple in \\bigl parens',
     '\\begin{equation*}\n\\correct{a}\\ \\Longleftarrow\\ \\bigl(\\text{\u05e2\u05d5\u05dc\u05d4},\\ \\text{\u05d9\u05d5\u05e8\u05d3\u05ea},\\ \\text{\u05dc\u05d0 \u05d9\u05d3\u05d5\u05e2}\\bigr)\n\\end{equation*}',
     'bidi', {'SPLIT-HEBREW-IN-DISPLAY'}),
    ('shd: align-row label pair before &',
     '\\begin{align*}\n\\Bias\\ \\text{\u05d2\u05d1\u05d5\u05d4\u05d4},\\ \\text{\u05ea\u05ea\u05be\u05d4\u05ea\u05d0\u05de\u05d4}\\ &\\Longleftarrow\\ E\n\\end{align*}',
     'bidi', {'SPLIT-HEBREW-IN-DISPLAY'}),
    ('shd: plain comma pair in \\[..\\]',
     '\\[\n\\text{\u05e2\u05d5\u05e0\u05e9}, \\text{\u05d0\u05e0\u05d8\u05e8\u05d5\u05e4\u05d9\u05d4}\n\\]',
     'bidi', {'SPLIT-HEBREW-IN-DISPLAY'}),
    ('shd-ok: colon chain register (quickmaps, render-reviewed)',
     '\\[\nk\\ \\text{\\h{\u05e7\u05d8\u05df}}:\\ \\ \\text{\\h{\u05d2\u05de\u05d9\u05e9\u05d5\u05ea}}\\uparrow\\ \\to\\ B\n\\]',
     'bidi', set()),
    ('shd-ok: ONE \\text block holds the whole statement (the sanctioned fix)',
     '\\[\n\\text{\u05de\u05e9\u05e4\u05d8 \u05e9\u05dc\u05dd \u05d1\u05e2\u05d1\u05e8\u05d9\u05ea, \u05e2\u05dd \u05e4\u05e1\u05d9\u05e7}\n\\]',
     'bidi', set()),
    ('shd-ok: math atoms between the segments',
     '\\[\n\\text{\u05d0\u05dd}\\ x>0,\\ \\text{\u05d0\u05d6}\\ y=1\n\\]',
     'bidi', set()),
    ('shd-ok: cases cells isolate (blanked like the BOXED rule)',
     '\\[\nf=\\begin{cases}\\text{\u05d0\u05e4\u05e1}, & x<0\\\\ \\text{\u05d0\u05d7\u05d3}, & x\\ge 0\\end{cases}\n\\]',
     'bidi', set()),
    ('shd-ok: segments on separate align rows',
     '\\begin{align*}\n\\text{\u05e2\u05dc\u05d9\u05d9\u05d4}, &= 1\\\\\n\\text{\u05d9\u05e8\u05d9\u05d3\u05d4}, &= 2\n\\end{align*}',
     'bidi', set()),
    ('shd-ok: inline math is out of scope',
     '\u05d8\u05e7\u05e1\u05d8 $\\text{\u05d0}, \\text{\u05d1}$ \u05d8\u05e7\u05e1\u05d8.',
     'bidi', set()),
    ('shd-ok: Latin-only siblings',
     '\\[\n\\text{if}, \\text{then}\n\\]',
     'bidi', set()),
    ('shd-ok: \\\\[2pt] is a line break, not a display (BIDI-62 anchor)',
     '\u05e9\u05d5\u05e8\u05d4 \u05e8\u05d0\u05e9\u05d5\u05e0\u05d4 \\\\[2pt]\n\\text{\u05d0}, \\text{\u05d1} \u05d1\u05e4\u05e8\u05d5\u05d6\u05d4 \u05e8\u05d2\u05d9\u05dc\u05d4.',
     'bidi', set()),
    # ---- PGFPLOTS-CONTOUR-EXTERNAL (v4.26.0, BLD-70) -------------------------
    # contour lua / gnuplot / external compute contours at COMPILE time through
    # a generated script the gate cannot run, and a result left in the source
    # directory is read instead: measured, the gnuplot form with a stale table
    # printed "✓ clean build" and published the old contour. Fires where
    # pgfkeys reads the key; silent where prose, comments or literals NAME it,
    # and on the families that need no external program.
    ('contour70: lua, the BLD-70 minimal plot',
     '\\begin{tikzpicture}\n\\begin{axis}[view={0}{90}]\n\\addplot3[contour lua={levels={1,2}}, domain=-2:2, samples=21] {x^2+y^2};\n\\end{axis}\n\\end{tikzpicture}',
     'hazards', {'PGFPLOTS-CONTOUR-EXTERNAL'}),
    ('contour70: gnuplot (shell escape, stale table)',
     '\\addplot3[contour gnuplot={levels={1,2}}, domain=-2:2] {x^2+y^2};',
     'hazards', {'PGFPLOTS-CONTOUR-EXTERNAL'}),
    ('contour70: external, the common base key',
     '\\addplot3[contour external={script={s}, cmd={true}}] {x^2};',
     'hazards', {'PGFPLOTS-CONTOUR-EXTERNAL'}),
    ('contour70: bare key last in the list',
     '\\addplot3[domain=-2:2, contour lua] {x^2};',
     'hazards', {'PGFPLOTS-CONTOUR-EXTERNAL'}),
    ('contour70: key split over two lines',
     '\\addplot3[\n  domain=-2:2,\n  contour\n  lua={levels={1}},\n] {x^2};',
     'hazards', {'PGFPLOTS-CONTOUR-EXTERNAL'}),
    ('contour70: addplot3+ with spaces',
     '\\addplot3 + [contour gnuplot] {x^2};',
     'hazards', {'PGFPLOTS-CONTOUR-EXTERNAL'}),
    ('contour70: style defined in pgfplotsset',
     '\\pgfplotsset{mycontour/.style={contour lua={levels={1,2}}}}',
     'hazards', {'PGFPLOTS-CONTOUR-EXTERNAL'}),
    ('contour70: every axis plot in axis options',
     '\\begin{axis}[view={0}{90}, every axis plot/.append style={contour lua}]\n\\end{axis}',
     'hazards', {'PGFPLOTS-CONTOUR-EXTERNAL'}),
    ('contour70: full key path in pgfkeys',
     '\\pgfkeys{/pgfplots/contour gnuplot={number=5}}',
     'hazards', {'PGFPLOTS-CONTOUR-EXTERNAL'}),
    ('contour70: plot inside a macro body',
     '\\newcommand{\\cplot}[1]{\\addplot3[contour lua={levels={#1}}] {x^2};}',
     'hazards', {'PGFPLOTS-CONTOUR-EXTERNAL'}),
    ('contour70-ok: contour prepared on precomputed data',
     '\\addplot3[contour prepared] table {c.dat};\n\\addplot3[contour prepared={labels=false}] coordinates {(1,0,1) (0,1,1)};',
     'hazards', set()),
    ('contour70-ok: contour filled is drawn by TeX',
     '\\addplot3[contour filled={number=4}, domain=-2:2] {x^2+y^2};',
     'hazards', set()),
    ('contour70-ok: surf and shared contour/ keys',
     '\\addplot3[surf, domain=-2:2] {x^2+y^2};\n\\pgfplotsset{contour/number=5, contour/labels=false}',
     'hazards', set()),
    ('contour70-ok: a redefinition path is not a use',
     '\\pgfplotsset{contour lua/.style={contour prepared}, contour external/cmd={x}}',
     'hazards', set()),
    ('contour70-ok: prose names the key',
     '\u05d4\u05d0\u05e4\u05e9\u05e8\u05d5\u05ea \\code{contour lua} \u05d5\u05d2\u05dd \\en{contour gnuplot} \u05d0\u05d9\u05e0\u05df \u05e2\u05d5\u05d1\u05e8\u05d5\u05ea \u05d0\u05ea \u05d4\u05e9\u05e2\u05e8.',
     'hazards', set()),
    ('contour70-ok: the fleet comment (lifting-optimization)',
     "% precomputed with contourpy: pgfplots' contour lua cannot pass the build gate\n% \\addplot3[contour lua] {x};\n\\addplot[forget plot] coordinates {(0,1) (1,0)};",
     'hazards', set()),
    ('contour70-ok: listing and verbatim bodies',
     '\\begin{lstlisting}\n\\addplot3[contour lua] {x^2};\n\\end{lstlisting}\n\\begin{verbatim}\n\\addplot3[contour gnuplot] {x};\n\\end{verbatim}',
     'hazards', set()),
    ('contour70-ok: inline literals',
     '\\verb|\\addplot3[contour lua] {x};| \u05d5\u05d2\u05dd \\lstinline|\\addplot3[contour gnuplot]|',
     'hazards', set()),
    ('contour70-ok: a node label is text',
     '\\begin{tikzpicture}\\node {contour lua};\\end{tikzpicture}',
     'hazards', set()),
    ('contour70-ok: library name and near-miss words',
     '\\usepgfplotslibrary{contourlua}\n\\addplot3[contours lua, contour luax] {x};',
     'hazards', set()),
]


def run_case(name, src, which, expect):
    # v3.23.1: system temp dir, NOT dir=HERE — deployed skills are mounted
    # read-only (e.g. /mnt/skills/user), and writing scratch files into the
    # skill's own scripts/ dir crashed there with PermissionError (measured
    # as an unprivileged user). Checker paths are absolute; snippets include
    # nothing — nothing needs the cwd.
    with tempfile.NamedTemporaryFile('w', suffix='.tex', delete=False,
                                     encoding='utf-8') as f:
        f.write(src + '\n')
        path = f.name
    try:
        # v4.3.1: call the exact checker entrypoints IN PROCESS. The former
        # corpus launched a fresh Python interpreter for every one of 517 cases;
        # measured runtime exceeded 4 minutes before completing, making FAST a
        # poor edit-time guard. The checkers keep their per-invocation state
        # local, so process isolation bought startup cost, not test isolation.
        # Temp files remain real files, preserving path/scope semantics.
        buf = io.StringIO()
        with redirect_stdout(buf), redirect_stderr(buf):
            if which == 'bidi':
                # Corpus cases are deliberately partial source snippets, not
                # executable include projects. Keep every source guard active
                # without resolving illustrative operands or caller roots.
                rc = bidi_checker.main([BIDI, path], resolve_includes=False)
            elif which == 'charset':
                rc = charset_checker.main([CHARSET, path])
            elif which == 'hazards':
                rc = hazard_checker.main([path])
            else:
                rc = density_checker.main([path])
        out = buf.getvalue()
        base = os.path.basename(path)
        hits = set()
        for line in out.splitlines():
            if line.startswith(base) or line.startswith(path):
                m = re.search(r'\[([A-Z-]+)\]', line)
                hits.add(m.group(1) if m else 'STRAY')
        # Exact semantics: every expected rule fired; if none expected, nothing
        # fired. The process status is part of the contract too: a positive
        # bidi/charset finding is exit 1, a clean input is exit 0, and a crash
        # (2+) can never impersonate either result. Density findings are
        # advisory by design and therefore return 0.
        # v3.71: STRICT equality, not issubset. Under issubset an over-firing
        # checker was invisible on every positive case — mutation-proven: guards
        # whose removal provably over-fires (the \text{} exemption on
        # PUNCT-RAW-IN-MATH, the english_ctx gate on BARE-IDENT-NEXT-TO-MATH)
        # SURVIVED the whole suite, because all FP detection rode on the clean
        # cases alone. With equality every positive case is also an FP test:
        # a case that legitimately fires several rules lists ALL of them.
        hits_ok = hits == expect if expect else (len(hits) == 0)
        expected_rc = 1 if which in {"bidi", "charset", "hazards"} and expect else 0
        ok = hits_ok and rc == expected_rc
        if rc != expected_rc:
            hits.add(f"EXIT-{rc}")
        return ok, hits
    finally:
        os.unlink(path)


_PART_ITEMIZE = ('\\begin{qeng}\n\\begin{itemize}\n\\item \\en{alpha}\n'
                 '\\end{itemize}\n\\end{qeng}\n')
_PART_CHOICES = ('\\begin{qeng}\n\\begin{choices}\n\\item[(a)] alpha\n'
                 '\\end{choices}\n\\end{qeng}\n')


def run_scope_case(name, macros_body, expect_flag, shape='ci',
                   part_body=_PART_ITEMIZE):
    """v3.76: cross-FILE alias sharing — main() collects the wrapper
    definitions of a collection and passes them to every file of that
    collection. run_case() is single-file, so this unit builds a real
    src/macros.tex + src/parts/a.tex pair on disk and invokes the checker the
    way a caller actually would.

    v3.82 (audit finding B) — SHAPE is now a parameter, because v3.76's scope
    test was a substring test on the argv string (`if '/src/' not in path`)
    and this unit only ever exercised the ONE shape that test could pass.
    v3.83 CORRECTION: v3.82 published "CI shape 18 hits" here. That number
    is not reproducible in any shape and is withdrawn.
    Re-derived by independent audit — v3.82's RULES with v3.76's '/src/'
    scoping restored, on the pre-fix sources: CI shape 64 findings (60
    LIST-IN-LTR-ISLAND + 4 BREAKABLE-VALUE-ISLAND) against 4 findings and 2
    non-zero exits for the one-file-at-a-time loop that every authoring
    guide in the host repo prescribed at the time (three separate
    documents, checked). The asymmetry is real and large;
    the published pair had mixed measurements from two different checkers.
    A writer following the documented loop shipped 60 of 64 defects behind a
    green checker.

      'ci'     macros.tex + the part in ONE invocation, under coll/src/.
      'single' the part ALONE — the prescribed authoring loop. The alias must
               come off the DISK (sibling ../macros.tex), not off argv.
      'flat'   both files in a build_<id>/ directory with no 'src' component
               anywhere in the path, invoked from inside it.
      'link'   the part reached through a SYMLINK from an unrelated directory
               (v3.83: abspath does not resolve links, so scope resolved to
               the link's own directory and a byte-identical file came back
               clean while the real path exited 1).
      'pre'    the alias defined in preamble.tex instead of macros.tex — the
               file 15 of this repo's 16 alias definitions actually live in
               (v3.83: only macros.tex was ingested, so finding B's fix was
               one filename short of closing).

    The hit is attributed to the PART's own path, so a rule that fired on
    macros.tex instead cannot pass the positive."""
    import shutil
    d = tempfile.mkdtemp()
    try:
        if shape == 'flat':
            src = os.path.join(d, 'build_7f3a2c1')
            os.makedirs(src)
            mp, pp = (os.path.join(src, 'macros.tex'),
                      os.path.join(src, 'a.tex'))
        else:
            src = os.path.join(d, 'coll', 'src')
            os.makedirs(os.path.join(src, 'parts'))
            mp, pp = (os.path.join(src, 'macros.tex'),
                      os.path.join(src, 'parts', 'a.tex'))
        if shape == 'pre':
            mp = os.path.join(os.path.dirname(mp), 'preamble.tex')
        with open(mp, 'w', encoding='utf-8') as f:
            f.write(macros_body + '\n')
        with open(pp, 'w', encoding='utf-8') as f:
            f.write(part_body)
        if shape == 'link':
            link = os.path.join(d, 'elsewhere.tex')
            os.symlink(pp, link)
            pp = link
        argv = [pp] if shape in ('single', 'link', 'pre') else [mp, pp]
        buf = io.StringIO()
        old_cwd = os.getcwd()
        try:
            if shape == 'flat':
                os.chdir(src)
            with redirect_stdout(buf), redirect_stderr(buf):
                rc = bidi_checker.main([BIDI] + argv, resolve_includes=False)
        finally:
            os.chdir(old_cwd)
        out = buf.getvalue()
        fired = any(l.startswith(pp) and 'LIST-IN-LTR-ISLAND' in l
                    for l in out.splitlines())
        expected_rc = 1 if expect_flag else 0
        ok = ((fired if expect_flag else
               'LIST-IN-LTR-ISLAND' not in out)
              and rc == expected_rc)
        return ok, out
    finally:
        shutil.rmtree(d, ignore_errors=True)


_QENG = ('\\newenvironment{qeng}{\\par\\begin{otherlanguage}{english}}'
         '{\\end{otherlanguage}\\par}')
# the live data-science-exams pair, byte-shape included: `choices` is defined
# over four source lines, so a same-line alias collector sees nothing.
_QENG_CHOICES = _QENG + (
    '\n\\newcounter{chcnt}\n'
    '\\newenvironment{choices}{%\n'
    '  \\setcounter{chcnt}{0}\\par\\smallskip\n'
    '  \\begin{list}{}{\\setlength{\\leftmargin}{2.2em}}%\n'
    '}{\\end{list}\\par\\smallskip}')

SCOPE_CASES = [
    # ---- v3.83 (round-10 audit): two shapes finding B's fix did not reach ---
    ('scope83: symlinked part still resolves its collection alias',
     _QENG, True, 'link'),
    ('scope83: alias defined in preamble.tex, not macros.tex',
     _QENG, True, 'pre'),
    ('scope83-ok: symlinked part, alias absent -> silent',
     '\\newcommand{\\nothing}{}', False, 'link'),
    ('scope76: sibling macros arms part', _QENG, True),
    ('scope76-ok: non-island sibling def',
     '\\newenvironment{qeng}{\\par\\small}{\\par}', False),
    # v3.82 finding B — the SINGLE-FILE shape, which returned "✓ clean" and
    # exit 0 on this exact input before the scope was resolved from disk.
    ('scope82: single-file shape arms part', _QENG, True, 'single'),
    ('scope82-ok: single-file non-island', '\\newenvironment{qeng}{\\par\\small}{\\par}',
     False, 'single'),
    # ...and the build_<id>/ shape, where NO path contains '/src/' at all.
    ('scope82: build_<id> shape arms part', _QENG, True, 'flat'),
    ('scope82-ok: build_<id> non-island', '\\newenvironment{qeng}{\\par\\small}{\\par}',
     False, 'flat'),
    # v3.82 finding A x B — both aliases must cross the file boundary in every
    # shape: `choices` is a LIST alias, `qeng` an ISLAND alias, and the live
    # defect needs both resolved at once.
    ('scope82: choices+qeng, ci shape', _QENG_CHOICES, True, 'ci', _PART_CHOICES),
    ('scope82: choices+qeng, single file', _QENG_CHOICES, True, 'single', _PART_CHOICES),
    ('scope82: choices+qeng, build_<id>', _QENG_CHOICES, True, 'flat', _PART_CHOICES),
    # a `choices` over a non-island wrapper of the same names stays silent —
    # the list alias alone must not arm the rule.
    ('scope82-ok: choices in non-island',
     '\\newenvironment{qeng}{\\par\\small}{\\par}\n'
     '\\newenvironment{choices}{\\par\\begin{list}{}{}}{\\end{list}\\par}',
     False, 'ci', _PART_CHOICES),
]


def main():
    failures = []
    for name, src, which, expect in CASES:
        ok, hits = run_case(name, src, which, expect)
        status = 'ok ' if ok else 'FAIL'
        print(f"  [{status}] {name:34} expected={sorted(expect) or 'clean'} got={sorted(hits) or 'clean'}")
        if not ok:
            failures.append(name)
    for _sc in SCOPE_CASES:
        name, macros_body, expect_flag = _sc[0], _sc[1], _sc[2]
        ok, _out = run_scope_case(name, macros_body, expect_flag, *_sc[3:])
        status = 'ok ' if ok else 'FAIL'
        print(f"  [{status}] {name:34} expected={'fires' if expect_flag else 'clean'}")
        if not ok:
            failures.append(name)
    print('-' * 72)
    _total = len(CASES) + len(SCOPE_CASES)
    if failures:
        print(f"✗ selftest: {len(failures)}/{_total} case(s) DRIFTED: {failures}")
        return 1
    print(f"✓ selftest: all {_total} cases pass — checkers match the verified corpus.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
