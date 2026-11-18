#!/usr/bin/env python3
"""
diary.py — what actually happened in your life, written down and findable.

THE GAP THIS FILLS:

    ## Changes  = receipts. What the AI wrote to which file.
    ## Diary    = your actual life. One line per real-life event, your words
                  or the AI's, written the same turn it comes up.

Two halves, and the second is the important one:

  1. `## Diary` in the daily note — one line per real-life event.
  2. `AIOS/generated/happened.md` — a flat, generated index of every event
     ever recorded, one line each, plus an entity index of every name, place
     and thing with all the dates it appeared on.

Half 2 is what makes "when did I go to X?" answerable in ONE grep instead of
an AI opening ninety daily notes and guessing. Same idea as `where.md`, which
does this for notes; this does it for events.

TRUTHFULNESS: --when only ever prints lines that are actually recorded. If
there is no match it says so plainly. It cannot invent a date, because it has
no way to produce a line that isn't in a daily note.

USAGE:

    # write an entry — plain text, no time, no voice marker; it's just a
    # space you (or the AI, on your behalf) can write into
    python3 AIOS/scripts/diary.py "Went to the lake with friends, swimming"

    # backdate
    python3 AIOS/scripts/diary.py --date 2026-08-18 "Bike shop, saw the model"

    # THE QUESTION: when did X happen
    python3 AIOS/scripts/diary.py --when "the lake"

    # maintenance
    python3 AIOS/scripts/diary.py --rebuild        # regenerate happened.md
    python3 AIOS/scripts/diary.py --list --last 20

Every write rebuilds happened.md, so the index can never drift from the
notes. No dependencies. Plain stdlib.

DUPLICATES: before writing, it looks for a near-identical line within the last
three days and, if it finds one, refuses: prints "NOT written, already
recorded", leaves the note alone and exits 3. Add `--force` when it really is
a different event.
"""

import argparse
import datetime as dt
import difflib
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from notelock import locked, write_atomic  # one lock, shared with logchange.py

VAULT = Path(__file__).resolve().parent.parent.parent
DAILY = VAULT / "Calendar" / "Daily"
HAPPENED = VAULT / "AIOS" / "generated" / "happened.md"
TEMPLATE = VAULT / "AIOS" / "templates" / "daily-note.md"

DIARY_HEADING = "## Diary"

# A diary entry. Convention: plain `- text`, no time, no marker — the same
# whether typed by hand or added by the AI. Old entries (or ones a different
# tool wrote) may still carry a bold **HH:MM** and/or a ~/— marker in either
# order; both are still accepted here on read even though nothing writes them
# anymore, because a parser that reads the vault has to survive the vault as
# it actually is, not as the current convention says it should be.
ENTRY_RE = re.compile(
    r"^-?\s*(?:\*\*(?P<time>\d{2}:\d{2})\*\*\s*)?(?P<marker>[~—-])?\s*(?P<text>.*)$"
)

# Words that get capitalised for reasons other than being a name. Without this
# the entity index fills up with "Went", "Today", "The" and is useless.
STOP = {
    "a", "an", "the", "and", "but", "or", "so", "then", "after", "before",
    "went", "got", "had", "did", "was", "were", "made", "took", "came",
    "today", "yesterday", "tomorrow", "morning", "afternoon", "evening",
    "night", "monday", "tuesday", "wednesday", "thursday", "friday",
    "saturday", "sunday", "january", "february", "march", "april", "may",
    "june", "july", "august", "september", "october", "november", "december",
    "i", "we", "he", "she", "they", "it", "my", "his", "her", "their",
    "this", "that", "these", "those", "there", "here", "when", "what",
    "asked", "said", "told", "wanted", "started", "finished", "added",
    "first", "second", "last", "next", "new", "old", "also", "still",
    "installed", "fixed", "bought", "decided", "recorded", "logged",
}


def day_path(d: dt.date) -> Path:
    """Canonical path — Calendar/Daily/YYYY-MM-DD.md. Writing always uses this."""
    return DAILY / f"{d.isoformat()}.md"


