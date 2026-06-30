"""对局编排器（Start.md §10 外层图）—— 共享 State · 并发 Think · 顺序 Act。

按"思考并发、行动顺序"的模型，把每个阶段分两类多人行动：
- 抢占式 PREEMPTIVE：所有 agent 在**冻结快照**上**并发思考**、各自提交意图，引擎按优先级/计票**顺序仲裁**。
  （夜晚秘密行动、白天投票）
- 排队式 QUEUED：agent 按座位**轮流**行动，后者看到前者已写入 State 的发言/动作。（白天讨论发言）

提供两套出口：
1. ``drive(...)``：纯 Python 步进循环（人机/全 AI 通用，轮到人类即暂停），PlayService 直接用它。
2. ``build_orchestrator(...)``：把同一语义建成 **LangGraph 图**（抢占式用 ``Send`` 并发扇出思考 + 仲裁节点），
   全 AI 驱动用，体现"用 LangGraph 搞并发思考 + 顺序行动"。
"""
from __future__ import annotations

import operator
from typing import Annotated, Any, Callable, Optional, TypedDict

from app.engine import Action, GameEngine, GameState
from app.engine.engine import PASS


# --------------------------------------------------------------------------- #
# 阶段模式
# --------------------------------------------------------------------------- #
QUEUED = "queued"
PREEMPTIVE = "preemptive"


def phase_mode(state: GameState) -> str:
    """阶段动作含 speak → 排队式（轮流发言）；否则 → 抢占式（并发暗投/秘密行动）。"""
    phase = state.definition.phase(state.phase)
    return QUEUED if "speak" in phase.actions else PREEMPTIVE


# --------------------------------------------------------------------------- #
# 发言（LLM 文本 / 模板兜底）
# --------------------------------------------------------------------------- #
_OPENERS = ("我观察了一圈，", "就目前局势，", "说说我的看法：", "我倾向于认为，")


def _template_speech(policy: Any, state: GameState, seat_id: int) -> str:
    """无 LLM 时的发言模板：依据自己的心证点名最可疑者。"""
    beliefs = getattr(policy, "beliefs", {}) or {}
    rng = getattr(policy, "_rng", None)
    opener = _OPENERS[(seat_id + state.round) % len(_OPENERS)]
    suspects = sorted(
        ((b.trust, s) for s, b in beliefs.items() if getattr(b, "suspected_faction", None) == "werewolf"),
    )
    if suspects:
        return f"{opener}#{suspects[0][1]} 的发言和行为很可疑，建议重点关注。"
    distrust = sorted(((getattr(b, "trust", 0), s) for s, b in beliefs.items()))
    if distrust and distrust[0][0] < 0:
        return f"{opener}我对 #{distrust[0][1]} 有些怀疑，先听听他怎么说。"
    return f"{opener}暂时没有明确目标，先过下信息，保持观察。"


def utterance(policy: Any, engine: GameEngine, state: GameState, seat) -> str:
    """生成一句发言：优先策略自带 speak（可能是 LLM），否则模板。"""
    speak = getattr(policy, "speak", None)
    if callable(speak):
        try:
            text = speak(engine, state, seat)
            if text and str(text).strip():
                return str(text).strip()
        except Exception:
            pass
    return _template_speech(policy, state, seat.seat_id)


# --------------------------------------------------------------------------- #
# 步进函数（编排器与 PlayService 共用，保证两条路径一致）
# --------------------------------------------------------------------------- #
def step_preemptive(
    engine: GameEngine, gs: GameState, policies: dict, human_seats: tuple = ()
) -> bool:
    """抢占式：AI 在冻结快照上并发思考（先全部决策、后统一应用），引擎按座位序仲裁。

    返回是否仍有人类待行动（True → 调用方应暂停等输入；AI 已秘密提交，看不到人类意图）。
    """
    actors = engine.actors_to_act(gs)
    ai = [s for s in actors if s.seat_id not in human_seats]
    human_pending = any(s.seat_id in human_seats for s in actors)
    # 1) 冻结快照并发思考：先全部产出意图（此时尚未 apply，互不可见）
    intents = [(s.seat_id, policies[s.seat_id].decide(engine, gs, s)) for s in ai]
    # 2) 顺序仲裁：按座位序应用
    for seat_id, act in sorted(intents, key=lambda t: t[0]):
        engine.apply(gs, act or Action(seat=seat_id, type=PASS))
    return human_pending


