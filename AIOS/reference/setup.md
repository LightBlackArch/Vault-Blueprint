---
title: setup
tags:
  - reference
---

# setup — every script in the vault

> [!important] Opened on demand, never boot-loaded
> For actually setting the vault up on a new computer, see
> **`README-START-HERE.md`** (say "set yourself up") and
> `python3 AIOS/scripts/setup-check.py` for the self-check. This file is the
> reference catalog of what every script does, for when you want to know
> what's available without re-reading each docstring.

## Every script

### `AIOS/scripts/`

| Script | What it does |
|---|---|
| `setup.py` | First-run bootstrap: creates folders, tries to install the scheduled jobs (`backup-cowork`, `vault-snapshot`) using whatever this OS actually has. |
| `setup-check.py` | The one "is this actually working" command — Python version, `me.md` filled-in state, skills active, scheduler found, chat folder found, git set up, `vault-check.py` pass. |
| `scheduler.py` | Cross-platform cron/Task-Scheduler abstraction other scripts install jobs through. Not called directly. |
| `logchange.py` | Appends one line to today's daily note under `## Changes` on every vault write. Runs several guards (see its own docstring) that keep generated files honest — `where.md`, `commands.md`, `taste.md`, `scale.md`, `happened.md`. |
| `notelock.py` | Shared file-lock module, imported by `logchange.py` and `diary.py` — not run directly. Stops two scripts racing to write the same daily note. |
| `paths.py` | The path registry every other script can import instead of hardcoding a string. Run `python3 AIOS/scripts/paths.py` to print every registered path. |
| `move.py` | Move or rename a file/folder and rewrite every mention of the old path across the vault, in one command. Never `mv` a vault file by hand. |
| `verify.py` | `--snapshot` before a multi-file change, `--diff` after — what was touched, what was deleted, whether anything shrank suspiciously, whether `Privat/` was touched. |
| `vault-check.py` | Integrity pass: broken wikilinks, missing frontmatter, bad `status:` values, dead `dataview` blocks, stale skill list. Reports only. |
| `vault-map.py` | Rebuilds the note-count table in `AIOS/generated/scale.md`. Runs automatically on any note create/delete. |
| `route-check.py` | Rebuilds `AIOS/generated/where.md` (the one-grep note index); `--exists` checks whether a subject already has a note before you create a duplicate; `--dupes` finds existing collisions; `--naming` checks filenames against the scheme in `naming.md`. |
| `stale-check.py` | Finds notes whose content has probably gone stale (past its folder's shelf life) and notes nothing links to. Reports only, except `--fix-orphans`. |
| `canon-check.py` | Greps the vault for stale wording after a repeated fact gets corrected in `AIOS/reference/canon.md`. |
| `taste.py` | Compiles every note's `## Taste` section into `AIOS/generated/taste.md`, grouped by category. |
| `commands.py` | Rebuilds `AIOS/generated/commands.md` — every skill and routine trigger phrase, in one flat list — whenever `skill-map.md` changes. |
| `migration-scan.py` | Rebuilds the generated inventory block in `AIOS/reference/migration.md` (what skills/routines/scripts exist), for the `migrate` routine. |
| `context-budget.py` | Measures what loads before you type a word — the always-loaded floor — and flags growth. |
| `changelog-check.py` | Scheduled: catches a note that changed with no `## Changes` receipt. |
| `next-actions.py` | Rebuilds `Efforts/Next Actions.md` from every project's `## Next action` section and every open checkbox. |
| `project-status.py` | `project-status <name>` — where a project stands, what's blocking it, its next action, without opening the full note. |
| `event.py` | Dated things that aren't projects — a trip, an appointment. Creates `Calendar/Events/YYYY/<Title>.md` and keeps it linked into the days it covers. |
| `diary.py` | Appends to today's `## Diary`, and answers "when did I…" from `AIOS/generated/happened.md` — an index of every real-life event ever recorded. |
| `capture.py` | Batch-write to the vault (frontmatter fields, table rows, Radar entries, canon corrections, a diary line) without reading the target file first. |
| `chronicle.py` | Builds a curated write-up from an already-backed-up chat, instead of retyping the conversation. |
| `backup-cowork.py` | Copies your local Claude/Cowork chat history into the vault, readable and raw. Must run on your own machine. |
| `vault-snapshot.py` | Optional git commit + push of the whole vault, independent of Obsidian being open. |
| `vault.py` | The one command (`python3 vault ...`): six verbs — `find`, `links`, `remember`, `recent`, `check`, `update` — each just runs one of the scripts below. |
| `search.py` | Finds a note by what you mean, ranked, in about a second with no AI. `--semantic` also matches by meaning when Ollama is running locally. |
| `graph.py` | Answers "what connects to what" from the `[[wikilinks]]` between notes — hubs, shortest path, orphans, missing links. Nothing sent anywhere, zero AI cost. |
| `dream.py` | Turns a correction you keep making into a rule: signalled three times it is confirmed in `AIOS/generated/learned-rules.md`; unused rules fade and expire. |
| `session-digest.py` | One line per past Claude Code session for this vault (first request, files edited) in `AIOS/generated/sessions.md`, so a new session can pick up where the last stopped. |
| `mcp-server.py` | Lets another MCP-capable AI app use this vault's search, links, session history and learned rules. Local, no network. |
| `selftest-all.py` | Compiles every script and runs each one's `--selftest` on throwaway data. Exit 1 if anything fails. |
| `tidy.py` | The `tidy` housekeeping list in one report: possible duplicate notes, orphan notes, and the `vault-check` findings. Reports only, changes nothing. |
| `catalog.py` | Rebuilds `AIOS/generated/catalog.md` — everything you watch, read, play or own, plus worlds and purchases, in one greppable file. |
| `shot.py` | Stamps a screenshot: copies it into `AIOS/history/screenshots/`, embeds what it shows inside the image, writes a sidecar note and an index row. |
| `video.py` | Prints a video's real transcript (cached in `AIOS/history/transcripts/`) or fails loudly — an unwatchable video is an error, never a guess from the title. |
| `hook-video.py` | A hook that runs `video.py` on every pasted video link before the model reads your message. `--install-hook` wires it in. |
| `link.py` | Saves every URL you send as its own note in `Atlas/Links/` with the page's real title; `--find`, `--list`, `--check` for dead links. |
| `person.py` | One note per family member, friend or teacher in `Atlas/People/`; creates it on first mention, appends dated facts after. |
| `cooldowns.py` | `--check` / `--upcoming N` on `Calendar/Cooldowns.md` — computes days left and flags what has unlocked. |
| `money.py` | Logs a transaction or sets a real balance in the money note's ledger, and flags drift against what it predicted. |
| `screentime.py` | Logs a day's screen time and sleep; `--avg` for the rolling average, `--check` for a warning only when a threshold is crossed. |
| `accounts-audit.py` | Ages the "needs action" table in the online-accounts note and flags anything unverified for 14+ days. Cannot read your inbox itself. |
| `machine-snapshot.py` | Appends a dated disk/RAM reading to `AIOS/history/machine-snapshots.md`, so "is it still filling up" is a trend. |
| `facts-check.py` | Keeps facts that change with the calendar current — starting with your age in `me.md` — and fixes that spot itself. |
| `weekly-digest.py` | Pulls one week's `## Changes` lines and checkboxes into a digest for the `weekly-review`, instead of opening seven daily notes. |
| `backup-claude-code.py` | Copies Claude Code CLI session transcripts into `AIOS/history/chat-history/claude-code/`. Must run on your own computer. |
| `capture-heartbeat.py` | Flags when chat activity synced but today's `## Changes` got zero entries for 45+ minutes. Mechanical, no reasoning. |
| `blueprint-update.py` | Pulls improvements from the Vault Blueprint into this vault, as a list of yes/no questions. |
| `blueprint-manifest.py`, `blueprint-release.py` | Blueprint-side tooling for regenerating and releasing the blueprint itself — not relevant to a downstream vault. |
| `scriptlog.py` | Shared run-history logger, imported by other scripts — not run directly. Appends to `AIOS/history/scripts/<name>.md` on every run. |

## Where things live

See the folder map in `AIOS/vault-map.md` for the full picture. The short
version: `AIOS/reference/` is opened on demand, `AIOS/generated/` is
machine-written and never hand-edited, `AIOS/config/` is small
machine-readable state, `AIOS/history/` is every kind of automated history.

## If something looks wrong

```
python3 AIOS/scripts/setup-check.py
python3 AIOS/scripts/vault-check.py
```

Neither writes anything. Both tell you what's actually true instead of
assuming.

## Related

- [[vault-map]]
- [[routines]] — the plain-English procedures these scripts back
- [[me]]
