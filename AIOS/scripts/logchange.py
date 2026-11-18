#!/usr/bin/env python3
"""
logchange.py — append a timestamped line to today's daily note under `## Changes`.

Every write an AI makes to this vault gets one line here, so you can open
today's daily note and see exactly what was changed, where, and when. The daily
note is the RECEIPT. The facts themselves still live in their own subject notes.

Usage:
    python3 AIOS/scripts/logchange.py "what changed" "path/to/note.md"
    python3 AIOS/scripts/logchange.py "what changed" "path/to/note.md" --kind new
    python3 AIOS/scripts/logchange.py "what changed"          # no file (rare)

    # several at once, one per line on stdin as:  what changed<TAB>path
    printf 'a\tx.md\nb\ty.md\n' | python3 AIOS/scripts/logchange.py --stdin

--kind is optional and defaults to "edit". Allowed: new, edit, append, skill,
script, template, map, delete.

Behaviour:
  - Creates today's daily note from AIOS/templates/daily-note.md if missing.
  - Creates the `## Changes` section if missing, placed after `## Diary`.
  - APPEND ONLY. Never rewrites or reorders an existing line.
  - Paths are stored relative to the vault root and wrapped in backticks.
  - Exits non-zero and prints to stderr on any failure, so a caller can tell
    the difference between "logged" and "silently did nothing".

A handful of guards ride along, because this is the one script that runs on
EVERY write and therefore the one place a check cannot be skipped. Each only
fires when the write actually touched something it cares about, so it costs
nothing the rest of the time. All report; none of them block a write.

  1. refresh_vault_map()       — the note count in AIOS/generated/scale.md
  2. check_boot_budget()       — the always-loaded context floor, if
                                  context-budget.py is present
  3. refresh_where_index()     — the one-grep note index in where.md
  4. nag_name_collision()      — a new note duplicating an old one
  5. check_canon_after_correction() — a canon.md row that never propagated,
     if canon-check.py is present
  6. refresh_commands_index() — AIOS/generated/commands.md, the flat list of
     every trigger phrase, whenever skill-map.md changes
  7. refresh_taste_profile() — AIOS/generated/taste.md, compiled from every
     `## Taste` section in the vault
  8. refresh_happened_index() — AIOS/generated/happened.md, the diary's event
     index
  9. connect_events()         — an event note gets linked into the days it
     covers, whenever anything under Calendar/Events/ is written
 10. nag_unregistered_images() — any image with no sidecar note; the fix is
     one `shot.py` command
 11. refresh_catalog()        — AIOS/generated/catalog.md, rebuilt whenever a
     write touches Atlas/Media/, Atlas/Worlds/, a `*Purchase*` project note
     or Money.md

Every guard checks whether its target script actually exists before running
it, so removing a script from AIOS/scripts/ just quietly disables the guard
instead of breaking logging.

A concurrent-write lock (see notelock.py) protects the read-modify-write on
today's daily note, since `diary.py` can also be writing the same file.

No dependencies. Plain stdlib.
"""

import argparse
import datetime as dt
import os
import re
import subprocess
import sys
from pathlib import Path

from notelock import locked, write_atomic  # one lock, shared with diary.py

# Vault root = two levels up from this file (AIOS/scripts/logchange.py)
VAULT = Path(__file__).resolve().parent.parent.parent

DAILY_DIR = VAULT / "Calendar" / "Daily"
TEMPLATE = VAULT / "AIOS" / "templates" / "daily-note.md"

CHANGES_HEADING = "## Changes"
CHANGES_BLURB = (
    "%% Appended by `AIOS/scripts/logchange.py` every time anything in the vault "
    "is written. This is the receipt, not the content — the facts themselves live "
    "in their own notes. Never overwritten. %%"
)

KINDS = {
    "new": "new",
    "edit": "edit",
    "append": "append",
    "skill": "skill",
    "script": "script",
    "template": "template",
    "map": "map",
    "delete": "delete",
}


