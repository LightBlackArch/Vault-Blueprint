#!/usr/bin/env python3
"""
search.py — find the right note by what you mean, ranked, without reading the vault.

    python3 AIOS/scripts/search.py "how do I back up my chats"        # best matches first
    python3 AIOS/scripts/search.py "bike brakes" --top 5
    python3 AIOS/scripts/search.py "automobile repair" --semantic     # matches by meaning too
    python3 AIOS/scripts/search.py --selftest

Two modes:

  Default — ranked word search (BM25, the formula most search engines use).
  Notes are scored by how often your words appear, how rare those words are
  across the vault, and the note's length; the title counts triple. Light
  stemming means "backups" finds "backing up". Instant, offline, free.

  --semantic — also matches by MEANING, so "automobile" finds a note that only
  says "car". It asks a local embedding model (a program that turns text into a
  list of numbers where similar meanings sit close together) running on your own
  machine through Ollama (free, ollama.com; `ollama pull nomic-embed-text`).
  Nothing leaves your computer. Vectors are cached in
  AIOS/generated/embeddings.json and only changed notes are re-sent. If Ollama
  isn't running, it says so and falls back to the default mode instead of failing.
  Set OLLAMA_HOST (default http://localhost:11434) or EMBED_MODEL to change it.

Keeps its word counts in AIOS/generated/search-index.json and re-reads only notes
whose file date changed, so it stays fast as the vault grows.

Skips Privat/, AIOS/history/, AIOS/archive/, AIOS/skills/, .git, .obsidian,
.trash. No dependencies. Plain stdlib. Never reads Privat/.
"""
import json
import math
import os
import re
import sys
import tempfile
import threading
import urllib.error
import urllib.request
from collections import Counter

VAULT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
SKIP = ("Privat", ".git", ".obsidian", ".trash", ".claude",
        os.path.join("AIOS", "history"), os.path.join("AIOS", "archive"),
        os.path.join("AIOS", "skills"), os.path.join("AIOS", "generated"))
STOP = set("a an the and or of to in on for is are was were be it this that with as at by from i you my me".split())
MAX_EMBED_CHARS = 4000


def tokens(text):
    out = []
    for w in re.findall(r"[a-z0-9]+", text.lower()):
        if len(w) < 2 or w in STOP:
            continue
        for suf in ("ing", "ies", "ed", "es", "s", "ly"):
            if w.endswith(suf) and len(w) - len(suf) >= 3:
                w = w[: -len(suf)] + ("y" if suf == "ies" else "")
                break
        out.append(w)
    return out


INDEX = os.path.join("AIOS", "generated", "search-index.json")
READS = {"n": 0}                     # how many notes were opened; the selftest watches this


def read_note(path):
    READS["n"] += 1
    return open(path, encoding="utf-8", errors="ignore").read()


def list_notes(root=VAULT):
    """{relative path: mtime} for every note. Only looks at file dates; opens nothing."""
    notes = {}
    for d, dirs, files in os.walk(root):
        rel = os.path.relpath(d, root)
        dirs[:] = [x for x in dirs
                   if not any(os.path.join(rel, x).lstrip("./").startswith(s) for s in SKIP)]
        for f in files:
            if f.endswith(".md"):
                p = os.path.join(d, f)
                try:
                    notes[os.path.relpath(p, root)] = os.path.getmtime(p)
                except OSError:
                    pass
    return notes


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    json.dump(data, open(tmp, "w", encoding="utf-8"))
    os.replace(tmp, path)


def build_index(root, listing):
    """Word counts per note, kept on disk. Only notes whose date changed are read again."""
    ip = os.path.join(root, INDEX)
    try:
        cache = json.load(open(ip, encoding="utf-8"))
    except (OSError, ValueError):
        cache = {}
    changed = False
    for p, m in listing.items():
        if cache.get(p, {}).get("mtime") != m:
            toks = tokens(os.path.splitext(os.path.basename(p))[0]) * 3 + tokens(read_note(os.path.join(root, p)))
            cache[p] = {"mtime": m, "tf": dict(Counter(toks)), "len": len(toks)}
            changed = True
    for p in [k for k in cache if k not in listing]:
        del cache[p]
        changed = True
    if changed:
        save_json(ip, cache)
    return {p: cache[p] for p in listing}


