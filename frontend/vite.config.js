import react from "@vitejs/plugin-react";
import { loadEnv } from "vite";
import { defineConfig } from "vitest/config";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, "..", "");
  const apiTarget = env.API_PROXY_TARGET || "http://localhost:8000";
  const proxy = Object.fromEntries(
    [
      "^/health$",
      "^/auth(?:/|$)",
      "^/accesos(?:/|$)",
      "^/tarifas(?:/|$)",
      "^/sedes(?:/|$)",
      "^/consultas(?:/|$)",
      "^/pagos(?:/|$)",
    ].map((path) => [
      path,
      {
        target: apiTarget,
      },
    ]),
  );

  return {
    plugins: [react()],
    envDir: "..",
    server: {
      proxy,
    },
    test: {
      environment: "jsdom",
      setupFiles: "./src/test-setup.js",
    },
  };
});
