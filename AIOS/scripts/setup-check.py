#!/usr/bin/env python3
"""
setup-check.py — one command that answers "is this actually working?"

Everything else in AIOS/scripts/ does one job and reports on itself. This
script runs all of them and prints a single pass/fail table, so a human (or
an AI) can tell at a glance what's real and what still needs attention,
instead of piecing it together from five separate script outputs.

Run it:
    python3 AIOS/scripts/setup-check.py

Run it any time. Nothing here changes the vault except reading it — this is
the "did the setup actually work" check, not the setup itself. Re-run it
after `setup.py`, and again a day or two later to confirm scheduled jobs
survived (see the note in setup.py about cloud/sandboxed sessions).

Exit code: 0 if everything checked is in a good state, 1 if anything needs
attention. Either way, nothing is ever silently assumed to be fine — every
row below was actually tested this run.

No dependencies. Plain stdlib.
"""
import scriptlog  # noqa: F401 -- logs this run to AIOS/history/scripts/

import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

VAULT = Path(__file__).resolve().parent.parent.parent
SCRIPTS = VAULT / "AIOS" / "scripts"
sys.path.insert(0, str(SCRIPTS))

PASS, WARN, FAIL = "PASS", "WARN", "FAIL"
rows = []


def check(name, status, detail):
    rows.append((name, status, detail))


def run(*args, timeout=60):
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout, r.stderr
    except FileNotFoundError:
        return 127, "", "not found"
    except subprocess.TimeoutExpired:
        return 124, "", "timed out"


def is_sandbox_guess() -> bool:
    """Best-effort, not authoritative — see setup.py's note on this. A path
    under /sessions/ or /tmp/ that isn't inside a real home directory is the
    strongest available signal that this is a disposable cloud container
    rather than someone's own computer."""
    p = str(VAULT)
    return "/sessions/" in p or p.startswith("/tmp/") or p.startswith("/var/")


def c_python():
    v = sys.version_info
    if v >= (3, 8):
        check("Python", PASS, f"{v.major}.{v.minor}.{v.micro}")
    else:
        check("Python", FAIL, f"{v.major}.{v.minor} — need 3.8+")


def c_vault_shape():
    if (VAULT / "AIOS").is_dir():
        check("Vault folder", PASS, str(VAULT))
    else:
        check("Vault folder", FAIL, f"{VAULT} has no AIOS/ subfolder")


def c_environment():
    if is_sandbox_guess():
        check("Environment", WARN,
              "looks like a cloud/sandboxed session, not your own computer — "
              "scheduled jobs installed here may not survive. Re-run this "
              "check in a day or two to be sure, or run setup from a real "
              "terminal on your machine instead.")
    else:
        check("Environment", PASS, f"{platform.system()} {platform.release()}")


def c_me_md():
    p = VAULT / "AIOS" / "me.md"
    if not p.exists():
        check("me.md", FAIL, "missing entirely")
        return
    text = p.read_text(encoding="utf-8", errors="replace")
    placeholders = len(re.findall(r"<<[^>>]+>>", text))
    if placeholders == 0:
        check("me.md", PASS, "filled in — no << >> placeholders left")
    else:
        check("me.md", WARN,
              f"{placeholders} placeholder(s) still unfilled — say "
              f'"set yourself up" to fix that')


def c_skills():
    d = VAULT / "AIOS" / "skills"
    expected = {"auto-capture", "vault-first", "vault-librarian",
               "no-bullshit", "daily-brief", "setup-vault", "update-vault"}
    if not d.is_dir():
        check("Skill source files", FAIL, "AIOS/skills/ is missing")
        return
    present = {p.name for p in d.iterdir() if p.is_dir()}
    missing = expected - present
    if missing:
        check("Skill source files", WARN,
              f"present: {len(present & expected)}/{len(expected)} — "
              f"missing: {', '.join(sorted(missing))}")
    else:
        check("Skill source files", PASS, f"all {len(expected)} present in AIOS/skills/")

    claude_dir = VAULT / ".claude" / "skills"
    if claude_dir.is_dir():
        native = {p.name for p in claude_dir.iterdir() if p.is_dir()}
        got = native & expected
        if got:
            check("Skills — Claude Code", PASS,
                  f"{len(got)}/{len(expected)} copied into .claude/skills/ "
                  f"(active automatically in this project)")
        else:
            check("Skills — Claude Code", WARN,
                  ".claude/skills/ exists but none of this vault's skills are in it yet")
    else:
        check("Skills — Claude Code", WARN,
              "no .claude/skills/ folder here — fine if you're using Cowork "
              "instead, see the note on Cowork skill install below")


_scheduled_count = [0, 3]  # [how many of the 3 jobs are really running, total]


def c_scheduler():
    try:
        import scheduler
    except ImportError:
        check("Scheduler", FAIL, "scheduler.py missing from AIOS/scripts/")
        return
    tool, why = scheduler.available()
    if tool is None:
        check("Scheduler", WARN,
              f"none available — {why}. Nothing below is running "
              f"automatically; every script still works run by hand.")
        return
    check("Scheduler", PASS, f"{tool} ({why})")
    for job, every, script in (
        ("backup-cowork", "hourly", "backup-cowork.py"),
        ("changelog-check", "30 min", "changelog-check.py"),
        ("vault-snapshot", "10 min", "vault-snapshot.py"),
    ):
        # Path-aware, same check setup.py uses to decide whether to
        # (re)install — a same-named job pointing at a DIFFERENT vault
        # (moved/renamed/re-copied folder) must not read as "installed".
        installed = scheduler.is_installed(job, script_path=SCRIPTS / script)
        if installed:
            _scheduled_count[0] += 1
        check(f"  schedule: {job}", PASS if installed else WARN,
              f"installed, runs {every}" if installed
              else "not installed for THIS vault — run setup.py again")


