#!/usr/bin/env python3
"""
selftest-all.py — one command that proves the scripts still work.

Compiles every script in AIOS/scripts/, then runs the `--selftest` of every script
that has one, each on throwaway data (never your notes). Prints one line per
script and exits 1 if anything fails. GitHub runs this on every push (see
.github/workflows/ci.yml); run it yourself after changing a script.

    python3 AIOS/scripts/selftest-all.py

No dependencies. Plain stdlib.
"""
import os
import py_compile
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    bad = 0
    for p in sorted(HERE.glob("*.py")):
        try:
            py_compile.compile(str(p), doraise=True)
        except py_compile.PyCompileError as e:
            print(f"[FAIL] {p.name}: does not compile: {e}")
            if os.environ.get("GITHUB_ACTIONS"):
                print(f"::error title={p.name} does not compile::{e}".replace("\n", "%0A"))
            bad += 1
    ran = 0
    for p in sorted(HERE.glob("*.py")):
        if p.name == Path(__file__).name or '"--selftest"' not in p.read_text(encoding="utf-8", errors="ignore"):
            continue
        r = subprocess.run([sys.executable, str(p), "--selftest"], capture_output=True, text=True, timeout=300)
        ran += 1
        if r.returncode:
            out = (r.stdout + r.stderr).strip()[-600:]
            print(f"[FAIL] {p.name}\n{out}")
            if os.environ.get("GITHUB_ACTIONS"):          # shows up as a readable annotation on the run
                print(f"::error title={p.name} failed::" + out.replace("\n", "%0A"))
            bad += 1
        else:
            print(f"[ ok ] {p.name}")
    print(f"\n{ran} selftests run, {bad} problem(s).")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
