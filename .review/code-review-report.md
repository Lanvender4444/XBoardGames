# 代码审查报告 — AI 桌游平台脚手架

> 本报告逐一总结本次构建产出的**每个文件、每个函数/类、每个库与包**，对照 `docs/Start.md`（SSOT）。
> 范围：Phase 0 地基 + Phase 1 可运行引擎（含狼人杀）+ Phase 2-5 接口占位 + 全栈 Monorepo 骨架。
> 验证状态：`uv run pytest` → 34 passed；`autoplay` 全 AI 整局收敛。

---

## 1. 仓库总览

```
XBoardGames/
├── apps/
│   ├── desktop/      Tauri + React 外壳（占位）
│   └── backend/      Python 后端（uv 管理；引擎可运行）
├── packages/protocol/  前后端共享协议类型
├── games/            内置游戏官方 Rule.md（werewolf 可运行 / avalon 草稿）
├── docs/Start.md     设计文档（单一事实来源）
└── README.md
```

实现状态对照路线图：

| Phase | 内容 | 状态 |
|---|---|---|
| 0 | 地基：目录、存储抽象层、协议、SQLAlchemy 模型、配置/路径 | ✅ 已搭建 |
| 1 | 引擎 + 内置狼人杀（无 AI、无联机） | ✅ 可运行 + 34 测试 |
| 2 | AI 玩家 + 记忆 | 🟡 接口占位（含可跑的 RandomPolicy） |
| 3 | 联机（WebSocket + Redis Pub/Sub） | 🟡 接口占位 |
| 4 | 规则摄取管线（文书 → Rule.md → 编译） | 🟡 编译器可用，文书解析占位 |
| 5 | 精彩瞬间 + 打磨 | 🟡 接口占位 |

---

## 2. 依赖（库与包）

### 2.1 后端 Python（`apps/backend/pyproject.toml`，uv 管理）

刻意分级：核心运行时极小，重依赖按 Phase 放进 optional-dependencies。

| 分组 | 包 | 用途 / 对应 Start.md |
|---|---|---|
| **核心** | `pyyaml>=6.0` | 解析 Rule.md 的 YAML frontmatter（§7.2） |
| `storage` | `sqlalchemy>=2.0` | ORM，统一 SQLite/MySQL（§4） |
| | `alembic>=1.13` | 数据库迁移，收敛两端类型差异（§4） |
| `api` | `fastapi>=0.110` | HTTP + WebSocket（§12） |
| | `uvicorn[standard]>=0.29` | ASGI 服务器（§13） |
| | `redis>=5.0` | 热状态/缓存/Pub-Sub（§6） |
| | `websockets>=12.0` | 实时连接 |
| `server` | `pymysql>=1.1` | MySQL 驱动（server profile） |
| `ai` | `langgraph>=0.2` | AI 玩家决策图（§10） |
| | `langchain-core>=0.3` | LLM 编排基础 |
| `vector` | `faiss-cpu>=1.8` | 本地向量库，长期记忆召回（§8） |
| `dev` | `pytest>=8.0` | 单元测试 |
| | `ruff>=0.4` | 代码检查 |

构建后端用 `hatchling`；脚本入口 `autoplay = app.cli.autoplay:main`；
pytest 配置 `pythonpath=["."]`，ruff `line-length=100 / py310`。

### 2.2 前端 / 桌面（占位，未安装）

| 文件 | 包 | 用途 |
|---|---|---|
| `apps/desktop/package.json` | `react`, `react-dom` | UI |
| | `zustand` | 前端状态（§3 store） |
| | `@tauri-apps/cli`, `vite`, `typescript` | 构建工具链 |
| `apps/desktop/src-tauri/Cargo.toml` | `tauri` (Rust) | 桌面外壳、sidecar、LAN 发现 |
| | `serde`, `serde_json` | 序列化 |
| `packages/protocol/package.json` | （无运行时依赖） | 纯类型定义包 |

