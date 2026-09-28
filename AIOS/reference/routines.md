---
title: routines
tags:
  - reference
---

# routines — full instructions, one per routine

> [!important] Opened on demand, never boot-loaded
> `AIOS/skill-map.md` keeps a one-line lookup table — trigger phrase, what it
> does, one sentence. This file carries the actual steps. Open it when a
> routine is running, not at session start.

## `message-capture` — at the start of every session

Scan the incoming message for facts, decisions, products, plans, questions —
route each to the right note. No filter, no "important enough" test. This is
what makes `auto-capture` actually fire on ordinary conversation instead of
only on things that sound like instructions.

## `daily-brief`

Compile today's brief. Steps:

1. Pull today's events from a calendar connector and anything unread and
   important from mail, if either is connected.
2. Check deadlines in `Efforts/` and any project notes touched in the last 3 days.
3. **Check `Calendar/Cooldowns.md`** if it exists. Anything unlocking today goes
   near the top with the action it enables; anything within 7 days gets one line.
   Neither? Write nothing.
4. Output: what's on today, what's slipping, one suggested focus.
5. Write to `Calendar/Daily/YYYY-MM-DD.md` using `AIOS/templates/daily-note.md`.
   **Never overwrite what you already wrote — append.**

## `changelog`

**Runs without being asked, on every single vault write.** Not something you
invoke — something that happens automatically.

```
python3 AIOS/scripts/logchange.py "what changed" "path/to/note.md" --kind edit
```

`--kind` defaults to `edit`. Others: `new`, `append`, `skill`, `script`,
`template`, `map`, `delete`. Several at once via stdin, tab-separated:

```
printf 'what\tpath\tkind\n...' | python3 AIOS/scripts/logchange.py --stdin
```

The script creates today's daily note from the template if it's missing,
creates the `## Changes` section if it's missing, and only ever appends.
Non-zero exit on failure — check it, don't assume. Several guards ride along
that keep generated files (`where.md`, `commands.md`, `taste.md`, `scale.md`,
`happened.md`) from drifting — see the script's own docstring.

**The daily note is the receipt. The subject note is still the content.**

Lines must be specific enough to be useful in six months:

- **Good:** `Status stalled → active after the part arrived → Efforts/Some Project.md`
- **Useless:** `Updated a note`

## `capture`

Any write to Radar/canon/frontmatter/a table row/today's diary that doesn't
need the file read first. Blind append via `capture.py` — never open the
file just to append to it:

```
python3 AIOS/scripts/capture.py --log "one thing that happened" \
  --set "Atlas/Media/Some Show.md::status=finished"
```

Every flag is repeatable and batches into one `logchange.py` call at the
end. See the script's own docstring for the full flag list.

## `diary` — what actually happened, and finding it again

**Runs without being asked**, the moment you mention something that happened
to you — where you went, who you saw, what you did. One plain line into
today's `## Diary`, no time, no marker:

```
python3 AIOS/scripts/diary.py "Went to the lake with friends, swimming"
python3 AIOS/scripts/diary.py --date 2026-08-18 "Backdated entry"   # backdate
```

You can also just type straight into the `## Diary` section yourself.

## `when` — when did I do X

**Never answer "when did I…" from memory.** Run:

```
python3 AIOS/scripts/diary.py --when "the lake"
```

It answers from `AIOS/generated/happened.md` — every event ever recorded,
one line each, plus every name and place with its dates — or it says
plainly there's no record. A confident guess about your own life is the
worst kind of wrong answer, and this is the one question where nothing
else catches it.

## `event` — a dated thing that isn't a project

A trip, an appointment, an exam week — anything anchored to specific dates
that isn't a project and isn't a diary entry:

```
python3 AIOS/scripts/event.py "Some Trip" --start 2026-09-01 --end 2026-09-05 \
  --where "somewhere" --about "one line on what it is"
python3 AIOS/scripts/event.py --today       # what's on today
python3 AIOS/scripts/event.py --upcoming 14 # the next two weeks
```

Creating one automatically links it into the `## Events` section of every
daily note it covers, and re-derives its status (`upcoming` → `happening` →
`done`) every time anything under `Calendar/Events/` is touched. A note
that isn't linked from the day it matters is a note that won't be read that
day.

