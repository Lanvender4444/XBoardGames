"""通信协议 Python 端镜像（Start.md §12）。

与 packages/protocol/src/messages.ts 保持一致（单一定义、生成 TS+Python，避免漂移）。
当前手写镜像；Phase 3 接入代码生成后由共享 schema 产出。
消息信封：{ "type", "session_id", "seq", "payload" }。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

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
