# Adopting `agentic-loop` in your project

This guide walks an external project from zero to a working
dispatch → implement → review → merge-gate loop, and shows how this repo itself
migrated from calling `scripts/agentic/*.sh` directly to using the installed
`agentic` CLI.

## 1. Install

`agentic-loop` is **not published to PyPI** (by design — see the project's
distribution preference). Adopt it via pip-from-git.

### 1.1 Latest release (default)

Every release lands on `main` and is tagged, so **`main` always points at the
latest release**. To track it, install without a ref — a reinstall picks up
whatever the newest release is:

```bash
uv pip install "git+https://github.com/billbraves/agentic-loop.git"
```

Re-run the same command (add `--force-reinstall`, or `--upgrade` under plain
pip) to move up to a newer release later. The package lives at the **root** of
the standalone repository, so no `#subdirectory=` fragment is needed.

### 1.2 Pin an exact version (reproducible)

For reproducible builds — CI, production lockfiles, or when you want a reinstall
to yield byte-identical code — pin an immutable ref instead. Replace `<TAG>` /
`<COMMIT_SHA>` with the version you are adopting (latest tag: **`v0.8.8`**):

```bash
# Pin a release tag:
uv pip install "git+https://github.com/billbraves/agentic-loop.git@v0.8.8"

# Pin an exact commit:
uv pip install "git+https://github.com/billbraves/agentic-loop.git@<COMMIT_SHA>"
```

### 1.3 Vendored

Alternatively, copy the package into your tree and install editable:

```bash
uv pip install -e path/to/vendored/agentic-loop
```

Record the adopted tag/commit in your own repo (e.g. a `VENDORED_COMMIT` file)
and copy the directory at that exact commit for reproducibility.

(If you instead install from the baofu monorepo, the package is under a
subdirectory — append `#subdirectory=packages/agentic-loop` to any ref above.)

The package targets Python **>= 3.9**. On Python **3.11+** it has **zero
third-party dependencies** (uses the stdlib `tomllib`); on Python **3.9 / 3.10**
it pulls a single conditional dependency, `tomli`, so config reading still works
via the fallback path.

## 2. Scaffold the project

```bash
agentic init --dir /path/to/project
```

This writes, under the target directory:

- `.agentic/config.toml` — the project adaptation layer (edit this; see §3).
- `AGENTS.md`, `CLAUDE.md`, `docs/agentic/OPERATING_MODEL.md` — governance
  contracts, rendered from the config and stamped with a
  `<!-- agentic-contract: template_version=… config_checksum=… -->` header.
- `docs/plans/` and `.agentic/locks/` skeleton directories.
- a `.gitignore` line for `.agentic/locks/` (runtime lock state is not tracked).

`init` is **non-destructive by default**: if any managed file already exists it
refuses (`INIT_REFUSED: <file>`) and writes nothing. Pass `--force` to overwrite,
or `--non-interactive` / `--config <seed.toml>` for headless/seeded runs.

## 3. Edit `.agentic/config.toml`

The config is the only thing you normally edit; the contracts are re-rendered
from it (§4). Its sections (schema defined in WP-06 — this guide references it,
it does not redefine it):

| Section | Purpose |
|---------|---------|
| `[project]` | `iterations_dir` (where WP plans live, default `docs/plans`); optional `default_output_language`. |
| `[roles]` | role → adapter name. A string is a single adapter; an array is primary/fallback candidates, e.g. `developer = ["kimi", "claude"]`. Roles: `orchestrator`, `developer`, `reviewer`, `consultant`. |
| `[quality_gate]` | zero or more `[[quality_gate.rule]]` entries, each a `match` path-prefix → `run` test-command list. Only your project's rules. |
| `[safety]` | `forbidden_paths` (never touched by dispatched work) and `production_paths` (writes gated). |
| `[review_policy]` | `min_independence` — the floor the merge-gate enforces between reviewer and consultant (`strong` / `weak` / `none`). |
| `[locks]` | `owner_source` (e.g. `env:AGENTIC_SESSION_ID`) and `ttl_minutes` for the concurrency locks. |
| `[adapters]` | `names` — the adapter identities the engine may resolve. |

