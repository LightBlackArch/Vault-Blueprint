---
title: blueprint-changes
tags:
  - reference
---

# What changed in the blueprint

This is the file that turns a pile of file diffs into a question a human can
answer. When someone runs the updater, this is what they read:

> **[3] Screenshots get their own folder**
> Right now a picture you send lands in `Inbox/` with everything else. This
> gives pictures their own home under `AIOS/history/`, writes a little note
> next to each one saying what was in it, and keeps an index of the lot. Want
> it?

Without an entry here they'd instead read *"updates the script shot.py"*, which
tells them nothing and gets declined out of caution.

> [!important] The rule for writing one
> **Describe what changes for the person, not what changed in the code.** They
> have never read your code and never will. "Screenshots get saved somewhere
> better now" is right. "Refactors `shot.py` to use `pathlib`" is wrong — it's
> true, and it's useless.
>
> Anything with no entry here still gets offered — the updater falls back to a
> generated description and their AI reads the raw diff. Nothing is ever
> invisible. An entry just makes it a decision they can actually make.

## The format

Blocks in any order. Newest at the top is easiest to read.

```
### id: some-stable-id
title: One line, plain English, no jargon
files: AIOS/scripts/thing.py, AIOS/reference/thing.md
needs: nothing            (or: Python 3.9+, or: a GitHub account — optional)

The body. Two or three sentences. What's different for them afterwards, and
why they might want it. Write it like you're telling a friend, because you
are.
```

- **`id:`** never changes once shipped. It's what "they said no to this
  already" is keyed on. Change the id and everyone who declined gets asked
  again.
- **`files:`** every file the change touches. Those files then get grouped
  under this one question instead of appearing as six separate ones.
- **`needs:`** anything extra required. Leave it as `nothing` most of the time.
- Editing the body of a shipped entry is fine and re-asks nobody. Editing the
  **files** re-asks the people who declined it, once, marked as *"you said no
  to this before, it has changed since"*. That's deliberate.

---

## Changes

### id: screentime-one-row-per-day
title: Screen time and sleep keep one row per day, and a sleep number said in the morning goes on last night
files: AIOS/scripts/screentime.py, AIOS/scripts/paths.py
needs: nothing

Telling your AI your sleep in the morning and your screen time that evening
used to give the same day two rows, and every average then counted that day
twice. Now the second number fills in the empty half of the row that's already
there, and any note already on that row is kept, with the new note added after
it. A sleep number said on its own ("slept 7 hours") is filed on the night
before, because that's the night you actually slept. And anything logged after
midnight but before 4 a.m. counts for the evening before, not for a day that
has barely started.

### id: age-stays-current
title: The age written in your me.md keeps itself up to date
files: AIOS/scripts/facts-check.py, AIOS/reference/routines.md, AIOS/skill-map.md
needs: nothing

Your `me.md` says how old you are, and that number quietly becomes wrong on
your next birthday. Nothing re-checks it, so an AI reading the file keeps
repeating the old age with full confidence. This adds a small check that reads
the birth date you already wrote in `me.md`, works out your age from today's
real date, and corrects that one number when it's out of date, with a line in
today's change log saying so. It never touches anything else in the file, and
until a full birth date (day, month and year) is written there, it does nothing
and says why. Run it yourself any time, or let the daily brief run it.

### id: video-transcripts
title: Videos you send actually get watched, not guessed at from the thumbnail
files: AIOS/scripts/video.py, AIOS/scripts/hook-video.py, AIOS/vault-map.md, AIOS/skill-map.md
needs: nothing (it downloads its own copy of yt-dlp on first use)

Before this, an AI answering about a video you sent was working from the
title and thumbnail — nothing actually opened it. Now a video link gets its
real transcript pulled and cached, and if that can't be done (private video,
no captions, network down), the AI is told plainly instead of guessing.
Optional one-time install for the strongest version — `python3
AIOS/scripts/hook-video.py --install-hook` — wires it in so the transcript
is already there the moment you paste the link, with no dependence on the
AI choosing to fetch it.

### id: link-notes
title: Every link you send gets saved as its own note
files: AIOS/scripts/link.py, AIOS/vault-map.md, AIOS/skill-map.md, AIOS/scripts/vault-check.py, Atlas/Links/Links.md, Atlas/Links/Links.base
needs: nothing

