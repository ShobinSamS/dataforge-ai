/** HTTP launcher. Stdio clients must launch run_mcp.py directly (no npm banners). */
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const python = join(root, ".venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
if (!existsSync(python)) {
  console.error("Run npm run setup, then install requirements-mcp.txt first.");
  process.exitCode = 1;
} else {
  const child = spawn(python, ["-X", "utf8", join(root, "scripts/run_mcp.py"), "--transport", "streamable-http", ...process.argv.slice(2)],
    { cwd: root, stdio: "inherit", windowsHide: true });
  const stop = () => { if (child.exitCode === null) child.kill("SIGTERM"); };
  process.once("SIGINT", stop); process.once("SIGTERM", stop); process.once("exit", stop);
  child.once("error", (error) => { console.error(error.message); process.exitCode = 1; });
  child.once("exit", (code) => { process.exitCode = code || 0; });
}
