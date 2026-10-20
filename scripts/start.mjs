/** One-command launcher. Uses only Node built-ins; owns only its own children. */
import { spawn, spawnSync } from "node:child_process";
import { existsSync, copyFileSync } from "node:fs";
import { resolve, dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { createConnection } from "node:net";

export const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const windows = process.platform === "win32";
const python = join(root, ".venv", windows ? "Scripts/python.exe" : "bin/python");
const vite = join(root, "frontend/node_modules/vite/bin/vite.js");

export function portOpen(port) {
  return new Promise((done) => {
    const socket = createConnection({ host: "127.0.0.1", port });
    const finish = (open) => { socket.destroy(); done(open); };
    socket.setTimeout(700, () => finish(false));
    socket.once("connect", () => finish(true));
    socket.once("error", () => finish(false));
  });
}

export async function identify(port, kind = port === 8000 ? "backend" : "frontend") {
  if (!await portOpen(port)) return false;
  try {
    const response = await fetch(`http://127.0.0.1:${port}/${kind === "backend" ? "openapi.json" : ""}`, { signal: AbortSignal.timeout(10000) });
    const known = kind === "backend" ? (await response.json()).info?.title === "DataForge AI" : /<title>DataForge AI/.test(await response.text());
    if (response.ok && known) return true;
  } catch { /* An occupied port is never assumed to belong to this app. */ }
  throw new Error(`Port ${port} is in use by another service. Stop it or use the existing app; no process was terminated.`);
}

function setup() {
  const run = (command, args, cwd = root) => {
    const result = spawnSync(command, args, { cwd, stdio: "inherit", windowsHide: true });
    if (result.error || result.status !== 0) throw new Error(`${command} failed. Check the output above.`);
  };
  if (!existsSync(python)) {
    const candidates = windows ? [["py", ["-3"]], ["python", []]] : [["python3", []], ["python", []]];
    const selected = candidates.find(([cmd, args]) => spawnSync(cmd, [...args, "--version"], { windowsHide: true }).status === 0);
    if (!selected) throw new Error("Install Python 3.11 or newer, then run npm run setup.");
    run(selected[0], [...selected[1], "-m", "venv", ".venv"]);
  }
  run(python, ["-m", "pip", "install", "-r", "requirements.txt"]);
  if (!existsSync(join(root, ".env"))) copyFileSync(join(root, ".env.example"), join(root, ".env"));
  if (!process.env.npm_execpath) throw new Error("Run setup using npm run setup.");
  run(process.execPath, [process.env.npm_execpath, "ci", "--no-audit", "--no-fund"], join(root, "frontend"));
  console.log("Setup complete. Run npm start.");
}

export async function launch({ browser = true, apiPort = 8000 } = {}) {
  if (!Number.isInteger(apiPort) || apiPort < 1 || apiPort > 65535 || apiPort === 5173) throw new Error("API port must be 1–65535 and different from the frontend port 5173.");
  if (!existsSync(python) || !existsSync(vite)) throw new Error("Dependencies are missing. Run npm run setup once, then npm start.");
  const backend = await identify(apiPort, "backend"), frontend = await identify(5173);
  const children = [];
  let stopping = false;
  const stop = () => {
    if (stopping) return;
    stopping = true;
    for (const child of children) {
      if (child.exitCode !== null || !child.pid) continue;
      if (windows) spawnSync("taskkill.exe", ["/PID", String(child.pid), "/T", "/F"], { windowsHide: true, stdio: "ignore" });
      else child.kill("SIGTERM");
    }
  };
  const start = (command, args, cwd) => {
    const child = spawn(command, args, { cwd, stdio: "inherit", windowsHide: true, env: { ...process.env, DATAFORGE_API_PORT: String(apiPort) } });
    children.push(child);
    child.on("error", (error) => { console.error(error.message); process.exitCode = 1; stop(); });
    child.on("exit", (code) => { if (!stopping) { process.exitCode = code || 1; stop(); } });
  };
  process.once("SIGINT", stop); process.once("SIGTERM", stop); process.once("exit", stop);
  try {
    if (!backend) start(python, ["-X", "utf8", "-m", "uvicorn", "backend.app.main:app", "--host", "127.0.0.1", "--port", String(apiPort)], root);
    if (!frontend) start(process.execPath, [vite, "--host", "127.0.0.1", "--port", "5173", "--strictPort"], join(root, "frontend"));
    const deadline = Date.now() + 45000;
    while (!stopping) {
      if (await portOpen(apiPort) && await portOpen(5173)) break;
      if (Date.now() > deadline) throw new Error("Startup timed out. Check server output above.");
      await new Promise((done) => setTimeout(done, 250));
    }
    if (stopping) return;
    await identify(apiPort, "backend"); await identify(5173);
    console.log(`DataForge API: http://127.0.0.1:${apiPort}`);
    console.log(`DataForge AI: http://127.0.0.1:5173/\n${children.length ? "Keep this terminal open. Ctrl+C stops the servers launched here." : "Already running; reusing the existing servers. Stop them from their original terminal."}`);
    if (browser) {
      const cmd = windows ? "rundll32.exe" : process.platform === "darwin" ? "open" : "xdg-open";
      const args = windows ? ["url.dll,FileProtocolHandler", "http://127.0.0.1:5173/"] : ["http://127.0.0.1:5173/"];
      const child = spawn(cmd, args, { windowsHide: true, stdio: "ignore" });
      child.on("error", () => console.log("Open http://127.0.0.1:5173/ in your browser."));
      child.unref();
    }
  } catch (error) { stop(); throw error; }
  return { stop, owned: children.length };
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  try { if (process.argv.includes("--setup")) setup(); else {
    const index=process.argv.indexOf("--api-port");
    await launch({ browser: !process.argv.includes("--no-browser"), apiPort: index < 0 ? 8000 : Number(process.argv[index+1]) });
  } }
  catch (error) { console.error(error.message); process.exitCode = 1; }
}
