export default function MessageList({ messages }) {
  return (
    <div style={styles.list}>
      {messages.map((m, i) => (
        <div
          key={i}
          style={{
            ...styles.msg,
            alignSelf: m.role === "user" ? "flex-end" : "flex-start",
            background: m.role === "user"
              ? "linear-gradient(135deg, #181825, #4c4eca)"
              : m.role === "system"
              ? "transparent"
              : "transparent",
            boxShadow: m.role === "user" ? "0 2px 10px rgba(0,0,0,0.2)" : "none",
            border: "none",
            padding: m.role === "user" ? "10px 14px" : "6px 0",
            color: m.role === "system" ? "rgba(239,68,68,0.6)" : "white",
            fontSize: m.role === "system" ? 11 : undefined,
            fontStyle: m.role === "system" ? "italic" : undefined,
          }}
        >
          {m.text}
        </div>
      ))}
    </div>
  );
}

const styles = {
  list: {
    flex: 1,
    padding: 10,
    overflowY: "auto",
    display: "flex",
    flexDirection: "column",
    gap: 8
  },
 msg: {
   padding: "10px 14px",
   borderRadius: 16,
   maxWidth: "70%",
   wordBreak: "break-word",
   boxShadow: "0 2px 10px rgba(0,0,0,0.2)"
 }
};