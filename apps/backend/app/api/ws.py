"""WebSocket 端点（Start.md §12）。

服务器→客户端的 ``request_action`` 一定带 ``legal_actions``，前端据此渲染可点选项，
保证前端展示与引擎判定一致（§12 末）。

连接生命周期：
  握手 accept → 下发 state_snapshot（按席位裁剪可见性）→ 若该席位需行动则发 request_action →
  循环接收 submit_action/heartbeat/leave → 每次提交后回传新增 event + 下一个 request_action。

多客户端扇出在生产中走 EventBus(Redis Pub/Sub)；此处为单连接的协议环参考实现，逻辑与单测一致。
"""
from typing import Optional

from app.api import protocol
from app.multiplayer import SessionManager


async def ws_endpoint(websocket, session_id: str, seat: int, sm: SessionManager) -> None:
    from starlette.websockets import WebSocketDisconnect

    await websocket.accept()
    # 1) 下发快照
    await websocket.send_text(
        protocol.Envelope("state_snapshot", session_id, 0, sm.snapshot(session_id, for_seat=seat)).to_json()
    )
    await _maybe_request(websocket, session_id, seat, sm)
    try:
        while True:
            raw = await websocket.receive_text()
            env = protocol.Envelope.from_json(raw)
            if env.type == "leave":
                break
            if env.type == "heartbeat":
                continue
            if env.type == "submit_action":
                try:
                    events = sm.submit_action(session_id, env.payload)
                except Exception as e:  # 非法行动等：回 error，不断开
                    await websocket.send_text(
                        protocol.Envelope("error", session_id, 0, {"message": str(e)}).to_json()
                    )
                    continue
                for ev in events:
                    if protocol.visible_to(ev, seat):
                        await websocket.send_text(
                            protocol.Envelope("event", session_id, ev.seq, protocol.event_to_payload(ev)).to_json()
                        )
                await _maybe_request(websocket, session_id, seat, sm)
    except WebSocketDisconnect:
        sm.on_disconnect(session_id, seat)


async def _maybe_request(websocket, session_id: str, seat: int, sm: SessionManager) -> None:
    """若该席位当前需要行动，下发带 legal_actions 的 request_action。"""
    for req in sm.request_action(session_id):
        if req["seat"] == seat:
            await websocket.send_text(
                protocol.Envelope("request_action", session_id, 0, req).to_json()
            )


def register_ws(app, sm: SessionManager) -> None:
    """把 WS 路由挂到 FastAPI app（懒导入，调用方已在 fastapi 环境内）。"""

    from fastapi import WebSocket

    @app.websocket("/ws/{session_id}/{seat}")
    async def _ws(websocket: WebSocket, session_id: str, seat: int):
        await ws_endpoint(websocket, session_id, seat, sm)
