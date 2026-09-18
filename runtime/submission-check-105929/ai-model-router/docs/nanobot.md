# nanobot 接入与验收

安装版本 nanobot-ai 0.3.5。项目根目录作为workspace，skills/ai-model-router为完整可发现技能，解释器使用项目内.venv。

## 已验证的 Skill + Script 真实调用

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-nanobot.txt
.\.venv\Scripts\python.exe scripts\verify_nanobot.py
```

先在网页保存DeepSeek密钥。验证脚本实际创建SkillsLoader，读取Skill，再由工作区受限ExecTool运行独立CLI，调用DeepSeek Flash生成回答。该命令会产生一次真实生成费用，结果写artifacts/nanobot-verification.json。不要把这项工具接口校验描述成自主规划质量测试。

## 完整自然语言编排

`scripts/run_nanobot.py`读取已保存密钥，仅注入子进程环境变量NANOBOT_PROVIDERS__CUSTOM__API_KEY；示例配置只保存端点、模型、参数。无需再次在文件填写Key。密钥不进入命令参数。

```powershell
.\.venv\Scripts\python.exe scripts\run_nanobot.py --message "请读取并使用 ai-model-router 技能。已授权把任务发送到 DeepSeek 并承担本次编排与执行费用。请用真实模型总结：需求已完成，周五验收。报告路由档位、答案和新增调用数。"
```

编排模型使用Flash关闭思考，任务模型由路由规则选择；二者分别计费。网页和SQLite只统计任务模型调用。完整Agent会话与工具日志可能保存在nanobot数据目录，可能包含公开任务内容，受nanobot自己的策略管理。

## 迁移

将整个skills/ai-model-router复制到其他Runtime的workspace/skills，保留目录结构；安装LiteLLM。默认密钥和审计位于目标workspace/runtime。也可通过操作者环境变量指定ROUTER_SETTINGS_FILE/ROUTER_DATA_DIR，请求JSON不能指定路径。

Windows加密配置与用户绑定，换机器要重新保存。示例配置匹配本次安装版本，升级nanobot后应重新验证加载和工具API。

本机已验证上述自然语言链路，公开执行记录见artifacts/nanobot-agent-verification.txt。启动器把不含密钥的配置放在用户应用数据目录RouteLab/nanobot-工作区摘要下，以满足nanobot会话位于工作区外的要求。