## `next`

The "what do I actually do now" page. Run:

```
python3 AIOS/scripts/next-actions.py
```

It regenerates `Efforts/Next Actions.md` from two sources it never invents: every
project note's `## Next action` section, and every open `- [ ]` checkbox outside
`Privat/`. Then read the live table.

Source of truth stays in the project notes — the generated file is disposable. If
a project has no `## Next action` section, the script names it at the bottom
rather than silently skipping it.

## `backup-cowork`

Copy your Claude/Cowork chat history into `AIOS/history/chat-history/cowork/`
(readable Markdown) and `cowork-raw/` (exact originals). **Must run on your own
machine, not from inside a cloud AI session.**

```bash
python3 AIOS/scripts/backup-cowork.py
python3 AIOS/scripts/backup-cowork.py --install-schedule --every-min 60
```

## `setup`

New machine. Registers folders, tries to install the scheduled jobs, prints
manual links for anything needing your hands. Say "set yourself up", or
directly: `python3 AIOS/scripts/setup.py`.

## `vault-snapshot`

Optional. Commits the vault to git and pushes it.

```bash
python3 AIOS/scripts/vault-snapshot.py
python3 AIOS/scripts/vault-snapshot.py --install-schedule --every-min 10
```

## `context-budget`

```
python3 AIOS/scripts/context-budget.py            # report
python3 AIOS/scripts/context-budget.py --baseline # reset the baseline
```

Measures what loads before you type a word and shouts if the floor has
grown noticeably since the baseline. Run it before adding text to any
always-loaded file.

## `vault-map` — rebuild the note-count table

```
python3 AIOS/scripts/vault-map.py             # rewrite AIOS/generated/scale.md
python3 AIOS/scripts/vault-map.py --check     # is it stale?
python3 AIOS/scripts/vault-map.py --reviewed  # stamp: hand-written half re-read
```

Runs automatically on any note create/delete. The generated block also
nags, every `REVIEW_EVERY` notes, that the hand-written folder map in
`vault-map.md` is due a re-read — a script can count notes, it can't decide
where they belong.

## `route-check` — the one-grep note index

```
python3 AIOS/scripts/route-check.py            # rebuild AIOS/generated/where.md
python3 AIOS/scripts/route-check.py --find gravel bike
```

Runs automatically whenever a note is created or deleted. Rebuilds
`AIOS/generated/where.md`, and fails (`--check`) if a project note in
`Efforts/` has no hand-written route in `vault-map.md`.

## `naming` — one subject, one name, one note

Before creating any note:

```
python3 AIOS/scripts/route-check.py --exists "the subject"
```

Exits 1 with the existing note if one probably already covers it. Full
scheme: [[naming]].

## `stale-check`

```
python3 AIOS/scripts/stale-check.py
```

