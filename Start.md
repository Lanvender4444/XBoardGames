# Start.md — AI 桌游平台（AI Tabletop Platform）

> 一个可扩展的 AI 桌游引擎：内置**狼人杀**与**阿瓦隆**，支持"喂规则文书 → 生成可执行游戏",拥有带**羁绊**与**长短期记忆**的 AI 人物卡，并提供**局域网 / 服务器**双模式联机。

---

## 0. 文档目的

本文件是项目的**单一事实来源（Single Source of Truth）**,定义架构、数据模型、核心模块契约、通信协议与开发路线。任何模块开始编码前,先回到本文件确认接口与边界。

设计上贯穿三条原则:

1. **游戏逻辑与 AI 解耦**。引擎只认"谁该行动、行动是否合法、状态如何变更",它不关心行动来自人类点击还是 LangGraph 推理。这样人机混局、纯 AI 局、纯人类局都跑同一套引擎。
2. **规则即数据**。游戏不是写死的代码,而是由 `Rule.md` 编译出的**游戏定义（Game Definition）**驱动的状态机。内置游戏只是"官方维护的 Rule.md"。
3. **存储分层（Storage Profile）**。同一套业务代码,通过存储抽象层在 LAN 模式(轻量内嵌)和服务器模式(MySQL + Redis)之间切换。

---

## 1. 技术栈与选型理由

| 层 | 技术 | 选它的原因 |
|---|---|---|
| 桌面外壳 | Tauri (Rust) | 体积小、原生窗口、可托管本地后端(LAN 主机模式)、可打包 Python sidecar |
| 前端 | React + TypeScript | 复杂状态多(牌局、卡片、计时器),组件化 + 强类型协议收益大 |
| 后端 | Python + FastAPI | LangGraph 是 Python 生态;FastAPI 同时提供 HTTP 与 WebSocket |
| AI 编排 | LangGraph | 游戏流程天然是"带状态的图":阶段=节点、转移=边、Agent 推理=子图 |
| 结构化存储 | MySQL(服务器)/ SQLite(LAN) | 通过 SQLAlchemy ORM 统一,见 §4 存储分层 |
| 实时状态 / 缓存 / 广播 | Redis | 牌局热状态、短期记忆、Pub/Sub 多端广播、回合锁与计时 |
| 向量检索(长期记忆) | pgvector / Chroma / FAISS(可插拔) | 长期记忆按"当前情境"做相似度召回 |

> **关于 MySQL + Redis 在 LAN 模式的取舍**:服务器部署用托管 MySQL + Redis 是标准做法。但要求每个 LAN 主机本地装 MySQL 太重。方案:ORM 层用 SQLAlchemy,LAN 用 SQLite、服务器用 MySQL(模型代码不变);Redis 体积小,LAN 模式把 `redis-server` 作为 Tauri sidecar 一起打包。详见 §4 与 §9。你之前在 Tauri + Python sidecar 项目里踩过的 `sys._MEIPASS` / 写权限问题,这里同样适用——所有可写数据(SQLite、Redis dump、上传文书)必须落到用户可写目录(`%APPDATA%` / `~/.local/share`),绝不写进安装目录。

---

## 2. 整体架构

```
┌──────────────────────────────────────────────────────────┐
│  Tauri 桌面应用                                            │
│  ┌────────────────────────┐   ┌──────────────────────┐    │
│  │ React 前端 (UI)        │   │ Rust 核心            │    │
│  │ - 牌桌 / 角色面板      │◄─►│ - 窗口 / IPC         │    │
│  │ - 人物卡 / 记忆查看    │   │ - 启动本地 sidecar   │    │
│  │ - 规则上传 / 房间大厅  │   │ - LAN 发现(mDNS/UDP) │    │
│  └───────────┬────────────┘   └──────────┬───────────┘    │
└──────────────┼───────────────────────────┼────────────────┘
               │ WebSocket / HTTP          │ 进程管理
               ▼                           ▼
┌──────────────────────────────────────────────────────────┐
│  后端 (FastAPI)                                            │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐  │
│  │ 规则管线 │ │ 游戏引擎 │ │ 记忆系统 │ │ 联机/会话    │  │
│  │ Rule     │ │ State    │ │ STM/LTM  │ │ Session +    │  │
│  │ Pipeline │ │ Machine  │ │ + 羁绊   │ │ Pub/Sub      │  │
│  └──────────┘ └────┬─────┘ └────┬─────┘ └──────┬───────┘  │
│                    │            │              │          │
│              ┌─────┴────────────┴──────────────┴─────┐    │
│              │ LangGraph 编排 (AI 玩家决策图)        │    │
│              └───────────────────────────────────────┘    │
└──────────────┬───────────────────────────┬───────────────┘
               ▼                           ▼
        ┌─────────────┐             ┌─────────────┐
        │ MySQL/SQLite│             │   Redis     │
        │ (持久结构)  │             │ (热状态/广播)│
        └─────────────┘             └─────────────┘
```

