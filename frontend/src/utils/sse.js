/** Authenticated API client. Tokens stay in memory and are never put in URLs. */
const baseUrl = (import.meta.env?.VITE_API_BASE_URL || "/api").replace(/\/+$/, "");
let apiToken = "";
export function setApiToken(token) { apiToken = token.trim(); }
export async function apiFetch(path, options = {}) {
  const headers = new Headers(options.headers);
  if (apiToken) headers.set("Authorization", `Bearer ${apiToken}`);
  const response = await fetch(`${baseUrl}${path}`, { ...options, headers });
  if (!response.ok) throw new Error(`HTTP ${response.status}: ${response.statusText}`);
  return response;
}
export function streamChat(message, callbacks = {}) {
  const controller = new AbortController();
  (async () => {
    let reader;
    let ended = false;
    try {
      const response = await apiFetch("/chat/stream", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message }), signal: controller.signal,
      });
      reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (!ended) {
        const { value, done } = await reader.read();
        buffer += decoder.decode(value, { stream: !done });
        let match;
        while ((match = /\r?\n\r?\n/.exec(buffer))) {
          const block = buffer.slice(0, match.index);
          buffer = buffer.slice(match.index + match[0].length);
          const payload = block.split(/\r?\n/).filter(line => line.startsWith("data:"))
            .map(line => line.slice(5).trimStart()).join("\n");
          if (!payload) continue;
          const event = JSON.parse(payload);
          const names = { start: "onStart", token: "onToken", sql: "onSql", data: "onData" };
          if (event.type === "error") throw new Error(event.content);
          if (event.type === "end") { ended = true; callbacks.onEnd?.(); break; }
          callbacks[names[event.type]]?.(event.content);
        }
        if (done) {
          if (!ended) throw new Error("Stream ended before completion");
          break;
        }
      }
    } catch (error) {
      if (error.name !== "AbortError") callbacks.onError?.(error.message);
    } finally {
      await reader?.cancel().catch(() => {});
      reader?.releaseLock();
    }
  })();
  return { close: () => controller.abort() };
}
export async function sendChat(message) {
  return (await apiFetch("/chat", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }) })).json();
}
export async function checkHealth() { return (await apiFetch("/")).json(); }
export async function getSchema() { return (await (await apiFetch("/schema")).json()).schema; }
export async function getTables() { return (await (await apiFetch("/tables")).json()).tables; }