def rel_day(d: dt.date) -> str:
    """Vault-relative text form of the day's note, for printing and for
    handing to logchange.py."""
    return f"Calendar/Daily/{d.isoformat()}.md"


# --------------------------------------------------------------------------
# writing
# --------------------------------------------------------------------------

def ensure_note(d: dt.date) -> Path:
    """Create the day's note from the template if it doesn't exist yet."""
    p = day_path(d)
    if p.exists():
        return p
    if TEMPLATE.exists():
        body = TEMPLATE.read_text(encoding="utf-8")
        body = body.replace("{{date:YYYY-MM-DD}}", d.isoformat())
        body = body.replace("{{date:dddd, D MMMM YYYY}}", d.strftime("%A, %-d %B %Y"))
    else:
        body = f"---\ntitle: \"{d.isoformat()}\"\ndate: {d.isoformat()}\ntags:\n  - daily\n---\n\n# {d:%A, %-d %B %Y}\n\n{DIARY_HEADING}\n"
    p.write_text(body, encoding="utf-8")
    return p


def ensure_diary_section(lines: list[str]) -> int:
    """Return the index of the `## Diary` heading, inserting it if absent.

    Placed directly after the H1 so your life sits above the machinery."""
    for i, l in enumerate(lines):
        if l.strip() == DIARY_HEADING:
            return i
    for i, l in enumerate(lines):
        if l.startswith("# ") and not l.startswith("## "):
            block = ["", DIARY_HEADING, "", ""]
            lines[i + 1:i + 1] = block
            return i + 2

    # No H1. Inserting the heading at line 0 would land ABOVE the YAML
    # frontmatter, which stops Obsidian parsing the properties at all and
    # turns title/date/tags into body text. Refuse instead: a malformed note
    # is a bug to fix, not something to write into.
    raise ValueError(
        "daily note has no '# ' heading — refusing to insert '## Diary', "
        "because doing so above the frontmatter would break the note's properties"
    )


def clean_entry_text(text: str) -> str:
    """Flatten an entry to one safe line — a newline in the argument would
    otherwise become real lines in the note, which can inject a heading."""
    flat = " ".join(text.replace("\r", "\n").split("\n"))
    flat = re.sub(r"\s+", " ", flat).strip()
    return flat


class DuplicateEntry(ValueError):
    pass


_STOP = {"about", "after", "again", "being", "because", "could", "didnt", "doesnt",
         "going", "their", "there", "these", "they", "this", "that", "with", "would",
         "which", "while", "where", "today", "yesterday", "tomorrow"}


def _sig(text: str) -> set[str]:
    """Distinctive tokens: 5+ chars (dates and hyphenated words stay whole), no filler."""
    return {w for w in re.findall(r"[\w][\w-]*", text.lower())
            if len(w) >= 5 and w not in _STOP}


def find_duplicate(text: str, d: dt.date, days: int = 3) -> str | None:
    """An existing Diary line (this day or the 2 before) that says the same thing.

    Same normalized text, or >=2 shared distinctive tokens covering >=25% of the
    shorter line. Exists because the same event ("the parcel arrives Saturday")
    gets mentioned in two chats and logged twice. Blocks, doesn't merge:
    `--force` overrides.
    """
    new = _sig(text)
    flat = re.sub(r"\W+", " ", text.lower()).strip()
    for back in range(days):
        p = day_path(d - dt.timedelta(days=back))
        if not p.exists():
            continue
        for _t, _m, old in section_entries(p.read_text(encoding="utf-8"), "Diary"):
            if re.sub(r"\W+", " ", old.lower()).strip() == flat:
                return old
            both = new & _sig(old)
            small = min(len(new), len(_sig(old))) or 1
            if len(both) >= 2 and len(both) / small >= 0.25:
                return old
    return None


