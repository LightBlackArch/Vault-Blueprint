# CLAUDE.md

Go immediately to `AIOS/me.md` and read it. Then read `AIOS/vault-map.md` and
`AIOS/skill-map.md`.

Do this every time without exception at the start of every session.

Confirm in one line that you've read all three, then wait for instructions.

If `AIOS/scripts/session-digest.py` exists, run `python3 AIOS/scripts/session-digest.py context`
too. It lists what recent sessions in this vault were about and which files they
changed, so you can pick up where the last one stopped instead of asking.

**Python is optional.** The scripts are automation, not requirements. If `python3`
isn't found, try `python` (or `py` on Windows). If there is no Python at all, or a
script errors, do not stop: do the same job by hand. Append one line to today's
daily note under `## Changes` instead of running `logchange.py`, write diary,
person and event notes straight into their folders, and search with your own file
tools. Say once that Python would make this automatic, then carry on.

Never read or write anything under `Privat/`.

**If `AIOS/me.md` still contains `<< >>` placeholders, the vault has not been
set up yet.** Say so, and offer to set it up — the trigger is just **"set
yourself up"**, which runs the `setup-vault` skill end to end (scripts,
skills, the interview, and a self-check) without needing anything else typed
first. Working from an unfilled `me.md` means working with no rules at all.

**If you can't confirm the six skills in `AIOS/skills/` are active as real,
natively-triggering skills on this platform** (this is normal on Cowork —
see `AIOS/skills/README.md`), **read `AIOS/skills/auto-capture/SKILL.md`,
`AIOS/skills/vault-first/SKILL.md`, `AIOS/skills/vault-librarian/SKILL.md`
and `AIOS/skills/no-bullshit/SKILL.md` now, in full, and follow them for this
session anyway.** The vault is supposed to behave the same way whether or not
the platform's own skill system is doing the work — these files are the
actual behavior either way.

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

---

That's deliberately the entire file. All real content lives in `AIOS/`, which is
provider-agnostic. If you switch AI providers, you write a new one-line pointer
file (`gemini.md`, `agent.md`, whatever it wants) aimed at the same `AIOS/`
folder — and nothing else changes.
