#!/usr/bin/env python3
"""
dream.py — turn corrections you keep making into rules that earn trust, and
let unused ones fade.

Every time the user corrects the AI, or states a preference, record it:

    python3 AIOS/scripts/dream.py signal "never delete files without asking"

The same signal three times makes it a CONFIRMED rule. A rule gains confidence
from repetition and loses it with time unless it is used again. One that sits
unused for 120 days EXPIRES (kept for the record, no longer shown as live).
No AI runs inside this: it is counting and a date formula, so the same data
always gives the same answer.

    python3 AIOS/scripts/dream.py signal "<rule>" [--date YYYY-MM-DD]
    python3 AIOS/scripts/dream.py use "<rule or id>"   # it came up again and held
    python3 AIOS/scripts/dream.py pin "<rule or id>"   # you reviewed it: confirmed, never expires
    python3 AIOS/scripts/dream.py reject "<rule or id>" # wrong: kept on record, never learned again
    python3 AIOS/scripts/dream.py run                  # recompute, rewrite the report
    python3 AIOS/scripts/dream.py list
    python3 AIOS/scripts/dream.py rollback             # undo the last change
    python3 AIOS/scripts/dream.py --selftest

Confidence = min(1, count / 5) x 0.5 ^ (days since last seen / 45).
Confirmed = seen 3+ times AND confidence >= 0.4. Expired = unseen 120+ days.
A confirmed rule stays "not yet reviewed" in the report until you `pin` it, so nothing
becomes a standing rule without you seeing it. `reject` is permanent and survives rollback of other changes.

Data: AIOS/data/rules.json. Report (never hand-edit): AIOS/generated/learned-rules.md.
Every change first copies the data to AIOS/history/dream-snapshots/ (newest 20
kept), which is what `rollback` restores. No dependencies. Plain stdlib.
"""
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile

VAULT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
HALF_LIFE, EXPIRE_DAYS, CONFIRM_COUNT, CONFIRM_CONF, KEEP = 45, 120, 3, 0.4, 20


def paths(root):
    return (os.path.join(root, "AIOS", "data", "rules.json"),
            os.path.join(root, "AIOS", "generated", "learned-rules.md"),
            os.path.join(root, "AIOS", "history", "dream-snapshots"))


def norm(text):
    return re.sub(r"[^a-z0-9 ]+", "", text.lower()).strip()


def rid(text):
    return hashlib.sha1(norm(text).encode()).hexdigest()[:8]


STOPW = set("a an the and or of to in on for is are was were be it this that with as at by from i you my me me please just do does not dont no".split())


def words(text):
    return {w for w in norm(text).split() if w not in STOPW and len(w) > 2}


def similar(a, b):
    """Same rule, said differently: shared meaningful words / all meaningful words >= 0.6."""
    wa, wb = words(a), words(b)
    return bool(wa and wb) and len(wa & wb) / len(wa | wb) >= 0.6


def load(root):
    p = paths(root)[0]
    if not os.path.exists(p):
        return {"rules": {}}
    return json.load(open(p, encoding="utf-8"))


def save(root, data):
    """Snapshot what is there, then replace the file in one step (no half-written state)."""
    p, _, snaps = paths(root)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    if os.path.exists(p):
        os.makedirs(snaps, exist_ok=True)
        stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        shutil.copy2(p, os.path.join(snaps, f"rules-{stamp}.json"))
        for old in sorted(os.listdir(snaps))[:-KEEP]:
            os.remove(os.path.join(snaps, old))
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)
    os.replace(tmp, p)


def score(rule, today):
    age = max(0, (today - dt.date.fromisoformat(rule["last"])).days)
    conf = min(1.0, rule["count"] / 5) * 0.5 ** (age / HALF_LIFE)
    if rule.get("rejected"):
        return 0.0, "rejected", age
    if rule.get("pinned"):
        return max(conf, 0.4), "confirmed", age
    if age >= EXPIRE_DAYS:
        status = "expired"
    elif rule["count"] >= CONFIRM_COUNT and conf >= CONFIRM_CONF:
        status = "confirmed"
    else:
        status = "candidate"
    return round(conf, 2), status, age


