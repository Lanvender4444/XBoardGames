// lobby feature — 选人数、建局开玩。
import React, { useEffect } from "react";
import { useApp } from "../../store";
import { Panel, Button, SectionHead, Shape, Label, Chip } from "../../components/Bauhaus";

export default function LobbyView(): React.ReactElement {
  const { players, setPlayers, createGame, loading, error, llm, loadProviders, setView } = useApp();
  useEffect(() => {
    loadProviders();
  }, [loadProviders]);

  return (
    <>
      <SectionHead title="大厅 · LOBBY" dot="red" />
      <div className="bh-grid bh-grid--2" style={{ alignItems: "start" }}>
        <Panel corner>
          <div className="bg-red" style={{ padding: "14px 20px", display: "flex", alignItems: "center", gap: 12 }}>
            <Shape kind="circle" size={18} color="yellow" />
            <h3 className="fg-white">狼人杀 · 人机对局</h3>
          </div>
          <div style={{ padding: 20, display: "flex", flexDirection: "column", gap: 18 }}>
            <div>
              <Label>玩家人数（你 + AI）</Label>
              <div style={{ display: "flex", gap: 10, marginTop: 10, alignItems: "center" }}>
                <Button variant="ghost" onClick={() => setPlayers(players - 1)}>−</Button>
                <span style={{ fontSize: "2rem", fontWeight: 800, minWidth: 48, textAlign: "center" }}>{players}</span>
                <Button variant="ghost" onClick={() => setPlayers(players + 1)}>＋</Button>
                <span className="bh-mono-label" style={{ marginLeft: 8 }}>6–12 人</span>
              </div>
            </div>
            <div className="bh-row" style={{ border: "none", padding: 0 }}>
              <Shape kind="square" size={36} color="blue" />
              <div>
                <Label>你的座位</Label>
                <p style={{ margin: "4px 0 0" }}>#0（人类），其余为 AI</p>
              </div>
            </div>
            <Button variant="red" onClick={createGame} disabled={loading}>
              {loading ? "创建中…" : "▸ 开始对局"}
            </Button>
            {error && <p style={{ color: "var(--bh-red)", margin: 0, fontWeight: 700 }}>错误：{error}</p>}
          </div>
        </Panel>

        <Panel>
          <div className="bg-blue" style={{ padding: "14px 20px" }}>
            <h3 className="fg-white">AI 大脑 · LLM</h3>
          </div>
          <div style={{ padding: 20, display: "flex", flexDirection: "column", gap: 14 }}>
            <div className="bh-row" style={{ border: "none", padding: 0 }}>
              <Shape kind="triangle" size={36} color="yellow" />
              <div>
                <Label>当前模型提供方</Label>
                <p style={{ margin: "4px 0 0" }}>
                  <Chip color="black">{llm.provider || "offline"}</Chip>{" "}
                  {llm.model ? <Chip color="white">{llm.model}</Chip> : null}
                </p>
              </div>
            </div>
            <p style={{ margin: 0 }}>
              AI 角色由 LangGraph 决策子图 + LLM 决策链驱动。默认离线内置模型（无需 Key）；
              要用真实大模型，去“设置”里配置（支持 OpenAI / DeepSeek / Kimi / GLM / 通义 / OpenRouter / Groq / Ollama 等）。
            </p>
            <Button variant="blue" onClick={() => setView("settings")}>⚙ 打开 LLM 设置</Button>
          </div>
        </Panel>
      </div>
    </>
  );
}
