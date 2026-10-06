#!/usr/bin/env python3
"""
vault — the one command. Six verbs, nothing else to learn.

    python3 vault find "words"            find the best-matching notes (add --semantic for meaning)
    python3 vault links "Note"            what links to it and from it   (two notes = shortest path,
                                          none = the most-connected notes, --ideas = missing links)
    python3 vault remember "never ..."    teach it a rule; say it 3 times and it sticks
                                          (no words = list rules; `pin X` keeps one, `reject X` drops one)
    python3 vault recent [N | word]       what past Claude Code sessions here were about
    python3 vault check [--tests]         is the vault healthy (and do all the scripts still work)
    python3 vault update                  see what the blueprint changed (--apply all, --undo)

Each verb just runs one of the scripts in AIOS/scripts/, so everything they do is still
available directly. `python3 AIOS/scripts/vault.py --selftest` checks the routing.
No dependencies. Plain stdlib.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def plan(argv):
    """The scripts to run for this command: a list of [script, *args], or None if unknown."""
    if not argv:
        return None
    v, a = argv[0], argv[1:]
    if v == "find" and a:
        return [["search.py", " ".join(x for x in a if not x.startswith("--")), *[x for x in a if x.startswith("--")]]]
    if v == "links":
        if not a:
            return [["graph.py", "hubs"]]
        if a == ["--ideas"]:
            return [["graph.py", "suggest"]]
        return [["graph.py", "path", *a]] if len(a) == 2 else [["graph.py", "explain", " ".join(a)]]
    if v == "remember":
        if not a:
            return [["dream.py", "list"]]
        if a[0] in ("pin", "reject") and len(a) > 1:
            return [["dream.py", a[0], " ".join(a[1:])]]
        return [["dream.py", "signal", " ".join(a)]]
    if v == "recent":
        if not a:
            return [["session-digest.py", "recent"]]
        return [["session-digest.py", "recent", a[0]]] if a[0].isdigit() else [["session-digest.py", "find", " ".join(a)]]
    if v == "check":
        return [["vault-check.py"], ["stale-check.py"]] + ([["selftest-all.py"]] if "--tests" in a else [])
    if v == "update":
        return [["blueprint-update.py", *a]]
    return None


def selftest():
    assert plan(["find", "back", "up", "--semantic"]) == [["search.py", "back up", "--semantic"]]
    assert plan(["links"]) == [["graph.py", "hubs"]] and plan(["links", "--ideas"]) == [["graph.py", "suggest"]]
    assert plan(["links", "A", "B"]) == [["graph.py", "path", "A", "B"]]
    assert plan(["remember", "never", "x"]) == [["dream.py", "signal", "never x"]]
    assert plan(["remember"]) == [["dream.py", "list"]] and plan(["remember", "pin", "x"]) == [["dream.py", "pin", "x"]]
    assert plan(["recent", "3"]) == [["session-digest.py", "recent", "3"]]
    assert plan(["recent", "bike"]) == [["session-digest.py", "find", "bike"]]
    assert plan(["check", "--tests"])[-1] == ["selftest-all.py"] and len(plan(["check"])) == 2
    assert plan(["update", "--apply", "all"]) == [["blueprint-update.py", "--apply", "all"]]
    assert plan(["nope"]) is None and plan([]) is None and plan(["find"]) is None
    for v in ("find", "links", "remember", "recent", "check", "update"):
        assert v in __doc__
    for cmds in (plan(["find", "x"]), plan(["links"]), plan(["remember"]), plan(["recent"]),
                 plan(["check", "--tests"]), plan(["update"])):
        for c in cmds:
            assert os.path.exists(os.path.join(HERE, c[0])), f"{c[0]} is missing"
    print("vault.py selftest: ok")
    return 0


def main(argv):
    if argv == ["--selftest"]:
        return selftest()
    cmds = plan(argv)
    if cmds is None:
        print(__doc__)
        return 0 if not argv or argv[0] in ("help", "-h", "--help") else 2
    bad = 0
    for script, *args in cmds:
        bad |= subprocess.call([sys.executable, os.path.join(HERE, script), *args]) != 0
    return bad


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
