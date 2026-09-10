// 前端类型定义。这里用 camelCase 命名（对齐 TS 习惯），
// 与后端 snake_case JSON 的转换统一在 api/client.ts 中完成。

export type BatchStatus = 'pending' | 'running' | 'success' | 'failed' | 'skipped'

export interface Batch {
  chapterIndex: number
  batchIndex: number
  charStart: number
  charEnd: number
  text: string
  status: BatchStatus
}

export interface Chapter {
  index: number
  title: string
  batchCount: number
  text?: string
  batches: Batch[]
}

export interface Book {
  bookId: string
  title: string
  sourcePath: string
  totalChapters: number
  chapters: Chapter[]
}

export interface BatchState {
  status: BatchStatus
  asset?: string
  ts: number
}

export interface TaskState {
  schemaVersion: number
  bookId: string
  title: string
  stateRevision: number
  cursor: string
  chapterStates: Record<string, BatchState>
  assetIndex: Record<string, string[]>
}

export interface ProgressEvent {
  cursor: string
  chapterIndex: number
  batchIndex: number
  // 后端会推送 running/success/failed（批级）以及 paused/done/error（任务级）。
  status: BatchStatus | 'paused' | 'done' | 'error'
  done: number
  total: number
}

export interface ModelInfo {
  id: string
  modelName: string
  protocol: string
  baseUrl: string
  hasKey: boolean
}

export interface ApiResponse<T> {
  code: number
  data: T
  message: string
}

// 服务端状态机：idle | running | paused | done | error
export type TaskStatus = 'idle' | 'running' | 'paused' | 'done' | 'error'

export interface StatusInfo {
  status: TaskStatus
  bookId: string | null
  cursor: string
  done: number
  total: number
}

// ---------------------------------------------------------------------------
// 阶段一新增类型（工作台可视化，见 DESIGN_gui_workbench §3.4）
// ---------------------------------------------------------------------------

export type AssetKind =
  | 'voice'
  | 'structure'
  | 'commercial'
  | 'craft'
  | 'genre_pack'
  | 'prose_card'
  | 'report'
  | 'book'

export interface AssetItem {
  kind: AssetKind
  id: string
  name: string
  path: string
  size: number
  mtime: number
  bookId?: string
}

export interface Overview {
  totalBooks: number
  totalGenrePacks: number
  totalReports: number
  totalAssets: number
  assetsByKind: Record<string, number>
  modelConfigured: boolean
  recentActivity: string[]
}

export interface ChapterScore {
  chapterIndex: number
  title: string
  consistency: number
  quality: number
}

export interface BookResults {
  bookId: string
  title: string
  voiceCard: Record<string, unknown>
  structure: Record<string, unknown>
  commercial: Record<string, unknown>
  craftCard: Record<string, unknown>
  chapterScores: ChapterScore[]
  reportIds: string[]
}

export interface ReportItem {
  id: string
  name: string
  kind: 'book' | 'craft'
  bookId: string
  size: number
}

export interface AssetListResult {
  total: number
  items: AssetItem[]
}
