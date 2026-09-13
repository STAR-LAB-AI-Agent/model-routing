"""
router/config.py
------------------------------------------------------------
模型池与全局配置。通过环境变量切换 Mock / 真实模式，无需改代码。
"""

import os

# 强制使用离线 Mock 模式（无 API Key 的评审/演示环境推荐设为 1）
USE_MOCK = os.environ.get("USE_MOCK", "1") in ("1", "true", "True")

# 单次调用的最大 token（超过则触发"长文本路由"分支）
LONG_CONTEXT_THRESHOLD = int(os.environ.get("LONG_CONTEXT_THRESHOLD", "2000"))

# 审计日志路径
LOG_PATH = os.environ.get("ROUTER_LOG_PATH", "./logs/router.log")

# 模型注册信息（capability / 价格 / 速度为示例，可按需覆盖）
MODEL_POOL = [
    {
        "name": "gpt-4o-mini", "display_name": "GPT-4o mini", "provider": "openai",
        "capability": "text", "context_window": 128000,
        "price_per_1k_input": 0.15, "price_per_1k_output": 0.60, "speed": "fast",
    },
    {
        "name": "gpt-4o", "display_name": "GPT-4o", "provider": "openai",
        "capability": "vision", "context_window": 128000,
        "price_per_1k_input": 2.50, "price_per_1k_output": 10.00, "speed": "medium",
    },
    {
        "name": "qwen-plus", "display_name": "通义千问 Plus", "provider": "qwen",
        "capability": "text", "context_window": 131072,
        "price_per_1k_input": 0.20, "price_per_1k_output": 0.60, "speed": "fast",
    },
    {
        "name": "qwen-max", "display_name": "通义千问 Max", "provider": "qwen",
        "capability": "long_context", "context_window": 1000000,
        "price_per_1k_input": 1.20, "price_per_1k_output": 3.60, "speed": "medium",
    },
    {
        "name": "deepseek-chat", "display_name": "DeepSeek Chat", "provider": "deepseek",
        "capability": "text", "context_window": 64000,
        "price_per_1k_input": 0.14, "price_per_1k_output": 0.28, "speed": "fast",
    },
]
