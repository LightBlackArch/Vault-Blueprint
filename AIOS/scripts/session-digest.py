#!/usr/bin/env python3
"""
session-digest.py — what happened in past Claude Code sessions, in one readable
file, so a new session can pick up where the last one stopped.

Claude Code keeps every session as a raw log (a .jsonl file: one JSON record
per line) in ~/.claude/projects/. Those are too long to read. This turns each
session for THIS vault into one line: the date, how many messages you sent,
what you asked first, and which files it edited. No AI is involved, so there is
no cost, no cloud, and nothing hidden: the digest is a plain note you can read.

    python3 AIOS/scripts/session-digest.py              # rebuild AIOS/generated/sessions.md
    python3 AIOS/scripts/session-digest.py recent [N]   # print the last N sessions (default 5)
    python3 AIOS/scripts/session-digest.py find WORD    # sessions whose request or files match
    python3 AIOS/scripts/session-digest.py context      # short block for a session-start hook
    python3 AIOS/scripts/session-digest.py --install-schedule   # rebuild it hourly, by itself
    python3 AIOS/scripts/session-digest.py --uninstall-schedule
    python3 AIOS/scripts/session-digest.py --selftest

Only sessions started from this vault's folder are read (Claude Code names the
log folder after the working directory). Set CLAUDE_PROJECTS_DIR to read logs
from somewhere else. Reads only the user's own typed messages and the file
paths the AI edited; tool output is never copied. Last 60 days, newest 300.
No dependencies. Plain stdlib. Never reads Privat/.
"""
import datetime as dt
import json
import os
import re
import sys
import tempfile

VAULT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
DAYS, MAX = 60, 300
EDIT_TOOLS = {"Edit", "Write", "NotebookEdit", "MultiEdit"}


def slug(path):
    return re.sub(r"[^A-Za-z0-9]", "-", path)


def project_dirs(vault, base):
    s = slug(vault)
    if not os.path.isdir(base):
        return []
    return [os.path.join(base, d) for d in sorted(os.listdir(base)) if d == s]


def user_text(msg):
    c = msg.get("content")
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return " ".join(b.get("text", "") for b in c if isinstance(b, dict) and b.get("type") == "text")
    return ""


def real_prompt(text):
    """A message he typed, not a reminder, hook output or slash-command wrapper."""
    t = text.strip()
    return bool(t) and not t.startswith(("<system-reminder", "<local-command", "<command-", "Caveat:", "[Request interrupted"))


def digest_one(path, vault):
    first_ts, prompts, first, edited = None, 0, "", []
    try:
        lines = open(path, encoding="utf-8", errors="ignore")
    except OSError:
        return None
    for line in lines:
        try:
            r = json.loads(line)
        except ValueError:
            continue
        ts = r.get("timestamp")
        if ts and not first_ts:
            first_ts = ts
        if r.get("type") == "user" and not r.get("isMeta") and not r.get("toolUseResult"):
            t = user_text(r.get("message", {}))
            if real_prompt(t):
                prompts += 1
                if not first:
                    first = re.sub(r"\s+", " ", t).strip()[:140]
        elif r.get("type") == "assistant":
            c = r.get("message", {}).get("content")
            for b in c if isinstance(c, list) else []:
                if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") in EDIT_TOOLS:
                    fp = (b.get("input") or {}).get("file_path") or (b.get("input") or {}).get("notebook_path")
                    if fp:
                        fp = os.path.relpath(fp, vault) if fp.startswith(vault) else fp
                        if "Privat" not in fp.split(os.sep) and fp not in edited:
                            edited.append(fp)
    if not first_ts or not prompts:
        return None
    return {"date": first_ts[:10], "id": os.path.basename(path)[:8], "prompts": prompts,
            "first": first.replace("|", "/"), "edited": edited}


def collect(vault=VAULT, base=None):
    base = base or os.environ.get("CLAUDE_PROJECTS_DIR") or os.path.join(os.path.expanduser("~"), ".claude", "projects")
    cutoff = (dt.date.today() - dt.timedelta(days=DAYS)).isoformat()
    rows = []
    for d in project_dirs(vault, base):
        for f in os.listdir(d):
            if f.endswith(".jsonl"):
                r = digest_one(os.path.join(d, f), vault)
                if r and r["date"] >= cutoff:
                    rows.append(r)
    rows.sort(key=lambda r: (r["date"], r["id"]), reverse=True)
    return rows[:MAX]


