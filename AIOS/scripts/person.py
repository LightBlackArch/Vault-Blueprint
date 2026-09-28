#!/usr/bin/env python3
"""
AIOS/scripts/person.py

Every family member, friend, or teacher you actually talk about gets their
own note in `Atlas/People/<Name>.md`, instead of getting folded into the
`About Me` aggregate notes (`Family.md`, `Friends and social.md`) where a
detail about one specific person is hard to find again and harder to keep
current. Nothing from `Privat/` — this is for people mentioned in a normal
session, never a private diary.

    python3 AIOS/scripts/person.py "Dana Novak" --category family \
        --relation "younger sister" --fact "Starting middle school this year"

    python3 AIOS/scripts/person.py "Chris" --category friend \
        --relation "friend from climbing" \
        --fact "Also training for the same event"

    python3 AIOS/scripts/person.py --list
    python3 AIOS/scripts/person.py --rebuild-index

First call for a name creates the note from `AIOS/templates/person-note.md`.
Every later call for the same name (matched case-insensitively against the
filename) appends new facts under `## Facts`, dated, and never overwrites or
reorders what's already there — same append-only discipline as `diary.py`.
`--relation`/`--category` on a later call only touch the note if the value
actually changed, so a repeat call with the same relation is a no-op there.

`Atlas/People/People.md` is machine-written, grouped by category
(family / friend / teacher / other) — rebuilt on every write and by
`--rebuild-index`. Don't hand-edit it.

WHY THIS EXISTS: `auto-capture`'s routing table already said a person who
keeps coming up gets their own note; this is what makes that a script that
actually runs instead of a line nobody executes.
"""

import scriptlog  # noqa: F401 -- logs this run to AIOS/history/scripts/

import argparse
import datetime as dt
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths as P  # noqa: E402

VAULT = P.VAULT
PEOPLE = P.PEOPLE
PEOPLE_INDEX = P.PEOPLE_INDEX
TEMPLATE = P.PERSON_TEMPLATE
LOGCHANGE = VAULT / "AIOS" / "scripts" / "logchange.py"

CATEGORIES = ("family", "friend", "teacher", "other")
CATEGORY_LABEL = {
    "family": "Family",
    "friend": "Friends",
    "teacher": "Teachers",
    "other": "Other",
}

BAD_TITLE = re.compile(r'[\\/:*?"<>|\[\]]|^\.|\.\.')


def clean_title(title: str) -> str:
    """Becomes both a filename and a wikilink — same guard as event.py's
    clean_title, for the same reason."""
    t = title.strip()
    if not t or BAD_TITLE.search(t):
        raise ValueError(
            f"bad person name {title!r} — no / \\ : * ? \" < > | [ ] and no "
            f"leading dot or '..'. It becomes a filename and a wikilink.")
    return t


# ---------------------------------------------------------------- frontmatter

