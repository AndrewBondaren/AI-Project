export async function sendChatMessage(sessionId, message) {
  const res = await fetch("http://127.0.0.1:8000/api/chat", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      llm_provider: "qwen",
      model: "qwen3.6",
      user_id: "session_1", //sessionId
      message: message
    })
  });

  return res.json();
}