from __future__ import annotations

import os
import shutil
import subprocess

from agentic_loop.adapters.base import Adapter
from agentic_loop.adapters.base import AdapterCapabilities
from agentic_loop.adapters.base import AgentIdentity
from agentic_loop.adapters.base import ImplementResult
from agentic_loop.adapters.base import ReviewContract
from agentic_loop.adapters.base import Verdict
from agentic_loop.provider_binding import ProviderBinding
from agentic_loop.secret_redaction import redact_env_value


class ClaudeAdapter(Adapter):
    """Claude CLI 的 developer adapter。

    命令形态为用户 2026-08-10 裁决的最小实现：
    ``claude -p <prompt>``，并以 ``cwd=worktree`` 执行（Claude CLI 无 ``-w`` flag）。
    自主审批 / 权限 flag 与 brief→prompt 合并归 WP-13 engine 编排。

    本 adapter 只负责命令封装与执行，不写 status、不 merge/push、不改仓库文件。
    """

    name = "claude"

    def __init__(self, claude_bin: str = "claude",
                 binding: ProviderBinding | None = None) -> None:
        self._claude_bin = claude_bin
        self._binding = binding

    def capabilities(self) -> AdapterCapabilities:
        # claude 不自证只读沙箱，诚实上报 fail-closed 能力，
        # 使 engine 拒绝其充当 reviewer/consultant。
        return AdapterCapabilities(
            sandbox_enforced=False,
            structured_output=False,
            can_be_engine_sandboxed=False,
        )

    def identity(self) -> AgentIdentity:
        model = self._binding.identity_model if self._binding else None
        return AgentIdentity(tool="claude", model=model, account=None, session=None)

    def _build_env(self) -> dict:
        """Subprocess env with DeepSeek injected when a binding is present."""
        env = dict(os.environ)
        if self._binding is not None:
            env["ANTHROPIC_BASE_URL"] = self._binding.anthropic_base_url or ""
            env["ANTHROPIC_AUTH_TOKEN"] = os.environ.get(self._binding.api_key_env, "")
            env["ANTHROPIC_MODEL"] = self._binding.cli_selector
        return env

    def implement(
        self,
        *,
        worktree: str,
        brief: str,
        prompt: str,
        dry_run: bool = False,
    ) -> ImplementResult:
        """Developer 能力：在 worktree 下派发 claude 执行 prompt。

        ``brief`` 进签名以满足统一契约，但本 WP 不改写命令或 prompt；
        brief 如何并入 prompt 归 WP-13 engine 编排。
        """
        cmd = [self._claude_bin, "-p", prompt]           # key never in argv
        if dry_run:
            return ImplementResult(
                dispatched=False,
                exit_code=None,
                output="",
                command=tuple(cmd),
                dry_run=True,
            )

        try:
            proc = subprocess.run(
                cmd,
                cwd=worktree,
                env=self._build_env(),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
        except OSError as exc:
            return ImplementResult(
                dispatched=False,
                exit_code=None,
                output=str(exc),
                command=tuple(cmd),
                dry_run=False,
            )
        out = redact_env_value(proc.stdout or "",
                               self._binding.api_key_env) if self._binding else (proc.stdout or "")
        return ImplementResult(
            dispatched=proc.returncode == 0,
            exit_code=proc.returncode,
            output=out,
            command=tuple(cmd),
            dry_run=False,
        )

    def review(
        self,
        *,
        diff: str,
        brief: str | None,
        contract: ReviewContract,
        effort: str,
    ) -> Verdict:
        """Claude adapter 在本框架中充当 developer adapter，不提供 reviewer/consultant 能力。"""
        raise NotImplementedError(
            f"adapter {self.name} does not implement reviewer capability"
        )

    def probe(self) -> bool:
        """轻量存活探测：``shutil.which`` 命中可执行文件即视为可派发，不真跑 claude。"""
        return shutil.which(self._claude_bin) is not None

    _PROBE_PROMPT = "reply exactly: DEEPSEEK_PROBE_OK"
    _SENTINEL = "DEEPSEEK_PROBE_OK"

    def probe_injection(self) -> bool:
        if self._binding is None:
            return self.probe()
        try:
            proc = subprocess.run(
                [self._claude_bin, "-p", self._PROBE_PROMPT],
                env=self._build_env(),
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            )
        except OSError:
            return False
        return proc.returncode == 0 and self._SENTINEL in (proc.stdout or "")
