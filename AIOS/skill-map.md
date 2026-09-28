# skill-map.md

> Dictionary of what tooling is available and when to use it. Skills are packaged
> instructions loaded by the AI. Routines live here in the vault as plain
> markdown, so you own them regardless of which AI you use.

## Installed skills

> [!warning] Keep this table honest
> If a skill gets installed or removed, update this table. An AI trusting a stale
> list will confidently reference tooling that isn't there. `vault-check.py`
> compares this file against what's actually installed and complains.

### Vault — the core five

| Skill | Use when |
|---|---|
| `auto-capture` | **Always on.** Captures decisions, status changes, facts, media, world state from screenshots, numbers, tasks and Radar interests as they come up. One note per subject, never a catch-all file. No transcripts unless asked. Mirrors any changed skill into `AIOS/skills/`. Every write gets a line in today's `## Changes`. |
| `vault-first` | **Always on.** Opens the matching note *before* answering anything about you or your stuff. Rule Two: never say a fact isn't saved without grepping for it first. |
| `vault-librarian` | **Always on when writing.** Where a new note goes, required frontmatter, tag scheme, naming, and how to invent a home when nothing fits. |
| `no-bullshit` | **Always on.** Fires before any claim you'll act on — specs, prices, versions, compatibility, "is this safe" — and whenever you push back or ask "are you sure". |
| `daily-brief` | Morning brief into today's daily note, and the `log` routine. |

### Worth installing (Anthropic's, one click)

| Skill | Use when |
|---|---|
| `morning` | Renders the morning brief as a styled HTML page instead of plain markdown |
| `consolidate-memory` | Periodic pass to merge duplicate notes and prune stale facts |
| `obsidian-markdown` | Writing notes — frontmatter, callouts, wikilinks |
| `obsidian-cli` | Reading/searching the vault from the command line |
| `schedule` | Setting up recurring automated tasks ("every morning at 6") |
| `skill-creator` | Building a new skill or fixing one that doesn't trigger reliably |
| `find-skills` | Looking for a skill that might already exist for something |
| `docx` `xlsx` `pptx` `pdf` | Documents, spreadsheets, decks, PDFs |

### Staying current

| Skill | Use when |
|---|---|
| `update-vault` | **"update my vault from the blueprint".** Fetches the latest blueprint, works out what's genuinely different from *your* vault, reads the changes out in plain English, and applies only what you pick. Never overwrites anything you wrote. Keep this one — it's how every future improvement reaches you. |

### Setup only — delete when done

| Skill | Use when |
|---|---|
| `setup-vault` | **The whole first-run bootstrap.** Triggers on "set yourself up" and similar — runs the setup scripts, gets the skills active for whatever platform this is, runs the interview from `AIOS/setup-questions.md`, and finishes with a real self-check. One skill, one trigger phrase, does everything. |

> [!note] Every skill is backed up in the vault
> Plain-markdown copies live in `AIOS/skills/<name>/SKILL.md`, re-exported
> automatically whenever a skill changes. That folder is the portability
> guarantee — it works in Claude Code as-is, and is readable by any other AI.

---

## Routines

Plain-language procedures. Say the name and the AI follows the steps. These are
deliberately not code and not provider-specific — **edit them in plain
English.** This table is the lookup; **`AIOS/reference/routines.md`** carries
the full steps for each one — open it when a routine is actually running, not
at session start.

