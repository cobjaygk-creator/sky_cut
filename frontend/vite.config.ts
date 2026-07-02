import { defineConfig, type PluginOption } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react() as PluginOption],
  server: {
    host: "127.0.0.1",
    port: 5173,
  },
});
