// M3 质检工作台：检查 / 全书质检 / qc 三 Tab。
import { useState, useEffect, useRef } from 'react'
import Box from '@mui/material/Box'
import ContextHelpButton from './ContextHelpButton'
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
import { hasDesktopBridge, pickPath, type PickKind } from '../desktopBridge'
import type { QualityTaskState, QcReportItem } from '../types'
import { friendlyError } from '../api/client'
import QcVisuals from './QcVisuals'
import PoisonCheckPanel from './PoisonCheckPanel'
import { useI18n } from '../state/I18nContext'

/**
 * 桌面版（Electron）才出现的"选择…"按钮。
 *
 * 浏览器里的网页拿不到真实路径（这也是导入功能走 multipart 上传的原因），
 * 所以非桌面环境下这个按钮干脆不渲染，而不是渲染一个点了没反应的。
 */
function PathPickerButton({ kind, onPicked }: { kind: PickKind; onPicked: (path: string) => void }) {
  const { t } = useI18n()
  if (!hasDesktopBridge()) return null
  return (
    <Button
      variant="outlined"
      onClick={async () => {
        const picked = await pickPath(kind)
        if (picked) onPicked(picked)
      }}
    >
      {kind === 'dir' ? t('quality_btn_pick_dir') : t('quality_btn_pick_file')}
    </Button>
  )
}

const verdictLabel = (v: string | null | undefined, t: (k: string) => string) => {
  if (!v) return v
  const key = `quality_verdict_${v.toLowerCase()}`
  const translated = t(key)
  return translated === key ? v : translated
}

const statusLabel = (s: string | null | undefined, t: (k: string) => string) => {
  if (!s) return s
  const key = `quality_status_${s.toLowerCase()}`
  const translated = t(key)
  return translated === key ? s : translated
}

// 全书质检面板「收起」时最多渲染的问题行数。注意它与后端响应体的 issues_limit（50）不是
// 同一个数：响应体可能在 50 条处截断，而面板收起时只渲染 20 行。只要「屏幕条数 < 声称的
// 总数」就必须说明，且文案里的条数要按实际渲染条数给出，否则会出现「共 61 条，仅显示前
// 50 条」却只有 20 行明细的错误指引。
// 展开入口（2026-09-17）：issues.length 超过本行数时，面板提供「展开全部 / 收起」按钮，
// 展开后渲染响应体内的全部条目（最多 issues_limit 条），提示行同步改写，不再谎报「仅显示前」。
const ISSUE_ROWS = 20

export default function QualityWorkbench() {
  const { t } = useI18n()
  const [tab, setTab] = useState(0)
  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <Box sx={{ display: 'flex', alignItems: 'center', borderBottom: 1, borderColor: 'divider', pr: 1 }}>
        <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ flex: 1, px: 2 }}>
        <Tab label={t('quality_tab_check')} />
        <Tab label={t('quality_tab_book')} />
        <Tab label={t('quality_tab_qc')} />
        <Tab label={t('quality_tab_poison')} />
      </Tabs>
        <ContextHelpButton guideKey="quality" />
      </Box>
      <Box sx={{ flex: 1, minHeight: 0, overflow: 'auto', p: 2 }}>
        {tab === 0 && <CheckPanel />}
        {tab === 1 && <BookQualityPanel />}
        {tab === 2 && <QcPanel />}
        {tab === 3 && <PoisonCheckPanel />}
      </Box>
    </Box>
  )
}

// ---------------------------------------------------------------------------
// 单章检查
// ---------------------------------------------------------------------------

