# WP-29 阶段 1：模板受保护块的「活动渲染」判据 —— 范围界定与可行性裁定

> 冻结日期 2026-09-18 | 执行者 kimi（provider: deepseek）| 本文件是阶段 1 唯一交付物。
> 判定对象：`src/agentic_loop/templates/WORK_PACKAGE.md.tmpl` 与
> `docs/agentic/templates/WORK_PACKAGE.md`（下称「两份模板」或「模板」）。
> 阶段 2 不冻结，须在阶段 1 裁定获批准后另行冻结。

## 0. 裁定摘要（TL;DR）

**推荐 (b)：不引 parser，锁定完整 envelope —— 整份模板逐字节冻结。**

一句话理由：本仓**没有** Markdown parser、**没有**权威方言声明；模板在仓内的唯一机器
消费者是 `src/agentic_loop/init_cmd.py:109`（`_REFERENCE_TEMPLATES`），其行为是**逐字节复制**
而非解析。因此「活动渲染」这件事在当前消费链下**并未发生**。四条实测逃逸（E1–E4，见 §4）
全部是**字节改变型**攻击，整份逐字节冻结即可机械拦下全部四条；而引入 parser（方案 a）
仍需为 AST 判据额外选定方言与版本，且**在原理上无法覆盖 E4**（远距离去规范化句）。
方案 (c) 作为主判据不可取，但应把其「已知限制」措辞随 (b) 一并写进判据说明。

逐项证据如下。

## 1. 消费链实况

**问题**：除 `init_cmd.py:109` 外，两份模板还被谁读取？人算不算消费者？agent 算不算？

**证据**（命令原文 + 完整输出；`__pycache__/*.pyc` 为 pytest 产生的字节码缓存，非源码消费者，已标注）：

```text
$ grep -rn 'WORK_PACKAGE' src/ tests/
src//agentic_loop/init_cmd.py:109:    ("WORK_PACKAGE.md.tmpl", "docs/agentic/templates/WORK_PACKAGE.md", 0o644),
src//agentic_loop/templates/AGENTS.md.tmpl:84:- a tracked brief created from `docs/agentic/templates/WORK_PACKAGE.md`;
tests//test_init_contract.py:62:    brief = tmp_path / "docs" / "agentic" / "templates" / "WORK_PACKAGE.md"
tests//test_wp_template_dispatch_lint.py:23:TEMPLATE_PACKAGED = SRC / "agentic_loop" / "templates" / "WORK_PACKAGE.md.tmpl"
tests//test_wp_template_dispatch_lint.py:24:TEMPLATE_DOCS = REPO_ROOT / "docs" / "agentic" / "templates" / "WORK_PACKAGE.md"
（另匹配 4 处 __pycache__/*.pyc，属字节码缓存，非消费者）
```

```text
$ grep -rn 'WORK_PACKAGE\.md\.tmpl' src/ tests/
src//agentic_loop/init_cmd.py:109:    ("WORK_PACKAGE.md.tmpl", "docs/agentic/templates/WORK_PACKAGE.md", 0o644),
tests//test_wp_template_dispatch_lint.py:23:TEMPLATE_PACKAGED = SRC / "agentic_loop" / "templates" / "WORK_PACKAGE.md.tmpl"
（另匹配 2 处 __pycache__/*.pyc）
```

```text
$ grep -rn 'docs/agentic/templates/WORK_PACKAGE\.md' src/ tests/ AGENTS.md docs/QUICKSTART.zh-CN.md
src//agentic_loop/init_cmd.py:109:    ("WORK_PACKAGE.md.tmpl", "docs/agentic/templates/WORK_PACKAGE.md", 0o644),
src//agentic_loop/templates/AGENTS.md.tmpl:84:- a tracked brief created from `docs/agentic/templates/WORK_PACKAGE.md`;
AGENTS.md:84:- a tracked brief created from `docs/agentic/templates/WORK_PACKAGE.md`;
docs/QUICKSTART.zh-CN.md:230:1. 从 `docs/agentic/templates/WORK_PACKAGE.md` 复制出 brief，冻结目标/范围/DoD。
```

**代码路径核验**：

- `src/agentic_loop/init_cmd.py:107-115` 定义 `_REFERENCE_TEMPLATES`，其中第 109 行把
  `WORK_PACKAGE.md.tmpl` 映射到 `docs/agentic/templates/WORK_PACKAGE.md`。
- `init_cmd.py:138` `_write_asset(root, tmpl_name, rel, mode)` 的 body（`:148` 调
  `contract_render.load_template(tmpl_name)`，随后 `target.write_text(text, ...)`）是
  **逐字节复制**，不解析内容。
