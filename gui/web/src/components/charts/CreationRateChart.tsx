// 创作速率与字数统计折线图（ECharts 封装）
import { useMemo } from 'react'
import BaseChart from './BaseChart'
import { useThemeMode } from '../../state/ThemeModeContext'
import { ink } from '../../ink'

export interface DailyStatPoint {
  date: string
  words: number
  chapters?: number
}

export interface CreationRateChartProps {
  data: DailyStatPoint[]
  height?: number
}

export default function CreationRateChart({ data, height = 260 }: CreationRateChartProps) {
  const { isDark } = useThemeMode()

  const option = useMemo(() => {
    const dates = data.map((d) => d.date.slice(5)) // MM-DD
    const words = data.map((d) => d.words)
    // 计算移动速率（字/天平滑）
    const rates = words.map((_, i, arr) => {
      const slice = arr.slice(Math.max(0, i - 2), i + 1)
      const avg = slice.reduce((a, b) => a + b, 0) / slice.length
      return Math.round(avg)
    })

    return {
      tooltip: {
        trigger: 'axis' as const,
        axisPointer: { type: 'cross' as const },
      },
      legend: {
        data: ['每日字数', '平滑速率'],
        top: 0,
        textStyle: { color: isDark ? ink.moonSoft : ink.textSecondary },
      },
      grid: {
        left: '3%',
        right: '4%',
        bottom: '8%',
        top: '16%',
        containLabel: true,
      },
      xAxis: {
        type: 'category' as const,
        data: dates,
        axisLine: { lineStyle: { color: isDark ? ink.nightLine : ink.hairline } },
        axisLabel: { color: isDark ? ink.moonSoft : ink.textTertiary, fontSize: 11 },
      },
      yAxis: [
        {
          type: 'value' as const,
          name: '字数',
          splitLine: { lineStyle: { color: isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.04)' } },
          axisLabel: { color: isDark ? ink.moonSoft : ink.textTertiary, fontSize: 11 },
        },
      ],
      series: [
        {
          name: '每日字数',
          type: 'line' as const,
          smooth: true,
          data: words,
          itemStyle: { color: '#2563EB' },
          areaStyle: {
            color: {
              type: 'linear' as const,
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: 'rgba(37, 99, 235, 0.35)' },
                { offset: 1, color: 'rgba(37, 99, 235, 0.02)' },
              ],
            },
          },
        },
        {
          name: '平滑速率',
          type: 'line' as const,
          smooth: true,
          lineStyle: { width: 2, type: 'dashed' as const },
          itemStyle: { color: '#059669' },
          data: rates,
        },
      ],
    }
  }, [data, isDark])

  return <BaseChart option={option} height={height} />
}
