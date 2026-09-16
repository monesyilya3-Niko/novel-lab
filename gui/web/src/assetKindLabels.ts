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

// 后端 snake_case → deepToCamel 后的 camelCase（genre_pack → genrePack）。
// 概览接口的 assetsByKind 键走的就是 camelCase，必须与共享表共用同一份标签。
const CAMEL_TO_SNAKE: Record<string, string> = Object.fromEntries(
  Object.keys(KIND_LABELS).map((k) => [k.replace(/_([a-z])/g, (_, c: string) => c.toUpperCase()), k]),
)

/** 取中文标签；同时接受后端 snake_case 与 deepToCamel 后的 camelCase 键，未知 kind 回退原值。 */
export function kindLabel(kind: string): string {
  const key = CAMEL_TO_SNAKE[kind] ?? kind
  return (KIND_LABELS as Record<string, string>)[key] ?? kind
}
