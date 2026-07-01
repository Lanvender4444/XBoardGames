import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Tauri 期望前端构建产物落在 ../dist、开发服务器跑在 5173（见 src-tauri/tauri.conf.json）。
export default defineConfig({
  plugins: [react()],
  // Tauri 通过固定端口连接 dev server；strictPort 避免端口漂移。
  server: { port: 5173, strictPort: true },
  build: { outDir: "dist", target: "es2021" },
  clearScreen: false,
});
