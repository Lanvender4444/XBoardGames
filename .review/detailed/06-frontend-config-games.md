# 06 · 前端 / 共享协议 / 内置规则 / 工程配置

> 本文覆盖四块：① 前端桌面端（Tauri+React，§3，Phase 3 占位）② 共享协议 `packages/protocol`
> ③ 内置游戏 `games/*/Rule.md` ④ 工程配置（`pyproject.toml`、Alembic 迁移）。
> 前端层几乎全是结构占位（接口/组件签名就位，逻辑标 `TODO`），目的是先锁定契约与目录形态。

---

# 一、`packages/protocol/` — 前后端共享协议（§12）🟢

**唯一一处"有实质内容"的占位**：定义通信契约，供 TS 前端与 Python 后端共同遵守。

## `packages/protocol/src/messages.ts`
- `interface Envelope<P>`：消息信封——`type / session_id / seq / payload<P>`。所有收发消息的统一外壳，`seq` 用于排序与补丁对齐。
- `type ClientMessageType`：客户端→服务器，五种——`join / leave / submit_action / chat / heartbeat`。
- `type ServerMessageType`：服务器→客户端，七种——`state_snapshot / state_patch / event / request_action / phase_changed / game_over / error`。
- `interface Action`：客户端意图行动——`seat / type(原语名) / target? / channel? / extra?`。`type` 直接对应能力原语库
  （eliminate/investigate/vote/nominate/quest/speak…），保证前端发的意图与引擎原语同名。
- `interface RequestActionPayload`：服务器向某席位请求行动——`seat / legal_actions / deadline_ms`。
  **关键**：`legal_actions` 由引擎下发，前端只渲染这批合法行动，确保"前端能点的=引擎认的"，杜绝非法提交（§12）。

> 注释明确：当前为手写定义，Phase 3 接入代码生成后将由单一 schema 同时产出 TS 与 Python，
> 消除两端漂移（与 `app/api/protocol.py` 的镜像现状对应）。

## `packages/protocol/package.json` / `README.md`
包声明与说明。

---

# 二、`apps/desktop/` — Tauri + React 桌面客户端（§3）

## `src/net/client.ts` 🟡 — WebSocket 客户端占位
`class GameSocket`：`connect() / send<P>(msg) / onMessage(cb)` 三个方法全为 `TODO Phase 3`。
已正确 `import type { Envelope }`，证明前端复用 `packages/protocol` 的类型（单一事实来源）。

## `src/store/index.ts` 🟡 — 前端状态（zustand）占位
`interface AppState { sessionId }`；注释标注 Phase 2 用 `create<AppState>()` 建 store。当前仅类型骨架。

## `src/features/*/index.tsx` 🟡 — 四个功能视图占位
- `lobby/`：LobbyView——建房/加入/选游戏（大厅）。
- `rules/`：RulesView——上传 Rule.md、查看规则管线结果。
- `table/`：TableView——牌桌主界面（席位、阶段、行动）。
- `cards/`：CardsView——人物卡/能力展示。

四者均为 `export default function XView(): React.ReactElement`，返回 `<div data-feature="...">TODO</div>`。
目录即 §3 规定的 feature 切分，组件签名稳定，后续逐个填充 UI 与状态绑定。

## `src-tauri/` 🟡 — Tauri 原生外壳（Rust）
- `src/main.rs`：`fn main()` 仅打印占位串。注释写明三大职责——
  窗口管理、启动 **Python 后端 sidecar + 内嵌 redis-server**、**LAN 发现(mDNS/UDP)**；
  并强调**所有可写数据必须落用户可写目录，绝不写安装目录**（§1/§4，安全/权限约束）。
- `Cargo.toml`：Rust 依赖清单（占位）。
- `tauri.conf.json`：Tauri 应用配置（窗口、打包、sidecar 等占位）。

## `package.json` / `README.md`
前端包声明与说明。

---

# 三、`games/` — 内置规则文书（§7.1 / 附录 A）🟢

Rule.md 采用 **YAML front-matter（机器可读，编译器消费）+ 正文 Markdown（人类可读镜像，供审校）** 的双轨结构。
两个内置样本共用同一套原语与状态机，正是用来验证引擎通用性。

