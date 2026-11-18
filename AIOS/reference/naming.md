---
title: naming
tags:
  - reference
---

# naming.md — one subject, one name, one note

> [!important] Opened on demand, never boot-loaded
> `route-check.py` enforces this; this file is what it enforces against and
> the place to record a deliberate exception. Read before creating a note
> whose subject might already exist.

## Before creating any note — one command

```bash
python3 AIOS/scripts/route-check.py --exists "the subject, in your own words"
```

Exits 1 and shows you the existing note if one probably already covers it.
Exits 0 either with close matches to check first, or a clean "safe to
create it". This is what `vault-first` and `vault-librarian` run before
staging a new note — not a suggestion, the actual check.

## The scheme, per folder

| Folder | Convention |
|---|---|
| `Efforts/` | Subject only, Title Case: `Bike Purchase.md`, never `Buying a bike.md` |
| `Atlas/Media/` | The actual title, exactly as published: `The Left Hand of Darkness.md` |
| `Atlas/Worlds/` | The world/save/server's own name |
| `Atlas/Knowledge/` | The concept, sentence case: `Systemd units.md` |
| `Calendar/Events/YYYY/` | The event's own title — created by `event.py`, never by hand |
| Index notes | Named after their folder: `Atlas/Atlas.md`, `Efforts/Efforts.md` |

## Naming the aspect, when a subject really does need two notes

Two notes about the same subject are usually one note that should have been
edited instead of duplicated — `route-check.py --dupes` finds these. But
occasionally two things really are different and just share a name family:
a franchise and a specific entry in it, a general topic and one deep-dive
inside it. When that's genuinely true, name each note after the *aspect*
that makes it different, not after a synonym for the same aspect:

- **Right:** `Some Show.md` (the whole series) and `Some Show Theory.md` (a
  specific fan theory) — different aspects, same subject, both findable.
- **Wrong:** `Bike Purchase.md` and `Buying a bike.md` — same aspect, same
  subject, two names for no reason. `route-check.py` folds these together
  automatically by stripping the verb and comparing what's left.

## Confirmed distinct

Pairs that look like a naming collision to `route-check.py --dupes` but
really are two different things. Add a row here instead of just ignoring the
warning — a check that cries wolf forever is a check nobody reads.

**Format:** two backticked `.md` paths on one row — that is all the check
reads, so the reason column is for humans. Each pair needs its own row;
a wildcard row is readable by you but never silences the check.

| Note A | Note B | Why they're different |
|---|---|---|
| _(none yet)_ | | |

## Related

- [[vault-map]] — the folder map this scheme lives inside
- [[vault-conventions]] — tags, status vocabulary, daily-note anatomy
- [[me]]
