// M2 写作工作台：三步向导（注入 → 写作 → 打分）+ 组装 Tab。
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
import LinearProgress from '@mui/material/LinearProgress'
import Divider from '@mui/material/Divider'
import { writingApi, subscribeTaskEvents } from '../api/client'
import type { WritingProject, WritingTaskState, ScoreResult } from '../types'

export default function WritingWorkbench() {
  const [tab, setTab] = useState(0)
  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ borderBottom: 1, borderColor: 'divider', px: 2 }}>
        <Tab label="注入" />
        <Tab label="写作" />
        <Tab label="打分" />
        <Tab label="组装" />
      </Tabs>
      <Box sx={{ flex: 1, overflow: 'auto', p: 2 }}>
        {tab === 0 && <InjectPanel />}
        {tab === 1 && <GeneratePanel />}
        {tab === 2 && <ScorePanel />}
        {tab === 3 && <AssemblePanel />}
      </Box>
    </Box>
  )
}

// ---------------------------------------------------------------------------
// 注入面板
// ---------------------------------------------------------------------------

function InjectPanel() {
  const [assets, setAssets] = useState<{ id: string; name: string; kind: string }[]>([])
  const [voice, setVoice] = useState('')
  const [genrePack, setGenrePack] = useState('')
  const [craft, setCraft] = useState('')
  const [prompt, setPrompt] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    fetch('/api/assets?limit=100')
      .then((r) => r.json())
      .then((j) => {
        const items = (j.data?.items ?? []) as { id: string; name: string; kind: string }[]
        setAssets(items)
        const vc = items.find((a) => a.kind === 'voice')
        if (vc) setVoice(vc.id)
        const gp = items.find((a) => a.kind === 'genre_pack')
        if (gp) setGenrePack(gp.id)
        const cc = items.find((a) => a.kind === 'craft')
        if (cc) setCraft(cc.id)
      })
      .catch(() => {})
  }, [])

  const doInject = async () => {
    setLoading(true)
    setError('')
    try {
      const r = await writingApi.inject({ voice, genre_pack: genrePack || undefined, craft: craft || undefined, save: true })
      setPrompt(r.prompt)
    } catch (e) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }

  const byKind = (k: string) => assets.filter((a) => a.kind === k)

  return (
    <Box>
      <Typography variant="h6" gutterBottom>资产注入</Typography>
      <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', mb: 2 }}>
        <TextField select label="voice-card（必选）" value={voice} onChange={(e) => setVoice(e.target.value)} sx={{ minWidth: 220 }} size="small">
          {byKind('voice').map((a) => <MenuItem key={a.id} value={a.id}>{a.name}</MenuItem>)}
        </TextField>
        <TextField select label="genre-pack（可选）" value={genrePack} onChange={(e) => setGenrePack(e.target.value)} sx={{ minWidth: 220 }} size="small">
          <MenuItem value="">无</MenuItem>
          {byKind('genre_pack').map((a) => <MenuItem key={a.id} value={a.id}>{a.name}</MenuItem>)}
        </TextField>
        <TextField select label="craft-card（可选）" value={craft} onChange={(e) => setCraft(e.target.value)} sx={{ minWidth: 220 }} size="small">
          <MenuItem value="">无</MenuItem>
          {byKind('craft').map((a) => <MenuItem key={a.id} value={a.id}>{a.name}</MenuItem>)}
        </TextField>
        <Button variant="contained" onClick={doInject} disabled={!voice || loading}>
          {loading ? <CircularProgress size={20} /> : '生成 Prompt'}
        </Button>
      </Box>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      {prompt && (
        <Paper sx={{ p: 2, maxHeight: 400, overflow: 'auto', bgcolor: '#f5f5f5' }}>
          <Typography variant="caption" color="text.secondary">{prompt.length} 字符</Typography>
          <pre style={{ whiteSpace: 'pre-wrap', fontSize: 12, margin: 0 }}>{prompt}</pre>
        </Paper>
      )}
    </Box>
  )
}

// ---------------------------------------------------------------------------
// 写作面板
// ---------------------------------------------------------------------------