**核心数据流(一局游戏的生命周期)**:

1. 玩家在大厅选择已生成的游戏定义 → 创建 `GameSession`。
2. 引擎从 `Rule.md` 编译出的 Game Definition 初始化状态机,把热状态写入 Redis。
3. 进入某阶段 → 引擎确定"本阶段哪些 actor 需要行动"。
4. 对人类 actor:通过 WebSocket 推送可选行动,等待回传;对 AI actor:调用 LangGraph 决策图。
5. 行动经引擎**合法性校验 + 优先级结算** → 状态变更 → 通过 Redis Pub/Sub 广播给所有客户端。
6. 阶段转移条件满足 → 进入下一阶段,循环直到满足胜利条件。
7. 游戏结束 → 触发记忆**固化(consolidation)**:短期记忆中的关键事件提炼为长期记忆,更新角色间羁绊,标记"精彩瞬间"。

---

## 3. 目录结构(Monorepo)

```
ai-tabletop/
├── apps/
│   ├── desktop/                  # Tauri + React
│   │   ├── src/                  # React 前端
│   │   │   ├── features/
│   │   │   │   ├── lobby/        # 大厅 / 房间发现
│   │   │   │   ├── table/        # 牌桌主界面
│   │   │   │   ├── cards/        # 人物卡 / 羁绊图 / 记忆查看
│   │   │   │   └── rules/        # 规则文书上传与 Rule.md 编辑器
│   │   │   ├── net/              # WebSocket 客户端 + 协议类型
│   │   │   └── store/            # 前端状态(zustand/redux)
│   │   └── src-tauri/            # Rust:窗口、sidecar 启动、LAN 发现
│   │
│   └── backend/                  # Python 后端
│       ├── app/
│       │   ├── api/              # FastAPI 路由 + WebSocket 端点
│       │   ├── rules/            # 规则摄取管线(解析→Rule.md→编译)
│       │   │   ├── parser.py     # 文书 → 结构化抽取(LLM)
│       │   │   ├── schema.py     # Rule.md 规范与校验
│       │   │   ├── compiler.py   # Rule.md → Game Definition
│       │   │   └── primitives.py # 能力原语库
│       │   ├── engine/           # 游戏引擎(状态机、结算、胜负判定)
│       │   ├── agents/           # LangGraph 图与 AI 玩家
│       │   ├── memory/           # STM / LTM / 羁绊 / 精彩瞬间
│       │   ├── multiplayer/      # 会话管理、Pub/Sub、连接生命周期
│       │   ├── storage/          # 存储抽象层(profile: local/server)
│       │   ├── models/           # SQLAlchemy 模型
│       │   └── core/             # 配置、依赖注入、日志
│       └── tests/
│
├── packages/
│   └── protocol/                 # 前后端共享的协议 schema(TS + Python 代码生成)
│
├── games/                        # 内置游戏的官方 Rule.md
│   ├── werewolf/Rule.md
│   └── avalon/Rule.md
│
└── docs/
    └── Start.md                  # 本文件
```

---

## 4. 存储分层(Storage Profile)

存储抽象层根据环境变量 `STORAGE_PROFILE` 选择实现,业务代码只依赖接口:

