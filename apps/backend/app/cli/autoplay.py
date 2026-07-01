"""命令行自动对局（Start.md §14 Phase 1 里程碑）。

用"随机合法行动"策略驱动全 AI 的一整局，逐回合打印事件，直到满足胜负条件。
这是验证引擎抽象是否成立的关键工具：引擎不区分行动来源，CLI 与未来的人类 WebSocket、
AI LangGraph 走的是同一条 ``apply`` 路径（§11）。

用法：
    uv run python -m app.cli.autoplay --game werewolf --players 8 --seed 42
    uv run python -m app.cli.autoplay --game werewolf --players 8 --seed 42 --quiet
"""

from __future__ import annotations

import argparse
import sys
from typing import Optional

from app.agents.decision_graph import HeuristicPolicy, RandomPolicy
from app.agents.langgraph_graph import LangGraphPolicy
from app.agents.llm import LLMPolicy
from app.agents.orchestrator import run_orchestrator
from app.engine import Action, Event, GameEngine, GameState, Seat, Visibility
from app.engine.engine import PASS
from app.rules.compiler import load_builtin


def run_game(
    slug: str,
    players: int,
    seed: int = 0,
    max_rounds: int = 50,
    on_event: Optional[callable] = None,
    policy_kind: str = "random",
) -> GameState:
    """跑通一整局，返回终局状态。``on_event`` 可选地接收每条新事件用于打印。"""
    definition = load_builtin(slug)
    engine = GameEngine()
    # 全 AI 局；actor_type 不影响引擎逻辑，只标注来源
    seats = [Seat(seat_id=i, actor_type="ai") for i in range(players)]
    state = engine.init_session(definition, seats, seed=seed)
    # 每个席位一个策略实例；heuristic 策略持有跨回合心证（见 app.agents 决策子图）
    if policy_kind == "heuristic":
        policies = {s.seat_id: HeuristicPolicy(seed=seed + s.seat_id) for s in seats}
    elif policy_kind == "langgraph":
        policies = {s.seat_id: LangGraphPolicy(seed=seed + s.seat_id) for s in seats}
    elif policy_kind == "llm":
        policies = {s.seat_id: LLMPolicy(seed=seed + s.seat_id) for s in seats}
    else:
        policies = {s.seat_id: RandomPolicy(seed=seed + s.seat_id) for s in seats}

    _flush(state, 0, on_event)
    # 全 AI 对局由 LangGraph 编排器驱动：抢占式阶段并发思考(Send)+顺序仲裁，排队式阶段轮流发言。
    run_orchestrator(engine, state, policies, on_event=on_event, max_steps=max_rounds * 6)
    return state


def _flush(state: GameState, since: int, on_event: Optional[callable]) -> None:
    if on_event is None:
        return
    for ev in state.log[since:]:
        on_event(state, ev)


def _seat_label(state: GameState, seat_id: Optional[int]) -> str:
    if seat_id is None:
        return "—"
    s = state.seat(seat_id)
    return f"#{seat_id}({s.role})"


def _print_event(state: GameState, ev: Event) -> None:
    actor = _seat_label(state, ev.actor)
    vis = "" if ev.visibility is Visibility.PUBLIC else f" [{ev.visibility.value}]"
    print(f"  [r{ev.round}/{ev.phase}] {actor} {ev.action} {ev.payload}{vis}")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="AI Tabletop 引擎自动对局")
    parser.add_argument("--game", default="werewolf", help="内置游戏 slug（werewolf）")
    parser.add_argument("--players", type=int, default=8)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--quiet", action="store_true", help="只打印结果，不逐条打印事件")
    parser.add_argument("--policy", choices=["random", "heuristic", "langgraph", "llm"], default="random",
                        help="AI 策略：random=随机；heuristic=纯Python子图；langgraph=LangGraph子图；llm=LangGraph+LLM决策链(langchain，默认离线模型)")
    args = parser.parse_args(argv)

    print(f"== {args.game} | players={args.players} | seed={args.seed} | policy={args.policy} ==")
    state = run_game(
        args.game,
        args.players,
        seed=args.seed,
        on_event=None if args.quiet else _print_event,
        policy_kind=args.policy,
    )

    print("-- 角色公开 --")
    for s in state.seats:
        status = "存活" if s.alive else "出局"
        print(f"  #{s.seat_id} {s.name}: {s.role}/{s.faction} ({status})")
    if state.winner:
        print(f"== 胜者阵营: {state.winner.faction}  （条件: {state.winner.reason}）==")
    else:
        print("== 未分胜负（达到最大回合）==")
    return 0


if __name__ == "__main__":
    sys.exit(main())
