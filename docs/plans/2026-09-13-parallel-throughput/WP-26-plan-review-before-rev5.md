# WP-26 第 4 次 re-freeze 强制停手复核（rev5 前置）

> 复核者 claude-code（编排者，计划面自审）| 2026-09-18
> 规则来源：`WORK_PACKAGE.md.tmpl:9`「第 3 次**及以后** re-freeze：冻结前必须停手复核计划，
> 未经用户批准不得冻结。」
> 前序：`WP-26-plan-review-before-rev4.md`（第 3 次，任务 #30 的首次实弹）。本文件是第 4 次。

## 1. 规则命中确认

`WP-26.status.json`：`state = CHANGES_REQUESTED`，`evidence.refreeze_count = 3`
（口径 = brief rev 号），`refreeze_stop_rule_check.fires = true`。rev5 是 rev4 之后的又一次
冻结，规则「第 3 次及以后」**连续命中**。被复核提交 `eea0130`（rev2 实现 `0b4deb2`）。

## 2. 五轮是不是同一个根因

是。而且 rev4 的阻塞项与 rev3 的属于**同一个判别力缺口的两个消费面**。

| 轮次 | 阻塞项 | 根因归属 |
|---|---|---|
| rev2 | scope/risk 差分方向 | 执行者 + brief 措辞 |
| rev3 | B29 跨进程二次读取 | 判据设计不足 |
| rev4 | **B35** bash 面只钉进程拓扑不钉读取次数、**B36** 出口 9/10 措辞逐字相同、B37 五条新增负面用例缺 oracle ③ | **编排者 brief 缺陷**（B35）+ 本轮合并动作新产生（B36） |

B35 的病与 WP-25 的 B38 **同型**：INV-B 写的是「验证的字节与消费的字节必须是同一次读取
的同一份快照」（覆盖同进程二次读取），但修法清单只点名了 rev3 那个**跨进程**形状，
执行者照清单把 process B 并进 process A 就交付了 —— 不变式够宽，清单收窄，
执行者照清单做就够不着不变式。

python 面没犯这个错，是因为它的判据天然钉**读取次数**（`state["calls"] == 1`）；
bash 面用 shim 在内层进程退出后投毒，钉的是**进程拓扑**，所以只有恢复成 rev3 的写法才转红。
**同一个不变式，两个消费面的判据强度不同** —— 这是 brief 没有对两面提出同一条量化要求。

## 3. 我这一轮的计划面失误

### 失误 1：我给出的修法方向这轮已实测，但 rev4 的 brief 从未要求「可实测的读取计数」

rev4 的 DoD 第 3 条写的是「两个消费面对 brief 的读取调用各 1 次，**报告给出实测计数**」。
执行者 bash 面给的是 `Single open(real, "rb").read() site` —— 一个**静态**计数。
brief §A 确实加粗禁止静态确认，但 DoD 第 3 条的措辞「报告给出实测计数」允许被理解成
「报告里写出一个数」，而没有要求**该计数由用例在运行时采集并断言**。措辞漏洞在我这边。

rev5 的 DoD 必须写成：**判据在运行时采集读取次数并在用例内断言恰为 1；静态数人工读码
不算证据；且该断言不得依赖进程拓扑（同进程二次读取必须转红）。**

### 失误 2：把「两个消费面」当成两个交付项，而不是同一不变式的两次兑现

rev3 的复核已记过一次「兄弟消费面没有在同一 WP 内收口」（`before-rev4.md` §3 失误 3），
rev4 又在同一处栽了一次 —— 上一轮我只要求**两面都有用例**，没要求**两面的判据钉同一个量**。
rev5 的 brief 要把这一条写成对称要求，并在自检里对**两面施加同一个变异**（同进程二次读取），
要求两面都转红。

### 失误 3：B36 是我本轮合并动作的副产物，但它暴露的是一条通用规则没进 brief

