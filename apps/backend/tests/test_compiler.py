"""规则编译器测试：Rule.md → GameDefinition（含受控编译的失败路径）。"""

import pytest

from app.rules import primitives
from app.rules.compiler import CompileError, compile_rule_md, load_builtin
from app.rules.schema import parse_rule_md

MINIMAL = """---
slug: mini
name: Mini
min_players: 2
max_players: 4
start_phase: night
factions: [good, werewolf]
win_conditions:
  good: "werewolf_count == 0"
  werewolf: "werewolf_count >= good_count"
roles:
  - name: Wolf
    faction: werewolf
    count: 1
    abilities:
      - eliminate: { target: single_other, phase: night, group_decision: true }
  - name: Villager
    faction: good
    count: rest
phases:
  - name: night
    actors: "Wolf"
    resolution_order: [eliminate]
    next: day_vote
  - name: day_vote
    actors: all_alive
    actions: [vote]
    on_complete: eliminate_top_voted
    next: night
    check_win: true
---
body
"""


def test_compile_minimal():
    d = compile_rule_md(MINIMAL)
    assert d.slug == "mini"
    assert {r.name for r in d.roles} == {"Wolf", "Villager"}
    assert d.phase("night").actor_roles == ("Wolf",)
    assert d.start_phase == "night"


def test_builtin_werewolf_compiles():
    d = load_builtin("werewolf")
    assert d.slug == "werewolf"
    assert d.min_players == 6 and d.max_players == 12
    roles = {r.name: r for r in d.roles}
    assert roles["Werewolf"].faction == "werewolf"
    assert roles["Villager"].count == "rest"
    # 女巫两个有限次能力
    witch_prims = {a.primitive for a in roles["Witch"].abilities}
    assert witch_prims == {"protect", "eliminate"}


def test_builtin_avalon_compiles():
    # 阿瓦隆是 Phase 4 样本，但结构上应能解析+编译
    d = load_builtin("avalon")
    assert d.slug == "avalon"
    assert d.phase("team_building").next == "team_vote"


def test_unknown_primitive_rejected():
    bad = MINIMAL.replace("eliminate: { target: single_other, phase: night, group_decision: true }",
                          "teleport: { target: single_other }")
    with pytest.raises(CompileError):
        compile_rule_md(bad)


def test_dangling_phase_reference_rejected():
    bad = MINIMAL.replace("next: day_vote", "next: nowhere", 1)
    with pytest.raises(CompileError):
        compile_rule_md(bad)


def test_unknown_actor_role_rejected():
    bad = MINIMAL.replace('actors: "Wolf"', 'actors: "Ghost"')
    with pytest.raises(CompileError):
        compile_rule_md(bad)


def test_bad_win_predicate_rejected():
    bad = MINIMAL.replace('good: "werewolf_count == 0"', 'good: "ghost_count == 0"')
    with pytest.raises(CompileError):
        compile_rule_md(bad)


def test_all_primitives_registered():
    # §7.3 九个原语都在库里
    assert primitives.all_names() >= {
        "eliminate", "protect", "investigate", "vote",
        "nominate", "reveal", "swap", "assign", "speak",
    }
