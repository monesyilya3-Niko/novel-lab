// 分析结果视图（M1/M3）：拆书完成后结果面板 —— 资产卡（非裸 JSON）+ 章节打分图 + 报告 Markdown。
import { lazy, Suspense, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import Box from '@mui/material/Box'
import Grid from '@mui/material/Grid'
import Card from '@mui/material/Card'
import CardContent from '@mui/material/CardContent'
import Typography from '@mui/material/Typography'
import Chip from '@mui/material/Chip'
import Button from '@mui/material/Button'
import Tabs from '@mui/material/Tabs'
import Tab from '@mui/material/Tab'
import Accordion from '@mui/material/Accordion'
import AccordionSummary from '@mui/material/AccordionSummary'
import AccordionDetails from '@mui/material/AccordionDetails'
import CircularProgress from '@mui/material/CircularProgress'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import { useApp } from '../state/AppContext'
import * as api from '../api/client'
const BarChart = lazy(() => import('./charts/BarChart'))
const RadarChart = lazy(() => import('./charts/RadarChart'))
import MarkdownReport from './MarkdownReport'
import { chartSeries, palette } from '../theme'
import { useThemeMode } from '../state/ThemeModeContext'
import { useI18n } from '../state/I18nContext'
import { friendlyError } from '../api/client'

// 资产卡展示（字段级键值对，避免裸 JSON 堆叠）。
function AssetCard({ title, data, color }: { title: string; data: Record<string, unknown>; color: string }) {
  const { t } = useI18n()
  const entries = useMemo(() => {
    if (!data) return []
    return Object.entries(data)
      .filter(([, v]) => v !== null && v !== undefined && v !== '')
      .slice(0, 12)
  }, [data])

  return (
    <Card variant="outlined" sx={{ height: '100%' }}>
      <CardContent sx={{ py: 1.5 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
          <Box sx={{ width: 10, height: 10, borderRadius: '50%', bgcolor: color, mr: 1 }} />
          <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
            {title}
          </Typography>
        </Box>
        {entries.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            {t('analysis_card_empty')}
          </Typography>
        ) : (
          <Box component="dl" sx={{ m: 0 }}>
            {entries.map(([k, v]) => {
              const val =
                typeof v === 'object' ? JSON.stringify(v) : String(v)
              return (
                <Box key={k} sx={{ display: 'flex', gap: 1, mb: 0.5 }}>
                  <Typography
                    component="dt"
                    variant="caption"
                    color="text.secondary"
                    sx={{ minWidth: 72, flexShrink: 0, fontWeight: 600 }}
                  >
                    {k}
                  </Typography>
                  <Typography
                    component="dd"
                    variant="caption"
                    sx={{ m: 0, wordBreak: 'break-word', flex: 1 }}
                  >
                    {val}
                  </Typography>
                </Box>
              )
            })}
          </Box>
        )}
      </CardContent>
    </Card>
  )
}

// 单个报告：加载后以 Markdown 渲染。
function ReportSection({ reportId }: { reportId: string }) {
  const { t } = useI18n()
  const [report, setReport] = useState<{ id: string; name: string; markdown: string } | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let alive = true
    api
      .getReport(reportId)
      .then((r) => {
        if (alive) setReport(r)
      })
      .catch((e) => {
        if (alive) setError((e as Error).message)
      })
    return () => {
      alive = false
    }
  }, [reportId])

  if (error) {
    return (
      <AlertBox severity="error">{t('analysis_report_load_error')}：{error}</AlertBox>
    )
  }
  if (!report) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 3 }}>
        <CircularProgress size={20} />
      </Box>
    )
  }
  return <MarkdownReport title={report.name} markdown={report.markdown} />
}

