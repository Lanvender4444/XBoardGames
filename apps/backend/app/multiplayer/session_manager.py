"""会话管理 + 连接生命周期（Start.md §9）。

服务器权威：后端是状态唯一权威，客户端只发意图行动（§9.1）。本管理器把引擎、热状态(StateStore)、
广播(EventBus) 三者粘合：
- create_session：初始化引擎状态，登记到内存会话表，并把快照写入 StateStore（供重连）。
- request_action：列出当前该行动的席位与其合法行动（request_action 必带 legal_actions，§12）。
- submit_action：校验意图 → 引擎 apply → 所有人都行动完则 advance_phase → 按席位可见性广播事件。
- on_disconnect：标记离线；可选 AI 托管该席位（drive_ai 驱动）。

依赖均走存储抽象层：默认内存实现即可单机/单测跑通；Phase 3 换真实 Redis(StateStore/EventBus)
时本类不变。
"""
from __future__ import annotations

import itertools
import uuid
from typing import Optional

from app.api import protocol
from app.engine import GameEngine
from app.engine.types import Action, GameDefinition, GameState, Seat
from app.storage import EventBus, StateStore, get_event_bus, get_state_store

_seq = itertools.count(1)


class SessionManager:
    def __init__(
        self,
        engine: Optional[GameEngine] = None,
        state_store: Optional[StateStore] = None,
        event_bus: Optional[EventBus] = None,
    ) -> None:
        self.engine = engine or GameEngine()
        self._store = state_store or get_state_store()
        self._bus = event_bus or get_event_bus()
        self._sessions: dict[str, GameState] = {}
        self._offline: dict[str, set[int]] = {}

    # ---------------------------------------------------------------- channels
    @staticmethod
    def _channel(session_id: str) -> str:
        return f"channel:session:{session_id}"

    @staticmethod
    def _snap_key(session_id: str) -> str:
        return f"session:{session_id}:snapshot"

    # ----------------------------------------------------------------- create
    def create_session(
        self,
        definition: GameDefinition,
        players: list[Seat],
        mode: str = "lan",
        seed: Optional[int] = None,
    ) -> str:
        session_id = uuid.uuid4().hex[:12]
        state = self.engine.init_session(definition, players, seed=seed)
        self._sessions[session_id] = state
        self._offline[session_id] = set()
        self._persist(session_id)
        return session_id

    def state(self, session_id: str) -> GameState:
        return self._sessions[session_id]

    def snapshot(self, session_id: str, for_seat: Optional[int] = None) -> dict:
        return protocol.snapshot_payload(self._sessions[session_id], for_seat=for_seat)

    def _persist(self, session_id: str) -> None:
        env = protocol.Envelope("state_snapshot", session_id, next(_seq),
                                protocol.snapshot_payload(self._sessions[session_id]))
        self._store.set(self._snap_key(session_id), env.to_json())

    # --------------------------------------------------------- request_action
    def request_action(self, session_id: str) -> list[dict]:
        """列出当前需行动的席位与其合法行动（前端据此渲染，保证与引擎一致）。"""
        state = self._sessions[session_id]
        out = []
        for seat in self.engine.actors_to_act(state):
            legal = self.engine.legal_actions(state, seat)
            out.append({
                "seat": seat.seat_id,
                "legal_actions": [protocol.action_to_payload(a) for a in legal],
            })
        return out

    # ----------------------------------------------------------- submit_action
    def submit_action(self, session_id: str, action: Action | dict) -> list:
        """客户端意图行动 → 引擎校验/改状态 → 广播（§9.1）。返回本次新增事件。"""
        state = self._sessions[session_id]
        if isinstance(action, dict):
            action = protocol.action_from_payload(action)
        _, events = self.engine.apply(state, action)  # 非法行动会抛 IllegalActionError
        self._broadcast_events(session_id, events)

        # 所有该行动的席位都已行动 → 推进阶段
        if not self.engine.actors_to_act(state):
            prev_phase = state.phase
            _, adv = self.engine.advance_phase(state)
            self._broadcast_events(session_id, adv)
            if state.phase != prev_phase and not state.finished:
                self._publish(session_id, "phase_changed", {"phase": state.phase, "round": state.round})
            if state.finished:
                self._publish(session_id, "game_over",
                              {"faction": state.winner.faction, "reason": state.winner.reason})
            events = events + adv
        self._persist(session_id)
        return events

    def _broadcast_events(self, session_id: str, events: list) -> None:
        for ev in events:
            self._publish(session_id, "event", protocol.event_to_payload(ev))

    def _publish(self, session_id: str, mtype: str, payload: dict) -> None:
        env = protocol.Envelope(mtype, session_id, next(_seq), payload)
        self._bus.publish(self._channel(session_id), env.to_json())

    # ------------------------------------------------------ connection lifecycle
    def on_disconnect(self, session_id: str, seat: int, ai_takeover: bool = True) -> None:
        """标记某席位离线；可选把该席位交给 AI 托管继续。"""
        self._offline.setdefault(session_id, set()).add(seat)
        if ai_takeover:
            self._sessions[session_id].seat(seat).actor_type = "ai"
        self._publish(session_id, "event",
                      {"action": "seat_offline", "seat": seat, "ai_takeover": ai_takeover})

    def on_reconnect(self, session_id: str, seat: int) -> dict:
        self._offline.get(session_id, set()).discard(seat)
        return self.snapshot(session_id, for_seat=seat)

    def is_offline(self, session_id: str, seat: int) -> bool:
        return seat in self._offline.get(session_id, set())

    # ------------------------------------------------------------- AI driving
    def drive_ai(self, session_id: str, policies: dict, max_rounds: int = 100) -> None:
        """无人类时（或 AI 托管），用 policies 把所有 AI 席位的行动推进到对局结束。"""
        state = self._sessions[session_id]
        rounds = 0
        while not state.finished and rounds < max_rounds:
            actors = self.engine.actors_to_act(state)
            if not actors:
                self._broadcast_events(session_id, self.engine.advance_phase(state)[1])
                rounds += 1
                continue
            for seat in actors:
                pol = policies.get(seat.seat_id)
                if pol is None:
                    continue
                a = pol.decide(self.engine, state, seat)
                if a is not None:
                    self.submit_action(session_id, a)
        self._persist(session_id)
