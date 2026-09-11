// 模型管理面板：自定义 API/模型的增删改查与测试。
import { useState, useEffect, useCallback } from 'react'
import Box from '@mui/material/Box'
import Typography from '@mui/material/Typography'
import Button from '@mui/material/Button'
import TextField from '@mui/material/TextField'
import MenuItem from '@mui/material/MenuItem'
import Paper from '@mui/material/Paper'
import Alert from '@mui/material/Alert'
import CircularProgress from '@mui/material/CircularProgress'
import Chip from '@mui/material/Chip'
import Dialog from '@mui/material/Dialog'
import DialogTitle from '@mui/material/DialogTitle'
import DialogContent from '@mui/material/DialogContent'
import DialogActions from '@mui/material/DialogActions'
import AddIcon from '@mui/icons-material/Add'
import EditIcon from '@mui/icons-material/Edit'
import DeleteIcon from '@mui/icons-material/Delete'
import PlayArrowIcon from '@mui/icons-material/PlayArrow'
import KeyIcon from '@mui/icons-material/Key'

interface ModelInfo {
  id: string
  label: string
  protocol: string
  baseUrl: string
  modelName: string
  roles: string[]
  hasKey: boolean
  note?: string
}

interface Preset {
  name: string
  label: string
  protocol: string
  baseUrl: string
  modelName: string
}

