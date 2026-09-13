import { defineConfig } from '@playwright/test'

// E2E 冒烟配置：针对本地已启动的 novel-lab 服务（默认 127.0.0.1:8000，
// 可用 E2E_BASE_URL 覆盖）。CI 中由 e2e job 先起服务再跑本套件。
export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  retries: process.env.CI ? 1 : 0,
  workers: 1, // 单机本地服务，避免并发干扰
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://127.0.0.1:8000',
    locale: 'zh-CN',
  },
  reporter: [['list']],
})
