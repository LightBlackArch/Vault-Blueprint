---
title: UPDATE-MY-VAULT
tags:
  - index
---

# Give your vault the ability to update itself

**You only ever do this once.** After it, saying *"update my vault from the
blueprint"* works forever, in any session, on its own.

You need this file if you built your vault from a copy of the blueprint that
predates the update system — that is, if there's no `AIOS/scripts/blueprint-update.py`
in your vault. If that file is already there, you don't need this: just say
**"update my vault from the blueprint"** and stop reading.

---

## How to use it

1. Open your vault in **Claude Cowork** or **Claude Code** — something that can
   actually read and write your files. A plain chat window cannot do this.
2. Copy **everything below the line**, paste it as your message, send it.
3. Answer the questions it asks you. That's it.

Nothing below touches a single note you wrote.

---
---

**Set my vault up so it can pull in improvements from the Vault Blueprint.
Here is exactly what I want you to do, in order. Do all of it in this one
conversation, and tell me plainly if any step fails rather than moving on.**

**Step 1 — check where you are.** Confirm you can read and write files in my
vault folder, and that `AIOS/` exists in it. If you can't, stop and tell me —
everything else depends on it.

**Step 2 — install the updater.** Fetch these two files from the blueprint repo
and save them into my vault at the same paths:

```
https://raw.githubusercontent.com/LightBlackArch/Vault-Blueprint/main/AIOS/scripts/blueprint-update.py
https://raw.githubusercontent.com/LightBlackArch/Vault-Blueprint/main/AIOS/scripts/blueprint-manifest.py
```

→ `AIOS/scripts/blueprint-update.py` and `AIOS/scripts/blueprint-manifest.py`

If you can run shell commands, this one line does it:

```bash
mkdir -p AIOS/scripts AIOS/config AIOS/reference && python3 - <<'PY'
import urllib.request, pathlib
base = "https://raw.githubusercontent.com/LightBlackArch/Vault-Blueprint/main/"
for f in ("AIOS/scripts/blueprint-update.py", "AIOS/scripts/blueprint-manifest.py"):
    p = pathlib.Path(f); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(urllib.request.urlopen(base + f).read())
    print("installed", f)
PY
```

If neither works, tell me which of these it was, because they mean different
things:

- **404 / "not found"** — the file isn't in the repo. That's the blueprint's
  problem, not mine and not my vault's. Say so plainly and stop; there is
  nothing to install yet.
- **No network from your shell, or you can't fetch URLs at all** — then I'll
  download the repo as a ZIP myself and point you at the unpacked folder. The
  updater takes `--from /path/to/that/folder` and works entirely offline that
  way.

Don't paper over either one by writing the file from memory. A hand-typed
copy of a script that's supposed to update itself is worse than not having it.

**Step 3 — install the skill.** Fetch this and save it to my vault at the same
path (`AIOS/skills/update-vault/SKILL.md`):

```
https://raw.githubusercontent.com/LightBlackArch/Vault-Blueprint/main/AIOS/skills/update-vault/SKILL.md
```

Then make it actually active for the tool I'm using:

- **Claude Code** — copy the folder to `.claude/skills/update-vault/`. Done, it
  loads itself from now on.
- **Cowork** — you cannot silently create an account skill for me; I have to
  click save. So either package it for me to save, or just tell me honestly
  that you'll read the `SKILL.md` from my vault each time instead. Both work.
  Don't tell me a skill is installed if I haven't clicked anything.

**Step 4 — make it work even with no skill at all.** This is the part that
makes it permanent.

**First check whether my `CLAUDE.md` already contains the words "Updating from
the Vault Blueprint". If it does, skip this whole step** — a newer copy of the
blueprint ships with it already, and adding it twice gives every future session
the same instructions twice.

Otherwise, add this block to my `CLAUDE.md` at the vault root, near the end,
keeping everything already in that file exactly as it is:

```markdown
## Updating from the Vault Blueprint

When I say **"update my vault from the blueprint"** (or anything close —
"check for blueprint updates", "is there anything new in the blueprint"),
follow `AIOS/skills/update-vault/SKILL.md` in full. Short version:

1. `python3 AIOS/scripts/blueprint-update.py --json`
2. Read every waiting change out to me in plain English — what it does for me,
   not which file changed — numbered, and ask which ones I want.
3. Apply the ones I picked with `--apply`. Record the ones I turned down with
   `--decline`, so I'm never asked about them again.
4. `CLAUDE.md`, `AIOS/me.md`, `AIOS/vault-map.md` and `AIOS/skill-map.md` are
   half mine — never let the script write those. Merge the structural change
   into them by hand and keep every word I wrote.

Never apply anything without asking. Never touch `Privat/`. Never delete a
file because the blueprint stopped shipping it.
```

**Step 5 — first run, but don't change anything yet.** Run:

```bash
python3 AIOS/scripts/blueprint-update.py
```

Show me the list it prints. Explain each item to me in plain English — what
it actually does for me, not which file it edits — and tell me which ones are
safe swaps versus which ones need a decision from me.

**Then wait.** Don't apply anything until I've said which ones I want. The
first run will probably list a lot, because my vault has never been updated
before, and that's normal.

**Step 6 — tell me the truth about what happened.** A short list: what got
installed, what didn't, and anything that failed. If step 2 or 3 didn't
actually work, say so — I'd much rather know now than find out the next time I
ask for an update.

---
---

## What it does after that

Any time, in any session:

| Say this | What happens |
|---|---|
| *"update my vault from the blueprint"* | Fetches the latest, lists what's new in plain English, asks what you want |
| *"what blueprint updates am I ignoring?"* | Shows everything you've said no to |
| *"undo the last blueprint update"* | Puts back every file that update touched |

Or straight from a terminal, no AI involved:

```bash
python3 AIOS/scripts/blueprint-update.py --interactive
```

## What it will never do

- Read or write anything in `Privat/`. Hard-coded, not a setting.
- Touch your notes in `Atlas/`, `Efforts/`, `Calendar/` or `Inbox/`.
- Overwrite `AIOS/me.md` — the file that has *you* in it. A script is not
  allowed to write that file at all.
- Delete anything, ever. If the blueprint drops a file, yours stays.
- Change one single thing you didn't say yes to.

Every file it does change gets copied into
`AIOS/history/blueprint-updates/<date>/` before it's touched. That's what makes
the undo real rather than a promise.
