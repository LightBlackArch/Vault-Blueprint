#!/usr/bin/env python3
"""
blueprint-update.py — pull improvements from the Vault Blueprint into YOUR vault,
without ever touching a single word you wrote.

WHAT THIS IS FOR
----------------
You downloaded the Vault Blueprint once and made it yours. Since then the
blueprint got better — a new script, a safer rule, a folder that turned out to
be worth having. This fetches whatever changed and offers it to you, one item
at a time, in plain English:

    [3] Screenshots now get saved into AIOS/history/screenshots/ instead of
        sitting in Inbox/. Adds the folder and an index note.
        Want it? (y/n)

Nothing is applied unless you say so. Your notes are never read, never
rewritten, never deleted. `Privat/` is untouchable and hard-coded as such.

HOW TO USE IT
-------------
    python3 AIOS/scripts/blueprint-update.py                 # show what's waiting
    python3 AIOS/scripts/blueprint-update.py --interactive   # ask y/n for each
    python3 AIOS/scripts/blueprint-update.py --apply 1,3,5   # apply just those
    python3 AIOS/scripts/blueprint-update.py --apply all     # apply everything
    python3 AIOS/scripts/blueprint-update.py --decline 2,4   # never ask again
    python3 AIOS/scripts/blueprint-update.py --undo          # put back the last update
    python3 AIOS/scripts/blueprint-update.py --check         # one line, for a schedule
    python3 AIOS/scripts/blueprint-update.py --json          # for your AI to read

Or just tell your AI: **"update my vault from the blueprint"**.

HOW IT DECIDES WHAT'S SAFE
--------------------------
Every file the blueprint ships is labelled in `AIOS/config/blueprint-manifest.json`:

  system     Scripts, skills, templates. Blueprint owns these. Safe to update.
  seed       Files you were given once to fill in yourself (me.md, the EXAMPLE
             notes, your index notes). Written on install, never overwritten.
  brain      CLAUDE.md, AIOS/me.md, vault-map.md, skill-map.md. A script must
             NEVER write these — they're half yours. Changes here are handed to
             your AI to merge by hand, keeping everything personal intact.
  structure  Folders. A new one is offered, never forced.
  never      Privat/, your history, your generated files. Not looked at.

For `system` files it does a three-way comparison, which is the bit that makes
this safe: it remembers the exact version it gave you last time. So it can tell
the difference between "you never touched this, take the new one" and "you
edited this yourself, I must ask first". A file you customised is flagged as a
conflict and shown as a diff — it is never silently overwritten.

Everything it does touch gets backed up first, into
`AIOS/history/blueprint-updates/<timestamp>/`, so `--undo` is real.

NO DEPENDENCIES. Plain Python 3.8+ stdlib. Works with or without git — if git
isn't installed it downloads a tarball straight from GitHub instead.
"""
try:
    import scriptlog  # noqa: F401 -- logs this run to AIOS/history/scripts/
except Exception:      # bootstrap case: this script can arrive before scriptlog does
    pass

# aios-run: schedule  (optional --check nag; see --install-schedule)

import argparse
import difflib
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

VAULT = Path(__file__).resolve().parent.parent.parent

DEFAULT_REPO = "https://github.com/LightBlackArch/Vault-Blueprint"
DEFAULT_BRANCH = "main"

STATE_PATH = VAULT / "AIOS" / "config" / "blueprint-state.json"
MANIFEST_REL = "AIOS/config/blueprint-manifest.json"
CHANGES_REL = "AIOS/reference/blueprint-changes.md"
BACKUP_ROOT = VAULT / "AIOS" / "history" / "blueprint-updates"

# Hard stop. Not configurable, not overridable, not read from the manifest.
# If a path matches any of these the updater will not read it, write it,
# compare it, or mention it. This list is the reason this script is safe to run.
FORBIDDEN = (
    "Privat/",
    ".git/",
    ".obsidian/workspace",
    "AIOS/history/",
    "AIOS/generated/",
    "AIOS/archive/",
    "Attachments/",
    "__pycache__/",
)

# Used only when the remote ships no manifest (an old blueprint, or a fork).
FALLBACK_CLASSES = (
    ("AIOS/scripts/", "system"),
    ("AIOS/skills/", "system"),
    ("AIOS/templates/", "system"),
    ("AIOS/reference/", "system"),
    ("AIOS/config/", "system"),
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
)

