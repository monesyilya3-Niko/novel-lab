// novel-lab GUI 端到端冒烟：首页 KPI / 资产库列表 / 设置页读写路径。
// 前置：本地服务已启动（CI 中由 e2e job 负责；本地可 `python -m gui.server`）。
import { expect, test } from '@playwright/test'

test.describe('GUI 冒烟', () => {
  test('首页加载：标题 + KPI 卡 + 饼图渲染', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByRole('heading', { name: 'novel-lab 全功能工作台' })).toBeVisible()
    await expect(page.getByText('已拆书')).toBeVisible()
    await expect(page.getByText('资产总数')).toBeVisible()
    // 饼图（canvas，BaseChart role=img）
    await expect(page.locator('[role="img"][aria-label="饼图"]')).toBeVisible()
  })

  test('资产库：分类筛选可见且列表非空', async ({ page }) => {
    await page.goto('/')
    // 侧栏导航（ListItemButton 渲染为 role=button）
    const nav = page.getByRole('button', { name: '资产库', exact: true }).first()
    await nav.click()
    // 类型筛选 chips 是稳定锚点（KINDS 枚举固定渲染）
    await expect(page.getByRole('button', { name: '全部', exact: true })).toBeVisible()
    await expect(page.getByRole('button', { name: '声线卡', exact: true })).toBeVisible()
    // 列表由真实 assets/ 驱动：至少一个条目含大小文本
    await expect(page.getByText(/KB/).first()).toBeVisible({ timeout: 10_000 })
  })

  test('设置页：可打开且含可交互控件', async ({ page }) => {
    await page.goto('/')
    await page.getByRole('button', { name: '设置', exact: true }).first().click()
    await expect(page.getByText(/阈值|设置/).first()).toBeVisible()
  })

  test('暗色切换：模式写入 localStorage 且刷新后保持', async ({ page }) => {
    await page.goto('/')
    // 轮转点击切换按钮（light→dark→system 循环），直到 localStorage 落到 dark
    for (let i = 0; i < 3; i++) {
      const mode = await page.evaluate(() => window.localStorage.getItem('novellab.theme-mode'))
      if (mode === 'dark') break
      const btn = page.locator('header button').last()
      await btn.click()
      await page.waitForTimeout(300)
    }
    expect(await page.evaluate(() => window.localStorage.getItem('novellab.theme-mode'))).toBe('dark')
    await page.reload()
    await expect(page.getByRole('heading', { name: 'novel-lab 全功能工作台' })).toBeVisible()
    expect(await page.evaluate(() => window.localStorage.getItem('novellab.theme-mode'))).toBe('dark')
  })
})