| 能力 | 接口 | `local`(LAN) | `server` |
|---|---|---|---|
| 关系存储 | `Repository` | SQLite(SQLAlchemy) | MySQL(SQLAlchemy) |
| 热状态/缓存 | `StateStore` | 内嵌 `redis-server` sidecar | 托管 Redis |
| 广播 | `EventBus` | Redis Pub/Sub(本机) | Redis Pub/Sub(集群) |
| 向量检索 | `VectorStore` | FAISS / Chroma(本地文件) | pgvector / 托管向量库 |

要点:
- 因为统一走 SQLAlchemy,SQLite ↔ MySQL 的差异(类型、并发)收敛在迁移脚本里;迁移用 Alembic。
- LAN 模式仍然用 Redis(只是本机进程),保证联机广播逻辑与服务器模式**完全一致**,避免两套代码路径。
- 所有可写路径由 `core/paths.py` 统一解析到平台用户目录,杜绝打包后的写权限问题。

---

## 5. 数据模型(关系表)

以下为核心表,字段用 ORM 视角描述(省略时间戳等通用列)。

**games** — 游戏定义(由 Rule.md 编译产物快照)
- `id`, `slug`(werewolf/avalon/...), `name`, `min_players`, `max_players`
- `rule_md`(原始 Rule.md 文本), `definition`(JSON,编译后的可执行定义), `source`(builtin/generated), `version`

**rule_documents** — 上传的规则源文书
- `id`, `game_id`(可空,生成前为空), `filename`, `storage_path`, `mime`, `extract_status`

**game_sessions** — 一局游戏实例
- `id`, `game_id`, `host_user_id`, `mode`(lan/server), `status`(lobby/running/finished)
- `seed`(随机种子,用于复盘), `snapshot_ref`(Redis 中热状态键), `result`(JSON)

**users** — 人类玩家
- `id`, `display_name`, `identity_hash`(LAN 模式用 MAC+UUID 哈希,沿用你 ebook 项目的身份方案), `auth`(server 模式凭证)

**session_players** — 某局的参与者(人或 AI)
- `id`, `session_id`, `seat`, `actor_type`(human/ai), `user_id`(人), `character_id`(AI), `assigned_role`

**character_cards** — AI 人物卡
- `id`, `name`, `avatar`, `persona`(性格/口吻/策略倾向的 prompt 描述), `traits`(JSON:谨慎度、攻击性、欺骗倾向等数值), `owner_user_id`(可空,玩家可拥有自己的卡)

**character_bonds** — 羁绊(有向)
- `id`, `from_character_id`, `to_character_id`, `affinity`(-100~100 信任/好感), `tags`(JSON:背叛过、救过、宿敌...), `last_updated_session_id`

**long_term_memories** — 长期记忆(跨局)
- `id`, `character_id`, `kind`(semantic/episodic), `content`(自然语言摘要), `embedding_ref`(向量库引用), `salience`(重要度), `related_character_ids`(JSON), `source_session_id`

**highlight_moments** — 精彩瞬间
- `id`, `session_id`, `title`, `summary`, `participants`(JSON), `kind`(神预言/极限翻盘/经典欺骗...), `replay_ref`(指向事件日志区间), `shared`(是否可分享)

**session_events** — 事件日志(复盘 + 记忆来源)
- `id`, `session_id`, `seq`, `phase`, `actor`, `action`, `payload`(JSON), `visibility`(public/private/faction)

> 设计点:`session_events` 是一切的底账。复盘、记忆固化、精彩瞬间提取都从它派生,而不是各自重复记录。`visibility` 决定某条事件对谁可见(狼队私聊、预言家查验结果只对本人可见等)。

---

## 6. Redis 使用设计

- `session:{id}:state` — 牌局完整热状态(JSON 或 Hash),引擎的工作内存。
- `session:{id}:stm:{character_id}` — AI 角色本局短期记忆(带 TTL,局结束清理)。
- `session:{id}:presence` — 玩家在线/连接状态(Set + 心跳过期)。
- `session:{id}:phase_timer` — 阶段计时(用过期键 + keyspace 通知触发超时)。
- `session:{id}:locks:turn` — 回合锁,避免并发行动竞态。
- Pub/Sub 频道 `channel:session:{id}` — 状态变更广播,所有连接此局的 WebSocket 订阅并转发给客户端。

---

## 7. 核心功能一:规则摄取管线(文书 → Rule.md → 游戏)

