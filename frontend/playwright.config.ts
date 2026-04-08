import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "tests/e2e",
  use: {
    baseURL: "http://localhost:5173",
  },
  webServer: [
    {
      command:
        "APP_USERNAME=admin APP_PASSWORD=adminpass123 " +
        "DATABASE_URL=postgresql://market_data:market_data@127.0.0.1:5432/market_data " +
        "MARKETDATA_API_TOKEN=dummy " +
        "uvicorn src.api.main:create_app --factory --host 127.0.0.1 --port 8001",
      url: "http://127.0.0.1:8001/api/health",
      cwd: "..",
      reuseExistingServer: true,
    },
    {
      command: "pnpm dev",
      url: "http://localhost:5173",
      reuseExistingServer: true,
    },
  ],
});
