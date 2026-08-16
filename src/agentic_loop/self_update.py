#!/usr/bin/env python3
"""agentic update — reinstall the latest agentic-loop from main.

`main` always points at the newest release, so a bare `uv tool install --force`
(no tag) upgrades to the latest without needing a shell function or a version
number. This command is bundled with the package so it works on any machine,
unlike a `~/.zshrc` alias that has to be set up per host.
"""
from __future__ import annotations

import shutil
import subprocess
import sys

# Pinned install source (the framework's own repo). No tag = track main.
GIT_URL = "git+https://github.com/billbraves/agentic-loop.git"


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv:
        print("agentic update: takes no arguments", file=sys.stderr)
        return 2

    if shutil.which("uv") is None:
        print(
            "agentic update: uv not found. Install uv first: "
            "https://docs.astral.sh/uv/getting-started/installation/",
            file=sys.stderr,
        )
        return 2

    print(f"agentic update: uv tool install --force {GIT_URL}")
    proc = subprocess.run(["uv", "tool", "install", GIT_URL, "--force"])
    if proc.returncode != 0:
        print(
            f"agentic update: failed (exit {proc.returncode})",
            file=sys.stderr,
        )
        return proc.returncode

    print("agentic update: done — run `agentic --help` to verify.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
