# AI Tabletop Platform（AI 桌游平台）

可扩展的 AI 桌游引擎：内置**狼人杀**与**阿瓦隆**，支持"喂规则文书 → 生成可执行游戏"，
拥有带**羁绊**与**长短期记忆**的 AI 人物卡，并提供**局域网 / 服务器**双模式联机。

> 单一事实来源（SSOT）见 [`docs/Start.md`](docs/Start.md)。本仓库按其架构搭建。

## 仓库结构（Monorepo）

```
ai-tabletop/
├── apps/
│   ├── desktop/      # Tauri + React 桌面外壳（占位骨架）
│   └── backend/      # Python + FastAPI 后端（引擎可运行）
├── packages/
│   └── protocol/     # 前后端共享协议 schema
├── games/            # 内置游戏官方 Rule.md（werewolf / avalon）
└── docs/Start.md     # 设计文档（SSOT）
```

## 当前实现状态（对照路线图）

| Phase | 内容 | 状态 |
|---|---|---|
| 0 | 地基：目录、存储抽象层、协议、SQLAlchemy 模型、配置/路径 | ✅ 已搭建 |
| 1 | 引擎 + 内置狼人杀（无 AI、无联机） | ✅ 可运行 + 有测试 |
| 2 | AI 玩家 + 记忆 | 🟡 接口占位 |
| 3 | 联机（WebSocket + Redis Pub/Sub） | 🟡 接口占位 |
| 4 | 规则摄取管线（文书 → Rule.md → 编译） | 🟡 编译器可用，解析占位 |
| 5 | 精彩瞬间 + 打磨 | 🟡 接口占位 |

## 快速开始（后端）

后端使用 [uv](https://docs.astral.sh/uv/) 管理 Python 依赖与虚拟环境。

```bash
cd apps/backend
uv sync                      # 安装依赖、创建虚拟环境
uv run pytest                # 运行引擎单元测试
uv run python -m app.cli.autoplay --game werewolf --players 8 --seed 42
```

`autoplay` 会用"随机合法行动"驱动一整局狼人杀，逐回合打印事件，
直到满足胜负条件——用于验证引擎抽象（Phase 1 里程碑）。

## 前端 / 桌面外壳

`apps/desktop` 为 Tauri + React 骨架（占位）。需要 Node 与 Rust 工具链；当前仅含目录、
协议类型与组件占位，待 Phase 2+ 填充。