function CheckPanel() {
  const { t } = useI18n()
  const [target, setTarget] = useState('')
  const [text, setText] = useState('')
  const [voice, setVoice] = useState('')
  const [assets, setAssets] = useState<{ id: string; name: string; kind: string }[]>([])
  // genre-pack：后端 /quality/check 支持，之前前端没传导致选了也用不上。
  const [genrePack, setGenrePack] = useState('')
  const [genrePacks, setGenrePacks] = useState<{ id: string; name: string; kind: string }[]>([])
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
      .catch((e) => setError(`${t('quality_check_load_asset_failed')}${e}`))
    // genre-pack 可选：默认不选，保持与之前一致的行为（不传即不用题材包）。
    assetApi.list({ kind: 'genre_pack', limit: 50 })
      .then((j) => {
        const items = ((j as Record<string, unknown>).items ?? []) as { id: string; name: string; kind: string }[]
        setGenrePacks(items)
      })
      .catch(() => setGenrePacks([]))
  }, [t])

  const doCheck = async () => {
    setLoading(true)
    setError('')
    try {
      const body: Record<string, unknown> = {}
      if (target.trim()) body.target = target.trim()
      else if (text.trim()) body.text = text
      if (voice) body.voice = voice
      if (genrePack) body.genre_pack = genrePack
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
      <Typography variant="h6" gutterBottom>{t('quality_check_title')}</Typography>
      <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', mb: 2 }}>
        <TextField label={t('quality_check_target_label')} value={target} onChange={(e) => setTarget(e.target.value)} sx={{ minWidth: 280 }} size="small" />
        <PathPickerButton kind="file" onPicked={setTarget} />
        <TextField select label={t('quality_check_voice_label')} value={voice} onChange={(e) => setVoice(e.target.value)} sx={{ minWidth: 200 }} size="small">
          <MenuItem value="">{t('quality_check_option_none')}</MenuItem>
          {assets.map((a) => <MenuItem key={a.id} value={a.id}>{a.name}</MenuItem>)}
        </TextField>
        <TextField select label={t('quality_check_genre_label')} value={genrePack} onChange={(e) => setGenrePack(e.target.value)} sx={{ minWidth: 200 }} size="small">
          <MenuItem value="">{t('quality_check_option_none')}</MenuItem>
          {genrePacks.map((a) => <MenuItem key={a.id} value={a.id}>{a.name}</MenuItem>)}
        </TextField>
        <Button variant="contained" onClick={doCheck} disabled={loading || (!target.trim() && !text.trim())}>
          {loading ? <CircularProgress size={20} /> : t('quality_check_btn_start')}
        </Button>
      </Box>
      {!target.trim() && (
        <TextField
          label={t('quality_check_text_label')} multiline rows={5} fullWidth value={text}
          onChange={(e) => setText(e.target.value)} sx={{ mb: 2 }} size="small"
        />
      )}
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      {result && (
        <Paper sx={{ p: 2 }}>
          {quality && (
            <Box sx={{ mb: 2 }}>
              <Typography variant="subtitle1">
                {t('quality_check_score_quality')}{quality.score}/100 <Chip label={verdictLabel(quality.verdict, t)} size="small" color={quality.verdict === 'PASS' ? 'success' : quality.verdict === 'WARN' ? 'warning' : 'error'} />
              </Typography>
              {(quality.details ?? []).slice(0, 10).map((d, i) => (
                <Typography key={i} variant="body2" sx={{ fontSize: 12 }}>{d}</Typography>
              ))}
            </Box>
          )}
          {consistency && (
            <Box>
              <Typography variant="subtitle1">{t('quality_check_score_consistency')}{consistency.score?.toFixed(1)}/100</Typography>
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
  const { t, locale } = useI18n()
  const [target, setTarget] = useState('')
  const [result, setResult] = useState<Record<string, unknown> | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  // 展开态是纯本地 UI 状态：切换只改渲染条数，不重新请求后端。
  const [expanded, setExpanded] = useState(false)

  const doBook = async () => {
    setLoading(true)
    setError('')
    // 新结果回到收起态，避免沿用上一份结果的展开态。
    setExpanded(false)
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
  // 屏幕实际渲染条数：收起时取面板上限与响应实收条数的较小者，展开时取响应实收条数。
  const canExpand = issues.length > ISSUE_ROWS
  const isExpanded = canExpand && expanded
  const renderedIssues = isExpanded ? issues : issues.slice(0, ISSUE_ROWS)
  const visibleIssues = renderedIssues.length
  // 两种「列表被砍短」都要说明：响应体被截断（issues_truncated），或仅前端渲染受限
  // （未截断但 issues.length 超过面板行数）。未超行数且未截断时保持静默。
  const issuesCutShort = issuesTruncated || canExpand
  // 提示行必须与屏幕一致：展开且未截断时说明「已显示全部」，不得再说「仅显示前」；
  // 响应体被截断时，即使展开也要保留「响应上限 M 条」并指出去处。
  const cutShortHint = locale === 'en-US'
    ? issuesTruncated
      ? isExpanded
        ? `Total ${totalIssues} issue(s), showing all ${visibleIssues} in response (response limit: ${issuesLimit}). For remainder, please check via CLI or JSON output.`
        : `Total ${totalIssues} issue(s), showing first ${visibleIssues} (response limit: ${issuesLimit})`
      : isExpanded
        ? `Total ${totalIssues} issue(s), showing all ${visibleIssues}`
        : `Total ${totalIssues} issue(s), showing first ${visibleIssues}`
    : issuesTruncated
      ? isExpanded
        ? `共 ${totalIssues} 条，已显示响应内全部 ${visibleIssues} 条（响应上限 ${issuesLimit} 条），超出部分请用 CLI 或 JSON 输出查看`
        : `共 ${totalIssues} 条，仅显示前 ${visibleIssues} 条（响应上限 ${issuesLimit} 条）`
      : isExpanded
        ? `共 ${totalIssues} 条，已显示全部 ${visibleIssues} 条`
        : `共 ${totalIssues} 条，仅显示前 ${visibleIssues} 条`

  return (
    <Box>
      <Typography variant="h6" gutterBottom>{t('quality_book_title')}</Typography>
      <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
        <TextField label={t('quality_book_target_label')} value={target} onChange={(e) => setTarget(e.target.value)} sx={{ minWidth: 320 }} size="small" />
        <PathPickerButton kind="dir" onPicked={setTarget} />
        <Button variant="contained" onClick={doBook} disabled={!target.trim() || loading}>
          {loading ? <CircularProgress size={20} /> : t('quality_book_btn_start')}
        </Button>
      </Box>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      {result && (
        <Paper sx={{ p: 2 }}>
          <Typography variant="subtitle1">
            {t('quality_book_verdict_label')}<Chip label={verdictLabel(verdict, t)} size="small" color={verdict === 'PASS' ? 'success' : verdict === 'WARN' ? 'warning' : 'error'} />
          </Typography>
          <Typography variant="body2" sx={{ mt: 1 }}>
            {locale === 'en-US' ? `Total ${totalIssues} issues` : `共 ${totalIssues} 个问题`}
          </Typography>
          {issuesCutShort && (
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
              {cutShortHint}
            </Typography>
          )}
          {renderedIssues.map((iss, i) => (
            <Typography key={i} variant="body2" sx={{ fontSize: 12 }}>
              [{iss.severity}] {iss.type} {iss.chapter ? `Ch${iss.chapter}` : ''} — {iss.detail}
            </Typography>
          ))}
          {canExpand && (
            <Button size="small" variant="text" onClick={() => setExpanded((v) => !v)} sx={{ mt: 0.5 }}>
              {isExpanded
                ? t('quality_book_collapse')
                : locale === 'en-US'
                  ? `Expand All (Total ${issues.length})`
                  : `展开全部（共 ${issues.length} 条）`}
            </Button>
          )}
        </Paper>
      )}
    </Box>
  )
}

// ---------------------------------------------------------------------------
// QC 综合
// ---------------------------------------------------------------------------

function QcPanel() {
  const { t } = useI18n()
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
      <Typography variant="h6" gutterBottom>{t('quality_qc_title')}</Typography>
      <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
        <TextField label={t('quality_qc_target_label')} value={target} onChange={(e) => setTarget(e.target.value)} sx={{ minWidth: 320 }} size="small" />
        <PathPickerButton kind="dir" onPicked={setTarget} />
        <Button variant="contained" onClick={doQc} disabled={!target.trim() || running}>
          {running ? <CircularProgress size={20} /> : t('quality_qc_btn_start')}
        </Button>
      </Box>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      {taskState && (
        <Paper sx={{ p: 2, mb: 2 }}>
          <Typography variant="subtitle1">
            {t('quality_qc_status_label')}{statusLabel(taskState.status, t)}
            {taskState.verdict && <> | {t('quality_qc_verdict_label')}<Chip label={verdictLabel(taskState.verdict, t)} size="small" color={taskState.verdict === 'PASS' ? 'success' : taskState.verdict === 'WARN' ? 'warning' : 'error'} /></>}
            {taskState.totalScore != null && <> | {t('quality_qc_score_label')}{taskState.totalScore.toFixed(1)}</>}
          </Typography>
          {(taskState.status === 'running' || taskState.status === 'pending') && <LinearProgress sx={{ mt: 1 }} />}
          {taskState.status === 'error' && <Alert severity="error" sx={{ mt: 1 }}>{taskState.error}</Alert>}
          {(taskState.layers ?? []).length > 0 && (
            <Box sx={{ mt: 1 }}>
              {taskState.layers.map((layer) => (
                <Typography key={layer.layer} variant="body2">
                  {layer.layer} {layer.label}：{layer.score?.toFixed(1)}{t('quality_qc_score_suffix')}（{layer.dimensions.length}{t('quality_qc_layer_suffix')}）
                </Typography>
              ))}
            </Box>
          )}
          {taskState.status === 'done' && (taskState.layers ?? []).length > 0 && (
            <Box sx={{ mt: 2 }}>
              <QcVisuals layers={taskState.layers ?? []} issues={taskState.issues ?? []} />
            </Box>
          )}
          {taskState.reportMd && <Alert severity="success" sx={{ mt: 1 }}>{t('quality_qc_report_saved')}{taskState.reportMd}</Alert>}
        </Paper>
      )}

      {reports.length > 0 && (
        <Box>
          <Typography variant="subtitle2" gutterBottom>{t('quality_qc_history_title')}</Typography>
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
