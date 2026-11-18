#!/usr/bin/env python3
"""
vault-snapshot.py — commit the vault to git and push it to GitHub (or any
remote), on a timer, without Obsidian being involved at all.

WHY THIS EXISTS
---------------
Obsidian's own Git plugin (if you use it) only commits WHILE OBSIDIAN IS
OPEN. Close Obsidian and the vault stops being versioned — and if your AI
writes to the vault with Obsidian shut, none of that gets committed either.
A timer that runs independently of any app fixes that.

This is entirely optional. Nothing else in this vault requires git. It exists
because plain-text files in a synced folder (Dropbox etc.) already protect
you against most disasters, but git adds full history and an off-machine copy
if you also push to a remote.

SETUP (one-time, by hand — a script should never invent credentials for you)
------------------------------------------------------------------------------
  1. `cd` into the vault folder and run `git init` if `.git` doesn't exist yet
     (this script does that for you automatically on first run).
  2. Optional: create an empty repo on GitHub (or GitLab, or your own server)
     and add it as a remote:
       git remote add origin git@github.com:YOU/YOUR-REPO.git
     Use the SSH URL, not HTTPS — GitHub stopped accepting plain passwords
     for git in 2021, and an HTTPS remote will fail every push with a
     confusing auth error until you set up a token instead. SSH just works
     once your key is on your GitHub account.

USAGE
-----
    python3 AIOS/scripts/vault-snapshot.py              # commit + push now
    python3 AIOS/scripts/vault-snapshot.py --check      # report only, no writes
    python3 AIOS/scripts/vault-snapshot.py --no-push    # commit locally only
    python3 AIOS/scripts/vault-snapshot.py --install-schedule --every-min 10

Exits non-zero when the snapshot did not fully succeed, so a scheduler and any
caller can tell the difference between "pushed" and "quietly did nothing".

No dependencies beyond `git` itself. Plain stdlib otherwise.
"""
import scriptlog  # noqa: F401 -- logs this run to AIOS/history/scripts/

# aios-run: cron  (hourly by default, plus by hand any time you want to check)

import argparse
import datetime as dt
import re
import shutil
import subprocess
import sys
from pathlib import Path

VAULT = Path(__file__).resolve().parent.parent.parent
STATUS_NOTE = VAULT / "AIOS" / "generated" / "git-status.md"

NEVER_COMMIT = ("Privat/",)

GIT_MISSING_MSG = ("git isn't installed on this machine — version history is off. "
                   "Install git (Debian/Ubuntu/Mint: sudo apt install git), then run "
                   "this script again. Nothing else in the vault needs it.")
GIT_IDENTITY_HINT = ("\n\n  ← git doesn't know who you are yet. Run these two lines once, "
                     "with your own name and email, then run this script again:\n"
                     '        git config --global user.name "Your Name"\n'
                     '        git config --global user.email "you@example.com"')


def git(*args, timeout=120):
    """Run one git command inside the vault. Never raises."""
    cmd = ["git", "-C", str(VAULT), *args]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout.strip(), p.stderr.strip()
    except FileNotFoundError:
        return 127, "", "git is not installed on this machine"
    except subprocess.TimeoutExpired:
        return 124, "", f"git {args[0]} timed out after {timeout}s"


def clear_stale_lock(max_age_seconds: int = 300) -> str | None:
    """Remove `.git/index.lock` if it's old enough to be safely assumed dead.

    WHY THIS EXISTS
    ----------------
    Found 2026-08-29: a single interrupted git process (this vault's own
    tooling got killed mid-`git commit`) left `.git/index.lock` behind, and
    every run after that — every 10 minutes, for 1.5 days — failed with
    "Unable to create '.git/index.lock': File exists" and quietly wrote
    BROKEN into a generated note nobody was reading. The push pipeline
    doesn't come back from that on its own; someone has to notice the note
    and delete the file by hand.

    A lock file genuinely held by a running git process is always younger
    than this script's own runs — every git call here finishes in seconds.
    So a lock older than `max_age_seconds` (default 5 min — an order of
    magnitude more than any real operation needs, well under the 10-minute
    cron cadence) is never a live process; it's a corpse. Clearing it is the
    same fix git's own error message tells a human to do by hand:

        "If it still fails, a git process may have crashed in this
         repository earlier: remove the file manually to continue."

    Returns a one-line note for the status report if a lock was cleared,
    else None.
    """
    lock = VAULT / ".git" / "index.lock"
    if not lock.exists():
        return None
    try:
        age = dt.datetime.now().timestamp() - lock.stat().st_mtime
    except OSError:
        return None
    if age < max_age_seconds:
        # Young enough that a concurrent git process could genuinely hold
        # it — leave it alone rather than race a real operation.
        return None
    try:
        lock.unlink()
    except OSError as e:
        return f"stale lock found (age {age / 60:.0f}m) but could not remove it: {e}"
    return f"cleared a stale .git/index.lock (age {age / 60:.0f}m) before running — see docstring"


