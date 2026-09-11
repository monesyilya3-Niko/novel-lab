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
import { deepToCamel } from '../api/client'

export default function AdvancedWorkbench() {
  const [tab, setTab] = useState(0)
  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ borderBottom: 1, borderColor: 'divider', px: 2 }}>
        <Tab label="蒸馏" />
        <Tab label="批量状态" />
        <Tab label="资产编辑" />
      </Tabs>
      <Box sx={{ flex: 1, overflow: 'auto', p: 2 }}>
        {tab === 0 && <DistillPanel />}
        {tab === 1 && <BatchStatusPanel />}
        {tab === 2 && <AssetEditPanel />}
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
  const [result, setResult] = useState('')
  const [loading, setLoading] = useState(false)

  const loadStatus = async () => {
    try {
      const res = await fetch(`/api/advanced/distill/${encodeURIComponent(genre)}`)
      const json = await res.json()
      if (json.code === 0) setStatus(deepToCamel(json.data))
    } catch { /* ignore */ }
  }

  useEffect(() => { loadStatus() }, [genre])

  const doDistill = async () => {
    setLoading(true)
    setResult('')
    try {
      const res = await fetch(`/api/advanced/distill/${encodeURIComponent(genre)}`, { method: 'POST' })
      const json = await res.json()
      if (json.code !== 0) throw new Error(json.message)
      setResult(JSON.stringify(deepToCamel(json.data), null, 2))
      loadStatus()
    } catch (e) {
      setResult(String(e))
    } finally {
      setLoading(false)
    }
  }

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
        <Paper sx={{ p: 1, bgcolor: '#f5f5f5' }}>
          <pre style={{ fontSize: 12, margin: 0 }}>{result}</pre>
        </Paper>
      )}
    </Box>
  )
}

// ---------------------------------------------------------------------------
// 批量状态面板
// ---------------------------------------------------------------------------

function BatchStatusPanel() {
  const [status, setStatus] = useState<Record<string, unknown> | null>(null)

  useEffect(() => {
    fetch('/api/advanced/batch-status')
      .then((r) => r.json())
      .then((j) => { if (j.code === 0) setStatus(deepToCamel(j.data)) })
      .catch(() => {})
  }, [])

  const books = (status?.books ?? []) as Record<string, unknown>[]

  return (
    <Box>
      <Typography variant="h6" gutterBottom>批量拆书状态</Typography>
      {books.map((b) => (
        <Paper key={String(b.name)} sx={{ p: 1.5, mb: 1 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Typography variant="body2" sx={{ flex: 1, fontWeight: 600 }}>{String(b.name)}</Typography>
            <Chip label={`${String(b.passCount)}/5 pass`} size="small" color={(b.passCount as number) >= 5 ? 'success' : 'warning'} />
            {Boolean(b.hasAssets) && <Chip label="已有资产" size="small" color="info" />}
          </Box>
          <Box sx={{ display: 'flex', gap: 0.5, mt: 0.5 }}>
            {Object.entries(b.passes as Record<string, boolean>).map(([k, v]) => (
              <Chip key={k} label={k.replace('pass', 'P').replace('_structure', '').replace('_character', '').replace('_style', '').replace('_commercial', '').replace('_craft', '')} size="small" color={v ? 'success' : 'default'} variant={v ? 'filled' : 'outlined'} />
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
  const [message, setMessage] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    fetch('/api/assets?limit=100')
      .then((r) => r.json())
      .then((j) => {
        const items = (j.data?.items ?? []) as { id: string; name: string; kind: string }[]
        setAssets(items)
      })
      .catch(() => {})
  }, [])

  const loadAsset = async () => {
    if (!selected) return
    setLoading(true)
    try {
      const [kind, ...rest] = selected.split(':')
      const id = rest.join(':')
      const res = await fetch(`/api/assets/${kind}/${encodeURIComponent(id)}`)
      const json = await res.json()
      if (json.code === 0) {
        setContent(JSON.stringify(json.data?.content ?? json.data, null, 2))
      }
    } catch (e) {
      setMessage(String(e))
    } finally {
      setLoading(false)
    }
  }

  const saveAsset = async () => {
    if (!selected || !content) return
    setLoading(true)
    setMessage('')
    try {
      const parsed = JSON.parse(content)
      const [kind, ...rest] = selected.split(':')
      const id = rest.join(':')
      const res = await fetch(`/api/assets/${kind}/${encodeURIComponent(id)}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: parsed }),
      })
      const json = await res.json()
      if (json.code !== 0) throw new Error(json.message)
      setMessage('保存成功')
    } catch (e) {
      setMessage(String(e))
    } finally {
      setLoading(false)
    }
  }

  return (
    <Box>
      <Typography variant="h6" gutterBottom>资产编辑</Typography>
      <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
        <TextField select label="选择资产" value={selected} onChange={(e) => setSelected(e.target.value)} sx={{ minWidth: 300 }} size="small">
          {assets.map((a) => <MenuItem key={a.id} value={`${a.kind}:${a.id}`}>{a.name}（{a.kind}）</MenuItem>)}
        </TextField>
        <Button variant="outlined" onClick={loadAsset} disabled={!selected || loading}>加载</Button>
        <Button variant="contained" onClick={saveAsset} disabled={!content || loading}>
          {loading ? <CircularProgress size={20} /> : '保存'}
        </Button>
      </Box>
      {message && <Alert severity={message === '保存成功' ? 'success' : 'error'} sx={{ mb: 2 }}>{message}</Alert>}
      <TextField
        label="资产 JSON 内容" multiline rows={16} fullWidth value={content}
        onChange={(e) => setContent(e.target.value)} size="small"
        InputProps={{ style: { fontFamily: 'monospace', fontSize: 12 } }}
      />
    </Box>
  )
}
