# Template - lessons (`$LEDGER/lessons.md`)

Append one dated section per run. Never edit older sections except the `repeat` line and added evidence of a repeated lesson.

```markdown
# Lessons

## 2026-10-15 (run 2026-10-15)

### L2 - <one falsifiable sentence>   [structural habit]
- Evidence: `idea-factory:README.md:12`, `podcast-idea:notes.md:3`
- Falsifier: <what observation would prove this wrong>
- Stop reasons: unfinished
- Repeat: 3 (runs 2026-09-01, 2026-09-20, 2026-10-15)

### L5 - <one falsifiable sentence>
- Evidence: `newsletter-draft:draft.md:¶4`
- Falsifier: ...
- Stop reasons: abandoned
- Repeat: 1
```

Rules:
- One claim per lesson. Evidence location is mandatory and must exist.
- `[structural habit]` when `Repeat >= 3`.
- A repeated lesson keeps its original id; add the new evidence and update `Repeat` in its original section, and list it again in the new section as `### L2 - (repeat, see 2026-09-01)` with the new evidence only.
