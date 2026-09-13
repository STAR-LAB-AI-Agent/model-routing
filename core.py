"""
router/core.py
------------------------------------------------------------
AI 模型智能路由 —— 核心路由引擎

职责：
1. 管理一组「模型 provider」的注册信息（能力、价格、速度、上下文窗口）。
2. 根据任务类型、难度、长度等维度，把一条请求「路由」到最合适的模型。
3. 统一调用模型，并记录耗时、Token、成本，做聚合统计。

设计原则（对应课程要求）：
- 确定性逻辑放在 Python 侧，只有真正需要「模型能力」时才调用 LLM，
  避免把全部上下文塞给模型 → 低 Token。
- 工具返回值简洁结构化，便于 Skill / Agent Runtime 消费。
- 最小权限：仅使用显式注册的模型，不做任意代码执行。

离线可运行：若未配置任何真实 API Key，自动注册内置 MockProvider，
保证 "保存即可运行 / 测试 / 演示" 全链路可用；配置真实 Key 后无需改代码即可切换。
"""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Callable, Dict, List, Optional


def _load_call_records_from_log() -> List[CallRecord]:
    """从审计日志重建 CallRecord 列表（用于跨进程累计统计）。

    只解析 event=call 的行，且严格白名单字段，避免日志注入风险。
    """
    path = os.environ.get("ROUTER_LOG_PATH", "./logs/router.log")
    if not os.path.exists(path):
        return []
    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if obj.get("event") != "call":
                continue
            try:
                records.append(CallRecord(
                    call_id=obj.get("call_id", ""),
                    model=obj.get("model", ""),
                    task_type="",  # 日志未记录，留空
                    input_tokens=int(obj.get("input_tokens", 0)),
                    output_tokens=int(obj.get("output_tokens", 0)),
                    latency_ms=int(obj.get("latency_ms", 0)),
                    cost_usd=float(obj.get("cost_usd", 0.0)),
                    status=obj.get("status", "success"),
                    timestamp=0.0,
                ))
            except (TypeError, ValueError):
                continue
    return records


# ----------------------------------------------------------------------
# 数据模型
# ----------------------------------------------------------------------
@dataclass
class ModelInfo:
    """一个可被路由的模型描述。"""

    name: str                       # 内部标识，如 "gpt-4o-mini"
    display_name: str               # 展示名
    provider: str                   # 提供方，如 openai / qwen / mock
    capability: str                 # 主要能力: text / vision / long_context / tool
    context_window: int             # 最大上下文 token 数
    price_per_1k_input: float       # 每 1k input token 价格（美元）
    price_per_1k_output: float      # 每 1k output token 价格
    speed: str                      # fast / medium / slow
    is_available: bool = True       # 当前是否可用（缺 Key 时置 False）


@dataclass
class RouteDecision:
    """一次路由决策结果。"""

    selected_model: str
    reason: str                     # 为什么选它（可解释）
    scores: Dict[str, float] = field(default_factory=dict)


@dataclass
class CallRecord:
    """一次真实调用的审计记录（不记录 prompt/密钥等敏感内容）。"""

    call_id: str
    model: str
    task_type: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    cost_usd: float
    status: str                     # success / failed
    timestamp: float


# ----------------------------------------------------------------------
# Provider 抽象 + Mock
# ----------------------------------------------------------------------
class BaseProvider:
    """模型调用适配器的统一接口。"""

    def __init__(self, model_info: ModelInfo):
        self.info = model_info

    def complete(self, prompt: str, **kwargs) -> dict:
        raise NotImplementedError


