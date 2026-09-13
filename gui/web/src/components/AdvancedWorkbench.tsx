// M1 高级分析 + M4 资产写入工作台：蒸馏 / 聚合 / 批量状态 / 资产编辑。
import { useState, useEffect } from 'react'
import Box from '@mui/material/Box'
import Tabs from '@mui/material/Tabs'
import Tab from '@mui/material/Tab'
import Typography from '@mui/material/Typography'
import Button from '@mui/material/Button'
import TextField from '@mui/material/TextField'
import MenuItem from '@mui/material/MenuItem'
import Paper from '@mui/material/Paper'
import Alert from '@mui/material/Alert'
import CircularProgress from '@mui/material/CircularProgress'
import Chip from '@mui/material/Chip'
import { advancedApi, assetApi } from '../api/client'
import PlatformPanel from './PlatformPanel'
import { friendlyError } from '../api/client'

export default function AdvancedWorkbench() {
  const [tab, setTab] = useState(0)
  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ borderBottom: 1, borderColor: 'divider', px: 2 }}>
        <Tab label="蒸馏" />
        <Tab label="批量状态" />
        <Tab label="资产编辑" />
        <Tab label="平台适配" />
      </Tabs>
      <Box sx={{ flex: 1, overflow: 'auto', p: 2 }}>
        {tab === 0 && <DistillPanel />}
        {tab === 1 && <BatchStatusPanel />}
        {tab === 2 && <AssetEditPanel />}
        {tab === 3 && <PlatformPanel />}
      </Box>
    </Box>
  )
}

// ---------------------------------------------------------------------------
// 蒸馏面板
// ---------------------------------------------------------------------------

function DistillPanel() {
  const [genre, setGenre] = useState('campus-redemption')
  const [status, setStatus] = useState<Record<string, unknown> | null>(null)
  const [result, setResult] = useState<Record<string, unknown> | null>(null)
  const [rawOpen, setRawOpen] = useState(false)
  const [loading, setLoading] = useState(false)

  const loadStatus = async () => {
    try {
      const data = await advancedApi.distillStatus(genre)
      setStatus(data as Record<string, unknown>)
    } catch { /* ignore */ }
  }

  useEffect(() => { loadStatus() }, [genre])

  const doDistill = async () => {
    setLoading(true)
    setResult(null)
    try {
      const data = await advancedApi.distillRun(genre)
      setResult(data as Record<string, unknown>)
      loadStatus()
    } catch (e) {
      setResult({ error: friendlyError(e) })
    } finally {
      setLoading(false)
    }
  }

  const books = (result?.books as string[]) ?? []
  const written = (result?.written as string[]) ?? []
  const dimensions = (result?.dimensions as string[]) ?? []

  return (
    <Box>
      <Typography variant="h6" gutterBottom>题材蒸馏</Typography>
      <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
        <TextField label="题材" value={genre} onChange={(e) => setGenre(e.target.value)} sx={{ minWidth: 200 }} size="small" />
        <Button variant="contained" onClick={doDistill} disabled={loading || !status?.canDistill}>
          {loading ? <CircularProgress size={20} /> : '执行蒸馏'}
        </Button>
      </Box>
      {status && (
        <Paper sx={{ p: 2, mb: 2 }}>
          <Typography variant="body2">
            可蒸馏书目：{(status.books as string[])?.length ?? 0} 本 — {(status.books as string[])?.join('、')}
          </Typography>
          <Typography variant="body2">
            已有蒸馏产物：{(status.distilledAssets as string[])?.length ?? 0} 个
          </Typography>
          <Chip label={status.canDistill ? '可蒸馏' : '书目不足（需≥2本）'} size="small" color={status.canDistill ? 'success' : 'warning'} />
        </Paper>
      )}
      {result && (
        result.error ? (
          <Alert severity="error" sx={{ mb: 2 }}>{String(result.error)}</Alert>
        ) : (
          <Paper sx={{ p: 2, mb: 2 }}>
            <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 1 }}>
              蒸馏完成 — {books.length} 本书目 · {written.length} 个产出
            </Typography>
            <Typography variant="caption" color="text.secondary">参与书目</Typography>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mb: 1.5 }}>
              {books.map((b) => <Chip key={b} label={b} size="small" variant="outlined" />)}
            </Box>
            <Typography variant="caption" color="text.secondary">蒸馏维度</Typography>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mb: 1.5 }}>
              {dimensions.map((d) => <Chip key={d} label={DIM_LABELS[d] ?? d} size="small" color="primary" variant="outlined" />)}
            </Box>
            <Typography variant="caption" color="text.secondary">产出文件（已入库）</Typography>
            <Box component="ul" sx={{ m: 0, pl: 2.5 }}>
              {written.map((w) => (
                <Typography key={w} component="li" variant="body2" sx={{ fontFamily: 'monospace', fontSize: 12 }}>
                  {w}
                </Typography>
              ))}
            </Box>
            <Button size="small" onClick={() => setRawOpen((v) => !v)} sx={{ mt: 1 }}>
              {rawOpen ? '收起原始 JSON' : '查看原始 JSON'}
            </Button>
            {rawOpen && (
              <Box component="pre" sx={{ fontSize: 12, m: 0, mt: 1, p: 1, bgcolor: 'action.hover', borderRadius: 1, overflow: 'auto' }}>
                {JSON.stringify(result, null, 2)}
              </Box>
            )}
          </Paper>
        )
      )}
    </Box>
  )
}

