// 首页仪表盘（M0）：「墨」设计系统 v2 重制版。
// 纸墨质感 + 衬线标题 + 交错入场动画 + 悬浮卡片。
import { useState, useEffect, useMemo } from 'react'
import Box from '@mui/material/Box'
import IconButton from '@mui/material/IconButton'
import Tooltip from '@mui/material/Tooltip'
import HelpOutlineIcon from '@mui/icons-material/HelpOutline'
import Grid from '@mui/material/Grid'
import Card from '@mui/material/Card'
import CardContent from '@mui/material/CardContent'
import Typography from '@mui/material/Typography'
import Chip from '@mui/material/Chip'
import CircularProgress from '@mui/material/CircularProgress'
import Alert from '@mui/material/Alert'
import Divider from '@mui/material/Divider'
import MenuBookIcon from '@mui/icons-material/MenuBook'
import StyleIcon from '@mui/icons-material/Style'
import ArticleIcon from '@mui/icons-material/Article'
import FolderIcon from '@mui/icons-material/Folder'
import ArrowForwardIcon from '@mui/icons-material/ArrowForward'
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome'
import AsyncBoundary from './common/AsyncBoundary'
import { useApp } from '../state/AppContext'
import { lazy, Suspense } from 'react'
const PieChart = lazy(() => import('./charts/PieChart'))
import type { WorkbenchKey } from '../layout/WorkbenchNav'
import { friendlyError } from '../api/client'
import { kindLabel } from '../assetKindLabels'
import { ink, cardHover, stagger } from '../ink'
import { useThemeMode } from '../state/ThemeModeContext'
import { useI18n } from '../state/I18nContext'

const CAMEL_TO_SNAKE: Record<string, string> = {
  voice: 'voice',
  structure: 'structure',
  commercial: 'commercial',
  craft: 'craft',
  genrePack: 'genre_pack',
  genre_pack: 'genre_pack',
  proseCard: 'prose_card',
  prose_card: 'prose_card',
  distilled: 'distilled',
  proseCardIndex: 'prose_card_index',
  prose_card_index: 'prose_card_index',
  trope: 'trope',
  report: 'report',
  book: 'book',
}

function getKindLabel(kind: string, t: (k: string, fb?: string) => string): string {
  const snake = CAMEL_TO_SNAKE[kind] ?? kind
  const key = `asset_kind_${snake}`
  const fb = kindLabel(kind)
  return t(key, fb)
}