Finds notes whose content has probably stopped being true (past its
folder's shelf life) and notes nothing links to. Reports only.

## `canon-check`

```
python3 AIOS/scripts/canon-check.py
```

Greps the whole vault for stale wording after a repeated fact gets a row in
`AIOS/reference/canon.md`. Run right after correcting anything repeated in
more than one note — `logchange.py` also runs it automatically whenever
`canon.md` itself is touched.

## `facts-check` — facts that go stale with the calendar

```
python3 AIOS/scripts/facts-check.py --check   # fix drift, print what changed
python3 AIOS/scripts/facts-check.py --list    # every fact's value today, writes nothing
```

Recomputes facts that are pure functions of today's date — for now just your
age, from the birth date on the `Born` line of `AIOS/me.md` — and fixes that
one number in place when it's out of date, with a receipt in today's
`## Changes`. Nothing else in the file is touched. Prints `UNARMED` and does
nothing until that line holds a full date (DD.MM.YYYY). The daily brief runs
it every morning. `canon-check` above is the other half: it catches a fact
that was corrected in one note but not in the others.

## `relocate` — moving or renaming anything

```
python3 AIOS/scripts/move.py "<old/path>" "<new/path>" --reason "..."
```

Moves it, rewrites every mention across notes/scripts/config, logs the row
in `AIOS/reference/moves.md`. **Never `mv` a vault file by hand.**

## `verify` — did anything break

```
python3 AIOS/scripts/verify.py --snapshot     # before a multi-file change
... do the work ...
python3 AIOS/scripts/verify.py --diff         # after — prints the numbers
```

What was added, removed, changed; whether any `.md` file's line count
dropped suspiciously (possible content loss); whether `Privat/` was
touched. Run this after any change touching more than a couple of files.

## `vault-check`

Integrity pass. Run:

```
python3 AIOS/scripts/vault-check.py
```

Reports broken wikilinks, missing frontmatter, notes not reachable from their
folder index, `status:` values outside the allowed vocabulary, dead `dataview`
blocks, skills installed but missing from `skill-map.md`, and sync conflict files.
**Reports only.** Run it monthly, or whenever the vault feels wrong.

## `changelog-check`

**Runs on its own if scheduled.** Notices a note whose content changed with
no `## Changes` receipt for it, and appends a catch-line so the miss
doesn't disappear silently. First run ever only builds a baseline.

## `project-status <project>`

```
python3 AIOS/scripts/project-status.py "<name>"
```

Where a project stands, what's blocking it, and its single next action —
without opening the full note.

## `decide <question>`

When stuck between options. Lay out the real trade-offs with numbers where
numbers exist, give a recommendation, and say what would change your mind.
Then write the decision into the project note's decisions log once picked.
**Don't guess the numbers.** Search for specs and prices, or say plainly
you're unsure.

## `learn <topic>`

Scaffold a new topic: what it is, why it matters, the things to learn in
order, and one concrete thing to build this week. Create a note in
`Atlas/Knowledge/` from `AIOS/templates/learn-note.md`.

## `weekly-review`

Sunday pass. Read the week's daily notes. What actually got finished, what
was promised and didn't happen, which projects went untouched, and what to
drop. Be blunt. Write to `Calendar/Weekly/YYYY-Wnn.md` from
`AIOS/templates/weekly-review.md`.

## `rock-tumbler <note or text>`

Feedback on creative writing without rewriting it. Your voice is the asset.

Ask open-ended questions using the **IDI** framework:

1. **Imagine** — what could this become? What's the version of this that's
   more itself, not more conventional?
2. **Discern** — what's actually working, and what's doing nothing?
3. **Integrate** — how does this connect to what already exists in the
   vault?

Questions over prescriptions, roughly 3:1. Point at logic gaps directly.
Never rewrite a passage unless explicitly asked.

## `chronicle` / `save-chat`

```
python3 AIOS/scripts/chronicle.py "<topic>" --find "<keyword>"
```

Finds an already-backed-up chat and writes a curated version with a
decisions/action-items/open-questions header on top, into
`AIOS/history/chat-history/curated/`. Only works on chats `backup-cowork.py`
has already saved.

## `migrate` — "make vault migratable"

```
python3 AIOS/scripts/migration-scan.py --write
```

Refreshes the generated inventory block in `AIOS/reference/migration.md` —
hand that one file to a new AI and it rebuilds the automation layer itself.

## `courier <note>`

Prepare a note for someone else's eyes. Steps:

1. Read the note plus any notes it wikilinks to.
2. Strip anything personal.
3. Replace wikilinks with a short inline summary or nothing.
4. Output as a standalone file.
5. **Show the sanitised version before it leaves.** Every time.

Never courier anything from `Privat/`.

## `tidy`

Housekeeping. Find notes with no links, inconsistent tags, obvious
duplicates, orphan files, and frontmatter that doesn't match
`vault-conventions.md`. **Propose a list first. Change nothing until
approved.**

---

## Adding a routine

Full steps go here, same shape as the others. Add one row to the table in
`AIOS/skill-map.md` so it can be found without opening this file.

## When to promote a routine into a skill

A routine becomes worth turning into a real skill when:

- You run it more than about once a week, **and**
- It needs to trigger automatically without you naming it, **or**
- It needs reference files, scripts, or more instructions than fit here
  readably.

Use the `skill-creator` skill to do it, and keep the routine here as the
plain-markdown fallback.

## Related

- [[skill-map]] — the one-line lookup table
- [[vault-map]]
- [[naming]]
- [[me]]
