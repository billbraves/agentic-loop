# Changelog

All notable changes to `agentic-loop` are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and the project adheres to
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.6.0] — 2026-08-16

The `[autonomy]` section stops being inert config and becomes a machine-checkable
gate. A new autonomy policy engine maps each orchestration action to `AUTO`/`STOP`
(fail-closed: `always_stop` actions always stop, `ultra` mode auto-approves only
`ultra_auto` actions, everything else stops), and the terminal/dispatch gates now
enforce it — while staying opt-in so existing projects keep their current behavior
until they adopt the section.

### Added

- **Autonomy policy engine + `agentic autonomy <action>`.** A pure `decide()`
  predicate over the `[autonomy]` config (`default_mode` / `ultra_auto` /
  `always_stop`), exposed as a CLI that prints `AUTONOMY_AUTO` (exit 0),
  `AUTONOMY_STOP` (exit 3), or `AUTONOMY_NOT_CONFIGURED` (exit 0) when a project
  has no `[autonomy]` section. Fail-closed: unknown actions and non-approved
  actions resolve to STOP.

### Changed

- **`agentic preflight`, `agentic gate`, and `agentic finalize` enforce autonomy.**
  `dispatch_developer`, `merge_gate`, and `finalize_merge` are checked against the
  policy before acquiring the WP lock / spending Codex quota / stamping MERGED,
  with an explicit human-approval escape hatch (`AGENTIC_AUTONOMY_APPROVE=1`).
  Opt-in: a project without `[autonomy]` is not gated (backward compatible).
- **AGENTS.md template documents the autonomy gate** (§4.1) and the contract
  template version is bumped to 4.

### Distribution

- Version bumped to **`0.6.0`** (minor: backward-compatible feature — the gate is
  opt-in). No new dependencies; wrapper set unchanged (ten wrappers).

## [0.5.0] — 2026-08-16

Adoption hardening: the rendered contracts now teach the portable `agentic` CLI
(instead of in-repo `scripts/agentic/*.sh` paths that don't exist in an external
project), the framework ships the previously-missing per-WP brief/status
templates so a new work package can actually start, and a legacy-status
converter bridges projects coming from the older `.wp/*.status.json` workflow.
The contract render engine now reads the unified `[[gate]]` array (matching
`quality-gate.sh`) instead of the superseded `[quality_gate]` section.

### Added

- **Per-WP reference templates (STATUS.json / WORK_PACKAGE.md).** `agentic init`
  now scaffolds `docs/agentic/templates/STATUS.json` (a valid v2 DRAFT skeleton)
  and `WORK_PACKAGE.md` (a brief skeleton), so an adopting project has a
  starting point for a new work package. Scaffolded once, never overwritten.
- **`agentic migrate-status` subcommand.** Converts a legacy
  `.wp/WP-<id>.status.json` (states `DISPATCHED/IMPLEMENTING/DONE/BLOCKED`) to a
  valid `agentic-wp-status/v2` status, preserving every mechanical field and
  warning on dropped fields and merge-state fields that must be filled by a
  human (no fabricated evidence).

### Changed

- **Rendered contracts teach the CLI, not `scripts/agentic/`.** AGENTS.md /
  CLAUDE.md templates now reference `agentic preflight|gate|finalize|lock|health|…`
  (config-driven `$merge_gate_cmd` / `$health_check_cmd` default to
  `agentic gate` / `agentic health`). Contract template version bumped to 2.
- **Contract render engine reads the unified `[[gate]]` array.** §9 quality-gate
  commands now come from `[[gate]]` (kind="command", stage="pre_review") with a
  legacy `[quality_gate]` fallback, so the rendered contract matches what
  `quality-gate.sh` actually runs.

### Distribution

- Version bumped to **`0.5.0`** (minor: backward-compatible features + template
  wording fix). No new dependencies; wrapper set unchanged.

## [0.4.0] — 2026-08-16

Outcome of the `agentic-deepseek-single-key-v1` iteration (4 work packages),
which lets all coding-agent roles be driven from a **single DeepSeek key** —
one provider injected into claude / kimi / codex, with an `agentic bootstrap`
zero-config on-ramp and honest same-source-weak independence rating. All changes
are backward compatible: with no `[providers]` section the config reader, every
adapter, and the independence engine fall back verbatim to prior behavior (zero
regression), and v2 double-sign status files are untouched.

### Added

- **Provider binding schema + roles-table reader (P1 / WP-01).** A generic
  `[providers.<name>]` config section (canonical `identity_model`, per-adapter
  `[selectors]`, two base URLs, `api_key_env`) resolves each role into an
  immutable `ProviderBinding`. `[roles]` gains a table form (with `provider`)
  while still accepting the legacy string / primary-fallback-array forms. A
  missing `[providers]` section falls back verbatim to current behavior.
