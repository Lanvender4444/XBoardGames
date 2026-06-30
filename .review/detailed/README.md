# 详细代码解释（逐文件 / 逐函数）

本目录对本次构建的**每个文件、每个函数/类**给出十分详细的解释：签名、用途、参数、返回值、
内部逻辑、边界情况与设计理由（对照 `docs/Start.md`）。

## 阅读顺序

| 文档 | 覆盖范围 |
|---|---|
| [01-foundation.md](01-foundation.md) | `app/core`（路径/配置/日志）、`app/storage`（抽象层+内存实现）、`app/models`（SQLAlchemy 表） |
| [02-rules.md](02-rules.md) | `app/rules`：能力原语库 `primitives`、规范解析 `schema`、受控编译 `compiler`、文书解析 `parser` |
| [03-engine.md](03-engine.md) | `app/engine`：数据类型 `types`、安全谓词 `predicates`、引擎核心 `engine`（逐方法详解） |
| [04-placeholders.md](04-placeholders.md) | `app/agents`、`app/memory`、`app/multiplayer`、`app/api` 的**原始占位形态**（历史快照；现已实现，见 07） |
| [05-cli-tests.md](05-cli-tests.md) | `app/cli/autoplay`（自动对局驱动）、`tests/`（用例逐个说明） |
| [06-frontend-config-games.md](06-frontend-config-games.md) | 前端/Tauri、`packages/protocol`、`games/*/Rule.md`、`pyproject.toml`、Alembic 迁移 |
| [07-phase2-5-implementation.md](07-phase2-5-implementation.md) | **Phase 2–5 实现详解 + 模块联动**：记忆系统、AI 决策子图、联机层、FastAPI、规则摄取管线；端到端数据流与接缝替换矩阵 |

## 术语速查

- **GameDefinition**：Rule.md 编译后的可执行定义（状态机 + 原语绑定）。引擎只认它。
- **原语（Primitive）**：一组有限、可组合、可测的能力单元（eliminate/vote/investigate…）。Rule.md 的每个能力必须映射到原语。
- **Seat（席位）**：一局中的一个位置，承载角色/阵营/存活状态；actor 是人还是 AI 引擎不关心。
- **Visibility（可见性）**：事件对谁可见——public（所有人）/ private（仅本人）/ faction（同阵营）。
- **Storage Profile**：`local`（LAN：SQLite+内嵌 Redis+本地向量）/ `server`（MySQL+托管 Redis+pgvector）。

## 标注约定

- 🟢 **已实现可运行**　🟡 **接口占位（NotImplementedError）**　⚙️ **配置/脚手架**

> 更新：文档 04 描述的占位层（agents/memory/multiplayer/api）**已全部实现**，详见
> [07-phase2-5-implementation.md](07-phase2-5-implementation.md)。当前 `uv run pytest` → 71 passed。
