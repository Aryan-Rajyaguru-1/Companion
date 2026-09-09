/// <reference types="vitest" />
import { defineConfig } from 'vite';

export default defineConfig({
  test: {
    environment: 'jsdom',
    globals:     true,
    include:     ['src/**/*.test.{js,jsx,ts,tsx}'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      include:  ['src/utils/**', 'src/components/**'],
      exclude:  ['src/**/__tests__/**', 'src/**/*.test.*'],
    },
  },
});