// ---------------------------------------------------------------------------
// 批量状态面板
// ---------------------------------------------------------------------------

const PASS_SHORT: Record<string, string> = {
  pass1_structure: 'P1 结构',
  pass2_character: 'P2 人物',
  pass3_style: 'P3 文风',
  pass4_commercial: 'P4 商业',
  pass5_aggregate: 'P5 聚合',
}

const DIM_LABELS: Record<string, string> = {
  'voice-card': '声线卡',
  'craft-card': '笔法卡',
  'structure-obs': '结构观测',
  'commercial-obs': '商业观测',
}

function BatchStatusPanel() {
  const [status, setStatus] = useState<Record<string, unknown> | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    advancedApi.batchStatus()
      .then((data) => setStatus(data as Record<string, unknown>))
      .catch((e) => setError(friendlyError(e)))
  }, [])

  const books = (status?.books ?? []) as Record<string, unknown>[]

  if (error) return <Alert severity="error">{error}</Alert>

  return (
    <Box>
      <Typography variant="h6" gutterBottom>批量拆书状态</Typography>
      {books.length === 0 && (
        <Typography variant="body2" color="text.secondary">暂无拆书数据</Typography>
      )}
      {books.map((b) => (
        <Paper key={String(b.name)} sx={{ p: 1.5, mb: 1 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Typography variant="body2" sx={{ flex: 1, fontWeight: 600 }}>{String(b.name)}</Typography>
            <Chip label={`${String(b.passCount)}/5 pass`} size="small" color={(b.passCount as number) >= 5 ? 'success' : 'warning'} />
            {Boolean(b.hasAssets) && <Chip label="已有资产" size="small" color="info" />}
          </Box>
          <Box sx={{ display: 'flex', gap: 0.5, mt: 0.5 }}>
            {Object.entries(b.passes as Record<string, boolean>).map(([k, v]) => (
              <Chip key={k} label={PASS_SHORT[k] ?? k} size="small" color={v ? 'success' : 'default'} variant={v ? 'filled' : 'outlined'} />
            ))}
          </Box>
        </Paper>
      ))}
    </Box>
  )
}

// ---------------------------------------------------------------------------
// 资产编辑面板（M4）
// ---------------------------------------------------------------------------

function AssetEditPanel() {
  const [assets, setAssets] = useState<{ id: string; name: string; kind: string }[]>([])
  const [selected, setSelected] = useState('')
  const [content, setContent] = useState('')
  const [savedContent, setSavedContent] = useState('')
  const [message, setMessage] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    assetApi.list({ limit: 100 })
      .then((j) => {
        const items = ((j as Record<string, unknown>).items ?? []) as { id: string; name: string; kind: string }[]
        setAssets(items)
      })
      .catch((e) => setError(friendlyError(e)))
  }, [])

  const selectedAsset = assets.find((a) => `${a.kind}:${a.id}` === selected)
  const dirty = content !== savedContent
  // 活体 JSON 校验：输入即反馈，保存前就知道合不合法
  const validation = (() => {
    if (!content.trim()) return { ok: false, msg: '内容为空' }
    try {
      const v = JSON.parse(content)
      if (typeof v !== 'object' || v === null || Array.isArray(v)) {
        return { ok: false, msg: '顶层必须是 JSON 对象' }
      }
      return { ok: true, msg: 'JSON 合法' }
    } catch (e) {
      return { ok: false, msg: `JSON 错误：${e instanceof Error ? e.message : String(e)}` }
    }
  })()

  const loadAsset = async () => {
    if (!selected) return
    setLoading(true)
    try {
      const [kind, ...rest] = selected.split(':')
      const id = rest.join(':')
      const data = await assetApi.detail(kind, id)
      const text = JSON.stringify((data as Record<string, unknown>)?.content ?? data, null, 2)
      setContent(text)
      setSavedContent(text)
      setMessage('')
    } catch (e) {
      setMessage(friendlyError(e))
    } finally {
      setLoading(false)
    }
  }

  const saveAsset = async () => {
    if (!selected || !content || !validation.ok) return
    setLoading(true)
    setMessage('')
    try {
      const parsed = JSON.parse(content)
      const [kind, ...rest] = selected.split(':')
      const id = rest.join(':')
      await assetApi.update(kind, id, parsed)
      setSavedContent(content)
      setMessage('保存成功')
    } catch (e) {
      setMessage(friendlyError(e))
    } finally {
      setLoading(false)
    }
  }

  return (
    <Box>
      <Typography variant="h6" gutterBottom>资产编辑</Typography>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      <Box sx={{ display: 'flex', gap: 2, mb: 1, flexWrap: 'wrap' }}>
        <TextField select label="选择资产" value={selected} onChange={(e) => setSelected(e.target.value)} sx={{ minWidth: 300, flex: 1 }} size="small">
          {assets.map((a) => <MenuItem key={a.id} value={`${a.kind}:${a.id}`}>{a.name}（{a.kind}）</MenuItem>)}
        </TextField>
        <Button variant="outlined" onClick={loadAsset} disabled={!selected || loading}>加载</Button>
        <Button variant="contained" onClick={saveAsset} disabled={!content || loading || !validation.ok || !dirty}>
          {loading ? <CircularProgress size={20} /> : '保存'}
        </Button>
      </Box>
      {selectedAsset && (
        <Box sx={{ display: 'flex', gap: 1, mb: 1, alignItems: 'center', flexWrap: 'wrap' }}>
          <Chip label={selectedAsset.kind} size="small" color="primary" variant="outlined" />
          <Chip label={validation.ok ? '✓ JSON 合法' : '✗ JSON 错误'} size="small" color={validation.ok ? 'success' : 'error'} variant="outlined" />
          {dirty && <Chip label="未保存修改" size="small" color="warning" />}
          {selectedAsset.name && <Typography variant="caption" color="text.secondary">{selectedAsset.name}</Typography>}
        </Box>
      )}
      {!validation.ok && content.trim() && (
        <Alert severity="warning" sx={{ mb: 1 }}>{validation.msg}</Alert>
      )}
      {message && <Alert severity={message === '保存成功' ? 'success' : 'error'} sx={{ mb: 1 }}>{message}</Alert>}
      <TextField
        label="资产 JSON 内容" multiline rows={16} fullWidth value={content}
        onChange={(e) => setContent(e.target.value)} size="small"
        InputProps={{ style: { fontFamily: 'monospace', fontSize: 12 } }}
      />
    </Box>
  )
}
