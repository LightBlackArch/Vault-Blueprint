"""
AIOS/scripts/paths.py

The single source of truth for every path in the vault that anything —
script, note, or human — might need to refer to.

If a folder or file listed here ever moves or gets renamed, this is the ONE
file that changes. Don't edit it by hand and then go fix every note and
script that mentioned the old path — run:

    python3 AIOS/scripts/move.py "<old/path>" "<new/path>" --reason "..."

move.py does the actual move, rewrites this file's constant, rewrites every
place across the vault (notes, scripts, config) that referenced the old
path, and logs the change to AIOS/reference/moves.md. See that file for
the history of every relocation made this way.

New scripts should import their paths from here instead of hardcoding a
string. Existing scripts still build their own paths locally — move.py
rewrites those in place when something moves, so nothing has to be
mass-migrated to adopt this file.
"""
from pathlib import Path

# ---- root ----
VAULT = Path(__file__).resolve().parent.parent.parent

# Every constant below is built directly off VAULT with its full component
# chain (VAULT / "a" / "b" / "c"), never off another constant. That's
# deliberate, not repetitive-by-accident: move.py rewrites these lines by
# pattern-matching the literal chain of quoted parts, and a constant built
# from another constant (SCRIPTS = AIOS / "scripts") hides part of that
# chain behind a name move.py can't see through. Flat chains are the only
# form that's safe to auto-rewrite.

# ---- AIOS/ boot files ----
AIOS = VAULT / "AIOS"
ME = VAULT / "AIOS" / "me.md"
VAULT_MAP = VAULT / "AIOS" / "vault-map.md"
SKILL_MAP = VAULT / "AIOS" / "skill-map.md"

# ---- AIOS/scripts/ ----
SCRIPTS = VAULT / "AIOS" / "scripts"
SCRIPTS_HISTORY = VAULT / "AIOS" / "history" / "scripts"
PATHS_PY = VAULT / "AIOS" / "scripts" / "paths.py"
MOVE_PY = VAULT / "AIOS" / "scripts" / "move.py"

# ---- AIOS/reference/ — opened on demand, never boot-loaded ----
REFERENCE = VAULT / "AIOS" / "reference"
CANON = VAULT / "AIOS" / "reference" / "canon.md"
NAMING = VAULT / "AIOS" / "reference" / "naming.md"
MIGRATION = VAULT / "AIOS" / "reference" / "migration.md"
ROUTINES = VAULT / "AIOS" / "reference" / "routines.md"
MOVES = VAULT / "AIOS" / "reference" / "moves.md"
BLUEPRINT_CHANGES = VAULT / "AIOS" / "reference" / "blueprint-changes.md"

# ---- AIOS/generated/ — machine-written, never hand-edited ----
GENERATED = VAULT / "AIOS" / "generated"
WHERE = VAULT / "AIOS" / "generated" / "where.md"
COMMANDS_GEN = VAULT / "AIOS" / "generated" / "commands.md"
GIT_STATUS = VAULT / "AIOS" / "generated" / "git-status.md"
SCALE = VAULT / "AIOS" / "generated" / "scale.md"
TASTE = VAULT / "AIOS" / "generated" / "taste.md"
HAPPENED = VAULT / "AIOS" / "generated" / "happened.md"

# ---- AIOS/config/ ----
CONFIG = VAULT / "AIOS" / "config"
BLUEPRINT_MANIFEST = VAULT / "AIOS" / "config" / "blueprint-manifest.json"
BLUEPRINT_STATE = VAULT / "AIOS" / "config" / "blueprint-state.json"

# ---- AIOS/history/ — every kind of automated history, one umbrella ----
HISTORY = VAULT / "AIOS" / "history"
HISTORY_CHAT = VAULT / "AIOS" / "history" / "chat-history"
HISTORY_COWORK = VAULT / "AIOS" / "history" / "chat-history" / "cowork"
HISTORY_COWORK_RAW = VAULT / "AIOS" / "history" / "chat-history" / "cowork-raw"
HISTORY_CURATED = VAULT / "AIOS" / "history" / "chat-history" / "curated"
HISTORY_BLUEPRINT_UPDATES = VAULT / "AIOS" / "history" / "blueprint-updates"
TRANSCRIPTS = VAULT / "AIOS" / "history" / "transcripts"

# ---- AIOS/templates/ ----
TEMPLATES = VAULT / "AIOS" / "templates"
DAILY_TEMPLATE = VAULT / "AIOS" / "templates" / "daily-note.md"
EVENT_TEMPLATE = VAULT / "AIOS" / "templates" / "event-note.md"
PERSON_TEMPLATE = VAULT / "AIOS" / "templates" / "person-note.md"

# ---- AIOS/skills/ ----
SKILLS_MIRROR = VAULT / "AIOS" / "skills"

# ---- Inbox/ ----
INBOX = VAULT / "Inbox"
INBOX_FILES = VAULT / "Inbox" / "Files"
INBOX_SCREENSHOTS = VAULT / "Inbox" / "Screenshots"

