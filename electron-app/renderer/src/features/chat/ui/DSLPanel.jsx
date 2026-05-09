// import { useState } from "react";
// import { sendMessage } from "../service/chatService";

// export default function DSLPanel() {
//   const [code, setCode] = useState("");
//   const [result, setResult] = useState(null);

//   const handleSend  = async () => {
//     const data = await sendMessage("test-session", "hello");;
//     setResult(data);
//   };

//   return (
//     <div style={{ padding: 20 }}>
//       <h2>World of Demiurgs</h2>

//       <textarea
//         value={code}
//         onChange={(e) => setCode(e.target.value)}
//         style={{ width: "100%", height: 200 }}
//       />

//       <button onClick={handleSend}>
//         Compile
//       </button>

//       <pre style={{ marginTop: 20 }}>
//         {JSON.stringify(result, null, 2)}
//       </pre>
//     </div>
//   );
// }