C = {
    "b": "\033[1m", "dim": "\033[2m", "r": "\033[0m",
    "grn": "\033[32m", "yel": "\033[33m", "red": "\033[31m", "cyn": "\033[36m",
}
if not sys.stdout.isatty() or os.environ.get("NO_COLOR"):
    C = {k: "" for k in C}


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha_file(p: Path) -> str:
    try:
        return sha(p.read_bytes())
    except Exception:
        return ""


def forbidden(rel: str) -> bool:
    rel = rel.replace("\\", "/")
    return any(rel == f.rstrip("/") or rel.startswith(f) for f in FORBIDDEN)


def load_state() -> dict:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"{C['yel']}warning:{C['r']} {STATE_PATH.name} is unreadable "
                  f"({e}). Starting from scratch — nothing is lost, the worst "
                  f"case is you get re-asked about things you already decided.")
    return {
        "_what": "Which blueprint version this vault is on, which files came "
                 "from it, and which suggestions you already said no to. "
                 "Written by AIOS/scripts/blueprint-update.py. Safe to delete — "
                 "you'll just get re-asked about everything once.",
        "repo": DEFAULT_REPO,
        "branch": DEFAULT_BRANCH,
        "installed_sha": None,
        "installed_at": None,
        "files": {},
        "declined": {},
    }


def save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n",
                          encoding="utf-8")


def wrap(text: str, width: int = 74, indent: str = "") -> str:
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return f"\n{indent}".join(lines)


# --------------------------------------------------------------------------
# getting the latest blueprint
# --------------------------------------------------------------------------

def parse_repo(url: str):
    m = re.search(r"github\.com[:/]+([^/]+)/([^/.]+)", url)
    if not m:
        return None, None
    return m.group(1), m.group(2)


def fetch_blueprint(repo: str, branch: str, local: str, workdir: Path):
    """Return (path_to_blueprint, revision_string). Never raises on network
    failure — returns (None, reason) so the caller can print something useful."""
    if local:
        p = Path(local).expanduser().resolve()
        if not (p / "AIOS").is_dir():
            return None, f"{p} doesn't look like a blueprint (no AIOS/ folder)"
        return p, f"local:{p}"

    dest = workdir / "blueprint"

    if shutil.which("git"):
        r = subprocess.run(
            ["git", "clone", "--depth", "1", "--branch", branch, repo, str(dest)],
            capture_output=True, text=True, timeout=180)
        if r.returncode == 0:
            rev = subprocess.run(["git", "-C", str(dest), "rev-parse", "HEAD"],
                                 capture_output=True, text=True)
            return dest, (rev.stdout.strip()[:12] if rev.returncode == 0 else branch)

    owner, name = parse_repo(repo)
    if not owner:
        return None, (f"couldn't work out the GitHub owner/repo from '{repo}'. "
                      f"Pass --from <path> with a downloaded copy instead.")
    url = f"https://codeload.github.com/{owner}/{name}/tar.gz/refs/heads/{branch}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "blueprint-update"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            blob = resp.read()
    except urllib.error.HTTPError as e:
        return None, (f"GitHub said {e.code} for {url}. Check the repo name and "
                      f"that the '{branch}' branch exists.")
    except Exception as e:
        return None, (f"couldn't reach GitHub ({e}). If you're offline, download "
                      f"the repo as a ZIP, unpack it, and re-run with "
                      f"--from /path/to/that/folder")

    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as tf:
        root = os.path.commonprefix([m.name for m in tf.getmembers() if m.name]) or ""
        root = root.split("/")[0]
        for m in tf.getmembers():
            rel = m.name[len(root):].lstrip("/")
            if not rel or forbidden(rel) or ".." in Path(rel).parts:
                continue
            m.name = rel
            try:
                tf.extract(m, dest)
            except Exception:
                pass
    return dest, f"tarball:{branch}"


def walk_blueprint(root: Path):
    """Every shippable file in a blueprint folder, as forward-slash rel paths."""
    out = {}
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(root).as_posix()
        if forbidden(rel) or p.name in (".DS_Store",) or rel.endswith(".pyc"):
            continue
        out[rel] = p
    return out


