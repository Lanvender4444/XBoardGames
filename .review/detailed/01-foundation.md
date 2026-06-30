# 01 · 地基层：core / storage / models

---

## `app/__init__.py` ⚙️
仅声明包与 `__version__ = "0.0.1"`。让 `app` 成为可导入包（hatchling 打包入口）。

---

# 一、`app/core/` — 配置、路径、日志

## `app/core/paths.py` 🟢 — 可写路径的单一出口

**为什么存在**：Start.md §1/§4/§15 反复强调——打包成 Tauri + PyInstaller sidecar 后，安装目录
（`sys._MEIPASS`）是只读的，任何写操作（SQLite、Redis dump、上传文书、向量库）必须落到平台
**用户可写目录**。本文件是全项目唯一允许拼可写路径的地方，其它模块一律调用这里，杜绝散落的硬编码路径。

### `_is_frozen() -> bool`
判断是否运行在 PyInstaller 打包产物中：检查 `sys.frozen` 为真且存在 `sys._MEIPASS`。
打包态与开发态的资源根目录不同（见 `resource_dir`），靠它区分。

### `user_data_dir() -> Path`
返回平台相关的用户数据根目录并确保已创建：
- 优先读环境变量 `AI_TABLETOP_DATA_DIR`（测试/服务器部署覆盖用）。
- Windows → `%APPDATA%\ai-tabletop`；macOS → `~/Library/Application Support/ai-tabletop`；
  Linux → `$XDG_DATA_HOME/ai-tabletop` 或 `~/.local/share/ai-tabletop`。
- 末尾 `mkdir(parents=True, exist_ok=True)` 保证目录存在。
**边界**：环境变量优先级最高，便于单测把数据隔离到临时目录。

### `_sub(name) -> Path`
在用户数据根下创建并返回名为 `name` 的子目录（内部辅助，统一 `mkdir`）。

### `db_path() / redis_dump_dir() / uploads_dir() / vector_dir() / logs_dir()`
分别返回 SQLite 文件、Redis dump、上传文书、本地向量库、日志的可写路径，
全部经 `_sub`，因此都落在用户目录下。各自对应 Start.md：db_path→§4 local 关系存储，
redis_dump_dir→§4/§9.2 内嵌 Redis，uploads_dir→§5 rule_documents，vector_dir→§4/§8 向量库。

### `resource_dir() -> Path`
返回**只读资源**根目录（内置 `games/*/Rule.md` 等）：
- 打包态返回 `sys._MEIPASS`（资源被打进产物）。
- 开发态返回 `Path(__file__).resolve().parents[4]`，即从 `app/core/paths.py` 上溯 4 级到仓库根，
  这样 `compiler.builtin_rule_path` 能定位 `<repo>/games/<slug>/Rule.md`。

---

## `app/core/config.py` 🟢 — 存储分层配置（§4）

**为什么存在**：同一套业务代码要在 LAN（轻量内嵌）与服务器（MySQL+Redis）间切换。
通过环境变量 `STORAGE_PROFILE` 选择，业务代码只依赖 `Settings` 与存储接口。
刻意不引入 `pydantic-settings`，让核心在 `uv sync` 最小依赖下即可导入。

### `class StorageProfile(str, Enum)`
两个取值：`LOCAL`（LAN：SQLite + 内嵌 redis-server sidecar + 本地向量文件）、
`SERVER`（部署：MySQL + 托管 Redis + pgvector）。继承 `str` 便于直接与环境变量字符串比较。

### `class Settings`（`@dataclass(frozen=True)`）
不可变配置载体，字段：`profile / database_url / redis_url / vector_backend`。
属性 `is_local` → `profile is StorageProfile.LOCAL`，供分支判断。

### `_default_database_url(profile) -> str`
按 profile 给默认 DB URL：local→`sqlite:///<db_path()>`（落用户目录）；
server→读 `DATABASE_URL`，否则给一个 MySQL 占位串（部署时由真实环境变量覆盖）。

### `load_settings() -> Settings`
从环境变量装配 `Settings`：读取 `STORAGE_PROFILE`（默认 local）、`DATABASE_URL`、`REDIS_URL`
（默认本机 6379）、`VECTOR_BACKEND`（local 默认 faiss，server 默认 pgvector）。

### 模块级 `settings`
进程启动时调用一次 `load_settings()` 得到的单例，供全局 `from app.core.config import settings`。

---

## `app/core/logging.py` 🟢 — 日志

### `get_logger(name) -> logging.Logger`
首次调用时配置 `app` 根 logger：加一个控制台 `StreamHandler` 和一个落到 `logs_dir()/backend.log`
的 `RotatingFileHandler`（2MB×3 备份）；用模块级 `_CONFIGURED` 防重复加 handler。
若文件 handler 因权限失败（`OSError`）则静默退化为仅控制台。返回 `app.*` 命名的子 logger。

---

# 二、`app/storage/` — 存储抽象层（§4 / §6）

**整体设计**：业务代码只依赖 `base.py` 的四个 `Protocol` 接口；`factory.py` 按 profile 返回实现；
Phase 0/1 用 `memory.py` 的纯内存实现（最小依赖、确定性、可测），真实 Redis/SQLAlchemy/FAISS 在后续 Phase 接入。

## `app/storage/base.py` 🟢 — 四个接口（`typing.Protocol`，结构化鸭子类型）

### `Repository`（关系存储）
方法 `add(entity) / get(model, pk) / list(model, **filters) / commit()`。对应 SQLite/MySQL 的统一 CRUD 契约。

