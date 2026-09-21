# B47 实测：段落门禁从未读过任何 revN brief

> 编排者 claude｜2026-09-18｜read-only 测量，不改任何门禁
> 起因：WP-28 rev5 的 `agentic preflight` 报 `PREFLIGHT_PASS`，
> 但它校验的段落不是 rev5 的段落。

## 缺陷

`src/agentic_loop/wrappers/dispatch_lint.sh:60`：

```sh
brief_file="$iterations_dir/$iteration_id/${work_package_id}-brief.md"
```

brief 路径由 `iteration_id` + `work_package_id` 拼出，**完全不读 `evidence.brief.path`**。
该脚本里 `evidence` 一词只出现在这一处拼接的上下文之外 —— 即从未出现。

于是 re-freeze 一旦落在 `WP-N-brief-revM.md`，段落门禁读的仍是 `WP-N-brief.md`。

## 实测范围（全 plan 22 个 WP）

对每个 WP 比较「门禁按固定名读到的文件」与「`evidence.brief.path` 指向的冻结文件」：

| 结果 | 数量 |
|---|---|
| 门禁读的**不是**冻结 brief | **18 / 22** |
| 二者一致 | 4 / 22 |

4 个一致的情形都不是门禁做对了，而是**规范名恰好持有冻结内容**：
WP-23 / WP-29 冻结的就是规范名本身（无 revN）；WP-22 / WP-24 曾把 revN 内容
覆盖到规范名上（两者 sha256 完全相同）。

## WP-28 的具体表现

| | |
|---|---|
| 门禁读到 | `WP-28-brief.md`，sha256 `24dc48cf…`，14215 bytes |
| 该文件实为 | rev1（与 `WP-28-brief-rev1.md` sha256 完全相同） |
| 冻结的是 | `WP-28-brief-rev5.md`，sha256 `d96a7fa3…` |

标题即可看出差异：

```
门禁读: # WP-28: 把两条编排规范从任务列表落成机械可检的模板条目（INV-N）
冻结:   # WP-28 (rev5): 变异必须施加于判据真实的输入面，并证明用例杀得掉自己的 fix
```

**五轮冻结，段落门禁一次都没看过 rev2–rev5。** 它一直在校验 rev1 的段落是否齐备。

## 严重性

不是 false green 意义上的逃逸 —— 三个必需段落（`Acceptance tests` /
`Allowed and forbidden paths` / `Completion definition`）在 rev1 里确实都在，
所以 PASS 本身没说谎，它只是**答了另一张卷子**。

真实风险是门禁的保护完全失效：若某个 revN brief 漏段（我在 WP-25 rev2 上真的犯过，
见任务 #28），门禁照样 PASS，因为它读的是那份齐备的 rev1。这类缺陷的特征是
**平时无症状，恰在需要它的那一刻不生效**。

## 修法方向（不在本次范围）

`brief_file` 应优先取 `evidence.brief.path`（存在则用，且须校验其 sha256 与
`evidence.brief.sha256` 一致），仅在缺该字段时回落到固定命名。回落分支须显式记录，
避免又一个「校验被回落分支跳过」（同 B21 的形状）。

顺带：`preflight.sh` 对 status 的多次独立 `open`（B22 / 任务 #27）与本项同族 ——
判定面与消费面分离。建议合并为一个「门禁读的必须是它声称要读的那一份」WP。