def fail(msg: str) -> None:
    print(f"logchange: ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def today_note(now: dt.datetime) -> Path:
    return DAILY_DIR / f"{now:%Y-%m-%d}.md"


def render_template(now: dt.datetime) -> str:
    """Fill the Obsidian template placeholders we can fill ourselves."""
    if TEMPLATE.exists():
        text = TEMPLATE.read_text(encoding="utf-8")
        text = text.replace("{{date:YYYY-MM-DD}}", f"{now:%Y-%m-%d}")
        # e.g. Friday, 7 August 2026
        long_date = f"{now:%A}, {now.day} {now:%B} {now:%Y}"
        text = text.replace("{{date:dddd, D MMMM YYYY}}", long_date)
        return text
    # Minimal fallback if the template is ever missing
    return (
        f"---\ntitle: \"{now:%Y-%m-%d}\"\ndate: {now:%Y-%m-%d}\ntags:\n  - daily\n---\n\n"
        f"# {now:%A}, {now.day} {now:%B} {now:%Y}\n\n## Brief\n\n---\n\n## Log\n\n---\n\n"
        "## Tomorrow\n\n- [ ]\n"
    )


def ensure_note(path: Path, now: dt.datetime) -> str:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render_template(now), encoding="utf-8")
        print(f"logchange: created {path.relative_to(VAULT)}")
    return path.read_text(encoding="utf-8")


def ensure_changes_section(text: str) -> str:
    """Return text guaranteed to contain a `## Changes` section."""
    if re.search(r"^## Changes\s*$", text, flags=re.MULTILINE):
        return text

    block = f"\n{CHANGES_HEADING}\n\n{CHANGES_BLURB}\n"

    # Preferred position: immediately after `## Diary` (or the older `## Log`,
    # for a note written before the rename), before whatever comes next.
    for heading in ("## Diary", "## Log"):
        m = re.search(rf"^{re.escape(heading)}\s*$", text, flags=re.MULTILINE)
        if not m:
            continue
        rest = text[m.end():]
        nxt = re.search(r"^(## |---\s*$)", rest, flags=re.MULTILINE)
        cut = m.end() + (nxt.start() if nxt else len(rest))
        return text[:cut] + block + text[cut:]

    # Fallback: append at the end of the file.
    return text.rstrip("\n") + "\n\n" + block.lstrip("\n")


def rel_path(raw: str) -> str:
    """Normalise a path to be vault-relative, without exploding on odd input."""
    p = Path(raw)
    try:
        if p.is_absolute():
            return str(p.resolve().relative_to(VAULT))
    except ValueError:
        return str(p)  # outside the vault; log it verbatim
    return str(p).lstrip("./")


def make_line(now: dt.datetime, what: str, where: str | None, kind: str) -> str:
    what = " ".join(what.split()).rstrip(".")
    if not what:
        fail("empty change description")
    stamp = f"{now:%H:%M}"
    tag = f" _{kind}_" if kind != "edit" else ""
    if where:
        return f"- **{stamp}** —{tag} {what} → `{rel_path(where)}`"
    return f"- **{stamp}** —{tag} {what}"


def append_lines(lines: list[str], now: dt.datetime) -> Path:
    """Append receipts to today's `## Changes`, under a lock, atomically.

    This is a read-modify-write on a file that `diary.py` also writes — and
    diary.py calls this script to write, too. Unlocked, the two can race and
    destroy real notes. See notelock.py for the full story.
    """
    note = today_note(now)
    with locked(note):
        text = ensure_note(note, now)
        text = ensure_changes_section(text)

        m = re.search(r"^## Changes\s*$", text, flags=re.MULTILINE)
        if not m:
            fail("could not find or create the ## Changes section")

        # Find the end of this section: the next `## ` heading, `---`, or EOF.
        rest = text[m.end():]
        nxt = re.search(r"^(## |---\s*$)", rest, flags=re.MULTILINE)
        end = m.end() + (nxt.start() if nxt else len(rest))

        body = text[m.end():end].rstrip("\n")

        # CommonMark needs a blank line before a list starts. If the section so far
        # ends with prose (the blurb) rather than an existing bullet, add one.
        last = body.splitlines()[-1].strip() if body.strip() else ""
        gap = "\n" if last.startswith("- ") else "\n\n"

        body += gap + "\n".join(lines)
        new_text = text[:m.end()] + body + "\n\n" + text[end:]

        write_atomic(note, new_text)
    return note


