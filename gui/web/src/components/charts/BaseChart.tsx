// ECharts 统一封装：主题 / initOpts / notMerge / resize 处理。
// 内部包裹 ReactECharts，收敛图表初始化差异，其余图表组件继承本组件。
import React, { useMemo } from 'react'
import ReactECharts from 'echarts-for-react'
import type { EChartsOption } from 'echarts'
import { chartDefaults } from '../../theme'

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
 * 基础图表组件：统一 initOpts（背景透明 / 字体 / 色板）、notMerge、resize。
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
  // 合并默认文本样式与色板，调用方 option 优先级更高。
  const merged = useMemo<EChartsOption>(
    () => ({
      color: [...chartDefaults.color],
      textStyle: chartDefaults.textStyle,
      ...option,
    }),
    [option],
  )

  return (
    <div role="img" aria-label={ariaLabel} style={{ width: '100%', ...style }}>
      <ReactECharts
        option={merged}
        notMerge={notMerge}
        lazyUpdate
        showLoading={loading}
        style={{ height, width: '100%' }}
        opts={{
          renderer: 'canvas',
          locale: 'ZH',
        }}
        {...(disableResize ? {} : { autoResize: true })}
      />
    </div>
  )
}
