# WP-22: 消除 finalize 判定与读取之间的 symlink TOCTOU 窗口（A34）

> 冻结日期 2026-09-15 | 编排者 claude（claude-code） | 执行者 kimi。
> 所属 Plan：2026-09-13-parallel-throughput（集成到 `plan/2026-09-13-parallel-throughput`，不直接合入 main）。
> 冻结后执行期间不得修改；需修订走 re-freeze（新建 rev2 并重派）。

## 目标（一句话）

`finalize_merge.sh` 先用 `path_is_in_worktree` 判定 status 路径，随后 `-f`、两处
validator、读旧 JSON 各自**重新按路径解析**同一个文件；把这段「判定一次、按路径读四次」
改成「判定与读取共用同一个已打开的文件」，关掉 symlink 重定向的时间窗。

## 前置事实（编排者已实测，执行者不必重做，但**不得与之矛盾**）

| 面 | 结论 | 依据 |
|----|------|------|
| **写回** | **已免疫，不要改** | `mktemp "$status_file.XXXXXX"` 取的是**路径字符串的 dirname**（不解析 symlink），临时文件建在主区；`mv` 是 `rename(2)`，**替换 symlink 本身**而非跟随它。实测写回落在主区路径，worktree 副本未被触碰，且与主区/worktree 是否同一文件系统无关 |
| **读取** | **可被换掉** | 同一路径替换前后读到不同内容（`MAIN_COPY_REWORK` → `WORKTREE_COPY_FORGED_ACCEPT`）；`:56` `-f`、`:61`/`:64` 两处 validator、`:209` 读旧 JSON 四处都跟随替换后的 symlink |
| **判据本身** | 正确 | 对替换**后**的路径答 `True`（会拒收）。问题不在判据，在「判定与读取之间存在间隙」 |

→ 故本 WP **只收读面**，**不要动写回形态**（改它属于无谓返工，会被驳回）。

## 范围

- **allowed_paths**（白名单）：
  - `src/agentic_loop/wrappers/finalize_merge.sh`（判定与读取的时序）
  - `src/agentic_loop/validate_wp_status.py`（**仅**为支持按已打开 fd/描述符读取而必要的最小改动；若你的修法不需要改它，就不要改）
  - `tests/test_finalize_merge_toctou.py`（新建）
- **forbidden_paths**（黑名单）：
  - `src/agentic_loop/gate/__init__.py`（判据正确，本轮零改动）
  - `src/agentic_loop/wrappers/preflight.sh`
  - `src/agentic_loop/independence.py`
  - `src/agentic_loop/adapters/`、`src/agentic_loop/redispatch.py`
  - `docs/`（brief 与 status 由编排者维护）
  - `.agentic/config.toml`、`.agentic/locks/`、`.env`、`.context/`
- **owner 边界**：对齐 CODEOWNERS，不跨 owner 写入。

> ⚠️ `validate_wp_status.py` 是 A14/A15/A18 的面。本 WP 白名单里**只为 fd 读取支持**，
> 不得改 `--field` 的返回语义、不得改校验规则、不得碰 A14/A15/A18 相关逻辑。

## 交付物清单

- [ ] `finalize_merge.sh`：判定与后续读取**共用同一个已打开的文件**。
      建议形态：判定阶段用 `os.open(path, O_RDONLY | O_NOFOLLOW)` 拿到 fd，
      在**同一个 Python 进程内**完成「判定 + 读取决策所需字段」，把结果一次性交回 shell；
      而不是让 shell 拿着路径字符串反复调 Python。
      若采用别的等效修法，须在报告里说明为何同样关掉了窗口。
- [ ] 保留现有的全部拒收语义：worktree 内路径仍拒收、不可解析路径仍 fail-closed、
      status 不存在仍 `FINALIZE_FAIL`。**不得因重构而放宽任何一条。**
- [ ] 写回段（`:204-229` 的 mktemp/trap/mv）**保持不变**（已免疫，见前置事实）。
- [ ] `tests/test_finalize_merge_toctou.py`：
      - 判定通过后把主区 status 换成指向 worktree 副本的 symlink，
        断言 finalize **不会**采用 worktree 副本的字段做决策（用两份内容可区分的 status）
      - 主区真文件的正常路径仍 `FINALIZE_OK`（不回归）
      - worktree 内路径仍被拒收
      - 不可解析路径仍 fail-closed 且不抛异常

## 完成定义（DoD）

- [ ] 交付物逐项就绪；A34 有一个失败→通过的测试
- [ ] **跨版本**：`tests/test_finalize_merge_toctou.py` 与
      `tests/test_finalize_merge_first_call.py` 在 **python3.11、3.13、3.14** 三个解释器全绿
      （缺 pytest 的用 `uv run --python <ver> --with pytest --no-project python -m pytest <file> -q`）
