# Step 4 - Intent (optional)

Capture the user's own thoughts and constraints so both tracks respect them. One question, skippable.

## Inputs

- `summary.active_intents` from `<CLI> recall` (step 0). Format: [../../assets/templates/intents.md](../../assets/templates/intents.md).
- Recall summary and lessons from steps 0 and 3.

## Do

1. Ask **one** message combining the carry-over check and new input (translate):

   ```
   Optional: anything the directions must respect?
   Last time you set: (I1) "B2B only"  (I2) "keep the RSS parser part"
   Answer like: keep I1, drop I2, + "under $70/month to run"   |   keep all   |   skip
   ```
   Korean equivalents: `유지`, `모두 유지`, `그대로` = keep all; `바꿀래`, `수정` + id = edit (ask for the wording once more if missing); `빼`, `종료` + id = end; `스킵` = skip. New intents follow a `+`. With no active intents, ask only for new ones.
2. `skip` or keep all: write nothing.
3. Otherwise copy `<LEDGER>/intents.md` to `<WORK>/intents.md` (or start from the template) and edit the copy: dropped intents move to "Ended" with today's date (never deleted), new ones get ids `I<n>` after the highest id, edited ones keep their id. `commit` refuses a file that lost an id.

## Output

- The active intent list (id + text) for both tracks, identically. `bundle a`/`bundle b` read `<WORK>/intents.md` if it exists, else the ledger.

## Reject if

- [`04.reworded`] An intent was paraphrased into something stronger or weaker than what the user said. Keep the user's words.
- [`04.track-asymmetry`] Intents were given to only one track or worded differently per track.
- [`04.deleted`] A dropped intent was removed instead of moved to "Ended".
