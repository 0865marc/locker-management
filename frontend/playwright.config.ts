import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  timeout: 20000,
  use: {
    baseURL: 'http://127.0.0.1:4321',
    headless: true,
    trace: 'retain-on-failure',
    launchOptions: {
      executablePath:
        process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH || undefined,
    },
  },
  webServer: [
    {
      command:
        'PUBLIC_API_BASE_URL=http://127.0.0.1:8765 npm run build && python3 -m http.server 4321 --bind 127.0.0.1 --directory dist',
      url: 'http://127.0.0.1:4321',
      reuseExistingServer: false,
      timeout: 60000,
    },
    {
      command: '../backend/.venv/bin/python tests/cors_server.py',
      url: 'http://127.0.0.1:8765/openapi.json',
      reuseExistingServer: false,
      timeout: 30000,
    },
  ],
});