### 2.3 Python 标准库使用

`ast`/`operator`（安全谓词求值）、`random`（角色分配/随机策略）、`collections.Counter`（计票）、
`dataclasses`/`enum`/`typing`（数据类型）、`pathlib`/`os`/`sys`（路径解析）、
`logging`（含 `RotatingFileHandler`）、`functools.lru_cache`（存储单例）、`argparse`（CLI）、`time`（TTL）。

---

## 3. 后端逐文件 / 逐函数总结

### 3.1 `app/core/` — 配置、路径、日志

**`paths.py`** — 可写路径的单一出口（§1/§4/§15，杜绝打包后写安装目录）
- `_is_frozen()` — 是否运行在 PyInstaller 打包态（`sys._MEIPASS`）。
- `user_data_dir()` — 平台用户可写根目录（Win `%APPDATA%` / macOS Application Support / Linux XDG），可用 `AI_TABLETOP_DATA_DIR` 覆盖。
- `_sub(name)` — 在根目录下创建/返回子目录。
- `db_path()` — local profile 的 SQLite 文件路径。
- `redis_dump_dir()` — 内嵌 redis dump 目录。
- `uploads_dir()` — 上传规则文书目录。
- `vector_dir()` — 本地向量库文件目录。
- `logs_dir()` — 日志目录。
- `resource_dir()` — 只读资源根（打包态=`_MEIPASS`，开发态=仓库根，供 `load_builtin` 定位 `games/`）。

**`config.py`** — 运行时配置（§4 存储分层）
- `StorageProfile`(Enum) — `LOCAL` / `SERVER`。
- `Settings`(dataclass, frozen) — `profile / database_url / redis_url / vector_backend`；属性 `is_local`。
- `_default_database_url(profile)` — local→SQLite URL，server→MySQL 占位/环境变量。
- `load_settings()` — 从环境变量装配 `Settings`。
- 模块级 `settings` — 进程级单例。

**`logging.py`**
- `get_logger(name)` — 首次调用配置控制台 + 轮转文件日志（落用户目录），返回 `app.*` logger。

### 3.2 `app/storage/` — 存储抽象层（§4/§6）

**`base.py`** — 四个 `Protocol` 接口（业务代码只依赖它们）
- `Repository` — 关系存储：`add / get / list / commit`。
- `StateStore` — Redis 热状态：`get / set / delete / hset / hgetall / expire`。
- `EventBus` — Pub/Sub：`publish / subscribe / unsubscribe`。
- `VectorStore` — 向量检索：`upsert / query / delete`。

**`memory.py`** — 纯内存实现（最小依赖即可跑引擎/测试，语义贴近 Redis）
- `InMemoryStateStore` — `_expired`(惰性 TTL) / `get / set / delete / hset / hgetall / expire`。
- `InMemoryEventBus` — `publish / subscribe / unsubscribe`（同步回调）。
- `InMemoryRepository` — 按 model 类型分桶：`add / get / list / commit`。
- `InMemoryVectorStore` — `_cosine`(余弦相似度) / `upsert / query`(top-k) / `delete`。

**`factory.py`** — 后端工厂（按 profile 选实现，`lru_cache` 单例）
- `get_state_store()` / `get_event_bus()` / `get_repository()` / `get_vector_store()` — local 返回内存实现；server 抛 `NotImplementedError`（待 Phase 3）。

**`__init__.py`** — 重导出接口与工厂函数。

### 3.3 `app/models/` — SQLAlchemy 模型（§5）

**`base.py`**
- `Base`(DeclarativeBase) — 声明基类。
- `TimestampMixin` — `created_at / updated_at` 通用列。

