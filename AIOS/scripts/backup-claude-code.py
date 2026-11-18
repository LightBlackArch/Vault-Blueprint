#!/usr/bin/env python3
"""
backup-claude-code — copy Claude Code CLI session transcripts into this vault
so they survive a reinstall, a dead disk, or `~/.claude` getting wiped.

RUN THIS ON YOUR OWN COMPUTER, in a real terminal — not by asking an AI to run
it inside a cloud/sandboxed session. It needs real filesystem access to
`~/.claude`, which only exists on the machine the CLI actually ran on.

    python3 AIOS/scripts/backup-claude-code.py
    python3 AIOS/scripts/backup-claude-code.py --install-schedule --every-min 60
    python3 AIOS/scripts/backup-claude-code.py --uninstall-schedule

It only ever READS from ~/.claude/projects and WRITES inside this vault,
under AIOS/history/chat-history/claude-code/. It never deletes anything and
is safe to run as often as you like — unchanged files are skipped.

What it saves
--------------
  AIOS/history/chat-history/claude-code/      every session as readable
                                               Markdown (always)
  AIOS/history/chat-history/claude-code-raw/  every session exactly as Claude
                                               Code stored it (.jsonl), one
                                               subfolder per project — ONLY
                                               when you pass --raw

Raw copies are off by default: they run to gigabytes in a heavy-use vault, and
if the vault folder is synced (Dropbox, iCloud, OneDrive) they fill the free
plan. The raw .jsonl is the one backup that cannot lose anything, so pass --raw
once if you want it; the Markdown is what you'd actually open and read — same
reasoning as backup-cowork.py.

Separate script on purpose: Claude Code (the CLI) and Cowork/Claude Desktop
keep entirely different session stores on disk. This one never touches
`~/.config/Claude`; backup-cowork.py never touches `~/.claude`.

No dependencies. Plain stdlib.
"""
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

HOME = Path.home()
SRC_PROJECTS = HOME / ".claude" / "projects"

# This script lives at <vault>/AIOS/scripts/backup-claude-code.py, so the
# vault is two levels up — found this way, not hardcoded, so renaming the
# vault folder never breaks it. Same trick as backup-cowork.py.
VAULT = Path(__file__).resolve().parent.parent.parent
DEST_RAW = VAULT / "AIOS" / "history" / "chat-history" / "claude-code-raw"
DEST_MD = VAULT / "AIOS" / "history" / "chat-history" / "claude-code"

RAW = "--raw" in sys.argv

stats = {"seen": 0, "raw": 0, "raw_skipped": 0, "md": 0, "md_skipped": 0,
         "md_failed": 0, "bytes": 0}


def copy_if_newer(src: Path, dst: Path) -> bool:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        s, d = src.stat(), dst.stat()
        if s.st_size == d.st_size and s.st_mtime <= d.st_mtime:
            return False
    shutil.copy2(src, dst)
    stats["bytes"] += src.stat().st_size
    return True


def text_of(content) -> str:
    """Pull readable text out of a message body, whatever shape it is."""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    out = []
    for block in content:
        if not isinstance(block, dict):
            out.append(str(block))
            continue
        t = block.get("type")
        if t == "text":
            out.append(block.get("text", ""))
        elif t == "thinking":
            continue
        elif t == "tool_use":
            out.append(f"*[used tool: {block.get('name', 'unknown')}]*")
        elif t == "tool_result":
            out.append("*[tool result]*")
    return "\n\n".join(x for x in out if x)


def project_label(rows, fallback):
    """A readable project name, taken from the first `cwd` a row records.

    The folder Claude Code actually stores this under is the project path
    with every `/` turned into `-`, which is unreadable and ambiguous to
    reverse. The `cwd` field inside the transcript itself is the real path,
    so use its last component instead.
    """
    for r in rows:
        cwd = r.get("cwd")
        if cwd:
            return Path(cwd.rstrip("/")).name or fallback
    return fallback


