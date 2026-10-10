# Hebrew English LaTeX Studio: installation and migration

## התקנה ושימוש

זהו סקיל אחד לעברית, לאנגלית ולמסמכים דו־לשוניים. שם ההפעלה החדש הוא
`$hebrew-english-latex-studio`. בחירת השפה אינה מגבילה את סוג המסמך או העיצוב.
כל המסלולים משתמשים באותו `assets/preamble.tex`.

מגרסה 5.4.0 בחירות התבניות מרוכזות בקטלוג קנוני משותף למחולל,
לפותר ולתיעוד. [קטלוג התבניות](template-catalog.md) מציג תבניות,
פריסות, עיצובים ודוגמאות קיימים; [מילון המושגים](glossary-he-en.md)
מסביר את המונחים בעברית ובאנגלית. לבדיקת בחירה לפני יצירת פרויקט:

```bash
python3 /path/to/skill/scripts/template_registry.py list
python3 /path/to/skill/scripts/template_registry.py resolve --kind paper \
  --language english --json
```

פקודות אלה קוראות את הקטלוג ללא בנייה או יצירת פרויקט. פותר הבחירות
מתעד את הבקשה, התוצאה ומקור ברירות המחדל; תיעוד זה אינו ראיית בדיקה
של PDF. הממשקים ההיסטוריים ופרויקטים שכבר נערכו נשמרים; המחולל אינו
משכתב אותם. למפתח: [תחזוקת הקטלוג](catalog-development.md).

Before redistributing the tooling, read the [scoped AGPLv3 grant and closed local
source boundary](../LICENSING.md), [dependency notices](../NOTICE.md), and
[Generated Output Permission](../LICENSES/Generated-Output-Permission.txt).
The grant covers the exact tooling/support file list, without assigning a new license
to TeX templates, fonts, or other unlisted material. Original user document
content and output PDFs do not automatically become AGPL through tool use;
copied source retains its actual license. Original fragments emitted by the seven
named programs in normal output have the stated additional permission; copied
inputs and third-party material retain their terms. New projects preserve the
permission as `GENERATED-OUTPUT-PERMISSION.txt` in their creation-time hashes.

נדרשים LuaLaTeX מלא, Poppler וסביבת Python התואמת ל־`requirements-qa.txt`.
קובצי הגופנים הם תלות חיצונית. התקנה מקוונת מפורשת:

```bash
python3 -m pip install -r /path/to/skill/requirements-qa.txt
python3 /path/to/skill/scripts/download_fonts.py --destination /path/to/fonts
export HEBREW_LATEX_FONT_DIR=/path/to/fonts
python3 /path/to/skill/scripts/doctor.py
```

אפשר גם לייבא קבצים מקומיים באמצעות `setup_fonts.sh --from-directory`.
הקומפילציה עצמה אינה מורידה גופנים ואינה דורשת רשת.

Without a nonempty `HEBREW_LATEX_FONT_DIR`, the installer and build use
`$XDG_DATA_HOME/fonts/hebrew-lualatex-pdf` when `XDG_DATA_HOME` is an absolute
path, otherwise `$HOME/.local/share/fonts/hebrew-lualatex-pdf`. Empty or relative
XDG values select the home default, including in direct LuaLaTeX execution.
An explicit installer destination takes precedence over the environment.

```bash
python3 /path/to/skill/scripts/new_document.py --kind general \
  --language hebrew-with-english --theme reader --directory /path/to/new-document
HEBREW_LATEX_SKILL_ROOT=/path/to/skill bash /path/to/new-document/build.sh
python3 /path/to/skill/scripts/render_review.py render \
  /path/to/new-document/main.pdf --output /path/to/new-review
```

Use the generated wrapper to retain the recipe's build defaults, including any
explicitly selected optional components. Existing sources without a wrapper
require explicitly declared configuration for the managed builder.

For native English, use `--language english`. For substantial sections in both
languages, use `--language bilingual --main-language english` or `hebrew`.
Review every rendered page. A successful build is not a visual attestation.