**`entities.py`** — 10 张核心表（均含通用时间戳，JSON 列用可移植 `JSON` 类型）
- `Game` — 游戏定义（slug/rule_md/definition/source/version）。
- `RuleDocument` — 上传文书（filename/storage_path/extract_status）。
- `GameSession` — 一局实例（mode/status/seed/snapshot_ref/result）。
- `User` — 人类玩家（identity_hash LAN 身份 / auth）。
- `SessionPlayer` — 参与者（seat/actor_type/user_id/character_id/assigned_role）。
- `CharacterCard` — AI 人物卡（persona/traits）。
- `CharacterBond` — 羁绊有向（affinity -100~100 / tags）。
- `LongTermMemory` — 长期记忆（kind/content/embedding_ref/salience）。
- `HighlightMoment` — 精彩瞬间（title/summary/kind/replay_ref/shared）。
- `SessionEvent` — 事件底账（seq/phase/actor/action/payload/visibility）。

### 3.4 `app/rules/` — 规则摄取管线（§7）

**`primitives.py`** — 能力原语库（§7.3，编译器只认这有限集）
- `Primitive`(dataclass) — `name / semantics / params`。
- `REGISTRY` — 9 个原语：`eliminate / protect / investigate / vote / nominate / reveal / swap / assign / speak`。
- `is_known(name)` / `get(name)`(未知抛错并提示扩展流程) / `all_names()`。

**`schema.py`** — Rule.md 规范与解析（§7.2）
- `RuleParseError`(异常)。
- `AbilitySpec / RoleSpec / PhaseSpec / RuleSpec`(dataclass) — 解析中间表示。
- `_parse_ability(raw)` — 支持 `{primitive: ...}` 与单键映射 `{investigate: {...}}` 两种写法。
- `_parse_role(raw)` / `_parse_phase(raw)` — 角色/阶段解析。
- `_split_frontmatter(text)` — 切出 YAML frontmatter + 正文。
- `parse_rule_md(text)` — 文本 → `RuleSpec`（仅语法结构，不做原语映射校验）。

**`compiler.py`** — 受控编译 Rule.md → GameDefinition（§7.1 第④步）
- `CompileError`(异常)。
- `_ability_def(spec)` — 校验原语已知、参数合法、visibility 合法 → `AbilityDef`。
- `compile_rule_md(text)` — 解析 + 编译的便捷入口。
- `compile_spec(spec)` — 核心：角色配额/阵营校验、阶段引用闭合、actor 角色解析、原语校验、胜负谓词静态校验 → `GameDefinition`。
- `load_builtin(slug)` — 加载并编译 `games/<slug>/Rule.md`。
- `builtin_rule_path(slug)` — 解析内置 Rule.md 路径（经 `resource_dir`）。

**`parser.py`** — 文书结构化（§7.1 ①②，Phase 4 占位）
- `ExtractResult`(dataclass)。
- `extract_text(path)` / `structure_to_rule_md(raw_text)` — 当前 `NotImplementedError`。

### 3.5 `app/engine/` — 游戏引擎（§11，纯逻辑可单测）

**`types.py`** — 数据类型 + 已编译定义
- `Visibility`(Enum) — `PUBLIC / PRIVATE / FACTION`。
- 定义类：`AbilityDef / RoleDef / PhaseDef / GameDefinition`(含 `phase()`/`role()` 查询)。
- 运行时类：`Seat / Action / Event / WinResult / GameState`。
- `GameState` 便捷查询：`seat() / alive_seats() / faction_count()`。

**`predicates.py`** — 胜负谓词安全求值（§7.2，**用 ast 而非 eval**）
- `_eval(node, ctx)` — 递归求值，仅允许比较/布尔/算术/变量/数字。
- `evaluate(predicate, ctx)` — 对谓词求布尔值。
- `validate(predicate, allowed_names)` — 编译期静态校验变量名。

