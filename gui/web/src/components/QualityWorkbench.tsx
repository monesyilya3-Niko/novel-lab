// M3 质检工作台：检查 / 全书质检 / qc 三 Tab。
import { useState, useEffect, useRef } from 'react'
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
import Chip from '@mui/material/Chip'
import { qualityApi, assetApi, subscribeTaskEvents } from '../api/client'
import type { QualityTaskState, QcReportItem } from '../types'
import { friendlyError } from '../api/client'
import QcVisuals from './QcVisuals'

const VERDICT_LABELS: Record<string, string> = {
  PASS: '通过',
  WARN: '警告',
  FAIL: '不通过',
}
const verdictLabel = (v: string | null | undefined) => (v ? VERDICT_LABELS[v] ?? v : v)

// 全书质检面板最多渲染的问题行数。注意它与后端响应体的 issues_limit（50）不是同一个
// 数：响应体可能在 50 条处截断，而面板只渲染 20 行。只要「屏幕条数 < 声称的总数」就必须
// 说明，且文案里的条数要按实际渲染条数给出，否则会出现「共 61 条，仅显示前 50 条」
// 却只有 20 行明细的错误指引。
const ISSUE_ROWS = 20

export default function QualityWorkbench() {
  const [tab, setTab] = useState(0)
  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ borderBottom: 1, borderColor: 'divider', px: 2 }}>
        <Tab label="单章检查" />
        <Tab label="全书质检" />
        <Tab label="QC 综合" />
      </Tabs>
      <Box sx={{ flex: 1, overflow: 'auto', p: 2 }}>
        {tab === 0 && <CheckPanel />}
        {tab === 1 && <BookQualityPanel />}
        {tab === 2 && <QcPanel />}
      </Box>
    </Box>
  )
}

// ---------------------------------------------------------------------------
// 单章检查
// ---------------------------------------------------------------------------

function CheckPanel() {
  const [target, setTarget] = useState('')
  const [text, setText] = useState('')
  const [voice, setVoice] = useState('')
  const [assets, setAssets] = useState<{ id: string; name: string; kind: string }[]>([])
  const [result, setResult] = useState<Record<string, unknown> | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    assetApi.list({ kind: 'voice', limit: 50 })
      .then((j) => {
        const items = ((j as Record<string, unknown>).items ?? []) as { id: string; name: string; kind: string }[]
        setAssets(items)
        if (items.length > 0) setVoice(items[0].id)
      })
      .catch((e) => setError(`加载资产失败: ${e}`))
  }, [])

  const doCheck = async () => {
    setLoading(true)
    setError('')
    try {
      const body: Record<string, unknown> = {}
      if (target.trim()) body.target = target.trim()
      else if (text.trim()) body.text = text
      if (voice) body.voice = voice
      const r = await qualityApi.check(body)
      setResult(r)
    } catch (e) {
      setError(friendlyError(e))
    } finally {
      setLoading(false)
    }
  }

  const quality = result?.quality as { score?: number; verdict?: string; details?: string[]; issues?: string[] } | undefined
  const consistency = result?.consistency as { score?: number; details?: string[] } | undefined

  return (
    <Box>
      <Typography variant="h6" gutterBottom>单章检查</Typography>
      <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', mb: 2 }}>
        <TextField label="章节路径（或粘贴文本）" value={target} onChange={(e) => setTarget(e.target.value)} sx={{ minWidth: 280 }} size="small" />
        <TextField select label="voice-card（可选）" value={voice} onChange={(e) => setVoice(e.target.value)} sx={{ minWidth: 200 }} size="small">
          <MenuItem value="">无</MenuItem>
          {assets.map((a) => <MenuItem key={a.id} value={a.id}>{a.name}</MenuItem>)}
        </TextField>
        <Button variant="contained" onClick={doCheck} disabled={loading || (!target.trim() && !text.trim())}>
          {loading ? <CircularProgress size={20} /> : '检查'}
        </Button>
      </Box>
      {!target.trim() && (
        <TextField
          label="或粘贴章节正文" multiline rows={5} fullWidth value={text}
          onChange={(e) => setText(e.target.value)} sx={{ mb: 2 }} size="small"
        />
      )}
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      {result && (
        <Paper sx={{ p: 2 }}>
          {quality && (
            <Box sx={{ mb: 2 }}>
              <Typography variant="subtitle1">
                章节质量：{quality.score}/100 <Chip label={verdictLabel(quality.verdict)} size="small" color={quality.verdict === 'PASS' ? 'success' : quality.verdict === 'WARN' ? 'warning' : 'error'} />
              </Typography>
              {(quality.details ?? []).slice(0, 10).map((d, i) => (
                <Typography key={i} variant="body2" sx={{ fontSize: 12 }}>{d}</Typography>
              ))}
            </Box>
          )}
          {consistency && (
            <Box>
              <Typography variant="subtitle1">一致性：{consistency.score?.toFixed(1)}/100</Typography>
              {(consistency.details ?? []).slice(0, 8).map((d, i) => (
                <Typography key={i} variant="body2" sx={{ fontSize: 12 }}>{d}</Typography>
              ))}
            </Box>
          )}
        </Paper>
      )}
    </Box>
  )
}