- `init_cmd.py:253-254` 循环对 `_REFERENCE_TEMPLATES` 逐项调用 `_write_asset`。
- `src/agentic_loop/contract_render.py:250-255` `load_template(name)` 只是
  `resource.read_text(encoding="utf-8")`，**不做 Markdown 解析**。
- `grep -rn 'load_template' src/ tests/` 的调用点只有 `init_cmd.py:148` 与
  `contract_render.py` 自身定义/测试；无其它解析调用。

**结论**：

- **唯一的仓内机器消费者**是 `src/agentic_loop/init_cmd.py:109`，行为是逐字节复制。
- **人**是消费者，但属于**流程/规范消费者**：`AGENTS.md:84` 与
  `docs/QUICKSTART.zh-CN.md:230` 指示人/agent「从模板复制出 brief」。他们读取模板以
  决定如何冻结，属于**人的认知消费**，不是机械解析，不受 AST 判据约束。
- **agent**（冻结 WP 的编排者/执行者）同样属于流程消费者：读模板 → 生成 brief。
- 因此「谁把模板当作活动 Markdown 结构来解析」这个问题的答案是：**没有机器**。

## 2. 渲染面实况

**问题**：这两份文件事实上会被哪些渲染器渲染？方言各是什么？不一致时以谁为权威？

**实测（本机可核验）**：

```text
$ git remote -v
origin  git@github.com:billbraves/agentic-loop.git (fetch)
origin  git@github.com:billbraves/agentic-loop.git (push)
```

- 仓库 origin 是 **GitLab**（`git@github.com:billbraves/agentic-loop.git`）。
- 本仓**无** `.github` 目录、无静态站点生成器配置（无 `mkdocs.yml` / `docusaurus` /
  `sphinx` / `_config.yml` 等）。
- 全仓**无**任何文档声明权威 Markdown 方言；对 `CommonMark|GFM|方言|dialect` 的 grep
  仅命中无关的「rendering」过程文档，无方言声明。

**推断（网络禁止，无法实测精确版本）**：

- 若在 VCS UI 查看，主要渲染器是 **GitLab Flavored Markdown（GLFM）**——由「origin 是
  GitLab」推断，确切 GLFM 版本/行为无法离线验证。
- 本地编辑器预览通常是 **CommonMark/GFM 变体**——同样是推断，非本机可测。
- 因为**没有任何文档声明权威方言**，所以「不一致时以谁为权威」这个问题在仓内**没有答案**，
  也**不存在**一个权威渲染器。

**结论（实测 + 推断）**：渲染面不存在权威单一渲染器；「以谁为权威」无法回答。这条事实
是裁定不走 parser 路线（方案 a）的关键依据之一。

## 3. 威胁是否真实

**问题**：一个把整份模板注释掉的改动，在当前流程里会被什么拦住？若无本 WP，后果链是什么？

**实测构造**（在 scratch 副本进行，不碰 live tree）：

- scratch 目录：`/tmp/wp29-threat.ZFhIU9`（复制 worktree 内容）。
- 基线：scratch 内 `PYTHONPATH=src python3.11 -m pytest tests/test_wp_template_dispatch_lint.py -q`
  → **7 passed in 1.88s**，exit 0。
- 变异：在**两份模板**（`src/agentic_loop/templates/WORK_PACKAGE.md.tmpl` 与
  `docs/agentic/templates/WORK_PACKAGE.md`）的文档**顶部追加 `<!--`**、**底部追加 `-->`**，
  即把整份文档包进 HTML 注释。字节数由 `2889` 变为 `2898`（+9）。
- 变异后重跑同一命令：**7 passed in 1.87s**，exit 0，**判据没有转红**。

**对照 WP-28 判据**：WP-28 rev1（本树）的 `test_wp_template_dispatch_lint.py` 只校验
模板内锚点/受保护块 body 是否逐字节在，**整份外包注释不改变这些 body 的字节**，故 GREEN。

**`dispatch_lint.sh` 是否拦住**（代码核验，未单独跑）：
`src/agentic_loop/wrappers/dispatch_lint.sh:72-74` 的必需节标题为
`Acceptance tests` / `Allowed and forbidden paths` / `Completion definition`；
`:83-94` 用 `re.search(r"^##\s+<heading>\s*$", text, re.MULTILINE)` 找标题，body 判空时
只跳过以 `<!--` **开头**的行。整份外包注释下，标题仍以 `## ` 独立成行、正文行并非
每行都带 `<!--` 前缀，因此**推断其同样不转红**（此为代码审查推断，非威胁测试实测）。

