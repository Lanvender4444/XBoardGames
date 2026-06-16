"""AI 玩家决策子图（Start.md §10，Phase 2 占位）。

内层决策子图（对每个需要行动的 AI 角色调用一次）：
    感知(Perceive) → 召回(Recall) → 推理(Reason) → 行动(Act) → 编码(Encode)

要点：
- 人物卡驱动差异：persona/traits 注入 prompt（§10）。
- 合法性双保险：LLM 产出的行动仍要过引擎 ``validate``，非法则重试或回退安全默认（§10 / §15）。
- 成本控制：召回 top-k、限制 STM 窗口、低风险阶段降级到小模型（§10）。

当前提供一个**随机合法行动**的基线策略（``RandomPolicy``），无需 LLM 即可驱动引擎跑通整局，
供 CLI 自动对局与测试使用；LangGraph 真实子图在 Phase 2 接入。
"""

from __future__ import annotations

import random
from typing import Optional, Protocol

from app.engine import Action, GameEngine, GameState, Seat


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


class DecisionGraph:
    """LangGraph 决策子图（占位）。Phase 2 用 langgraph 实现感知/召回/推理/行动/编码节点。"""

    def __init__(self) -> None:
        # TODO Phase 2: build StateGraph with perceive/recall/reason/act/encode nodes.
        raise NotImplementedError("LangGraph 决策子图待 Phase 2 接入")


class AIPlayer:
    """绑定一张人物卡的 AI 玩家（占位）。"""

    def __init__(self, character_id: int, policy: Optional[Policy] = None) -> None:
        self.character_id = character_id
        self.policy = policy or RandomPolicy()

    def act(self, engine: GameEngine, state: GameState, seat: Seat) -> Optional[Action]:
        return self.policy.decide(engine, state, seat)
