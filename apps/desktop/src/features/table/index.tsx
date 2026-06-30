// table feature — 真实可玩牌桌：席位 + 事件流 + 你的行动（接后端）。
import React, { useState } from "react";
import { useApp } from "../../store";
import type { SeatVM } from "../../api";
import { Panel, Button, SectionHead, Chip, Shape, Label } from "../../components/Bauhaus";

const VIS = { public: "white", private: "red", faction: "blue" } as const;

function fmtEvent(e: { action: string; actor: number | null; payload: Record<string, unknown> }): string {
  const p = e.payload as Record<string, any>;
  const who = e.actor !== null ? `#${e.actor}` : "系统";
  switch (e.action) {
    case "speak":
      return p.text ? `${who} 发言：${p.text}` : `${who} 发言`;
    case "vote_submitted":
      return `${who} 投票 → #${(p.targets || [])[0]}`;
    case "investigate_result":
      return `${who} 查验 #${p.target} → ${p.value}`;
    case "death":
      return `#${p.seat} 出局（${p.cause === "vote" ? "投票" : "夜晚"}）`;
    case "vote_result":
      return `计票：${JSON.stringify(p.tally)}`;
    case "phase_enter":
      return `进入阶段 ${p.phase}`;
    case "game_start":
      return `开局（${p.players} 人）`;
    case "game_over":
      return `对局结束 · 胜者 ${p.faction}`;
    case "eliminate_submitted":
      return `${who} 出手（秘密）`;
    case "protect_submitted":
      return `${who} 使用解药（秘密）`;
    case "pass":
      return `${who} 跳过`;
    default:
      return `${who} ${e.action}`;
  }
}

