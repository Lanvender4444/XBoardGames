"""LLM 驱动的 AI 决策（Start.md §10 推理节点 · langchain）。

整个平台的核心是"AI 操控 AI 角色"——每个 AI 角色的行动由 **LLM 决策链**产生。本模块用
**langchain-core** 把决策建成一条标准链：``ChatPromptTemplate | ChatModel | OutputParser``。

- 决策链是必经路径：感知/召回得到的情境（合法行动、心证、羁绊偏置、人物卡 persona）渲染进 prompt，
  交给 ChatModel 选出行动编号，再由引擎做合法性双保险（§10）。
- ChatModel 可注入：
  - 默认 ``LocalHeuristicChatModel``——一个**真实的 langchain ``BaseChatModel``**，无需 API key、可离线确定性运行
    （读取 prompt 里每个候选的"提示分"挑最优）；保证无网络也能整局跑通、可单测。
  - 配置 ``XBOARD_LLM_PROVIDER=openai`` 且装了 ``langchain-openai`` 时，``get_chat_model`` 返回 ``ChatOpenAI``，
    决策链其余部分**完全不变**——这就是"换成真模型即真 LLM 对局"。
- 与 LangGraph 协同：``LLMReasoner`` 实现 ``Reasoner`` 协议，直接插进 LangGraph/纯 Python 决策子图的 reason 节点。
"""
from __future__ import annotations

import os
import re
from typing import Any, Optional

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate


def _str_parser():
    return StrOutputParser()

from app.agents.decision_graph import GraphContext, HeuristicReasoner, Reasoner
from app.engine import Action


# --------------------------------------------------------------------------- #
# 默认离线模型：一个真实的 langchain BaseChatModel
# --------------------------------------------------------------------------- #
class LocalHeuristicChatModel(BaseChatModel):
    """无需 API key 的本地 ChatModel：读 prompt 里候选的"提示分"，回复最优编号。

    它是合法的 langchain ``BaseChatModel``（可进任何 LCEL 链），让整条 LLM 决策链在离线、确定性、
    可单测的前提下跑通；换成 ChatOpenAI 等真实模型时，链路与下游解析完全不变。
    """

    @property
    def _llm_type(self) -> str:
        return "local-heuristic"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: Optional[list[str]] = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        text = messages[-1].content if messages else ""
        idx = _argmax_hint(text if isinstance(text, str) else str(text))
        msg = AIMessage(content=str(idx))
        return ChatResult(generations=[ChatGeneration(message=msg)])


# 解析候选块里形如 "[i] ... 提示分 12.5" 的行，返回提示分最高的编号
_CAND = re.compile(r"\[(\d+)\][^\n]*?提示分\s*([-\d.]+)")


def _argmax_hint(prompt_text: str) -> int:
    best_i, best_s = 0, float("-inf")
    for m in _CAND.finditer(prompt_text):
        i, s = int(m.group(1)), float(m.group(2))
        if s > best_s:
            best_i, best_s = i, s
    return best_i


def get_chat_model(model: Optional[BaseChatModel] = None) -> BaseChatModel:
    """决策用 ChatModel 工厂。

    - 显式传入 → 用它。
    - 否则按**运行期 provider 配置**（前端/接口可改，见 app.agents.providers）构造：OpenAI 兼容的主流
      开源/闭源 API、Anthropic 原生，或离线内置模型（默认、无需 key）。
    """
    if model is not None:
        return model
    from app.agents.providers import build_chat_model

    return build_chat_model()


# --------------------------------------------------------------------------- #
# 决策链 + Reasoner
# --------------------------------------------------------------------------- #
_SYSTEM = (
    "你是社交推理桌游里的一名 AI 玩家：{persona}。"
    "你只能从给定候选行动里选择一个，目标是为自己的阵营取得胜利。"
    "综合你的身份、对其他玩家的心证、与他人的羁绊来判断。只回复你选择的候选编号（一个整数），不要解释。"
)
_HUMAN = (
    "阶段：{phase}　回合：{round}\n"
    "你的身份：席位#{seat} {role}/{faction}\n"
    "心证（对他人的判断）：{beliefs}\n"
    "羁绊偏置：{bias}\n"
    "召回的相关记忆：{memories}\n"
    "候选行动：\n{candidates}\n"
    "请只回复最佳候选的编号。"
)


