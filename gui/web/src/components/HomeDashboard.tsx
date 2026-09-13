// 首页仪表盘（M0）：KPI 卡片 + 资产类型分布 + 数据管理入口。
import { useState, useEffect, useMemo } from 'react'
import Box from '@mui/material/Box'
import Grid from '@mui/material/Grid'
import Card from '@mui/material/Card'
import CardContent from '@mui/material/CardContent'
import Typography from '@mui/material/Typography'
import Chip from '@mui/material/Chip'
import Button from '@mui/material/Button'
import Alert from '@mui/material/Alert'
import MenuBookIcon from '@mui/icons-material/MenuBook'
import StyleIcon from '@mui/icons-material/Style'
import ArticleIcon from '@mui/icons-material/Article'
import FolderIcon from '@mui/icons-material/Folder'
import AsyncBoundary from './common/AsyncBoundary'
import { useApp } from '../state/AppContext'
import PieChart from './charts/PieChart'
import type { WorkbenchKey } from '../layout/WorkbenchNav'
import { friendlyError } from '../api/client'

const KIND_LABELS: Record<string, string> = {
  voice: '声线卡',
  structure: '结构观测',
  commercial: '商业观测',
  craft: '笔法卡',
  genrePack: '题材包',
  proseCard: '文风卡',
  trope: '桥段',
  report: '报告',
  book: '语料',
}

export default function HomeDashboard() {
  const { overview, refreshOverview, setWorkbench } = useApp()
  const [loadError, setLoadError] = useState<unknown>(null)

  useEffect(() => {
    refreshOverview()
      .then(() => setLoadError(null))
      .catch((e) => setLoadError(friendlyError(e)))
  }, [refreshOverview])

  const pieData = useMemo(() => {
    if (!overview) return []
    // report/book 是虚拟 kind，已由「报告」「已拆书」卡片单独展示，
    // 不属于「资产类型分布」——计入会让饼图与「资产总数」卡片口径打架。
    return Object.entries(overview.assetsByKind)
      .filter(([k, v]) => v > 0 && k !== 'report' && k !== 'book')
      .map(([k, v]) => ({ name: KIND_LABELS[k] ?? k, value: v }))
  }, [overview])

  const kpis = overview ? [
    { label: '已拆书', value: overview.totalBooks, icon: <MenuBookIcon />, color: 'primary.main' },
    { label: '题材包', value: overview.totalGenrePacks, icon: <StyleIcon />, color: '#9c27b0' },
    { label: '报告', value: overview.totalReports, icon: <ArticleIcon />, color: 'success.main' },
    { label: '资产总数', value: overview.totalAssets, icon: <FolderIcon />, color: 'info.main' },
  ] : []

  const retry = () => {
    setLoadError('')
    refreshOverview().catch((e) => setLoadError(e))
  }

  return (
    <Box sx={{ p: 3, height: '100%', overflow: 'auto' }}>
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
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
        <Typography variant="h6" sx={{ fontWeight: 600 }}>
          项目概览
        </Typography>
        <Chip
          label={overview.modelConfigured ? '模型已配置' : '模型未配置'}
          color={overview.modelConfigured ? 'success' : 'warning'}
          size="small"
        />
      </Box>

      {!overview.modelConfigured && (
        <Alert severity="warning" sx={{ mb: 2 }}>
          尚未配置外部模型，请先运行 model_config.py 配置（PRD Q7）。
        </Alert>
      )}

      <Grid container spacing={2}>
        {kpis.map((k) => (
          <Grid item xs={6} sm={3} key={k.label}>
            <Card variant="outlined">
              <CardContent sx={{ textAlign: 'center', py: 2 }}>
                <Box sx={{ color: k.color, mb: 1 }}>{k.icon}</Box>
                <Typography variant="h5" sx={{ fontWeight: 700 }}>
                  {k.value}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  {k.label}
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>

      <Grid container spacing={2} sx={{ mt: 1 }}>
        <Grid item xs={12} md={5}>
          <Card variant="outlined">
            <CardContent>
              <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 1 }}>
                资产类型分布
              </Typography>
              {pieData.length > 0 ? (
                <PieChart data={pieData} height={300} />
              ) : (
                <Typography variant="body2" color="text.secondary" sx={{ py: 6, textAlign: 'center' }}>
                  暂无资产数据
                </Typography>
              )}
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={7}>
          <Card variant="outlined">
            <CardContent>
              <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 1 }}>
                数据管理入口
              </Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1.5 }}>
                <Button
                  variant="outlined"
                  onClick={() => setWorkbench('analysis' as WorkbenchKey)}
                >
                  去分析拆书
                </Button>
                <Button
                  variant="outlined"
                  onClick={() => setWorkbench('assets' as WorkbenchKey)}
                >
                  浏览资产库
                </Button>
              </Box>
              {overview.recentActivity && overview.recentActivity.length > 0 && (
                <Box sx={{ mt: 2 }}>
                  <Typography variant="caption" color="text.secondary">
                    最近动态
                  </Typography>
                  {overview.recentActivity.map((a, i) => (
                    <Typography key={i} variant="body2" sx={{ mt: 0.5 }}>
                      {a}
                    </Typography>
                  ))}
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