- **Three-adapter DeepSeek injection + real-injection probe (P2 / WP-02).**
  claude (env), codex (`-c` inline) and kimi (0600 temp config) each accept an
  optional `ProviderBinding`, report identity by the canonical `identity_model`
  (never a per-adapter selector, feeding INV-1), and gain a `probe_injection()`
  that sends a sentinel request so only a truly-effective injection passes (a
  `which` hit or `rc=0` does not). A unified secret-redaction layer keeps the key
  out of argv and command output. `binding=None` falls back verbatim.
- **`agentic bootstrap` subcommand (P2 / WP-03).** Detects whether
  claude / kimi / codex are installed, installs missing ones from pinned sources
  (confirmation or `--yes`), verifies `DEEPSEEK_API_KEY` is present (never
  fills or persists it), runs the real-injection probe per CLI, and fails closed
  with `CLI_INSTALLED_BUT_INCOMPATIBLE` (no auto-upgrade). `--dry-run` prints the
  install/probe plan without installing or spending DeepSeek quota. Three
  signatures, no Qoder.

### Changed

- **Same-source weak independence made explicit (P3 / WP-04).** When all three
  signatures resolve to the same DeepSeek `identity_model`, the INV-1 dual-sign
  engine rates independence `weak` natively (engine unchanged). Ships an explicit
  `min_independence="weak"` single-deepseek profile example (with a cost note),
  plus tests proving the engine rates `weak` at same-source and that the reasons
  trail records it — no faked `strong`, no downgrade branch in `independence.py`.

### Distribution

- Version bumped to **`0.4.0`** (minor: backward-compatible feature additions —
  provider binding, DeepSeek injection, `agentic bootstrap`, weak-independence
  profile). No new dependencies; wrapper set unchanged (ten wrappers).

## [0.3.0] — 2026-08-15

Outcome of the `agentic-gate-unification-v1` iteration (7 work packages), which
unified the gate declaration system, added an independent Qoder security gate as
a third merge signature, and landed the ask/ultra autonomy model. All changes
are backward compatible: v2 double-sign status files and existing
`[quality_gate]` behavior are preserved, and the new security signature applies
only to `agentic-wp-status/v3`.

### Added

- **Unified `[[gate]]` declaration system (P1 / WP-01).** A single `[[gate]]`
  array (`kind` ∈ {command, codex, qoder_security, qoder_judge}, `stage` ∈
  {pre_review, merge}, `apply` ∈ {first_match, overlay}) replaces the special
  cased `[quality_gate]` section, which is migrated to one `kind=command`
  `stage=pre_review` gate with its rule order preserved. Also adds the
  `[autonomy]` section (default mode + ultra-auto / always-stop / soft-limit
  categories).
- **Gate runner engine with overlay + generic result model (P1 / WP-02).** A new
  `agentic_loop.runner.gate_runner` schedules and executes the unified gates,
  deduplicates shared commands at the execution level (not just the planner),
  and enforces a canonical merge-stage order (codex signoff → qoder security →
  qoder judge) so a blocking codex failure never burns Qoder credits.
- **Qoder security gate engine (P1 / WP-03).** `agentic_loop.gate.qoder_security`
  drives `qodercli … security scan` over the reviewed tip's changed paths,
  reading a SARIF 2.1.0 report, taking the highest severity across all signals,
  and failing closed on any high/medium finding, unknown value, external
  reference, or version/cleanliness mismatch. The former single-file `gate.py`
  becomes a `gate/` package.
- **`agentic init` pre-push gate hook (P4 / WP-07).** `agentic init` scaffolds an
  opt-in `.githooks/pre-push` (delegating to the unified runner) plus an
  `install.sh` that sets `core.hooksPath`; idempotent, never runs `git config`
  itself, and honors `--no-verify` as an escape hatch.

### Changed

- **`validate_wp_status` generalized for v3 (P3 / WP-04).** Recognizes the
  top-level `qoder_security` block (required only for v3; v2 stays valid without
  it), validates its decision / error-kind / findings / dataflow structure, and
  gates the merge state on a Qoder PASS or a complete approved override
  (same four-field shape as `consult.override`).
- **`finalize_merge.sh` three-signature gate (P3 / WP-05).** Finalization now
  requires reviewer + consult + Qoder signatures for v3 (PASS or a complete
  approved override), read-only and with `schema_version` as the sole dividing
  line; the v2 double-sign path is unchanged.

### Distribution

- Version bumped to **`0.3.0`** (minor: backward-compatible feature additions —
  Qoder security gate, gate runner, init hook).
- **Two more bundled wrappers.** `gate-runner.sh` (WP-02) and
  `qoder_security_gate.sh` (WP-03) now ship inside the wheel under
  `agentic_loop/wrappers/` alongside the existing eight, so `pip install
  agentic-loop` runs the unified gate runner and Qoder security gate without a
  `scripts/agentic/` in the consuming project (ten wrappers total).

## [0.2.0] — 2026-08-14

Outcome of the `agentic-loop-hardening-v1` iteration (7 work packages), which
fixed three classes of structural pain: external-adoption blockers, merge-gate
false positives that made manual overrides routine, and dual-sign independence
resting on implicit bootstrap crutches. All changes are backward compatible.

### Added

