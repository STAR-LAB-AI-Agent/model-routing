"""Operator-owned model profiles and pricing; requests cannot set endpoints."""
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = SKILL_ROOT.parents[1]
TIERS = ("eco", "balanced", "reasoner")
API_BASE = "https://api.deepseek.com"


class RouterError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code, self.message = code, message


def validate_endpoint(cfg):
    if cfg.get("api_base") != API_BASE:
        raise RouterError("ENDPOINT_BLOCKED", "密钥只允许发送到官方 https://api.deepseek.com。")


def load_config(mode="live", now=None):
    if mode != "live":
        raise RouterError("INVALID_MODE", "系统仅支持真实 API 调用。")
    try:
        cfg = json.loads((SKILL_ROOT / "config/models.json").read_text(encoding="utf-8"))
        validate_endpoint(cfg)
        assert cfg["currency"] == "USD"
        stamp = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        peak = stamp.weekday() < 5 and (1 <= stamp.hour < 4 or 6 <= stamp.hour < 10)
        cfg["pricing_band"] = "peak" if peak else "off_peak"
        for tier in TIERS:
            m = cfg["models"][tier]
            assert m["model"] in ("openai/deepseek-flash", "openai/deepseek-v4-pro")
            assert m["thinking"] in ("enabled", "disabled")
            assert type(m["context_tokens"]) is int and m["context_tokens"] >= 2048
            for field in ("input_per_million", "cached_input_per_million", "output_per_million"):
                assert type(m[field]) in (int, float) and math.isfinite(m[field]) and m[field] >= 0
                m[field] *= 1 if peak else 0.5
        return cfg
    except RouterError:
        raise
    except (OSError, ValueError, KeyError, TypeError, AssertionError):
        raise RouterError("INVALID_CONFIG", "模型配置无效，请检查 config/models.json。") from None


def data_dir():
    return Path(os.environ.get("ROUTER_DATA_DIR", str(PROJECT_ROOT / "runtime"))).resolve()
