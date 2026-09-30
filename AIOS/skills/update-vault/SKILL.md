---
name: update-vault
description: "Pull improvements from the Vault Blueprint into this vault, without touching anything the user wrote. Use when they say \"update my vault\", \"update my vault from the blueprint\", \"check for blueprint updates\", \"is there anything new in the blueprint\", \"sync with the blueprint\", or \"undo the last blueprint update\". Also use when a daily brief or a scheduled check reported that blueprint updates are waiting and they say yes. Never runs on its own — the fetching can be automatic, applying anything never is."
---

# update-vault

Fetch the latest Vault Blueprint, work out what's genuinely different from
**this** vault, present it as plain-English choices, and apply only what the
user picks.

> [!danger] The one thing that must never happen
> **This must never overwrite something the user wrote.** Not a note, not a
> line in `me.md`, not their own edit to a script. Everything else about this
> skill is negotiable; that isn't. If you are ever unsure whether a file is
> theirs, treat it as theirs and ask.

> [!important] Take the slow path. Every time.
> This skill is allowed to be expensive. Reading three files carefully, working
> out what a change is *for*, and hand-writing the result into somebody's
> customised vault is the correct amount of effort — not a fallback for when
> something goes wrong.
>
> **A choice offered to the user is usually a merge you didn't do.** "Keep
> yours or take the blueprint's?" is the lazy version of "I read both and
> combined them." Only ask when the two genuinely conflict in intent — when
> the blueprint wants X and they have deliberately chosen not-X. A blueprint
> change and a user edit that touch different parts of the same file are not
> a conflict; they're two things that both belong in the file, and doing that
> work is the job.
>
> Same for a change that implies work beyond copying a file. If a new folder
> needs an index note, a map row and a script that reads it, **do all of it**.
> "Applied the file, you may want to update your map" is not applying the
> change, it's describing it.

## Before anything else

The script does the hard part. Do not diff files yourself, do not read the
whole blueprint into context, and do not decide what's changed by eye.

```bash
python3 AIOS/scripts/blueprint-update.py --json
```

That returns every waiting change as structured data: a number, a kind, a
plain-English title and detail, the files it touches, whether a script may
write it, and a diff where one is relevant. Work from that.

If the script isn't there yet, this vault predates the update system — see
§6.

## 1. Read the plan out loud

Present each item as a **question the person can answer**, not a file path.
Number them the way the script did, so `--apply 3` means what they think.

Good:

> **3. Screenshots get their own folder** — right now a picture you send lands
> in `Inbox/` with everything else. This gives them their own home, writes a
> short note next to each one saying what it showed, and keeps an index. Adds
> one folder and updates one script.

Bad — never do this:

> 3. `AIOS/scripts/shot.py` modified (+42 −11)

Rules for this list:

- **Lead with what changes for them.** The file paths go last, small, or in a
  fold. They are evidence, not the message.
- **Explain any word they haven't met**, in the same breath, one sentence.
  Someone who downloaded this blueprint may never have written a line of code.
- **Group by what it does**, not by file. The script already groups anything
  described in `AIOS/reference/blueprint-changes.md`; keep that grouping.
- **Say plainly which ones are safe.** Items with `"manual": false` are clean
  swaps of files they never touched. Items with `"manual": true` need a
  judgement call — say so and say why.
- **Flag `changed_since_decline`.** Those read: *"You said no to this before,
  but it's different now — worth another look?"* Say it exactly that plainly.
  Don't sneak a declined item back in without naming that it was declined.
- If the list is long, offer the obvious shortcut: *"1, 2 and 5 are safe
  no-brainers — want me to just do those and go through the rest with you?"*

Then ask which ones they want. Accept "all", "none", "just the safe ones",
numbers, or a description ("the screenshot one").

## 2. Apply the straightforward ones

```bash
python3 AIOS/scripts/blueprint-update.py --apply file:AIOS/scripts/logchange.py,screenshots-folder
```

> [!warning] Use the `id`, not the number
> The numbers are positions in one printed list. Apply something and the list
> gets shorter, so `3` now means what `4` meant a second ago. Every proposal
> also carries a stable `id` — `--apply` and `--decline` both take those, and
> they can't drift. Numbers are for reading to the user; ids are for acting.

The script backs up every file it overwrites before overwriting it, records
what it applied, and updates the state file so next time it still knows which
version they're on. Report what it printed. Don't paraphrase a success it
didn't report.

## 2.5. Conflicts: merge both sides, don't make them choose

A `conflict` or `unknown` item means they edited a shipped file and the
blueprint changed it too. **The default is not a question — it's a merge.**

1. Read all three: their file, the blueprint's file, and the `diff` in the JSON.
2. Work out what each side was *for*. Their edit usually has a reason sitting
   right there in it — a raised timeout, an extra path, a commented-out line
   with their name on it. The blueprint's change has a reason in
   `blueprint-changes.md`.
3. **Write a version that has both.** Take the blueprint's file as the base,
   re-apply their edit on top, and keep their comment explaining why it's
   there. Then say in one line what you did and what you kept.
