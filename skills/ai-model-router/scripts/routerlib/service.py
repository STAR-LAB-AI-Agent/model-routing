"""Routing, bounded in-memory TTL cache, and content-free SQLite audit data."""
from collections import OrderedDict
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import threading
import time
import uuid
from .config import RouterError, load_config, data_dir
from .policy import validate_request, plan
from .providers import LiteLLMProvider


class RouterService:
    def __init__(self, storage=None, provider=None, config_loader=None):
        self.storage = Path(storage) if storage else data_dir()
        self.storage.mkdir(parents=True, exist_ok=True)
        self.db = self.storage / "audit-live-v2.sqlite3"
        self.provider = provider or LiteLLMProvider()
        self.config_loader = config_loader or load_config
        self.cache = OrderedDict()
        self.lock = threading.RLock()
        with self.connect() as con:
            con.execute("""CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY, created_at TEXT NOT NULL, request_id TEXT NOT NULL,
                mode TEXT NOT NULL, currency TEXT NOT NULL, tier TEXT, task_type TEXT,
                prompt_sha256 TEXT, status TEXT, error_code TEXT, cache_hit INTEGER,
                provider_calls INTEGER, input_tokens INTEGER, output_tokens INTEGER,
                cost REAL, latency_ms REAL, model_latency_ms REAL, usage_source TEXT)""")

    @contextmanager
    def connect(self):
        con = sqlite3.connect(self.db, timeout=10)
        con.row_factory = sqlite3.Row
        try:
            with con:
                yield con
        finally:
            con.close()

    def preview(self, payload):
        req = validate_request(payload)
        route = plan(req, self.config_loader(req["mode"]))
        return {"ok": True, "mode": req["mode"], "route": route, "provider_calls": 0,
                "requires_confirmation": req["mode"] == "live"}

    def run(self, payload):
        start = time.perf_counter()
        req = validate_request(payload)
        cfg = self.config_loader(req["mode"])
        route = plan(req, cfg)
        req_id = uuid.uuid4().hex[:16]
        base = {"request_id": req_id, "mode": req["mode"], "route": route,
                "currency": cfg["currency"], "cache_hit": False, "provider_calls": 0}
        if req["mode"] == "live" and not req["confirm_live"]:
            raise RouterError("CONFIRMATION_REQUIRED", "请先预览路由，并确认发送任务及可能的费用。")
        with self.lock:
            # Bind one credential to both cache namespace and this call, even if
            # settings change while the upstream request is in flight.
            provider = self.provider.snapshot() if hasattr(self.provider, "snapshot") else self.provider
            key = hashlib.sha256(json.dumps({"prompt": req["prompt"], "mode": req["mode"],
                "model": route["model"], "max_tokens": req["max_tokens"], "cfg": cfg,
                "thinking": route["thinking"],
                "credential_revision": provider.revision() if hasattr(provider, "revision") else "test",
                "version": 2}, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
            now = time.monotonic()
            for old in list(self.cache):
                if now - self.cache[old][0] > 600:
                    del self.cache[old]
            if req["use_cache"] and key in self.cache:
                result = deepcopy(self.cache[key][1])
                self.cache.move_to_end(key)
                result.update(base, cache_hit=True, provider_calls=0, input_tokens=0, output_tokens=0,
                              cost=0.0, model_latency_ms=0.0, provider_cache_hit_tokens=0,
                              provider_cache_miss_tokens=0, reasoning_tokens=0,
                              usage_source="cache_no_new_usage", cost_source="cache_no_new_charge")
            else:
                try:
                    call = provider.complete(req, route, cfg)
                    m = cfg["models"][route["tier"]]
                    incoming, outgoing = call["input_tokens"], call["output_tokens"]
                    hit, miss = call.get("provider_cache_hit_tokens"), call.get("provider_cache_miss_tokens")
                    cache_reported = type(hit) is int and type(miss) is int and min(hit, miss) >= 0 and hit + miss == incoming
                    cost = None if incoming is None or outgoing is None else round(((hit * m["cached_input_per_million"] + miss * m["input_per_million"] if cache_reported else incoming * m["input_per_million"]) + outgoing * m["output_per_million"]) / 1_000_000, 8)
                    result = {"ok": True, **base, **call, "provider_calls": 1, "cost": cost,
                              "cost_source": "provider_usage_official_rates_estimate" if cache_reported else "cache_breakdown_missing_upper_estimate",
                              "pricing_band": cfg["pricing_band"],
                              "rates": {k: m[k] for k in ("input_per_million", "cached_input_per_million", "output_per_million")},
                              "original_usage": {"input_tokens": incoming, "output_tokens": outgoing, "cost": cost}}
                    if req["use_cache"] and not call.get("incomplete"):
                        self.cache[key] = (time.monotonic(), deepcopy(result))
                        while len(self.cache) > 128:
                            self.cache.popitem(last=False)
                except RouterError as exc:
                    local = exc.code in ("API_KEY_MISSING", "CONFIRMATION_REQUIRED")
                    result = {"ok": False, **base, "error": {"code": exc.code, "message": exc.message},
                              "provider_calls": 0 if local else 1, "input_tokens": None, "output_tokens": None,
                              "cost": None, "usage_source": "unavailable", "model_latency_ms": None,
                              "note": "失败调用是否计费需核对服务商账单。"}
            result["latency_ms"] = round((time.perf_counter() - start) * 1000, 2)
            self.record(req, result)
            return result

    def record(self, req, result):
        route = result["route"]
        values = (datetime.now(timezone.utc).isoformat(), result["request_id"], req["mode"],
            result["currency"], route["tier"], route["task_type"], hashlib.sha256(req["prompt"].encode()).hexdigest(),
            "ok" if result["ok"] else "error", result.get("error", {}).get("code"), int(result["cache_hit"]),
            result["provider_calls"], result["input_tokens"], result["output_tokens"], result["cost"],
            result["latency_ms"], result["model_latency_ms"], result["usage_source"])
        with self.connect() as con:
            con.execute("""INSERT INTO events (created_at,request_id,mode,currency,tier,task_type,
                prompt_sha256,status,error_code,cache_hit,provider_calls,input_tokens,output_tokens,
                cost,latency_ms,model_latency_ms,usage_source) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", values)

    def stats(self, mode="live"):
        if mode != "live":
            raise RouterError("INVALID_MODE", "系统仅支持真实 API 调用。")
        with self.connect() as con:
            rows = [dict(r) for r in con.execute("SELECT * FROM events WHERE mode=? ORDER BY id DESC LIMIT 30", (mode,))]
            groups = [dict(r) for r in con.execute("""SELECT currency,COUNT(*) requests,
                SUM(status='ok') successes,SUM(status='error') failures,SUM(cache_hit) cache_hits,
                SUM(provider_calls) provider_calls,COALESCE(SUM(input_tokens),0) input_tokens,
                COALESCE(SUM(output_tokens),0) output_tokens,COALESCE(SUM(cost),0) known_cost,
                SUM(cost IS NULL) unknown_cost_requests,ROUND(AVG(latency_ms),2) average_latency_ms
                FROM events WHERE mode=? GROUP BY currency""", (mode,))]
        return {"ok": True, "mode": mode, "groups": groups, "recent": rows,
                "note": "仅统计路由脚本；nanobot 编排模型的 Token/费用不包含在内。不同币种分组，未知费用不视为零。"}

    def clear_cache(self):
        with self.lock:
            size = len(self.cache)
            self.cache.clear()
        return {"ok": True, "cleared_entries": size}
