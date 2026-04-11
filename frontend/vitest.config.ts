import { defineConfig } from "vitest/config";
import solidPlugin from "vite-plugin-solid";

export default defineConfig({
  plugins: [solidPlugin()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./tests/setup.ts"],
    exclude: ["tests/e2e/**", "node_modules/**"],
    coverage: {
      provider: "v8",
      thresholds: {
        "src/lib/**": { lines: 80, functions: 80 },
        global: { lines: 70 },
      },
    },
  },
  resolve: {
    conditions: ["development", "browser"],
    alias: {
      "~": new URL("./src", import.meta.url).pathname,
    },
  },
});
