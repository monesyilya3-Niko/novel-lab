import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import InspirationWorkbench from './InspirationWorkbench'

vi.mock('../api/client', () => ({
  toolsApi: {
    generateNames: vi.fn().mockResolvedValue({
      kind: 'character',
      style: 'xianxia',
      gender: 'all',
      count: 3,
      names: ['林清绝', '陆云深', '苏长生'],
    }),
    getHooks: vi.fn().mockResolvedValue({
      totalCount: 1,
      hooks: [
        {
          id: 'HK-001',
          name: '宗门废柴退婚打脸',
          genre: '仙侠修真',
          first300Words: '寒风呼啸，退婚书扔在脸上。',
          chapter1Beat: '被辱受挫，神秘青铜残片觉醒',
          chapter2Beat: '修复经脉，一夜突破三个境界',
          chapter3Beat: '宗门大比前夕，当众镇压挑衅者',
        },
      ],
    }),
    getGoldfingers: vi.fn().mockResolvedValue({
      totalCount: 1,
      goldfingers: [
        {
          id: 'GF-001',
          name: '神级选择系统',
          category: '系统外挂',
          triggerMechanism: '面临危机或命运抉择时',
          progressionCurve: '初期提供极品功法',
          costAndLimits: ['不可撤回'],
          antiCollapseRule: '奖励梯度严格与当前剧情相称',
        },
      ],
    }),
  },
  friendlyError: (e: unknown) => String(e),
}))

describe('InspirationWorkbench', () => {
  it('渲染起名工坊并显示名称 Chips', async () => {
    render(<InspirationWorkbench />)
    expect(screen.getByText('起名工坊 (离线智能)')).toBeDefined()
    await waitFor(() => {
      expect(screen.getByText('林清绝')).toBeDefined()
      expect(screen.getByText('陆云深')).toBeDefined()
      expect(screen.getByText('苏长生')).toBeDefined()
    })
  })

  it('切换到开篇钩子库', async () => {
    render(<InspirationWorkbench />)
    fireEvent.click(screen.getByText('开篇钩子库 (黄金三章)'))
    await waitFor(() => {
      expect(screen.getByText('宗门废柴退婚打脸')).toBeDefined()
      expect(screen.getByText('寒风呼啸，退婚书扔在脸上。')).toBeDefined()
    })
  })

  it('切换到金手指机制库', async () => {
    render(<InspirationWorkbench />)
    fireEvent.click(screen.getByText('金手指机制库 (12大外挂)'))
    await waitFor(() => {
      expect(screen.getByText('神级选择系统')).toBeDefined()
      expect(screen.getByText('系统外挂')).toBeDefined()
    })
  })
})
