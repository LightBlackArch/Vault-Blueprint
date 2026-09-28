#!/usr/bin/env python3
"""
route-check.py — make every note findable in one grep, and shout when one isn't.

Why this exists
---------------
A project note can exist, be correct, and be complete, and still cost several
minutes and a wall of tool calls to find again — if `AIOS/vault-map.md`
doesn't contain the word someone would actually type. That's the second of
two failure modes this vault design cares about:

    "A right fact written down, then NOT inherited — the fix exists in a note
    nothing reads."

`AIOS/me.md` already carries the rule: *"update `vault-map.md` so the next
session can find it too."* A session that creates a note can just forget to.
A rule that fires only when someone remembers it is not a mechanism.

So: two mechanisms, one cheap, one loud.

1. `AIOS/generated/where.md` — GENERATED. One line per note: its path, its
   title, and the words that actually distinguish it from every other note.
   A session that doesn't know where something lives greps ONE file instead
   of ripgrepping the whole vault:

       grep -i gravel AIOS/generated/where.md

   Deliberately NOT in the boot set — it costs nothing until it's needed,
   the opposite of routing rows in `vault-map.md`, which load in every
   session forever, so only genuinely hot routes belong there.

2. `--check` — fails when a note in `Efforts/` has no route in `vault-map.md`.
   Projects are what you ask about by name mid-decision, so those earn a
   place in the boot file. Everything else rides on where.md.

How the trigger words are picked
--------------------------------
TF-IDF-lite, stdlib only. A word earns a place if it is frequent inside its
own note and rare across the vault. Filename words, `title:` and `aliases:`
are always included regardless of rarity, because those are what a person
types first.

This is an index, not a summary. It answers "which file", never "what does it
say" — the note is still the content.

Usage
-----
    python3 AIOS/scripts/route-check.py            # rebuild AIOS/generated/where.md
    python3 AIOS/scripts/route-check.py --check    # report only, changes nothing
    python3 AIOS/scripts/route-check.py --find gravel bike   # query the index
    python3 AIOS/scripts/route-check.py --exists "bike budgeting"  # before creating
    python3 AIOS/scripts/route-check.py --dupes    # one subject, two notes
    python3 AIOS/scripts/route-check.py --naming   # filenames breaking the scheme

Exit codes: 0 fine · 1 an Efforts/ note has no route (--check only) · 2 couldn't run.

No dependencies. Plain stdlib.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import re
import sys
from collections import Counter
from pathlib import Path

VAULT = Path(__file__).resolve().parent.parent.parent
WHERE = VAULT / "AIOS" / "generated" / "where.md"
MAP = VAULT / "AIOS" / "vault-map.md"
# Not a vault note — a scratch cache of parsed word-counts, keyed by each
# note's mtime and size, so a rebuild only re-reads notes that actually
# changed. Never indexed itself, never committed (see .gitignore), safe to
# delete: worst case is one slow rebuild that repopulates it.
CACHE = VAULT / "AIOS" / "scripts" / ".route-cache.json"

# Matches vault-map.py / vault-check.py. If you change it here, change it there.
SKIP_PARTS = {"Privat", ".git", ".obsidian", ".trash", ".claude", "__pycache__"}
SKIP_PREFIXES = ("AIOS/history/chat-history/cowork/",
                  "AIOS/history/chat-history/cowork-raw/",
                  "AIOS/skills/", "AIOS/history/scripts/")

# Folders whose notes must have a hand-written route in vault-map.md.
# Only Efforts/ — projects are asked about by name. Everything else rides on
# where.md, so the boot file stays small.
MUST_ROUTE = ("Efforts/",)
# Generated or structural notes inside those folders that need no route.
MUST_ROUTE_EXEMPT = {"Efforts/Efforts.md", "Efforts/Next Actions.md"}

STOPWORDS = set("""
a about above after again against all also am an and any are aren as at be
because been before being below between both but by can cant cannot could
couldnt did didnt do does doesnt doing dont down during each few for from
further had hadnt has hasnt have havent having he hed hes her here heres hers
herself him himself his how hows i id ill im ive if in into is isnt it its
itself lets me more most mustnt my myself no nor not of off on once only or
other ought our ours ourselves out over own same shant she shed shes should
shouldnt so some such than that thats the their theirs them themselves then
there theres these they theyd theyll theyre theyve this those through to too
under until up very was wasnt we wed were weve werent what whats when whens
where wheres which while who whos whom why whys with wont would wouldnt you
youd youll youre youve your yours yourself yourselves
just get got go going make made makes new now one two three still even much
many way ways thing things something anything nothing lot lots need needs
needed use uses used using want wants wanted like likes really actually
note notes vault file files folder md yes real see says said say tags title
status related date added run runs added change changes changed fix fixed
work works working good bad best better first last next time times day days
""".split())

WORD_RE = re.compile(r"[a-zA-Z][\w\-]{2,}")
TERMS_PER_NOTE = 14


def rel(p: Path) -> str:
    return p.relative_to(VAULT).as_posix()


def is_skipped(p: Path) -> bool:
    r = rel(p)
    if any(part in SKIP_PARTS for part in p.relative_to(VAULT).parts):
        return True
    return any(r.startswith(pre) for pre in SKIP_PREFIXES)


def all_notes() -> list[Path]:
    out = []
    for dirpath, dirnames, filenames in os.walk(VAULT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_PARTS]
        for fn in filenames:
            if not fn.endswith(".md"):
                continue
            p = Path(dirpath) / fn
            if not is_skipped(p):
                out.append(p)
    return sorted(out, key=rel)


def split_front(text: str) -> tuple[dict, str]:
    """Return (frontmatter-ish dict, body). Deliberately shallow — no yaml dep."""
    fm: dict = {}
    body = text
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        if end != -1:
            raw = text[4:end]
            body = text[end + 4:]
            key = None
            for line in raw.splitlines():
                if re.match(r"^\s*-\s+", line) and key:
                    fm.setdefault(key + "_list", []).append(
                        re.sub(r"^\s*-\s+", "", line).strip())
                elif ":" in line:
                    key, _, val = line.partition(":")
                    key = key.strip()
                    fm[key] = val.strip()
    return fm, body


def words(text: str) -> list[str]:
    return [w.lower() for w in WORD_RE.findall(text)]


def always_terms(p: Path, fm: dict) -> list[str]:
    """Words a person would actually type first: the name and its aliases."""
    seed = [p.stem]
    if fm.get("title"):
        seed.append(fm["title"])
    for a in fm.get("aliases_list", []) or []:
        seed.append(a.strip("\"'[] "))
    if fm.get("aliases"):
        seed.append(fm["aliases"].strip("[]\"' "))
    out: list[str] = []
    for s in seed:
        for w in words(s):
            if w not in out and w not in STOPWORDS:
                out.append(w)
    return out


def load_cache() -> dict:
    try:
        return json.loads(CACHE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_cache(cache: dict) -> None:
    try:
        CACHE.write_text(json.dumps(cache), encoding="utf-8")
    except OSError:
        pass


def build_index(notes: list[Path]) -> list[tuple[str, str, list[str], int]]:
    """(path, title, terms, size) — terms ranked frequent-here, rare-elsewhere."""
    cache = load_cache()
    live = set()
    parsed = []
    doc_freq: Counter[str] = Counter()
    reused = 0
    for p in notes:
        r = rel(p)
        live.add(r)
        try:
            st = p.stat()
        except OSError:
            continue
        hit = cache.get(r)
        if hit and hit.get("mtime") == st.st_mtime and hit.get("size") == st.st_size:
            fm, tf = hit["fm"], Counter(hit["tf"])
            reused += 1
        else:
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            fm, body = split_front(text)
            ws = [w for w in words(body) if w not in STOPWORDS and not w.isdigit()]
            tf = Counter(ws)
            cache[r] = {"mtime": st.st_mtime, "size": st.st_size,
                        "fm": fm, "tf": dict(tf)}
        parsed.append((p, fm, tf, cache[r]["size"]))
        doc_freq.update(set(tf))

    for k in list(cache):
        if k not in live:
            del cache[k]
    save_cache(cache)
    if parsed:
        print(f"route-check: {reused}/{len(parsed)} notes unchanged since last "
              f"rebuild, skipped re-reading them")

    n = max(len(parsed), 1)
    rows = []
    for p, fm, tf, size in parsed:
        pinned = always_terms(p, fm)
        scored = []
        for w, c in tf.items():
            if w in pinned:
                continue
            df = doc_freq.get(w, 1)
            if df > n * 0.25:
                continue
            scored.append((c * math.log(n / df), w))
        scored.sort(reverse=True)
        extra = [w for _, w in scored[:TERMS_PER_NOTE]]
        title = fm.get("title") or p.stem
        rows.append((rel(p), title, pinned + extra, size))
    return rows


def unrouted(notes: list[Path]) -> list[str]:
    """Notes in MUST_ROUTE folders that vault-map.md never names."""
    try:
        map_text = MAP.read_text(encoding="utf-8", errors="replace").lower()
    except OSError:
        return []
    out = []
    for p in notes:
        r = rel(p)
        if not r.startswith(MUST_ROUTE) or r in MUST_ROUTE_EXEMPT:
            continue
        # The fake EXAMPLE notes are there to be read once and deleted; a
        # route row for one would send the next session to a note that's gone.
        if p.name.startswith("EXAMPLE "):
            continue
        if p.stem.lower() not in map_text:
            out.append(r)
    return out


def render(rows: list[tuple[str, str, list[str], int]], missing: list[str]) -> str:
    today = dt.date.today().isoformat()
    head = f"""---