# ---------------------------------------------------------------------------
# guards — each fires only when the write actually touched what it cares
# about, and only if its target script is actually present in this vault.
# ---------------------------------------------------------------------------

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".heic"}
# Not "history": a bare entry here once pruned AIOS/history/screenshots/, the
# exact folder this guard exists to police. Add your own code projects here —
# their app icons are build assets, not pictures worth a record.
SKIP_DIRS = {"Privat", ".git", ".obsidian", ".trash", ".claude", "skills",
             "node_modules", "dist"}


def nag_unregistered_images() -> None:
    """Shout, on every vault write, about images that have no record.

    A picture copied into the vault by hand has no note saying what it shows
    or where it came from, and a rule in a file read once per session does not
    survive the session. This runs on every write, so the warning can't be
    missed. Cheap on purpose: it only asks whether the sidecar note exists.
    Reports only — never blocks a write."""
    orphans = []
    for dirpath, dirnames, filenames in os.walk(VAULT):
        dirnames[:] = [d for d in dirnames
                       if d not in SKIP_DIRS and not d.startswith(".")]
        for fn in sorted(filenames):
            p = Path(dirpath) / fn
            if p.suffix.lower() in IMAGE_EXTS and not p.with_suffix(".md").exists():
                orphans.append(p.relative_to(VAULT))
    if not orphans:
        return
    print("", file=sys.stderr)
    print(f"logchange: !! {len(orphans)} image(s) in the vault have no record "
          f"of what they show or where they came from:", file=sys.stderr)
    for p in orphans[:10]:
        print(f"  - {p}", file=sys.stderr)
    if len(orphans) > 10:
        print(f"  ... and {len(orphans) - 10} more", file=sys.stderr)
    print('logchange: fix each one now, in this turn:\n'
          '  python3 AIOS/scripts/shot.py "<image>" --keep-name '
          '--shows "what it shows" --chat "<chat name>" --chat-id <id>\n'
          "logchange: that one command writes the sidecar note, embeds the "
          "facts in the file, and adds the row to Screenshots.md.",
          file=sys.stderr)


CATALOG_TRIGGER_PREFIXES = ("Atlas/Media/", "Atlas/Worlds/")
CATALOG_TRIGGER_RE = re.compile(r"^Efforts/.*Purchase.*\.md$")
CATALOG_TRIGGER_EXACT = {"Atlas/About Me/Money.md"}


def refresh_catalog(paths: list[str]) -> None:
    """Rebuild AIOS/generated/catalog.md whenever a write touches a
    game/anime/show note, a world/server note, a purchase-decision project, or
    the money ledger. Pure extraction from structured frontmatter, so it can't
    drift. Reports only."""
    touched = False
    for p in paths:
        if not p:
            continue
        r = rel_path(p)
        if r.startswith(CATALOG_TRIGGER_PREFIXES) or r in CATALOG_TRIGGER_EXACT \
                or CATALOG_TRIGGER_RE.match(r):
            touched = True
            break
    if not touched:
        return
    script = VAULT / "AIOS" / "scripts" / "catalog.py"
    if not script.exists():
        return
    try:
        r = subprocess.run([sys.executable or "python3", str(script)],
                           capture_output=True, text=True, timeout=60)
        out = (r.stdout or "").strip()
        if "rewrote" in out:
            print(f"logchange: {out}")
    except Exception as e:
        print(f"logchange: couldn't refresh AIOS/generated/catalog.md ({e})",
              file=sys.stderr)


