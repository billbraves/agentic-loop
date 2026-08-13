from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from agentic_loop.adapters.base import Adapter
from agentic_loop.adapters.base import AdapterCapabilities
from agentic_loop.adapters.base import AgentIdentity
from agentic_loop.adapters.base import ReviewContract
from agentic_loop.adapters.base import Verdict


class CodexAdapter(Adapter):
    """Codex CLI 的 review adapter。

    逐字封装现有 codex_merge_gate.sh 的安全语义：
    ``codex exec --sandbox read-only --skip-git-repo-check
    -c model_reasoning_effort=<effort> --output-schema <schema> -o <answer>``。

    与现有 gate 的唯一差异：投资硬规则不再硬编码，改由
    ``contract.review_policy`` 注入占位（WP-10 从 config 填充）。
    """

    name = "codex"

    def __init__(self, codex_bin: str = "codex") -> None:
        self._codex_bin = codex_bin

    def capabilities(self) -> AdapterCapabilities:
        return AdapterCapabilities(
            sandbox_enforced=True,
            structured_output=True,
            can_be_engine_sandboxed=False,
        )

    def identity(self) -> AgentIdentity:
        """上报 engine 可观测信号；拿不到则填 None，不伪造。"""
        return AgentIdentity(
            tool="codex",
            model=None,
            account=None,
            session=None,
        )

    def probe(self) -> bool:
        return shutil.which(self._codex_bin) is not None

    def review(
        self,
        *,
        diff: str,
        brief: str | None,
        contract: ReviewContract,
        effort: str,
    ) -> Verdict:
        with tempfile.TemporaryDirectory() as workdir:
            workdir_path = Path(workdir)

            schema_file = workdir_path / "verdict.schema.json"
            schema_file.write_text(
                json.dumps(contract.output_schema, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            prompt = self._build_prompt(diff=diff, brief=brief, contract=contract)
            prompt_file = workdir_path / "prompt.md"
            prompt_file.write_text(prompt, encoding="utf-8")

            answer_file = workdir_path / "answer.md"

            cmd = [
                self._codex_bin,
                "exec",
                "--sandbox",
                "read-only",
                "--skip-git-repo-check",
                "-c",
                f"model_reasoning_effort={effort}",
                "--output-schema",
                str(schema_file),
                "-o",
                str(answer_file),
                "-",
            ]

            proc = subprocess.run(
                cmd,
                input=prompt.encode("utf-8"),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            if proc.returncode != 0:
                err = proc.stderr.decode("utf-8", errors="replace").strip()
                raise RuntimeError(
                    f"codex exec failed (exit {proc.returncode}): {err}"
                )

            raw: str | None = None
            if answer_file.exists() and answer_file.stat().st_size > 0:
                raw = answer_file.read_text(encoding="utf-8").strip()
            else:
                stdout = proc.stdout.decode("utf-8", errors="replace").strip()
                if stdout:
                    raw = stdout

            if raw is None:
                raise RuntimeError("codex produced no verdict output")

            obj = self._parse_verdict(raw)
            return Verdict(
                decision=obj["decision"],
                rationale=obj.get("rationale", ""),
                findings=obj.get("findings") or [],
            )

    def _build_prompt(
        self, *, diff: str, brief: str | None, contract: ReviewContract
    ) -> str:
        lines = [
            "You are Codex acting as the independent Architecture & Incident Consultant",
            "(AGENTS.md §2). A separate reviewer (Claude) already returned ACCEPT. You are",
            "the SECOND, independent signature on the merge gate. Do not defer to the first",
            "reviewer. Judge the diff on its own merits against the work-package brief.",
            "",
            "Return a structured verdict:",
            "  ACCEPT  — the diff satisfies the brief; no blocking correctness, architecture,",
            "            time/as-of, migration, or security concern; no test/threshold/signal",
            "            semantics weakened merely to pass.",
            "  REWORK  — a concrete, bounded defect must be fixed before merge.",
            "  CONSULT — an architectural/semantic question needs human resolution before merge.",
            "",
        ]
        if contract.review_policy:
            lines.append(contract.review_policy)
            lines.append("")
        lines.extend(
            [
                "Review scope: judge using ONLY the work-package brief and the diff included",
                "below. Do not read other files in the repository — everything you need to",
                "reach a verdict is inline.",
                "",
            ]
        )
        if brief:
            lines.append("## Brief")
            lines.append("```markdown")
            lines.append(brief)
            lines.append("```")
            lines.append("")
        lines.append("## Diff under review")
        lines.append("```diff")
        lines.append(diff)
        lines.append("```")
        return os.linesep.join(lines)

    @staticmethod
    def _parse_verdict(raw: str) -> dict:
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            m = re.search(r"\{.*\}", raw, re.DOTALL)
            if not m:
                raise ValueError(
                    f"Could not parse structured verdict from codex output: {raw!r}"
                ) from None
            try:
                obj = json.loads(m.group(0))
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Could not parse structured verdict from codex output: {raw!r}"
                ) from exc

        if not isinstance(obj, dict) or obj.get("decision") not in (
            "ACCEPT",
            "REWORK",
            "CONSULT",
        ):
            raise ValueError(f"Invalid verdict structure: {obj!r}")
        return obj
