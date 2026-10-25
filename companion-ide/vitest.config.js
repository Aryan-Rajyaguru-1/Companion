/// <reference types="vitest" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Keep the test transform aligned with vite.config.js. Without the React
// plugin, component tests use the classic JSX runtime and fail with
// "React is not defined" even though the packaged app builds correctly.
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals:     true,
    // electron/ is included deliberately: the main-process CLI wrapper shipped a
    // ReferenceError on every call across v0.3.1..v0.3.3 and no test here could
    // see it, because each caller catches and degrades to an empty result.
    include:     ['src/**/*.test.{js,jsx,ts,tsx}', 'electron/**/*.test.js'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      include:  ['src/utils/**', 'src/components/**', 'electron/**'],
      exclude:  ['src/**/__tests__/**', 'src/**/*.test.*', 'electron/**/__tests__/**'],
    },
  },
});
