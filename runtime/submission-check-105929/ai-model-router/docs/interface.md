# 统一接口

CLI：skills/ai-model-router/scripts/router.py；动作 plan、run、stats、doctor。UTF-8 stdin JSON 或 --prompt，stdout 单个 JSON。0成功、1业务错误、2用法错误。

输入 prompt（1–24000字符）、preference（balanced/cost/quality）、max_tokens（64–8192，默认2048）、use_cache（true）、confirm_live（false）。mode兼容字段只接受live。run需要发送及费用授权；plan不需要Key、不生成文本。

HTTP：GET /api/health、/api/stats、/api/settings；POST /api/plan、/api/run、/api/cache/clear。POST /api/settings 接受唯一字段api_key；/api/settings/check读取模型列表；/api/settings/clear移除本地密钥。配置GET只返回是否配置、来源、存储类型、固定端点，不返回原值或片段。JSON请求最大120KB。

结果包括route、answer、response_model、thinking、usage_source、Token、provider_cache_hit_tokens、provider_cache_miss_tokens、cost、rates、pricing_band、耗时、finish_reason、incomplete及缓存状态。thinking在route中。供应商未返回用量时记null；本地缓存命中新调用/Token/费用为0，original_usage保存首次数据。费用按USD官方配置估算，未知供应商输入缓存分项时采用未命中费率上界估算。

错误例：EMPTY_PROMPT、MISSING_MATERIAL、INPUT_TOO_LONG、INVALID_MAX_TOKENS、CONFIRMATION_REQUIRED、API_KEY_MISSING、AUTH_FAILED、RATE_LIMITED、UPSTREAM_TIMEOUT、UPSTREAM_ERROR。服务原始异常不回显。输出预算耗尽保留已知用量与可能的不完整文本，标记incomplete=true，不缓存。
