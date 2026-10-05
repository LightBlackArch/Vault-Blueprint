#!/usr/bin/env python3
"""
setup.py — make this computer into a working vault machine. Cross-platform:
Linux, macOS and Windows are all first-class here, not "Linux, and Windows if
you're lucky."

    python3 AIOS/scripts/setup.py            # set this machine up
    python3 AIOS/scripts/setup.py --check    # say what's missing, change nothing

What it does
------------
  1. Checks Python is new enough.
  2. Creates the folders the automation writes into.
  3. Finds a scheduler for this OS (cron on Linux/macOS, Task Scheduler on
     Windows) and, if one exists, installs these recurring jobs — none
     duplicated if already present:
       - the chat backup (backup-cowork.py), hourly
       - the changelog safety net (changelog-check.py), every 30 min
       - the git snapshot (vault-snapshot.py), every 10 min — only if git
         is installed; entirely optional, see that script's own docstring
       - the Claude Code session backup (backup-claude-code.py), hourly —
         only if this machine has ever run Claude Code (a `~/.claude/projects`
         folder exists); optional, does nothing if that tool isn't used here
       - the capture heartbeat (capture-heartbeat.py), every 30 min —
         optional, only useful once you're actually using the `auto-capture`
         skill day to day
  4. Runs the vault's own health check and prints the result.
  5. Prints exactly what still needs a human — installing an app, signing
     into an account. A script that half-installs something with sudo is
     worse than one that hands you the one command to run yourself.

Everything it does is safe to repeat. It never deletes and never overwrites a
note.

IMPORTANT — read this if you're running this from an AI chat session
-----------------------------------------------------------------------
If the AI running this is working inside a cloud sandbox rather than on your
own computer, everything below still *runs* without error, but the cron job
/ scheduled task it installs lives inside a disposable container that gets
thrown away — so the backup will look "installed" and then simply never fire
again. There is no way for a script to detect this with certainty, which is
why `AIOS/scripts/setup-check.py` exists: run it again in a day or two and
check the jobs are still there. If they vanished, this needs to run in a
terminal on your actual computer instead (Claude Code, or Cowork's "on this
device" mode, not a cloud/hosted session).

No dependencies. Plain stdlib.
"""
import scriptlog  # noqa: F401 -- logs this run to AIOS/history/scripts/

import platform
import shutil
import subprocess
import sys
from pathlib import Path

VAULT = Path(__file__).resolve().parent.parent.parent
SCRIPTS = VAULT / "AIOS" / "scripts"
CODE = VAULT / "AIOS" / "code"

sys.path.insert(0, str(SCRIPTS))



def _linux_install(pkg):
    """The install line for THIS distro, not just Debian's."""
    for exe, line in (("pacman", "sudo pacman -S "), ("dnf", "sudo dnf install "),
                      ("zypper", "sudo zypper install "), ("apt", "sudo apt install ")):
        if shutil.which(exe):
            return line + pkg
    return "sudo apt install " + pkg

def ok(msg):
    print(f"  [ok]   {msg}")


def todo(msg, cmd=None):
    print(f"  [YOU]  {msg}")
    if cmd:
        print(f"           {cmd}")


def fail(msg):
    print(f"  [!!]   {msg}")


def check_python():
    v = sys.version_info
    if v >= (3, 8):
        ok(f"Python {v.major}.{v.minor}.{v.micro}")
        return True
    fail(f"Python {v.major}.{v.minor} is too old — need 3.8 or newer")
    system = platform.system()
    if system == "Darwin":
        todo("Install a newer Python:", "brew install python3")
    elif system == "Windows":
        todo("Install a newer Python:", "https://www.python.org/downloads/windows/")
    else:
        todo("Install a newer Python:", _linux_install("python3" if shutil.which("apt") else "python"))
    return False


def make_folders(dry):
    made = []
    for d in (
        VAULT / "AIOS" / "history" / "chat-history" / "cowork",
        VAULT / "AIOS" / "history" / "chat-history" / "cowork-raw",
        VAULT / "AIOS" / "history" / "chat-history" / "claude-code",
        VAULT / "AIOS" / "history" / "chat-history" / "claude-code-raw",
        VAULT / "AIOS" / "history" / "screenshots",
        VAULT / "AIOS" / "history" / "scripts",
        VAULT / "AIOS" / "generated",
        VAULT / "AIOS" / "reference",
        VAULT / "AIOS" / "archive",
        CODE,
        VAULT / "Inbox" / "Screenshots",
        VAULT / "Inbox" / "Files",
    ):
        if d.exists():
            continue
        made.append(str(d.relative_to(VAULT)))
        if not dry:
            d.mkdir(parents=True, exist_ok=True)
    if made:
        ok(("would create " if dry else "created ") + ", ".join(made))
    else:
        ok("all folders already exist")


