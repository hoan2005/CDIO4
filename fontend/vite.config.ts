import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path' // 1. Thêm import này

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/chat': 'http://localhost:8000',
    },
  },
  // 2. Thêm cấu hình resolve dưới đây
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
})