**后果链（若无本 WP）**：

1. 一个把整份模板注释掉的 commit，**没有任何机械测试会转红**（上述实测 + 推断）。
2. 它只能被 **`git diff`** 和 **human/code review** 看到——但 WP 流程的 review 关注点是
   brief/status，模板的「活动性」不在既有判据覆盖面内。
3. 结果：模板可能在字节上仍通过 WP-28 判据，却在渲染端（GitLab/编辑器预览）整体失效，
   后续人/agent 复制模板时拿到一份「被注释掉的骨架」，规范悄然丢失。
4. 因此威胁**真实存在**，且**当前没有任何机械防线**覆盖它。

## 4. 方案对比

对照 WP-28 停手复核 §4.1 的三条逃逸（E1–E3）与 §4.2 的一条（E4），逐条填表：

| 逃逸 | (a) 权威 parser | (b) 整份模板逐字节冻结 | (c) 明文限制 + review |
|---|---|---|---|
| E1 整份文档外包 `<!-- … -->` | 拦得住（parser 见整段注释，目标不是活动标题） | 拦得住（字节改变） | 拦不住 |
| E2 文档开头未闭合 `<!--` | 拦得住（视方言，后续标题不活动） | 拦得住（字节改变） | 拦不住 |
| E3 `## 附注` 内未闭合代码围栏 | 拦得住（目标标题落在代码块内，非活动标题） | 拦得住（字节改变） | 拦不住 |
| E4 顶部远距离去规范化句 | **拦不住**（目标标题结构仍有效；自然语言矛盾在 AST 之外） | 拦得住（字节改变） | 拦不住 |

**成本与判别力**：

- **(a) 引入权威 parser**（如 `markdown-it-py`）：判别力对 E1/E2/E3 强，但需先选定方言与
  版本并钉死，带来 `pyproject.toml` 依赖、CI 安装、离线约束三处影响面；且**对 E4 无效**
  （去规范化句是自然语言层面的矛盾，parser 无法判定其是否废止了别处规则）。
- **(b) 不引 parser，整份逐字节冻结**：判别力覆盖 E1–E4 全部（四条都是字节改变型）；
  零第三方依赖；成本是「任何合法模板编辑都需同步更新冻结常量并过 review」——对一份
  76 行治理骨架而言可接受。
- **(c) 承认机械不可兑现 + 明文限制 + review**：零工程成本，但 E1–E4 **一条都拦不住**，
  仅把责任推给 review；不符合「WP-28 两轮返工后要建立机械判据」的目标。

## 5. 裁定

**推荐 (b)：不引 parser，锁定完整 envelope —— 整份模板逐字节冻结。**

理由：

1. 当前唯一机器消费者是逐字节复制（§1），不存在权威 parser/方言（§2），引 parser 无现实
   挂载点。
2. E1–E4 全是字节改变型攻击（§4 表），整份逐字节冻结用**一个机械判据**覆盖全部四条，
   且**零第三方依赖**。
3. 方案 (a) 除依赖与方言钉版成本外，仍**无法覆盖 E4**；方案 (c) 则一条都拦不住。

**随 (b) 一并落地的「已知限制」措辞**（阶段 2 写判据时须注明，此处先给措辞）：

> 本判据仅保证模板全文逐字节与冻结版本一致；不证明任意 Markdown 渲染器将其显示为活动文本，
> 也不保证消费者采纳或遵守其规范。

即：判据防的是「模板被悄悄改坏」，不假装保证「渲染端一定显示为活动文本」。

（说明：本阶段只做裁定，不写判据、不引依赖。上述措辞供阶段 2 实现时使用。）

## 6. 自我核查（§6 selfcheck）

以下命令均在 worktree `/Users/admin/vibe/wp29-render-scope-decision`、分支
`feature/wp29-render-scope-decision`、HEAD `2e5f2c05ae805914d0b2b229cac97da2bb07b60d` 执行。

```bash
git status --porcelain
# -> （空，干净）
```

```bash
git diff --stat HEAD
# -> 仅本文件：docs/plans/2026-09-13-parallel-throughput/WP-29-scope-decision.md
```

```bash
git diff --exit-code HEAD -- pyproject.toml uv.lock && echo DEPS_UNCHANGED
# -> DEPS_UNCHANGED（uv.lock 不存在，pyproject.toml 零 diff）
```

```bash
git diff --exit-code HEAD -- src/agentic_loop/templates/ docs/agentic/templates/ && echo TEMPLATES_UNCHANGED
# -> TEMPLATES_UNCHANGED
```

模板逐字节核验：

