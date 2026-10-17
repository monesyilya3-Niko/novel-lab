// 首页资产类型分布标签回归（M-7）：
// 首页曾维护第三份本地 KIND_LABELS（键为 camelCase、缺 distilled / proseCardIndex），
// 于是「蒸馏规则」「题材文风卡索引」在饼图里显示成原始英文 kind。
// 这里锁定：概览接口的 camelCase 键必须渲染成与共享表一致的中文标签，且不得出现 undefined。
import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import HomeDashboard from './HomeDashboard'
import { KIND_LABELS, kindLabel } from '../assetKindLabels'
import { ThemeModeProvider } from '../state/ThemeModeContext'
import { I18nProvider } from '../state/I18nContext'
import { writeStorage, removeStorage } from '../safeStorage'

// HomeDashboard 依赖 useThemeMode，测试需包裹 Provider。
// ThemeModeProvider 内部用 window.matchMedia，jsdom 无此 API，先 mock。
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  }),
})

const renderDashboard = () => render(
  <ThemeModeProvider>
    <HomeDashboard />
  </ThemeModeProvider>
)

// 后端 snake_case 经 deepToCamel 后的真实形状（见 api/client.test.ts）。
const OVERVIEW = {
  totalBooks: 3,
  totalGenrePacks: 1,
  totalReports: 2,
  totalAssets: 9,
  assetsByKind: {
    voice: 2,
    craft: 1,
    genrePack: 1,
    proseCard: 1,
    distilled: 2,
    proseCardIndex: 1,
    report: 1,
  },
  modelConfigured: true,
  recentActivity: [],
}

vi.mock('../api/client', () => ({
  friendlyError: (e: unknown) => String(e),
}))

vi.mock('../state/AppContext', () => ({
  useApp: () => ({
    overview: OVERVIEW,
    refreshOverview: vi.fn().mockResolvedValue(undefined),
    setWorkbench: vi.fn(),
  }),
}))

// 用桩件替代 echarts 饼图，直接暴露传给图表的切片名，避免依赖 canvas。
vi.mock('./charts/PieChart', () => ({
  default: ({ data }: { data: { name: string; value: number }[] }) => (
    <div data-testid="pie-slices">{data.map((d) => `${d.name}=${d.value}`).join('|')}</div>
  ),
}))

describe('HomeDashboard 资产类型分布标签', () => {
  it('camelCase 键渲染为共享表中的中文标签', async () => {
    renderDashboard()

    const slices = (await screen.findByTestId('pie-slices')).textContent ?? ''
    expect(slices).toContain(`${KIND_LABELS.prose_card}=1`)
    expect(slices).toContain(`${KIND_LABELS.genre_pack}=1`)
    expect(slices).toContain(`${KIND_LABELS.distilled}=2`)
    expect(slices).toContain(`${KIND_LABELS.prose_card_index}=1`)
    expect(slices).toContain(`${KIND_LABELS.voice}=2`)
  })

  it('不得把原始英文 kind 或 undefined 渲染进图例', async () => {
    renderDashboard()

    const slices = (await screen.findByTestId('pie-slices')).textContent ?? ''
    expect(slices).not.toContain('undefined')
    for (const raw of ['distilled', 'proseCardIndex', 'proseCard', 'genrePack']) {
      expect(slices).not.toContain(`${raw}=`)
    }
  })

  it('与共享 kindLabel 对同一批键给出完全一致的标签', async () => {
    renderDashboard()

    const slices = (await screen.findByTestId('pie-slices')).textContent ?? ''
    for (const [camelKey, value] of Object.entries(OVERVIEW.assetsByKind)) {
      if (camelKey === 'report' || camelKey === 'book') continue
      expect(slices).toContain(`${kindLabel(camelKey)}=${value}`)
    }
  })
})

describe('HomeDashboard 双语国际化支持', () => {
  it('en-US 环境下全量渲染英文标题、KPI卡片、饼图切片与快捷入口', async () => {
    writeStorage('novellab.locale', 'en-US')
    try {
      render(
        <I18nProvider>
          <ThemeModeProvider>
            <HomeDashboard />
          </ThemeModeProvider>
        </I18nProvider>
      )

      // 品牌标题与副标题
      expect(screen.getByText('Exoscribe Studio')).toBeInTheDocument()
      expect(screen.getByText('Bilingual Narrative Exoskeleton & Writing Engine')).toBeInTheDocument()
      expect(screen.getByText('Model Configured')).toBeInTheDocument()
      expect(screen.getByLabelText('Quick Start')).toBeInTheDocument()

      // 四大 KPI 卡片
      expect(screen.getByText('Deconstructed Books')).toBeInTheDocument()
      expect(screen.getByText('Genre Packs')).toBeInTheDocument()
      expect(screen.getByText('Analysis Reports')).toBeInTheDocument()
      expect(screen.getByText('Total Assets')).toBeInTheDocument()

      // 资产分布标题与统计
      expect(screen.getByText('Asset Distribution')).toBeInTheDocument()
      expect(screen.getByText('Total 9 items')).toBeInTheDocument()

      // 饼图切片英文标签
      const slices = (await screen.findByTestId('pie-slices')).textContent ?? ''
      expect(slices).toContain('Voice Card=2')
      expect(slices).toContain('Craft Card=1')
      expect(slices).toContain('Genre Pack=1')
      expect(slices).toContain('Prose Card=1')
      expect(slices).toContain('Distilled Rule=2')
      expect(slices).toContain('Genre Prose Index=1')

      // 快捷操作入口卡片
      expect(screen.getByText('Start Writing')).toBeInTheDocument()
      expect(screen.getByText('Deconstruct')).toBeInTheDocument()
      expect(screen.getByText('Import TXT & full-pipeline deconstruction')).toBeInTheDocument()
      expect(screen.getByText('Asset Matrix')).toBeInTheDocument()
      expect(screen.getByText('Browse genre packs & craft cards')).toBeInTheDocument()
      expect(screen.getByText('Immersion Studio')).toBeInTheDocument()
      expect(screen.getByText('3-Column Workspace · AI Copilot')).toBeInTheDocument()
      expect(screen.getAllByText(/Enter/)).toHaveLength(3)
    } finally {
      removeStorage('novellab.locale')
    }
  })
})
