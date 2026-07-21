import { fileURLToPath } from 'node:url'
import { defineConfig, devices } from '@playwright/test'

const frontendDir = fileURLToPath(new URL('.', import.meta.url))
const reuseExistingServer = process.env.PLAYWRIGHT_REUSE_SERVERS === '1' && !process.env.CI

export default defineConfig({
  testDir: './e2e',
  outputDir: 'test-results',
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: [['list'], ['html', { open: 'never', outputFolder: 'playwright-report' }], ['junit', { outputFile: 'test-results/e2e-junit.xml' }]],
  use: {
    baseURL: 'http://127.0.0.1:5174',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'off',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: [
    {
      command: 'python3 -c "from pathlib import Path; Path(\'../backend/e2e_app.db\').unlink(missing_ok=True)" && APARTMENT_ENV=test APARTMENT_DB_PATH=../backend/e2e_app.db python3 -m uvicorn app.main:app --app-dir ../backend --host 127.0.0.1 --port 9000',
      cwd: frontendDir,
      url: 'http://127.0.0.1:9000/api/health',
      reuseExistingServer,
      timeout: 120_000,
    },
    {
      command: 'npm run dev -- --host 127.0.0.1 --port 5174',
      cwd: frontendDir,
      url: 'http://127.0.0.1:5174',
      reuseExistingServer,
      timeout: 120_000,
    },
  ],
})
