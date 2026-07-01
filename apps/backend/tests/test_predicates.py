"""胜负谓词求值器测试（安全 ast 求值，非 eval）。"""

import pytest

from app.engine import predicates


def test_basic_comparisons():
    ctx = {"werewolf_count": 0, "good_count": 5, "alive_count": 5}
    assert predicates.evaluate("werewolf_count == 0", ctx) is True
    assert predicates.evaluate("werewolf_count >= good_count", ctx) is False


def test_werewolf_win_condition():
    ctx = {"werewolf_count": 3, "good_count": 3}
    assert predicates.evaluate("werewolf_count >= good_count", ctx) is True


def test_boolean_and_arithmetic():
    ctx = {"a": 2, "b": 3}
    assert predicates.evaluate("a + b == 5 and a < b", ctx) is True
    assert predicates.evaluate("not (a > b)", ctx) is True


def test_unknown_variable_raises():
    with pytest.raises(ValueError):
        predicates.evaluate("ghost_count == 0", {"good_count": 1})


def test_validate_rejects_unknown_names():
    with pytest.raises(ValueError):
        predicates.validate("mystery == 1", {"good_count", "werewolf_count"})


def test_no_arbitrary_code_execution():
    # 函数调用等非允许语法必须被拒绝
    with pytest.raises(ValueError):
        predicates.evaluate("__import__('os')", {})
