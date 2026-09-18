# 任务书与实现对照

依据课程任务书第4页题目25、第5–7页通用要求。

| 要求 | 实现与证据 |
|---|---|
| 难度、长度、类型路由 | policy.py；十条test-cases.json |
| 多模型 | Flash、Pro两个真实模型；三个能力档位 |
| 耗时、Token、成本 | usage+实测计时+官方费率估算；evaluation.json |
| 至少三类意图 | 问答、摘要、代码/推理；真实API评估与录屏 |
| 真实开源Python项目 | LiteLLM 1.101.0实际completion调用；许可原文 |
| Skill + Script | skills/ai-model-router完整可移植目录 |
| nanobot加载调用 | SkillsLoader+ExecTool真实调用证据 |
| 独立CLI与JSON | router.py plan/run/stats/doctor |
| 5–10测试样例 | examples/test-cases.json十条；另有细化pytest |
| 低Token优化 | 规则不调模型；三次重复请求命中本地缓存 |
| 安全日志、确认 | 哈希审计、固定官方端点、confirm_live及网页执行提示 |
| 动态API配置 | 页面密码框、加密保存、立即生效、模型列表连接测试 |
| 可选统计看板 | 请求、实际调用、缓存、新增用量、费用估算 |
| 源码、依赖、README | 完整仓库与requirements-lock.txt |
| 报告与视频 | deliverables/实验报告.pdf、demo.mp4（<60秒） |
| 脱敏配置 | models.json公开费率；密钥存runtime并排除提交 |

验证边界：真实API调用、Runtime工具接口和本地功能已验证；未声称付费账单对账、普遍模型质量或自主Agent规划准确率。
