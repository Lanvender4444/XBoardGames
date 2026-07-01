"""便捷启动器：``uv run serve`` 即启动后端（避免 uvicorn CLI 字符串各种坑）。

等价于 ``uvicorn app.api.app:create_app --factory --host 0.0.0.0 --port 8000``，
但把 host/port 做成环境变量可配（XBOARD_HOST / XBOARD_PORT），并给出清晰的启动提示。
"""
from __future__ import annotations

import os


def main() -> None:
    try:
        import uvicorn
    except ImportError as e:  # pragma: no cover
        raise SystemExit("uvicorn 未安装，请先执行 `uv sync --extra api`") from e

    host = os.getenv("XBOARD_HOST", "0.0.0.0")
    port = int(os.getenv("XBOARD_PORT", "8000"))
    print(f"[AI Tabletop] 后端启动中 → http://localhost:{port}  (前端默认连这个地址)")
    print("[AI Tabletop] 健康检查: GET /health ；对局: POST /games ；LLM 配置: /llm/config ；测试: /llm/test")
    uvicorn.run("app.api.app:create_app", host=host, port=port, factory=True)


if __name__ == "__main__":
    main()
