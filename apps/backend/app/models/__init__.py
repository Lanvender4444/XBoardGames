"""SQLAlchemy 模型（Start.md §5）。

需要 ``sqlalchemy`` 依赖（``uv sync --extra storage``）。引擎/CLI 不依赖本包，
因此核心可在无 SQLAlchemy 时运行。
"""

from app.models.base import Base
from app.models.entities import (
    CharacterBond,
    CharacterCard,
    Game,
    GameSession,
    HighlightMoment,
    LongTermMemory,
    RuleDocument,
    SessionEvent,
    SessionPlayer,
    User,
)

__all__ = [
    "Base",
    "Game",
    "RuleDocument",
    "GameSession",
    "User",
    "SessionPlayer",
    "CharacterCard",
    "CharacterBond",
    "LongTermMemory",
    "HighlightMoment",
    "SessionEvent",
]