这是平台可扩展性的关键。难点在于:**如何把自然语言规则变成可执行游戏,又不需要为每个新游戏写任意代码**。答案是"能力原语库 + 受控编译"。

### 7.1 管线四步

```
文书(PDF/docx/txt/图片)
   │  ① 提取:OCR / 文本抽取
   ▼
原始文本
   │  ② 结构化:LLM 抽取角色、阶段、动作、胜负条件
   ▼
Rule.md(结构化中间表示) ←── ③ 人工审校/编辑(关键!)
   │  ④ 编译:Rule.md → Game Definition(状态机 + 原语绑定)
   ▼
可运行游戏
```

**第 ③ 步人工审校不可省**。LLM 抽取会有歧义和遗漏,Rule.md 是人类可读可改的中间层。前端提供 Rule.md 编辑器 + 实时校验(schema 合法、阶段引用闭合、能力都映射到已知原语)。审校通过才允许编译。

### 7.2 Rule.md 规范

`Rule.md` = YAML frontmatter(元信息)+ 结构化正文。约定如下:

```markdown
---
slug: werewolf
name: 狼人杀
min_players: 6
max_players: 12
factions: [good, werewolf]            # 阵营
win_conditions:
  good:      "werewolf_count == 0"     # 谓词,对游戏状态求值
  werewolf:  "werewolf_count >= good_count"
---

## 角色(Roles)

### 预言家 Seer
- faction: good
- count: 1
- abilities:
    - investigate:                     # 映射到原语 investigate
        target: single_other
        reveals: faction               # 查验结果:阵营
        phase: night
        visibility: private

### 女巫 Witch
- faction: good
- count: 1
- abilities:
    - protect: { uses: 1, phase: night }   # 解药
    - eliminate: { uses: 1, phase: night }  # 毒药

### 狼人 Werewolf
- faction: werewolf
- count: 2
- abilities:
    - eliminate: { target: single_other, phase: night, group_decision: true }
- channels: [werewolf_chat]            # 狼队私聊频道

### 平民 Villager
- faction: good
- count: rest                          # 占满剩余席位

## 阶段(Phases)

### night
- actors: [Werewolf, Seer, Witch]
- resolution_order: [investigate, protect, eliminate]   # 结算优先级
- timer: 60s
- next: day_discussion

### day_discussion
- actors: all_alive
- actions: [speak]
- timer: 180s
- next: day_vote

### day_vote
- actors: all_alive
- actions: [vote]
- on_complete: eliminate_top_voted
- next: night
- check_win: true                      # 每轮投票后检查胜负
```

阿瓦隆的 `Rule.md` 同理,只是原语组合不同:`nominate`(队长提名队员)、`vote`(组队公投)、`quest`(任务成败投票,梅林/刺客等特殊角色用 `reveal` / `investigate` 的变体)。

### 7.3 能力原语库(Primitives)

编译器只认有限的一组可组合原语;Rule.md 里的每个 ability 必须映射到其中之一(带参数)。这样"生成任意游戏"被约束在安全、可测的范围内:

| 原语 | 语义 | 参数示例 |
|---|---|---|
| `eliminate` | 移除一名玩家 | target, uses, group_decision |
| `protect` | 抵消一次 eliminate | target, uses |
| `investigate` | 向行动者揭示目标信息 | target, reveals(faction/role) |
| `vote` | 群体决策,产出计票 | candidates, tie_rule |
| `nominate` | 提名/组队 | count, by(队长) |
| `reveal` | 向某范围公开信息 | attribute, scope |
| `swap` | 交换两者的某属性 | a, b, attribute |
| `assign` | 分配角色/标记 | target, value |
| `speak` | 发言(进入公共/私有频道) | channel |

新游戏若需要库里没有的机制 → 走"扩展原语"评审流程(写新 primitive + 测试),而不是在 Rule.md 里塞任意逻辑。这是**可控性**与**表达力**的刻意权衡。

---

## 8. 核心功能二:人物卡片 · 羁绊 · 记忆系统

这是项目的灵魂:AI 玩家不是一次性 prompt,而是**有性格、有关系、会记事**的角色。

### 8.1 记忆分层

