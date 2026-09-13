// M5 系统与合规工作台：系统状态 / 版权合规 / 模型配置 / 设置。
import { useState, useEffect } from 'react'
import Box from '@mui/material/Box'
import Tabs from '@mui/material/Tabs'
import Tab from '@mui/material/Tab'
import Typography from '@mui/material/Typography'
import Button from '@mui/material/Button'
import Paper from '@mui/material/Paper'
import Alert from '@mui/material/Alert'
import CircularProgress from '@mui/material/CircularProgress'
import Chip from '@mui/material/Chip'
import { systemApi } from '../api/client'
import ModelManager from './ModelManager'
import { friendlyError } from '../api/client'

export default function SystemWorkbench() {
  const [tab, setTab] = useState(0)
  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ borderBottom: 1, borderColor: 'divider', px: 2 }}>
        <Tab label="系统状态" />
        <Tab label="版权合规" />
        <Tab label="模型配置" />
        <Tab label="设置" />
      </Tabs>
      <Box sx={{ flex: 1, overflow: 'auto', p: 2 }}>
        {tab === 0 && <SystemStatusPanel />}
        {tab === 1 && <CompliancePanel />}
        {tab === 2 && <ModelManager />}
        {tab === 3 && <SettingsPanel />}
      </Box>
    </Box>
  )
}

// ---------------------------------------------------------------------------
// 系统状态
// ---------------------------------------------------------------------------

