# 07 · Phase 2–5 实现详解 与 模块联动

> 本文记录把原"接口占位（`NotImplementedError`）"落地为**真实可运行实现**的全过程：每个模块怎么实现、
> 模块之间如何联动。验证：`uv run pytest` → **71 passed**（原 34 + 新增 37）；
> `autoplay --policy heuristic` 全 AI 整局收敛；FastAPI `TestClient` HTTP + WebSocket 往返通过。

## 设计总原则：可运行的本地默认 + 可注入的真实后端

所有实现都遵循同一条线：**默认用无外部依赖、确定性的本地实现把链路跑通并单测**，同时把
LLM / Redis / 真实向量库 / OCR 这些重依赖放在**可注入的接口（协议）背后**。这样：

- 在最小依赖（仅 `pyyaml`）下，记忆/AI/联机/规则摄取整链都能跑、能测、能复盘；
- 生产环境把对应实现换成真模型/真服务即可，**业务代码与方法签名不变**（延续 §4 存储抽象层思路）。

可注入的接缝一览：`Embedder`（嵌入）、`Reasoner`（推理，可换 LLM）、`Structurer`（规则结构化，可换 LLM）、
`StateStore`/`EventBus`/`VectorStore`（存储抽象，可换 Redis/FAISS/pgvector）。

---

# 一、Phase 2 · 记忆系统（`app/memory/`）

## `embedding.py` — 嵌入向量（新增）🟢
`Embedder` 协议（`dim` + `embed(text)->list[float]`）。默认 `HashingEmbedder`：分词（英文按词、中文逐字）
→ 特征哈希落桶 → L2 归一化。共享词多的文本余弦相似度更高（实测"狼人袭击村民/平民"≈0.83，对比"预言家查验"=0.0）。
确定性、可复现。`get_embedder()` 给进程级默认，Phase 5 可换真实句向量模型。

## `stm.py` — 短期记忆（实现）🟢
`Belief(seat, suspected_faction, trust∈[-100,100], notes)`。`ShortTermMemory` 把每个被观察席位序列化成
JSON 存进 `StateStore` 的 hash（键 `session:{id}:stm:{cid}`，带 TTL）。方法：`update_belief/belief/beliefs/
note/adjust_trust/clear`。默认 `StateStore` 是内存实现（贴 Redis 语义），换真 Redis 不改本模块。

## `ltm.py` — 长期记忆（实现）🟢
`Memory(character_id, kind=semantic|episodic, content, salience, related, age)`。
`LongTermMemoryStore` 把内容+元数据写进 `VectorStore`（余弦检索）并维护 id 索引：
- `write`：缺省由内容自动 `embed`，存向量库+索引。
- `recall(query, top_k, character_id)`：query 可为文本或向量；命中记忆**就地强化**（salience+0.1、age 归零）——常被想起的更牢固。
- `decay(threshold, rate, max_age)`：每条 age+1、salience 按 rate 衰减，低于阈值或太老则遗忘（删向量库+索引），防膨胀（§8.4 / Phase 5）。

## `bonds.py` — 羁绊（实现）🟢
有向好感 `affinity[(frm,to)]` + 标签。`apply_outcome(events, seat_to_char)` 扫描一局事件：
`protect_submitted`→目标对施救者 +15「救过我」；`vote_submitted`→ -10「票过我」；`eliminate_submitted`→ -12「夜里下手」；
累积到阈值自动打「宿敌」。`to_behavior_bias(cid, present)` 把羁绊翻成 `{seat:{affinity,stance(ally/enemy/neutral),tags}}`，
供 AI 推理直接消费（§8.2）。

## `highlights.py` — 精彩瞬间（实现，Phase 5）🟢
`HighlightEvaluator.scan(events)` 确定性启发式识别：**神预言**（查验到狼且该狼后来出局）、**关键一票**（vote 致死）、
**极限翻盘**（多轮拉锯后取胜）。产 `Highlight(title,summary,kind,participants,replay_ref="seq:n")`，可回放。
真实部署可注入 LLM 润色标题/摘要，识别框架不变。

## `consolidation.py` — 局末固化（实现）🟢
`consolidate_session(session_id, events, seats, …)` 是把"单局短期信息"沉淀为"跨局长期记忆+羁绊"的枢纽：
1) 精彩瞬间 → 每个参与者写一条 episodic；2) 终局身份 → 每个 AI 对他人写 semantic 印象；
3) `BondGraph.apply_outcome` 更新羁绊；4) 清各角色 STM。返回 `ConsolidationResult`（写入计数+瞬间）。

