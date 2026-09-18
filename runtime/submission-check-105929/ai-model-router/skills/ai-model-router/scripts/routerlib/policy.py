"""Deterministic routing: type, difficulty, length, preference, context limit."""
import math
import re
from .config import RouterError, TIERS

SYSTEM_PROMPT = "你是课程实验助手。请用中文直接回答用户任务，保持简洁、准确；不确定时明确说明。"
TYPE_LABELS = {"qa": "简单问答", "summary": "摘要整理", "code": "代码任务", "reasoning": "复杂推理"}


def estimate_tokens(text):
    """Offline heuristic, NOT a provider tokenizer. Conservative CJK weighting."""
    cjk = len(re.findall(r"[\u3400-\u9fff]", text))
    return max(1, math.ceil(cjk * 1.5 + (len(text) - cjk) / 3))


def normalize(text):
    # Keep indentation/newlines, essential for code and tabular tasks.
    return text.replace("\r\n", "\n").strip()


def validate_request(req):
    if not isinstance(req, dict):
        raise RouterError("INVALID_INPUT", "输入必须为 JSON 对象。")
    allowed = {"prompt", "mode", "preference", "max_tokens", "use_cache", "confirm_live"}
    if set(req) - allowed:
        raise RouterError("UNKNOWN_FIELD", "包含不支持的字段；请求不能指定路径、端点或密钥。")
    text = req.get("prompt")
    if not isinstance(text, str) or not text.strip():
        raise RouterError("EMPTY_PROMPT", "请提供非空任务，例如：用一句话解释什么是机器学习。")
    if len(text) > 24000:
        raise RouterError("INPUT_TOO_LONG", "任务最多 24000 个字符，请先分段。")
    mode = req.get("mode", "live")
    if mode != "live":
        raise RouterError("INVALID_MODE", "系统仅支持真实 API 调用。")
    pref = req.get("preference", "balanced")
    if pref not in ("balanced", "cost", "quality"):
        raise RouterError("INVALID_PREFERENCE", "策略只能为 balanced、cost 或 quality。")
    cap = req.get("max_tokens", 2048)
    if type(cap) is not int or not 64 <= cap <= 8192:
        raise RouterError("INVALID_MAX_TOKENS", "max_tokens 必须是 64 至 8192 的整数（包含推理 Token）。")
    for key in ("use_cache", "confirm_live"):
        if key in req and type(req[key]) is not bool:
            raise RouterError("INVALID_INPUT", f"{key} 必须是布尔值。")
    return {"prompt": normalize(text), "mode": mode, "preference": pref,
            "max_tokens": cap, "use_cache": req.get("use_cache", True),
            "confirm_live": req.get("confirm_live", False)}


def plan(req, cfg):
    prompt = req["prompt"]
    low = prompt.lower()
    code = bool(re.search(r"代码|编程|函数|算法|调试|单元测试|python|javascript|\bsql\b|\bcode\b|\bdebug\b", low))
    summary = bool(re.search(r"总结|摘要|概括|提炼|整理|summari[sz]e|summary", low))
    if re.fullmatch(r"(?:请|帮我|请帮我)?(?:总结|摘要|概括|提炼|整理)(?:一下)?[。！! ]*", low):
        raise RouterError("MISSING_MATERIAL", "请补充需要总结的材料，例如：请总结：周一开发，周五测试。")
    hard_hits = re.findall(r"证明|推导|复杂度|并发|分布式|动态规划|权衡|多步骤|设计方案|prove|reason step|trade.?off", low)
    kind = "code" if code else "reasoning" if hard_hits else "summary" if summary else "qa"
    tokens = estimate_tokens(prompt) + estimate_tokens(SYSTEM_PROMPT) + 16
    level = min(3, len(hard_hits)) + (2 if code else 1 if summary else 0)
    level += 2 if tokens > 3000 else 1 if tokens > 600 else 0
    index = 2 if code or hard_hits or level >= 4 else 1 if summary or tokens > 600 else 0
    reasons = [f"任务类型：{TYPE_LABELS[kind]}", f"启发式难度分：{level}/7", f"输入约 {tokens} Token（含系统提示，字符启发式估算）"]
    if req["preference"] == "quality":
        index = min(2, index + 1)
        reasons.append("质量优先：提升一个档位")
    elif req["preference"] == "cost":
        if index == 1 and tokens <= 3000:
            index = 0
            reasons.append("成本优先：短摘要降至轻量档位")
        else:
            reasons.append("成本优先：保留复杂任务或长文本的能力下限")
    minimum = index
    while index < 3 and tokens + req["max_tokens"] > cfg["models"][TIERS[index]]["context_tokens"]:
        index += 1
    if index == 3:
        raise RouterError("CONTEXT_EXCEEDED", "估算上下文加输出预算超过所有模型容量，请分段或降低输出上限。")
    if index != minimum:
        reasons.append("输入与输出预算超过原模型上下文，自动升级")
    tier = TIERS[index]
    m = cfg["models"][tier]
    estimated = (tokens * m["input_per_million"] + req["max_tokens"] * m["output_per_million"]) / 1_000_000
    return {"tier": tier, "model": m["model"], "label": m["label"], "task_type": kind,
            "thinking": m["thinking"], "pricing_band": cfg["pricing_band"],
            "task_label": TYPE_LABELS[kind], "difficulty_score": level, "characters": len(prompt),
            "estimated_input_tokens": tokens, "max_output_tokens": req["max_tokens"],
            "estimated_cost_at_output_limit": round(estimated, 8), "currency": cfg["currency"],
            "pricing_note": cfg["pricing_note"], "reasons": reasons,
            "routing_model_calls": 0, "token_estimator": "character_heuristic_not_tokenizer"}
