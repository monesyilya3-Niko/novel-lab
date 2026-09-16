// 资产 kind 的中文标签：资产库分类、高级工作台资产编辑等处共用同一张表，避免两处漂移。
import type { AssetKind } from './types'

export const KIND_LABELS: Record<AssetKind, string> = {
  voice: '声线卡',
  structure: '结构观测',
  commercial: '商业观测',
  craft: '笔法卡',
  genre_pack: '题材包',
  prose_card: '文风卡',
  // 蒸馏卡与题材索引各自独立标签：索引只是题材→卡片文件的寻址表，不是卡片本身。
  distilled: '蒸馏规则',
  prose_card_index: '题材文风卡索引',
  trope: '桥段',
  report: '报告',
  book: '语料',
}

/** 取中文标签；后端返回未知 kind 时回退原值，避免界面渲染出 undefined。 */
export function kindLabel(kind: string): string {
  return (KIND_LABELS as Record<string, string>)[kind] ?? kind
}
