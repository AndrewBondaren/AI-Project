import { useEffect, useRef, useState } from "react";
import MessageList from "./MessageList";
import MessageInput from "./MessageInput";
import { streamMessage } from "../service/chatService";
import { getSessionId } from "@/common/sessionId";

export default function ChatPanel() {
  const [messages,    setMessages]    = useState([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [statusLabel, setStatusLabel] = useState(null);  // current pipeline phase
  const [thinkingMs,  setThinkingMs]  = useState(null);  // LLM internal thinking duration

  const chatRef      = useRef(null);
  const timerRef     = useRef(null);
  const startTimeRef = useRef(null);
  const [elapsed, setElapsed] = useState(0);

  // auto-scroll
  useEffect(() => {
    const el = chatRef.current;
    if (!el) return;
    requestAnimationFrame(() => { el.scrollTop = el.scrollHeight; });
  }, [messages, isStreaming]);

  const startTimer = () => {
    startTimeRef.current = Date.now();
    setElapsed(0);
    timerRef.current = setInterval(() => {
      setElapsed(Date.now() - startTimeRef.current);
    }, 100);
  };

  const stopTimer = () => {
    clearInterval(timerRef.current);
    timerRef.current = null;
  };

  const handleSend = async (text) => {
    if (!text.trim() || isStreaming) return;
    const sessionId = getSessionId();

    setMessages((prev) => [...prev, { role: "user", text }]);
    setIsStreaming(true);
    setStatusLabel(null);
    setThinkingMs(null);
    startTimer();

    try {
      await streamMessage(sessionId, text, (event) => {
        switch (event.type) {
          case "node_status":
            setStatusLabel({ phase: event.phase, task_type: event.task_type });
            break;

          case "thinking":
            setThinkingMs(event.elapsed_ms);
            break;

          case "result": {
            const response = event.response;
            const botText =
              typeof response === "string"
                ? response
                : JSON.stringify(response, null, 2);
            setMessages((prev) => [...prev, { role: "bot", text: botText }]);
            break;
          }

          case "error":
            setMessages((prev) => [...prev, { role: "bot", text: `Error: ${event.message}` }]);
            break;
        }
      });
    } catch (e) {
      setMessages((prev) => [...prev, { role: "bot", text: `Error: ${e.message}` }]);
    } finally {
      stopTimer();
      setIsStreaming(false);
      setStatusLabel(null);
      setThinkingMs(null);
    }
  };

  const statusText = buildStatusText(statusLabel, thinkingMs, elapsed);

  return (
    <div style={styles.page}>
      <div style={styles.wrapper}>

        <div ref={chatRef} style={styles.chatArea}>
          <MessageList messages={messages} />
        </div>

        {isStreaming && (
          <div style={styles.statusBar}>
            <span style={styles.statusDot} />
            <span>{statusText}</span>
            <span style={styles.timer}>{(elapsed / 1000).toFixed(1)}s</span>
          </div>
        )}

        <div style={styles.inputBar}>
          <MessageInput onSend={handleSend} disabled={isStreaming} />
        </div>

      </div>
    </div>
  );
}

function buildStatusText(statusLabel, thinkingMs, elapsed) {
  if (thinkingMs !== null) {
    // elapsed_ms=0 means LLM just started — use growing global timer
    const displayMs = thinkingMs > 0 ? thinkingMs : elapsed;
    return `LLM thinking... ${(displayMs / 1000).toFixed(1)}s`;
  }
  if (!statusLabel) return "Processing...";
  const phase = statusLabel.phase;
  const task  = statusLabel.task_type ?? "";
  if (phase === "repairing") return `Repairing: ${task}`;
  if (phase === "executing") return `Executing: ${task}`;
  if (phase === "done")      return `Done: ${task}`;
  return phase;
}

const styles = {
  page: {
    height: "100vh",
    width: "100%",
    display: "flex",
    justifyContent: "center",
    background: "#0f0f10",
    overflow: "hidden",
  },
  wrapper: {
    width: "100%",
    maxWidth: 920,
    height: "100vh",
    display: "flex",
    flexDirection: "column",
  },
  chatArea: {
    flex: 1,
    overflowY: "auto",
    padding: 12,
    minHeight: 0,
    background: "rgba(10, 10, 10, 0.7)",
  },
  statusBar: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    padding: "6px 16px",
    fontSize: 12,
    color: "rgba(255,255,255,0.55)",
    borderTop: "1px solid rgba(255,255,255,0.06)",
    background: "rgba(20,20,20,0.8)",
  },
  statusDot: {
    width: 6,
    height: 6,
    borderRadius: "50%",
    background: "#6366f1",
    flexShrink: 0,
    animation: "pulse 1.4s ease-in-out infinite",
  },
  timer: {
    marginLeft: "auto",
    fontVariantNumeric: "tabular-nums",
    color: "rgba(255,255,255,0.3)",
  },
  inputBar: {
    padding: 12,
    borderTop: "1px solid rgba(255,255,255,0.1)",
    background: "rgba(37, 37, 37, 0.6)",
    backdropFilter: "blur(12px)",
  },
};
