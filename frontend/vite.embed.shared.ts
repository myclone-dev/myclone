import { loadEnv } from "vite";
import path from "path";
import tailwindcss from "@tailwindcss/postcss";
import react from "@vitejs/plugin-react";

/**
 * Get environment variable definitions for Vite build
 */
export function getEnvDefines(mode: string) {
  const env = loadEnv(mode, process.cwd(), "");

  return {
    // Production URLs as fallback for embed widget
    "process.env.NEXT_PUBLIC_API_URL": JSON.stringify(
      env.NEXT_PUBLIC_API_URL || "http://localhost:8001/api/v1",
    ),
    "process.env.NEXT_PUBLIC_APP_URL": JSON.stringify(
      env.NEXT_PUBLIC_APP_URL || "http://localhost:3000",
    ),
    "process.env.NEXT_PUBLIC_API_KEY": JSON.stringify(
      env.NEXT_PUBLIC_API_KEY || "",
    ),
    "process.env.NEXT_PUBLIC_LIVEKIT_URL": JSON.stringify(
      env.NEXT_PUBLIC_LIVEKIT_URL || "",
    ),
  };
}

/**
 * Shared config for both embed builds
 */
export const sharedConfig = {
  plugins: [react()],
  base: "/embed/",

  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },

  css: {
    postcss: {
      plugins: [tailwindcss()],
    },
  },

  publicDir: false as const,

  build: {
    outDir: "public/embed",
    emptyOutDir: false,
    minify: "terser" as const,
    terserOptions: {
      compress: {
        drop_console: false,
        drop_debugger: true,
      },
    },
    sourcemap: process.env.VITE_SOURCEMAP === "true",
  },

  envPrefix: "VITE_",
};
