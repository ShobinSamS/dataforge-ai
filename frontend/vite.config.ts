import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const apiPort = Number(
    loadEnv(mode, ".", "DATAFORGE_").DATAFORGE_API_PORT || 8000,
  );
  if (!Number.isInteger(apiPort) || apiPort < 1 || apiPort > 65535)
    throw new Error("DATAFORGE_API_PORT must be 1–65535");

  return {
    plugins: [react()],
    server: {
      port: 5173,
      strictPort: true,
      proxy: { "/api": `http://127.0.0.1:${apiPort}` },
      watch: {
        // Formatters can truncate a file before writing its final contents. Wait
        // for a stable file before HMR caches a transformed stylesheet/module.
        awaitWriteFinish: { stabilityThreshold: 300, pollInterval: 50 },
      },
    },
    build: { chunkSizeWarningLimit: 1000 },
  };
});
