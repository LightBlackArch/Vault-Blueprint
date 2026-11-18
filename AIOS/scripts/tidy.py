#!/usr/bin/env python3
"""
tidy.py — the `tidy` routine as one command: a housekeeping list for the vault.

REPORTS ONLY. CHANGES NOTHING. It runs three checks the vault already has and
prints what they found under one heading each, so you can say which items to
act on:

  - Possible duplicate notes         -> route-check.py --dupes
  - Orphan notes (nothing links in)  -> stale-check.py, the [ORPHAN] section
  - Broken links, bad frontmatter,   -> vault-check.py, passed through
    index coverage, status values

Usage:
    python3 AIOS/scripts/tidy.py
    python3 AIOS/scripts/tidy.py --selftest

Exit 0 when the report ran, whether or not it found anything: the findings ARE
the output. Exit 1 only if one of the three checks could not run at all.

No dependencies beyond the sibling scripts. Plain stdlib. Never reads Privat/
(the three checks skip it themselves). Deliberately does not log its own run
under AIOS/history/scripts/, so tidy itself writes nothing. The one file a pass
can touch is route-check's usual git-ignored scratch cache,
AIOS/scripts/.route-cache.json; no note or setting is ever changed.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
VAULT = os.path.abspath(os.path.join(HERE, "..", ".."))


def run(script, *args):
    """Run a sibling script, return (exit_code, output). Never raises.

    Exit codes 0 and 1 are the checks' own "clean" / "found something"; anything
    else means the check itself broke, which tidy reports as a failure.
    """
    path = os.path.join(HERE, script)
    try:
        p = subprocess.run([sys.executable, path, *args],
                           capture_output=True, text=True, cwd=VAULT)
    except OSError as e:
        return 2, f"tidy: could not run {script}: {e}"
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def broke(code, out):
    """A check broke if it exited above 1, or crashed (a traceback exits 1 too)."""
    return code > 1 or "Traceback (most recent call last)" in out


def extract_section(stale_output, section):
    """Pull just the '[SECTION]' block out of stale-check.py's output."""
    out, inside = [], False
    for line in stale_output.splitlines():
        s = line.strip()
        if s == f"[{section}]":
            inside = True
        elif inside and s.startswith("[") and s.endswith("]"):
            break
        elif inside:
            out.append(line)
    return out


def selftest():
    sample = ("[EXPIRED]\n  - a.md\n[ORPHAN]\n  - b.md\n  - c.md\n[NO ROUTE]\n  - d/\n")
    assert extract_section(sample, "ORPHAN") == ["  - b.md", "  - c.md"]
    assert extract_section(sample, "MISSING") == []
    assert run("no-such-script.py")[0] != 0
    assert broke(1, "Traceback (most recent call last):") and not broke(1, "found 2") and broke(2, "")
    print("tidy selftest: ok")
    return 0


def main():
    if sys.argv[1:] == ["--selftest"]:
        return selftest()

    failed = []
    print(f"tidy — housekeeping pass over {VAULT}")
    print("Reports only. Nothing below has been changed.")
    print()

    code, out = run("route-check.py", "--dupes")
    print("## Possible duplicate notes  (route-check.py --dupes)")
    print(out.strip() or "_(none)_")
    print()
    if broke(code, out):
        failed.append("route-check.py")

    code, out = run("stale-check.py")
    print("## Orphan notes — nothing links to them  (stale-check.py)")
    orphans = extract_section(out, "ORPHAN")
    print("\n".join(orphans) if orphans else "_(none)_")
    print()
    if broke(code, out):
        failed.append("stale-check.py")

    code, out = run("vault-check.py")
    print("## Vault integrity — links, frontmatter, index, status values  (vault-check.py)")
    print(out.strip() or "_(none)_")
    print()
    if broke(code, out):
        failed.append("vault-check.py")

    print("---")
    if failed:
        print(f"tidy: could not run {', '.join(failed)} — see the output above.")
        return 1
    print("tidy: that is the list. Nothing was changed — say what to act on.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
