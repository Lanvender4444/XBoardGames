"""中期记忆 MTM（Start.md §8）——作用域=**本局跨回合**。

三级记忆的中间层：
- STM 短期：**即时心证**（当前对各席位的怀疑/信任），随时更新、颗粒最细。
- MTM 中期：**本局到目前为止**的关键信息滚动摘要（谁哪晚死的、我查到过什么、局势走向），跨回合累积、局末清空。
- LTM 长期：**跨局**的稳定印象与羁绊。

MTM 既可主动 ``add_note`` 记要点，也能 ``summary(state, seat)`` 从共享事件日志按可见性即时汇总本局态势。
存 StateStore（键 ``session:{id}:mtm:{cid}``），局末 ``clear``。
"""
from __future__ import annotations

import json
from typing import Optional

from app.engine.types import Visibility
from app.storage import StateStore, get_state_store


class MediumTermMemory:
    def __init__(self, session_id: int, character_id: int, store: Optional[StateStore] = None) -> None:
        self.session_id = session_id
        self.character_id = character_id
        self._store = store or get_state_store()

    def _key(self) -> str:
        return f"session:{self.session_id}:mtm:{self.character_id}"

    def add_note(self, round_no: int, text: str, ttl: int = 7200) -> None:
        key = self._key()
        notes = self.notes()
        notes.append({"round": round_no, "text": text})
        self._store.set(key, json.dumps(notes[-40:]), ttl=ttl)

    def notes(self) -> list:
        raw = self._store.get(self._key())
        return json.loads(raw) if raw else []

    def clear(self) -> None:
        self._store.delete(self._key())

    # 从共享事件日志按可见性汇总"本局到现在"的态势（无需显式记 note 也能用）
    def summary(self, state, seat) -> str:
        deaths, my_finds, votes = [], [], []
        for e in state.log:
            if e.action == "death":
                cause = "夜里" if e.payload.get("cause") == "eliminate" else "被票"
                deaths.append(f"R{e.round} #{e.payload.get('seat')}{cause}出局")
            elif e.action == "investigate_result" and e.actor == seat.seat_id:
                my_finds.append(f"R{e.round} 我查 #{e.payload.get('target')}={e.payload.get('value')}")
            elif e.action == "vote_result":
                votes.append(f"R{e.round} 计票{e.payload.get('tally')}")
        parts = []
        if my_finds:
            parts.append("（我的私密线索）" + "；".join(my_finds))
        if deaths:
            parts.append("出局记录：" + "；".join(deaths[-6:]))
        if votes:
            parts.append(votes[-1])
        stored = [f"R{n['round']}:{n['text']}" for n in self.notes()[-6:]]
        if stored:
            parts.append("我的笔记：" + "；".join(stored))
        return "｜".join(parts) if parts else "本局暂无重大事件"