```
                 ┌─────────────── 长期记忆 LTM(跨局,MySQL + 向量库) ──────────────┐
                 │  · 语义记忆:对某角色的稳定认知("阿狼总爱悍跳预言家")           │
   固化          │  · 情景记忆:具体精彩事件(可被未来对局召回)                     │
 (局结束) ──────►│  · 召回:按"当前情境"embedding 相似度检索 top-k                  │
                 └────────────────────────────────────────────────────────────────┘
                                          ▲
                                          │ 提炼
                 ┌──────────── 短期记忆 STM(单局,Redis,带 TTL) ──────────────────┐
                 │  · 本局事件流、对各玩家的实时怀疑度/信任度                       │
                 │  · 当前心证("3 号发言矛盾,可能是狼")                           │
                 └────────────────────────────────────────────────────────────────┘
```

- **短期记忆(STM)**:作用域=单局。每个 AI 角色维护本局的"心证"——对其他席位的身份猜测、信任度、关键发言摘要。存 Redis,局结束清空。
- **长期记忆(LTM)**:作用域=跨局。分语义(对某角色的稳定印象)和情景(难忘事件)。存关系表 + 向量库,通过 embedding 按当前情境召回。
- **羁绊(Bonds)**:角色间的有向关系数值(`affinity` -100~100)+ 标签(救过我/坑过我/宿敌)。每局结束根据共同经历更新,**直接影响 AI 行为**(对高好感者更倾向相信、组队、护体;对宿敌更倾向针对)。

### 8.2 记忆如何进入决策(与 LangGraph 配合)

AI 角色每次行动前,LangGraph 图里的"召回节点"做三件事:
1. 取本局 STM(当前心证 + 近期事件)。
2. 以"当前情境"为 query,从 LTM 向量库召回 top-k 相关情景/语义记忆。
3. 读取与在场角色的羁绊,转成行为偏置。

这些拼进 prompt 后交给"推理节点"产出行动。行动落地后"编码节点"更新 STM。详见 §10。

### 8.3 精彩瞬间(Highlight Moments)

游戏过程中,一个**瞬间评估器**扫描 `session_events`,识别高戏剧性事件(神预言命中、最后一票翻盘、成功的深度欺骗、关键自爆等),用 LLM 生成标题与摘要,存 `highlight_moments` 并关联事件区间(可回放)。

- "和你的精彩瞬间":若该局有人类玩家参与,瞬间会标注涉及的人类玩家,沉淀为 AI 角色对**这位玩家**的长期记忆——下次同台,AI 会"记得你上次那波操作"。
- "和其他角色的精彩瞬间":纯 AI 之间的高光同样进入彼此 LTM,并更新羁绊。
- 可分享:`shared=true` 的瞬间可导出(图文/短回放),用于社交传播。

### 8.4 局结束的记忆固化(Consolidation)

一局结束触发后台任务:
1. 从 STM + 事件日志中,用 LLM 提炼"本局值得长期记住的若干条"。
2. 写入 LTM(语义 + 情景),生成 embedding 入向量库,设 `salience`。
3. 根据共同经历更新所有相关羁绊(谁救了谁、谁出卖了谁)。
4. 清理本局 STM。

> 控制记忆膨胀:LTM 设容量与衰减——低 `salience` 且长期未被召回的记忆会被合并或遗忘,模拟人类记忆的自然淡化,也防止向量库无限增长。

---

## 9. 核心功能三:联机系统(LAN / 服务器双模式)

引擎对"actor 是人还是 AI、在本机还是远程"无感知。联机层只解决三件事:**发现、连接、广播**。

### 9.1 服务器权威模型

无论哪种模式,**后端是状态唯一权威**。客户端只发"意图行动",由引擎校验后改状态,再经 Redis Pub/Sub 广播。客户端永不直接改游戏状态——杜绝作弊与不一致。可见性由 `session_events.visibility` 控制:狼队私聊、查验结果等只推给该看见的客户端。

### 9.2 LAN 模式(局域网)

