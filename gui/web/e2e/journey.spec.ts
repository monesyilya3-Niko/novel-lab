// novel-lab 完整用户旅程 E2E（含 P0-4 题材必填链路）。
// 隔离策略：跑在 scripts/e2e_isolated.sh 启动的 rsync 副本服务上（独立端口），
// 每个用例使用唯一书名（e2e_<用例>_<时间戳>），临时上传目录 /tmp/e2e-book-* 在
// 每个用例结束后删除（afterEach），跑完全部删除副本目录 →
// 真实 gui_state/、corpus/、assets/ 零写入，用例之间无交叉污染（单用例级隔离）。
// 无可用 LLM key：模型相关断言只做到"请求被接受 / 被拒绝"的边界；
// 用 dummy 模型（base_url 指向 127.0.0.1:9 黑洞端口）越过"未配置模型"检查，
// 直达题材校验层——外部模型链路本身未实测（见最终验收报告声明）。
import { expect, test, request } from '@playwright/test'
import type { Page } from '@playwright/test'
import * as fs from 'fs'
import * as path from 'path'
import * as os from 'os'

// 本文件创建的临时上传目录：每个用例结束后删除（单用例级文件系统隔离）。
const tempDirs: string[] = []
test.afterEach(() => {
  for (const d of tempDirs.splice(0)) {
    fs.rmSync(d, { recursive: true, force: true })
  }
})

function makeBookFile(name: string): string {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'e2e-book-'))
  tempDirs.push(dir)
  const fp = path.join(dir, `${name}.txt`)
  const chapters = Array.from({ length: 6 }, (_, i) =>
    `第${i + 1}章 标题${i + 1}\n${'正文内容。'.repeat(100)}\n`
  ).join('\n')
  fs.writeFileSync(fp, chapters, 'utf-8')
  return fp
}

function uniqueName(tag: string): string {
  return `e2e_${tag}_${Date.now()}`
}

async function bookCount(baseURL: string): Promise<number> {
  const ctx = await request.newContext({ baseURL })
  const r = await ctx.get('/api/overview')
  const j = await r.json()
  await ctx.dispose()
  return j.data.total_books as number
}

async function fetchGenres(baseURL: string): Promise<string[]> {
  const ctx = await request.newContext({ baseURL })
  const r = await ctx.get('/api/genres')
  const j = await r.json()
  await ctx.dispose()
  return j.data.genres as string[]
}

/** UI 上传导入一本书，返回 book_id（调用方保证书名唯一）。 */
async function importBookViaUI(page: Page, name: string): Promise<string> {
  const fp = makeBookFile(name)
  await page.goto('/')
  await page.getByRole('button', { name: '分析', exact: true }).first().click()
  const fileInput = page.locator('input[type="file"]').first()
  await expect(fileInput).toBeAttached({ timeout: 10_000 })
  const [resp] = await Promise.all([
    page.waitForResponse(
      (r) => r.url().includes('/api/import-upload') && r.request().method() === 'POST',
      { timeout: 30_000 },
    ),
    fileInput.setInputFiles(fp),
  ])
  await expect(page.getByText(/导入成功|已导入/).first()).toBeVisible({ timeout: 30_000 })
  const body = await resp.json()
  return body.data.book_id as string
}