| Routine | Fires | One line |
|---|---|---|
| `message-capture` | Start of every session | Scan the incoming message for facts, decisions, plans, questions — route each to the right note. |
| `daily-brief` | On request, or scheduled | Calendar + mail + deadlines + cooldowns → today's daily note. |
| `capture` | Any blind append (Radar/canon/frontmatter/table row/diary) | One command via `capture.py` — never open the file first. |
| `diary` | Any real-life thing you mention | One plain line into today's `## Diary`. `python3 AIOS/scripts/diary.py "..."` |
| `when` | "When did I…" about anything that happened | `python3 AIOS/scripts/diary.py --when "<thing>"` — answers from the generated index or says plainly there's no record. |
| `event` | A dated real-life thing that isn't a project — trip, appointment, exam week | `python3 AIOS/scripts/event.py "<Title>" --start YYYY-MM-DD [--end YYYY-MM-DD]`. Links itself into every daily note it covers. |
| `changelog` | Every single vault write, no exception | `logchange.py` appends the receipt and runs a few guards that keep generated files honest. |
| `log` | You dictate a thought | Timestamp, clean typos only, append to today's diary. |
| `next` | On request | Regenerate `Efforts/Next Actions.md` from project notes. |
| `cooldown` | Any fixed waiting period, unprompted | `python3 AIOS/scripts/cooldowns.py --check` / `--upcoming N` — compute the unlock date for real, row in `Cooldowns.md`. `--resolve` moves a row to Passed. |
| `money` | Any real balance, spend, or gift you mention | `python3 AIOS/scripts/money.py "<what>" <±amount>` for a transaction, or `--set-balance <amount> --note "..."` when you state a real number. Appends to a ledger, flags drift between what it predicted and what you actually reported. |
| `catalog` | Any write to `Atlas/Media/`, `Atlas/Worlds/`, an `Efforts/*Purchase*.md` note, or a money note | `python3 AIOS/scripts/catalog.py` — rebuilds `AIOS/generated/catalog.md`, one rolled-up index of everything you're watching/reading/playing, worlds/servers, and purchases (deciding + bought). |
| `screentime` | A screen-time or sleep number you state | `python3 AIOS/scripts/screentime.py --hours N [--sleep N]`. `--avg` for the rolling average, `--check` for a silent-unless-triggered warning (near-zero night, sustained low average, downward trend) — wire it into `daily-brief` if you want it surfaced automatically. |
| `video` | Every video link sent, before answering anything about it | `python3 AIOS/scripts/video.py "<url>"` — prints the real transcript, caches it to `AIOS/history/transcripts/`. **Exits non-zero and says so if it can't get one** — an unwatchable video is an error, never a blank you fill in from the title. `--check` self-tests the toolchain, `--list` shows what's cached. Guaranteed by a `UserPromptSubmit` hook, not just the model choosing to run it: `python3 AIOS/scripts/hook-video.py --install-hook`, then restart the app. Also fires inside `link` for YouTube URLs. |
| `link` | Every URL sent, no exception | `python3 AIOS/scripts/link.py "<url>" --why "..." --tag x` — fetches the page, writes its own note in `Atlas/Links/` with the real title, dedupes by normalized URL, regenerates the index, logs its own receipt. `--from-text "<pasted message>"` pulls every URL out of a blob. `--list` / `--find "<word>"` / `--set "<match>" read` / `--check` (re-test for dead links) / `--rebuild`. Never rewrites `## My notes`. |
| `person` | Any time you tell the AI something about a specific family member, friend, or teacher — first mention or a new detail about one already noted | `python3 AIOS/scripts/person.py "<Name>" --category family/friend/teacher --relation "..." --fact "..."` — creates `Atlas/People/<Name>.md` on first mention, appends dated facts on every later one, rebuilds `Atlas/People/People.md`. Unnamed still gets a note under a role (`Mum`, `Maths teacher`) until a name is known. `--list` / `--rebuild-index`. Nothing from `Privat/`. |
| `accounts-audit` | Re-checking account state, or after a fresh signup pass | `python3 AIOS/scripts/accounts-audit.py --check` — ages every row in an "online accounts" reference table, flags anything unverified 14+ days. `--add`/`--add-active` to log a new one. |
| `machine-snapshot` | Any `df`/`free`/`lsblk`-style numbers you paste or report | `python3 AIOS/scripts/machine-snapshot.py --machine "<label>" --disk "..." --ram "..."` — a dated row in a history file, so disk/RAM trends are visible instead of one stale reading. |
| `shot` | Every image sent, no exception | `python3 AIOS/scripts/shot.py IMAGE --shows "..."` — embeds facts in the file itself, writes a sidecar note, adds an index row. |
| `backup-claude-code` | Hourly (optional, your own machine's scheduler) | Claude Code CLI session transcripts → `AIOS/history/chat-history/claude-code/`. Same shape as `backup-cowork`, separate session store. |
| `capture-heartbeat` | Every 30 min (optional, your own machine's scheduler) | Mechanical, no reasoning: flags when chat activity synced but today's `## Changes` got zero entries for 45+ minutes. |
| `vault-map` | Any note created/deleted | Rebuilds the note-count table in `AIOS/generated/scale.md`. |
| `route-check` | Any note created/deleted | Rebuilds `AIOS/generated/where.md`, the one-grep index. |
| `naming` | Before creating any note | Checks this subject doesn't already have a note. |
| `relocate` | Any time a file/folder needs to move or be renamed | `move.py` — moves it and rewrites every mention across the vault. Never `mv` by hand. |
| `verify` | Before/after a multi-file change | Snapshot/diff — did anything break, in numbers. |
| `vault-check` | Monthly or on request | Broken links, bad frontmatter, stale skill list. |
| `context-budget` | Any boot-file write | Measures the always-loaded floor. |
| `backup-cowork` | Hourly (your own machine's scheduler) | Chat history → `AIOS/history/chat-history/cowork/`. |
| `vault-snapshot` | Every 10 min (optional, your own machine) | git commit + push, writes `git-status.md`. |
| `update-vault` | "update my vault from the blueprint" | Pulls in blueprint improvements as yes/no questions. Never overwrites your writing. |
| `setup-check` | On request, especially after setup | One pass/fail table — is the automation actually working. |
| `canon-check` | `canon.md` touched (immediate) | Finds notes still repeating a corrected fact. |
| `facts-check` | Every morning inside `daily-brief`, or on request | `python3 AIOS/scripts/facts-check.py --check` — keeps facts that change with the date current (your age in `me.md`), fixing that one number in place and logging it. `UNARMED` until a full birth date is written. `--list` shows the values without writing. |
| `stale-check` | Weekly (if scheduled), or on request | EXPIRED / ORPHAN / NO ROUTE report. |
| `changelog-check` | Timer, if scheduled | Catches a write with no `## Changes` receipt. |
| `project-status <project>` | On request | Where it stands, what's blocking it, next action. |
| `decide <question>` | On request | Trade-offs with numbers, a recommendation. |
| `learn <topic>` | On request | Scaffold a new `Knowledge/` note. |
| `weekly-review` | Sunday (if scheduled) | What got done, what slipped. `python3 AIOS/scripts/weekly-digest.py [--week YYYY-Wnn] [--write]` pulls the week's raw material (changes + checkboxes) first, so you're not opening 7 daily notes by hand. |
| `rock-tumbler <note>` | On request | IDI feedback on writing, never rewrites. |
| `chronicle` / `save-chat` | On request | Curated write-up from an already-backed-up chat. |
| `migrate` | On request — "make vault migratable" | Refreshes `AIOS/reference/migration.md`'s inventory. |
| `courier <note>` | On request | Strip personal info, show before it leaves. |
| `tidy` | On request | Housekeeping list — propose first, change nothing. |

## Adding a routine

Full steps go in `AIOS/reference/routines.md`, same shape as the others there.
Add one row to the table above so it can be found without opening that file.

## When to promote a routine into a skill

A routine becomes worth turning into a real skill when:

- You run it more than about once a week, **and**
- It needs to trigger automatically without you naming it, **or**
- It needs reference files, scripts, or more instructions than fit here readably.

Use the `skill-creator` skill to do it, and keep the routine here as the
plain-markdown fallback.

## Related

- [[Home]]
- [[me]]
- [[vault-map]]
- [[routines]] — the full steps for every routine above
- [[how-to-use-this]]