function GeneratePanel() {
  const [projects, setProjects] = useState<WritingProject[]>([])
  const [project, setProject] = useState('')
  const [chapterNo, setChapterNo] = useState(1)
  const [task, setTask] = useState('')
  const [voice, setVoice] = useState('')
  const [assets, setAssets] = useState<{ id: string; name: string; kind: string }[]>([])
  const [running, setRunning] = useState(false)
  const [taskState, setTaskState] = useState<WritingTaskState | null>(null)
  const [error, setError] = useState('')
  const [importContent, setImportContent] = useState('')
  const [importResult, setImportResult] = useState('')

  useEffect(() => {
    writingApi.projects().then(setProjects).catch(() => {})
    fetch('/api/assets?kind=voice&limit=50')
      .then((r) => r.json())
      .then((j) => {
        const items = (j.data?.items ?? []) as { id: string; name: string; kind: string }[]
        setAssets(items)
        if (items.length > 0) setVoice(items[0].id)
      })
      .catch(() => {})
  }, [])

  const doGenerate = async () => {
    setRunning(true)
    setError('')
    setTaskState(null)
    try {
      const r = await writingApi.generate({
        voice, project, chapter_no: chapterNo, task, target_score: 90,
      })
      setTaskState(r)
      if (r.status === 'running' && r.taskId) {
        const unsub = subscribeTaskEvents(r.taskId, async () => {
          try {
            const s = await writingApi.taskState(r.taskId)
            setTaskState(s)
            if (s.status === 'done' || s.status === 'error' || s.status === 'degraded') {
              setRunning(false)
              unsub()
            }
          } catch { /* ignore */ }
        })
      } else {
        setRunning(false)
      }
    } catch (e) {
      setError(String(e))
      setRunning(false)
    }
  }

  const doImport = async () => {
    if (!importContent.trim() || !project) return
    try {
      const r = await writingApi.importChapter({
        project, chapter_no: chapterNo, content: importContent, voice: voice || undefined,
      })
      setImportResult(JSON.stringify(r, null, 2))
    } catch (e) {
      setImportResult(String(e))
    }
  }

  const writableProjects = projects.filter((p) => !p.readOnly)

  return (
    <Box>
      <Typography variant="h6" gutterBottom>写作</Typography>
      <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', mb: 2 }}>
        <TextField select label="项目" value={project} onChange={(e) => setProject(e.target.value)} sx={{ minWidth: 180 }} size="small">
          {writableProjects.map((p) => <MenuItem key={p.id} value={p.id}>{p.name}</MenuItem>)}
        </TextField>
        <TextField label="章节号" type="number" value={chapterNo} onChange={(e) => setChapterNo(Number(e.target.value))} sx={{ width: 100 }} size="small" />
        <TextField select label="voice-card" value={voice} onChange={(e) => setVoice(e.target.value)} sx={{ minWidth: 200 }} size="small">
          {assets.map((a) => <MenuItem key={a.id} value={a.id}>{a.name}</MenuItem>)}
        </TextField>
        <TextField label="写作要点" value={task} onChange={(e) => setTask(e.target.value)} sx={{ minWidth: 250 }} size="small" />
        <Button variant="contained" onClick={doGenerate} disabled={!project || !voice || !task || running}>
          {running ? <CircularProgress size={20} /> : '开始写作'}
        </Button>
      </Box>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      {taskState && (
        <Paper sx={{ p: 2, mb: 2 }}>
          <Typography variant="subtitle2">
            状态：{taskState.status} | 第{taskState.chapterNo}章
            {taskState.attempt ? ` | 第${taskState.attempt}稿` : ''}
          </Typography>
          {taskState.status === 'running' || taskState.status === 'rewriting' || taskState.status === 'scoring' ? (
            <LinearProgress sx={{ mt: 1 }} />
          ) : null}
          {taskState.score != null && (
            <Typography variant="body2" sx={{ mt: 1 }}>
              一致性 {taskState.score.toFixed(1)}/100（目标 {taskState.targetScore}）| 质量 {taskState.qualityScore}/100（及格 {taskState.passLine}）
            </Typography>
          )}
          {taskState.message && <Typography variant="body2" color="text.secondary">{taskState.message}</Typography>}
          {taskState.status === 'degraded' && (
            <Alert severity="info" sx={{ mt: 1 }}>
              {taskState.notice}
              {taskState.guidePath && <><br />指引已落盘：{taskState.guidePath}</>}
            </Alert>
          )}
          {taskState.status === 'error' && <Alert severity="error" sx={{ mt: 1 }}>{taskState.error}</Alert>}
          {taskState.chapterPath && taskState.status === 'done' && (
            <Alert severity="success" sx={{ mt: 1 }}>已落盘：{taskState.chapterPath}</Alert>
          )}
        </Paper>
      )}

      <Divider sx={{ my: 2 }} />
      <Typography variant="subtitle1" gutterBottom>手动入库（无模型时贴回正文）</Typography>
      <TextField
        label="章节正文" multiline rows={6} fullWidth value={importContent}
        onChange={(e) => setImportContent(e.target.value)} sx={{ mb: 1 }} size="small"
      />
      <Button variant="outlined" onClick={doImport} disabled={!importContent.trim() || !project}>
        入库并打分
      </Button>
      {importResult && (
        <Paper sx={{ p: 1, mt: 1, bgcolor: '#f5f5f5' }}>
          <pre style={{ fontSize: 12, margin: 0 }}>{importResult}</pre>
        </Paper>
      )}
    </Box>
  )
}

