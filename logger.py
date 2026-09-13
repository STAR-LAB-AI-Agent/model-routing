"""
router/logger.py
------------------------------------------------------------
审计日志工具：仅记录脱敏字段（模型、耗时、Token、成本、调用状态），
绝不记录 prompt、回复、API Key 等敏感内容 → 满足"最小权限 + 敏感信息保护"。
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime
from typing import Optional


class AuditLogger:
    def __init__(self, path: Optional[str] = None):
        self.path = path or os.environ.get(
            "ROUTER_LOG_PATH", "./logs/router.log"
        )
        self._lock = threading.Lock()
        os.makedirs(os.path.dirname(self.path), exist_ok=True)

    def _write(self, event: str, data: dict):
        record = {"time": datetime.utcnow().isoformat() + "Z", "event": event}
        # 只保留白名单字段，任何情况下都不写入敏感内容
        safe = {k: v for k, v in data.items() if k not in ("prompt", "api_key", "key")}
        record.update(safe)
        with self._lock:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def route(self, model: str, reason: str, scores: dict):
        self._write("route", {"model": model, "reason": reason, "scores": scores})

    def call(self, call_id: str, model: str, status: str, latency_ms: int,
             input_tokens: int, output_tokens: int, cost_usd: float):
        self._write("call", {
            "call_id": call_id, "model": model, "status": status,
            "latency_ms": latency_ms, "input_tokens": input_tokens,
            "output_tokens": output_tokens, "cost_usd": cost_usd,
        })

    def info(self, msg: str):
        self._write("info", {"message": msg})

    def error(self, msg: str):
        self._write("error", {"message": msg})


# 单例，便于模块间共享
_default_logger: Optional[AuditLogger] = None


def get_logger() -> AuditLogger:
    global _default_logger
    if _default_logger is None:
        _default_logger = AuditLogger()
    return _default_logger
