"""AI 玩家决策子图（Start.md §10）。

对每个需要行动的 AI 角色调用一次的内层决策子图：
    感知(Perceive) → 召回(Recall) → 推理(Reason) → 行动(Act) → 编码(Encode)

本模块提供两种策略：
- ``RandomPolicy``：从合法行动里随机挑一个（基线，确定性可控）。
- ``HeuristicPolicy``：跑完整决策子图，用"心证(STM)+羁绊偏置"做出优于随机的决策
  （狼不刀队友、预言家查未知、票投最可疑），无需 LLM 即可运行。

``DecisionGraph`` 是子图编排器：把五个节点串起来执行。真实部署可把 ``Reasoner`` 换成
LLM 推理节点（注入 persona/traits + 召回记忆构造 prompt），或在 langgraph 上重建同构子图；
节点契约与"合法性双保险"（产出行动必过引擎 legal_actions 校验）保持不变（§10 / §15）。
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Optional, Protocol

from app.engine import Action, GameEngine, GameState, Seat
from app.memory.bonds import BondGraph
from app.memory.stm import Belief


class Policy(Protocol):
    """行动策略：给定状态与席位，返回一个合法行动。"""

    def decide(self, engine: GameEngine, state: GameState, seat: Seat) -> Optional[Action]: ...


class RandomPolicy:
    """从引擎给出的合法行动里随机挑一个（确定性可控，便于复盘）。"""

    def __init__(self, seed: Optional[int] = None) -> None:
        self._rng = random.Random(seed)

    def decide(self, engine: GameEngine, state: GameState, seat: Seat) -> Optional[Action]:
        legal = engine.legal_actions(state, seat)
        if not legal:
            return None
        return self._rng.choice(legal)


# --------------------------------------------------------------------------- #
# 决策子图：上下文 + 节点 + 编排器
# --------------------------------------------------------------------------- #
@dataclass
class GraphContext:
    engine: GameEngine
    state: GameState
    seat: Seat
    beliefs: dict  # seat_id -> Belief（本策略实例跨回合累积的心证）
    bonds: Optional[BondGraph] = None
    rng: random.Random = field(default_factory=random.Random)
    # 工作字段
    legal: list = field(default_factory=list)
    wolf_mates: set = field(default_factory=set)
    bias: dict = field(default_factory=dict)
    chosen: Optional[Action] = None


class Reasoner(Protocol):
    """推理节点：给定上下文与一个候选行动，返回打分（越高越优先）。"""

    def score(self, ctx: GraphContext, action: Action) -> float: ...


class HeuristicReasoner:
    """无需 LLM 的启发式推理：依据阵营、心证、羁绊偏置给候选行动打分。"""

    def _enemy_factions(self, ctx: GraphContext) -> set:
        return {f for f in ctx.state.definition.factions if f != ctx.seat.faction}

    def _suspicion(self, ctx: GraphContext, target: int) -> float:
        b = ctx.beliefs.get(target)
        if not b:
            return 0.0
        s = 0.0
        if b.suspected_faction in self._enemy_factions(ctx):
            s += 1.0
        s += (-b.trust) / 100.0  # 越不信任越可疑
        return s

    def score(self, ctx: GraphContext, action: Action) -> float:
        me = ctx.seat
        if action.type == "pass":
            return 0.0
        if not action.targets:
            return 0.1  # speak 等无目标行动，低优先
        target = action.targets[0]
        bias = ctx.bias.get(target, {})
        affinity = bias.get("affinity", 0)
        b = ctx.beliefs.get(target)
        trust = b.trust if b else 0
        susp = self._suspicion(ctx, target)

        if action.type == "eliminate":
            if me.faction == "werewolf":
                if target in ctx.wolf_mates:
                    return -999.0  # 绝不刀队友
                # 优先刀：低好感 / 我方不信任的威胁
                return 50.0 + (-affinity) / 10.0 + (-trust) / 10.0
            # 女巫毒药等：毒最可疑的敌人
            return 25.0 + susp * 15.0 + (-trust) / 10.0
        if action.type == "investigate":
            if b is None:
                return 40.0  # 优先查未知
            return 18.0 + (-trust) / 10.0
        if action.type == "vote":
            if me.faction == "werewolf" and target in ctx.wolf_mates:
                return -999.0  # 不票队友
            return 20.0 + susp * 18.0 + (-trust) / 10.0 + (-affinity) / 12.0
        if action.type == "protect":
            return 20.0 + trust / 10.0 + affinity / 10.0  # 护信任的/好感高的
        if action.type == "nominate":
            return 12.0 + susp * 10.0 + (-trust) / 10.0
        return 1.0


class DecisionGraph:
    """决策子图编排器：感知→召回→推理→行动→编码。

    纯 Python 执行（无外部依赖即可运行）。如需可视化/可观测的图，可在 langgraph 上重建同构子图，
    把下列方法登记为节点；本编排器即其参考实现。
    """

    def __init__(self, reasoner: Optional[Reasoner] = None) -> None:
        self.reasoner = reasoner or HeuristicReasoner()

    def run(self, ctx: GraphContext) -> Optional[Action]:
        self.perceive(ctx)
        self.recall(ctx)
        self.reason(ctx)
        action = self.act(ctx)
        self.encode(ctx)
        return action

    # ① 感知：拉合法行动、识别狼队友（狼人互认）
    def perceive(self, ctx: GraphContext) -> None:
        ctx.legal = ctx.engine.legal_actions(ctx.state, ctx.seat)
        if ctx.seat.faction == "werewolf":
            ctx.wolf_mates = {
                s.seat_id for s in ctx.state.alive_seats() if s.faction == "werewolf"
            }

    # ② 召回：扫描"自己可见的"私有事件更新心证 + 取羁绊偏置
    def recall(self, ctx: GraphContext) -> None:
        me = ctx.seat.seat_id
        for ev in ctx.state.log:
            if ev.action == "investigate_result" and ev.actor == me:
                tgt = ev.payload.get("target")
                val = ev.payload.get("value")
                bel = ctx.beliefs.get(tgt) or Belief(seat=tgt)
                if ev.payload.get("reveals") == "faction":
                    bel.suspected_faction = val
                    bel.trust = -80 if val == "werewolf" else 60
                ctx.beliefs[tgt] = bel
        if ctx.bonds is not None:
            present = {s.seat_id: s.seat_id for s in ctx.state.alive_seats()}
            ctx.bias = ctx.bonds.to_behavior_bias(me, present)

    # ③ 推理：给每个合法行动打分
    def reason(self, ctx: GraphContext) -> None:
        ctx._scores = [(self.reasoner.score(ctx, a), a) for a in ctx.legal]  # type: ignore[attr-defined]

    # ④ 行动：取最高分（同分确定性随机），合法性双保险后落地
    def act(self, ctx: GraphContext) -> Optional[Action]:
        if not ctx.legal:
            return None
        scores = getattr(ctx, "_scores", [(0.0, a) for a in ctx.legal])
        best = max(s for s, _ in scores)
        top = [a for s, a in scores if s == best]
        chosen = top[0] if len(top) == 1 else ctx.rng.choice(top)
        # 合法性双保险：必须在引擎给出的合法集合内，否则回退安全默认
        if not ctx.engine._is_legal(ctx.state, chosen):
            chosen = ctx.legal[0]
        ctx.chosen = chosen
        return chosen

    # ⑤ 编码：把本回合形成的心证写回（此实例跨回合记忆）
    def encode(self, ctx: GraphContext) -> None:
        pass  # 心证已就地更新于 ctx.beliefs（HeuristicPolicy 持有），此处可扩展为写 STM/LTM


class HeuristicPolicy:
    """跑完整决策子图的策略；持有跨回合心证，可选注入羁绊图。"""

    def __init__(
        self,
        seed: Optional[int] = None,
        bonds: Optional[BondGraph] = None,
        reasoner: Optional[Reasoner] = None,
    ) -> None:
        self._rng = random.Random(seed)
        self._beliefs: dict = {}
        self._bonds = bonds
        self._graph = DecisionGraph(reasoner)

    def decide(self, engine: GameEngine, state: GameState, seat: Seat) -> Optional[Action]:
        ctx = GraphContext(
            engine=engine,
            state=state,
            seat=seat,
            beliefs=self._beliefs,
            bonds=self._bonds,
            rng=self._rng,
        )
        return self._graph.run(ctx)

    @property
    def beliefs(self) -> dict:
        return self._beliefs

    def speak(self, engine, state, seat) -> str:
        from app.agents.orchestrator import _template_speech
        return _template_speech(self, state, seat.seat_id)


class AIPlayer:
    """绑定一张人物卡的 AI 玩家；默认由 LLM 决策链操控（langchain + LangGraph）。"""

    def __init__(self, character_id: int, policy: Optional[Policy] = None) -> None:
        self.character_id = character_id
        if policy is None:
            from app.agents.llm import LLMPolicy  # 懒导入避免循环

            policy = LLMPolicy()
        self.policy = policy

    def act(self, engine: GameEngine, state: GameState, seat: Seat) -> Optional[Action]:
        return self.policy.decide(engine, state, seat)
