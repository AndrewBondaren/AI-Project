export async function sendChatMessage(sessionId, message) {
  const res = await fetch("http://127.0.0.1:8000/api/chat", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      llm_provider: "qwen",
      model: "qwen3.6",
      meta: {},
      user_id: "session_1", //sessionId
      message: message,
      repair_iterations: 4
    })
  });

  const data = await res.json();

  if (!res.ok) {
    throw new Error(data.detail ?? data.error ?? `HTTP ${res.status}`);
  }

  return data;
}