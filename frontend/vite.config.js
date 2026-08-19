import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const backend = (env.DEV_API_PROXY_TARGET || "http://127.0.0.1:8750").replace(/\/+$/, "");

  return {
    plugins: [react()],
    server: {
      port: 8760,
      strictPort: false,
      proxy: {
        "/api": { target: backend, changeOrigin: true },
        "/health": { target: backend, changeOrigin: true },
      },
    },
  };
});
