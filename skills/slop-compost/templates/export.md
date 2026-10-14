# Template - export (`$LEDGER/export/<run-id>.md`)

**v1: format only.** Nothing is sent anywhere. The file is written only when the user asks for an export.
The format exists so a future opt-in "public idea graveyard" can accept it. Sending will always require the user's consent per export.

Strip before writing:
- personal data (names, emails, company names, local paths, private URLs),
- source code and verbatim private text (summarize instead),
- ledger ids that reveal private project names (replace with `artifact-1`, `artifact-2`).

```markdown
---
format: slop-compost-export
version: 1
run: <run-id>
language: <ko|en>
---

## Artifacts
### artifact-1
- Type: code
- Summary: <generic one-liner, no names>
- Completeness: 40%
- Stop reasons: unfinished

## Lessons
- <sentence> - stop reasons: unfinished - repeat: 2

## Judgments
| track | candidate (generic) | decision | reason |
|---|---|---|---|
| A | Cut scope to one feature | adopt | |
| B | Recombine parser + niche newsletter | reject | ops burden |
```
