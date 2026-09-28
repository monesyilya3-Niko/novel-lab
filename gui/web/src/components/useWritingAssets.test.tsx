// useWritingAssets 回归用例（交接文档待办 ③ 补遗）。
//
// 覆盖：
// 1. 默认选择策略——只有 voice 默认首张；genre_pack / craft / distilled /
//    prose_card 默认空（用户明确选择后才共享，避免凭空制造题材不一致）。
// 2. mismatches 预检与后端 _require_genre_match 同规则：voice 与已选资产题材
//    均已知且不同才警告；任一侧未知不警告；prose_card 豁免。
import { render, screen, act } from '@testing-library/react'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { useWritingAssets } from './useWritingAssets'
import { assetApi } from '../api/client'

vi.mock('../api/client', () => ({
  assetApi: { list: vi.fn() },
}))

const listMock = vi.mocked(assetApi.list)

const ALL = [
  { id: 'v1', name: 'Voice 1', kind: 'voice', genre: 'xianxia' },
  { id: 'g1', name: 'Pack 1', kind: 'genre_pack', genre: 'dushi' },
  { id: 'c1', name: 'Craft 1', kind: 'craft', genre: 'xianxia' },
  { id: 'p1', name: 'Prose 1', kind: 'prose_card', genre: 'kehuan' },
]
const DISTILLED = [{ id: 'd1', name: 'Distilled 1', kind: 'distilled', genre: 'dushi' }]

function Probe() {
  const sel = useWritingAssets()
  return (
    <div>
      <span data-testid="voice">{sel.voice}</span>
      <span data-testid="genrePack">{sel.genrePack}</span>
      <span data-testid="craft">{sel.craft}</span>
      <span data-testid="distilled">{sel.distilled}</span>
      <span data-testid="proseCard">{sel.proseCard}</span>
      <span data-testid="mismatches">{JSON.stringify(sel.mismatches)}</span>
      <button onClick={() => sel.setGenrePack('g1')}>pick-pack</button>
      <button onClick={() => sel.setProseCard('p1')}>pick-prose</button>
    </div>
  )
}

async function renderProbe() {
  listMock.mockImplementation((params?: { kind?: string }) => {
    if (params?.kind === 'distilled') return Promise.resolve({ items: DISTILLED })
    return Promise.resolve({ items: ALL })
  })
  let container: HTMLElement
  await act(async () => {
    const r = render(<Probe />)
    container = r.container
  })
  return container!
}

const text = (container: HTMLElement, id: string) =>
  container.querySelector(`[data-testid="${id}"]`)?.textContent ?? ''

describe('useWritingAssets', () => {
  beforeEach(() => vi.clearAllMocks())

  it('默认：只有 voice 取首张，其余为空', async () => {
    const c = await renderProbe()
    expect(text(c, 'voice')).toBe('v1')
    expect(text(c, 'genrePack')).toBe('')
    expect(text(c, 'craft')).toBe('')
    expect(text(c, 'distilled')).toBe('')
    expect(text(c, 'proseCard')).toBe('')
  })

  it('题材不一致：voice(xianxia) + genre_pack(dushi) → 警告', async () => {
    const c = await renderProbe()
    await act(async () => {
      screen.getByText('pick-pack').click()
    })
    const mm = JSON.parse(text(c, 'mismatches'))
    expect(mm).toHaveLength(1)
    expect(mm[0].kind).toBe('genre_pack')
  })

  it('prose_card 跨题材豁免：不产生警告', async () => {
    const c = await renderProbe()
    await act(async () => {
      screen.getByText('pick-prose').click()
    })
    expect(JSON.parse(text(c, 'mismatches'))).toHaveLength(0)
  })
})
