from __future__ import annotations

import os
import stat
import subprocess
import tempfile
from contextlib import contextmanager

from agentic_loop.adapters.base import Adapter
from agentic_loop.adapters.base import AdapterCapabilities
from agentic_loop.adapters.base import AgentIdentity
from agentic_loop.adapters.base import ImplementResult
from agentic_loop.adapters.base import ReviewContract
from agentic_loop.adapters.base import Verdict
from agentic_loop.provider_binding import ProviderBinding
from agentic_loop.secret_redaction import redact_env_value


class KimiAdapter(Adapter):
    """Kimi CLI 的 developer adapter。

    逐字封装现有 ``redispatch.sh`` 的 kimi 派发语义：
    ``kimi --afk --print -w <worktree> -p <prompt>``；
    存活探测：``kimi -p "reply PROBE_OK"``，退出 0 且 stdout 含 PROBE_OK 为成功。

    本 adapter 只负责命令封装与执行，不写 status、不 merge/push、不改仓库文件。
    """

    name = "kimi"

    def __init__(self, kimi_bin: str = "kimi",
                 binding: ProviderBinding | None = None) -> None:
        self._kimi_bin = kimi_bin
        self._binding = binding

    def capabilities(self) -> AdapterCapabilities:
        # kimi 不自证只读沙箱，诚实上报 fail-closed 能力，
        # 使 engine 拒绝其充当 reviewer/consultant。
        return AdapterCapabilities(
            sandbox_enforced=False,
            structured_output=False,
            can_be_engine_sandboxed=False,
        )

    def identity(self) -> AgentIdentity:
        model = self._binding.identity_model if self._binding else None
        return AgentIdentity(tool="kimi", model=model, account=None, session=None)

    @contextmanager
    def _temp_config(self):
        """Yield a 0600 temp TOML with DeepSeek provider+model; always removed."""
        b = self._binding
        key = os.environ.get(b.api_key_env, "")
        # provider name is fixed per DeepSeek anthropic-compat endpoint.
        text = (
            f'[providers."{b.provider}-anthropic"]\n'
            f'type     = "anthropic"\n'
            f'base_url = "{b.anthropic_base_url}"\n'
            f'api_key  = "{key}"\n\n'
            f'[models."{b.cli_selector}"]\n'
            f'provider = "{b.provider}-anthropic"\n'
            f'model    = "{b.identity_model}"\n'
            f'max_context_size = 786432\n'
        )
        fd, path = tempfile.mkstemp(suffix=".toml", prefix="agentic-kimi-")
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(text)
            yield path
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass

    def implement(
        self,
        *,
        worktree: str,
        brief: str,
        prompt: str,
        dry_run: bool = False,
    ) -> ImplementResult:
        """Developer 能力：派发 kimi 到 worktree 执行 prompt。

        ``brief`` 进签名以满足统一契约，但本 WP 不改写现有 kimi CLI flag；
        brief 如何并入 prompt 归 WP-13 engine 编排。
        """
        if self._binding is None:
            cmd = [self._kimi_bin, "--afk", "--print", "-w", worktree, "-p", prompt]
        else:
            # dry_run shows the shape (temp path placeholder); real run below fills it.
            cmd = [self._kimi_bin, "--afk", "--print", "--config-file", "<tmp>",
                   "--model", self._binding.cli_selector, "-w", worktree, "-p", prompt]
        if dry_run:
            return ImplementResult(
                dispatched=False,
                exit_code=None,
                output="",
                command=tuple(cmd),
                dry_run=True,
            )
        if self._binding is None:
            real_cmd = [self._kimi_bin, "--afk", "--print", "-w", worktree, "-p", prompt]
            return self._run(real_cmd, redact_env=None)
        with self._temp_config() as cfg:
            real_cmd = [self._kimi_bin, "--afk", "--print", "--config-file", cfg,
                        "--model", self._binding.cli_selector, "-w", worktree, "-p", prompt]
            return self._run(real_cmd, redact_env=self._binding.api_key_env)

    def _run(self, cmd, *, redact_env):
        try:
            proc = subprocess.run(
                cmd,
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
        out = proc.stdout or ""
        if redact_env:
            out = redact_env_value(out, redact_env)
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
        """Kimi adapter 是 developer adapter，不提供 reviewer/consultant 能力。"""
        raise NotImplementedError(
            f"adapter {self.name} does not implement reviewer capability"
        )

    def probe(self) -> bool:
        """存活探测：``kimi -p "reply PROBE_OK"``，成功 = 退出 0 且 stdout 含 PROBE_OK。"""
        try:
            proc = subprocess.run(
                [self._kimi_bin, "-p", "reply PROBE_OK"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
        except OSError:
            return False
        return proc.returncode == 0 and "PROBE_OK" in (proc.stdout or "")

    _PROBE_PROMPT = "reply exactly: DEEPSEEK_PROBE_OK"
    _SENTINEL = "DEEPSEEK_PROBE_OK"

    def probe_injection_detail(self) -> tuple[bool, str]:
        if self._binding is None:
            try:
                proc = subprocess.run(
                    [self._kimi_bin, "-p", "reply PROBE_OK"],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                )
            except OSError:
                return (False, "")
            out = proc.stdout or ""
            return (proc.returncode == 0 and "PROBE_OK" in out, out)
        with self._temp_config() as cfg:
            try:
                proc = subprocess.run(
                    [self._kimi_bin, "--config-file", cfg,
                     "--model", self._binding.cli_selector, "-p", self._PROBE_PROMPT],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                )
            except OSError:
                return (False, "")
        out = proc.stdout or ""
        if self._binding is not None:
            out = redact_env_value(out, self._binding.api_key_env)
        ok = proc.returncode == 0 and self._SENTINEL in out
        return (ok, out)
