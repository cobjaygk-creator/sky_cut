import path from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig, type PluginOption } from "vite";
import react from "@vitejs/plugin-react";

const rootDir = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  plugins: [react() as PluginOption],
  resolve: {
    alias: {
      "@new-cut/remotion": path.resolve(rootDir, "../remotion/src"),
    },
  },
  server: {
    host: "127.0.0.1",
    port: 5173,
    fs: {
      allow: [rootDir, path.resolve(rootDir, "../remotion")],
    },
  },
  optimizeDeps: {
    include: ["remotion", "@remotion/player"],
  },
});
