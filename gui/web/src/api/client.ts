// REST/SSE 客户端封装。统一做 snake_case（后端）↔ camelCase（前端）转换。

import type {
  ApiResponse,
  AssetItem,
  AssetListResult,
  Batch,
  Book,
  BookResults,
  Chapter,
  ChapterScore,
  ModelInfo,
  Overview,
  ProgressEvent,
  ReportItem,
  StatusInfo,
} from '../types'

const BASE = '/api'

// ---------------------------------------------------------------------------
// 字段转换
// ---------------------------------------------------------------------------

function toCamel<T>(obj: Record<string, unknown>): T {
  const out: Record<string, unknown> = {}
  for (const [k, v] of Object.entries(obj)) {
    const key = k.replace(/_([a-z])/g, (_, c: string) => c.toUpperCase())
    out[key] = v
  }
  return out as T
}

function batchFromSnake(b: Record<string, unknown>): Batch {
  return {
    chapterIndex: b.chapter_index as number,
    batchIndex: b.batch_index as number,
    charStart: b.char_start as number,
    charEnd: b.char_end as number,
    text: (b.text ?? '') as string,
    status: (b.status ?? 'pending') as Batch['status'],
  }
}

function chapterFromSnake(c: Record<string, unknown>): Chapter {
  return {
    index: c.index as number,
    title: c.title as string,
    batchCount: c.batch_count as number,
    batches: ((c.batches ?? []) as Record<string, unknown>[]).map(batchFromSnake),
  }
}

function bookFromSnake(b: Record<string, unknown>): Book {
  return {
    bookId: b.book_id as string,
    title: b.title as string,
    sourcePath: b.source_path as string,
    totalChapters: b.total_chapters as number,
    chapters: ((b.chapters ?? []) as Record<string, unknown>[]).map(chapterFromSnake),
  }
}

// ---------------------------------------------------------------------------
// 请求封装
// ---------------------------------------------------------------------------

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  const json = (await res.json()) as ApiResponse<unknown>
  if (json.code !== 0) {
    throw new Error(json.message || `请求失败 (code=${json.code})`)
  }
  return json.data as T
}

// ---------------------------------------------------------------------------
// API
// ---------------------------------------------------------------------------

export async function importBook(path: string, batchSize?: number): Promise<Book> {
  const data = await request<Record<string, unknown>>('POST', '/import', { path, batch_size: batchSize })
  return bookFromSnake(data)
}

export async function getBook(bookId: string): Promise<Book> {
  const data = await request<Record<string, unknown>>('GET', `/book/${bookId}`)
  return bookFromSnake(data)
}

export async function getChapter(bookId: string, idx: number): Promise<Chapter> {
  const data = await request<Record<string, unknown>>('GET', `/book/${bookId}/chapter/${idx}`)
  return {
    index: data.index as number,
    title: data.title as string,
    batchCount: data.batch_count as number,
    text: data.text as string,
    batches: ((data.batches ?? []) as Record<string, unknown>[]).map(batchFromSnake),
  } as Chapter
}

export async function splitBatches(bookId: string, idx: number, batchSize?: number): Promise<Batch[]> {
  const data = await request<Record<string, unknown>[]>('POST', `/book/${bookId}/chapter/${idx}/batch`, { batch_size: batchSize })
  return (data as unknown as Record<string, unknown>[]).map(batchFromSnake)
}

export async function startAnalysis(
  bookId: string,
  genre: string,
  modelId?: string,
  batchSize?: number,
): Promise<{ taskId: string; cursor: string }> {
  return toCamel(await request<Record<string, unknown>>('POST', '/analyze/start', {
    book_id: bookId,
    genre,
    model_id: modelId,
    batch_size: batchSize,
  }))
}

export async function pauseAnalysis(bookId: string): Promise<{ cursor: string }> {
  return toCamel(await request<Record<string, unknown>>('POST', '/analyze/pause', { book_id: bookId }))
}

export async function resumeAnalysis(bookId: string, genre?: string, modelId?: string): Promise<{ cursor: string }> {
  return toCamel(await request<Record<string, unknown>>('POST', '/analyze/resume', {
    book_id: bookId,
    genre,
    model_id: modelId,
  }))
}

