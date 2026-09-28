// 柱状图封装：章节打分对比 / severity 分布等。「墨」v3.5 色板。
import { useMemo } from 'react'
import type { EChartsOption } from 'echarts'
import BaseChart from './BaseChart'
import { getInkPalette, inkTextStyle, inkTooltip } from '../../charts/inkPalette'
import { useThemeMode } from '../../state/ThemeModeContext'
import { ink } from '../../ink'

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
  const { isDark } = useThemeMode()
  const option = useMemo<EChartsOption>(() => {
    const palette = getInkPalette(isDark)
    const axisLine = isDark ? ink.nightLine : ink.line
    const base: EChartsOption = {
      color: [...palette],
      tooltip: { trigger: 'axis', ...inkTooltip(isDark) },
      legend: stacked
        ? {
            bottom: 0,
            data: series.map((s) => s.name),
            textStyle: inkTextStyle(isDark),
            icon: 'roundRect',
            itemWidth: 12,
            itemHeight: 8,
          }
        : undefined,
      grid: { left: 8, right: 16, top: 24, bottom: 32, containLabel: true },
      xAxis: horizontal
        ? {
            type: 'value',
            axisLine: { lineStyle: { color: axisLine } },
            axisLabel: inkTextStyle(isDark),
            splitLine: { lineStyle: { color: axisLine, type: 'dashed' } },
          }
        : {
            type: 'category',
            data: categories,
            axisLine: { lineStyle: { color: axisLine } },
            axisLabel: {
              ...inkTextStyle(isDark),
              interval: 0,
              rotate: categories.length > 8 ? 30 : 0,
            },
          },
      yAxis: horizontal
        ? {
            type: 'category',
            data: categories,
            axisLine: { lineStyle: { color: axisLine } },
            axisLabel: inkTextStyle(isDark),
          }
        : {
            type: 'value',
            axisLine: { lineStyle: { color: axisLine } },
            axisLabel: inkTextStyle(isDark),
            splitLine: { lineStyle: { color: axisLine, type: 'dashed' } },
          },
      series: series.map((s, si) => ({
        name: s.name,
        type: 'bar',
        data: s.data,
        stack: stacked ? 'total' : undefined,
        itemStyle: {
          color: s.color ?? palette[si % palette.length],
          borderRadius: [4, 4, 0, 0],
        },
        barMaxWidth: 32,
        emphasis: { itemStyle: { shadowBlur: 8, shadowColor: 'rgba(0,0,0,0.2)' } },
      })),
    }
    return { ...base, ...optionOverride }
  }, [categories, series, stacked, horizontal, optionOverride, isDark])

  return <BaseChart option={option} height={height} ariaLabel="柱状图" />
}
