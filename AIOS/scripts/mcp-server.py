#!/usr/bin/env python3
"""
mcp-server.py — lets any MCP-capable AI tool use this vault's search, links,
session history and learned rules directly.

MCP (Model Context Protocol) is a standard way for an AI app to call tools
offered by a program. This is a tiny server speaking it over standard input and
output, with no dependencies and no network. It adds nothing new: each tool just
runs one of this vault's own scripts and returns what it printed.

Tools: search, graph_explain, graph_path, graph_suggest, sessions_find,
       rules_list, rules_signal

Connect it (once, from the vault folder):
    claude mcp add vault -- python3 "$PWD/AIOS/scripts/mcp-server.py"
Other tools (Codex, Cursor, Claude Desktop): add a stdio server whose command is
`python3` and whose argument is the full path to this file.

    python3 AIOS/scripts/mcp-server.py --selftest

Read-only except `rules_signal`, which records one rule in AIOS/data/rules.json
(undo with `dream.py rollback`). Never reads Privat/.
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = {
    "search": ("Ranked search of the vault's notes by what you mean. Returns best-matching note paths with a snippet.",
               {"query": "string", "top": "integer?"}, lambda a: ["search.py", a["query"], "--top", str(a.get("top", 8))]),
    "graph_explain": ("What links to a note and what it links to.",
                      {"note": "string"}, lambda a: ["graph.py", "explain", a["note"]]),
    "graph_path": ("Shortest chain of links between two notes.",
                   {"a": "string", "b": "string"}, lambda a: ["graph.py", "path", a["a"], a["b"]]),
    "graph_suggest": ("Notes that name each other in plain text but never link.",
                      {"n": "integer?"}, lambda a: ["graph.py", "suggest", str(a.get("n", 15))]),
    "sessions_find": ("Past Claude Code sessions in this vault whose request or edited files mention a word.",
                      {"word": "string"}, lambda a: ["session-digest.py", "find", a["word"]]),
    "rules_list": ("Learned rules with confidence and status.",
                   {}, lambda a: ["dream.py", "list"]),
    "rules_signal": ("Record that a rule/preference/correction came up again (3+ times confirms it).",
                     {"rule": "string"}, lambda a: ["dream.py", "signal", a["rule"]]),
}


def schema(props):
    return {"type": "object",
            "properties": {k: {"type": v.rstrip("?")} for k, v in props.items()},
            "required": [k for k, v in props.items() if not v.endswith("?")]}


def call(name, args):
    if name not in TOOLS:
        return f"unknown tool {name}", True
    desc, props, build = TOOLS[name]
    for k, v in props.items():
        if not v.endswith("?") and k not in args:
            return f"missing argument: {k}", True
    try:
        argv = build(args)
        r = subprocess.run([sys.executable, os.path.join(HERE, argv[0])] + argv[1:],
                           capture_output=True, text=True, timeout=120, cwd=os.path.join(HERE, "..", ".."))
        return (r.stdout + r.stderr).strip() or "(no output)", r.returncode not in (0, 1)
    except Exception as e:                       # a tool failure is a result, never a crash
        return f"failed: {e}", True


def handle(msg):
    """One JSON-RPC message in, one reply out (None for notifications)."""
    mid, method, params = msg.get("id"), msg.get("method", ""), msg.get("params") or {}
    if mid is None:
        return None                                 # notifications/initialized etc: no reply
    if method == "initialize":
        res = {"protocolVersion": params.get("protocolVersion", "2024-11-05"),
               "capabilities": {"tools": {}}, "serverInfo": {"name": "vault", "version": "1.0"}}
    elif method == "tools/list":
        res = {"tools": [{"name": n, "description": d, "inputSchema": schema(p)} for n, (d, p, _) in TOOLS.items()]}
    elif method == "tools/call":
        text, err = call(params.get("name", ""), params.get("arguments") or {})
        res = {"content": [{"type": "text", "text": text}], "isError": err}
    elif method == "ping":
        res = {}
    else:
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"no such method: {method}"}}
    return {"jsonrpc": "2.0", "id": mid, "result": res}


def selftest():
    r = handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-03-26"}})
    assert r["result"]["protocolVersion"] == "2025-03-26" and "tools" in r["result"]["capabilities"]
    assert handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
    tools = handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})["result"]["tools"]
    assert {t["name"] for t in tools} == set(TOOLS) and all(t["inputSchema"]["type"] == "object" for t in tools)
    assert handle({"jsonrpc": "2.0", "id": 3, "method": "nope"})["error"]["code"] == -32601
    bad = handle({"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "search", "arguments": {}}})
    assert bad["result"]["isError"] and "missing" in bad["result"]["content"][0]["text"]
    ok = handle({"jsonrpc": "2.0", "id": 5, "method": "tools/call",
                 "params": {"name": "graph_suggest", "arguments": {"n": 1}}})
    assert ok["result"]["isError"] is False, ok
    print("mcp-server.py selftest: ok")
    return 0


def main():
    if "--selftest" in sys.argv:
        return selftest()
    for line in sys.stdin:                           # one JSON message per line
        line = line.strip()
        if not line:
            continue
        try:
            out = handle(json.loads(line))
        except ValueError:
            out = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}}
        if out is not None:
            sys.stdout.write(json.dumps(out) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
