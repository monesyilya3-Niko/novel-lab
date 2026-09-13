// ECharts 统一封装：直接使用 echarts 原生 API（弃用 echarts-for-react 包装——
// 其实例化路径在 echarts 6 + Vite 7 组合下静默失败且无报错，自研更可控）。
// 统一主题 / setOption / resize / dispose，其余图表组件继承本组件。
import { useEffect, useMemo, useRef } from 'react'
import * as echarts from 'echarts'
import type { EChartsOption } from 'echarts'
import { chartDefaults } from '../../theme'
import { useThemeMode } from '../../state/ThemeModeContext'

export interface BaseChartProps {
  /** ECharts option（series/data 由调用方传入）。 */
  option: EChartsOption
  /** 图表高度（px），默认 280。 */
  height?: number
  /** 是否在 option 变化时整图重建（默认 true，避免残影）。 */
  notMerge?: boolean
  /** 禁用图表自带的 resize 监听（用于虚拟列表等场景）。 */
  disableResize?: boolean
  /** 加载中占位（可选）。 */
  loading?: boolean
  /** 无障碍标签。 */
  ariaLabel?: string
  style?: React.CSSProperties
}

/**
 * 基础图表组件：统一 initOpts（背景透明 / 字体 / 色板）、setOption、resize。
 * 所有具体图表（RadarChart / BarChart / GaugeChart / PieChart）复用此组件，
 * 保证视觉与交互一致。
 */
export default function BaseChart({
  option,
  height = 280,
  notMerge = true,
  disableResize = false,
  loading = false,
  ariaLabel,
  style,
}: BaseChartProps) {
  const { isDark } = useThemeMode()
  const elRef = useRef<HTMLDivElement>(null)
  const instRef = useRef<echarts.ECharts | null>(null)

  // 合并默认文本样式与色板（随暗色模式联动），调用方 option 优先级更高。
  const merged = useMemo<EChartsOption>(
    () => ({
      color: [...chartDefaults(isDark).color],
      textStyle: chartDefaults(isDark).textStyle,
      ...option,
    }),
    [option, isDark],
  )

  // 初始化 / dispose（仅挂载期执行一次）
  useEffect(() => {
    if (!elRef.current) return
    const inst = echarts.init(elRef.current, undefined, {
      renderer: 'canvas',
      locale: 'ZH',
    })
    instRef.current = inst
    return () => {
      inst.dispose()
      instRef.current = null
    }
  }, [])

  // option / 主题变化 → setOption
  useEffect(() => {
    instRef.current?.setOption(merged, notMerge)
  }, [merged, notMerge])

  // 容器尺寸自适应
  useEffect(() => {
    if (disableResize) return
    const ro = new ResizeObserver(() => instRef.current?.resize())
    if (elRef.current) ro.observe(elRef.current)
    return () => ro.disconnect()
  }, [disableResize])

  // loading 状态
  useEffect(() => {
    if (loading) instRef.current?.showLoading()
    else instRef.current?.hideLoading()
  }, [loading])

  return (
    <div
      ref={elRef}
      role="img"
      aria-label={ariaLabel}
      style={{ width: '100%', height, ...style }}
    />
  )
}
