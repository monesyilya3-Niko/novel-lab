// 全书质检截断提示回归（终审 M-5 的 GUI 侧补漏）：
// book_quality_check 的 issues 最多 issues_limit 条，而 total_issues 是真实总数。
// 面板必须在该差异存在时显式说明；未截断时不得出现这行提示。
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

const ISSUES = [
  { type: '重复', severity: 'high', chapter: 1, detail: '与第 1 章高度重合' },
  { type: 'AI味', severity: 'medium', chapter: 2, detail: '句式模板化' },
]

async function runBookQuality() {
  render(<QualityWorkbench />)
  fireEvent.click(screen.getByRole('tab', { name: '全书质检' }))
  fireEvent.change(screen.getByLabelText('章节目录路径'), { target: { value: 'chapters' } })
  fireEvent.click(screen.getByRole('button', { name: '质检' }))
  await screen.findByText('共 2 个问题')
}

describe('BookQualityPanel 截断提示', () => {
  beforeEach(() => {
    bookMock.mockReset()
  })

  it('issues_truncated 为真时显示真实总数与截断上限', async () => {
    bookMock.mockResolvedValue({
      total_chapters: 12,
      total_issues: 61,
      severity: { critical: 0, high: 3, medium: 58 },
      types: {},
      verdict: 'WARN',
      issues: ISSUES,
      issues_truncated: true,
      issues_limit: 50,
    })
    await runBookQuality()

    expect(await screen.findByText('共 61 条，仅显示前 50 条')).toBeInTheDocument()
  })

  it('issues_truncated 为假时不显示该提示', async () => {
    bookMock.mockResolvedValue({
      total_chapters: 12,
      total_issues: 2,
      severity: { critical: 0, high: 1, medium: 1 },
      types: {},
      verdict: 'WARN',
      issues: ISSUES,
      issues_truncated: false,
      issues_limit: 50,
    })
    await runBookQuality()

    expect(screen.queryByText(/仅显示前/)).toBeNull()
  })

  it('旧后端未返回截断字段时同样不显示该提示', async () => {
    bookMock.mockResolvedValue({
      total_chapters: 12,
      total_issues: 2,
      severity: { critical: 0, high: 1, medium: 1 },
      types: {},
      verdict: 'WARN',
      issues: ISSUES,
    })
    await runBookQuality()

    expect(screen.queryByText(/仅显示前/)).toBeNull()
  })
})
