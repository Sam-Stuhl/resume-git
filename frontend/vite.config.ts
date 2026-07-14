import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In dev, proxy API + PDF calls to the FastAPI server on :8080.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://localhost:8080",
      "/health": "http://localhost:8080",
    },
  },
});
