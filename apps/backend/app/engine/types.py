"""引擎数据类型与已编译的游戏定义（Start.md §7.2 / §11）。

``GameDefinition`` 是 ``rules.compiler`` 的产物：状态机（阶段图）+ 原语绑定。引擎只认它。
所有类型为纯数据（dataclass），无网络/LLM 依赖，便于单测与（反）序列化。
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any, Optional, Union


class Visibility(str, enum.Enum):
    PUBLIC = "public"
    PRIVATE = "private"  # 只对行动者本人可见（如查验结果）
    FACTION = "faction"  # 只对同阵营可见（如狼队私聊）


# ---------------------------------------------------------------------------
# 已编译的游戏定义
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AbilityDef:
    """一个角色能力，已绑定到能力原语库中的一个原语（§7.3）。"""

    primitive: str  # eliminate / protect / investigate / vote / nominate / reveal / swap / assign / speak
    params: dict[str, Any] = field(default_factory=dict)
    phase: Optional[str] = None  # 该能力可用的阶段
    uses: Optional[int] = None  # 使用次数上限（None = 不限）
    visibility: Visibility = Visibility.PUBLIC


@dataclass(frozen=True)
class RoleDef:
    name: str
    faction: str
    count: Union[int, str]  # 具体数量，或 "rest" 占满剩余席位
    abilities: tuple[AbilityDef, ...] = ()
    channels: tuple[str, ...] = ()  # 私有频道（如 werewolf_chat）


@dataclass(frozen=True)
class PhaseDef:
    name: str
    actors: str  # 角色名列表(逗号分隔) | "all_alive" | "all"
    actor_roles: tuple[str, ...] = ()  # 解析后的具体角色名（actors 为角色列表时）
    actions: tuple[str, ...] = ()  # 本阶段允许的原语
    resolution_order: tuple[str, ...] = ()  # 结算优先级
    timer: Optional[int] = None  # 秒
    next: Optional[str] = None
    on_complete: Optional[str] = None  # 如 eliminate_top_voted
    check_win: bool = False


@dataclass(frozen=True)
class GameDefinition:
    slug: str
    name: str
    min_players: int
    max_players: int
    factions: tuple[str, ...]
    win_conditions: dict[str, str]  # faction -> 谓词字符串
    roles: tuple[RoleDef, ...]
    phases: tuple[PhaseDef, ...]
    start_phase: str

    def phase(self, name: str) -> PhaseDef:
        for p in self.phases:
            if p.name == name:
                return p
        raise KeyError(f"unknown phase: {name}")

    def role(self, name: str) -> RoleDef:
        for r in self.roles:
            if r.name == name:
                return r
        raise KeyError(f"unknown role: {name}")


# ---------------------------------------------------------------------------
# 运行时状态
# ---------------------------------------------------------------------------


@dataclass
class Seat:
    seat_id: int
    actor_type: str = "ai"  # human / ai
    role: Optional[str] = None
    faction: Optional[str] = None
    alive: bool = True
    name: Optional[str] = None  # 显示名（玩家昵称 / 人物卡名）


@dataclass
class Action:
    """一次行动意图。引擎对人类/AI 来源无感知（§11）。"""

    seat: int
    type: str  # 原语名，或 "pass"（跳过可选行动）
    targets: tuple[int, ...] = ()
    channel: Optional[str] = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class Event:
    """一条 session_event（已带 visibility，§5）。"""

    seq: int
    phase: str
    round: int
    actor: Optional[int]  # seat_id 或 None（系统事件）
    action: str
    payload: dict[str, Any] = field(default_factory=dict)
    visibility: Visibility = Visibility.PUBLIC
    audience: tuple[int, ...] = ()  # private/faction 时的可见席位集合（空=按 visibility 规则推导）


@dataclass(frozen=True)
class WinResult:
    faction: str
    reason: str


@dataclass
class GameState:
    definition: GameDefinition
    seats: list[Seat]
    phase: str
    round: int = 1
    seq: int = 0
    finished: bool = False
    winner: Optional[WinResult] = None
    # 能力剩余次数： (seat_id, primitive) -> remaining
    ability_uses: dict[tuple[int, str], int] = field(default_factory=dict)
    # 本阶段已行动的席位
    acted: set[int] = field(default_factory=set)
    # 本阶段收集的待结算行动（按原语分组）
    pending: dict[str, list[Action]] = field(default_factory=dict)
    log: list[Event] = field(default_factory=list)

    # ---- 便捷查询 ----
    def seat(self, seat_id: int) -> Seat:
        return self.seats[seat_id]

    def alive_seats(self) -> list[Seat]:
        return [s for s in self.seats if s.alive]

    def faction_count(self, faction: str, alive_only: bool = True) -> int:
        return sum(
            1
            for s in self.seats
            if s.faction == faction and (s.alive or not alive_only)
        )
