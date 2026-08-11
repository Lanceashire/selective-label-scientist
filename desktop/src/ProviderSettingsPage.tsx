import { useEffect, useRef, useState } from "react";
import { CheckCircle2, KeyRound, LoaderCircle, PlugZap, ShieldCheck, Trash2 } from "lucide-react";
import { DesktopBridge, type ConnectionTestResult, type ProviderDefinition, type ProviderId, type ProviderProfile } from "./bridge";

const fallbackProviders: ProviderDefinition[] = [
  { id: "openai", label: "OpenAI", requires_base_url: false }, { id: "anthropic", label: "Anthropic", requires_base_url: false }, { id: "deepseek", label: "DeepSeek", requires_base_url: false }, { id: "google", label: "Google Gemini", requires_base_url: false }, { id: "openrouter", label: "OpenRouter", requires_base_url: false }, { id: "moonshot", label: "Moonshot", requires_base_url: false }, { id: "qwen", label: "Qwen", requires_base_url: false }, { id: "minimax", label: "MiniMax", requires_base_url: false }, { id: "custom_openai_compatible", label: "Custom OpenAI-Compatible", requires_base_url: true },
];

function errorMessage(error: unknown, fallback: string) {
  if (typeof error === "string") return error;
  if (error && typeof error === "object" && "message" in error && typeof error.message === "string") return error.message;
  return fallback;
}

