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
import { ink, fontStack, cardHover, stagger } from '../ink'
import { useThemeMode } from '../state/ThemeModeContext'

export default function HomeDashboard() {
  const { overview, refreshOverview, setWorkbench, openHelp } = useApp()
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
      .map(([k, v]) => ({ name: kindLabel(k), value: v }))
  }, [overview])

  const kpis = overview ? [
    { label: '已拆书', value: overview.totalBooks, icon: <MenuBookIcon sx={{ fontSize: 28 }} />, accent: ink.cinnabar },
    { label: '题材包', value: overview.totalGenrePacks, icon: <StyleIcon sx={{ fontSize: 28 }} />, accent: ink.gold },
    { label: '报告', value: overview.totalReports, icon: <ArticleIcon sx={{ fontSize: 28 }} />, accent: ink.teal },
    { label: '资产总数', value: overview.totalAssets, icon: <FolderIcon sx={{ fontSize: 28 }} />, accent: '#3A7CA5' },
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
        emptyTitle="还没有任何书籍数据"
        emptyHint="从「分析」页导入一本 TXT 开始拆书"
        emptyCta={{ label: '去分析拆书', onClick: () => setWorkbench('analysis' as WorkbenchKey) }}
        minHeight={420}
      >
      {overview && (
      <>
      {/* —— 页眉：书卷气标题 —— */}
      <Box sx={{ mb: 3, ...stagger(0) }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 1 }}>
          <Box sx={{
            width: 40, height: 40, borderRadius: 3,
            background: `linear-gradient(135deg, ${ink.cinnabar}, ${ink.cinnabarDeep})`,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: '0 4px 12px rgba(199,62,58,0.3)',
          }}>
            <AutoAwesomeIcon sx={{ color: '#fff', fontSize: 22 }} />
          </Box>
          <Box>
            <Typography variant="h5" sx={{ fontFamily: fontStack.serif, fontWeight: 700, letterSpacing: '0.05em' }}>
              墨 韵 工 作 台
            </Typography>
            <Typography variant="caption" color="text.secondary" sx={{ letterSpacing: '0.2em' }}>
              NOVEL-LAB · 网文创作辅助系统
            </Typography>
          </Box>
          <Box sx={{ flex: 1 }} />
          <Tooltip title="新手上路：从这里开始">
            <IconButton size="small" onClick={() => openHelp('start', null)} aria-label="新手上路">
              <HelpOutlineIcon fontSize="small" />
            </IconButton>
          </Tooltip>
          <Chip
            label={overview.modelConfigured ? '模型已配置' : '模型未配置'}
            color={overview.modelConfigured ? 'success' : 'warning'}
            size="small"
            sx={{ fontWeight: 600 }}
          />
        </Box>
        <Divider sx={{ mt: 2 }} />
      </Box>

      {!overview.modelConfigured && (
        <Alert severity="warning" sx={{ mb: 3, borderRadius: 3 }}>
          尚未配置外部模型，请先运行 model_config.py 配置。
        </Alert>
      )}

      {/* —— KPI 卡片 —— */}
      <Grid container spacing={2.5} sx={{ mb: 3 }}>
        {kpis.map((k, i) => (
          <Grid item xs={6} sm={3} key={k.label} sx={stagger(i + 1)}>
            <Card sx={{ ...cardHover, overflow: 'hidden', position: 'relative' }}>
              <Box sx={{
                position: 'absolute', top: 0, left: 0, right: 0, height: 3,
                background: `linear-gradient(90deg, ${k.accent}, transparent)`,
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
                  sx={{ fontFamily: fontStack.serif, fontWeight: 700, lineHeight: 1.1, mb: 0.5 }}
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
                <Typography variant="h6" sx={{ fontFamily: fontStack.serif, fontWeight: 600 }}>
                  资产类型分布
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  共 {overview.totalAssets} 项
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
                    暂无资产数据
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    拆书分析后自动生成
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
              <Typography variant="h6" sx={{ fontFamily: fontStack.serif, fontWeight: 600, mb: 1 }}>
                开始创作
              </Typography>
              <Divider sx={{ mb: 2.5 }} />
              <Grid container spacing={2}>
                {[
                  { title: '分析拆书', desc: '导入 TXT，全链路拆解', key: 'analysis' as WorkbenchKey, accent: ink.cinnabar },
                  { title: '资产库', desc: '浏览题材包与笔法卡', key: 'assets' as WorkbenchKey, accent: ink.teal },
                  { title: '辅助写作', desc: '注入资产，AI 伴写', key: 'writing' as WorkbenchKey, accent: ink.gold },
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
                          进入 <ArrowForwardIcon sx={{ fontSize: 16, ml: 0.5 }} />
                        </Box>
                      </CardContent>
                    </Card>
                  </Grid>
                ))}
              </Grid>

              {overview.recentActivity && overview.recentActivity.length > 0 && (
                <Box sx={{ mt: 3 }}>
                  <Typography variant="subtitle2" sx={{ fontWeight: 700, mb: 1.5, letterSpacing: '0.05em' }}>
                    最近动态
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
