"""用 LangGraph 实现的 AI 决策子图（Start.md §10 内层子图）。

这是 ``decision_graph.DecisionGraph`` 的 **LangGraph 版**：把同一套五节点
``感知 → 召回 → 推理 → 行动 → 编码`` 建成一张真正的 ``StateGraph``（节点=Node、转移=Edge），
由 langgraph 的图执行器驱动。相比纯 Python 编排器，好处是：图可观测（节点轨迹）、可扩展
（条件边/重试/并行）、与未来"外层游戏编排图"同构。

- langgraph 为**可选依赖**（`uv sync --extra ai`）：本模块在构图时才导入，未安装则给出明确提示，
  其余模块（引擎/记忆/联机/CLI 的 random/heuristic 策略）不受影响。
- 推理节点默认复用 ``HeuristicReasoner``（无需 LLM 即可跑），**LLM 推理就替换这一个节点**：
  把 ``Reasoner`` 换成基于 langchain-core 的 LLM 实现即可，图结构、合法性双保险都不变。
- 节点逻辑直接复用 ``DecisionGraph`` 的 perceive/recall/reason/act/encode 方法，确保两版行为一致。
"""
from __future__ import annotations

import operator
import random
from typing import Annotated, Any, Optional, TypedDict

from app.agents.decision_graph import DecisionGraph, GraphContext, Reasoner
from app.engine import Action, GameEngine, GameState, Seat
from app.memory.bonds import BondGraph


def langgraph_available() -> bool:
    try:
        import langgraph  # noqa: F401

        return True
    except ImportError:
        return False


class DecisionState(TypedDict):
    """图在节点间传递的状态。

    - ``ctx``：决策上下文对象（引擎/状态/席位/心证/打分/选择），各节点就地读写它。
    - ``trace``：节点执行轨迹，用累加 reducer 记录，便于观测"图确实按 5 节点跑过"。
    """

    ctx: Any
    trace: Annotated[list, operator.add]


def build_decision_app(reasoner: Optional[Reasoner] = None):
    """构造并编译 LangGraph 决策子图（懒导入 langgraph）。返回可 ``invoke`` 的编译图。"""
    try:
        from langgraph.graph import END, START, StateGraph
    except ImportError as e:  # pragma: no cover
        raise ImportError("LangGraph 未安装，请先执行 `uv sync --extra ai`") from e

    dg = DecisionGraph(reasoner)  # 复用同一套节点逻辑

    def perceive(state: DecisionState) -> dict:
        dg.perceive(state["ctx"])
        return {"trace": ["perceive"]}

    def recall(state: DecisionState) -> dict:
        dg.recall(state["ctx"])
        return {"trace": ["recall"]}

    def reason(state: DecisionState) -> dict:
        dg.reason(state["ctx"])
        return {"trace": ["reason"]}

    def act(state: DecisionState) -> dict:
        dg.act(state["ctx"])  # 设置 ctx.chosen，并已过引擎合法性双保险
        return {"trace": ["act"]}

    def encode(state: DecisionState) -> dict:
        dg.encode(state["ctx"])
        return {"trace": ["encode"]}

    g = StateGraph(DecisionState)
    g.add_node("perceive", perceive)
    g.add_node("recall", recall)
    g.add_node("reason", reason)
    g.add_node("act", act)
    g.add_node("encode", encode)
    # 线性子图：感知 → 召回 → 推理 → 行动 → 编码
    g.add_edge(START, "perceive")
    g.add_edge("perceive", "recall")
    g.add_edge("recall", "reason")
    g.add_edge("reason", "act")
    g.add_edge("act", "encode")
    g.add_edge("encode", END)
    return g.compile()


class LangGraphPolicy:
    """基于 LangGraph 决策子图的策略；持有跨回合心证，可选注入羁绊与自定义推理节点。"""

    def __init__(
        self,
        seed: Optional[int] = None,
        bonds: Optional[BondGraph] = None,
        reasoner: Optional[Reasoner] = None,
    ) -> None:
        self._app = build_decision_app(reasoner)  # 未装 langgraph 会在此抛 ImportError
        self._rng = random.Random(seed)
        self._beliefs: dict = {}
        self._bonds = bonds
        self.last_trace: list = []

    def decide(self, engine: GameEngine, state: GameState, seat: Seat) -> Optional[Action]:
        ctx = GraphContext(
            engine=engine, state=state, seat=seat,
            beliefs=self._beliefs, bonds=self._bonds, rng=self._rng,
        )
        out = self._app.invoke({"ctx": ctx, "trace": []})
        self.last_trace = out["trace"]
        return ctx.chosen

    @property
    def beliefs(self) -> dict:
        return self._beliefs
