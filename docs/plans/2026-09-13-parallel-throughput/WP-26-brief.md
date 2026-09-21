# WP-26: 门禁与重派必须读 `evidence.brief.path` 并校验 `sha256`（B16）

> 冻结日期 2026-09-16 | 编排者 claude | 执行者 kimi。冻结后执行期间不得修改。

## 目标（一句话）

`dispatch_lint.sh` 与 `redispatch.py` 都按**固定命名**推出 brief 路径，从不读
status 里的 `evidence.brief.path`，也从不校验 `evidence.brief.sha256`；
本 WP 把两处的读取面改成「以 status 声明的路径为权威 + 校验 sha256」，
使 `-revN` 冻结进入门禁面、并让 sha256 第一次拥有消费者。

## 前置事实（编排者已实测，执行者不必重做，但**不得与之矛盾**）

**缺陷位置**（活树，非 `agentic` 冻结副本）：

- `src/agentic_loop/wrappers/dispatch_lint.sh:60`
  ```bash
  brief_file="$iterations_dir/$iteration_id/${work_package_id}-brief.md"
  ```
- `src/agentic_loop/redispatch.py:493-494`
  ```python
  brief_path = iteration_dir / f"{work_package_id}-brief.md"
  brief = brief_path.read_text(encoding="utf-8") if brief_path.is_file() else ""
  ```

**差分对实测**（证明门禁真的没读该字段，不是「读了但恰好一致」）：

| 变动 | 结果 |
|---|---|
| `evidence.brief.path` 改指 `DOES-NOT-EXIST.md` | 仍 `DISPATCH_LINT_PASS rc=0` |
| 同一 status **仅**换 `work_package_id=WP-999` | 立刻 `DISPATCH_LINT_FAIL brief not found rc=2` |

即路径完全由 `iteration_id` + `work_package_id` 推出，声明字段是死字段。

**第二层后果**：`redispatch.py` 喂给执行者的 prompt 也走固定命名，
所以 rev2 冻结后若不做人工搬移，重派会把 **rev1** 正文喂给执行者。

**第三个事实**：全仓扫描 `evidence.brief.sha256`，**没有任何消费者**——
它只被写入、从不被校验。

## 范围

- **allowed_paths**：
  - `src/agentic_loop/wrappers/dispatch_lint.sh`
  - `src/agentic_loop/redispatch.py`
  - `tests/test_dispatch_lint_brief_source.py`（新建）
  - `tests/test_redispatch_brief_source.py`（新建）
- **forbidden_paths**：
  - `src/agentic_loop/wrappers/preflight.sh`（B17 归 WP-27，本 WP 不碰）
  - `src/agentic_loop/wrappers/finalize_merge.sh`
  - `src/agentic_loop/validate_wp_status.py`
  - `src/agentic_loop/gate/__init__.py`
  - `src/agentic_loop/templates/`、`CLAUDE.md`、`AGENTS.md`、`docs/agentic/OPERATING_MODEL.md`
  - `docs/plans/`（含本 brief 与全部 status JSON）
  - `.agentic/config.toml`、`.agentic/locks/`、`.env`、`.context/`

## 交付物清单

1. `dispatch_lint.sh`：brief 路径**以 `evidence.brief.path` 为权威**。
   - 该字段存在 → 用它（相对路径按**主仓根**解析，与 `:26-29` 对 status 的既有口径一致）；
   - 该字段缺失 → 保持现有固定命名回退（零回归，老 status 仍可用）；
   - 路径不得逃出主仓（`../`、绝对路径指向仓外、symlink 逃逸一律 fail-closed 拒收）。
2. `dispatch_lint.sh`：`evidence.brief.sha256` 存在时**必须校验**，
   不匹配则 `DISPATCH_LINT_FAIL` 退 2 并打印实测值与声明值。
3. `redispatch.py`：同样以 `evidence.brief.path` 为权威取正文，缺失时回退固定命名；
   sha256 存在且不匹配则**拒绝重派**（不得静默喂旧 rev）。
4. 两个新测试文件，每条负面断言自带 oracle 三项。

## Allowed and forbidden paths

**allowed_paths**

- `src/agentic_loop/wrappers/dispatch_lint.sh`
- `src/agentic_loop/redispatch.py`
- `tests/test_dispatch_lint_brief_source.py` (new)
- `tests/test_redispatch_brief_source.py` (new)

**forbidden_paths**

- `src/agentic_loop/wrappers/preflight.sh` (B17 belongs to WP-27)
- `src/agentic_loop/wrappers/finalize_merge.sh`
- `src/agentic_loop/validate_wp_status.py`
- `src/agentic_loop/gate/__init__.py`
- `src/agentic_loop/templates/`, `CLAUDE.md`, `AGENTS.md`,
  `docs/agentic/OPERATING_MODEL.md`
