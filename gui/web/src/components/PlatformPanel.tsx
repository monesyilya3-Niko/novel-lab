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
import Stack from '@mui/material/Stack'
import Divider from '@mui/material/Divider'
import { platformApi, SubmissionDiagnosisResult } from '../api/client'
import { friendlyError } from '../api/client'

interface Platform {
  id: string
  name: string
  chapterMinChars?: number
  chapterMaxChars?: number
  chapter_min_chars?: number
  chapter_max_chars?: number
  supportsSerialization?: boolean
  supports_serialization?: boolean
  climax_interval?: string
  rhythm_type?: string
  genreCount?: number
}

export default function PlatformPanel() {
  const [platforms, setPlatforms] = useState<Platform[]>([])
  const [selected, setSelected] = useState('')
  const [chapterText, setChapterText] = useState('')
  const [chapterTitle, setChapterTitle] = useState('')
  const [result, setResult] = useState<Record<string, unknown> | null>(null)
  const [diagnosis, setDiagnosis] = useState<SubmissionDiagnosisResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [diagnosing, setDiagnosing] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    platformApi.list()
      .then((data) => {
        const list = (data.platforms ?? []) as Platform[]
        setPlatforms(list)
        setSelected((prev) => (prev && list.some((pl) => pl.id === prev) ? prev : (list[0]?.id ?? '')))
      })
      .catch((e) => setError(`加载平台列表失败: ${e}`))
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
      setError(friendlyError(e))
    } finally {
      setLoading(false)
    }
  }

  const doDiagnose = async () => {
    setDiagnosing(true)
    setError('')
    try {
      const data = await platformApi.diagnose({
        platform_id: selected,
        chapter_text: chapterText,
        chapter_title: chapterTitle,
      })
      setDiagnosis(data)
    } catch (e) {
      setError(friendlyError(e))
    } finally {
      setDiagnosing(false)
    }
  }

  const currentPlatform = platforms.find((p) => p.id === selected)
  const issues = (result?.issues ?? []) as { type: string; severity: string; message: string }[]

  const getRatingColor = (rating: string) => {
    if (rating === 'A') return 'success'
    if (rating === 'B') return 'warning'
    return 'error'
  }

  const minChars = currentPlatform?.chapter_min_chars ?? currentPlatform?.chapterMinChars ?? 0
  const maxChars = currentPlatform?.chapter_max_chars ?? currentPlatform?.chapterMaxChars ?? 0

  return (
    <Box>
      <Typography variant="h6" gutterBottom>多平台适配与签约诊断</Typography>

      <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap', mb: 2 }}>
        <TextField select label="目标平台" value={selected} onChange={(e) => setSelected(e.target.value)} sx={{ minWidth: 180 }} size="small">
          {platforms.map((p) => <MenuItem key={p.id} value={p.id}>{p.name}</MenuItem>)}
        </TextField>
        {currentPlatform && (
          <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
            {minChars > 0 && (
              <Chip
                label={`${minChars}-${maxChars}字/章`}
                size="small" color="primary" variant="outlined"
              />
            )}
            {currentPlatform.climax_interval && (
              <Chip label={`爽点周期: ${currentPlatform.climax_interval}`} size="small" color="secondary" variant="outlined" />
            )}
            {currentPlatform.rhythm_type && (
              <Chip label={currentPlatform.rhythm_type} size="small" variant="outlined" />
            )}
          </Stack>
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
      <Stack direction="row" spacing={2} sx={{ mb: 2 }}>
        <Button variant="outlined" onClick={doCheck} disabled={!chapterText.trim() || loading || diagnosing}>
          {loading ? <CircularProgress size={20} /> : '检查合规性'}
        </Button>
        <Button variant="contained" color="secondary" onClick={doDiagnose} disabled={!chapterText.trim() || loading || diagnosing}>
          {diagnosing ? <CircularProgress size={20} /> : '🎯 签约过稿深度诊断'}
        </Button>
      </Stack>

      {result && (
        <Paper sx={{ p: 2, mb: 2 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
            <Typography variant="subtitle2">合规检查结果</Typography>
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

      {diagnosis && (
        <Paper sx={{ p: 2, mb: 2, borderLeft: (theme) => `4px solid ${diagnosis.grade === 'A' ? theme.palette.success.main : diagnosis.grade === 'B' ? theme.palette.warning.main : theme.palette.error.main}` }}>
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1.5, flexWrap: 'wrap', gap: 1 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>签约过稿诊断报告</Typography>
              <Chip
                label={`评级 ${diagnosis.grade} · 签约概率: ${diagnosis.signingProb}`}
                color={getRatingColor(diagnosis.grade)}
                size="small"
              />
              <Chip
                label={`签约潜力分: ${diagnosis.score} / 100`}
                variant="outlined"
                color={diagnosis.score >= 80 ? 'success' : diagnosis.score >= 60 ? 'warning' : 'error'}
                size="small"
              />
            </Box>
            <Typography variant="caption" color="text.secondary">
              字数: {diagnosis.charCount} | 对话占比: {(diagnosis.dialogueRatio * 100).toFixed(1)}%
            </Typography>
          </Box>

          <Divider sx={{ my: 1.5 }} />

          {diagnosis.vetoRisks.length > 0 && (
            <Box sx={{ mb: 1.5 }}>
              <Typography variant="subtitle2" color="error.main" gutterBottom sx={{ fontWeight: 600 }}>
                🚨 致命劝退点（直接影响编辑初筛签约）:
              </Typography>
              {diagnosis.vetoRisks.map((risk, idx) => (
                <Alert key={idx} severity="error" sx={{ mb: 0.75 }}>
                  {risk}
                </Alert>
              ))}
            </Box>
          )}

          {diagnosis.actionableFixes.length > 0 && (
            <Box sx={{ mt: 1 }}>
              <Typography variant="subtitle2" color="text.primary" gutterBottom sx={{ fontWeight: 600 }}>
                💡 针对性修改建议:
              </Typography>
              {diagnosis.actionableFixes.map((fix, idx) => (
                <Alert key={idx} severity="info" sx={{ mb: 0.75 }}>
                  {fix}
                </Alert>
              ))}
            </Box>
          )}

          {diagnosis.vetoRisks.length === 0 && diagnosis.actionableFixes.length === 0 && (
            <Alert severity="success">
              正文节奏与篇幅极佳，未发现明显编辑劝退项，保持当前水准即可投稿！
            </Alert>
          )}
        </Paper>
      )}

      <Paper sx={{ p: 2 }}>
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
