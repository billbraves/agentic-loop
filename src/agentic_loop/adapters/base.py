from __future__ import annotations

import abc
from dataclasses import dataclass
from dataclasses import field


@dataclass(frozen=True)
class AgentIdentity:
    """INV-1: 证明双签真独立的身份。engine 用它校验二签 identity 真不同。

    只填 engine 可观测或施加的信号；拿不到时显式填 None，绝不伪造。
    """

    tool: str
    model: str | None = None
    account: str | None = None
    session: str | None = None


@dataclass(frozen=True)
class AdapterCapabilities:
    """INV-2: adapter 可验证能力，决定它能否充当审核者。"""

    sandbox_enforced: bool = False
    structured_output: bool = False
    can_be_engine_sandboxed: bool = False


@dataclass(frozen=True)
class ReviewContract:
    """INV-2/INV-7: reviewer/consultant 执行契约。engine 按 role 构造并校验。"""

    role: str
    sandbox: str = "read-only"
    output_schema: dict = field(default_factory=dict)
    forbid_repo_read: bool = True
    review_policy: str = ""

    def __post_init__(self) -> None:
        if self.role not in ("reviewer", "consultant"):
            raise ValueError(
                f"Invalid role: {self.role!r}; must be 'reviewer' or 'consultant'"
            )

    @property
    def writes(self) -> tuple[str, ...]:
        """INV-7: 一签写 review 块，二签写 consult 块，绝不混。"""
        mapping = {"reviewer": ("review",), "consultant": ("consult",)}
        if self.role not in mapping:
            raise ValueError(
                f"Invalid role: {self.role!r}; must be 'reviewer' or 'consultant'"
            )
        return mapping[self.role]


@dataclass(frozen=True)
class Verdict:
    """结构化裁决，与 codex_merge_gate.sh verdict.schema.json 同构。"""

    decision: str
    rationale: str
    findings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.decision not in ("ACCEPT", "REWORK", "CONSULT"):
            raise ValueError(
                f"Invalid decision: {self.decision!r}; "
                "must be ACCEPT, REWORK, or CONSULT"
            )
        if not isinstance(self.findings, tuple):
            object.__setattr__(self, "findings", tuple(self.findings))


@dataclass(frozen=True)
class ImplementResult:
    """Developer 能力 `implement()` 的返回契约。

    与 `redispatch.sh` 现有 stdout/dry-run JSON 形态对齐：
    - `dispatched`: 派发命令是否成功发起；
    - `exit_code`: 子进程退出码（dry-run 为 ``None``）；
    - `output`: 子进程 stdout/stderr 合并尾部，供审计/health；
    - `command`: 实际执行或计划执行的命令元组；
    - `dry_run`: 是否为 dry-run（不真正 exec）。
    """

    dispatched: bool
    exit_code: int | None
    output: str
    command: tuple[str, ...]
    dry_run: bool = False


class Adapter(abc.ABC):
    """工具无关的 adapter 抽象基类。"""

    name: str

    @abc.abstractmethod
    def identity(self) -> AgentIdentity:
        """上报底层身份，供 engine 做 INV-1 独立性校验。"""
        raise NotImplementedError

    @abc.abstractmethod
    def capabilities(self) -> AdapterCapabilities:
        """上报可验证能力，供 engine 做 INV-2 沙箱/禁读可强制性分级。"""
        raise NotImplementedError

    @abc.abstractmethod
    def review(
        self,
        *,
        diff: str,
        brief: str | None,
        contract: ReviewContract,
        effort: str,
    ) -> Verdict:
        """Reviewer/Consultant 能力：在 contract 约束下出结构化裁决。

        只构造/返回裁决，不写任何 status 文件。
        """
        raise NotImplementedError

    def implement(
        self,
        *,
        worktree: str,
        brief: str,
        prompt: str,
    ) -> ImplementResult:
        """Developer 能力：在 worktree 里跑实现。

        基类提供安全默认，使 review-only adapter（如 CodexAdapter）仍可实例化。
        Developer adapter 必须覆写此方法。
        """
        raise NotImplementedError(
            f"adapter {self.name} does not implement developer capability"
        )

    @abc.abstractmethod
    def probe(self) -> bool:
        """存活探测。"""
        raise NotImplementedError
