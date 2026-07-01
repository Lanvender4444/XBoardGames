"""Rule.md → GameDefinition 编译器（Start.md §7.1 第④步）。

受控编译：每个 ability 必须映射到能力原语库中的已知原语；阶段引用必须闭合；
胜负谓词只能引用允许的变量。任一不满足 → ``CompileError``，编译期即报错（§7.1 / §15）。
"""

from __future__ import annotations

from pathlib import Path

from app.core import paths
from app.engine import predicates
from app.engine.types import (
    AbilityDef,
    GameDefinition,
    PhaseDef,
    RoleDef,
    Visibility,
)
from app.rules import primitives
from app.rules.schema import AbilitySpec, RuleSpec, parse_rule_md


class CompileError(ValueError):
    pass


def _ability_def(spec: AbilitySpec) -> AbilityDef:
    if not primitives.is_known(spec.primitive):
        raise CompileError(
            f"能力 '{spec.primitive}' 未映射到已知原语；已知: {sorted(primitives.all_names())}"
        )
    prim = primitives.get(spec.primitive)
    # 校验参数键都在该原语声明的允许集合内
    unknown = set(spec.params) - set(prim.params)
    if unknown:
        raise CompileError(
            f"原语 '{spec.primitive}' 收到未知参数 {sorted(unknown)}；允许: {sorted(prim.params)}"
        )
    vis = spec.params.get("visibility", "public")
    try:
        visibility = Visibility(vis)
    except ValueError as e:
        raise CompileError(f"非法 visibility: {vis!r}") from e
    return AbilityDef(
        primitive=spec.primitive,
        params={k: v for k, v in spec.params.items() if k not in ("phase", "uses", "visibility")},
        phase=spec.params.get("phase"),
        uses=spec.params.get("uses"),
        visibility=visibility,
    )


def compile_rule_md(text: str) -> GameDefinition:
    spec: RuleSpec = parse_rule_md(text)
    return compile_spec(spec)


def compile_spec(spec: RuleSpec) -> GameDefinition:
    # 1) 角色 + 能力映射
    roles: list[RoleDef] = []
    role_names: set[str] = set()
    rest_count = 0
    for r in spec.roles:
        if r.name in role_names:
            raise CompileError(f"重复角色名: {r.name}")
        role_names.add(r.name)
        if r.faction not in spec.factions:
            raise CompileError(f"角色 {r.name} 的阵营 '{r.faction}' 不在 factions {spec.factions}")
        if r.count == "rest":
            rest_count += 1
        roles.append(
            RoleDef(
                name=r.name,
                faction=r.faction,
                count=r.count,
                abilities=tuple(_ability_def(a) for a in r.abilities),
                channels=tuple(r.channels),
            )
        )
    if rest_count > 1:
        raise CompileError("最多只能有一个角色 count='rest'")

    # 2) 阶段：引用闭合 + actor 角色解析
    phase_names = {p.name for p in spec.phases}
    if spec.start_phase not in phase_names:
        raise CompileError(f"start_phase '{spec.start_phase}' 不存在")
    phases: list[PhaseDef] = []
    for p in spec.phases:
        if p.next is not None and p.next not in phase_names:
            raise CompileError(f"阶段 '{p.name}' 的 next '{p.next}' 指向不存在的阶段")
        actor_roles: tuple[str, ...] = ()
        if p.actors not in ("all_alive", "all"):
            # actors 为逗号分隔或 YAML 列表风格的角色名
            names = [a.strip() for a in p.actors.replace(",", " ").split()]
            for nm in names:
                if nm not in role_names:
                    raise CompileError(f"阶段 '{p.name}' 引用未知角色 '{nm}'")
            actor_roles = tuple(names)
        # 校验本阶段引用的原语 / on_complete 已知
        for prim in (*p.actions, *p.resolution_order):
            if not primitives.is_known(prim):
                raise CompileError(f"阶段 '{p.name}' 引用未知原语 '{prim}'")
        phases.append(
            PhaseDef(
                name=p.name,
                actors=p.actors,
                actor_roles=actor_roles,
                actions=tuple(p.actions),
                resolution_order=tuple(p.resolution_order),
                timer=p.timer,
                next=p.next,
                on_complete=p.on_complete,
                check_win=p.check_win,
            )
        )

    # 3) 胜负谓词静态校验（只允许引用 {faction}_count / alive_count）
    allowed = {"alive_count", *(f"{f}_count" for f in spec.factions)}
    for faction, predicate in spec.win_conditions.items():
        if faction not in spec.factions:
            raise CompileError(f"win_conditions 含未知阵营 '{faction}'")
        try:
            predicates.validate(predicate, allowed)
        except (ValueError, SyntaxError) as e:
            raise CompileError(f"阵营 '{faction}' 的胜负谓词非法: {e}") from e

    return GameDefinition(
        slug=spec.slug,
        name=spec.name,
        min_players=spec.min_players,
        max_players=spec.max_players,
        factions=tuple(spec.factions),
        win_conditions=dict(spec.win_conditions),
        roles=tuple(roles),
        phases=tuple(phases),
        start_phase=spec.start_phase,
    )


def load_builtin(slug: str) -> GameDefinition:
    """加载并编译内置游戏的官方 Rule.md（games/<slug>/Rule.md）。"""
    rule_path = builtin_rule_path(slug)
    if not rule_path.exists():
        raise FileNotFoundError(f"内置游戏 Rule.md 不存在: {rule_path}")
    return compile_rule_md(rule_path.read_text(encoding="utf-8"))


def builtin_rule_path(slug: str) -> Path:
    return paths.resource_dir() / "games" / slug / "Rule.md"