def add_entry(text: str, d: dt.date, dry: bool, force: bool = False) -> str:
    text = clean_entry_text(text)
    if not text:
        raise ValueError("refusing to write an empty diary entry")

    line = f"- {text}"
    if not force:
        dup = find_duplicate(text, d)
        if dup:
            raise DuplicateEntry(dup)
    if dry:
        return line

    p = day_path(d)
    with locked(p):
        ensure_note(d)
        lines = p.read_text(encoding="utf-8").split("\n")
        head = ensure_diary_section(lines)

        end = next((i for i in range(head + 1, len(lines))
                    if re.match(r"^#+\s", lines[i])), len(lines))
        while end - 1 > head and not lines[end - 1].strip():
            end -= 1

        lines.insert(end, line)
        write_atomic(p, "\n".join(lines))
    return line


# --------------------------------------------------------------------------
# reading
# --------------------------------------------------------------------------

def section_entries(text: str, heading: str) -> list[tuple[str, str, str]]:
    """(time, marker, text) for each entry under `## <heading>`.

    Entries are unwrapped first: a bullet ('-' or the older '~') starts a new
    entry, a line without one is a continuation of the previous entry. An
    index that stores half a wrapped sentence fails the search it exists for.
    """
    raw, inside = [], False
    for line in text.splitlines():
        if line.strip().startswith("## "):
            inside = line.strip() == f"## {heading}"
            continue
        if inside:
            raw.append(line)

    joined: list[str] = []
    for line in raw:
        s = line.strip()
        if not s or s.startswith("%%") or s.startswith("<!--") or s == "---":
            continue
        if re.match(r"^[-~]\s", s) or not joined:
            joined.append(s)
        else:
            joined[-1] += " " + s

    out = []
    for s in joined:
        m = ENTRY_RE.match(s)
        if m and m.group("text").strip():
            out.append((m.group("time"), m.group("marker") or "~", m.group("text").strip()))
    return out


def collect() -> list[dict]:
    """Every recorded event across every daily note, oldest first."""
    events = []
    for f in sorted(DAILY.glob("20*.md")):
        try:
            d = dt.date.fromisoformat(f.stem)
        except ValueError:
            continue
        text = f.read_text(encoding="utf-8")
        for source in ("Diary", "Log"):
            for time, marker, body in section_entries(text, source):
                events.append({
                    "date": d,
                    "time": time or "",
                    "text": body,
                    "source": source.lower(),
                    "who": "you" if marker == "—" else "agent",
                })
    events.sort(key=lambda e: (e["date"], e["time"]))
    return events


def entities(text: str) -> set[str]:
    """Names, places and things, extracted without an AI. Deliberately
    crude — it exists to make grep land, not to be a parser."""
    found = set()
    for m in re.finditer(r"\[\[([^\]|#]+)", text):
        found.add(m.group(1).strip())

    plain = re.sub(r"\[\[[^\]]*\]\]", " ", text)
    plain = re.sub(r"`[^`]*`", " ", plain)

    for m in re.finditer(r"\b([A-Z][\w’'-]+(?:\s+[A-Z][\w’'-]+)*)", plain):
        phrase = m.group(1).strip()

        if " " not in phrase:
            before = plain[:m.start()].rstrip()
            if not before or before[-1] in ".!?:;":
                continue

        words = [w for w in phrase.split() if w.lower() not in STOP]
        if not words:
            continue
        cand = " ".join(words)
        if len(cand) < 3 or cand.lower() in STOP:
            continue
        found.add(cand)
    return found


def gist(text: str, limit: int = 100) -> str:
    """The shortest string that still identifies an event. happened.md is an
    INDEX, not a second copy of the daily note — enough to recognise and to
    grep, then a link to the day that holds the real text."""
    t = re.sub(r"\s+", " ", text).strip()
    t = re.sub(r"\*\*|__|\*|`", "", t)
    t = re.sub(r"\[\[([^\]|#]+)(?:\|[^\]]*)?\]\]", r"\1", t)
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", t)
    t = t.strip()
    if len(t) <= limit:
        return t
    cut = t[:limit]
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut + "…"


