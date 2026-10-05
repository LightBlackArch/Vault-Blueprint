#!/usr/bin/env python3
"""
blueprint-release.py — the gate every blueprint change has to get through
before anyone downstream sees it.

Run this in the BLUEPRINT folder after changing anything in it, before pushing.

    python3 AIOS/scripts/blueprint-release.py            # check, then write
    python3 AIOS/scripts/blueprint-release.py --check    # check only
    python3 AIOS/scripts/blueprint-release.py --push     # ...and git push

WHY THIS EXISTS
---------------
The update system has one failure mode that kills it quietly: a change ships
with no plain-English description. Downstream, someone sees

    [4] UPDATE  logchange.py — updates the script logchange.py

...and declines it, because who wouldn't. Do that three times and they stop
running updates at all. The system then looks like it's working — it fetches,
it lists, it exits 0 — while delivering nothing.

So this refuses to pass a release where a changed *system* file isn't spoken
for by an entry in `AIOS/reference/blueprint-changes.md`. It is a nag on
purpose. Writing three sentences about what a change does for a human is the
entire product; the code is just plumbing.

WHAT IT CHECKS
--------------
  1. Every .py file compiles.
  2. The manifest is current (regenerates it).
  3. Every changed or added system file is covered by a changes entry.
  4. No entry points at a file that doesn't exist (a typo'd path silently
     un-describes a change).
  5. No duplicate ids, no id renamed from one that already shipped — a
     renamed id re-asks everybody who already declined it.
  6. Nothing personal leaked, if a denylist is available.
"""
try:
    import scriptlog  # noqa: F401
except Exception:
    pass

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
CHANGES = ROOT / "AIOS" / "reference" / "blueprint-changes.md"
MANIFEST = ROOT / "AIOS" / "config" / "blueprint-manifest.json"

OK, BAD = "[ ok ]", "[ !! ]"
fails = []


def say(good, msg):
    print(f"{OK if good else BAD} {msg}")
    if not good:
        fails.append(msg)


