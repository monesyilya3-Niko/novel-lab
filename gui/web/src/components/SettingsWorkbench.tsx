// 设置工作台：阈值 / 写作 / 端口配置管理。
// P2-F12：数值字段即时校验（与后端 update_settings 规则对齐），非法时禁用保存；
// 保存成功后调用 refreshThresholds()，让 QC/写作面板即时用上新阈值。
import { useState, useEffect } from 'react'
import Box from '@mui/material/Box'
import ContextHelpButton from './ContextHelpButton'
import Typography from '@mui/material/Typography'
import Button from '@mui/material/Button'
import TextField from '@mui/material/TextField'
import Paper from '@mui/material/Paper'
import Alert from '@mui/material/Alert'
import CircularProgress from '@mui/material/CircularProgress'
import Divider from '@mui/material/Divider'
import Chip from '@mui/material/Chip'
import { systemApi } from '../api/client'
import { friendlyError } from '../api/client'
import { useApp } from '../state/AppContext'

interface Settings {
  port: number
  batchSize: number
  thresholds: { consistencyTarget: number; qualityPassLine: number; qualityWarnLine: number }
  writing: { defaultWords: number; maxAttempts: number }
  paths: Record<string, string>
  envOverrides: Record<string, string>
  saved: Record<string, unknown>
}

// 与后端 system_service.update_settings 的校验规则保持一致
export function validateSettingsField(
  name: 'consistencyTarget' | 'qualityPassLine' | 'qualityWarnLine' | 'defaultWords' | 'maxAttempts',
  raw: string,
  all: Record<string, string>,
): string {
  const v = raw.trim()
  if (v === '') return '不能为空'
  if (!/^-?\d+(\.\d+)?$/.test(v)) return '请输入数字'
  const n = Number(v)
  if (name === 'defaultWords' || name === 'maxAttempts') {
    if (!Number.isInteger(n)) return '必须为整数'
  }
  if (name === 'consistencyTarget' || name === 'qualityPassLine' || name === 'qualityWarnLine') {
    if (n < 0 || n > 100) return '必须在 0-100 之间'
  }
  if (name === 'defaultWords' && (n < 100 || n > 20000)) return '必须在 100-20000 之间'
  if (name === 'maxAttempts' && (n < 1 || n > 10)) return '必须在 1-10 之间'
  // 及格线必须 >= 警告线（交叉校验，用解析后的数值）
  const pl = name === 'qualityPassLine' ? n : Number(all.qualityPassLine)
  const wl = name === 'qualityWarnLine' ? n : Number(all.qualityWarnLine)
  if (!Number.isNaN(pl) && !Number.isNaN(wl) && pl < wl) {
    return name === 'qualityPassLine'
      ? '及格线必须 ≥ 警告线'
      : '警告线必须 ≤ 及格线'
  }
  return ''
}

const FIELD_NAMES = ['consistencyTarget', 'qualityPassLine', 'qualityWarnLine', 'defaultWords', 'maxAttempts'] as const
type FieldName = (typeof FIELD_NAMES)[number]

const FIELD_LABEL: Record<FieldName, string> = {
  consistencyTarget: '一致性目标分',
  qualityPassLine: '质量及格线',
  qualityWarnLine: '质量警告线',
  defaultWords: '默认字数',
  maxAttempts: '最大改写轮数',
}

const FIELD_HELPER: Record<FieldName, string> = {
  consistencyTarget: '写作改写循环的一致性达标线（0-100）',
  qualityPassLine: '章节质量 PASS 阈值（默认 75）',
  qualityWarnLine: '章节质量 WARN 阈值（默认 60）',
  defaultWords: '每章默认目标字数（100-20000）',
  maxAttempts: '1 初稿 + N-1 次改写（1-10）',
}

