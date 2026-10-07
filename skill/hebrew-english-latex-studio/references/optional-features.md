# יכולות אופציונליות ומצב מבחן

Language scope (v5): Hebrew/RTL examples and rules in this guide apply to Hebrew contexts. Native English uses its own base language; see [language and design](language-design.md). Layout and style examples are choices, not requirements for every document.

קרא מסמך זה רק כאשר נדרשים פריטי רשימה ניתנים להפניה, יחידות פיזיקליות,
רשימות איורים/טבלאות, גרסה נקייה, כותרת רצה או פס נושאים. מקור האמת
להגדרות הוא `assets/preamble.tex`; עזרי מבחן חיים ב־`assets/exam_components.tex` וה־clean presentation ב־`assets/clean_theme.tex`.

## תוכן עניינים

- [מספור עברי ברשימות](#מספור-עברי-ברשימות)
- [יחידות פיזיקליות](#יחידות-פיזיקליות)
- [כיתובים קצרים לרשימות](#כיתובים-קצרים-לרשימות)
- [קופסה שאינה נשברת](#קופסה-שאינה-נשברת)
- [הגרסה הנקייה](#הגרסה-הנקייה)
- [כותרת רצה ופס נושאים](#כותרת-רצה-ופס-נושאים)

## מספור עברי ברשימות

לפריטים שצריכים `\ref` וגם `\autoref`, הפעל `\hebenumlabels` בתוך קבוצה
והשתמש ב־`\item\label{...}` רגיל:

```latex
{\hebenumlabels
\begin{enumerate}
\item\label{item:first} הסעיף הראשון.
\item\label{item:second} הסעיף השני.
\end{enumerate}}
```

התוויות מודפסות `(א)`, `(ב)`; `\ref{item:first}` מחזיר `א`, והעוגן הוא
עוגן פריט אמיתי. אל תשים `\label` בתוך `\item[...]`: פריט בעל תווית
מפורשת אינו בהכרח מקדם counter, ולכן ההפניה עלולה להיקשר לכותרת הסובבת.

כאשר דרושה תווית עברית מפורשת ורק `\ref` חשוב, אפשר:

```latex
\begin{enumerate}
\hitem{א}{item:manual} סעיף בעל אות מפורשת.
\end{enumerate}
```

`\hitem` אינו המסלול המומלץ ל־`\autoref` או `\nameref`; העדף
`\hebenumlabels` כאשר נדרשת סמנטיקה מלאה.

## יחידות פיזיקליות

`\punit` מיועד למצב מתמטי בלבד ומחזיק מספר ויחידה באותו אי LTR:

```latex
הטמפרטורה היא $300\punit{K}$ וזמן הגישה הוא $80\punit{ns}$.
```

אל תכתוב מספר חשוף ואחריו יחידת טקסט נפרדת בבסיס RTL. אל תשתמש ב־
`\punit` בפרוזה מחוץ ל־math; `\mathrm` שם אינו תקף. לקיצור תחומי צור
מאקרו מקומי במונחי `\punit` או math תקין.

## כיתובים קצרים לרשימות

`\figcap` ו־`\tabcap` כותבים ל־`\listoffigures`/`\listoftables` רק כאשר
ניתן ארגומנט קצר אופציונלי. השאר אותו פשוט וללא פקודות בלוק:

```latex
\begin{tikzpic}
\begin{tikzpicture}
  \node[draw] {Input};
\end{tikzpicture}
\end{tikzpic}
\figcap[מסלול הקלט]{\label{fig:input}מסלול הקלט מן המקור אל המעבד}
```

בטבלה, `\tabcap[קצר]{ארוך}` הוא הרכיב האחרון **בתוך** `tablebox`.
ללא הארגומנט הקצר הכיתוב עדיין מודפס וממוספר, אך אינו נרשם לרשימה.

## קופסה שאינה נשברת

לקופסת ייחוס קצרה בלבד אפשר להוסיף `nobreak=true`:

```latex
\begin{notebox}[nobreak=true]
זהות קצרה שאסור להשאיר ממנה שורה בודדת בעמוד הבא.
\end{notebox}
```

אל תשתמש באפשרות על קופסה שעלולה להיות גבוהה מעמוד; קופסה בלתי־שבירה
גבוהה מדי גורמת לאובדן תוכן ולכשל build.

## הגרסה הנקייה

במסמך חדש טען presentation ועזרי מבחן כשתי שכבות נפרדות:

```latex
\input{preamble.tex}
\input{exam_components.tex} % אם נדרשים עזרי מבחן
\input{clean_theme.tex}
```

`clean_theme.tex` מונוכרומי, הופך `exbox`/`keybox`/`notebox` לרכיבים נקיים
ומפעיל `showonlyrefs`. מאחר שרק `\eqref` מכריח מספר משוואה תחת
`showonlyrefs`, השתמש בו לכל הפניה למשוואה.

`clean_variant.tex` נשאר compatibility bundle generated למסמכים ותיקים; אין
לערוך אותו ישירות.

עזרי המבחן מגיעים מ־`exam_components.tex` ואינם תלויים ב־theme:

| מאקרו | שימוש |
|---|---|
| `\qlabel{טקסט}{key}` | עוגן אמין לכותרת שאלה לא ממוספרת |
| `\pts{30\%}` | הצגת ניקוד; אפשר `\renewcommand` מקומי |
| `\finalans{...}` | תשובה סופית ב־math; טקסט נכנס דרך `\text{...}` |
| `\srcfig{0.55}{file.png}{כיתוב}` | איור מקור מדוד עם `\figcap` |

```latex
\chapter{שאלה 2 — אוסצילטור}
\qlabel{שאלה 2}{q:oscillator}
\pts{30\%}
\[
  \finalans{E_0=\tfrac12\hbar\omega}
\]
```

`\srcfig` מחפש כברירת מחדל תחת `figures/`. לפרויקט קיים עם שם אחר:

```latex
\renewcommand{\srcfigdir}{figs}
```

## כותרת רצה ופס נושאים

לכותרת רצה פשוטה הפעל פעם אחת אחרי הפרמבול ולפני `\begin{document}`:

```latex
\input{preamble.tex}
\lakithead{שם המסמך}
\begin{document}
```

המאקרו משתמש בשם הפרק ב־`report` ובשם הסעיף ב־`article`, ומטפל גם
בכותרות starred. למסמך רב־חטיבתי שבו נדרשת התמצאות חזותית, השתמש במקום
זאת ב־`assets/topicrail.tex` ובדוגמה `assets/example_topicrail.tex`; הפס
מיועד למסמך ארוך ואינו ברירת מחדל.