4. Only ask them if the two genuinely contradict — the blueprint deletes the
   thing they customised, or changes the behaviour they deliberately changed
   back. Then show both, explain the trade-off, and let them call it.

Once merged, record it so it stops being offered:

```bash
python3 AIOS/scripts/blueprint-update.py --apply <id> --force-manual
```

For a `system` file that flag *does* write the file, so merge into their copy
**first**, then run it only to update the record — or simpler, write your
merged version to the file yourself and then run it to re-stamp the hash.

> [!warning] `unknown` means you don't know, so don't guess
> `unknown` is "your copy differs and there's no record of which version you
> started from". That's often just an older blueprint, not an edit. Read the
> diff before assuming they customised anything — a "merge" that preserves a
> difference that was never theirs is how stale code becomes permanent.

## 3. Merge the brain files by hand — never with the script

`CLAUDE.md`, `AIOS/me.md`, `AIOS/vault-map.md`, `AIOS/skill-map.md` and
`AIOS/how-to-use-this.md` are **half theirs**. The blueprint's version of
`vault-map.md` describes folders; theirs describes folders *plus* every note
they've filed and every convention they invented. Replacing it would be
vandalism.

So for anything the script marked `"manual": true` on one of those files:

1. Read the `diff` field in the JSON. Work out what **structural** thing
   changed — a new folder, a new convention, a new rule, a new row in a table.
2. Tell them that one thing in a sentence, and ask.
3. If yes: `Edit` their file to add *just that*. Match their file's existing
   shape and wording. Preserve every personal line, every note name, every
   rule of their own. You are inserting a paragraph, not swapping a file.
4. If the change implies real work elsewhere — a new folder needs creating, a
   new index note needs writing, a script needs a row in a table — **do that
   too, in the same turn.** The point is that the change actually works
   afterwards, not that a line got added to a map.

   Concretely, "the blueprint added `Atlas/Worlds/`" is not one edit, it's
   five: create the folder, write its index note in the style of their other
   index notes, add the row to *their* `vault-map.md` phrased the way they
   phrase rows, add the status vocabulary to the conventions table, and add
   the tag to their tag scheme. Ship it working or don't ship it.

5. **Then check it actually works.** If the change added a script, run it. If
   it added a folder a script reads, run that script. If it changed a rule in
   `vault-map.md`, run `vault-check.py` to confirm nothing now contradicts it.
   Report what you ran, not what you intended.

Then record that they took it, so it stops being offered:

```bash
python3 AIOS/scripts/blueprint-update.py --apply <id> --force-manual
```

Only ever pass `--force-manual` **after** you have merged by hand, or when the
file genuinely doesn't exist in their vault yet. It is not a shortcut past step
3.

## 4. Record the noes

Anything they turned down:

```bash
python3 AIOS/scripts/blueprint-update.py --decline 4,6
```

This is not cosmetic. A declined item is never offered again unless the
blueprint changes that specific thing later. Without this they get asked the
same question every month and stop running updates.

They can see what they've said no to any time:

```bash
python3 AIOS/scripts/blueprint-update.py --show-declined
```

## 5. Close honestly

Say what was applied, what was skipped, what was declined, and where the backup
went. If something failed, say it failed — a wrong "done" here costs them their
trust in every future update.

Offer the undo in one line, because it's real:

```bash
python3 AIOS/scripts/blueprint-update.py --undo
```

Suggest a `vault-check` afterwards if scripts or skills changed, and mention
that changed skills need re-copying into `.claude/skills/` on Claude Code, or
re-saving on Cowork — the vault copy changing doesn't flip the live one.

## 6. If the updater isn't installed yet

Vaults built from an older blueprint have no `blueprint-update.py`. Install it,
then carry on from §1:

```bash
mkdir -p AIOS/scripts AIOS/config AIOS/reference
python3 - <<'PY'
import urllib.request, pathlib
base = "https://raw.githubusercontent.com/LightBlackArch/Vault-Blueprint/main/"
for f in ("AIOS/scripts/blueprint-update.py",
          "AIOS/scripts/blueprint-manifest.py"):
    p = pathlib.Path(f); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(urllib.request.urlopen(base + f).read())
    print("installed", f)
PY
```

If the machine has no network access from the shell, ask them to open
`UPDATE-MY-VAULT.md` in the blueprint repo and follow it — it's written for
exactly this case.

## 7. Scheduled checking

`--check` prints one line and exits non-zero when anything is waiting. It's
safe to run on a timer because it only ever reads:

```bash
python3 AIOS/scripts/blueprint-update.py --check
```

If a daily brief runs in this vault, that line belongs in it. Never apply
anything from a scheduled run.

## What this skill must never do

- **Never** write inside `Privat/`. Not to read it, not to check it, not once.
- **Never** delete a file because the blueprint stopped shipping it. Report it,
  leave it. Deleting someone's file to match a template is indefensible.
- **Never** overwrite a note in `Atlas/`, `Efforts/`, `Calendar/` or `Inbox/`.
  Those are theirs entirely. The updater's manifest already refuses, but the
  refusal should live in two places.
- **Never** claim something was applied before the script said it was.
- **Never** apply anything on a schedule, or as a side effect of another task.
