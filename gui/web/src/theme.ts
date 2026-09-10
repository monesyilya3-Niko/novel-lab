// 统一主题色板：MUI theme 与 ECharts 共用（见 DESIGN_gui_workbench §7）。
// 单一数据源，避免图表与组件色值漂移。

export const palette = {
  primary: '#1976d2',
  success: '#2e7d32',
  info: '#0288d1',
  error: '#d32f2f',
  warning: '#b0a47a',
  // 章节打分图：一致性 = 主色，质量 = 成功绿。
  consistency: '#1976d2',
  quality: '#2e7d32',
  // 图表色板（ECharts series 默认取色顺序）。
  chartSeries: [
    '#1976d2',
    '#2e7d32',
    '#ed6c02',
    '#9c27b0',
    '#0288d1',
    '#d32f2f',
    '#b0a47a',
    '#00796b',
  ] as const,
} as const

// MUI 主题（与 ECharts 共用同一份色板）。
export const muiThemeOptions = {
  palette: {
    mode: 'light' as const,
    primary: { main: palette.primary },
    success: { main: palette.success },
    info: { main: palette.info },
    error: { main: palette.error },
    warning: { main: palette.warning },
  },
}

// ECharts 统一文本样式。
export const chartTextStyle = {
  color: '#37474f',
  fontFamily:
    "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif",
} as const

// 图表工具提示 / 图例等共用默认值。
export const chartDefaults = {
  textStyle: chartTextStyle,
  color: [...palette.chartSeries],
} as const
