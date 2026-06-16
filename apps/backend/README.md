# backend — Python + FastAPI 后端

见 Start.md §3 / §11。使用 [uv](https://docs.astral.sh/uv/) 管理依赖与虚拟环境。

## 安装与运行

```bash
uv sync                                  # 仅核心依赖（引擎 + 规则编译）
uv sync --extra dev --extra storage      # 含测试与 SQLAlchemy/Alembic
uv run pytest                            # 引擎契约单元测试
uv run python -m app.cli.autoplay --game werewolf --players 8 --seed 42
```

## 模块边界（Start.md §3）

- `app/core`        — 配置、路径解析（用户可写目录）、日志、DI
- `app/storage`     — 存储抽象层（Repository / StateStore / EventBus / VectorStore），profile: local/server
- `app/models`      — SQLAlchemy 模型（§5）
- `app/rules`       — 规则摄取管线：parser → schema → compiler → primitives（§7）
- `app/engine`      — 游戏引擎：状态机、结算、胜负判定（§11，纯逻辑可单测）
- `app/agents`      — LangGraph 决策子图 + AI 玩家（§10，占位）
- `app/memory`      — STM / LTM / 羁绊 / 精彩瞬间（§8，占位）
- `app/multiplayer` — 会话、Pub/Sub、连接生命周期（§9，占位）
- `app/api`         — FastAPI 路由 + WebSocket 端点（§12，占位）
- `app/cli`         — 命令行自动对局（引擎验证工具）

## 设计原则

引擎不区分行动来源（人类 WebSocket / AI LangGraph 都变成 `Action` 喂给 `apply`），
因此 `app/engine` 不 import 网络与 LLM 模块，可独立单测。
