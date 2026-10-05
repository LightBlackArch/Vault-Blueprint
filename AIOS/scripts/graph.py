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
    python3 AIOS/scripts/graph.py --selftest

Names match the way Obsidian does: case-insensitive, by file name, no folder,
no .md. Skips Privat/, AIOS/history/, AIOS/archive/, AIOS/skills/, .git,
.obsidian and .trash. No dependencies. Plain stdlib. Never reads Privat/.
"""
import os
import re
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
    print("graph.py selftest: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