def jsonl_to_markdown(path: Path, project: str):
    """Best-effort conversion. Returns (markdown, n_messages) or (None, 0)."""
    rows = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    if not rows:
        return None, 0

    first_ts = next((r.get("timestamp") for r in rows if r.get("timestamp")), "")
    date = (first_ts or "")[:10] or "unknown-date"
    proj = project_label(rows, project)

    title = "Claude Code session"
    for r in rows:
        if r.get("type") == "user":
            msg = r.get("message") or {}
            txt = text_of(msg.get("content", "")).strip()
            if txt and not txt.startswith("<"):
                title = " ".join(txt.split())[:70]
                break

    out = ["---",
           f'title: "{title.replace(chr(34), chr(39))}"',
           f"date: {date}",
           "tags:",
           "  - chat-log",
           f"project: {proj}",
           f"source: {path.name}",
           "---",
           "",
           f"# {title}",
           "",
           "> [!quote] Automatic session transcript — not a note",
           "> Written by `AIOS/scripts/backup-claude-code.py`, overwritten on"
           " every run. Don't edit it. If something here matters, put it in"
           " the project note instead.",
           ">",
           "> Deliberately **no wikilinks** in generated transcripts. Dozens"
           " of session files each linking to `me.md` would bury that note's"
           " real backlinks under machine-written noise.",
           "",
           f"*Backed up {datetime.now().strftime('%Y-%m-%d %H:%M')} from "
           f"`{path.name}` (project: {proj})*",
           ""]

    n = 0
    for r in rows:
        role = r.get("type")
        if role not in ("user", "assistant"):
            continue
        msg = r.get("message") or {}
        body = text_of(msg.get("content", "")).strip()
        if not body:
            continue
        if role == "user" and body == "*[tool result]*":
            continue
        ts = (r.get("timestamp") or "")[11:16]
        who = "**You**" if role == "user" else "**Claude**"
        out.append(f"### {who}" + (f" · {ts}" if ts else ""))
        out.append("")
        out.append(body)
        out.append("")
        n += 1

    return "\n".join(out), n


def backup_sessions():
    if not SRC_PROJECTS.is_dir():
        print(f"  !! not found: {SRC_PROJECTS}")
        print("     Claude Code may not be installed on this machine, or it "
              "stores sessions somewhere else.")
        return
    for project in sorted(p.name for p in SRC_PROJECTS.iterdir() if p.is_dir()):
        pdir = SRC_PROJECTS / project
        # Walk recursively, not just the top level: a session that spawned
        # subagents stores their transcripts one level deeper, at
        # <session-uuid>/subagents/agent-*.jsonl. A plain iterdir() never
        # sees those, so they'd silently never make it into the backup.
        for src in sorted(pdir.rglob("*.jsonl")):
            if not src.is_file():
                continue
            fn = src.name
            rel = src.relative_to(pdir)
            parent_session = rel.parts[0] if len(rel.parts) > 1 else ""

            stats["seen"] += 1
            if RAW:
                if copy_if_newer(src, DEST_RAW / project / rel):
                    stats["raw"] += 1
                else:
                    stats["raw_skipped"] += 1

            try:
                md, n = jsonl_to_markdown(src, project)
                if md and n:
                    stem = fn[:-6]
                    proj = md.split("project: ")[1].split("\n")[0]
                    date = md.split("date: ")[1][:10]
                    tag = f"-{parent_session[:8]}-subagent" if parent_session else ""
                    name = f"{date}-{proj}-{stem[:8]}{tag}.md"
                    p = DEST_MD / name
                    p.parent.mkdir(parents=True, exist_ok=True)
                    old = p.read_text(encoding="utf-8") if p.exists() else ""

                    def strip_ts(t):
                        return "\n".join(
                            ln for ln in t.splitlines()
                            if not ln.startswith("*Backed up "))
                    if strip_ts(old) != strip_ts(md):
                        p.write_text(md, encoding="utf-8")
                        stats["md"] += 1
                    else:
                        stats["md_skipped"] += 1
            except Exception as e:
                stats["md_failed"] += 1
                print(f"  .. couldn't convert {fn}: {e}")