A URL pasted into a chat used to be gone the moment the chat scrolled. Now
each one gets its own note in `Atlas/Links/` — the real page title, what it
is, and a status (unread/read/useful/dead) — fetched automatically, with an
empty space at the bottom that's yours and never gets touched by an update.
Re-sending the same link updates its note instead of creating a duplicate.

### id: person-notes
title: Family, friends and teachers you mention get their own note
files: AIOS/scripts/person.py, AIOS/templates/person-note.md, AIOS/vault-map.md, AIOS/skill-map.md, AIOS/skills/auto-capture/SKILL.md, AIOS/scripts/vault-check.py, Atlas/People/People.md
needs: nothing

Mention someone specific — a sibling, a friend, a teacher — and they now get
their own small note the first time, with new details appended and dated
every time they come up again, instead of getting folded into a general
"family" or "friends" note where a specific detail about one person is easy
to lose. Works for an unnamed person too ("my maths teacher") until a name
is known.

### id: screentime-check
title: Screen time / sleep tracking can warn you instead of sitting silent
files: AIOS/scripts/screentime.py, Atlas/About Me/Screen time.md, AIOS/skills/daily-brief/SKILL.md, AIOS/skill-map.md
needs: nothing

The existing screen-time log can now watch itself: a near-zero sleep night,
a sustained low average, or a downward trend over two weeks gets flagged —
quietly, only when it's actually worth mentioning, and only once you've
logged at least one number. Wired into the daily brief if you use one, so
it can surface on its own instead of needing to be asked for.

### id: claude-code-backup-subagents
title: Claude Code backup now catches transcripts from spawned subagents too
files: AIOS/scripts/backup-claude-code.py
needs: nothing

If a Claude Code session spawns a subagent, its transcript is stored one
folder deeper than a normal session — and the backup script was only ever
looking at the top level, so those transcripts silently never made it into
the vault. Fixed; nothing to do on your end.

### id: screenshot-stamping
title: A screenshot you send now gets its facts saved permanently, not just read once
files: AIOS/scripts/shot.py, AIOS/skills/auto-capture/SKILL.md, AIOS/vault-map.md, AIOS/scripts/setup.py, AIOS/history/screenshots/Screenshots.md
needs: nothing

Before this, a screenshot got looked at once and the facts in it — coordinates,
prices, error text, whatever — went into a note if the AI remembered to.
Six months later the image itself was just a picture again. Now every
screenshot gets filed into its own dated folder, gets a short note next to it
saying what it showed and where it came from, and has those same facts
written invisibly inside the image file itself — so even if you copy the
picture out of the vault entirely, its story survives with it.

### id: money-tracking
title: Track your real balance without opening a banking app mid-conversation
files: AIOS/scripts/money.py, Atlas/About Me/Money.md, AIOS/skill-map.md, AIOS/vault-map.md, Atlas/About Me/About Me.md
needs: nothing

State a number — "spent 40 on X" or "I've got 350 in the bank" — and it gets
logged to a running ledger with the balance kept current, instead of living
only in that one conversation. Ships with an empty ledger; nothing is
invented on your behalf.

### id: media-worlds-catalog
title: One page lists everything you're watching, playing, or buying
files: AIOS/scripts/catalog.py, AIOS/vault-map.md, AIOS/skill-map.md
needs: nothing

Right now, "what shows am I watching" means an AI opening every note in
`Atlas/Media/` one at a time. This rebuilds a single page — every show, game,
book and world by status, plus what you're deciding to buy or have bought —
so that question is one grep instead of a folder scan.

### id: cooldown-tracking
title: Waiting periods get a real unlock date, not an eyeballed guess
files: AIOS/scripts/cooldowns.py, AIOS/skill-map.md
needs: nothing

A rename cooldown, a free trial ending, a returns window — anything with a
fixed wait now gets its unlock date computed for real and tracked in
`Calendar/Cooldowns.md`, with a script to check what's unlocked or coming up
in the next N days instead of asking an AI to do the date math from memory.

### id: screentime-tracking
title: Screen time and sleep, logged as you mention them
files: AIOS/scripts/screentime.py, Atlas/About Me/Screen time.md, AIOS/skill-map.md, Atlas/About Me/About Me.md
needs: nothing

State an hours number and it's appended to a running log with a rolling
average available on request. Not a nag, just the data — nothing is flagged
or judged, it's there if a pattern ever matters to you.

### id: accounts-audit
title: Get reminded about accounts you signed up for and never finished verifying
files: AIOS/scripts/accounts-audit.py, Atlas/Reference/My online accounts.md, Atlas/Reference/Reference.md, AIOS/skill-map.md
needs: nothing

