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
repositories running older interpreters, and declares **zero third-party
dependencies** (`dependencies = []`).

## Install (editable, independent of the root workspace)

```bash
uv pip install -e packages/agentic-loop
uv run python3 -c "import agentic_loop; print(agentic_loop.__version__)"
```

(Use `uv run python3`, not bare `python3`: the editable install lands in the uv
venv, which the system interpreter does not see.)

Note: this package is intentionally **not** a member of the root
`[tool.uv.workspace]` (the workspace requires Python >= 3.13, which would
conflict with this package's >= 3.9 portability declaration).

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
| `init` | Scaffold `.agentic/config.toml` + governance contracts (AGENTS.md, CLAUDE.md, docs/agentic/OPERATING_MODEL.md) + `docs/plans/` & `.agentic/locks/` skeleton. Refuses to overwrite existing managed files without `--force`. |
| `contract check` | Read-only drift report per contract: `IN_SYNC` / `TEMPLATE_OUTDATED` / `CONFIG_DRIFT` (exit 0 all in sync, 3 on any drift). |
| `contract diff [--apply]` | Show the re-render diff; `--apply` writes it back and re-stamps. |

Orchestration gates (forward verbatim to the wrapper — the main-repo
`scripts/agentic/<wrapper>.sh` when present, else the wheel-bundled copy; argv,
streams and exit codes pass through unchanged):

| Subcommand | Forwards to |
|------------|-------------|
| `gate` | `codex_merge_gate.sh` — independent merge-gate second sign |
| `redispatch` | `redispatch.sh` — rework re-dispatch reflow |
| `preflight` | `preflight.sh` — status validation + branch/WP-lock gate |
| `finalize` | `finalize_merge.sh` — stamp `state=MERGED` + `merged_commit` |
| `dispatch-lint` | `dispatch_lint.sh` — dispatch-time status lint |
| `quality-gate` | `quality-gate.sh` — path-matched project test rules |
| `lock` | `lock.sh` — WP / merge concurrency locks |
| `health` | `kimi-health.sh` — background-executor progress probe |

The wrappers hold the real orchestration glue; keeping them as bash is a frozen
design decision (the CLI forwards, it does not reimplement them).
