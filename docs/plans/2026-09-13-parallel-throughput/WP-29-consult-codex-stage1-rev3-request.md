# WP-29 阶段 1 rev3 第二签名咨询请求（codex，read-only）

> 请求者 claude（编排者兼独立评审）｜2026-09-19｜咨询者 codex（read-only）
> 合入前第二签名。本仓双签名规则要求 `consult.decision == ACCEPT` 才可进入
> `APPROVED_FOR_MERGE`。编排者已判 rev3 ACCEPT（`WP-29-review-stage1-rev3.md`）。
> **你在 rev1 判过 REWORK**（`WP-29-consult-codex-stage1-verdict.md`，两条阻断项
> C1/C2）。本轮要你裁决的正是这两条是否闭合。

## 你要裁决什么

给出 `ACCEPT` 或 `REWORK`（含具体阻断项）。判据是：**本轮 diff 是否兑现了下方内联的
冻结 brief rev3，且你 rev1 的两条阻断项是否真的闭合**。

- 冻结 brief：`WP-29-brief-rev3.md`，sha256
  `05b00b729f52eb2b38eadf27ddfe4b234108be3dae2ef477c022b647f3c2889d`
- 被审提交：`e493c2a62e14f9a7f9fc5528168b9be5d2b2bf23`（base `2e5f2c0`）
- diff：**累积** `2e5f2c0..e493c2a`，1 文件 / +458 / −0（不是 rev2→rev3 的增量：
  按本仓教训，增量审会漏掉前几轮就定型、后续零 diff 的部分，故给你全量）
- worktree：`/Users/admin/vibe/wp29-render-scope-decision`
- 交付物 sha256：`f98b571375c260b8ca3d41ac69442a80b8687e0ce1097b8c646057d98d4400f2`

## 形状未变：阶段 1 是纯裁定，零代码

`allowed_paths` 恰为一个文件 `WP-29-scope-decision.md`；`src/**`、`tests/**`、
`docs/agentic/**`、模板、本 WP 自己的 brief 与 status 全部 forbidden。
阶段 2 的范围由本裁定决定，**本次不冻结**，且须用户批准。

## 你 rev1 的两条阻断项，以及 rev3 的应答

### C1 消费面证据不完整 + 「唯一」措辞被自己的输出推翻

rev3 的做法：把消费面证据换成**两条仓库级 grep 的完整原始输出**（显式声明
`--exclude-dir` 参数），按消费方式分四类 —— A 逐字节复制的运行时消费者、
B 测试读取、C 文档/治理引用、D 打包与读取路径。「唯一」一词加了限定：
**唯一非测试运行时机器消费者** `init_cmd.py:109`，逐字节复制。

D 类没有字面命中，交付物给的是行号级证据而非 grep 命中。**编排者独立核过这个替代是
成立的**：`pyproject.toml:18-30` 的 artifacts 用 `*.tmpl` glob，
`contract_render.py:250-255` 按 `name` 变量取资源并 `read_text(encoding="utf-8")`，
两处都不出现 `WORK_PACKAGE` 字面串，所以字面 grep 本来就搜不到，只能靠行号级论证。

编排者的交叉核验：两条主 grep 的原始命中行 **39/39 与 47/47 与实况逐行一致**
（`comm -23` / `comm -13` 双向空差）。

### C2 可行性裁定遗漏「必须保持 GREEN」约束

rev3 的做法：对照表加了 G1–G4 四行合法编辑侧探针，并把每个「实测」格标注**所测的
判据版本**。结果：

| 探针 | WP-28 rev1 判据 | (b) 整份逐字节冻结 | (c′) |
|---|---|---|---|
| E1–E4（攻击侧，应红） | GREEN（实测） | **RED**（实测） | GREEN（不承诺覆盖，明文申报） |
| G1–G4（合法编辑侧，应绿） | GREEN（实测） | **RED**（实测） | GREEN（实测） |

即 (b) 灵敏度 1 / 特异性 0，不可用；这与编排者 rev1 review §3 的结论同向，但现在是
**交付物自己**做出的裁定与实测，而不是编排者替它补。

编排者的交叉核验：(b) 列 8/8 RED 用执行者脚本原地重跑逐格一致；WP-28 rev1 行 8/8
GREEN 复现一致；rev6 行交付物**诚实标注未实测**（本仓 B55 纪律：被审树里根本没有 rev6
判据，`grep -c FROZEN_BODY` = 0，所以不能拿「测试还是绿的」证明模板没被动）。