class LLMReasoner:
    """用 langchain 决策链选行动的 Reasoner。

    实现 ``Reasoner.score``：每次决策（每个 ctx）只调用一次 LLM 选出编号并缓存，
    被选中的行动给高分、其余 0 分；落地仍由引擎合法性双保险。解析失败回退启发式最优。
    """

    def __init__(
        self,
        model: Optional[BaseChatModel] = None,
        persona: str = "理性、谨慎、以阵营胜利为目标",
        ltm: Any = None,
    ) -> None:
        self.model = get_chat_model(model)
        self.persona = persona
        self.ltm = ltm
        self._heur = HeuristicReasoner()  # 提供候选特征/提示分 + 兜底
        prompt = ChatPromptTemplate.from_messages([("system", _SYSTEM), ("human", _HUMAN)])
        self.chain = prompt | self.model | StrOutputParser()

    # ---- Reasoner 协议 ----
    def score(self, ctx: GraphContext, action: Action) -> float:
        pick = getattr(ctx, "_llm_pick", None)
        if pick is None or getattr(ctx, "_llm_pick_for", None) is not ctx.legal:
            pick = self._choose(ctx)
            ctx._llm_pick = pick
            ctx._llm_pick_for = ctx.legal
        return 1.0 if action is pick else 0.0

    # ---- 调用决策链 ----
    def _choose(self, ctx: GraphContext) -> Optional[Action]:
        legal = ctx.legal
        if not legal:
            return None
        cand_lines = []
        for i, a in enumerate(legal):
            hint = self._heur.score(ctx, a)
            tgt = f" 目标#{a.targets[0]}" if a.targets else ""
            cand_lines.append(f"[{i}] {a.type}{tgt} | 提示分 {round(hint, 1)}")
        memories = ""
        if self.ltm is not None:
            mem = self.ltm.recall(f"阶段 {ctx.state.phase} 谁可疑", top_k=3,
                                  character_id=ctx.seat.seat_id)
            memories = "；".join(m.content for m in mem) or "无"
        out = self.chain.invoke({
            "persona": self.persona,
            "phase": ctx.state.phase,
            "round": ctx.state.round,
            "seat": ctx.seat.seat_id,
            "role": ctx.seat.role,
            "faction": ctx.seat.faction,
            "beliefs": _fmt_beliefs(ctx),
            "bias": ctx.bias or "无",
            "memories": memories or "无",
            "candidates": "\n".join(cand_lines),
        })
        idx = _first_int(out)
        if idx is None or not (0 <= idx < len(legal)):
            # 回退：启发式最优
            return max(legal, key=lambda a: self._heur.score(ctx, a))
        return legal[idx]


def _fmt_beliefs(ctx: GraphContext) -> str:
    if not ctx.beliefs:
        return "无"
    parts = []
    for seat, b in sorted(ctx.beliefs.items()):
        parts.append(f"#{seat}:{b.suspected_faction or '?'}(信任{b.trust})")
    return "，".join(parts)


def _first_int(text: str) -> Optional[int]:
    m = re.search(r"-?\d+", text or "")
    return int(m.group()) if m else None


# --------------------------------------------------------------------------- #
# LLM 策略：默认走 LangGraph 决策子图 + LLM 推理节点
# --------------------------------------------------------------------------- #
class LLMPolicy:
    """AI 角色的默认策略：LLM（langchain 决策链）驱动，跑在 LangGraph 决策子图里。

    langgraph 可用时走 LangGraph 子图（可观测/可扩展）；否则回退纯 Python 决策子图。
    无论哪种，推理节点都用 ``LLMReasoner``，即 AI 角色由 LLM 操控。
    """

    def __init__(
        self,
        model: Optional[BaseChatModel] = None,
        seed: Optional[int] = None,
        bonds: Any = None,
        persona: str = "理性、谨慎、以阵营胜利为目标",
        ltm: Any = None,
        use_langgraph: bool = True,
    ) -> None:
        import random

        self._reasoner = LLMReasoner(model=model, persona=persona, ltm=ltm)
        self._rng = random.Random(seed)
        self._beliefs: dict = {}
        self._bonds = bonds
        self.last_trace: list = []

        self._app = None
        self._graph = None
        from app.agents.langgraph_graph import build_decision_app, langgraph_available

        if use_langgraph and langgraph_available():
            self._app = build_decision_app(self._reasoner)
        else:
            from app.agents.decision_graph import DecisionGraph

            self._graph = DecisionGraph(self._reasoner)

    def decide(self, engine, state, seat) -> Optional[Action]:
        ctx = GraphContext(
            engine=engine, state=state, seat=seat,
            beliefs=self._beliefs, bonds=self._bonds, rng=self._rng,
        )
        if self._app is not None:
            out = self._app.invoke({"ctx": ctx, "trace": []})
            self.last_trace = out["trace"]
        else:
            self._graph.run(ctx)
        return ctx.chosen

    def speak(self, engine, state, seat) -> str:
        """讨论阶段发言：用 LLM 依据共享状态 + 自身身份/心证生成一句话。

        离线内置模型不擅长自由文本 → 抛出让编排器回退模板；接真实 LLM 时返回自然语言发言。
        """
        from app.agents.llm import LocalHeuristicChatModel as _Local
        if isinstance(self._reasoner.model, _Local):
            raise RuntimeError("offline model: fall back to template")
        alive = [s.seat_id for s in state.alive_seats()]
        beliefs = "，".join(
            f"#{k}:{getattr(v,'suspected_faction', None) or '?'}(信任{getattr(v,'trust',0)})"
            for k, v in sorted(self._beliefs.items())
        ) or "暂无"
        prompt = self._speak_prompt(seat, state, alive, beliefs)
        text = (self._reasoner.model | _str_parser()).invoke(prompt)
        return str(text).strip().splitlines()[0][:120]

    @staticmethod
    def _speak_prompt(seat, state, alive, beliefs):
        from langchain_core.messages import HumanMessage, SystemMessage
        sys = (
            "你是社交推理游戏狼人杀里的一名玩家。现在是白天讨论，请用**一句中文**发言："
            "可以表达怀疑、辩护、带节奏，但不要直接报出自己的真实身份/底牌。简洁、有信息量。"
        )
        human = (
            f"你的席位 #{seat.seat_id}（身份保密）。第 {state.round} 回合，存活席位：{alive}。"
            f"你的心证：{beliefs}。只输出你的发言内容，不要加引号或前缀。"
        )
        return [SystemMessage(content=sys), HumanMessage(content=human)]

    @property
    def beliefs(self) -> dict:
        return self._beliefs
