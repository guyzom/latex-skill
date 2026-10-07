# doc_examples_exempt.md — harness fixture (T6), the NEGATIVE probe matrix

`lint_doc_examples.py --docs <this file> --min-blocks 1` MUST exit 0.
Every block here abuses a documented EXEMPTION — a gate that fires on any
of them has broken a load-bearing convention (a counter-example the docs
are allowed to show would start failing CI). This is the standing negative
probe matrix (v3.39.4): the ❌→✅ region contract caught a real regression
in the first draft of RAW-CONTROL-CHAR (raw-block scan) before it shipped.

A ```latex-bad fence is skipped entirely, even with control bytes and bugs:

```latex-bad
שבור בכוונה: egin{tabular} וגם 	oprule וגם \en{A}, \en{B}
```

A ❌→✅ negative region inside a good block is stripped before checking:

```latex
% ❌ כך זה נשבר (דוגמה־נגדית, מדולגת):
% egin{x} עם 	extbf וגם \en{ID:} עברית
% ✅ הצורה הנכונה:
בלוק תקין לגמרי — עברית פשוטה בלי שום מלכודת.
```