def git(*a):
    r = subprocess.run(["git", "-C", str(ROOT), *a],
                       capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def parse_entries():
    if not CHANGES.exists():
        return {}
    out, cur, fenced = {}, None, False
    for line in CHANGES.read_text(encoding="utf-8").splitlines():
        if line.lstrip().startswith("```"):
            fenced = not fenced          # skip the format example
            continue
        if fenced:
            continue
        m = re.match(r"^###\s+id:\s*(\S+)", line.strip())
        if m:
            cur = m.group(1)
            out[cur] = {"files": [], "title": "", "body": 0}
            continue
        if not cur:
            continue
        if line.startswith("## "):
            cur = None
            continue
        m = re.match(r"^files:\s*(.*)$", line.strip(), re.I)
        if m:
            out[cur]["files"] = [f.strip() for f in m.group(1).split(",") if f.strip()]
        m = re.match(r"^title:\s*(.*)$", line.strip(), re.I)
        if m:
            out[cur]["title"] = m.group(1).strip()
        if line.strip() and not re.match(r"^(title|files|needs):", line.strip(), re.I):
            out[cur]["body"] += len(line.split())
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="don't write anything")
    ap.add_argument("--push", action="store_true", help="commit and push if clean")
    ap.add_argument("--since", default="HEAD",
                    help="what to diff against (default: uncommitted changes)")
    args = ap.parse_args()

    print(f"\nBlueprint release check — {ROOT}\n")

    # 1. everything compiles
    pys = sorted((ROOT / "AIOS" / "scripts").glob("*.py"))
    bad = []
    for p in pys:
        r = subprocess.run([sys.executable, "-m", "py_compile", str(p)],
                           capture_output=True, text=True)
        if r.returncode != 0:
            bad.append(f"{p.name}: {r.stderr.strip().splitlines()[-1]}")
    say(not bad, f"{len(pys)} scripts compile" if not bad
        else "scripts failed to compile: " + "; ".join(bad))

    # 2. manifest current
    r = subprocess.run([sys.executable,
                        str(ROOT / "AIOS/scripts/blueprint-manifest.py"), "--check"],
                       capture_output=True, text=True)
    if r.returncode != 0 and not args.check:
        subprocess.run([sys.executable,
                        str(ROOT / "AIOS/scripts/blueprint-manifest.py")],
                       capture_output=True, text=True)
        say(True, "manifest was stale — regenerated")
    else:
        say(r.returncode == 0, "manifest is current" if r.returncode == 0
            else "manifest is stale — run blueprint-manifest.py")

    manifest = {}
    if MANIFEST.exists():
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8")).get("files", {})

    # 3-5. described changes
    entries = parse_entries()
    say(bool(entries), f"{len(entries)} change entries in blueprint-changes.md"
        if entries else "no change entries found — blueprint-changes.md is empty "
                        "or unparseable")

    described = set()
    for cid, e in entries.items():
        for f in e["files"]:
            described.add(f)
            if not (ROOT / f).exists():
                say(False, f"entry '{cid}' names {f}, which doesn't exist — "
                           f"a typo here silently un-describes the change")
        if e["body"] < 15:
            say(False, f"entry '{cid}' has almost no body ({e['body']} words). "
                       f"Write what it does for a person, or they'll decline it")
        if not e["title"]:
            say(False, f"entry '{cid}' has no title:")

    # which system files actually changed
    changed = set()
    porcelain = git("status", "--porcelain")
    for line in porcelain.splitlines():
        f = line[3:].strip().strip('"')
        if "->" in f:
            f = f.split("->")[-1].strip()
        changed.add(f)
    if args.since != "HEAD":
        for f in git("diff", "--name-only", args.since, "HEAD").splitlines():
            changed.add(f.strip())

    undescribed = sorted(
        f for f in changed
        if manifest.get(f, {}).get("class") == "system"
        and f not in described
        and not f.startswith("AIOS/config/")
    )
    if undescribed:
        say(False, f"{len(undescribed)} changed system file(s) have no entry in "
                   f"blueprint-changes.md:")
        for f in undescribed:
            print(f"         {f}")
        print("\n       Downstream this reads as \"updates the script "
              "<name>\", which nobody says yes to.\n       Add a block to "
              "AIOS/reference/blueprint-changes.md — the format is at the "
              "top of that file.")
    else:
        say(True, "every changed system file is described in plain English")

    # 6. nothing personal, if a denylist is reachable
    deny = None
    for cand in (Path(os.environ["BLUEPRINT_DENYLIST"]) if os.environ.get("BLUEPRINT_DENYLIST") else ROOT / "nope",
                 ROOT.parent / "AI-OS" / "AIOS" / "config" / "blueprint-denylist.txt",
                 ROOT.parent / "Ai Os" / "AIOS" / "config" / "blueprint-denylist.txt",
                 ROOT / "AIOS" / "config" / "blueprint-denylist.txt"):
        if cand.exists():
            deny = cand
            break
    if deny:
        terms = [l.strip() for l in deny.read_text(encoding="utf-8").splitlines()
                 if l.strip() and not l.startswith("#")]
        allowed = []
        allow_file = ROOT / "AIOS" / "config" / "blueprint-allowed.txt"
        if allow_file.exists():
            for l in allow_file.read_text(encoding="utf-8").splitlines():
                l = l.strip()
                if not l or l.startswith("#") or "::" not in l:
                    continue
                g, rx = (x.strip() for x in l.split("::", 1))
                allowed.append((g, rx))
        # The allowlist necessarily contains the terms it allows, so scanning
        # it always hits. Rather than exempt it quietly — which is exactly
        # where a real leak would hide — print the whole thing every run so
        # it gets read every time.
        if allowed:
            print(f"       {len(allowed)} documented exception(s) — read them:")
            for g, rx in allowed:
                print(f"         {g}  ::  {rx}")

        skip = ("/.git/", "__pycache__", "/Privat/", "AIOS/history/",
                "AIOS/generated/", ".pyc", "blueprint-allowed.txt")
        hits = []
        for p in ROOT.rglob("*"):
            rel = p.relative_to(ROOT).as_posix() if p.is_file() else ""
            if not p.is_file() or any(s.strip("/") in p.as_posix() for s in skip):
                continue
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            for t in terms:
                try:
                    m = re.search(t, text, re.I)
                except re.error:
                    continue
                if not m:
                    continue
                ctx = text[max(0, m.start() - 30):m.end() + 30]
                if any((g == "*" or g == rel or rel.startswith(g.rstrip("*")))
                       and re.search(rx, ctx, re.I) for g, rx in allowed):
                    continue
                hits.append(f"{rel}: /{t}/ → {ctx!r}")
        say(not hits, "denylist scan clean" if not hits
            else f"DENYLIST HIT — {len(hits)} match(es). Do not push:")
        for h in hits[:20]:
            print(f"         {h}")
    else:
        print(f"[ -- ] denylist NOT scanned — none found next to the blueprint. "
              f"Fine for anyone but the original author; if that's you, set "
              f"BLUEPRINT_DENYLIST=/path/to/blueprint-denylist.txt and re-run "
              f"before pushing.")

    print()
    if fails:
        print(f"{len(fails)} problem(s). Fix them, then re-run.\n")
        return 1

    print("Clean. Safe to push.\n")
    if args.push and not args.check:
        n = len([l for l in git("status", "--porcelain").splitlines() if l])
        if not n:
            print("Nothing to commit.")
            return 0
        titles = [e["title"] for e in entries.values() if e["title"]]
        msg = titles[0] if titles else "blueprint update"
        add = subprocess.run(["git", "-C", str(ROOT), "add", "-A"],
                             capture_output=True, text=True)
        if add.returncode != 0:
            print(f"{BAD} git add failed: {add.stderr.strip()}")
            return 1
        com = subprocess.run(["git", "-C", str(ROOT), "commit", "-m", msg],
                             capture_output=True, text=True)
        if com.returncode != 0:
            # Never carry on to push after a failed commit — that pushes the
            # PREVIOUS state and prints a success line for work that isn't in it.
            print(f"{BAD} commit failed, nothing was pushed:\n"
                  f"       {(com.stderr or com.stdout).strip()}")
            if "user.email" in (com.stderr + com.stdout):
                print("       Set an identity first:\n"
                      "         git config --global user.name  'Your Name'\n"
                      "         git config --global user.email 'you@example.com'")
            return 1
        print(com.stdout.strip().splitlines()[0] if com.stdout.strip() else "committed")
        r = subprocess.run(["git", "-C", str(ROOT), "push"],
                           capture_output=True, text=True)
        if r.returncode != 0:
            print(f"{BAD} committed locally, but the push failed:\n"
                  f"       {(r.stderr or r.stdout).strip().splitlines()[-1]}")
            print("       The change is safe in git — it just isn't on GitHub "
                  "yet, so nobody downstream can see it.")
            return 1
        print(f"{OK} pushed — downstream vaults can see this now")
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
