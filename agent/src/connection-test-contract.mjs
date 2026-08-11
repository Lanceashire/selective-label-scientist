/** User-safe, stable result contract shared by the Pi probe and desktop UI. */
export const CONNECTION_FAILURES = Object.freeze({
  unauthorized: "API Key 无效、已失效，或当前账户没有该模型权限。",
  not_found: "模型 ID 或 API Base URL 不存在，请检查配置。",
  rate_limited: "请求频率或账户额度受限，请稍后重试。",
  timeout: "网络连接超时，请检查网络、代理或 Provider 状态。",
  network: "无法连接到 Provider，请检查网络、代理和 API Base URL。",
  malformed: "Provider 返回格式异常，无法完成安全验证。",
  unknown: "API 连接失败，请检查 Provider、模型 ID 与账户状态。",
});

export function classifyConnectionFailure(error) {
  const message = String(error?.message ?? error ?? "");
  if (/\b(401|403)\b|unauthori[sz]ed|forbidden|invalid api.?key/i.test(message)) return "unauthorized";
  if (/\b404\b|not found|unknown model|model.*not.*exist/i.test(message)) return "not_found";
  if (/\b429\b|rate limit|quota|too many requests/i.test(message)) return "rate_limited";
  if (/timeout|timed out|ETIMEDOUT|AbortError/i.test(message)) return "timeout";
  if (/malformed|invalid json|unexpected token|parse error|invalid response/i.test(message)) return "malformed";
  if (/ENOTFOUND|ECONNREFUSED|ECONNRESET|network|fetch failed|socket|DNS/i.test(message)) return "network";
  return "unknown";
}

export function failedConnectionResult(error) {
  const kind = classifyConnectionFailure(error);
  return { status: "ERROR", kind, tool_calling_verified: false, message: CONNECTION_FAILURES[kind] };
}

export function successfulConnectionResult(toolCallingVerified) {
  return toolCallingVerified
    ? { status: "SUCCESS", kind: "success", tool_calling_verified: true, message: "连接成功，模型响应正常，Tool Calling 已验证。" }
    : { status: "ERROR", kind: "malformed", tool_calling_verified: false, message: "模型已响应，但未按要求返回 Tool Call；Scientist Agent 将保持锁定。" };
}