def step_queued(
    engine: GameEngine, gs: GameState, policies: dict,
    on_event: Optional[Callable] = None, human_seats: tuple = (),
) -> bool:
    """排队式：按座位序轮流行动；发言生成文本写入共享 State；遇人类则停下。

    返回是否在人类席位处暂停（True → 等输入）。引擎已 acted 的会被跳过，故可中断后续重入续跑。
    """
    for s in engine.actors_to_act(gs):
        if s.seat_id in human_seats:
            return True
        before = len(gs.log)
        act = policies[s.seat_id].decide(engine, gs, s) or Action(seat=s.seat_id, type=PASS)
        if act.type == "speak":
            act.extra = {**(act.extra or {}), "text": utterance(policies[s.seat_id], engine, gs, s)}
        engine.apply(gs, act)
        if on_event is not None:
            for ev in gs.log[before:]:
                on_event(gs, ev)
    return False


def drive(
    engine: GameEngine, gs: GameState, policies: dict,
    on_event: Optional[Callable] = None, human_seats: tuple = (), max_steps: int = 400,
) -> None:
    """推进对局到"轮到人类"或"结束"。人机与全 AI 通用（human_seats=() 即全 AI）。"""
    steps = 0
    while not gs.finished and steps < max_steps:
        steps += 1
        actors = engine.actors_to_act(gs)
        if not actors:
            before = len(gs.log)
            engine.advance_phase(gs)
            if on_event is not None:
                for ev in gs.log[before:]:
                    on_event(gs, ev)
            continue
        if phase_mode(gs) == QUEUED:
            if step_queued(engine, gs, policies, on_event, human_seats):
                return
        else:
            if step_preemptive(engine, gs, policies, human_seats):
                return


# --------------------------------------------------------------------------- #
# LangGraph 编排图（全 AI；抢占式用 Send 并发思考）
# --------------------------------------------------------------------------- #
def _merge_intentions(old, new):
    if new is None:  # 仲裁后重置
        return []
    return (old or []) + new


class OrchestratorState(TypedDict):
    gs: Any
    intentions: Annotated[list, _merge_intentions]
    steps: Annotated[int, operator.add]


def build_orchestrator(engine: GameEngine, policies: dict,
                       on_event: Optional[Callable] = None, max_steps: int = 400):
    """把"并发思考 + 顺序仲裁 + 排队发言"建成 LangGraph 图（懒导入 langgraph）。"""
    from langgraph.graph import END, START, StateGraph
    from langgraph.types import Send

    def dispatch(state: OrchestratorState) -> dict:
        return {}

    def route(state: OrchestratorState):
        gs: GameState = state["gs"]
        if gs.finished or state["steps"] >= max_steps:
            return "end"
        actors = engine.actors_to_act(gs)
        if not actors:
            return "advance"
        if phase_mode(gs) == QUEUED:
            return "queued"
        # 抢占式：并发扇出到 think_one（每个待行动席位一个分支，共享同一快照 gs）
        return [Send("think_one", {"seat": s.seat_id, "gs": gs}) for s in actors]

    def think_one(payload: dict) -> dict:
        gs: GameState = payload["gs"]
        seat = gs.seat(payload["seat"])
        act = policies[seat.seat_id].decide(engine, gs, seat)
        return {"intentions": [(seat.seat_id, act)]}

    def arbitrate(state: OrchestratorState) -> dict:
        gs: GameState = state["gs"]
        for seat_id, act in sorted(state["intentions"], key=lambda t: t[0]):
            engine.apply(gs, act or Action(seat=seat_id, type=PASS))
        return {"intentions": None}  # 仲裁后重置并发收集通道

    def queued(state: OrchestratorState) -> dict:
        step_queued(engine, state["gs"], policies, on_event, human_seats=())
        return {}

    def advance(state: OrchestratorState) -> dict:
        gs: GameState = state["gs"]
        before = len(gs.log)
        engine.advance_phase(gs)
        if on_event is not None:
            for ev in gs.log[before:]:
                on_event(gs, ev)
        return {"steps": 1}

    g = StateGraph(OrchestratorState)
    g.add_node("dispatch", dispatch)
    g.add_node("think_one", think_one)
    g.add_node("arbitrate", arbitrate)
    g.add_node("queued", queued)
    g.add_node("advance", advance)
    g.add_edge(START, "dispatch")
    g.add_conditional_edges("dispatch", route,
                            {"end": END, "advance": "advance", "queued": "queued"})
    g.add_edge("think_one", "arbitrate")
    g.add_edge("arbitrate", "dispatch")
    g.add_edge("queued", "dispatch")
    g.add_edge("advance", "dispatch")
    return g.compile()


def run_orchestrator(engine: GameEngine, gs: GameState, policies: dict,
                     on_event: Optional[Callable] = None, max_steps: int = 400) -> GameState:
    """用 LangGraph 编排图把全 AI 对局跑到结束（含并发思考 + 顺序仲裁 + 排队发言）。"""
    app = build_orchestrator(engine, policies, on_event=on_event, max_steps=max_steps)
    app.invoke({"gs": gs, "intentions": [], "steps": 0},
               config={"recursion_limit": max_steps + 10})
    return gs
