// 共享 kind 标签表回归：同一张表必须同时服务 snake_case 与 camelCase 两种键。
//
// 后端资产 kind 是 snake_case（prose_card / genre_pack / prose_card_index），
// 而概览接口经 deepToCamel 后 `assetsByKind` 的键变成 camelCase
// （proseCard / genrePack / proseCardIndex）。历史上首页维护了第三份本地表，
// 键为 camelCase 且缺 distilled / proseCardIndex，导致这两类显示原始英文 kind。
import { describe, expect, it } from 'vitest'
import { KIND_LABELS, kindLabel } from './assetKindLabels'

describe('kindLabel', () => {
  it('接受后端 snake_case kind', () => {
    expect(kindLabel('voice')).toBe('声线卡')
    expect(kindLabel('prose_card')).toBe('文风卡')
    expect(kindLabel('genre_pack')).toBe('题材包')
    expect(kindLabel('prose_card_index')).toBe('题材文风卡索引')
    expect(kindLabel('distilled')).toBe('蒸馏规则')
  })

  it('接受 deepToCamel 后的 camelCase kind（概览 assetsByKind 的键）', () => {
    expect(kindLabel('proseCard')).toBe('文风卡')
    expect(kindLabel('genrePack')).toBe('题材包')
    expect(kindLabel('proseCardIndex')).toBe('题材文风卡索引')
    expect(kindLabel('distilled')).toBe('蒸馏规则')
  })

  it('未知 kind 回退原值，不渲染 undefined', () => {
    expect(kindLabel('brand-new-kind')).toBe('brand-new-kind')
    expect(kindLabel('')).toBe('')
  })

  it('共享表覆盖全部 11 个 kind 且无空标签', () => {
    const values = Object.values(KIND_LABELS)
    expect(values).toHaveLength(11)
    expect(values.every((v) => typeof v === 'string' && v.length > 0)).toBe(true)
  })
})
