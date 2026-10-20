# WP-02 round 5 独立复核证据

审核对象：`b01dfd21cc1de2ef81af0b2c416b2e0d6c66a436`。
实际工作树 HEAD：`5a34ec0`；与审核对象之间只有 PLAN 和旧 r5 中断记录两份文档变化，源码、测试、配置一致。

- `pbv-r5-mutate.py`：从指定提交 `git archive` 导出临时副本，逐个修改并恢复；每条替换要求唯一命中；使用合成 canary。覆盖 r1-r4 全部历史 guard/消息/fixture mutation，以及 WP-01/03 的反向验证。
- `pbv-r5-before.py`：对 `b01dfd2^` 运行四个 r4 mutation，均为 27 passed，确认修复前存活。
- `pbv-r5-extra.py`：fixture 自检、参数表接线、非字符串假值和 URL 边界实测；也复核 WP-03 live evidence 中不同写法的 mutation。
- `logs/`、`before-logs/`：每项完整 pytest 输出；摘要分别在 `pbv-r5-mutations.log`、`pbv-r5-before.log`、`pbv-r5-extra.log`。
- `pbv-r5-gates.json`：从主仓运行的只读 plan check/lint 与 autonomy 查询，含实际 exit code。
- `metadata.json`：提交、命令及 mutation 环境。

## 已确认的范围与计数

重点模块 control：31 passed。r4 binding 放行空串、binding 空串错误原因+key、adapter 放行空串、adapter 空串错误原因+key：2/2/1/1 failed。

历史 mutation：r1 无关原因+假密钥 6；正确原因+环境密钥 6；r2 错误原因 3；仅缺省时泄漏 2；仅 present None 泄漏 2；仅 present 字段泄漏 4；恢复旧 adapter 校验集合 7；删除 adapter 守卫 2；r3 adapter 泄漏/错误原因各 2。两个旧 fixture 分别 1/2 failed。

codex-only 错误原因+泄漏：31 passed，既有非 kimi 范围债务仍存活。

fixture 自身空串改 None：1 failed / 30 passed；仅将 declared_empty 参数表项改接到 None fixture：31 passed；删除该表项：29 passed。自检有效但只保护 fixture 本身，不能证明整个参数矩阵未退化。

两守卫缩窄为只拒绝 None/空字符串：31 passed。说明不能宣称覆盖任意 Python 假值；冻结范围中的 str | None + 字段缺省覆盖已补齐。

当前生产代码对 None、空字符串、0、False、[]、{} 均拒绝；对空白字符串、带首尾空格的 URL、裸 host 均接受，后者不属于此缺值 guard 的 URL 格式验证职责。

WP-01：宿主默认分支 master/review-unusual 均 5 passed，恢复裸 git init 各 4 failed。WP-03：26 passed，精确恢复旧列表包裹 5 failed；live evidence 使用的直接下标变体 6 failed，二者不是同一 mutation。

## 操作边界

审核者未修改仓库文件、状态或 Git 历史，未执行 finalize/merge/push，未联网探测真实 provider。
本目录是交接用临时证据，应由编排者将报告和证据归档到迭代目录，并在 finalize 提交中记录本轮独立签署。不得将先前 quota-aborted r5 误作本轮判决。

## 全套测试结果

命令：`python3.11 -m pytest tests -q`，在指定工作树执行。进程退出码：0。

```text
....................................................................     [100%]
928 passed, 4 skipped in 167.14s (0:02:47)
```