---

# 二、Phase 2 · AI 决策子图（`app/agents/decision_graph.py`）🟢

把 `DecisionGraph` 从占位实现为**纯 Python 的五节点子图**：感知→召回→推理→行动→编码。

- **感知 perceive**：取引擎 `legal_actions`；若自己是狼，识别狼队友（狼人互认）。
- **召回 recall**：扫描"**自己可见的**私有事件"（`investigate_result` 且 `actor==我`）更新心证（查到狼→trust=-80）；
  若注入了 `BondGraph`，取行为偏置。这一步只用合法可见信息，不开天眼。
- **推理 reason**：`Reasoner.score(ctx, action)` 给每个合法行动打分。默认 `HeuristicReasoner`：
  狼刀人**绝不刀队友**（-999）、优先低好感/不信任目标；预言家**优先查未知**；投票投最可疑（心证+羁绊综合）；女巫救信任的人。
- **行动 act**：取最高分（同分确定性随机），再过一遍引擎 `_is_legal` **合法性双保险**，非法则回退安全默认（§10/§15）。
- **编码 encode**：心证已就地写入 `ctx.beliefs`（策略实例跨回合持有）。

策略层：`RandomPolicy`（基线，保留）、`HeuristicPolicy`（跑完整子图、持心证、可注入羁绊）。
`Reasoner` 是接缝——**换成 LLM 推理节点（persona/traits + 召回记忆构造 prompt）即升级为真 AI**，子图骨架与双保险不变。
真实可视化/可观测子图可在 langgraph 上重建同构节点；本编排器即其参考实现。
验证：20 局启发式对局全部收敛，狼**零次**指向队友。

---

# 三、Phase 3 · 联机层（`app/multiplayer/`）🟢

**服务器权威**：后端是状态唯一权威，客户端只发意图（§9.1）。`SessionManager` 把引擎+`StateStore`+`EventBus` 粘合：

- `create_session`：引擎 `init_session` → 登记内存会话表 → 快照写 `StateStore`（重连用）。
- `request_action`：列出当前需行动席位与其 `legal_actions`（**request_action 必带 legal_actions**，与前端渲染一致，§12）。
- `submit_action`：意图（Action 或 dict）→ 引擎 `apply`（非法抛 `IllegalActionError`）→ 按可见性广播 `event`；
  全员行动完则 `advance_phase`，广播 `phase_changed`/`game_over`，落快照。
- `on_disconnect`/`on_reconnect`：标记离线、**可选 AI 托管**（把席位 actor_type 改 ai）、重连拉按席位裁剪的快照。
- `drive_ai`：无人类时用 policies 把全 AI 推进到终局（测试与 headless 用）。

`discovery.py`：进程内房间注册表 `announce_room/discover_rooms/withdraw_room`（带过期）。真实 mDNS/UDP 在 Tauri 的 Rust 侧，
此处为后端登记/查询，Rust 侧把发现到的房间镜像进来。

依赖全走存储抽象：默认内存实现单机可跑可测；换真 Redis(StateStore/EventBus) 时本层不变。

---

# 四、Phase 3 · FastAPI 应用（`app/api/`）🟢

`fastapi` 为**可选依赖**（`uv sync --extra api`），全部**懒导入**，不影响引擎/CLI/记忆/联机的纯逻辑导入。

- `protocol.py`：协议镜像 + 编解码助手（`Envelope.to_json/from_json`、`action_*_payload`、`event_to_payload`、
  `snapshot_payload(for_seat=…)` 按席位裁剪可见性、`visible_to`）。**无 fastapi 依赖**，联机层直接复用。
- `routes_rules.py`：**框架无关核心函数** `validate_text/compile_text/ingest_text`（可脱离 fastapi 单测）+ `build_router()` 挂到 `/rules/*`。
- `ws.py`：`/ws/{session_id}/{seat}` —— accept → 下发裁剪快照 → 该席位需行动则发带 `legal_actions` 的 `request_action` →
  循环收 `submit_action`（非法回 `error` 不断开）→ 回传可见 `event` + 下一个 `request_action`；断开触发 `on_disconnect`。
- `app.py`：`create_app()` 装配 `/health`、`/rooms`、`/sessions`（建局返回快照+request_action）、`/sessions/{id}`、规则路由、WS。

