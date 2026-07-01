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
from app.agents.persona import assign_personas
from app.memory import LongTermMemoryStore
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


_session_seq = 0


class _Game:
    def __init__(self, engine, state, human_seats, policies, personas, session_id):
        self.engine = engine
        self.state = state
        self.human_seats = set(human_seats)
        self.policies = policies
        self.personas = personas          # seat_id -> Persona
        self.session_id = session_id
        self.thoughts: dict = {}          # seat_id -> 最近一次思维轨迹（调试用）


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
        auto_drive: bool = True,
    ) -> str:
        human_seats = human_seats if human_seats is not None else [0]
        definition = load_builtin(slug)
        engine = GameEngine()
        seats = [
            Seat(seat_id=i, actor_type=("human" if i in human_seats else "ai"))
            for i in range(players)
        ]
        state = engine.init_session(definition, seats, seed=seed)
        # 人设：给每个席位分配互不相同的性格 + 说话习惯；显示名用人设名
        personas = assign_personas(seed or 0, state.seats)
        for s in state.seats:
            s.name = personas[s.seat_id].name
        global _session_seq
        _session_seq += 1
        session_id = _session_seq
        # 全局共享长期记忆库（跨席位；真实部署换 pgvector/FAISS）
        ltm = LongTermMemoryStore()
        # 每个 AI 席位一个 LLM 决策策略：注入人设 + 三级记忆句柄（用当前运行期 provider 配置）
        policies = {
            s.seat_id: LLMPolicy(
                seed=(seed or 0) + s.seat_id, persona=personas[s.seat_id],
                session_id=session_id, character_id=s.seat_id, ltm=ltm,
            )
            for s in state.seats if s.seat_id not in human_seats
        }
        gid = uuid.uuid4().hex[:12]
        self._games[gid] = _Game(engine, state, human_seats, policies, personas, session_id)
        if auto_drive:  # 非流式客户端：直接把 AI 跑到第一个人类回合；流式客户端交给 SSE 驱动
            self._drive(gid)
        return gid

    # ----------------------------------------------------------------- drive
    def _drive(self, gid: str, max_steps: int = 400) -> None:
        """自动推进：按"抢占式并发 / 排队式发言"两模式驱动 AI + 阶段结算，
        直到轮到某个人类席位或对局结束（编排器统一逻辑，见 app.agents.orchestrator）。"""
        from app.agents.orchestrator import drive

        g = self._games[gid]
        drive(g.engine, g.state, g.policies,
              human_seats=tuple(g.human_seats), max_steps=max_steps,
              on_think=lambda sid, th: g.thoughts.__setitem__(sid, th))

    # ------------------------------------------------------------------ act
    def act(self, gid: str, action: dict, auto_drive: bool = True) -> dict:
        g = self._games[gid]
        act = protocol.action_from_payload(action)
        g.engine.apply(g.state, act)  # 非法 → IllegalActionError
        if auto_drive:  # 流式客户端提交后不在此驱动，改由 SSE 逐帧推进 AI
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
            "personas": {str(sid): {"name": p.name, "traits": p.traits, "style": p.speech_style}
                         for sid, p in g.personas.items()},
            "thoughts": {str(sid): th for sid, th in g.thoughts.items()},
        }

    # --------------------------------------------------------------- stream
    def stream(self, gid: str, max_steps: int = 400):
        """串行推进并逐帧产出（供 SSE）：思考→思维→(逐token发言)→事件→…→轮到人类/终局。

        帧类型：thinking / thought / speak_start / speak_delta / speak_end / event / your_turn / game_over。
        抢占式阶段：先让各 AI 在同一快照上思考（互不可见），再按序应用；排队式：轮流发言、发言 token 流式。
        """
        from app.agents.orchestrator import PREEMPTIVE, QUEUED, phase_mode

        g = self._games[gid]
        eng, st, hs = g.engine, g.state, g.human_seats

        def ev(e):
            return {"type": "event", "event": protocol.event_to_payload(e)}

        def pname(sid):
            return g.personas[sid].name if sid in g.personas else f"#{sid}"

        steps = 0
        while not st.finished and steps < max_steps:
            steps += 1
            actors = eng.actors_to_act(st)
            if not actors:
                before = len(st.log)
                eng.advance_phase(st)
                for e in st.log[before:]:
                    yield ev(e)
                continue
            if any(sd.seat_id in hs for sd in actors):
                yield {"type": "your_turn", "view": self.view(gid, min(hs))}
                return

            if phase_mode(st) == QUEUED:
                for sd in actors:
                    if sd.seat_id in hs:
                        yield {"type": "your_turn", "view": self.view(gid, min(hs))}
                        return
                    pol = g.policies[sd.seat_id]
                    yield {"type": "thinking", "seat": sd.seat_id, "persona": pname(sd.seat_id)}
                    act = pol.decide(eng, st, sd) or Action(seat=sd.seat_id, type=PASS)
                    g.thoughts[sd.seat_id] = getattr(pol, "last_thought", {})
                    yield {"type": "thought", "seat": sd.seat_id, "thought": g.thoughts[sd.seat_id]}
                    if act.type == "speak":
                        yield {"type": "speak_start", "seat": sd.seat_id, "persona": pname(sd.seat_id)}
                        buf = ""
                        streamer = getattr(pol, "stream_speak", None)
                        if callable(streamer):
                            for delta in streamer(eng, st, sd):
                                buf += delta
                                yield {"type": "speak_delta", "seat": sd.seat_id, "delta": delta}
                        else:
                            from app.agents.orchestrator import utterance
                            buf = utterance(pol, eng, st, sd)
                            yield {"type": "speak_delta", "seat": sd.seat_id, "delta": buf}
                        act.extra = {**(act.extra or {}), "text": buf}
                        yield {"type": "speak_end", "seat": sd.seat_id, "text": buf}
                    before = len(st.log)
                    eng.apply(st, act)
                    for e in st.log[before:]:
                        yield ev(e)
            else:
                # 抢占式：并发思考（同一快照，互不可见）→ 按序仲裁
                intents = []
                for sd in actors:
                    if sd.seat_id in hs:
                        continue
                    pol = g.policies[sd.seat_id]
                    yield {"type": "thinking", "seat": sd.seat_id, "persona": pname(sd.seat_id)}
                    a = pol.decide(eng, st, sd)
                    g.thoughts[sd.seat_id] = getattr(pol, "last_thought", {})
                    yield {"type": "thought", "seat": sd.seat_id, "thought": g.thoughts[sd.seat_id]}
                    intents.append((sd.seat_id, a))
                for sid, a in sorted(intents, key=lambda t: t[0]):
                    before = len(st.log)
                    eng.apply(st, a or Action(seat=sid, type=PASS))
                    for e in st.log[before:]:
                        yield ev(e)

        yield {"type": "game_over" if st.finished else "your_turn",
               "view": self.view(gid, min(hs) if hs else 0)}


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
        stream: bool = False  # true=前端将用 SSE 流式驱动，建局不预跑 AI

    class ActionIn(BaseModel):
        seat: int
        type: str
        stream: bool = False  # true=提交后不在此驱动，改由 SSE 推进
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

    @router.post("/llm/test")
    def _test_llm(body: LLMConfigIn) -> dict:
        """用**已保存的**配置真正调用一次模型（与开局所用一致），返回成功样例或**具体错误**。

        先按 body 更新配置（空/掩码 key 会保留已存真钥），再测——因此"保存后测试"用的就是真实 key。
        """
        from langchain_core.messages import HumanMessage

        from app.agents.providers import build_chat_model, get_runtime_config, set_runtime_config
        set_runtime_config(body.model_dump())
        cfg = get_runtime_config()
        try:
            model = build_chat_model(cfg)
            resp = model.invoke([HumanMessage(content="用一个字回复：好")])
            text = getattr(resp, "content", str(resp))
            kind = type(model).__name__
            return {"ok": True, "provider": cfg.get("provider"), "model": cfg.get("model"),
                    "model_class": kind, "sample": str(text)[:120],
                    "note": "LocalHeuristicChatModel 表示当前用内置离线模型（未走真实 API）"
                    if kind == "LocalHeuristicChatModel" else "已成功调用真实模型 API"}
        except Exception as e:  # 网络/鉴权/地址错误等，原样返回 + 排查提示
            msg = f"{type(e).__name__}: {e}"
            low = msg.lower()
            if "authenticat" in low or "401" in low or "invalid" in low and "key" in low:
                hint = "鉴权失败：① 确认 Key 正确、无多余空格/引号；② Key 必须与所选 Provider 匹配（如 DeepSeek 的 Key 不能配 OpenAI 地址）；③ 确认账户已开通该模型且有余额。"
            elif "connect" in low or "timeout" in low or "getaddrinfo" in low or "404" in low:
                hint = "连接失败：确认 Base URL 正确（OpenAI 兼容端点通常以 /v1 结尾）；本地服务（Ollama/LM Studio）需先启动。"
            else:
                hint = "请对照错误信息检查 Provider / Base URL / Model / Key。"
            return {"ok": False, "error": msg, "hint": hint}

    @router.post("/games")
    def _create(body: CreateIn) -> dict:
        gid = svc.create_game(body.slug, body.players, body.human_seats, body.seed,
                              auto_drive=not body.stream)
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
            return svc.act(gid, body.model_dump(), auto_drive=not body.stream)
        except Exception as e:
            raise HTTPException(400, str(e))

    @router.get("/games/{gid}/stream")
    def _stream(gid: str):
        """SSE 串行流：AI 逐个思考/发言/行动，发言逐 token 流式，到人类回合或终局收尾。"""
        import json as _json

        from fastapi.responses import StreamingResponse

        if gid not in svc._games:
            raise HTTPException(404, "game not found")

        def gen():
            for frame in svc.stream(gid):
                yield f"data: {_json.dumps(frame, ensure_ascii=False)}\n\n"

        return StreamingResponse(
            gen(), media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return router