export default function SettingsWorkbench() {
  const { refreshThresholds } = useApp()
  const [settings, setSettings] = useState<Settings | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  // 表单状态用字符串保存，避免非法输入被 Number() 吞成 NaN/0
  const [fields, setFields] = useState<Record<FieldName, string>>({
    consistencyTarget: '90',
    qualityPassLine: '75',
    qualityWarnLine: '60',
    defaultWords: '2400',
    maxAttempts: '3',
  })

  const loadSettings = async () => {
    setLoading(true)
    setError('')
    try {
      const d = await systemApi.settings() as Record<string, unknown>
      setSettings(d as unknown as Settings)
      const th = d.thresholds as Record<string, number> | undefined
      const wr = d.writing as Record<string, number> | undefined
      // deepToCamel 已将 snake_case 转为 camelCase
      setFields({
        consistencyTarget: String(th?.consistencyTarget ?? 90),
        qualityPassLine: String(th?.qualityPassLine ?? 75),
        qualityWarnLine: String(th?.qualityWarnLine ?? 60),
        defaultWords: String(wr?.defaultWords ?? 2400),
        maxAttempts: String(wr?.maxAttempts ?? 3),
      })
    } catch (e) {
      setError(friendlyError(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadSettings() }, [])

  const fieldErrors = Object.fromEntries(
    FIELD_NAMES.map((n) => [n, validateSettingsField(n, fields[n], fields)]),
  ) as Record<FieldName, string>
  const hasError = FIELD_NAMES.some((n) => fieldErrors[n] !== '')

  const saveSettings = async () => {
    if (hasError) return
    setSaving(true)
    setMessage('')
    setError('')
    try {
      const data = await systemApi.updateSettings({
        thresholds: {
          consistency_target: Number(fields.consistencyTarget),
          quality_pass_line: Number(fields.qualityPassLine),
          quality_warn_line: Number(fields.qualityWarnLine),
        },
        writing: {
          default_words: Number(fields.defaultWords),
          max_attempts: Number(fields.maxAttempts),
        },
      })
      setSettings(data as unknown as Settings)
      setMessage('设置已保存')
      // 阈值即时刷新：QC 合格线/写书目标分立即生效
      await refreshThresholds()
    } catch (e) {
      setError(friendlyError(e))
    } finally {
      setSaving(false)
    }
  }

  const resetSettings = async () => {
    // P2-F11/F13：重置二次确认
    if (!window.confirm('确定将所有设置重置为默认值吗？此操作不可恢复。')) return
    setSaving(true)
    setMessage('')
    setError('')
    try {
      const data = await systemApi.resetSettings()
      setSettings(data as unknown as Settings)
      setFields({
        consistencyTarget: '90',
        qualityPassLine: '75',
        qualityWarnLine: '60',
        defaultWords: '2400',
        maxAttempts: '3',
      })
      setMessage('已重置为默认值')
      await refreshThresholds()
    } catch (e) {
      setError(friendlyError(e))
    } finally {
      setSaving(false)
    }
  }

  const renderField = (name: FieldName) => (
    <TextField
      key={name}
      label={FIELD_LABEL[name]} type="number" size="small" fullWidth
      value={fields[name]}
      onChange={(e) => setFields((f) => ({ ...f, [name]: e.target.value }))}
      error={fieldErrors[name] !== ''}
      helperText={fieldErrors[name] || FIELD_HELPER[name]}
    />
  )

  if (loading) return <CircularProgress />
  if (error && !settings) return <Alert severity="error">{error}</Alert>

  return (
    <Box sx={{ maxWidth: 600 }}>
      <Box sx={{ display: 'flex', alignItems: 'center' }}>
        <Typography variant="h6" gutterBottom sx={{ flex: 1 }}>系统设置</Typography>
        <ContextHelpButton guideKey="settings" />
      </Box>
      {message && <Alert severity="success" sx={{ mb: 2 }}>{message}</Alert>}
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      {/* 打分阈值 */}
      <Paper sx={{ p: 2, mb: 2 }}>
        <Typography variant="subtitle2" gutterBottom>打分阈值</Typography>
        <Box sx={{ display: 'flex', gap: 2, mb: 1.5, flexWrap: 'wrap' }}>
          {renderField('consistencyTarget')}
          {renderField('qualityPassLine')}
          {renderField('qualityWarnLine')}
        </Box>
      </Paper>

      {/* 写作设置 */}
      <Paper sx={{ p: 2, mb: 2 }}>
        <Typography variant="subtitle2" gutterBottom>写作设置</Typography>
        <Box sx={{ display: 'flex', gap: 2, mb: 1.5, flexWrap: 'wrap' }}>
          {renderField('defaultWords')}
          {renderField('maxAttempts')}
        </Box>
      </Paper>

      {/* 操作按钮 */}
      <Box sx={{ display: 'flex', gap: 2, mb: 2, flexWrap: 'wrap' }}>
        <Button variant="contained" onClick={saveSettings} disabled={saving || hasError}>
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