// ---------------------------------------------------------------------------
// 全书质检
// ---------------------------------------------------------------------------

function BookQualityPanel() {
  const [target, setTarget] = useState('')
  const [result, setResult] = useState<Record<string, unknown> | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const doBook = async () => {
    setLoading(true)
    setError('')
    try {
      const r = await qualityApi.book({ target })
      setResult(r)
    } catch (e) {
      setError(friendlyError(e))
    } finally {
      setLoading(false)
    }
  }

  const issues = (result?.issues ?? []) as { type?: string; severity?: string; detail?: string; chapter?: number }[]
  const verdict = result?.verdict as string | undefined
  // 2026-09-17（终审 M-5）：book_quality_check 的 issues 最多 issues_limit 条，而
  // total_issues 是真实总数。截断时若不说明，界面会像「共 61 个问题」却只列出 50 条。
  // fix round 2：面板自己还有 ISSUE_ROWS 行上限，「响应未截断但超过行上限」同样要说明。
  const issuesTruncated = result?.issues_truncated === true
  // total_issues 缺失时（旧后端）退回响应实收条数，避免渲染出「共 undefined 条」。
  // fix round 3（M-1）：表头也用它，屏幕上「共 N 个问题」与「共 N 条」统一为真实总数口径，
  // 不再并列出现「共 50 个问题」（响应实收数）与「共 61 条」（真实总数）两个 N。
  const totalIssues = (result?.total_issues as number | undefined) ?? issues.length
  // fix round 3（M-5）：截断为真但 issues_limit 缺失时，用响应实收条数兜底——截断响应里
  // issues.length 恰好等于上限，不会渲染出「响应上限 undefined 条」。
  const issuesLimit = (result?.issues_limit as number | undefined) ?? issues.length
  // 屏幕实际渲染条数：面板上限与响应实收条数的较小者。
  const visibleIssues = Math.min(ISSUE_ROWS, issues.length)
  // 两种「列表被砍短」都要说明：响应体被截断（issues_truncated），或仅前端渲染受限
  // （未截断但 issues.length 超过面板行数）。未超行数且未截断时保持静默。
  const issuesCutShort = issuesTruncated || issues.length > ISSUE_ROWS
  const cutShortHint = issuesTruncated
    ? `共 ${totalIssues} 条，仅显示前 ${visibleIssues} 条（响应上限 ${issuesLimit} 条）`
    : `共 ${totalIssues} 条，仅显示前 ${visibleIssues} 条`

  return (
    <Box>
      <Typography variant="h6" gutterBottom>全书质检</Typography>
      <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
        <TextField label="章节目录路径" value={target} onChange={(e) => setTarget(e.target.value)} sx={{ minWidth: 320 }} size="small" />
        <Button variant="contained" onClick={doBook} disabled={!target.trim() || loading}>
          {loading ? <CircularProgress size={20} /> : '质检'}
        </Button>
      </Box>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      {result && (
        <Paper sx={{ p: 2 }}>
          <Typography variant="subtitle1">
            判定：<Chip label={verdictLabel(verdict)} size="small" color={verdict === 'PASS' ? 'success' : verdict === 'WARN' ? 'warning' : 'error'} />
          </Typography>
          <Typography variant="body2" sx={{ mt: 1 }}>共 {totalIssues} 个问题</Typography>
          {issuesCutShort && (
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
              {cutShortHint}
            </Typography>
          )}
          {issues.slice(0, ISSUE_ROWS).map((iss, i) => (
            <Typography key={i} variant="body2" sx={{ fontSize: 12 }}>
              [{iss.severity}] {iss.type} {iss.chapter ? `Ch${iss.chapter}` : ''} — {iss.detail}
            </Typography>
          ))}
        </Paper>
      )}
    </Box>
  )
}