export async function retryFailed(bookId: string): Promise<{ retried: number }> {
  return toCamel(await request<Record<string, unknown>>('POST', '/analyze/retry-failed', { book_id: bookId }))
}

export async function getStatus(bookId?: string): Promise<StatusInfo> {
  const q = bookId ? `?book_id=${encodeURIComponent(bookId)}` : ''
  const data = await request<Record<string, unknown>>('GET', `/status${q}`)
  return {
    status: data.status as StatusInfo['status'],
    bookId: data.book_id as string | null,
    cursor: data.cursor as string,
    done: data.done as number,
    total: data.total as number,
  }
}

export async function getModels(): Promise<{ models: ModelInfo[]; anyConfigured: boolean }> {
  const data = await request<Record<string, unknown>>('GET', '/config/models')
  const models = ((data.models ?? []) as Record<string, unknown>[]).map((m) => toCamel<ModelInfo>(m))
  return { models, anyConfigured: data.any_configured as boolean }
}

export async function getAsset(
  bookId: string,
  chapterIndex: number,
  batchIndex: number,
  passName: string,
): Promise<Record<string, unknown>> {
  const q = new URLSearchParams({
    book_id: bookId,
    chapter: String(chapterIndex),
    batch: String(batchIndex),
    pass: passName,
  })
  return request<Record<string, unknown>>('GET', `/asset?${q.toString()}`)
}

// ---------------------------------------------------------------------------
// 阶段一新增 API（概览 / 资产 / 报告 / 拆书结果 / 一键分析）
// ---------------------------------------------------------------------------

function assetItemFromSnake(a: Record<string, unknown>): AssetItem {
  return {
    kind: a.kind as AssetItem['kind'],
    id: a.id as string,
    name: a.name as string,
    path: a.path as string,
    size: a.size as number,
    mtime: a.mtime as number,
    bookId: (a.book_id ?? undefined) as string | undefined,
  }
}

function chapterScoreFromSnake(c: Record<string, unknown>): ChapterScore {
  return {
    chapterIndex: c.chapter_index as number,
    title: c.title as string,
    consistency: c.consistency as number,
    quality: c.quality as number,
  }
}

export async function getOverview(): Promise<Overview> {
  const data = await request<Record<string, unknown>>('GET', '/overview')
  return toCamel<Overview>(data)
}

export async function listAssets(kind?: string, offset = 0, limit = 50): Promise<AssetListResult> {
  const q = new URLSearchParams({ offset: String(offset), limit: String(limit) })
  if (kind) q.set('kind', kind)
  const data = await request<Record<string, unknown>>('GET', `/assets?${q.toString()}`)
  return {
    total: data.total as number,
    items: ((data.items ?? []) as Record<string, unknown>[]).map(assetItemFromSnake),
  }
}

export async function getAssetDetail(kind: string, id: string): Promise<Record<string, unknown>> {
  return request<Record<string, unknown>>('GET', `/assets/${encodeURIComponent(kind)}/${encodeURIComponent(id)}`)
}

export async function listReports(): Promise<ReportItem[]> {
  const data = await request<Record<string, unknown>[]>('GET', '/reports')
  return (data as unknown as Record<string, unknown>[]).map((r) => toCamel<ReportItem>(r))
}

export async function getReport(reportId: string): Promise<{ id: string; name: string; markdown: string }> {
  return request<{ id: string; name: string; markdown: string }>(
    'GET',
    `/reports/${encodeURIComponent(reportId)}`,
  )
}

export async function getBookResults(bookId: string): Promise<BookResults> {
  const data = await request<Record<string, unknown>>('GET', `/book/${bookId}/results`)
  return {
    bookId: data.book_id as string,
    title: data.title as string,
    voiceCard: (data.voice_card ?? {}) as Record<string, unknown>,
    structure: (data.structure ?? {}) as Record<string, unknown>,
    commercial: (data.commercial ?? {}) as Record<string, unknown>,
    craftCard: (data.craft_card ?? {}) as Record<string, unknown>,
    chapterScores: ((data.chapter_scores ?? []) as Record<string, unknown>[]).map(chapterScoreFromSnake),
    reportIds: (data.report_ids ?? []) as string[],
  }
}

