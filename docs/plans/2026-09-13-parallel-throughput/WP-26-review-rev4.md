# WP-26 rev4 编排者独立复核

> 复核者 claude（编排者，独立复核）| 复核时间 2026-09-17
> 被复核提交 `eea0130`（基线 `57cd572`，diff = 4 个文件 +310/−102）
> 冻结 brief `WP-26-brief-rev4.md` sha256 `b21f97d966a62fb5edeede508fc31798586e5a6eaeddb8d5d6ad8baf30814b16`

## 裁定

**REWORK**

理由一句话：**INV-B 在 bash 消费面上没有被任何用例钉住** —— A2 差分只能识别
「跨进程传路径再重读」这一个旧形态，同进程内的第二次 `open()` 完全逃逸；而这正是
brief 加粗禁止的「降级为静态确认」。python 面合格，bash 面不合格。

## 已达成的部分（复核确认，非转述）

| DoD 项 | 结论 | 证据 |
|---|---|---|
| python 侧单次 `read_bytes`，sha256 与返回内容同源 | ✅ | `redispatch.py` 只有一处 `read_bytes()`，hash 与 `decode` 同取 `raw` |
| python 侧解码失败 → `BriefIntegrityError` | ✅ | 新措辞 `cannot decode brief: …`，与既有 5 条互不相同 |
| bash 侧 section 判据消费已校验字节，不再跨进程传路径 | ✅ | process B 整体删除；`brief_file` 变量与 `sed -n '2p'` 路径交接均已消失（`grep brief_file` 无命中） |
| `brief_file` 消费者逐个交代 | ✅ | 报告列出三个前消费者（`sed -n '2p'` / `[[ -f ]]` / process B），实测全部删除 |
| A1 python 差分方向正确 | ✅ **实测** | 旧实现 `57cd572`：`BriefIntegrityError: brief sha256 mismatch`（FAIL）；rev4：PASS |
| A2 bash 差分方向正确 | ⚠️ 方向对、**强度不足** | 旧实现：`(2, '', "DISPATCH_LINT_FAIL: brief missing section 'Acceptance tests'")` FAIL；rev4 PASS。但见 B35 |
| 重复措辞 #2/#3、#5/#6 已可区分 | ✅ | `(absolute)` / `(fallback)` 已落地，两条用例断言精确首行 |
| bash 8 个出口各有原因特异 witness | ✅ 8 个原枚举出口全覆盖 | #1 status 不可读（shim 删 status）、#2 `..`、#3 `(absolute)`、#4 `(symlink)`、#5 声明路径缺失、#6 `(fallback)`、#7 `cannot read brief`（chmod 0）、#8 sha 不匹配；断言均为首行逐字相等 |
| python 5～6 个出口各有 witness | ✅ | 6 条，断言从子串包含改为逐字相等（本轮顺手收紧，方向正确） |
| C：rev3 四条输出契约 + 5 条 helper 用例 + 拒用理由 docstring | ✅ | `_assert_single_fail_token` 四条约束原文保留，21 处调用；`def test_helper_` 计 5；「刻意不用全局 `len(splitlines())==1`」docstring 原文在 |
| D：`DISPATCH_LINT_SHA256` 常量已删除，改 `live_before` 逐字节自比 | ✅ | 常量与 `_file_sha256` helper 均已删除，`assert DISPATCH_LINT.read_bytes() == live_before` 保留 |
| `preflight.sh` 未被碰 | ✅ | `git diff 57cd572..HEAD -- preflight.sh` = 0 行 |
| 相对基线零回归 | ✅ | targeted 29 → **37 passed**（只增）；全量 3.11 = 4 failed / **634** passed / 4 skipped，4 条失败仍是 `test_finalize_merge_triple_sign.py` 的 `git checkout main` 环境失败，未被修 |
| 3.11 / 3.13 / 3.14 全绿 | ✅（**报告失实，实际比报告好**） | 见「报告偏差」 |

## 阻塞项

### B35：bash 面的 INV-B 只被「旧形态」钉住，同进程二次读取完全逃逸（阻塞）

A2（`test_dispatch_lint_single_read_invariant`）的拦截手法是：用 shim 冒充
`AGENTIC_PYTHON`，在**内层 python 进程退出之后**把 brief 文件改成 EVIL。
因此它能判别的只有一件事 —— 校验与消费**是否跨越了那个进程边界**。
一旦第二次读取发生在同一个进程内，这条用例毫无反应。

实测（scratch 副本，活树未动）：把 rev4 的

```python
text = raw.decode("utf-8")
```

变异为

```python
text = open(real, "rb").read().decode("utf-8")   # 第二次读取
```

即「先按 `raw` 校验 sha256、再重新开文件取正文」—— 这是 INV-B 定义下**同族、同性质**
的缺口（B29 的同进程版本）。结果：

```
python3.11 -m pytest tests/test_dispatch_lint_brief_source.py -q
25 passed
```

**全绿。** 包括 A2 自己。对照 python 面同样的变异：

```
tests/test_redispatch_brief_source.py::test_brief_content_single_read_invariant
AssertionError: expected exactly one read, got 2   → 1 failed
```

python 面钉住的是**读取次数**（`state["calls"] == 1`），所以任何第二次读取都转红；
bash 面钉住的是**进程拓扑**，所以只有恢复成 rev3 那个特定写法才转红。

