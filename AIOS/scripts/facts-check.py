#!/usr/bin/env python3
"""
facts-check.py — keep the facts that change with the calendar current, starting
with the one every vault has: your age.

THE GAP: `AIOS/me.md` says "Born **DD.MM.YYYY** — N." That N is only true until
your next birthday. Nothing re-derives it, so after that day it just sits there
wrong, and an AI reading `me.md` states the wrong age with full confidence.
`canon-check.py` catches a fact somebody typed twice and corrected once; this
catches a fact that goes stale on its own, with time.

Each registered fact is recomputed fresh from a real source (today's date plus a
value already written in the vault). If the note disagrees, this rewrites that
exact number, nothing else in the file, and logs the change via logchange.py
like any other vault write.

    python3 AIOS/scripts/facts-check.py --check   # fix drift, print what changed
    python3 AIOS/scripts/facts-check.py --list    # every fact and its value today, writes nothing

One line per fact:
    OK         still current
    CORRECTED  the note said X, today it's Y: fixed in place and logged
    UNARMED    nothing to check yet (the birth date is still a << placeholder >>,
               or has no year): not an error, it just says so
    WARN       something a human should look at (me.md is missing, a birth
               date in the future)

Exit code: 0 when everything is OK, CORRECTED or UNARMED; 1 if anything is WARN;
2 if a correction couldn't be written.

The daily brief runs `--check` every morning (AIOS/skills/daily-brief/SKILL.md)
and only mentions it when something was CORRECTED or needs a look.

DATES it can read on the `Born` line: DD.MM.YYYY (what the me.md template asks
for) or YYYY-MM-DD. Slashes are refused on purpose: 04/03/1990 is April in one
country and March in another, and a guessed birthday is worse than none.

ADDING A FACT: write a function that takes (text of the file, today) and returns
a Result, then add it to FACTS with the file it reads. Only add facts you
actually want kept current; the registry exists so the next one is a few lines,
not a new script.

No dependencies. Plain stdlib.
"""
import scriptlog  # noqa: F401 -- logs this run to AIOS/history/scripts/

# aios-run: agent  (the daily brief, every morning; or by hand)

import datetime as dt
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths as P  # noqa: E402
from notelock import locked, write_atomic  # noqa: E402


class Result:
    """What one fact check found. `edit` is (start, end, new_text) when the
    file needs one span replaced, else None."""

    def __init__(self, status, message, current=None, correct=None, edit=None):
        self.status = status
        self.message = message
        self.current = current
        self.correct = correct
        self.edit = edit


# "Born **14.03.1990** — 36." The dash may be an em dash, an en dash or a
# hyphen; the age is the first whole number after it.
BORN_LINE = re.compile(r"Born \*\*(?P<date>[^*\n]+)\*\*(?P<sep>\s*[—–-]+\s*)"
                       r"(?P<age>[^\s.,;]*)")


def parse_birth_date(raw: str):
    raw = raw.strip()
    for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def age_on(born: dt.date, today: dt.date) -> int:
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


def fact_age(text: str, today: dt.date) -> Result:
    m = BORN_LINE.search(text)
    if not m:
        return Result("UNARMED", "no `Born **DD.MM.YYYY** — <age>` line in me.md, "
                                 "so there is no age to keep current")
    raw_date, raw_age = m.group("date"), m.group("age")
    if "<<" in raw_date:
        return Result("UNARMED", "birth date is still a << placeholder >> in me.md; "
                                 "fill it in (DD.MM.YYYY) to turn this on")
    born = parse_birth_date(raw_date)
    if born is None:
        return Result("UNARMED", f"can't read a full birth date in {raw_date.strip()!r}; "
                                 "write it as DD.MM.YYYY to turn this on")
    if born > today:
        return Result("WARN", f"birth date {born.isoformat()} is in the future; "
                              "typo in me.md?")
    correct = str(age_on(born, today))
    if not raw_age.isdigit():
        return Result("UNARMED", f"the age after the birth date isn't a number yet "
                                 f"({raw_age!r}); it should say {correct}")
    if raw_age == correct:
        return Result("OK", f"age {correct}", current=raw_age, correct=correct)
    return Result("CORRECTED", f"age {raw_age} -> {correct}", current=raw_age,
                  correct=correct, edit=(m.start("age"), m.end("age"), correct))


# (name, file it reads, function)
FACTS = [
    ("age", P.ME, fact_age),
]


def evaluate(name, path, fn, today):
    if not path.exists():
        return Result("WARN", f"{P.relative(path)} does not exist")
    return fn(path.read_text(encoding="utf-8"), today)


def cmd_list() -> int:
    today = dt.date.today()
    for name, path, fn in FACTS:
        r = evaluate(name, path, fn, today)
        shown = r.correct if r.correct is not None else "-"
        print(f"{name}: {shown}  [{r.status}] {r.message}  ({P.relative(path)})")
    return 0


def cmd_check() -> int:
    today = dt.date.today()
    worst = 0
    ok = 0
    for name, path, fn in FACTS:
        if not path.exists():
            print(f"facts-check: WARN {name}: {P.relative(path)} does not exist")
            worst = max(worst, 1)
            continue
        # Read, decide and write under one lock, so a note edited a moment
        # earlier by another script is never overwritten with a stale copy.
        with locked(path):
            text = path.read_text(encoding="utf-8")
            r = fn(text, today)
            if r.status == "CORRECTED" and r.edit:
                start, end, new = r.edit
                try:
                    write_atomic(path, text[:start] + new + text[end:])
                except OSError as e:
                    print(f"facts-check: ERROR {name}: couldn't write "
                          f"{P.relative(path)}: {e}")
                    worst = 2
                    continue
        if r.status == "OK":
            ok += 1
            continue
        print(f"facts-check: {r.status} {name}: {r.message} ({P.relative(path)})")
        if r.status == "WARN":
            worst = max(worst, 1)
        if r.status == "CORRECTED":
            subprocess.run(
                [sys.executable or "python3", str(P.SCRIPTS / "logchange.py"),
                 f"facts-check: {name} corrected {r.current} -> {r.correct}",
                 P.relative(path)],
                check=False)
    if ok == len(FACTS):
        print(f"facts-check: OK — {ok} fact(s) checked, all current.")
    return worst


def main() -> int:
    if "--list" in sys.argv:
        return cmd_list()
    if "--check" in sys.argv:
        return cmd_check()
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main())