test.describe('用户旅程', () => {
  test('分析页上传导入 → 书入库', async ({ page, baseURL }) => {
    const before = await bookCount(baseURL!)
    const fp = makeBookFile(uniqueName('journey'))
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
})

test.describe('P0-4 题材必填链路', () => {
  // dummy 模型：仅用于越过"未配置外部模型"检查，直达题材校验层。
  // base_url 指向黑洞端口，任何真实调用都会快速失败；写在隔离服务里，不污染真实密钥库。
  test.beforeAll(async ({ request }) => {
    const r = await request.post('/api/models', {
      data: { id: 'e2e-dummy', protocol: 'openai', base_url: 'http://127.0.0.1:9', model_name: 'dummy' },
    })
    expect([200, 409], 'dummy 模型应创建成功或已存在').toContain(r.status())
  })

  test('未选题材时一键分析禁用', async ({ page }) => {
    await importBookViaUI(page, uniqueName('genre_disabled'))
    // 题材下拉出现（书已选中），但未选择时按钮禁用
    await expect(page.getByLabel('题材 *')).toBeVisible({ timeout: 10_000 })
    const startBtn = page.getByRole('button', { name: /一键分析/ }).first()
    await expect(startBtn).toBeVisible()
    await expect(startBtn).toBeDisabled()
  })

  test('题材下拉选项与后端注册表一致', async ({ page, baseURL }) => {
    await importBookViaUI(page, uniqueName('genre_options'))
    // 后端注册表（唯一来源）
    const genres = await fetchGenres(baseURL!)
    expect(genres.length).toBeGreaterThan(0)

    await page.getByLabel('题材 *').click()
    const options = page.getByRole('option')
    await expect(options).toHaveCount(genres.length, { timeout: 10_000 })
    for (const g of genres) {
      await expect(page.getByRole('option', { name: g, exact: true })).toBeVisible()
    }
  })

  test('选择合法题材后一键分析变为可用', async ({ page, baseURL }) => {
    await importBookViaUI(page, uniqueName('genre_select'))
    const genres = await fetchGenres(baseURL!)

    await page.getByLabel('题材 *').click()
    await page.getByRole('option', { name: genres[0], exact: true }).click()
    const startBtn = page.getByRole('button', { name: /一键分析/ }).first()
    await expect(startBtn).toBeEnabled({ timeout: 10_000 })
  })

  test('UI 真点击一键分析 → /api/analyze/full 返回 200 + task_id', async ({ page, baseURL }) => {
    await importBookViaUI(page, uniqueName('genre_click'))
    const genres = await fetchGenres(baseURL!)

    await page.getByLabel('题材 *').click()
    await page.getByRole('option', { name: genres[0], exact: true }).click()
    const startBtn = page.getByRole('button', { name: /一键分析/ }).first()
    await expect(startBtn).toBeEnabled({ timeout: 10_000 })

    // dummy 模型指向黑洞端口：请求被接受（200 + task_id），后台模型调用会失败，
    // 这里只断言"请求被接受"的边界——外部模型链路本身未实测。
    const [resp] = await Promise.all([
      page.waitForResponse(
        (r) => r.url().includes('/api/analyze/full') && r.request().method() === 'POST',
        { timeout: 30_000 },
      ),
      startBtn.click(),
    ])
    expect(resp.status()).toBe(200)
    const body = await resp.json()
    expect(body.code).toBe(0)
    expect(body.data.task_id).toBeTruthy()
  })

  test('非法题材 → 后端 400 未知题材（API）', async ({ page, request }) => {
    const bookId = await importBookViaUI(page, uniqueName('genre_invalid'))
    const r = await request.post('/api/analyze/start', {
      data: { book_id: bookId, genre: '__invalid_genre_xyz__' },
    })
    expect(r.status()).toBe(400)
    const body = await r.json()
    expect(body.message).toContain('未知题材')
  })

  test('合法题材 → 后端接受请求（API）', async ({ page, request, baseURL }) => {
    const bookId = await importBookViaUI(page, uniqueName('genre_valid'))
    const genres = await fetchGenres(baseURL!)

    const r = await request.post('/api/analyze/start', {
      data: { book_id: bookId, genre: genres[0] },
    })
    expect(r.status()).toBe(200)
    const body = await r.json()
    expect(body.code).toBe(0)
    expect(body.data.task_id).toBeTruthy()
  })

  test('题材接口失败时显示错误提示', async ({ page }) => {
    await page.route('**/api/genres', (route) => route.abort())
    await page.goto('/')
    await page.getByRole('button', { name: '分析', exact: true }).first().click()
    await expect(page.getByText('题材列表加载失败，请刷新重试')).toBeVisible({ timeout: 10_000 })
  })
})