title: where
tags:
  - index
  - generated
confirmed: {today}
---

# where.md — one line per note, so finding something is one grep

> [!warning] Generated — do not edit by hand
> Rebuilt by `python3 AIOS/scripts/route-check.py`, which `logchange.py` runs
> automatically whenever a note is created or deleted. Anything typed in here is
> gone on the next write.

**This file is not read at session start and must never be added to the boot
set.** It exists to be *searched*, not loaded:

```bash
grep -i gravel  AIOS/generated/where.md      # -> a project note about a bike
python3 AIOS/scripts/route-check.py --find "some words"
```

Terms are picked by how often a word appears in its own note versus how rare it
is across the vault, so they are the words that actually *distinguish* one note
from the other {len(rows) - 1}. The note is still the content — this only ever
answers **which file**.

**{len(rows)} notes**, indexed {today}.

| Note | Find it by |
|---|---|
"""
    body = []
    for path, title, terms, _ in rows:
        stem = Path(path).stem
        t = ", ".join(dict.fromkeys(terms))[:220]
        # Plain [[stem]] always resolves and never needs escaping. A `|` alias
        # would need `\|` to survive as a table cell, but Obsidian doesn't
        # treat a backslash-escaped pipe as the alias separator inside
        # [[ ]] — it rendered literally, and broke vault-check.py's wikilink
        # parser too. Show the real title alongside instead, only when it
        # actually differs from the filename.
        link = f"[[{stem}]]" if stem == title else f"[[{stem}]] ({title})"
        body.append(f"| {link} · `{path}` | {t} |")

    tail = "\n\n## Notes in `Efforts/` with no route in vault-map.md\n\n"
    if missing:
        tail += ("These are projects a session can only find by full-text search.\n"
                 "Add a row to the \"Where to look for what\" table in "
                 "`AIOS/vault-map.md` for each:\n\n")
        tail += "\n".join(f"- `{m}`" for m in missing) + "\n"
    else:
        tail += "None — every project note has a route.\n"

    tail += "\n## Related\n\n- [[vault-map]] — the hand-written routing table\n- [[me]]\n"
    return head + "\n".join(body) + tail


# ---------------------------------------------------------------------------
# Naming collisions — "does a note for this already exist?"
# ---------------------------------------------------------------------------
# An index only helps if the thing you want is filed under a name you'd think
# to type. Three names, one subject, three notes — and where.md dutifully
# indexes all three. The index cannot fix that; only refusing to create the
# second one can.
#
# The trick is to strip the VERB out of a note name and keep the SUBJECT.
# "Bike Purchase", "Buying a bike" and "Bike budgeting" all reduce to
# {bike, buy}. "Laptop Purchase" reduces to {laptop, buy}, which must NOT
# collide with the bike — so a collision requires a shared *subject* word,
# never merely a shared verb. That one rule is what stops this being noise.

NAMING = VAULT / "AIOS" / "reference" / "naming.md"

ASPECT_GROUPS = {
    "buy": "buy buys buying bought purchase purchases purchasing purchased "
           "order orders ordering budget budgets budgeting cost costs price "
           "prices pricing shop shopping",
    "install": "install installs installing installed installation setup "
               "set-up configure configures configuring config configuration "
               "provision provisioning deploy deploying",
    "fix": "fix fixes fixing fixed repair repairs repairing broken issue "
           "issues problem problems troubleshoot troubleshooting slowdown "
           "debug debugging error errors",
    "learn": "learn learns learning learned guide guides tutorial tutorials "
             "howto basics intro introduction cheatsheet",
    "build": "build builds building built create creates creating",
    "upgrade": "upgrade upgrades upgrading upgraded update updates updating "
               "migrate migrating migration",
    "backup": "backup backups sync syncs syncing synced snapshot snapshots",
}
ASPECT = {w: c for c, ws in ASPECT_GROUPS.items() for w in ws.split()}
ASPECTS = set(ASPECT_GROUPS)

NAME_NOISE = {"my", "the", "a", "an", "for", "on", "in", "of", "and", "to",
              "with", "from", "at"}

ROOT_OK = {"Home.md", "CLAUDE.md", "AGENTS.md", "Random.md", "README.md"}
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
WEEK_RE = re.compile(r"^\d{4}-W\d{2}$")
PLACEHOLDER = ("pasted image", "untitled", "new note", "document")

# Folder trees where every folder is expected to carry an index note named
# after itself. Deliberately not AIOS/ — that folder is flat by design.
INDEXED_TREES = ("Atlas/", "Efforts/", "Calendar/", "Inbox/")


def stem(w: str) -> str:
    """Crude on purpose: enough to fold plurals and -ing, nothing more."""
    for suf, repl in (("ies", "y"), ("ing", ""), ("es", ""), ("ed", ""), ("s", "")):
        if w.endswith(suf) and len(w) - len(suf) >= 4:
            return w[: -len(suf)] + repl
    return w


def canon_tokens(name: str) -> tuple[set[str], set[str]]:
    """(all tokens, subject-only tokens) for a note name or a proposed name."""
    toks: set[str] = set()
    subj: set[str] = set()
    for w in words(name):
        if w in NAME_NOISE or w in STOPWORDS:
            continue
        c = ASPECT.get(w) or stem(w)
        toks.add(c)
        if c not in ASPECTS:
            subj.add(c)
    return toks, subj


def allowed_pairs() -> set[frozenset]:
    """Pairs a human has confirmed are genuinely different things.

    Read from the table in AIOS/reference/naming.md. Without this the check
    cries wolf on any two similarly-named-but-different subjects and gets
    ignored, which is worse than not having it.
    """
    out: set[frozenset] = set()
    try:
        text = NAMING.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return out
    for line in text.splitlines():
        found = re.findall(r"`([^`]+\.md)`", line)
        if len(found) >= 2:
            out.add(frozenset(found[:2]))
    return out


def name_hits(query: str, rows: list, exclude: str | None = None) -> list:
    """Existing notes that look like they already cover `query`, best first."""
    qt, qs = canon_tokens(query)
    if not qs:
        return []
    hits = []
    for path, title, terms, _ in rows:
        if exclude and path == exclude:
            continue
        nt, ns = canon_tokens(Path(path).stem)
        t2, s2 = canon_tokens(title)
        nt |= t2
        ns |= s2
        shared = qs & ns
        if not shared:
            continue
        j = len(qt & nt) / max(len(qt | nt), 1)
        term_hit = len({stem(t) for t in terms} & qs)
        hits.append((round(j + 0.08 * term_hit, 3), round(j, 3), path, title,
                     sorted(shared)))
    hits.sort(reverse=True)
    return hits


def cmd_exists(query: str, rows: list, exclude: str | None = None) -> int:
    """Before creating a note: is this already covered? Exit 1 if probably yes."""
    _, qs = canon_tokens(query)
    hits = name_hits(query, rows, exclude=exclude)
    strong = [h for h in hits if h[1] >= 0.5]
    weak = [h for h in hits if h[1] < 0.5][:5]

    if strong:
        print(f'route-check: "{query}" looks like it ALREADY EXISTS.')
        for _, j, path, title, shared in strong[:5]:
            print(f"  {j:>5}  {path}   — {title}   (same subject: "
                  f"{', '.join(shared)})")
        print("\nAdd to that note. Do not create a second one. If it really is "
              "a different thing, say so in AIOS/reference/naming.md so this stops "
              "asking.")
        return 1

    seen = {h[2] for h in hits}
    by_content = []
    for path, title, terms, _ in rows:
        if path in seen or path == exclude:
            continue
        hit = {stem(t) for t in terms} & qs
        if hit:
            by_content.append((len(hit), path, title, sorted(hit)))
    by_content.sort(reverse=True)

    if weak or by_content:
        print(f'route-check: no note is NAMED after "{query}". These already '
              f"talk about it — read before creating anything:")
        for _, j, path, title, shared in weak:
            print(f"  name   {path}   — {title}   (shares: {', '.join(shared)})")
        for n, path, title, shared in by_content[:5]:
            print(f"  inside {path}   — {title}   (mentions: {', '.join(shared)})")
        return 0

    print(f'route-check: nothing covers "{query}" — safe to create it.')
    return 0


def cmd_dupes(rows: list, threshold: float = 0.6) -> int:
    """Notes that already collided: same subject, two different names."""
    allow = allowed_pairs()
    skip = ("Calendar/Daily/", "Calendar/Weekly/")
    items = []
    for path, title, terms, _ in rows:
        if path.startswith(skip):
            continue
        t, s = canon_tokens(Path(path).stem)
        if s:
            items.append((path, title, t, s))

    pairs = []
    for i in range(len(items)):
        pa, ta, tka, sa = items[i]
        for k in range(i + 1, len(items)):
            pb, tb, tkb, sb = items[k]
            shared = sa & sb
            if not shared:
                continue
            j = len(tka & tkb) / max(len(tka | tkb), 1)
            if j < threshold or frozenset((pa, pb)) in allow:
                continue
            pairs.append((round(j, 3), pa, pb, sorted(shared)))

    pairs.sort(reverse=True)
    if not pairs:
        print("route-check: no name collisions — every subject has one note.")
        return 0
    print(f"route-check: {len(pairs)} possible name collision(s). Same subject, "
          f"two names — the next session will find one and miss the other.\n")
    for j, pa, pb, shared in pairs:
        print(f"  {j:>5}  {pa}\n         {pb}\n         same subject: "
              f"{', '.join(shared)}\n")
    print("Merge, or add the pair to the \"Confirmed distinct\" table in "
          "AIOS/reference/naming.md with one line saying why.")
    return 1


def cmd_naming(notes: list) -> int:
    """Filenames that break the convention, so the name stays the index."""
    problems: list[tuple[str, str]] = []
    folders: dict[str, list[str]] = {}

    for p in notes:
        r = rel(p)
        s = p.stem
        parent = str(Path(r).parent)
        folders.setdefault(parent, []).append(s)

        if "/" not in r and r not in ROOT_OK:
            problems.append((r, "sits at the vault root — the root is only for "
                                + ", ".join(sorted(ROOT_OK))))
        if s != s.strip() or "  " in s:
            problems.append((r, "stray or doubled space in the filename"))
        if s.lower().startswith(PLACEHOLDER):
            problems.append((r, "placeholder name — nobody will ever grep for "
                                "this; rename it after its subject"))
        if r.startswith("Calendar/Daily/") and s != "Daily":
            if not DATE_RE.match(s):
                problems.append((r, "Calendar/Daily/ is YYYY-MM-DD.md only"))
        if r.startswith("Calendar/Events/") and s != "Events":
            parts = r.split("/")
            if len(parts) != 4 or not parts[2].isdigit() or len(parts[2]) != 4:
                problems.append((r, "event note belongs in "
                                    "Calendar/Events/YYYY/<Title>.md — create it "
                                    "with AIOS/scripts/event.py, never by hand"))
        if r.startswith("Calendar/Weekly/") and s != "Weekly":
            if not WEEK_RE.match(s):
                problems.append((r, "Calendar/Weekly/ is YYYY-Wnn.md only"))

    for folder, stems in sorted(folders.items()):
        if folder in (".", "") or not folder.startswith(INDEXED_TREES):
            continue
        if re.fullmatch(r"Calendar/(Daily|Weekly|Events)(/\d{4})?", folder):
            continue
        want = Path(folder).name
        if want not in stems:
            problems.append((folder + "/", f"no index note — this folder should "
                                           f"contain {want}.md"))

    if not problems:
        print("route-check: every filename follows the naming scheme.")
        return 0
    print(f"route-check: {len(problems)} naming problem(s) — see AIOS/reference/naming.md "
          f"for the scheme.\n")
    for where, why in sorted(problems):
        print(f"  {where}\n      {why}\n")
    return 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true",
                    help="report unrouted notes and index staleness, change nothing")
    ap.add_argument("--find", nargs="+", metavar="TERM",
                    help="query the index for notes matching these terms")
    ap.add_argument("--exists", metavar="NAME",
                    help="before creating a note: does one already cover this? "
                         "exits 1 if it probably does")
    ap.add_argument("--exclude", metavar="PATH", default=None,
                    help="with --exists: ignore this note (it is the one being "
                         "created, and it always matches itself)")
    ap.add_argument("--dupes", action="store_true",
                    help="notes that already collided — one subject, two names")
    ap.add_argument("--naming", action="store_true",
                    help="filenames that break the scheme in AIOS/reference/naming.md")
    args = ap.parse_args()

    if not VAULT.exists():
        print(f"route-check: no vault at {VAULT}", file=sys.stderr)
        return 2

    notes = all_notes()
    if not notes:
        print("route-check: found no notes — refusing to write an empty index",
              file=sys.stderr)
        return 2

    rows = build_index(notes)
    missing = unrouted(notes)

    if args.exists:
        return cmd_exists(args.exists, rows, exclude=args.exclude)

    if args.dupes:
        return cmd_dupes(rows)

    if args.naming:
        return cmd_naming(notes)

    if args.find:
        needles = [t.lower() for t in args.find]
        hits = []
        for path, title, terms, _ in rows:
            hay = (path + " " + title + " " + " ".join(terms)).lower()
            score = sum(1 for t in needles if t in hay)
            if score:
                hits.append((score, path, title))
        hits.sort(reverse=True)
        if not hits:
            print("route-check: nothing matched. That is a real gap — the note "
                  "may exist under words nobody would type.")
            return 0
        for score, path, title in hits[:10]:
            print(f"  {score}/{len(needles)}  {path}   — {title}")
        return 0

    if args.check:
        print(f"route-check: {len(rows)} notes indexed")
        churn = ("Calendar/Daily/", "Calendar/Weekly/", "AIOS/generated/git-status.md")
        others = [p for p in notes
                  if p.resolve() != WHERE.resolve()
                  and not rel(p).startswith(churn)]
        stale = (not WHERE.exists() or not others
                 or WHERE.stat().st_mtime < max(p.stat().st_mtime for p in others))
        print(f"route-check: AIOS/generated/where.md is {'STALE' if stale else 'current'}")
        if missing:
            print(f"route-check: !! {len(missing)} project note(s) have no route "
                  f"in AIOS/vault-map.md:", file=sys.stderr)
            for m in missing:
                print(f"  - {m}", file=sys.stderr)
            return 1
        print("route-check: every project note has a route")
        return 0

    WHERE.write_text(render(rows, missing), encoding="utf-8")
    print(f"route-check: rewrote AIOS/generated/where.md — {len(rows)} notes indexed")
    if missing:
        print(f"route-check: !! {len(missing)} project note(s) have no route in "
              f"AIOS/vault-map.md — add a row for each:", file=sys.stderr)
        for m in missing:
            print(f"  - {m}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
