"""会话管理 + 连接生命周期（Start.md §9.4，Phase 3 占位）。

入局：WS 握手 → 鉴权/身份 → 加入 presence → 订阅 channel:session:{id} → 收快照。
断线：心跳过期 → 标记离线；人类超时可由 AI 托管该席位继续（可配置）。
重连：凭 session token 重新订阅，拉最新快照 + 增量事件补齐。
"""
from __future__ import annotations

from typing import Optional

from app.engine import GameEngine
from app.storage import EventBus, StateStore


class SessionManager:
    def __init__(
        self,
        engine: Optional[GameEngine] = None,
        state_store: Optional[StateStore] = None,
        event_bus: Optional[EventBus] = None,
    ) -> None:
        self.engine = engine or GameEngine()
        self._store = state_store
        self._bus = event_bus

    def create_session(self, definition, players, mode: str = "lan") -> str:
        raise NotImplementedError("会话创建/快照入 Redis 待 Phase 3 接入")

    def submit_action(self, session_id: str, action) -> None:
        """客户端意图行动 → 引擎校验 → 改状态 → Redis Pub/Sub 广播（§9.1）。"""
        raise NotImplementedError("行动提交/广播待 Phase 3 接入")

    def on_disconnect(self, session_id: str, seat: int) -> None:
        raise NotImplementedError("断线处理/AI 托管待 Phase 3 接入")
