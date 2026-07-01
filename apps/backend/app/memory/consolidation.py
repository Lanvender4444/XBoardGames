"""局结束记忆固化（Start.md §8.4）。

一局结束触发：
1. 从事件流识别精彩瞬间（episodic）+ 从终局身份提炼稳定印象（semantic）。
2. 写入 LTM（生成 embedding 入向量库，设 salience）。
3. 根据共同经历更新所有相关羁绊（BondGraph）。
4. 清理本局所有角色的 STM。

把"单局短期信息"沉淀为"跨局长期记忆 + 羁绊"——下一局的召回/行为偏置即来源于此。
所有依赖均可注入，缺省用各自默认实现，保证无外部依赖即可运行。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.memory.bonds import BondGraph
from app.memory.embedding import Embedder, get_embedder
from app.memory.highlights import HighlightEvaluator
from app.memory.ltm import LongTermMemoryStore, Memory
from app.memory.stm import ShortTermMemory


@dataclass
class ConsolidationResult:
    episodic_written: int
    semantic_written: int
    highlights: list
    bonds_updated: bool


def consolidate_session(
    session_id: int,
    events: Optional[list] = None,
    seats: Optional[list] = None,
    *,
    ltm: Optional[LongTermMemoryStore] = None,
    bonds: Optional[BondGraph] = None,
    evaluator: Optional[HighlightEvaluator] = None,
    embedder: Optional[Embedder] = None,
    seat_to_char: Optional[dict] = None,
    ai_character_ids: Optional[list] = None,
) -> ConsolidationResult:
    events = events or []
    seats = seats or []
    ltm = ltm or LongTermMemoryStore(embedder=embedder or get_embedder())
    bonds = bonds or BondGraph()
    evaluator = evaluator or HighlightEvaluator()
    m = seat_to_char or {s.seat_id: s.seat_id for s in seats}

    # 1) episodic：精彩瞬间 → 每个参与者各记一条
    highlights = evaluator.scan(session_id, events)
    episodic = 0
    for h in highlights:
        for seat in h.participants:
            cid = m.get(seat, seat)
            ltm.write(
                Memory(
                    character_id=cid,
                    kind="episodic",
                    content=f"{h.title}：{h.summary}",
                    salience=0.8,
                    related_character_ids=[m.get(s, s) for s in h.participants if s != seat],
                )
            )
            episodic += 1

    # 2) semantic：终局身份 → 每个 AI 角色对其他人形成稳定印象
    semantic = 0
    ai_seats = [s for s in seats if getattr(s, "actor_type", "ai") == "ai"]
    for obs in ai_seats:
        ocid = m.get(obs.seat_id, obs.seat_id)
        for other in seats:
            if other.seat_id == obs.seat_id:
                continue
            ltm.write(
                Memory(
                    character_id=ocid,
                    kind="semantic",
                    content=f"#{other.seat_id}（{other.role}）属于 {other.faction} 阵营。",
                    salience=0.4,
                    related_character_ids=[m.get(other.seat_id, other.seat_id)],
                )
            )
            semantic += 1

    # 3) 羁绊更新
    bonds.apply_outcome(events, seat_to_char=m, session_id=session_id)

    # 4) 清理 STM
    for cid in ai_character_ids or [m.get(s.seat_id, s.seat_id) for s in ai_seats]:
        ShortTermMemory(session_id, cid).clear()

    return ConsolidationResult(
        episodic_written=episodic,
        semantic_written=semantic,
        highlights=highlights,
        bonds_updated=True,
    )
