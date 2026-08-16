# 环境问题记录：wrapper 硬编码裸 `python3`（外部安装场景 ModuleNotFoundError）

> 状态：已修复（v0.8.4） · 修复方式见文末「修复落地」
> 发现：baofu 项目迭代中实测命中，用「uv-tool bin 提到 PATH 前」绕过

## 现象

在 baofu-monorepo（已归档 `packages/agentic-loop`，走外部 `agentic` CLI）里跑编排门时：

```
ModuleNotFoundError: No module named 'agentic_loop'
```

## 根因

`agentic` CLI 是 uv-tool 装的（`~/.local/bin/agentic` shim），shim 内部用 **uv-tool 的
venv python** 跑 `cli.py`，所以 `agentic` 命令本身能起来。但 `cli.py` 把门转发给
bash wrapper 时（`cli.py` 第 194/201 行：`["bash", wrapper, ...]`），wrapper 里是
**裸 `python3`**（如 `python3 -m agentic_loop.resolve_paths`、`python3 -m
agentic_loop.validate_wp_status`、`python3 - <<'PY'`），这个 `python3` 解析到
**系统解释器**（PATH 里第一个 python3），而系统解释器**没装 agentic_loop**。

wrapper 的 preamble 本想在「框架仓库内 dogfood」场景用 `PYTHONPATH` 指向
`<main_repo>/packages/agentic-loop/src`，但 baofu 归档后该路径已不存在，PYTHONPATH
也失效。于是裸 `python3` 彻底找不到 `agentic_loop`。

## 绕过（当前）

把 uv-tool 的 bin 目录提到 PATH 最前，让 wrapper 里的 `python3` 也解析到 uv 的
python（它装了 agentic_loop）：

```bash
export PATH="$HOME/.local/bin:$PATH"
```

## 修复方向（后续迭代）

让 wrapper 用「agentic 自己的解释器」而非裸 `python3`：

1. `cli.py` 转发 wrapper 前，注入当前解释器：
   ```python
   env = dict(os.environ)
   env["AGENTIC_PYTHON"] = sys.executable
   # bash wrapper 进程带上该 env
   ```
2. wrapper 里把裸 `python3` 统一换成 `"${AGENTIC_PYTHON:-python3}"`。

这样无论 `agentic` 是从 uv-tool venv、系统 pip 还是源码跑，wrapper 都用同一个解释器，
彻底消除「裸 python3 命中系统解释器」的问题。

## 影响面

所有 `scripts/agentic/wrappers/*.sh`（约 11 个）里的裸 `python3` 调用；纯函数式
heredoc（`python3 - <<'PY'`）不受影响（不 import agentic_loop），但为一致性可一并换。

## 修复落地（v0.8.4）

- `cli.py`：转发 wrapper 前构造局部 env `wrapper_env["AGENTIC_PYTHON"]=sys.executable`，
  `subprocess.run(..., env=wrapper_env)` / `_exec_or_run(cmd, wrapper_env)` ——
  用局部 env 而非 `os.environ.setdefault`，避免泄漏污染父进程（曾导致测试串扰）。
- 11 个 wrapper：裸 `python3 -m agentic_loop...` 统一换成
  `"${AGENTIC_PYTHON:-python3}" -m agentic_loop...`。