def bm25(docs, query, k1=1.5, b=0.75):
    n = len(docs) or 1
    avg = sum(d["len"] for d in docs.values()) / n or 1
    df = Counter(w for d in docs.values() for w in d["tf"])
    q = set(tokens(query))
    scores = {}
    for p, d in docs.items():
        s = 0.0
        for w in q:
            f = d["tf"].get(w, 0)
            if f:
                idf = math.log(1 + (n - df[w] + 0.5) / (df[w] + 0.5))
                s += idf * f * (k1 + 1) / (f + k1 * (1 - b + b * d["len"] / avg))
        if s:
            scores[p] = s
    return scores


def embed(text, model, host):
    """One vector for `text`. Uses Ollama's current /api/embed; older servers get /api/embeddings."""
    def post(path, body):
        req = urllib.request.Request(host.rstrip("/") + path, json.dumps(body).encode(),
                                     {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    text = text[:MAX_EMBED_CHARS]
    try:
        return post("/api/embed", {"model": model, "input": text})["embeddings"][0]
    except urllib.error.HTTPError as e:
        if e.code != 404:                       # 404 = old server (or model missing, which the fallback also reports)
            raise
    return post("/api/embeddings", {"model": model, "prompt": text})["embedding"]


def cosine(a, b):
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(x * x for x in b))
    return sum(x * y for x, y in zip(a, b)) / (na * nb) if na and nb else 0.0


def semantic(listing, query, root, model, host):
    """Cosine score per note against the query. Raises if the model is unreachable."""
    cache_path = os.path.join(root, "AIOS", "generated", "embeddings.json")
    try:
        cache = json.load(open(cache_path, encoding="utf-8"))
    except (OSError, ValueError):
        cache = {}
    if cache.get("_model") != model:
        cache = {"_model": model}
    qv = embed(query, model, host)
    for p, mtime in listing.items():
        if cache.get(p, {}).get("mtime") != mtime:
            cache[p] = {"mtime": mtime,
                        "v": embed(os.path.basename(p) + "\n" + read_note(os.path.join(root, p)), model, host)}
    for p in [k for k in cache if k != "_model" and k not in listing]:
        del cache[p]
    save_json(cache_path, cache)
    return {p: cosine(qv, cache[p]["v"]) for p in listing}


def fuse(*rankings):
    """Reciprocal rank fusion: a note near the top of either list rises."""
    out = Counter()
    for r in rankings:
        for i, p in enumerate(sorted(r, key=r.get, reverse=True)):
            out[p] += 1 / (60 + i)
    return out


def snippet(text, query):
    q = set(tokens(query))
    for line in text.splitlines():
        if line.strip() and not line.startswith(("---", "#")) and q & set(tokens(line)):
            return re.sub(r"\s+", " ", line.strip())[:140]
    return ""


def search(query, root=VAULT, top=8, use_semantic=False, model=None, host=None):
    listing = list_notes(root)
    ranks = [bm25(build_index(root, listing), query)]
    note = ""
    if use_semantic:
        try:
            ranks.append(semantic(listing, query, root, model or os.environ.get("EMBED_MODEL", "nomic-embed-text"),
                                  host or os.environ.get("OLLAMA_HOST", "http://localhost:11434")))
        except Exception as e:
            note = f"(--semantic unavailable: {e}. Showing word-ranked results. Is Ollama running?)"
    final = fuse(*ranks) if len(ranks) > 1 else ranks[0]
    rows = sorted(final, key=final.get, reverse=True)[:top]
    return [(p, snippet(read_note(os.path.join(root, p)), query)) for p in rows], note


def main(argv):
    if argv and argv[0] == "--selftest":
        return selftest()
    if not argv or argv[0].startswith("--"):
        print(__doc__)
        return 0
    top = int(argv[argv.index("--top") + 1]) if "--top" in argv else 8
    rows, note = search(argv[0], top=top, use_semantic="--semantic" in argv)
    if note:
        print(note)
    for p, s in rows:
        print(f"{p}" + (f"\n    {s}" if s else ""))
    if not rows:
        print("no matches")
    return 0 if rows else 1


def selftest():
    import http.server

    class Fake(http.server.BaseHTTPRequestHandler):
        """Stands in for Ollama: 'car' and 'automobile' share a dimension, so meaning can match without words.
        OLD=True imitates a server that only has the deprecated /api/embeddings."""
        OLD = False

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            new_api = self.path == "/api/embed"
            if (new_api and Fake.OLD) or self.path not in ("/api/embed", "/api/embeddings"):
                self.send_response(404)
                self.end_headers()
                return
            low = (body["input"] if new_api else body["prompt"]).lower()
            vec = [1.0 if ("car" in low or "automobile" in low) else 0.0,
                   1.0 if "bread" in low else 0.0, 0.01]
            data = json.dumps({"embeddings": [vec]} if new_api else {"embedding": vec}).encode()
            self.send_response(200)
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *a):
            pass

    with tempfile.TemporaryDirectory() as t:
        def w(name, text):
            os.makedirs(os.path.dirname(os.path.join(t, name)), exist_ok=True)
            open(os.path.join(t, name), "w").write(text)
        w("Efforts/Car Repair.md", "Replacing the brake pads on the car. Brakes were squealing.")
        w("Efforts/Baking.md", "Bread recipe: flour, water, salt. Backups of the starter.")
        w("Atlas/Backups.md", "How I back up my chats every hour, a backup of everything.")
        w("Privat/diary.md", "brake pads secret")
        w("AIOS/history/old.md", "brake pads history")
        rows, _ = search("brakes", t)
        assert [p for p, _ in rows][0] == os.path.join("Efforts", "Car Repair.md"), rows   # ranked, Privat/history skipped
        assert len(rows) == 1, rows
        rows, _ = search("backing up chats", t)
        assert rows[0][0] == os.path.join("Atlas", "Backups.md"), rows                     # stemming: backing/back up
        assert tokens("Backups") == tokens("backup") or tokens("backups")[0].startswith("backup")
        # the saved index: later searches open only the few result notes, not the whole vault
        for i in range(40):
            w(f"Filler/n{i}.md", f"filler note number {i} about gardening")
        search("gardening", t)                                  # builds the index (reads everything once)
        before = READS["n"]
        search("brakes", t)
        assert READS["n"] - before <= 8, READS["n"] - before    # only result snippets, not 44 notes
        w("Filler/new.md", "a fresh note about telescopes")
        before = READS["n"]
        rows, _ = search("telescopes", t)
        assert rows[0][0] == os.path.join("Filler", "new.md") and READS["n"] - before <= 3
        os.remove(os.path.join(t, "Filler", "new.md"))
        assert search("telescopes", t)[0] == []                 # deleted notes drop out of the index
        # by meaning: 'automobile' is not in any note, only the embedding links it to 'car'
        assert search("automobile", t)[0] == []
        srv = http.server.HTTPServer(("127.0.0.1", 0), Fake)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        host = f"http://127.0.0.1:{srv.server_port}"
        rows, note = search("automobile", t, use_semantic=True, host=host)
        assert not note and rows[0][0] == os.path.join("Efforts", "Car Repair.md"), (rows, note)
        assert os.path.exists(os.path.join(t, "AIOS", "generated", "embeddings.json"))
        Fake.OLD = True                                                       # an older Ollama: fallback endpoint
        os.remove(os.path.join(t, "AIOS", "generated", "embeddings.json"))
        rows, note = search("automobile", t, use_semantic=True, host=host)
        assert not note and rows[0][0] == os.path.join("Efforts", "Car Repair.md"), (rows, note)
        srv.shutdown()
        rows, note = search("brakes", t, use_semantic=True, host="http://127.0.0.1:9")   # nothing listening
        assert "unavailable" in note and rows, (rows, note)                              # falls back, doesn't fail
    print("search.py selftest: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