function ChartSkeleton({ height }: { height: number }) {
  return (
    <Box sx={{ height, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <CircularProgress size={24} />
    </Box>
  )
}

function AlertBox({ severity, children }: { severity: 'error' | 'info' | 'warning'; children: ReactNode }) {
  const color =
    severity === 'error' ? palette.error : severity === 'warning' ? palette.warning : palette.info
  return (
    <Box sx={{ p: 1.5, borderRadius: 1, bgcolor: `${color}15`, color }}>
      <Typography variant="body2">{children}</Typography>
    </Box>
  )
}

type ResultTab = 'overview' | 'scores' | 'reports'

export default function AnalysisResultView() {
  const { t } = useI18n()
  const { isDark } = useThemeMode()
  const series = chartSeries(isDark)
  const { book, bookResults, loadBookResults } = useApp()
  const [tab, setTab] = useState<ResultTab>('overview')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const bookId = book?.bookId ?? null

  // P1-F5：请求竞态守卫——bookId 快速切换时，只有最新请求能写状态。
  // 渲染期重置 loading/error（React 推荐模式，避免 effect 内同步 setState）。
  const [prevBookId, setPrevBookId] = useState(bookId)
  if (bookId !== prevBookId) {
    setPrevBookId(bookId)
    setLoading(true)
    setError('')
  }
  useEffect(() => {
    if (!bookId) return
    let latest = true
    loadBookResults(bookId)
      .catch((e) => {
        if (latest) setError(friendlyError(e))
      })
      .finally(() => {
        if (latest) setLoading(false)
      })
    return () => {
      latest = false
    }
  }, [bookId, loadBookResults])

  const scoreCategories = useMemo(
    () => bookResults?.chapterScores.map((s) => s.title || `${t('analysis_chap_prefix')}${s.chapterIndex}${t('analysis_chap_suffix')}`) ?? [],
    [bookResults, t],
  )

  const barSeries = useMemo(
    () => [
      {
        name: t('analysis_chart_consistency'),
        data: bookResults?.chapterScores.map((s) => s.consistency) ?? [],
        color: palette.consistency,
      },
      {
        name: t('analysis_chart_quality'),
        data: bookResults?.chapterScores.map((s) => s.quality) ?? [],
        color: palette.quality,
      },
    ],
    [bookResults, t],
  )

  // 雷达图：取各章节均分为一个综合能力面。
  const radarIndicators = useMemo(
    () => [
      { name: t('analysis_chart_consistency'), max: 100 },
      { name: t('analysis_chart_quality'), max: 100 },
    ],
    [t],
  )

  const radarSeries = useMemo(() => {
    if (!bookResults || bookResults.chapterScores.length === 0) return []
    const n = bookResults.chapterScores.length
    const avgConsistency = bookResults.chapterScores.reduce((a, s) => a + s.consistency, 0) / n
    const avgQuality = bookResults.chapterScores.reduce((a, s) => a + s.quality, 0) / n
    return [{ name: t('analysis_chart_avg'), value: [Number(avgConsistency.toFixed(1)), Number(avgQuality.toFixed(1))] }]
  }, [bookResults, t])

  if (!bookId) {
    return (
      <Box sx={{ p: 4, textAlign: 'center' }}>
        <Typography color="text.secondary">{t('analysis_no_book_hint')}</Typography>
      </Box>
    )
  }

  if (error) {
    return (
      <Box sx={{ p: 4, textAlign: 'center' }}>
        <Typography color="error" sx={{ mb: 2 }}>{t('analysis_load_failed')}：{error}</Typography>
        <Button variant="outlined" onClick={() => { setError(''); setLoading(true); loadBookResults(bookId).catch((e) => setError(friendlyError(e))).finally(() => setLoading(false)) }}>
          {t('analysis_retry')}
        </Button>
      </Box>
    )
  }

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
        <CircularProgress />
      </Box>
    )
  }

  if (!bookResults || Object.keys(bookResults.voiceCard).length === 0 && Object.keys(bookResults.structure).length === 0) {
    return (
      <Box sx={{ p: 4, textAlign: 'center' }}>
        <Typography variant="h6" sx={{ mb: 1 }}>
          {bookResults?.title ?? book?.title ?? t('analysis_current_book')}
        </Typography>
        <Typography color="text.secondary">{t('analysis_not_generated')}</Typography>
      </Box>
    )
  }

  return (
    <Box sx={{ p: 3, height: '100%', overflow: 'auto' }}>
      <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
        <Typography variant="h6" sx={{ fontWeight: 600 }}>
          {bookResults.title}
        </Typography>
        <Chip label={t('analysis_result_chip')} size="small" color="success" sx={{ ml: 1.5 }} />
      </Box>

      <Tabs value={tab} onChange={(_e, v) => setTab(v as ResultTab)} sx={{ mb: 2 }}>
        <Tab value="overview" label={t('analysis_res_tab_overview')} />
        <Tab value="scores" label={t('analysis_res_tab_scores')} />
        <Tab value="reports" label={t('analysis_res_tab_reports')} />
      </Tabs>

      {tab === 'overview' && (
        <Grid container spacing={2}>
          <Grid item xs={12} md={6}>
            <AssetCard title={t('analysis_card_voice')} data={bookResults.voiceCard} color={series[0]} />
          </Grid>
          <Grid item xs={12} md={6}>
            <AssetCard title={t('analysis_card_structure')} data={bookResults.structure} color={series[1]} />
          </Grid>
          <Grid item xs={12} md={6}>
            <AssetCard title={t('analysis_card_commercial')} data={bookResults.commercial} color={series[2]} />
          </Grid>
          <Grid item xs={12} md={6}>
            <AssetCard title={t('analysis_card_craft')} data={bookResults.craftCard} color={series[3]} />
          </Grid>
        </Grid>
      )}

      {tab === 'scores' && (
        <Grid container spacing={2}>
          {bookResults.chapterScores.length === 0 ? (
            <Grid item xs={12}>
              <AlertBox severity="info">{t('analysis_score_empty')}</AlertBox>
            </Grid>
          ) : (
            <>
              <Grid item xs={12} md={7}>
                <Card variant="outlined">
                  <CardContent>
                    <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 1 }}>
                      {t('analysis_score_bar_title')}
                    </Typography>
                    <Suspense fallback={<ChartSkeleton height={320} />}>
                      <BarChart categories={scoreCategories} series={barSeries} height={320} />
                    </Suspense>
                  </CardContent>
                </Card>
              </Grid>
              <Grid item xs={12} md={5}>
                <Card variant="outlined">
                  <CardContent>
                    <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 1 }}>
                      {t('analysis_score_radar_title')}
                    </Typography>
                    <Suspense fallback={<ChartSkeleton height={320} />}>
                      <RadarChart indicators={radarIndicators} series={radarSeries} height={320} />
                    </Suspense>
                  </CardContent>
                </Card>
              </Grid>
            </>
          )}
        </Grid>
      )}

      {tab === 'reports' && (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          {bookResults.reportIds.length === 0 ? (
            <AlertBox severity="info">{t('analysis_reports_empty')}</AlertBox>
          ) : (
            bookResults.reportIds.map((rid) => (
              <Accordion key={rid} defaultExpanded={bookResults.reportIds.length === 1}>
                <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                  <Typography variant="subtitle2">{t('analysis_report_item')} · {rid}</Typography>
                </AccordionSummary>
                <AccordionDetails>
                  <ReportSection reportId={rid} />
                </AccordionDetails>
              </Accordion>
            ))
          )}
        </Box>
      )}
    </Box>
  )
}
