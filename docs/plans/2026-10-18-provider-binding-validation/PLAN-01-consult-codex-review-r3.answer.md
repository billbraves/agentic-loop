# Codex 独立评审 r3（WP-02 第三轮）— 配额中断，仅部分结论

> 评审者：codex-cli（consultant 角色，独立于实现者）
> 时间：2026-10-18
> 评审对象：`eb2947c`（WP-02 r2 返工）
> **状态：未完成。** codex 在产出正式判决前再次耗尽配额
> （`try again at 2:50 PM`），因此本轮**没有 ACCEPT/REWORK 判决**。
> 原始会话见 /tmp/codex-r3-out.txt。

## 中断前已独立确认的结论（可用）

1. **r2 的两个变异已被杀死**——「两项 r2 变异现在都会使测试失败，说明对应
   修复有效。」即 `eb2947c` 对 r1/r2 的缺口修复成立。

2. **发现同一缺陷的第三处实例（新增阻断发现）**——原文：

   > 但新探针发现：把 kimi adapter 守卫改成错误归因，或让它追加环境中的
   > 假密钥，27 个相关测试仍全部通过。

   编排者独立复现了这一点（见下），并在 `5dbc0b8` 修复。

3. **`plan check` / `plan lint` 实测输出**（codex 在主仓运行）：
   - `plan check` exit 3：三个 WP 均 `state=IMPLEMENTING (not merged)`，
     `merge NOT detected`，`not converged`。
   - `plan lint` exit 3：仅 `finalize commit x0 (expected 1)`，**无 status-sync
     提交**——r1 的提交纪律发现确认关闭。

   注意 `plan check` 读的是**主仓**的 status 副本（单一真相源），而本迭代的
   status 改动按 §4.3 故意留在工作树未提交，所以它看到的是冻结时的
   `IMPLEMENTING`，并非状态记录错误。

## 未完成、需 r4 补齐的部分

- WP-02 在 `5dbc0b8` 之后的正式判决（r3 的 PRIMARY 任务）。
- 「是否应升级为 CONSULT」的独立判断（AGENTS.md §7，第三轮同根因）。
- brief 口径残留（`f4c4f5a`）与 WP-03 `base_commit`（`9d943b8`）的关闭确认。
- WP-01 / WP-03 的 ACCEPT 是否继续成立。

## 编排者对发现 2 的独立复现与修复

变异证据（`test_adapter_injection.py` + `test_provider_binding.py`，27 例，基线全绿）：

| 变异 | 修复前 | 修复后（`5dbc0b8`） |
|---|---|---|
| adapter 守卫拼接 `os.environ` 里的 key | 27 passed（漏检） | **1 failed** |
| adapter 守卫报错误归因（刻意保留 `openai_base_url` 子串） | 27 passed（漏检） | **1 failed** |

根因与 r1/r2 同形：`pytest.raises(ValueError, match="openai_base_url")` 是子串
断言且无 canary。这条路径更危险——守卫运行时 `_temp_config` 已把真实凭据从
环境读入局部变量。只修 `provider_binding` 等于把弱点搬了个位置，因为不变式是
「这个原因被准确报告且不带凭据」，而非「provider_binding 准确报告它」。

已检查并确认无需改动：`codex.py` 的 `ValueError` 全部属 verdict JSON 解析，
不涉及 base_url 或凭据，不在本 WP 不变式内。`kimi.py:67` 是唯一结构同形处。