def report(root, today):
    data, rows = load(root), []
    for r in data["rules"].values():
        conf, status, age = score(r, today)
        rows.append((status, conf, age, r))
    out = ["---", "title: Learned rules", "tags:", "  - generated", "---", "",
           "# Learned rules", "",
           f"> Machine-written by `dream.py run` on {today}. Never hand-edit; record a "
           "correction with `dream.py signal`. Confidence rises with repetition and "
           f"halves every {HALF_LIFE} days unused.", ""]
    for title, key in (("Confirmed", "confirmed"), ("Candidates (not yet seen enough)", "candidate"),
                       (f"Expired (unseen {EXPIRE_DAYS}+ days)", "expired"), ("Rejected (never learned again)", "rejected")):
        sel = sorted((x for x in rows if x[0] == key), key=lambda x: (-x[1], x[3]["text"]))
        if key == "confirmed":
            sel = [x for x in sel if x[3].get("pinned")] + [x for x in sel if not x[3].get("pinned")]
        out += [f"## {title}", ""]
        out += [f"- **{c:.2f}** {r['text']} — seen {r['count']}x, last {r['last']} (`{rid(r['text'])}`)"
                + (" — pinned" if r.get("pinned") else " — not yet reviewed; `dream.py pin` or `reject`" if key == "confirmed" else "")
                for _, c, _, r in sel] or ["- none"]
        out.append("")
    p = paths(root)[1]
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w", encoding="utf-8").write("\n".join(out))
    return rows


def find(data, key):
    """A rule by id prefix, exact wording, or reworded match."""
    k = rid(key)
    if k in data["rules"]:
        return k
    return next((x for x, v in data["rules"].items() if x.startswith(key.strip()) or similar(v["text"], key)), None)


def mark(root, key, field):
    data = load(root)
    k = find(data, key)
    if k is None:
        sys.exit(f"no rule matches '{key}'")
    data["rules"][k][field] = True
    if field == "rejected":
        data["rules"][k].pop("pinned", None)
    else:
        data["rules"][k].pop("rejected", None)
    save(root, data)
    return data["rules"][k]


def signal(root, text, day, bump=1, use=False):
    data = load(root)
    k = rid(text)
    r = data["rules"].get(k)
    if r is None and use:
        k = next((x for x in data["rules"] if x.startswith(text.strip())), None)
        r = data["rules"].get(k)
        if r is None:
            sys.exit(f"no rule matches '{text}'")
    if r is None and not use:                      # said differently before? count it as the same rule
        k = next((x for x, v in data["rules"].items() if similar(v["text"], text)), k)
        r = data["rules"].get(k)
    if r is not None and r.get("rejected"):
        return r                                   # rejected rules are never counted again
    if r is None:
        r = data["rules"][k] = {"text": text.strip(), "count": 0, "first": day, "last": day, "uses": 0}
    if use:
        r["uses"] += 1
    else:
        r["count"] += bump
    r["last"] = max(r["last"], day)
    save(root, data)
    return r


def rollback(root):
    snaps = paths(root)[2]
    files = sorted(os.listdir(snaps)) if os.path.isdir(snaps) else []
    if not files:
        sys.exit("nothing to roll back to")
    last = os.path.join(snaps, files[-1])
    os.replace(last, paths(root)[0])        # the snapshot becomes the live file again
    return files[-1]


