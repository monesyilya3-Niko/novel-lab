// 情绪起伏波形图（Emotion Tension Wave Chart）
import { useMemo } from 'react'
import BaseChart from './BaseChart'
import { useThemeMode } from '../../state/ThemeModeContext'
import { ink } from '../../ink'

export interface EmotionWaveChartProps {
  tensionPoints?: number[] // 0-100 的张力值列表
  benchmarkPoints?: number[] // 可选：神作标杆张力基准曲线（重叠对比）
  benchmarkName?: string
  labels?: string[]
  height?: number
}

const DEFAULT_WAVE = [30, 45, 40, 65, 55, 85, 92, 70, 88, 95, 60]
const DEFAULT_LABELS = ['开端', '伏笔', '微冲突', '试探', '积蓄', '爆发', '高潮', '喘息', '反扑', '决胜', '留白']

export default function EmotionWaveChart({
  tensionPoints = DEFAULT_WAVE,
  benchmarkPoints,
  benchmarkName = '神作标杆基准',
  labels = DEFAULT_LABELS,
  height = 240,
}: EmotionWaveChartProps) {
  const { isDark } = useThemeMode()

  const option = useMemo(() => {
    const hasBenchmark = Boolean(benchmarkPoints && benchmarkPoints.length > 0)
    return {
      tooltip: {
        trigger: 'axis' as const,
        formatter: (params: any) => {
          const list = Array.isArray(params) ? params : [params]
          const header = list[0]?.name || ''
          const lines = list.map((p: any) => `${p.marker} ${p.seriesName}: <b>${p.value}</b> / 100`).join('<br/>')
          return `${header}<br/>${lines}`
        },
      },
      legend: {
        show: hasBenchmark,
        top: 0,
        right: 10,
        textStyle: { color: isDark ? ink.moonSoft : ink.textSecondary, fontSize: 11 },
      },
      grid: {
        left: '3%',
        right: '4%',
        bottom: '8%',
        top: hasBenchmark ? '18%' : '12%',
        containLabel: true,
      },
      xAxis: {
        type: 'category' as const,
        boundaryGap: false,
        data: labels,
        axisLine: { lineStyle: { color: isDark ? ink.nightLine : ink.hairline } },
        axisLabel: { color: isDark ? ink.moonSoft : ink.textTertiary, fontSize: 11 },
      },
      yAxis: {
        type: 'value' as const,
        min: 0,
        max: 100,
        splitLine: { lineStyle: { color: isDark ? 'rgba(255,255,255,0.05)' : 'rgba(0,0,0,0.04)' } },
        axisLabel: { color: isDark ? ink.moonSoft : ink.textTertiary, fontSize: 11 },
      },
      series: [
        {
          name: hasBenchmark ? '当前章节' : '情绪张力',
          type: 'line' as const,
          smooth: 0.35,
          symbol: 'circle',
          symbolSize: 6,
          itemStyle: { color: '#E11D48' },
          lineStyle: { width: 3, color: '#E11D48' },
          areaStyle: {
            color: {
              type: 'linear' as const,
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: 'rgba(225, 29, 72, 0.45)' },
                { offset: 0.7, color: 'rgba(225, 29, 72, 0.12)' },
                { offset: 1, color: 'rgba(225, 29, 72, 0.01)' },
              ],
            },
          },
          markLine: {
            symbol: 'none' as const,
            data: [
              {
                yAxis: 80,
                name: '高潮警戒线',
                lineStyle: { color: '#D97706', type: 'dashed' as const },
                label: { formatter: '高潮阈值 80', position: 'insideEndTop' as const, fontSize: 10 },
              },
            ],
          },
          data: tensionPoints,
        },
        ...(hasBenchmark && benchmarkPoints ? [{
          name: benchmarkName,
          type: 'line' as const,
          smooth: 0.35,
          symbol: 'diamond',
          symbolSize: 5,
          itemStyle: { color: '#0284C7' },
          lineStyle: { width: 2, type: 'dashed' as const, color: '#0284C7' },
          data: benchmarkPoints,
        }] : []),
      ],
    }
  }, [tensionPoints, benchmarkPoints, benchmarkName, labels, isDark])

  return <BaseChart option={option} height={height} />
}
