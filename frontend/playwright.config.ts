import { defineConfig } from '@playwright/test';
import { resolve } from 'node:path';

const python = process.env.GRAPHSCOPE_PYTHON || (process.platform === 'win32' ? '.venv/Scripts/python.exe' : '.venv/bin/python');
export default defineConfig({
  testDir: './e2e', timeout: 60_000, workers: 1, retries: 0,
  use: { baseURL: 'http://127.0.0.1:8765', headless: true, trace: 'retain-on-failure' },
  outputDir: '../reports/playwright',
  webServer: [
    { command: `npm --prefix frontend run build && "${python}" -m graphscope serve --port 8765`, cwd: resolve(process.cwd(), '..'), url: 'http://127.0.0.1:8765/api/health', reuseExistingServer: false, timeout: 180_000 },
  ],
});
