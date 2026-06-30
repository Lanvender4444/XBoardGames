# 04 · 占位层：agents / memory / multiplayer / api

这些模块给出**真实接口签名 + 数据流注释**，业务逻辑多为 `NotImplementedError`，待对应 Phase 接入。
唯一例外是 `agents` 里的 `RandomPolicy`——它可运行，用来驱动 CLI 自动对局与测试。

---

# 一、`app/agents/` — AI 玩家与 LangGraph（§10，Phase 2）

## `app/agents/decision_graph.py`

### `class Policy(Protocol)` 🟢
行动策略接口：`decide(engine, state, seat) -> Action | None`。任何能给席位挑行动的对象都满足它。

### `class RandomPolicy` 🟢（可运行基线）
- `__init__(seed=None)`：持有一个 `random.Random(seed)`，保证可复现。
- `decide(engine, state, seat)`：取 `engine.legal_actions`，随机挑一个（无合法行动返回 None）。
**作用**：无需 LLM 即可让全 AI 局跑通整局，是 Phase 1 验证引擎抽象的关键——它和未来的 LangGraph 策略
走的是完全相同的"取合法行动→提交"路径。

### `class DecisionGraph` 🟡
LangGraph 决策子图占位。`__init__` 抛 `NotImplementedError`。Phase 2 将用 langgraph 构建
感知(Perceive)→召回(Recall)→推理(Reason)→行动(Act)→编码(Encode) 五节点子图（§10）。

### `class AIPlayer` 🟢/🟡
绑定一张人物卡的 AI 玩家。`__init__(character_id, policy=None)`（默认 RandomPolicy）；
`act(engine, state, seat)` 委托给 policy。结构就绪，接入真实 LangGraph 策略即可升级。

### `app/agents/__init__.py`
重导出 `DecisionGraph`、`AIPlayer`。

---

# 二、`app/memory/` — 记忆系统（§8，Phase 2/5）

整体分层：STM（单局，Redis，带 TTL）→ 固化 → LTM（跨局，关系表 + 向量库）；羁绊直接影响 AI 行为。

## `app/memory/stm.py` — 短期记忆（§8.1）
- `class Belief`（dataclass）🟢：对某席位的心证——`seat / suspected_faction / trust(-100~100) / notes`。
- `class ShortTermMemory`：
  - `__init__(session_id, character_id, store=None)`🟢：默认用 `get_state_store()`。
  - `_key()`🟢：返回 Redis 键 `session:{id}:stm:{cid}`（§6）。
  - `update_belief(belief, ttl=3600)`🟡 / `beliefs()`🟡：写/读心证（待 JSON 序列化进 Redis hash）。
  - `clear()`🟢：删除本局该角色 STM 键（局结束清理，可用）。

## `app/memory/ltm.py` — 长期记忆（§8.1/§8.4）
- `class Memory`（dataclass）🟢：`character_id / kind(semantic|episodic) / content / salience / related_character_ids`。
- `class LongTermMemoryStore`：
  - `__init__(vector=None)`🟢：默认用 `get_vector_store()`。
  - `write(memory, embedding)`🟡：写关系表 + 向量库。
  - `recall(query_embedding, top_k=5)`🟡：按"当前情境"向量召回（§8.2 召回节点）。
  - `decay()`🟡：衰减/合并低价值记忆，防向量库无限增长（§8.4，Phase 5）。

## `app/memory/bonds.py` — 羁绊（§8.1）
- `class Bond`（dataclass）🟢：`from/to_character_id / affinity / tags`。
- `class BondGraph` 🟡：`affinity(frm,to)` 读取；`apply_outcome(session_id,events)` 按共同经历更新（谁救谁/谁坑谁）；
  `to_behavior_bias(character_id, present_seats)` 转成 prompt 行为偏置（对高好感更信任、对宿敌更针对）。

## `app/memory/highlights.py` — 精彩瞬间（§8.3，Phase 5）
- `class Highlight`（dataclass）🟢：`title / summary / kind / participants / replay_ref`。
- `class HighlightEvaluator.scan(session_id, events)` 🟡：扫描事件识别高戏剧性瞬间（神预言、极限翻盘、深度欺骗等）。

## `app/memory/consolidation.py` — 局结束固化（§8.4，Phase 2）
- `consolidate_session(session_id)` 🟡：提炼本局值得长期记住的若干条→写 LTM+embedding→更新羁绊→清理 STM。

## `app/memory/__init__.py`
重导出 `ShortTermMemory / LongTermMemoryStore / BondGraph / HighlightEvaluator / consolidate_session`。

---

# 三、`app/multiplayer/` — 联机（§9，Phase 3）

引擎对"actor 是人/AI、本机/远程"无感知；联机层只解决发现、连接、广播。**服务器权威**：客户端只发意图行动。

## `app/multiplayer/session_manager.py`
### `class SessionManager`
- `__init__(engine=None, state_store=None, event_bus=None)`🟢：默认持有一个 `GameEngine`。
- `create_session(definition, players, mode="lan")` 🟡：创建会话、热状态入 Redis。
- `submit_action(session_id, action)` 🟡：客户端意图→引擎 `apply` 校验改状态→Redis Pub/Sub 广播（§9.1）。
- `on_disconnect(session_id, seat)` 🟡：断线处理；人类超时可由 AI 托管该席位（可配置）。

## `app/multiplayer/discovery.py`（§9.2）
- `announce_room(session_id, host_addr, port)` 🟡 / `discover_rooms(timeout=2.0)` 🟡：
  LAN 房间宣告/发现（mDNS/UDP）。注释说明实际 UDP 发现通常在 Tauri 的 Rust 核心实现，此处为后端侧登记/查询占位。

## `app/multiplayer/__init__.py`
重导出 `SessionManager`。

---

# 四、`app/api/` — FastAPI（§12，Phase 3）

## `app/api/protocol.py` 🟢
通信协议 Python 端镜像，与 `packages/protocol/src/messages.ts` 保持一致（避免漂移）：
- 常量集 `CLIENT_MESSAGES`（join/leave/submit_action/chat/heartbeat）、
  `SERVER_MESSAGES`（state_snapshot/state_patch/event/request_action/phase_changed/game_over/error）。
- `class Envelope`（dataclass）：消息信封 `type / session_id / seq / payload`。

## `app/api/app.py` 🟡
`create_app()`：FastAPI 应用工厂占位（NotImplementedError）。LAN 下作为 Tauri 的 Python sidecar 启动，
绑定 `0.0.0.0:PORT`。

## `app/api/routes_rules.py` 🟡 / `app/api/ws.py` 🟡
规则管线 HTTP 路由（上传→提取→结构化→审校→编译，§7）与 WebSocket 端点（注释强调 `request_action` 必带
`legal_actions` 让前端渲染与引擎判定一致，§12）的占位模块。

## `app/api/__init__.py`
包说明（§12，Phase 3 占位）。
