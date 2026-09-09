import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  base: './',
  build: { outDir: 'dist', emptyOutDir: true },
  server: { 
    port: 5173, 
    strictPort: true,
    fs: { allow: ['.', 'node_modules'] }
  },
  resolve: { 
    alias: { 
      '@': path.resolve(__dirname, 'src')
    } 
  },
  optimizeDeps: { 
    exclude: ['electron'],
    include: ['@monaco-editor/react', 'monaco-editor']
  },
});
