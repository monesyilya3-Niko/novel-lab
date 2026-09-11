// 多平台适配面板：平台列表 / 章节合规检查 / 格式化导出。
import { useState, useEffect } from 'react'
import Box from '@mui/material/Box'
import Typography from '@mui/material/Typography'
import Button from '@mui/material/Button'
import TextField from '@mui/material/TextField'
import MenuItem from '@mui/material/MenuItem'
import Paper from '@mui/material/Paper'
import Alert from '@mui/material/Alert'
import CircularProgress from '@mui/material/CircularProgress'
import Chip from '@mui/material/Chip'
import { platformApi } from '../api/client'

interface Platform {
  id: string
  name: string
  chapterMinChars: number
  chapterMaxChars: number
  supportsSerialization: boolean
  genreCount: number
}

export default function PlatformPanel() {
  const [platforms, setPlatforms] = useState<Platform[]>([])
  const [selected, setSelected] = useState('qidian')
  const [chapterText, setChapterText] = useState('')
  const [chapterTitle, setChapterTitle] = useState('')
  const [result, setResult] = useState<Record<string, unknown> | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    platformApi.list()
      .then((data) => setPlatforms((data.platforms ?? []) as Platform[]))
      .catch(() => {})
  }, [])

  const doCheck = async () => {
    setLoading(true)
    setError('')
    try {
      const data = await platformApi.check({
        platform_id: selected,
        chapter_text: chapterText,
        chapter_title: chapterTitle,
      })
      setResult(data)
    } catch (e) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }

  const currentPlatform = platforms.find((p) => p.id === selected)
  const issues = (result?.issues ?? []) as { type: string; severity: string; message: string }[]

  return (
    <Box>
      <Typography variant="h6" gutterBottom>多平台适配</Typography>

      <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', mb: 2 }}>
        <TextField select label="目标平台" value={selected} onChange={(e) => setSelected(e.target.value)} sx={{ minWidth: 180 }} size="small">
          {platforms.map((p) => <MenuItem key={p.id} value={p.id}>{p.name}</MenuItem>)}
        </TextField>
        {currentPlatform && (
          <Chip
            label={`${currentPlatform.chapterMinChars}-${currentPlatform.chapterMaxChars}字/章`}
            size="small" color="primary" variant="outlined"
          />
        )}
      </Box>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      <TextField
        label="章节标题（可选）" fullWidth size="small" sx={{ mb: 1.5 }}
        value={chapterTitle} onChange={(e) => setChapterTitle(e.target.value)}
      />
      <TextField
        label="章节正文" multiline rows={8} fullWidth size="small" sx={{ mb: 1.5 }}
        value={chapterText} onChange={(e) => setChapterText(e.target.value)}
        helperText={currentPlatform ? `建议 ${currentPlatform.chapterMinChars}-${currentPlatform.chapterMaxChars} 字` : ''}
      />
      <Button variant="contained" onClick={doCheck} disabled={!chapterText.trim() || loading}>
        {loading ? <CircularProgress size={20} /> : '检查合规性'}
      </Button>

      {result && (
        <Paper sx={{ p: 2, mt: 2 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
            <Typography variant="subtitle2">检查结果</Typography>
            <Chip
              label={result.compliant ? '合规' : '不合规'}
              size="small"
              color={result.compliant ? 'success' : 'error'}
            />
            <Typography variant="body2" color="text.secondary">
              {String(result.charCount)} 字
            </Typography>
          </Box>
          {issues.length > 0 && (
            <Box sx={{ mt: 1 }}>
              {issues.map((iss, i) => (
                <Alert key={i} severity={iss.severity === 'error' ? 'error' : 'warning'} sx={{ mb: 0.5 }}>
                  {iss.message}
                </Alert>
              ))}
            </Box>
          )}
        </Paper>
      )}

      <Paper sx={{ p: 2, mt: 2 }}>
        <Typography variant="subtitle2" gutterBottom>平台要求</Typography>
        {platforms.map((p) => (
          <Box key={p.id} sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
            <Typography variant="body2" sx={{ minWidth: 100 }}>{p.name}</Typography>
            <Typography variant="caption" color="text.secondary">
              {p.chapterMinChars}-{p.chapterMaxChars}字 | {p.supportsSerialization ? '连载' : '短篇'} | {p.genreCount} 题材
            </Typography>
          </Box>
        ))}
      </Paper>
    </Box>
  )
}