Every account you sign up for gets logged, and anything still sitting
unverified after two weeks gets flagged so it doesn't just get forgotten
about — the classic way an old signup becomes a stray subscription or an
unclaimed account nobody remembers exists.

### id: machine-snapshot
title: See whether your disk is actually filling up, instead of one stale reading
files: AIOS/scripts/machine-snapshot.py, AIOS/skill-map.md
needs: nothing

Paste a `df`/`free`-style disk or RAM reading and it's logged with a
timestamp, so the trend over weeks is visible instead of a single number that
goes stale the day after it's written down.

### id: claude-code-backup
title: If you use Claude Code (the terminal tool), those sessions get backed up too
files: AIOS/scripts/backup-claude-code.py, AIOS/scripts/setup.py, AIOS/scripts/setup-check.py, AIOS/vault-map.md, AIOS/skill-map.md
needs: nothing

Until now, only conversations in the Claude desktop app got backed up into
the vault. If you also use Claude Code from a terminal, those sessions were
never saved anywhere durable. This adds the same hourly backup for Claude
Code's own session store — a separate, optional job that only turns itself on
if it finds evidence Claude Code has actually run on this machine.

### id: capture-heartbeat
title: A second, mechanical check that nothing got missed
files: AIOS/scripts/capture-heartbeat.py, AIOS/scripts/setup.py, AIOS/scripts/setup-check.py, AIOS/skills/auto-capture/SKILL.md
needs: nothing

The AI is supposed to save a fact the moment you say it, but a live
conversation can miss things. This adds a simple, no-reasoning background
check — no LLM involved, just clocks — that notices when real chat activity
happened but nothing got written to today's changes log for 45+ minutes, and
leaves a flag so it gets looked at. It can't say what was missed, only that
something probably was.

### id: weekly-digest
title: Weekly review pulls its own raw material now, instead of opening seven notes by hand
files: AIOS/scripts/weekly-digest.py, AIOS/skill-map.md
needs: nothing

Doing a weekly review used to mean an AI opening up to seven daily notes one
at a time to see what happened. This pulls the week's changes and open/closed
checkboxes into one digest first — the judgement of "what actually mattered"
is still yours to write, but the file-reading part is now one command.

### id: vault-first-clarifying-questions
title: Checks your own notes before asking you a question it could answer itself
files: AIOS/skills/vault-first/SKILL.md
needs: nothing

Before this, an AI could ask you "which device is this about?" or "what app
do you mean?" without first checking whether a project note already answered
that. Now it checks the vault's own index and the matching project note
first, and only asks if that comes up genuinely empty.

### id: vault-librarian-duplicate-check
title: Restored the check that stops the same subject getting two separate notes
files: AIOS/skills/vault-librarian/SKILL.md
needs: nothing

The vault has always had a script that checks "does a note for this already
exist" before creating a new one, but the instructions telling the AI to
actually run it before writing had drifted out of the skill. Put back, so a
subject reliably gets one note instead of accidentally getting two under
slightly different names.

### id: auto-capture-narrower-exception
title: Capture skips almost nothing now — and options you're still weighing get saved right away
files: AIOS/skills/auto-capture/SKILL.md
needs: nothing

Two tightenings to what gets written down automatically. First, the list of
things that *don't* get captured shrank to a single test: skip only when a
message has zero personal content in it at all (pure math, a unit
conversion) — anything with even a small personal detail mixed in still gets
saved. Second, options you're still weighing (not yet decided) now get
captured the moment you mention them, instead of waiting until you actually
pick one — the old behavior could lose a whole comparison if the
conversation moved on before a decision was made.

### id: me-md-more-defaults
title: A few more default working habits in the starter file
files: AIOS/me.md
needs: nothing

Four more defaults in the "how to work with me" template: never hand you a
command with a blank you have to fill in yourself; when ranking options, name
the close runner-up too, not just the winner; tell you plainly when a
connector or folder isn't shared yet instead of quietly working around it;
and say something when a conversation is getting close to its context limit.

### id: research-folder
title: A dedicated place for things you actually looked up
files: Atlas/Research/Research.md, Atlas/Atlas.md, AIOS/vault-map.md
needs: nothing

New `Atlas/Research/` folder for one note per question you've looked up —
answer, sources, what would change it. Checking here before researching the
same thing twice was previously not possible; there was nowhere for that
kind of note to live.

