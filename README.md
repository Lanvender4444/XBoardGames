# AI Tabletop Platform（AI 桌游平台）

可扩展的 AI 桌游引擎：内置**狼人杀**与**阿瓦隆**，支持"喂规则文书 → 生成可执行游戏"，
拥有带**羁绊**与**长短期记忆**的 AI 人物卡，并提供**局域网 / 服务器**双模式联机。

> 单一事实来源（SSOT）见 [`docs/Start.md`](docs/Start.md)。本仓库按其架构搭建。

## 仓库结构（Monorepo）

```
ai-tabletop/
├── apps/
│   ├── desktop/      # Tauri + React 桌面端（可运行，包豪斯风格）
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
| 2 | AI 玩家（**LangGraph 决策子图 + langchain LLM 决策链**驱动）+ 记忆（STM/LTM/羁绊/精彩瞬间/固化） | ✅ 已实现 + 测试 |
| 3 | 联机（SessionManager 广播 + 房间发现）+ FastAPI/WebSocket | ✅ 已实现 + 测试 |
| 4 | 规则摄取管线（文书 → 结构化 → Rule.md → 编译） | ✅ 已实现 + 测试 |
| 5 | 精彩瞬间 + 记忆衰减 + 打磨 | ✅ 已实现 + 测试 |

> 平台核心是"AI 操控 AI 角色"：AI 角色的每个行动都由 **langchain LLM 决策链**（跑在 **LangGraph 决策子图**里）
> 产生，故 `langchain-core` 与 `langgraph` 是**核心依赖**（`uv sync` 默认安装）。默认用内置**离线 ChatModel**，
> 无 API key 也能整局运行、可单测（`uv run pytest` → 87 passed）；设 `XBOARD_LLM_PROVIDER=openai` + `uv sync --extra ai`
> 即换真实 LLM，决策链其余部分不变。Redis / 真实向量库 / OCR 同样放在可注入接口之后。
> 实现见 [`.review/llm-langchain决策实现报告.md`](.review/llm-langchain决策实现报告.md) 与
> [`.review/detailed/07-phase2-5-implementation.md`](.review/detailed/07-phase2-5-implementation.md)。
> 注：API 层依赖 `uv sync --extra api`（fastapi/uvicorn）。

## 在浏览器里玩狼人杀（人机对局 + 前端配置大模型）

最快路线：开两个终端，一个跑后端，一个跑前端，然后在网页里玩。

```bash
# 终端 A —— 后端（提供对局 API + LLM 配置）
cd apps/backend
uv sync --extra api --extra ai          # api=FastAPI/WS；ai=真实大模型(OpenAI兼容/Anthropic)
uv run uvicorn "app.api.app:create_app" --factory --host 0.0.0.0 --port 8000

# 终端 B —— 前端
cd apps/desktop
npm install && npm run dev              # 打开 http://localhost:5173
```

在网页里：

1. **设置**页配置 AI 大脑：选 Provider（OpenAI / DeepSeek / Kimi / 智谱GLM / 通义 / OpenRouter / Groq /
   Together / Mistral / 本地 Ollama·LM Studio·vLLM / Anthropic / 自定义），填 Base URL（预设会自动填）、模型、API Key，
   保存。**不配也能玩**——默认内置离线模型，无需 Key。
2. **大厅**选人数（你=席位#0，其余 AI）→「开始对局」。
3. **牌桌**轮到你时点行动按钮（查验/投票/发言…），AI 由 LangGraph + LLM 决策链自动行动。

> “支持所有主流模型”靠 **OpenAI 兼容协议**（base_url + key + model）实现，覆盖绝大多数开/闭源厂商与本地推理服务；
> Anthropic 走原生适配。后端地址也可在设置页改（默认 `http://localhost:8000`）。
> 实现说明见 [`.review/前端可玩与多模型配置报告.md`](.review/前端可玩与多模型配置报告.md)。

---

## 启动项目（分模块）

本仓库分**后端**（Python 引擎，可运行）与**前端**（Tauri + React 桌面端，包豪斯风格 UI）两块，
二者可各自独立启动。本节为完整启动路径，照做即可在本地跑通。

### 一、安装工具链（首次）

| 用途 | 工具 | 安装方式 |
|---|---|---|
| 后端依赖/虚拟环境 | **uv** | macOS/Linux：`curl -LsSf https://astral.sh/uv/install.sh \| sh`；Windows：`powershell -c "irm https://astral.sh/uv/install.ps1 \| iex"` |
| 前端运行 | **Node.js ≥ 18**（建议 20/22）+ npm | 见 [nodejs.org](https://nodejs.org/) 或用 nvm 安装 |
| Tauri 桌面壳（可选） | **Rust 工具链** + 平台 WebView | `rustup`（[rustup.rs](https://rustup.rs/)）；Windows 自带 WebView2，Linux 需 `libwebkit2gtk`，macOS 需 Xcode CLT |

> 只想看引擎跑对局 → 装 uv 即可。只想看前端界面 → 装 Node 即可。要桌面原生窗口 → 再加 Rust。

### 二、后端：引擎 + CLI 自动对局

```bash
cd apps/backend
uv sync                      # 安装依赖、创建虚拟环境（仅核心依赖）
uv sync --extra dev --extra storage   # 含测试 + SQLAlchemy/Alembic（跑 pytest 需要）
uv run pytest                # 运行引擎单元测试（34 用例）
uv run python -m app.cli.autoplay --game werewolf --players 8 --seed 42
```

`autoplay` 会用"随机合法行动"驱动一整局狼人杀，逐回合打印事件，直到分出胜负——
用于验证引擎抽象（Phase 1 里程碑）。常用参数：`--game werewolf|avalon`、`--players N`、
`--seed N`、`--quiet`（只打印结果）。

### 三、前端：桌面端 UI（包豪斯风格）

```bash
cd apps/desktop
npm install                  # 安装依赖（首次或拉取代码后）
npm run dev                  # 网页模式：浏览器打开 http://localhost:5173，热更新
npm run build                # 生产构建：类型检查 + 打包到 dist/
npm run preview              # 本地预览构建产物
npm run tauri dev            # 桌面模式：Tauri 原生窗口（需 Rust 工具链）
npm run tauri build          # 打包安装包（需 Rust 工具链）
```

当前前端用本地模拟数据驱动四个视图（大厅 / 规则 / 牌桌 / 角色卡），展示完整的包豪斯界面；
Phase 3 接入 WebSocket 后切换为真实会话状态。设计系统与目录细节见
[`apps/desktop/README.md`](apps/desktop/README.md)。

### 四、最短跑通路径（两条命令各开一个终端）

```bash
# 终端 A —— 后端验证引擎
cd apps/backend && uv sync && uv run python -m app.cli.autoplay --game werewolf

# 终端 B —— 前端看界面
cd apps/desktop && npm install && npm run dev   # 打开 http://localhost:5173
```

### 常见问题

- **前端 `node_modules` 报二进制/平台错误**：多为跨平台拷贝（如 Linux→Windows）导致。
  删除 `apps/desktop/node_modules` 后重新 `npm install` 即可（该目录已被 `.gitignore` 忽略）。
- **`uv run pytest` 找不到 pytest**：先执行 `uv sync --extra dev` 安装开发依赖。
- **`npm run tauri dev` 报错**：确认已装 Rust 工具链与平台 WebView 依赖（见上表）。
