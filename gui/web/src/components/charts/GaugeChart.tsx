// 仪表盘 / 进度环封装：单值进度（一致性总分 / 完成度 / 质检通过率）。
import { useMemo } from 'react'
import type { EChartsOption } from 'echarts'
import BaseChart from './BaseChart'

export interface GaugeChartProps {
  /** 当前值（0-100 或按 max 缩放）。 */
  value: number
  /** 最大值（默认 100）。 */
  max?: number
  /** 标题文本。 */
  title?: string
  /** 单位后缀（如 %）。 */
  unit?: string
  /** 高度（px）。 */
  height?: number
  optionOverride?: EChartsOption
}

/** 仪表盘：单值 → ECharts gauge option。 */
export default function GaugeChart({
  value,
  max = 100,
  title,
  unit = '',
  height = 240,
  optionOverride,
}: GaugeChartProps) {
  const option = useMemo<EChartsOption>(() => {
    const base: EChartsOption = {
      series: [
        {
          type: 'gauge',
          min: 0,
          max,
          startAngle: 210,
          endAngle: -30,
          radius: '90%',
          center: ['50%', '60%'],
          progress: { show: true, width: 12, roundCap: true },
          axisLine: { lineStyle: { width: 12 } },
          axisTick: { show: false },
          splitLine: { length: 8, lineStyle: { width: 1, color: '#999' } },
          axisLabel: { distance: 16, fontSize: 10 },
          pointer: { show: false },
          detail: {
            valueAnimation: true,
            fontSize: 22,
            fontWeight: 'bold',
            offsetCenter: [0, '40%'],
            formatter: (v: number) => `${v}${unit}`,
          },
          title: title ? { offsetCenter: [0, '75%'], fontSize: 13 } : undefined,
          data: [{ value, name: title }],
        },
      ],
    }
    return { ...base, ...optionOverride }
  }, [value, max, title, unit, optionOverride])

  return <BaseChart option={option} height={height} ariaLabel="仪表盘" />
}
