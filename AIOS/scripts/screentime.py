#!/usr/bin/env python3
"""
screentime.py — one command to log a day's screen time and sleep, so "is it
actually going down" is a number instead of a feeling.

THE GAP: a screen-time or sleep number that only ever gets said out loud, with
no date attached and no history, can't answer "is this actually changing."
This appends one row per day and can print a rolling average.

Usage:
    python3 AIOS/scripts/screentime.py --hours 6.5 [--sleep 7] \
        [--date 2026-09-05] [--note "mostly gaming"]

    One row per date. Logging the same date twice fills in whichever number
    the row was missing (sleep in the morning, screen time at night) instead
    of adding a second row that every average would count twice, and a note
    already on the row is kept — a new note is added after it, never over it.

    A row's date is the day: screen time used that day, and the sleep of the
    night that STARTED that day (in bed on the 25th -> the 25th). So a sleep
    number given on its own, with no --date, goes on last night — it's said
    after waking up. Without --date, a day runs until 04:00 (paths.night()),
    so something logged at 00:30 lands on the evening it belongs to.

    python3 AIOS/scripts/screentime.py --list [--last 14]
    python3 AIOS/scripts/screentime.py --avg [--last 14]   # rolling average
    python3 AIOS/scripts/screentime.py --check             # warning system, silent if fine

Judgement doesn't belong in --list/--avg output — those just track the
number, they don't editorialize. `--check` is different on purpose: it's a
threshold-based warning system meant to be run automatically (e.g. from a
daily-brief routine) and only speaks up when a real threshold is crossed —
same pattern as a cooldowns/grades `--check`. Printing nothing worth
surfacing means nothing gets added to the day's brief. That's by design: a
warning that fires every day trains a person to ignore it.

No dependencies. Plain stdlib.
"""
import scriptlog  # noqa: F401

# aios-run: agent  (any time a screen-time or sleep number comes up)

import argparse
import datetime as dt
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths as P  # noqa: E402
from notelock import locked, write_atomic  # noqa: E402

NOTE = P.ABOUT_ME / "Screen time.md"
HEADING = "## Log"
INTRO = (
    "%% Append-only, via `AIOS/scripts/screentime.py`. One row per day you "
    "state a number for — not a nag, just the data. %%"
)
COLS = "| Date | Screen hrs | Sleep hrs | Note |"
SEP = "|---|---|---|---|"


