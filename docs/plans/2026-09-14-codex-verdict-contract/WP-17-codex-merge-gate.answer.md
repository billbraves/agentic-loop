{
  "decision": "ACCEPT",
  "rationale": "该 diff 在 allowed_paths 范围内实现了 WP-17 的配置隔离、按文件/hunk 边界分块、每块复用 WP-16 有界恢复，以及保守 fail-closed 聚合。命令契约标志与 provider 注入保留，key 值不入 argv；分块只切分不重写 diff，无法继续切分或单块仍超限时抛错而非截断。聚合依据 `_parse_verdict` 白名单的严重度顺序实现 REWORK > CONSULT > ACCEPT，未引入自然语言映射，任一块失败会向上抛出。未发现阻塞性的正确性、架构、时间/时点、迁移或安全问题。",
  "findings": [
    "`--ignore-user-config` 已覆盖 review 路径与 probe_injection 路径，且保留 `-c` 注入、`--sandbox read-only`、`--skip-git-repo-check`、effort、`--output-schema`、`-o` 等既有契约，key 值不进入 argv。",
    "分块先按 `diff --git` 文件边界，单文件超限再按 `@@` hunk 边界二次切分；每块只包含自身 diff，未截断或改写 diff 内容。",
    "聚合通过 `_parse_verdict` 白名单的严重度降序确定性选出整体裁决，REWORK > CONSULT > ACCEPT，并合并 findings 与 rationale；任一块无合法 verdict 会由 `_review_single` 抛错，绝不降级为 ACCEPT。",
    "每块使用独立临时目录和独立 answer 文件，复用 WP-16 的空输出重试/归一化恢复逻辑；全局文件清单摘要仅作只读上下文。",
    "新增测试为离线确定性 fake 可执行，覆盖隔离标志、阈值下界、文件分块、保守聚合、失败抛错、WP-16 恢复与静态 killer；未发现 forbidden_paths 或越界改动。",
    "非阻塞观察：多 hunk 正向二次切分的成功路径未单独断言，但现有超限失败用例与实现逻辑未暴露缺陷。"
  ]
}
