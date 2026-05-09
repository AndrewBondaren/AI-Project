export async function compileRequest(code) {
  const res = await fetch("http://127.0.0.1:8000/compile", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ code })
  });

  return res.json();
}