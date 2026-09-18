import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace as N
import pytest
from routerlib.config import RouterError, load_config, validate_endpoint
from routerlib.policy import validate_request, plan
from routerlib.providers import LiteLLMProvider
from routerlib.service import RouterService
from routerlib.settings import SettingsStore

ROOT = Path(__file__).resolve().parents[1]


class FakeProvider:
    def __init__(self): self.calls = 0
    def complete(self, req, route, cfg):
        self.calls += 1
        return {"answer": "unit test answer", "input_tokens": 100, "output_tokens": 20,
                "provider_cache_hit_tokens": 40, "provider_cache_miss_tokens": 60,
                "usage_source": "provider_reported", "model_latency_ms": 2.5,
                "incomplete": False, "finish_reason": "stop"}


def request(**kwargs):
    return {"prompt": "hello", "confirm_live": True, **kwargs}


@pytest.fixture
def svc(tmp_path):
    return RouterService(tmp_path, FakeProvider(), lambda _: load_config(now=datetime(2026,9,17,2,tzinfo=timezone.utc)))


@pytest.mark.parametrize("prompt,tier,kind", [
    ("用一句话解释机器学习。", "eco", "qa"),
    ("请总结：第一阶段完成，第二阶段明天开始。", "balanced", "summary"),
    ("Python 实现二分查找并分析复杂度", "reasoner", "code"),
    ("证明两个连续整数乘积为偶数", "reasoner", "reasoning"),
    ("Explain machine learning", "eco", "qa"),
    ("Summarize this note: meeting tomorrow", "balanced", "summary"),
    ("summarize " + "长文材料。" * 1000, "balanced", "summary")])
def test_routing(svc, prompt, tier, kind):
    r = svc.preview({"prompt": prompt})["route"]
    assert (r["tier"], r["task_type"]) == (tier, kind)
    assert svc.provider.calls == 0


@pytest.mark.parametrize("req,code", [
    ({"prompt":"  "},"EMPTY_PROMPT"), ({"prompt":"x"*24001},"INPUT_TOO_LONG"),
    ({"prompt":"帮我总结"},"MISSING_MATERIAL"), ({"prompt":"hi","max_tokens":63},"INVALID_MAX_TOKENS"),
    ({"prompt":"hi","max_tokens":True},"INVALID_MAX_TOKENS"),
    ({"prompt":"hi","mode":"invalid"},"INVALID_MODE"),
    ({"prompt":"hi","preference":"fast"},"INVALID_PREFERENCE"),
    ({"prompt":"hi","api_base":"https://evil.invalid"},"UNKNOWN_FIELD"),
    ({"prompt":"hi","confirm_live":"true"},"INVALID_INPUT"), ([],"INVALID_INPUT")])
def test_invalid(svc, req, code):
    with pytest.raises(RouterError) as exc: svc.preview(req)
    assert exc.value.code == code


def test_context_and_preferences(svc):
    assert svc.preview({"prompt":"总结：明天开会","preference":"cost"})["route"]["tier"] == "eco"
    assert svc.preview({"prompt":"hi","preference":"quality"})["route"]["tier"] == "balanced"
    assert svc.preview({"prompt":"证明此结论","preference":"cost"})["route"]["tier"] == "reasoner"
    cfg = load_config()
    for m in cfg["models"].values(): m["context_tokens"] = 10
    with pytest.raises(RouterError, match="上下文"): plan(validate_request({"prompt":"hi"}), cfg)


def test_cache_billing_and_disable(svc):
    first, second = svc.run(request()), svc.run(request())
    assert first["cost"] == round((40*.006+60*.3+20*1.2)/1e6,8)
    assert second["cache_hit"] and second["provider_calls"] == 0
    assert second["cost"] == second["input_tokens"] == second["output_tokens"] == 0
    assert second["original_usage"]["input_tokens"] == 100
    svc.run(request(use_cache=False))
    stats = svc.stats()["groups"][0]
    assert stats["requests"] == 3 and stats["cache_hits"] == 1 and stats["input_tokens"] == 200


def test_cache_limits_expiry_and_namespace(svc):
    svc.run(request()); svc.run(request(max_tokens=1024))
    assert svc.provider.calls == 2
    for k, (_, v) in list(svc.cache.items()): svc.cache[k] = (time.monotonic()-601, v)
    svc.run(request())
    assert svc.provider.calls == 3
    for i in range(130): svc.run(request(prompt=f"item {i}"))
    assert len(svc.cache) == 128
    assert svc.clear_cache()["cleared_entries"] == 128


