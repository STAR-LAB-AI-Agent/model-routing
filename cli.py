#!/usr/bin/env python3
"""
router/cli.py
------------------------------------------------------------
CLI / Script 入口 —— 可被智能体 / nanobot Skill 直接调用的命令行工具。

子命令：
  route   <task>           仅做路由决策（不真正调用模型），输出选中模型 + 理由
  call    <task> [--model] 路由并真实调用，返回结果 + token + 成本 + 耗时
  stats                      打印累计调用统计（成本 / token / 延迟）
  models                     列出当前已注册的可用模型

用法示例：
  python -m router.cli route "用一段话解释相对论"
  python -m router.cli call  "请分析这张图片的内容" --json
  python -m router.cli stats

设计要点（对应课程要求）：
- Script/CLI 可独立运行，便于单独测试与定位问题。
- 默认输出人类可读文本；--json 输出简洁结构化，供 Skill / Agent Runtime 消费。
- 不把完整 prompt 写进日志，仅记录脱敏审计字段（低 Token + 安全）。
"""

from __future__ import annotations

import argparse
import json
import sys

from .core import build_default_router
from .logger import get_logger


_logger = get_logger()


def _print_route(decision, as_json: bool):
    if as_json:
        print(json.dumps({
            "selected_model": decision.selected_model,
            "reason": decision.reason,
            "scores": decision.scores,
        }, ensure_ascii=False, indent=2))
    else:
        print("=== 路由决策 ===")
        print(f"选定模型 : {decision.selected_model}")
        print(f"决策理由 : {decision.reason}")
        print("候选打分 :")
        for name, score in decision.scores.items():
            print(f"  - {name:16s} {score}")


def cmd_route(args, router):
    decision = router.route(args.task)
    _print_route(decision, args.json)
    return 0 if decision.selected_model != "__none__" else 2


def cmd_call(args, router):
    result = router.call(args.task, model_name=args.model)
    # 脱敏审计：仅记录元信息，不记 prompt / 回复
    _logger.call(
        call_id=result.get("call_id", "-"),
        model=result.get("model", "-"),
        status="success" if result.get("ok") else "failed",
        latency_ms=result.get("latency_ms", 0),
        input_tokens=result.get("tokens", {}).get("input", 0),
        output_tokens=result.get("tokens", {}).get("output", 0),
        cost_usd=result.get("cost_usd", 0.0),
    )
    if args.json:
        # 输出前剥离原始大段文本，仅保留必要摘要 → 低 Token
        out = dict(result)
        if out.get("result"):
            out["result_preview"] = out["result"][:120]
            del out["result"]
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print("=== 调用结果 ===")
        print(f"状态     : {'成功' if result.get('ok') else '失败'}")
        print(f"调用ID   : {result.get('call_id')}")
        print(f"使用模型 : {result.get('model')}")
        print(f"路由理由 : {result.get('route_reason')}")
        if result.get("ok"):
            print(f"输入Token: {result['tokens']['input']}")
            print(f"输出Token: {result['tokens']['output']}")
            print(f"成本(USD): {result['cost_usd']}")
            print(f"耗时(ms) : {result['latency_ms']}")
            print(f"回复预览 : {result.get('result', '')[:120]}")
        else:
            print(f"错误     : {result.get('error')}")
    return 0 if result.get("ok") else 3


def cmd_stats(args, router):
    summary = router.stats_summary(from_log=args.from_log)
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print("=== 调用统计 ===")
        print(f"总调用   : {summary['total_calls']}")
        print(f"成功     : {summary['success_calls']}")
        print(f"总输入tok: {summary['total_input_tokens']}")
        print(f"总输出tok: {summary['total_output_tokens']}")
        print(f"总成本USD: {summary['total_cost_usd']}")
        print("按模型   :")
        for name, d in summary["by_model"].items():
            print(f"  - {name:16s} 调用={d['calls']} 成本=${d['cost_usd']} "
                  f"平均延迟={d['avg_latency_ms']}ms")
    return 0


def cmd_models(args, router):
    models = router.available_models()
    if args.json:
        print(json.dumps([m.__dict__ for m in models], ensure_ascii=False, indent=2))
    else:
        print("=== 已注册模型 ===")
        for m in models:
            print(f"  - {m.name:16s} {m.display_name:14s} "
                  f"能力={m.capability:12s} 上下文={m.context_window} "
                  f"价格=${m.price_per_1k_input}/1k")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ai-model-router",
        description="AI 模型智能路由 CLI（题25：基于 LiteLLM 的多模型路由）",
    )
    p.add_argument("--json", action="store_true", help="以 JSON 结构化输出")
    sub = p.add_subparsers(dest="cmd", required=True)

    pr = sub.add_parser("route", help="仅做路由决策")
    pr.add_argument("task", help="自然语言任务描述")

    pc = sub.add_parser("call", help="路由并调用模型")
    pc.add_argument("task", help="自然语言任务描述")
    pc.add_argument("--model", help="手动指定模型（跳过自动路由）")

    ps = sub.add_parser("stats", help="打印调用统计")
    ps.add_argument("--from-log", action="store_true",
                    help="从审计日志跨进程累计统计")

    sub.add_parser("models", help="列出已注册模型")

    return p


def main(argv=None) -> int:
    # 允许 `--json` 出现在任意位置（前后皆可）
    argv = list(sys.argv[1:] if argv is None else argv)
    as_json = "--json" in argv
    argv = [a for a in argv if a != "--json"]

    parser = build_parser()
    args = parser.parse_args(argv)
    args.json = as_json  # 统一注入

    router = build_default_router()
    handlers = {
        "route": cmd_route,
        "call": cmd_call,
        "stats": cmd_stats,
        "models": cmd_models,
    }
    return handlers[args.cmd](args, router)


if __name__ == "__main__":
    sys.exit(main())
