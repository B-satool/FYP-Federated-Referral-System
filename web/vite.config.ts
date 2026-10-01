import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In development the Vite server proxies the same /api/* paths that nginx serves in the container.
const target = (port: number) => ({
  target: `http://localhost:${port}`,
  changeOrigin: true,
  rewrite: (p: string) => p.replace(/^\/api\/[a-z]+/, ""),
});

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api/central": target(8000),
      "/api/clinic": target(8001),
      "/api/lab": target(8002),
      "/api/specialist": target(8003),
    },
  },
});