# ---- Atlas/ ----
ATLAS = VAULT / "Atlas"
ABOUT_ME = VAULT / "Atlas" / "About Me"
WORKING_WITH_AI = VAULT / "Atlas" / "About Me" / "Working with AI.md"
KNOWLEDGE = VAULT / "Atlas" / "Knowledge"
ATLAS_REFERENCE = VAULT / "Atlas" / "Reference"
CLIPPINGS = VAULT / "Atlas" / "Clippings"
MEDIA = VAULT / "Atlas" / "Media"
WORLDS = VAULT / "Atlas" / "Worlds"
RADAR = VAULT / "Atlas" / "Radar.md"
LINKS_DIR = VAULT / "Atlas" / "Links"
LINKS = VAULT / "Atlas" / "Links" / "Links.md"
LINKS_BASE = VAULT / "Atlas" / "Links" / "Links.base"
PEOPLE = VAULT / "Atlas" / "People"
PEOPLE_INDEX = VAULT / "Atlas" / "People" / "People.md"

# ---- Calendar/ ----
# Flat by design here: Calendar/Daily/YYYY-MM-DD.md, Calendar/Weekly/YYYY-Wnn.md.
# The source vault this blueprint comes from nests these by year/month once a
# folder crosses a few hundred files — see the note in vault-conventions.md.
# Nothing here stops you doing that later; it's a `move.py`-sized change,
# not a rewrite.
CALENDAR = VAULT / "Calendar"
COOLDOWNS = VAULT / "Calendar" / "Cooldowns.md"
DAILY = VAULT / "Calendar" / "Daily"
WEEKLY = VAULT / "Calendar" / "Weekly"
EVENTS = VAULT / "Calendar" / "Events"

# ---- Efforts/ ----
EFFORTS = VAULT / "Efforts"
EFFORTS_INDEX = VAULT / "Efforts" / "Efforts.md"
NEXT_ACTIONS = VAULT / "Efforts" / "Next Actions.md"

# Privat/ deliberately not listed here. Never read, never write, never a
# move target.

# ---- registry: every constant above, name -> Path, for move.py to search ----
REGISTRY = {
    name: value
    for name, value in list(globals().items())
    if isinstance(value, Path) and name.isupper()
}


def relative(p: Path) -> str:
    """Vault-relative path as forward-slash text, the form used in notes."""
    return p.resolve().relative_to(VAULT).as_posix()


def find_constant(path_text: str):
    """Given a vault-relative path string, return the constant name that
    currently points at it, or None. Used by move.py to keep this file in
    sync when the path it names is relocated."""
    target = path_text.strip("/")
    for name, value in REGISTRY.items():
        if relative(value) == target:
            return name
    return None


# --------------------------------------------------------------------------
# Calendar layout — one place that knows where a dated note lives
# --------------------------------------------------------------------------
import datetime as _dt  # noqa: E402


def _as_date(d) -> _dt.date:
    """Accept a date, a datetime, or 'YYYY-MM-DD'."""
    if isinstance(d, _dt.datetime):
        return d.date()
    if isinstance(d, _dt.date):
        return d
    return _dt.date.fromisoformat(str(d).strip())


# For logging, a day runs until 04:00, not midnight. Something logged at 00:30
# ("two hours of screen time tonight") belongs to the evening it happened in,
# not to a day that has barely started. Scripts that keep one row per day use
# night() as their default date instead of date.today(). Change the hour here
# if your days end earlier or later.
ROLLOVER_H = 4


def night(now=None) -> _dt.date:
    """The day a log entry belongs to when no date was given: today, except
    between midnight and ROLLOVER_H o'clock, when it is still yesterday."""
    now = now or _dt.datetime.now()
    return (now - _dt.timedelta(hours=ROLLOVER_H)).date()


def daily_note(d) -> Path:
    """Canonical path for a day's note: Calendar/Daily/YYYY-MM-DD.md."""
    return DAILY / f"{_as_date(d).isoformat()}.md"


def find_daily_note(d):
    """The day's note if it exists, else None. A thin wrapper so callers
    don't have to know the layout — if you ever nest this folder the way the
    source vault does, only this function and daily_note() change."""
    p = daily_note(d)
    return p if p.exists() else None


def all_daily_notes() -> list:
    """Every daily note in the vault, sorted by date."""
    out = []
    for p in sorted(DAILY.glob("*.md")):
        name = p.stem
        if len(name) == 10 and name[4] == "-" and name[7] == "-":
            out.append(p)
    return out


def weekly_note(year, week=None) -> Path:
    """Canonical path for a weekly review: Calendar/Weekly/YYYY-Wnn.md.

    Takes either (2026, 34) or the string '2026-W34'."""
    if week is None:
        stem = str(year).strip()
    else:
        stem = f"{int(year)}-W{int(week):02d}"
    return WEEKLY / f"{stem}.md"


def find_weekly_note(year, week=None):
    p = weekly_note(year, week)
    return p if p.exists() else None


def all_weekly_notes() -> list:
    return sorted(p for p in WEEKLY.glob("*.md") if "-W" in p.stem)


def event_note(title: str, start) -> Path:
    """Canonical path for an event note: Calendar/Events/YYYY/<Title>.md."""
    return EVENTS / f"{_as_date(start):%Y}" / f"{title}.md"


def all_event_notes() -> list:
    """Every event note, newest folder last. The index note is excluded."""
    out = [p for p in EVENTS.rglob("*.md") if p.stem != "Events"]
    return sorted(out)


if __name__ == "__main__":
    # Quick sanity check: print every registered path, vault-relative.
    for name in sorted(REGISTRY):
        print(f"{name:22s} {relative(REGISTRY[name])}")
    today = _dt.date.today()
    print(f"{'daily_note(today)':22s} {relative(daily_note(today))}")
    print(f"{'weekly_note(now)':22s} "
          f"{relative(weekly_note(*today.isocalendar()[:2]))}")
