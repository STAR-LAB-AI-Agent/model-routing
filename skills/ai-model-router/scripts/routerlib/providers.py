"""The only generation boundary: real DeepSeek through LiteLLM."""
import os
import hashlib
import time
from .config import RouterError, validate_endpoint
from .policy import SYSTEM_PROMPT
from .settings import SettingsStore

os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
os.environ["DO_NOT_TRACK"] = "1"


def integer(obj, field):
    value = getattr(obj, field, None)
    return value if type(value) is int and value >= 0 else None


class LiteLLMProvider:
    def __init__(self, settings=None, key_snapshot=None):
        self.settings = settings or SettingsStore()
        self._key_snapshot = key_snapshot

    def snapshot(self):
        return LiteLLMProvider(self.settings, self.settings.key())

    def key(self):
        return self.settings.key() if self._key_snapshot is None else self._key_snapshot

    def revision(self):
        return hashlib.sha256(self.key().encode()).hexdigest()

    def complete(self, req, route, cfg):
        import litellm
        litellm.telemetry = False
        litellm.suppress_debug_info = True
        validate_endpoint(cfg)
        key = self.key()
        if not key:
            raise RouterError("API_KEY_MISSING", "请点击页面右上角 API 配置，保存 DeepSeek 密钥。")
        if not req["confirm_live"]:
            raise RouterError("CONFIRMATION_REQUIRED", "请确认发送任务与可能的费用。")
        m = cfg["models"][route["tier"]]
        kwargs = {"model": m["model"], "api_base": cfg["api_base"], "api_key": key,
                  "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": req["prompt"]}],
                  "max_tokens": req["max_tokens"], "timeout": 120, "num_retries": 0,
                  "extra_body": {"thinking": {"type": m["thinking"]}}}
        if m["thinking"] == "enabled":
            kwargs["reasoning_effort"] = m.get("reasoning_effort", "low")
        start = time.perf_counter()
        try:
            response = litellm.completion(**kwargs)
            choice = response.choices[0]
            answer = choice.message.content or ""
            usage = getattr(response, "usage", None)
            incoming, outgoing = integer(usage, "prompt_tokens"), integer(usage, "completion_tokens")
            if incoming is None or outgoing is None:
                incoming = outgoing = None
            hit = integer(usage, "prompt_cache_hit_tokens")
            miss = integer(usage, "prompt_cache_miss_tokens")
            details = getattr(usage, "completion_tokens_details", None)
            reasoning = integer(details, "reasoning_tokens")
            finish = getattr(choice, "finish_reason", None)
            if not answer.strip() and finish != "length":
                raise RouterError("EMPTY_RESPONSE", "服务未返回最终文本，请检查模型状态。")
            return {"answer": answer, "input_tokens": incoming, "output_tokens": outgoing,
                    "provider_cache_hit_tokens": hit, "provider_cache_miss_tokens": miss,
                    "reasoning_tokens": reasoning, "finish_reason": finish,
                    "incomplete": finish == "length", "response_model": getattr(response, "model", m["model"]),
                    "warning": "输出预算耗尽，结果可能不完整；增加输出上限后重试。" if finish == "length" else None,
                    "usage_source": "provider_reported" if incoming is not None else "provider_usage_unavailable",
                    "model_latency_ms": round((time.perf_counter() - start) * 1000, 2)}
        except RouterError:
            raise
        except Exception as exc:
            code, message = {
                "AuthenticationError": ("AUTH_FAILED", "鉴权失败，请在 API 配置中更新密钥。"),
                "RateLimitError": ("RATE_LIMITED", "服务限流或额度不足，请检查账户余额或稍后重试。"),
                "Timeout": ("UPSTREAM_TIMEOUT", "模型调用超时（120 秒），请稍后重试。"),
                "ContextWindowExceededError": ("UPSTREAM_CONTEXT", "服务报告上下文超限，请分段处理。"),
            }.get(type(exc).__name__, ("UPSTREAM_ERROR", "模型服务调用失败，请检查网络、余额及模型权限；原始错误已隐藏。"))
            raise RouterError(code, message) from None
