# 设计说明

架构：网页或nanobot → Skill/CLI → RouterService → policy → LiteLLM → DeepSeek。网页和CLI共用核心；settings.py负责动态密钥；config/models.json仅保存公开模型档位与费率。

路由：代码和复杂推理特征优先，随后摘要。难度分=最多3分推理关键词+最多2分任务类型+最多2分输入长度。代码、推理特征或总分>=4使用reasoner；摘要或输入估算>600 Token使用balanced；其余eco。质量优先提升一档；成本优先降低短摘要，保留复杂任务能力下限。上下文不足逐档升级，全部不足则拒绝；当前项目保守限额65536，并非声称模型只支持该长度。

eco使用deepseek-flash关闭思考；balanced使用deepseek-v4-pro关闭思考；reasoner使用Pro开启思考、reasoning_effort=low。上游默认思考开启，因此代码显式传递thinking参数。服务超时120秒、不额外重试；没有失败备用文本。

配置在每次请求读取。Windows DPAPI保护密钥，原子替换文件；设置接口不回显。缓存键包括规范化文本、模型、思考配置、预算、公开配置、密钥摘要和版本。密钥摘要仅内存，不写审计。更换密钥清缓存；独立CLI仍能发现配置更新。

缓存OrderedDict+锁，128条，10分钟TTL。锁使本地请求串行，避免并发相同请求重复收费；长请求期间其他生成需等待，适合单用户验收。只有完整成功答案缓存。SQLite连接显式关闭，支持Windows文件清理。

费用采用usage输入/输出，按输入缓存命中与未命中分别计价；UTC周一至五01–04、06–10使用峰值费率，其他时段减半。按请求开始选费率，跨时段边界可能偏差，以账单为准。缓存分类缺失时给出上界估算；未知用量记null。供应商输出Token包含推理，界面不保存或显示推理正文。

本地HTTP只绑定127.0.0.1，Host/Origin校验，固定静态资源映射，Content-Type与体积限制。使用textContent渲染答案，不执行代码。审计只含任务哈希和元数据；统计数据库使用audit-live-v2.sqlite3，与旧数据隔离。
