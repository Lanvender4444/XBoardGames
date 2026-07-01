"""羁绊 Bonds（Start.md §8.1 / §8.2）。

角色间有向关系：affinity(-100~100) + 标签（救过我/票过我/宿敌…）。每局结束按共同经历更新，
**直接影响 AI 行为**：对高好感者更倾向相信/组队/护体，对宿敌更倾向针对。

实现说明：
- ``affinity[(frm,to)]`` 表示"frm 对 to 的好感"。``apply_outcome`` 从一局事件流读取谁对谁
  做了什么（救/票/夜杀），据此增减好感并打标签。
- ``to_behavior_bias`` 把羁绊翻译成 AI 决策可直接消费的偏置，由决策子图推理节点使用。
- 默认进程内存储；真实部署把存储换成 ``character_bonds`` 关系表即可，方法语义不变。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Optional

# 不同事件对"目标对行动者"的好感影响与标签
_RULES = {
    "protect_submitted": (15, "救过我"),
    "vote_submitted": (-10, "票过我"),
    "eliminate_submitted": (-12, "夜里下手"),
}
_ENEMY_THRESHOLD = -40
_ALLY_THRESHOLD = 30


@dataclass
class Bond:
    from_character_id: int
    to_character_id: int
    affinity: int = 0
    tags: list[str] = field(default_factory=list)

    def clamp(self) -> "Bond":
        self.affinity = max(-100, min(100, self.affinity))
        return self


class BondGraph:
    def __init__(self) -> None:
        self._bonds: dict[tuple[int, int], Bond] = {}

    def _bond(self, frm: int, to: int) -> Bond:
        key = (frm, to)
        if key not in self._bonds:
            self._bonds[key] = Bond(frm, to)
        return self._bonds[key]

    def affinity(self, frm: int, to: int) -> int:
        b = self._bonds.get((frm, to))
        return b.affinity if b else 0

    def tags(self, frm: int, to: int) -> list[str]:
        b = self._bonds.get((frm, to))
        return list(b.tags) if b else []

    def _adjust(self, frm: int, to: int, delta: int, tag: Optional[str]) -> None:
        if frm == to:
            return
        b = self._bond(frm, to)
        b.affinity += delta
        if tag and tag not in b.tags:
            b.tags.append(tag)
        if b.affinity <= _ENEMY_THRESHOLD and "宿敌" not in b.tags:
            b.tags.append("宿敌")
        b.clamp()

    def apply_outcome(
        self,
        events: Iterable,
        seat_to_char: Optional[dict] = None,
        session_id: Optional[int] = None,
    ) -> None:
        """根据一局共同经历更新羁绊（谁救了谁、谁票了谁、谁夜里下手）。

        events: 引擎产生的 Event 序列。seat_to_char: 席位→角色id 映射（缺省按席位号当角色id）。
        好感方向="目标对行动者"：A 救了 T → T 对 A↑；A 票/杀了 T → T 对 A↓。
        """
        m = seat_to_char or {}

        def cid(seat):
            return m.get(seat, seat)

        for ev in events:
            rule = _RULES.get(getattr(ev, "action", ""))
            actor = getattr(ev, "actor", None)
            if rule is None or actor is None:
                continue
            delta, tag = rule
            targets = getattr(ev, "payload", {}).get("targets", [])
            for t in targets:
                self._adjust(cid(t), cid(actor), delta, tag)

    def to_behavior_bias(self, character_id: int, present) -> dict:
        """把羁绊翻译成行为偏置，供决策子图推理节点使用（§8.2）。

        present: 当前在场席位→角色id 的映射（或直接给角色id 列表，此时键即角色id）。
        返回 ``{seat_id: {"affinity", "stance"(ally/enemy/neutral), "tags"}}``。
        """
        if isinstance(present, dict):
            items = list(present.items())
        else:
            items = [(c, c) for c in present]
        bias: dict = {}
        for seat_id, other_char in items:
            if other_char == character_id:
                continue
            aff = self.affinity(character_id, other_char)
            stance = (
                "ally" if aff >= _ALLY_THRESHOLD
                else "enemy" if aff <= _ENEMY_THRESHOLD
                else "neutral"
            )
            bias[seat_id] = {"affinity": aff, "stance": stance, "tags": self.tags(character_id, other_char)}
        return bias