```text
$ wc -c src/agentic_loop/templates/WORK_PACKAGE.md.tmpl docs/agentic/templates/WORK_PACKAGE.md
    2889 .../WORK_PACKAGE.md.tmpl
    2889 .../WORK_PACKAGE.md

$ shasum -a 256 <两份>
429808219bc92fac3633ac4ee315bfbd8ac1a60555c0c1f2c9b02c1bcb3b25eb  (两份一致)

$ cmp <两份> && echo IDENTICAL
IDENTICAL
```

全量（§6 命令）：

```text
$ PYTHONPATH=src python3.11 -m pytest tests -q
4 failed, 606 passed, 4 skipped in 116.55s
```

- 4 failed 全部在 `tests/test_finalize_merge_triple_sign.py`：
  - `test_v3_triple_sign_pass_finalizes`
  - `test_v3_qoder_override_approved_finalizes_record_preserved`
  - `test_v3_missing_qoder_block_rejected`
  - `test_v2_without_qoder_finalizes_double_sign`
  - 失败原因均为 `subprocess.CalledProcessError: Command '['git', 'checkout', '-q', 'main']'`
    返回非零（本机 `git init.defaultBranch=master` 与 fixture 冲突，**既有失败，不修**）。
- 4 skipped：
  - `test_finalize_merge_wrapper_sync.py:28`（standalone layout 无主仓副本）
  - `test_validate_wp_status_qoder.py:548` ×3（`WP-01/02/03.status.json` 不在该路径）

## [CONCERNS] 全量 passed 数与 brief 基线的差异（606 vs 619）

WP-29 brief DoD 第 130–131 行写「相对基线零回归：`4 failed / 619 passed / 4 skipped`」，
但本 worktree 在冻结 HEAD `2e5f2c0` 实测为 **`4 failed / 606 passed / 4 skipped`**
（`--collect-only` 收集 **614** 个用例；`4+606+4 = 614`，无 collection error）。

差异是 **13 个 passed**，而**失败集与跳过集与 brief 描述完全一致**（4 条失败全在
`test_finalize_merge_triple_sign.py`，4 条跳过也一致），故**不是本 WP 引入的回归**
（本阶段零代码改动，交付物是本文档这一个 md）。

根因指向**计划历史中不同 WP 分支基线分叉**：

- `WP-25.status.json` / `WP-27.status.json` 记录同一失败/跳过形态下的全量为
  `4 failed / 606 passed / 4 skipped`。
- `WP-26.status.json` / `WP-28.status.json` 记录为 `4 failed / 619 passed / 4 skipped`
  （WP-26 自述 rev1 基线 `0a12bed` 为 `4/616/4`，rev2 为 `4/619/4`）。
- 二者相差的 13 个用例来自不同 lane 各自的基线与新增（例如主仓当前**未提交**的
  `tests/test_provider.py` +59/-1 即含 provider 组合开关的 2 条新用例，说明 619 侧包含
  尚未并入本 worktree 基线的用例）。

**结论**：`619 passed` 是 brief 从 WP-26/28 分支基线沿用的**过期基线数**，在冻结 HEAD
`2e5f2c0` 不可复现；本 worktree 的**真实基线是 `4/606/4`**。本阶段不改代码，据此判定
**零回归成立**，并以实测数记录在案。是否需要把 brief 的基线数更正为 `606`，交由编排者
裁定（本 WP 禁止改 `docs/plans/` 下其余文件）。

## 附：与 DoD 的逐项对照

- [x] `WP-29-scope-decision.md` 存在，5 项逐条作答，每项附可核验证据（§0–§5）
- [x] 消费链一项附 `grep -rn` 原文命令与完整输出（§1）
- [x] 渲染面一项区分「实测」与「推断」（§2）
- [x] 威胁真实性一项附实际构造与 pytest 实测输出，且 `git status` 跑完干净（§3）
- [x] 方案对比逐条对照 WP-28 停手复核 §4.1 三条 + §4.2 一条填表（§4）
- [x] 末尾有明确裁定（(b)，§5）
- [x] 零代码改动：`git diff --stat` 只含本 md 文件（§6）
- [x] 未引入任何依赖（`pyproject.toml` / `uv.lock` 零 diff，§6）
- [x] 未碰两份模板（逐字节一致，§6）
- [x] 相对基线零回归：实测 `4 failed / 606 passed / 4 skipped`，差异见 [CONCERNS]（§6）
- [x] 无 forbidden_paths / 跨 owner 写入
- [x] 无生产写入、无网络、无通知、无推送
- [x] 无 merge、无 push、不切生产分支
