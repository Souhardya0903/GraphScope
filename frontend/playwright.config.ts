import { defineConfig } from '@playwright/test';
import { resolve } from 'node:path';

const python = process.env.GRAPHSCOPE_PYTHON || (process.platform === 'win32' ? '.venv/Scripts/python.exe' : '.venv/bin/python');
export default defineConfig({
  testDir: './e2e', timeout: 60_000, workers: 1, retries: 0,
  use: { baseURL: 'http://127.0.0.1:5179', headless: true, trace: 'retain-on-failure' },
  outputDir: '../reports/playwright',
  webServer: [
    { command: `"${python}" -m uvicorn graphscope.api.main:app --host 127.0.0.1 --port 8765`, cwd: resolve(process.cwd(), '..'), url: 'http://127.0.0.1:8765/api/health', reuseExistingServer: false, timeout: 60_000 },
    { command: 'npm run build && npm run preview -- --host 127.0.0.1 --port 5179 --strictPort', url: 'http://127.0.0.1:5179', env: { GRAPHSCOPE_API_URL: 'http://127.0.0.1:8765' }, reuseExistingServer: false, timeout: 180_000 },
  ],
});
