"""CLI 自动对局测试：整局必须收敛到胜负，且终局自洽。"""

import pytest

from app.cli.autoplay import run_game


@pytest.mark.parametrize("seed", [0, 1, 7, 42, 123])
def test_werewolf_game_converges(seed):
    state = run_game("werewolf", players=8, seed=seed)
    assert state.finished, f"seed={seed} 未收敛"
    assert state.winner is not None
    assert state.winner.faction in ("good", "werewolf")


def test_winner_consistent_with_alive_counts():
    state = run_game("werewolf", players=8, seed=5)
    wolves = state.faction_count("werewolf")
    good = state.faction_count("good")
    if state.winner.faction == "good":
        assert wolves == 0
    else:
        assert wolves >= good


@pytest.mark.parametrize("n", [6, 8, 10, 12])
def test_various_player_counts(n):
    state = run_game("werewolf", players=n, seed=2)
    assert state.finished
    assert len(state.seats) == n


def test_event_log_is_ordered():
    state = run_game("werewolf", players=8, seed=9)
    seqs = [e.seq for e in state.log]
    assert seqs == sorted(seqs)
    assert seqs == list(range(len(seqs)))  # seq 连续无洞
