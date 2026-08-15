# Changelog

All notable changes to `agentic-loop` are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and the project adheres to
[Semantic Versioning](https://semver.org/).

## [Unreleased]

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