def test_confirmation(svc):
    with pytest.raises(RouterError, match="确认"): svc.run({"prompt":"hello"})
    assert svc.provider.calls == 0


def test_audit_content_and_handles(svc):
    marker = "PRIVATE-PROMPT-DO-NOT-LOG"
    svc.run(request(prompt=marker)); svc.stats()
    assert marker.encode() not in svc.db.read_bytes()
    assert b"unit test answer" not in svc.db.read_bytes()
    svc.db.unlink()


def test_code_whitespace():
    assert "\n    return" in validate_request({"prompt":"def x():\n    return 1"})["prompt"]


def test_missing_usage_and_failure(svc):
    class Missing(FakeProvider):
        def complete(self,*args):
            r=super().complete(*args);r.update(input_tokens=None,output_tokens=None);return r
    svc.provider=Missing()
    assert svc.run(request())["cost"] is None
    assert svc.stats()["groups"][0]["unknown_cost_requests"] == 1
    svc.clear_cache()
    class Broken(FakeProvider):
        def complete(self,*args):
            self.calls+=1;raise RouterError("UPSTREAM_TIMEOUT","timeout")
    svc.provider=Broken()
    for _ in range(2): assert not svc.run(request())["ok"]
    assert svc.provider.calls == 2 and not svc.cache


@pytest.mark.parametrize("endpoint",["http://api.deepseek.com","https://evil.invalid","https://user:pass@api.deepseek.com","https://api.deepseek.com?key=x"])
def test_endpoint(endpoint):
    with pytest.raises(RouterError): validate_endpoint({"api_base":endpoint})


def test_prices():
    peak=load_config(now=datetime(2026,9,17,2,tzinfo=timezone.utc))
    off=load_config(now=datetime(2026,9,19,2,tzinfo=timezone.utc))
    assert off["models"]["eco"]["input_per_million"]*2 == peak["models"]["eco"]["input_per_million"]


def test_dynamic_key_and_redaction(tmp_path,monkeypatch):
    import litellm
    store=SettingsStore(tmp_path/"credentials.json")
    key1,key2="sk-unit-test-first-123456","sk-unit-test-second-123456"
    store.save({"api_key":key1})
    assert key1 not in json.dumps(store.status())
    if sys.platform == "win32": assert key1.encode() not in store.path.read_bytes()
    calls=[]
    def complete(**kw):
        calls.append(kw)
        assert kw["extra_body"]["thinking"]["type"] in ("disabled","enabled")
        return N(choices=[N(message=N(content="answer"),finish_reason="stop")],model="deepseek-flash",
                 usage=N(prompt_tokens=12,completion_tokens=9,prompt_cache_hit_tokens=2,prompt_cache_miss_tokens=10))
    monkeypatch.setattr(litellm,"completion",complete)
    svc=RouterService(tmp_path,LiteLLMProvider(store))
    svc.run(request());svc.run(request())
    snapshot=svc.provider.snapshot()
    revision=snapshot.revision()
    store.save({"api_key":key2});svc.run(request())
    assert snapshot.revision()==revision and svc.provider.revision()!=revision
    assert len(calls)==2 and calls[0]["api_key"]==key1 and calls[1]["api_key"]==key2
    assert "mock_response" not in calls[0]
    def broken(**_): raise Exception(key2+" SECRET PROMPT")
    monkeypatch.setattr(litellm,"completion",broken)
    r=svc.run(request(prompt="different"))
    assert not r["ok"] and key2 not in json.dumps(r) and key2.encode() not in svc.db.read_bytes()
    store.clear()
    assert not store.path.exists()


def test_truncated_not_cached(svc):
    class Short(FakeProvider):
        def complete(self,*args):
            r=super().complete(*args);r["incomplete"]=True;return r
    svc.provider=Short()
    svc.run(request());svc.run(request())
    assert svc.provider.calls==2 and not svc.cache


def test_cli(tmp_path):
    import os
    env={**os.environ,"ROUTER_DATA_DIR":str(tmp_path),"PYTHONUTF8":"1"}
    cmd=[sys.executable,str(ROOT/"skills/ai-model-router/scripts/router.py"),"plan","--json-stdin"]
    r=subprocess.run(cmd,input=json.dumps({"prompt":"请总结会议记录"}),text=True,encoding="utf-8",capture_output=True,env=env)
    assert r.returncode==0 and json.loads(r.stdout)["route"]["tier"]=="balanced"
    r=subprocess.run(cmd,input="not-json",text=True,encoding="utf-8",capture_output=True,env=env)
    assert r.returncode==1 and json.loads(r.stdout)["error"]["code"]=="INVALID_JSON"
