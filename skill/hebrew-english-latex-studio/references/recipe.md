# מתכון בנייה: LuaLaTeX לעברית, אנגלית ומתמטיקה

מסמך זה מפרט התקנה, מבנה פרויקט, metadata, קומפילציה ופתרון תקלות. מקור
האמת למקרואים ולחבילות הוא `assets/preamble.tex`; אין לשכפל ממנו פרמבול
מקוצר.

## תוכן עניינים

- [תמיכה וגבול אמון](#תמיכה-וגבול-אמון)
- [דרישות והתקנה](#דרישות-והתקנה)
- [מבנה פרויקט](#מבנה-פרויקט)
- [פונטים וכיסוי תווים](#פונטים-וכיסוי-תווים)
- [עברית, אנגלית ומתמטיקה](#עברית-אנגלית-ומתמטיקה)
- [כותרות, סימניות ו-metadata](#כותרות-סימניות-ו-metadata)
- [ביבליוגרפיה והפניות](#ביבליוגרפיה-והפניות)
- [בנייה ובדיקות](#בנייה-ובדיקות)
- [נגישות: מה כן ומה לא](#נגישות-מה-כן-ומה-לא)
- [פתרון תקלות](#פתרון-תקלות)

## תמיכה וגבול אמון

המסלול מכוון ל־TeX Live 2023 ואילך עם LuaLaTeX, ונבדק מול מחלקות
`report` ו־`article`. הפרמבול משתמש בכמה hooks ומקרואים פנימיים של LaTeX,
babel, mathtools ו־hyperref; לכן שינוי גרסה מחייב smoke test מלא ולא רק
קומפילציה של עמוד אחד.

**אימות מלא מול תמיכה.** ה־runtime עובד מ־TeX Live 2023 ואילך, אך שלוש
בקרות־שחזור ברתמה דורשות את המנוע שבו הפגם המקורי מתרחש (‏LuaHBTeX 1.18.0
ואילך — סביבת האימות שמתועדת ב־`output-recovery.md`), ומדלגות מתחתיו עם
ציון גרסת המנוע. רתמה ירוקה על 1.17.0 פירושה שכל ההגנות נבדקו; ההוכחה
שהן נחוצות נבדקת על 1.18.0 ואילך.

קומפל רק מקור TeX מהימן בסביבה חד־פעמית ללא סודות. `--no-shell-escape`
אינו חוסם `\directlua`; הוא אינו sandbox.

## דרישות והתקנה

נדרשים LuaLaTeX מלא, babel Hebrew ו־English, גופני Latin Modern,
חבילות AMS, TikZ/pgfplots/quantikz ותלותו
`ctablestack`, listings, mdframed, hyperref, Python 3.10+ עם PyMuPDF ו־fontTools,
וכלי Poppler.
לרכיב האינדקס האופציונלי נדרשים גם imakeidx בגרסה המתועדת ו־makeindex.
המסלול המנוהל מופעל רק עם `INDEX_PROCESSOR=makeindex`; סגנון הרכיב נבחר
באמצעות `INDEX_STYLE=index.ist`. שלב זה רץ בין מעברי LuaLaTeX ובודק שכל
הרשומות התקבלו, שאין אזהרות טווח ושפלט האינדקס הנוכחי נכלל במסמך.
כשל קלט, אינדקס ריק או יציאה תקינה עם רשומות שנדחו אינם בנייה תקינה.
מסלולי אינדקס ומספור אחרים דורשים שילוב נפרד; ראו [אינדקסים](indexes.md).
גרסאות ה־Python QA שעליהן נבדק השחרור מוצמדות ב־`requirements-qa.txt`.

אפשר להתקין חבילות גם בעצים המקומיים התקניים של TeX. הבנייה מכבדת את
`TEXMFHOME` ואת `TEXMFLOCAL` כפי שהם מוחזרים ב־`kpsewhich -var-value=...`,
לצד עצי ההפצה הקיימים. תיקיות אלו הן חלק מה־toolchain המהימן; תיקייה שכנה
או נתיב חיצוני שאינו בעץ מוגדר אינם מקבלים אמון אוטומטי. לאחר הוספת חבילה
לעץ מקומי, ודא שהיא נפתרת באמצעות `kpsewhich` וש־`scripts/doctor.py` עובר.

ב־Debian/Ubuntu:

```bash
apt-get install -y texlive-luatex texlive-lang-other texlive-pictures \
  texlive-latex-extra texlive-latex-recommended poppler-utils fontconfig
python3 -m pip install -r requirements-qa.txt
```

בדיקות מהירות:

```bash
kpsewhich luaotfload-main.lua
kpsewhich luatexbase.sty
kpsewhich babel-he.ini
kpsewhich babel-en.ini
kpsewhich lmroman10-regular.otf
kpsewhich ctablestack.sty
python3 -c "import fitz; from fontTools.ttLib import TTFont"
python3 scripts/doctor.py --qa-only
# לפני release / אימות מלא של הסביבה:
python3 scripts/doctor.py
```

`build.sh` בודק רשימה מלאה יותר של תלות הפרמבול ונכשל אם רכיב חסר. אין
fallback אוטומטי לפורמט אחר; אם הסביבה חלקית, דווח מה חסר ואל תציג PDF
כמאומת.

ה־preflight מאמת תחילה את כל הפקודות, מודולי Python, קבצי TeX וה־checkers,
ורק אחר כך בודק את חבילת הפונטים. כשל סביבה מוחזר כ־exit 2 ואבחון יחיד;
כשל במסמך או בשער איכות מוחזר כ־exit 1.

## מבנה פרויקט

מבנה מומלץ:

```text
project/
├── main.tex
├── preamble.tex
├── clean_theme.tex          # optional pure presentation
├── exam_components.tex      # optional semantic exam helpers
├── clean_variant.tex        # legacy generated bundle only
├── parts/
│   ├── introduction.tex
│   └── exercises.tex
└── figures/
```

העתק `assets/preamble.tex` לפרויקט. הפרמבול כולל `\documentclass`, אך
class/layout הם כעת חוזה נפרד מליבת ה־RTL/Math: למסמך קצר הגדר את ה־hook
לפני טעינת הפרמבול במקום לערוך את הליבה. ברירת המחדל נשארת `report`, ‏A4.

```latex
\def\lakitdocumentclass{article} % השמט למסמך report קנוני
\input{preamble.tex}
\begin{document}
\section{מבוא}
\input{parts/introduction}
\end{document}
```

לשוליים, line spacing, class options ועומקי TOC/מספור קיימים hooks נוספים;
ראו [`architecture.md`](architecture.md#layout-contract). החוזה נתמך רק עבור
`report` ו־`article`; class אחר נכשל במפורש לפני `\documentclass` במקום
להיכנס למסלול best-effort שלא כוסה ב־regressions. הבנייה מאמתת גם את גודל
העמוד בפועל, ולכן גודל חלופי דורש גם `EXPECTED_PAPER` ואינו יכול להתפרסם
בשקט בגודל אחר.

למסמך חדש אל תשתמש ב־`clean_variant.tex` כמקור ארכיטקטוני. הוא compatibility
bundle בלבד. אם נדרשים עזרי מבחן ו־clean presentation, העתק את
`assets/exam_components.tex` ואת `assets/clean_theme.tex` וטען אותם בנפרד:

```latex
\input{preamble.tex}
\input{exam_components.tex}
\input{clean_theme.tex}
```

הסדר וה־ownership המלאים מתועדים ב־[`architecture.md`](architecture.md#architecture-roles).

נתיבי `\input`, `\include`, `\subfile`, משפחת import.sty ו־
`\lstinputlisting` צריכים להיות ליטרליים ולהישאר מתחת לשורש הפרויקט.
`build.sh` מבצע preflight שמרני, ולאחר pass ראשון משתמש ב־`.fls` כמקור
האמת לקבצים שהמנוע קרא בפועל.

## פונטים וכיסוי תווים

קובצי הגופנים אינם מצורפים לשחרור. משפחות Frank Ruhl Libre, Heebo ו־DejaVu
נשארות תלויות מדויקות; הרישיונות וחתימות SHA-256 נמצאים ב־`assets/fonts`.
להתקנה מקוונת מפורשת, הורד רק את קובצי המקור הרשמיים שהוצמדו לגרסה:

```bash
python3 scripts/download_fonts.py --destination /path/to/fonts
export HEBREW_LATEX_FONT_DIR=/path/to/fonts
python3 scripts/doctor.py
```

הורדה זו היא פעולת התקנה נפרדת; הבנייה עצמה אינה מורידה גופנים.
אפשר לייבא עותק מקומי התואם **לחתימות הגרסה הנוכחית** ללא רשת:

```bash
bash scripts/setup_fonts.sh /path/to/fonts --from-directory /path/to/verified-fonts
export HEBREW_LATEX_FONT_DIR=/path/to/fonts
python3 scripts/doctor.py
```

`--from-skill /path/to/font-bearing.skill` מיועד רק לארכיון שמכיל קובצי גופנים
התואמים לחתימות הנוכחיות. הארכיונים שסופקו לעדכון 5.1.0 אינם מכילים גופנים,
והחתימות הישנות אינן תואמות לבסיס החדש; אין להציג יבוא מהן כדרך התקנה.
מקורות ההורדה והשלכות המעבר מתועדים ב־[התקנת הסטודיו](studio-setup.md#font-provenance-and-compatibility).

בשני המסלולים קובצי ZIP נקראים לפי שמות ידועים בלבד, ללא חילוץ נתיבים
שרירותיים; כל הגופנים נבדקים בתיקייה זמנית לפני פרסום. שינוי משותף של גופן
ושל רשימת החתימות החיצונית אינו עוקף את חתימות הגרסה הקנוניות.
תיקייה שאינה ברירת המחדל נבחרת ב־`HEBREW_LATEX_FONT_DIR`.

```bash
FONT_DIR="$(python3 scripts/font_paths.py)"
python3 scripts/verify_font_bundle.py "$FONT_DIR"
python3 scripts/font_coverage.py "$FONT_DIR/FrankRuhlLibre-Regular.ttf"
```

## עברית, אנגלית ומתמטיקה

בחר תחילה אחד מחמשת פרופילי השפה לפי [Language and design](language-design.md). הדוגמאות העבריות להלן מדגימות הקשר RTL; באנגלית ראשית כתוב אנגלית באופן רגיל, ועברית בתוך `\h` או `hebrewprose`.

שלישיית הכיוון:

```latex
\h{עברית בתוך LTR}
\en{Latin (inside RTL)}
\code{grep --help}
```

פסקה אנגלית מלאה משתמשת ב־`englishprose`, שמחזיר שבירה רגילה גם במקף
מפורש:

```latex
\begin{englishprose}
A state-of-the-art result can break normally in a narrow measure.
\end{englishprose}
```

`\en` מיועד למונח או label קצר, ולכן מונע hyphenation. אין להשתמש ב־
`otherlanguage{english}` כתחליף ל־`englishprose` בפרוזה ארוכה.

בתוך math, טקסט נכנס ל־`\text`; בידוד שפה נכנס בתוכו:

```latex
\[
  T = T_0 + \text{זמן המתנה}
      + \text{\en{setup (fixed)}}
\]
```

עברית בתוך `\text{...}` מותרת. אסור להשתמש ב־`\h`/`\en` ישירות בתוך
math מחוץ ל־`\text`. SVG הוא נכס חיצוני: אם הוא כולל טקסט עברי, יש להמיר
אותו לנתיבים או ליצור את הטקסט ב־TikZ/LaTeX כדי שהכיוון והפונט יהיו נשלטים.

מספרים:

```latex
הטמפרטורה היא $-40^\circ\mathrm{C}$.
הטווח הוא 2020-2023.
הטווח הטיפוגרפי הוא \en{2020–2023}.
השיעור הוא 85\%.
```

טווח חשוף עם en dash בין שתי ריצות ספרות עלול להתהפך ב־RTL. אחוז לא
escaped מתחיל comment ומוחק את יתר השורה.

## כותרות, סימניות ו-metadata

מגרסה 4.8.0, `\code` מוגן ברמת מנוע TeX. הוא מותר בכותרת; הפרמבל גם
מנטרל אותו במחרוזות PDF דרך `\pdfstringdefDisableCommands` כדי למנוע אזהרות.
ניסוי הסרת ה־hook כבר אינו מקריס את המנוע: הסימנייה שבניסוי נשארת מדויקת,
אך מתקבלת אזהרת `Token not allowed`, וה־build האמיתי דוחה אותה. לכן אין
להסיר את ה־hook או לתאר את היעדרו כקריסה הכרחית. ההגנה המנועית שנמדדה
אינה שקולה להחלפה נאיבית ב־`\DeclareRobustCommand` (ראה [`pitfalls.md`](pitfalls.md)).

```latex
\section{שימוש ב־\code{grep}}
```

`\codeline` הוא בלוק ואסור בכותרת. `\footnote` בכותרת חייב להיות מוגן או
להעביר את ההערה לגוף.

מתמטיקה בכותרת מקבלת חלופת bookmark:

```latex
\section{סיבוכיות \texorpdfstring{$O(n\log n)$}{O(n log n)}}
```

הארגומנט השני חייב להיות plain text ללא `$`, `^` או `_`.

הגדר metadata אמיתי:

```latex
\hypersetup{
  pdftitle={כותרת המסמך},
  pdfauthor={שם המחבר}
}
```

`pdflang` נקבע לפי שפת הבסיס: `he` או `en`. פרופיל השפה נבחר לפני הפרמבול; ראו [Language and design](language-design.md).

## ביבליוגרפיה והפניות

ה־pipeline אינו מריץ BibTeX/Biber. למסמך עצמאי השתמש ב־
`thebibliography`. לרשומות מקומיות טען `document_components.tex` אחרי הפרמבול:

```latex
\begin{thebibliography}{9}
\bibitem{knuth}
\bibentryprose{english}{Donald E. Knuth. \emph{The TeXbook}. Addison-Wesley, 1984.}
\end{thebibliography}
```

רשומה מלאה נכתבת בפסקת `\bibentryprose` בשפתה, כולל הפיסוק הסופי.
שורות המשך באנגלית מתחילות משמאל; הכותרת והמספור נשארים במעטפת המקורית.
ראו [מדריך הסימוכין](citations.md); איים קצרים עדיין משתמשים ב־`\en` ו־`\h`. הפניות למשוואה
בפרוזה הן `\eqref{...}` ללא `$...$`:

```latex
כפי שנובע ממשוואה \eqref{eq:energy}.
```

טווח הפניות מאוחד:

```latex
\en{\eqref{eq:first}–\eqref{eq:last}}
```

## בנייה ובדיקות

לפרויקט שנוצר במחולל, השתמש במעטפת הפרויקט כדי לשמור את ברירות המחדל
של המתכון, כולל מעבד האינדקס והסגנון שנבחרו במפורש:

```bash
HEBREW_LATEX_SKILL_ROOT=/path/to/skill bash /absolute/path/to/project/build.sh
```

בפרויקט קיים ללא מעטפת, הגדר את חוזה הבנייה במפורש והפעל את הבונה ישירות:

```bash
bash /path/to/skill/scripts/build.sh /absolute/path/to/project/main.tex
```

דוגמאות ההגדרות הבאות משתמשות במעטפת המחולל. בפרויקט קיים העבר אותן
לבונה הישיר; לאינדקס נדרשים גם המעבד והסגנון לפי [אינדקסים](indexes.md).

הגודל הצפוי הוא A4 כברירת מחדל. הבדיקה קוראת את ה־`MediaBox` וה־`CropBox`
בכל עמוד, אינה מסתפקת בהצהרת `a4paper`, ומקבלת גם A4 לרוחב. רק לבקשה
מפורשת על נייר אחר יש לציין ערך תואם:

```bash
EXPECTED_PAPER=letter HEBREW_LATEX_SKILL_ROOT=/path/to/skill \
  bash /absolute/path/to/project/build.sh
```

הערכים הנתמכים הם `a3`,‏ `a4`,‏ `a5`,‏ `letter` ו־`legal`.

הוכחת pass נוסף:

```bash
REPRO=1 HEBREW_LATEX_SKILL_ROOT=/path/to/skill \
  bash /absolute/path/to/project/build.sh
```

לבדיקות העריכה ה־advisory בחר ז׳אנר כאשר הוא ידוע; ללא ערך מופעל
`generic`, שאינו כופה מכסות של ספר לימוד:

```bash
CONTENT_PROFILE=report HEBREW_LATEX_SKILL_ROOT=/path/to/skill \
  bash /absolute/path/to/project/build.sh
```

הערכים הנתמכים הם `study-guide`, `report`, `exam`, `formula-sheet`
ו־`review-sheet`.


כל ערכי ה־build contract נבדקים לפני LuaLaTeX. טעות כתיב בפרופיל, בגודל
הנייר, ב־`SECTION_MACROS`, ב־`REPRO` או בתקציב
`MAX_CROSS_PAGE_DESTINATIONS` מחזירה `exit 2`; היא אינה advisory ואינה יכולה
להיבלע אחרי פרסום PDF. ראו [`architecture.md`](architecture.md#build-and-configuration-contracts).

`check_pdf_navigation.py` קורא כל פעולת GoTo פנימית בסימניות ובקישורים,
פותר יעד שמי דרך עץ היעדים, משווה את עמוד הפעולה לעמוד שנפתר ומאמת את
אובייקט העמוד. הוא אינו מנחש כמה סימניות או אילו יחסי תוכן אמורים להתקיים.
כאשר הפרויקט דורש metadata או outline מסוימים, מסור את החוזה במפורש:

```bash
PDF_REQUIRE_TITLE=1 PDF_MIN_BOOKMARKS="$PROJECT_MIN_BOOKMARKS" \
  PDF_MIN_BOOKMARK_DEPTH="$PROJECT_MIN_BOOKMARK_DEPTH" \
  HEBREW_LATEX_SKILL_ROOT=/path/to/skill bash /absolute/path/to/project/build.sh
```

הערכים המספריים נקבעים מן המסמך; הסקיל אינו מספק סף קשיח. ללא חוזה כזה,
PDF בן 20 עמודים ומעלה ללא outline מפיק אזהרה advisory. שנה את הסף עם
`PDF_WARN_NO_OUTLINE_AFTER`, או קבע `0` כדי לבטל את האזהרה. יעד שמי תקני
נשאר מותר. כאשר נתיבים קריטיים חייבים לעקוף כשל תאימות מוכח במציג מסוים,
הגבל את דרישת היעד הישיר לדפוסי השמות שלהם בלבד:

```bash
DIRECT_NAVIGATION_DESTINATIONS='landing-*,landing-bookmark-*' \
  HEBREW_LATEX_SKILL_ROOT=/path/to/skill bash /absolute/path/to/project/build.sh
```

החוזה הזה בודק כל שם יעד שנבחר בנפרד: חייבת להיות לפחות פעולה ישירה אחת לאותו עמוד,
לאותו מיקום `XYZ` מלא ולאותו zoom. פעולה לכותרת אחרת באותו עמוד אינה מכסה
את היעד. המיקומים מושווים בקואורדינטות המנורמלות של MuPDF לאחר CropBox,
סיבוב ו־UserUnit, בסבילות של `0.05` נקודה; אין להשוות אותם ישירות לערכי
`resolve_names()`, הניתנים במרחב PDF מלמטה למעלה. zoom של `0` או `null`
שומר את ההגדלה הנוכחית. החוזה המוגבל תומך ביעדי `XYZ` עם מיקום מפורש;
יעדי `Fit*` או `XYZ` עם קואורדינטה חסרה נכשלים כלא ניתנים לאימות תחת
הדרישה הקריטית. השתמשו ביעד `XYZ` מלא או אמתו את מצב התצוגה בנפרד לפני
בחירת חוזה מתאים. יעדים שמיים רגילים ממשיכים להיבדק במסלול ברירת המחדל;
אין כאן הוכחה לכל כוונת ניווט או לכל מציג PDF.

הבנייה נעשית לתיקייה זמנית ומפורסמת אטומית רק אחרי:

- source graph, charset,‏ bidi ו־source hazards;
- fixed-point convergence;
- log gates להפניות, גליפים, footnotes/listings, destinations ו־overflow;
- gate לגודל נייר בכל עמוד ולאחריו render gate גאומטרי;
- hash reproducibility כאשר `REPRO=1`.

`REPRO=1` מוכיח יציבות בשני builds באותה סביבה. שחזור ביט־ל־ביט במכונה
אחרת דורש גם את שכבות הסגנון, הנכסים והפונטים המוצמדים, וכן גרסה קבועה של
TeX Live והסקריפטים; אם אלה אינם נמסרים, ציין במפורש את התלות.

לאחר הצלחה, רנדר לתיקיית סקירה חדשה:

```bash
python3 /path/to/skill/scripts/render_review.py render \
  /absolute/path/to/project/main.pdf --output /absolute/path/to/new-review
```

פתח את כל התמונות ובדוק כל עמוד. רשום סקירה ואמת את הפלט העדכני לפי
[תהליך הסקירה](everyday-workflow.md#review-actual-rendered-pages), עם הנתיבים
המלאים ל־PDF ול־`review.json`. `assets/example_math.tex`,
`assets/example_figures.tex`, `assets/example_tables.tex`,
`assets/example_boxes.tex`, `assets/example_listings.tex` ו־
`assets/example_exam.tex` הם מסמכי smoke מלאים; אין לשכפל דוגמה מקוצרת
שאינה משתמשת בפרמבול הקנוני.

## שחרור ואריזה דטרמיניסטית

אל תארוז את הסקיל עם `zip` ידני. `VERSION`, ‏`requirements-qa.txt` והכותרת
העליונה ב־`CHANGELOG.md` הם חוזה release שנבדק אוטומטית. פעל לפי
[נוהל השחרור הקנוני](catalog-development.md#release-workflow): הקפאת מועמד
עם `scripts/package_skill.py`, מטריצה מלאה וראיות מחוץ לעץ החבילה, סקירה
בפועל של כל עמוד ראשי, חתימת הראיות ובדיקות FULL הקשורות לאותו מועמד.
הארכיון הסופי חייב להתאים ל־SHA-256 של המועמד. שינוי מקור לאחר ההקפאה
דורש מועמד חדש וחידוש הראיות המושפעות.

`FAST` או יצירת ארכיון אינם מחליפים בדיקות מנוע וסקירה חזותית. לבדיקת FULL
שאינה שחרור, השתמש בהצהרת `HEBREW_LATEX_CATALOG_VISUAL=routine` לפי אותו נוהל;
הרצה כזו אינה ראיית שחרור.

האריזה ממיינת נתיבים, מקבעת timestamps והרשאות, ואינה כוללת directory entries
או artifacts. אותו עץ תוכן חייב להפיק אותם bytes גם כשה־checkout נקרא בשם אחר.
ה־build וה־harness מגדירים `PYTHONDONTWRITEBYTECODE=1`, ולכן גם שימוש רגיל
אינו אמור להשאיר `__pycache__` בתוך חבילת הסקיל.

## נגישות: מה כן ומה לא

הפרמבול מספק Unicode PDF strings ו־`/Lang` בסיסי. אלה עוזרים ל־metadata
ולסימניות אך אינם tagging.

המסלול אינו מספק:

- `StructTreeRoot`/PDF tagging;
- סדר קריאה סמנטי RTL;
- Alt/ActualText לאיורים, TikZ או נוסחאות;
- אימות PDF/UA.

למסירה נגישה נדרש workflow נפרד עם tagging, טקסט חלופי ובדיקה בכלי
כגון veraPDF ובקורא מסך. אל תסיק נגישות מ־`pdflang` בלבד.

## פתרון תקלות

| תסמין | אבחון | תיקון |
|---|---|---|
| `luaotfload-main.lua` או `luatexbase.sty` חסר | TeX Live חלקי | התקן `texlive-luatex` |
| `babel-he.ini` חסר | Hebrew language files חסרים | התקן `texlive-lang-other` |
| `quantikz.sty`/TikZ חסר | חבילות ציור חסרות | התקן `texlive-pictures`/`texlive-latex-extra` |
| font bundle verification נכשל | קובץ חסר/שונה | ייבא שוב התקנה שתואמת לחתימות הגרסה |
| `Missing character` | codepoint מחוץ למדיניות או face שגוי | הרץ `check_charset.py` ותקן מקור |
| `Token not allowed in a PDF string` | math/command בכותרת | `\texorpdfstring` או פקודה plain |
| `??` ב־PDF | `\label`/`\ref` שגוי | תקן מפתח ובנה מחדש |
| build לא מתכנס | aux משתנה או מבנה לא יציב | בדוק TOC/labels/package writes |
| `FIGCAP-NOT-ADJACENT` | חומר בין איור לכיתוב | העבר `\figcap` מיד אחרי הסביבה |
| `DEST-CROSS-PAGE` | כיתוב נשבר לעמוד הבא | הקטן/פצל איור או הוסף `\Needspace` לפניו |
| `FOLIO-COVERAGE-LOW` | המספרים המודפסים אינם מכסים די עמודים באזור שהוצהר | תקן מספור או התאם `PDF_FOLIO_LAYOUT` ו־`PDF_FOLIO_BAND` לעיצוב בפועל. `none`/`custom` מצהירים במפורש שאין מדידה אוטומטית; ראו [folios](pdf-folios.md). |
| `PAGE-SIZE-MISMATCH` | אחד מ־MediaBox/CropBox אינו A4 או אינו הגודל שנבחר במפורש | שחזר `a4paper`, או התאם גם את המקור וגם את `EXPECTED_PAPER` לבקשה המפורשת |
| `BARE-LATEX-COMMAND` | `qquad`/`frac`/`mathrm` וכדומה הודפסו כמילים בתוך math | הוסף את הלוכסן החסר ובנה מחדש |
| `NEEDSPACE-IN-MULTICOLS` | `\Needspace` ישיר או דרך מאקרו בתוך עמודות | החלף בכותרת עם `\nopagebreak[4]` ובדוק זרימת RTL |
| PDF נבנה אך פריסה חשודה | checker אינו תחליף לעין | רנדר ובדוק כל עמוד |


### הפניות בין הקשרים ובדיקת סביבת העבודה

`\eqref` נכתב ישירות בפרוזה; בתוך סביבה מתמטית השתמש ב־`\text{\eqref{eq:key}}`.
אל תעטוף את ההפניה כולה ב־`$...$` בפרוזה, ואל תשחזר ידנית `\maketag@@@`.
למעבר פסקה השתמש ב־`englishprose`; למונח בתוך שורה ב־`\en`.
היקף הבדיקות, מספור בררני והתאמת שפת ההפניות מתועדים ב־`bilingual-references.md`.
לצילום של רכיבי הסביבה המותקנת ראה `environment-report.md`; הצילום אינו
מחליף בנייה, בדיקות יעד או סקירת עמודים.
