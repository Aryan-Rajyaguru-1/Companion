/// <reference types="vitest" />
import { defineConfig } from 'vite';

export default defineConfig({
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
