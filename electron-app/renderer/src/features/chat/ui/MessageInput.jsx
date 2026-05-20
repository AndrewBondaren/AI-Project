import { useEffect, useRef, useState } from "react";

export default function MessageInput({ onSend, disabled = false }) {
  const [text, setText] = useState("");
  const ref = useRef(null);

  const send = () => {
    if (!text.trim() || disabled) return;
    onSend(text);
    setText("");
  };

  // авто-расширение textarea
  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    el.style.height = "0px";
    el.style.height = Math.min(el.scrollHeight, 160) + "px";
  }, [text]);

  return (
    <div style={styles.container}>
      <textarea
        ref={ref}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            send();
          }
        }}
        placeholder="Type message... (Shift+Enter = new line)"
        disabled={disabled}
        style={{ ...styles.input, opacity: disabled ? 0.5 : 1 }}
      />

    <button
        onClick={send}
        style={{
            ...styles.button,
            opacity: text.trim() ? 1 : 0.4,
            pointerEvents: text.trim() ? "auto" : "none"
        }}
        onMouseOver={(e) => {
            if (text.trim()) e.target.style.background = "#6366f1";
        }}
        onMouseOut={(e) => {
            e.target.style.background = "#4f46e5";
        }}
    >
        ↑
    </button>
    </div>
  );
}

const styles = {
  container: {
    display: "flex",
    padding: 10,
    gap: 8,
    alignItems: "flex-end"
  },
  input: {
    flex: 1,
    resize: "none",
    overflowY: "auto",
    maxHeight: 160,
    minHeight: 40,
    padding: 10,
    borderRadius: 8,
    outline: "none",
    fontSize: 14
  },
  button: {
    width: 40,
    height: 40,
    borderRadius: "50%",
    border: "none",
    background: "#4f46e5",
    color: "white",
    fontSize: 18,
    cursor: "pointer",

    display: "flex",
    alignItems: "center",
    justifyContent: "center",

    transition: "0.2s",
    
  }
};