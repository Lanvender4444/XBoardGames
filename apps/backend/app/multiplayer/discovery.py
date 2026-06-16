"""LAN 房间发现（Start.md §9.2，Phase 3 占位）。

host 通过 mDNS 或 UDP 广播宣告房间；同网段客户端收到后在大厅列出。
（实际 UDP 发现通常在 Tauri 的 Rust 核心实现，见 apps/desktop/src-tauri；
此处为后端侧的房间登记/查询接口占位。）
"""
from __future__ import annotations


def announce_room(session_id: str, host_addr: str, port: int) -> None:
    raise NotImplementedError("mDNS/UDP 房间宣告待 Phase 3 接入")


def discover_rooms(timeout: float = 2.0) -> list[dict]:
    raise NotImplementedError("房间发现待 Phase 3 接入")
