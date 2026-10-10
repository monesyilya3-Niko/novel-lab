// M2 写作工作台：三步向导（注入 → 写作 → 打分）+ 组装 Tab。
import { useState, useEffect, useRef } from 'react'
import Box from '@mui/material/Box'
import ContextHelpButton from './ContextHelpButton'
import InlineGuide from './InlineGuide'
import ChapterEditor from './ChapterEditor'
import TropePanel from './TropePanel'
import Tabs from '@mui/material/Tabs'
import Tab from '@mui/material/Tab'
import Typography from '@mui/material/Typography'
import Button from '@mui/material/Button'
import TextField from '@mui/material/TextField'
import MenuItem from '@mui/material/MenuItem'
import Paper from '@mui/material/Paper'
import Alert from '@mui/material/Alert'
import { useApp } from '../state/AppContext'
import CircularProgress from '@mui/material/CircularProgress'
import LinearProgress from '@mui/material/LinearProgress'
import Divider from '@mui/material/Divider'
import Dialog from '@mui/material/Dialog'
import DialogTitle from '@mui/material/DialogTitle'
import DialogContent from '@mui/material/DialogContent'
import DialogActions from '@mui/material/DialogActions'
import { writingApi, assetApi, subscribeTaskEvents } from '../api/client'
import type { WritingProject, WritingTaskState, ScoreResult } from '../types'
import StylePanel from './StylePanel'
import WritingExtras from './WritingExtras'
import DeslopPanel from './DeslopPanel'
import InspirationWorkbench from './InspirationWorkbench'
import { friendlyError } from '../api/client'
import { useWritingAssets, type WritingAssetSelection } from './useWritingAssets'

// 写作任务状态中文化（后端返回英文 status，直接渲染会让用户困惑）
const WRITING_STATUS_LABELS: Record<string, string> = {
  pending: '等待中',
  running: '写作中',
  rewriting: '改写中',
  scoring: '打分中',
  done: '已完成',
  error: '失败',
}
const writingStatusLabel = (s: string | null | undefined) => (s ? WRITING_STATUS_LABELS[s] ?? s : s)

export default function WritingWorkbench() {
  const [tab, setTab] = useState(0)
  // 注入 / 写作两页签共享同一份资产选择（单真相源）：「注入」页选好的
  // voice / genre-pack，「写作」页签生成章节时会自动用上。
  const sel = useWritingAssets()
  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <Box sx={{ display: 'flex', alignItems: 'center', borderBottom: 1, borderColor: 'divider', pr: 1 }}>
        <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ flex: 1, px: 2 }}>
        <Tab label="注入" />
        <Tab label="写作" />
        <Tab label="打分" />
        <Tab label="组装" />
        <Tab label="文风" />
        <Tab label="创作" />
        <Tab label="去 AI 味" />
        <Tab label="灵感工坊" />
      </Tabs>
        <ContextHelpButton guideKey="writing" />
      </Box>
      <Box sx={{ flex: 1, minHeight: 0, overflow: 'auto', p: 2 }}>
        {tab === 0 && <InjectPanel sel={sel} />}
        {tab === 1 && <GeneratePanel sel={sel} />}
        {tab === 2 && <ScorePanel />}
        {tab === 3 && <AssemblePanel />}
        {tab === 4 && <StylePanel />}
        {tab === 5 && <WritingExtras />}
        {tab === 6 && <DeslopPanel />}
        {tab === 7 && <InspirationWorkbench />}
      </Box>
    </Box>
  )
}

// ---------------------------------------------------------------------------
// 注入面板
// ---------------------------------------------------------------------------

