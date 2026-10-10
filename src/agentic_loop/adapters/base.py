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
class ReviewerAttestation:
    """WP-07: 结构化 reviewer attestation(声明,非 engine 证明)。

    在 bootstrap 路径下,reviewer 是编排者(无 adapter identity),engine 拿不到
    其可观测 model id。此时 weak-attested 的评级依据不再是散在 reasons 里的
    自由文本,而是这份带字段的结构化声明。它由编排者填(``attested_by`` 指明
    声明来源),engine 只负责**校验结构完整 + 各条件为真**,校验不过就
    fail-closed 到 none。

    诚实边界:attestation 是声明,不是 engine-proven 信号,绝不据此评 strong;
    ``weak-attested`` 的 "attested" 后缀即指本结构,而非 engine 观测证明。
    """

    reviewer_role: str
    reviewer_tool: str
    fresh_session: bool
    adversarial_prompt: bool
    attested_by: str
    attested_at: str | None = None

    def is_complete(self) -> bool:
        """结构完整:必填字符串字段均非空(时间戳可选)。"""
        return bool(
            isinstance(self.reviewer_role, str)
            and self.reviewer_role.strip()
            and isinstance(self.reviewer_tool, str)
            and self.reviewer_tool.strip()
            and isinstance(self.attested_by, str)
            and self.attested_by.strip()
        )

    def is_valid(self) -> bool:
        """结构完整 + 各声明条件为真(fresh_session & adversarial_prompt)。

        严格布尔判定:``fresh_session`` 与 ``adversarial_prompt`` 必须是 Python
        真值 ``True``(JSON ``true``),字符串 ``"false"`` / ``"true"`` 或任何非
        bool 类型一律判 invalid,避免 ``bool("false") == True`` 的隐性拐杖。
        """
        return (
            self.is_complete()
            and self.fresh_session is True
            and self.adversarial_prompt is True
        )


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

    _binding = None  # 子类构造时覆盖

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

    def probe_injection_detail(self) -> tuple[bool, str]:
        """真实注入探针（detail 形态）：返回 ``(ok, raw_output)``。

        binding 非空时子类应覆写本方法，返回探针结果与真实输出。
        默认无 binding 时等价于存活探测，输出为空字符串。
        """
        if getattr(self, "_binding", None) is None:
            return (self.probe(), "")
        raise NotImplementedError(
            f"adapter {self.name} must implement probe_injection for binding path"
        )

    def probe_injection(self) -> bool:
        """真实注入探针：委托 ``probe_injection_detail()`` 的布尔结果。

        子类覆写 ``probe_injection_detail()`` 即可；引擎需要原始输出做额度判定时
        调用 detail 形态，其余路径用布尔形态。
        """
        return self.probe_injection_detail()[0]
