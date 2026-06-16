"""Rule.md 规范与解析（Start.md §7.2）。

``Rule.md`` = YAML frontmatter（元信息 + 机器可读的 roles/phases）+ 结构化正文（人类可读文档）。

设计取舍：§7.2 在正文里用 markdown 片段描述角色/阶段以便人类阅读，但供编译器消费的
**权威机器可读定义放在 frontmatter** 的 ``roles`` / ``phases`` 键下。正文是其人类可读镜像，
便于审校（第③步）。这样解析稳健、可单测，同时保留"YAML frontmatter + 结构化正文"的形态。

能力（ability）两种写法皆可：
1. ``{primitive: investigate, target: single_other, reveals: faction, phase: night}``
2. 单键映射（§7.2 风格）：``{investigate: {target: single_other, reveals: faction}}``
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Union

import yaml


class RuleParseError(ValueError):
    pass


@dataclass
class AbilitySpec:
    primitive: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class RoleSpec:
    name: str
    faction: str
    count: Union[int, str]
    abilities: list[AbilitySpec] = field(default_factory=list)
    channels: list[str] = field(default_factory=list)


@dataclass
class PhaseSpec:
    name: str
    actors: str = "all_alive"
    actions: list[str] = field(default_factory=list)
    resolution_order: list[str] = field(default_factory=list)
    timer: Optional[int] = None
    next: Optional[str] = None
    on_complete: Optional[str] = None
    check_win: bool = False


@dataclass
class RuleSpec:
    slug: str
    name: str
    min_players: int
    max_players: int
    factions: list[str]
    win_conditions: dict[str, str]
    roles: list[RoleSpec]
    phases: list[PhaseSpec]
    start_phase: str
    body: str = ""  # 正文（文档/审校用）


_RESERVED = {"phase", "uses", "visibility", "group_decision"}


def _parse_ability(raw: Any) -> AbilitySpec:
    if not isinstance(raw, dict):
        raise RuleParseError(f"ability 必须是映射，得到: {raw!r}")
    if "primitive" in raw:
        prim = raw["primitive"]
        params = {k: v for k, v in raw.items() if k != "primitive"}
        return AbilitySpec(primitive=prim, params=params)
    # 单键映射写法： {investigate: {...}} 或 {protect: {uses: 1}}
    if len(raw) == 1:
        (prim, params), = raw.items()
        if params is None:
            params = {}
        if not isinstance(params, dict):
            raise RuleParseError(f"原语 {prim} 的参数必须是映射，得到: {params!r}")
        return AbilitySpec(primitive=prim, params=dict(params))
    raise RuleParseError(f"无法解析 ability: {raw!r}")


def _parse_role(raw: dict) -> RoleSpec:
    return RoleSpec(
        name=raw["name"],
        faction=raw["faction"],
        count=raw["count"],
        abilities=[_parse_ability(a) for a in raw.get("abilities", [])],
        channels=list(raw.get("channels", [])),
    )


def _parse_phase(raw: dict) -> PhaseSpec:
    return PhaseSpec(
        name=raw["name"],
        actors=raw.get("actors", "all_alive"),
        actions=list(raw.get("actions", [])),
        resolution_order=list(raw.get("resolution_order", [])),
        timer=raw.get("timer"),
        next=raw.get("next"),
        on_complete=raw.get("on_complete"),
        check_win=bool(raw.get("check_win", False)),
    )


def _split_frontmatter(text: str) -> tuple[dict, str]:
    text = text.lstrip()
    if not text.startswith("---"):
        raise RuleParseError("Rule.md 缺少 YAML frontmatter（应以 '---' 开头）")
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise RuleParseError("Rule.md frontmatter 未正确闭合（需两行 '---'）")
    fm = yaml.safe_load(parts[1]) or {}
    body = parts[2]
    if not isinstance(fm, dict):
        raise RuleParseError("frontmatter 必须是 YAML 映射")
    return fm, body


def parse_rule_md(text: str) -> RuleSpec:
    """把 Rule.md 文本解析为 ``RuleSpec``（仅语法/结构，不做原语映射校验，那在编译器里做）。"""
    fm, body = _split_frontmatter(text)
    try:
        spec = RuleSpec(
            slug=fm["slug"],
            name=fm["name"],
            min_players=int(fm["min_players"]),
            max_players=int(fm["max_players"]),
            factions=list(fm["factions"]),
            win_conditions=dict(fm["win_conditions"]),
            roles=[_parse_role(r) for r in fm["roles"]],
            phases=[_parse_phase(p) for p in fm["phases"]],
            start_phase=fm.get("start_phase") or fm["phases"][0]["name"],
            body=body,
        )
    except KeyError as e:
        raise RuleParseError(f"Rule.md frontmatter 缺少必填字段: {e}") from e
    return spec
