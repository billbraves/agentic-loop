"""Orchestrator probe: run G1-G4 (WP-28 rev3 brief §D harmless probes) against
two criteria that actually exist / are hypothesised, on /tmp copies only.

Criterion A = WP-28 rev1's real dispatch_lint.sh section check (the criterion
              that exists in the WP-29 worktree at base 2e5f2c0).
Criterion B = hypothetical option (b): whole-file byte freeze.

Every mutation carries a no-op guard (mutated != original), per B53.
"""
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TREE = Path("/Users/admin/vibe/wp29-render-scope-decision")
TMPL = TREE / "src/agentic_loop/templates/WORK_PACKAGE.md.tmpl"
LINT = TREE / "src/agentic_loop/wrappers/dispatch_lint.sh"

ORIGINAL = TMPL.read_text(encoding="utf-8")
FROZEN_BYTES = TMPL.read_bytes()


def g1(t):  # placeholder edit
    return t.replace("<这个 WP 要交付什么>", "<这个 WP 要交付什么（本轮：X）>")


def g2(t):  # append an unrelated section
    return t + "\n## 无关新章节\n\n本节与受保护块无关。\n"


def g3(t):  # edit the body of the unrelated `## 范围` section
    return t.replace(
        "  - **owner 边界**：对齐 CODEOWNERS，不跨 owner 写入。",
        "  - **owner 边界**：对齐 CODEOWNERS，不跨 owner 写入（本轮无跨 owner 需求）。",
    ) if "  - **owner 边界**" in t else t.replace(
        "- **owner 边界**：对齐 CODEOWNERS，不跨 owner 写入。",
        "- **owner 边界**：对齐 CODEOWNERS，不跨 owner 写入（本轮无跨 owner 需求）。",
    )


def g4(t):  # edit the freeze-date header line
    return t.replace("> 冻结日期 <YYYY-MM-DD> |", "> 冻结日期 2026-09-19 |")


GS = [("G1 改占位符", g1), ("G2 文末追加无关章节", g2),
      ("G3 改 ## 范围 正文", g3), ("G4 改冻结日期抬头", g4)]

STATUS = None


def criterion_rev1(text, workdir):
    """Run the REAL dispatch_lint.sh section check over `text` as a brief."""
    import json, os
    proj = workdir / "proj"
    proj.mkdir()
    subprocess.run(["git", "init", "-q", str(proj)], check=True)
    for k, v in (("user.email", "t@t"), ("user.name", "t")):
        subprocess.run(["git", "-C", str(proj), "config", k, v], check=True)
    iterdir = proj / "docs" / "plans" / "it-1"
    iterdir.mkdir(parents=True)
    (iterdir / "WP-01.status.json").write_text(json.dumps(STATUS, ensure_ascii=False), encoding="utf-8")
    (iterdir / "WP-01-brief.md").write_text(text, encoding="utf-8")
    subprocess.run(["git", "-C", str(proj), "add", "-A"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(proj), "commit", "-qm", "seed"], check=True, capture_output=True)
    env = dict(os.environ)
    env["PYTHONPATH"] = str(TREE / "src")
    env["AGENTIC_PYTHON"] = sys.executable
    r = subprocess.run(["bash", str(LINT), "docs/plans/it-1/WP-01.status.json"],
                       cwd=str(proj), env=env, capture_output=True, text=True)
    return "GREEN" if r.returncode == 0 else "RED", r.stdout.strip() or r.stderr.strip()


def criterion_option_b(text, workdir):
    """Hypothetical option (b): whole-file byte freeze against FROZEN_BYTES."""
    same = text.encode("utf-8") == FROZEN_BYTES
    return ("GREEN" if same else "RED"), ("bytes identical" if same else "bytes differ")


def main():
    global STATUS
    import json
    STATUS = json.loads((Path(__file__).parent / "status.json").read_text(encoding="utf-8"))

    # baseline first: unmutated template must be GREEN under both
    rows = []
    with tempfile.TemporaryDirectory() as td:
        v, why = criterion_rev1(ORIGINAL, Path(td))
    b, bwhy = criterion_option_b(ORIGINAL, Path("/tmp"))
    rows.append(("baseline 未变异", v, why, b, bwhy))
    if v != "GREEN" or b != "GREEN":
        print("PROBE_ABORT: baseline is not GREEN under both criteria", rows[-1])
        return 2

    for name, fn in GS:
        mutated = fn(ORIGINAL)
        if mutated == ORIGINAL:
            print(f"PROBE_ABORT: no-op mutation for {name} (guard fired)")
            return 3
        with tempfile.TemporaryDirectory() as td:
            v, why = criterion_rev1(mutated, Path(td))
        b, bwhy = criterion_option_b(mutated, Path("/tmp"))
        rows.append((name, v, why, b, bwhy))

    print(f"{'变异':<24} {'rev1 判据':<10} {'(b) 整份冻结':<12}")
    for name, v, why, bb, bwhy in rows:
        print(f"{name:<24} {v:<10} {bb:<12}  | rev1: {why[:40]} | b: {bwhy}")

    # live tree must be untouched
    r = subprocess.run(["git", "-C", str(TREE), "status", "--porcelain"],
                       capture_output=True, text=True)
    print("LIVE_TREE_STATUS:", repr(r.stdout))
    print("TEMPLATE_UNCHANGED:", TMPL.read_bytes() == FROZEN_BYTES)
    return 0


if __name__ == "__main__":
    sys.exit(main())
