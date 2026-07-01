"""核心关系表（Start.md §5）。

设计点：``session_events`` 是一切的底账——复盘、记忆固化、精彩瞬间提取都从它派生。
``visibility`` 决定某条事件对谁可见（狼队私聊、预言家查验结果只对本人可见等）。
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.models.base import Base, TimestampMixin


class Game(Base, TimestampMixin):
    """游戏定义（由 Rule.md 编译产物快照）。"""

    __tablename__ = "games"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)  # werewolf/avalon
    name: Mapped[str] = mapped_column(String(128))
    min_players: Mapped[int] = mapped_column(Integer)
    max_players: Mapped[int] = mapped_column(Integer)
    rule_md: Mapped[str] = mapped_column(Text)  # 原始 Rule.md 文本
    definition: Mapped[dict] = mapped_column(JSON)  # 编译后的可执行定义
    source: Mapped[str] = mapped_column(String(16), default="builtin")  # builtin/generated
    version: Mapped[int] = mapped_column(Integer, default=1)


class RuleDocument(Base, TimestampMixin):
    """上传的规则源文书。"""

    __tablename__ = "rule_documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[Optional[int]] = mapped_column(ForeignKey("games.id"), nullable=True)
    filename: Mapped[str] = mapped_column(String(255))
    storage_path: Mapped[str] = mapped_column(String(512))
    mime: Mapped[str] = mapped_column(String(128))
    extract_status: Mapped[str] = mapped_column(String(32), default="pending")


class GameSession(Base, TimestampMixin):
    """一局游戏实例。"""

    __tablename__ = "game_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"))
    host_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    mode: Mapped[str] = mapped_column(String(16))  # lan/server
    status: Mapped[str] = mapped_column(String(16), default="lobby")  # lobby/running/finished
    seed: Mapped[int] = mapped_column(Integer)  # 随机种子，用于复盘
    snapshot_ref: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)  # Redis 热键
    result: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)


class User(Base, TimestampMixin):
    """人类玩家。"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    display_name: Mapped[str] = mapped_column(String(64))
    identity_hash: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)  # LAN: MAC+UUID
    auth: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # server 凭证


class SessionPlayer(Base, TimestampMixin):
    """某局的参与者（人或 AI）。"""

    __tablename__ = "session_players"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("game_sessions.id"), index=True)
    seat: Mapped[int] = mapped_column(Integer)
    actor_type: Mapped[str] = mapped_column(String(8))  # human/ai
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    character_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("character_cards.id"), nullable=True
    )
    assigned_role: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)


class CharacterCard(Base, TimestampMixin):
    """AI 人物卡。"""

    __tablename__ = "character_cards"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    avatar: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    persona: Mapped[str] = mapped_column(Text)  # 性格/口吻/策略倾向的 prompt 描述
    traits: Mapped[dict] = mapped_column(JSON)  # 谨慎度、攻击性、欺骗倾向等数值
    owner_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)


class CharacterBond(Base, TimestampMixin):
    """羁绊（有向）。直接影响 AI 行为（§8.1）。"""

    __tablename__ = "character_bonds"

    id: Mapped[int] = mapped_column(primary_key=True)
    from_character_id: Mapped[int] = mapped_column(ForeignKey("character_cards.id"), index=True)
    to_character_id: Mapped[int] = mapped_column(ForeignKey("character_cards.id"), index=True)
    affinity: Mapped[int] = mapped_column(Integer, default=0)  # -100~100 信任/好感
    tags: Mapped[dict] = mapped_column(JSON)  # 背叛过、救过、宿敌...
    last_updated_session_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("game_sessions.id"), nullable=True
    )


class LongTermMemory(Base, TimestampMixin):
    """长期记忆（跨局）。"""

    __tablename__ = "long_term_memories"

    id: Mapped[int] = mapped_column(primary_key=True)
    character_id: Mapped[int] = mapped_column(ForeignKey("character_cards.id"), index=True)
    kind: Mapped[str] = mapped_column(String(16))  # semantic/episodic
    content: Mapped[str] = mapped_column(Text)  # 自然语言摘要
    embedding_ref: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)  # 向量库引用
    salience: Mapped[float] = mapped_column(Integer, default=1)  # 重要度
    related_character_ids: Mapped[dict] = mapped_column(JSON)
    source_session_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("game_sessions.id"), nullable=True
    )


class HighlightMoment(Base, TimestampMixin):
    """精彩瞬间（§8.3）。"""

    __tablename__ = "highlight_moments"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("game_sessions.id"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    summary: Mapped[str] = mapped_column(Text)
    participants: Mapped[dict] = mapped_column(JSON)
    kind: Mapped[str] = mapped_column(String(64))  # 神预言/极限翻盘/经典欺骗...
    replay_ref: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)  # 事件区间
    shared: Mapped[bool] = mapped_column(default=False)


class SessionEvent(Base):
    """事件日志（复盘 + 记忆来源）。一切的底账（§5 设计点）。"""

    __tablename__ = "session_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("game_sessions.id"), index=True)
    seq: Mapped[int] = mapped_column(Integer)
    phase: Mapped[str] = mapped_column(String(64))
    actor: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # seat
    action: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSON)
    visibility: Mapped[str] = mapped_column(String(16), default="public")  # public/private/faction