export default function ModelManager() {
  const [models, setModels] = useState<ModelInfo[]>([])
  const [presets, setPresets] = useState<Preset[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  // Dialog state
  const [showAdd, setShowAdd] = useState(false)
  const [editing, setEditing] = useState<ModelInfo | null>(null)
  const [showKey, setShowKey] = useState<string | null>(null)
  const [apiKey, setApiKey] = useState('')
  const [testing, setTesting] = useState<string | null>(null)

  // Form state
  const [form, setForm] = useState({
    id: '', label: '', protocol: 'openai', baseUrl: '', modelName: '', note: '',
  })

  const loadModels = useCallback(async () => {
    try {
      const res = await fetch('/api/models')
      const json = await res.json()
      if (json.code !== 0) throw new Error(json.message)
      setModels(json.data.models)
    } catch (e) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }, [])

  const loadPresets = useCallback(async () => {
    try {
      const res = await fetch('/api/models/presets')
      const json = await res.json()
      if (json.code === 0) setPresets(json.data.presets)
    } catch { /* ignore */ }
  }, [])

  useEffect(() => {
    loadModels()
    loadPresets()
  }, [loadModels, loadPresets])

  const resetForm = () => setForm({ id: '', label: '', protocol: 'openai', baseUrl: '', modelName: '', note: '' })

  const openAdd = () => {
    resetForm()
    setEditing(null)
    setShowAdd(true)
  }

  const openEdit = (m: ModelInfo) => {
    setForm({
      id: m.id, label: m.label, protocol: m.protocol,
      baseUrl: m.baseUrl, modelName: m.modelName, note: m.note || '',
    })
    setEditing(m)
    setShowAdd(true)
  }

  const applyPreset = (p: Preset) => {
    setForm({
      id: p.name, label: p.label, protocol: p.protocol,
      baseUrl: p.baseUrl, modelName: p.modelName, note: '',
    })
  }

  const saveModel = async () => {
    setMessage('')
    setError('')
    try {
      const body: Record<string, unknown> = {
        id: form.id, label: form.label, protocol: form.protocol,
        base_url: form.baseUrl, model_name: form.modelName,
      }
      if (form.note) body.note = form.note

      const url = editing ? `/api/models/${editing.id}` : '/api/models'
      const method = editing ? 'PUT' : 'POST'
      const res = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      const json = await res.json()
      if (json.code !== 0) throw new Error(json.message)
      setMessage(editing ? '模型已更新' : '模型已添加')
      setShowAdd(false)
      loadModels()
    } catch (e) {
      setError(String(e))
    }
  }

  const deleteModel = async (id: string) => {
    if (!confirm(`确认删除模型 ${id}？`)) return
    try {
      const res = await fetch(`/api/models/${id}`, { method: 'DELETE' })
      const json = await res.json()
      if (json.code !== 0) throw new Error(json.message)
      setMessage(`模型 ${id} 已删除`)
      loadModels()
    } catch (e) {
      setError(String(e))
    }
  }

  const saveKey = async () => {
    if (!showKey || !apiKey) return
    try {
      const res = await fetch(`/api/models/${showKey}/key`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_key: apiKey }),
      })
      const json = await res.json()
      if (json.code !== 0) throw new Error(json.message)
      setMessage(`API Key 已保存`)
      setShowKey(null)
      setApiKey('')
      loadModels()
    } catch (e) {
      setError(String(e))
    }
  }

  const testModel = async (id: string) => {
    setTesting(id)
    setMessage('')
    try {
      const res = await fetch(`/api/models/${id}/test`, { method: 'POST' })
      const json = await res.json()
      if (json.code !== 0) throw new Error(json.message)
      if (json.data.success) {
        setMessage(`模型 ${id} 连接成功`)
      } else {
        setError(`模型 ${id} 连接失败: ${json.data.error}`)
      }
    } catch (e) {
      setError(String(e))
    } finally {
      setTesting(null)
    }
  }

  if (loading) return <CircularProgress />

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2 }}>
        <Typography variant="h6">模型管理</Typography>
        <Button variant="contained" startIcon={<AddIcon />} onClick={openAdd}>添加模型</Button>
      </Box>

      {message && <Alert severity="success" sx={{ mb: 2 }} onClose={() => setMessage('')}>{message}</Alert>}
      {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>{error}</Alert>}

      {models.length === 0 && (
        <Alert severity="info" sx={{ mb: 2 }}>暂无模型配置，点击「添加模型」开始</Alert>
      )}

      {models.map((m) => (
        <Paper key={m.id} sx={{ p: 2, mb: 1.5 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Box sx={{ flex: 1 }}>
              <Typography variant="subtitle2">
                {m.label} <Chip label={m.id} size="small" />
                <Chip label={m.protocol} size="small" color="primary" variant="outlined" sx={{ ml: 0.5 }} />
                {m.hasKey && <Chip label="已配 Key" size="small" color="success" sx={{ ml: 0.5 }} />}
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ fontSize: 12 }}>
                {m.modelName} @ {m.baseUrl}
              </Typography>
              {m.roles.length > 0 && (
                <Typography variant="caption" color="text.secondary">
                  角色：{m.roles.join(', ')}
                </Typography>
              )}
            </Box>
            <Box sx={{ display: 'flex', gap: 1, flexShrink: 0 }}>
              <Button size="small" startIcon={<PlayArrowIcon />} onClick={() => testModel(m.id)} disabled={testing === m.id}>
                {testing === m.id ? '测试中' : '测试'}
              </Button>
              <Button size="small" startIcon={<KeyIcon />} onClick={() => { setShowKey(m.id); setApiKey('') }}>
                密钥
              </Button>
              <Button size="small" startIcon={<EditIcon />} onClick={() => openEdit(m)}>
                编辑
              </Button>
              <Button size="small" color="error" startIcon={<DeleteIcon />} onClick={() => deleteModel(m.id)}>
                删除
              </Button>
            </Box>
          </Box>
        </Paper>
      ))}

      {/* 添加/编辑对话框 */}
      <Dialog open={showAdd} onClose={() => setShowAdd(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{editing ? `编辑模型: ${editing.id}` : '添加模型'}</DialogTitle>
        <DialogContent>
          {!editing && presets.length > 0 && (
            <Box sx={{ mb: 2 }}>
              <Typography variant="caption" color="text.secondary">快速选择预设：</Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mt: 0.5 }}>
                {presets.map((p) => (
                  <Chip key={p.name} label={p.label} size="small" onClick={() => applyPreset(p)} variant="outlined" />
                ))}
              </Box>
            </Box>
          )}
          <TextField
            label="模型 ID" fullWidth size="small" sx={{ mb: 1.5 }}
            value={form.id} onChange={(e) => setForm({ ...form, id: e.target.value })}
            disabled={!!editing}
            helperText="唯一标识，如 my-gpt4"
          />
          <TextField
            label="显示名称" fullWidth size="small" sx={{ mb: 1.5 }}
            value={form.label} onChange={(e) => setForm({ ...form, label: e.target.value })}
          />
          <TextField
            select label="协议" fullWidth size="small" sx={{ mb: 1.5 }}
            value={form.protocol} onChange={(e) => setForm({ ...form, protocol: e.target.value })}
          >
            <MenuItem value="openai">OpenAI 兼容</MenuItem>
            <MenuItem value="anthropic">Anthropic</MenuItem>
            <MenuItem value="ollama">Ollama</MenuItem>
          </TextField>
          <TextField
            label="Base URL" fullWidth size="small" sx={{ mb: 1.5 }}
            value={form.baseUrl} onChange={(e) => setForm({ ...form, baseUrl: e.target.value })}
            helperText="如 https://api.openai.com/v1"
          />
          <TextField
            label="模型名称" fullWidth size="small" sx={{ mb: 1.5 }}
            value={form.modelName} onChange={(e) => setForm({ ...form, modelName: e.target.value })}
            helperText="如 gpt-4o, claude-3-5-sonnet"
          />
          <TextField
            label="备注" fullWidth size="small"
            value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowAdd(false)}>取消</Button>
          <Button variant="contained" onClick={saveModel} disabled={!form.id || !form.baseUrl || !form.modelName}>
            {editing ? '保存' : '添加'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* API Key 对话框 */}
      <Dialog open={!!showKey} onClose={() => setShowKey(null)} maxWidth="sm" fullWidth>
        <DialogTitle>设置 API Key: {showKey}</DialogTitle>
        <DialogContent>
          <TextField
            label="API Key" fullWidth size="small" type="password"
            value={apiKey} onChange={(e) => setApiKey(e.target.value)}
            helperText="Key 将加密存储在本地 .secrets.json"
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowKey(null)}>取消</Button>
          <Button variant="contained" onClick={saveKey} disabled={!apiKey}>保存</Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}