def ensure_repo() -> tuple:
    """git init if there's no repo yet. Returns (ok, message)."""
    if (VAULT / ".git").exists():
        return True, "existing repo"
    rc, out, err = git("init")
    if rc != 0:
        return False, f"git init failed: {err}"
    # A sensible default .gitignore if the blueprint's own is missing for
    # some reason — Privat/ must never be trackable even by accident.
    gi = VAULT / ".gitignore"
    if not gi.exists():
        gi.write_text("Privat/\n.obsidian/workspace.json\n__pycache__/\n*.pyc\n",
                      encoding="utf-8")
    return True, "initialized a new repo"


def collect() -> dict:
    s = {
        "checked": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "repo_ok": False,
        "branch": None,
        "remote": None,
        "remote_kind": None,
        "last_commit": None,
        "last_commit_at": None,
        "last_commit_age_days": None,
        "dirty_files": 0,
        "unpushed": None,
        "errors": [],
        "notes": [],
    }

    if not (VAULT / ".git").exists():
        s["errors"].append(GIT_MISSING_MSG if shutil.which("git") is None
                           else "no git repo here yet — run this script once to create one")
        return s

    lock_note = clear_stale_lock()
    if lock_note:
        (s["notes"] if "could not remove" not in lock_note else s["errors"]).append(lock_note)

    rc, _, err = git("rev-parse", "--git-dir")
    if rc != 0:
        s["errors"].append(f"not a usable git repo: {err}")
        return s
    s["repo_ok"] = True

    rc, out, _ = git("rev-parse", "--abbrev-ref", "HEAD")
    if rc == 0:
        s["branch"] = out

    rc, out, _ = git("remote", "get-url", "origin")
    if rc == 0 and out:
        s["remote"] = out
        s["remote_kind"] = "ssh" if out.startswith("git@") or out.startswith("ssh://") else "https"
    # No remote is a normal, non-broken state (verdict() reports it as
    # "LOCAL ONLY", not an error) — plenty of people just want local history.

    rc, out, _ = git("log", "-1", "--format=%h|%cI|%s")
    if rc == 0 and "|" in out:
        h, iso, subj = out.split("|", 2)
        s["last_commit"] = f"{h} {subj}"
        s["last_commit_at"] = iso
        try:
            when = dt.datetime.fromisoformat(iso)
            now = dt.datetime.now(when.tzinfo)
            s["last_commit_age_days"] = round((now - when).total_seconds() / 86400, 1)
        except ValueError:
            pass
    else:
        s["errors"].append("no commits in the repo yet")

    rc, out, _ = git("status", "--porcelain")
    if rc == 0:
        s["dirty_files"] = len([ln for ln in out.splitlines() if ln.strip()])

    if s["branch"] and s["remote"]:
        rc, out, _ = git("rev-list", "--count", f"origin/{s['branch']}..HEAD")
        if rc == 0 and out.isdigit():
            s["unpushed"] = int(out)
        else:
            s["errors"].append(
                f"can't compare against origin/{s['branch']} — "
                "the branch has probably never been pushed"
            )
    return s


def snapshot(push=True) -> dict:
    ok, msg = ensure_repo()
    if not ok:
        return {"checked": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
                "repo_ok": False, "errors": [msg], "dirty_files": 0,
                "unpushed": None}

    s = collect()
    if not s["repo_ok"]:
        return s
    s["errors"] = []

    for bad in NEVER_COMMIT:
        rc, out, _ = git("status", "--porcelain", "--", bad)
        if rc == 0 and out.strip():
            s["errors"].append(
                f"REFUSING TO COMMIT — {bad} has staged/unstaged changes. "
                "That folder must never enter git. Check .gitignore."
            )
            return s

    if s["dirty_files"]:
        rc, _, err = git("add", "-A")
        if rc != 0:
            s["errors"].append(f"git add failed: {err}")
            return s
        stamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        rc, _, err = git("commit", "-m", f"vault snapshot: {stamp}")
        if rc != 0 and "nothing to commit" not in (err or "").lower():
            low = (err or "").lower()
            hint = GIT_IDENTITY_HINT if ("identity unknown" in low or "tell me who you are" in low) else ""
            s["errors"].append(f"git commit failed: {err}{hint}")
            return s
        s["committed"] = s["dirty_files"]

    if push and s["remote"]:
        branch = s["branch"] or "main"
        rc, _, err = git("push", "origin", f"HEAD:{branch}", timeout=180)
        if rc != 0:
            hint = ""
            low = (err or "").lower()
            if "authentication" in low or "invalid username" in low or "password" in low:
                hint = ("  ← GitHub has not accepted passwords for git since "
                        "2021. Switch the remote to SSH instead.")
            elif "could not read from remote" in low or "permission denied" in low:
                hint = "  ← the SSH key on this machine isn't on your GitHub account yet."
            s["errors"].append(f"git push failed: {err}{hint}")
        else:
            s["pushed_at"] = dt.datetime.now().strftime("%Y-%m-%d %H:%M")

    after = collect()
    after["errors"] = s["errors"] + after["errors"]
    after["notes"] = s.get("notes", []) + after.get("notes", [])
    for k in ("committed", "pushed_at"):
        if k in s:
            after[k] = s[k]
    return after


