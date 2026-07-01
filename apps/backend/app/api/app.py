"""FastAPI 应用入口（Start.md §12 / §13）。

提供 HTTP（健康检查、大厅房间、规则上传/校验/编译、可玩对局、LLM 配置）与 WebSocket（对局实时）端点。
LAN 模式下作为 Tauri 的 Python sidecar 启动，绑定 0.0.0.0:PORT（§9.2）。

fastapi 为可选依赖（``uv sync --extra api``）；本模块在 create_app 内部懒导入，
未安装时给出明确提示，不影响引擎/CLI/记忆/联机这些纯逻辑模块的导入。
"""

from typing import Optional

from app.engine.types import Seat
from app.multiplayer import SessionManager, announce_room, discover_rooms
from app.rules.compiler import load_builtin


def create_app(session_manager: Optional[SessionManager] = None):
    """构造 FastAPI 实例。需 ``uv sync --extra api``。"""
    try:
        from fastapi import FastAPI
        from fastapi.middleware.cors import CORSMiddleware
        from pydantic import BaseModel
    except ImportError as e:  # pragma: no cover
        raise ImportError("FastAPI 未安装，请先执行 `uv sync --extra api`") from e

    from app.api.play import build_play_router
    from app.api.routes_rules import build_router
    from app.api.ws import register_ws

    sm = session_manager or SessionManager()
    app = FastAPI(title="AI Tabletop", version="0.1.0")
    # 前端(vite dev / tauri)与后端不同源，开放 CORS（LAN 本地工具，宽松即可）
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=False,
    )

    @app.get("/health")
    def _health() -> dict:
        return {"status": "ok"}

    @app.get("/rooms")
    def _rooms() -> dict:
        return {"rooms": discover_rooms()}

    class CreateIn(BaseModel):
        slug: str = "werewolf"
        players: int = 8
        seed: Optional[int] = None
        human_seats: list[int] = [0]

    @app.post("/sessions")
    def _create(body: CreateIn) -> dict:
        defn = load_builtin(body.slug)
        seats = [
            Seat(seat_id=i, actor_type=("human" if i in body.human_seats else "ai"))
            for i in range(body.players)
        ]
        sid = sm.create_session(defn, seats, seed=body.seed)
        announce_room(sid, "127.0.0.1", 8765, name=body.slug)
        return {"session_id": sid, "snapshot": sm.snapshot(sid), "request_action": sm.request_action(sid)}

    @app.get("/sessions/{session_id}")
    def _snapshot(session_id: str, seat: Optional[int] = None) -> dict:
        return {"snapshot": sm.snapshot(session_id, for_seat=seat),
                "request_action": sm.request_action(session_id)}

    app.include_router(build_router())
    app.include_router(build_play_router())
    register_ws(app, sm)
    app.state.session_manager = sm
    return app