### id: setup-checks-catch-up
title: The self-check now actually checks for all seven skills, and the setup interview reminds itself to index new notes
files: AIOS/scripts/setup-check.py, AIOS/skills/setup-vault/SKILL.md
needs: nothing

Two small honesty fixes found by actually running a fresh setup end to end.
The self-check script was still only looking for six of the seven shipped
skills, so it could never have told you the seventh (`update-vault`) failed
to copy. And the setup interview could leave a new `Atlas/About Me/` note
created but not linked from that folder's index — findable by luck, not by
looking. Both now do what they were already supposed to.

### id: character-voice-file
title: A file for teaching your AI how you talk, not just what you want
files: AIOS/character.md, AIOS/vault-map.md
needs: nothing

A new optional file, `AIOS/character.md`, read right after `me.md`. `me.md`
covers *what* the AI should do; this one covers *how it sounds* while doing
it — the difference between an answer that's technically right and one that
reads like a person instead of a corporate report. It ships as a template
with a few blanks: what your style actually is, what tics annoy you, and
space for one real "before/after" example from your own conversations,
which turns out to matter more than any abstract rule. Delete it if you
don't want a separate voice file — nothing else depends on it.

### id: vault-conventions-split
title: Naming and formatting rules moved to their own file
files: AIOS/reference/vault-conventions.md, AIOS/vault-map.md
needs: nothing

The naming scheme, tag list, status values, and the anatomy of a daily note
used to live inside `vault-map.md`, which loads every single session. They
now live in `AIOS/reference/vault-conventions.md`, opened only when you're
actually writing or naming a note. Nothing about the rules changed — just
where they live, so the file that loads every time you type something stays
lighter.

### id: routines-reference-split
title: Routine instructions moved out of the main tooling file
files: AIOS/reference/routines.md, AIOS/skill-map.md
needs: nothing

The full step-by-step for every routine (`daily-brief`, `changelog`, `tidy`,
and the rest) used to live directly in `skill-map.md`. That file now keeps a
short one-line lookup table — trigger phrase, what it does — and the actual
steps moved to `AIOS/reference/routines.md`, opened only when a routine is
running. Same effect as the conventions split: less always-loaded text, same
capability.

### id: naming-duplicate-check
title: A check before creating a note, so you don't end up with two notes about the same thing
files: AIOS/reference/naming.md, AIOS/scripts/route-check.py
needs: nothing

Before creating a new note, your AI can now check whether one already
covers the subject — "Bike Purchase" and "Buying a bike" would otherwise
both get created, and then only one of them ever gets found again. The
check also finds collisions that already happened, and flags filenames that
break the vault's naming scheme. A small table in `naming.md` lets you mark
two similarly-named notes as genuinely different things, so the check
doesn't keep asking about ones you've already confirmed.

### id: diary-and-when
title: A real diary section, and a way to ask "when did I do X"
files: AIOS/scripts/diary.py, AIOS/scripts/notelock.py, AIOS/scripts/logchange.py, AIOS/scripts/capture.py, AIOS/templates/daily-note.md, AIOS/reference/vault-conventions.md
needs: nothing

The daily note's `## Log` section is now `## Diary` — a plain space for
what actually happened that day, written by you or by the AI the moment
you mention something, no timestamps or markers required. The real change
is underneath: every diary line ever written gets indexed, so asking "when
did I go to the lake?" is an instant, honest lookup instead of an AI
guessing its way through old notes. It will say plainly when there's no
record, rather than making one up. Also fixes a real bug: two scripts
writing the same daily note at once could previously corrupt it; they now
share a lock.

### id: dated-events
title: Trips, appointments and exam weeks get their own kind of note that links itself into your calendar
files: AIOS/scripts/event.py, AIOS/templates/event-note.md, AIOS/scripts/logchange.py
needs: nothing

A new note type for anything with a start and end date that isn't a project
— a trip, a hospital appointment, an exam week. Create one and it
automatically shows up on every day it covers, in that day's note, with its
status ("upcoming" / "happening" / "done") kept current on its own. Before
this, a note like that could sit in a folder for its entire duration without
anything on the actual days pointing at it.

### id: move-and-verify
title: Renaming or moving a file, and checking nothing broke, are both one command now
files: AIOS/scripts/move.py, AIOS/scripts/verify.py, AIOS/reference/moves.md, AIOS/scripts/paths.py
needs: nothing