def verdict(s: dict) -> tuple:
    if s["errors"] and not s.get("repo_ok", True):
        if shutil.which("git") is None:
            return "NOT SET UP", GIT_MISSING_MSG
        return "NOT SET UP", "No git repo yet — run this script once to create one."
    if s["errors"]:
        return "BROKEN", "The vault is NOT fully backed up by git."
    if s.get("unpushed"):
        return "BEHIND", f"{s['unpushed']} commit(s) committed locally but not pushed."
    if s["dirty_files"]:
        return "BEHIND", f"{s['dirty_files']} changed file(s) not committed."
    age = s.get("last_commit_age_days")
    if age is not None and age > 2:
        return "STALE", f"Last snapshot was {age} days ago."
    if not s.get("remote"):
        return "LOCAL ONLY", "Committing fine, but no remote — nothing leaves this machine."
    return "OK", "Everything committed and pushed."


def write_status_note(s: dict) -> None:
    head, detail = verdict(s)
    callout = {"OK": "success", "LOCAL ONLY": "info", "BEHIND": "warning",
              "STALE": "warning", "BROKEN": "danger",
              "NOT SET UP": "info"}[head]

    lines = [
        "---", "title: git-status", "tags:", "  - reference", "  - generated",
        f"confirmed: {dt.date.today().isoformat()}", "---", "",
        "# git-status", "",
        "> [!info] Generated — do not edit by hand",
        "> Rewritten by `python3 AIOS/scripts/vault-snapshot.py` on every run.",
        "> This is optional version history for the vault — nothing else here",
        "> depends on it working.",
        "",
        f"> [!{callout}] {head} — {detail}",
        f"> Checked **{s['checked']}**.",
        "",
        "| | |", "|---|---|",
        f"| Branch | `{s.get('branch') or '—'}` |",
        f"| Remote | `{s.get('remote') or 'NONE — local commits only'}` |",
        f"| Remote type | {s.get('remote_kind') or '—'} |",
        f"| Last commit | {s.get('last_commit') or '— none —'} |",
        f"| Last commit at | {s.get('last_commit_at') or '—'} |",
    ]
    if s.get("last_commit_age_days") is not None:
        lines.append(f"| Age | {s['last_commit_age_days']} days |")
    lines += [
        f"| Uncommitted files | {s.get('dirty_files', 0)} |",
        f"| Unpushed commits | {s['unpushed'] if s.get('unpushed') is not None else 'unknown'} |",
    ]
    if s.get("committed"):
        lines.append(f"| Committed this run | {s['committed']} file(s) |")
    if s.get("pushed_at"):
        lines.append(f"| Pushed at | {s['pushed_at']} |")

    if s["errors"]:
        lines += ["", "## Notes", ""] + [f"- {e}" for e in s["errors"]]
    if s.get("notes"):
        lines += ["", "## Self-healed", ""] + [f"- {n}" for n in s["notes"]]

    lines += [
        "", "## Related", "", "- [[Home]]", "",
    ]
    STATUS_NOTE.parent.mkdir(parents=True, exist_ok=True)
    STATUS_NOTE.write_text("\n".join(lines), encoding="utf-8")


def print_report(s: dict) -> None:
    head, detail = verdict(s)
    print(f"\n  {head} — {detail}\n")
    print(f"  branch           {s.get('branch') or '—'}")
    print(f"  remote           {s.get('remote') or 'NONE'}  ({s.get('remote_kind') or '—'})")
    print(f"  last commit      {s.get('last_commit') or '— none —'}")
    print(f"  uncommitted      {s.get('dirty_files', 0)} file(s)")
    print(f"  unpushed         {s['unpushed'] if s.get('unpushed') is not None else 'unknown'}")
    if s.get("committed"):
        print(f"  committed now    {s['committed']} file(s)")
    if s.get("pushed_at"):
        print(f"  pushed at        {s['pushed_at']}")
    for e in s["errors"]:
        print(f"\n  NOTE  {e}")
    for n in s.get("notes", []):
        print(f"\n  SELF-HEALED  {n}")
    print(f"\n  written to       {STATUS_NOTE.relative_to(VAULT)}\n")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--no-push", action="store_true")
    ap.add_argument("--install-schedule", "--install-cron", dest="install_schedule",
                    action="store_true")
    ap.add_argument("--every-min", type=int, default=10, metavar="N")
    a = ap.parse_args()

    if a.install_schedule:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import scheduler  # noqa: E402
        ok, detail = scheduler.install("vault-snapshot", Path(__file__),
                                       every_minutes=a.every_min)
        print(("Installed. " if ok else "Could NOT install automatically. ") + detail)
        return 0 if ok else 1

    if not (VAULT / "AIOS").is_dir():
        print(f"{VAULT} is not the vault — no AIOS/ folder in it", file=sys.stderr)
        return 2

    s = collect() if a.check else snapshot(push=not a.no_push)
    write_status_note(s)
    print_report(s)

    head, _ = verdict(s)
    return 0 if head in ("OK", "LOCAL ONLY", "NOT SET UP") else 1


if __name__ == "__main__":
    sys.exit(main())
