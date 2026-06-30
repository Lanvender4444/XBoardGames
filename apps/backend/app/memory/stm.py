"""短期记忆 STM（Start.md §8.1）。

作用域=单局。每个 AI 角色维护本局的"心证"——对其他席位的身份猜测、信任度、关键发言摘要。
存 StateStore（键 ``session:{id}:stm:{character_id}``，hash 结构、带 TTL），局结束 ``clear``。

实现说明：每个被观察席位对应 hash 的一个 field（field=seat 号，value=Belief 的 JSON）。
默认 StateStore 为内存实现（贴近 Redis hash 语义），Phase 3 换真实 Redis 时本模块无需改动。
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Optional

from app.storage import StateStore, get_state_store


@dataclass
class Belief:
    """对某席位的心证。"""

    seat: int
    suspected_faction: Optional[str] = None
    trust: int = 0  # -100~100
    notes: list[str] = field(default_factory=list)

    def clamp(self) -> "Belief":
        self.trust = max(-100, min(100, self.trust))
        return self


class ShortTermMemory:
    def __init__(
        self, session_id: int, character_id: int, store: Optional[StateStore] = None
    ) -> None:
        self.session_id = session_id
        self.character_id = character_id
        self._store = store or get_state_store()

    def _key(self) -> str:
        return f"session:{self.session_id}:stm:{self.character_id}"

    def update_belief(self, belief: Belief, ttl: int = 3600) -> None:
        """写入/覆盖对某席位的心证，并续期整个 STM 键。"""
        key = self._key()
        self._store.hset(key, str(belief.seat), json.dumps(asdict(belief.clamp())))
        self._store.expire(key, ttl)

    def belief(self, seat: int) -> Optional[Belief]:
        raw = self._store.hgetall(self._key()).get(str(seat))
        if raw is None:
            return None
        return Belief(**json.loads(raw))

    def beliefs(self) -> list[Belief]:
        out = [Belief(**json.loads(v)) for v in self._store.hgetall(self._key()).values()]
        out.sort(key=lambda b: b.seat)
        return out

    def note(self, seat: int, text: str, ttl: int = 3600) -> None:
        """便捷：往某席位心证追加一条观察笔记（不存在则新建）。"""
        b = self.belief(seat) or Belief(seat=seat)
        b.notes.append(text)
        self.update_belief(b, ttl=ttl)

    def adjust_trust(self, seat: int, delta: int, ttl: int = 3600) -> None:
        b = self.belief(seat) or Belief(seat=seat)
        b.trust += delta
        self.update_belief(b, ttl=ttl)

    def clear(self) -> None:
        self._store.delete(self._key())
