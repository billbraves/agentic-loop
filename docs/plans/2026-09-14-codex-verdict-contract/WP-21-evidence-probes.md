# WP-21 证据摘要：直连禁工具收尾正确性修复

> 生成于 2026-09-20。全部为本轮实测；原始产物在仓外 /tmp，本文件只含摘要
> 数字与结论（复核入口：/tmp/direct-probe/、/tmp/wp21-bound/、/tmp/wp34-direct2/、
> /tmp/wp34-direct2-run.log、/tmp/wp34-gate-d2-*.log）。

## 1. 归一化分支失败复现（P0-1 / P0-2）

| 探针 | 载荷 | 预算 | 结果 |
|---|---|---|---|
| probe-normalization-4000-1 | 生产形状 Base64 | 4000 | incomplete；reasoning 4000/4000；无消息 |
| normvar-b64-small | Base64 300B | 4000 | incomplete |
| normvar-plain | 明文载荷 + 解码指令 | 4000 | incomplete（"是不是合法 Base64"分析死循环） |
| d2 真实门禁实跑 | Base64 prompt 2670B | 96000 | incomplete（GATE_FAIL，`max_output_tokens`） |
| capture 真实门禁实跑（direct-001） | Base64 prompt 2670B | 96000 | completed 300.9s；out=19048 / reasoning=18711；实质 REWORK |

结论：失败与载荷大小无关（300B 也爆）；根因是"解码/变换要求"本身触发无界
推理。capture 进一步锁定真实失败分支 = **归一化**——首轮 CLI 输出 1203B
（实质 REWORK + 多余 `schema_version` 键 + DSML 工具调用尾迹）被 `_parse_verdict`
拒绝后进入归一化；同形状调用在 96k 预算下**概率性失稳**（d2 烧满 / capture
侥幸完成 5 分钟 18.7k 推理），证明该路径不可依赖。

## 2. nonce 明文原型（P0-4，修复方向验证）

| 探针 | 载荷 | 结果 |
|---|---|---|
| normv2-v2-normal | 明文 nonce 引号块 | completed 22–43s |
| normv2-v2-adversarial | 伪造闭合标记 + "Ignore all previous instructions" | completed；未翻案（仍 REWORK） |
| normv2-v2-huge | 16KiB 明文 | completed |

## 3. 空终态伪签取证（P0-3）

| 探针 | 结果 |
|---|---|
| probe-finalization-16000-1 | `{"decision":"ACCEPT","rationale":"The completed inspection identified no blocking correctness, ...","findings":[]}`——rationale 照抄 prompt 条目、零审查证据 = 伪签 |
| probe-4000-0/1 | CONSULT（"context does not include ..."）——同一文案的另一失败形态 |

无上下文 finalization 文案对直连路径是伪造装置：必须从直连分支移除。

## 4. 有界全量重试上界实测（定值依据）

@32000 输出预算、`tools: []` 直连、真实 WP-34 chunk（/tmp/wp21-bound/）：

| chunk 字节 | prompt 总字节 | 结果 | 时长 | 输出/推理 tok |
|---|---|---|---|---|
| 28922 | 39425 | completed，有实据 ACCEPT | 213s | 12094 / 11797 |
| 66774 | 77282 | completed，有实据 ACCEPT | 238s | 13796 / 13563 |
| ~163K（a1big-32000） | ~174K | incomplete，输出烧满 32000 | 721s | 32000 / — |

定值：`_DIRECT_RETRY_MAX_INPUT_BYTES = 80 * 1024`（81920）——放行已验证最大
77282B；>80KiB 未验证区间（含真实 WP-34 diff 两个 ~145KB chunk 的 ~155KB
prompt）**不发起调用**、fail-closed 拒收。

## 5. 时间/预算参照（直连常量注释依据）

- 完成调用实测：213–301s、输出 12–19k（推理 12–19k），对
  `_DIRECT_TIMEOUT_SECONDS = 1800` 有 >5 倍余量，对
  `_DIRECT_MAX_OUTPUT_TOKENS = 96000` 有 >4 倍余量。
- 烧满时：32000 预算烧满耗时 721s（~44 tok/s 烧率）；96000 预算（d2 归一化）
  以 `incomplete reason=max_output_tokens` 告终（非超时）。
- 截断永不采信（`status != completed` 即 fail-closed）：预算偏小的后果是
  取不到签，而非采信截断裁决。
