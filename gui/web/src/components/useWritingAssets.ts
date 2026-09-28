// 写作工作台共享的资产选择状态（注入 / 写作两页签共用同一份选择）。
//
// 背景：之前 InjectPanel 与 GeneratePanel 各自维护独立的 voice / genrePack
// state，导致「注入」页签的 InlineGuide 宣称「写作页签生成章节时会自动用上
// 这里选好的资产」与事实不符。现在选择状态上提到 WritingWorkbench，两处
// 下拉读写同一份 state，文案即事实。
import { useState, useEffect, useMemo } from 'react'
import { assetApi } from '../api/client'

export interface AssetOption {
  id: string
  name: string
  kind: string
  /** 题材标识（后端 _make_item / _asset_row_to_item 提供；未知为 undefined） */
  genre?: string
}

export interface GenreMismatch {
  /** 资产 kind：genre_pack / craft / distilled（prose_card 豁免，不参与） */
  kind: string
  label: string
  genre: string
}

export interface WritingAssetSelection {
  assets: AssetOption[]
  distilledAssets: AssetOption[]
  voice: string
  setVoice: (v: string) => void
  genrePack: string
  setGenrePack: (v: string) => void
  craft: string
  setCraft: (v: string) => void
  distilled: string
  setDistilled: (v: string) => void
  proseCard: string
  setProseCard: (v: string) => void
  byKind: (k: string) => AssetOption[]
  genreOf: (id: string) => string | undefined
  voiceGenre?: string
  /** 与后端 writing_service._require_genre_match 同规则的预检：
   * voice 题材已知、且某已选资产题材已知、两者不一致 → 后端会 400。
   * 任一侧题材未知时不警告（后端同样不阻断，避免误伤历史资产）。 */
  mismatches: GenreMismatch[]
}

const KIND_LABEL: Record<string, string> = {
  genre_pack: 'genre-pack（题材规则）',
  craft: 'craft-card（笔法技巧）',
  distilled: '蒸馏规则',
}

export function useWritingAssets(): WritingAssetSelection {
  const [assets, setAssets] = useState<AssetOption[]>([])
  const [distilledAssets, setDistilledAssets] = useState<AssetOption[]>([])
  const [voice, setVoice] = useState('')
  const [genrePack, setGenrePack] = useState('')
  const [craft, setCraft] = useState('')
  const [distilled, setDistilled] = useState('')
  const [proseCard, setProseCard] = useState('')

  useEffect(() => {
    assetApi.list({ limit: 500 })
      .then((j) => {
        const items = ((j as Record<string, unknown>).items ?? []) as AssetOption[]
        setAssets(items)
        // 默认选择策略（2026-09-29）：只有 voice 默认首张；genre_pack / craft /
        // distilled / prose_card 默认空——旧写作页 genre_pack 默认为空，自动携带
        // 首张会凭空制造题材不一致。只有用户明确选择后才在两页签间共享。
        if (!voice) {
          const firstVoice = items.find((a) => a.kind === 'voice')?.id ?? ''
          setVoice(firstVoice)
        }
      })
      .catch(() => setAssets([]))
    // 蒸馏卡按 kind 单独拉取：混在首页列表里会在资产总数超限被分页截断时静默选不到。
    assetApi.list({ kind: 'distilled', limit: 50 })
      .then((j) => {
        const items = ((j as Record<string, unknown>).items ?? []) as AssetOption[]
        setDistilledAssets(items)
      })
      .catch(() => setDistilledAssets([]))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const byKind = (k: string) => assets.filter((a) => a.kind === k)

  const genreOf = (id: string): string | undefined => {
    if (!id) return undefined
    const a = assets.find((x) => x.id === id) ?? distilledAssets.find((x) => x.id === id)
    return a?.genre || undefined
  }

  const voiceGenre = genreOf(voice) || undefined

  const mismatches = useMemo<GenreMismatch[]>(() => {
    if (!voiceGenre) return []
    const out: GenreMismatch[] = []
    const check = (kind: string, id: string) => {
      if (!id) return
      const g = genreOf(id)
      if (g && g !== voiceGenre) out.push({ kind, label: KIND_LABEL[kind] ?? kind, genre: g })
    }
    check('genre_pack', genrePack)
    check('craft', craft)
    check('distilled', distilled)
    // prose_card 豁免：文风卡是风格参照物，允许跨题材选用（后端同理）。
    return out
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [voiceGenre, genrePack, craft, distilled, assets, distilledAssets])

  return {
    assets, distilledAssets,
    voice, setVoice,
    genrePack, setGenrePack,
    craft, setCraft,
    distilled, setDistilled,
    proseCard, setProseCard,
    byKind, genreOf, voiceGenre, mismatches,
  }
}
