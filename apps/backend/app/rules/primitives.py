"""能力原语库（Start.md §7.3）。

编译器只认这有限的一组可组合原语；Rule.md 里的每个 ability 必须映射到其一（带参数）。
这样"生成任意游戏"被约束在安全、可测的范围内——可控性与表达力的刻意权衡。

新游戏若需要库里没有的机制 → 走"扩展原语"评审流程（写新 primitive + 测试），
而不是在 Rule.md 里塞任意逻辑。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Primitive:
    name: str
    semantics: str
    params: tuple[str, ...] = ()  # 允许的参数名（用于编译期校验）


# 语义见 §7.3 表格。params 为该原语可接受的参数键。
REGISTRY: dict[str, Primitive] = {
    p.name: p
    for p in [
        Primitive("eliminate", "移除一名玩家", ("target", "uses", "group_decision", "phase", "visibility")),
        Primitive("protect", "抵消一次 eliminate", ("target", "uses", "phase", "visibility")),
        Primitive("investigate", "向行动者揭示目标信息", ("target", "reveals", "phase", "visibility")),
        Primitive("vote", "群体决策，产出计票", ("candidates", "tie_rule", "phase")),
        Primitive("nominate", "提名/组队", ("count", "by", "phase")),
        Primitive("reveal", "向某范围公开信息", ("attribute", "scope", "phase", "visibility")),
        Primitive("swap", "交换两者的某属性", ("a", "b", "attribute", "phase")),
        Primitive("assign", "分配角色/标记", ("target", "value", "phase")),
        Primitive("speak", "发言（进入公共/私有频道）", ("channel", "phase")),
    ]
}


def is_known(name: str) -> bool:
    return name in REGISTRY


def get(name: str) -> Primitive:
    if name not in REGISTRY:
        raise KeyError(
            f"未知原语 '{name}'。已知原语: {sorted(REGISTRY)}。"
            f"新机制需扩展原语库（写 primitive + 测试），不要在 Rule.md 里塞任意逻辑。"
        )
    return REGISTRY[name]


def all_names() -> set[str]:
    return set(REGISTRY)
