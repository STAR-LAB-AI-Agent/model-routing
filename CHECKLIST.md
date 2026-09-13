# 验收自检清单

对应《智能体开发实战》评分标准（满分 95 + 可选 5）逐项自查。

## 核心功能完成度 (35)
- [x] 基础任务：按任务类型/难度/长度自动路由到合适模型
- [x] **3 类自然语言意图**：① 选模型(route) ② 调用模型(call) ③ 查统计(stats/models)
- [x] 可选功能：**Token / 成本统计展示**（已实现，含 by_model 聚合 + 跨进程 from-log）
- [x] 结果正确、可复现（Mock 模式固定可重现）

## 智能体 + Skill/工具集成 (15)
- [x] 完整链路：自然语言 → Skill → CLI → Router → LiteLLM → 结果
- [x] Skill 说明：SKILL.md（场景/参数/调用/结果格式/2+示例）+ skills.yaml
- [x] Script/CLI 可独立运行（route/call/stats/models）

## 开源项目集成 (10)
- [x] LiteLLM（任务书指定），README 注明名称/版本/许可证(MIT)/使用方式
- [x] 核心能力（多模型统一调用）确由 LiteLLM 支撑

## 用户交互体验 (10)
- [x] 自然语言触发；必要时可指定 --model；结果含"为什么选这个模型"的可解释理由
- [x] 错误提示友好（如未知模型返回结构化错误）

## 安全与异常处理 (10)
- [x] 最小权限：Key 仅环境变量，文件/网络白名单
- [x] 用户确认：无破坏性操作（本 Skill 不删不改文件），故无需确认项
- [x] 敏感信息保护：审计日志白名单字段，不记 prompt/回复/Key
- [x] 异常处理：空模型池降级、未知模型友好报错

## 测试与工程规范 (10)
- [x] **24 个测试用例**，覆盖正常/边界/异常
- [x] README.md、requirements.txt、.env.example、.gitignore、Git 结构、日志、可维护
- [x] 提交前删除 logs/、__pycache__、.pytest_cache

## 低 Token/性能优化 (5)
- [x] 意图识别用确定性 Python 逻辑（不调 LLM）
- [x] 工具返回简洁结构化 + result_preview（不回传全文）
- [x] 统计按需聚合，长文本/大结果由 Python 侧筛选

## 可选功能 (5)
- [x] Token / 成本统计展示（题目对应功能，已完成）
