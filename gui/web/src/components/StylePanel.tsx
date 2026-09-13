// 文风集成面板：风格分析 / 风格库 / 风格应用。
import { useState, useEffect } from 'react'
import Box from '@mui/material/Box'
import Typography from '@mui/material/Typography'
import Button from '@mui/material/Button'
import TextField from '@mui/material/TextField'
import Paper from '@mui/material/Paper'
import Alert from '@mui/material/Alert'
import CircularProgress from '@mui/material/CircularProgress'
import { styleApi } from '../api/client'
import { friendlyError } from '../api/client'

interface StyleCard {
  name: string
  createdAt: string
  metrics: Record<string, number>
}

export default function StylePanel() {
  const [tab, setTab] = useState<'analyze' | 'library'>('analyze')
  const [text, setText] = useState('')
  const [styleName, setStyleName] = useState('')
  const [result, setResult] = useState<Record<string, unknown> | null>(null)
  const [styles, setStyles] = useState<StyleCard[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  const loadStyles = async () => {
    try {
      const data = await styleApi.list()
      setStyles((data.styles ?? []) as StyleCard[])
    } catch { /* ignore */ }
  }

  useEffect(() => { loadStyles() }, [])

  const doAnalyze = async () => {
    setLoading(true)
    setError('')
    setMessage('')
    try {
      const data = await styleApi.analyze({ text, name: styleName || '未命名' })
      setResult(data)
    } catch (e) {
      setError(friendlyError(e))
    } finally {
      setLoading(false)
    }
  }

  const doSave = async () => {
    if (!result || !styleName) return
    try {
      await styleApi.save({ name: styleName, style_card: result })
      setMessage(`风格「${styleName}」已保存`)
      loadStyles()
    } catch (e) {
      setError(friendlyError(e))
    }
  }

  const doDelete = async (name: string) => {
    try {
      await styleApi.delete(name)
      setMessage(`风格「${name}」已删除`)
      loadStyles()
    } catch (e) {
      setError(friendlyError(e))
    }
  }

  const metrics = result?.metrics as Record<string, number> | undefined

  return (
    <Box>
      <Box sx={{ display: 'flex', gap: 1, mb: 2 }}>
        <Button variant={tab === 'analyze' ? 'contained' : 'outlined'} onClick={() => setTab('analyze')}>
          风格分析
        </Button>
        <Button variant={tab === 'library' ? 'contained' : 'outlined'} onClick={() => setTab('library')}>
          风格库
        </Button>
      </Box>

      {message && <Alert severity="success" sx={{ mb: 2 }} onClose={() => setMessage('')}>{message}</Alert>}
      {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>{error}</Alert>}

      {tab === 'analyze' && (
        <Box>
          <TextField
            label="风格名称" fullWidth size="small" sx={{ mb: 1.5 }}
            value={styleName} onChange={(e) => setStyleName(e.target.value)}
            helperText="保存时使用，如：悬疑冷峻风"
          />
          <TextField
            label="文本样本" multiline rows={8} fullWidth size="small" sx={{ mb: 1.5 }}
            value={text} onChange={(e) => setText(e.target.value)}
            helperText="粘贴至少 100 字的代表性文本"
          />
          <Button variant="contained" onClick={doAnalyze} disabled={!text.trim() || loading}>
            {loading ? <CircularProgress size={20} /> : '分析风格'}
          </Button>

          {result && metrics && (
            <Paper sx={{ p: 2, mt: 2 }}>
              <Typography variant="subtitle2" gutterBottom>风格指标</Typography>
              <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1 }}>
                <Typography variant="body2">平均句长：{String(metrics.avgSentenceLength ?? metrics.avg_sentence_length ?? '-')} 字</Typography>
                <Typography variant="body2">对话占比：{(Number(metrics.dialogueRatio ?? metrics.dialogue_ratio ?? 0) * 100).toFixed(1)}%</Typography>
                <Typography variant="body2">情绪密度：{String(metrics.emotionDensity ?? metrics.emotion_density ?? '-')}/千字</Typography>
                <Typography variant="body2">段落均长：{String(metrics.avgParagraphLength ?? metrics.avg_paragraph_length ?? '-')} 字</Typography>
                <Typography variant="body2">短段占比：{(Number(metrics.shortParagraphRatio ?? metrics.short_paragraph_ratio ?? 0) * 100).toFixed(1)}%</Typography>
                <Typography variant="body2">总字数：{String(metrics.totalChars ?? metrics.total_chars ?? '-')}</Typography>
              </Box>
              <Button variant="outlined" size="small" sx={{ mt: 1.5 }} onClick={doSave} disabled={!styleName}>
                保存风格卡
              </Button>
            </Paper>
          )}
        </Box>
      )}

      {tab === 'library' && (
        <Box>
          {styles.length === 0 && (
            <Alert severity="info">暂无风格卡，请先在「风格分析」中创建</Alert>
          )}
          {styles.map((s) => (
            <Paper key={s.name} sx={{ p: 1.5, mb: 1 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <Box sx={{ flex: 1 }}>
                  <Typography variant="subtitle2">{s.name}</Typography>
                  <Typography variant="caption" color="text.secondary">
                    句长 {String(s.metrics?.avg_sentence_length ?? '-')} 字 | 对话 {(Number(s.metrics?.dialogue_ratio ?? 0) * 100).toFixed(0)}%
                  </Typography>
                </Box>
                <Button size="small" color="error" onClick={() => doDelete(s.name)}>删除</Button>
              </Box>
            </Paper>
          ))}
        </Box>
      )}
    </Box>
  )
}
