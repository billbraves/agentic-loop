# WP-19: codex adapter 行级 sub-hunk 切分（单个超界 hunk 的无损再切）

> 立项日期 <待冻结> | 编排者 Kiro（DeepSeek Harness）| 执行者 <待定>
> 冻结后执行期间不得修改；需修订走 re-freeze。

## 目标（一句话）
在 WP-18 已合并的分块能力之上，补一层「行级 sub-hunk 切分」：当单个 `@@` hunk
本身仍超过 chunk 字节上界、无法按 hunk 再切时，对该 hunk 按行范围**无损**再切，
使超大单-hunk 文件也能逐段送入 provider 单轮评审——在可无损切分的场景内解除
WP-39 Run 1 暴露的 fail-closed（190KB 单-hunk 新文件取不到 verdict）。

## 背景与动机
- WP-39 Run 1（合并 runtime `3d50ab7` 对 WP-34 候选 `a92af05` 跑 P2 native gate）
  证明 WP-18 分块生效、修复了 388KB 单轮空返；但 fail-closed 于 chunk 3/9：新增
  文件 `.ci/tests/test_harness_release_gate.py` 是 `@@ -0,0 +1,4170 @@` 单一 hunk、
  190KB，超 150KB 安全线且无法按 hunk 再切。adapter 遵循「绝不截断」正确拒绝。
- 现状：`_split_file_by_hunks` 只能切到 hunk 粒度；单个超界 hunk 无下一级手段。
- 证据：见 consumer-repo `docs/plans/harness-architecture/WP-39-unlock-record.md`
  （Run 1，gate log sha256 `66679f50…9ea8f`）。

## 范围
- **allowed_paths**（白名单）：
  - `src/agentic_loop/adapters/codex.py`（仅新增 `_split_hunk_by_lines` 及其在
    `_split_file_by_hunks` 末端的调用；不改 review()/JSONL/文件回填/聚合语义）
  - `tests/test_codex_line_level_split.py`（新增，本 WP 专属测试）
- **forbidden_paths**（黑名单）：
  - `.env`、`.context/`、`.agentic/config.toml`
  - `src/agentic_loop/gate/`、`src/agentic_loop/wrappers/`、`src/agentic_loop/independence.py`
  - `tests/test_codex_verdict_recovery.py`、`tests/test_codex_config_isolation_chunking.py`、
    `tests/test_codex_gate_capability_merge.py`、`tests/test_gate_diff_start.py`
    （WP-16/17/18 冻结测试，不得改动；本 WP 只加新测试文件）
  - 一切消费方仓库文件

## 设计约束（关键——无损与安全优先）
1. **只在安全可无损的场景切分单个超界 hunk**：
   - **纯新增 hunk 的严格判定（整-hunk 级谓词，不得用"局部纯增"近似）**：一个 hunk
     被判定为可行级切分，当且仅当**同时**满足：
     (a) hunk 头删除侧计数为 0（形如 `@@ -X,0 +Y,N @@`）；
     (b) hunk 体内**没有任何上下文行**（不以 `+`/`-` 开头的行，通常是前导空格行）；
     (c) hunk 体内**没有任何删除行**（`-` 开头，`---` 文件头除外）。
     即整个 hunk 体必须全部是 `+` 行。**禁止**对"删除侧非 0 或含上下文/删除行、
     但内部某连续区段恰好全是 `+`"的混合 hunk 动刀——那不是纯新增 hunk，切它会破坏
     无损性与可应用性。
   - **切分与头重算**：对满足上述谓词的 hunk，按 `+` 行的连续区间切成多段，每段
     重算头为 `@@ -X,0 +start,count @@`：
     - **删除侧 `-X,0` 的 `X` 对所有子段保持与原 hunk 头相同的值**（新文件为 0，
       "追加到非空文件尾部"则为原起始行如 100；因无实际删除，锚点不变，各段一致）；
     - **仅 `+` 侧的 `start,count` 随子段递增**：第一段 `start` = 原 hunk `+` 侧起始行，
       其后每段 `start` = 上一段 `start` + 上一段 `count`，`count` = 本段 `+` 行数。
     - 各段拼接的 `+` 行序列 == 原 hunk 的 `+` 行序列，行序不变、无截断 → 可证明无损。
   - **其它 hunk 形态**（不满足上述严格谓词的任何 hunk）：**不切**，维持现有 fail-closed
     语义。跨上下文/删除边界切分会破坏 diff 可应用性与评审语义，明确不在本 WP 内做。
