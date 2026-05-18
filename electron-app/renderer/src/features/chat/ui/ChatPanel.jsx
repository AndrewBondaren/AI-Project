import { useEffect, useRef, useState } from "react";
import MessageList from "./MessageList";
import MessageInput from "./MessageInput";
import { sendMessage } from "../service/chatService";
import { getSessionId } from "@/common/sessionId";

export default function ChatPanel() {
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);

  const chatRef = useRef(null);

  useEffect(() => {
    const el = chatRef.current;
    if (!el) return;

    // после рендера DOM
    requestAnimationFrame(() => {
      el.scrollTop = el.scrollHeight;
    });
  }, [messages, loading]);

  const handleSend = async (text) => {
    if (!text.trim()) return;
    const sessionId = getSessionId();

    setMessages((prev) => [...prev, { role: "user", text }]);
    setLoading(true);

    try {
      const res = await sendMessage(sessionId, text);

      let botText;
      if (res.ok === false) {
        botText = res.error ?? JSON.stringify(res.response, null, 2);
      } else if (typeof res.response === "string") {
        botText = res.response;
      } else {
        botText = JSON.stringify(res.response, null, 2);
      }

      setMessages((prev) => [...prev, { role: "bot", text: botText }]);
    } catch (e) {
      setMessages((prev) => [
        ...prev,
        { role: "bot", text: `Error: ${e.message}` },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={styles.page}>
      <div style={styles.wrapper}>

        {/* CHAT */}
        <div ref={chatRef} style={styles.chatArea}>
          <MessageList messages={messages} />
        </div>

        {/* TYPING */}
        {loading && (
          <div style={styles.typing}>
            bot is typing...
          </div>
        )}

        {/* INPUT */}
        <div style={styles.inputBar}>
          <MessageInput onSend={handleSend} />
        </div>

      </div>
    </div>
  );
}

const styles = {
  page: {
    height: "100vh",
    width: "100%",
    display: "flex",
    justifyContent: "center",
    background: "#0f0f10",
    overflow: "hidden"
  },

  wrapper: {
    width: "100%",
    maxWidth: 920,
    height: "100vh",
    display: "flex",
    flexDirection: "column"
  },

  chatArea: {
    flex: 1,
    overflowY: "auto",
    padding: 12,
    minHeight: 0,
    background: "rgba(10, 10, 10, 0.7)"
  },

  inputBar: {
    padding: 12,
    borderTop: "1px solid rgba(255,255,255,0.1)",
    background: "rgba(37, 37, 37, 0.6)",
    backdropFilter: "blur(12px)"
  },

  typing: {
    position: "absolute",
    bottom: 70,
    left: 12,
    fontSize: 12,
    opacity: 0.6,
    color: "white"
  }
};