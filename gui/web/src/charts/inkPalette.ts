// ECharts 墨色系色板：「墨」设计系统 v3.5。
// 浅色：朱砂为主，辅以石青、鎏金、黛蓝、赭石
// 暗色：月白为基，朱砂/鎏金提亮，保持夜读质感
import { ink } from '../ink'

/** 浅色模式图表色板（按顺序取色） */
export const inkPaletteLight = [
  ink.cinnabar,      // 朱砂红
  ink.teal,          // 石青
  ink.gold,          // 鎏金
  '#3A7CA5',         // 黛蓝
  '#8A6D3B',         // 赭石
  '#6B7F59',         // 苔绿
  '#9B6B9E',         // 紫苑
  '#C17C5B',         // 陶土
] as const

/** 暗色模式图表色板（提亮，保证夜读对比度） */
export const inkPaletteDark = [
  '#E06C5B',         // 亮朱砂
  '#4DB6A0',         // 亮石青
  ink.goldBright,    // 亮金
  '#6BA3C7',         // 亮黛蓝
  '#C9A86A',         // 亮赭石
  '#93B183',         // 亮苔绿
  '#C49AC6',         // 亮紫苑
  '#D69A7B',         // 亮陶土
] as const

export const getInkPalette = (isDark: boolean): readonly string[] =>
  isDark ? inkPaletteDark : inkPaletteLight

/** ECharts 全局文本样式（跟随 MUI 主题） */
export const inkTextStyle = (isDark: boolean) => ({
  color: isDark ? ink.moonSoft : ink.inkSoft,
  fontFamily: '"Noto Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif',
  fontSize: 12,
})

/** 提示框样式（墨纸质感） */
export const inkTooltip = (isDark: boolean) => ({
  backgroundColor: isDark ? ink.nightCard : ink.card,
  borderColor: isDark ? ink.nightLine : ink.line,
  borderWidth: 1,
  textStyle: {
    color: isDark ? ink.moonWhite : ink.ink,
    fontSize: 12,
  },
  extraCssText: 'box-shadow: 0 4px 16px rgba(0,0,0,0.12); border-radius: 8px; padding: 8px 12px;',
})
