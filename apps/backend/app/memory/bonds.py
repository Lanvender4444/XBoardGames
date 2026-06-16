"""羁绊 Bonds（Start.md §8.1，Phase 2 占位）。

角色间有向关系：affinity(-100~100) + 标签（救过我/坑过我/宿敌）。每局结束按共同经历更新，
**直接影响 AI 行为**：对高好感者更倾向相信/组队/护体，对宿敌更倾向针对（§8.2 行为偏置）。
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Bond:
    from_character_id: int
    to_character_id: int
    affinity: int = 0
    tags: list[str] = field(default_factory=list)


class BondGraph:
    def affinity(self, frm: int, to: int) -> int:
        raise NotImplementedError("羁绊读取待 Phase 2 接入（character_bonds 表）")

    def apply_outcome(self, session_id: int, events: list) -> None:
        """根据共同经历更新羁绊（谁救了谁、谁出卖了谁）。"""
        raise NotImplementedError("羁绊更新待 Phase 2 接入")

    def to_behavior_bias(self, character_id: int, present_seats: list[int]) -> dict:
        """转成 prompt 行为偏置（§8.2）。"""
        raise NotImplementedError("羁绊→行为偏置待 Phase 2 接入")
