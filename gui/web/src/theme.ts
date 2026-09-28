// 统一主题色板：MUI theme 与 ECharts 共用（见 DESIGN_gui_workbench §7）。
// 单一数据源，避免图表与组件色值漂移。
// 「墨」设计系统 v2：纸墨质感 + 朱砂点缀 + 双模式（light/dark）。
// 品牌色板定义见 ink.ts，本文件负责 MUI theme 组装。

import { ink, fontStack } from './ink'

export const palette = {
  primary: ink.cinnabar,
  success: ink.teal,
  info: '#3A7CA5',
  error: '#d32f2f',
  warning: ink.gold,
  // 章节打分图：一致性 = 朱砂，质量 = 石青。
  consistency: ink.cinnabar,
  quality: ink.teal,
  // 图表色板（ECharts series 默认取色顺序）——暗色下提高明度保证可读。
  chartSeriesLight: [
    ink.cinnabar,
    ink.teal,
    ink.gold,
    '#3A7CA5',
    '#7B5EA7',
    '#C17C5B',
    '#5B8C5A',
    '#8A8478',
  ] as const,
  chartSeriesDark: [
    '#E57373',
    '#4DB6AC',
    ink.goldBright,
    '#64B5F6',
    '#BA9BC9',
    '#D4A574',
    '#81C784',
    ink.moonSoft,
  ] as const,
} as const

export const chartSeries = (isDark: boolean) =>
  isDark ? palette.chartSeriesDark : palette.chartSeriesLight

// MUI 主题工厂（与 ECharts 共用同一份品牌色）。
export const buildMuiTheme = (isDark: boolean) => ({
  palette: {
    mode: (isDark ? 'dark' : 'light') as 'dark' | 'light',
    primary: { main: palette.primary, dark: ink.cinnabarDeep, light: '#E57373' },
    success: { main: palette.success },
    info: { main: palette.info },
    error: { main: palette.error },
    warning: { main: palette.warning },
    text: {
      primary: isDark ? ink.moonWhite : ink.ink,
      secondary: isDark ? ink.moonSoft : ink.inkSoft,
      disabled: isDark ? '#6B655A' : ink.inkFaint,
    },
    divider: isDark ? ink.nightLine : ink.line,
    background: isDark
      ? { default: ink.night, paper: ink.nightCard }
      : { default: ink.paper, paper: ink.card },
  },
  typography: {
    fontFamily: fontStack.sans,
    h1: { fontFamily: fontStack.serif, fontWeight: 700, letterSpacing: '0.02em' },
    h2: { fontFamily: fontStack.serif, fontWeight: 700, letterSpacing: '0.02em' },
    h3: { fontFamily: fontStack.serif, fontWeight: 600, letterSpacing: '0.02em' },
    h4: { fontFamily: fontStack.serif, fontWeight: 600 },
    h5: { fontFamily: fontStack.serif, fontWeight: 600 },
    h6: { fontFamily: fontStack.serif, fontWeight: 600 },
  },
  shape: { borderRadius: 12 },
  components: {
    MuiCard: {
      styleOverrides: {
        root: {
          border: `1px solid ${isDark ? ink.nightLine : ink.line}`,
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: { backgroundImage: 'none' },
      },
    },
    MuiButton: {
      styleOverrides: {
        root: { textTransform: 'none' as const, fontWeight: 600 },
      },
    },
  },
})

// ECharts 统一文本样式（暗色下用浅字色）。
export const chartTextStyle = (isDark: boolean) => ({
  color: isDark ? ink.moonSoft : ink.inkSoft,
  fontFamily: fontStack.sans,
})

// 图表工具提示 / 图例等共用默认值。
export const chartDefaults = (isDark: boolean) => ({
  textStyle: chartTextStyle(isDark),
  color: [...chartSeries(isDark)],
})
