import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: { "/api": "http://127.0.0.1:8000" },
    watch: {
      // Formatters can truncate a file before writing its final contents. Wait
      // for a stable file before HMR caches a transformed stylesheet/module.
      awaitWriteFinish: { stabilityThreshold: 300, pollInterval: 50 },
    },
  },
  build: { chunkSizeWarningLimit: 1000 },
});
