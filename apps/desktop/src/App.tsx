// 应用外壳：左侧几何导航条 + 顶部三色刊头 + 主视图区。
import React from "react";
import { useApp, type ViewKey } from "./store";
import { Shape } from "./components/Bauhaus";
import LobbyView from "./features/lobby";
import TableView from "./features/table";
import CardsView from "./features/cards";
import SettingsView from "./features/settings";

const NAV: { key: ViewKey; label: string; shape: "circle" | "square" | "triangle" | "half-circle"; color: "red" | "blue" | "yellow" }[] = [
  { key: "lobby", label: "大厅", shape: "circle", color: "red" },
  { key: "table", label: "牌桌", shape: "triangle", color: "yellow" },
  { key: "cards", label: "角色", shape: "half-circle", color: "red" },
  { key: "settings", label: "设置", shape: "square", color: "blue" },
];

function Masthead(): React.ReactElement {
  const { game, llm } = useApp();
  return (
    <header className="bh-masthead">
      <div className="bh-masthead__bars">
        <div className="bh-masthead__bar bg-red" />
        <div className="bh-masthead__bar bg-blue" />
        <div className="bh-masthead__bar bg-yellow" />
      </div>
      <div className="bh-masthead__title">
        <span className="bh-mono-label">AI TABLETOP · 狼人杀</span>
        <h1>WEREWOLF</h1>
      </div>
      <div className="bh-masthead__badge">
        <span className="bh-mono-label fg-white">{game ? `R${game.round} · ${game.phase}` : "未开局"}</span>
        <span className="bh-mono-label fg-white">LLM: {llm.provider || "offline"}</span>
      </div>
    </header>
  );
}

function Rail(): React.ReactElement {
  const { view, setView } = useApp();
  return (
    <nav className="bh-rail">
      <div className="bh-rail__mark">
        <Shape kind="circle" size={20} color="red" style={{ marginRight: -8, zIndex: 2 }} />
        <Shape kind="square" size={20} color="yellow" style={{ marginLeft: -8 }} />
      </div>
      {NAV.map((n) => (
        <button key={n.key} className="bh-nav-btn" data-active={view === n.key} onClick={() => setView(n.key)} title={n.label}>
          <Shape kind={n.shape} size={28} color={n.color} />
          <span className="bh-nav-btn__label">{n.label}</span>
        </button>
      ))}
    </nav>
  );
}

const VIEWS: Record<ViewKey, () => React.ReactElement> = {
  lobby: LobbyView,
  table: TableView,
  cards: CardsView,
  settings: SettingsView,
};

export default function App(): React.ReactElement {
  const view = useApp((s) => s.view);
  const Current = VIEWS[view];
  return (
    <div className="bh-app">
      <Rail />
      <main className="bh-main">
        <Masthead />
        <Current />
      </main>
    </div>
  );
}
