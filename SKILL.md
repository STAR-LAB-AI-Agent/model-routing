---
name: ai-model-router
version: 1.0.0
description: >
  AI 模型智能路由 Skill。根据用户任务的自然语言描述，自动判断任务类型、
  难度与长度，将请求路由到最合适的 LLM 模型（GPT / 通义千问 / DeepSeek 等），
  并统计耗时、Token 与成本。基于 LiteLLM 统一调用，支持真实 Key 与离线 Mock 双模式。
author: AI智能体项目实习 - 第25题
license: MIT
runtime: nanobot
entrypoint: python -m router.cli   # Script/CLI 入口（可被 Agent Runtime 直接调用）
---

# AI 模型智能路由 (ai-model-router)

## 使用场景 (When to use)
当用户提出以下意图时使用本 Skill：
1. **「帮我选模型 / 哪个模型合适」**：根据用户任务复杂度推荐最经济/最合适的模型。
2. **「用模型处理 X / 帮我调用模型」**：需要真正发起一次模型调用并拿到结果。
3. **「统计 / 成本 / 用了多少 Token」**：查询本次会话的调用统计、成本与延迟。

## 参数 (Parameters)
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `task` | string | 是 | 用户的自然语言任务描述（路由 + 调用时都需要） |
| `model` | string | 否 | 手动指定模型名（见 `models`），省略则自动路由 |

## 调用方式 (Invocation)
本 Skill 通过统一的 **Script/CLI** 暴露能力，nanobot 等 Agent Runtime 以子进程方式加载调用：

```bash
# 1) 仅路由决策（不消耗真实模型调用，推荐先做意图确认）
python -m router.cli route "<用户任务>"

# 2) 路由 + 真实调用
python -m router.cli call "<用户任务>"

# 3) 手动指定模型（跳过自动路由）
python -m router.cli call "<用户任务>" --model gpt-4o-mini

# 4) 结构化输出（供 Agent Runtime 解析）
python -m router.cli call "<用户任务>" --json

# 5) 查看统计 / 模型池
python -m router.cli stats --json
python -m router.cli models
```

## 结果格式 (Result Format)
所有命令支持 `--json`，返回简洁结构化对象（**不**回传完整 prompt，低 Token）：

```json
{
  "selected_model": "gpt-4o-mini",
  "reason": "任务类型=simple_qa, 难度=1 ...",
  "scores": {"gpt-4o-mini": 35.7, "deepseek-chat": 33.0}
}
```

`call` 命令额外返回 `tokens`、`cost_usd`、`latency_ms`、`result_preview`。

## 示例 (Examples)
### 示例 1：简单问答 → 路由到便宜快速的模型
```
用户: "用一段话解释相对论"
→ route → 任务类型=simple_qa, 难度=1 → 选中 gpt-4o-mini
```

### 示例 2：复杂推理 → 路由到能力更强的模型
```
用户: "请逐步推理并证明费马小定理"
→ route → 任务类型=reasoning, 难度=3 → 选中 gpt-4o
```

### 示例 3：长文本 → 路由到大上下文模型
```
用户: 粘贴 3000 字文档并要求总结
→ route → 任务类型=long_context → 选中 qwen-max (1M 上下文)
```

## 安全与权限 (Security)
- 模型 API Key **仅**从环境变量读取（`OPENAI_API_KEY` / `DASHSCOPE_API_KEY` 等），
  不写入代码、不进入日志、不随仓库提交（见 `.env.example`）。
- 审计日志仅记录脱敏字段（模型名、Token 数、耗时、成本），不记录 prompt 与回复全文。
- 默认目录白名单：仅在本项目目录内读写；不执行任意用户代码。
- 离线环境自动降级为 MockProvider，无需 Key 即可完整运行与演示。

## 依赖 (Dependencies)
- Python 3.10+
- `litellm`（可选，有真实 Key 时使用）
- 其余为标准库，见 `requirements.txt`
