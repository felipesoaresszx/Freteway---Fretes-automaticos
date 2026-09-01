import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const apiUrl = process.env.VITE_API_URL || env.VITE_API_URL || "/api/v1";
  if (mode === "production" && /(?:localhost|127\.0\.0\.1):(?:8000|5173)/i.test(apiUrl)) {
    throw new Error("Build bloqueado: VITE_API_URL aponta para um endpoint local.");
  }
  return { plugins: [react()], server: { port: 5173, host: true } };
});
