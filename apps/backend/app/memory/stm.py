"""短期记忆 STM（Start.md §8.1，Phase 2 占位）。

作用域=单局。每个 AI 角色维护本局的"心证"——对其他席位的身份猜测、信任度、关键发言摘要。
存 Redis（键 `session:{id}:stm:{character_id}`，带 TTL），局结束清空。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from app.storage import StateStore, get_state_store


@dataclass
class Belief:
    """对某席位的心证。"""
    seat: int
    suspected_faction: Optional[str] = None
    trust: int = 0  # -100~100
    notes: list[str] = field(default_factory=list)


class ShortTermMemory:
    def __init__(self, session_id: int, character_id: int, store: Optional[StateStore] = None):
        self.session_id = session_id
        self.character_id = character_id
        self._store = store or get_state_store()

    def _key(self) -> str:
        return f"session:{self.session_id}:stm:{self.character_id}"

    def update_belief(self, belief: Belief, ttl: int = 3600) -> None:
        raise NotImplementedError("STM 写入待 Phase 2 接入（JSON 序列化进 Redis hash）")

    def beliefs(self) -> list[Belief]:
        raise NotImplementedError("STM 读取待 Phase 2 接入")

    def clear(self) -> None:
        self._store.delete(self._key())