def classify(rel: str, manifest: dict) -> str:
    if manifest.get("files"):
        # A manifest is authoritative. Anything it doesn't list is deliberately
        # not shipped — the blueprint's own state files, for instance — so the
        # safe reading of "not in the manifest" is "none of your business".
        return manifest["files"].get(rel, {}).get("class", "never")
    if rel.endswith(".gitkeep"):
        return "structure"
    for prefix, cls in FALLBACK_CLASSES:
        if rel == prefix or rel.startswith(prefix):
            return cls
    return "seed"


# --------------------------------------------------------------------------
# the plain-English change log
# --------------------------------------------------------------------------

def load_changes(root: Path):
    """Parse AIOS/reference/blueprint-changes.md into described proposals.

    Format — one block per change, order doesn't matter:

        ### id: screenshots-folder
        title: Screenshots get their own folder
        files: AIOS/scripts/shot.py, AIOS/history/screenshots/.gitkeep
        needs: nothing
        <blank line>
        Plain-English body. What actually changes for you, and why you might
        want it. Written for someone who has never read the code.
    """
    p = root / CHANGES_REL
    if not p.exists():
        return {}
    described, cur, fenced = {}, None, False
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.lstrip().startswith("```"):
            fenced = not fenced          # the format example at the top of the
            continue                     # file is not a real change entry
        if fenced:
            continue
        m = re.match(r"^###\s+id:\s*(\S+)", line.strip())
        if m:
            cur = {"id": m.group(1), "title": "", "files": [], "needs": "",
                   "body": []}
            described[cur["id"]] = cur
            continue
        if cur is None:
            continue
        if line.startswith("### ") or line.startswith("## "):
            cur = None
            continue
        m = re.match(r"^(title|files|needs):\s*(.*)$", line.strip(), re.I)
        if m and not cur["body"]:
            key, val = m.group(1).lower(), m.group(2).strip()
            if key == "files":
                cur["files"] = [f.strip() for f in val.split(",") if f.strip()]
            else:
                cur[key] = val
            continue
        if line.strip() or cur["body"]:
            cur["body"].append(line.rstrip())
    for c in described.values():
        c["body"] = "\n".join(c["body"]).strip()
    return described


# --------------------------------------------------------------------------
# building the plan
# --------------------------------------------------------------------------

def describe_file(rel: str, kind: str) -> str:
    """A sentence for a change nobody wrote a description for."""
    name = Path(rel).name
    if rel.startswith("AIOS/skills/"):
        skill = rel.split("/")[2] if len(rel.split("/")) > 2 else name
        what = f"the '{skill}' skill — the instructions your AI follows"
    elif rel.startswith("AIOS/scripts/"):
        what = f"the script {name}, one of the vault's automated helpers"
    elif rel.startswith("AIOS/templates/"):
        what = f"the {Path(rel).stem.replace('-', ' ')} template"
    elif rel.startswith("AIOS/reference/"):
        what = f"the reference doc {name}"
    else:
        what = name
    verbs = {
        "new": f"Adds {what}. You don't have this file yet.",
        "update": f"Updates {what}. You haven't edited it, so this is a clean swap.",
        "conflict": f"Updates {what} — but you've edited your copy, so this "
                    f"needs your call.",
        "unknown": f"Your copy of {what} differs from the blueprint's, and "
                   f"there's no record of which version you started from — so "
                   f"an edit you made and an update you're missing look "
                   f"identical from here. Read the diff before deciding.",
        "removed": f"The blueprint dropped {what}. Yours is left exactly where "
                   f"it is — nothing is ever deleted for you.",
        "folder": f"Adds the folder {rel.rsplit('/', 1)[0]}/.",
        "manual": f"Changes {what}. This one is half yours, so a script won't "
                  f"write it — your AI merges just the new part and keeps "
                  f"everything you wrote.",
    }
    return verbs.get(kind, f"Changes {what}.")


