import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// 前端构建产物输出到 gui/web/dist，由后端 launch.py 直接静态托管。
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    rollupOptions: {
      output: {
        // 4B：react+mui 合并为 vendor 避免 circular；echarts 独立 chunk。
        manualChunks: {
          'vendor': ['react', 'react-dom', '@mui/material', '@mui/icons-material', '@emotion/react', '@emotion/styled'],
          'echarts': ['echarts'],
        },
      },
    },
  },
})