def write_history_index():
    files = sorted((f.name for f in DEST_MD.glob("*.md")
                    if f.name != "Claude Code chats.md"), reverse=True)

    (DEST_MD / "Claude Code chats.base").write_text(
        'filters:\n  and:\n'
        '    - file.inFolder("AIOS/history/chat-history/claude-code")\n'
        '    - file.hasTag("chat-log")\n'
        'properties:\n'
        '  file.name:\n    displayName: Session\n'
        '  title:\n    displayName: Opened with\n'
        '  date:\n    displayName: Date\n'
        '  project:\n    displayName: Project\n'
        'views:\n'
        '  - type: table\n    name: All sessions\n'
        '    order:\n      - title\n      - date\n      - project\n'
        '      - file.mtime\n'
        '  - type: table\n    name: By project\n'
        '    group_by: project\n'
        '    order:\n      - title\n      - date\n'
        '  - type: table\n    name: This month\n'
        '    filters:\n      and:\n'
        '        - \'file.mtime > now() - "30d"\'\n'
        '    order:\n      - title\n      - date\n', encoding="utf-8")

    (DEST_MD / "Claude Code chats.md").write_text(
        "---\ntitle: Claude Code chats\ntags:\n  - index\n---\n\n"
        "# Claude Code chats\n\n"
        f"**{len(files)} sessions**, updated "
        f"{datetime.now().strftime('%Y-%m-%d %H:%M')}.\n\n"
        "> [!info] Different tool, same shape as Cowork chats\n"
        "> This is the Claude Code CLI (terminal / IDE sessions) — a separate\n"
        "> session store from the Cowork/Claude Desktop app, see\n"
        "> the Cowork chats index.\n\n"
        "> [!warning] This whole folder is generated. Don't edit anything in it.\n"
        "> Written by `AIOS/scripts/backup-claude-code.py`. Every file here is\n"
        "> overwritten on each run.\n>\n"
        "> These are **session logs, not notes**. `AIOS/me.md` is explicit:\n"
        "> save facts, not chat logs. They live here so nothing is lost and so\n"
        "> you can search old sessions — **not** so decisions can live here.\n"
        "> A decision that only exists in this folder is a decision the next\n"
        "> session will re-argue. Put it in the project note.\n\n"
        "![[Claude Code chats.base]]\n\n"
        "## Searching these\n\n"
        "In Obsidian, restrict a search to just these sessions with:\n\n"
        "```\ntag:#chat-log \"the thing you're looking for\"\n```\n\n"
        "Or exclude them from a normal search with `-tag:#chat-log`.\n\n"
        "## Related\n\n- [[Home]]\n",
        encoding="utf-8")


def main() -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import scheduler  # noqa: E402

    if "--install-schedule" in sys.argv or "--install-cron" in sys.argv:
        every = 60
        if "--every-min" in sys.argv:
            every = int(sys.argv[sys.argv.index("--every-min") + 1])
        ok, detail = scheduler.install("backup-claude-code", Path(__file__),
                                       every_minutes=every)
        print(("Installed. " if ok else "Could NOT install automatically. ")
              + detail)
        if not ok:
            print("  You'll need to run this script by hand from time to "
                  "time instead, or set it up in your OS's own scheduler.")
            return 1
        print()
        print("Running it once now so you don't wait for the first scheduled run:")
        print()

    if "--uninstall-schedule" in sys.argv or "--uninstall-cron" in sys.argv:
        ok, detail = scheduler.uninstall("backup-claude-code")
        print(("Removed. " if ok else "Could not remove: ") + detail)
        return 0 if ok else 1

    print("backup-claude-code")
    if not (VAULT / "AIOS").is_dir():
        print(f"  !! {VAULT} doesn't look like the vault (no AIOS/ folder).")
        print("     Run this script from where it lives inside the vault.")
        return 1

    if not SRC_PROJECTS.is_dir():
        print(f"  !! Couldn't find a Claude Code session folder at {SRC_PROJECTS}.")
        print("     Claude Code may not have run on this machine yet, or this")
        print("     is a cloud/sandboxed session rather than your own computer —")
        print("     this has to run on the machine where the CLI itself ran.")
        return 1

    print(f"  from: {SRC_PROJECTS}")
    print(f"  to:   {DEST_MD.relative_to(VAULT)}  (readable)")
    if RAW:
        print(f"        {DEST_RAW.relative_to(VAULT)}  (raw, exact)")
    print()

    if RAW:
        DEST_RAW.mkdir(parents=True, exist_ok=True)
    DEST_MD.mkdir(parents=True, exist_ok=True)
    backup_sessions()
    write_history_index()

    print("  markdown transcripts . %d new/updated  (%d unchanged, %d failed)"
          % (stats["md"], stats["md_skipped"], stats["md_failed"]))
    if RAW:
        print("  raw files ............ %d new/updated  (%d unchanged)"
              % (stats["raw"], stats["raw_skipped"]))
        print("  new data ............. %.2f MB" % (stats["bytes"] / 1048576))
    else:
        print("  raw files ............ skipped (pass --raw to keep exact copies)")
    print()
    total = stats["seen"]
    if total == 0:
        print("  NOTHING FOUND. Either Claude Code hasn't been used on this")
        print("  machine yet, or it stores sessions somewhere this script")
        print("  doesn't check yet.")
        return 1
    print(f"  Done. {total} session file(s) tracked in total.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
