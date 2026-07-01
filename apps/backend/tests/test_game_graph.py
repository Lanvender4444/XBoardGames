"""[兼容] game_graph 现为 orchestrator 的别名——验证别名仍可驱动整局。"""
import pytest

from app.agents import langgraph_available

pytestmark = pytest.mark.skipif(not langgraph_available(), reason="需要 langgraph")

from app.agents.decision_graph import HeuristicPolicy  # noqa: E402
from app.agents.game_graph import build_game_graph, run_game_graph  # noqa: E402
from app.agents.orchestrator import build_orchestrator, run_orchestrator  # noqa: E402
from app.engine import GameEngine  # noqa: E402
from app.engine.types import Seat  # noqa: E402
from app.rules.compiler import load_builtin  # noqa: E402


def test_game_graph_is_orchestrator_alias():
    assert build_game_graph is build_orchestrator
    assert run_game_graph is run_orchestrator


@pytest.mark.parametrize("seed", [0, 7])
def test_alias_runs_full_game(seed):
    defn = load_builtin("werewolf")
    eng = GameEngine()
    gs = eng.init_session(defn, [Seat(seat_id=i, actor_type="ai") for i in range(8)], seed=seed)
    pols = {s.seat_id: HeuristicPolicy(seed=seed + s.seat_id) for s in gs.seats}
    run_game_graph(eng, gs, pols, max_steps=400)
    assert gs.finished
