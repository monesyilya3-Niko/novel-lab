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

// ---------------------------------------------------------------------------
// W16/W17 阶段二：写作（M2）+ 质检（M3）
// ---------------------------------------------------------------------------

export interface WritingProject {
  id: string
  name: string
  readOnly: boolean
}

export interface InjectResult {
  prompt: string
  charCount: number
  injectedKinds: string[]
  meta: { sourceTitle: string; genre: string; savedPath: string | null }
}

export interface WritingAttempt {
  attempt: number
  consistency: number
  quality: number
  consistencyOk: boolean
  qualityOk: boolean
  issues: string[]
  charCount: number
}

export interface WritingTaskState {
  taskId: string
  status: 'pending' | 'running' | 'scoring' | 'rewriting' | 'done' | 'degraded' | 'error'
  mode: 'llm' | 'no_model'
  chapterNo: number
  attempt?: number
  score?: number | null
  qualityScore?: number | null
  targetScore: number
  passLine: number
  chapterPath?: string | null
  message?: string
  attempts: WritingAttempt[]
  error?: string | null
  // 降级模式额外字段
  prompt?: string
  guideMarkdown?: string
  guidePath?: string
  notice?: string
}

export interface ConsistencyResult {
  score: number
  dims: { voice: number; emotion: number; narration: number; banned: number; imagery: number }
  details: string[]
  radar?: {
    indicators: { name: string; max: number }[]
    series: { name: string; value: number[] }[]
  }
}

export interface QualityCheckResult {
  score: number
  maxScore: number
  verdict: string
  details: string[]
  issues: string[]
}

export interface ScoreResult {
  consistency: ConsistencyResult
  quality: QualityCheckResult
  verdict: string
  passLine: number
}

export interface QcIssue {
  type: string
  severity: 'critical' | 'high' | 'medium' | 'low'
  chapter?: number
  detail: string
}

export interface QcDimension {
  key: string
  label: string
  layer: string
  score: number
  issues: QcIssue[]
}

export interface QcLayer {
  layer: string
  label: string
  score: number
  dimensions: QcDimension[]
}

export interface QualityTaskState {
  taskId: string
  status: 'pending' | 'running' | 'done' | 'error'
  phase: string
  target: string
  verdict: string | null
  totalScore: number | null
  layers: QcLayer[]
  issues: QcIssue[]
  meta: Record<string, unknown>
  reportJson: string | null
  reportMd: string | null
  error: string | null
}

export interface QcReportItem {
  name: string
  path: string
  verdict: string
  totalScore: number | null
  createdAt: string | null
}