def refresh_vault_map(paths: list[str], kinds: list[str]) -> None:
    """Keep the note count in `AIOS/generated/scale.md` true without anybody
    retyping it. Only fires when a note was created or deleted."""
    if not any(k in ("new", "delete") for k in kinds):
        return
    script = VAULT / "AIOS" / "scripts" / "vault-map.py"
    if not script.exists():
        return
    try:
        r = subprocess.run([sys.executable or "python3", str(script)],
                           capture_output=True, text=True, timeout=60)
        out = (r.stdout or "").strip()
        if "rewritten" in out:
            print(f"logchange: {out.splitlines()[-1]}")
    except Exception as e:
        print(f"logchange: couldn't refresh AIOS/generated/scale.md ({e})",
              file=sys.stderr)


def _boot_files() -> list[str]:
    """The always-loaded set, read from context-budget.py so it can't drift.

    Falls back to a hardcoded copy if the import fails, because a broken
    guard must not break logging."""
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "context_budget", VAULT / "AIOS" / "scripts" / "context-budget.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return list(mod.BOOT_FILES)
    except Exception:
        return ["CLAUDE.md", "AIOS/me.md", "AIOS/character.md", "AIOS/vault-map.md",
                "AIOS/skill-map.md", "Atlas/About Me/Working with AI.md"]


def check_boot_budget(paths: list[str]) -> None:
    """Shout if a write to an always-loaded file grew the session floor.
    Reports only — never blocks or reverts a write."""
    boot = _boot_files()
    touched = any(
        p and (rel_path(p) in boot or rel_path(p).startswith("AIOS/skills/"))
        for p in paths
    )
    if not touched:
        return
    budget = VAULT / "AIOS" / "scripts" / "context-budget.py"
    if not budget.exists():
        return
    try:
        r = subprocess.run([sys.executable or "python3", str(budget)],
                           capture_output=True, text=True, timeout=60)
    except Exception as e:
        print(f"logchange: couldn't measure the context floor ({e})",
              file=sys.stderr)
        return
    if r.returncode == 0:
        for line in (r.stdout or "").splitlines():
            if line.strip().startswith("Now:"):
                print(f"logchange: boot file touched — floor {line.split(':',1)[1].strip()}")
        return
    print("", file=sys.stderr)
    print("logchange: !! you just edited a file that loads in EVERY session, "
          "and the floor is over budget:", file=sys.stderr)
    for line in (r.stdout or "").splitlines():
        if line.strip().startswith(("Baseline", "Now:", "OVER BUDGET", "FLOOR")):
            print(f"  {line.strip()}", file=sys.stderr)
    print("logchange: full report: python3 AIOS/scripts/context-budget.py",
          file=sys.stderr)


def refresh_where_index(paths: list[str], kinds: list[str]) -> None:
    """Keep `AIOS/generated/where.md` true, and shout when a project has no
    route. Only fires when a note was created or deleted. Reports only."""
    if not any(k in ("new", "delete") for k in kinds):
        return
    script = VAULT / "AIOS" / "scripts" / "route-check.py"
    if not script.exists():
        return
    try:
        r = subprocess.run([sys.executable or "python3", str(script)],
                           capture_output=True, text=True, timeout=120)
    except Exception as e:
        print(f"logchange: couldn't refresh AIOS/generated/where.md ({e})", file=sys.stderr)
        return
    for line in (r.stdout or "").splitlines():
        if "rewrote" in line:
            print(f"logchange: {line.split(':', 1)[1].strip()}")
    err = (r.stderr or "").strip()
    if err:
        print("", file=sys.stderr)
        print(err, file=sys.stderr)
        print("logchange: a project with no route is a project the next session "
              "can only find by ripgrepping the whole vault. Add a row to the "
              '"Where to look for what" table in AIOS/vault-map.md now.',
              file=sys.stderr)


