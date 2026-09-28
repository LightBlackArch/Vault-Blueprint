---
name: "daily-brief"
description: "Compile the user's daily brief and write it into today's Obsidian daily note, or append a timestamped thought via the `log` routine. Use when they say \"daily brief\", \"brief me\", \"what's on today\", \"morning brief\", \"log ...\", or when the scheduled morning task runs."
---

# Daily Brief

Write today's brief into `Calendar/Daily/YYYY-MM-DD.md` in the user's vault.
The note's sections are Brief → Events (machine-owned, `event.py`, only present
if something's actually on) → Diary → Changes.

## Before writing

Get today's real date — check it, don't assume.

If the file doesn't exist, create it from `AIOS/templates/daily-note.md`.
If it exists, **fill in the Brief section only. Never touch anything below
`## Diary`.**

## What goes in the brief

Gather what's actually available. Skip sections for sources that aren't
connected at all rather than writing filler.

**But a check that failed is not a check that found nothing.** If a connected
source errors out (mail, calendar, a search), or a script below exits with an
error, carry on with the rest and write one line saying so — `Email: not
checked (connector error)`. Never leave that section out as if it were empty:
"nothing important" and "nothing was looked at" must never read the same.

1. **Weather** — for wherever they live, per `AIOS/me.md`. Search for it; don't
   guess.
2. **Cooldowns** — read `Calendar/Cooldowns.md` if it exists. Anything unlocking
   **today** goes near the top with the action it enables. Anything unlocking
   within 7 days gets one heads-up line. Neither? Write nothing — no "no
   cooldowns" filler. Compare against the real date, don't eyeball it.
3. **Today's events** — from a calendar connector if one is available, and from
   any `Calendar/Events/` note covering today (`python3 AIOS/scripts/event.py
   --today`). If neither has anything, skip the section silently.
4. **Unread and important email** — from a mail connector if one is available.
   Important means: money, school or work, something expecting a reply. Not
   newsletters.
5. **Deadlines** — check dated items in `Efforts/`.
6. **Project momentum** — which notes in `Efforts/` changed in the last 3 days,
   and which haven't been touched in over a week. Name the stale ones; that's the
   useful half.
7. **Suggested focus** — exactly one thing. Pick what unblocks the most other
   work, and say in one line why.
8. **Screen time / sleep check** — if `Atlas/About Me/Screen time.md` has any
   log rows, run `python3 AIOS/scripts/screentime.py --check`. Add a line to
   the brief if it prints `WARN`, `UNARMED`, or `STALE` — silent only on `OK`,
   same no-daily-nag rule as everywhere else in this list. Skip the whole step
   if the note has never been logged to — an unused check has nothing to say.
9. **Facts that change with the date** — if `AIOS/scripts/facts-check.py`
   exists, run `python3 AIOS/scripts/facts-check.py --check`. It keeps the age
   in `AIOS/me.md` current and fixes it itself. Add a line to the brief only
   if it prints `CORRECTED` (say what changed) or `WARN` (surface it as is).
   `OK` and `UNARMED` add nothing.

## After writing

Log the receipt, per `auto-capture` Rule Three:

```
python3 AIOS/scripts/logchange.py "Daily brief written" "Calendar/Daily/YYYY-MM-DD.md" --kind append
```

Check it exits zero. If it fails, say so plainly — never claim a write happened
when it didn't.

## Tone

Short. This gets read in under a minute. No preamble, no encouragement, no
"Good morning!". Bullets, not paragraphs.

If nothing is happening today, say so in one line. A brief that pads itself out
teaches them to stop reading it.

## The `log` routine

When they say `log` followed by a thought:

1. Get the current time (`HH:MM`).
2. Clean up **only** obvious typos. Keep their wording, their phrasing, their
   voice. Do not make it more articulate. Do not expand it.
3. Append a plain line under `## Diary` in today's daily note (no timestamp
   prefix needed, but keep one if it helps you scan a busy day):

   `- the thought, in their words`

4. Confirm in one short line. Don't repeat the entry back at them.

## Never

- Overwrite anything they typed themselves
- Read or write anything under `Privat/`
- Invent calendar events, email, or weather when the source isn't connected

## Related

Conventions: the `vault-librarian` skill and `AIOS/vault-map.md`.
