from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from agentic_loop import resolve_paths as rp
from agentic_loop.adapters.claude import ClaudeAdapter
from agentic_loop.adapters.codex import CodexAdapter
from agentic_loop.independence import evaluate, meets_threshold
from agentic_loop.provider_binding import ProviderBinding

EXAMPLE = (
    Path(__file__).resolve().parents[1] / "examples" / "config.single-deepseek.toml"
)


def _mk_repo_from_example(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    a = tmp_path / ".agentic"
    a.mkdir()
    (a / "config.toml").write_text(EXAMPLE.read_text(encoding="utf-8"), encoding="utf-8")
    return tmp_path


def test_profile_resolves_all_three_to_same_identity_model(tmp_path):
    repo = _mk_repo_from_example(tmp_path)
    _, dev = rp.resolve_role_binding("developer", repo=repo)
    _, rev = rp.resolve_role_binding("reviewer", repo=repo)
    _, con = rp.resolve_role_binding("consultant", repo=repo)
    assert dev.identity_model == rev.identity_model == con.identity_model == "deepseek-v4-pro"
    # per-adapter selectors differ:
    assert dev.cli_selector == "deepseek/v4-pro"        # kimi
    assert rev.cli_selector == "deepseek-v4-pro"        # claude


def test_profile_min_independence_is_weak(tmp_path):
    repo = _mk_repo_from_example(tmp_path)
    policy = rp.get_review_policy(repo=repo)
    assert policy["min_independence"] == "weak"


def test_end_to_end_engine_rates_weak_and_gate_passes(tmp_path):
    repo = _mk_repo_from_example(tmp_path)
    _, rev = rp.resolve_role_binding("reviewer", repo=repo)      # claude binding
    _, con = rp.resolve_role_binding("consultant", repo=repo)    # codex binding
    reviewer_adapter = ClaudeAdapter(binding=rev)
    consultant_adapter = CodexAdapter(binding=con)
    level, reasons = evaluate(
        reviewer_id=reviewer_adapter.identity(),
        consultant_id=consultant_adapter.identity(),
        capabilities=consultant_adapter.capabilities(),
        min_independence="weak",
    )
    assert level == "weak"
    assert meets_threshold(level, "weak") is True               # 门放行
    assert any("same model" in r for r in reasons)              # reasons 留痕同源
