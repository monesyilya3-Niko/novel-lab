// 饼图 / 环形图封装：资产类型分布等占比可视化。
import { useMemo } from 'react'
import type { EChartsOption } from 'echarts'
import BaseChart from './BaseChart'

export interface PieSlice {
  name: string
  value: number
}

export interface PieChartProps {
  /** 数据切片。 */
  data: PieSlice[]
  /** 是否环形图（donut）。 */
  donut?: boolean
  /** 高度（px）。 */
  height?: number
  optionOverride?: EChartsOption
}

/** 饼图：切片 → ECharts pie option。 */
export default function PieChart({ data, donut = true, height = 280, optionOverride }: PieChartProps) {
  const option = useMemo<EChartsOption>(() => {
    const base: EChartsOption = {
      tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
      legend: { bottom: 0, orient: 'horizontal' },
      series: [
        {
          type: 'pie',
          radius: donut ? ['40%', '68%'] : '70%',
          center: ['50%', '46%'],
          avoidLabelOverlap: true,
          itemStyle: { borderRadius: 4, borderColor: '#fff', borderWidth: 1 },
          label: { show: true, formatter: '{b}\n{d}%' },
          data,
        },
      ],
    }
    return { ...base, ...optionOverride }
  }, [data, donut, optionOverride])

  return <BaseChart option={option} height={height} ariaLabel="饼图" />
}
