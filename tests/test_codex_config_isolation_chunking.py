"""WP-17（WP-18 升级 fake 为 JSONL）：Codex 配置隔离与大 diff 无损分块。

复用确定性 fake 可执行手法（无网络、无真实 codex），覆盖分块/聚合/隔离的每个
killer。WP-18 起，adapter 的单次评审走**文件回填 + JSONL 硬化**：完整 brief 与
本块 diff 以 bytes/SHA-256 绑定写入隔离目录文件，Codex 以 ``--json`` 输出可信
事件，adapter 要求 ``-o`` artifact 与最终 ``agent_message`` 逐字一致。因此本文件的
fake 相应升级为**发 JSONL 双通道协议**（与 test_codex_verdict_recovery.py 同构），
但分块/聚合/fail-closed 的**行为断言全部保留、不削弱**：
- 每次 codex exec 的 argv 含 --ignore-user-config 且既有命令契约标志全部保留；
- 绑定 diff <= 阈值走单次路径（一次调用）；
- 绑定 diff > 阈值按文件边界无损分块，每块 prompt 含全局文件清单摘要，且每块只
  绑定本块 diff（不含其它块 diff body）；
- 保守 fail-closed 聚合：全 ACCEPT->ACCEPT；含 REWORK->REWORK 且 findings 合并；
  含 CONSULT（无 REWORK）->CONSULT；某块 fail-closed 则整体抛错，绝不 ACCEPT；
- 静态 killer：聚合不得引入自由文本->decision 的短语/正则映射表。
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from agentic_loop.adapters.base import ReviewContract
from agentic_loop.adapters.base import Verdict
from agentic_loop.adapters.codex import CodexAdapter
from agentic_loop.provider_binding import ProviderBinding

# fake 可执行：按调用次序读 behavior-N.json（可缺省），记录 argv/stdin/cwd 与
# 绑定文件快照，模拟 Codex --json + -o 双通道协议。缺省行为由 prompt 中出现的
# 块标签决定 decision（供分块用例批量配置），并发一条 canonical-UUID 的 JSONL
# 事件流，其最终 agent_message 与写入 -o 的内容逐字一致。
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
    # 默认行为：由 prompt 中出现的块标签决定 decision（供分块用例批量配置）。
    with open(os.path.join(record, "default-map.json"), encoding="utf-8") as f:
        dmap = json.load(f)
    # WP-18：diff 绑定在 candidate.diff 文件而非 prompt；needle 需匹配本次绑定的
    # diff 内容（外加 prompt，兼容基于文件标签的匹配）。
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
    # 每次调用一个 distinct canonical-UUID thread（末段用调用序号 n）。
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
BRIEF = "WP-17 brief body"


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
    """读取第 n 次调用时绑定到 candidate.diff 的内容快照（fake 记录）。"""
    p = record / f"candidate.diff-{n}.bin"
    return p.read_text(encoding="utf-8") if p.exists() else ""


def small_diff() -> str:
    return "diff --git a/x.py b/x.py\n--- a/x.py\n+++ b/x.py\n@@ -0,0 +1 @@\n+print('x')\n"


def big_multifile_diff(n_files: int, body_bytes: int) -> str:
    """构造超过分块阈值的多文件 diff：每个文件塞 body_bytes 的加号行。"""
    parts = []
    filler = "+" + ("A" * 78) + "\n"
    lines_per_file = max(1, body_bytes // len(filler))
    for i in range(n_files):
        hdr = f"diff --git a/f{i}.py b/f{i}.py\n--- a/f{i}.py\n+++ b/f{i}.py\n@@ -0,0 +1,{lines_per_file} @@\n"
        parts.append(hdr + filler * lines_per_file)
    return "".join(parts)


# ---------------------------------------------------------------------------
# 1. 配置隔离：每次 exec 的 argv 含 --ignore-user-config，契约标志保留
# ---------------------------------------------------------------------------

def test_every_exec_carries_ignore_user_config(fake_codex):
    adapter, record, set_behavior, _ = fake_codex
    set_behavior(1, answer=json.dumps({"decision": "ACCEPT", "rationale": "ok", "findings": []}))
    v = adapter.review(diff=small_diff(), brief=BRIEF, contract=mk_contract(), effort="high")
    assert v.decision == "ACCEPT"
    assert invocation_count(record) == 1
    argv = read_argv(record, 1)
    # 正向：隔离标志存在
    assert "--ignore-user-config" in argv
    # 契约标志全部保留（WP-18：新增 --json 亦在）
    assert argv[0] == "exec"
    for flag in ("--sandbox", "read-only", "--skip-git-repo-check",
                 "--output-schema", "--json", "-o", "-"):
        assert flag in argv
    assert "model_reasoning_effort=high" in argv
    # provider 注入在（-m selector）
    assert "-m" in argv and "deepseek-v4-pro" in argv
    # key 值绝不入 argv
    assert CANARY not in " ".join(argv)


def test_ignore_user_config_precedes_injection_and_contract(fake_codex):
    # --ignore-user-config 必须紧跟 exec，在 provider/sandbox 标志之前。
    adapter, record, set_behavior, _ = fake_codex
    set_behavior(1, answer=json.dumps({"decision": "ACCEPT", "rationale": "ok", "findings": []}))
    adapter.review(diff=small_diff(), brief=BRIEF, contract=mk_contract(), effort="medium")
    argv = read_argv(record, 1)
    assert argv[0] == "exec"
    assert argv[1] == "--ignore-user-config"


# ---------------------------------------------------------------------------
# 2. 阈值下界：绑定 diff <= 阈值走单次路径（正向可达对照）
# ---------------------------------------------------------------------------

def test_small_prompt_uses_single_path(fake_codex):
    adapter, record, set_behavior, _ = fake_codex
    set_behavior(1, answer=json.dumps({"decision": "ACCEPT", "rationale": "ok", "findings": []}))
    v = adapter.review(diff=small_diff(), brief=BRIEF, contract=mk_contract(), effort="high")
    assert v.decision == "ACCEPT"
    assert invocation_count(record) == 1  # 单次，未分块


# ---------------------------------------------------------------------------
# 3. 分块触发：绑定 diff > 阈值按文件边界分块，每块含全局摘要且只绑定本块 diff
# ---------------------------------------------------------------------------

def test_large_prompt_splits_by_file(fake_codex):
    adapter, record, _sb, set_default_map = fake_codex
    set_default_map("ACCEPT")
    # 3 个文件，每个 80KB -> 总 ~240KB > 150KB 阈值；单文件 80KB < 阈值
    diff = big_multifile_diff(n_files=3, body_bytes=80 * 1024)
    v = adapter.review(diff=diff, brief=BRIEF, contract=mk_contract(), effort="high")
    assert v.decision == "ACCEPT"
    # 每个文件一次调用（无恢复，因 answer 合法）
    assert invocation_count(record) == 3
    # 每块 prompt 含全局文件清单摘要 + 本块文件标签
    p1 = read_prompt(record, 1)
    assert "Chunk context" in p1
    for fn in ("f0.py", "f1.py", "f2.py"):
        assert fn in p1  # 文件清单列出全部
    # WP-18：diff 不再内联进 prompt，而是绑定到 candidate.diff 文件。
    # 块1 绑定 f0 的 diff body，不含 f1/f2 的 diff body。
    d1 = read_bound_diff(record, 1)
    assert "a/f0.py b/f0.py" in d1
    assert "a/f1.py b/f1.py" not in d1
    assert "a/f2.py b/f2.py" not in d1


def test_bound_diff_chunks_are_lossless_concatenation(fake_codex):
    """无损性：各块绑定的 candidate.diff 依次拼接 == 原始完整 diff。"""
    adapter, record, _sb, set_default_map = fake_codex
    set_default_map("ACCEPT")
    diff = big_multifile_diff(n_files=3, body_bytes=80 * 1024)
    adapter.review(diff=diff, brief=BRIEF, contract=mk_contract(), effort="high")
    n = invocation_count(record)
    joined = "".join(read_bound_diff(record, i) for i in range(1, n + 1))
    assert joined == diff


# ---------------------------------------------------------------------------
# 4. 保守聚合
# ---------------------------------------------------------------------------

def test_aggregate_all_accept_is_accept(fake_codex):
    adapter, record, _sb, set_default_map = fake_codex
    set_default_map("ACCEPT")
    diff = big_multifile_diff(n_files=3, body_bytes=80 * 1024)
    v = adapter.review(diff=diff, brief=BRIEF, contract=mk_contract(), effort="high")
    assert v.decision == "ACCEPT"


def test_aggregate_any_rework_is_rework_and_merges_findings(fake_codex):
    adapter, record, _sb, set_default_map = fake_codex
    # f1 判 REWORK，其余 ACCEPT
    set_default_map("ACCEPT", by_needle={"a/f1.py b/f1.py": "REWORK"})
    diff = big_multifile_diff(n_files=3, body_bytes=80 * 1024)
    v = adapter.review(diff=diff, brief=BRIEF, contract=mk_contract(), effort="high")
    assert v.decision == "REWORK"
    # findings 合并了各块（至少含 REWORK 块的 finding）
    assert any("REWORK" in f for f in v.findings)
    assert any("ACCEPT" in f for f in v.findings)


def test_aggregate_consult_without_rework_is_consult(fake_codex):
    adapter, record, _sb, set_default_map = fake_codex
    set_default_map("ACCEPT", by_needle={"a/f2.py b/f2.py": "CONSULT"})
    diff = big_multifile_diff(n_files=3, body_bytes=80 * 1024)
    v = adapter.review(diff=diff, brief=BRIEF, contract=mk_contract(), effort="high")
    assert v.decision == "CONSULT"


def test_rework_beats_consult(fake_codex):
    adapter, record, _sb, set_default_map = fake_codex
    set_default_map("ACCEPT", by_needle={"a/f0.py b/f0.py": "CONSULT", "a/f1.py b/f1.py": "REWORK"})
    diff = big_multifile_diff(n_files=3, body_bytes=80 * 1024)
    v = adapter.review(diff=diff, brief=BRIEF, contract=mk_contract(), effort="high")
    assert v.decision == "REWORK"


# ---------------------------------------------------------------------------
# 5. fail-closed：某块两次调用后仍无合法 verdict -> 整体抛错，绝不 ACCEPT
# ---------------------------------------------------------------------------

def test_chunk_fail_closed_raises_not_accept(fake_codex):
    adapter, record, set_behavior, set_default_map = fake_codex
    set_default_map("ACCEPT")
    # 让第 1 块首调空终态（有可信 thread），收尾仍空 -> fail-closed。
    set_behavior(1, answer_mode="omit", thread_id="11111111-1111-1111-1111-111111111111")
    set_behavior(2, answer_mode="omit", thread_id="11111111-1111-1111-1111-111111111111")
    diff = big_multifile_diff(n_files=3, body_bytes=80 * 1024)
    with pytest.raises(RuntimeError) as exc:
        adapter.review(diff=diff, brief=BRIEF, contract=mk_contract(), effort="high")
    assert "no verdict" in str(exc.value)


# ---------------------------------------------------------------------------
# 6. 单块仍超阈值 -> fail-closed，不截断
# ---------------------------------------------------------------------------

def test_single_file_over_bound_after_hunk_split_fails_closed(fake_codex):
    adapter, record, _sb, set_default_map = fake_codex
    set_default_map("ACCEPT")
    # 单文件单 hunk 且 > 阈值，无法再切 -> fail-closed
    huge = "diff --git a/big.py b/big.py\n--- a/big.py\n+++ b/big.py\n@@ -0,0 +1,3000 @@\n" + ("+" + "B" * 78 + "\n") * 3000
    assert len(huge.encode("utf-8")) > CodexAdapter._CHUNK_PROMPT_MAX_BYTES
    with pytest.raises(RuntimeError) as exc:
        adapter.review(diff=huge, brief=BRIEF, contract=mk_contract(), effort="high")
    assert "failing closed without truncation" in str(exc.value)


# ---------------------------------------------------------------------------
# 7. 分块内每块仍复用 WP-16 恢复（空终态同 session 收尾一次成功）
# ---------------------------------------------------------------------------

def test_chunk_reuses_wp16_recovery(fake_codex):
    adapter, record, set_behavior, set_default_map = fake_codex
    set_default_map("ACCEPT")
    # 第 1 块首调空终态（有可信 thread），收尾给合法 ACCEPT；块2/块3 走 default-map
    tid = "11111111-1111-1111-1111-111111111111"
    set_behavior(1, answer_mode="omit", thread_id=tid)
    set_behavior(2, answer=json.dumps({"decision": "ACCEPT", "rationale": "recovered", "findings": []}), thread_id=tid)
    diff = big_multifile_diff(n_files=3, body_bytes=80 * 1024)
    v = adapter.review(diff=diff, brief=BRIEF, contract=mk_contract(), effort="high")
    assert v.decision == "ACCEPT"
    # 块1 用了 2 次调用（首调空 + 收尾），块2、块3 各 1 次 = 4 次
    assert invocation_count(record) == 4
    # 块1 的第二次是同 thread 的 resume 收尾
    argv2 = read_argv(record, 2)
    assert argv2[:2] == ["exec", "resume"]
    assert tid in argv2


# ---------------------------------------------------------------------------
# 8. 禁止变异转红：把保守聚合改成"任一 ACCEPT 即 ACCEPT" 必须使 REWORK 用例转红
# ---------------------------------------------------------------------------

def test_mutation_lenient_aggregation_would_fail(fake_codex, monkeypatch):
    adapter, record, _sb, set_default_map = fake_codex
    set_default_map("ACCEPT", by_needle={"a/f1.py b/f1.py": "REWORK"})

    # 被改坏的宽松聚合：任一 ACCEPT 即 ACCEPT（错误语义）
    def lenient(verdicts):
        for v in verdicts:
            if v.decision == "ACCEPT":
                return Verdict(decision="ACCEPT", rationale="lenient", findings=())
        return verdicts[0]

    monkeypatch.setattr(CodexAdapter, "_aggregate_verdicts", staticmethod(lenient))
    diff = big_multifile_diff(n_files=3, body_bytes=80 * 1024)
    v = adapter.review(diff=diff, brief=BRIEF, contract=mk_contract(), effort="high")
    # 改坏后含 REWORK 却被判 ACCEPT —— 证明保守聚合是被真正依赖的（守卫存在性）
    assert v.decision == "ACCEPT"


# ---------------------------------------------------------------------------
# 9. 静态 killer：源码不得引入自由文本->decision 的短语映射表/正则
# ---------------------------------------------------------------------------

def test_no_phrase_to_decision_mapping_in_source():
    src_path = SRC / "agentic_loop" / "adapters" / "codex.py"
    tree = ast.parse(src_path.read_text(encoding="utf-8"))
    decision_literals = {"ACCEPT", "REWORK", "CONSULT"}
    # 聚合方法体内不得出现把任意字符串 key 映射到 decision 的 dict 字面量。
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            vals = {
                v.value for v in node.values
                if isinstance(v, ast.Constant) and isinstance(v.value, str)
            }
            keys = [
                k.value for k in node.keys
                if isinstance(k, ast.Constant) and isinstance(k.value, str)
            ]
            # 若一个 dict 的 value 是 decision 字面量、key 是自由文本短语 -> 禁止
            if vals & decision_literals and keys:
                bad = [k for k in keys if k not in decision_literals]
                assert not bad, f"phrase->decision mapping table found: keys={bad}"