- 某玩家点"创建本地房间" → Tauri 的 Rust 核心启动打包好的 Python 后端 sidecar + 内嵌 `redis-server`,绑定 `0.0.0.0:PORT`。
- **房间发现**:host 通过 mDNS 或 UDP 广播宣告房间(沿用你 ebook 项目的 UDP 发现经验);同网段其他客户端收到后在大厅列出。
- 其他玩家的 React 前端直接把 WebSocket 连到 host 的后端。
- 数据落 host 本地 SQLite(用户可写目录),Redis 用本机 sidecar。

### 9.3 服务器模式(部署)

- 后端部署在云服务器,所有客户端连公网地址,需鉴权(`users.auth`)。
- MySQL + 托管 Redis;Redis Pub/Sub 同时承担多实例间广播,可水平扩展。
- 同一套后端代码,仅 `STORAGE_PROFILE=server` 与配置不同。

### 9.4 连接生命周期

- 入局:WebSocket 握手 → 鉴权/身份 → 加入 `presence` → 订阅 `channel:session:{id}` → 收到状态快照。
- 断线:心跳过期 → 标记离线;若是人类 actor 且超时,可由 AI 托管该席位继续游戏(可配置)。
- 重连:凭 session token 重新订阅,拉取最新快照 + 增量事件补齐。

---

## 10. LangGraph 编排设计

把游戏建模成图,正是 LangGraph 的强项。分两层:

**外层——游戏编排图**:节点 = 游戏阶段(night / day_discussion / day_vote ...),边 = 阶段转移(由 Rule.md 编译而来)。状态对象 = 牌局完整状态。每个阶段节点负责"收集本阶段所有 actor 的行动"。

**内层——AI 玩家决策子图**(对每个需要行动的 AI 角色调用一次):

```
   感知(Perceive)            ← 取当前可见游戏状态 + 本阶段可选行动
        │
   召回(Recall)              ← STM + LTM 向量召回 + 羁绊偏置(§8.2)
        │
   推理(Reason)              ← LLM 结合人物卡 persona/traits 产出决策
        │
   行动(Act)                 ← 输出合法行动(交回引擎做最终校验)
        │
   编码(Encode)              ← 更新 STM(更新心证、信任度)
```

要点:
- **人物卡驱动差异**:同样的局面,谨慎型角色保守,激进型角色悍跳——差异来自 `character_cards.persona/traits` 注入 prompt。
- **合法性双保险**:LLM 产出的行动仍要过引擎的 `validate`(防止 AI"幻觉"出非法操作),非法则要求重试或回退到安全默认行动。
- **成本控制**:召回 top-k、限制 STM 窗口、对低风险阶段(如纯发言)用更小的模型,关键决策(查验/投票)用更强模型。

---

## 11. 游戏引擎契约

引擎是纯逻辑、可单测、不依赖网络与 LLM。核心接口:

```python
class GameEngine:
    def init_session(self, definition: GameDefinition, players: list[Seat]) -> GameState: ...
    def actors_to_act(self, state: GameState) -> list[Seat]:
        """当前阶段需要行动的席位"""
    def legal_actions(self, state: GameState, seat: Seat) -> list[Action]:
        """某席位的合法行动集合"""
    def apply(self, state: GameState, action: Action) -> tuple[GameState, list[Event]]:
        """校验 + 按 resolution_order 结算 + 产出事件(已带 visibility)"""
    def advance_phase(self, state: GameState) -> tuple[GameState, list[Event]]:
        """阶段转移"""
    def check_win(self, state: GameState) -> WinResult | None:
        """对 win_conditions 谓词求值"""
```

引擎不区分行动来源:人类行动从 WebSocket 进来,AI 行动从 LangGraph 进来,二者都变成 `Action` 喂给 `apply`。这就是"人机混局跑同一套引擎"的实现基础。

---

## 12. 通信协议(WebSocket)

前后端共享 `packages/protocol` 的 schema(单一定义,生成 TS 与 Python 类型,避免漂移)。消息信封:

```json
{ "type": "...", "session_id": "...", "seq": 0, "payload": { } }
```

**客户端 → 服务器**
- `join` / `leave` — 入局/离开
- `submit_action` — 提交行动(投票、查验、发言、提名...)
- `chat` — 频道发言(payload 带 channel)
- `heartbeat`

