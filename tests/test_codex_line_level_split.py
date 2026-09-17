"""WP-19: 行级 sub-hunk 切分（单个超界纯新增 hunk 的无损再切）单测。

约束（见 WP-19-brief.md 设计约束）：
- 只切严格纯新增 hunk：hunk 头删除计数=0 且 hunk 体全为 '+' 行。
- 删除侧 -X,0 的 X 对所有子段保持不变；仅 '+' 侧 start/count 递增。
- 各段拼接的 '+' 行序列 == 原始 '+' 行序列（无损不变量）。
- 混合/含上下文/含删除行的 hunk 不切；单行超界 fail-closed（保持原 hunk）。
- 阈值以下的 hunk 完全不进入行切路径（回归：行为同 WP-18）。
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from agentic_loop.adapters.base import ReviewContract
from agentic_loop.adapters.codex import CodexAdapter as C
from agentic_loop.provider_binding import ProviderBinding

SCHEMA = {
    "type": "object",
    "properties": {
        "decision": {"type": "string", "enum": ["ACCEPT", "REWORK", "CONSULT"]},
        "rationale": {"type": "string"},
        "findings": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["decision", "rationale", "findings"],
    "additionalProperties": False,
}


def mk_binding() -> ProviderBinding:
    return ProviderBinding(
        provider="deepseek",
        anthropic_base_url="https://api.deepseek.com/anthropic",
        openai_base_url="https://api.deepseek.com/v1",
        identity_model="deepseek-v4-pro",
        cli_selector="deepseek-v4-pro",
        api_key_env="DEEPSEEK_API_KEY",
    )


def mk_contract() -> ReviewContract:
    return ReviewContract(role="consultant", output_schema=SCHEMA)


def _plus_body_lines(text: str) -> list[str]:
    """diff 文本中的新增内容行（'+' 开头，排除 '+++' 文件头）。"""
    out = []
    for ln in text.splitlines(keepends=True):
        if ln.startswith("+") and not ln.startswith("+++"):
            out.append(ln)
    return out


def _new_file_diff(path: str, n_lines: int, width: int = 40) -> str:
    """构造一个新文件的纯新增 diff（单一 hunk `@@ -0,0 +1,N @@`）。"""
    header = (
        f"diff --git a/{path} b/{path}\n"
        "new file mode 100644\n"
        "index 0000000..1111111\n"
        f"--- /dev/null\n"
        f"+++ b/{path}\n"
    )
    body = [f"+line {i:05d} " + ("x" * width) + "\n" for i in range(1, n_lines + 1)]
    hunk = f"@@ -0,0 +1,{n_lines} @@\n" + "".join(body)
    return header + hunk


def _append_diff(path: str, old_start: int, new_start: int, n_lines: int, width: int = 40) -> str:
    """构造一个'追加到非空文件尾部'的纯新增 hunk（`@@ -old_start,0 +new_start,N @@`）。"""
    header = (
        f"diff --git a/{path} b/{path}\n"
        "index 1111111..2222222 100644\n"
        f"--- a/{path}\n"
        f"+++ b/{path}\n"
    )
    body = [f"+appended {i:05d} " + ("y" * width) + "\n" for i in range(1, n_lines + 1)]
    hunk = f"@@ -{old_start},0 +{new_start},{n_lines} @@\n" + "".join(body)
    return header + hunk


# ---------------------------------------------------------------------------
# 1. 新文件纯新增大 hunk：被切成多段，无损、各段 ≤ 有效上界
# ---------------------------------------------------------------------------

def test_new_file_pure_addition_split_lossless_and_bounded():
    diff = _new_file_diff(".ci/tests/big_new.py", n_lines=4170)
    assert len(diff.encode()) > C._CHUNK_PROMPT_MAX_BYTES  # 前提：确实超界
    chunks = C._split_diff(diff, reserved_bytes=0)
    assert len(chunks) >= 2, "超界纯新增新文件应被行级切成多段"
    # 无损：各段拼接的 '+' 行 == 原始 '+' 行（序不变、无截断）
    joined = []
    for _lbl, piece in chunks:
        joined += _plus_body_lines(piece)
    assert joined == _plus_body_lines(diff)
    # 各段 ≤ 有效上界
    assert all(len(p.encode()) <= C._CHUNK_PROMPT_MAX_BYTES for _l, p in chunks)


def test_new_file_split_headers_are_git_applicable():
    diff = _new_file_diff(".ci/tests/big_new2.py", n_lines=4170)
    chunks = C._split_diff(diff, reserved_bytes=0)
    assert len(chunks) >= 2
    tmp = tempfile.mkdtemp()
    subprocess.run(["git", "init", "-q", tmp], check=True)
    for _lbl, piece in chunks:
        r = subprocess.run(
            ["git", "-C", tmp, "apply", "--check", "--recount", "-"],
            input=piece, capture_output=True, text=True,
        )
        assert r.returncode == 0, f"重算后的 hunk 头非法/不可应用: {r.stderr!r}"


# ---------------------------------------------------------------------------
# 2. 追加到非空文件尾部（-100,0）：X 恒为 100，仅 '+' 侧递增，无损
# ---------------------------------------------------------------------------

def test_append_to_nonempty_file_preserves_old_start():
    diff = _append_diff(".ci/x.py", old_start=100, new_start=101, n_lines=4170)
    assert len(diff.encode()) > C._CHUNK_PROMPT_MAX_BYTES
    chunks = C._split_diff(diff, reserved_bytes=0)
    assert len(chunks) >= 2
    # 无损
    joined = []
    for _lbl, piece in chunks:
        joined += _plus_body_lines(piece)
    assert joined == _plus_body_lines(diff)
    # 每段删除侧 -100,0 的 X 恒为 100；'+' 侧 start 从 101 起连续递增
    plus_starts = []
    for _lbl, piece in chunks:
        for ln in piece.splitlines():
            if ln.startswith("@@ "):
                p = C._parse_hunk_header(ln + "\n")
                assert p is not None
                old_start, old_count, new_start, new_count = p
                assert old_start == 100 and old_count == 0, f"删除侧锚点被改: {ln}"
                plus_starts.append((new_start, new_count))
    # '+' 侧连续：下一段 start == 上一段 start + count
    for (s0, c0), (s1, _c1) in zip(plus_starts, plus_starts[1:]):
        assert s1 == s0 + c0, f"'+' 侧 start 不连续: {plus_starts}"
    assert plus_starts[0][0] == 101


# ---------------------------------------------------------------------------
# 3. 混合 hunk（含上下文/删除行）即便内部有大段连续 '+' 也不被行切 → fail-closed
# ---------------------------------------------------------------------------

def test_mixed_hunk_with_context_is_not_line_split():
    path = ".ci/mixed.py"
    header = (
        f"diff --git a/{path} b/{path}\n"
        "index 1111111..2222222 100644\n"
        f"--- a/{path}\n"
        f"+++ b/{path}\n"
    )
    # 删除侧非 0 + 含上下文行 + 大段 '+'，整体超界
    added = [f"+added {i:05d} " + ("z" * 60) + "\n" for i in range(1, 4200)]
    hunk = (
        "@@ -1,3 +1,4201 @@\n"
        " context line kept\n"          # 上下文行
        "-old line removed\n"           # 删除行
        + "".join(added)
        + " trailing context\n"
    )
    diff = header + hunk
    assert len(diff.encode()) > C._CHUNK_PROMPT_MAX_BYTES
    # 混合 hunk 不可无损行切 → _split_diff 返回单块（该块仍超界），上层 review() fail-closed
    chunks = C._split_diff(diff, reserved_bytes=0)
    assert len(chunks) == 1, "混合 hunk 不应被行切"
    assert chunks[0][1] == diff  # 原样返回，未改写


def test_mixed_hunk_review_fails_closed():
    """review() 面对混合超界 hunk 必须 fail-closed（RuntimeError），绝不 ACCEPT。

    fail-closed 在分块阶段即触发（早于任何 codex 子进程调用），故无需 fake binary。"""
    path = ".ci/mixed2.py"
    header = (
        f"diff --git a/{path} b/{path}\n"
        f"--- a/{path}\n+++ b/{path}\n"
    )
    added = [f"+a {i} " + ("z" * 80) + "\n" for i in range(1, 4200)]
    hunk = "@@ -1,2 +1,4200 @@\n context\n" + "".join(added)
    diff = header + hunk
    adapter = C(binding=mk_binding())
    with pytest.raises(RuntimeError):
        adapter.review(diff=diff, brief="b", contract=mk_contract(), effort="high")


# ---------------------------------------------------------------------------
# 4. 单行超界的病态输入：fail-closed（保持原 hunk，不强切一行）
# ---------------------------------------------------------------------------

def test_single_oversized_line_fails_closed():
    path = ".ci/oneline.py"
    header = (
        f"diff --git a/{path} b/{path}\n"
        "new file mode 100644\n"
        f"--- /dev/null\n+++ b/{path}\n"
    )
    # 单个 '+' 行本身就超过上界
    giant = "+" + ("Q" * (C._CHUNK_PROMPT_MAX_BYTES + 1000)) + "\n"
    diff = header + "@@ -0,0 +1,1 @@\n" + giant
    chunks = C._split_diff(diff, reserved_bytes=0)
    assert len(chunks) == 1
    assert chunks[0][1] == diff  # 未强切、未截断


# ---------------------------------------------------------------------------
# 5. 阈值以下的 hunk 完全不进入行切路径（回归：行为同 WP-18）
# ---------------------------------------------------------------------------

def test_small_hunk_not_line_split():
    diff = _new_file_diff(".ci/small.py", n_lines=50)
    assert len(diff.encode()) <= C._CHUNK_PROMPT_MAX_BYTES
    # 未超界的整 diff 走单块路径（<whole-diff> 或单文件），不进入 _split_file_by_hunks 行切
    chunks = C._split_diff(diff, reserved_bytes=0)
    assert len(chunks) == 1
    assert chunks[0][1] == diff
    # label 不应带 #lines 标记（未行切）
    assert "#lines" not in chunks[0][0]


# ---------------------------------------------------------------------------
# 6. _parse_hunk_header 基础正确性（含省略 count 的缺省=1）
# ---------------------------------------------------------------------------

def test_parse_hunk_header_variants():
    assert C._parse_hunk_header("@@ -0,0 +1,4170 @@\n") == (0, 0, 1, 4170)
    assert C._parse_hunk_header("@@ -100,0 +101,20 @@\n") == (100, 0, 101, 20)
    # 省略 count -> 缺省 1
    assert C._parse_hunk_header("@@ -5 +5 @@\n") == (5, 1, 5, 1)
    # 非法
    assert C._parse_hunk_header("not a hunk\n") is None
    assert C._parse_hunk_header("@@ -1,2 @@\n") is None