export default function HomeDashboard() {
  const { overview, refreshOverview, setWorkbench, openHelp } = useApp()
  const { t, locale } = useI18n()
  const [loadError, setLoadError] = useState<unknown>(null)
  const { isDark } = useThemeMode()

  useEffect(() => {
    refreshOverview()
      .then(() => setLoadError(null))
      .catch((e) => setLoadError(friendlyError(e)))
  }, [refreshOverview])

  const pieData = useMemo(() => {
    if (!overview) return []
    return Object.entries(overview.assetsByKind)
      .filter(([k, v]) => v > 0 && k !== 'report' && k !== 'book')
      .map(([k, v]) => ({ name: getKindLabel(k, t), value: v }))
  }, [overview, t])

  const kpis = overview ? [
    { label: t('home_kpi_books'), value: overview.totalBooks, icon: <MenuBookIcon sx={{ fontSize: 28 }} />, accent: ink.cinnabar },
    { label: t('home_kpi_genre_packs'), value: overview.totalGenrePacks, icon: <StyleIcon sx={{ fontSize: 28 }} />, accent: ink.gold },
    { label: t('home_kpi_reports'), value: overview.totalReports, icon: <ArticleIcon sx={{ fontSize: 28 }} />, accent: ink.teal },
    { label: t('home_kpi_assets'), value: overview.totalAssets, icon: <FolderIcon sx={{ fontSize: 28 }} />, accent: '#3A7CA5' },
  ] : []

  const retry = () => {
    setLoadError('')
    refreshOverview().catch((e) => setLoadError(e))
  }

  const accentSoft = (c: string) => `${c}14`

  return (
    <Box sx={{ p: { xs: 2, md: 4 }, height: '100%', overflow: 'auto', maxWidth: 1200, mx: 'auto' }}>
      <AsyncBoundary
        loading={!overview && !loadError}
        error={loadError}
        onRetry={retry}
        empty={!!overview && overview.totalAssets === 0 && overview.totalBooks === 0}
        emptyTitle={t('home_empty_title')}
        emptyHint={t('home_empty_hint')}
        emptyCta={{ label: t('home_empty_cta'), onClick: () => setWorkbench('analysis' as WorkbenchKey) }}
        minHeight={420}
      >
      {overview && (
      <>
      {/* —— 页眉：书卷气标题 —— */}
      <Box sx={{ mb: 3, ...stagger(0) }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 1 }}>
          <Box sx={{
            width: 40, height: 40, borderRadius: 3,
            background: ink.primary,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: '0 4px 12px rgba(16,16,20,0.18)',
          }}>
            <AutoAwesomeIcon sx={{ color: '#fff', fontSize: 22 }} />
          </Box>
          <Box>
            <Typography variant="h5" sx={{ fontWeight: 700, letterSpacing: '0.05em' }}>
              {t('home_brand_title')}
            </Typography>
            <Typography variant="caption" color="text.secondary" sx={{ letterSpacing: '0.2em' }}>
              {t('home_brand_subtitle')}
            </Typography>
          </Box>
          <Box sx={{ flex: 1 }} />
          <Tooltip title={t('home_help_tooltip')}>
            <IconButton size="small" onClick={() => openHelp('start', null)} aria-label={t('home_help_aria')}>
              <HelpOutlineIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <Chip
            label={overview.modelConfigured ? t('home_model_configured') : t('home_model_not_configured')}
            color={overview.modelConfigured ? 'success' : 'warning'}
            size="small"
            sx={{ fontWeight: 600 }}
          />
        </Box>
        <Divider sx={{ mt: 2 }} />
      </Box>

      {!overview.modelConfigured && (
        <Alert severity="warning" sx={{ mb: 3, borderRadius: 3 }}>
          {t('home_model_alert')}
        </Alert>
      )}

      {/* —— KPI 卡片 —— */}
      <Grid container spacing={2.5} sx={{ mb: 3 }}>
        {kpis.map((k, i) => (
          <Grid item xs={6} sm={3} key={k.label} sx={stagger(i + 1)}>
            <Card sx={{ ...cardHover, overflow: 'hidden', position: 'relative' }}>
              <Box sx={{
                position: 'absolute', top: 0, left: 0, right: 0, height: 3,
                background: k.accent,
              }} />
              <CardContent sx={{ py: 2.5, px: 2.5 }}>
                <Box sx={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', mb: 1.5 }}>
                  <Box sx={{
                    width: 44, height: 44, borderRadius: 2.5,
                    background: accentSoft(k.accent), color: k.accent,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                  }}>
                    {k.icon}
                  </Box>
                </Box>
                <Typography
                  variant="h3"
                  sx={{ fontWeight: 700, lineHeight: 1.1, mb: 0.5 }}
                >
                  {k.value}
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ letterSpacing: '0.1em' }}>
                  {k.label}
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>

      <Grid container spacing={2.5}>
        {/* —— 资产分布 —— */}
        <Grid item xs={12} md={5} sx={stagger(5)}>
          <Card sx={{ height: '100%' }}>
            <CardContent sx={{ p: 3 }}>
              <Box sx={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', mb: 1 }}>
                <Typography variant="h6" sx={{ fontWeight: 600 }}>
                  {t('home_asset_dist_title')}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  {locale === 'en-US' ? `Total ${overview.totalAssets} items` : `共 ${overview.totalAssets} 项`}
                </Typography>
              </Box>
              <Divider sx={{ mb: 2 }} />
              {pieData.length > 0 ? (
                <Suspense fallback={<Box sx={{ height: 280, display: 'flex', alignItems: 'center', justifyContent: 'center' }}><CircularProgress size={24} /></Box>}>
                  <PieChart data={pieData} height={280} />
                </Suspense>
              ) : (
                <Box sx={{ py: 8, textAlign: 'center' }}>
                  <Typography variant="body2" color="text.secondary">
                    {t('home_asset_dist_empty')}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {t('home_asset_dist_empty_sub')}
                  </Typography>
                </Box>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* —— 快捷入口 —— */}
        <Grid item xs={12} md={7} sx={stagger(6)}>
          <Card sx={{ height: '100%' }}>
            <CardContent sx={{ p: 3 }}>
              <Typography variant="h6" sx={{ fontWeight: 600, mb: 1 }}>
                {t('home_quick_start_title')}
              </Typography>
              <Divider sx={{ mb: 2.5 }} />
              <Grid container spacing={2}>
                {[
                  { title: t('home_quick_action_analysis_title'), desc: t('home_quick_action_analysis_desc'), key: 'analysis' as WorkbenchKey, accent: ink.cinnabar },
                  { title: t('home_quick_action_assets_title'), desc: t('home_quick_action_assets_desc'), key: 'assets' as WorkbenchKey, accent: ink.teal },
                  { title: t('home_quick_action_writing_title'), desc: t('home_quick_action_writing_desc'), key: 'writing' as WorkbenchKey, accent: ink.gold },
                ].map((a) => (
                  <Grid item xs={12} sm={4} key={a.key}>
                    <Card
                      variant="outlined"
                      onClick={() => setWorkbench(a.key)}
                      sx={{
                        cursor: 'pointer', ...cardHover,
                        borderLeft: `3px solid ${a.accent}`,
                      }}
                    >
                      <CardContent sx={{ p: 2 }}>
                        <Typography variant="subtitle1" sx={{ fontWeight: 700, mb: 0.5 }}>
                          {a.title}
                        </Typography>
                        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1.5 }}>
                          {a.desc}
                        </Typography>
                        <Box sx={{ display: 'flex', alignItems: 'center', color: a.accent, fontSize: 13, fontWeight: 600 }}>
                          {t('home_quick_action_enter')} <ArrowForwardIcon sx={{ fontSize: 16, ml: 0.5 }} />
                        </Box>
                      </CardContent>
                    </Card>
                  </Grid>
                ))}
              </Grid>

              {overview.recentActivity && overview.recentActivity.length > 0 && (
                <Box sx={{ mt: 3 }}>
                  <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1.5, letterSpacing: '0.05em' }}>
                    {t('home_recent_activity_title')}
                  </Typography>
                  <Box sx={{ position: 'relative', pl: 2.5 }}>
                    <Box sx={{
                      position: 'absolute', left: 6, top: 8, bottom: 8, width: 2,
                      background: isDark ? ink.nightLine : ink.line, borderRadius: 1,
                    }} />
                    {overview.recentActivity.slice(0, 5).map((a, i) => (
                      <Box key={i} sx={{ position: 'relative', pb: 1.5 }}>
                        <Box sx={{
                          position: 'absolute', left: -20.5, top: 5, width: 9, height: 9,
                          borderRadius: '50%', background: i === 0 ? ink.cinnabar : ink.inkFaint,
                          border: `2px solid ${isDark ? ink.nightCard : ink.card}`,
                        }} />
                        <Typography variant="body2" sx={{ lineHeight: 1.6 }}>
                          {a}
                        </Typography>
                      </Box>
                    ))}
                  </Box>
                </Box>
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>
      </>
      )}
      </AsyncBoundary>
    </Box>
  )
}
