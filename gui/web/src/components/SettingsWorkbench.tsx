// 设置工作台：阈值 / 写作 / 端口配置管理。
import { useState, useEffect } from 'react'
import Box from '@mui/material/Box'
import Typography from '@mui/material/Typography'
import Button from '@mui/material/Button'
import TextField from '@mui/material/TextField'
import Paper from '@mui/material/Paper'
import Alert from '@mui/material/Alert'
import CircularProgress from '@mui/material/CircularProgress'
import Divider from '@mui/material/Divider'
import Chip from '@mui/material/Chip'
import { systemApi } from '../api/client'

interface Settings {
  port: number
  batchSize: number
  thresholds: { consistencyTarget: number; qualityPassLine: number; qualityWarnLine: number }
  writing: { defaultWords: number; maxAttempts: number }
  paths: Record<string, string>
  envOverrides: Record<string, string>
  saved: Record<string, unknown>
}

export default function SettingsWorkbench() {
  const [settings, setSettings] = useState<Settings | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  // 表单状态
  const [consistencyTarget, setConsistencyTarget] = useState(90)
  const [qualityPassLine, setQualityPassLine] = useState(75)
  const [qualityWarnLine, setQualityWarnLine] = useState(60)
  const [defaultWords, setDefaultWords] = useState(2400)
  const [maxAttempts, setMaxAttempts] = useState(3)

  const loadSettings = async () => {
    setLoading(true)
    setError('')
    try {
      const d = await systemApi.settings() as Record<string, unknown>
      setSettings(d as unknown as Settings)
      const th = d.thresholds as Record<string, number> | undefined
      const wr = d.writing as Record<string, number> | undefined
      // deepToCamel 已将 snake_case 转为 camelCase
      setConsistencyTarget(th?.consistencyTarget ?? 90)
      setQualityPassLine(th?.qualityPassLine ?? 75)
      setQualityWarnLine(th?.qualityWarnLine ?? 60)
      setDefaultWords(wr?.defaultWords ?? 2400)
      setMaxAttempts(wr?.maxAttempts ?? 3)
    } catch (e) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadSettings() }, [])

  const saveSettings = async () => {
    setSaving(true)
    setMessage('')
    setError('')
    try {
      const data = await systemApi.updateSettings({
        thresholds: {
          consistency_target: consistencyTarget,
          quality_pass_line: qualityPassLine,
          quality_warn_line: qualityWarnLine,
        },
        writing: {
          default_words: defaultWords,
          max_attempts: maxAttempts,
        },
      })
      setSettings(data as unknown as Settings)
      setMessage('设置已保存')
    } catch (e) {
      setError(String(e))
    } finally {
      setSaving(false)
    }
  }

  const resetSettings = async () => {
    setSaving(true)
    setMessage('')
    setError('')
    try {
      const data = await systemApi.resetSettings()
      setSettings(data as unknown as Settings)
      setConsistencyTarget(90)
      setQualityPassLine(75)
      setQualityWarnLine(60)
      setDefaultWords(2400)
      setMaxAttempts(3)
      setMessage('已重置为默认值')
    } catch (e) {
      setError(String(e))
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <CircularProgress />
  if (error && !settings) return <Alert severity="error">{error}</Alert>

  return (
    <Box sx={{ maxWidth: 600 }}>
      <Typography variant="h6" gutterBottom>系统设置</Typography>
      {message && <Alert severity="success" sx={{ mb: 2 }}>{message}</Alert>}
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      {/* 打分阈值 */}
      <Paper sx={{ p: 2, mb: 2 }}>
        <Typography variant="subtitle2" gutterBottom>打分阈值</Typography>
        <Box sx={{ display: 'flex', gap: 2, mb: 1.5 }}>
          <TextField
            label="一致性目标分" type="number" size="small" fullWidth
            value={consistencyTarget} onChange={(e) => setConsistencyTarget(Number(e.target.value))}
            inputProps={{ min: 0, max: 100 }}
            helperText="写作改写循环的一致性达标线（0-100）"
          />
          <TextField
            label="质量及格线" type="number" size="small" fullWidth
            value={qualityPassLine} onChange={(e) => setQualityPassLine(Number(e.target.value))}
            inputProps={{ min: 0, max: 100 }}
            helperText="章节质量 PASS 阈值（默认 75）"
          />
          <TextField
            label="质量警告线" type="number" size="small" fullWidth
            value={qualityWarnLine} onChange={(e) => setQualityWarnLine(Number(e.target.value))}
            inputProps={{ min: 0, max: 100 }}
            helperText="章节质量 WARN 阈值（默认 60）"
          />
        </Box>
      </Paper>

      {/* 写作设置 */}
      <Paper sx={{ p: 2, mb: 2 }}>
        <Typography variant="subtitle2" gutterBottom>写作设置</Typography>
        <Box sx={{ display: 'flex', gap: 2, mb: 1.5 }}>
          <TextField
            label="默认字数" type="number" size="small" fullWidth
            value={defaultWords} onChange={(e) => setDefaultWords(Number(e.target.value))}
            inputProps={{ min: 100, max: 20000 }}
            helperText="每章默认目标字数（100-20000）"
          />
          <TextField
            label="最大改写轮数" type="number" size="small" fullWidth
            value={maxAttempts} onChange={(e) => setMaxAttempts(Number(e.target.value))}
            inputProps={{ min: 1, max: 10 }}
            helperText="1 初稿 + N-1 次改写（1-10）"
          />
        </Box>
      </Paper>

      {/* 操作按钮 */}
      <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
        <Button variant="contained" onClick={saveSettings} disabled={saving}>
          {saving ? <CircularProgress size={20} /> : '保存设置'}
        </Button>
        <Button variant="outlined" color="warning" onClick={resetSettings} disabled={saving}>
          重置为默认
        </Button>
      </Box>

      <Divider sx={{ my: 2 }} />

      {/* 只读信息 */}
      <Paper sx={{ p: 2, mb: 2 }}>
        <Typography variant="subtitle2" gutterBottom>
          服务配置 <Chip label="需重启生效" size="small" color="warning" />
        </Typography>
        <Typography variant="body2">端口：{settings?.port}</Typography>
        <Typography variant="body2">批次大小：{settings?.batchSize} 字符</Typography>
        <Typography variant="caption" color="text.secondary">
          修改端口/批次大小请通过环境变量 NOVEL_LAB_GUI_PORT / NOVEL_LAB_GUI_BATCH_SIZE
        </Typography>
      </Paper>

      <Paper sx={{ p: 2, mb: 2 }}>
        <Typography variant="subtitle2" gutterBottom>路径</Typography>
        {settings?.paths && Object.entries(settings.paths).map(([k, v]) => (
          <Typography key={k} variant="body2" sx={{ fontSize: 12, fontFamily: 'monospace' }}>
            {k}: {v}
          </Typography>
        ))}
      </Paper>

      <Paper sx={{ p: 2 }}>
        <Typography variant="subtitle2" gutterBottom>环境变量覆盖</Typography>
        {settings?.envOverrides && Object.entries(settings.envOverrides).map(([k, v]) => (
          <Typography key={k} variant="body2" sx={{ fontSize: 12, fontFamily: 'monospace' }}>
            {k}: {v || '（未设置）'}
          </Typography>
        ))}
      </Paper>
    </Box>
  )
}
