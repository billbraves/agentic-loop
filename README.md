# agentic-loop

Portable agentic-orchestration framework, dogfooded in the baofu monorepo.

`agentic-loop` packages the orchestration engine that drives a
dispatch → implement → review → merge-gate workflow across coding agents
(Claude / Codex / Kimi / …). It ships:

- a **pure engine** (drift/independence/status/render logic) — no business code,
- the **`agentic` CLI** that forwards to the orchestration gates and adds two
  project-facing commands (`init`, `contract`),
- **governance-contract templates** rendered per project from a small config.

It is compatible with Python **>= 3.9** so it can be vendored into external
repositories running older interpreters. On Python **3.11+** it declares **zero
third-party dependencies** (stdlib `tomllib`); on **3.9 / 3.10** it pulls a
single conditional dependency, `tomli`.

## How it differs from coding SKILLs / agent harnesses

These sit at different layers and compose rather than compete:

| Tool | Layer | It answers |
|------|-------|------------|
| Claude Code **SKILL** | method | how *one* agent does a task correctly |
| DeepSeek **Harness** | runtime | how *one* agent executes / fans out sub-tasks |
| **agentic-loop** | governance | how *many* independent agents stay disciplined |

One line: SKILLs and harnesses make a single agent **more capable**;
`agentic-loop` makes a team of agents **more trustworthy** — the former solve
**capability**, the latter solves **discipline** (machine-enforced scope,
multi-sign review, merge/finalize traceability, per-action autonomy).

## Install (latest release)

Every release lands on `main` and is tagged, so `main` always points at the
newest release. Install without a ref to track it:

```bash
uv pip install "git+https://github.com/billbraves/agentic-loop.git"
python3 -c "import agentic_loop; print(agentic_loop.__version__)"
```

Re-run with `--force-reinstall` (or `--upgrade` under plain pip) to move up to a
later release. To pin an exact version for reproducible builds, append a tag
(`@v0.7.0`) or commit — see [`MIGRATION.md`](MIGRATION.md) §1.

## Adopting it in another project

```bash
# 1. vendor / install the package (see MIGRATION.md for pip-from-git / vendored)
# 2. scaffold config + governance contracts + skeleton
agentic init --dir /path/to/project
# 3. edit /path/to/project/.agentic/config.toml (roles, quality gates, safety)
# 4. re-render contracts to match the edited config
agentic contract diff --apply --dir /path/to/project
# 5. run the gates
agentic preflight docs/plans/<iteration>/WP-XX.status.json
```

The full adoption walkthrough — config sections, drift governance, and the
in-repo-scripts → installed-CLI migration — lives in
[`MIGRATION.md`](MIGRATION.md).

Note: every subcommand works from a bare `pip install` — the wheel **bundles**
the `scripts/agentic/*.sh` wrappers, so an external project needs **no**
`scripts/agentic/` directory of its own. When a main-repo copy *is* present (the
framework dogfooding itself) the CLI prefers it, so live wrapper edits take
effect without a reinstall (see the [`MIGRATION.md`](MIGRATION.md) §5 note).

## Command reference

`agentic <subcommand> [args...]` — run `agentic --help` for the live listing.

Project commands (Python, package-internal):

| Subcommand | What it does |
|------------|--------------|
| `init` | Scaffold `.agentic/config.toml` + governance contracts (AGENTS.md, CLAUDE.md, docs/agentic/OPERATING_MODEL.md) + per-WP templates (docs/agentic/templates/{STATUS.json,WORK_PACKAGE.md}) + `docs/plans/` & `.agentic/locks/` skeleton. Refuses to overwrite existing managed files without `--force`. |
| `contract check` | Read-only drift report per contract: `IN_SYNC` / `TEMPLATE_OUTDATED` / `CONFIG_DRIFT` (exit 0 all in sync, 3 on any drift). |
| `contract diff [--apply]` | Show the re-render diff; `--apply` writes it back and re-stamps. |
| `bootstrap` | Detect/install claude+kimi+codex, verify `DEEPSEEK_API_KEY`, and run a real-injection probe per CLI (fails closed on an installed-but-incompatible CLI). `--dry-run` prints the plan without installing or spending DeepSeek quota; `--yes` skips the install confirmation. |
| `migrate-status` | Convert a legacy `.wp/WP-<id>.status.json` to `agentic-wp-status/v2` (`--iteration`, optional `--merged-commit`). |
| `autonomy` | Check an orchestration action against the `[autonomy]` policy — prints `AUTONOMY_AUTO` / `AUTONOMY_STOP` / `AUTONOMY_NOT_CONFIGURED`; `autonomy signal <signal>` classifies a soft-limit signal. |

Orchestration gates (forward verbatim to the wrapper — the main-repo
`scripts/agentic/<wrapper>.sh` when present, else the wheel-bundled copy; argv,
streams and exit codes pass through unchanged):

| Subcommand | Forwards to |
|------------|-------------|
| `gate` | `codex_merge_gate.sh` — independent merge-gate second sign |
| `redispatch` | `redispatch.sh` — rework re-dispatch reflow |
| `preflight` | `preflight.sh` — status validation + branch/WP-lock gate |
| `finalize` | `finalize_merge.sh` — three-signature gate (reviewer + consult + Qoder for v3; v2 double-sign) then stamp `state=MERGED` + `merged_commit` |
| `merge` | `merge.sh` — local no-ff merge of an APPROVED_FOR_MERGE WP (autonomy-gated) |
| `dispatch-lint` | `dispatch_lint.sh` — dispatch-time status lint |
| `quality-gate` | `quality-gate.sh` — path-matched project test rules |
| `lock` | `lock.sh` — WP / merge concurrency locks |
| `health` | `kimi-health.sh` — background-executor progress probe |

The wrappers hold the real orchestration glue; keeping them as bash is a frozen
design decision (the CLI forwards, it does not reimplement them).