def split_front(text: str):
    fm = {}
    if not text.startswith("---"):
        return fm, text
    end = text.find("\n---", 3)
    if end == -1:
        return fm, text
    for line in text[3:end].splitlines():
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if m:
            fm[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    return fm, text


def set_front(text: str, key: str, value: str) -> str:
    if not text.startswith("---"):
        return text
    end = text.find("\n---", 3)
    if end == -1:
        return text
    head, rest = text[:end], text[end:]
    pat = re.compile(rf"^({re.escape(key)}):.*$", re.M)
    if pat.search(head):
        return pat.sub(rf"\1: {value}", head, count=1) + rest
    return head.rstrip("\n") + f"\n{key}: {value}" + rest


def get_tags(text: str) -> list:
    fm_end = text.find("\n---", 3) if text.startswith("---") else -1
    if fm_end == -1:
        return []
    head = text[:fm_end]
    m = re.search(r"^tags:\s*\n((?:  - .*\n?)+)", head, re.M)
    if not m:
        return []
    return [ln.strip()[2:].strip() for ln in m.group(1).splitlines() if ln.strip()]


def set_tags(text: str, tags: list) -> str:
    fm_end = text.find("\n---", 3) if text.startswith("---") else -1
    if fm_end == -1:
        return text
    head, rest = text[:fm_end], text[fm_end:]
    block = "tags:\n" + "".join(f"  - {t}\n" for t in tags)
    if re.search(r"^tags:\s*\n(?:  - .*\n?)*", head, re.M):
        head = re.sub(r"^tags:\s*\n(?:  - .*\n?)*", block, head, count=1, flags=re.M)
    else:
        head = head.rstrip("\n") + "\n" + block
    return head + rest


def append_under_heading(text: str, heading: str, line: str) -> str:
    """Append one line under `heading`, right before the next `## ` heading
    (or end of file). Creates the heading at the end if it's missing."""
    pat = re.compile(rf"^{re.escape(heading)}\s*$", re.M)
    m = pat.search(text)
    if not m:
        return text.rstrip("\n") + f"\n\n{heading}\n\n{line}\n"
    rest = text[m.end():]
    nxt = re.search(r"^## ", rest, re.M)
    cut = m.end() + (nxt.start() if nxt else len(rest))
    block = text[m.end():cut]
    # Drop a single leading placeholder bullet ("- ") if that's all there is.
    stripped = block.strip()
    if stripped in ("", "-"):
        block = "\n\n" + line + "\n\n"
    else:
        block = block.rstrip("\n") + "\n" + line + "\n\n"
    return text[:m.end()] + block + text[cut:]


# ---------------------------------------------------------------- log

def log(what: str, where: str, kind: str = "edit") -> None:
    if not LOGCHANGE.exists():
        return
    env = dict(os.environ, AIOS_PERSON_SYNC="1")
    subprocess.run([sys.executable or "python3", str(LOGCHANGE), what, where,
                    "--kind", kind],
                   capture_output=True, text=True, timeout=60, env=env)


# ---------------------------------------------------------------- index

def rebuild_index(quiet=False) -> Path:
    PEOPLE.mkdir(parents=True, exist_ok=True)
    groups = {c: [] for c in CATEGORIES}
    for p in sorted(PEOPLE.glob("*.md")):
        if p.stem == "People":
            continue
        text = p.read_text(encoding="utf-8")
        fm, _ = split_front(text)
        tags = get_tags(text)
        category = next((t for t in tags if t in CATEGORIES), "other")
        title = fm.get("title") or p.stem
        relation = fm.get("relation", "")
        groups.setdefault(category, []).append((title, relation, p))

    lines = [
        "---",
        "title: People",
        "tags:",
        "  - index",
        "  - person",
        "---",
        "",
        "# People",
        "",
        "Family, friends and teachers who keep coming up — one note each, so a",
        "detail about a specific person doesn't get lost inside the `About Me`",
        "aggregate notes. Machine-written by `AIOS/scripts/person.py` — don't",
        "hand-edit, run the script instead; it rebuilds this table on every write.",
        "Nothing from `Privat/` lives here.",
        "",
    ]
    any_people = any(groups[c] for c in CATEGORIES)
    if not any_people:
        lines.append("Nobody logged yet. Run `person.py \"<Name>\" --category "
                      "family|friend|teacher --relation \"...\"`.")
    for cat in CATEGORIES:
        rows = groups.get(cat, [])
        if not rows:
            continue
        lines.append(f"## {CATEGORY_LABEL[cat]}")
        lines.append("")
        lines.append("| Person | Relation |")
        lines.append("|---|---|")
        for title, relation, _ in sorted(rows, key=lambda r: r[0].lower()):
            lines.append(f"| [[{title}]] | {relation} |")
        lines.append("")
    lines += ["## Related", ""]
    # `Family` and `Friends and social` are suggested About Me notes, not ones
    # every vault has. Link them only when they exist: a link to a note that
    # isn't there is exactly what vault-check reports as broken.
    for aggregate in ("Family", "Friends and social"):
        if (P.ABOUT_ME / f"{aggregate}.md").exists():
            lines.append(f"- [[{aggregate}]]")
    lines += ["- [[About Me]]", ""]
    new_text = "\n".join(lines).rstrip("\n") + "\n"
    changed = not PEOPLE_INDEX.exists() or PEOPLE_INDEX.read_text(encoding="utf-8") != new_text
    if changed:
        PEOPLE_INDEX.write_text(new_text, encoding="utf-8")
        if not quiet:
            print(f"person: rebuilt {P.relative(PEOPLE_INDEX)}")
    return PEOPLE_INDEX


# ---------------------------------------------------------------- commands

def find_note(name: str):
    """Match an existing person note case-insensitively by filename, so
    'chris' and 'Chris' land on the same note."""
    if not PEOPLE.exists():
        return None
    target = name.strip().lower()
    for p in PEOPLE.glob("*.md"):
        if p.stem.lower() == target:
            return p
    return None


def cmd_new_or_update(args) -> int:
    try:
        name = clean_title(args.name)
    except ValueError as exc:
        print(f"person: {exc}", file=sys.stderr)
        return 1

    category = (args.category or "other").lower()
    if category not in CATEGORIES:
        print(f"person: --category must be one of {CATEGORIES}", file=sys.stderr)
        return 1

    PEOPLE.mkdir(parents=True, exist_ok=True)
    existing = find_note(name)
    today = dt.date.today().isoformat()

    if existing is None:
        body = TEMPLATE.read_text(encoding="utf-8") if TEMPLATE.exists() else (
            "---\ntitle: \ntags:\n  - person\n  - \nrelation: \n---\n\n"
            "# \n\nOne line: who they are.\n\n## Facts\n\n- \n\n"
            "## Related\n\n- [[People]]\n")
        body = body.replace("title: \n", f"title: {name}\n", 1)
        body = set_tags(body, ["person", category])
        body = set_front(body, "relation", args.relation or "")
        body = body.replace("# \n", f"# {name}\n", 1)
        about = args.about or "_One line: who they are and how they relate to you._"
        body = body.replace(
            "One line: who they are and how they relate to you.\n", about + "\n", 1)

        facts = args.fact or []
        if facts:
            fact_lines = "\n".join(f"- {today} — {f}" for f in facts)
            body = re.sub(
                r"(## Facts\n\n)- \n", rf"\1{fact_lines}\n", body, count=1)

        path = PEOPLE / f"{name}.md"
        path.write_text(body, encoding="utf-8")
        print(f"person: created {P.relative(path)}")
        rebuild_index(quiet=True)
        log(f"New person note for {name} ({category}"
            f"{': ' + args.relation if args.relation else ''})",
            P.relative(path), "new")
        return 0

    # ---- existing note: append only ----
    text = existing.read_text(encoding="utf-8")
    fm, _ = split_front(text)
    changed_bits = []

    if args.relation and fm.get("relation", "") != args.relation:
        text = set_front(text, "relation", args.relation)
        changed_bits.append(f"relation -> {args.relation}")

    tags = get_tags(text)
    if args.category and category not in tags:
        tags = [t for t in tags if t not in CATEGORIES] + [category]
        text = set_tags(text, tags)
        changed_bits.append(f"category -> {category}")

    added_facts = []
    for f in (args.fact or []):
        line = f"- {today} — {f}"
        if line in text:
            continue
        added_facts.append(f)
        text = append_under_heading(text, "## Facts", line)

    if not changed_bits and not added_facts:
        print(f"person: {P.relative(existing)} — nothing new")
        return 0

    existing.write_text(text, encoding="utf-8")
    print(f"person: updated {P.relative(existing)}")
    rebuild_index(quiet=True)

    what = []
    if added_facts:
        what.append("; ".join(added_facts))
    if changed_bits:
        what.append(", ".join(changed_bits))
    log(f"{name}: {' — '.join(what)}", P.relative(existing), "edit")
    return 0


def cmd_list() -> int:
    if not PEOPLE.exists() or not any(PEOPLE.glob("*.md")):
        print("person: nobody logged yet.")
        return 0
    for p in sorted(PEOPLE.glob("*.md")):
        if p.stem == "People":
            continue
        fm, text = split_front(p.read_text(encoding="utf-8"))
        tags = get_tags(text)
        category = next((t for t in tags if t in CATEGORIES), "other")
        relation = fm.get("relation", "")
        print(f"{p.stem:<28} [{category:<7}] {relation}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("name", nargs="?", help="the person's name (or role, if unnamed)")
    ap.add_argument("--category", choices=CATEGORIES,
                     help="family / friend / teacher / other")
    ap.add_argument("--relation", help="e.g. 'younger sibling', 'maths teacher'")
    ap.add_argument("--fact", action="append",
                     help="one fact to append, dated. Repeatable.")
    ap.add_argument("--about", help="one-line intro, used only when creating")
    ap.add_argument("--list", action="store_true", help="list every person note")
    ap.add_argument("--rebuild-index", action="store_true",
                     help="regenerate Atlas/People/People.md")
    args = ap.parse_args()

    if args.rebuild_index:
        rebuild_index()
        return 0
    if args.list:
        return cmd_list()
    if args.name:
        return cmd_new_or_update(args)
    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