def nag_name_collision(paths: list[str], kinds: list[str]) -> None:
    """Shout when a brand-new note duplicates a subject that already has one.
    Reports only — the note is already on disk by the time this fires."""
    if "new" not in kinds:
        return
    script = VAULT / "AIOS" / "scripts" / "route-check.py"
    if not script.exists():
        return
    skip = ("Calendar/Daily/", "Calendar/Weekly/", "AIOS/history/", "AIOS/skills/")
    for raw in paths:
        rel = raw.strip().strip("`")
        if not rel.endswith(".md") or rel.startswith(skip):
            continue
        stem = Path(rel).stem
        try:
            r = subprocess.run(
                [sys.executable or "python3", str(script),
                 "--exists", stem, "--exclude", rel],
                capture_output=True, text=True, timeout=120)
        except Exception as e:
            print(f"logchange: couldn't run the name-collision check ({e})",
                  file=sys.stderr)
            continue
        if r.returncode == 1:
            print("", file=sys.stderr)
            print(f"logchange: !! `{rel}` may duplicate a note that already "
                  f"exists:", file=sys.stderr)
            for line in (r.stdout or "").splitlines():
                if line.strip():
                    print(f"  {line}", file=sys.stderr)
            print("logchange: merge them now, or add the pair to the "
                  '"Confirmed distinct" table in AIOS/reference/naming.md with one line '
                  "saying why.", file=sys.stderr)


def check_canon_after_correction(paths: list[str]) -> None:
    """Run canon-check.py immediately when AIOS/reference/canon.md itself
    was touched, instead of waiting for a scheduled sweep."""
    if not any(p and rel_path(p) == "AIOS/reference/canon.md" for p in paths):
        return
    script = VAULT / "AIOS" / "scripts" / "canon-check.py"
    if not script.exists():
        return
    try:
        r = subprocess.run([sys.executable or "python3", str(script)],
                           capture_output=True, text=True, timeout=60)
    except Exception as e:
        print(f"logchange: couldn't run canon-check.py ({e})", file=sys.stderr)
        return
    out = (r.stdout or "").strip()
    if r.returncode == 0:
        print("logchange: canon.md row added — canon-check.py CLEAN, nothing "
              "else repeats the old wording")
        return
    print("", file=sys.stderr)
    print("logchange: !! you just added/edited a canon.md row, and other "
          "notes still repeat the old wording:", file=sys.stderr)
    for line in out.splitlines():
        if line.strip():
            print(f"  {line.strip()}", file=sys.stderr)
    print("logchange: fix each one now — full report: "
          "python3 AIOS/scripts/canon-check.py", file=sys.stderr)


def refresh_commands_index(paths: list[str]) -> None:
    """Keep `AIOS/generated/commands.md` true whenever `AIOS/skill-map.md`
    changes."""
    if not any(p and rel_path(p) == "AIOS/skill-map.md" for p in paths):
        return
    script = VAULT / "AIOS" / "scripts" / "commands.py"
    if not script.exists():
        return
    try:
        r = subprocess.run([sys.executable or "python3", str(script)],
                           capture_output=True, text=True, timeout=60)
        out = (r.stdout or "").strip()
        if "rewrote" in out:
            print(f"logchange: {out}")
    except Exception as e:
        print(f"logchange: couldn't refresh AIOS/generated/commands.md ({e})",
              file=sys.stderr)


def refresh_taste_profile(paths: list[str]) -> None:
    """Rebuild AIOS/generated/taste.md whenever a write touches a note that
    has a `## Taste` section."""
    touched = False
    for p in paths:
        if not p:
            continue
        fp = VAULT / rel_path(p)
        try:
            if fp.exists() and re.search(r"^## Taste\s*$", fp.read_text(encoding="utf-8"),
                                         re.MULTILINE):
                touched = True
                break
        except Exception:
            continue
    if not touched:
        return
    script = VAULT / "AIOS" / "scripts" / "taste.py"
    if not script.exists():
        return
    try:
        r = subprocess.run([sys.executable or "python3", str(script)],
                           capture_output=True, text=True, timeout=60)
        out = (r.stdout or "").strip()
        if "rewrote" in out:
            print(f"logchange: {out}")
    except Exception as e:
        print(f"logchange: couldn't refresh AIOS/generated/taste.md ({e})",
              file=sys.stderr)


