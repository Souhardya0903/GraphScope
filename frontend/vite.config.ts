import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: process.env.GRAPHSCOPE_API_URL || 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  preview: { proxy: { '/api': { target: process.env.GRAPHSCOPE_API_URL || 'http://127.0.0.1:8000', changeOrigin: true } } },
  // @ts-expect-error vitest config
  test: {
    include: ['src/**/*.test.{ts,tsx}'],
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/setupTests.ts'],
  },
});
