// 统一主题色板：MUI theme 与 ECharts 共用（见 DESIGN_gui_workbench §7）。
// 单一数据源，避免图表与组件色值漂移。
// P3：双模式（light/dark）——品牌色不变，表面色/文本色随模式切换。

export const palette = {
  primary: '#1976d2',
  success: '#2e7d32',
  info: '#0288d1',
  error: '#d32f2f',
  warning: '#b0a47a',
  // 章节打分图：一致性 = 主色，质量 = 成功绿。
  consistency: '#1976d2',
  quality: '#2e7d32',
  // 图表色板（ECharts series 默认取色顺序）——暗色下提高明度保证可读。
  chartSeriesLight: [
    '#1976d2',
    '#2e7d32',
    '#ed6c02',
    '#9c27b0',
    '#0288d1',
    '#d32f2f',
    '#b0a47a',
    '#00796b',
  ] as const,
  chartSeriesDark: [
    '#64b5f6',
    '#81c784',
    '#ffb74d',
    '#ce93d8',
    '#4fc3f7',
    '#e57373',
    '#cbc28a',
    '#4db6ac',
  ] as const,
} as const

export const chartSeries = (isDark: boolean) =>
  isDark ? palette.chartSeriesDark : palette.chartSeriesLight

// MUI 主题工厂（与 ECharts 共用同一份品牌色）。
export const buildMuiTheme = (isDark: boolean) => ({
  palette: {
    mode: (isDark ? 'dark' : 'light') as 'dark' | 'light',
    primary: { main: palette.primary },
    success: { main: palette.success },
    info: { main: palette.info },
    error: { main: palette.error },
    warning: { main: palette.warning },
    ...(isDark
      ? { background: { default: '#121820', paper: '#1a222d' } }
      : {}),
  },
  typography: {
    fontFamily:
      "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif",
  },
})

// ECharts 统一文本样式（暗色下用浅字色）。
export const chartTextStyle = (isDark: boolean) => ({
  color: isDark ? '#c3cfdd' : '#37474f',
  fontFamily:
    "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif",
})

// 图表工具提示 / 图例等共用默认值。
export const chartDefaults = (isDark: boolean) => ({
  textStyle: chartTextStyle(isDark),
  color: [...chartSeries(isDark)],
})

