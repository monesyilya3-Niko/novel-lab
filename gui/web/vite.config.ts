import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// 前端构建产物输出到 gui/web/dist，由后端 launch.py 直接静态托管。
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // dev 模式下把 API 与 SSE 代理到本地 GUI 后端（默认 8000）。
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
})