## `games/werewolf/Rule.md` — 狼人杀（内置，Phase 1 主验证样本）
- **元信息**：slug=werewolf，6–12 人，起始阶段 night，阵营 `good / werewolf`。
- **胜负**：好人 `werewolf_count == 0`；狼人 `werewolf_count >= good_count`（屠边）。
- **角色**：Seer（investigate，夜晚查阵营，private）、Witch（protect 解药×1 / eliminate 毒药×1）、
  Werewolf×2（eliminate，`group_decision`，私有频道 `werewolf_chat`）、Villager（count=`rest` 占满剩余）。
- **阶段闭环**：night（结算序 investigate→protect→eliminate，60s）→ day_discussion（speak，180s）→
  day_vote（vote，`on_complete: eliminate_top_voted`，`check_win`）→ night。
- 正文 Markdown 与 front-matter 一一对应，是审校第③步比对的依据。

## `games/avalon/Rule.md` — 阿瓦隆（管线生成验证样本，Phase 4）
- 定位：**非内置、走规则摄取管线生成**的样本（§14 Phase 4）。当前可被 `schema.parse_rule_md` 解析、
  `compiler.compile_spec` 编译通过。
- 5–10 人，阵营 `good / evil`，角色含 Merlin/Percival/LoyalServant/Morgana/Assassin/MinionOfMordred，
  阶段 team_building→team_vote→quest→（循环）+ assassinate。
- **诚实的占位说明**：注释明确当前胜负谓词（`evil_count==0` / `good_count==0`）只是为通过编译期校验的合法占位；
  阿瓦隆真实胜负（任务成败计数 + 刺杀梅林）需 Phase 4 新增扩展原语 `quest`（§7.3）。`team_vote` 的
  `eliminate_top_voted`、`assassinate` 同为占位语义。这种"先编译通过、逻辑留待扩展"的标注体现了渐进式设计。

---

# 四、工程配置 ⚙️

## `apps/backend/pyproject.toml`
- 元信息 + **极简核心依赖**：运行时仅 `pyyaml`（引擎是纯逻辑，可单测、不碰网络/LLM）。
- **按 Phase 切分的 optional-dependencies**，保持核心轻量、按需安装：
  `storage`（sqlalchemy/alembic）、`api`（fastapi/uvicorn/redis/websockets，Phase 3）、
  `server`（pymysql，server profile）、`ai`（langgraph/langchain-core，Phase 2）、
  `vector`（faiss-cpu，local 向量库；server 可换 pgvector）、`dev`（pytest/ruff）。
- `[project.scripts]`：`autoplay = "app.cli.autoplay:main"`（命令行自动对局入口）。
- 构建用 hatchling 打包 `app`；pytest 配 `pythonpath=["."]`；ruff line-length=100 / py310。

## `apps/backend/alembic.ini` + `migrations/`（§4/§13）
- `alembic.ini`：脚本目录 `migrations`，`prepend_sys_path=.`，日志配置；
  注释强调 **SQLite↔MySQL 差异收敛在迁移脚本里**，且 `sqlalchemy.url` 不在此硬编码。
- `migrations/env.py`：从 `app.core.config.settings.database_url` 取 URL、`app.models.Base` 取 metadata，
  保证 **LAN(SQLite) 与 server(MySQL) 共用同一套模型与迁移**；同时支持 offline/online 两种迁移模式。
- `migrations/versions/`：目前仅 `.gitkeep`，**尚无版本脚本**（待模型定稿后 `alembic revision --autogenerate`）。
- `script.py.mako`：迁移脚本模板。

---

# 五、架构契约小结

这一层虽未实现，但已用代码"钉死"了三条关键契约：

1. **类型单一来源**：前端 `import` 自 `packages/protocol`，后端 `app/api/protocol.py` 镜像同一套常量，
   Phase 3 用代码生成收口，从根上防止协议漂移。
2. **服务器权威 + 合法行动下发**：`request_action` 必带 `legal_actions`，前端不自行判定合法性，
   与引擎 `legal_actions`/`apply` 校验链一致（§9/§12）。
3. **数据落点安全**：Tauri 注释明确禁止写安装目录，所有可写状态进用户目录与内嵌 Redis（§1/§4）。