def install_job(name, script, every_min, dry, required=True):
    import scheduler
    path = SCRIPTS / script
    if not path.exists():
        (fail if required else todo)(f"{script} is missing from AIOS/scripts/ — skipping")
        return

    tool, why = scheduler.available()
    if tool is None:
        fail(f"no scheduler on this machine for {name} — {why}")
        todo(f"Run it by hand from time to time instead:",
             f'python3 "{path}"')
        return

    if scheduler.is_installed(name, script_path=path):
        ok(f"{name} is already scheduled ({tool}), pointing at this vault")
        return

    if dry:
        todo(f"{name} is NOT correctly scheduled yet for this vault "
             f"(a differently-pathed job with the same name doesn't count)",
             f'python3 "{path}" --install-schedule --every-min {every_min}')
        return

    ok_install, detail = scheduler.install(name, path, every_minutes=every_min)
    if ok_install:
        ok(f"scheduled {name} — {detail}")
    else:
        fail(f"couldn't schedule {name} automatically: {detail}")
        todo("Run this yourself and read what it says:",
             f'python3 "{path}" --install-schedule --every-min {every_min}')


def run_checks():
    for name in ("vault-check.py", "canon-check.py"):
        p = SCRIPTS / name
        if not p.exists():
            continue
        r = subprocess.run([sys.executable or "python3", str(p)],
                           capture_output=True, text=True)
        state = "clean" if r.returncode == 0 else "found something"
        print(f"  [ok]   {name}: {state}")
        if r.returncode != 0:
            tail = [ln for ln in (r.stdout or "").splitlines() if ln.strip()][-4:]
            for ln in tail:
                print(f"           {ln}")


def manual_steps():
    system = platform.system()
    print()
    print("  Things a script must not do for you:")
    print()
    if system == "Darwin":
        print("   * Obsidian: https://obsidian.md — download the macOS build.")
    elif system == "Windows":
        print("   * Obsidian: https://obsidian.md — download the Windows build.")
    else:
        print("   * Obsidian: https://obsidian.md — or your distro's package,")
        print("     e.g. flatpak install flathub md.obsidian.Obsidian")
    print("     Then: Open folder as vault -> this folder.")
    print("   * Claude (Cowork or Claude Code), if it isn't already what you're")
    print("     using to read this: https://claude.ai/download")
    print("   * A sync folder (Dropbox, Syncthing, iCloud Drive...) if you want")
    print("     this vault to reach more than one machine. Optional.")
    print("   * git, only if you want the optional version-history snapshot:")
    if system == "Darwin":
        print("       xcode-select --install")
    elif system == "Windows":
        print("       https://git-scm.com/download/win")
    else:
        print("       " + _linux_install("git"))


def do_setup(dry):
    print("Vault setup — this machine" + (" (dry run)" if dry else ""))
    print(f"  vault:  {VAULT}")
    print(f"  system: {platform.system()} {platform.release()}")
    print()
    if not (VAULT / "AIOS").is_dir():
        fail(f"{VAULT} is not the vault — no AIOS/ folder in it")
        return 1

    check_python()
    make_folders(dry)

    import scheduler
    tool, why = scheduler.available()
    if tool:
        ok(f"scheduler available: {tool} ({why})")
    else:
        fail(f"no scheduler available on this machine — {why}")
        print("           Automation (chat backup, etc.) will need to be run")
        print("           by hand until this is fixed.")

    install_job("backup-cowork", "backup-cowork.py", 60, dry)
    install_job("changelog-check", "changelog-check.py", 30, dry)
    if shutil.which("git"):
        install_job("vault-snapshot", "vault-snapshot.py", 10, dry, required=False)
    else:
        todo("git isn't installed — skipping the optional version-history "
             "snapshot. Install git any time and re-run this to turn it on.")

    if (Path.home() / ".claude" / "projects").is_dir():
        install_job("backup-claude-code", "backup-claude-code.py", 60, dry,
                     required=False)
    else:
        todo("no Claude Code session folder found on this machine — skipping "
             "the optional Claude Code chat backup. Safe to ignore if you "
             "only use Cowork/Claude Desktop.")

    install_job("capture-heartbeat", "capture-heartbeat.py", 30, dry,
                 required=False)

    run_checks()
    manual_steps()
    print()
    print("  Done." if not dry else "  Nothing was changed.")
    print()
    print("  Now run: python3 AIOS/scripts/setup-check.py")
    print("  for the full picture of what's actually working.")
    return 0


def main():
    return do_setup(dry="--check" in sys.argv or "--dry-run" in sys.argv)


if __name__ == "__main__":
    sys.exit(main())
