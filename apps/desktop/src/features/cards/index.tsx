// cards feature — 人物卡 / 角色能力展示。见 Start.md §3 / §8（羁绊预留）。
import React from "react";
import { Panel, SectionHead, Chip, Shape, Label } from "../../components/Bauhaus";

interface RoleCard {
  name: string;
  zh: string;
  faction: "good" | "werewolf";
  count: string;
  abilities: string[];
  color: "red" | "blue" | "yellow";
  shape: "circle" | "square" | "triangle" | "half-circle";
}

// 狼人杀角色（对应 games/werewolf/Rule.md）
const ROLES: RoleCard[] = [
  { name: "Seer", zh: "预言家", faction: "good", count: "×1", abilities: ["investigate · 夜晚查阵营 · 私有"], color: "blue", shape: "circle" },
  { name: "Witch", zh: "女巫", faction: "good", count: "×1", abilities: ["protect · 解药×1", "eliminate · 毒药×1"], color: "blue", shape: "half-circle" },
  { name: "Werewolf", zh: "狼人", faction: "werewolf", count: "×2", abilities: ["eliminate · 群体决策击杀", "频道 werewolf_chat"], color: "red", shape: "triangle" },
  { name: "Villager", zh: "平民", faction: "good", count: "rest", abilities: ["无主动能力 · 靠推理与投票"], color: "yellow", shape: "square" },
];

export default function CardsView(): React.ReactElement {
  return (
    <>
      <SectionHead title="角色卡 · CARDS" dot="red" />

      <div className="bh-grid bh-grid--2">
        {ROLES.map((r) => {
          const wolf = r.faction === "werewolf";
          return (
            <Panel key={r.name} corner>
              {/* 头部色带 + 大几何图形 */}
              <div
                className={wolf ? "bg-red" : "bg-blue"}
                style={{ padding: 20, display: "flex", alignItems: "center", justifyContent: "space-between" }}
              >
                <div>
                  <span className="bh-mono-label fg-white">{r.name}</span>
                  <h2 className="fg-white" style={{ marginTop: 6 }}>{r.zh}</h2>
                </div>
                <Shape kind={r.shape} size={56} color="yellow" />
              </div>

              <div style={{ padding: 20, display: "flex", flexDirection: "column", gap: 14 }}>
                <div style={{ display: "flex", gap: 8 }}>
                  <Chip color={wolf ? "red" : "blue"}>{r.faction}</Chip>
                  <Chip color="white">{r.count}</Chip>
                </div>
                <div>
                  <Label>能力</Label>
                  <ul style={{ margin: "8px 0 0", paddingLeft: 0, listStyle: "none", display: "flex", flexDirection: "column", gap: 8 }}>
                    {r.abilities.map((a, i) => (
                      <li key={i} style={{ display: "flex", gap: 10, alignItems: "center" }}>
                        <Shape kind="square" size={12} color={r.color} />
                        <span>{a}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </Panel>
          );
        })}
      </div>

      {/* 羁绊预留区 */}
      <Panel flat style={{ borderStyle: "dashed" }}>
        <div style={{ padding: 20, display: "flex", alignItems: "center", gap: 16 }}>
          <Shape kind="circle" size={28} color="yellow" />
          <div>
            <Label>羁绊 · BONDS（Phase 2）</Label>
            <p style={{ margin: "4px 0 0" }}>跨局记忆将在此呈现角色间的好感与宿敌关系，影响 AI 行为偏置。</p>
          </div>
        </div>
      </Panel>
    </>
  );
}
