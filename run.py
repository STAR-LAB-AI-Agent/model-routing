#!/usr/bin/env python3
"""
run.py
------------------------------------------------------------
项目主运行 / 演示脚本 —— 可被 nanobot 等 Agent Runtime 加载调用：

    from run import handle
    handle("用一段话解释相对论")          # 自动路由 + 调用
    handle("route: 请证明费马小定理")      # 前缀控制：仅路由
    handle("stats")                       # 查询统计

也支持命令行直接运行：
    python run.py                 # 进入交互模式（输入自然语言，输入 quit 退出）
    python run.py "解释相对论"     # 单次执行

安全：
- 启动时打印当前是 Mock 还是真实模式（不泄露 Key）。
- 通过 logger 记录脱敏审计日志。
"""

from __future__ import annotations

import json
import sys

from router import build_default_router
from router.config import USE_MOCK
from router.logger import get_logger


router = build_default_router(use_mock_fallback=True)
logger = get_logger()

INTENTS = {
    "route:": "route",
    "路由": "route",
    "stats": "stats",
    "统计": "stats",
    "models": "models",
    "模型": "models",
}


def _classify(text: str) -> str:
    """极轻量意图分类（确定性 Python 逻辑，低 Token）。"""
    t = text.strip().lower()
    if t.startswith("route:") or t.startswith("路由"):
        return "route"
    if t in ("stats", "统计", "统计一下", "调用统计"):
        return "stats"
    if t in ("models", "模型", "模型列表", "有哪些模型"):
        return "models"
    return "call"


def handle(user_input: str, as_json: bool = False) -> str:
    """统一入口，供 Agent Runtime / Skill 调用。返回字符串（文本或 JSON）。"""
    text = (user_input or "").strip()
    if not text:
        return "请输入任务描述。"

    intent = _classify(text)
    # 去掉前缀
    task = text.split(":", 1)[-1].strip() if intent == "route" else text

    if intent == "route":
        decision = router.route(task)
        payload = {
            "intent": "route",
            "selected_model": decision.selected_model,
            "reason": decision.reason,
            "scores": decision.scores,
        }
        logger.route(decision.selected_model, decision.reason, decision.scores)
    elif intent == "stats":
        payload = {"intent": "stats", "data": router.stats_summary()}
    elif intent == "models":
        payload = {"intent": "models", "data": [m.__dict__ for m in router.available_models()]}
    else:  # call
        result = router.call(task)
        logger.call(
            call_id=result.get("call_id", "-"),
            model=result.get("model", "-"),
            status="success" if result.get("ok") else "failed",
            latency_ms=result.get("latency_ms", 0),
            input_tokens=result.get("tokens", {}).get("input", 0),
            output_tokens=result.get("tokens", {}).get("output", 0),
            cost_usd=result.get("cost_usd", 0.0),
        )
        payload = {"intent": "call", "data": result}

    return json.dumps(payload, ensure_ascii=False, indent=2) if as_json else _human(payload)


def _human(payload: dict) -> str:
    i = payload["intent"]
    if i == "route":
        return (
            f"【路由决策】选定模型: {payload['selected_model']}\n"
            f"理由: {payload['reason']}\n"
            f"候选打分: {payload['scores']}"
        )
    if i == "stats":
        d = payload["data"]
        return (
            f"【调用统计】总={d['total_calls']} 成功={d['success_calls']} "
            f"总Token(in/out)={d['total_input_tokens']}/{d['total_output_tokens']} "
            f"总成本=${d['total_cost_usd']}\n"
            f"按模型: {json.dumps(d['by_model'], ensure_ascii=False)}"
        )
    if i == "models":
        lines = ["【可用模型】"]
        for m in payload["data"]:
            lines.append(
                f"  - {m['name']:16s} {m['display_name']:14s} "
                f"能力={m['capability']:12s} 上下文={m['context_window']}"
            )
        return "\n".join(lines)
    # call
    d = payload["data"]
    if not d.get("ok"):
        return f"【调用失败】{d.get('error')}（{d.get('message','')}）"
    return (
        f"【调用结果】模型={d['model']} 路由={d['route_reason']}\n"
        f"Token(in/out)={d['tokens']['input']}/{d['tokens']['output']} "
        f"成本=${d['cost_usd']} 耗时={d['latency_ms']}ms\n"
        f"回复: {d.get('result','')[:200]}"
    )


def main(argv=None):
    args = (argv or sys.argv)[1:]
    mode = "MOCK(离线兜底)" if USE_MOCK else "REAL(真实模型，需 API Key)"
    print(f"[ai-model-router] 当前模式: {mode}\n")

    if args:
        # 单次执行
        print(handle(" ".join(args)))
        return 0

    # 交互模式
    print("输入自然语言任务（可选前缀: route:/路由, stats/统计, models/模型）。输入 quit 退出。")
    while True:
        try:
            line = input("你 > ").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            break
        if not line or line.lower() in ("quit", "exit", "q"):
            break
        print(handle(line))
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