### `StateStore`（Redis 热状态，键约定见 §6）
方法 `get / set(key,value,ttl) / delete / hset / hgetall / expire`。语义对齐 Redis 的字符串与 hash + TTL。

### `EventBus`（Redis Pub/Sub，频道 `channel:session:{id}`）
方法 `publish(channel,message) / subscribe(channel,handler) / unsubscribe(channel)`。状态变更广播用。

### `VectorStore`（长期记忆向量检索，§8）
方法 `upsert(vid,vector,metadata) / query(vector,top_k)->[(vid,score,meta)] / delete(vid)`。

> 四者都用 `@runtime_checkable`，可用 `isinstance` 做运行时契约检查。

## `app/storage/memory.py` 🟢 — 纯内存实现

### `class InMemoryStateStore`
用三个 dict 模拟 Redis：`_kv`（字符串）、`_hash`（hash）、`_exp`（过期时间）。
- `_expired(key)`：惰性过期——读取时若 `time.monotonic()` 超过登记的过期时刻，删除并返回 True。
- `get/set/delete/hset/hgetall/expire`：贴近 Redis 语义；`set` 带可选 ttl，`expire` 单独设过期。
**设计理由**：TTL 用惰性检查（读时判断），单进程足够；语义贴近 Redis 以便将来无缝替换。

### `class InMemoryEventBus`
`_subs: dict[channel -> list[handler]]`。`publish` 同步遍历调用所有 handler；`subscribe` 追加；
`unsubscribe` 移除频道。**边界**：`publish` 遍历 `list(...)` 拷贝，允许 handler 内修改订阅而不出错。

### `class InMemoryRepository`
按 `type(entity)` 分桶存对象。`add` 入桶并返回实体；`get` 按 `.id` 线性查找；
`list` 支持等值过滤（`all(getattr==v)`）；`commit` 空操作（内存无事务）。

### `class InMemoryVectorStore`
`_vecs: dict[vid -> (vector, metadata)]`。
- 静态 `_cosine(a,b)`：余弦相似度，长度不等或零向量返回 0。
- `upsert/query/delete`：`query` 对所有向量算相似度，降序取 top-k 返回 `(vid, score, meta)`。

## `app/storage/factory.py` 🟢 — 后端工厂

四个 `@lru_cache(maxsize=1)` 单例函数：
- `get_state_store()` / `get_event_bus()`：local 返回内存实现；server 抛 `NotImplementedError`（待 Phase 3 接 Redis）。
- `get_repository()`：当前返回内存仓储（TODO 接 SQLAlchemy）。
- `get_vector_store()`：当前返回内存向量库（TODO 接 FAISS/pgvector）。
**设计理由**：`lru_cache` 让每种存储进程内单例，业务代码 `get_xxx()` 拿到的始终是同一实例。

## `app/storage/__init__.py`
重导出四接口与四工厂函数，方便 `from app.storage import StateStore, get_state_store`。

---

# 三、`app/models/` — SQLAlchemy 模型（§5）

> 需 `uv sync --extra storage`。引擎/CLI 不依赖本包，故核心在无 SQLAlchemy 时仍可运行。

## `app/models/base.py` 🟢
- `class Base(DeclarativeBase)`：SQLAlchemy 2.0 声明基类，所有表继承它，`Base.metadata` 汇总建表信息（供 Alembic）。
- `class TimestampMixin`：提供 `created_at`（`server_default=now()`）与 `updated_at`（`onupdate=now()`）两列，被业务表混入。

## `app/models/entities.py` 🟢 — 10 张核心表

> JSON 列统一用 SQLAlchemy 可移植 `JSON` 类型，SQLite/MySQL 两端都支持；SQLite↔MySQL 差异收敛进 Alembic 迁移（§4）。

| 类 | 表 | 关键列 | 对应 Start.md |
|---|---|---|---|
| `Game` | games | slug(唯一)、rule_md、definition(JSON)、source、version | §5 游戏定义快照 |
| `RuleDocument` | rule_documents | game_id(可空)、filename、storage_path、extract_status | §5 上传文书 |
| `GameSession` | game_sessions | game_id、host_user_id、mode、status、seed、snapshot_ref、result | §5 一局实例 |
| `User` | users | display_name、identity_hash(LAN 身份)、auth(server) | §5 人类玩家 |
| `SessionPlayer` | session_players | session_id、seat、actor_type、user_id/character_id、assigned_role | §5 参与者 |
| `CharacterCard` | character_cards | name、persona、traits(JSON)、owner_user_id | §5/§8 人物卡 |
| `CharacterBond` | character_bonds | from/to_character_id、affinity、tags(JSON) | §5/§8.1 羁绊 |
| `LongTermMemory` | long_term_memories | character_id、kind、content、embedding_ref、salience | §5/§8 长期记忆 |
| `HighlightMoment` | highlight_moments | session_id、title、summary、kind、replay_ref、shared | §5/§8.3 精彩瞬间 |
| `SessionEvent` | session_events | session_id、seq、phase、actor、action、payload(JSON)、visibility | §5 事件底账 |

**设计要点**：`SessionEvent` 是一切的底账——复盘、记忆固化、精彩瞬间都从它派生而非各自记录；
`visibility` 决定每条事件对谁可见（狼队私聊、查验结果只对本人）。

## `app/models/__init__.py`
重导出 `Base` 与全部 10 个模型类，使 `from app.models import Base` 即注册所有表的 metadata（Alembic 用）。
