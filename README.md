# AI 模型智能路由 (ai-model-router)

> 《智能体开发实战》课程实验 · 第 **25** 题：**AI 模型智能路由**
> 自然语言 → 智能体 → Skill → Python Script/CLI → LiteLLM → 多模型结果

根据任务的自然语言描述，自动判断**任务类型 / 难度 / 长度**，把请求路由到最合适的 LLM（GPT / 通义千问 / DeepSeek 等），并统计**耗时、Token、成本**。

---

## ✨ 特性

- **3 类自然语言意图**：① 选模型（路由）② 调用模型（call）③ 查统计（成本/Token）— 全部可直接用中文自然语言触发。
- **真实开源项目集成**：基于 **LiteLLM** 统一调用多家 LLM（任务书指定），README 中注明了项目名 / 版本 / 许可证 / 使用方式。
- **离线可运行**：未配置 API Key 时自动降级为内置 `MockProvider`，**保存即可运行、测试、演示**，无需任何 Key。
- **统一 Skill + Script 接口**：`SKILL.md` + `skills.yaml` + CLI，可被 **nanobot / 任意 Agent Runtime** 以子进程方式加载调用。
- **低 Token**：意图识别用确定性 Python 逻辑；工具返回简洁结构化；审计日志只记脱敏字段。
- **安全**：Key 仅读环境变量，不进代码/日志/仓库；文件/网络最小权限；无破坏性操作，无需确认。

---

## 📁 项目结构

```
ai_model_router/
├── run.py                  # 主运行/演示脚本（nanobot 可直接 import handle）
├── router/
│   ├── __init__.py
│   ├── core.py             # 路由引擎：模型池、打分、调用、统计
│   ├── adapters.py         # LiteLLM 真实模型适配器（可选）
│   ├── cli.py              # CLI/Script 入口（route/call/stats/models）
│   ├── config.py           # 模型池配置 + 环境变量
│   └── logger.py           # 脱敏审计日志
├── skill/
│   ├── SKILL.md            # Skill 定义（nanobot 加载）
│   └── skills.yaml         # nanobot skills 注册
├── tests/
│   ├── conftest.py
│   └── test_router.py      # 测试用例（正常/边界/异常）
├── .env.example             # 脱敏配置模板（勿提交真实 Key）
├── .gitignore
├── requirements.txt
└── README.md
```

---

## 🚀 快速开始

### 1. 环境准备
```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env       # 默认 USE_MOCK=1，离线即可跑
```

### 2. 三种运行方式

**A. 命令行交互**
```bash
python run.py
# 你 > 用一段话解释相对论
# 你 > route: 请证明费马小定理        ← 前缀控制：仅路由
# 你 > stats                          ← 查统计
```

**B. CLI 直调（Skill/Script 统一接口）**
```bash
python -m router.cli route  "解释相对论" --json
python -m router.cli call   "解释相对论"
python -m router.cli call   "分析这张图片内容" --model gpt-4o
python -m router.cli stats  --json
python -m router.cli models
```

**C. 作为模块被 Agent Runtime 调用**
```python
from run import handle
print(handle("解释相对论"))          # 自动路由 + 调用
print(handle("route: 证明费马小定理")) # 仅路由决策
print(handle("stats"))              # 统计
```

### 3. 启用真实模型（可选）
在 `.env` 中填任一 Key 并设 `USE_MOCK=0`：
```bash
export OPENAI_API_KEY=sk-xxx        # 或 DASHSCOPE / DEEPSEEK
export USE_MOCK=0
python run.py "用强模型推理一个复杂问题"
```

---

## 🔌 在 nanobot 中加载

nanobot 读取 `skill/skills.yaml`，通过 `script: python -m router.cli` 以子进程调用，
每个 `command` 对应一个子命令，`${task}` / `${model}` 由 runtime 从 Skill 参数注入。
无需开发 MCP Server，纯 Skill + Script/CLI 轻量集成。

---

## 🧪 测试

```bash
pytest tests/ -v -s
# 或直接
python tests/test_router.py
```
覆盖：3 类意图理解、路由打分、调用/统计/成本、CLI 独立运行、脱敏日志、离线降级 等 **20+** 用例。

---

## 🔐 安全 & 低 Token

- **最小权限**：Key 仅环境变量；文件系统仅项目内 + `./logs`；无任意代码执行。
- **敏感信息保护**：审计日志白名单字段，绝不记 prompt / 回复 / Key。
- **低 Token**：Python 侧做意图识别与打分；返回值仅摘要；统计按需聚合。

## 📄 开源依赖与许可

| 项目 | 用途 | 许可证 |
|------|------|--------|
| [LiteLLM](https://github.com/BerriAI/litellm) | 统一调用多家 LLM | MIT |

---

实验报告、演示视频、测试数据见各课程提交材料要求另行补充。