**`engine.py`** — `GameEngine` 契约实现
- `IllegalActionError`(异常) — 防作弊/防 AI 幻觉（§9.1/§10）。
- `init_session(definition, players, seed)` — 分配角色、初始化能力次数、进起始阶段。
- `_expand_roles(definition, n)` — 按 count（含 `rest`）展开角色清单。
- `actors_to_act(state)` — 当前阶段仍需行动且未提交的席位。
- `_phase_seats(state, phase)` — 解析阶段行动者（all_alive / 角色列表）。
- `legal_actions(state, seat)` — 合法行动集（阶段动作 vote/speak/nominate + 角色能力 + 可选 pass）。
- `_targets_other_alive / _vote_options / _nominate_options / _ability_options` — 各类目标/选项生成。
- `apply(state, action)` — 校验 + 即时结算(investigate 私有揭示) / 累积(eliminate/protect/vote) + 产事件。
- `_is_legal / _ability / _consume_use` — 合法性检查、能力查找、次数消耗。
- `advance_phase(state)` — 结算夜晚/投票 → 胜负检查 → 阶段转移（回起始阶段则 round+1）。
- `_resolve_night(state, phase)` — 按 resolution_order 处理 protect/eliminate。
- `_eliminate_victims(state)` — 区分群体决策击杀（狼队取多数）与个体击杀（女巫毒）。
- `_resolve_vote(state, phase)` — 计票、平票无人出局、出局结算。
- `check_win(state)` — 对各阵营 win_conditions 谓词求值。
- `_win_context(state)` — 构造 `{faction}_count / alive_count` 上下文。
- `_emit(...)` — 追加 `Event`（带 seq/round/visibility/audience）。

### 3.6 `app/agents/` — AI 玩家（§10，Phase 2 占位 + 可跑基线）

**`decision_graph.py`**
- `Policy`(Protocol) — `decide(engine, state, seat)`。
- `RandomPolicy` — 从合法行动随机挑选（确定性 seed，驱动 CLI/测试）。
- `DecisionGraph` — LangGraph 子图占位（`NotImplementedError`）。
- `AIPlayer` — 绑定人物卡的 AI 玩家：`__init__ / act`。

### 3.7 `app/memory/` — 记忆系统（§8，Phase 2/5 占位）

- **`stm.py`** `Belief`(心证) / `ShortTermMemory`(`_key/update_belief/beliefs/clear`，键 `session:{id}:stm:{cid}`)。
- **`ltm.py`** `Memory` / `LongTermMemoryStore`(`write/recall/decay`)。
- **`bonds.py`** `Bond` / `BondGraph`(`affinity/apply_outcome/to_behavior_bias`)。
- **`highlights.py`** `Highlight` / `HighlightEvaluator.scan`。
- **`consolidation.py`** `consolidate_session(session_id)` — 局结束固化。
- 除 `ShortTermMemory.clear` 外业务逻辑均 `NotImplementedError`。

### 3.8 `app/multiplayer/` — 联机（§9，Phase 3 占位）

- **`session_manager.py`** `SessionManager`(`__init__/create_session/submit_action/on_disconnect`) — 服务器权威路径。
- **`discovery.py`** `announce_room / discover_rooms` — LAN mDNS/UDP 房间发现。

### 3.9 `app/api/` — FastAPI（§12，Phase 3 占位）

- **`protocol.py`** `Envelope`(dataclass) + `CLIENT_MESSAGES / SERVER_MESSAGES` 常量集（与 TS 镜像）。
- **`app.py`** `create_app()` — FastAPI 工厂占位。
- **`routes_rules.py` / `ws.py`** — 规则管线路由、WebSocket 端点占位。

### 3.10 `app/cli/` — 命令行自动对局（Phase 1 验证工具）

**`autoplay.py`**
- `run_game(slug, players, seed, max_rounds, on_event)` — 全 AI 随机合法行动跑通整局，返回终局；含死循环保护。
- `_flush(state, since, on_event)` — 增量派发新事件。
- `_seat_label(state, seat_id)` — 席位标签 `#i(Role)`。
- `_print_event(state, ev)` — 逐条事件打印（含 round/phase/visibility）。
- `main(argv)` — argparse 入口（`--game/--players/--seed/--quiet`），打印终局角色与胜者。

