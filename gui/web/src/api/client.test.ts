import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError, deepToCamel, friendlyError, getOverview } from './client'

// fetch mock 助手：返回 envelope JSON
function mockFetchOnce(payload: unknown, init?: { ok?: boolean; status?: number; json?: boolean }) {
  const ok = init?.ok ?? true
  const status = init?.status ?? 200
  const asJson = init?.json ?? true
  const body = asJson ? JSON.stringify(payload) : '<html>not json</html>'
  return vi.fn().mockResolvedValueOnce({
    ok,
    status,
    json: asJson
      ? () => Promise.resolve(payload)
      : () => Promise.reject(new SyntaxError('not json')),
    text: () => Promise.resolve(body),
  })
}

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn())
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('deepToCamel', () => {
  it('转换顶层与嵌套对象的 snake_case 键', () => {
    const out = deepToCamel<Record<string, unknown>>({
      total_assets: 55,
      assets_by_kind: { prose_card: 32, genre_pack: 1 },
    })
    expect(out).toEqual({
      totalAssets: 55,
      assetsByKind: { proseCard: 32, genrePack: 1 },
    })
  })

  it('透传数组内的对象键转换', () => {
    const out = deepToCamel<unknown[]>([{ book_id: 'bk-1', chapter_index: 3 }])
    expect(out).toEqual([{ bookId: 'bk-1', chapterIndex: 3 }])
  })

  it('不改动原始值类型', () => {
    expect(deepToCamel(42)).toBe(42)
    expect(deepToCamel('plain')).toBe('plain')
    expect(deepToCamel(null)).toBeNull()
  })

  it('已是 camelCase 的键保持不变', () => {
    const out = deepToCamel<Record<string, unknown>>({ alreadyCamel: 1, b: { nestedKey: [{}] } })
    expect(out).toEqual({ alreadyCamel: 1, b: { nestedKey: [{}] } })
  })
})

describe('typedRequest 请求核心', () => {
  it('code=0 时返回 data 并做 camelCase 转换', async () => {
    vi.mocked(fetch).mockImplementationOnce(mockFetchOnce({
      code: 0, data: { total_books: 4, assets_by_kind: { voice: 5 } }, message: '',
    }) as never)
    const ov = await getOverview()
    expect(ov).toEqual({ totalBooks: 4, assetsByKind: { voice: 5 } })
  })

  it('code!=0 时抛 ApiError 并携带后端消息', async () => {
    vi.mocked(fetch).mockImplementationOnce(mockFetchOnce(
      { code: 404, data: null, message: '语料不存在: x' },
      { ok: false, status: 404 },
    ) as never)
    await expect(getOverview()).rejects.toMatchObject({
      name: 'ApiError',
      message: '语料不存在: x',
      code: 404,
    })
  })

  it('非 JSON 响应（崩溃页/代理）翻译为中文 ApiError', async () => {
    vi.mocked(fetch).mockImplementationOnce(mockFetchOnce(null, { json: false, status: 502 }) as never)
    const err = await getOverview().catch((e) => e)
    expect(err).toBeInstanceOf(ApiError)
    expect(err.message).toContain('服务返回异常响应')
    expect(err.message).toContain('502')
  })

  it('网络失败翻译为可读中文', async () => {
    vi.mocked(fetch).mockRejectedValueOnce(new TypeError('Failed to fetch'))
    const err = await getOverview().catch((e) => e)
    expect(friendlyError(err)).toContain('无法连接服务')
  })

  it('超时触发 AbortError 并翻译为中文', async () => {
    vi.useFakeTimers()
    vi.mocked(fetch).mockImplementationOnce(
      (_url, init) => new Promise((_resolve, reject) => {
        init?.signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')))
      }),
    )
    const p = getOverview()
    vi.advanceTimersByTime(31_000)
    const err = await p.catch((e) => e)
    expect(friendlyError(err)).toBe('请求超时，请重试')
    vi.useRealTimers()
  })
})