def line(r):
    files = ", ".join(r["edited"][:4]) + (f" (+{len(r['edited']) - 4} more)" if len(r["edited"]) > 4 else "")
    return f"- {r['date']} `{r['id']}` {r['prompts']} msg — {r['first']}" + (f" — edited: {files}" if files else "")


def write(rows, vault=VAULT):
    p = os.path.join(vault, "AIOS", "generated", "sessions.md")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    head = ["---", "title: Sessions", "tags:", "  - generated", "---", "", "# Sessions", "",
            f"> Machine-written by `session-digest.py`: one line per Claude Code session started "
            f"in this vault, last {DAYS} days. Never hand-edit. Search: `session-digest.py find WORD`.", ""]
    open(p, "w", encoding="utf-8").write("\n".join(head + [line(r) for r in rows] + [""]))
    return p


def main(argv):
    if argv and argv[0] == "--selftest":
        return selftest()
    if argv and argv[0] in ("--install-schedule", "--uninstall-schedule"):
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        try:
            import scheduler
        except ImportError:
            print("This vault has no scheduler.py; add `0 * * * * python3 <this file>` to your crontab yourself.")
            return 1
        if argv[0] == "--uninstall-schedule":
            ok, detail = scheduler.uninstall("session-digest")
        else:
            every = int(argv[argv.index("--every-min") + 1]) if "--every-min" in argv else 60
            ok, detail = scheduler.install("session-digest", os.path.abspath(__file__), every_minutes=every)
        print(("Done. " if ok else "Could not: ") + detail)
        return 0 if ok else 1
    rows = collect()
    cmd = argv[0] if argv else "build"
    if cmd == "build":
        print(f"{len(rows)} session(s) -> {os.path.relpath(write(rows), VAULT)}")
    elif cmd == "recent":
        n = int(argv[1]) if len(argv) > 1 else 5
        print("\n".join(line(r) for r in rows[:n]) or "no sessions found for this vault")
    elif cmd == "find" and len(argv) > 1:
        w = argv[1].lower()
        hits = [r for r in rows if w in line(r).lower()]
        print("\n".join(line(r) for r in hits) or f"no session mentions '{w}'")
        return 0 if hits else 1
    elif cmd == "context":
        print("Recent sessions in this vault (newest first):")
        print("\n".join(line(r) for r in rows[:5]) or "none yet")
    else:
        print(__doc__)
        return 2
    return 0


def selftest():
    with tempfile.TemporaryDirectory() as t:
        vault = os.path.join(t, "my vault")
        os.makedirs(vault)
        base = os.path.join(t, "projects")
        d = os.path.join(base, slug(vault))
        os.makedirs(d)
        os.makedirs(os.path.join(base, "other-project"))
        today = dt.date.today().isoformat()

        def rec(**k):
            return json.dumps(k)
        u = lambda text, **x: rec(type="user", timestamp=today + "T10:00:00Z", message={"content": text}, **x)
        with open(os.path.join(d, "abcdef12-0000.jsonl"), "w") as f:
            f.write(u("<system-reminder>boot</system-reminder>") + "\n")
            f.write(u("fix the bike note | please") + "\n")
            f.write(rec(type="assistant", timestamp=today + "T10:01:00Z", message={"content": [
                {"type": "tool_use", "name": "Edit", "input": {"file_path": os.path.join(vault, "Efforts", "Bike.md")}},
                {"type": "tool_use", "name": "Write", "input": {"file_path": os.path.join(vault, "Privat", "x.md")}},
                {"type": "tool_use", "name": "Read", "input": {"file_path": "/etc/passwd"}}]}) + "\n")
            f.write(u("second message") + "\n")
            f.write("not json\n")
        with open(os.path.join(base, "other-project", "zz.jsonl"), "w") as f:
            f.write(u("belongs to another project") + "\n")
        rows = collect(vault, base)
        assert len(rows) == 1, rows                       # other project's log is not read
        r = rows[0]
        assert r["prompts"] == 2 and r["first"] == "fix the bike note / please", r
        assert r["edited"] == [os.path.join("Efforts", "Bike.md")], r["edited"]   # Privat + Read ignored
        assert "Bike.md" in line(r) and r["id"] == "abcdef12"
        p = write(rows, vault)
        assert "fix the bike note" in open(p).read()
    print("session-digest.py selftest: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
