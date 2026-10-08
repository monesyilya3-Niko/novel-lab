// 桌面版"选择…"按钮的渲染与回填回归（配合 desktopBridge 的桥检测）。
//
// 用户反馈"有些路径放不进去"，其中一部分其实是手打 Windows 路径打错。
// 这里钉住三件事：桌面版才出现按钮、按 tab 传对 kind、取消时不把输入框弄脏。
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const { pickPathMock } = vi.hoisted(() => ({ pickPathMock: vi.fn() }))

vi.mock('../desktopBridge', () => ({
  hasDesktopBridge: () => true,
  pickPath: (kind: string) => pickPathMock(kind),
}))

vi.mock('../api/client', () => ({
  friendlyError: (e: unknown) => String(e),
  subscribeTaskEvents: vi.fn(() => () => {}),
  assetApi: { list: vi.fn().mockResolvedValue({ items: [] }) },
  qualityApi: {
    check: vi.fn(),
    book: vi.fn(),
    qc: vi.fn(),
    taskState: vi.fn(),
    reports: vi.fn().mockResolvedValue([]),
  },
}))

vi.mock('./QcVisuals', () => ({ default: () => null }))

import QualityWorkbench from './QualityWorkbench'

beforeEach(() => {
  pickPathMock.mockReset()
})

describe('质检路径选择器（桌面版）', () => {
  it('单章检查用文件选择器，选中的路径回填进输入框', async () => {
    pickPathMock.mockResolvedValue('C:/稿子/第1章.txt')
    render(<QualityWorkbench />)
    fireEvent.click(screen.getByRole('button', { name: '选择文件…' }))
    await waitFor(() => expect(pickPathMock).toHaveBeenCalledWith('file'))
    await waitFor(() =>
      expect(screen.getByLabelText('章节路径（或粘贴文本）')).toHaveValue('C:/稿子/第1章.txt'),
    )
  })

  it('全书质检用目录选择器', async () => {
    pickPathMock.mockResolvedValue('D:/写作/我的书')
    render(<QualityWorkbench />)
    fireEvent.click(screen.getByRole('tab', { name: '全书质检' }))
    fireEvent.click(screen.getByRole('button', { name: '选择目录…' }))
    await waitFor(() => expect(pickPathMock).toHaveBeenCalledWith('dir'))
    await waitFor(() =>
      expect(screen.getByLabelText('章节目录路径')).toHaveValue('D:/写作/我的书'),
    )
  })

  it('用户取消时不动输入框', async () => {
    pickPathMock.mockResolvedValue(null)
    render(<QualityWorkbench />)
    fireEvent.click(screen.getByRole('button', { name: '选择文件…' }))
    await waitFor(() => expect(pickPathMock).toHaveBeenCalledTimes(1))
    expect(screen.getByLabelText('章节路径（或粘贴文本）')).toHaveValue('')
  })
})
