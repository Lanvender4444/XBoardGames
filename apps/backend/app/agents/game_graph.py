"""[已废弃] 外层游戏循环图 —— 现已由 ``app.agents.orchestrator`` 取代。

旧版是一个 ``play_phase`` 节点 + 自循环条件边的线性图；新版编排器把每个阶段显式区分为
**抢占式（并发思考→顺序仲裁）** 与 **排队式（轮流发言）** 两种多人行动模式，语义更完整。
本模块保留为兼容别名，新代码请直接用 ``orchestrator``。
"""
from __future__ import annotations

from app.agents.orchestrator import build_orchestrator as build_game_graph  # noqa: F401
from app.agents.orchestrator import run_orchestrator as run_game_graph  # noqa: F401

__all__ = ["build_game_graph", "run_game_graph"]
