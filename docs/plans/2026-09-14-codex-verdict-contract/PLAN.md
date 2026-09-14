# Codex verdict contract hardening

> Iteration: `2026-09-14-codex-verdict-contract` | Orchestrator: Kiro | Frozen: 2026-09-14

## Goal

Keep the native merge gate fail-closed while recovering from one observed provider incompatibility: Codex exits 0 but either writes no verdict or emits a semantically useful free-text verdict despite `--output-schema`.

## Frozen product decisions

1. Free text is never parsed or keyword-mapped by adapter code into ACCEPT/REWORK/CONSULT.
2. A valid first structured result returns immediately with exactly one provider invocation.
3. Empty first output permits one and only one full retry of the original review prompt, with an explicit JSON-only suffix and the same provider, read-only sandbox, schema and reasoning effort.
4. Non-empty but invalid structured output permits one and only one structure-only normalization call. It receives the redacted prior output as quoted untrusted data plus the schema; it must preserve decision, rationale and findings and must not re-review the diff.
5. A non-zero subprocess exit is not retried. Any second non-zero, empty, malformed or invalid decision remains a hard failure.
6. Each invocation uses a distinct output file; stale first-attempt content cannot satisfy the second attempt.
7. Secrets remain redacted from exceptions and from any normalization prompt.

## Work packages

| WP | Scope | Lane |
|---|---|---|
| WP-16 | Codex adapter bounded structured-verdict recovery and deterministic tests | lane-codex-verdict |

## Completion

WP-16 must pass targeted tests, the repository suite modulo an independently reproduced pre-existing baseline, independent review, and the native gate. Installation and consumer WP-30L gate rerun happen only after this plan is merged locally and the installed tool is updated from the reviewed source.