// ---------------------------------------------------------------------------
// 打分面板
// ---------------------------------------------------------------------------

function ScorePanel() {
  const [assets, setAssets] = useState<{ id: string; name: string; kind: string }[]>([])
  const [voice, setVoice] = useState('')
  const [text, setText] = useState('')
  const [result, setResult] = useState<ScoreResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    fetch('/api/assets?kind=voice&limit=50')
      .then((r) => r.json())
      .then((j) => {
        const items = (j.data?.items ?? []) as { id: string; name: string; kind: string }[]
        setAssets(items)
        if (items.length > 0) setVoice(items[0].id)
      })
      .catch(() => {})
  }, [])

  const doScore = async () => {
    setLoading(true)
    setError('')
    try {
      const r = await writingApi.score({ voice, text })
      setResult(r)
    } catch (e) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }

  return (
    <Box>
      <Typography variant="h6" gutterBottom>双维度打分</Typography>
      <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
        <TextField select label="voice-card" value={voice} onChange={(e) => setVoice(e.target.value)} sx={{ minWidth: 220 }} size="small">
          {assets.map((a) => <MenuItem key={a.id} value={a.id}>{a.name}</MenuItem>)}
        </TextField>
        <Button variant="contained" onClick={doScore} disabled={!voice || !text.trim() || loading}>
          {loading ? <CircularProgress size={20} /> : '打分'}
        </Button>
      </Box>
      <TextField
        label="章节正文" multiline rows={8} fullWidth value={text}
        onChange={(e) => setText(e.target.value)} sx={{ mb: 2 }} size="small"
      />
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      {result && (
        <Paper sx={{ p: 2 }}>
          <Typography variant="subtitle1">
            综合判定：<strong>{result.verdict}</strong> | 及格线 {result.passLine}
          </Typography>
          <Typography variant="body2" sx={{ mt: 1 }}>
            一致性 {result.consistency.score.toFixed(1)}/100 | 质量 {result.quality.score}/100
          </Typography>
          <Box sx={{ mt: 1 }}>
            <Typography variant="caption" color="text.secondary">五维明细：</Typography>
            {result.consistency.details.slice(0, 8).map((d, i) => (
              <Typography key={i} variant="body2" sx={{ fontSize: 12 }}>{d}</Typography>
            ))}
          </Box>
          {result.quality.issues.length > 0 && (
            <Box sx={{ mt: 1 }}>
              <Typography variant="caption" color="error">质量问题：</Typography>
              {result.quality.issues.map((iss, i) => (
                <Typography key={i} variant="body2" sx={{ fontSize: 12, color: 'error.main' }}>{iss}</Typography>
              ))}
            </Box>
          )}
        </Paper>
      )}
    </Box>
  )
}

// ---------------------------------------------------------------------------
// 组装面板
// ---------------------------------------------------------------------------

function AssemblePanel() {
  const [candidates, setCandidates] = useState<{ name: string; passes: string[] }[]>([])
  const [name, setName] = useState('')
  const [genre, setGenre] = useState('campus-redemption')
  const [result, setResult] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    writingApi.assembleCandidates()
      .then((r) => {
        setCandidates(r as { name: string; passes: string[] }[])
        if (r.length > 0) setName((r[0] as { name: string }).name)
      })
      .catch(() => {})
  }, [])

  const doAssemble = async () => {
    setLoading(true)
    try {
      const r = await writingApi.assemble({ name, genre })
      setResult(JSON.stringify(r, null, 2))
    } catch (e) {
      setResult(String(e))
    } finally {
      setLoading(false)
    }
  }

  return (
    <Box>
      <Typography variant="h6" gutterBottom>资产组装</Typography>
      <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
        <TextField select label="书名" value={name} onChange={(e) => setName(e.target.value)} sx={{ minWidth: 200 }} size="small">
          {candidates.map((c) => <MenuItem key={c.name} value={c.name}>{c.name}（{c.passes.length} pass）</MenuItem>)}
        </TextField>
        <TextField label="题材" value={genre} onChange={(e) => setGenre(e.target.value)} sx={{ minWidth: 180 }} size="small" />
        <Button variant="contained" onClick={doAssemble} disabled={!name || !genre || loading}>
          {loading ? <CircularProgress size={20} /> : '组装入库'}
        </Button>
      </Box>
      {result && (
        <Paper sx={{ p: 1, bgcolor: '#f5f5f5' }}>
          <pre style={{ fontSize: 12, margin: 0 }}>{result}</pre>
        </Paper>
      )}
    </Box>
  )
}
