import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  use: {
    baseURL: "http://127.0.0.1:5001",
    viewport: { width: 1366, height: 900 },
    trace: "retain-on-failure",
  },
  webServer: {
    command:
      process.platform === "win32"
        ? "..\\.venv\\Scripts\\python.exe ..\\tests\\dashboard_preview.py"
        : "python ../tests/dashboard_preview.py",
    url: "http://127.0.0.1:5001/api/v1/bootstrap",
    reuseExistingServer: !process.env.CI,
    timeout: 30000,
  },
});