def make_diff(old: bytes, new: bytes, rel: str, limit: int = 120) -> str:
    try:
        a = old.decode("utf-8", "replace").splitlines()
        b = new.decode("utf-8", "replace").splitlines()
    except Exception:
        return "(binary file — no diff)"
    d = list(difflib.unified_diff(a, b, f"yours/{rel}", f"blueprint/{rel}",
                                  lineterm="", n=2))
    if len(d) > limit:
        d = d[:limit] + [f"... ({len(d) - limit} more diff lines)"]
    return "\n".join(d)


def build_plan(bp_root: Path, state: dict, include_declined: bool):
    manifest = {}
    mpath = bp_root / MANIFEST_REL
    if mpath.exists():
        try:
            manifest = json.loads(mpath.read_text(encoding="utf-8"))
        except Exception:
            manifest = {}

    described = load_changes(bp_root)
    remote = walk_blueprint(bp_root)
    recorded = state.get("files", {})
    proposals = []
    claimed = set()

    # Files a hand-written entry speaks for get grouped under it, so the reader
    # sees "Screenshots get their own folder" instead of six file paths.
    # A file belongs to the NEWEST entry that lists it (blueprint-changes.md puts
    # the newest entry at the top, so the first listing wins), and the change
    # log itself never counts. Without
    # this, one edit to a shared script re-opens every old entry that ever
    # mentioned it, and a 6-change release shows up as 27 questions.
    owner = {}
    for cid, c in described.items():
        for f in c["files"]:
            owner.setdefault(f, cid)
    for cid, c in described.items():
        touched = [f for f in c["files"]
                   if owner.get(f) == cid and f != CHANGES_REL
                   and f in remote and not forbidden(f)]
        pending = []
        for rel in touched:
            local = VAULT / rel
            rhash = sha_file(remote[rel])
            if not local.exists() or sha_file(local) != rhash:
                pending.append(rel)
        if not pending:
            continue
        claimed.update(touched)
        cls = {classify(r, manifest) for r in pending}
        manual = bool(cls & {"brain", "seed"})
        proposals.append({
            "id": cid,
            "kind": "described",
            "title": c["title"] or cid,
            "detail": c["body"] or describe_file(pending[0], "update"),
            "files": pending,
            "manual": manual,
            "needs": c.get("needs", ""),
            "fingerprint": sha("".join(sorted(
                sha_file(remote[r]) for r in pending)).encode()),
        })

    # Everything else, file by file.
    for rel, src in sorted(remote.items()):
        if rel in claimed or forbidden(rel) or rel == CHANGES_REL:
            continue                 # the change log is a record, not a question
        cls = classify(rel, manifest)
        if cls == "never":
            continue
        if cls == "setup":
            # First-run scaffolding: the EXAMPLE notes, the setup interview,
            # README-START-HERE. The README tells people to delete these once
            # they're done. Offering them back every month would be nagging
            # somebody with a chore they already completed.
            continue
        local = VAULT / rel
        rhash = sha_file(src)
        lhash = sha_file(local) if local.exists() else None
        known = recorded.get(rel, {}).get("blueprint_sha256")

        if lhash == rhash:
            if known != rhash:                      # silently re-sync the record
                recorded.setdefault(rel, {})["blueprint_sha256"] = rhash
            continue

        if cls == "structure":
            if local.exists():
                continue
            folder = rel.rsplit("/", 1)[0]
            if (VAULT / folder).is_dir():
                continue
            kind, manual = "folder", False
        elif not local.exists():
            kind, manual = "new", cls in ("brain",)
        elif cls in ("brain", "seed"):
            kind, manual = "manual", True
        elif known is None:
            kind, manual = "unknown", True
        elif lhash == known:
            kind, manual = "update", False
        else:
            kind, manual = "conflict", True

        p = {
            "id": f"file:{rel}",
            "kind": kind,
            "title": f"{Path(rel).name} — {kind}",
            "detail": describe_file(rel, kind),
            "files": [rel],
            "manual": manual,
            "needs": "",
            "class": cls,
            "fingerprint": rhash,
        }
        if kind in ("conflict", "unknown", "manual") and local.exists():
            p["diff"] = make_diff(local.read_bytes(), src.read_bytes(), rel)
        proposals.append(p)

    # Files the blueprint dropped. Reported, never acted on.
    for rel in sorted(recorded):
        if rel in remote or forbidden(rel) or not (VAULT / rel).exists():
            continue
        proposals.append({
            "id": f"gone:{rel}",
            "kind": "removed", "title": f"{Path(rel).name} — no longer shipped",
            "detail": describe_file(rel, "removed"), "files": [rel],
            "manual": True, "needs": "", "fingerprint": "gone",
        })

    # Declines. Re-offered exactly once if the thing itself changed since.
    declined = state.get("declined", {})
    out = []
    for p in proposals:
        d = declined.get(p["id"])
        if d and not include_declined:
            if d.get("fingerprint") == p["fingerprint"]:
                continue
            p["changed_since_decline"] = True
            p["declined_at"] = d.get("at")
        elif d:
            p["previously_declined"] = True
        out.append(p)

    order = {"described": 0, "new": 1, "update": 2, "folder": 3,
             "manual": 4, "conflict": 5, "unknown": 6, "removed": 7}
    out.sort(key=lambda p: (order.get(p["kind"], 9), p["id"]))
    for i, p in enumerate(out, 1):
        p["n"] = i
    return out, manifest