- **Structured reviewer attestation (P3 / WP-07).** The merge gate now reads a
  structured `review.attestation` (reviewer role, fresh-session, adversarial
  prompt) and fails closed when it is missing, so independence is asserted by
  explicit fields instead of implicit bootstrap state.
- **Legal `consult.override` terminal state (P2 / WP-06).** `validate_wp_status`
  recognizes a complete manual override (`approved` + `approver` +
  `justification` + `reviewed_at`) as a legitimate path to MERGED when
  `consult.decision=REWORK`; incomplete overrides still fail closed.

### Changed

- **Merge-gate diff scoped by `scope` (P2 / WP-04).** The reviewed diff is
  filtered by `scope.allowed_paths` / `forbidden_paths`, eliminating three
  classes of false positive at once (scaffold overreach, self-reference, stale
  base carry-in).
- **Diff-start `merge-base` fallback (P2 / WP-05).** The diff-start layer falls
  back to `git merge-base --all` over the recorded `base_commit`, failing closed
  on an ambiguous (criss-cross) fork point instead of guessing.
- **De-baofu'd built-in defaults (P1 / WP-01).** `resolve_paths` ships neutral
  `DEFAULT_SAFETY` / `QUALITY_GATE` / `REVIEW_POLICY` / `ADAPTERS`; project
  behavior is layered in via `.agentic/config.toml`.
- **Developer fallback chain repaired (P1 / WP-03).** The adapter registry
  assembles the `claude` fallback, and `redispatch` resolves its wrapper via a
  shared `resolve_wrapper()` instead of a hard-coded `lock.sh` path.

### Distribution

- Version bumped to **`0.2.0`**. On Python **3.11+** still zero third-party
  dependencies (stdlib `tomllib`); on **3.9 / 3.10** pulls a single conditional
  dependency `tomli` (P1 / WP-02), fixing the earlier zero-dependency
  contradiction on older interpreters.

### Added — carried from 0.1.0 post-release

- **Bundled wrappers (P7 / WP-23).** The eight `scripts/agentic/*.sh`
  orchestration wrappers now ship inside the wheel under
  `agentic_loop/wrappers/`, so `pip install agentic-loop` runs every forwarding
  gate (`gate`, `preflight`, `finalize`, `dispatch-lint`, `redispatch`, `lock`,
  `health`, `quality-gate`) with **no** `scripts/agentic/` in the consuming
  project.
- **Dual-copy wrapper resolution (P7 / WP-23).** `agentic <gate>` resolves the
  wrapper main-repo-first (`scripts/agentic/<wrapper>.sh` when inside the
  framework's own tree — dogfood, live edits without reinstall), else the
  wheel-bundled copy via `importlib.resources` (Python 3.9-safe API). A clean
  one-line error is emitted only when neither copy is present.
- **`quality-gate.sh` de-baofu'd (P7 / WP-23).** Its path→test rules are read
  from the project's `.agentic/config.toml` `[quality_gate]` section instead of
  hard-coded baofu paths; baofu's rules moved into that config. The config-driven
  expansion reproduces the previous hard-coded pytest targets exactly.

## [0.1.0] — 2026-08-12

First releasable version. Early / pre-1.0: the framework is dogfooded in the
baofu monorepo and the API is not yet frozen.

This release is the outcome of the `agentic-portability-v1` iteration (P0–P6),
which turned the in-repo orchestration scripts into a portable, adoptable
package.

### Added

- **Engine (P0–P4).** Portable orchestration logic with zero third-party
  dependencies and Python >= 3.9 support: path resolver, config reader,
  WP-status validator, independence rating, merge-gate, dispatch/redispatch,
  and executor-health probe — with a P0 regression suite locked as a hard gate.
- **Package (P5).** `agentic-loop` package skeleton, engine modules migrated
  into `agentic_loop`, and the `agentic` console-script CLI forwarding each
  orchestration gate verbatim to `scripts/agentic/<wrapper>.sh`.
- **Governance-contract templates + render engine (P6 / WP-20).** Stdlib-only
  rendering of AGENTS.md / CLAUDE.md / OPERATING_MODEL.md from a project config,
  with a version + config-checksum stamp header.
- **Project commands (P6 / WP-21).** `agentic init` scaffolds
  `.agentic/config.toml`, the three governance contracts, and the
  `docs/plans/` + `.agentic/locks/` skeleton — non-destructive by default.
  `agentic contract check` reports drift read-only (IN_SYNC / TEMPLATE_OUTDATED
  / CONFIG_DRIFT); `agentic contract diff [--apply]` previews and applies the
  re-render.
- **Release docs (P6 / WP-22).** README rewritten to the real command surface,
  a `MIGRATION.md` adoption guide, and this changelog.

### Distribution

- Package name **`agentic-loop`**, version **`0.1.0`**, `dependencies = []`.
- **MIT license.** This release ships under the MIT license, with the
  `license`/`authors`/`readme` metadata completed in `pyproject.toml` and a
  standard `LICENSE` file added.
- Not published to PyPI. Adopt via pip-from-git or by vendoring the package
  directory (see `MIGRATION.md`).
