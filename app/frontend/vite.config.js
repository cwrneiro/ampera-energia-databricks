import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev: `uvicorn app:app` on :8000 serves the API; `npm run dev` proxies /api to it. To develop against
// the deployed app instead: API_TARGET=https://<app-url> API_TOKEN=$(databricks auth token ... | jq -r .access_token).
const target = process.env.API_TARGET || "http://127.0.0.1:8000";
const token = process.env.API_TOKEN;
export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/api": { target, changeOrigin: true, headers: token ? { Authorization: `Bearer ${token}` } : {} } } },
  build: { chunkSizeWarningLimit: 1500 },
});
