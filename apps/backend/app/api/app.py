"""FastAPI 应用入口（Start.md §12 / §13，Phase 3 占位）。

提供 HTTP（大厅、规则上传、Rule.md 编辑/校验/编译）与 WebSocket（对局实时）端点。
LAN 模式下作为 Tauri 的 Python sidecar 启动，绑定 0.0.0.0:PORT（§9.2）。
"""
from __future__ import annotations


def create_app():
    """构造 FastAPI 实例。需 `uv sync --extra api`。"""
    raise NotImplementedError(
        "FastAPI 应用待 Phase 3 接入；当前 Phase 1 通过 app.cli.autoplay 驱动引擎。"
    )