DoD 第 3 条要求「两个消费面对 brief 的读取调用各 1 次，**报告给出实测计数**」。
报告 bash 一行给的是 `Single open(real, "rb").read() site` —— 这是读代码数出来的静态计数，
brief §A 加粗禁止：「不许把 A1/A2 写成『读代码确认只有一次 open』…静态确认无法阻止
未来重新引入第二次读取」。python 面给了真实计数器，bash 面没有。

**这不是「不可行」，因此也不适用 BLOCKED。** 编排者已实测一条可行的补法（约 25 行）：
用 `PYTHONPATH` 注入一个 `sitecustomize.py`，把 `builtins.open` 包一层计数器
（按 `os.path.realpath` 比对目标文件，macOS `/var`→`/private/var` 已处理），
`AGENTIC_PYTHON` 指向携带该 `PYTHONPATH` 的 shim，让内层进程把命中次数写进一个文件，
用例断言恰为 1。实测结果：

```
real (rev4)  → stdout='BRIEF_OK' reads_of_brief=1
mutated      → stdout='BRIEF_OK' reads_of_brief=2
```

即该补法对上面那个变异**转红**，且不依赖进程拓扑。这只是一种可行解，执行者可另择
（例如把 section 判据抽成接受 `bytes` 的纯函数并单测其签名/调用面），但**必须**做到：
bash 面的判据钉的是读取次数或等价的字节同一性，而不是「process B 是否存在」。

### B36：section 判据的两个出口措辞逐字相同，且其中一个无任何用例（阻塞）

rev4 把 process B 并进 process A，`fail()` 出口从 8 个变成 **10 个**，新增两个：

| 出口 | 触发条件 | 措辞 |
|---|---|---|
| 9 | 标题整段缺失（`re.search` 未命中） | `brief missing section '{heading}'` |
| 10 | 标题在、正文全空 | `brief missing section '{heading}'` ← **与 9 逐字相同** |

实测两条路径的输出（直接跑判据逻辑）：

```
[MISSING-HEADING exit] brief missing section 'Acceptance tests'
[EMPTY-BODY exit]      brief missing section 'Acceptance tests'
```

这与 brief 点名要求修掉的 #2/#3、#5/#6 是**同一类问题**，只是它由本 rev 的合并动作
新产生。brief §B 的要求按不变式读：「每一个出口都要有一条用例，其断言能把失败原因
钉到这一个出口」，并且「若两个出口措辞逐字相同，**必须**在实现里把措辞改成可区分的」。

现状：
- 唯一的 section 用例 `test_brief_missing_section_fails_closed` 用 `_bad_brief()`
  （标题在、正文空），命中出口 10；
- 出口 9（标题整段缺失）**没有任何 fixture**（`_valid_brief` / `_bad_brief` 都带全三个标题）；
- 因为措辞相同，即使补一条用例，断言也无法区分它命中的是 9 还是 10。

要求：给出口 9/10 各补一条可区分措辞（例如 `missing heading` / `empty section body`），
并各配一条 fixture 只触发自己那一个出口。

### B37：五条新增负面用例缺 oracle 第③项（次要，但 DoD 明列）

brief §B 末尾：「每条负面用例带 oracle 三项：① 正向可达性控制 ② 原因特异的 witness
③ **能让它转红的变异**」。本轮新增的五条 bash 用例
（`test_fallback_missing_fails_closed`、`test_cannot_read_status_fails_closed`、
`test_cannot_read_brief_fails_closed`、`test_brief_missing_section_fails_closed`、
`test_dispatch_lint_single_read_invariant`）以及两条新增 python 用例，
均无 `copytree` scratch 变异（`grep -c 'copytree\|mutated'` = 0）。

①②具备（fixture 只触发单一出口、断言逐字相等、同形状合法输入另有绿用例）。缺的是③。
注：A1 的 `state["calls"] == 1` 天然对「多读一次」敏感，编排者已实测其转红；但
DoD 要求变异证据落在用例集里，而不是靠复核者临时构造。

## 报告偏差（非代码缺陷，但须纠正）

报告称：

> Full 3.13 / 3.14: not runnable — python3.13/python3.14 report No module named pytest

不成立。brief 给的运行形态是 `uv run --quiet --python 3.1X --with pytest --no-project
python -m pytest`，执行者用了裸 `python3.13`。编排者按 brief 形态实测：

```
3.13 → 37 passed
3.14 → 37 passed
```

即 DoD「3.11 / 3.13 / 3.14 全绿」**实际满足**，报告低估了自己的成绩。这属于
「未按 brief 给定命令形态执行并据此下结论」，返工时请按 brief 形态复测并如实记录。

## 合并门（三项，当前一项不成立）

1. 编排者独立复核 = **REWORK**（B35/B36 阻塞）
2. codex 第二签名 —— 未取，本轮不必取（一审已 REWORK）
3. 用户批准 —— 未取，且现在不应取

## 给 rev5 的范围提示（编排者备忘，非本文件裁定）

本轮是 WP-26 的第 4 次 re-freeze。任务 #24 的规则针对「第 3 次」，rev4 已按规则做过
停手复核。B35 不是新一环链条，而是**同一环的强度问题** —— rev4 修对了实现，
但 bash 面的判据没有跟上实现的抽象层次。rev5 的标的应当是「判据钉读取次数」这一条，
范围不再扩大，`preflight.sh`（B22 / 任务 #27）依旧不许碰。
