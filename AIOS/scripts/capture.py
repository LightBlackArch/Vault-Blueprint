#!/usr/bin/env python3
"""capture.py — write to the vault without reading it first.

Appending one line to a Radar-style list, one row to canon.md, one line to
today's diary and one frontmatter field can otherwise mean opening all four
files in full just to append to them — expensive for zero benefit, since
they're append-only tables that nothing needs to read to write to.

So: one command, no reads, all the changelog lines batched into a single
`logchange.py` call at the end.

    python3 AIOS/scripts/capture.py \
      --set "Atlas/Media/Some Show.md::status=finished" \
      --log "Finished the show, season 1."

Every flag is repeatable and they can be mixed in one call. Field separator is
`::` everywhere — never `|` (breaks markdown tables) and never `,` (breaks
anything that splits a list on commas).

    --log TEXT                    append a line to today's ## Diary
    --set FILE::key=value         set one frontmatter key (creates it if absent)
    --append FILE::HEADING::TEXT  append TEXT under HEADING (creates heading)
    --row FILE::HEADING::|row|    insert a markdown table row right after the
                                   last existing row of the table under HEADING.
                                   Never use --append for a table row: --append
                                   lands at the end of the whole section, which
                                   can be after a callout that follows the
                                   table — that silently breaks the table.
    --radar ITEM::TYPE::WHY::STATUS       insert a Radar row, dated today
                                   TYPE: book, manga, anime, show, game, tool, idea, other
                                   STATUS: want to check out, in progress, done, dropped
    --canon FACT::TRUTH::OWNER::STALE::ALLOWED   append a canon row
    --why TEXT                    override the changelog line (single action only)
    --dry-run                     print every change, write nothing

`today` is accepted as a value for any date field. Nothing is ever overwritten:
every action inserts or replaces a single line. Refuses to touch `Privat/`.
Exits non-zero if any action failed, and says which.
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import subprocess
import sys
from pathlib import Path

VAULT = Path(__file__).resolve().parent.parent.parent
SCRIPTS = VAULT / "AIOS" / "scripts"
SEP = "::"

STATUS_VOCAB = {
    "Efforts": {"active", "planned", "upcoming", "stalled", "parked", "done"},
    "Atlas/Media": {"watching", "reading", "playing", "finished", "dropped", "on hold"},
    "Atlas/Worlds": {"active", "parked", "dead", "unconfirmed"},
}

RADAR = Path("Atlas/Radar.md")
RADAR_MARKER = "<!-- New rows go above this line"
CANON = Path("AIOS/reference/canon.md")

errors: list[str] = []
changes: list[tuple[str, str, str]] = []  # (what, where, kind)


def die(msg: str) -> None:
    print(f"capture: {msg}", file=sys.stderr)
    sys.exit(1)


def problem(msg: str) -> None:
    errors.append(msg)
    print(f"  FAILED  {msg}", file=sys.stderr)


def split(raw: str, n: int, flag: str) -> list[str]:
    parts = [p.strip() for p in raw.split(SEP)]
    if len(parts) < n:
        problem(f"{flag} needs {n} fields separated by '{SEP}', got {len(parts)}: {raw!r}")
        return []
    return parts[:n - 1] + [SEP.join(parts[n - 1:]).strip()] if len(parts) > n else parts


def resolve(rel: str) -> Path | None:
    p = (VAULT / rel).resolve()
    try:
        p.relative_to(VAULT)
    except ValueError:
        problem(f"outside the vault: {rel}")
        return None
    if "Privat" in p.relative_to(VAULT).parts:
        problem(f"refusing to touch Privat/: {rel}")
        return None
    return p


def date_value(v: str, now: dt.datetime) -> str:
    return now.strftime("%Y-%m-%d") if v.strip().lower() == "today" else v


# ---------------------------------------------------------------- frontmatter

def set_frontmatter(raw: str, now: dt.datetime, dry: bool) -> None:
    parts = split(raw, 2, "--set")
    if not parts:
        return
    rel, assignment = parts
    if "=" not in assignment:
        problem(f"--set needs key=value, got {assignment!r}")
        return
    key, value = assignment.split("=", 1)
    key, value = key.strip(), date_value(value.strip(), now)

    path = resolve(rel)
    if path is None:
        return
    if not path.exists():
        problem(f"no such note: {rel}")
        return

    folder = str(path.parent.relative_to(VAULT)).replace("\\", "/")
    if key == "status":
        vocab = STATUS_VOCAB.get(folder)
        if vocab and value not in vocab:
            problem(f"status '{value}' not allowed in {folder}/ — pick from {sorted(vocab)}")
            return

    text = path.read_text(encoding="utf-8")
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        problem(f"{rel} has no frontmatter block to set '{key}' in")
        return
    try:
        close = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        problem(f"{rel} has an unterminated frontmatter block")
        return

    pattern = re.compile(rf"^{re.escape(key)}\s*:", re.IGNORECASE)
    hit = next((i for i in range(1, close) if pattern.match(lines[i])), None)
    old = lines[hit].split(":", 1)[1].strip() if hit is not None else None
    if old == value:
        print(f"  unchanged  {rel}  {key}: {value}")
        return

    if hit is not None:
        lines[hit] = f"{key}: {value}"
        what = f"{key}: {old} -> {value}"
    else:
        lines.insert(close, f"{key}: {value}")
        what = f"{key}: {value} added to frontmatter"

    print(f"  set        {rel}  {what}")
    if not dry:
        path.write_text("\n".join(lines), encoding="utf-8")
    changes.append((what, rel, "edit"))


# ------------------------------------------------------------- append to note

def append_section(raw: str, dry: bool) -> None:
    parts = split(raw, 3, "--append")
    if not parts:
        return
    rel, heading, body = parts
    heading = heading if heading.startswith("#") else f"## {heading}"
    path = resolve(rel)
    if path is None:
        return
    if not path.exists():
        problem(f"no such note: {rel} (create it with Write first — this flag only appends)")
        return

    lines = path.read_text(encoding="utf-8").split("\n")
    level = len(heading) - len(heading.lstrip("#"))
    hit = next((i for i in range(len(lines)) if lines[i].strip() == heading), None)

    if hit is None:
        while lines and not lines[-1].strip():
            lines.pop()
        lines += ["", heading, "", body]
        what = f"new section {heading} — {body[:70]}"
    else:
        end = len(lines)
        for i in range(hit + 1, len(lines)):
            m = re.match(r"^(#+)\s", lines[i])
            if m and len(m.group(1)) <= level:
                end = i
                break
        while end - 1 > hit and not lines[end - 1].strip():
            end -= 1
        lines.insert(end, body)
        lines.insert(end, "")
        what = f"{heading} — {body[:70]}"

    print(f"  append     {rel}  {heading}")
    if not dry:
        path.write_text("\n".join(lines), encoding="utf-8")
    changes.append((what, rel, "append"))


# --------------------------------------------------------- table row (generic)

def append_row(raw: str, dry: bool) -> None:
    parts = split(raw, 3, "--row")
    if not parts:
        return
    rel, heading, row = parts
    heading = heading if heading.startswith("#") else f"## {heading}"
    row = row.strip()
    if not (row.startswith("|") and row.endswith("|")):
        problem(f"--row value must be a full '| cell | cell |' markdown row: {row!r}")
        return

    path = resolve(rel)
    if path is None:
        return
    if not path.exists():
        problem(f"no such note: {rel} (create it with Write first — this flag only appends)")
        return

    lines = path.read_text(encoding="utf-8").split("\n")
    hit = next((i for i in range(len(lines)) if lines[i].strip() == heading), None)
    if hit is None:
        problem(f"no '{heading}' heading in {rel} — --row needs an existing table under an "
                f"existing heading; use --append to create a new section first")
        return

    sep_re = re.compile(r"^\|(?:[\s:-]+\|)+\s*$")
    header_idx = next(
        (i for i in range(hit, len(lines))
         if lines[i].strip().startswith("|") and i + 1 < len(lines)
         and sep_re.match(lines[i + 1].strip())),
        None,
    )
    if header_idx is None:
        problem(f"no markdown table found under '{heading}' in {rel}")
        return

    last_row = header_idx + 1
    i = last_row + 1
    while i < len(lines) and lines[i].strip().startswith("|"):
        last_row = i
        i += 1

    lines.insert(last_row + 1, row)
    print(f"  row        {rel}  {heading}")
    if not dry:
        path.write_text("\n".join(lines), encoding="utf-8")
    changes.append((f"{heading} — {row[:80]}", rel, "append"))


# -------------------------------------------------------------------- radar

def add_radar(raw: str, now: dt.datetime, dry: bool) -> None:
    parts = split(raw, 4, "--radar")
    if not parts:
        return
    item, kind, why, status = parts
    allowed = {"book", "manga", "anime", "show", "game", "tool", "idea", "other"}
    if kind not in allowed:
        problem(f"--radar type '{kind}' not in {sorted(allowed)}")
        return
    ok = {"want to check out", "in progress", "done", "dropped"}
    if status not in ok:
        problem(f"--radar status '{status}' not in {sorted(ok)}")
        return

    path = VAULT / RADAR
    lines = path.read_text(encoding="utf-8").split("\n")
    marker = next((i for i in range(len(lines)) if RADAR_MARKER in lines[i]), None)
    if marker is None:
        problem(f"{RADAR} has lost its '{RADAR_MARKER}' marker")
        return
    if any(f"**{item}**" in ln for ln in lines):
        print(f"  skipped    {RADAR}  '{item}' already has a row")
        return

    today = now.strftime("%Y-%m-%d")
    for field in (item, kind, why, status):
        if "|" in field:
            problem("'|' cannot appear in a table field — it breaks the row")
            return
    row = f"| {today} | **{item}** | {kind} | {why} | Chat {today} | {status} |"
    lines.insert(marker, row)
    print(f"  radar      {item} ({kind}, {status})")
    if not dry:
        path.write_text("\n".join(lines), encoding="utf-8")
    changes.append((f"Radar: {item} ({kind}) — {status}. {why[:80]}", str(RADAR), "append"))


# -------------------------------------------------------------------- canon

def add_canon(raw: str, now: dt.datetime, dry: bool) -> None:
    parts = split(raw, 5, "--canon")
    if not parts:
        return
    fact, truth, owner, stale, allowed_in = parts
    for field in parts:
        if "|" in field:
            problem("'|' cannot appear in a table field — it breaks the row")
            return
    if "," in stale and ";" not in stale:
        problem("stale wordings are separated by ';' not ',' — see canon.md")
        return

    path = VAULT / CANON
    lines = path.read_text(encoding="utf-8").split("\n")
    rows = [i for i, ln in enumerate(lines) if re.match(r"^\|\s*\d+\s*\|", ln)]
    if not rows:
        problem(f"{CANON} has no numbered rows — table shape changed")
        return
    used = {int(re.match(r"^\|\s*(\d+)", lines[i]).group(1)) for i in rows}
    num = max(used) + 1

    row = (f"| {num} | {fact} | {truth} | {owner} | {stale or '—'} | "
           f"{allowed_in or '—'} | {now.strftime('%Y-%m-%d')} |")
    lines.insert(rows[-1] + 1, row)
    print(f"  canon      row {num}: {fact}")
    if not dry:
        path.write_text("\n".join(lines), encoding="utf-8")
    changes.append((f"Canon row {num} — {fact}: {truth[:90]}", str(CANON), "append"))


# ---------------------------------------------------------------- diary log

def add_log(text: str, now: dt.datetime, dry: bool) -> None:
    day = VAULT / "Calendar" / "Daily" / f"{now:%Y-%m-%d}.md"
    if not day.exists():
        # logchange.py owns note creation from the template; let it run first.
        if dry:
            print(f"  log        would create {day.relative_to(VAULT)} via logchange first")
        else:
            run_logchange([("Created today's note", str(day.relative_to(VAULT)), "new")])
    lines = day.read_text(encoding="utf-8").split("\n") if day.exists() else []
    hit = next((i for i in range(len(lines)) if lines[i].strip() == "## Diary"), None)
    if hit is None:
        problem(f"{day.name} has no '## Diary' heading")
        return
    end = next((i for i in range(hit + 1, len(lines))
                if re.match(r"^#+\s", lines[i])), len(lines))
    while end - 1 > hit and not lines[end - 1].strip():
        end -= 1
    line = f"- {text}"
    lines.insert(end, line)
    print(f"  log        {line[:90]}")
    if not dry:
        day.write_text("\n".join(lines), encoding="utf-8")
    changes.append((f"Diary: {text[:90]}", str(day.relative_to(VAULT)), "append"))


# ----------------------------------------------------------------- changelog

def run_logchange(batch: list[tuple[str, str, str]]) -> None:
    payload = "".join(f"{w}\t{p}\t{k}\n" for w, p, k in batch)
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "logchange.py"), "--stdin"],
        input=payload, text=True, capture_output=True,
    )
    sys.stdout.write(proc.stdout)
    sys.stderr.write(proc.stderr)
    if proc.returncode != 0:
        problem(f"logchange.py exited {proc.returncode} — the writes happened, the receipt did not")


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Write to the vault without reading it first. Fields split on '::'.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("Every flag is repeatable")[1] if __doc__ else None,
    )
    ap.add_argument("--log", action="append", default=[], metavar="TEXT")
    ap.add_argument("--set", action="append", default=[], metavar="FILE::key=value")
    ap.add_argument("--append", action="append", default=[], metavar="FILE::HEADING::TEXT")
    ap.add_argument("--row", action="append", default=[], metavar="FILE::HEADING::|row|")
    ap.add_argument("--radar", action="append", default=[], metavar="ITEM::TYPE::WHY::STATUS")
    ap.add_argument("--canon", action="append", default=[],
                    metavar="FACT::TRUTH::OWNER::STALE::ALLOWED")
    ap.add_argument("--why", metavar="TEXT",
                    help="changelog wording, only with exactly one action")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    actions = (len(args.log) + len(args.set) + len(args.append) + len(args.row)
               + len(args.radar) + len(args.canon))
    if not actions:
        ap.print_help()
        die("nothing to do")
    if args.why and actions != 1:
        die("--why only makes sense with exactly one action")

    now = dt.datetime.now()
    print(f"capture — {VAULT}" + ("  (DRY RUN)" if args.dry_run else ""))

    for raw in args.set:
        set_frontmatter(raw, now, args.dry_run)
    for raw in args.append:
        append_section(raw, args.dry_run)
    for raw in args.row:
        append_row(raw, args.dry_run)
    for raw in args.radar:
        add_radar(raw, now, args.dry_run)
    for raw in args.canon:
        add_canon(raw, now, args.dry_run)
    for raw in args.log:
        add_log(raw, now, args.dry_run)

    if changes and args.why:
        changes[0] = (args.why, changes[0][1], changes[0][2])

    if args.dry_run:
        print(f"\n  {len(changes)} change(s) would be logged. Nothing written.")
        if errors:
            print(f"capture: {len(errors)} action(s) failed", file=sys.stderr)
            sys.exit(1)
        return
    if changes:
        run_logchange(changes)
    else:
        print("  nothing changed")

    if errors:
        print(f"\ncapture: {len(errors)} action(s) failed", file=sys.stderr)
        sys.exit(1)
    print(f"  {len(changes)} change(s) done, logged in one call.")


if __name__ == "__main__":
    main()