- `docs/plans/` (this brief and every status JSON)
- `.agentic/config.toml`, `.agentic/locks/`, `.env`, `.context/`

## Acceptance tests

- **The differential pair above must invert.** With the fix in place, a status
  whose `evidence.brief.path` points at a nonexistent file must FAIL (it passes
  today), and a status whose declared path points at a real `-rev2` brief must
  lint THAT file, not the fixed-name one. Assert both directions in one test:
  put DIFFERENT content in the fixed-name file and in the declared `-rev2`
  file, arrange for exactly one of them to satisfy the section predicate, and
  assert the verdict follows the DECLARED file. This is the only construction
  that distinguishes "reads the declared path" from "happens to agree".
- A sha256 mismatch must FAIL with both values printed; a matching sha256 must
  pass; an absent sha256 must not fail (backward compatible).
- A status with NO `evidence.brief.path` must still lint the fixed-name brief
  exactly as today (zero regression for old statuses).
- Path escape attempts must fail closed: `../outside.md`, an absolute path
  outside the main repo, and a symlink whose target is outside the main repo.
- `redispatch.py` must feed the DECLARED brief: assert the generated prompt
  contains a marker unique to the `-rev2` file and does NOT contain a marker
  unique to the fixed-name file.
- Each negative assertion carries the oracle three items:
  1. positive reachability control on the same fixture;
  2. a cause-specific witness — and note that `dispatch_lint.sh:86` and `:98`
     print the SAME line, so if a witness cannot be made cause-specific by
     wording, use a differential pair instead (defect B11);
  3. a representative forbidden mutation that turns the test red (e.g. revert
     the path resolution to the fixed name and show the declared-path test goes
     red), then restore and show it green again.
- Green on 3.11, 3.13 and 3.14.
- Zero regression against the baseline recorded in this WP's status JSON.

## Completion definition

- [ ] `dispatch_lint.sh` 以 `evidence.brief.path` 为权威，缺失时回退固定命名
- [ ] 相对路径按主仓根解析；逃出主仓的路径 fail-closed 拒收
- [ ] `evidence.brief.sha256` 存在时必须校验，不匹配退 2 并打印双值
- [ ] `redispatch.py` 同口径取正文，sha256 不匹配则拒绝重派
- [ ] 差分对**双向**成立（声明路径不存在 → FAIL；声明 rev2 → lint 的是 rev2）
- [ ] 老 status（无该字段）行为不变
- [ ] 每条负面断言带 oracle 三项，含一个能转红的 forbidden 变异
- [ ] 3.11 / 3.13 / 3.14 全绿
- [ ] 相对基线零回归（`tests/test_finalize_merge_triple_sign.py` 的 4 条是既有失败，**不要修**）
- [ ] 无 forbidden_paths 写入、无跨 owner 写入
- [ ] 无生产写入、无网络、无通知、无推送
- [ ] 无 merge、无 push、不切生产分支
- [ ] commit message 符合仓库规范

## 风险声明

| 维度 | 取值 |
|---|---|
| production_writes | FORBIDDEN |
| network | FORBIDDEN |
| notifications | FORBIDDEN |
| data_access | READ_ONLY |

## 附注

### 已知陷阱

1. **不要把固定命名回退删掉**。仓里已有 status 不带 `evidence.brief.path`，
   删回退即制造回归。字段存在才切换权威。
2. **相对路径的锚点是主仓根，不是 cwd**。`dispatch_lint.sh:26-29` 对 status
   已有正确口径（`main_root` 前缀），照抄同一口径；用 cwd 会重演 B17。
3. **不要顺手修 B17**。`preflight.sh` 的 status 读取面归 WP-27，本 WP 只动 brief 读取面。
4. **sha256 的失败必须 fail-closed**。算不出（文件读不到、权限）也要拒收，不得跳过。
5. **不要用 `agentic dispatch-lint` 自证**（B14：那是落后活树的冻结副本）。
   直跑 `bash src/agentic_loop/wrappers/dispatch_lint.sh <status>`。
6. **差分对必须让两个文件内容不同且判据结论相反**。若两份 brief 都能过判据，
   测试无法区分「读了声明路径」和「读了固定命名但恰好也过」——这正是 B16 藏了一整轮的原因。

### 口径权威源引用

- 主仓根解析的既有正确口径：`src/agentic_loop/wrappers/dispatch_lint.sh:26-29`
- 缺陷实测记录：`docs/plans/2026-09-13-parallel-throughput/WP-08-candidate.md` §B16
- oracle 三项规则：`docs/agentic/templates/WORK_PACKAGE.md`
- B11 判据来源纪律：同上 §B11