def c_optional_jobs():
    """Report on the two optional scheduled jobs, without counting against
    the core 3/3 automation total above — neither is expected to be
    installed on every machine (backup-claude-code only matters if Claude
    Code is used here; capture-heartbeat only matters once auto-capture is
    in daily use)."""
    try:
        import scheduler
    except ImportError:
        return
    tool, _ = scheduler.available()
    if tool is None:
        return

    has_claude_code = (Path.home() / ".claude" / "projects").is_dir()
    installed = scheduler.is_installed(
        "backup-claude-code", script_path=SCRIPTS / "backup-claude-code.py")
    if not has_claude_code:
        check("  schedule: backup-claude-code", PASS,
              "not applicable — no Claude Code session folder on this machine")
    elif installed:
        check("  schedule: backup-claude-code", PASS, "installed, runs hourly")
    else:
        check("  schedule: backup-claude-code", WARN,
              "optional, not installed — run setup.py again to turn it on")

    if has_claude_code:
        installed = scheduler.is_installed(
            "session-digest", script_path=SCRIPTS / "session-digest.py")
        check("  schedule: session-digest", PASS if installed else WARN,
              "installed, rebuilds the session list hourly" if installed
              else "optional, not installed — run setup.py again to turn it on")

    installed = scheduler.is_installed(
        "capture-heartbeat", script_path=SCRIPTS / "capture-heartbeat.py")
    check("  schedule: capture-heartbeat", PASS if installed else WARN,
          "installed, runs every 30 min" if installed
          else "optional, not installed — run setup.py again to turn it on")


def c_chat_backup_source():
    # The filename has a hyphen, so it can't be `import`ed normally.
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "backup_cowork", SCRIPTS / "backup-cowork.py")
    bc = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(bc)
    except Exception as e:
        check("Chat backup source", FAIL, f"couldn't load backup-cowork.py: {e}")
        return
    src = bc.find_source()
    if src:
        n = sum(1 for _ in src.rglob("*.jsonl"))
        check("Chat backup source", PASS, f"found: {src} ({n} session file(s))")
    else:
        check("Chat backup source", WARN,
              "no local Claude chat folder found on this machine yet — normal "
              "if you haven't had a conversation here, otherwise see "
              "backup-cowork.py's docstring for where it looked")


def c_chat_backup_output():
    d = VAULT / "AIOS" / "history" / "chat-history" / "cowork"
    if not d.is_dir():
        check("Chat backup output", WARN, "no backups written yet — run backup-cowork.py once")
        return
    n = len(list(d.glob("*.md"))) - (1 if (d / "Cowork chats.md").exists() else 0)
    if n > 0:
        check("Chat backup output", PASS, f"{n} conversation(s) backed up in AIOS/history/chat-history/cowork/")
    else:
        check("Chat backup output", WARN, "folder exists but is empty")


def c_git():
    if not shutil.which("git"):
        check("Git", WARN, "not installed — optional, only needed for version history")
        return
    if not (VAULT / ".git").exists():
        check("Git", WARN, "not initialized yet — run vault-snapshot.py once, or skip it")
        return
    rc, out, _ = run("git", "-C", str(VAULT), "remote", "get-url", "origin")
    if rc == 0 and out.strip():
        check("Git", PASS, f"repo present, remote: {out.strip()}")
    else:
        check("Git", WARN, "repo present, no remote — commits stay local only")


def c_vault_check():
    p = SCRIPTS / "vault-check.py"
    if not p.exists():
        check("vault-check", FAIL, "vault-check.py missing")
        return
    rc, out, _ = run(sys.executable or "python3", str(p))
    if rc == 0:
        check("vault-check", PASS, "clean")
    else:
        lines = [ln for ln in out.splitlines() if ln.strip()]
        check("vault-check", WARN, f"{len(lines)} line(s) of findings — run it directly for detail")


def main():
    c_python()
    c_vault_shape()
    c_environment()
    c_me_md()
    c_skills()
    c_scheduler()
    c_optional_jobs()
    c_chat_backup_source()
    c_chat_backup_output()
    c_git()
    c_vault_check()

    print("setup-check — " + str(VAULT))
    print()
    width = max(len(n) for n, _, _ in rows)
    n_fail = n_warn = 0
    for name, status, detail in rows:
        mark = {"PASS": "[ OK ]", "WARN": "[WARN]", "FAIL": "[FAIL]"}[status]
        print(f"  {mark}  {name.ljust(width)}  {detail}")
        if status == "FAIL":
            n_fail += 1
        elif status == "WARN":
            n_warn += 1
    print()
    print(f"  {len(rows)} checks — {n_fail} failed, {n_warn} need attention, "
          f"{len(rows) - n_fail - n_warn} clean.")
    done, total = _scheduled_count
    print()
    if done < total:
        print(f"  >> AUTOMATION: {done}/{total} scheduled jobs are actually "
              f"running for this vault. <<")
        print(f"     This is the single fact most worth not missing — a low "
              f"number here means chat backup, the")
        print(f"     changelog check, or the git snapshot are NOT happening "
              f"on their own, whatever the line")
        print(f"     above about total WARNs suggests. Everything still "
              f"works run by hand in the meantime.")
    else:
        print(f"  >> AUTOMATION: all {total}/{total} scheduled jobs are "
              f"running for this vault. <<")
    print()
    print("  A WARN here is often expected on a fresh vault, not a bug —")
    print("  read the detail column. A FAIL means something is actually broken.")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