# --------------------------------------------------------------------------
# applying
# --------------------------------------------------------------------------

def apply_proposals(chosen, bp_root: Path, state: dict, force_manual: bool,
                    manifest: dict):
    ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    backup = BACKUP_ROOT / ts
    n = 2
    while backup.exists():          # two applies inside one second must not
        backup = BACKUP_ROOT / f"{ts}-{n}"   # share a folder, or undo loses one
        n += 1
    applied, skipped, record, noted, created = [], [], [], [], []

    for p in chosen:
        if p["manual"] and not force_manual:
            skipped.append((p, "needs your AI to merge it by hand — a script "
                               "won't write this file"))
            continue
        if p["kind"] == "removed":
            skipped.append((p, "nothing to do — files are never deleted for you"))
            continue
        for rel in p["files"]:
            if forbidden(rel):
                skipped.append((p, f"refused: {rel} is in a protected folder"))
                continue
            src = bp_root / rel
            if not src.exists():
                continue
            dst = VAULT / rel

            # THE HARD STOP. A file that is half the user's — CLAUDE.md,
            # me.md, vault-map.md, skill-map.md — is never written by this
            # script once it exists, by any flag, in any mode. `--force-manual`
            # on one of these means "my AI has already merged it by hand, stop
            # offering it", so all that happens is the record gets updated.
            # There is deliberately no command-line route to overwriting the
            # file that has the user in it.
            if classify(rel, manifest) == "brain" and dst.exists():
                state.setdefault("files", {})[rel] = {
                    "blueprint_sha256": sha_file(src),
                    "adopted_at": datetime.now().isoformat(timespec="seconds"),
                    "merged_by_hand": True,
                }
                noted.append(rel)
                continue

            if dst.exists():
                b = backup / "files" / rel
                b.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(dst, b)
                record.append(rel)
            else:
                # Written down explicitly, because --undo removing a file it
                # never created is the worst thing this program could do.
                # Undo deletes from this list and from nowhere else.
                created.append(rel)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            if dst.suffix == ".py":
                try:
                    os.chmod(dst, 0o755)
                except Exception:
                    pass
            state.setdefault("files", {})[rel] = {
                "blueprint_sha256": sha_file(src),
                "adopted_at": datetime.now().isoformat(timespec="seconds"),
            }
        applied.append(p)

    # No backup folder when nothing was actually written — otherwise a
    # record-only apply leaves an empty restore point, and `--undo` then
    # "succeeds" by doing nothing while the real change stays applied.
    if applied and (record or created):
        backup.mkdir(parents=True, exist_ok=True)
        (backup / "applied.json").write_text(json.dumps({
            "at": datetime.now().isoformat(timespec="seconds"),
            "proposals": [{k: v for k, v in p.items() if k != "diff"}
                          for p in applied],
            "backed_up": record,
            "created": created,
            "recorded_only": noted,
        }, indent=2) + "\n", encoding="utf-8")
    return applied, skipped, (backup if (applied and (record or created))
                              else None), noted


