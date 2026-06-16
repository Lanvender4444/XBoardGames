"""联机系统（Start.md §9，Phase 3 占位）。

引擎对"actor 是人/AI、本机/远程"无感知；联机层只解决发现、连接、广播三件事。
服务器权威：后端是状态唯一权威，客户端只发意图行动（§9.1）。
"""
from app.multiplayer.session_manager import SessionManager

__all__ = ["SessionManager"]
