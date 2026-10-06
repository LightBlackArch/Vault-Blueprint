#!/usr/bin/env python3
"""
blueprint-manifest.py — label every file the blueprint ships, so the updater
knows what it's allowed to touch.

Run this in the BLUEPRINT folder (not in someone's real vault) whenever the
blueprint changes. It writes `AIOS/config/blueprint-manifest.json`, which
`blueprint-update.py` reads on the other end.

    python3 AIOS/scripts/blueprint-manifest.py            # write it
    python3 AIOS/scripts/blueprint-manifest.py --check    # is it out of date?

THE FIVE LABELS
---------------
The whole safety of the update system is this one decision per file. Getting a
file into the wrong class is the only way this thing can hurt somebody.

  system     The blueprint owns it outright. Scripts, skills, templates,
             reference docs. Nobody's personal writing is in here, so it can be
             updated in place — as long as they haven't edited it themselves,
             which the updater checks separately.

  seed       Handed over once, then it's theirs. `setup-questions.md`, the
             EXAMPLE notes, index notes like `Efforts/Efforts.md` that fill up
             with their own links. Shipped on install, NEVER overwritten after.

  brain      Half blueprint, half person: `CLAUDE.md`, `AIOS/me.md`,
             `vault-map.md`, `skill-map.md`, `how-to-use-this.md`. A script must
             never write these. Changes are handed to their AI, which merges the
             new structural bit and leaves every personal line alone.

  structure  A `.gitkeep` standing in for a folder. Offered as "want this
             folder too?", never forced.

  never      Not shipped, not compared, not looked at.

WHEN IN DOUBT, PICK THE MORE CAUTIOUS ONE. `seed` never overwrites anything;
`system` does. A file wrongly marked `seed` means someone misses an
improvement. A file wrongly marked `system` means someone loses their writing.
Those are not the same size of mistake.
"""
try:
    import scriptlog  # noqa: F401
except Exception:
    pass

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
OUT = ROOT / "AIOS" / "config" / "blueprint-manifest.json"

SKIP = (".git/", "Privat/", "__pycache__/", ".obsidian/workspace",
        "AIOS/history/", "AIOS/generated/", "Attachments/", ".trash/")

# Order matters — first match wins.
RULES = [
    ("AIOS/config/blueprint-manifest.json", "never"),   # itself
    ("AIOS/config/blueprint-state.json", "never"),      # per-person state
    (".github/", "never"),                              # the blueprint's own CI, not for anyone's vault
    # First-run scaffolding. README-START-HERE tells people to delete all of
    # this once they're set up, so the updater must never offer it back — that
    # would be nagging somebody about a chore they already finished.
    ("README-START-HERE.md", "setup"),
    ("AIOS/setup-questions.md", "setup"),
    ("AIOS/skills/setup-vault/", "setup"),
    ("CLAUDE.md", "brain"),
    ("AIOS/me.md", "brain"),
    ("AIOS/vault-map.md", "brain"),
    ("AIOS/skill-map.md", "brain"),
    ("AIOS/how-to-use-this.md", "brain"),
    ("AIOS/setup-questions.md", "seed"),
    ("README-START-HERE.md", "seed"),
    ("UPDATE-MY-VAULT.md", "system"),
    ("Home.md", "seed"),
    ("LICENSE", "system"),
    ("AIOS/scripts/", "system"),
    ("AIOS/skills/", "system"),
    ("AIOS/templates/", "system"),
    ("AIOS/reference/", "system"),
    # Their editor settings — theme, enabled plugins, window state. Shipped
    # once as sensible defaults, then permanently theirs. These files get
    # rewritten by Obsidian just from opening the vault, so treating them as
    # updatable means every user is repeatedly asked whether they want the
    # blueprint author's colour scheme. Nobody wants that, and it's noise
    # sitting on top of the changes that actually matter.
    (".obsidian/", "setup"),
]


def classify(rel: str) -> str:
    if rel.endswith(".gitkeep"):
        return "structure"
    if Path(rel).name.startswith("EXAMPLE "):
        return "setup"          # fake notes, deleted on purpose after a look
    for prefix, cls in RULES:
        if rel == prefix or (prefix.endswith("/") and rel.startswith(prefix)):
            return cls
    # Anything left is a note. Notes are somebody's writing the moment they
    # touch them, so they only ever get seeded, never updated.
    return "seed"


def build():
    files = {}
    for p in sorted(ROOT.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(ROOT).as_posix()
        if any(rel.startswith(s) or rel == s.rstrip("/") for s in SKIP):
            continue
        if rel.endswith((".pyc", ".DS_Store")):
            continue
        cls = classify(rel)
        if cls == "never":
            continue
        files[rel] = {
            "class": cls,
            "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
            "bytes": p.stat().st_size,
        }
    return {
        "_what": "Every file this blueprint ships, and how much of it belongs "
                 "to the blueprint versus to the person using it. Read by "
                 "AIOS/scripts/blueprint-update.py. Generated — do not hand-edit; "
                 "change the rules in AIOS/scripts/blueprint-manifest.py instead.",
        "_classes": {
            "system": "Blueprint owns it. Updated in place unless the user "
                      "edited it, in which case they're asked.",
            "seed": "Given once, then theirs. Never overwritten.",
            "brain": "Half theirs. A script never writes it; their AI merges "
                     "the structural change by hand.",
            "structure": "A folder. Offered, never forced.",
            "setup": "First-run scaffolding the user is told to delete once "
                     "they're set up. Shipped, then never offered again.",
        },
        "generated": datetime.now().isoformat(timespec="seconds"),
        "count": len(files),
        "files": files,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="report drift, write nothing")
    args = ap.parse_args()

    fresh = build()
    if args.check:
        if not OUT.exists():
            print("No manifest yet. Run without --check.")
            return 1
        old = json.loads(OUT.read_text(encoding="utf-8")).get("files", {})
        new = fresh["files"]
        added = sorted(set(new) - set(old))
        gone = sorted(set(old) - set(new))
        moved = sorted(r for r in set(new) & set(old)
                       if new[r]["sha256"] != old[r]["sha256"])
        if not (added or gone or moved):
            print(f"Manifest is current — {len(new)} files.")
            return 0
        for r in added:
            print(f"  + {r}  ({new[r]['class']})")
        for r in gone:
            print(f"  - {r}")
        for r in moved:
            print(f"  ~ {r}")
        print(f"\n{len(added)} added, {len(gone)} removed, {len(moved)} changed. "
              f"Re-run without --check to write it.")
        return 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(fresh, indent=2, sort_keys=True) + "\n",
                   encoding="utf-8")
    counts = {}
    for f in fresh["files"].values():
        counts[f["class"]] = counts.get(f["class"], 0) + 1
    print(f"Wrote {OUT.relative_to(ROOT)} — {fresh['count']} files: "
          + ", ".join(f"{v} {k}" for k, v in sorted(counts.items())))
    brain = [r for r, f in fresh["files"].items() if f["class"] == "brain"]
    print("\nbrain files (a script will never write these):")
    for r in sorted(brain):
        print(f"  {r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
