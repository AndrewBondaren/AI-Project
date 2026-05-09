import { useState } from "react";
import { compile } from "../service/compilerService";

export default function CompilerPanel() {
  const [code, setCode] = useState("");
  const [result, setResult] = useState(null);

  const handleCompile = async () => {
    const res = await compile( code );
    setResult(res);
  };

  return (
    <div style={{ padding: 20 }}>
      <h2>DSL Compiler</h2>

      <textarea
        value={code}
        onChange={(e) => setCode(e.target.value)}
        style={{ width: "100%", height: 200 }}
      />

      <button onClick={handleCompile}>
        Compile
      </button>

      <pre style={{ marginTop: 20 }}>
        {JSON.stringify(result, null, 2)}
      </pre>
    </div>
  );
}