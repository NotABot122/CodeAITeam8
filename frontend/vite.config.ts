import react from '@vitejs/plugin-react';
import {fileURLToPath} from 'node:url';
import {defineConfig} from 'vitest/config';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {'@': fileURLToPath(new URL('./src', import.meta.url))},
  },
  server: {proxy: {'/api': 'http://127.0.0.1:8080'}},
  test: {environment: 'node', include: ['src/**/*.test.{ts,tsx}']},
});
