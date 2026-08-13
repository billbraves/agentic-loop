from __future__ import annotations

import subprocess

from agentic_loop.adapters.base import Adapter
from agentic_loop.adapters.base import AdapterCapabilities
from agentic_loop.adapters.base import AgentIdentity
from agentic_loop.adapters.base import ImplementResult
from agentic_loop.adapters.base import ReviewContract
from agentic_loop.adapters.base import Verdict


class KimiAdapter(Adapter):
    """Kimi CLI 的 developer adapter。

    逐字封装现有 ``redispatch.sh`` 的 kimi 派发语义：
    ``kimi --afk --print -w <worktree> -p <prompt>``；
    存活探测：``kimi -p "reply PROBE_OK"``，退出 0 且 stdout 含 PROBE_OK 为成功。

    本 adapter 只负责命令封装与执行，不写 status、不 merge/push、不改仓库文件。
    """

    name = "kimi"

    def __init__(self, kimi_bin: str = "kimi") -> None:
        self._kimi_bin = kimi_bin

    def capabilities(self) -> AdapterCapabilities:
        # kimi 不自证只读沙箱，诚实上报 fail-closed 能力，
        # 使 engine 拒绝其充当 reviewer/consultant。
        return AdapterCapabilities(
            sandbox_enforced=False,
            structured_output=False,
            can_be_engine_sandboxed=False,
        )

    def identity(self) -> AgentIdentity:
        # 本机 CLI 无法可靠观测底层 model/account/session，拿不到则填 None，不伪造。
        return AgentIdentity(
            tool="kimi",
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
        """Developer 能力：派发 kimi 到 worktree 执行 prompt。

        ``brief`` 进签名以满足统一契约，但本 WP 不改写现有 kimi CLI flag；
        brief 如何并入 prompt 归 WP-13 engine 编排。
        """
        cmd = [
            self._kimi_bin,
            "--afk",
            "--print",
            "-w",
            worktree,
            "-p",
            prompt,
        ]
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