## מאמר אקדמי בעברית או באנגלית

מגרסה 5.2.0 אפשר ליצור מאמר עם העיצוב המשותף `academic`:

```bash
python3 /path/to/skill/scripts/new_document.py --kind paper \
  --language hebrew --directory /path/to/new-paper
HEBREW_LATEX_SKILL_ROOT=/path/to/skill bash /path/to/new-paper/build.sh
```

למאמר באנגלית החלף את השפה ל־`english`. למאמר דו־לשוני בחר `bilingual`
והוסף `--main-language hebrew` או `english`. כשלא מציינים עיצוב, `paper`
בוחר `academic`; סוגי המסמכים הקיימים ממשיכים לבחור `reader`. בחירת עיצוב
מפורשת גוברת על ברירת המחדל. אין צורך בסקיל או בפרמבול נוסף.

ברירת המחדל למאמר היא A4, גודל כתב 11 נקודות, שוליים 2.7 ס״מ ומספר עמוד
במרכז התחתית. נוסחאות מרכזיות או כאלה שמפנים אליהן מקבלות מספור; צעדי
גזירה שגרתיים נשארים ללא מספור. מחבר ותאריך אינם מומצאים. מדריך
[המאמרים האקדמיים](academic-articles.md) מפרט את הכותרת, התקצירים,
הנוסחאות, הכיתובים והביבליוגרפיה, וכן מעבר מפורש לנייר Letter.

## דף נוסחאות בטורים בעברית או באנגלית

מגרסה 5.3.0 אפשר לבחור עימוד ייעודי לדף נוסחאות בתוך אותו סקיל:

```bash
python3 /path/to/skill/scripts/new_document.py --kind formula-sheet \
  --language hebrew --layout reference-readable --directory /path/to/new-sheet
HEBREW_LATEX_SKILL_ROOT=/path/to/skill bash /path/to/new-sheet/build.sh
```

לאנגלית בחר `--language english`. הגרסה הקריאה משתמשת בשני טורים ובכתב
9 נקודות עם מרווח בסיס 11; `reference-compact` משתמשת בשלושה טורים ובכתב
6.3 נקודות עם מרווח בסיס 7.8. בחר צפיפות לפי השימוש בפועל ובדוק בגודל
הדפסה. אין הקטנת כתב אוטומטית או כפייה של מספר עמודים.

גודל הפרוזה וגודלי המתמטיקה מוגדרים בנפרד. בגרסה הקומפקטית כתב הנוסחאות
הראשי הוא 6.25 נקודות, כתב עילי ותחתון הוא 4.375, והכתב המקונן הוא
3.125. בגרסה הקריאה הגדלים המתמטיים הם 8.75, 6.125 ו־4.375 נקודות.
העימוד משתמש בתכנונים האופטיים של Computer Modern בגודלי מקור 10, 7
ו־5 נקודות, בהתאמה, ומשנה את קנה המידה של הגופן באופן אחיד. כך נשמרות
פרופורציות האותיות; אין כיווץ אנכי או מתיחה של נוסחה כתמונה. הגופנים
המתמטיים האלה זמינים בהפצת TeX ואינם מוסיפים קובצי גופן לסקיל.

