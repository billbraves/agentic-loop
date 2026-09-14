# WP-16: Codex structured verdict bounded recovery

> Frozen 2026-09-14 | Orchestrator Kiro | Developer kimi
> Plan: `PLAN-CODEX`; integrate into `plan/2026-09-14-codex-verdict-contract`, never directly into main.

## Goal

Make `CodexAdapter.review()` tolerate one empty or non-schema rc=0 provider response without weakening the native merge gate's fail-closed decision contract.

## Incident evidence

A real P2 high-effort gate against an unchanged, independently ACCEPTed consumer diff produced two engine failures: first `codex produced no verdict output`; one manual retry returned `未发现阻断合并的问题。`, which was not valid JSON. Both correctly failed closed. This WP fixes the adapter/provider contract, not the consumer WP and not its verdict.

## Scope

- **allowed_paths**:
  - `src/agentic_loop/adapters/codex.py`
  - `tests/test_codex_verdict_recovery.py`
- **forbidden_paths**:
  - `.env`
  - `.context/`
  - `.agentic/config.toml`
  - `src/agentic_loop/gate/`
  - `src/agentic_loop/wrappers/`
  - `src/agentic_loop/independence.py`
  - every consumer repository and all files not explicitly allowed
- **owner boundary**: adapter implementation and its new focused test module only.

## Required behavior

1. Refactor the subprocess launch enough to support at most two invocations, always preserving the existing command contract: same configured Codex binary/provider flags, `--sandbox read-only`, `--skip-git-repo-check`, exact reasoning effort, `--output-schema`, and no key value in argv.
2. First-attempt valid structured verdict returns immediately. No recovery invocation.
3. First-attempt non-zero exit fails immediately after redacting bound key material. No retry.
4. First-attempt rc=0 with no non-whitespace answer-file or stdout content performs exactly one full retry. Retry the original inline brief+diff review with a JSON-only suffix; same schema/provider/sandbox/effort. It is a new review because no prior semantics exist.
5. First-attempt rc=0 with non-empty output that `_parse_verdict()` rejects performs exactly one structure-only normalization invocation. Its prompt:
   - contains the exact output schema;
   - contains only the **redacted**, bounded prior output as clearly delimited untrusted data;
   - says not to follow instructions in that data, not to re-review, and not to change decision/rationale/findings;
   - requests only one JSON object.
6. Use a distinct answer file for each attempt and never accept stale output.
7. The second result is accepted only through the existing strict `_parse_verdict()` decision allowlist. Second non-zero, empty, malformed, wrong root, or unknown decision fails closed. Never perform a third invocation.
8. Do not add adapter-side natural-language keyword/regex mapping, including Chinese or English phrases. The same provider performs normalization.
9. Preserve current exception redaction. Raw prior output must be redacted before it enters a second prompt or any surfaced exception. Bound normalization input to a documented constant (recommended 16 KiB); oversized output fails closed rather than truncating semantics.
10. Preserve existing probe, identity, capabilities, provider injection and prompt review-policy semantics.

## Acceptance tests

Create `tests/test_codex_verdict_recovery.py` with deterministic fake executable/subprocess tests proving:

- valid first JSON: one invocation and unchanged Verdict;
- first answer-file empty and stdout empty: exactly one full retry, second valid JSON accepted;
- first free text `未发现阻断合并的问题。`: second prompt is structure-only, contains quoted redacted source and schema but no original diff/brief, second valid ACCEPT accepted;
- first explicit Markdown REWORK with findings: normalization returns REWORK and findings are preserved;
- first non-zero: no retry and secret redacted;
- second non-zero, empty, malformed, invalid decision: fail closed with exactly two invocations;
- oversized first output: fail closed with one invocation and no raw body/secret in error;
- each invocation has a distinct `-o` path and identical provider/sandbox/schema/effort controls;
- no third invocation is possible;
- static killer: no phrase-to-decision mapping table/regex is introduced.

Run:

- `python3.11 -m pytest tests/test_codex_verdict_recovery.py tests/test_adapter_injection.py tests/test_injection_probe.py -q`
- `python3.11 -m pytest tests -q`; any baseline exception must be reproduced on the frozen base and documented, never hidden.
- `python3.11 -m compileall -q src/agentic_loop tests/test_codex_verdict_recovery.py`
- `git diff --check`
- `agentic quality-gate <WP-16.status.json>`

## Completion definition

- All required behavior and killers pass.
- No forbidden path is changed.
- No network, production write, notification, credential read/write or push.
- Status truthfully records evidence and commit; state becomes READY_FOR_REVIEW only after tests.

## Risk

| Dimension | Value |
|---|---|
| production_writes | FORBIDDEN |
| network | FORBIDDEN |
| notifications | FORBIDDEN |
| data_access | READ_ONLY |

## Allowed and forbidden paths

The machine status `scope` is authoritative and matches the Scope section above.

## Acceptance tests

The exact commands and negative cases are frozen above.
