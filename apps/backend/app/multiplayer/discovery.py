"""LAN 房间发现（Start.md §9.2）。

host 通过 mDNS/UDP 宣告房间；同网段客户端收到后在大厅列出。实际 UDP/mDNS 通常落在 Tauri 的
Rust 核心（apps/desktop/src-tauri）；本模块是**后端侧的房间登记/查询**实现：进程内注册表，
单机/服务器场景直接可用，LAN 场景由 Rust 侧把发现到的房间灌入或镜像到这里。
"""
from __future__ import annotations

import time

# 进程内房间注册表：session_id -> 房间信息
_ROOMS: dict[str, dict] = {}


def announce_room(session_id: str, host_addr: str, port: int, name: str = "") -> dict:
    """登记/更新一个房间宣告。"""
    room = {
        "session_id": session_id,
        "host_addr": host_addr,
        "port": port,
        "name": name or session_id,
        "ts": time.time(),
    }
    _ROOMS[session_id] = room
    return room


def withdraw_room(session_id: str) -> None:
    _ROOMS.pop(session_id, None)


def discover_rooms(timeout: float = 2.0, max_age: float = 30.0) -> list[dict]:
    """返回当前可见的房间（过滤掉过期宣告）。"""
    now = time.time()
    fresh = [r for r in _ROOMS.values() if now - r["ts"] <= max_age]
    return sorted(fresh, key=lambda r: r["ts"], reverse=True)


def clear_rooms() -> None:
    _ROOMS.clear()
