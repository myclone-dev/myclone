import { defineConfig } from "vite";
import path from "path";
import { getEnvDefines, sharedConfig } from "./vite.embed.shared";

/**
 * Build config for the embed app (React app that runs in iframe)
 * Creates the chat interface shown inside the widget
 */
export default defineConfig(({ mode }) => ({
  ...sharedConfig,

  define: getEnvDefines(mode),

  root: path.resolve(__dirname, "src/embed/app"),

  build: {
    outDir: path.resolve(__dirname, "public/embed"),
    emptyOutDir: false,
    minify: "terser" as const,
    terserOptions: {
      compress: {
        drop_console: false,
        drop_debugger: true,
      },
    },
    sourcemap: process.env.VITE_SOURCEMAP === "true",

    rollupOptions: {
      input: path.resolve(__dirname, "src/embed/app/app.html"),
      output: {
        format: "es",
        entryFileNames: "assets/app.js",
        chunkFileNames: "assets/[name]-[hash].js",
        assetFileNames: (assetInfo) => {
          if (assetInfo.name?.includes(".css")) {
            return "assets/app.css";
          }
          return "assets/[name]-[hash].[ext]";
        },
        manualChunks: undefined,
      },
    },
  },

  server: {
    port: 5174,
    strictPort: true,
  },
}));
