"""FastAPI 路由 + WebSocket 端点（Start.md §12）。

- ``protocol``     通信协议镜像 + 编解码助手（无 fastapi 依赖，联机层直接复用）。
- ``app``          create_app 应用工厂（懒导入 fastapi）。
- ``routes_rules`` 规则管线路由 + 框架无关核心函数（validate/compile/ingest）。
- ``ws``           WebSocket 端点（request_action 必带 legal_actions）。
"""

__all__ = ["protocol"]
