import { defineConfig, devices } from '@playwright/test'

const webUrl = 'http://127.0.0.1:5175'
const apiUrl = 'http://127.0.0.1:8002'

export default defineConfig({
  testDir: './e2e',
  globalTeardown: './e2e/global-teardown.ts',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [['list']],
  use: {
    ...devices['Desktop Chrome'],
    baseURL: webUrl,
    headless: true,
    launchOptions: {
      executablePath: process.env.PLAYWRIGHT_CHROMIUM_PATH ?? '/usr/bin/chromium',
      args: ['--no-sandbox'],
    },
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
  },
  webServer: [
    {
      command: [
        'TRIALSYNC_EXTRACTION_PROVIDER=rule_based',
        'TRIALSYNC_SCREENING_CHAT_PROVIDER=canonical',
        `TRIALSYNC_CORS_ORIGINS='["${webUrl}"]'`,
        '../backend/.venv/bin/uvicorn trialsync.main:create_app',
        '--factory --app-dir ../backend/src --host 127.0.0.1 --port 8002',
      ].join(' '),
      url: `${apiUrl}/health/live`,
      timeout: 30_000,
      reuseExistingServer: false,
      stdout: 'pipe',
      stderr: 'pipe',
    },
    {
      command: `VITE_API_BASE_URL=${apiUrl}/api/v1 npm run dev -- --host 127.0.0.1 --port 5175`,
      url: webUrl,
      timeout: 30_000,
      reuseExistingServer: false,
      stdout: 'pipe',
      stderr: 'pipe',
    },
  ],
})
