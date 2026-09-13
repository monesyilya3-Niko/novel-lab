import { describe, expect, it } from 'vitest'
import { deepToCamel } from './client'

describe('deepToCamel', () => {
  it('转换顶层与嵌套对象的 snake_case 键', () => {
    const out = deepToCamel<Record<string, unknown>>({
      total_assets: 55,
      assets_by_kind: { prose_card: 32, genre_pack: 1 },
    })
    expect(out).toEqual({
      totalAssets: 55,
      assetsByKind: { proseCard: 32, genrePack: 1 },
    })
  })

  it('透传数组内的对象键转换', () => {
    const out = deepToCamel<unknown[]>([{ book_id: 'bk-1', chapter_index: 3 }])
    expect(out).toEqual([{ bookId: 'bk-1', chapterIndex: 3 }])
  })

  it('不改动原始值类型（number/string/null/Date 外结构）', () => {
    expect(deepToCamel(42)).toBe(42)
    expect(deepToCamel('plain')).toBe('plain')
    expect(deepToCamel(null)).toBeNull()
  })

  it('已是 camelCase 的键保持不变', () => {
    const out = deepToCamel<Record<string, unknown>>({ alreadyCamel: 1, b: { nestedKey: [{}] } })
    expect(out).toEqual({ alreadyCamel: 1, b: { nestedKey: [{}] } })
  })
})
