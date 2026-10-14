# Step 4 - Intent (optional)

Capture the user's own thoughts and constraints so both tracks respect them. One question, skippable.

## Inputs

- Active intents from `<LEDGER>/intents.md` (section "Active"; format [../templates/intents.md](../templates/intents.md)).
- Recall summary and lessons from steps 0 and 3.

## Do

1. Ask **one** message that combines the carry-over check and new input. Example (translate):

   ```
   Optional: anything the directions must respect?
   Last time you set: (I1) "B2B only"  (I2) "keep the RSS parser part"
   Answer like: keep I1, drop I2, + "under $70/month to run"   |   keep all   |   skip
   ```
   Accept answers in the user's language. Korean equivalents: `유지`, `모두 유지`, `그대로` = keep all; `바꿀래`, `수정` + id = edit that intent (ask for the new wording in the same line or once more); `빼`, `종료` + id = end that intent; `스킵` = skip. New intents can follow a `+`.
   With no active intents, ask only for new ones. Examples of intents: target ("B2B only"), must-keep part, budget, time ("weekends only"), things to avoid.
2. Parse: kept intents stay active, dropped ones move to "Ended" with today's date (never deleted), new ones get ids `I<n>` continuing the highest id.
3. `skip` = keep all active intents unchanged, add none.
4. Stage the result in `<LEDGER>/runs/<run-id>.work/intents.md`.

## Output

- Active intent list (id + text) passed to both tracks, identically.
- Staged intent changes for step 8.

## Reject if

- [`04.reworded`] An intent was paraphrased into something stronger or weaker than what the user said. Keep the user's words.
- [`04.track-asymmetry`] Intents were given to only one track or worded differently per track.
- [`04.deleted`] A dropped intent was removed instead of moved to "Ended".
