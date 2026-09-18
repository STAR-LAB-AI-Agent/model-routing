---
name: ai-model-router
description: 根据任务类型、难度与长度在 DeepSeek 真实模型之间路由，处理问答、摘要、代码与推理，返回选型、答案、耗时、Token 和估算费用；支持路由预览与统计。
---

# AI 模型智能路由

执行本目录 scripts/router.py。整个目录可复制到 nanobot workspace/skills/ai-model-router。优先使用工作区 .venv/Scripts/python.exe（Windows）或 .venv/bin/python；需安装 LiteLLM 1.101.0。脚本的模型、配置与库均使用相对 Skill 路径。

## 流程

1. 确定完整任务与材料；“帮我总结”没有原文时先询问材料。
2. 仅选择模型用 plan，执行任务用 run，查询历史用 stats。
3. 所有生成都是真实 DeepSeek API。用户已授权当前任务的外发与费用时设 confirm_live=true；否则先 plan 并告知模型和预算。沿用会话已有授权，不重复询问。
4. 密钥经网页 API 配置、交互式 configure_key.py 或服务端环境变量配置。不要读取并显示密钥，也不要放入调用参数、输入 JSON、shell 命令。
5. 使用 UTF-8 stdin JSON。复杂文本通过 Runtime 文件工具写到工作区，再从文件输入；禁止把用户原文未经转义拼入 shell。
6. 读取 ok 和 error；成功后返回答案、选型依据、用量来源、估算费用与缓存状态。incomplete=true 表示输出预算耗尽，需说明结果不完整。

## 统一接口

```text
python <skill-dir>/scripts/router.py plan|run --json-stdin
python <skill-dir>/scripts/router.py stats
python <skill-dir>/scripts/router.py doctor
```

输入：prompt 非空字符串、最多24000字符；preference=balanced/cost/quality，默认balanced；max_tokens=64–8192，默认2048，包含思考Token；use_cache 默认true；confirm_live 默认false。mode 如提供只能是 live。请求不能覆盖端点、路径或密钥。

输出：ok、route（tier/model/thinking/类型/难度/原因）、answer、input_tokens、output_tokens、usage_source、provider_cache_hit_tokens、cost/cost_source、currency、latency_ms、model_latency_ms、cache_hit、provider_calls、finish_reason、incomplete。未知用量或费用为 null；不得解释为0。脚本 stdout 单个 JSON；退出码0成功、1业务错误、2参数错误。

## 示例

用户已授权：“用真实模型一句话解释机器学习。”

```json
{"prompt":"用一句话解释机器学习。","max_tokens":256,"confirm_live":true}
```

run --json-stdin，预计 eco：deepseek-flash，关闭思考。

用户已授权：“请总结会议内容，用真实模型处理：需求完成，周五验收。”

```json
{"prompt":"请总结：需求完成，周五验收。","max_tokens":256,"confirm_live":true}
```

run --json-stdin，预计 balanced：deepseek-v4-pro，关闭思考。

用户：“Python 实现二分查找，先看路由。”

```json
{"prompt":"Python 实现二分查找并分析复杂度。","max_tokens":2048}
```

plan --json-stdin，预计 reasoner：deepseek-v4-pro，开启思考；不调用生成接口。

## 约束

两个模型、三个参数档位，不能描述为三个独立模型。路由不调用分类模型。预算估算采用字符启发式，生成用量取自服务响应；费用按官方配置估算，以服务商账单为准，不包含 nanobot 自身编排费用。

固定官方端点 https://api.deepseek.com。超时120秒、额外重试0次。服务失败不返回预设答案；不执行生成的代码。缓存128条、TTL10分钟，仅当前进程；密钥变化隔离缓存，失败与不完整输出不缓存。审计只有哈希和元数据，正文只驻留内存；nanobot 自身会话可能保存正文。