> 踩坑记录：`from __future__ import annotations` 会把"函数内定义的 Pydantic 模型 / WebSocket 参数注解"变成
> 无法解析的前向引用，FastAPI 便把请求体/WebSocket 误判为 query 参数（422 / 1008）。解决：在定义路由模型的
> `routes_rules.py`、`app.py`、`ws.py` 去掉该 future 导入，并显式注解 `websocket: WebSocket`。

---

# 五、Phase 4 · 规则摄取管线（`app/rules/parser.py`）🟢

四步管线 ①提取 ②结构化 ③人工审校 ④编译。把"理解任意自然语言规则书"的②抽象成可注入的 `Structurer` 协议：

- `extract_text(path)`：txt/md 直读；pdf/docx 尝试可选库（pypdf/python-docx），未装给明确提示。
- 默认 `HeuristicStructurer`（无 LLM、确定性）：**已是 Rule.md（带 front-matter）→ 透传**；自由文本 → 抽标题/人数生成
  **最小骨架草稿 + 警告**（提示需人工补全）。真实 LLM 结构器实现同一协议即可处理任意散文。
- `ingest(path|text)`：提取→结构化→（可选）编译，返回草稿/警告/编译结果。第③步人工审校在前端编辑器进行。

验证：内置 werewolf Rule.md 透传后可编译；自由文本生成的 5–9 人骨架可编译。

---

# 六、Phase 5 · 打磨 🟢
精彩瞬间识别（见上）+ LTM `decay` 衰减遗忘已实现，构成"记忆不无限膨胀、戏剧瞬间被记住"的闭环。

---

# 七、模块如何联动（端到端数据流）

## 一局之内（实时）
```
客户端意图 Action
  → SessionManager.submit_action
      → GameEngine.apply（校验+结算，产出带 visibility 的 Event）
      → EventBus 按可见性广播；StateStore 落快照
  → 轮到 AI 席位时：HeuristicPolicy.decide
      → DecisionGraph: 感知(legal_actions) → 召回(扫自己可见事件→STM心证 + BondGraph行为偏置)
        → 推理(打分) → 行动(_is_legal 双保险) → 编码(写回心证)
      → 产出的 Action 同样回到 engine.apply（人/AI 同一条路径，引擎无感知，§11）
```

## 一局结束（固化，跨局）
```
game_over
  → consolidate_session(events, seats)
      → HighlightEvaluator.scan ──→ episodic 记忆
      → 终局身份 ───────────────→ semantic 记忆
      → 二者经 Embedder 向量化 → LongTermMemoryStore.write（入 VectorStore）
      → BondGraph.apply_outcome（更新羁绊）
      → 各角色 STM.clear
```

## 下一局（记忆生效）
```
DecisionGraph.recall
  → LongTermMemoryStore.recall(当前情境)  → 取回"上局这人是狼/那次被坑"
  → BondGraph.to_behavior_bias            → 对宿敌更针对、对恩人更信任
  → 注入推理打分 → 行为随历史改变（"记得你上次那波操作"）
```

## 规则摄取 → 可玩
```
文书 → parser.extract_text → structure_to_rule_md(可注入 LLM) → Rule.md 草稿
  → 前端审校(routes_rules.validate_text 实时校验) → compiler.compile_rule_md → GameDefinition
  → SessionManager.create_session 即可开局
```

## 接缝替换矩阵（本地默认 → 生产）
| 接缝 | 本地默认 | 生产可换 |
|---|---|---|
| Embedder | HashingEmbedder | 句向量模型（bge / text-embedding-3） |
| Reasoner | HeuristicReasoner | LangGraph + LLM 推理节点 |
| Structurer | HeuristicStructurer | LLM 规则结构化 |
| StateStore/EventBus | 内存实现 | Redis / Redis Pub/Sub |
| VectorStore | InMemoryVectorStore | FAISS(local) / pgvector(server) |

---

# 八、新增/改写文件与测试
- 新增：`memory/embedding.py`、`tests/test_memory.py`、`tests/test_agents.py`、`tests/test_multiplayer.py`、
  `tests/test_rules_ingest.py`、`tests/test_api.py`。
- 改写（占位→实现）：`memory/{stm,ltm,bonds,highlights,consolidation}.py`、`agents/decision_graph.py`、
  `multiplayer/{session_manager,discovery}.py`、`api/{protocol,routes_rules,ws,app}.py`、`rules/parser.py`、`cli/autoplay.py`（加 `--policy`）。
- 测试：原 34 全绿 + 新增 37 = **71 passed**。引擎纯逻辑约束测试仍通过（引擎不 import 网络/LLM）。