def fail(msg: str) -> None:
    print(f"screentime: ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def safe_cell(text: str) -> str:
    if text is None:
        return ""
    return " ".join(str(text).replace("\r", "\n").split("\n")).replace("|", "¦").strip()


def ensure_section(lines) -> int:
    for i, l in enumerate(lines):
        if l.strip() == HEADING:
            return i
    rel = next((i for i, l in enumerate(lines) if l.strip() == "## Related"), len(lines))
    block = ["", HEADING, "", INTRO, "", COLS, SEP, ""]
    lines[rel:rel] = block
    return rel + 1


def table_bounds(lines):
    hit = next((i for i, l in enumerate(lines) if l.strip() == HEADING), None)
    if hit is None:
        return None, None
    header_idx = next((i for i in range(hit, len(lines)) if lines[i].startswith("| Date")), None)
    if header_idx is None:
        return None, None
    last = header_idx + 1
    i = last + 1
    while i < len(lines) and lines[i].startswith("|"):
        last = i
        i += 1
    return header_idx, last


def cmd_add(args) -> int:
    if args.date:
        try:
            date_str = dt.date.fromisoformat(args.date).isoformat()
        except ValueError:
            fail(f"--date must be YYYY-MM-DD, got {args.date!r}")
    elif args.sleep is not None and args.hours is None:
        # "slept 7h", said in the morning, is about the night before.
        date_str = (P.night() - dt.timedelta(days=1)).isoformat()
    else:
        date_str = P.night().isoformat()

    # Both cells are independently optional — don't force a guessed number into
    # the one that wasn't actually given. "?" means genuinely unknown, not zero.
    hours_cell = f"**{args.hours:g}h**" if args.hours is not None else "?"
    sleep_cell = f"{args.sleep:g}" if args.sleep is not None else ""
    row = f"| {date_str} | {hours_cell} | {sleep_cell} | {safe_cell(args.note)} |"

    with locked(NOTE):
        if not NOTE.exists():
            fail(f"{NOTE} does not exist")
        lines = NOTE.read_text(encoding="utf-8").split("\n")
        ensure_section(lines)
        header_idx, last_row_idx = table_bounds(lines)
        # One row per day. The same date logged twice (sleep in the morning,
        # screen hours at night) would otherwise be two rows, and every
        # average would count that day twice. Fill the cell that was given,
        # keep the one that wasn't.
        existing = next((i for i in range(header_idx + 2, last_row_idx + 1)
                         if lines[i].split("|")[1].strip() == date_str), None)
        if existing is not None:
            old_cells = [c.strip() for c in lines[existing].split("|")]
            if args.hours is None and len(old_cells) > 2:
                hours_cell = old_cells[2]
            if args.sleep is None and len(old_cells) > 3:
                sleep_cell = old_cells[3]
            old_note = old_cells[4] if len(old_cells) > 4 else ""
            # Never replace a note someone wrote with a later one: the context
            # in the first note ("travelling, atypical day") is exactly what
            # a later look at the numbers needs.
            new_note = safe_cell(args.note)
            if old_note and new_note and new_note not in old_note:
                note_cell = f"{old_note}; {new_note}"
            else:
                note_cell = old_note or new_note
            lines[existing] = f"| {date_str} | {hours_cell} | {sleep_cell} | {note_cell} |"
            row = lines[existing]
            verb = "updated"
        else:
            lines.insert(last_row_idx + 1, row)
            verb = "logged"
        write_atomic(NOTE, "\n".join(lines))

    print(f"screentime: {verb} — {row}")
    rel = P.relative(NOTE)
    parts = []
    if args.hours is not None:
        parts.append(f"{args.hours:g}h screen")
    if args.sleep is not None:
        parts.append(f"sleep {args.sleep:g}h")
    what = "Screen time: " + ", ".join(parts) if parts else "Screen time: logged"
    subprocess.run([sys.executable or "python3", str(P.SCRIPTS / "logchange.py"), what, rel],
                    check=False)
    return 0


def load_rows():
    if not NOTE.exists():
        fail(f"{NOTE} does not exist")
    lines = NOTE.read_text(encoding="utf-8").split("\n")
    header_idx, last_row_idx = table_bounds(lines)
    if header_idx is None:
        return []
    out = []
    for i in range(header_idx + 2, last_row_idx + 1):
        cells = [c.strip() for c in lines[i].split("|")]
        if len(cells) < 5:
            continue
        m = re.search(r"[\d.]+", cells[2])
        sleep_m = re.search(r"[\d.]+", cells[3])
        if not m and not sleep_m:
            continue  # row has neither number, nothing usable
        out.append({"date": cells[1], "hours": float(m.group(0)) if m else None,
                     "sleep": float(sleep_m.group(0)) if sleep_m else None,
                     "note": cells[4]})
    return out


def cmd_list(last: int) -> int:
    rows = load_rows()[-last:]
    if not rows:
        print("screentime: nothing logged yet.")
        return 0
    for r in rows:
        screen = f"{r['hours']:g}h screen" if r["hours"] is not None else "screen ?"
        sleep = f"{r['sleep']:g}h sleep" if r["sleep"] is not None else "sleep ?"
        print(f"{r['date']}  {screen}  {sleep}  {r['note']}")
    return 0


def cmd_avg(last: int) -> int:
    rows = load_rows()[-last:]
    if not rows:
        print("screentime: nothing logged yet.")
        return 0
    hours = [r["hours"] for r in rows if r["hours"] is not None]
    sleeps = [r["sleep"] for r in rows if r["sleep"] is not None]
    parts = [f"last {len(rows)} entries"]
    parts.append(f"avg screen {sum(hours)/len(hours):.1f}h/day" if hours else "no screen data")
    if sleeps:
        parts.append(f"avg sleep {sum(sleeps)/len(sleeps):.1f}h/night")
    print("screentime: " + " — ".join(parts))
    return 0


SLEEP_TARGET = 8.0  # AASM/National Sleep Foundation floor for teens; adjust
                     # for an adult household — see Atlas/About Me/Screen time.md


def cmd_check() -> int:
    """Not silent by default — silent only once it's actually armed and fine.
    A check with no input just looks like nothing's wrong, which is worse than
    saying nothing at all."""
    rows = load_rows()
    fired = False

    sleep_rows = [r for r in rows if r["sleep"] is not None]
    if not sleep_rows:
        print("UNARMED sleep: never logged once — this check has no data and does "
              "nothing until a sleep number is stated, once, in any conversation.")
        return 0

    last_date = dt.date.fromisoformat(sleep_rows[-1]["date"])
    days_quiet = (dt.date.today() - last_date).days
    if days_quiet > 7:
        print(f"STALE sleep: last logged {days_quiet}d ago ({sleep_rows[-1]['date']}) — "
              f"the check has gone quiet because it has nothing new to look at, not "
              f"because sleep's been fine.")
        fired = True

    recent = sleep_rows[-7:]
    avg7 = sum(r["sleep"] for r in recent) / len(recent)

    last3 = sleep_rows[-3:]
    zero_nights = [r for r in last3 if r["sleep"] <= 1.0]
    if zero_nights:
        dates = ", ".join(r["date"] for r in zero_nights)
        print(f"WARN sleep: near-zero night logged ({dates}) — acute deprivation hits "
              f"attention/memory within 1-7 nights.")
        fired = True

    if avg7 < SLEEP_TARGET - 1.5:  # meaningfully below target, not just a rounding gap
        print(f"WARN sleep: {avg7:.1f}h/night avg over last {len(recent)} logged nights, "
              f"target is {SLEEP_TARGET:g}h — memory consolidation happens during sleep, "
              f"this isn't a slow effect.")
        fired = True

    if len(sleep_rows) >= 10:
        prev = sleep_rows[-14:-7] if len(sleep_rows) >= 14 else None
        if prev:
            avg_prev = sum(r["sleep"] for r in prev) / len(prev)
            if avg7 < avg_prev - 1.0:
                print(f"WARN sleep: trending down — {avg_prev:.1f}h avg two weeks ago vs "
                      f"{avg7:.1f}h avg this week.")
                fired = True

    if not fired:
        print(f"screentime: sleep OK — {avg7:.1f}h/night avg over last {len(recent)} logged nights.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--hours", type=float, help="screen hours today")
    ap.add_argument("--sleep", type=float, help="sleep hours last night")
    ap.add_argument("--date", help="YYYY-MM-DD, defaults to today")
    ap.add_argument("--note", default="", help="free text")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--avg", action="store_true", help="rolling average")
    ap.add_argument("--check", action="store_true", help="warning system — silent if within range")
    ap.add_argument("--last", type=int, default=14)
    args = ap.parse_args()

    if args.check:
        return cmd_check()
    if args.list:
        return cmd_list(args.last)
    if args.avg:
        return cmd_avg(args.last)
    if args.hours is not None or args.sleep is not None:
        return cmd_add(args)
    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
