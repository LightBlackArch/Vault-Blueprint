# Vault Blueprint

*An Obsidian second brain for Claude Code and Claude Cowork: persistent AI memory in plain markdown, free, MIT.*

**An Obsidian vault an AI actually runs — for your whole life, not just your
projects. It remembers, corrects itself when you correct it, and updates
without ever overwriting what you wrote.**

Most "AI memory" setups are two things: a chat window with no files behind
it, or a folder of notes the AI reads but never really maintains. This is
neither. You keep your life in plain markdown. The AI reads it every
session, writes to it without being asked, and when the blueprint itself
gets better, your vault can pull the improvement in — one file at a time,
in plain English, without touching a single word you wrote.

Built and run daily since August 2026. Not a demo, not a template someone
wrote once and moved on from — it's the same system its own maintainer
uses every day, mistakes and fixes included.

---

## What actually makes this different

Plenty of "second brain" templates exist. Almost none of them solve the
part that actually breaks in practice:

- **Updates don't cost you your notes.** Every file the blueprint ships is
  labelled `system` / `seed` / `brain` / `structure` / `setup`. A three-way
  merge compares the blueprint's latest version, your copy, and what you
  last pulled — so "you never touched this, take the new one" and "you
  edited this yourself, ask first" are never confused. Files with *you* in
  them (`me.md`, `vault-map.md`, `skill-map.md`) can never be silently
  overwritten by a script — full stop, not a setting. Every change is
  described in one plain-English sentence before you approve it, and
  everything touched is backed up first, so `undo the last blueprint
  update` is a real command, not a hope.
- **Corrections actually propagate.** Tell it a fact was wrong once, and a
  `canon.md` registry plus a check script make sure that correction reaches
  every note repeating the old version — not just the one you happened to
  have open.
- **It's provider-agnostic on purpose.** One paragraph at the root
  (`CLAUDE.md`) points at everything real, which lives in `AIOS/`. Switch
  AI providers later and you write one new one-line pointer file. Nothing
  else changes.
- **A skill whose whole job is to stop the AI guessing.** `no-bullshit`
  fires before any claim you'd act on — a spec, a price, a recommendation —
  and requires either a search or an honest "unverified," plus a
  case-against before it's allowed to agree with you.
- **It learns, finds, and recalls without an AI bill.** Three plain scripts
  do what memory plugins do with a hidden database: `dream.py` turns
  corrections you repeat into rules whose confidence grows with use and
  fades without it (with snapshot and rollback); `graph.py` answers "what
  connects to what" from your links in under a second; `session-digest.py`
  keeps one readable line per past Claude Code session. Everything stays a
  file you can open.
- **It writes things down without being asked.** `auto-capture` runs every
  session. A fact, a decision, a screenshot's contents — it gets its own
  note, in the right folder, logged, instead of evaporating when the chat
  ends.

None of that is exotic engineering. It's what breaks first when you
actually try to live inside one of these systems for months instead of a
weekend, and this blueprint exists because those breaks already happened
once, for real, and got fixed.


## What works with nothing installed, and what is optional

Everything above needs only Python 3 and a folder. These extras are optional,
and each one falls back cleanly if you skip it:

| Extra | What you get | If you skip it |
|---|---|---|
| `search.py --semantic` | Finds notes by meaning ("automobile" finds "car"). Needs [Ollama](https://ollama.com) running locally. | Normal ranked search still works, and `--semantic` says why it fell back. |
| `graph.py ai "Note"` | Your own `claude` command suggests links nobody wrote. Needs Claude Code logged in. | Every other `graph.py` command is local and free. |
| `mcp-server.py` | Other AI apps can query the vault. Connect with `claude mcp add vault -- python3 "$PWD/AIOS/scripts/mcp-server.py"`. | Nothing else depends on it. |
| `dream.py` | Counts corrections you repeat into rules with confidence and expiry. Run `dream.py signal "<rule>"` when you correct your AI; it does not listen to your chats on its own. | The vault works the same; rules just aren't tracked. |
| `session-digest.py` | One readable line per past Claude Code session. `setup.py` schedules it hourly when Claude Code is present. | Run it by hand when you want it. |

Every script has `--selftest`, so you can check it works on your machine.

---

## Quick start

**You need:** [Obsidian](https://obsidian.md) (free), and something that
can read and write files in a folder — Claude Cowork's folder mode, or
Claude Code. A plain chat window can't touch your files, so it won't work
here.

1. Download this repo (**Code → Download ZIP**), unzip it, rename the
   folder to whatever you want your vault called.
2. Open it in Obsidian (**Open folder as vault**), and point your AI at the
   same folder.
3. Say **"set yourself up."** That's the whole step — it runs the setup
   scripts, activates the skills, interviews you a few questions at a time,
   and shows you a real pass/fail check at the end, not a "trust me."

Full walkthrough, every option, troubleshooting: [`README-START-HERE.md`](README-START-HERE.md).

Once it's running, keeping it current is one line, any time:

> **update my vault from the blueprint**

---

## What's inside

```
CLAUDE.md              One paragraph. The only thing an AI needs to boot.
AIOS/                  Identity, maps, scripts, skills, templates — the system.
  me.md                Who you are. Never touched by an update script.
  skill-map.md          What tooling exists and when it fires.
  scripts/              ~35 small, dependency-free Python scripts.
  skills/               auto-capture, no-bullshit, vault-first, vault-librarian,
                         daily-brief, setup-vault, update-vault.
Atlas/                  Knowledge, reference, media, research — timeless material.
Calendar/               Daily notes, weekly reviews, events, cooldowns.
Efforts/                One note per active project, with a live status table.
Privat/                 Yours. No skill in this repo will ever read or write it.
```

Ships empty — no one's real notes, four fake example notes to show the
shape, and a 50-question setup interview that fills in who *you* are.

---

## License

MIT. Use it, fork it, change it, ship a competing version of it — see
[`LICENSE`](LICENSE).
