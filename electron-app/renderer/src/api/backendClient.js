const BASE = "http://127.0.0.1:8000/api";

const DEFAULT_BODY = {
  llm_provider: "qwen",
  model: "qwen3.6",
  meta: {},
  session_id: "session_1"
};

export async function sendChatMessage(sessionId, message) {
  const res = await fetch(`${BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...DEFAULT_BODY, message, request_id: crypto.randomUUID() }),
  });

  const data = await res.json();
  if (!res.ok) throw new Error(data.detail ?? data.error ?? `HTTP ${res.status}`);
  return data;
}

export async function streamChatMessage(sessionId, message, onEvent, { resume = false, requestId } = {}) {
  const request_id = requestId ?? crypto.randomUUID();

  const res = await fetch(`${BASE}/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...DEFAULT_BODY, message, request_id, resume }),
  });

  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail ?? data.error ?? `HTTP ${res.status}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop(); // keep potentially incomplete last line

    for (const line of lines) {
      if (line.startsWith("data: ")) {
        try {
          onEvent(JSON.parse(line.slice(6)));
        } catch {
          // ignore malformed JSON
        }
      }
    }
  }

  return request_id;
}

export async function cancelStream(requestId) {
  await fetch(`${BASE}/chat/stream/${requestId}`, { method: "DELETE" });
}
