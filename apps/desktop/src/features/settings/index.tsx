// settings feature — LLM provider 配置（支持主流开源/闭源 API）+ 后端地址。
import React, { useEffect } from "react";
import { useApp } from "../../store";
import { Panel, Button, SectionHead, Label, Chip } from "../../components/Bauhaus";

const inputStyle: React.CSSProperties = {
  width: "100%", padding: "10px 12px", border: "3px solid var(--bh-black)",
  fontFamily: "var(--bh-font)", fontSize: "0.95rem", background: "var(--bh-white)",
};

export default function SettingsView(): React.ReactElement {
  const { providers, llm, backend, loadProviders, setLLMField, saveLLM, setBackend, loading, error, testInfo, testBackend, testLLM } = useApp();
  useEffect(() => {
    loadProviders();
  }, [loadProviders]);

  const current = providers.find((p) => p.id === llm.provider);

  const onProvider = (id: string) => {
    setLLMField("provider", id);
    const p = providers.find((x) => x.id === id);
    if (p) {
      setLLMField("base_url", p.base_url);
      setLLMField("model", p.default_model);
    }
  };

  return (
    <>
      <SectionHead title="设置 · LLM" dot="blue" />
      <div className="bh-grid bh-grid--2" style={{ alignItems: "start" }}>
        <Panel corner>
          <div className="bg-black" style={{ padding: "14px 20px" }}>
            <h3 className="fg-white">模型提供方</h3>
          </div>
          <div style={{ padding: 20, display: "flex", flexDirection: "column", gap: 16 }}>
            <div>
              <Label>提供方 Provider</Label>
              <select
                value={llm.provider}
                onChange={(e) => onProvider(e.target.value)}
                style={{ ...inputStyle, marginTop: 8 }}
              >
                {providers.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <Label>Base URL（OpenAI 兼容端点）</Label>
              <input
                style={{ ...inputStyle, marginTop: 8 }}
                value={llm.base_url || ""}
                placeholder="https://api.deepseek.com/v1"
                onChange={(e) => setLLMField("base_url", e.target.value)}
              />
            </div>
            <div>
              <Label>模型 Model</Label>
              <input
                style={{ ...inputStyle, marginTop: 8 }}
                value={llm.model || ""}
                placeholder={current?.default_model || "gpt-4o-mini"}
                onChange={(e) => setLLMField("model", e.target.value)}
              />
            </div>
            <div>
              <Label>API Key {current && !current.needs_key ? "（本地/离线可留空）" : ""}</Label>
              <input
                style={{ ...inputStyle, marginTop: 8 }}
                type="password"
                value={llm.api_key || ""}
                placeholder={llm.has_key ? "已设置（留空则不变）" : "sk-..."}
                onChange={(e) => setLLMField("api_key", e.target.value)}
              />
            </div>
            <div>
              <Label>温度 Temperature：{llm.temperature ?? 0.7}</Label>
              <input
                type="range" min={0} max={1.5} step={0.1}
                value={llm.temperature ?? 0.7}
                onChange={(e) => setLLMField("temperature", Number(e.target.value))}
                style={{ width: "100%", marginTop: 8 }}
              />
            </div>
            <Button variant="red" onClick={saveLLM} disabled={loading}>
              {loading ? "保存中…" : "保存配置"}
            </Button>
            {llm.has_key && <Chip color="blue">Key 已配置</Chip>}
            {error && <p style={{ color: "var(--bh-red)", margin: 0, fontWeight: 700 }}>错误：{error}</p>}
          </div>
        </Panel>

        <Panel>
          <div className="bg-yellow" style={{ padding: "14px 20px" }}>
            <h3>后端 & 说明</h3>
          </div>
          <div style={{ padding: 20, display: "flex", flexDirection: "column", gap: 14 }}>
            <div>
              <Label>后端地址 Backend URL</Label>
              <input
                style={{ ...inputStyle, marginTop: 8 }}
                value={backend}
                onChange={(e) => setBackend(e.target.value)}
              />
            </div>
            <p style={{ margin: 0 }}>
              支持任何 OpenAI 兼容服务：选预设会自动填好 Base URL 与默认模型；也可选“自定义”手填。
              本地模型用 Ollama / LM Studio（无需 Key）。Anthropic 走原生适配。
            </p>
            <p style={{ margin: 0 }}>
              <span className="bh-mono-label">提示</span>：先在此保存模型配置，再去大厅创建对局，AI 即用该模型。
            </p>
            <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
              <Button variant="ghost" onClick={testBackend}>测试后端连接</Button>
              <Button variant="blue" onClick={testLLM}>测试模型连接</Button>
            </div>
            {testInfo && (
              <div style={{ border: "3px solid var(--bh-black)", padding: 12, background: "var(--bh-paper-2)", fontSize: "0.85rem" }}>
                {testInfo}
              </div>
            )}
          </div>
        </Panel>
      </div>
    </>
  );
}
