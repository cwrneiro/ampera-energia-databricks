import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev: `uvicorn app:app` on :8000 serves the API; `npm run dev` proxies /api to it.
export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/api": "http://127.0.0.1:8000" } },
  build: { chunkSizeWarningLimit: 1500 },
});
