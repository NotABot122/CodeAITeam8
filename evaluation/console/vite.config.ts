import react from '@vitejs/plugin-react';
import {defineConfig} from 'vitest/config';

export default defineConfig({
  plugins: [react()],
  // Relative asset URLs so the console also works behind a path prefix (e.g. an IDE port proxy /proxy/8090/).
  base: './',
  server: {port: 5174, proxy: {'/api': 'http://127.0.0.1:8090'}},
  test: {environment: 'node', include: ['src/**/*.test.{ts,tsx}']},
});
