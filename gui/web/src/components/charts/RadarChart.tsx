// 雷达图封装：多维度能力对比（拆书结果 / 文风 / 一致性维度）。「墨」v3.5 色板。
import { useMemo } from 'react'
import type { EChartsOption } from 'echarts'
import BaseChart from './BaseChart'
import { getInkPalette, inkTextStyle, inkTooltip } from '../../charts/inkPalette'
import { useThemeMode } from '../../state/ThemeModeContext'
import { ink } from '../../ink'

export interface RadarSeries {
  name: string
  value: number[]
}

export interface RadarChartProps {
  /** 雷达图指标名（维度）。 */
  indicators: { name: string; max: number }[]
  /** 系列数据（可多组对比）。 */
  series: RadarSeries[]
  /** 高度（px）。 */
  height?: number
  /** 自定义 option 覆盖（合并到最终 option）。 */
  optionOverride?: EChartsOption
}

/** 雷达图：指标 + 系列 → ECharts radar option。 */
export default function RadarChart({
  indicators,
  series,
  height = 280,
  optionOverride,
}: RadarChartProps) {
  const { isDark } = useThemeMode()
  const option = useMemo<EChartsOption>(() => {
    const palette = getInkPalette(isDark)
    const axisColor = isDark ? ink.nightLine : ink.line
    const base: EChartsOption = {
      color: [...palette],
      tooltip: { trigger: 'item', ...inkTooltip(isDark) },
      legend: {
        bottom: 0,
        data: series.map((s) => s.name),
        textStyle: inkTextStyle(isDark),
        icon: 'circle',
        itemWidth: 8,
        itemHeight: 8,
      },
      radar: {
        indicator: indicators,
        radius: '65%',
        axisName: inkTextStyle(isDark),
        splitLine: { lineStyle: { color: axisColor } },
        splitArea: {
          areaStyle: {
            // 淡蓝晕：交替透明度
            color: ['rgba(37,99,235,0.04)', 'rgba(37,99,235,0.08)'],
          },
        },
        axisLine: { lineStyle: { color: axisColor } },
      },
      series: [
        {
          type: 'radar',
          data: series.map((s) => ({ name: s.name, value: s.value })),
          symbol: 'circle',
          symbolSize: 5,
          lineStyle: { width: 2 },
          areaStyle: { opacity: 0.18 },
          emphasis: { lineStyle: { width: 3 } },
        },
      ],
    }
    return { ...base, ...optionOverride }
  }, [indicators, series, optionOverride, isDark])

  return <BaseChart option={option} height={height} ariaLabel="雷达图" />
}
