import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";

// The build output is embedded in the Python package as resources that
// pulsar_ui.server hosts at "/". Everything is bundled locally: no CDN,
// no runtime network dependency.
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: fileURLToPath(new URL("../src/pulsar_ui/static", import.meta.url)),
    emptyOutDir: true,
    sourcemap: false,
    target: "es2020",
    chunkSizeWarningLimit: 1600,
  },
});
