// QC 报告可视化：12 维总览条形图 + 章节×维度热力图 + 章节问题分布。
// 数据来自 qc 长任务的 taskState.layers（含各维度 raw.perChapter 原始小分）。
import Box from '@mui/material/Box'
import Typography from '@mui/material/Typography'
import Paper from '@mui/material/Paper'
import CircularProgress from '@mui/material/CircularProgress'
import type { EChartsOption } from 'echarts'
import { lazy, Suspense, useMemo } from 'react'
const BaseChart = lazy(() => import('./charts/BaseChart'))
import { useApp } from '../state/AppContext'
import type { QcIssue, QcLayer } from '../types'
import { palette } from '../theme'

// 四层固定配色：品牌色取自 theme.ts 统一色板（单一数据源）；
// L3 橙是分类色（与图表色板第 3 位同源），无对应主题角色，保留字面量。
const LAYER_COLORS: Record<string, string> = {
  L1: palette.primary,
  L2: palette.success,
  L3: '#ed6c02',
  L4: palette.info,
}

// P1-F3：合格线来自系统设置（默认 75），不再硬编码 70。

function ChartFallback() {
  return (
    <Box sx={{ height: 200, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <CircularProgress size={24} />
    </Box>
  )
}

export default function QcVisuals({
  layers = [],
  issues = [],
}: {
  layers?: QcLayer[]
  issues?: QcIssue[]
}) {
  const { qualityPassLine } = useApp()
  // ---- 12 维总览（条形）----
  const barOption = useMemo<EChartsOption | null>(() => {
    const dims = (layers ?? []).flatMap((l) =>
      l.dimensions.map((d) => ({ label: `${l.label}·${d.label}`, score: d.score, layer: l.layer })),
    )
    if (!dims.length) return null
    return {
      tooltip: { trigger: 'axis' },
      grid: { left: 110, right: 40, top: 10, bottom: 30 },
      xAxis: { type: 'value', max: 100 },
      yAxis: {
        type: 'category',
        data: dims.map((d) => d.label).reverse(),
        axisLabel: { fontSize: 11 },
      },
      series: [
        {
          type: 'bar',
          barMaxWidth: 14,
          markLine: {
            symbol: 'none',
            lineStyle: { color: palette.error, type: 'dashed' },
            data: [{ xAxis: qualityPassLine }],
            label: { formatter: `合格线 ${qualityPassLine}`, fontSize: 10 },
          },
          data: dims
            .map((d) => ({
              value: d.score,
              itemStyle: { color: d.score < qualityPassLine ? palette.error : (LAYER_COLORS[d.layer] ?? palette.primary) },
            }))
            .reverse(),
        },
      ],
    }
  }, [layers, qualityPassLine])

  // ---- 章节×维度热力图（仅含有 raw.perChapter 的维度，维度内归一）----
  const heat = useMemo(() => {
    const dims = (layers ?? []).flatMap((l) =>
      (l.dimensions ?? []).map((d) => ({ label: `${l.label}·${d.label}`, raw: d.raw as Record<string, unknown> | undefined })),
    )
    const withPc = dims
      .map((d) => {
        const pc = (d.raw?.perChapter ?? null) as Record<string, number> | null
        if (!pc || !Object.keys(pc).length) return null
        const max = Math.max(...Object.values(pc), 1)
        return { label: d.label, pc, max }
      })
      .filter((x): x is NonNullable<typeof x> => x !== null)
    if (!withPc.length) return null
    const chapters = [...new Set(withPc.flatMap((d) => Object.keys(d.pc)))].sort((a, b) => Number(a) - Number(b))
    // ECharts heatmap data: [xIndex, yIndex, value]
    const data: [number, number, number][] = []
    withPc.forEach((d, y) => {
      for (const [ch, v] of Object.entries(d.pc)) {
        const x = chapters.indexOf(ch)
        if (x >= 0) data.push([x, y, Math.round((v / d.max) * 100)])
      }
    })
    const option: EChartsOption = {
      tooltip: {
        formatter: (p: unknown) => {
          const pt = p as { data: [number, number, number] }
          const dim = withPc[pt.data[1]]
          const ch = chapters[pt.data[0]]
          const rawVal = dim?.pc[ch]
          return `${dim?.label}<br/>第 ${ch} 章：得分率 ${pt.data[2]}%（原始 ${rawVal}）`
        },
      },
      grid: { left: 110, right: 90, top: 10, bottom: 40 },
      xAxis: { type: 'category', data: chapters.map((c) => `第${c}章`), axisLabel: { fontSize: 10 } },
      yAxis: { type: 'category', data: withPc.map((d) => d.label), axisLabel: { fontSize: 11 } },
      visualMap: {
        min: 0,
        max: 100,
        calculable: true,
        orient: 'vertical',
        right: 0,
        top: 'center',
        text: ['得分率高', '低'],
        // 热力图渐变：两端取主题 error/success，中间浅琥珀为渐变过渡色（无主题对应，保留）。
        inRange: { color: [palette.error, '#ffecb3', palette.success] },
      },
      series: [{ type: 'heatmap', data, label: { show: true, fontSize: 10, formatter: (p: unknown) => String((p as { data: [number, number, number] }).data[2]) } }],
    }
    return { option, chapterCount: chapters.length, dimCount: withPc.length }
  }, [layers])

  // ---- 章节问题分布（按严重度堆叠）----
  const issueOption = useMemo<EChartsOption | null>(() => {
    const byChapter = new Map<number, Record<string, number>>()
    for (const i of issues ?? []) {
      if (i.chapter == null) continue
      const rec = byChapter.get(i.chapter) ?? {}
      rec[i.severity] = (rec[i.severity] ?? 0) + 1
      byChapter.set(i.chapter, rec)
    }
    if (!byChapter.size) return null
    const chapters = [...byChapter.keys()].sort((a, b) => a - b)
    // 严重度配色：high/low 取主题 error/warning；critical/medium 为其深/浅变体（语义区分度需要）。
    const severities: Array<{ key: QcIssue['severity']; label: string; color: string }> = [
      { key: 'critical', label: '严重', color: '#b71c1c' },
      { key: 'high', label: '高', color: palette.error },
      { key: 'medium', label: '中', color: '#ed6c02' },
      { key: 'low', label: '低', color: palette.warning },
    ]
    return {
      tooltip: { trigger: 'axis' },
      legend: { bottom: 0, data: severities.map((s) => s.label) },
      grid: { left: 40, right: 20, top: 20, bottom: 60 },
      xAxis: { type: 'category', data: chapters.map((c) => `第${c}章`) },
      yAxis: { type: 'value', minInterval: 1 },
      series: severities.map((s) => ({
        name: s.label,
        type: 'bar' as const,
        stack: 'issues',
        itemStyle: { color: s.color },
        data: chapters.map((c) => byChapter.get(c)?.[s.key] ?? 0),
      })),
    }
  }, [issues])

  if (!barOption) return null

  return (
    <Box>
      <Paper sx={{ p: 2, mb: 2 }}>
        <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 1 }}>
          十二维得分总览（红 = 低于合格线 {qualityPassLine}）
        </Typography>
        <Suspense fallback={<ChartFallback />}><BaseChart option={barOption} height={Math.max(200, 26 * (layers.reduce((n, l) => n + l.dimensions.length, 0) + 2))} ariaLabel="十二维得分总览条形图" notMerge={false} /></Suspense>
      </Paper>

      {heat && (
        <Paper sx={{ p: 2, mb: 2 }}>
          <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 0.5 }}>
            章节 × 维度 得分率热力图
          </Typography>
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
            仅含提供章节粒度的 {heat.dimCount} 个维度；得分为维度内归一（相对该维度各章最高分）。
          </Typography>
          <Suspense fallback={<ChartFallback />}><BaseChart option={heat.option} height={Math.max(180, 34 * heat.dimCount + 70)} ariaLabel="章节维度得分率热力图" notMerge={false} /></Suspense>
        </Paper>
      )}

      {issueOption && (
        <Paper sx={{ p: 2 }}>
          <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 1 }}>
            章节问题分布（按严重度）
          </Typography>
          <Suspense fallback={<ChartFallback />}><BaseChart option={issueOption} height={240} ariaLabel="章节问题分布柱状图" notMerge={false} /></Suspense>
        </Paper>
      )}
    </Box>
  )
}