def undo_last():
    if not BACKUP_ROOT.is_dir():
        return "There's nothing to undo — no blueprint update has ever run here."
    dirs = sorted([d for d in BACKUP_ROOT.iterdir()
                   if d.is_dir() and (d / "applied.json").exists()])
    if not dirs:
        return "There's nothing to undo — no blueprint update has ever run here."
    last = dirs[-1]
    info = json.loads((last / "applied.json").read_text(encoding="utf-8"))
    restored, removed = 0, 0
    files_root = last / "files"
    backed = set(info.get("backed_up", []))
    # Undo deletes ONLY files this updater is recorded as having created. It
    # never infers "must have been new because there's no backup" — that
    # inference once deleted somebody's me.md, because a file that was only
    # *recorded* as handled has no backup either and looked identical from
    # here. If `created` is missing (an update written by an older version),
    # nothing is deleted at all. Restoring too little is recoverable;
    # deleting somebody's file is not.
    created = set(info.get("created", []))
    for rel in sorted(backed):
        if forbidden(rel) or not (files_root / rel).exists():
            continue
        target = VAULT / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(files_root / rel, target)
        restored += 1
    for rel in sorted(created):
        if forbidden(rel) or rel in backed:
            continue
        target = VAULT / rel
        if target.exists():
            target.unlink()
            removed += 1
    state = load_state()
    for p in info.get("proposals", []):
        for rel in p.get("files", []):
            state.get("files", {}).pop(rel, None)
    save_state(state)
    shutil.move(str(last), str(last) + ".undone")
    return (f"Undone: {restored} file(s) put back the way they were, "
            f"{removed} newly-added file(s) removed. From {info.get('at')}.")


# --------------------------------------------------------------------------
# printing
# --------------------------------------------------------------------------

BADGE = {
    "described": ("NEW", "grn"), "new": ("NEW", "grn"),
    "update": ("UPDATE", "cyn"), "folder": ("FOLDER", "grn"),
    "manual": ("YOUR CALL", "yel"), "conflict": ("CONFLICT", "yel"),
    "unknown": ("CHECK", "yel"), "removed": ("DROPPED", "dim"),
}


def print_plan(plan, rev, state, show_diffs):
    at = state.get("installed_at")
    print()
    print(f"{C['b']}Blueprint update{C['r']}  {C['dim']}(blueprint at {rev}"
          + (f", you last updated {at[:10]}" if at else ", never updated before")
          + f"){C['r']}")
    print()
    if not plan:
        print(f"  {C['grn']}Nothing waiting.{C['r']} Your vault already has "
              f"everything the blueprint offers.")
        print()
        return
    for p in plan:
        label, col = BADGE.get(p["kind"], ("CHANGE", "cyn"))
        flag = ""
        if p.get("changed_since_decline"):
            flag = f"  {C['dim']}(you said no to this before — it has changed since){C['r']}"
        elif p.get("previously_declined"):
            flag = f"  {C['dim']}(previously declined){C['r']}"
        print(f"  {C['b']}[{p['n']}]{C['r']} {C[col]}{label}{C['r']}  "
              f"{C['b']}{p['title']}{C['r']}{flag}")
        print(f"      {wrap(p['detail'], 72, '      ')}")
        if p.get("needs"):
            print(f"      {C['dim']}needs: {p['needs']}{C['r']}")
        print(f"      {C['dim']}files: {', '.join(p['files'][:4])}"
              + (f" (+{len(p['files']) - 4} more)" if len(p["files"]) > 4 else "")
              + C["r"])
        print(f"      {C['dim']}id: {p['id']}{C['r']}")
        if show_diffs and p.get("diff"):
            for line in p["diff"].splitlines():
                colr = C["grn"] if line.startswith("+") else (
                    C["red"] if line.startswith("-") else C["dim"])
                print(f"      {colr}{line}{C['r']}")
        print()
    auto = sum(1 for p in plan if not p["manual"])
    print(f"  {len(plan)} waiting — {auto} can be applied straight away, "
          f"{len(plan) - auto} need you (or your AI) to decide.")
    print()
    print(f"  {C['dim']}Apply:   python3 AIOS/scripts/blueprint-update.py --apply 1,2{C['r']}")
    print(f"  {C['dim']}Ask one by one: ... --interactive{C['r']}")
    print(f"  {C['dim']}Never ask again: ... --decline 3{C['r']}")
    print()


