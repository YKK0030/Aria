import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/admin': 'http://localhost:8001',
      '/metrics': 'http://localhost:8001',
      '/ws': 'ws://localhost:8001',
    },
  },
  build: {
    outDir: '../dist',
    emptyOutDir: true,
  },
});