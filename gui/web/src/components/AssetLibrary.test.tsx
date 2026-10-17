import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import AssetLibrary from './AssetLibrary'
import { I18nProvider } from '../state/I18nContext'
import { writeStorage, removeStorage } from '../safeStorage'

const { listAssetsMock, getAssetDetailMock } = vi.hoisted(() => ({
  listAssetsMock: vi.fn(),
  getAssetDetailMock: vi.fn(),
}))

vi.mock('../api/client', () => ({
  friendlyError: (e: unknown) => String(e),
  listAssets: (...args: unknown[]) => listAssetsMock(...args),
  getAssetDetail: (...args: unknown[]) => getAssetDetailMock(...args),
}))

const MOCK_ASSETS = [
  { id: 'voice-xianni', name: '仙逆王林冷酷果决声线', kind: 'voice', size: 2048, path: 'assets/voice-xianni.json' },
  { id: 'genre-xuanhuan', name: '玄幻脑洞题材包', kind: 'genre_pack', size: 4096, path: 'assets/genre-xuanhuan.json' },
  { id: 'distilled-battle', name: '生死极速战斗蒸馏规则', kind: 'distilled', size: 1024, path: 'assets/distilled-battle.json' },
]

describe('AssetLibrary 资产库组件与双语国际化', () => {
  beforeEach(() => {
    listAssetsMock.mockReset()
    getAssetDetailMock.mockReset()
  })

  it('zh-CN 默认环境下渲染中文标题、全部分类标签、列表与详情', async () => {
    listAssetsMock.mockResolvedValue({ total: 3, items: MOCK_ASSETS })
    getAssetDetailMock.mockResolvedValue({
      summary: '## 核心声线特征\n- 沉稳肃杀：语速极稳\n- 意志如铁：从不犹豫',
      content: { version: '2.0', parameters: { coolness: 0.9 } },
    })

    render(<AssetLibrary />)

    // 标题与分类标签
    expect(screen.getByText('资产库')).toBeInTheDocument()
    expect(screen.getByText('全部')).toBeInTheDocument()
    expect(screen.getByText('声线卡')).toBeInTheDocument()
    expect(screen.getByText('题材包')).toBeInTheDocument()
    expect(screen.getByText('蒸馏规则')).toBeInTheDocument()
    expect(screen.getByText('题材文风卡索引')).toBeInTheDocument()
    expect(screen.getByText('桥段')).toBeInTheDocument()

    // 默认右侧占位说明
    expect(screen.getByText('从左侧选择一个资产查看详情')).toBeInTheDocument()

    // 列表渲染
    await waitFor(() => {
      expect(screen.getByText('仙逆王林冷酷果决声线')).toBeInTheDocument()
      expect(screen.getByText('声线卡 · 2.0 KB')).toBeInTheDocument()
    })

    // 选中第一项
    fireEvent.click(screen.getByText('仙逆王林冷酷果决声线'))

    await waitFor(() => {
      expect(getAssetDetailMock).toHaveBeenCalledWith('voice', 'voice-xianni')
    })

    // 详情区域显示摘要与原始数据折叠入口
    expect(await screen.findByText('核心声线特征')).toBeInTheDocument()
    expect(screen.getByText('沉稳肃杀')).toBeInTheDocument()
    expect(screen.getByText('高级 · 查看原始数据')).toBeInTheDocument()
  })

  it('en-US 国际化环境下渲染英文标题、英文类型标签、英文提示与折叠区', async () => {
    writeStorage('novellab.locale', 'en-US')
    try {
      listAssetsMock.mockResolvedValue({ total: 3, items: MOCK_ASSETS })
      getAssetDetailMock.mockResolvedValue({
        markdown: '# Voice Card Specification\n\n- Cold & Determined: Fast paced dialogue\n- Unyielding Will: Decisive action',
        content: { version: '2.0', parameters: { coolness: 0.9 } },
      })

      render(
        <I18nProvider>
          <AssetLibrary />
        </I18nProvider>
      )

      // 标题与分类标签
      expect(screen.getByText('Asset Library & Matrix')).toBeInTheDocument()
      expect(screen.getByText('All')).toBeInTheDocument()
      expect(screen.getByText('Voice Card')).toBeInTheDocument()
      expect(screen.getByText('Genre Pack')).toBeInTheDocument()
      expect(screen.getByText('Distilled Rule')).toBeInTheDocument()
      expect(screen.getByText('Genre Prose Index')).toBeInTheDocument()
      expect(screen.getByText('Trope')).toBeInTheDocument()

      // 默认右侧占位说明
      expect(screen.getByText('Select an asset from the list to view details')).toBeInTheDocument()

      // 列表渲染（英文次级标签）
      await waitFor(() => {
        expect(screen.getByText('仙逆王林冷酷果决声线')).toBeInTheDocument()
        expect(screen.getByText('Voice Card · 2.0 KB')).toBeInTheDocument()
      })

      // 选中项并加载详情
      fireEvent.click(screen.getByText('仙逆王林冷酷果决声线'))

      await waitFor(() => {
        expect(getAssetDetailMock).toHaveBeenCalledWith('voice', 'voice-xianni')
      })

      expect(await screen.findByText(/Voice Card Specification/)).toBeInTheDocument()

      // 切换分类筛选
      fireEvent.click(screen.getByText('Genre Pack'))
      await waitFor(() => {
        expect(listAssetsMock).toHaveBeenLastCalledWith('genre_pack', 0, 20)
      })
    } finally {
      removeStorage('novellab.locale')
    }
  })

  it('空列表与加载失败状态在双语下的表现', async () => {
    // 1. 空资产
    listAssetsMock.mockResolvedValue({ total: 0, items: [] })
    const { unmount } = render(<AssetLibrary />)
    await screen.findByText('暂无资产')
    unmount()

    // 2. 英文空资产
    writeStorage('novellab.locale', 'en-US')
    try {
      const { unmount: unmountEn } = render(
        <I18nProvider>
          <AssetLibrary />
        </I18nProvider>
      )
      await screen.findByText('No assets found')
      unmountEn()

      // 3. 加载失败提示
      listAssetsMock.mockRejectedValue(new Error('Network offline'))
      render(
        <I18nProvider>
          <AssetLibrary />
        </I18nProvider>
      )
      await screen.findByText('Failed to load assets: Error: Network offline')
    } finally {
      removeStorage('novellab.locale')
    }
  })
})
