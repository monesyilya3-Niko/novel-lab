// 柱状图封装：章节打分对比 / severity 分布等。
import { useMemo } from 'react'
import type { EChartsOption } from 'echarts'
import BaseChart from './BaseChart'

export interface BarSeries {
  name: string
  data: number[]
  /** 系列颜色（默认走全局色板）。 */
  color?: string
}

export interface BarChartProps {
  /** 横轴类目名（如章节名）。 */
  categories: string[]
  /** 系列（可多组柱）。 */
  series: BarSeries[]
  /** 是否堆叠。 */
  stacked?: boolean
  /** 是否横向条形图。 */
  horizontal?: boolean
  /** 高度（px）。 */
  height?: number
  optionOverride?: EChartsOption
}

/** 柱状图：类目 + 系列 → ECharts bar option。 */
export default function BarChart({
  categories,
  series,
  stacked = false,
  horizontal = false,
  height = 280,
  optionOverride,
}: BarChartProps) {
  const option = useMemo<EChartsOption>(() => {
    const base: EChartsOption = {
      tooltip: { trigger: 'axis' },
      legend: stacked ? { bottom: 0, data: series.map((s) => s.name) } : undefined,
      grid: { left: 8, right: 16, top: 24, bottom: 32, containLabel: true },
      xAxis: horizontal
        ? { type: 'value' }
        : { type: 'category', data: categories, axisLabel: { interval: 0, rotate: categories.length > 8 ? 30 : 0 } },
      yAxis: horizontal
        ? { type: 'category', data: categories }
        : { type: 'value' },
      series: series.map((s) => ({
        name: s.name,
        type: 'bar',
        data: s.data,
        stack: stacked ? 'total' : undefined,
        itemStyle: s.color ? { color: s.color } : undefined,
        barMaxWidth: 32,
      })),
    }
    return { ...base, ...optionOverride }
  }, [categories, series, stacked, horizontal, optionOverride])

  return <BaseChart option={option} height={height} ariaLabel="柱状图" />
}