class MockProvider(BaseProvider):
    """离线兜底 provider：不联网，按长度估算 token，返回固定结构化结果。

    保证在无任何 API Key 的评审/演示环境里，路由链路仍可完整跑通。
    """

    def complete(self, prompt: str, **kwargs) -> dict:
        # 简易 token 估算：中文按字，英文按空格分词，统一取 max 兜底
        text = prompt or ""
        est_input = max(1, len(text) // 2)
        output_text = (
            f"[Mock:{self.info.name}] 已收到任务。路由/调用链路正常运行。"
        )
        est_output = max(1, len(output_text) // 2)
        return {
            "text": output_text,
            "input_tokens": est_input,
            "output_tokens": est_output,
            "model": self.info.name,
        }


# ----------------------------------------------------------------------
# 路由引擎
# ----------------------------------------------------------------------
class Router:
    """模型智能路由引擎。"""

    # 任务类型 → 最匹配的能力标签（用于打分）
    TASK_CAPABILITY = {
        "simple_qa": "text",        # 简单问答：追求快、便宜
        "reasoning": "text",        # 复杂推理：追求能力强
        "long_context": "long_context",   # 长文本：追求上下文窗口
        "vision": "vision",         # 图文：需要视觉能力
        "tool_use": "tool",         # 工具调用：需要 function calling
    }

    def __init__(self):
        self._models: Dict[str, ModelInfo] = {}
        self._providers: Dict[str, BaseProvider] = {}
        self._stats: List[CallRecord] = []

    # ---- 注册 / 可用性 -------------------------------------------------
    def register(self, info: ModelInfo, provider: BaseProvider):
        self._models[info.name] = info
        self._providers[info.name] = provider

    def available_models(self) -> List[ModelInfo]:
        return [m for m in self._models.values() if m.is_available]

    # ---- 任务理解：自然语言 → 结构化意图 -------------------------------
    @staticmethod
    def understand(task: str) -> dict:
        """极轻量的本地意图识别（不调用 LLM，低 Token）。

        返回 {task_type, difficulty(1-3), est_tokens}，供路由打分使用。
        这是一个 *示例* 解析器：真实场景可用 LiteLLM + 小模型替换，
        但保持确定性逻辑在 Python 侧。

        判定优先级：**长文本 > 视觉/工具 > 难度关键词 > 简单问答**，
        保证"超长文本"不会被后续 reasoning 分支覆盖。
        """
        text = (task or "").lower()
        length = len(task or "")
        est_tokens = max(1, length // 2)

        # 关键词 → 任务类型
        vision_kw = ["图片", "图像", "识别", "截图", "image", "picture", "ocr"]
        tool_kw = ["调用工具", "执行", "运行", "查天气", "搜索", "tool", "天气"]
        long_kw = ["长文本", "长文档", "整本书", "全文", "万字"]

        # 1) 长文本：超长字符 或 显式长文本关键词 → 最高优先级
        if length > 2000 or any(k in text for k in long_kw):
            task_type = "long_context"
        elif any(k in text for k in vision_kw):
            task_type = "vision"
        elif any(k in text for k in tool_kw):
            task_type = "tool_use"
        else:
            # 2) 难度关键词（仅作用于"非视觉/非工具/非长文本"）
            hard_kw = ["推理", "证明", "复杂", "分析", "代码", "reasoning", "why", "定理"]
            if any(k in text for k in hard_kw) or length > 500:
                task_type = "reasoning"
            else:
                task_type = "simple_qa"

        # 难度
        if task_type in ("reasoning", "vision"):
            difficulty = 3
        elif task_type in ("tool_use", "long_context"):
            difficulty = 2
        else:
            difficulty = 1

        return {
            "task_type": task_type,
            "difficulty": difficulty,
            "est_tokens": est_tokens,
        }

    # ---- 核心：做出路由决策 -------------------------------------------
    def route(self, task: str) -> RouteDecision:
        intent = self.understand(task)
        needed = self.TASK_CAPABILITY.get(intent["task_type"], "text")
        candidates = self.available_models()
        if not candidates:
            # 没有任何可用模型：返回一个明确的降级决策（容错）
            return RouteDecision(
                selected_model="__none__",
                reason="当前无可用模型，请检查 API Key 或注册 Mock provider",
                scores={},
            )

        scores: Dict[str, float] = {}
        for m in candidates:
            score = 0.0
            # 1) 能力匹配（最关键）
            if m.capability == needed:
                score += 50
            elif m.capability == "text":   # 通用文本模型兜底
                score += 20
            # 2) 难度适配：难的题偏好慢但强的模型（这里用价格近似"强弱"）
            if intent["difficulty"] >= 3 and m.price_per_1k_input >= 0.5:
                score += 15
            if intent["difficulty"] <= 1 and m.price_per_1k_input < 0.5:
                score += 15
            # 3) 长文本必须能装下
            if intent["est_tokens"] > m.context_window:
                score -= 100   # 装不下直接淘汰
            # 4) 成本效率：优先便宜的（同分取低价）
            score -= m.price_per_1k_input * 2
            # 5) 速度：简单任务偏好 fast
            if intent["difficulty"] <= 1 and m.speed == "fast":
                score += 5
            scores[m.name] = round(score, 2)

        best = max(candidates, key=lambda m: scores.get(m.name, -999))
        return RouteDecision(
            selected_model=best.name,
            reason=(
                f"任务类型={intent['task_type']}, 难度={intent['difficulty']}, "
                f"预估tokens={intent['est_tokens']}, 所需能力={needed}; "
                f"选中「{best.display_name}」(能力={best.capability}, "
                f"价格=${best.price_per_1k_input}/1k, 速度={best.speed})"
            ),
            scores={k: v for k, v in sorted(scores.items(), key=lambda x: -x[1])},
        )

    # ---- 调用 + 统计 ---------------------------------------------------
    def call(self, task: str, model_name: Optional[str] = None) -> dict:
        """路由（若未指定模型）并调用，返回结构化结果 + 统计。"""
        decision = self.route(task) if model_name is None else None
        target = model_name or (decision.selected_model if decision else None)
        if target == "__none__" or target not in self._providers:
            return {
                "ok": False,
                "error": "no_available_model",
                "message": "没有可调用的模型，请先注册 provider",
                "route": decision and asdict(decision),
            }

        provider = self._providers[target]
        info = self._models[target]
        call_id = uuid.uuid4().hex[:8]
        start = time.time()
        try:
            result = provider.complete(task)
            latency = int((time.time() - start) * 1000)
            cost = (
                result["input_tokens"] / 1000 * info.price_per_1k_input
                + result["output_tokens"] / 1000 * info.price_per_1k_output
            )
            record = CallRecord(
                call_id=call_id,
                model=target,
                task_type=self.understand(task)["task_type"],
                input_tokens=result["input_tokens"],
                output_tokens=result["output_tokens"],
                latency_ms=latency,
                cost_usd=round(cost, 6),
                status="success",
                timestamp=time.time(),
            )
            self._stats.append(record)
            return {
                "ok": True,
                "call_id": call_id,
                "model": target,
                "route_reason": decision.reason if decision else f"手动指定模型={target}",
                "result": result["text"],
                "tokens": {"input": result["input_tokens"], "output": result["output_tokens"]},
                "cost_usd": record.cost_usd,
                "latency_ms": latency,
            }
        except Exception as e:  # pragma: no cover - 真实调用异常兜底
            latency = int((time.time() - start) * 1000)
            self._stats.append(CallRecord(
                call_id=call_id, model=target,
                task_type=self.understand(task)["task_type"],
                input_tokens=0, output_tokens=0, latency_ms=latency,
                cost_usd=0.0, status="failed", timestamp=time.time(),
            ))
            return {"ok": False, "call_id": call_id, "error": str(e)}

    # ---- 统计聚合（低 Token：只在查询时聚合，不缓存全量明细） ------------
    def stats_summary(self, *, from_log: bool = False) -> dict:
        """返回调用统计聚合。

        参数 from_log：若为 True，则从审计日志文件重新聚合（跨进程累计）；
        否则仅统计当前进程内存中的记录。两者可叠加。
        """
        records = list(self._stats)
        if from_log:
            records.extend(_load_call_records_from_log())

        total = len(records)
        success = [r for r in records if r.status == "success"]
        by_model: Dict[str, dict] = {}
        for r in success:
            d = by_model.setdefault(r.model, {
                "calls": 0, "input_tokens": 0, "output_tokens": 0,
                "cost_usd": 0.0, "latency_ms_sum": 0,
            })
            d["calls"] += 1
            d["input_tokens"] += r.input_tokens
            d["output_tokens"] += r.output_tokens
            d["cost_usd"] += r.cost_usd
            d["latency_ms_sum"] += r.latency_ms
        for d in by_model.values():
            d["cost_usd"] = round(d["cost_usd"], 6)
            d["avg_latency_ms"] = round(d["latency_ms_sum"] / d["calls"], 1)
            del d["latency_ms_sum"]
        return {
            "total_calls": total,
            "success_calls": len(success),
            "total_cost_usd": round(sum(r.cost_usd for r in success), 6),
            "total_input_tokens": sum(r.input_tokens for r in success),
            "total_output_tokens": sum(r.output_tokens for r in success),
            "by_model": by_model,
        }

    def reset_stats(self):
        self._stats.clear()


# ----------------------------------------------------------------------
# 工厂：默认模型池 + 离线自动降级
# ----------------------------------------------------------------------
def build_default_router(use_mock_fallback: bool = True) -> Router:
    """构造一个带默认模型池的 Router。

    - 若环境变量存在真实 Key，可在此接入 LiteLLMProvider（见 adapters.py）。
    - 否则自动注册 MockProvider，保证"保存即可运行"。
    """
    router = Router()

    # 默认模型池（capability/价格/速度为示例值，可在配置中覆盖）
    pool = [
        ModelInfo("gpt-4o-mini", "GPT-4o mini", "openai", "text",
                  128000, 0.15, 0.60, "fast"),
        ModelInfo("gpt-4o", "GPT-4o", "openai", "vision",
                  128000, 2.50, 10.00, "medium"),
        ModelInfo("qwen-plus", "通义千问 Plus", "qwen", "text",
                  131072, 0.20, 0.60, "fast"),
        ModelInfo("qwen-max", "通义千问 Max", "qwen", "long_context",
                  1000000, 1.20, 3.60, "medium"),
        ModelInfo("deepseek-chat", "DeepSeek Chat", "deepseek", "text",
                  64000, 0.14, 0.28, "fast"),
    ]

    import os
    has_real_key = any(
        os.environ.get(k) for k in
        ("OPENAI_API_KEY", "DASHSCOPE_API_KEY", "QWEN_API_KEY", "DEEPSEEK_API_KEY")
    )

    if has_real_key:
        # 真实 Key 存在：尝试用 LiteLLM 接入；单个模型失败不影响其它模型
        try:
            from .adapters import LiteLLMProvider  # type: ignore
            for info in pool:
                try:
                    router.register(info, LiteLLMProvider(info))
                except Exception:
                    info.is_available = False
        except Exception:
            has_real_key = False

    if not has_real_key:
        # 离线 / 无 Key：全部注册为 Mock，保证可运行、可演示
        for info in pool:
            info.is_available = True
            router.register(info, MockProvider(info))

    # 始终额外注册一个明确的 "mock-fast" 用于测试（确保即使有真 Key 也有离线用例）
    if use_mock_fallback:
        mock_info = ModelInfo("mock-fast", "Mock 快速模型", "mock", "text",
                              32000, 0.0, 0.0, "fast")
        router.register(mock_info, MockProvider(mock_info))

    return router
