// 全书质检截断提示回归（终审 M-5 的 GUI 侧补漏 + fix round 1）：
// book_quality_check 的 issues 最多 issues_limit 条（50），而 total_issues 是真实总数；
// 面板自己还只渲染前 20 行。三者口径不同，提示行必须同时说清「屏幕可见条数」与
// 「响应上限」，否则会出现「共 61 条，仅显示前 50 条」却只有 20 行明细的错误指引。
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

const SMALL_ISSUES = [
  { type: '重复', severity: 'high', chapter: 1, detail: '与第 1 章高度重合' },
  { type: 'AI味', severity: 'medium', chapter: 2, detail: '句式模板化' },
]

// 截断现场的真实形状：响应体恰好给满 issues_limit 条，真实总数更大。
const TRUNCATED_ISSUES = Array.from({ length: 50 }, (_, i) => ({
  type: i % 2 === 0 ? '重复' : 'AI味',
  severity: i % 3 === 0 ? 'high' : 'medium',
  chapter: i + 1,
  detail: `第 ${i + 1} 条问题明细`,
}))

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

  it('截断时提示行同时给出屏幕可见条数与响应上限', async () => {
    bookMock.mockResolvedValue({
      total_chapters: 60,
      total_issues: 61,
      severity: { critical: 0, high: 3, medium: 58 },
      types: {},
      verdict: 'WARN',
      issues: TRUNCATED_ISSUES,
      issues_truncated: true,
      issues_limit: 50,
    })
    await runBookQuality('共 50 个问题')

    // 完整文案：可见条数（20，面板渲染上限）与响应上限（50）缺一不可。
    const hint = screen.getByText('共 61 条，仅显示前 20 条（响应上限 50 条）')
    expect(hint).toBeInTheDocument()
    // 不得退化成只报响应上限——那正是本轮要修的错误指引。
    expect(hint).not.toHaveTextContent('仅显示前 50 条')
    // 提示行说的 20 条必须与列表实际渲染行数一致。
    expect(screen.getAllByText(/^\[(critical|high|medium|low)\]/)).toHaveLength(VISIBLE_ROWS)
  })

  it('issues_truncated 为假时不显示该提示', async () => {
    bookMock.mockResolvedValue({
      total_chapters: 12,
      total_issues: 2,
      severity: { critical: 0, high: 1, medium: 1 },
      types: {},
      verdict: 'WARN',
      issues: SMALL_ISSUES,
      issues_truncated: false,
      issues_limit: 50,
    })
    await runBookQuality('共 2 个问题')

    expect(screen.queryByText(/仅显示前/)).toBeNull()
  })

  it('旧后端未返回截断字段时同样不显示该提示', async () => {
    bookMock.mockResolvedValue({
      total_chapters: 12,
      total_issues: 2,
      severity: { critical: 0, high: 1, medium: 1 },
      types: {},
      verdict: 'WARN',
      issues: SMALL_ISSUES,
    })
    await runBookQuality('共 2 个问题')

    expect(screen.queryByText(/仅显示前/)).toBeNull()
  })
})
