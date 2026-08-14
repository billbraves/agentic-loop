# Changelog

All notable changes to `agentic-loop` are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and the project adheres to
[Semantic Versioning](https://semver.org/).

## [Unreleased]

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
