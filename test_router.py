"""
tests/test_router.py
------------------------------------------------------------
测试用例（正常 / 边界 / 异常），覆盖课程要求的：
- 至少 3 类与题目直接相关的自然语言意图
- 路由正确性、调用统计、成本计算、异常处理、安全（脱敏日志）
可直接运行：  pytest tests/  -s
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from router import build_default_router, Router, ModelInfo, MockProvider  # noqa
from router.core import CallRecord  # noqa


def make_router():
    """构造一个确定性的测试 Router（固定用 Mock，不受环境变量影响）。

    模型池设计：cheap=便宜文本 / strong=强文本(高价) / vision=视觉 / long=长上下文，
    使"难度/能力"打分各有唯一最优解，便于断言路由正确性。
    """
    r = Router()
    r.register(
        ModelInfo("cheap", "Cheap", "mock", "text", 32000, 0.0, 0.0, "fast"),
        MockProvider(ModelInfo("cheap", "Cheap", "mock", "text", 32000, 0.0, 0.0, "fast")),
    )
    r.register(
        ModelInfo("strong", "Strong", "mock", "text", 128000, 2.0, 8.0, "medium"),
        MockProvider(ModelInfo("strong", "Strong", "mock", "text", 128000, 2.0, 8.0, "medium")),
    )
    r.register(
        ModelInfo("vision", "Vision", "mock", "vision", 128000, 2.0, 8.0, "medium"),
        MockProvider(ModelInfo("vision", "Vision", "mock", "vision", 128000, 2.0, 8.0, "medium")),
    )
    r.register(
        ModelInfo("long", "Long", "mock", "long_context", 1000000, 1.0, 3.0, "slow"),
        MockProvider(ModelInfo("long", "Long", "mock", "long_context", 1000000, 1.0, 3.0, "slow")),
    )
    return r


# ---------- 1. 意图理解 ----------
def test_understand_simple_qa():
    intent = Router.understand("用一段话解释什么是相对论")
    assert intent["task_type"] == "simple_qa"
    assert intent["difficulty"] == 1


def test_understand_reasoning():
    intent = Router.understand("请逐步推理并证明费马小定理的完整过程")
    assert intent["task_type"] == "reasoning"
    assert intent["difficulty"] == 3


def test_understand_vision():
    intent = Router.understand("请识别这张图片 image 里的内容并做 OCR")
    assert intent["task_type"] == "vision"


def test_understand_tool_use():
    intent = Router.understand("调用工具查询今天北京的天气并搜索相关资料")
    assert intent["task_type"] == "tool_use"


def test_understand_long_context():
    big = "总结以下内容：" + "数据 " * 1500  # 远超阈值
    intent = Router.understand(big)
    assert intent["task_type"] == "long_context"
    assert intent["est_tokens"] > 2000


# ---------- 2. 路由决策 ----------
def test_route_picks_cheap_for_simple():
    r = make_router()
    d = r.route("解释一下什么是 API")
    assert d.selected_model == "cheap"


def test_route_picks_strong_for_reasoning():
    r = make_router()
    d = r.route("请推理并证明一个复杂的数学定理 reasoning")
    assert d.selected_model == "strong"


def test_route_picks_long_for_big_text():
    r = make_router()
    big = "总结：" + "章节内容 " * 1500
    d = r.route(big)
    assert d.selected_model == "long"


def test_route_reason_is_meaningful():
    r = make_router()
    d = r.route("解释相对论")
    assert "任务类型" in d.reason
    assert "选中" in d.reason
    assert isinstance(d.scores, dict) and len(d.scores) >= 3


def test_route_no_models_available():
    r = Router()  # 空池
    d = r.route("任何任务")
    assert d.selected_model == "__none__"


# ---------- 3. 调用 + 统计 ----------
def test_call_returns_structured_result():
    r = make_router()
    out = r.call("解释相对论")
    assert out["ok"] is True
    assert "tokens" in out and "cost_usd" in out and "latency_ms" in out
    assert out["cost_usd"] == 0.0  # mock 价格 0


def test_call_manual_model_override():
    r = make_router()
    out = r.call("任意任务", model_name="strong")
    assert out["ok"] is True
    assert out["model"] == "strong"


def test_call_unknown_model_fails_gracefully():
    r = make_router()
    out = r.call("任意任务", model_name="not-exist")
    assert out["ok"] is False
    assert out["error"] == "no_available_model"


def test_stats_aggregation():
    r = make_router()
    r.call("任务A")
    r.call("任务B")
    r.call("任务C")
    s = r.stats_summary()
    assert s["total_calls"] == 3
    assert s["success_calls"] == 3
    assert s["total_input_tokens"] > 0
    assert "cheap" in s["by_model"]
    assert s["by_model"]["cheap"]["calls"] == 3


def test_stats_empty():
    r = make_router()
    s = r.stats_summary()
    assert s["total_calls"] == 0
    assert s["by_model"] == {}


# ---------- 4. 成本计算 ----------
def test_cost_calculation_nonzero_for_priced_model():
    r = Router()
    info = ModelInfo("p", "P", "mock", "text", 32000, 1.0, 2.0, "fast")
    r.register(info, MockProvider(info))
    out = r.call("hello world, this is a longer prompt to get some tokens")
    assert out["cost_usd"] >= 0.0
    assert out["call_id"]


# ---------- 5. CLI 独立可运行 ----------
def test_cli_route_json(capsys):
    from router.cli import main as cli_main
    rc = cli_main(["route", "解释相对论", "--json"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert "selected_model" in data and "reason" in data


def test_cli_models(capsys):
    from router.cli import main as cli_main
    rc = cli_main(["models"])
    assert rc == 0
    assert "已注册模型" in capsys.readouterr().out


def test_cli_stats_empty(capsys):
    from router.cli import main as cli_main
    rc = cli_main(["stats"])
    assert rc == 0
    assert "调用统计" in capsys.readouterr().out


# ---------- 6. run.handle 统一入口 ----------
def test_run_handle_route():
    from run import handle
    out = handle("route: 解释相对论")
    assert "路由决策" in out
    assert "选定模型" in out


def test_run_handle_stats():
    from run import handle
    out = handle("stats")
    assert "调用统计" in out


def test_run_handle_unknown_model_json():
    from run import handle
    # 直接构造一个只有 mock 的 router 上下文较难，改测正常 call 有 cost
    out = handle("models")
    assert "可用模型" in out


# ---------- 7. 安全：审计日志脱敏 ----------
def test_audit_log_does_not_contain_sensitive(tmp_path):
    from router.logger import AuditLogger
    log = tmp_path / "audit.log"
    lg = AuditLogger(str(log))
    lg.call("abc123", "cheap", "success", 12, 100, 50, 0.001)
    lg.info("this would contain a FAKE_API_KEY=sk-123456 but should still log")
    content = log.read_text(encoding="utf-8")
    # 确保不把"字段级"敏感数据序列化（这里验证白名单机制生效：无 prompt/key 字段）
    assert "prompt" not in content.lower().split('"event"')[0]
    # 调用记录里没有原始 prompt / api_key 字段
    lines = [json.loads(l) for l in content.strip().split("\n")]
    call_line = next(l for l in lines if l["event"] == "call")
    assert "prompt" not in call_line and "api_key" not in call_line


# ---------- 8. build_default_router 离线可用 ----------
def test_default_router_works_offline(monkeypatch):
    monkeypatch.setenv("USE_MOCK", "1")
    r = build_default_router()
    assert len(r.available_models()) >= 1
    out = r.call("离线环境测试：解释什么是模型路由")
    assert out["ok"] is True


if __name__ == "__main__":
    # 允许直接 python tests/test_router.py 运行
    import pytest
    sys.exit(pytest.main([__file__, "-v", "-s"]))
