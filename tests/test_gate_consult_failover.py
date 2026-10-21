"""WP-01 (2026-10-21-consult-llm-failover): single-hop provider failover for
the merge-gate consult.

The gate's independent consult normally runs on the consultant role binding
(``kirogpt`` / ``gpt-5.6-sol`` via the local LiteLLM gateway). This suite
proves the single-hop failover semantics end-to-end against an isolated git
repo with a stub ``codex`` in PATH (no real provider or gateway is ever
contacted):

1. primary success -> one call, consult block records the primary identity;
2. quota-classified primary failure -> exactly one fallback call on
   ``deepseekpro`` / ``deepseek-v4-pro``, ``GATE_DECISION`` printed, audit
   fields record the effective provider/model/fallback_used;
3. auth_config and task primary failures -> exactly one call, gate fails, no
   fallback (the category is the witness);
4. failing fallback -> exactly two calls, both categories reported, no third
   attempt;
5. missing fallback credential env var / unconfigured fallback_provider ->
   fail closed with an explicit reason naming the env var NAME only;
6. independence/audit uses the identity of the adapter that actually served
   the consult (deepseek-v4-pro after a hop).

Direct unit tests over ``_consult_with_failover`` pin the routing matrix with
fake adapters. The e2e assertions key on the REAL surface: the stub codex's
actual argv (``-c model_providers.<name>...``) and call count, and the
persisted status/answer-artifact bytes.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from agentic_loop.adapters.base import AgentIdentity  # noqa: E402
from agentic_loop.adapters.base import Verdict  # noqa: E402
from agentic_loop.gate import ConsultFailoverError  # noqa: E402
from agentic_loop.gate import _consult_with_failover  # noqa: E402
from agentic_loop.quota_fallback import DEFAULT_QUOTA_PATTERNS  # noqa: E402

ITERATION = "it-failover"
STATUS_REL = f"docs/plans/{ITERATION}/WP-01.status.json"
ANSWER_REL = f"docs/plans/{ITERATION}/WP-01-codex-merge-gate.answer.md"

API_KEY_PLACEHOLDER = "test-placeholder-deepseek-key"

CONFIG_WITH_FALLBACK = """\
[providers.kirogpt]
openai_base_url = "http://127.0.0.1:18090/v1"
api_key_env     = "OPENAI_API_KEY"
identity_model  = "gpt-5.6-sol"
[providers.kirogpt.selectors]
codex = "gpt-5.6-sol"

[providers.deepseekpro]
openai_base_url = "https://api.deepseek.com/v1"
api_key_env     = "DEEPSEEK_API_KEY"
identity_model  = "deepseek-v4-pro"
[providers.deepseekpro.selectors]
codex = "deepseek-v4-pro"

[roles]
consultant = { adapter = "codex", provider = "kirogpt", fallback_provider = "deepseekpro" }
"""

CONFIG_NO_FALLBACK = """\
[providers.kirogpt]
openai_base_url = "http://127.0.0.1:18090/v1"
api_key_env     = "OPENAI_API_KEY"
identity_model  = "gpt-5.6-sol"
[providers.kirogpt.selectors]
codex = "gpt-5.6-sol"

