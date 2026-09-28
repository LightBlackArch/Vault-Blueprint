#!/usr/bin/env python3
"""
stale-check.py — find facts that have probably stopped being true, and notes
that exist but can't be found.

Reports only by default. `--fix-orphans` is the one flag that writes.

    python3 AIOS/scripts/stale-check.py
    python3 AIOS/scripts/stale-check.py --quiet   # exit 1 if anything found, no output

Three checks:

  [EXPIRED]  A note whose content has a shelf life and is past it. Shelf life is
             decided by folder + status, not by guessing at the text. A media
             note saying `status: watching` that nobody has touched in 30 days
             is a strong candidate for "actually just stopped".

  [ORPHAN]   A note that no other note links to. It is not lost — search still
             finds it — but nothing routes an agent to it.

  [NO ROUTE] A folder that vault-map.md's routing table never mentions. If the
             map doesn't name it, a session won't look in it.

Saving everything has a real downside beyond context cost: retrieval decay
and silent staleness. Both are mechanical problems, so they get a mechanical
check instead of another paragraph of rules in a file read once per session.

No dependencies. Plain stdlib.
"""
import argparse
import datetime as dt
import os
import re
import sys

VAULT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

SKIP_DIRS = {
    "Privat",
    ".obsidian",
    ".git",
    ".trash",
}
SKIP_PATHS = (
    os.path.join("AIOS", "history"),
    os.path.join("AIOS", "skills"),
)

# Shelf life in days, by folder and status. None means "never expires".
SHELF_LIFE = {
    "Atlas/Media": {
        "watching": 30,
        "reading": 30,
        "playing": 30,
        "on hold": 120,
        "finished": None,
        "dropped": None,
    },
    "Efforts": {
        "active": 21,
        "stalled": 60,
        "upcoming": 60,
        "planned": 90,
        "parked": None,
        "done": None,
    },
    "Atlas/Worlds": {
        "active": 45,
        "unconfirmed": 21,
        "parked": None,
        "dead": None,
    },
    "Atlas/About Me": {"*": 365},
}

INDEX_TAGS = {"index", "daily", "weekly", "chat-log", "generated"}

findings = []


def flag(section, msg):
    findings.append((section, msg))


def rel(path):
    return os.path.relpath(path, VAULT)


def skip(path):
    r = rel(path)
    parts = r.split(os.sep)
    if parts[0] in SKIP_DIRS:
        return True
    return any(r.startswith(p) for p in SKIP_PATHS)


def walk_md():
    for root, dirs, files in os.walk(VAULT):
        dirs[:] = [d for d in dirs if not skip(os.path.join(root, d))]
        for f in files:
            if f.endswith(".md"):
                p = os.path.join(root, f)
                if not skip(p):
                    yield p


def read(p):
    try:
        with open(p, encoding="utf-8") as fh:
            return fh.read()
    except (OSError, UnicodeDecodeError):
        return None


def frontmatter(text):
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    block = text[3:end]
    out = {}
    for line in block.splitlines():
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if m:
            key, val = m.group(1), m.group(2).strip().strip('"').strip("'")
            out[key] = val
    tags = re.findall(r"^\s*-\s*(\S+)\s*$", block, re.M)
    if tags:
        out.setdefault("_tags", []).extend(tags)
    return out


def shelf_days(relpath, status):
    for folder, table in SHELF_LIFE.items():
        if relpath.replace(os.sep, "/").startswith(folder + "/"):
            if "*" in table:
                return table["*"]
            return table.get(status, None)
    return None


def parse_date(s):
    try:
        return dt.date.fromisoformat(s.strip())
    except (ValueError, AttributeError):
        return None


