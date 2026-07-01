# desktop — Tauri + React 桌面端

见 Start.md §2 / §3。Vite + React + TypeScript 前端，采用**包豪斯（Bauhaus）视觉风格**：
三原色（红/蓝/黄）+ 黑 + 纸白、几何无衬线大写字体、粗黑描边、强网格、硬边无圆角。
当前用本地模拟数据驱动 UI（Phase 1），Phase 3 接入 `GameSocket` 后换成真实会话状态。

## 环境要求

- **Node.js ≥ 18**（建议 20/22）与 npm
- 仅跑网页前端只需 Node；跑 Tauri 桌面壳还需 **Rust 工具链**（`rustup`）与各平台的
  WebView 依赖（Windows 自带 WebView2；Linux 需 `libwebkit2gtk`；macOS 需 Xcode CLT）

## 启动

```bash
cd apps/desktop

# 1) 安装依赖（首次或拉取代码后）
npm install

# 2) 网页模式：浏览器打开 http://localhost:5173，改代码热更新
npm run dev

# 3) 生产构建：类型检查 + 打包到 dist/
npm run build
npm run preview        # 本地预览构建产物

# 4) 桌面模式：启动 Tauri 原生窗口（需 Rust 工具链）
npm run tauri dev
npm run tauri build    # 打包安装包
```

> 注意：`node_modules/` 与 `dist/` 已被 `.gitignore` 忽略。若从其他平台
> （如 Linux）拷来的 `node_modules` 报二进制错误，删除该目录后重新 `npm install` 即可。

## 目录结构

```
apps/desktop/
├── index.html              # Vite 入口 HTML
├── vite.config.ts          # Vite 配置（端口 5173 / 产物 dist）
├── tsconfig*.json          # TypeScript 配置
├── package.json
├── src/
│   ├── main.tsx            # React 挂载入口
│   ├── App.tsx             # 应用外壳：几何导航条 + 三色刊头 + 视图切换
│   ├── styles/bauhaus.css  # 包豪斯设计系统（设计令牌 + 组件样式）
│   ├── components/Bauhaus.tsx  # 共享几何组件：Shape/Panel/Button/Chip…
│   ├── store/index.ts      # 前端状态（zustand）+ 模拟数据
│   ├── net/client.ts       # WebSocket 客户端（Phase 3 占位）
│   └── features/
│       ├── lobby/          # 大厅：选游戏 / 建本地局
│       ├── rules/          # 规则摄取管线 + 能力原语库
│       ├── table/          # 牌桌：席位 + 事件流 + 行动区
│       └── cards/          # 人物卡 / 角色能力（羁绊预留）
└── src-tauri/              # Rust：窗口、sidecar 启动、LAN 发现（mDNS/UDP，占位）
```

## 设计系统速览（`src/styles/bauhaus.css`）

调色板与字体集中在 `:root` CSS 变量里，改主题只动这一处：

- 颜色：`--bh-red #e2231a` / `--bh-blue #1356a2` / `--bh-yellow #f7c200` / `--bh-black` / `--bh-paper`
- 字体：`--bh-font`（Futura → Century Gothic → Helvetica Neue 回退）
- 线条/网格：`--bh-rule`（粗黑线）、`--bh-gap`、`--bh-radius: 0`（无圆角）

`components/Bauhaus.tsx` 导出可复用的几何组件：`Shape`（圆/方/三角/半圆）、`Panel`、
`Button`、`Chip`、`SectionHead`、`Label`，四个视图均基于它们拼装。
