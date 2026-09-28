#!/usr/bin/env python3
"""
vault-check — integrity pass over this vault. REPORTS ONLY, CHANGES NOTHING.

Run:  python3 AIOS/scripts/vault-check.py
Exit: 0 clean, 1 if anything needs attention.

Never reads Privat/.

Checks, in order of how much damage each one does when it goes wrong:
  1. Dead query blocks      — a ```dataview block when Dataview isn't installed
                              renders as a grey box and links nothing.
  2. Index coverage         — notes unreachable from their own folder index.
  3. Broken wikilinks       — links pointing at nothing.
  4. status vocabulary      — status: values outside the documented set.
  5. Missing next action    — project notes breaking the one-next-action rule.
  6. Frontmatter            — notes with no title/tags.
  7. Skill drift            — skills installed but missing from AIOS/skill-map.md.
  8. Note count             — vs the number written in AIOS/vault-map.md.
  9. Sync conflicts         — Dropbox "conflicted copy" files. Harmless in
                              .obsidian/, but a conflicted copy of a NOTE means
                              two machines edited it and one version is hiding.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
VAULT = os.path.abspath(os.path.join(HERE, "..", ".."))

SKIP_DIRS = {"Privat", ".git", ".obsidian", ".trash", ".claude"}
# AIOS/history/ is generated chat transcripts and run logs, not notes. Counting
# them would make "how many notes do I have" meaningless within a week, and
# every check below would report on machine-written files nobody edits.
SKIP_PATHS = {os.path.join("AIOS", "skills"),
              os.path.join("AIOS", "history")}

STATUS_OK = {
    "Efforts": {"active", "planned", "upcoming", "stalled", "parked", "done"},
    "Atlas/Media": {"watching", "reading", "playing", "finished", "dropped",
                    "on hold"},
    "Atlas/Worlds": {"active", "parked", "dead", "unconfirmed"},
    "Atlas/Links": {"unread", "read", "useful", "dead"},
}

# folder -> index note basename. A folder with a .base file is exempt from the
# hand-linked index check, because the base counts itself.
INDEXED = {
    "Atlas/Media": "Media",
    "Atlas/Worlds": "Worlds",
    "Atlas/Reference": "Reference",
    "Atlas/Knowledge": "Knowledge",
    "Atlas/Clippings": "Clippings",
    "Atlas/About Me": "About Me",
    "Atlas/Links": "Links",
    "Atlas/People": "People",
    "Efforts": "Efforts",
}

problems = []


def flag(section, msg):
    problems.append((section, msg))


def walk(exts=(".md",), include_skipped=False):
    """Files to CHECK. Pass include_skipped=True for files that are still valid
    link targets but shouldn't be audited or counted — generated transcripts and
    the skills mirror. Leaving them out of the target set made every link to a
    generated index report as broken."""
    for dp, dns, fns in os.walk(VAULT):
        dns[:] = [d for d in dns if d not in SKIP_DIRS]
        rel = os.path.relpath(dp, VAULT)
        if not include_skipped and any(
                rel == s or rel.startswith(s + os.sep) for s in SKIP_PATHS):
            continue
        for fn in sorted(fns):
            if fn.endswith(exts):
                yield os.path.join(dp, fn)


def read(p):
    return open(p, encoding="utf-8", errors="replace").read()


def fm_field(text, key):
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end < 0:
        return None
    m = re.search(rf"^{key}:\s*(.+)$", text[3:end], re.M)
    return m.group(1).strip().strip('"').strip("'") if m else None


def main():
    md = list(walk((".md",)))                       # files to audit and count
    all_md = list(walk((".md",), include_skipped=True))   # valid link targets
    attachments = {os.path.basename(p) for p in walk(
        (".png", ".jpg", ".jpeg", ".pdf", ".gif", ".webp", ".svg", ".base"),
        include_skipped=True)}
    names = {os.path.basename(p)[:-3] for p in all_md}
    bases = {os.path.relpath(p, VAULT) for p in walk((".base",),
                                                    include_skipped=True)}

    dataview_installed = False
    cp = os.path.join(VAULT, ".obsidian", "community-plugins.json")
    if os.path.exists(cp):
        dataview_installed = "dataview" in read(cp)

    # ---- 1. dead query blocks
    # Only a fence at the start of a line is a real block. Notes that *discuss*
    # dataview inside inline code are not broken.
    fence = re.compile(r"^```+dataview\b", re.M)
    for p in md:
        t = read(p)
        if fence.search(t) and not dataview_installed:
            flag("DEAD QUERY BLOCK",
                 f"{os.path.relpath(p, VAULT)} uses ```dataview but Dataview "
                 f"is not installed. It renders as a grey box and links "
                 f"nothing. Use a .base file instead.")

    # ---- 2. index coverage
    for folder, index in INDEXED.items():
        d = os.path.join(VAULT, folder)
        if not os.path.isdir(d):
            continue
        ip = os.path.join(d, index + ".md")
        if not os.path.exists(ip):
            flag("MISSING INDEX", f"{folder}/ has no {index}.md")
            continue
        it = read(ip)
        has_base = bool(re.search(r"!\[\[[^\]]+\.base\]\]", it)) or \
            any(b.startswith(folder + os.sep) for b in bases)
        if has_base:
            continue
        linked = {m.split("/")[-1].strip()
                  for m in re.findall(r"\[\[([^\]|#]+)", it)}
        files = {f[:-3] for f in os.listdir(d)
                 if f.endswith(".md")} - {index}
        missing = sorted(files - linked)
        if missing:
            flag("INDEX MISS",
                 f"{folder}/{index}.md links {len(files) - len(missing)}/"
                 f"{len(files)} notes. Unreachable: {', '.join(missing)}")

    # ---- 3. broken wikilinks
    for p in md:
        rel = os.path.relpath(p, VAULT)
        t = read(p)
        if rel == os.path.join("AIOS", "vault-map.md"):
            continue  # contains a literal example link
        # Strip fenced and inline code spans first. Docs routinely show
        # `![[Example.base]]` as a syntax example inside backticks — that's
        # not a real link and shouldn't be flagged as one.
        t = re.sub(r"```.*?```", "", t, flags=re.S)
        t = re.sub(r"`[^`\n]*`", "", t)
        bad = set()
        for m in re.finditer(r"\[\[([^\]|#^]+)", t):
            tgt = m.group(1).strip().split("/")[-1]
            if tgt in names or tgt in attachments or tgt + ".md" in attachments:
                continue
            bad.add(tgt)
        if bad:
            flag("BROKEN LINK", f"{rel} -> {', '.join(sorted(bad))}")

    # ---- 4. status vocabulary
    for folder, allowed in STATUS_OK.items():
        d = os.path.join(VAULT, folder)
        if not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            if not f.endswith(".md"):
                continue
            st = fm_field(read(os.path.join(d, f)), "status")
            if st and st.lower() not in allowed:
                flag("BAD STATUS",
                     f"{folder}/{f}: status '{st}' not in "
                     f"{sorted(allowed)}")

    # ---- 5. missing next action
    d = os.path.join(VAULT, "Efforts")
    for f in sorted(os.listdir(d)):
        if not f.endswith(".md") or f in ("Efforts.md", "Next Actions.md"):
            continue
        t = read(os.path.join(d, f))
        if not re.search(r"^##+[ \t]*Next action[ \t]*$", t, re.M):
            flag("NO NEXT ACTION",
                 f"Efforts/{f} has no '## Next action' section")

    # ---- 6. frontmatter
    for p in md:
        rel = os.path.relpath(p, VAULT)
        # The AIOS layer is instructions, not notes. So are the entry points
        # at the root: AI tools (CLAUDE.md, AGENTS.md) and GitHub's front page
        # (README.md) read them raw, where a YAML header is only clutter.
        if rel.startswith("AIOS") or rel in ("claude.md", "CLAUDE.md",
                                             "AGENTS.md", "README.md"):
            continue
        t = read(p)
        if not t.startswith("---"):
            flag("NO FRONTMATTER", rel)
        else:
            miss = [k for k in ("title", "tags") if fm_field(t, k) is None
                    and not re.search(rf"^{k}:\s*$", t[3:t.find(chr(10) + '---', 3)], re.M)]
            if miss:
                flag("FRONTMATTER", f"{rel} missing {miss}")

    # ---- 7. skill drift
    sd = os.path.join(VAULT, "AIOS", "skills")
    smp = os.path.join(VAULT, "AIOS", "skill-map.md")
    if os.path.isdir(sd) and os.path.exists(smp):
        smt = read(smp)
        for s in sorted(os.listdir(sd)):
            if not os.path.isdir(os.path.join(sd, s)):
                continue
            if f"`{s}`" not in smt:
                flag("SKILL DRIFT",
                     f"skill '{s}' is installed and mirrored but not listed "
                     f"in AIOS/skill-map.md")

    # ---- 8. note count
    # Scoped to the actual claim line ("**247 notes, per `vault-check.py`
    # on ...**"), not any stray "100 notes" mentioned in passing elsewhere
    # in the file — an earlier, looser regex flagged a brand-new vault as
    # stale just for explaining, in prose, when to re-scan this file.
    vm = os.path.join(VAULT, "AIOS", "vault-map.md")
    if os.path.exists(vm):
        claimed = re.findall(r"\*\*(\d+)\s+notes,\s+per", read(vm))
        actual = len(md)
        if claimed and not any(abs(int(c) - actual) <= 5 for c in claimed):
            flag("STALE COUNT",
                 f"vault-map.md says {' / '.join(claimed)} notes; actual is "
                 f"{actual} (excluding Privat/ and AIOS/skills/)")

    # ---- 9. sync conflicts
    # Dropbox renames a clashing file to "name (machine's conflicted copy
    # YYYY-MM-DD).ext". This scan deliberately ignores SKIP_DIRS/SKIP_PATHS and
    # looks everywhere except Privat/ and .git/, because the usual offender is
    # .obsidian/workspace.json — which every other check skips, which is why
    # nine of them piled up unnoticed on 2026-08-07.
    conflicts = []
    for dp, dns, fns in os.walk(VAULT):
        dns[:] = [d for d in dns if d not in ("Privat", ".git")]
        for fn in sorted(fns):
            if "conflicted copy" in fn.lower():
                conflicts.append(os.path.relpath(os.path.join(dp, fn), VAULT))
    notes = [c for c in conflicts if c.endswith(".md")]
    junk = [c for c in conflicts if not c.endswith(".md")]
    for c in notes:
        flag("CONFLICTED NOTE",
             f"{c} — two machines edited this note. Diff it against the "
             f"original before deleting; one version has edits the other "
             f"doesn't.")
    if junk:
        flag("SYNC JUNK",
             f"{len(junk)} conflicted-copy config file(s), safe to delete: "
             f"{', '.join(junk[:4])}"
             f"{' …' if len(junk) > 4 else ''}")

    # ---- report
    print(f"vault-check — {VAULT}")
    print(f"  {len(md)} notes, {len(bases)} bases, "
          f"Dataview installed: {dataview_installed}")
    print()
    if not problems:
        print("CLEAN — nothing to fix.")
        return 0
    cur = None
    for sect, msg in problems:
        if sect != cur:
            print(f"[{sect}]")
            cur = sect
        print(f"  - {msg}")
    print()
    print(f"{len(problems)} item(s) need attention. Nothing was changed.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