function SystemStatusPanel() {
  const [status, setStatus] = useState<Record<string, unknown> | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = async () => {
    setLoading(true)
    setError('')
    try {
      const data = await systemApi.status()
      setStatus(data as Record<string, unknown>)
    } catch (e) {
      setError(friendlyError(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  if (loading) return <CircularProgress />
  if (error) return <Alert severity="error">{error}</Alert>
  if (!status) return null

  const disk = status.disk as Record<string, number>
  const counts = status.counts as Record<string, unknown>
  const model = status.model as Record<string, unknown>
  const paths = status.paths as Record<string, string>

  const fmtSize = (bytes: number) => {
    if (bytes > 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`
    if (bytes > 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${bytes} B`
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2 }}>
        <Typography variant="h6">系统状态</Typography>
        <Button variant="outlined" size="small" onClick={load}>刷新</Button>
      </Box>

      <Paper sx={{ p: 2, mb: 2 }}>
        <Typography variant="subtitle2" gutterBottom>磁盘占用</Typography>
        <Typography variant="body2">资产：{fmtSize(Number(disk.assetsBytes ?? 0))} | 报告：{fmtSize(Number(disk.reportsBytes ?? 0))}</Typography>
        <Typography variant="body2">语料：{fmtSize(Number(disk.corpusBytes ?? 0))} | 写作：{fmtSize(Number(disk.novelBytes ?? 0))}</Typography>
        <Typography variant="body2">数据库：{fmtSize(Number(disk.dbBytes ?? 0))} | 总计：{fmtSize(Number(disk.totalBytes ?? 0))}</Typography>
      </Paper>

      <Paper sx={{ p: 2, mb: 2 }}>
        <Typography variant="subtitle2" gutterBottom>数据统计</Typography>
        <Typography variant="body2">
          资产 {String(counts.assets ?? 0)} 个 | 报告 {String(counts.reports ?? 0)} 份 | 已拆书 {((counts.bookNames ?? counts.book_names ?? []) as string[]).length} 本
        </Typography>
        <Typography variant="body2" color="text.secondary">
          {((counts.bookNames ?? counts.book_names ?? []) as string[]).join('、')}
        </Typography>
      </Paper>

      <Paper sx={{ p: 2, mb: 2 }}>
        <Typography variant="subtitle2" gutterBottom>模型状态</Typography>
        <Chip label={model.configured ? '已配置' : '未配置'} size="small" color={model.configured ? 'success' : 'warning'} />
        {Array.isArray(model.models) && (model.models as Record<string, unknown>[]).map((m, i) => (
          <Typography key={i} variant="body2">{String(m.id)} — {String(m.name)}</Typography>
        ))}
      </Paper>

      <Paper sx={{ p: 2 }}>
        <Typography variant="subtitle2" gutterBottom>路径</Typography>
        {Object.entries(paths).map(([k, v]) => (
          <Typography key={k} variant="body2" sx={{ fontSize: 12, fontFamily: 'monospace' }}>
            {k}: {v}
          </Typography>
        ))}
      </Paper>
    </Box>
  )
}

// ---------------------------------------------------------------------------
// 版权合规
// ---------------------------------------------------------------------------

function CompliancePanel() {
  const [results, setResults] = useState<Record<string, unknown> | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const doScan = async () => {
    setLoading(true)
    setError('')
    try {
      const data = await systemApi.compliance()
      setResults(data as Record<string, unknown>)
    } catch (e) {
      setError(friendlyError(e))
    } finally {
      setLoading(false)
    }
  }

  const items = (results?.results ?? []) as { name: string; verdict: string; errors: string[]; warns: string[] }[]
  const summary = results?.summary as Record<string, number> | undefined

  return (
    <Box>
      <Typography variant="h6" gutterBottom>版权合规扫描</Typography>
      <Button variant="contained" onClick={doScan} disabled={loading} sx={{ mb: 2 }}>
        {loading ? <CircularProgress size={20} /> : '全量扫描'}
      </Button>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      {summary && (
        <Alert severity={summary.rejected > 0 ? 'error' : summary.warned > 0 ? 'warning' : 'success'} sx={{ mb: 2 }}>
          共 {summary.total} 个资产：{summary.passed} PASS / {summary.warned} WARN / {summary.rejected} REJECT
        </Alert>
      )}
      {items.map((r) => (
        <Paper key={r.name} sx={{ p: 1.5, mb: 1 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Typography variant="body2" sx={{ flex: 1 }}>{r.name}</Typography>
            <Chip
              label={r.verdict} size="small"
              color={r.verdict === 'PASS' ? 'success' : r.verdict === 'WARN' ? 'warning' : 'error'}
            />
          </Box>
          {(r.errors ?? []).map((e, i) => (
            <Typography key={i} variant="caption" sx={{ color: 'error.main', display: 'block' }}>{e}</Typography>
          ))}
          {(r.warns ?? []).map((w, i) => (
            <Typography key={i} variant="caption" sx={{ color: 'warning.main', display: 'block' }}>{w}</Typography>
          ))}
        </Paper>
      ))}
    </Box>
  )
}

// ---------------------------------------------------------------------------
// 模型配置
// ---------------------------------------------------------------------------
// 设置
// ---------------------------------------------------------------------------

function SettingsPanel() {
  const [settings, setSettings] = useState<Record<string, unknown> | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    systemApi.settings()
      .then((data) => setSettings(data as Record<string, unknown>))
      .catch((e) => setError(friendlyError(e)))
  }, [])

  if (error) return <Alert severity="error">{error}</Alert>
  if (!settings) return <CircularProgress />

  const paths = (settings.paths ?? {}) as Record<string, string>
  const env = (settings.envOverrides ?? {}) as Record<string, string>

  return (
    <Box>
      <Typography variant="h6" gutterBottom>系统设置</Typography>
      <Paper sx={{ p: 2, mb: 2 }}>
        <Typography variant="subtitle2" gutterBottom>服务</Typography>
        <Typography variant="body2">端口：{String(settings.port ?? '-')}</Typography>
        <Typography variant="body2">批次大小：{String(settings.batchSize ?? settings.batch_size ?? '-')} 字符</Typography>
      </Paper>
      <Paper sx={{ p: 2, mb: 2 }}>
        <Typography variant="subtitle2" gutterBottom>路径</Typography>
        {Object.entries(paths).map(([k, v]) => (
          <Typography key={k} variant="body2" sx={{ fontSize: 12, fontFamily: 'monospace' }}>{k}: {String(v)}</Typography>
        ))}
      </Paper>
      <Paper sx={{ p: 2 }}>
        <Typography variant="subtitle2" gutterBottom>环境变量覆盖</Typography>
        {Object.entries(env).map(([k, v]) => (
          <Typography key={k} variant="body2" sx={{ fontSize: 12, fontFamily: 'monospace' }}>
            {k}: {v ? String(v) : '（未设置）'}
          </Typography>
        ))}
      </Paper>
      <Alert severity="info" sx={{ mt: 2 }}>
        设置修改请通过环境变量或直接编辑 gui/config.py。GUI 写入设置属阶段三规划。
      </Alert>
    </Box>
  )
}
