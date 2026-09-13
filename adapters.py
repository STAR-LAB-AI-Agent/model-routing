"""
router/adapters.py
------------------------------------------------------------
真实模型适配器：通过 LiteLLM 统一调用多家 LLM。

仅在环境变量中存在对应 API Key 时启用；无 Key 时 Router 自动降级为 Mock，
无需修改任何业务代码。这保证了：
  - 有 Key → 真实多模型路由（满足"正确集成 Python 开源项目 LiteLLM"）
  - 无 Key → 全链路仍可运行、测试、演示（满足"保存即可提交运行"）

安全：
  - Key 仅从环境变量读取，绝不写进代码 / 日志 / 提交物。
  - prompt 不进入审计日志，日志只保留 token 数、模型、耗时等脱敏字段。
"""

from __future__ import annotations

import os
from typing import Optional

from .core import BaseProvider, ModelInfo


class LiteLLMProvider(BaseProvider):
    """用 LiteLLM 统一调用真实模型。

    model_name 映射规则（可在子类/配置中覆盖）：
      - openai/*  → 直接使用
      - qwen/*    → 通过兼容端点（DASHSCOPE / 自建网关）调用
      - deepseek/*→ DeepSeek 官方端点
    """

    def __init__(self, model_info: ModelInfo, api_key: Optional[str] = None):
        super().__init__(model_info)
        try:
            import litellm  # 真实依赖，仅在启用时 import
            self._litellm = litellm
        except ImportError as e:
            raise RuntimeError(
                "未安装 litellm，无法使用真实模型。请 `pip install litellm` "
                "或通过环境变量 USE_MOCK=1 使用离线 Mock 模式。"
            ) from e

        self._api_key = api_key  # 允许显式注入；None 时由 litellm 读环境变量

    def _resolve_model(self) -> str:
        """把内部 model name 转成 LiteLLM 可识别的 model string。"""
        name = self.info.name
        mapping = {
            "gpt-4o-mini": "openai/gpt-4o-mini",
            "gpt-4o": "openai/gpt-4o",
            "qwen-plus": "openai/qwen-plus",   # 通过兼容端点
            "qwen-max": "openai/qwen-max",
            "deepseek-chat": "deepseek/deepseek-chat",
        }
        return mapping.get(name, f"openai/{name}")

    def complete(self, prompt: str, **kwargs) -> dict:
        response = self._litellm.completion(
            model=self._resolve_model(),
            messages=[{"role": "user", "content": prompt}],
            api_key=self._api_key,
            max_tokens=kwargs.get("max_tokens", 512),
        )
        msg = response["choices"][0]["message"]["content"]
        usage = response.get("usage", {}) or {}
        return {
            "text": msg,
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
            "model": self.info.name,
        }
