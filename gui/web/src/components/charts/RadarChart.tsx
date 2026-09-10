// 雷达图封装：多维度能力对比（拆书结果 / 文风 / 一致性维度）。
import { useMemo } from 'react'
import type { EChartsOption } from 'echarts'
import BaseChart from './BaseChart'

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
  const option = useMemo<EChartsOption>(() => {
    const base: EChartsOption = {
      tooltip: { trigger: 'item' },
      legend: { bottom: 0, data: series.map((s) => s.name) },
      radar: {
        indicator: indicators,
        radius: '65%',
        splitArea: { areaStyle: { color: ['rgba(25,118,210,0.03)', 'rgba(25,118,210,0.06)'] } },
      },
      series: [
        {
          type: 'radar',
          data: series.map((s) => ({ name: s.name, value: s.value })),
          symbol: 'circle',
          symbolSize: 4,
          areaStyle: { opacity: 0.15 },
        },
      ],
    }
    return { ...base, ...optionOverride }
  }, [indicators, series, optionOverride])

  return <BaseChart option={option} height={height} ariaLabel="雷达图" />
}
