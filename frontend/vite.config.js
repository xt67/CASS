import { defineConfig } from "vite";

export default defineConfig({
  // Serve from root
  root: ".",

  // Public assets folder
  publicDir: "public",

  // Dev server settings
  server: {
    port: 3000,
    open: false,
    // Proxy API calls to backend during development
    proxy: {
      "/api": {
        target: "http://localhost:8001",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },

  // Build output
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
});