### 3.11 `migrations/` — Alembic（§4/§13）

- `env.py` — 从 `app.core.config.settings` 取 URL，注册 `models.Base.metadata`，支持 offline/online。
- `script.py.mako` — 迁移模板；`alembic.ini` — 配置（URL 由 env.py 注入）。

---

## 4. 测试（`apps/backend/tests/`，34 用例全通过）

- **`test_predicates.py`**（6）— 比较/布尔/算术求值、未知变量拒绝、校验拒绝未知名、**拒绝任意代码执行**(`__import__`)。
- **`test_compiler.py`**（8）— 最小 Rule 编译、内置 werewolf/avalon 编译、未知原语/悬空阶段/未知角色/非法谓词均报错、9 原语注册齐全。
- **`test_engine.py`**（10）— 角色分配、人数边界、夜晚行动者、预言家查验私有性、非法行动拒绝、夜晚结算推进、两种胜负条件、**引擎不 import 网络/LLM**。
- **`test_autoplay.py`**（多参数）— 多 seed 收敛、胜者与存活数自洽、6/8/10/12 人均跑通、事件 seq 连续有序。

---

## 5. 前端 / 协议 / 桌面（占位骨架）

- **`packages/protocol/src/messages.ts`** — `Envelope / ClientMessageType / ServerMessageType / Action / RequestActionPayload`（§12 单一定义，后续生成 TS+Python）。
- **`apps/desktop/src/features/{lobby,table,cards,rules}/index.tsx`** — 四个 feature 视图占位组件。
- **`apps/desktop/src/net/client.ts`** — `GameSocket`(`connect/send/onMessage`) WS 客户端占位。
- **`apps/desktop/src/store/index.ts`** — `AppState` zustand store 占位。
- **`apps/desktop/src-tauri/`** — `main.rs`(sidecar/LAN 发现占位) + `Cargo.toml` + `tauri.conf.json`。

---

## 6. 内置游戏规则

- **`games/werewolf/Rule.md`** — 完整可编译可运行。frontmatter 含机器可读 roles/phases；6-12 人；角色 Seer/Witch/Werewolf(群体决策)/Villager(rest)；阶段 night(investigate→protect→eliminate)/day_discussion/day_vote(eliminate_top_voted)；胜负 `werewolf_count==0` 与 `werewolf_count>=good_count`。
- **`games/avalon/Rule.md`** — Phase 4 管线生成样本。可解析+结构化编译；真实"任务成败计数/刺杀梅林"需扩展原语 `quest`（已在文档标注），故占位谓词仅为通过编译期校验。

---

## 7. 关键设计落点（对照 Start.md）

1. **游戏逻辑与 AI 解耦**：`engine` 不 import fastapi/redis/langgraph（有测试守护）；人类与 AI 行动都走 `apply`。
2. **规则即数据**：`compiler` 受控编译，未知原语/悬空引用/非法谓词编译期即报错。
3. **存储分层**：`storage` 接口 + profile 工厂；Phase 0/1 用内存实现保证最小依赖可跑。
4. **可写路径统一**：`core/paths.py` 单一出口，避免打包后写安装目录。
5. **安全**：胜负谓词用 ast 求值（非 eval）；引擎对 AI 产出做 `validate` 双保险。

---

## 8. 已知限制 / 后续

- avalon 完整胜负需新增 `quest` 扩展原语（Phase 4）。
- 夜晚结算为简化模型（女巫毒/狼刀分流已处理，未覆盖猎人开枪、连环等复杂联动）。
- 投票平票当前规则=无人出局；可由 Rule.md `tie_rule` 配置覆盖（接口已留）。
- agents/memory/multiplayer/api 为接口占位，业务逻辑待对应 Phase 接入。
- 验证沙箱曾出现文件挂载读取不一致（`cp`/`ruff` 偶读到截断版本），但 Python import 读到完整版本，故 34 测试稳定通过；本机真实文件完整正确。
