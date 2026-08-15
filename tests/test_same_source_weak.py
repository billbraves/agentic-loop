from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from agentic_loop.adapters.base import AdapterCapabilities, AgentIdentity
from agentic_loop.independence import evaluate, meets_threshold


def _consultant_caps():
    # codex 能力：sandbox_enforced + structured_output 均 True。
    return AdapterCapabilities(sandbox_enforced=True, structured_output=True)


def test_same_identity_model_rates_weak_non_bootstrap():
    # 正常路径：reviewer 有 adapter identity（claude, 同 deepseek-v4-pro），
    # consultant（codex, 同 deepseek-v4-pro）→ same_model → weak。
    reviewer = AgentIdentity(tool="claude", model="deepseek-v4-pro")
    consultant = AgentIdentity(tool="codex", model="deepseek-v4-pro")
    level, reasons = evaluate(
        reviewer_id=reviewer,
        consultant_id=consultant,
        capabilities=_consultant_caps(),
        min_independence="weak",
    )
    assert level == "weak"
    assert any("same model" in r for r in reasons)
    assert any("deepseek-v4-pro" in r for r in reasons)


def test_weak_meets_weak_threshold():
    assert meets_threshold("weak", "weak") is True


def test_weak_does_not_meet_strong_threshold():
    # 证明若 profile 仍写 strong，同源会被门拦（这正是必须显式降 weak 的原因）。
    assert meets_threshold("weak", "strong") is False


def test_different_identity_model_still_strong():
    # 反向对照：不同 model 仍 strong（本轮不动这条语义）。
    reviewer = AgentIdentity(tool="claude", model="deepseek-v4-pro")
    consultant = AgentIdentity(tool="codex", model="deepseek-reasoner")
    level, _ = evaluate(
        reviewer_id=reviewer,
        consultant_id=consultant,
        capabilities=_consultant_caps(),
        min_independence="weak",
    )
    assert level == "strong"
