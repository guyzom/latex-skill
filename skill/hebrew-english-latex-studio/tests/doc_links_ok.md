# fixture: every link here must PASS (doc_links negative control, v4.2.2)

## כותרת עברית עם מקף-פנימי וגם Latin words

## עוגן כפול
טקסט.
## עוגן כפול
(השני מקבל סיומת ‎-1 לפי כללי GitHub.)

## כותרת עם `קוד פנימי` באמצע

- [עוגן עברי באותו קובץ](#כותרת-עברית-עם-מקף-פנימי-וגם-latin-words)
- [העותק השני של הכפול](#עוגן-כפול-1)
- [עוגן עם קוד פנימי](#כותרת-עם-קוד-פנימי-באמצע)
- [קובץ אחר בחבילה](../references/pitfalls.md)
- [עוגן בקובץ אחר](../references/direction-and-math.md#אמירה-מילולית-בתוך-display-math)
- [קישור חיצוני — לא תלות](https://example.com/not-a-dependency#whatever)
- דוגמת תחביר בתוך קוד אינה קישור: `[not-a-link](./no-such-file.md)`

```markdown
[קישור בתוך fence אינו נבדק](./also-no-such-file.md)
# heading inside a fence is code, not an anchor target
```