אפשר להגדיר מראש את `\ReferenceMathFontSize`,
`\ReferenceMathScriptSize` ו־`\ReferenceMathScriptScriptSize`, לצד גודל
הפרוזה ומרווח הבסיס. הגדלים חייבים להיות חיוביים; הכתב המקונן אינו גדול
מהכתב המשני, והכתב המשני אינו גדול מהכתב הראשי.
בחירת הגופן המתמטי מקומית ל־`referencecolumns` ול־`referencewide`;
המתמטיקה שמחוץ להן שומרת על הגדרותיה. בטעינה ישירה ללא הגדרות מפורשות,
גודל המתמטיקה הראשי הוא גודל הפרוזה, ושתי רמות הכתב המשני הן 70% ו־50%
ממנו. היצרן מגדיר במפורש את הגדלים של שתי גרסאות העימוד לעיל.
אין החלפת גופן שקטה, הקטנה לפי אורך התוכן או רצפה של 5 נקודות לכתב המשני.
ראה [עימוד וטיפוגרפיה לדפי עזר](reference-sheets.md) ו־
[אימות גופנים בזמן בנייה](runtime-fonts.md#reference-mathematics).

ברירת המחדל לדף נוסחאות כוללת שתי רמות מספור בלבד: נושא ותת־נושא.
הנוסחאות מופיעות בעיקר ישירות בטקסט, עם הנחות קצרות לידן; תיבות שמורות
לנוסחאות מרכזיות בודדות, להערות ולשאלות קצרות. `referenceentry` שומר יחד
נושא קצר או פתיחה מגדירה; נושא ארוך יכול לזרום או להתחלק לקטעים שנכתבו
במפורש. תוכן רחב נשאר אפשרות נפרדת לשימוש כשנדרש רוחב של עמוד.

שתי גרסאות העימוד בוחרות בעיצוב `reference` אם לא צוין עיצוב אחר. בחירה
מפורשת של עיצוב גוברת על ברירת המחדל; בחירת `reference` לבדה אינה יוצרת
טורים. `--layout standard`, שהוא ברירת המחדל, שומר על מסלול דף הנוסחאות
הקודם. העימודים החדשים זמינים כרגע לסוג `formula-sheet` בלבד.

גם מסלולים מעורבים ודו־לשוניים עם שפת בסיס מפורשת משתמשים באותה ליבה.
סדר הטורים מתאים לשפת הבסיס, והנוסחאות והתרשימים שומרים על משמעותם.
לגרסה דו־לשונית יש תוכן מתורגם שנכתב בנפרד. מדריך
[דפי הנוסחאות](reference-sheets.md) מפרט את הרכיבים, הכותרת, מעברי הטורים,
פתרונות ארוכים ותוכן רחב. אין תלות גופן חדשה או פרמבול נוסף.

## Font provenance and compatibility

Version 5.1.0 deliberately replaces the unavailable legacy font-byte baseline.
The supplied archives contained only licenses and a manifest; their old hashes
could not be recovered from the official files tested during this update.
The old manifest remains in `legacy-font-pins.txt` for identification only.
Do not use it as an installation trust root or claim old/new pixel identity.

The new canonical SHA-256 manifest is `assets/fonts/SHA256SUMS`. It pins:

- Frank Ruhl Libre 6.004: `fontef/frankruhllibre` commit
  `2372d1998e51dc011f86554c0d23f1ccf44afddf`, `fonts/ttf`.
- Heebo 3.100: `OdedEzer/heebo` commit
  `76c7d538568d3e6d7f052a12c5675c84430df25f`, `fonts/ttf`.
- DejaVu 2.37: official `dejavu-fonts-ttf-2.37.zip` release, `ttf` members.

Exact immutable URLs are in `scripts/download_fonts.py`. Upstream responses
are bounded in size; only named archive members are read, and every font must
match the current manifest before installation. Existing offline installation
and physical-file runtime observation continue to fail closed.

New fonts can reflow existing documents. Rebuild and inspect the actual pages
before delivering a migrated project. This release does not claim old PDF byte
identity. Do not overwrite a customized preamble without inspecting changes.

The historical `HEBREW_LATEX_*` environment variables, internal `hllpdf`/`lakit`
macros and default font-install directory remain supported for existing projects.
The public skill name and display name are new. Retire the previous installed
skill when installing this one to avoid two overlapping routing instructions.
No second language-specific skill or preamble is necessary.

## Toolchain execution

Use trusted TeX in a disposable workspace. LuaLaTeX executes Lua even with
shell escape disabled. The build preserves the caller's TeX file-access policy;
it does not change `openout_any`. Some Debian installations apply `p` to Lua
cache probes, causing `no writeable cache path` for an external private cache.
Use a compatible isolated TeX runtime and record its policy. Do not interpret
such an engine startup failure as a font mismatch or a document defect.
The release evidence records the tested runtime settings explicitly.