def interactive(plan, bp_root, state):
    print()
    print(f"{C['b']}One at a time. y = do it, n = never ask again, "
          f"s = skip for now, q = stop.{C['r']}")
    take, decline = [], []
    for p in plan:
        label, col = BADGE.get(p["kind"], ("CHANGE", "cyn"))
        print()
        print(f"  {C[col]}{label}{C['r']}  {C['b']}{p['title']}{C['r']}")
        print(f"  {wrap(p['detail'], 72, '  ')}")
        print(f"  {C['dim']}files: {', '.join(p['files'])}{C['r']}")
        if p["manual"]:
            print(f"  {C['yel']}This one a script won't write — say y and your "
                  f"AI merges it by hand, keeping your own words.{C['r']}")
        while True:
            try:
                a = input("  y/n/s/q/d(iff) > ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print()
                return take, decline
            if a == "d" and p.get("diff"):
                print(p["diff"])
                continue
            if a in ("y", "n", "s", "q", ""):
                break
        if a == "q":
            break
        if a == "y":
            take.append(p)
        elif a == "n":
            decline.append(p)
    return take, decline


# --------------------------------------------------------------------------

def selftest():
    """Run the updater end to end on throwaway copies: a missing system script comes back,
    a hand-edited me.md and a Privat/ file are never touched, and --undo reverses it."""
    import filecmp
    with tempfile.TemporaryDirectory(prefix="bp-selftest-") as t:
        t = Path(t)
        skip = shutil.ignore_patterns(".git", "__pycache__", "Privat", "history", "generated")
        shutil.copytree(VAULT, t / "bp", ignore=skip)
        shutil.copytree(VAULT, t / "vault", ignore=skip)
        down = t / "vault"
        (down / "AIOS" / "scripts" / "weekly-digest.py").unlink()            # a system file the user lacks
        mine = down / "AIOS" / "me.md"
        mine.write_text(mine.read_text(encoding="utf-8") + "\nMY OWN LINE\n", encoding="utf-8")
        (down / "Privat").mkdir()
        (down / "Privat" / "diary.md").write_text("secret", encoding="utf-8")
        me_before, diary_before = mine.read_bytes(), (down / "Privat" / "diary.md").read_bytes()

        def run(*a):
            return subprocess.run([sys.executable, str(down / "AIOS" / "scripts" / "blueprint-update.py"),
                                   "--from", str(t / "bp"), *a], capture_output=True, text=True, timeout=120)
        plan = json.loads(run("--json").stdout)
        assert any("weekly-digest.py" in f for p in plan["proposals"] for f in p["files"]), "missing file not proposed"
        r = run("--apply", "all")
        assert r.returncode == 0, r.stderr
        assert (down / "AIOS" / "scripts" / "weekly-digest.py").exists(), "system file not restored"
        assert mine.read_bytes() == me_before, "me.md was written"
        assert (down / "Privat" / "diary.md").read_bytes() == diary_before, "Privat/ was touched"
        u = subprocess.run([sys.executable, str(down / "AIOS" / "scripts" / "blueprint-update.py"), "--undo"],
                           capture_output=True, text=True, timeout=120)
        assert not (down / "AIOS" / "scripts" / "weekly-digest.py").exists(), "undo did not remove it"
        assert mine.read_bytes() == me_before and u.returncode == 0
    print("blueprint-update.py selftest: ok")
    return 0


def main():
    ap = argparse.ArgumentParser(
        description="Pull improvements from the Vault Blueprint into your vault.")
    ap.add_argument("--repo", help="blueprint git URL")
    ap.add_argument("--branch", help="branch (default main)")
    ap.add_argument("--from", dest="local", metavar="PATH",
                    help="use a blueprint folder already on disk instead of "
                         "downloading (a ZIP you unpacked, say)")
    ap.add_argument("--apply", metavar="N,N|all")
    ap.add_argument("--decline", metavar="N,N")
    ap.add_argument("--undo", action="store_true")
    ap.add_argument("--selftest", action="store_true", help="test the updater on throwaway copies")
    ap.add_argument("--check", action="store_true",
                    help="one line, exits 1 if updates are waiting")
    ap.add_argument("--json", action="store_true", help="machine-readable plan")
    ap.add_argument("--interactive", "-i", action="store_true")
    ap.add_argument("--diffs", action="store_true", help="show full diffs")
    ap.add_argument("--show-declined", action="store_true")
    ap.add_argument("--force-manual", action="store_true",
                    help="let the script write brain/seed files too. Only for "
                         "an AI that has already merged them, or a fresh vault.")
    args = ap.parse_args()

    if args.selftest:
        return selftest()

    if args.undo:
        print(undo_last())
        return 0

    state = load_state()
    repo = args.repo or state.get("repo") or DEFAULT_REPO
    branch = args.branch or state.get("branch") or DEFAULT_BRANCH

    with tempfile.TemporaryDirectory(prefix="bp-update-") as tmp:
        bp_root, rev = fetch_blueprint(repo, branch, args.local, Path(tmp))
        if bp_root is None:
            msg = f"Couldn't get the blueprint: {rev}"
            print(json.dumps({"error": msg}) if args.json
                  else f"{C['red']}{msg}{C['r']}", file=sys.stderr)
            return 2

        plan, manifest = build_plan(bp_root, state, args.show_declined)
        by_n = {p["n"]: p for p in plan}

        def pick(spec):
            if not spec:
                return []
            if spec.strip().lower() == "all":
                return list(plan)
            out = []
            for tok in re.split(r"[,\s]+", spec.strip()):
                if not tok:
                    continue
                if tok.isdigit() and int(tok) in by_n:
                    out.append(by_n[int(tok)])
                else:
                    match = [p for p in plan if p["id"] == tok]
                    if match:
                        out.append(match[0])
                    else:
                        print(f"{C['yel']}no such item: {tok}{C['r']}",
                              file=sys.stderr)
            return out

        if args.check:
            auto = sum(1 for p in plan if not p["manual"])
            if not plan:
                print("Blueprint: up to date.")
                return 0
            print(f"Blueprint: {len(plan)} update(s) waiting "
                  f"({auto} ready to apply). "
                  f"Say \"update my vault from the blueprint\".")
            return 1

        if args.json:
            print(json.dumps({
                "revision": rev, "repo": repo, "branch": branch,
                "vault": str(VAULT),
                "installed_sha": state.get("installed_sha"),
                "installed_at": state.get("installed_at"),
                "count": len(plan),
                "blueprint_path": str(bp_root),
                "proposals": plan,
            }, indent=2))
            return 0

        take, decline = [], []
        if args.interactive:
            take, decline = interactive(plan, bp_root, state)
        else:
            take = pick(args.apply)
            decline = pick(args.decline)

        if not take and not decline:
            print_plan(plan, rev, state, args.diffs)
            save_state(state)
            return 0

        for p in decline:
            state.setdefault("declined", {})[p["id"]] = {
                "at": datetime.now().isoformat(timespec="seconds"),
                "fingerprint": p["fingerprint"],
                "title": p["title"],
            }

        applied, skipped, backup, noted = apply_proposals(
            take, bp_root, state, args.force_manual, manifest)

        if applied:
            state["installed_sha"] = rev
            state["installed_at"] = datetime.now().isoformat(timespec="seconds")
        state["repo"], state["branch"] = repo, branch
        save_state(state)

        print()
        for p in applied:
            print(f"  {C['grn']}done{C['r']}   {p['title']}")
        for rel in noted:
            print(f"  {C['cyn']}noted{C['r']}  {rel} — recorded as handled. "
                  f"{C['dim']}Not written: this file is half yours, only your "
                  f"AI may edit it.{C['r']}")
        for p, why in skipped:
            print(f"  {C['yel']}left{C['r']}   {p['title']}  {C['dim']}— {why}{C['r']}")
        for p in decline:
            print(f"  {C['dim']}no     {p['title']} — won't be offered again{C['r']}")
        if backup:
            print()
            print(f"  Backed up to {backup.relative_to(VAULT)}")
            print(f"  {C['dim']}Undo it all: python3 AIOS/scripts/"
                  f"blueprint-update.py --undo{C['r']}")
        print()
        if any(p["files"] == ["AIOS/scripts/blueprint-update.py"] or
               "AIOS/scripts/blueprint-update.py" in p["files"] for p in applied):
            print(f"  {C['yel']}This updater updated itself — run it once more "
                  f"to use the new version.{C['r']}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
