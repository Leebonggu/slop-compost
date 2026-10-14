# Template - direction (`<LEDGER>/runs/<run-id>.md`, shown in step 6)

Translate headings and prose into the user's language. Keep labels (A1, B1), ids, and enum values as is.

```markdown
# slop-compost run <run-id>

- Mode: incremental (3 new, 1 changed, 2 unchanged) | full (--full)
- Artifacts: idea-factory (partial: 50/212 files), podcast-idea, ~~notion-page~~ (blocked: Notion MCP not connected)
- fallback: sequential            # only if tracks ran without subagents

## Recall                          # omit on first run
- Adopted 3, started 1 (`2026-10-01:A1`).
- L2 is now a structural habit (3 runs).

## Parts
| id | kind | location | what |
|---|---|---|---|
| idea-factory#p2 | module | src/rss/parse.ts:1-88 | RSS fetch + dedupe |

## Patterns across artifacts
- Theme: <theme> - `idea-factory`, `podcast-idea`
- Behavior: <behavior> - `idea-factory:TODO.md:3`, `podcast-idea:notes.md:9`
- Theme: <theme> - `podcast-idea`, `old-blog` (ledger)

## Lessons
- **L2** [structural habit] <sentence> - `idea-factory:README.md:12`

## Two tracks

### If you revive the current idea (Track A)
#### A1 - <one-line definition>
- Parts: `idea-factory#p2`
- Lessons -> changes: L2 -> <concrete change>
- First experiment (<= 7 days): <what, by when, cost>
- Success: <number>   |   Kill: <number>
- Intents: respects I1; bends none

#### Release note
- `old-blog`: no motivation found -> let it go; parts `old-blog#p1` stay in the parts list.

### If you go for a new idea (Track B)
#### B1 - <one-line definition>
- Who pays: <buyer, rough price>
- Parts: `idea-factory#p2`, `podcast-idea#p1`
- Lessons -> changes: L2 -> <concrete change>
- External evidence: <claim> - <source> - <YYYY-MM-DD> [src:<source id>]
- Counter-evidence: why it could fail: <mechanism>; similar failure: <case> (Cause: <cause>, Closed: <year>) - <source> - <YYYY-MM-DD> [src:<source id>]
- First experiment (<= 7 days): <...>
- Success: <number>   |   Kill: <number>
- Intents: respects I1
- Source ids: hn-show, failory

Convergence: A1 ≈ B1 - <what they share>. Two independent paths reached the same direction: a strong signal, not a duplicate.

## Sources checked
- failory: 2 items, freshest 2024-03-01. geeknews: 1 item, 2026-10-12. failure-search: 0 (queries shown in B1). trustmrr: 403, skipped. Lightweight: no.

Composted 3 (05b.ev-no-counter: 2, 03.unfalsifiable: 1)
```

## Candidate

Both tracks use the same fields; Track B adds "Who pays", "External evidence", and "Counter-evidence".
A candidate missing a required field is composted, never shown with a blank.
