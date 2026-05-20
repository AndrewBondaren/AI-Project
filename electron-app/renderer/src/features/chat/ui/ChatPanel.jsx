import { useEffect, useRef, useState } from "react";
import MessageList from "./MessageList";
import MessageInput from "./MessageInput";
import { streamMessage, cancelStream } from "../service/chatService";
import { getSessionId } from "@/common/sessionId";

export default function ChatPanel() {
  const [messages,    setMessages]    = useState([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [statusLabel, setStatusLabel] = useState(null);
  const [thinkingMs,  setThinkingMs]  = useState(null);
  const [canResume,   setCanResume]   = useState(false);

  const chatRef        = useRef(null);
  const timerRef       = useRef(null);
  const startTimeRef   = useRef(null);
  const requestIdRef   = useRef(null);
  const lastMessageRef = useRef(null);
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const el = chatRef.current;
    if (!el) return;
    requestAnimationFrame(() => { el.scrollTop = el.scrollHeight; });
  }, [messages, isStreaming, canResume]);

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

  const handleCancel = () => {
    if (requestIdRef.current) cancelStream(requestIdRef.current);
  };

  const runStream = async (text, resume = false) => {
    const sessionId = getSessionId();
    const requestId = crypto.randomUUID();
    requestIdRef.current = requestId;
    lastMessageRef.current = text;

    setIsStreaming(true);
    setCanResume(false);
    setStatusLabel(null);
    setThinkingMs(null);
    startTimer();

    try {
      await streamMessage(sessionId, text, (event) => {
        switch (event.type) {
          case "node_status":
            setStatusLabel({ phase: event.phase, task_type: event.task_type });
            setThinkingMs(null);
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

          case "cancelled":
            setMessages((prev) => [...prev, { role: "system", text: "Cancelled" }]);
            setCanResume(true);
            break;

          case "error":
            setMessages((prev) => [...prev, { role: "bot", text: `Error: ${event.message}` }]);
            break;
        }
      }, { requestId, resume });
    } catch (e) {
      setMessages((prev) => [...prev, { role: "bot", text: `Error: ${e.message}` }]);
    } finally {
      requestIdRef.current = null;
      stopTimer();
      setIsStreaming(false);
      setStatusLabel(null);
      setThinkingMs(null);
    }
  };

  const handleSend = async (text) => {
    if (!text.trim() || isStreaming) return;
    setCanResume(false);
    setMessages((prev) => [...prev, { role: "user", text }]);
    await runStream(text, false);
  };

  const handleResume = async () => {
    if (!lastMessageRef.current || isStreaming) return;
    await runStream(lastMessageRef.current, true);
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
            <button style={styles.cancelBtn} onClick={handleCancel} title="Cancel">
              ✕
            </button>
          </div>
        )}

        {canResume && !isStreaming && (
          <div style={styles.resumeBar}>
            <span style={styles.resumeHint}>Request was cancelled.</span>
            <button style={styles.resumeBtn} onClick={handleResume}>
              Continue
            </button>
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
  cancelBtn: {
    marginLeft: 8,
    padding: "2px 8px",
    fontSize: 11,
    lineHeight: 1,
    background: "rgba(239,68,68,0.15)",
    color: "rgba(239,68,68,0.8)",
    border: "1px solid rgba(239,68,68,0.3)",
    borderRadius: 4,
    cursor: "pointer",
  },
  resumeBar: {
    display: "flex",
    alignItems: "center",
    gap: 10,
    padding: "6px 16px",
    fontSize: 12,
    color: "rgba(255,255,255,0.4)",
    borderTop: "1px solid rgba(255,255,255,0.06)",
    background: "rgba(20,20,20,0.8)",
  },
  resumeHint: {
    flex: 1,
    fontStyle: "italic",
  },
  resumeBtn: {
    padding: "3px 12px",
    fontSize: 12,
    background: "rgba(99,102,241,0.2)",
    color: "rgba(99,102,241,0.9)",
    border: "1px solid rgba(99,102,241,0.4)",
    borderRadius: 4,
    cursor: "pointer",
  },
  inputBar: {
    padding: 12,
    borderTop: "1px solid rgba(255,255,255,0.1)",
    background: "rgba(37, 37, 37, 0.6)",
    backdropFilter: "blur(12px)",
  },
};