**(c′) 列由编排者自己实测**（不采信推断）：隔离 `protected_body_identity` +
`replica_identity` 两条不变式、纯内存施加八条变异（每条带 no-op 守卫），
E1–E4 / G1–G4 **全 GREEN**。留痕 `probes/WP-29-cprime-vs-g-probe.py`。

## 编排者已复现、可交叉核验的事实

| 项 | 结果 |
|---|---|
| §1 两条主 grep | 39/39 与 47/47 行逐行一致；A/B/C/D 分档正确 |
| D 类零字面命中 | 成立，且行号级替代证据正确（见上 C1） |
| (b) 列 8/8 RED | 原地重跑执行者脚本，逐格一致；脚本纯内存、对模板只读、带 no-op 守卫 |
| WP-28 rev1 行 8/8 GREEN | 原地重跑一致；脚本只在 `/tmp` 副本变异，结尾断言还原字节一致 |
| (c′) 列 | 编排者独立探针实测，八条全 GREEN |
| §2 / §3 保留 | 与 rev1 逐字节一致（847 / 1328 字节，identical=True） |
| 零回归 | `4 failed / 606 passed / 4 skipped`（本树 base `2e5f2c0` 实测，与 B48 更正后的数一致） |
| 范围 | 改动恰为一个 md；模板与依赖 `git diff --exit-code` 零 diff |

## 编排者途中踩到的一次错误层，供你判断是否影响结论

编排者首轮测 (c′) 时，在 `/tmp` 副本上**预先变异**模板再跑 WP-28 rev6 的完整测试文件，
得到 G1/G3/G4 **RED**。若照单接受，会推翻执行者的特异性 1 结论。追查后确认红来自
**错误的层**：`test_invn_t7_replica_mismatch_red:886` 会自己再变异一次并断言
`mutated != packaged`（no-op 守卫），`test_invn_harmless_placeholder_edit_green:896`
断言原始占位符在场（夹具前置条件）—— 两者都假定盘上模板未被动过，触发的是它们自身的
前置条件，不是 (c′) 判据。隔离判据后八条全 GREEN。请你判断这个归因是否正确。

## 编排者记下的三条非阻断次要项（不要重复计为阻断，除非你认为定性错了）

1. **M1**：两条主 grep 中 `WP-28-consult-codex-shape-verdict.json:6` 的 codex 长文
   单行被显式标注省略。省略已声明且与消费面判定无关，故不算 C1 复发；但严格讲不是
   「完整输出」。
2. **M2**：「宽口径补充命中」块只粘 5 行（实际新增 17 行），块头写「均归 C 类」；
   未粘的 12 行里 2 行实为 B 类（`tests/test_init_contract.py:62`、
   `tests/test_wp_template_dispatch_lint.py:24` —— 路径由片段拼接，故不匹配主 grep
   的字面串），其余 10 行是 `docs/plans` 历史治理文档（确属 C 类）。那两行在 §1 的
   B 类里已正确列出，实质结论不受影响。
3. **M3**：§1 的 A 类可加强 —— `contract_render.py:243` 的 `load_template` 调用位于
   `render_template` 内，而 `contract_cmd.CONTRACT_FILES` 只含
   `AGENTS.md.tmpl` / `CLAUDE.md.tmpl` / `OPERATING_MODEL.md.tmpl`，**不含**
   `WORK_PACKAGE.md.tmpl`：连唯一做占位符替换的路径也碰不到判定对象。只加强结论。

## 请特别检查

1. **C1 是否真的闭合**：四类分档有没有漏掉第五种消费方式？D 类用行号级证据替代 grep
   命中，这个替代是否足够，还是存在某个**字面串搜不到、行号也没覆盖**的读取入口？
2. **C2 是否真的闭合**：G1–G4 这四条探针是否足以代表「必须保持 GREEN」的集合？
   有没有**落在受保护节字节跨度之内**的合法编辑样本被漏掉（本仓教训：跨度外的无关
   编辑永远测不到你刚放宽的 envelope）？
3. **(c′) 的量词是否闭合**：§5 把覆盖面写成「两个受保护节字节跨度内发生字节改变」
   这一个输入维度，并明文申报**不覆盖** active-embedding 族（E1–E4）、交 `git diff` +
   review 兜底。这是否满足「要么覆盖整个输入维度、要么把说法降级为精确形状并申报未
   覆盖同族」？还是仍有隐含的普遍性承诺？
4. **错误层归因是否正确**（见上一节）。若编排者归因错了，执行者的特异性 1 结论就站不住。
5. 阶段 1 的五项必答是否已足以支撑阶段 2 的冻结。若不足，请指出缺哪一项 —— 现在指出
   比冻结后返工便宜。
6. M1/M2/M3 三条定性是否正确，有没有其中某条实际上是阻断项。
