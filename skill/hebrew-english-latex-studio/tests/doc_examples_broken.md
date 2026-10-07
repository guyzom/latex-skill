# doc_examples_broken.md — harness fixture (T6), deliberately broken

A documentation exemplar teaching a known bug class. `lint_doc_examples.py
--docs <this file> --min-blocks 1` MUST flag it — that is the proof that the
doc-exemplar gate can fire (a gate whose rules can't fire is decoration).
The blocks reproduce the three classes that actually shipped through the docs:
a trapped label colon (v3.27.0), unmerged adjacent code islands (v3.27.1),
and raw control bytes from a non-raw Python string write — \b/\t eating
\begin/\toprule (v3.39.2; check_charset flags these WITHOUT a bracketed
[FLAG] token, so the gate must honor its exit code, not just [FLAG] lines).
The TAB-only block is the v3.39.3 residual: TAB is charset-ALLOWED, so
only the gate's own RAW-CONTROL-CHAR sees it. The last two blocks are the
invisible-bidi probes (RLM U+200F, ZWJ U+200D) — check_charset flags them
without a [FLAG] token, proving the exit-code path on non-control chars.
The full standing probe matrix (v3.39.4) = this file (must FAIL, every
class asserted) + doc_examples_exempt.md (must PASS — the skip
conventions are load-bearing: a raw-scan draft of RAW-CONTROL-CHAR broke
the ❌-region contract and only a negative probe caught it).

```latex
\textbf{\en{ID:}} קרא \code{\$rs}, \code{\$rt} מקובץ הרגיסטרים.
```

```latex
שלום egin{tabular}{l l} עולם 	extbf{ערך}
```

```latex
טבלה בעברית: 	oprule ואז 	extbf{ערך} — הטאב בלע את הפקודות
```

```latex
שלום ‏עולם — סימן RLM בלתי־נראה לפני "עולם"
```

```latex
מילה‍מחוברת — ZWJ בלתי־נראה באמצע
```
