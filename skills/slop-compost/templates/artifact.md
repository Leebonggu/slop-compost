# Template - artifact card (`$LEDGER/artifacts/<id>.md`)

Translate headings into the user's language. Keep the front-matter keys and enum values in English.

```markdown
---
id: idea-factory
source: ~/playground/idea-factory               # path, URL, repo@branch:path, or "text"
type: code                                       # code | writing | idea
secondary_types: [writing]
fingerprint: {method: git-head, value: 3f2a9c1}
partial: false                                   # true if the 50-file cap was hit
stop_reasons: [unfinished]                       # no-revenue | unfinished | abandoned | other
stop_reason_notes: {unfinished: "lost interest after the first demo"}   # optional note per reason (any enum value may carry a note)
stop_reason_source: user                         # user | accepted-guess
first_run: 2026-10-15
last_run: 2026-10-15
---

# idea-factory

## Summary
- Goal: <one sentence>
- How far: <completeness %> - <furthest checkpoint reached, with evidence location>
- Last activity: <YYYY-MM-DD>

## Parts
| id | kind | location | what | why reusable |
|---|---|---|---|---|
| idea-factory#p1 | module | src/rss/parse.ts:1-88 | RSS fetch + dedupe | any feed product needs it; has tests |

## Why it stopped
- <reason enum>: <evidence location> - <one line>

## Updates
### <YYYY-MM-DD> (run <run-id>)
- <what changed since the last fingerprint>
```