Renaming or relocating a note used to mean manually finding and fixing
every place that mentioned its old path — easy to miss one. One command now
does the move and rewrites every mention across the whole vault, and keeps
a running history of what moved where. A second new command lets your AI
snapshot the vault before a big change and diff it after, so "did anything
break" gets a real answer — files added, removed, or suspiciously
shortened — instead of a reassurance.

### id: where-and-scale-generators
title: Two self-updating index files — what every note is about, and how big each folder is
files: AIOS/scripts/route-check.py, AIOS/scripts/vault-map.py
needs: nothing

Two files now keep themselves current automatically: one indexes every note
by the words that actually distinguish it, so finding something is one grep
instead of an AI opening files at random; the other keeps an honest,
per-folder note count instead of a hand-typed number that goes stale within
days.

### id: taste-commands-migration-generators
title: Three more files that keep themselves current
files: AIOS/scripts/taste.py, AIOS/scripts/commands.py, AIOS/scripts/migration-scan.py, AIOS/reference/migration.md, AIOS/reference/setup.md
needs: nothing

A taste profile that compiles everything you like/dislike into one place
instead of scattered across notes; a flat list of every command and trigger
phrase in the vault, for when you've forgotten the exact wording; and an
inventory step for the file you'd hand to a different AI if you ever
switch, so it can't quietly go out of date.

### id: stale-and-orphan-check
title: A check for facts that have probably gone stale, and notes nothing links to
files: AIOS/scripts/stale-check.py
needs: nothing

A report-only check that flags two things a broken-link checker can't see:
a note whose content has a shelf life and is past it (a "currently watching"
note nobody's touched in a month), and a note that exists and is correct but
that nothing else links to, so it's only findable by luck.

### id: project-status-and-chronicle-scripts
title: A few routines that used to be manual are now one command
files: AIOS/scripts/project-status.py, AIOS/scripts/chronicle.py, AIOS/scripts/capture.py
needs: nothing

"Where does this project actually stand" and "write up this old
conversation with decisions pulled to the top" both used to mean an AI
reading a full note or retyping a transcript by hand. Both are now a single
script call — faster, and the same every time.

### id: canon-correction-in-auto-capture
title: Corrections to a fact now get tracked so they reach every note that repeats it
files: AIOS/skills/auto-capture/SKILL.md
needs: nothing

If a fact gets corrected in one note but the vault has it written in three
others, the old fix left the other three wrong — no error, no broken link,
just quietly out of date. The capture skill now registers a corrected fact
in one place and checks the whole vault for the old wording, in the same
turn as the correction.

### id: daily-brief-events-and-receipt
title: Daily brief now shows today's events and logs its own receipt
files: AIOS/skills/daily-brief/SKILL.md
needs: nothing

The daily brief now pulls in anything from the new dated-events feature
that's happening today, and logs a one-line receipt of its own run — small,
but it closes the last gap where a vault write could happen with no record
of it.

### id: me-md-new-defaults
title: A few new default working habits
files: AIOS/me.md
needs: nothing

Three small defaults added to the "how to work with me" template: check
whether a repeated manual step should just be a script before doing it by
hand again; don't open a file just to append to it when a blind-write
command already exists; and after any change touching several files, show
what was actually touched instead of just saying it's fine.

### id: vault-updates-from-blueprint
title: Your vault can now pull in blueprint improvements by itself
files: AIOS/scripts/blueprint-update.py, AIOS/scripts/blueprint-manifest.py, AIOS/scripts/blueprint-release.py, AIOS/reference/blueprint-changes.md, AIOS/skills/update-vault/SKILL.md, UPDATE-MY-VAULT.md
needs: nothing

Until now, if the blueprint got better after you downloaded it, you'd never
find out. This adds a way to check.

Say **"update my vault from the blueprint"** and your AI fetches the latest
version, works out what's actually different from your copy, and reads the
changes out to you one at a time in plain English. You pick what you want.
Anything you say no to is remembered and never brought up again.

It cannot touch your writing. Your notes, your `Privat/` folder, and your own
answers in `AIOS/me.md` are off limits to it by design, not by good intentions
— the four files that are half yours (`CLAUDE.md`, `me.md`, `vault-map.md`,
`skill-map.md`) can only ever be merged by your AI, sentence by sentence, never
overwritten by a script. Everything it does change is backed up first, so
"undo the last blueprint update" is a real thing you can say.

Also works from the terminal on its own, if you'd rather:
`python3 AIOS/scripts/blueprint-update.py --interactive`
