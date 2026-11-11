# Table blank lines

Mattermost keeps a pipe table as a table only when a blank line sits immediately before the header and immediately after the last row.

```
新票

| CaseID | Date | Status | Title |
| --- | --- | --- | --- |
| C-example | 2026-11-02 | Not Started | Example title |

下一節
```

Do not put a heading on the header line. Do not put a pipe character inside a cell.
