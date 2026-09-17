"""WP-18: 两支能力合并的组合行为（确定性、离线）。

单独的分块行为见 test_codex_config_isolation_chunking.py；单独的文件回填/JSONL
硬化/finalization 见 test_codex_verdict_recovery.py。本文件专门证明两支在**同一次
大 diff 评审**中同时生效——即分块的每一块都真正走了文件回填 + JSONL 硬化的单次
评审通道，而非只有其一：

- 每块把完整 brief 与**本块 diff** 以 bytes/SHA-256 绑定写入隔离目录文件，并在
  prompt 中声明该文件名/字节/摘要（文件回填在分块路径生效）；
- 每块 exec 的 argv 同时含 --json 与分块所需的隔离/契约标志（JSONL 硬化在分块
  路径生效）；
- 每块的 -o artifact 与 JSONL 最终 agent_message 不一致时，整条评审 fail-closed
  （artifact/event 逐字一致校验在分块路径生效）；
- 分块路径中某块首调空终态，可用同 thread resume 收尾（finalization 在分块
  路径生效）；
- 各块绑定 diff 依次拼接 == 原始完整 diff（无损分块 + 文件回填联合不变量）；
- 非 JSONL stdout 使某块输出通道失效 -> fail-closed，绝不 ACCEPT。
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from agentic_loop.adapters.base import ReviewContract
from agentic_loop.adapters.codex import CodexAdapter
from agentic_loop.provider_binding import ProviderBinding

# 与 chunking 测试同构的 JSONL fake：默认行为按绑定 diff 的块标签决定 decision，
# 发 canonical-UUID 单 thread 事件流，最终 agent_message 与 -o 写入内容逐字一致。
_FAKE_SRC = r'''
import json
import os
import sys

record = os.environ["FAKE_RECORD_DIR"]
os.makedirs(record, exist_ok=True)
count_file = os.path.join(record, "count")
n = 1
if os.path.exists(count_file):
    with open(count_file, encoding="utf-8") as f:
        n = int(f.read().strip() or "0") + 1
with open(count_file, "w", encoding="utf-8") as f:
    f.write(str(n))

argv = sys.argv[1:]
with open(os.path.join(record, f"argv-{n}.json"), "w", encoding="utf-8") as f:
    json.dump(argv, f)
stdin = sys.stdin.read()
with open(os.path.join(record, f"prompt-{n}.md"), "w", encoding="utf-8") as f:
    f.write(stdin)
with open(os.path.join(record, f"cwd-{n}.txt"), "w", encoding="utf-8") as f:
    f.write(os.getcwd())
for name in ("work-package-brief.md", "candidate.diff"):
    path = os.path.join(os.getcwd(), name)
    if os.path.isfile(path):
        with open(path, "rb") as src, open(
            os.path.join(record, f"{name}-{n}.bin"), "wb"
        ) as dst:
            dst.write(src.read())

out_path = None
if "-o" in argv:
    out_path = argv[argv.index("-o") + 1]

beh_path = os.path.join(record, f"behavior-{n}.json")
if os.path.exists(beh_path):
    with open(beh_path, encoding="utf-8") as f:
        beh = json.load(f)
else:
    with open(os.path.join(record, "default-map.json"), encoding="utf-8") as f:
        dmap = json.load(f)
    haystack = stdin
    bound = os.path.join(os.getcwd(), "candidate.diff")
    if os.path.isfile(bound):
        with open(bound, encoding="utf-8") as bf:
            haystack = haystack + bf.read()
    decision = dmap["default"]
    for needle, dec in dmap.get("by_needle", {}).items():
        if needle in haystack:
            decision = dec
            break
    beh = {"rc": 0, "answer": json.dumps({
        "decision": decision,
        "rationale": "r-" + decision,
        "findings": ["f-" + decision + "-" + str(n)],
    })}

mode = beh.get("answer_mode", "write")
data = beh.get("answer", "")
if mode == "empty":
    data = ""
if out_path and mode != "omit":
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(data)

if "stdout_raw" in beh:
    sys.stdout.write(beh["stdout_raw"])
else:
    thread_id = beh.get("thread_id", "00000000-0000-0000-0000-%012d" % n)
    events = beh.get("events")
    if events is None:
        events = [
            {"type": "thread.started", "thread_id": thread_id},
            {"type": "turn.started"},
        ]
        event_answer = beh.get("event_answer", data)
        if event_answer or beh.get("emit_empty_message"):
            events.append({
                "type": "item.completed",
                "item": {"id": "item-final", "type": "agent_message", "text": event_answer},
            })
        if not beh.get("omit_turn_completed"):
            events.append({"type": beh.get("turn_event", "turn.completed")})
    for event in events:
        sys.stdout.write(json.dumps(event) + "\n")
if beh.get("stderr"):
    sys.stderr.write(beh["stderr"])
sys.exit(beh.get("rc", 0))
'''

CANARY = "sk-CANARY"
SCHEMA = {
    "type": "object",
    "properties": {
        "decision": {"type": "string", "enum": ["ACCEPT", "REWORK", "CONSULT"]},
        "rationale": {"type": "string"},
        "findings": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["decision"],
}
BRIEF = "WP-18 combined-capability brief body"


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


@pytest.fixture
def fake_codex(tmp_path, monkeypatch):
    record = tmp_path / "record"
    record.mkdir()
    monkeypatch.setenv("FAKE_RECORD_DIR", str(record))
    monkeypatch.setenv("DEEPSEEK_API_KEY", CANARY)
    fake = tmp_path / "fake-codex"
    fake.write_text("#!/usr/bin/env python3\n" + _FAKE_SRC, encoding="utf-8")
    fake.chmod(0o755)

    def set_behavior(n: int, **beh) -> None:
        (record / f"behavior-{n}.json").write_text(json.dumps(beh), encoding="utf-8")

    def set_default_map(default: str, by_needle: dict | None = None) -> None:
        (record / "default-map.json").write_text(
            json.dumps({"default": default, "by_needle": by_needle or {}}),
            encoding="utf-8",
        )

    adapter = CodexAdapter(codex_bin=str(fake), binding=mk_binding())
    return adapter, record, set_behavior, set_default_map


def invocation_count(record: Path) -> int:
    cf = record / "count"
    return int(cf.read_text().strip()) if cf.exists() else 0


def read_argv(record: Path, n: int) -> list:
    return json.loads((record / f"argv-{n}.json").read_text(encoding="utf-8"))


def read_prompt(record: Path, n: int) -> str:
    return (record / f"prompt-{n}.md").read_text(encoding="utf-8")


def read_bound_diff(record: Path, n: int) -> str:
    p = record / f"candidate.diff-{n}.bin"
    return p.read_text(encoding="utf-8") if p.exists() else ""


def read_bound_brief(record: Path, n: int) -> str:
    p = record / f"work-package-brief.md-{n}.bin"
    return p.read_text(encoding="utf-8") if p.exists() else ""


def big_multifile_diff(n_files: int, body_bytes: int) -> str:
    parts = []
    filler = "+" + ("A" * 78) + "\n"
    lines_per_file = max(1, body_bytes // len(filler))
    for i in range(n_files):
        hdr = f"diff --git a/f{i}.py b/f{i}.py\n--- a/f{i}.py\n+++ b/f{i}.py\n@@ -0,0 +1,{lines_per_file} @@\n"
        parts.append(hdr + filler * lines_per_file)
    return "".join(parts)


# ---------------------------------------------------------------------------
# 1. 组合不变量：分块路径的每一块都同时走文件回填 + JSONL 硬化
# ---------------------------------------------------------------------------

def test_each_chunk_uses_file_backing_and_jsonl(fake_codex):
    adapter, record, _sb, set_default_map = fake_codex
    set_default_map("ACCEPT")
    diff = big_multifile_diff(n_files=3, body_bytes=80 * 1024)
    v = adapter.review(diff=diff, brief=BRIEF, contract=mk_contract(), effort="high")
    assert v.decision == "ACCEPT"
    n = invocation_count(record)
    assert n == 3
    for i in range(1, n + 1):
        argv = read_argv(record, i)
        # JSONL 硬化：每块 exec 带 --json，且隔离/契约标志保留
        assert "--json" in argv
        assert "--ignore-user-config" in argv
        assert "--output-schema" in argv and "-o" in argv
        # 文件回填：本块把完整 brief 与本块 diff 绑定成文件
        bound_diff = read_bound_diff(record, i)
        bound_brief = read_bound_brief(record, i)
        assert bound_brief == BRIEF
        assert bound_diff  # 非空
        # prompt 声明的 SHA-256 与实际绑定文件一致（bytes/SHA 绑定生效）
        prompt = read_prompt(record, i)
        assert hashlib.sha256(bound_diff.encode("utf-8")).hexdigest() in prompt
        assert hashlib.sha256(bound_brief.encode("utf-8")).hexdigest() in prompt
        # diff 不内联进 prompt（体量不再挤占单轮上下文）
        assert "diff --git a/f" not in prompt


# ---------------------------------------------------------------------------
# 2. 联合无损：各块绑定 diff 依次拼接 == 原始完整 diff
# ---------------------------------------------------------------------------

def test_chunks_bound_diffs_are_lossless(fake_codex):
    adapter, record, _sb, set_default_map = fake_codex
    set_default_map("ACCEPT")
    diff = big_multifile_diff(n_files=4, body_bytes=60 * 1024)
    adapter.review(diff=diff, brief=BRIEF, contract=mk_contract(), effort="high")
    n = invocation_count(record)
    joined = "".join(read_bound_diff(record, i) for i in range(1, n + 1))
    assert joined == diff


# ---------------------------------------------------------------------------
# 3. JSONL 硬化在分块路径生效：某块 artifact 与 event 不一致 -> fail-closed
# ---------------------------------------------------------------------------

def test_chunk_artifact_event_mismatch_fails_closed(fake_codex):
    adapter, record, set_behavior, set_default_map = fake_codex
    set_default_map("ACCEPT")
    # 第 1 块：-o 写 ACCEPT，但 JSONL 最终 message 是 REWORK -> 逐字不一致
    set_behavior(
        1,
        answer=json.dumps({"decision": "ACCEPT", "rationale": "a", "findings": []}),
        event_answer=json.dumps({"decision": "REWORK", "rationale": "b", "findings": []}),
    )
    diff = big_multifile_diff(n_files=3, body_bytes=80 * 1024)
    with pytest.raises(RuntimeError) as exc:
        adapter.review(diff=diff, brief=BRIEF, contract=mk_contract(), effort="high")
    assert "artifact/event differ" in str(exc.value)


# ---------------------------------------------------------------------------
# 4. finalization 在分块路径生效：某块首调空终态 -> 同 thread resume 收尾成功
# ---------------------------------------------------------------------------

def test_chunk_empty_terminal_uses_same_thread_finalization(fake_codex):
    adapter, record, set_behavior, set_default_map = fake_codex
    set_default_map("ACCEPT")
    tid = "22222222-2222-2222-2222-222222222222"
    set_behavior(1, answer_mode="omit", thread_id=tid)
    set_behavior(2, answer=json.dumps({"decision": "ACCEPT", "rationale": "final", "findings": []}), thread_id=tid)
    diff = big_multifile_diff(n_files=3, body_bytes=80 * 1024)
    v = adapter.review(diff=diff, brief=BRIEF, contract=mk_contract(), effort="high")
    assert v.decision == "ACCEPT"
    # 块1: 首调(1) + 同 thread resume 收尾(2)，块2(3)、块3(4)
    assert invocation_count(record) == 4
    argv2 = read_argv(record, 2)
    assert argv2[:2] == ["exec", "resume"]
    assert tid in argv2
    # 收尾禁用工具：shell_tool / unified_exec 均被 --disable
    assert "shell_tool" in argv2 and "unified_exec" in argv2


# ---------------------------------------------------------------------------
# 5. 非 JSONL stdout 使某块输出通道失效 -> fail-closed（不 ACCEPT）
# ---------------------------------------------------------------------------

def test_chunk_non_jsonl_stdout_fails_closed(fake_codex):
    adapter, record, set_behavior, set_default_map = fake_codex
    set_default_map("ACCEPT")
    # 第 1 块 stdout 非 JSONL，且 -o 有内容 -> _read_verdict_output 判 artifact/event
    # 缺失（event 通道失效），fail-closed。
    set_behavior(
        1,
        answer=json.dumps({"decision": "ACCEPT", "rationale": "a", "findings": []}),
        stdout_raw="not-a-json-line\n",
    )
    diff = big_multifile_diff(n_files=3, body_bytes=80 * 1024)
    with pytest.raises(RuntimeError) as exc:
        adapter.review(diff=diff, brief=BRIEF, contract=mk_contract(), effort="high")
    assert "artifact/event missing" in str(exc.value)


# ---------------------------------------------------------------------------
# 6. 单块路径（不分块）也是文件回填 + JSONL：小 diff 一次调用即完成
# ---------------------------------------------------------------------------

def test_single_chunk_path_is_file_backed_and_jsonl(fake_codex):
    adapter, record, set_behavior, _ = fake_codex
    set_behavior(1, answer=json.dumps({"decision": "ACCEPT", "rationale": "ok", "findings": []}))
    small = "diff --git a/x.py b/x.py\n--- a/x.py\n+++ b/x.py\n@@ -0,0 +1 @@\n+print('x')\n"
    v = adapter.review(diff=small, brief=BRIEF, contract=mk_contract(), effort="high")
    assert v.decision == "ACCEPT"
    assert invocation_count(record) == 1
    argv = read_argv(record, 1)
    assert "--json" in argv
    assert read_bound_diff(record, 1) == small
    assert read_bound_brief(record, 1) == BRIEF
    # 单块路径无 chunk context（未分块）
    assert "Chunk context" not in read_prompt(record, 1)


# ---------------------------------------------------------------------------
# 7. REWORK 修复：分块阈值计入 brief 字节（大 brief 会把本可通过的 diff 推入分块）
# ---------------------------------------------------------------------------

def test_bound_counts_brief_bytes_not_diff_only(fake_codex):
    adapter, record, _sb, set_default_map = fake_codex
    set_default_map("ACCEPT")
    # 单文件 diff 约 120KB（diff-only < 150KB 阈值，若只算 diff 则单次不分块），
    # 但配一个 ~60KB 的 brief -> brief+diff > 150KB，必须触发分块。
    one_file = big_multifile_diff(n_files=1, body_bytes=120 * 1024)
    big_brief = "B" * (60 * 1024)
    # 该单文件可按 hunk 进一步切分？此处只有一个 hunk，故会 fail-closed；
    # 用多文件更贴近真实：两个 60KB 文件，diff-only=120KB<阈值，+60KB brief 超阈值。
    two_files = big_multifile_diff(n_files=2, body_bytes=60 * 1024)
    v = adapter.review(diff=two_files, brief=big_brief, contract=mk_contract(), effort="high")
    assert v.decision == "ACCEPT"
    # 若阈值只算 diff（120KB<150KB）会是单次调用；计入 brief 后应分块 -> >1 次。
    assert invocation_count(record) >= 2
    # 无损：各块绑定 diff 拼接 == 原 diff
    n = invocation_count(record)
    joined = "".join(read_bound_diff(record, i) for i in range(1, n + 1))
    assert joined == two_files
    _ = one_file  # 说明性变量，保留注释语义


# ---------------------------------------------------------------------------
# 8. REWORK 修复：探针与真实评审路径一致携带 --ignore-user-config
# ---------------------------------------------------------------------------

def test_probe_injection_carries_ignore_user_config(fake_codex, monkeypatch):
    adapter, record, _sb, _dm = fake_codex
    # probe_injection 会真正 exec fake；fake 记录 argv。让它回 sentinel。
    monkeypatch.setenv("FAKE_RECORD_DIR", str(record))
    # 直接断言命令构造：probe 与 _exec_attempt 一样带 --ignore-user-config。
    ok = adapter.probe_injection()
    # fake 不认识 probe prompt，不必求 True；关键是它被以隔离契约调用。
    argv = read_argv(record, 1)
    assert argv[0] == "exec"
    assert "--ignore-user-config" in argv
