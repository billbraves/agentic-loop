from __future__ import annotations

import shutil
import subprocess

from agentic_loop.adapters.base import Adapter
from agentic_loop.adapters.base import AdapterCapabilities
from agentic_loop.adapters.base import AgentIdentity
from agentic_loop.adapters.base import ImplementResult
from agentic_loop.adapters.base import ReviewContract
from agentic_loop.adapters.base import Verdict


class ClaudeAdapter(Adapter):
    """Claude CLI 的 developer adapter。

    命令形态为用户 2026-08-10 裁决的最小实现：
    ``claude -p <prompt>``，并以 ``cwd=worktree`` 执行（Claude CLI 无 ``-w`` flag）。
    自主审批 / 权限 flag 与 brief→prompt 合并归 WP-13 engine 编排。

    本 adapter 只负责命令封装与执行，不写 status、不 merge/push、不改仓库文件。
    """

    name = "claude"

    def __init__(self, claude_bin: str = "claude") -> None:
        self._claude_bin = claude_bin

    def capabilities(self) -> AdapterCapabilities:
        # claude 不自证只读沙箱，诚实上报 fail-closed 能力，
        # 使 engine 拒绝其充当 reviewer/consultant。
        return AdapterCapabilities(
            sandbox_enforced=False,
            structured_output=False,
            can_be_engine_sandboxed=False,
        )

    def identity(self) -> AgentIdentity:
        # 本机 CLI 无法可靠观测底层 model/account/session，拿不到则填 None，不伪造。
        return AgentIdentity(
            tool="claude",
            model=None,
            account=None,
            session=None,
        )

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
        cmd = [self._claude_bin, "-p", prompt]
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
        return ImplementResult(
            dispatched=proc.returncode == 0,
            exit_code=proc.returncode,
            output=proc.stdout or "",
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