**服务器 → 客户端**
- `state_snapshot` — 完整快照(入局/重连时)
- `state_patch` — 增量状态变更
- `event` — 一条 `session_event`(已按接收者过滤 visibility)
- `request_action` — 轮到你,附 `legal_actions` 与计时
- `phase_changed` / `game_over`
- `error`

> 给人类的 `request_action` 一定带 `legal_actions`,前端据此渲染可点选项——保证前端展示与引擎判定一致。

---

## 13. 部署

- **LAN**:`tauri build` 产物内含 Python sidecar(PyInstaller)+ `redis-server` 二进制。首启在用户目录初始化 SQLite 并跑 Alembic 迁移。注意签名/防火墙放行(LAN 端口)。
- **服务器**:后端容器化(FastAPI + Uvicorn/Gunicorn);MySQL、Redis、向量库为独立服务;Nginx 反代 + WSS;客户端配置指向公网地址。

---

## 14. 开发路线图

**Phase 0 — 地基**
- Monorepo、存储抽象层、`protocol` 包、SQLAlchemy 模型 + Alembic、配置与路径管理。

**Phase 1 — 引擎 + 内置狼人杀(无 AI、无联机)**
- 能力原语库、状态机、结算与胜负判定;手写 `games/werewolf/Rule.md` 并编译;本地单机、全人类、命令行/最简 UI 跑通一局。这是验证引擎抽象是否成立的关键里程碑。

**Phase 2 — AI 玩家 + 记忆**
- LangGraph 决策子图、人物卡、STM;再接 LTM + 向量召回 + 羁绊;人机混局可玩。

**Phase 3 — 联机**
- WebSocket + Redis Pub/Sub + 会话/在线/断线重连;先 LAN(sidecar + UDP 发现),再服务器模式。

**Phase 4 — 规则摄取管线**
- 文书提取 → LLM 结构化 → Rule.md 编辑器/校验 → 编译;用阿瓦隆作为"非内置、走管线生成"的验证样本。

**Phase 5 — 精彩瞬间 + 打磨**
- 瞬间评估器、回放、分享;记忆衰减/合并;成本与体验优化。

> 路线刻意把"引擎正确性"(Phase 1)排在 AI 与联机之前。引擎抽象一旦站住,后面的 AI、联机、规则生成都是往同一套契约上挂模块。

---

## 15. 关键风险与取舍

| 风险 | 说明 | 缓解 |
|---|---|---|
| 规则生成不可控 | 自然语言规则千变万化,LLM 抽取易错 | 能力原语库约束表达力 + 强制人工审校 Rule.md + 编译期 schema 校验 |
| AI 产出非法行动 | LLM 幻觉出引擎不允许的操作 | 引擎 `validate` 双保险 + 非法重试/安全回退 |
| 记忆膨胀 | LTM 与向量库无限增长 | salience 衰减 + 低价值记忆合并/遗忘 |
| 两套存储路径分叉 | LAN(SQLite) vs 服务器(MySQL) | 统一 SQLAlchemy + Redis 在两端都用,逻辑单一路径 |
| 打包后写权限 | sidecar 写安装目录失败(你之前踩过) | 所有可写数据强制走用户可写目录,`core/paths.py` 统一 |
| LLM 成本 | 多 AI × 多回合 token 消耗大 | 分级模型 + 限制召回/记忆窗口 + 低风险阶段降级 |
| 实时一致性 | 多端状态不同步 | 服务器权威 + 快照/增量 + seq 序号补齐 |

---

## 附录 A — 内置游戏速览

| | 狼人杀 | 阿瓦隆 |
|---|---|---|
| 阵营 | 好人 vs 狼人 | 正义 vs 邪恶 |
| 核心机制原语 | eliminate / investigate / protect / vote | nominate / vote / quest / reveal |
| 特殊角色 | 预言家、女巫、猎人... | 梅林、刺客、派西维尔、莫甘娜... |
| 信息不对称 | 狼队私聊、夜晚私有行动 | 邪恶方互认、梅林知晓邪恶 |
| 胜负判据 | 屠边 / 票出狼 | 任务成败计数 + 刺杀梅林 |

两者都落在同一组原语 + 阶段状态机上,正好验证引擎的通用性。