export function ProviderSettingsPage() {
  const [definitions, setDefinitions] = useState<ProviderDefinition[]>(fallbackProviders);
  const [profiles, setProfiles] = useState<ProviderProfile[]>([]);
  const [selected, setSelected] = useState<ProviderId>("deepseek");
  const [modelId, setModelId] = useState("deepseek-chat");
  const [baseUrl, setBaseUrl] = useState("");
  const [notice, setNotice] = useState("API Key 不会写入 SQLite、报告、日志或浏览器存储。");
  const [connection, setConnection] = useState<ConnectionTestResult | null>(null);
  const [busy, setBusy] = useState(false);
  const keyInput = useRef<HTMLInputElement>(null);
  const active = definitions.find((provider) => provider.id === selected) ?? fallbackProviders[0];
  const existing = profiles.find((profile) => profile.provider === selected);

  const refresh = async () => {
    const state = await DesktopBridge.providerStatus();
    setDefinitions(state.providers);
    setProfiles(state.profiles);
  };

  useEffect(() => { void refresh().catch((error) => setNotice(errorMessage(error, "暂时无法读取本机 Provider 配置，可重新尝试。"))); }, []);

  const choose = (provider: ProviderId) => {
    setSelected(provider);
    const profile = profiles.find((item) => item.provider === provider);
    setModelId(profile?.model_id ?? (provider === "deepseek" ? "deepseek-chat" : ""));
    setBaseUrl(profile?.base_url ?? "");
    setConnection(null);
    if (keyInput.current) keyInput.current.value = "";
    setNotice(profile?.configured ? `已配置：${profile.masked_key ?? "Windows 凭据保管库"}` : "填写模型与 API Key 后安全保存。");
  };

  const save = async () => {
    setBusy(true);
    try {
      const apiKey = keyInput.current?.value ?? "";
      const result = await DesktopBridge.saveProvider({ provider: selected, model_id: modelId, base_url: baseUrl, api_key: apiKey, set_default: true });
      if (keyInput.current) keyInput.current.value = "";
      setConnection(null);
      setNotice(`已安全保存为默认模型：${result.masked_key}。完整 Key 从未写入普通文件。`);
      await refresh();
    } catch (error) {
      if (keyInput.current) keyInput.current.value = "";
      setNotice(errorMessage(error, "保存失败，请检查配置后重试。"));
    } finally { setBusy(false); }
  };

  const validate = async () => {
    setBusy(true);
    try { setNotice((await DesktopBridge.validateProvider(selected)).message); }
    catch (error) { setNotice(errorMessage(error, "配置检查失败。")); }
    finally { setBusy(false); }
  };

  const testConnection = async () => {
    if (!window.confirm("真实连接与 Tool Calling 测试将通过 Pi 向该模型发送一次最小请求，可能产生极少量 API Token 消耗。是否继续？")) return;
    setBusy(true);
    setConnection(null);
    try {
      const result = await DesktopBridge.testProviderConnection(selected);
      setConnection(result);
      setNotice(result.message);
      await refresh();
    } catch (error) { setNotice(errorMessage(error, "真实连接测试失败。")); }
    finally { setBusy(false); }
  };

  const remove = async () => {
    setBusy(true);
    try {
      await DesktopBridge.deleteProvider(selected);
      if (keyInput.current) keyInput.current.value = "";
      setConnection(null);
      setNotice("已从 Windows 凭据保管库清除该 Provider 的 API Key。普通文件中没有可删除的明文副本。");
      await refresh();
    } catch (error) { setNotice(errorMessage(error, "删除失败。")); }
    finally { setBusy(false); }
  };

  return <section className="provider-layout">
    <div className="provider-heading"><div><p className="kicker">MODEL & API</p><h2>模型与 API</h2><p>只展示 ECOMIC 当前 Pi Scientist Agent 已声明支持的 Provider。密钥由 Windows 凭据保管库保护。</p></div><div className="security-pill"><ShieldCheck size={18}/> Windows Credential Manager</div></div>
    <div className="provider-grid"><aside className="provider-list" aria-label="Provider 列表">{definitions.map((provider) => {
      const profile = profiles.find((item) => item.provider === provider.id);
      return <button key={provider.id} className={selected === provider.id ? "provider-item active" : "provider-item"} onClick={() => choose(provider.id)}><span>{provider.label}</span><small>{profile?.configured ? `已配置 ${profile.masked_key ?? ""}` : "未配置"}</small></button>;
    })}</aside>
      <section className="provider-form card"><div className="form-title"><div><h3>{active.label}</h3><p>{existing?.configured ? `当前密钥：${existing.masked_key}` : "尚未保存 API Key"}</p></div>{existing?.configured && <CheckCircle2 className="good" size={22}/>}</div>
        <label>Model ID<input aria-label="Model ID" value={modelId} onChange={(event) => setModelId(event.target.value)} placeholder="例如 deepseek-chat" autoComplete="off" /></label>
        <label>API Base URL {active.requires_base_url && <em>必填</em>}<input aria-label="API Base URL" value={baseUrl} onChange={(event) => setBaseUrl(event.target.value)} placeholder={active.requires_base_url ? "https://your-api.example/v1" : "可留空；使用 Pi Provider 默认地址"} autoComplete="off" /></label>
        <label>API Key <span className="secret-note">仅本次输入</span><div className="secret-input"><KeyRound size={17}/><input aria-label="API Key" ref={keyInput} type="password" placeholder={existing?.configured ? "留空可保留当前密钥" : "粘贴 API Key"} autoComplete="new-password" spellCheck={false} onPaste={(event) => { const pasted = event.clipboardData.getData("text"); if (pasted) { event.preventDefault(); if (keyInput.current) keyInput.current.value = pasted; } }} /></div></label>
        <p className="form-notice" role="status">{notice}</p>
        {connection && <p className={connection.status === "SUCCESS" ? "connection-result success" : "connection-result error"}>{connection.status === "SUCCESS" ? "✓" : "!"} {connection.message}</p>}
        <div className="form-actions"><button className="primary" disabled={busy} onClick={() => void save()}>{busy ? <LoaderCircle className="spin" size={17}/> : <ShieldCheck size={17}/>} 安全保存</button><button disabled={busy} onClick={() => void validate()}>检查配置</button><button className="connection-button" disabled={busy || !existing?.configured} onClick={() => void testConnection()}><PlugZap size={16}/> 真实连接与 Tool Calling 测试</button><button className="danger" disabled={busy || !existing?.configured} onClick={() => void remove()}><Trash2 size={16}/> 清除凭据</button></div>
        <p className="connection-hint">“检查配置”不会发送网络请求或消耗 Token；真实测试会明确询问，并通过 Pi Provider 发送最小请求。</p>
      </section></div>
  </section>;
}
