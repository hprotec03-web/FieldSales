/// <reference types="vitest" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Dev server proxies /api to the FastAPI backend so the HttpOnly auth cookie stays same-origin.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": { target: process.env.VITE_API_PROXY ?? "http://localhost:8000", changeOrigin: false } },
  },
  test: { environment: "jsdom", globals: true, setupFiles: ["./src/setupTests.ts"], css: false },
});
