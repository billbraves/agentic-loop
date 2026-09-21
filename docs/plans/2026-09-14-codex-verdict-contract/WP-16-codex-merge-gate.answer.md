{
  "decision": "ACCEPT",
  "rationale": "该 diff 满足 WP-16 的有界恢复与 fail-closed 契约。首次有效结果立即返回；首次非零退出不重试且脱敏；空输出仅完整重试一次；非空非法输出仅进行一次 structure-only normalization；所有二次结果仍通过既有严格 `_parse_verdict()` 白名单，且不存在第三次调用路径。归一化输入先脱敏、限制为 16 KiB、使用独立 answer 文件，并保持 provider、sandbox、schema 与 reasoning effort 一致。未引入自然语言到决策的映射，也未修改 forbidden paths、测试或信号语义。",
  "findings": []
}
