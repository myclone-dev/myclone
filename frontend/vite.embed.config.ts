import { defineConfig } from "vite";
import path from "path";
import { getEnvDefines, sharedConfig } from "./vite.embed.shared";

/**
 * Build config for the embed SDK loader (myclone-embed.js)
 * Creates the script that customers include on their websites
 */
export default defineConfig(({ mode }) => ({
  ...sharedConfig,

  define: getEnvDefines(mode),

  build: {
    ...sharedConfig.build,

    rollupOptions: {
      input: path.resolve(__dirname, "src/embed/sdk/index.ts"),
      output: {
        format: "iife",
        name: "MyClone",
        entryFileNames: "myclone-embed.js",
        inlineDynamicImports: true,
      },
    },
  },

  server: {
    port: 5173,
    strictPort: true,
  },
}));