function Seat({ s, me }: { s: SeatVM; me: number }): React.ReactElement {
  const wolf = s.faction === "werewolf" || s.faction === "evil";
  return (
    <div
      style={{
        border: "4px solid var(--bh-black)",
        background: s.alive ? "var(--bh-white)" : "var(--bh-paper-2)",
        padding: 12, display: "flex", flexDirection: "column", gap: 8,
        opacity: s.alive ? 1 : 0.5,
        boxShadow: s.seat === me ? "5px 5px 0 var(--bh-yellow)" : "none",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <span className="bh-num" style={{ background: s.role && wolf ? "var(--bh-red)" : "var(--bh-blue)", color: "var(--bh-white)" }}>
          {s.seat}
        </span>
        {!s.alive && <Shape kind="square" size={16} color="black" />}
      </div>
      <h3 style={{ fontSize: "0.9rem" }}>{s.seat === me ? "你" : s.name}</h3>
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
        <Chip color={s.actor_type === "human" ? "yellow" : "white"}>{s.actor_type === "human" ? "人类" : "AI"}</Chip>
        {s.role && <Chip color="black">{s.role}</Chip>}
      </div>
    </div>
  );
}

function ActionBar({
  actions,
  loading,
  onAct,
}: {
  actions: { type: string; targets: number[]; label: string }[];
  loading: boolean;
  onAct: (type: string, targets: number[], text?: string) => void;
}): React.ReactElement {
  const [text, setText] = useState("");
  const speak = actions.find((a) => a.type === "speak");
  const others = actions.filter((a) => a.type !== "speak");
  return (
    <>
      {speak && (
        <div style={{ display: "flex", gap: 8, alignItems: "center", flex: "1 1 320px" }}>
          <input
            value={text}
            placeholder="轮到你发言：说点什么带带节奏…（可留空跳过）"
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") { onAct("speak", [], text); setText(""); } }}
            style={{ flex: 1, padding: "10px 12px", border: "3px solid var(--bh-black)", fontFamily: "var(--bh-font)", fontSize: "0.95rem" }}
          />
          <Button variant="blue" disabled={loading} onClick={() => { onAct("speak", [], text); setText(""); }}>发言</Button>
        </div>
      )}
      {others.map((a, i) => (
        <Button
          key={i}
          variant={a.type === "vote" ? "red" : a.type === "investigate" ? "blue" : "ghost"}
          onClick={() => onAct(a.type, a.targets)}
          disabled={loading}
        >
          {a.label}
        </Button>
      ))}
    </>
  );
}

export default function TableView(): React.ReactElement {
  const { game, submit, refresh, leave, loading, error } = useApp();

  if (!game) {
    return (
      <>
        <SectionHead title="牌桌 · TABLE" dot="yellow" />
        <Panel>
          <div style={{ padding: 40, textAlign: "center", display: "flex", flexDirection: "column", gap: 16, alignItems: "center" }}>
            <div style={{ display: "flex" }}>
              <Shape kind="circle" size={40} color="red" style={{ marginRight: -10 }} />
              <Shape kind="triangle" size={40} color="yellow" style={{ marginRight: -10 }} />
              <Shape kind="square" size={40} color="blue" />
            </div>
            <h2>尚未开局</h2>
            <p style={{ margin: 0 }}>去大厅创建一局狼人杀。</p>
          </div>
        </Panel>
      </>
    );
  }

  const alive = game.seats.filter((s) => s.alive).length;

  return (
    <>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <SectionHead title="牌桌 · TABLE" dot="yellow" />
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <Chip color="blue">回合 {game.round}</Chip>
          <Chip color="red">{game.phase}</Chip>
          <Chip color="white">存活 {alive}/{game.seats.length}</Chip>
          <Chip color="black">你是 {game.your_role}</Chip>
          <Button variant="ghost" onClick={refresh} disabled={loading}>刷新</Button>
          <Button variant="ghost" onClick={leave}>离开</Button>
        </div>
      </div>

      {game.finished && (
        <Panel>
          <div className={game.winner === "werewolf" ? "bg-red" : "bg-blue"} style={{ padding: 20, display: "flex", alignItems: "center", gap: 16 }}>
            <Shape kind="circle" size={32} color="yellow" />
            <h2 className="fg-white">对局结束 · 胜者：{game.winner}</h2>
          </div>
        </Panel>
      )}

      <div className="bh-grid" style={{ gridTemplateColumns: "1.6fr 1fr", alignItems: "start" }}>
        <Panel>
          <div style={{ padding: 20 }}>
            <Label>席位 · SEATS</Label>
            <div className="bh-grid bh-grid--4" style={{ marginTop: 14, gap: 14 }}>
              {game.seats.map((s) => <Seat key={s.seat} s={s} me={game.your_seat} />)}
            </div>
          </div>
        </Panel>

        <Panel corner>
          <div className="bg-black" style={{ padding: "14px 20px" }}>
            <h3 className="fg-white">事件流 · EVENTS</h3>
          </div>
          <div style={{ maxHeight: 380, overflow: "auto" }}>
            {game.log.map((e) => (
              <div key={e.seq} className="bh-row" style={{ alignItems: "flex-start" }}>
                <span className="bh-mono-label" style={{ width: 40, flex: "0 0 40px", paddingTop: 2 }}>R{e.round}</span>
                <span style={{ flex: 1, fontSize: "0.85rem" }}>{fmtEvent(e)}</span>
                <Chip color={VIS[e.visibility as keyof typeof VIS] || "white"}>{e.visibility[0].toUpperCase()}</Chip>
              </div>
            ))}
          </div>
        </Panel>
      </div>

      {/* 你的行动 */}
      <Panel>
        <div className="bg-yellow" style={{ padding: "12px 20px" }}>
          <h3>{game.your_turn ? "轮到你了 · 选择行动" : game.finished ? "对局已结束" : "等待 AI 行动…"}</h3>
        </div>
        <div style={{ padding: 20, display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
          {game.your_turn ? (
            <ActionBar
              actions={game.your_actions}
              loading={loading}
              onAct={(t, tg, txt) => submit(t, tg, txt)}
            />
          ) : (
            <span className="bh-mono-label">
              {game.finished ? "—" : `等待席位 ${game.awaiting.join(", ")} 行动`}
            </span>
          )}
          {error && <p style={{ color: "var(--bh-red)", margin: 0, fontWeight: 700 }}>错误：{error}</p>}
        </div>
      </Panel>
    </>
  );
}