export async function getBookScores(bookId: string): Promise<ChapterScore[]> {
  const data = await request<Record<string, unknown>[]>('GET', `/book/${bookId}/scores`)
  return (data as unknown as Record<string, unknown>[]).map(chapterScoreFromSnake)
}

export async function runFullAnalysis(
  bookId: string,
  genre: string,
  modelId?: string,
): Promise<{ taskId: string; cursor: string; status: string }> {
  return toCamel(
    await request<Record<string, unknown>>('POST', '/analyze/full', {
      book_id: bookId,
      genre,
      model_id: modelId,
    }),
  )
}

// ---------------------------------------------------------------------------
// SSE
// ---------------------------------------------------------------------------

export function subscribeEvents(bookId: string | null, onEvent: (e: ProgressEvent) => void): () => void {
  const q = bookId ? `?book_id=${encodeURIComponent(bookId)}` : ''
  const es = new EventSource(`${BASE}/events${q}`)
  es.onmessage = (msg) => {
    try {
      const data = JSON.parse(msg.data) as Record<string, unknown>
      if (data.status === 'connected' || !('status' in data)) return
      onEvent({
        cursor: data.cursor as string,
        chapterIndex: data.chapter_index as number,
        batchIndex: data.batch_index as number,
        status: data.status as ProgressEvent['status'],
        done: data.done as number,
        total: data.total as number,
      })
    } catch {
      // 忽略无法解析的帧
    }
  }
  return () => es.close()
}

// ---------------------------------------------------------------------------
// W16/W17 阶段二：写作（M2）+ 质检（M3）
// ---------------------------------------------------------------------------

/** 递归把 snake_case 键转为 camelCase（含数组和嵌套对象）。 */
export function deepToCamel<T>(obj: unknown): T {
  if (Array.isArray(obj)) return obj.map(deepToCamel) as T
  if (obj !== null && typeof obj === 'object' && !(obj instanceof Date)) {
    const out: Record<string, unknown> = {}
    for (const [k, v] of Object.entries(obj as Record<string, unknown>)) {
      const key = k.replace(/_([a-z])/g, (_, c: string) => c.toUpperCase())
      out[key] = deepToCamel(v)
    }
    return out as T
  }
  return obj as T
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok && res.status >= 500) throw new Error(`HTTP ${res.status}`)
  const json = await res.json().catch(() => ({ code: res.status, message: `HTTP ${res.status}`, data: null }))
  if (json.code !== 0) throw new Error(json.message || `HTTP ${res.status}`)
  return deepToCamel<T>(json.data)
}

async function put<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok && res.status >= 500) throw new Error(`HTTP ${res.status}`)
  const json = await res.json().catch(() => ({ code: res.status, message: `HTTP ${res.status}`, data: null }))
  if (json.code !== 0) throw new Error(json.message || `HTTP ${res.status}`)
  return deepToCamel<T>(json.data)
}

async function del<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { method: 'DELETE' })
  if (!res.ok && res.status >= 500) throw new Error(`HTTP ${res.status}`)
  const json = await res.json().catch(() => ({ code: res.status, message: `HTTP ${res.status}`, data: null }))
  if (json.code !== 0) throw new Error(json.message || `HTTP ${res.status}`)
  return deepToCamel<T>(json.data)
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok && res.status >= 500) throw new Error(`HTTP ${res.status}`)
  const json = await res.json().catch(() => ({ code: res.status, message: `HTTP ${res.status}`, data: null }))
  if (json.code !== 0) throw new Error(json.message || `HTTP ${res.status}`)
  return deepToCamel<T>(json.data)
}

// 写作
export const writingApi = {
  projects: () => get<import('../types').WritingProject[]>('/writing/projects'),
  inject: (body: Record<string, unknown>) => post<import('../types').InjectResult>('/writing/inject', body),
  generate: (body: Record<string, unknown>) => post<import('../types').WritingTaskState>('/writing/generate', body),
  taskState: (taskId: string) => get<import('../types').WritingTaskState>(`/writing/tasks/${taskId}`),
  importChapter: (body: Record<string, unknown>) => post<Record<string, unknown>>('/writing/chapters', body),
  score: (body: Record<string, unknown>) => post<import('../types').ScoreResult>('/writing/score', body),
  assemble: (body: Record<string, unknown>) => post<Record<string, unknown>>('/writing/assemble', body),
  assembleCandidates: () => get<Record<string, unknown>[]>('/writing/assemble-candidates'),
}