2. **绝不截断、绝不改写行内容**：只在行边界分组并重算 hunk 头计数；任何一行都不
   增删改。
3. **切后每段仍须 ≤ 有效上界**（含 brief 预留）；若纯新增 hunk 的**单行**长度即已
   超界（病态输入），仍 fail-closed，不强切一行。
4. **不触碰决策/JSONL/文件回填/聚合**：本 WP 纯粹是 `_split_*` 家族的下钻，产物仍是
   `(label, sub_diff)` 列表，交由既有 `_review_single` 逐段评审、既有聚合合并。
5. **静态不变量延续**：无 regex；无决策字面量出现在 `_split_*`；label 用字符串处理
   （如 `f"{label}#hunk{h}#lines{a}-{b}"`）。

## 验收判据（DoD）
- [ ] 新增 `_split_hunk_by_lines`：对纯新增超界 hunk 按行区间无损切分，每段重算头；
      非纯新增 hunk 原样返回（触发上层 fail-closed）。
- [ ] `_split_file_by_hunks` 末端：对切出的仍超界的单 hunk 调用行级切分。
- [ ] 新测试 `tests/test_codex_line_level_split.py` 覆盖：
      - **新文件**纯新增大 hunk（如 4000+ 行，`@@ -0,0 +1,N @@`）被切成多段，
        **各段拼接的 `+` 行 == 原始 `+` 行**（无损不变量），且各段 ≤ 有效上界；
      - **追加到非空文件尾部**的纯新增大 hunk（如 `@@ -100,0 +101,N @@`）也能正确切分：
        各段 `-100,0` 的 `X` 恒为 100 不变，仅 `+` 侧 `start,count` 从 101 起连续递增，
        计数正确、拼接 `+` 行无损；
      - 各段 hunk 头 `+start,count` 连续、计数正确、`-X,0` 的 `X` 与原 hunk 一致；
      - **删除侧非 0 或含上下文/删除行的混合超界 hunk（即便内部有大段连续 `+`）不被行切**，
        走 fail-closed（RuntimeError，不 ACCEPT）；
      - 单行超界的病态输入 fail-closed；
      - 阈值以下的 hunk 完全不进入行切路径（回归：行为同 WP-18）。
- [ ] 现有 WP-16/17/18 四套 codex 测试**全绿不改动**（回归无削弱）。
- [ ] 全仓测试无新增失败（既有 git-env baseline 失败除外，与本 WP 无关）。
- [ ] 独立评审 ACCEPT 后方可合并；合并需用户批准。

## 风险声明
| 维度 | 值 |
|------|-----|
| production_writes | FORBIDDEN |
| network | FORBIDDEN |
| notifications | FORBIDDEN |
| data_access | READ_ONLY |

## 依赖与下游
- **上游**：WP-18 已 MERGED（`3d50ab7`），提供分块/文件回填/JSONL 基座。
- **下游**：WP-19 合并后，consumer-repo WP-39 跑 Run 2（用含行级切分的新 runtime
  重跑 WP-34 native gate 取第二签名）。WP-19 不含任何消费方仓改动。

## 附注
- 本 WP 是 WP-18 的**能力补丁**，边界严格限定在 `_split_*` 下钻 + 新测试，不重开
  已冻结的裁决/协议面。
- 明确不做混合 hunk 的行切（无损性无法保证）——那类超界文件维持 fail-closed，
  如确需评审另行立项讨论替代策略（如按文件语义分节由人工预切）。