rev4 把 process B 并进 process A，`fail()` 出口从 8 增到 10，新增出口 9（标题整段缺失）
与出口 10（标题在、正文全空）**措辞逐字相同**，且出口 9 无任何 fixture。
这与 rev3 点名修掉的 #2/#3、#5/#6 是同一类。规则本身（每个出口一条用例 + 措辞可区分）
在 brief §B 里有，但**没有把「本轮新增/合并产生的出口同样受此约束」写明**，
于是重构新引入的出口逃过了该规则。rev5 的 brief 要把它写成对出口集合的**闭包要求**：
出口数变化时，新增出口一并受约束，且报告须给出出口清单前后对比。

## 4. 两个消费面的实测确证（编排者本轮独立复现，不采信任何一方转述）

修法可行性我这轮重新实测，不沿用 rev4 复核里的转述。

**做法**：`PYTHONPATH` 注入 `sitecustomize.py`，把 `builtins.open` 包一层计数器，按
`os.path.realpath` 与目标 brief 比对（macOS `/var`→`/private/var` 已由 realpath 处理），
命中则往 sink 追加一行；`AGENTIC_PYTHON` 指向携带该 `PYTHONPATH` 的 shim。
被测对象是 `wp26-brief-source-of-truth` 活树的 `dispatch_lint.sh` **副本**（活树未改）。

**变异**：在 `raw = open(real, "rb").read()`（`dispatch_lint.sh:123`）之后插入一行
同进程二次读取。变异前后脚本 `cmp` 不同，探针带 no-op 守卫（`cmp -s` 相同则报错退出，
记忆 `mutations-must-assert-they-changed-something`）。

**结果（绿路径，两侧 stdout 相同，只有计数不同）**：

```
real       reads_of_brief=1   out=DISPATCH_LINT_PASS
mutated    reads_of_brief=2   out=DISPATCH_LINT_PASS
```

两点要记：

1. **两侧 stdout 完全相同** —— 这恰好证明 rev4 的用例为什么全绿：从外部行为看不出差别，
   只有读取计数能区分。任何靠 stdout / 退出码判别的用例对这个变异天然无感。
2. 该计数**不依赖进程拓扑** —— 计数器在解释器内，二次读取无论发生在哪个进程都被记到。

中途一处偏差如实记录：第一版探针用合成 fixture，因 brief 路径按主仓根解析而非 fixture 目录，
两侧 `reads_of_brief=0`（`brief not found`）—— 即**探针当时什么也没测到，两侧同样"绿"**。
把 fixture 做成真 git 仓 + `.agentic/config.toml` 后才拿到上面的分离结果。
这本身是 `your-own-probe-needs-a-noop-guard` 的又一个实例：计数为 0 必须当失败看，不是通过。

## 5. rev5 的范围裁定（本次复核的决定）

**收窄。** rev5 只做三件事：

1. **B35**：bash 面的 INV-B 判据改为**运行时读取计数断言恰为 1**（或等价的字节同一性断言），
   不得依赖进程拓扑。自检必须包含「同进程二次读取」变异，且**两个消费面都对该变异转红**。
   上节的 `sitecustomize` 计数器是一种可行解（已实测），执行者可另择，但量化要求不可降。
2. **B36**：出口 9 / 10 各给可区分措辞（例如 `missing heading` / `empty section body`），
   各配一条只触发自己那一个出口的 fixture；报告给出改前/改后的出口清单对比。
3. **B37**：五条新增 bash 负面用例 + 两条新增 python 用例补 oracle 第 ③ 项
   （能让它转红的变异），变异要落在用例集里，不靠复核者临时构造。

**不做**：不重构 `dispatch_lint.sh` 的其余出口；不扩 `allowed_paths`；不碰 python 面已达标
的 `state["calls"] == 1` 判据（它已是正确形态，rev5 只让 bash 面对齐它）。

## 6. 报告习惯的纠正（两个 WP 共有）

rev4 报告称 `python3.13 / python3.14 均无 pytest 模块`。本仓标准跑法是
`uv run --quiet --python 3.1X --with pytest --no-project python -m pytest`，不污染环境。
rev5 的派发提示里要写明正确形态（WP-25 rev5 同此）。

## 7. 门

- 本文件是 rev5 冻结的**前置**，规则要求**未经用户批准不得冻结**。
- 待办：用户批准后方可写 `WP-26-brief-rev5.md` 并派发。
- 本文件不改 `WP-26.status.json` 的 `state`（仍 `CHANGES_REQUESTED`）。