def main(argv):
    if argv and argv[0] == "--selftest":
        return selftest()
    if not argv or argv[0] not in ("signal", "use", "run", "list", "rollback", "pin", "reject"):
        print(__doc__)
        return 0
    cmd, rest = argv[0], argv[1:]
    day = dt.date.today().isoformat()
    if "--date" in rest:
        i = rest.index("--date")
        day = rest[i + 1]
        dt.date.fromisoformat(day)
        rest = rest[:i] + rest[i + 2:]
    if cmd in ("signal", "use"):
        if not rest:
            sys.exit(f"usage: dream.py {cmd} \"<rule>\"")
        r = signal(VAULT, rest[0], day, use=(cmd == "use"))
        conf, status, _ = score(r, dt.date.fromisoformat(day))
        print(f"{status} {conf:.2f}: {r['text']} (seen {r['count']}x)")
    elif cmd in ("pin", "reject"):
        if not rest:
            sys.exit(f"usage: dream.py {cmd} \"<rule or id>\"")
        r = mark(VAULT, rest[0], "pinned" if cmd == "pin" else "rejected")
        print(f"{'pinned' if cmd == 'pin' else 'rejected'}: {r['text']}")
    elif cmd == "rollback":
        print("restored", rollback(VAULT))
    else:
        rows = report(VAULT, dt.date.today())
        if cmd == "run":
            print(f"learned-rules.md rewritten: {sum(1 for x in rows if x[0]=='confirmed')} confirmed, "
                  f"{sum(1 for x in rows if x[0]=='candidate')} candidate, "
                  f"{sum(1 for x in rows if x[0]=='expired')} expired")
        else:
            for status, c, age, r in sorted(rows, key=lambda x: (x[0], -x[1])):
                print(f"{status:9} {c:.2f} {age:4d}d  {r['text']}")
    return 0


def selftest():
    with tempfile.TemporaryDirectory() as t:
        d0 = dt.date(2026, 1, 1)
        for i in range(3):
            signal(t, "Never delete files without asking!", (d0 + dt.timedelta(days=i)).isoformat())
        signal(t, "use short answers", d0.isoformat())
        data = load(t)
        assert len(data["rules"]) == 2                      # punctuation/case don't split a rule
        n_before = next(r for r in data["rules"].values() if r["count"] == 3)["count"]
        signal(t, "don't delete files without asking me", d0.isoformat())     # reworded: same rule
        assert len(load(t)["rules"]) == 2 and next(r for r in load(t)["rules"].values() if r["count"] == 4)
        signal(t, "always use metric units", d0.isoformat())                   # different rule stays separate
        assert len(load(t)["rules"]) == 3
        rollback(t); rollback(t)
        data = load(t)
        assert len(data["rules"]) == 2 and next(r for r in data["rules"].values() if r["count"] == 3)
        conf, status, _ = score(next(r for r in data["rules"].values() if r["count"] == 3), d0 + dt.timedelta(days=2))
        assert status == "confirmed" and conf == 0.6, (conf, status)
        # decay: 45 days later confidence halves; 120 days later it expires
        r3 = next(r for r in data["rules"].values() if r["count"] == 3)
        assert score(r3, d0 + dt.timedelta(days=2 + 45))[0] == 0.3
        assert score(r3, d0 + dt.timedelta(days=2 + 45))[1] == "candidate"
        assert score(r3, d0 + dt.timedelta(days=2 + 120))[1] == "expired"
        # using a rule resets its clock
        signal(t, rid("never delete files without asking"), (d0 + dt.timedelta(days=100)).isoformat(), use=True)
        assert score(load(t)["rules"][rid("Never delete files without asking")],
                     d0 + dt.timedelta(days=100))[1] == "confirmed"
        # snapshot + rollback: undo the last signal
        before = load(t)["rules"][rid("use short answers")]["count"]
        signal(t, "use short answers", d0.isoformat())
        assert load(t)["rules"][rid("use short answers")]["count"] == before + 1
        rollback(t)
        assert load(t)["rules"][rid("use short answers")]["count"] == before
        # pin: confirmed and never expires; reject: stays on record, never counted again
        k = rid("use short answers")
        mark(t, "use short", "pinned")
        assert score(load(t)["rules"][k], d0 + dt.timedelta(days=900))[1] == "confirmed"
        mark(t, k[:4], "rejected")
        c0 = load(t)["rules"][k]["count"]
        signal(t, "use short answers", d0.isoformat())
        assert load(t)["rules"][k]["count"] == c0 and score(load(t)["rules"][k], d0)[1] == "rejected"
        report(t, d0 + dt.timedelta(days=100))
        assert "## Rejected" in open(paths(t)[1]).read()
        assert "## Confirmed" in open(paths(t)[1]).read()
    print("dream.py selftest: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