def refresh_happened_index() -> None:
    """Rebuild AIOS/generated/happened.md — the diary's event index. Runs on
    every write, since any write can add a `## Diary` line and a drifted
    index is worse than no index — it answers, but wrongly."""
    script = VAULT / "AIOS" / "scripts" / "diary.py"
    if not script.exists():
        return
    try:
        subprocess.run([sys.executable or "python3", str(script), "--rebuild"],
                       capture_output=True, text=True, timeout=60)
    except Exception as e:
        print(f"logchange: couldn't refresh happened.md ({e})", file=sys.stderr)


def connect_events(paths: list[str]) -> None:
    """An event note that isn't linked from the days it covers is a note
    that won't be read on the day it matters. Whenever anything under
    `Calendar/Events/` is written, `event.py --sync` rebuilds the `## Events`
    section of every daily note in range."""
    if os.environ.get("AIOS_EVENT_SYNC"):
        return
    if not any(p.startswith("Calendar/Events/") for p in paths):
        return
    script = VAULT / "AIOS" / "scripts" / "event.py"
    if not script.exists():
        return
    try:
        r = subprocess.run([sys.executable or "python3", str(script), "--sync"],
                           capture_output=True, text=True, timeout=120,
                           env=dict(os.environ, AIOS_EVENT_SYNC="1"))
        out = (r.stdout or "").strip().splitlines()
        if out:
            print(f"logchange: {out[0]}")
    except Exception as exc:
        print(f"logchange: event sync skipped ({exc})", file=sys.stderr)


def main() -> None:
    ap = argparse.ArgumentParser(add_help=True, description=__doc__)
    ap.add_argument("what", nargs="?", help="what changed, in plain words")
    ap.add_argument("where", nargs="?", help="the file that changed")
    ap.add_argument("--kind", default="edit", choices=sorted(KINDS), help="type of change")
    ap.add_argument("--stdin", action="store_true", help="read 'what<TAB>where' lines from stdin")
    args = ap.parse_args()

    now = dt.datetime.now()
    lines: list[str] = []
    touched_paths: list[str] = []
    touched_kinds: list[str] = []

    if args.stdin:
        raw_lines = sys.stdin.read().splitlines()
        # Skip an accidental header row copy-pasted from the docstring's own
        # example ("what<TAB>path<TAB>kind" logged as if it were data).
        if raw_lines:
            first = [p.strip().lower() for p in raw_lines[0].split("\t")]
            if first and first[0] == "what" and (len(first) == 1 or first[1] in ("path", "where")):
                raw_lines = raw_lines[1:]
        for raw in raw_lines:
            if not raw.strip():
                continue
            parts = raw.split("\t")
            what = parts[0]
            where = parts[1] if len(parts) > 1 and parts[1].strip() else None
            kind = parts[2] if len(parts) > 2 and parts[2].strip() in KINDS else args.kind
            lines.append(make_line(now, what, where, kind))
            touched_kinds.append(kind)
            if where:
                touched_paths.append(where)
    else:
        if not args.what:
            fail("nothing to log — pass a description, or use --stdin")
        lines.append(make_line(now, args.what, args.where, args.kind))
        touched_kinds.append(args.kind)
        if args.where:
            touched_paths.append(args.where)

    if not lines:
        fail("nothing to log")

    note = append_lines(lines, now)
    for line in lines:
        print(f"logchange: {line}")
    print(f"logchange: written to {note.relative_to(VAULT)}")

    nag_unregistered_images()
    refresh_vault_map(touched_paths, touched_kinds)
    check_boot_budget(touched_paths)
    refresh_where_index(touched_paths, touched_kinds)
    nag_name_collision(touched_paths, touched_kinds)
    check_canon_after_correction(touched_paths)
    refresh_commands_index(touched_paths)
    refresh_taste_profile(touched_paths)
    refresh_catalog(touched_paths)
    refresh_happened_index()
    connect_events(touched_paths)


if __name__ == "__main__":
    main()