def ago(d: dt.date, today: dt.date) -> str:
    n = (today - d).days
    if n == 0:
        return "today"
    if n == 1:
        return "yesterday"
    if n < 14:
        return f"{n} days ago"
    if n < 60:
        return f"{n // 7} weeks ago"
    return f"{n // 30} months ago"


# --------------------------------------------------------------------------
# the index
# --------------------------------------------------------------------------

def rebuild(dry: bool = False) -> dict:
    events = collect()

    ent: dict[str, set[dt.date]] = {}
    for e in events:
        for name in entities(e["text"]):
            ent.setdefault(name, set()).add(e["date"])

    out = [
        "---", "title: happened", "tags:", "  - index", "  - generated",
        f"confirmed: {dt.date.today().isoformat()}", "---", "",
        "# happened.md — every event, one short line, so \"when did I…\" is one grep",
        "",
        "> [!warning] Generated — do not edit by hand",
        "> Rebuilt by `python3 AIOS/scripts/diary.py --rebuild`, and automatically on",
        "> every vault write. Anything typed in here is gone on the next rebuild.",
        "",
        "**Never add this to the boot set.** Like `where.md`, it exists to be *searched*,",
        "not loaded. **This file is a pointer, not storage** — it says *which day*, the",
        "daily note says what actually happened.",
        "",
        "```bash",
        'grep -i "something" AIOS/generated/happened.md',
        "python3 AIOS/scripts/diary.py --when something     # same, with dates worked out",
        "```",
        "",
    ]
    if events:
        out.append(
            f"**{len(events)} events** · **{len(ent)} names/places/things** · "
            f"{len(set(e['date'] for e in events))} days · "
            f"{min(e['date'] for e in events)} → {max(e['date'] for e in events)}"
        )
    else:
        out.append("**0 events recorded yet.**")
    out += [
        "",
        "## Name, place or thing → the days it came up",
        "",
        "**Start here.** One grep gives you the dates; jump to the day for the detail.",
        "",
    ]
    for name in sorted(ent, key=str.lower):
        dates = " ".join(d.isoformat() for d in sorted(ent[name]))
        out.append(f"- **{name}** — {dates}")

    out += [
        "",
        "## Every event, oldest first",
        "",
        "Trimmed to the first line's worth. The daily note holds the full text.",
        "",
    ]
    for e in events:
        stamp = f"**{e['time']}** " if e["time"] else ""
        out.append(
            f"- `{e['date']}` {stamp}{gist(e['text'])} → [[{e['date']}]]"
        )

    body = "\n".join(out) + "\n"
    if not dry:
        HAPPENED.parent.mkdir(parents=True, exist_ok=True)
        HAPPENED.write_text(body, encoding="utf-8")
    return {"events": len(events), "entities": len(ent)}


# --------------------------------------------------------------------------
# the question
# --------------------------------------------------------------------------