- [ ] `PYTHONPATH=src python3.11 -m pytest tests -q` 相对基线**零回归**
      （基线届时由编排者在派发时写入 status；那 4 个
      `tests/test_finalize_merge_triple_sign.py` 预存失败**不要修**）
- [ ] 按缺陷 B7：直接跑工作树代码，**不要**用 `agentic quality-gate` 自证
- [ ] `src/agentic_loop/gate/__init__.py` diff **必须为 0 行**
- [ ] 写回段 diff **必须为 0 行**
- [ ] 无 forbidden_paths / 跨 owner 写入
- [ ] 无生产写入、无网络、无通知、无推送
- [ ] 不 merge、不 push、不切生产分支
- [ ] commit message 符合规范

## 风险声明

| 维度 | 值 |
|------|-----|
| production_writes | FORBIDDEN |
| network | FORBIDDEN |
| notifications | FORBIDDEN |
| data_access | READ_ONLY |

## 附注

### 已知陷阱

1. **不要改写回形态**。mktemp+mv 已免疫；改它是无谓返工。
2. **不要改判据**。`path_is_in_worktree` 对替换后的路径答 `True`，行为正确。
3. **不要放宽拒收**。重构时最容易把 fail-closed 分支写丢——四条拒收语义逐条留测试。
4. **`O_NOFOLLOW` 的语义边界**：它只拒绝**最后一段**是 symlink，不防中间目录段被替换。
   若你的修法依赖它，须在报告里说明这个残余面（可作为 `[CONCERNS]` 申报，不必本轮修）。
5. **`validate_wp_status.py` 只碰 fd 支持那一处**。A14/A15/A18 是别的 WP 的面。
6. **`set -euo pipefail` 下的读取一律要守卫**（缺陷 A12 的来历）。

### 口径权威源引用

- worktree 判定：`agentic_loop.gate.path_is_in_worktree`（WP-19 建立的唯一权威，本轮只读）
- 主仓根解析：`resolve_paths --root main_repo`（既有唯一权威，不另造）
- 范围校验：`quality-gate.sh` 的 `_path_in_scope`（既有唯一权威，不另造）

---

> 以下三节为 `dispatch-lint` 要求的英文锚点（`## ` 精确匹配），
> 内容与上文中文章节同义，非另一份口径。

## Allowed and forbidden paths

**allowed_paths**

- `src/agentic_loop/wrappers/finalize_merge.sh` — collapse the predicate/read gap
- `src/agentic_loop/validate_wp_status.py` — **only** the minimum needed to read from an
  already-open descriptor; do not touch `--field` semantics or A14/A15/A18 logic
- `tests/test_finalize_merge_toctou.py` (new)

**forbidden_paths**

- `src/agentic_loop/gate/__init__.py` — predicate is correct; **zero-line diff**
- `src/agentic_loop/wrappers/preflight.sh`
- `src/agentic_loop/independence.py` — A9/A5 surface, separate WP (WP-20)
- `src/agentic_loop/adapters/`, `src/agentic_loop/redispatch.py`
- `docs/` — brief and status are orchestrator-maintained
- `.agentic/config.toml`, `.agentic/locks/`, `.env`, `.context/`

## Acceptance tests

Run with `PYTHONPATH=src python3.11 -m pytest` directly against the worktree.
Do **not** use `agentic quality-gate` to self-certify (defect B7).

- `tests/test_finalize_merge_toctou.py` — A34:
  - after the predicate passes, replacing the main-repo status with a symlink to a
    worktree copy must **not** let finalize take its decision fields from that copy
    (use two distinguishable status contents)
  - a normal main-repo file still reaches `FINALIZE_OK`
  - a worktree-local path is still refused
  - an unresolvable path still fails closed without raising
- **Cross-version**: both `test_finalize_merge_toctou.py` and
  `test_finalize_merge_first_call.py` green under python3.11, 3.13 and 3.14.
- Whole suite: zero regression against the baseline recorded in the status JSON at
  dispatch time. The 4 pre-existing `test_finalize_merge_triple_sign.py` failures
  stay exactly as they are — **do not fix them**.

## Completion definition

- [ ] Every deliverable in place; A34 has one failing-to-passing test
- [ ] All three interpreters green on the two target test files
- [ ] Zero regression relative to the recorded baseline
- [ ] `src/agentic_loop/gate/__init__.py` diff is **zero lines**
- [ ] The write-back block (mktemp/trap/mv) diff is **zero lines**
- [ ] All four refusal semantics still covered by tests
- [ ] No writes to forbidden_paths, no cross-owner writes
- [ ] No production writes, no network, no notifications, no pushes
- [ ] No merge, no push, no switching to a production branch
- [ ] Commit message follows the repository convention
