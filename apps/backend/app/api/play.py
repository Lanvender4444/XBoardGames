"""可玩对局服务（人类 + AI）+ LLM 配置接口（Start.md §9/§12）。

前端通过这组接口玩狼人杀：建局 → 取视图（含你的合法行动）→ 提交人类行动 → 服务器自动驱动 AI
（每个 AI 席位跑 LangGraph + LLM 决策子图）直到再次轮到人类或对局结束。
LLM provider 在前端可配置（支持主流开源/闭源 API，见 app.agents.providers）。

核心 ``PlayService`` 与框架无关（可直接调用/单测）；``build_play_router`` 把它挂到 FastAPI。
"""

import uuid
from typing import Optional

from app.agents import providers
from app.agents.llm import LLMPolicy
from app.api import protocol
from app.engine import GameEngine
from app.engine.engine import PASS
from app.engine.types import Action, GameState, Seat
from app.rules.compiler import load_builtin


def _label(action: Action) -> str:
    t = action.type
    tgt = action.targets[0] if action.targets else None
    if t == "investigate":
        return f"查验 #{tgt}"
    if t == "protect":
        return f"用解药救 #{tgt}"
    if t == "eliminate":
        return f"出手 #{tgt}"
    if t == "vote":
        return f"投票 #{tgt}"
    if t == "nominate":
        return f"提名 #{tgt}"
    if t == "speak":
        return "发言"
    if t == PASS:
        return "跳过"
    return t


class _Game:
    def __init__(self, engine, state, human_seats, policies):
        self.engine = engine
        self.state = state
        self.human_seats = set(human_seats)
        self.policies = policies


class PlayService:
    def __init__(self) -> None:
        self._games: dict[str, _Game] = {}

    # --------------------------------------------------------------- create
    def create_game(
        self,
        slug: str = "werewolf",
        players: int = 8,
        human_seats: Optional[list[int]] = None,
        seed: Optional[int] = None,
    ) -> str:
        human_seats = human_seats if human_seats is not None else [0]
        definition = load_builtin(slug)
        engine = GameEngine()
        seats = [
            Seat(seat_id=i, actor_type=("human" if i in human_seats else "ai"))
            for i in range(players)
        ]
        state = engine.init_session(definition, seats, seed=seed)
        # 每个 AI 席位一个 LLM 决策策略（用当前运行期 provider 配置）
        policies = {
            s.seat_id: LLMPolicy(seed=(seed or 0) + s.seat_id)
            for s in seats if s.seat_id not in human_seats
        }
        gid = uuid.uuid4().hex[:12]
        self._games[gid] = _Game(engine, state, human_seats, policies)
        self._drive(gid)  # 先把开局到第一个人类回合之间的 AI 行动跑掉
        return gid

    # ----------------------------------------------------------------- drive
    def _drive(self, gid: str, max_steps: int = 400) -> None:
        """自动推进：按"抢占式并发 / 排队式发言"两模式驱动 AI + 阶段结算，
        直到轮到某个人类席位或对局结束（编排器统一逻辑，见 app.agents.orchestrator）。"""
        from app.agents.orchestrator import drive

        g = self._games[gid]
        drive(g.engine, g.state, g.policies,
              human_seats=tuple(g.human_seats), max_steps=max_steps)

    # ------------------------------------------------------------------ act
    def act(self, gid: str, action: dict) -> dict:
        g = self._games[gid]
        act = protocol.action_from_payload(action)
        g.engine.apply(g.state, act)  # 非法 → IllegalActionError
        self._drive(gid)
        return self.view(gid, act.seat)

    # ----------------------------------------------------------------- view
    def view(self, gid: str, seat: Optional[int] = None) -> dict:
        g = self._games[gid]
        eng, st = g.engine, g.state
        if seat is None:
            seat = min(g.human_seats) if g.human_seats else 0
        snap = protocol.snapshot_payload(st, for_seat=seat)

        your_actions = []
        your_turn = False
        if not st.finished and st.seat(seat).alive:
            legal = eng.legal_actions(st, st.seat(seat))
            if legal and any(s.seat_id == seat for s in eng.actors_to_act(st)):
                your_turn = True
                your_actions = [
                    {**protocol.action_to_payload(a), "label": _label(a)} for a in legal
                ]
        me = st.seat(seat)
        return {
            "game_id": gid,
            "slug": st.definition.slug,
            "phase": st.phase,
            "round": st.round,
            "finished": st.finished,
            "winner": st.winner.faction if st.winner else None,
            "your_seat": seat,
            "your_role": me.role,
            "your_faction": me.faction,
            "your_turn": your_turn,
            "your_actions": your_actions,
            "awaiting": [s.seat_id for s in eng.actors_to_act(st)],
            "seats": snap["seats"],
            "log": snap["log"],
        }


# 进程级默认服务
_default = PlayService()


def get_service() -> PlayService:
    return _default


def build_play_router():
    """构造可玩对局 + LLM 配置的 FastAPI 路由（懒导入 fastapi）。"""
    from fastapi import APIRouter, HTTPException
    from pydantic import BaseModel

    router = APIRouter(tags=["play"])
    svc = get_service()

    class CreateIn(BaseModel):
        slug: str = "werewolf"
        players: int = 8
        human_seats: list[int] = [0]
        seed: Optional[int] = None

    class ActionIn(BaseModel):
        seat: int
        type: str
        targets: list[int] = []
        channel: Optional[str] = None
        extra: dict = {}

    class LLMConfigIn(BaseModel):
        provider: str = "offline"
        base_url: Optional[str] = None
        api_key: Optional[str] = None
        model: Optional[str] = None
        temperature: float = 0.7

    @router.get("/providers")
    def _providers() -> dict:
        return {"providers": providers.list_providers()}

    @router.get("/llm/config")
    def _get_cfg() -> dict:
        return providers.public_config()

    @router.post("/llm/config")
    def _set_cfg(body: LLMConfigIn) -> dict:
        return providers.set_runtime_config(body.model_dump())

    @router.post("/games")
    def _create(body: CreateIn) -> dict:
        gid = svc.create_game(body.slug, body.players, body.human_seats, body.seed)
        return svc.view(gid, min(body.human_seats) if body.human_seats else 0)

    @router.get("/games/{gid}")
    def _view(gid: str, seat: Optional[int] = None) -> dict:
        if gid not in svc._games:
            raise HTTPException(404, "game not found")
        return svc.view(gid, seat)

    @router.post("/games/{gid}/action")
    def _act(gid: str, body: ActionIn) -> dict:
        if gid not in svc._games:
            raise HTTPException(404, "game not found")
        try:
            return svc.act(gid, body.model_dump())
        except Exception as e:
            raise HTTPException(400, str(e))

    return router
