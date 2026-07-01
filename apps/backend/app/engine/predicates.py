"""胜负条件谓词求值（Start.md §7.2 win_conditions）。

谓词是对游戏状态求值的字符串，如 ``"werewolf_count == 0"``、``"werewolf_count >= good_count"``。
出于安全，**不使用 eval**：用 ``ast`` 解析并仅允许比较、布尔、算术与变量/数字字面量。
非法节点会抛 ``ValueError``，编译期即可发现写错的谓词。
"""

from __future__ import annotations

import ast
import operator
from typing import Any

_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
}
_CMP_OPS = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
}


def _eval(node: ast.AST, ctx: dict[str, Any]) -> Any:
    if isinstance(node, ast.Expression):
        return _eval(node.body, ctx)
    if isinstance(node, ast.BoolOp):
        vals = [_eval(v, ctx) for v in node.values]
        return all(vals) if isinstance(node.op, ast.And) else any(vals)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return not _eval(node.operand, ctx)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_eval(node.operand, ctx)
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
        return _BIN_OPS[type(node.op)](_eval(node.left, ctx), _eval(node.right, ctx))
    if isinstance(node, ast.Compare):
        left = _eval(node.left, ctx)
        for op, comparator in zip(node.ops, node.comparators):
            if type(op) not in _CMP_OPS:
                raise ValueError(f"不支持的比较运算符: {ast.dump(op)}")
            right = _eval(comparator, ctx)
            if not _CMP_OPS[type(op)](left, right):
                return False
            left = right
        return True
    if isinstance(node, ast.Name):
        if node.id not in ctx:
            raise ValueError(f"谓词引用了未知变量: {node.id}")
        return ctx[node.id]
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float, bool)):
        return node.value
    raise ValueError(f"谓词中含不允许的语法: {ast.dump(node)}")


def evaluate(predicate: str, ctx: dict[str, Any]) -> bool:
    """对 ``predicate`` 在上下文 ``ctx`` 下求值，返回布尔。"""
    tree = ast.parse(predicate, mode="eval")
    return bool(_eval(tree, ctx))


def validate(predicate: str, allowed_names: set[str]) -> None:
    """编译期静态校验：语法合法且只引用 ``allowed_names`` 中的变量。"""
    tree = ast.parse(predicate, mode="eval")
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id not in allowed_names:
            raise ValueError(f"谓词引用未知变量 '{node.id}'，允许: {sorted(allowed_names)}")
