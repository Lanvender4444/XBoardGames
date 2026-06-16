"""游戏引擎（Start.md §11）。

纯逻辑、可单测、不依赖网络与 LLM。引擎不区分行动来源：人类行动从 WebSocket 进来，
AI 行动从 LangGraph 进来，二者都变成 ``Action`` 喂给 ``apply``。
"""

from app.engine.engine import GameEngine
from app.engine.types import (
    Action,
    Event,
    GameDefinition,
    GameState,
    Seat,
    Visibility,
    WinResult,
)

__all__ = [
    "GameEngine",
    "GameDefinition",
    "GameState",
    "Seat",
    "Action",
    "Event",
    "WinResult",
    "Visibility",
]