// ---------------------------------------------------------------------------
// QC 综合
// ---------------------------------------------------------------------------

function QcPanel() {
  const [target, setTarget] = useState('')
  const [running, setRunning] = useState(false)
  const [taskState, setTaskState] = useState<QualityTaskState | null>(null)
  const [reports, setReports] = useState<QcReportItem[]>([])
  const [error, setError] = useState('')
  const sseUnsubRef = useRef<(() => void) | null>(null)

  useEffect(() => {
    qualityApi.reports().then((rs) => setReports(Array.isArray(rs) ? rs : [])).catch(() => setReports([]))
    return () => { sseUnsubRef.current?.() }
  }, [])

  const doQc = async () => {
    setRunning(true)
    setError('')
    setTaskState(null)
    sseUnsubRef.current?.()
    try {
      const r = await qualityApi.qc({ target })
      setTaskState(r)
      if (r.status === 'running' && r.taskId) {
        const unsub = subscribeTaskEvents(r.taskId, async () => {
          try {
            const s = await qualityApi.taskState(r.taskId)
            setTaskState(s)
            if (s.status === 'done' || s.status === 'error') {
              setRunning(false)
              unsub()
              sseUnsubRef.current = null
              qualityApi.reports().then((rs) => setReports(Array.isArray(rs) ? rs : [])).catch(() => setReports([]))
            }
          } catch { /* ignore */ }
        })
        sseUnsubRef.current = unsub
      } else {
        setRunning(false)
      }
    } catch (e) {
      setError(friendlyError(e))
      setRunning(false)
    }
  }

  return (
    <Box>
      <Typography variant="h6" gutterBottom>QC 综合质检（四层十二维）</Typography>
      <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
        <TextField label="章节目录路径" value={target} onChange={(e) => setTarget(e.target.value)} sx={{ minWidth: 320 }} size="small" />
        <Button variant="contained" onClick={doQc} disabled={!target.trim() || running}>
          {running ? <CircularProgress size={20} /> : '开始 QC'}
        </Button>
      </Box>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      {taskState && (
        <Paper sx={{ p: 2, mb: 2 }}>
          <Typography variant="subtitle1">
            状态：{taskState.status}
            {taskState.verdict && <> | 判定：<Chip label={verdictLabel(taskState.verdict)} size="small" color={taskState.verdict === 'PASS' ? 'success' : taskState.verdict === 'WARN' ? 'warning' : 'error'} /></>}
            {taskState.totalScore != null && <> | 总分 {taskState.totalScore.toFixed(1)}</>}
          </Typography>
          {(taskState.status === 'running' || taskState.status === 'pending') && <LinearProgress sx={{ mt: 1 }} />}
          {taskState.status === 'error' && <Alert severity="error" sx={{ mt: 1 }}>{taskState.error}</Alert>}
          {(taskState.layers ?? []).length > 0 && (
            <Box sx={{ mt: 1 }}>
              {taskState.layers.map((layer) => (
                <Typography key={layer.layer} variant="body2">
                  {layer.layer} {layer.label}：{layer.score?.toFixed(1)}分（{layer.dimensions.length} 维）
                </Typography>
              ))}
            </Box>
          )}
          {taskState.status === 'done' && (taskState.layers ?? []).length > 0 && (
            <Box sx={{ mt: 2 }}>
              <QcVisuals layers={taskState.layers ?? []} issues={taskState.issues ?? []} />
            </Box>
          )}
          {taskState.reportMd && <Alert severity="success" sx={{ mt: 1 }}>报告已落盘：{taskState.reportMd}</Alert>}
        </Paper>
      )}

      {reports.length > 0 && (
        <Box>
          <Typography variant="subtitle2" gutterBottom>历史报告</Typography>
          {reports.slice(0, 10).map((r) => (
            <Typography key={r.name} variant="body2" sx={{ fontSize: 12 }}>
              {r.name} — {r.verdict} {r.totalScore != null ? `(${r.totalScore.toFixed(1)})` : ''}
            </Typography>
          ))}
        </Box>
      )}
    </Box>
  )
}