def link_orphans(orphans):
    """Append each orphan to its folder's index note under '## Unfiled'.

    Deliberately dumb. It does not try to guess where a note belongs — it
    makes the note reachable and marks it as needing a proper home, which is
    the difference between 'lost' and 'untidy'. Only ever appends.
    """
    fixed, skipped = [], []
    for p in orphans:
        folder = os.path.dirname(p)
        r = rel(p)
        if folder == VAULT:
            skipped.append(f"{r} — sits at the vault root, no folder index")
            continue
        index = os.path.join(folder, os.path.basename(folder) + ".md")
        if not os.path.exists(index):
            skipped.append(f"{r} — {os.path.basename(folder)}.md does not exist")
            continue
        name = os.path.splitext(os.path.basename(p))[0]
        text = read(index)
        if not text or not text.strip():
            continue
        entry = f"- [[{name}]]\n"
        if entry.strip() in text:
            continue
        if "## Unfiled" in text:
            head, _, tail = text.partition("## Unfiled\n")
            body = tail.lstrip("\n")
            new = head + "## Unfiled\n\n" + entry + body
        else:
            new = text.rstrip("\n") + (
                "\n\n## Unfiled\n\n"
                "%% Auto-linked by stale-check.py --fix-orphans so these stay "
                "findable. Move them into a proper section when you get to "
                "it. %%\n\n" + entry)
        try:
            with open(index, "w", encoding="utf-8") as fh:
                fh.write(new)
            fixed.append(f"{r} -> {rel(index)}")
        except OSError as e:
            skipped.append(f"{r} — could not write index: {e}")
    return fixed, skipped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quiet", action="store_true",
                    help="no output, just exit 1 if anything was found")
    ap.add_argument("--fix-orphans", action="store_true",
                    help="link every orphan from its folder index, under an "
                         "'## Unfiled' heading. The only thing this script "
                         "ever writes. Never touches EXPIRED items — those "
                         "need a human to say whether the fact is still true.")
    args = ap.parse_args()

    today = dt.date.today()
    notes = list(walk_md())

    meta = {}
    linked_to = set()
    for p in notes:
        text = read(p) or ""
        fm = frontmatter(text)
        meta[p] = (fm, text)
        for target in re.findall(r"\[\[([^\]|#]+)", text):
            linked_to.add(target.strip().rstrip("\\").strip().lower())

    for p in notes:
        fm, text = meta[p]
        r = rel(p)
        status = fm.get("status", "")
        limit = shelf_days(r, status)
        if limit is None:
            continue

        confirmed = parse_date(fm.get("confirmed", ""))
        if confirmed:
            age = (today - confirmed).days
            basis = f"confirmed {confirmed}"
        else:
            mtime = dt.date.fromtimestamp(os.path.getmtime(p))
            age = (today - mtime).days
            basis = f"last edited {mtime}, no `confirmed:` field"

        if age > limit:
            label = f"status: {status}" if status else "no status"
            flag("EXPIRED",
                 f"{r} — {label}, {age}d old (limit {limit}d) — {basis}")

    orphans = []
    for p in notes:
        fm, text = meta[p]
        r = rel(p)
        tags = set(fm.get("_tags", []))
        if tags & INDEX_TAGS:
            continue
        if r.startswith("Calendar" + os.sep):
            continue
        # Templates are copied, not linked; the root entry points (CLAUDE.md,
        # AGENTS.md, README.md) are opened directly by tools and people.
        # None of them is meant to be reached through a wikilink.
        if r.startswith(os.path.join("AIOS", "templates")) or \
                r in ("CLAUDE.md", "AGENTS.md", "README.md"):
            continue
        name = os.path.splitext(os.path.basename(p))[0].lower()
        if name not in linked_to:
            orphans.append(p)
            flag("ORPHAN", f"{r} — nothing links to it; only findable by search")

    if args.fix_orphans:
        fixed, skipped = link_orphans(orphans)
        for line in fixed:
            print(f"  linked  {line}")
        for line in skipped:
            print(f"  skipped {line}")
        if fixed:
            print(f"\n{len(fixed)} orphan(s) linked. "
                  f"Log each one with logchange.py.")
        return 0

    map_path = os.path.join(VAULT, "AIOS", "vault-map.md")
    map_text = read(map_path)
    if map_text:
        folders = set()
        for p in notes:
            d = os.path.dirname(rel(p))
            if d and d != ".":
                folders.add(d.replace(os.sep, "/"))
        for f in sorted(folders):
            if f not in map_text and f.split("/")[0] not in map_text:
                flag("NO ROUTE", f"{f}/ — not mentioned in vault-map.md")

    if args.quiet:
        return 1 if findings else 0

    print(f"stale-check — {VAULT}")
    print(f"  {len(notes)} notes scanned "
          f"(excluding Privat/, AIOS/history/, AIOS/skills/)")
    print()

    if not findings:
        print("Nothing stale, nothing orphaned, nothing unrouted.")
        return 0

    current = None
    for section, msg in sorted(findings):
        if section != current:
            print(f"[{section}]")
            current = section
        print(f"  - {msg}")
    print()
    print(f"{len(findings)} item(s) need attention. Nothing was changed.")
    print("EXPIRED is not 'wrong' — it's 'nobody has confirmed this in a while'.")
    print("Confirm one by adding `confirmed: YYYY-MM-DD` to its frontmatter.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
