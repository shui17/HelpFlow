import { defineConfig } from '@playwright/test'
import { resolve } from 'node:path'
const python = resolve('../backend/.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python')
const testDatabase = process.env.HELPFLOW_TEST_DATABASE_URL
if (!testDatabase || !new URL(testDatabase).pathname.startsWith('/helpflow_stage5_test')) {
  throw new Error('E2E requires HELPFLOW_TEST_DATABASE_URL pointing to a dedicated helpflow_stage5_test database')
}
export default defineConfig({
  testDir: './e2e', timeout: 60000, workers: 1,
  use: { baseURL: 'http://127.0.0.1:5175', trace: 'retain-on-failure',
    launchOptions: process.env.E2E_BROWSER_PATH ? { executablePath: process.env.E2E_BROWSER_PATH } : {} },
  webServer: [
    { command: `"${python}" -m uvicorn app.main:app --host 127.0.0.1 --port 8011`, cwd: '../backend', env: {
      HELPFLOW_DATABASE_URL: testDatabase,
      HELPFLOW_JWT_SECRET_KEY: process.env.HELPFLOW_JWT_SECRET_KEY || 'local-browser-tests-only-signing-key-0123456789',
      HELPFLOW_CORS_ORIGINS: '["http://127.0.0.1:5175"]',
    }, url: 'http://127.0.0.1:8011/api/v1/health', reuseExistingServer: false, timeout: 30000 },
    { command: 'npm run dev -- --port 5175', url: 'http://127.0.0.1:5175', reuseExistingServer: false,
      env: { VITE_API_BASE_URL: 'http://127.0.0.1:8011/api/v1' } },
  ],
})