[roles]
consultant = { adapter = "codex", provider = "kirogpt" }
"""

# A stub ``codex`` that records its argv (one JSON line per invocation), then
# either fails with a category-specific stderr line (behavior from
# ``STUB_FAIL_<PROVIDER>``) or serves a schema-valid verdict on the WP-18
# hardened JSONL protocol.
STUB_CODEX = r'''
import json
import os
import sys

provider = ""
out = ""
args = sys.argv[1:]
i = 0
while i < len(args):
    if args[i] == "-c" and i + 1 < len(args):
        if args[i + 1].startswith("model_provider="):
            provider = args[i + 1].split("=", 1)[1]
        i += 2
    elif args[i] == "-o" and i + 1 < len(args):
        out = args[i + 1]
        i += 2
    else:
        i += 1

log = os.environ.get("STUB_LOG", "")
if log:
    with open(log, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"provider": provider, "argv": args}) + "\n")

sys.stdin.read()

behavior = os.environ.get("STUB_FAIL_" + provider.upper(), "")
if behavior == "quota":
    sys.stderr.write("Error: HTTP 429\n")
    sys.exit(1)
if behavior == "auth":
    sys.stderr.write("Error: 401 Unauthorized\n")
    sys.exit(1)
if behavior == "task":
    sys.stderr.write(
        "FAILED tests/test_stub.py::test_x - AssertionError: boom\n")
    sys.exit(1)
if behavior == "server":
    sys.stderr.write("Error: HTTP 503 Service Unavailable\n")
    sys.exit(1)

verdict = '{"decision":"ACCEPT","rationale":"stub","findings":[]}'
if out:
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(verdict)
print('{"type":"thread.started","thread_id":"00000000-0000-0000-0000-000000000001"}')
print('{"type":"turn.started"}')
text = verdict.replace("\\", "\\\\").replace('"', '\\"')
print('{"type":"item.completed","item":{"id":"item-final","type":"agent_message","text":"%s"}}' % text)
print('{"type":"turn.completed"}')
'''


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True, capture_output=True, text=True,
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    r.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=r, check=True)
    _git(r, "config", "user.email", "t@e.com")
    _git(r, "config", "user.name", "T")
    (r / "docs" / "plans" / ITERATION).mkdir(parents=True)
    (r / "seed.txt").write_text("seed\n")
    _git(r, "add", "-A")
    _git(r, "commit", "-qm", "seed")
    _git(r, "branch", "-M", "main")
    seed = _git(r, "rev-parse", "HEAD")

    (r / ".agentic").mkdir()
    (r / ".agentic" / "config.toml").write_text(CONFIG_WITH_FALLBACK)
    (r / "docs" / "plans" / ITERATION / "WP-01-brief.md").write_text(
        "# brief\n")

    _git(r, "checkout", "-q", "-b", "feat/x")
    (r / "wp_change.txt").write_text("wp code change\n")
    _git(r, "add", "-A")
    _git(r, "commit", "-qm", "impl: wp code change")
    tip = _git(r, "rev-parse", "HEAD")

    _write_status(
        r,
        git={"base_branch": "feat/x", "base_commit": seed,
             "branch": "feat/x", "worktree": ".", "commit": tip},
        scope={"allowed_paths": ["wp_change.txt", "seed.txt",
                                 f"docs/plans/{ITERATION}/"],
               "forbidden_paths": []},
    )
    return r


def _write_status(repo: Path, **over) -> None:
    data = {
        "schema_version": "agentic-wp-status/v2",
        "work_package_id": "WP-01",
        "iteration_id": ITERATION,
        "phase": "P0",
        "state": "READY_FOR_REVIEW",
        "role": "Developer",
        "executor": {"tool": "kimi-cli"},
        "orchestrator": {"tool": "claude-code"},
        "reviewer": {"tool": "claude-code"},
        "git": {"base_branch": "feat/x", "base_commit": None, "branch": None,
                "worktree": ".", "commit": None},
        "scope": {"allowed_paths": ["x"], "forbidden_paths": []},
        "risk": {"production_writes_authorized": False,
                 "network_authorized": False,
                 "real_notifications_authorized": False,
                 "irreversible_actions_authorized": False},
        "evidence": {"tests": [{"cmd": "pytest", "exit_code": 0}]},
        "review": {
            "decision": "ACCEPT",
            "attestation": {
                "reviewer_role": "orchestrator",
                "reviewer_tool": "claude-code",
                "fresh_session": True,
                "adversarial_prompt": True,
                "attested_by": "orchestrator",
                "attested_at": "2026-08-14T00:00:00Z",
            },
        },
        "consult": {"decision": None},
        "timestamps": {},
    }
    data.update(over)
    f = repo / STATUS_REL
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    # The authoritative-branch predicate reads the PLAN status beside the
    # judged file; base_branch must name the branch this repo actually holds.
    (f.parent / "PLAN-FIXTURE.status.json").write_text(json.dumps({
        "schema_version": "agentic-plan-status/v1",
        "plan_id": "PLAN-FIXTURE",
        "iteration_id": "fixture-iteration",
        "state": "ACTIVE",
        "title": "fixture plan",
        "git": {"base_branch": "feat/x", "target_branch": "main"},
        "work_packages": ["WP-01"],
        "timestamps": {"created_at": "2026-01-01T00:00:00Z",
                       "updated_at": "2026-01-01T00:00:00Z"},
    }, ensure_ascii=False, indent=2), encoding="utf-8")


def make_stub(tmp_path: Path) -> Path:
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    stub = bindir / "codex"
    stub.write_text("#!/usr/bin/env python3\n" + STUB_CODEX)
    stub.chmod(0o755)
    return bindir


def run_gate(repo: Path, bindir: Path, log: Path, *,
             extra_env: dict | None = None,
             strip_env: tuple[str, ...] = ()) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(SRC) + (
        os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
    )
    env["PATH"] = f"{bindir}:{env['PATH']}"
    env["STUB_LOG"] = str(log)
    for name in strip_env:
        env.pop(name, None)
    env.update(extra_env or {})
    return subprocess.run(
        [sys.executable, "-m", "agentic_loop.gate", STATUS_REL],
        cwd=str(repo), capture_output=True, text=True, env=env,
    )


def stub_calls(log: Path) -> list[dict]:
    if not log.is_file():
        return []
    return [json.loads(line) for line in log.read_text().splitlines() if line]


def read_status(repo: Path) -> dict:
    return json.loads((repo / STATUS_REL).read_text(encoding="utf-8"))


def read_answer(repo: Path) -> dict:
    return json.loads((repo / ANSWER_REL).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# End-to-end: the eight routing scenarios on the real gate surface.
# ---------------------------------------------------------------------------
def test_primary_success_single_call_records_primary_identity(repo, tmp_path):
    log = tmp_path / "calls.jsonl"
    res = run_gate(repo, make_stub(tmp_path), log,
                   extra_env={"DEEPSEEK_API_KEY": API_KEY_PLACEHOLDER})

    assert res.returncode == 0, res.stderr
    assert "GATE_DECISION=ACCEPT" in res.stdout
    calls = stub_calls(log)
    assert [c["provider"] for c in calls] == ["kirogpt"]  # exactly one call

    status = read_status(repo)
    consult = status["consult"]
    assert consult["decision"] == "ACCEPT"
    assert consult["reviewed_by"] == "codex-cli"
    assert consult["provider"] == "kirogpt"
    assert consult["model"] == "gpt-5.6-sol"
    assert consult["fallback_used"] is False

    answer = read_answer(repo)
    assert answer["provider"] == "kirogpt"
    assert answer["model"] == "gpt-5.6-sol"
    assert answer["fallback_used"] is False

    # The real injection surface: primary provider flags reach codex argv.
    argv = calls[0]["argv"]
    assert "model_provider=kirogpt" in argv
    assert "model_providers.kirogpt.base_url=http://127.0.0.1:18090/v1" in argv
    assert "gpt-5.6-sol" in argv
    # The key VALUE never travels in argv or the stub log (name only).
    assert API_KEY_PLACEHOLDER not in json.dumps(calls)


def test_quota_primary_failure_fails_over_to_deepseekpro(repo, tmp_path):
    log = tmp_path / "calls.jsonl"
    res = run_gate(repo, make_stub(tmp_path), log, extra_env={
        "STUB_FAIL_KIROGPT": "quota",
        "DEEPSEEK_API_KEY": API_KEY_PLACEHOLDER,
    })

    assert res.returncode == 0, res.stderr
    assert "GATE_DECISION=ACCEPT" in res.stdout
    calls = stub_calls(log)
    assert [c["provider"] for c in calls] == ["kirogpt", "deepseekpro"]

    # stderr names the primary failure category and the effective server.
    assert "quota" in res.stderr
    assert "consult failover" in res.stderr
    assert "deepseekpro/deepseek-v4-pro" in res.stderr

    # The fallback invocation carries the deepseekpro injection argv.
    fb_argv = calls[1]["argv"]
    assert "model_provider=deepseekpro" in fb_argv
    assert "model_providers.deepseekpro.base_url=https://api.deepseek.com/v1" in fb_argv
    assert "deepseek-v4-pro" in fb_argv
    assert API_KEY_PLACEHOLDER not in json.dumps(calls)

    status = read_status(repo)
    consult = status["consult"]
    assert consult["decision"] == "ACCEPT"
    assert consult["reviewed_by"] == "codex-cli"
    assert consult["provider"] == "deepseekpro"
    assert consult["model"] == "deepseek-v4-pro"
    assert consult["fallback_used"] is True
    # notes record the primary category and the actual server (audit).
    assert "quota" in consult["notes"]
    assert "deepseek-v4-pro" in consult["notes"]

    answer = read_answer(repo)
    assert answer["provider"] == "deepseekpro"
    assert answer["model"] == "deepseek-v4-pro"
    assert answer["fallback_used"] is True


def test_auth_primary_failure_never_falls_back(repo, tmp_path):
    log = tmp_path / "calls.jsonl"
    res = run_gate(repo, make_stub(tmp_path), log, extra_env={
        "STUB_FAIL_KIROGPT": "auth",
        "DEEPSEEK_API_KEY": API_KEY_PLACEHOLDER,
    })

    assert res.returncode == 2
    assert [c["provider"] for c in stub_calls(log)] == ["kirogpt"]
    assert "GATE_FAIL" in res.stderr
    assert "auth_config" in res.stderr
    # No fallback attempt, no audit fields written on failure.
    consult = read_status(repo)["consult"]
    assert consult["decision"] is None
    assert "fallback_used" not in consult
    assert "provider" not in consult


def test_task_primary_failure_never_falls_back(repo, tmp_path):
    log = tmp_path / "calls.jsonl"
    res = run_gate(repo, make_stub(tmp_path), log, extra_env={
        "STUB_FAIL_KIROGPT": "task",
        "DEEPSEEK_API_KEY": API_KEY_PLACEHOLDER,
    })

    assert res.returncode == 2
    assert [c["provider"] for c in stub_calls(log)] == ["kirogpt"]
    assert "GATE_FAIL" in res.stderr
    assert "(task)" in res.stderr
    consult = read_status(repo)["consult"]
    assert consult["decision"] is None
    assert "fallback_used" not in consult


def test_fallback_failure_reports_both_categories_no_third_attempt(
        repo, tmp_path):
    log = tmp_path / "calls.jsonl"
    res = run_gate(repo, make_stub(tmp_path), log, extra_env={
        "STUB_FAIL_KIROGPT": "quota",
        "STUB_FAIL_DEEPSEEKPRO": "server",
        "DEEPSEEK_API_KEY": API_KEY_PLACEHOLDER,
    })

    assert res.returncode == 2
    # Exactly two calls — the fallback failure is the end.
    assert [c["provider"] for c in stub_calls(log)] == [
        "kirogpt", "deepseekpro"]
    assert "GATE_FAIL" in res.stderr
    assert "(quota)" in res.stderr  # primary category witness
    assert "(server)" in res.stderr  # fallback category witness
    assert "single-hop" in res.stderr
    consult = read_status(repo)["consult"]
    assert consult["decision"] is None
    assert "fallback_used" not in consult


def test_fallback_credential_missing_fails_closed_naming_env_var(
        repo, tmp_path):
    log = tmp_path / "calls.jsonl"
    res = run_gate(repo, make_stub(tmp_path), log,
                   extra_env={"STUB_FAIL_KIROGPT": "quota"},
                   strip_env=("DEEPSEEK_API_KEY",))

    assert res.returncode == 2
    # Fail closed BEFORE launching the fallback: exactly one call.
    assert [c["provider"] for c in stub_calls(log)] == ["kirogpt"]
    assert "GATE_FAIL" in res.stderr
    assert "DEEPSEEK_API_KEY" in res.stderr  # env var NAME is the witness
    assert API_KEY_PLACEHOLDER not in res.stderr


def test_no_fallback_provider_configured_fails_closed(repo, tmp_path):
    (repo / ".agentic" / "config.toml").write_text(CONFIG_NO_FALLBACK)
    log = tmp_path / "calls.jsonl"
    res = run_gate(repo, make_stub(tmp_path), log, extra_env={
        "STUB_FAIL_KIROGPT": "quota",
        "DEEPSEEK_API_KEY": API_KEY_PLACEHOLDER,
    })

    assert res.returncode == 2
    assert [c["provider"] for c in stub_calls(log)] == ["kirogpt"]
    assert "GATE_FAIL" in res.stderr
    assert "no consultant fallback_provider configured" in res.stderr


def test_independence_and_audit_use_fallback_identity(repo, tmp_path):
    log = tmp_path / "calls.jsonl"
    res = run_gate(repo, make_stub(tmp_path), log, extra_env={
        "STUB_FAIL_KIROGPT": "quota",
        "DEEPSEEK_API_KEY": API_KEY_PLACEHOLDER,
    })

    assert res.returncode == 0, res.stderr
    status = read_status(repo)
    consult = status["consult"]
    # The identity that served the consult is what gets audited; the primary
    # model must not appear as the serving model anywhere in the consult block.
    assert consult["provider"] == "deepseekpro"
    assert consult["model"] == "deepseek-v4-pro"
    assert consult["model"] != "gpt-5.6-sol"
    assert "Independence" in consult["notes"]
    # reviewed_by contract unchanged by the hop.
    assert consult["reviewed_by"] == "codex-cli"


# ---------------------------------------------------------------------------
# Direct unit tests over the failover helper (fake adapters, zero I/O).
# ---------------------------------------------------------------------------
class _Caps:
    sandbox_enforced = True
    structured_output = True


class _BadCaps:
    sandbox_enforced = False
    structured_output = False


class _FakeAdapter:
    def __init__(self, model: str, fail_text: str | None = None,
                 caps: type = _Caps) -> None:
        self._model = model
        self._fail_text = fail_text
        self._caps = caps
        self.calls = 0

    def capabilities(self):
        return self._caps()

    def identity(self) -> AgentIdentity:
        return AgentIdentity(tool="codex", model=self._model, account=None,
                             session=None)

    def review(self, **kwargs) -> Verdict:
        self.calls += 1
        if self._fail_text is not None:
            raise RuntimeError(self._fail_text)
        return Verdict(decision="ACCEPT", rationale="stub", findings=[])


class _Binding:
    def __init__(self, provider: str, model: str, env: str) -> None:
        self.provider = provider
        self.identity_model = model
        self.api_key_env = env


def _bindings() -> tuple[_Binding, _Binding]:
    primary = _Binding("kirogpt", "gpt-5.6-sol", "OPENAI_API_KEY")
    fallback = _Binding("deepseekpro", "deepseek-v4-pro", "DEEPSEEK_API_KEY")
    return primary, fallback


KWARGS = {"diff": "d", "brief": None, "contract": None, "effort": "medium"}


def test_helper_primary_success_returns_primary_adapter():
    primary, fallback = _bindings()
    adapter = _FakeAdapter("gpt-5.6-sol")
    verdict, effective, provider, model, used, primary_failure = (
        _consult_with_failover(adapter, primary, fallback, None, KWARGS,
                               DEFAULT_QUOTA_PATTERNS))
    assert verdict.decision == "ACCEPT"
    assert effective is adapter
    assert provider == "kirogpt"
    assert model == "gpt-5.6-sol"
    assert used is False
    assert primary_failure is None
    assert adapter.calls == 1


def test_helper_quota_failure_returns_fallback_adapter_identity(
        monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "x")
    primary, fallback = _bindings()
    primary_adapter = _FakeAdapter("gpt-5.6-sol", fail_text="Error: HTTP 429")
    made: list[_Binding] = []

    def factory(binding):
        made.append(binding)
        return _FakeAdapter("deepseek-v4-pro")

    verdict, effective, provider, model, used, primary_failure = (
        _consult_with_failover(primary_adapter, primary, fallback, factory,
                               KWARGS, DEFAULT_QUOTA_PATTERNS))
    assert verdict.decision == "ACCEPT"
    assert made == [fallback]            # fallback built exactly once
    assert effective is not primary_adapter
    assert effective.identity().model == "deepseek-v4-pro"  # served identity
    assert provider == "deepseekpro"
    assert model == "deepseek-v4-pro"
    assert used is True
    assert primary_failure[0] == "quota"  # primary category preserved
    assert primary_adapter.calls == 1


def test_helper_auth_failure_raises_without_fallback(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "x")
    primary, fallback = _bindings()
    primary_adapter = _FakeAdapter(
        "gpt-5.6-sol", fail_text="Error: 401 Unauthorized")
    with pytest.raises(ConsultFailoverError) as excinfo:
        _consult_with_failover(primary_adapter, primary, fallback, None,
                               KWARGS, DEFAULT_QUOTA_PATTERNS)
    message = str(excinfo.value)
    assert "auth_config" in message  # original category is the witness
    assert "deepseekpro" not in message  # no fallback was attempted
    assert primary_adapter.calls == 1


def test_helper_fallback_failure_reports_both_categories(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "x")
    primary, fallback = _bindings()
    primary_adapter = _FakeAdapter("gpt-5.6-sol", fail_text="Error: HTTP 429")
    fallback_adapter = _FakeAdapter(
        "deepseek-v4-pro", fail_text="Error: HTTP 503 Service Unavailable")
    with pytest.raises(ConsultFailoverError) as excinfo:
        _consult_with_failover(
            primary_adapter, primary, fallback,
            lambda b: fallback_adapter, KWARGS, DEFAULT_QUOTA_PATTERNS)
    message = str(excinfo.value)
    assert "(quota)" in message
    assert "(server)" in message
    assert primary_adapter.calls == 1
    assert fallback_adapter.calls == 1


def test_helper_missing_fallback_binding_fails_closed():
    primary, _ = _bindings()
    primary_adapter = _FakeAdapter("gpt-5.6-sol", fail_text="Error: HTTP 429")
    with pytest.raises(ConsultFailoverError) as excinfo:
        _consult_with_failover(primary_adapter, primary, None, None,
                               KWARGS, DEFAULT_QUOTA_PATTERNS)
    assert "no consultant fallback_provider configured" in str(excinfo.value)
    assert primary_adapter.calls == 1


def test_helper_missing_fallback_credential_names_env_var_only(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    primary, fallback = _bindings()
    primary_adapter = _FakeAdapter("gpt-5.6-sol", fail_text="Error: HTTP 429")
    with pytest.raises(ConsultFailoverError) as excinfo:
        _consult_with_failover(primary_adapter, primary, fallback, None,
                               KWARGS, DEFAULT_QUOTA_PATTERNS)
    message = str(excinfo.value)
    assert "DEEPSEEK_API_KEY" in message
    assert "$DEEPSEEK_API_KEY" in message
    assert primary_adapter.calls == 1
# ---------------------------------------------------------------------------
# Consult finding 3 (REWORK r2): a fallback CONSTRUCTION or CAPABILITIES
# failure is still a single-hop fail-closed end — the error must preserve the
# PRIMARY category and name the fallback STAGE, and there is never a third
# attempt (the fallback review is never invoked).
# ---------------------------------------------------------------------------
def test_helper_fallback_construction_failure_names_primary_category_and_stage(
        monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "x")
    primary, fallback = _bindings()
    primary_adapter = _FakeAdapter("gpt-5.6-sol", fail_text="Error: HTTP 429")

    def bad_factory(binding):
        raise ValueError("adapter init exploded")

    with pytest.raises(ConsultFailoverError) as excinfo:
        _consult_with_failover(primary_adapter, primary, fallback, bad_factory,
                               KWARGS, DEFAULT_QUOTA_PATTERNS)
    message = str(excinfo.value)
    assert "(quota)" in message           # primary category preserved
    assert "fallback construction" in message   # fallback stage named
    assert "fallback_construction" in message
    assert primary_adapter.calls == 1     # primary tried exactly once
    assert "ValueError" in message


def test_helper_fallback_capability_failure_names_primary_category_and_stage(
        monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "x")
    primary, fallback = _bindings()
    primary_adapter = _FakeAdapter("gpt-5.6-sol", fail_text="Error: HTTP 429")
    fallback_adapter = _FakeAdapter("deepseek-v4-pro", caps=_BadCaps)

    with pytest.raises(ConsultFailoverError) as excinfo:
        _consult_with_failover(
            primary_adapter, primary, fallback,
            lambda b: fallback_adapter, KWARGS, DEFAULT_QUOTA_PATTERNS)
    message = str(excinfo.value)
    assert "(quota)" in message           # primary category preserved
    assert "fallback capabilities" in message   # fallback stage named
    assert "fallback_capabilities" in message
    assert primary_adapter.calls == 1     # primary tried exactly once
    assert fallback_adapter.calls == 0    # fallback review never called


# ---------------------------------------------------------------------------
# Invariant 10 (consult finding 1, REWORK r2): negative-oracle tests whose
# mutations are applied to the REAL input surface produced by one genuine
# quota-failover e2e run — the stub codex JSONL call log (actual argv + call
# sequence) and the persisted status JSON bytes — never to in-memory objects.
#
# _audit_oracle is the single audit oracle over those raw bytes; the positive
# reachability control proves the untouched artifacts satisfy it, and each
# forbidden mutation must turn the SAME oracle red.
# ---------------------------------------------------------------------------
def _run_quota_failover_e2e(tmp_path: Path):
    """One real e2e quota-failover run; returns (call_log, status_path, result)."""
    log = tmp_path / "calls.jsonl"
    repo = _fresh_repo(tmp_path)
    res = run_gate(repo, make_stub(tmp_path), log,
                   extra_env={
                       "STUB_FAIL_KIROGPT": "quota",
                       "DEEPSEEK_API_KEY": API_KEY_PLACEHOLDER,
                   })
    assert res.returncode == 0, res.stderr
    assert "GATE_DECISION=ACCEPT" in res.stdout
    return log, repo / STATUS_REL


def _fresh_repo(tmp_path: Path) -> Path:
    """The module ``repo`` fixture cannot be reused across tests, so build the
    same isolated repo shape on demand inside the given tmp dir."""
    r = tmp_path / "repo"
    r.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=r, check=True)
    _git(r, "config", "user.email", "t@e.com")
    _git(r, "config", "user.name", "T")
    (r / "docs" / "plans" / ITERATION).mkdir(parents=True)
    (r / "seed.txt").write_text("seed\n")
    _git(r, "add", "-A")
    _git(r, "commit", "-qm", "seed")
    _git(r, "branch", "-M", "main")
    seed = _git(r, "rev-parse", "HEAD")

    (r / ".agentic").mkdir()
    (r / ".agentic" / "config.toml").write_text(CONFIG_WITH_FALLBACK)
    (r / "docs" / "plans" / ITERATION / "WP-01-brief.md").write_text(
        "# brief\n")

    _git(r, "checkout", "-q", "-b", "feat/x")
    (r / "wp_change.txt").write_text("wp code change\n")
    _git(r, "add", "-A")
    _git(r, "commit", "-qm", "impl: wp code change")
    tip = _git(r, "rev-parse", "HEAD")

    _write_status(
        r,
        git={"base_branch": "feat/x", "base_commit": seed,
             "branch": "feat/x", "worktree": ".", "commit": tip},
        scope={"allowed_paths": ["wp_change.txt", "seed.txt",
                                 f"docs/plans/{ITERATION}/"],
               "forbidden_paths": []},
    )
    return r


def _audit_oracle(call_log_bytes: bytes, status_bytes: bytes) -> None:
    """Invariant-10 audit oracle over the REAL failover artifacts.

    Asserts, on the raw bytes (not parsed in-memory objects handed in by the
    producer), that:
      * the stub codex call sequence is EXACTLY ["kirogpt", "deepseekpro"]
        and each invocation carries its real ``-c model_provider=<name>``
        argv witness;
      * the persisted status JSON records the fallback identity honestly:
        consult.provider/model/fallback_used == deepseekpro/deepseek-v4-pro/
        True, and reviewed_by stays "codex-cli".
    Raises AssertionError on any forbidden deviation.
    """
    calls = [json.loads(line) for line in
             call_log_bytes.decode("utf-8").splitlines() if line.strip()]
    providers = [c["provider"] for c in calls]
    assert providers == ["kirogpt", "deepseekpro"], (
        f"call sequence witness violated: {providers}")
    assert "model_provider=kirogpt" in calls[0]["argv"]
    assert "model_provider=deepseekpro" in calls[1]["argv"]

    status = json.loads(status_bytes.decode("utf-8"))
    consult = status["consult"]
    assert consult["provider"] == "deepseekpro", (
        "fallback identity not audited: provider must be deepseekpro")
    assert consult["model"] == "deepseek-v4-pro"
    assert consult["fallback_used"] is True
    assert consult["reviewed_by"] == "codex-cli"


def test_invariant10_oracle_positive_control_untouched_artifacts_pass(
        tmp_path):
    """Reachability control: the REAL untouched artifacts satisfy the oracle."""
    log, status_path = _run_quota_failover_e2e(tmp_path)
    call_log_bytes = log.read_bytes()
    status_bytes = status_path.read_bytes()
    # sanity: these are the real e2e artifacts, not synthetic fixtures
    assert b"deepseekpro" in call_log_bytes
    assert b'"provider": "deepseekpro"' in status_bytes
    _audit_oracle(call_log_bytes, status_bytes)  # must NOT raise


def test_invariant10_forbidden_mutation_status_provider_becomes_kirogpt_turns_oracle_red(
        tmp_path):
    """Mutation (a): corrupt the persisted status JSON bytes so
    consult.provider reads "kirogpt" (the fallback identity is not audited).
    The byte string must actually change and the SAME oracle must turn red."""
    log, status_path = _run_quota_failover_e2e(tmp_path)
    original = status_path.read_bytes()
    needle = b'"provider": "deepseekpro"'
    assert needle in original  # the real artifact carries the fallback identity
    mutated = original.replace(needle, b'"provider": "kirogpt"', 1)
    assert mutated != original  # the real byte string actually changed
    # Apply the mutation to the real file, then re-read the bytes.
    status_path.write_bytes(mutated)
    reread = status_path.read_bytes()
    assert reread == mutated
    with pytest.raises(AssertionError):
        _audit_oracle(log.read_bytes(), reread)


def test_invariant10_forbidden_mutation_drop_fallback_invocation_from_call_log_turns_oracle_red(
        tmp_path):
    """Mutation (b): drop the fallback invocation from the real stub call log
    (variant: rewrite its provider to "kirogpt"). The call-count/argv witness
    must fail for each."""
    log, status_path = _run_quota_failover_e2e(tmp_path)
    original = log.read_bytes()
    assert original.count(b"\n") == 2  # exactly two JSONL records, one per call

    # (b1) drop the fallback invocation line from the real log bytes.
    lines = [ln for ln in original.splitlines(keepends=True)
             if b'"provider": "deepseekpro"' not in ln]
    dropped = b"".join(lines)
    assert dropped != original
    log.write_bytes(dropped)
    with pytest.raises(AssertionError):
        _audit_oracle(log.read_bytes(), status_path.read_bytes())

    # (b2) rewrite the fallback provider to "kirogpt" in the real log bytes.
    rewritten = original.replace(b'"provider": "deepseekpro"',
                                 b'"provider": "kirogpt"', 1)
    assert rewritten != original
    log.write_bytes(rewritten)
    with pytest.raises(AssertionError):
        _audit_oracle(log.read_bytes(), status_path.read_bytes())
