"""通信协议 Python 端镜像（Start.md §12）。

与 packages/protocol/src/messages.ts 保持一致（单一定义、生成 TS+Python，避免漂移）。
消息信封：{ "type", "session_id", "seq", "payload" }。

除常量与 ``Envelope`` 外，提供与引擎 ``Action`` / ``Event`` / 快照互转的编解码助手，
供联机层（SessionManager / WebSocket 端点）直接使用。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from app.engine.types import Action, Event, GameState, Visibility

# 客户端 -> 服务器
CLIENT_MESSAGES = {"join", "leave", "submit_action", "chat", "heartbeat"}
# 服务器 -> 客户端
SERVER_MESSAGES = {
    "state_snapshot", "state_patch", "event",
    "request_action", "phase_changed", "game_over", "error",
}


@dataclass
class Envelope:
    type: str
    session_id: str
    seq: int = 0
    payload: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(
            {"type": self.type, "session_id": self.session_id, "seq": self.seq, "payload": self.payload},
            ensure_ascii=False,
        )

    @staticmethod
    def from_json(raw: str) -> "Envelope":
        d = json.loads(raw)
        return Envelope(d["type"], d["session_id"], d.get("seq", 0), d.get("payload", {}))


# --------------------------- Action 编解码 --------------------------- #
def action_to_payload(a: Action) -> dict:
    return {"seat": a.seat, "type": a.type, "targets": list(a.targets),
            "channel": a.channel, "extra": a.extra}


def action_from_payload(p: dict) -> Action:
    return Action(
        seat=p["seat"],
        type=p["type"],
        targets=tuple(p.get("targets", []) or []),
        channel=p.get("channel"),
        extra=p.get("extra", {}) or {},
    )


# --------------------------- Event / 快照编码 --------------------------- #
def event_to_payload(e: Event) -> dict:
    return {
        "seq": e.seq, "phase": e.phase, "round": e.round, "actor": e.actor,
        "action": e.action, "payload": e.payload,
        "visibility": e.visibility.value if isinstance(e.visibility, Visibility) else e.visibility,
        "audience": list(e.audience),
    }


def visible_to(e: Event, seat: int) -> bool:
    """该事件是否对指定席位可见（服务器据此做按席位投递）。"""
    if e.visibility == Visibility.PUBLIC:
        return True
    return seat in e.audience


def snapshot_payload(state: GameState, *, for_seat: int | None = None) -> dict:
    """对外的状态快照：座位（含身份按可见性裁剪）、阶段、回合、可见事件。"""
    seats = []
    for s in state.seats:
        reveal = state.finished or (for_seat is not None and s.seat_id == for_seat)
        seats.append({
            "seat": s.seat_id, "name": s.name, "alive": s.alive,
            "actor_type": s.actor_type,
            "role": s.role if reveal else None,
            "faction": s.faction if reveal else None,
        })
    log = [event_to_payload(e) for e in state.log
           if for_seat is None or visible_to(e, for_seat)]
    return {
        "slug": state.definition.slug, "phase": state.phase, "round": state.round,
        "seq": state.seq, "finished": state.finished,
        "winner": state.winner.faction if state.winner else None,
        "seats": seats, "log": log,
    }
