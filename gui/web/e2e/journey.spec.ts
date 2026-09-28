// novel-lab 完整用户旅程 E2E（出版级补强）：
// 分析页导入 → API 验证书已入库 → 未选题材时开始分析禁用。
// 不依赖 LLM。测试跑在隔离服务上（E2E_BASE_URL）。
import { expect, test, request } from '@playwright/test'
import * as fs from 'fs'
import * as path from 'path'
import * as os from 'os'

const TEST_BOOK = 'e2e_journey_test_book'

function makeBookFile(): string {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'e2e-book-'))
  const fp = path.join(dir, `${TEST_BOOK}.txt`)
  const chapters = Array.from({ length: 6 }, (_, i) =>
    `第${i + 1}章 标题${i + 1}\n${'正文内容。'.repeat(100)}\n`
  ).join('\n')
  fs.writeFileSync(fp, chapters, 'utf-8')
  return fp
}

async function bookCount(baseURL: string): Promise<number> {
  const ctx = await request.newContext({ baseURL })
  const r = await ctx.get('/api/overview')
  const j = await r.json()
  await ctx.dispose()
  return j.data.total_books as number
}

test.describe('用户旅程', () => {
  test('分析页上传导入 → 书入库', async ({ page, baseURL }) => {
    const before = await bookCount(baseURL!)
    const fp = makeBookFile()
    await page.goto('/')
    await page.getByRole('button', { name: '分析', exact: true }).first().click()
    const fileInput = page.locator('input[type="file"]').first()
    await expect(fileInput).toBeAttached({ timeout: 10_000 })
    await fileInput.setInputFiles(fp)
    await expect(page.getByText(/导入成功|已导入/).first()).toBeVisible({ timeout: 30_000 })
    // API 验证书已入库
    const after = await bookCount(baseURL!)
    expect(after).toBe(before + 1)
  })

  test('未选题材时开始分析禁用（P0-4）', async ({ page }) => {
    await page.goto('/')
    await page.getByRole('button', { name: '分析', exact: true }).first().click()
    const startBtn = page.getByRole('button', { name: /一键分析/ }).first()
    await expect(startBtn).toBeVisible({ timeout: 10_000 })
    await expect(startBtn).toBeDisabled()
  })
})