function InjectPanel({ sel }: { sel: WritingAssetSelection }) {
  const { assets, distilledAssets, byKind } = sel
  const { voice, setVoice, genrePack, setGenrePack, craft, setCraft } = sel
  const { distilled, setDistilled, proseCard, setProseCard } = sel
  const [prompt, setPrompt] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const doInject = async () => {
    setLoading(true)
    setError('')
    try {
      const r = await writingApi.inject({
        voice, genre_pack: genrePack || undefined, craft: craft || undefined,
        distilled: distilled || undefined, prose_card: proseCard || undefined, save: true,
      })
      setPrompt(r.prompt)
    } catch (e) {
      setError(friendlyError(e))
    } finally {
      setLoading(false)
    }
  }

  return (
    <Box>
      <Typography variant="h6" gutterBottom>资产注入</Typography>
      <InlineGuide
        what="把拆书得到的资产卡拼成一段完整的写作 Prompt：决定「用谁的声音、按什么规则」写，后面生成章节都会按这套风格来。"
        steps={[
          'voice-card 必选：决定人物声线和叙事风格（来自你拆过的书）。',
          '可选叠加：genre-pack（题材规则）、craft-card（笔法技巧）、蒸馏规则（多本书提炼出的通用规律）、prose-card（跨题材文风参照）。',
          '点「生成 Prompt」可以预览拼好的提示词，确认风格对不对。',
          '这里选好的 voice-card 与 genre-pack，「写作」页签生成章节时会自动用上（同一份选择）。',
        ]}
        tips={[
          '资产列表是空的？先去「分析」工作台导入一本书并完成拆书。',
          '蒸馏规则是离线统计生成的，不需要配置 AI 模型也能用。',
          'voice 与其他资产题材不一致时，后端会按铁律一拒绝（400），请换成同题材资产。',
        ]}
      />
      {assets.length === 0 && (
        <Alert severity="info" sx={{ mb: 2 }}>暂无可用资产，请先在「分析」工作台完成拆书</Alert>
      )}
      {sel.mismatches.length > 0 && (
        <Alert severity="warning" sx={{ mb: 2 }}>
          题材不一致（铁律一：禁止跨题材污染）：voice 为「{sel.voiceGenre}」，{
            sel.mismatches.map((m) => `${m.label}为「${m.genre}」`).join('、')
          }。提交会被后端拒绝（400），请换成同题材资产，或将题材未知的一侧留空。
        </Alert>
      )}
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
        <TextField select label="蒸馏规则（可选）" value={distilled} onChange={(e) => setDistilled(e.target.value)} sx={{ minWidth: 220 }} size="small">
          <MenuItem value="">无</MenuItem>
          {distilledAssets.map((a) => <MenuItem key={a.id} value={a.id}>{a.name}</MenuItem>)}
        </TextField>
        <TextField select label="prose-card（文风参照，可选）" value={proseCard} onChange={(e) => setProseCard(e.target.value)} sx={{ minWidth: 220 }} size="small">
          <MenuItem value="">无</MenuItem>
          {byKind('prose_card').map((a) => <MenuItem key={a.id} value={a.id}>{a.name}</MenuItem>)}
        </TextField>
        <Button variant="contained" onClick={doInject} disabled={!voice || loading}>
          {loading ? <CircularProgress size={20} /> : '生成 Prompt'}
        </Button>
      </Box>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      {prompt && (
        <Paper sx={{ p: 2, maxHeight: 400, overflow: 'auto', bgcolor: 'background.paper' }}>
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

function GeneratePanel({ sel }: { sel: WritingAssetSelection }) {
  // P1-F4：写书目标分来自系统设置，不再硬编码 90。
  const { consistencyTarget } = useApp()
  const [projects, setProjects] = useState<WritingProject[]>([])
  const [project, setProject] = useState('')
  const [chapterNo, setChapterNo] = useState(1)
  const [task, setTask] = useState('')
  // voice / genre-pack 与「注入」页签共享同一份选择（useWritingAssets）：
  // 注入页选好的资产，生成章节时会自动用上；此处可直接调整。
  const { voice, setVoice, genrePack, setGenrePack, byKind } = sel
  const [running, setRunning] = useState(false)
  const [taskState, setTaskState] = useState<WritingTaskState | null>(null)
  const [error, setError] = useState('')
  const [importContent, setImportContent] = useState('')
  const [importResult, setImportResult] = useState('')
  const [importing, setImporting] = useState(false)
  const sseUnsubRef = useRef<(() => void) | null>(null)

  // 组件卸载时清理 SSE 订阅
  useEffect(() => {
    return () => { sseUnsubRef.current?.() }
  }, [])

  useEffect(() => {
    loadProjects()
  }, [])

  const loadProjects = (selectId?: string) => {
    writingApi
      .projects()
      .then((ps) => {
        setProjects(ps)
        if (selectId) setProject(selectId)
      })
      .catch((e) => setError(`加载项目失败: ${e}`))
  }

  // 新建项目对话框
  const [newProjOpen, setNewProjOpen] = useState(false)
  const [newProjName, setNewProjName] = useState('')
  const [creatingProj, setCreatingProj] = useState(false)

  const doCreateProject = async () => {
    const name = newProjName.trim()
    if (!name || creatingProj) return
    setCreatingProj(true)
    setError('')
    try {
      const created = await writingApi.createProject(name)
      setNewProjOpen(false)
      setNewProjName('')
      loadProjects(created.id) // 刷新列表并自动选中新建项目
    } catch (e) {
      setError(`新建项目失败: ${friendlyError(e)}`)
    } finally {
      setCreatingProj(false)
    }
  }

  const doGenerate = async () => {
    setRunning(true)
    setError('')
    setTaskState(null)
    sseUnsubRef.current?.()  // 清理旧订阅
    try {
      const r = await writingApi.generate({
        voice, project, chapter_no: chapterNo, task, target_score: consistencyTarget,
        genre_pack: genrePack || undefined,
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
              sseUnsubRef.current = null
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

  const doImport = async () => {
    if (!importContent.trim() || !project || importing) return
    setImporting(true)
    try {
      const r = await writingApi.importChapter({
        project, chapter_no: chapterNo, content: importContent, voice: voice || undefined,
        genre_pack: genrePack || undefined,
      })
      const summary = r.overwrote
        ? `第 ${r.chapter_no} 章已覆盖（本次 ${r.char_count} 字；字数统计只记增量）`
        : `第 ${r.chapter_no} 章入库成功（${r.char_count} 字）`
      setImportResult(`${summary}\n${JSON.stringify(r, null, 2)}`)
    } catch (e) {
      setImportResult(friendlyError(e))
    } finally {
      setImporting(false)
    }
  }

  const writableProjects = projects.filter((p) => !p.readOnly)

  return (
    <Box>
      <Typography variant="h6" gutterBottom>写作</Typography>
      <InlineGuide
        what="按你的「写作要点」生成新章节：模型写出初稿后自动打分，不达标就自动改写，直到达标或用完改写次数。写好的章节会落盘保存。"
        steps={[
          '选项目：项目就是用户数据目录 novel/ 下的文件夹——在 novel/ 下新建一个文件夹，就是一个新写作项目。',
          'voice-card 与 genre-pack 沿用「注入」页签的选择（同一份），这里可以直接调整。',
          '选章节号、写「写作要点」：交代本章发生什么、谁出场、情绪走向、字数和结尾要求，越具体越好。',
          '点「开始写作」，进度实时显示；完成后会提示章节文件的保存位置。',
        ]}
        example={'第5章：深秋傍晚，温霜禾抱着一摞粉色包装的礼物盒走进澜州老街的奶茶店，点了七分糖的芋泥波波奶茶。江春屿跟在后面替她拎包。两人因为"谁请客"斗嘴，温霜禾说了句"随便吧"——其实是生气了。要求：2200字左右，对话占四成，结尾留钩子：温霜禾发现奶茶店落地窗外站着一个熟悉的身影。'}
        tips={[
          '没配 AI 模型也能用：会进入降级模式，生成一份「AI接管写作任务.md」指引，你可以手动写完，再用下面的「手动入库」贴回来打分。',
          '「写作要点」决定了章节质量：只写"写一章校园恋爱"效果会很差，把人物、场景、冲突、字数都写清楚。',
        ]}
        defaultOpen
      />
      {sel.mismatches.length > 0 && (
        <Alert severity="warning" sx={{ mb: 2 }}>
          题材不一致（铁律一：禁止跨题材污染）：voice 为「{sel.voiceGenre}」，{
            sel.mismatches.map((m) => `${m.label}为「${m.genre}」`).join('、')
          }。提交会被后端拒绝（400），请换成同题材资产。
        </Alert>
      )}
      <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', mb: 2 }}>
        <TextField select label="项目" value={project} onChange={(e) => setProject(e.target.value)} sx={{ minWidth: 180 }} size="small">
          {writableProjects.map((p) => <MenuItem key={p.id} value={p.id}>{p.name}</MenuItem>)}
        </TextField>
        <Button variant="outlined" size="small" onClick={() => { setNewProjName(''); setNewProjOpen(true) }} sx={{ alignSelf: 'center' }}>
          新建项目
        </Button>
        <Dialog open={newProjOpen} onClose={() => setNewProjOpen(false)} maxWidth="xs" fullWidth>
          <DialogTitle>新建写作项目</DialogTitle>
          <DialogContent>
            <TextField
              autoFocus
              fullWidth
              label="项目名"
              value={newProjName}
              onChange={(e) => setNewProjName(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') doCreateProject() }}
              helperText="会作为目录名使用：不能包含 / \，不能叫 default"
              sx={{ mt: 1 }}
            />
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setNewProjOpen(false)}>取消</Button>
            <Button variant="contained" onClick={doCreateProject} disabled={!newProjName.trim() || creatingProj}>
              {creatingProj ? '创建中…' : '创建'}
            </Button>
          </DialogActions>
        </Dialog>
        <TextField label="章节号" type="number" value={chapterNo} onChange={(e) => setChapterNo(Math.max(1, Math.round(Number(e.target.value) || 1)))} sx={{ width: 100 }} size="small" />
        <TextField select label="voice-card" value={voice} onChange={(e) => setVoice(e.target.value)} sx={{ minWidth: 200 }} size="small">
          {byKind('voice').map((a) => <MenuItem key={a.id} value={a.id}>{a.name}</MenuItem>)}
        </TextField>
        <TextField select label="genre-pack（可选）" value={genrePack} onChange={(e) => setGenrePack(e.target.value)} sx={{ minWidth: 200 }} size="small">
          <MenuItem value="">无</MenuItem>
          {byKind('genre_pack').map((a) => <MenuItem key={a.id} value={a.id}>{a.name}</MenuItem>)}
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
            状态：{writingStatusLabel(taskState.status)} | 第{taskState.chapterNo}章
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
      <TropePanel
        currentGenre={sel.voiceGenre}
        taskText={task}
        onInsert={(text) => setTask((prev) => (prev ? `${prev}\n${text}` : text))}
      />
      <Divider sx={{ my: 2 }} />
      <Typography variant="subtitle1" gutterBottom>手动入库（无模型时贴回正文）</Typography>
      <Box sx={{ mb: 1 }}>
        <ChapterEditor
          value={importContent}
          onChange={setImportContent}
          placeholder="把在别处写好的章节正文粘贴到这里……"
          targetChars={1500}
        />
      </Box>
      <Button variant="outlined" onClick={doImport} disabled={!importContent.trim() || !project || importing}>
        入库并打分
      </Button>
      {importResult && (
        <Paper sx={{ p: 1, mt: 1, bgcolor: 'background.paper' }}>
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
    assetApi.list({ kind: 'voice', limit: 50 })
      .then((j) => {
        const items = ((j as Record<string, unknown>).items ?? []) as { id: string; name: string; kind: string }[]
        setAssets(items)
        if (items.length > 0) setVoice(items[0].id)
      })
      .catch((e) => setError(`加载资产失败: ${e}`))
  }, [])

  const doScore = async () => {
    setLoading(true)
    setError('')
    try {
      const r = await writingApi.score({ voice, text })
      setResult(r)
    } catch (e) {
      setError(friendlyError(e))
    } finally {
      setLoading(false)
    }
  }

  return (
    <Box>
      <Typography variant="h6" gutterBottom>双维度打分</Typography>
      <InlineGuide
        what="给一段章节正文打分：从「风格一致性」（像不像这张声线卡的味道）和「写作质量」（有没有硬伤）两个维度判定，低于及格线会列出具体问题。"
        steps={[
          '选一张 voice-card 作为参照标准。',
          '把章节正文粘贴进来，点「打分」。',
          '看综合判定：一致性得分 + 质量得分，以及五维明细和质量问题列表。',
          '分数不够就按列出的问题改，改完可以再打一次。',
        ]}
        tips={[
          '及格线可以在「设置」工作台里调整。',
          '打分不需要 AI 模型，是本地规则引擎跑的。',
        ]}
      />
      <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
        <TextField select label="voice-card" value={voice} onChange={(e) => setVoice(e.target.value)} sx={{ minWidth: 220 }} size="small">
          {assets.map((a) => <MenuItem key={a.id} value={a.id}>{a.name}</MenuItem>)}
        </TextField>
        <Button variant="contained" onClick={doScore} disabled={!voice || !text.trim() || loading}>
          {loading ? <CircularProgress size={20} /> : '打分'}
        </Button>
      </Box>
      <Box sx={{ mb: 2 }}>
        <ChapterEditor
          value={text}
          onChange={setText}
          placeholder="把要打分的章节正文粘贴到这里……"
          targetChars={1500}
        />
      </Box>
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
            {/* P2-F17：截断时提示剩余条数 */}
            {result.consistency.details.length > 8 && (
              <Typography variant="caption" color="text.secondary">
                还有 {result.consistency.details.length - 8} 条未显示
              </Typography>
            )}
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
  // P2-F14：默认题材改为空，必须显式选择，避免误用 campus-redemption。
  const [genre, setGenre] = useState('')
  const [result, setResult] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    writingApi.assembleCandidates()
      .then((r) => {
        setCandidates(r as { name: string; passes: string[] }[])
        if (r.length > 0) setName((r[0] as { name: string }).name)
      })
      .catch((e) => setError(`加载候选失败: ${e}`))
  }, [])

  const doAssemble = async () => {
    setLoading(true)
    try {
      const r = await writingApi.assemble({ name, genre })
      setResult(JSON.stringify(r, null, 2))
    } catch (e) {
      setResult(friendlyError(e))
    } finally {
      setLoading(false)
    }
  }

  return (
    <Box>
      <Typography variant="h6" gutterBottom>资产组装</Typography>
      <InlineGuide
        what="把一本书多轮拆书（pass1-5）的产出组装成正式资产并入库：书名选已完成全部 pass 的书，填上题材，组装后资产就能在注入和写作里用了。"
        steps={[
          '从下拉里选一本已完成 pass1-5 的书。',
          '填写题材（如：校园、玄幻、悬疑）——题材决定了资产的隔离分组，填错会导致注入时选不到。',
          '点「组装入库」，产出 voice-card / structure-obs 等正式资产。',
        ]}
        tips={[
          '列表是空的？说明还没有书跑完 pass1-5，先去「分析」工作台完成拆书。',
        ]}
      />
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      {candidates.length === 0 && !error && (
        <Alert severity="info" sx={{ mb: 2 }}>暂无可组装的书目（需先完成 pass1-5）</Alert>
      )}
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
        <Paper sx={{ p: 1, bgcolor: 'background.paper' }}>
          <pre style={{ fontSize: 12, margin: 0 }}>{result}</pre>
        </Paper>
      )}
    </Box>
  )
}
