# Alembic 迁移

首次生成（需 `uv sync --extra storage`）：

```bash
uv run alembic revision --autogenerate -m "init schema"
uv run alembic upgrade head
```

LAN 首启时由 Tauri 核心触发 `alembic upgrade head`，在用户可写目录初始化 SQLite（Start.md §13）。
