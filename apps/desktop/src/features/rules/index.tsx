// rules feature — 规则摄取管线可视化。见 Start.md §7。
import React from "react";
import { Panel, SectionHead, Shape, Label, Chip } from "../../components/Bauhaus";

// 规则管线五步（§7：上传 → 提取 → 结构化 → 审校 → 编译）
const PIPELINE = [
  { n: 1, title: "上传", desc: "Rule.md / PDF 文书", color: "red" as const, done: true },
  { n: 2, title: "提取", desc: "正文 + front-matter", color: "blue" as const, done: true },
  { n: 3, title: "结构化", desc: "角色 / 阶段 / 原语", color: "yellow" as const, done: true },
  { n: 4, title: "审校", desc: "人类比对镜像", color: "red" as const, done: false },
  { n: 5, title: "编译", desc: "GameDefinition", color: "blue" as const, done: false },
];

const PRIMITIVES = ["eliminate", "investigate", "protect", "vote", "nominate", "quest", "reveal", "speak", "pass"];

export default function RulesView(): React.ReactElement {
  return (
    <>
      <SectionHead title="规则管线 · RULES" dot="blue" />

      {/* 管线流程 */}
      <Panel>
        <div style={{ padding: 20 }}>
          <Label>摄取流程 · INGEST PIPELINE</Label>
          <div style={{ display: "flex", gap: 0, marginTop: 16, alignItems: "stretch", flexWrap: "wrap" }}>
            {PIPELINE.map((p, i) => (
              <React.Fragment key={p.n}>
                <div
                  style={{
                    flex: "1 1 140px", border: "4px solid var(--bh-black)",
                    background: p.done ? "var(--bh-white)" : "var(--bh-paper-2)",
                    padding: 16, display: "flex", flexDirection: "column", gap: 8,
                    opacity: p.done ? 1 : 0.7,
                  }}
                >
                  <span className="bh-num" style={{ background: `var(--bh-${p.color})`, color: p.color === "yellow" ? "var(--bh-black)" : "var(--bh-white)" }}>
                    {p.n}
                  </span>
                  <h3>{p.title}</h3>
                  <span className="bh-mono-label">{p.desc}</span>
                  <Chip color={p.done ? "blue" : "white"}>{p.done ? "就绪" : "Phase 3"}</Chip>
                </div>
                {i < PIPELINE.length - 1 && (
                  <div style={{ display: "grid", placeItems: "center", padding: "0 6px" }}>
                    <Shape kind="triangle" size={22} color="black" style={{ transform: "rotate(90deg)" }} />
                  </div>
                )}
              </React.Fragment>
            ))}
          </div>
        </div>
      </Panel>

      <div className="bh-grid bh-grid--2" style={{ alignItems: "start" }}>
        {/* 能力原语库 */}
        <Panel corner>
          <div className="bg-black" style={{ padding: "14px 20px" }}>
            <h3 className="fg-white">能力原语库 · PRIMITIVES</h3>
          </div>
          <div style={{ padding: 20, display: "flex", flexWrap: "wrap", gap: 10 }}>
            {PRIMITIVES.map((p, i) => (
              <Chip key={p} color={(["red", "blue", "yellow"] as const)[i % 3]}>{p}</Chip>
            ))}
          </div>
          <div style={{ padding: "0 20px 20px" }}>
            <p style={{ margin: 0 }}>
              每条规则能力必须映射到一个原语；未注册的原语在编译期被拒绝，杜绝任意代码执行。
            </p>
          </div>
        </Panel>

        {/* 安全编译 */}
        <Panel>
          <div className="bg-yellow" style={{ padding: "14px 20px" }}>
            <h3>受控编译 · SAFE COMPILE</h3>
          </div>
          <div style={{ padding: 20, display: "flex", flexDirection: "column", gap: 14 }}>
            {[
              ["谓词白名单", "胜负条件只允许受控变量与运算，非 eval"],
              ["阶段引用校验", "next / on_complete 必须指向已声明阶段"],
              ["角色配额校验", "count=rest 自动占满，人数边界检查"],
            ].map(([t, d], i) => (
              <div key={i} className="bh-row" style={{ border: "none", padding: 0 }}>
                <Shape kind={(["square", "circle", "triangle"] as const)[i]} size={32} color="blue" />
                <div>
                  <Label>{t}</Label>
                  <p style={{ margin: "4px 0 0" }}>{d}</p>
                </div>
              </div>
            ))}
          </div>
        </Panel>
      </div>
    </>
  );
}
