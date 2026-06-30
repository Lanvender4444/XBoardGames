"""LangGraph 决策子图测试（未安装 langgraph 时自动跳过）。"""
import pytest

from app.agents import langgraph_available

pytestmark = pytest.mark.skipif(not langgraph_available(), reason="需要 `uv sync --extra ai`")

from app.agents import LangGraphPolicy, build_decision_app  # noqa: E402
from app.agents.decision_graph import GraphContext  # noqa: E402
from app.engine import GameEngine  # noqa: E402
from app.engine.types import Seat  # noqa: E402
from app.rules.compiler import load_builtin  # noqa: E402


def _play(seed):
    defn = load_builtin("werewolf")
    eng = GameEngine()
    seats = [Seat(seat_id=i, actor_type="ai") for i in range(8)]
    state = eng.init_session(defn, seats, seed=seed)
    pols = {s.seat_id: LangGraphPolicy(seed=100 + s.seat_id) for s in state.seats}
    wolf_on_mate = 0
    rounds = 0
    while not state.finished and rounds < 80:
        for seat in eng.actors_to_act(state):
            a = pols[seat.seat_id].decide(eng, state, seat)
            if a is None:
                continue
            if a.type in ("eliminate", "vote") and a.targets and \
                    state.seat(seat.seat_id).faction == "werewolf" and \
                    state.seat(a.targets[0]).faction == "werewolf":
                wolf_on_mate += 1
            eng.apply(state, a)
        eng.advance_phase(state)
        rounds += 1
    return state, wolf_on_mate, pols


@pytest.mark.parametrize("seed", [0, 1, 7, 42])
def test_langgraph_game_converges(seed):
    state, wolf_on_mate, _ = _play(seed)
    assert state.finished
    assert state.winner.faction in ("good", "werewolf")
    assert wolf_on_mate == 0


def test_graph_runs_all_five_nodes_in_order():
    defn = load_builtin("werewolf")
    eng = GameEngine()
    seats = [Seat(seat_id=i, actor_type="ai") for i in range(8)]
    state = eng.init_session(defn, seats, seed=1)
    pol = LangGraphPolicy(seed=1)
    seat = eng.actors_to_act(state)[0]
    pol.decide(eng, state, seat)
    assert pol.last_trace == ["perceive", "recall", "reason", "act", "encode"]


def test_build_decision_app_is_compiled_graph():
    app = build_decision_app()
    # 编译后的 langgraph 图可 invoke，且暴露图结构
    assert hasattr(app, "invoke")
    assert hasattr(app, "get_graph")


def test_langgraph_action_is_always_legal():
    defn = load_builtin("werewolf")
    eng = GameEngine()
    seats = [Seat(seat_id=i, actor_type="ai") for i in range(8)]
    state = eng.init_session(defn, seats, seed=5)
    pol = LangGraphPolicy(seed=2)
    for seat in eng.actors_to_act(state):
        a = pol.decide(eng, state, seat)
        if a is not None:
            assert eng._is_legal(state, a)  # 合法性双保险
