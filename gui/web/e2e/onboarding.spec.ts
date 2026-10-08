// 空库首启引导 E2E：OnboardingWizard 在「无书籍 + 无资产 + 未标记 onboarded」时出现。
//
// 运行要求：必须跑在空库的隔离服务上（单文件独占一次隔离服务）：
//   bash scripts/e2e_isolated.sh e2e/onboarding.spec.ts
// 若与 journey 等导入书籍的用例共享同一服务，库非空时本文件自动 skip
// （用例内先查 /api/overview 做前置断言），避免 flaky。
import { expect, test, request } from '@playwright/test'

test.beforeEach(async ({ page, baseURL }) => {
  const api = await request.newContext({ baseURL })
  const resp = await api.get('/api/overview')
  const body = await resp.json()
  await api.dispose()
  // 注意：Playwright 的 request 是原生 JSON（snake_case），前端 client.ts 才做
  // camelCase 转换——这里必须用后端的 total_books / total_assets。
  test.skip(
    body?.data?.total_books !== 0 || body?.data?.total_assets !== 0,
    '需要空库（total_books/total_assets 均为 0），请单独隔离运行本文件',
  )
  // 全新浏览器上下文 localStorage 为空 → onboarded 未标记（Playwright 默认每用例新上下文）
  await page.goto('/')
})

test('空库首访显示引导向导，三步走完后不再出现', async ({ page }) => {
  // 步骤 1：欢迎
  await expect(page.getByText('欢迎使用暮冬念春')).toBeVisible({ timeout: 15_000 })
  await page.getByRole('button', { name: '下一步' }).click()

  // 步骤 2：导入并拆书（CTA 为「去导入」，点击进入下一步）
  await expect(page.getByText('第一步：导入并拆书')).toBeVisible({ timeout: 10_000 })
  await page.getByRole('button', { name: '去导入' }).click()

  // 步骤 3：完成
  await expect(page.getByRole('button', { name: '开始使用' })).toBeVisible({ timeout: 10_000 })
  await page.getByRole('button', { name: '开始使用' }).click()

  // 向导关闭且已持久化标记
  await expect(page.getByText('欢迎使用暮冬念春')).toBeHidden({ timeout: 10_000 })
  const flag = await page.evaluate(() => window.localStorage.getItem('novellab.onboarded'))
  expect(flag).toBe('1')

  // 刷新后不再弹出
  await page.reload()
  await expect(page.getByText('欢迎使用暮冬念春')).toBeHidden({ timeout: 15_000 })
})

test('空库首访可随时跳过引导', async ({ page }) => {
  await expect(page.getByText('欢迎使用暮冬念春')).toBeVisible({ timeout: 15_000 })
  await page.getByRole('button', { name: '跳过' }).click()
  await expect(page.getByText('欢迎使用暮冬念春')).toBeHidden({ timeout: 10_000 })
  const flag = await page.evaluate(() => window.localStorage.getItem('novellab.onboarded'))
  expect(flag).toBe('1')
})
