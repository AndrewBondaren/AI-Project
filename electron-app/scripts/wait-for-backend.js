const http = require("http");

function check() {
  return new Promise((resolve) => {
    http.get("http://127.0.0.1:8000/health", () => resolve(true))
      .on("error", () => resolve(false));
  });
}

async function wait() {
  console.log("⏳ Waiting for backend...");

  while (true) {
    const ok = await check();
    if (ok) {
      console.log("✅ Backend is ready");
      process.exit(0);
    }

    await new Promise(r => setTimeout(r, 500));
  }
}

wait();