## 4. Keep contracts in sync with config (drift governance)

The contracts are stamped with the template version + a checksum of the config
they were rendered from. After editing the config:

```bash
agentic contract check --dir /path/to/project     # read-only; rc 0 = all IN_SYNC, rc 3 = drift
```

`check` classifies each contract as `IN_SYNC`, `TEMPLATE_OUTDATED` (the package
shipped a newer template) or `CONFIG_DRIFT` (you edited the config). To resolve:

```bash
agentic contract diff --dir /path/to/project           # preview the re-render (print only)
agentic contract diff --apply --dir /path/to/project   # write it back + re-stamp
```

Re-running `check` after `--apply` returns all `IN_SYNC`. This turns "contracts
automatically follow config" into "drift is machine-detectable and applied on an
explicit, reviewable step".

## 5. Run the gates

> **No `scripts/agentic/` required.** `gate`, `redispatch`, `preflight`,
> `finalize`, `dispatch-lint`, `quality-gate`, `lock` and `health` do **not**
> reimplement their logic in the package — they forward to a bash wrapper. That
> wrapper is resolved dual-copy: the **main-repo** `scripts/agentic/<wrapper>.sh`
> when this runs inside the framework's own git tree (so live edits take effect
> without a reinstall), else the copy **bundled in the wheel** under
> `agentic_loop/wrappers/`. So an external project that merely `pip install`\ ed
> the package — with no git repo and no `scripts/agentic/` — still runs every
> gate. Only when *neither* copy is present does the CLI emit a clean
> `agentic: wrapper '<name>' not found …` (never a traceback).
>
> `quality-gate` is the one wrapper whose test-target rules are project-specific;
> it reads them from your `.agentic/config.toml` `[quality_gate]` section (§3),
> so the bundled copy carries no baofu-specific paths.

Once config and contracts are set, the orchestration gates are available through
`agentic`:

```bash
agentic preflight docs/plans/<iteration>/WP-XX.status.json   # validate status + branch/lock gate
agentic dispatch-lint docs/plans/<iteration>/WP-XX.status.json
agentic quality-gate docs/plans/<iteration>/WP-XX.status.json
agentic gate docs/plans/<iteration>/WP-XX.status.json        # merge-gate second sign
agentic finalize docs/plans/<iteration>/WP-XX.status.json    # stamp MERGED after an approved merge
agentic lock / agentic health / agentic redispatch           # locks / progress probe / rework reflow
```

## 6. Dogfood example: in-repo scripts → installed CLI

This repo grew the framework in-tree and still keeps the real glue as bash under
`scripts/agentic/`. The migration to the packaged CLI is a **rename of the entry
point**, not a rewrite — the CLI forwards to the same scripts:

| Before (in-repo direct) | After (installed CLI) |
|-------------------------|-----------------------|
| `bash scripts/agentic/preflight.sh <status>` | `agentic preflight <status>` |
| `bash scripts/agentic/codex_merge_gate.sh <status>` | `agentic gate <status>` |
| `bash scripts/agentic/finalize_merge.sh <status>` | `agentic finalize <status>` |
| `bash scripts/agentic/lock.sh …` | `agentic lock …` |
| (no equivalent — was manual) | `agentic init` / `agentic contract check\|diff` |

`agentic <gate> <args>` is byte-for-byte equivalent to invoking the wrapper
directly: argv, stdout, stderr and exit code all pass through. The migration is
therefore in the *entry point*, not the scripts. This repo keeps its
`scripts/agentic/*.sh` wrappers in-tree and the CLI prefers them (dogfood — see
§5); a project that merely installs the package uses the bundled copies and
needs no `scripts/` of its own. The two project commands (`init`, `contract`)
are pure-Python and have no in-repo predecessor or wrapper dependency.

External adoption is fully self-contained: `init`, `contract`, and every
forwarding gate all run from a bare `pip install`, because the wheel bundles the
wrappers (`agentic_loop/wrappers/*.sh`). Carrying `scripts/agentic/` at the
project root is optional — it only matters for dogfooding the framework's own
wrappers with no reinstall.
