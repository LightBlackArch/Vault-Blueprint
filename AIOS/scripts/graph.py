#!/usr/bin/env python3
"""
graph.py — ask the vault "what connects to what" without reading a single note.

Builds a map of every [[wikilink]] between notes (a wikilink is Obsidian's
double-bracket link) and answers questions about it. Nothing is sent to an AI,
nothing is stored: it re-reads the links each run, takes about a second, and
costs zero tokens. Tools that build a "knowledge graph" with an AI pass do the
same job for the price of re-reading every note.

Usage:
    python3 AIOS/scripts/graph.py hubs [N]          # most-linked-to notes
    python3 AIOS/scripts/graph.py explain "Note"    # what links in, what it links to
    python3 AIOS/scripts/graph.py neighbors "Note"  # everything one link away
    python3 AIOS/scripts/graph.py path "A" "B"      # shortest chain of links A -> B
    python3 AIOS/scripts/graph.py lonely            # notes nothing links to
    python3 AIOS/scripts/graph.py suggest [N]       # connections nobody wrote: A names B, never links it
    python3 AIOS/scripts/graph.py unlinked "Note"   # where else "Note" is mentioned without a link
    python3 AIOS/scripts/graph.py ai "Note"         # ask an AI which notes it SHOULD link to, even unnamed ones
    python3 AIOS/scripts/graph.py --selftest

`ai` is the only command that uses an AI: it sends that one note (first 4000
characters) and the list of other note titles to your own `claude` command (Claude
Code, `claude -p`), prints its suggestions, and writes nothing. Everything else
here is local and free.

Names match the way Obsidian does: case-insensitive, by file name, no folder,
no .md. Skips Privat/, AIOS/history/, AIOS/archive/, AIOS/skills/, .git,
.obsidian and .trash. No dependencies. Plain stdlib. Never reads Privat/.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import defaultdict, deque

VAULT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
SKIP = ("Privat", ".git", ".obsidian", ".trash", ".claude",
        os.path.join("AIOS", "history"), os.path.join("AIOS", "archive"),
        os.path.join("AIOS", "skills"))
LINK = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")
CODE = re.compile(r"```.*?```|`[^`\n]*`", re.S)


def build(root=VAULT):
    """Return (names, out_links, in_links): names maps lowercase -> display name."""
    names, out, inn = {}, defaultdict(set), defaultdict(set)
    notes = []
    for d, dirs, files in os.walk(root):
        rel = os.path.relpath(d, root)
        dirs[:] = [x for x in dirs
                   if not any(os.path.join(rel, x).lstrip("./").startswith(s) for s in SKIP)]
        for f in files:
            if f.endswith(".md"):
                notes.append(os.path.join(d, f))
    for p in notes:
        n = os.path.splitext(os.path.basename(p))[0]
        names.setdefault(n.lower(), n)
    for p in notes:
        src = os.path.splitext(os.path.basename(p))[0].lower()
        try:
            text = open(p, encoding="utf-8", errors="ignore").read()
        except OSError:
            continue
        for m in LINK.finditer(CODE.sub("", text)):
            dst = os.path.splitext(os.path.basename(m.group(1).strip()))[0].lower()
            if dst in names and dst != src:
                out[src].add(dst)
                inn[dst].add(src)
    return names, out, inn


def mentions(root=VAULT):
    """Plain-text mentions of one note's title inside another note that never links to it.

    Returns {(source, target): count}. Titles under 5 characters, and titles that
    turn up in over 5% of all notes (words like "Efforts"), are too common to
    mean anything and are ignored.
    """
    names, out, _ = build(root)
    texts, noise = {}, set()
    for d, dirs, files in os.walk(root):
        rel = os.path.relpath(d, root)
        dirs[:] = [x for x in dirs
                   if not any(os.path.join(rel, x).lstrip("./").startswith(s) for s in SKIP)]
        for f in files:
            if f.endswith(".md"):
                key = os.path.splitext(f)[0].lower()
                # dated logs and machine-written files mention everything; they'd drown the signal
                if rel.startswith((os.path.join("Calendar", "Daily"), os.path.join("Calendar", "Weekly"),
                                   os.path.join("AIOS", "generated"))) or re.match(r"\d{4}-", key):
                    noise.add(key)
                    continue
                try:
                    t = open(os.path.join(d, f), encoding="utf-8", errors="ignore").read()
                except OSError:
                    continue
                t = LINK.sub(lambda m: " ", CODE.sub("", t))
                texts[os.path.splitext(f)[0].lower()] = re.findall(r"[A-Za-z0-9']+", t)
    # case-sensitive on purpose: "Reading" the note is not every sentence that starts with Reading
    titles = {k: tuple(re.findall(r"[A-Za-z0-9']+", names[k])) for k in names if len(k) >= 5 and k not in noise}
    by_len = defaultdict(dict)
    for k, tup in titles.items():
        by_len[len(tup)][tup] = k
    found, seen_in = defaultdict(int), defaultdict(set)
    for src, words in texts.items():
        for n, table in by_len.items():
            for i in range(len(words) - n + 1):
                k = table.get(tuple(words[i:i + n]))
                if k and k != src:
                    found[(src, k)] += 1
                    seen_in[k].add(src)
    common = {k for k, v in seen_in.items() if len(v) > max(3, 0.05 * len(texts))}
    return {pair: c for pair, c in found.items()
            if pair[1] not in common and pair[1] not in out[pair[0]]}, names


def note_path(root, key):
    for d, dirs, files in os.walk(root):
        rel = os.path.relpath(d, root)
        dirs[:] = [x for x in dirs
                   if not any(os.path.join(rel, x).lstrip("./").startswith(s) for s in SKIP)]
        for f in files:
            if f.endswith(".md") and os.path.splitext(f)[0].lower() == key:
                return os.path.join(d, f)


def ai_prompt(title, text, others):
    return ("Below is one note from a personal knowledge vault, then the titles of the other notes.\n"
            "List up to 8 other notes this note SHOULD link to, even if it never names them: "
            "same topic, a decision it depends on, a concept it uses. One per line, exactly "
            "`Title :: one-sentence reason`. Use only titles from the list. No other text.\n\n"
            f"NOTE TITLE: {title}\n{text[:4000]}\n\nOTHER TITLES:\n" + "\n".join(others[:400]))


def ai_suggest(root, query):
    names, out, inn = build(root)
    k = resolve(names, query)
    path = note_path(root, k)
    exe = shutil.which("claude")
    if not path or not exe:
        sys.exit("needs the `claude` command (Claude Code) on this machine" if path else "note not found")
    text = open(path, encoding="utf-8", errors="ignore").read()
    others = sorted(names[x] for x in names if x != k and x not in out[k])
    r = subprocess.run([exe, "-p", ai_prompt(names[k], text, others)], capture_output=True, text=True, timeout=180, stdin=subprocess.DEVNULL)
    if r.returncode:
        sys.exit("claude failed: " + (r.stderr.strip() or r.stdout.strip())[:300])
    valid = {names[x].lower() for x in names}
    kept = [ln for ln in r.stdout.splitlines() if "::" in ln and ln.split("::")[0].strip().lower() in valid]
    return kept


def resolve(names, q):
    k = os.path.splitext(q.strip())[0].lower()
    if k in names:
        return k
    close = [n for n in names if k in n]
    if len(close) == 1:
        return close[0]
    sys.exit(f"no note called '{q}'" + (f" — did you mean: {', '.join(sorted(names[c] for c in close)[:8])}"
                                          if close else ""))


def shortest(out, inn, a, b):
    """Shortest chain of links, following links in either direction."""
    prev, q = {a: None}, deque([a])
    while q:
        cur = q.popleft()
        if cur == b:
            break
        for nxt in sorted(out[cur] | inn[cur]):
            if nxt not in prev:
                prev[nxt] = cur
                q.append(nxt)
    if b not in prev:
        return None
    chain, cur = [], b
    while cur is not None:
        chain.append(cur)
        cur = prev[cur]
    return chain[::-1]


def fmt(names, keys):
    return ", ".join(names[k] for k in sorted(keys)) or "(none)"


def main(argv):
    if argv and argv[0] == "--selftest":
        return selftest()
    if not argv:
        print(__doc__)
        return 0
    names, out, inn = build()
    cmd, args = argv[0], argv[1:]
    if cmd == "hubs":
        n = int(args[0]) if args else 15
        rows = sorted(names, key=lambda k: (-len(inn[k]), k))[:n]
        for k in rows:
            print(f"{len(inn[k]):4d} in  {len(out[k]):3d} out  {names[k]}")
    elif cmd == "lonely":
        for k in sorted(names):
            if not inn[k]:
                print(names[k])
    elif cmd in ("explain", "neighbors") and args:
        k = resolve(names, args[0])
        if cmd == "neighbors":
            print(fmt(names, out[k] | inn[k]))
        else:
            print(f"{names[k]}\n  linked from ({len(inn[k])}): {fmt(names, inn[k])}"
                  f"\n  links to    ({len(out[k])}): {fmt(names, out[k])}")
    elif cmd == "suggest":
        found, nm = mentions()
        n = int(args[0]) if args else 15
        for (src, dst), c in sorted(found.items(), key=lambda x: (-x[1], x[0]))[:n]:
            print(f"{nm[src]}  mentions  {nm[dst]}  ({c}x, no link)")
    elif cmd == "unlinked" and args:
        found, nm = mentions()
        k = resolve(names, args[0])
        rows = sorted(((nm[s_], c) for (s_, d_), c in found.items() if d_ == k), key=lambda x: (-x[1], x[0]))
        print("\n".join(f"{n}  ({c}x)" for n, c in rows) or "no unlinked mentions")
    elif cmd == "ai" and args:
        print("\n".join(ai_suggest(VAULT, args[0])) or "no suggestions it could stand behind")
    elif cmd == "path" and len(args) == 2:
        a, b = resolve(names, args[0]), resolve(names, args[1])
        chain = shortest(out, inn, a, b)
        print(" -> ".join(names[k] for k in chain) if chain else "no chain of links connects them")
        return 0 if chain else 1
    else:
        print(__doc__)
        return 2
    return 0


def selftest():
    with tempfile.TemporaryDirectory() as t:
        def w(name, text):
            os.makedirs(os.path.dirname(os.path.join(t, name)), exist_ok=True)
            open(os.path.join(t, name), "w").write(text)
        w("A.md", "[[B]] and [[b|alias]] and `[[Ignored]]`")
        w("sub/B.md", "see [[C#heading]]")
        w("C.md", "end")
        w("D.md", "alone [[A]]")
        w("Privat/secret.md", "[[A]]")
        w("AIOS/history/log.md", "[[C]]")
        names, out, inn = build(t)
        assert set(names) == {"a", "b", "c", "d"}, names          # Privat + history skipped
        assert out["a"] == {"b"} and "ignored" not in out["a"]     # code spans ignored
        assert shortest(out, inn, "a", "c") == ["a", "b", "c"]
        assert shortest(out, inn, "d", "c") == ["d", "a", "b", "c"]
        assert len(inn["a"]) == 1                                  # only D; Privat not read
        w("E.md", "Today I read about the Banana Bread note and Banana Bread again, not banana bread.")
        w("Banana Bread.md", "recipe")
        w("F.md", "I linked [[Banana Bread]] properly.")
        found, nm = mentions(t)
        assert found.get(("e", "banana bread")) == 2, found       # named twice, never linked
        assert ("f", "banana bread") not in found                  # already linked: not a suggestion
        assert not any(k[1] in ("a", "b", "c", "d") for k in found)  # short titles ignored
        if os.name != "nt":                                       # the stand-in is a shell script
            # ai: a stand-in `claude` that answers with one real and one invented title
            stub = os.path.join(t, "bin")
            os.makedirs(stub)
            open(os.path.join(stub, "claude"), "w").write(
                "#!/bin/sh\nprintf 'Banana Bread :: it is about recipes\\nMade Up Note :: invented\\n'\n")
            os.chmod(os.path.join(stub, "claude"), 0o755)
            old_path = os.environ["PATH"]
            os.environ["PATH"] = stub + os.pathsep + old_path
            try:
                got = ai_suggest(t, "A")
            finally:
                os.environ["PATH"] = old_path
            assert got == ["Banana Bread :: it is about recipes"], got   # invented titles are dropped
        assert "Privat" not in ai_prompt("A", "x", ["Banana Bread"])
    print("graph.py selftest: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