// 质检
export const qualityApi = {
  check: (body: Record<string, unknown>) => post<Record<string, unknown>>('/quality/check', body),
  book: (body: Record<string, unknown>) => post<Record<string, unknown>>('/quality/book', body),
  qc: (body: Record<string, unknown>) => post<import('../types').QualityTaskState>('/quality/qc', body),
  taskState: (taskId: string) => get<import('../types').QualityTaskState>(`/quality/tasks/${taskId}`),
  reports: () => get<import('../types').QcReportItem[]>('/quality/reports'),
}

// 系统
export const systemApi = {
  status: () => get<Record<string, unknown>>('/system/status'),
  compliance: (body?: Record<string, unknown>) => post<Record<string, unknown>>('/system/compliance', body ?? {}),
  models: () => get<Record<string, unknown>>('/system/models'),
  settings: () => get<Record<string, unknown>>('/system/settings'),
  updateSettings: (body: Record<string, unknown>) => put<Record<string, unknown>>('/system/settings', body),
  resetSettings: () => post<Record<string, unknown>>('/system/settings/reset'),
}

// 高级分析
export const advancedApi = {
  distillStatus: (genre: string) => get<Record<string, unknown>>(`/advanced/distill/${encodeURIComponent(genre)}`),
  distillRun: (genre: string) => post<Record<string, unknown>>(`/advanced/distill/${encodeURIComponent(genre)}`),
  batchStatus: () => get<Record<string, unknown>>('/advanced/batch-status'),
}

// 模型管理
export const modelApi = {
  list: () => get<Record<string, unknown>>('/models'),
  presets: () => get<Record<string, unknown>>('/models/presets'),
  get: (id: string) => get<Record<string, unknown>>(`/models/${encodeURIComponent(id)}`),
  add: (body: Record<string, unknown>) => post<Record<string, unknown>>('/models', body),
  update: (id: string, body: Record<string, unknown>) => put<Record<string, unknown>>(`/models/${encodeURIComponent(id)}`, body),
  delete: (id: string) => del<Record<string, unknown>>(`/models/${encodeURIComponent(id)}`),
  setKey: (id: string, apiKey: string) => post<Record<string, unknown>>(`/models/${encodeURIComponent(id)}/key`, { api_key: apiKey }),
  test: (id: string) => post<Record<string, unknown>>(`/models/${encodeURIComponent(id)}/test`),
}

// 资产
export const assetApi = {
  list: (params?: { kind?: string; limit?: number; offset?: number }) => {
    const q = new URLSearchParams()
    if (params?.kind) q.set('kind', params.kind)
    if (params?.limit) q.set('limit', String(params.limit))
    if (params?.offset) q.set('offset', String(params.offset))
    const qs = q.toString()
    return get<Record<string, unknown>>(`/assets${qs ? `?${qs}` : ''}`)
  },
  detail: (kind: string, id: string) => get<Record<string, unknown>>(`/assets/${kind}/${encodeURIComponent(id)}`),
  update: (kind: string, id: string, content: Record<string, unknown>) =>
    put<Record<string, unknown>>(`/assets/${kind}/${encodeURIComponent(id)}`, { content }),
  delete: (kind: string, id: string) =>
    del<Record<string, unknown>>(`/assets/${kind}/${encodeURIComponent(id)}`),
}

// SSE：按 task_id 订阅（写作/质检长任务）
export function subscribeTaskEvents(taskId: string, onEvent: (e: Record<string, unknown>) => void): () => void {
  const es = new EventSource(`${BASE}/events?task_id=${encodeURIComponent(taskId)}`)
  es.onmessage = (msg) => {
    try {
      const data = JSON.parse(msg.data) as Record<string, unknown>
      if (data.status === 'connected') return
      onEvent(data)
    } catch {
      // 忽略
    }
  }
  es.onerror = () => {
    // SSE 断线：EventSource 会自动重连，此处仅记录
  }
  return () => es.close()
}