def answer_when(query: str) -> int:
    """Print every recorded occurrence of `query`, or say there is none.

    This must never lie: it reports lines that exist in daily notes and
    nothing else. There is no code path here that can produce a date the
    vault doesn't contain.
    """
    events = collect()
    today = dt.date.today()
    q = query.lower().strip()

    how = None

    hits = [e for e in events if q in e["text"].lower()]

    tokens = [t for t in re.findall(r"[\w'’À-ž-]+", q) if len(t) > 1]
    if not hits and len(tokens) > 1:
        hits = [e for e in events
                if all(t in e["text"].lower() for t in tokens)]
        if hits:
            how = "all of those words, in the same entry"

    fuzzy_of = None
    if not hits:
        vocab: dict[str, str] = {}
        for e in events:
            for n in entities(e["text"]):
                vocab.setdefault(n.lower(), n)
            for w in re.findall(r"[A-Za-zÀ-ž]{4,}", e["text"]):
                vocab.setdefault(w.lower(), w)

        probe = tokens or [q]
        cutoff = 0.75 if len(probe) == 1 else 0.88

        resolved, spellings = [], []
        for t in probe:
            near = difflib.get_close_matches(t, list(vocab), n=1, cutoff=cutoff)
            if not near:
                resolved = []
                break
            resolved.append(near[0])
            spellings.append(vocab[near[0]])

        if resolved:
            hits = [e for e in events
                    if all(r in e["text"].lower() for r in resolved)]
            if hits:
                fuzzy_of = " ".join(spellings)

    if not hits:
        vocab_names = sorted({n for e in events for n in entities(e["text"])},
                             key=str.lower)
        close = difflib.get_close_matches(q, [n.lower() for n in vocab_names],
                                          n=8, cutoff=0.5)
        print(f'No record of "{query}" in any daily note.')
        print(f"Searched {len(events)} events across "
              f"{len(set(e['date'] for e in events))} days.")
        if close:
            print("\nClosest things that ARE recorded: " + ", ".join(close))
        print("\nThat means it was never written down — not that it never happened.")
        return 1

    if fuzzy_of:
        print(f'No exact match for "{query}" — showing "{fuzzy_of}", '
              f"which looks like what you meant.\n")
    elif how:
        print(f'No exact phrase "{query}" — showing entries containing {how}.\n')

    word = "time" if len(hits) == 1 else "times"
    print(f'"{query}" — {len(hits)} {word} recorded\n')
    for e in hits:
        stamp = f"{e['time']} — " if e["time"] else "— "
        print(f"  {e['date']} ({e['date']:%A}, {ago(e['date'], today)}) "
              f"{stamp}{e['text']}")
        print(f"      → {rel_day(e['date'])}  [{e['source']}]")
    if len(hits) > 1:
        print(f"\n  First: {hits[0]['date']}   Most recent: {hits[-1]['date']}")
    return 0


# --------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description="Your diary: write it, then find it.")
    ap.add_argument("text", nargs="?", help="what happened")
    ap.add_argument("--date", help="YYYY-MM-DD (default: today)")
    ap.add_argument("--when", metavar="QUERY", help="when did this happen?")
    ap.add_argument("--rebuild", action="store_true", help="regenerate happened.md")
    ap.add_argument("--list", action="store_true", help="print recent events")
    ap.add_argument("--last", type=int, default=15, help="how many, with --list")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true", help="write even if a similar line exists")
    args = ap.parse_args()

    if args.when:
        return answer_when(args.when)

    if args.list:
        events = collect()[-args.last:]
        today = dt.date.today()
        if not events:
            print("Nothing recorded yet.")
            return 0
        for e in events:
            print(f"{e['date']} {e['time'] or '--:--'} [{e['source']:5}] {e['text'][:100]}")
        print(f"\n{len(events)} shown, {ago(events[0]['date'], today)} → "
              f"{ago(events[-1]['date'], today)}")
        return 0

    if args.rebuild:
        s = rebuild(dry=args.dry_run)
        print(f"happened.md: {s['events']} events, {s['entities']} names/places/things")
        return 0

    if not args.text:
        ap.print_help()
        return 2

    try:
        d = dt.date.fromisoformat(args.date) if args.date else dt.date.today()
    except ValueError:
        print(f"diary: --date must be YYYY-MM-DD, got {args.date!r}", file=sys.stderr)
        return 2

    try:
        line = add_entry(args.text, d, args.dry_run, args.force)
    except DuplicateEntry as e:
        print(f"diary: NOT written, already recorded: {e}\n"
              f"       (--force if it really is a different event)", file=sys.stderr)
        return 3
    except ValueError as e:
        print(f"diary: {e}", file=sys.stderr)
        return 2
    print(f"diary  {d}  {line}")

    if not args.dry_run:
        s = rebuild()
        print(f"index  happened.md: {s['events']} events, {s['entities']} names/places/things")
        script = VAULT / "AIOS" / "scripts" / "logchange.py"
        if script.exists():
            subprocess.run(
                [sys.executable or "python3", str(script),
                 f"Diary: {args.text[:100]}",
                 rel_day(d), "--kind", "append"],
                capture_output=True, text=True, timeout=60,
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
