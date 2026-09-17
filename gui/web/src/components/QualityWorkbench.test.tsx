// 全书质检截断提示回归（终审 M-5 的 GUI 侧补漏 + fix round 1/2）：
// 「列表被砍短」有两种来源，面板都必须说明，且文案里的条数要与屏幕实际渲染行数一致：
//   1) 响应体被截断：book_quality_check 的 issues 最多 issues_limit 条（50），
//      total_issues 是真实总数；
//   2) 仅前端渲染受限：响应没截断，但 issues.length 超过面板行数上限 ISSUE_ROWS（20）。
// 未超行数且未截断时必须保持静默；不得出现「仅显示前 20 条」而屏幕不足 20 行。
import { render, screen, fireEvent } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import QualityWorkbench from './QualityWorkbench'

const { bookMock } = vi.hoisted(() => ({ bookMock: vi.fn() }))

vi.mock('../api/client', () => ({
  friendlyError: (e: unknown) => String(e),
  subscribeTaskEvents: vi.fn(() => () => {}),
  assetApi: { list: vi.fn().mockResolvedValue({ items: [] }) },
  qualityApi: {
    check: vi.fn(),
    book: (...args: unknown[]) => bookMock(...args),
    qc: vi.fn(),
    taskState: vi.fn(),
    reports: vi.fn().mockResolvedValue([]),
  },
}))

// 可视化走 echarts/canvas，与本次断言无关，用桩件替换。
vi.mock('./QcVisuals', () => ({ default: () => null }))

// 面板可渲染的问题行数上限（与 QualityWorkbench.tsx 的 ISSUE_ROWS 对齐）。
const VISIBLE_ROWS = 20

const SEVERITIES = ['critical', 'high', 'medium', 'low'] as const

// 与面板行渲染格式（[severity] type …）对齐，用于数屏幕上真实出现的明细行。
const ISSUE_ROW = /^\[(critical|high|medium|low)\]/

function makeIssues(count: number) {
  return Array.from({ length: count }, (_, i) => ({
    type: i % 2 === 0 ? '重复' : 'AI味',
    severity: SEVERITIES[i % SEVERITIES.length],
    chapter: i + 1,
    detail: `第 ${i + 1} 条问题明细`,
  }))
}

async function runBookQuality(expectedCountText: string) {
  render(<QualityWorkbench />)
  fireEvent.click(screen.getByRole('tab', { name: '全书质检' }))
  fireEvent.change(screen.getByLabelText('章节目录路径'), { target: { value: 'chapters' } })
  fireEvent.click(screen.getByRole('button', { name: '质检' }))
  await screen.findByText(expectedCountText)
}

describe('BookQualityPanel 截断提示', () => {
  beforeEach(() => {
    bookMock.mockReset()
  })

  it('响应被截断（61 条 / 上限 50）时，提示同时给出可见条数与响应上限', async () => {
    bookMock.mockResolvedValue({
      total_chapters: 60,
      total_issues: 61,
      severity: { critical: 0, high: 3, medium: 58 },
      types: {},
      verdict: 'WARN',
      issues: makeIssues(50),
      issues_truncated: true,
      issues_limit: 50,
    })
    await runBookQuality('共 50 个问题')

    const hint = screen.getByText('共 61 条，仅显示前 20 条（响应上限 50 条）')
    expect(hint).toBeInTheDocument()
    // 不得退化成只报响应上限——那正是 fix round 1 要修的错误指引。
    expect(hint).not.toHaveTextContent('仅显示前 50 条')
    // 提示行说的 20 条必须与列表实际渲染行数一致。
    expect(screen.getAllByText(ISSUE_ROW)).toHaveLength(VISIBLE_ROWS)
  })

  it('响应未截断但超过面板行数（30 条）时，仍提示仅显示前 20 条', async () => {
    bookMock.mockResolvedValue({
      total_chapters: 30,
      total_issues: 30,
      severity: { critical: 0, high: 2, medium: 28 },
      types: {},
      verdict: 'WARN',
      issues: makeIssues(30),
      issues_truncated: false,
      issues_limit: 50,
    })
    await runBookQuality('共 30 个问题')

    // 未截断 ⇒ 不得出现「响应上限」字样；但必须说明屏幕只列了 20 条。
    const hint = screen.getByText('共 30 条，仅显示前 20 条')
    expect(hint).toBeInTheDocument()
    expect(hint).not.toHaveTextContent('响应上限')
    expect(screen.getAllByText(ISSUE_ROW)).toHaveLength(VISIBLE_ROWS)
  })

  it('未截断且不超过面板行数（12 条）时，不显示任何提示且 12 行全渲染', async () => {
    bookMock.mockResolvedValue({
      total_chapters: 12,
      total_issues: 12,
      severity: { critical: 0, high: 1, medium: 11 },
      types: {},
      verdict: 'WARN',
      issues: makeIssues(12),
      issues_truncated: false,
      issues_limit: 50,
    })
    await runBookQuality('共 12 个问题')

    expect(screen.queryByText(/仅显示前/)).toBeNull()
    expect(screen.getAllByText(ISSUE_ROW)).toHaveLength(12)
  })

  it('旧后端未返回截断字段且条数未超行数时，同样不显示提示', async () => {
    bookMock.mockResolvedValue({
      total_chapters: 2,
      total_issues: 2,
      severity: { critical: 0, high: 1, medium: 1 },
      types: {},
      verdict: 'WARN',
      issues: makeIssues(2),
    })
    await runBookQuality('共 2 个问题')

    expect(screen.queryByText(/仅显示前/)).toBeNull()
    expect(screen.getAllByText(ISSUE_ROW)).toHaveLength(2)
  })

  it('实收条数不足面板行数时，提示按实际渲染条数给出而非写死 20', async () => {
    bookMock.mockResolvedValue({
      total_chapters: 60,
      total_issues: 61,
      severity: { critical: 0, high: 3, medium: 58 },
      types: {},
      verdict: 'WARN',
      issues: makeIssues(5),
      issues_truncated: true,
      issues_limit: 50,
    })
    await runBookQuality('共 5 个问题')

    const hint = screen.getByText('共 61 条，仅显示前 5 条（响应上限 50 条）')
    expect(hint).toBeInTheDocument()
    expect(screen.getAllByText(ISSUE_ROW)).toHaveLength(5)
  })

  it('旧后端缺截断字段但条数超过行数时，退回实收条数给出提示', async () => {
    bookMock.mockResolvedValue({
      total_chapters: 30,
      severity: { critical: 0, high: 2, medium: 28 },
      types: {},
      verdict: 'WARN',
      issues: makeIssues(30),
    })
    await runBookQuality('共 30 个问题')

    // 缺 total_issues 时必须退回 issues.length，不能渲染成「共 undefined 条」。
    const hint = screen.getByText('共 30 条，仅显示前 20 条')
    expect(hint).toBeInTheDocument()
    expect(screen.getAllByText(ISSUE_ROW)).toHaveLength(VISIBLE_ROWS)
  })
})
