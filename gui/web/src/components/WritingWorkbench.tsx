// M2 写作工作台：一屏三栏沉浸创作室（Studio）+ 专业工坊流水线（Pipeline）。
import { useState, useEffect, useRef, useMemo } from 'react'
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
import Chip from '@mui/material/Chip'
import IconButton from '@mui/material/IconButton'
import Tooltip from '@mui/material/Tooltip'
import Card from '@mui/material/Card'
import LinearProgress from '@mui/material/LinearProgress'
import CircularProgress from '@mui/material/CircularProgress'
import Divider from '@mui/material/Divider'
import Dialog from '@mui/material/Dialog'
import DialogTitle from '@mui/material/DialogTitle'
import DialogContent from '@mui/material/DialogContent'
import DialogActions from '@mui/material/DialogActions'
import Snackbar from '@mui/material/Snackbar'
import EditNoteIcon from '@mui/icons-material/EditNote'
import SecurityIcon from '@mui/icons-material/Security'
import SaveIcon from '@mui/icons-material/Save'
import SettingsSuggestIcon from '@mui/icons-material/SettingsSuggest'
import PersonIcon from '@mui/icons-material/Person'
import ContentCopyIcon from '@mui/icons-material/ContentCopy'
import InputIcon from '@mui/icons-material/Input'
import TuneIcon from '@mui/icons-material/Tune'
import ViewSidebarIcon from '@mui/icons-material/ViewSidebar'
import AssessmentIcon from '@mui/icons-material/Assessment'
import TrendingUpIcon from '@mui/icons-material/TrendingUp'
import FileDownloadIcon from '@mui/icons-material/FileDownload'
import AddIcon from '@mui/icons-material/Add'
import NavigateNextIcon from '@mui/icons-material/NavigateNext'
import NotificationsActiveIcon from '@mui/icons-material/NotificationsActive'
import {
  writingApi,
  toolsApi,
  platformApi,
  essenceApi,
  assetApi,
  subscribeTaskEvents,
  friendlyError,
  type PoisonCheckResult,
  type DeslopResult,
  type ProjectMeta,
  type EssenceAsset,
  type OutlineItem,
  type CharacterCard,
  type NoteItem,
  type WritingStats,
  type SubmissionDiagnosisResult,
  type EssenceChain,
} from '../api/client'
import type { WritingProject, WritingTaskState, ScoreResult } from '../types'
import { useApp } from '../state/AppContext'
import StylePanel from './StylePanel'
import WritingExtras from './WritingExtras'
import DeslopPanel from './DeslopPanel'
import InspirationWorkbench from './InspirationWorkbench'
import EssenceWorkbench from './EssenceWorkbench'
import { useWritingAssets, type WritingAssetSelection } from './useWritingAssets'

// 写作任务状态中文化
const WRITING_STATUS_LABELS: Record<string, string> = {
  pending: '等待中',
  running: '写作中',
  rewriting: '改写中',
  scoring: '打分中',
  done: '已完成',
  error: '失败',
}
const writingStatusLabel = (s: string | null | undefined) => (s ? WRITING_STATUS_LABELS[s] ?? s : s)

export interface WritingWorkbenchProps {
  initialMode?: 'studio' | 'pipeline'
  initialPipelineTab?: number
}

export default function WritingWorkbench({
  initialMode,
  initialPipelineTab = 0,
}: WritingWorkbenchProps = {}) {
  // 若环境未提供 getProjectMeta（如仅针对资产注入面板的遗留测试），自动以工坊流水线模式运行保持兼容
  const defaultMode =
    initialMode ?? (typeof writingApi?.getProjectMeta === 'function' ? 'studio' : 'pipeline')
  const [mode, setMode] = useState<'studio' | 'pipeline'>(defaultMode)
  const [pipelineTab, setPipelineTab] = useState(initialPipelineTab)
  const sel = useWritingAssets()

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* 顶部主工作台模式切换栏 */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          borderBottom: 1,
          borderColor: 'divider',
          px: 2,
          py: 0.5,
          bgcolor: 'background.paper',
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Tabs
            value={mode}
            onChange={(_, v) => setMode(v)}
            sx={{
              minHeight: 40,
              '& .MuiTab-root': { minHeight: 40, py: 0.5, fontWeight: 'bold' },
            }}
          >
            <Tab
              value="studio"
              icon={<EditNoteIcon fontSize="small" />}
              iconPosition="start"
              label="沉浸创作室 (Studio)"
            />
            <Tab
              value="pipeline"
              icon={<TuneIcon fontSize="small" />}
              iconPosition="start"
              label="工坊流水线 (Pipeline)"
            />
          </Tabs>
        </Box>

        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <ContextHelpButton guideKey="writing" />
        </Box>
      </Box>

      {/* 主体工作区 */}
      <Box sx={{ flex: 1, minHeight: 0, overflow: 'hidden' }}>
        {mode === 'studio' ? (
          <StudioView sel={sel} onSwitchPipeline={() => setMode('pipeline')} />
        ) : (
          <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
            <Box sx={{ borderBottom: 1, borderColor: 'divider', px: 2, bgcolor: 'background.paper' }}>
              <Tabs
                value={pipelineTab}
                onChange={(_, v) => setPipelineTab(v)}
                sx={{ minHeight: 40 }}
                variant="scrollable"
                scrollButtons="auto"
              >
                <Tab label="资产注入" />
                <Tab label="AI 章节生成" />
                <Tab label="单章质检打分" />
                <Tab label="拆书资产组装" />
                <Tab label="文风模型分析" />
                <Tab label="创作者企划中心" />
                <Tab label="去 AI 味实验室" />
                <Tab label="灵感与毒点避雷工坊" />
                <Tab label="小说精华数据库" />
              </Tabs>
            </Box>
            <Box sx={{ flex: 1, minHeight: 0, overflow: 'auto', p: 2 }}>
              {pipelineTab === 0 && <InjectPanel sel={sel} />}
              {pipelineTab === 1 && <GeneratePanel sel={sel} />}
              {pipelineTab === 2 && <ScorePanel />}
              {pipelineTab === 3 && <AssemblePanel />}
              {pipelineTab === 4 && <StylePanel />}
              {pipelineTab === 5 && <WritingExtras />}
              {pipelineTab === 6 && <DeslopPanel />}
              {pipelineTab === 7 && <InspirationWorkbench />}
              {pipelineTab === 8 && <EssenceWorkbench />}
            </Box>
          </Box>
        )}
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

// ---------------------------------------------------------------------------
// 沉浸式创作室 (StudioView)：一屏三栏闭环生产力
// ---------------------------------------------------------------------------

const PLATFORM_LABELS: Record<string, { name: string; color: 'default' | 'primary' | 'secondary' | 'error' | 'info' | 'success' | 'warning' }> = {
  general: { name: '通用平台', color: 'default' },
  fanqie: { name: '番茄小说', color: 'error' },
  qidian: { name: '起点中文网', color: 'primary' },
  jinjiang: { name: '晋江文学城', color: 'secondary' },
  qimao: { name: '七猫中文网', color: 'warning' },
  zhihu: { name: '知乎盐选', color: 'info' },
}

interface StudioViewProps {
  sel: WritingAssetSelection
  onSwitchPipeline: () => void
}

function StudioView({ sel, onSwitchPipeline }: StudioViewProps) {
  const [projects, setProjects] = useState<WritingProject[]>([])
  const [currentProject, setCurrentProject] = useState<string>('')
  const [meta, setMeta] = useState<ProjectMeta | null>(null)
  const [outlines, setOutlines] = useState<OutlineItem[]>([])
  const [characters, setCharacters] = useState<CharacterCard[]>([])
  const [notes, setNotes] = useState<NoteItem[]>([])
  const [stats, setStats] = useState<WritingStats | null>(null)

  // 中栏编辑状态
  const [chapterNo, setChapterNo] = useState<number>(1)
  const [chapterTitle, setChapterTitle] = useState<string>('第1章 惊变')
  const [content, setContent] = useState<string>(
    '寒风呼啸，少年林凡握紧手中残破铁剑，凝视着眼前深不见底的万丈深渊。宗门考核长老的冷笑声犹在耳畔，但他胸膛内那颗沉寂已久的神秘石珠，正隐隐泛起滚烫的微光。'
  )
  const [saving, setSaving] = useState<boolean>(false)

  // 本地草稿自动暂存 Key（防丢稿机制）
  const getDraftKey = (proj: string, ch: number) => `novel_draft_${proj}_ch${ch}`

  // 监听内容变动，自动同步到本地草稿缓存
  useEffect(() => {
    if (!currentProject || !content) return
    try {
      localStorage.setItem(getDraftKey(currentProject, chapterNo), content)
    } catch (_e) {
      void _e
    }
  }, [content, currentProject, chapterNo])

  // 左右栏交互
  const [leftTab, setLeftTab] = useState<'outlines' | 'characters' | 'notes'>('outlines')
  const [rightOpen, setRightOpen] = useState<boolean>(true)
  const [rightTab, setRightTab] = useState<'check' | 'essence' | 'generate'>('check')

  // 右栏诊断数据
  const [poisonLoading, setPoisonLoading] = useState(false)
  const [poisonResult, setPoisonResult] = useState<PoisonCheckResult | null>(null)
  const [deslopLoading, setDeslopLoading] = useState(false)
  const [deslopResult, setDeslopResult] = useState<DeslopResult | null>(null)
  const [diagLoading, setDiagLoading] = useState(false)
  const [diagResult, setDiagResult] = useState<SubmissionDiagnosisResult | null>(null)

  // 右栏精华反哺数据与伏笔暗线
  const [essenceAssets, setEssenceAssets] = useState<EssenceAsset[]>([])
  const [essenceCategory, setEssenceCategory] = useState<string>('all')
  const [chains, setChains] = useState<EssenceChain[]>([])
  const [essenceSubTab, setEssenceSubTab] = useState<'assets' | 'chains'>('assets')

  // 对话框状态：企划定位、新建作品、全书导出、新建大纲、新建人设、新建便签、新建暗线
  const [openMetaDialog, setOpenMetaDialog] = useState(false)
  const [metaPlatform, setMetaPlatform] = useState('fanqie')
  const [metaGenre, setMetaGenre] = useState('xianxia')
  const [metaTargetWords, setMetaTargetWords] = useState(1000000)
  const [metaSummary, setMetaSummary] = useState('')
  const [openNewProj, setOpenNewProj] = useState(false)
  const [newProjName, setNewProjName] = useState('')

  const [openExportDialog, setOpenExportDialog] = useState(false)
  const [exportFormat, setExportFormat] = useState<'docx' | 'md' | 'txt'>('docx')
  const [exporting, setExporting] = useState(false)

  const [openNewOutline, setOpenNewOutline] = useState(false)
  const [newOutlineTitle, setNewOutlineTitle] = useState('')
  const [newOutlineSummary, setNewOutlineSummary] = useState('')

  const [openNewChar, setOpenNewChar] = useState(false)
  const [newCharName, setNewCharName] = useState('')
  const [newCharRole, setNewCharRole] = useState('主角')
  const [newCharDesc, setNewCharDesc] = useState('')

  const [openNewNote, setOpenNewNote] = useState(false)
  const [newNoteTitle, setNewNoteTitle] = useState('')
  const [newNoteContent, setNewNoteContent] = useState('')

  const [openNewChain, setOpenNewChain] = useState(false)
  const [newChainTitle, setNewChainTitle] = useState('')
  const [newChainCategory, setNewChainCategory] = useState('identity')
  const [newChainPlant, setNewChainPlant] = useState(1)
  const [newChainReveal, setNewChainReveal] = useState(5)
  const [newChainClimax, setNewChainClimax] = useState(10)
  const [newChainDesc, setNewChainDesc] = useState('')

  const [toast, setToast] = useState('')
  const [error, setError] = useState('')

  // 计算当前章对应的伏笔协同推进节点
  const activeForeshadowings = useMemo(() => {
    return chains
      .map((c) => {
        if (c.plantChapter === chapterNo) {
          return { chain: c, stage: 'plant', stageName: '埋设初期' }
        }
        if (c.revealChapter === chapterNo) {
          return { chain: c, stage: 'reveal', stageName: '显露推进' }
        }
        if (c.climaxChapter === chapterNo) {
          return { chain: c, stage: 'climax', stageName: '高潮回收' }
        }
        return null
      })
      .filter((item): item is { chain: EssenceChain; stage: string; stageName: string } => item !== null)
  }, [chains, chapterNo])

  // 加载项目列表与当前项目关联信息
  const loadProjects = async () => {
    try {
      const ps = await writingApi.projects()
      setProjects(ps)
      if (ps.length > 0 && !ps.some((p) => p.name === currentProject)) {
        setCurrentProject(ps[0].name)
      }
    } catch (e) {
      setError(`加载项目失败: ${friendlyError(e)}`)
    }
  }

  const loadProjectData = async (projName: string) => {
    if (!projName) return
    try {
      const [metaRes, outlineRes, charRes, noteRes, statsRes, chainRes] = await Promise.all([
        writingApi.getProjectMeta(projName).catch(() => null),
        writingApi.outlines(projName).catch(() => []),
        writingApi.characters(projName).catch(() => []),
        writingApi.notes(projName).catch(() => []),
        writingApi.stats(projName, 30).catch(() => null),
        essenceApi?.listChains ? essenceApi.listChains(projName).catch(() => ({ chains: [] })) : Promise.resolve({ chains: [] }),
      ])
      setMeta(metaRes)
      if (metaRes) {
        setMetaPlatform(metaRes.platform || 'fanqie')
        setMetaGenre(metaRes.genre || 'xianxia')
        setMetaTargetWords(metaRes.targetWords || 1000000)
        setMetaSummary(metaRes.summary || '')
      }
      setOutlines(outlineRes || [])
      setCharacters(charRes || [])
      setNotes(noteRes || [])
      setStats(statsRes)
      const loadedChains = (chainRes as { chains?: EssenceChain[] })?.chains || []
      if (loadedChains.length > 0) {
        setChains(loadedChains)
      } else if (essenceApi?.listChains) {
        const fallback = await essenceApi.listChains().catch(() => ({ chains: [] }))
        setChains(fallback.chains || [])
      }
    } catch (e) {
      console.warn('加载项目详情失败', e)
    }
  }

  const loadEssenceAssets = async () => {
    try {
      const cat = essenceCategory === 'all' ? undefined : essenceCategory
      const res = await essenceApi.listAssets({ category: cat })
      setEssenceAssets(res.assets || [])
    } catch (e) {
      console.warn('加载精华资产失败', e)
    }
  }

  useEffect(() => {
    loadProjects()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (currentProject) {
      loadProjectData(currentProject)
    }
  }, [currentProject])

  useEffect(() => {
    loadEssenceAssets()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [essenceCategory])

  // 新建项目
  const handleCreateProject = async () => {
    if (!newProjName.trim()) return
    try {
      const p = await writingApi.createProject(newProjName.trim())
      setOpenNewProj(false)
      setNewProjName('')
      setToast(`小说工程《${p.name}》已创建`)
      setCurrentProject(p.name)
      loadProjects()
    } catch (e) {
      setError(friendlyError(e))
    }
  }

  // 保存企划 Meta
  const handleSaveMeta = async () => {
    try {
      const updated = await writingApi.updateProjectMeta(currentProject, {
        platform: metaPlatform,
        genre: metaGenre,
        target_words: metaTargetWords,
        summary: metaSummary,
      })
      setMeta(updated)
      setOpenMetaDialog(false)
      setToast('作品企划定位已保存并持久化')
    } catch (e) {
      setError(friendlyError(e))
    }
  }

  // 触发文件下载
  const triggerDownload = (blob: Blob, filename: string) => {
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  }

  // 全书导出
  const handleExportProject = async (format: 'docx' | 'md' | 'txt') => {
    setExporting(true)
    setError('')
    try {
      const res = await writingApi.export(currentProject, format)
      if (format === 'docx' && res.contentBase64) {
        const bin = atob(res.contentBase64)
        const bytes = new Uint8Array(bin.length)
        for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i)
        const blob = new Blob([bytes], {
          type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        })
        triggerDownload(blob, res.filename)
      } else {
        const blob = new Blob([res.content || ''], { type: 'text/plain;charset=utf-8' })
        triggerDownload(blob, res.filename)
      }
      setToast(`全书已成功导出为 ${res.filename}（共 ${res.chapters} 章，${res.words.toLocaleString()} 字）`)
      setOpenExportDialog(false)
    } catch (e) {
      setError(`导出失败: ${friendlyError(e)}`)
    } finally {
      setExporting(false)
    }
  }

  // 下一章快捷切换（带本地草稿记忆防误触）
  const handleNextChapter = () => {
    if (content.trim()) {
      try {
        localStorage.setItem(getDraftKey(currentProject, chapterNo), content)
      } catch (_e) {
        void _e
      }
    }
    const next = chapterNo + 1
    setChapterNo(next)
    setChapterTitle(`第${next}章`)
    let savedDraft = ''
    try {
      savedDraft = localStorage.getItem(getDraftKey(currentProject, next)) || ''
    } catch (_e) {
      void _e
    }
    setContent(savedDraft)
    setToast(`已准备好开启第 ${next} 章创作${savedDraft ? '（已自动恢复本章本地草稿）' : ''}`)
  }

  // 快捷创建章节大纲
  const handleCreateOutline = async () => {
    if (!newOutlineTitle.trim()) return
    try {
      await writingApi.createOutline({
        project: currentProject,
        title: newOutlineTitle.trim(),
        summary: newOutlineSummary.trim(),
        kind: 'chapter',
        status: 'planned',
      })
      setOpenNewOutline(false)
      setNewOutlineTitle('')
      setNewOutlineSummary('')
      setToast('新章节大纲已规划入库')
      loadProjectData(currentProject)
    } catch (e) {
      setError(friendlyError(e))
    }
  }

  // 快捷创建人物卡
  const handleCreateCharacter = async () => {
    if (!newCharName.trim()) return
    try {
      await writingApi.createCharacter({
        project: currentProject,
        name: newCharName.trim(),
        role: newCharRole,
        description: newCharDesc.trim(),
      })
      setOpenNewChar(false)
      setNewCharName('')
      setNewCharDesc('')
      setToast(`人物卡【${newCharName}】已创建`)
      loadProjectData(currentProject)
    } catch (e) {
      setError(friendlyError(e))
    }
  }

  // 快捷创建便签
  const handleCreateNote = async () => {
    if (!newNoteTitle.trim()) return
    try {
      await writingApi.createNote({
        project: currentProject,
        title: newNoteTitle.trim(),
        content: newNoteContent.trim(),
      })
      setOpenNewNote(false)
      setNewNoteTitle('')
      setNewNoteContent('')
      setToast('灵感便签已保存')
      loadProjectData(currentProject)
    } catch (e) {
      setError(friendlyError(e))
    }
  }

  // 快捷创建伏笔暗线
  const handleCreateChain = async () => {
    if (!newChainTitle.trim()) return
    try {
      await essenceApi.createChain({
        book_id: currentProject,
        title: newChainTitle.trim(),
        category: newChainCategory,
        plant_chapter: newChainPlant,
        reveal_chapter: newChainReveal,
        climax_chapter: newChainClimax,
        description: newChainDesc.trim(),
      })
      setOpenNewChain(false)
      setNewChainTitle('')
      setNewChainDesc('')
      setToast(`伏笔暗线【${newChainTitle}】已建档并启动追踪`)
      loadProjectData(currentProject)
    } catch (e) {
      setError(friendlyError(e))
    }
  }

  // 章节保存入库
  const handleSaveChapter = async () => {
    if (!content.trim()) {
      setError('章节正文不能为空')
      return
    }
    setSaving(true)
    setError('')
    try {
      const r = await writingApi.importChapter({
        project: currentProject,
        chapter_no: chapterNo,
        title: chapterTitle.trim() || `第${chapterNo}章`,
        content: content,
      })
      setToast(`第 ${chapterNo} 章已入库！共 ${r.char_count} 字（${r.overwrote ? '覆盖旧章' : '新增章节'}）`)
      try {
        localStorage.removeItem(getDraftKey(currentProject, chapterNo))
      } catch (_e) {
        void _e
      }
      // 重新加载统计与大纲
      loadProjectData(currentProject)
    } catch (e) {
      setError(friendlyError(e))
    } finally {
      setSaving(false)
    }
  }

  // 一键全维排毒与去AI检测
  const handleRunFullCheck = async () => {
    if (!content.trim()) {
      setError('请先在编辑器输入或生成正文')
      return
    }
    setRightOpen(true)
    setRightTab('check')
    setPoisonLoading(true)
    setDeslopLoading(true)
    setError('')
    try {
      const [pRes, dRes] = await Promise.all([
        toolsApi.checkPoison(content),
        writingApi.deslop(content),
      ])
      setPoisonResult(pRes)
      setDeslopResult(dRes)
      setToast('正文排毒与 AI 指纹检测已完成')
    } catch (e) {
      setError(`排查检测失败: ${friendlyError(e)}`)
    } finally {
      setPoisonLoading(false)
      setDeslopLoading(false)
    }
  }

  // 多平台签约过稿预测
  const handleRunPlatformDiagnose = async () => {
    if (!content.trim()) {
      setError('请先在编辑器输入正文')
      return
    }
    setRightOpen(true)
    setRightTab('check')
    setDiagLoading(true)
    setError('')
    try {
      const targetPlatform = meta?.platform || 'fanqie'
      const res = await platformApi.diagnose({
        platform_id: targetPlatform,
        chapter_text: content,
        chapter_title: chapterTitle,
        chapter_num: chapterNo,
      })
      setDiagResult(res)
      setToast(`已完成针对《${PLATFORM_LABELS[targetPlatform]?.name || targetPlatform}》的签约深度评级`)
    } catch (e) {
      setError(`签约诊断失败: ${friendlyError(e)}`)
    } finally {
      setDiagLoading(false)
    }
  }

  // 精华资产/人设一键插入正文
  const insertTextToEditor = (textToInsert: string, label: string) => {
    setContent((prev) => (prev ? `${prev}\n\n${textToInsert}` : textToInsert))
    setToast(`已成功将【${label}】插入当前正文`)
  }

  const platformInfo = PLATFORM_LABELS[meta?.platform || 'fanqie'] || PLATFORM_LABELS.general
  const totalWords = stats?.totalWords || 0
  const targetWords = meta?.targetWords || 1000000
  const progressPct = Math.min(100, Math.round((totalWords / targetWords) * 100))

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* 1. 顶栏：作品企划控制台 */}
      <Paper
        square
        elevation={0}
        sx={{
          borderBottom: 1,
          borderColor: 'divider',
          px: 2,
          py: 1,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: 1.5,
          bgcolor: 'background.paper',
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, flexWrap: 'wrap' }}>
          <TextField
            select
            size="small"
            label="当前小说"
            value={currentProject}
            onChange={(e) => setCurrentProject(e.target.value)}
            sx={{ minWidth: 180 }}
          >
            {projects.length === 0 && (
              <MenuItem value="" disabled>
                （暂无小说工程）
              </MenuItem>
            )}
            {projects.map((p) => (
              <MenuItem key={p.id} value={p.name}>
                {p.name}
              </MenuItem>
            ))}
          </TextField>

          <Button
            size="small"
            variant="outlined"
            onClick={() => setOpenNewProj(true)}
            sx={{ height: 40 }}
          >
            + 新建作品
          </Button>

          <Divider orientation="vertical" flexItem sx={{ mx: 0.5 }} />

          <Chip
            size="small"
            label={platformInfo.name}
            color={platformInfo.color}
            variant="outlined"
            sx={{ fontWeight: 'bold' }}
          />
          <Chip size="small" label={meta?.genre || '仙侠修真'} variant="filled" />

          {/* 进度条与目标字数 */}
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, minWidth: 220 }}>
            <Box sx={{ flex: 1 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.2 }}>
                <Typography variant="caption" sx={{ color: 'text.secondary', fontWeight: 'bold' }}>
                  创作进度: {totalWords.toLocaleString()} / {targetWords.toLocaleString()} 字
                </Typography>
                <Typography variant="caption" sx={{ color: 'primary.main', fontWeight: 'bold' }}>
                  {progressPct}%
                </Typography>
              </Box>
              <LinearProgress variant="determinate" value={progressPct} sx={{ height: 6, borderRadius: 3 }} />
            </Box>
          </Box>

          <Chip
            size="small"
            icon={<TrendingUpIcon />}
            label={`今日已写: ${stats?.todayWords || 0} 字`}
            color="success"
            variant="outlined"
          />

          <Button
            size="small"
            startIcon={<SettingsSuggestIcon />}
            onClick={() => setOpenMetaDialog(true)}
          >
            企划定位
          </Button>

          <Button
            size="small"
            variant="outlined"
            color="primary"
            startIcon={<FileDownloadIcon />}
            onClick={() => setOpenExportDialog(true)}
          >
            全书导出
          </Button>

          <Button
            size="small"
            variant="text"
            startIcon={<TuneIcon />}
            onClick={onSwitchPipeline}
          >
            工坊流水线
          </Button>
        </Box>

        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Tooltip title={rightOpen ? '折叠右侧智能副驾' : '展开右侧智能副驾'}>
            <IconButton size="small" onClick={() => setRightOpen(!rightOpen)} color={rightOpen ? 'primary' : 'default'}>
              <ViewSidebarIcon />
            </IconButton>
          </Tooltip>
        </Box>
      </Paper>

      {/* 2. 三栏生产力工作区 */}
      <Box sx={{ flex: 1, minHeight: 0, display: 'flex', overflow: 'hidden' }}>
        {/* 左栏：企划大纲树 & 设定智库 (280px) */}
        <Paper
          square
          elevation={0}
          sx={{
            width: 280,
            borderRight: 1,
            borderColor: 'divider',
            display: 'flex',
            flexDirection: 'column',
            bgcolor: 'background.paper',
          }}
        >
          <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
            <Tabs
              value={leftTab}
              onChange={(_, v) => setLeftTab(v)}
              variant="fullWidth"
              sx={{ minHeight: 40, '& .MuiTab-root': { minHeight: 40, py: 0.5, fontSize: 13 } }}
            >
              <Tab value="outlines" label={`大纲 (${outlines.length})`} />
              <Tab value="characters" label={`人设 (${characters.length})`} />
              <Tab value="notes" label={`便签 (${notes.length})`} />
            </Tabs>
          </Box>

          <Box sx={{ px: 1.5, py: 0.8, borderBottom: 1, borderColor: 'divider', display: 'flex', justifyContent: 'flex-end', bgcolor: 'action.hover' }}>
            {leftTab === 'outlines' && (
              <Button size="small" startIcon={<AddIcon />} onClick={() => setOpenNewOutline(true)} sx={{ fontSize: 11, py: 0.2 }}>
                规划新章
              </Button>
            )}
            {leftTab === 'characters' && (
              <Button size="small" startIcon={<AddIcon />} onClick={() => setOpenNewChar(true)} sx={{ fontSize: 11, py: 0.2 }}>
                新建人设
              </Button>
            )}
            {leftTab === 'notes' && (
              <Button size="small" startIcon={<AddIcon />} onClick={() => setOpenNewNote(true)} sx={{ fontSize: 11, py: 0.2 }}>
                新增便签
              </Button>
            )}
          </Box>

          <Box sx={{ flex: 1, minHeight: 0, overflow: 'auto', p: 1.5 }}>
            {leftTab === 'outlines' && (
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                {outlines.length === 0 ? (
                  <Typography variant="body2" color="text.secondary" sx={{ textAlign: 'center', py: 3 }}>
                    暂无大纲。可在上方点「规划新章」或去工坊流水线规划卷章。
                  </Typography>
                ) : (
                  outlines.map((ot) => (
                    <Card
                      key={ot.id}
                      variant="outlined"
                      sx={{
                        p: 1,
                        cursor: 'pointer',
                        '&:hover': { borderColor: 'primary.main', bgcolor: 'action.hover' },
                      }}
                      onClick={() => {
                        if (content.trim()) {
                          try {
                            localStorage.setItem(getDraftKey(currentProject, chapterNo), content)
                          } catch (_e) {
                            void _e
                          }
                        }
                        setChapterTitle(ot.title)
                        let targetNo = chapterNo
                        const m = ot.title.match(/第\s*(\d+)\s*章/)
                        if (m) {
                          targetNo = Number(m[1])
                          setChapterNo(targetNo)
                        }
                        let savedDraft = ''
                        try {
                          savedDraft = localStorage.getItem(getDraftKey(currentProject, targetNo)) || ''
                        } catch (_e) {
                          void _e
                        }
                        if (savedDraft) {
                          setContent(savedDraft)
                          setToast(`已选定大纲章节: ${ot.title}（已自动恢复本地草稿）`)
                        } else {
                          setToast(`已选定大纲章节: ${ot.title}`)
                        }
                      }}
                    >
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <Typography variant="subtitle2" sx={{ fontWeight: 'bold' }}>
                          {ot.title}
                        </Typography>
                        <Chip
                          size="small"
                          label={ot.status === 'done' ? '已写' : ot.status === 'writing' ? '写作中' : '待写'}
                          color={ot.status === 'done' ? 'success' : ot.status === 'writing' ? 'primary' : 'default'}
                          sx={{ height: 20, fontSize: 11 }}
                        />
                      </Box>
                      {ot.summary && (
                        <>
                          <Typography
                            variant="caption"
                            color="text.secondary"
                            sx={{
                              display: '-webkit-box',
                              WebkitLineClamp: 2,
                              WebkitBoxOrient: 'vertical',
                              overflow: 'hidden',
                              mt: 0.5,
                            }}
                          >
                            {ot.summary}
                          </Typography>
                          <Box sx={{ display: 'flex', justifyContent: 'flex-end', mt: 0.5 }}>
                            <Button
                              size="small"
                              variant="text"
                              startIcon={<InputIcon fontSize="small" />}
                              sx={{ fontSize: 11, py: 0 }}
                              onClick={(e) => {
                                e.stopPropagation()
                                insertTextToEditor(`【大纲细纲骨架：${ot.title}】\n${ot.summary}\n\n`, ot.title)
                              }}
                            >
                              引用细纲到正文
                            </Button>
                          </Box>
                        </>
                      )}
                    </Card>
                  ))
                )}
              </Box>
            )}

            {leftTab === 'characters' && (
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                {characters.length === 0 ? (
                  <Typography variant="body2" color="text.secondary" sx={{ textAlign: 'center', py: 3 }}>
                    暂无人物卡。可在工坊流水线中创建主角/配角人设。
                  </Typography>
                ) : (
                  characters.map((ch) => (
                    <Card key={ch.id} variant="outlined" sx={{ p: 1 }}>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                          <PersonIcon fontSize="small" color="primary" />
                          <Typography variant="subtitle2" sx={{ fontWeight: 'bold' }}>
                            {ch.name}
                          </Typography>
                        </Box>
                        <Chip size="small" label={ch.role} sx={{ height: 20, fontSize: 11 }} />
                      </Box>
                      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', my: 0.5 }}>
                        {ch.description}
                      </Typography>
                      <Button
                        size="small"
                        variant="text"
                        startIcon={<InputIcon fontSize="small" />}
                        sx={{ fontSize: 11, p: 0 }}
                        onClick={() => insertTextToEditor(`【角色登场：${ch.name}】（${ch.role}）\n设定特征：${ch.description}`, ch.name)}
                      >
                        引用设定到正文
                      </Button>
                    </Card>
                  ))
                )}
              </Box>
            )}

            {leftTab === 'notes' && (
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                {notes.length === 0 ? (
                  <Typography variant="body2" color="text.secondary" sx={{ textAlign: 'center', py: 3 }}>
                    暂无便签。
                  </Typography>
                ) : (
                  notes.map((n) => (
                    <Card key={n.id} variant="outlined" sx={{ p: 1 }}>
                      <Typography variant="subtitle2" sx={{ fontWeight: 'bold' }}>
                        {n.title}
                      </Typography>
                      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', my: 0.5 }}>
                        {n.content}
                      </Typography>
                      <Button
                        size="small"
                        variant="text"
                        startIcon={<InputIcon fontSize="small" />}
                        sx={{ fontSize: 11, p: 0 }}
                        onClick={() => insertTextToEditor(`【灵感便签：${n.title}】\n${n.content}`, n.title)}
                      >
                        引用便签
                      </Button>
                    </Card>
                  ))
                )}
              </Box>
            )}
          </Box>
        </Paper>

        {/* 中栏：沉浸式正文编辑器 (Flex: 1) */}
        <Box sx={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', p: 2, overflow: 'auto' }}>
          {error && <Alert severity="error" sx={{ mb: 1.5 }} onClose={() => setError('')}>{error}</Alert>}

          {/* 章节控制条 */}
          <Paper sx={{ p: 1.5, mb: 1.5, display: 'flex', alignItems: 'center', gap: 2, flexWrap: 'wrap' }}>
            <TextField
              type="number"
              size="small"
              label="章号"
              value={chapterNo}
              onChange={(e) => setChapterNo(Math.max(1, Number(e.target.value)))}
              sx={{ width: 90 }}
            />
            <TextField
              size="small"
              label="章节标题"
              value={chapterTitle}
              onChange={(e) => setChapterTitle(e.target.value)}
              sx={{ flex: 1, minWidth: 200 }}
              placeholder="例如：第1章 惊变"
            />
            <Button
              variant="contained"
              color="primary"
              startIcon={<SaveIcon />}
              onClick={handleSaveChapter}
              disabled={saving}
            >
              {saving ? '入库中...' : '保存并入库'}
            </Button>
            <Button
              variant="outlined"
              color="secondary"
              startIcon={<NavigateNextIcon />}
              onClick={handleNextChapter}
            >
              下一章
            </Button>
            <Button
              variant="outlined"
              color="error"
              startIcon={<SecurityIcon />}
              onClick={handleRunFullCheck}
            >
              ⚡ 排毒与去AI
            </Button>
            <Button
              variant="outlined"
              color="info"
              startIcon={<AssessmentIcon />}
              onClick={handleRunPlatformDiagnose}
            >
              📊 签约预测
            </Button>
            <Box sx={{ ml: 'auto', display: 'flex', alignItems: 'center', gap: 1 }}>
              <Chip
                size="small"
                label={`本章 ${content.length.toLocaleString()} 字`}
                color={content.length >= 2000 ? 'success' : content.length >= 1000 ? 'primary' : 'default'}
                variant={content.length >= 2000 ? 'filled' : 'outlined'}
                sx={{ fontWeight: 'bold' }}
              />
            </Box>
          </Paper>

          {/* 本章伏笔暗线协同推进提醒 */}
          {activeForeshadowings.length > 0 && (
            <Alert
              severity="info"
              icon={<NotificationsActiveIcon />}
              sx={{ mb: 1.5, borderRadius: 2 }}
            >
              <Typography variant="subtitle2" sx={{ fontWeight: 'bold' }}>
                本章（第 {chapterNo} 章）伏笔暗线协同推进提醒：
              </Typography>
              {activeForeshadowings.map((af, i) => (
                <Box key={i} sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mt: 0.5 }}>
                  <Typography variant="body2" sx={{ fontSize: 13 }}>
                    • 【{af.stageName}】<strong>{af.chain.title}</strong>：{af.chain.description || '按大纲节奏推进此伏笔'}
                  </Typography>
                  <Button
                    size="small"
                    variant="text"
                    startIcon={<InputIcon fontSize="small" />}
                    onClick={() => insertTextToEditor(`【伏笔推进提醒：${af.chain.title}】（${af.stageName}阶段）\n${af.chain.description}`, af.chain.title)}
                    sx={{ fontSize: 11, py: 0 }}
                  >
                    引用到正文
                  </Button>
                </Box>
              ))}
            </Alert>
          )}

          {/* Tiptap 正文编辑器主体 */}
          <Paper sx={{ flex: 1, minHeight: 480, p: 2, display: 'flex', flexDirection: 'column' }}>
            <ChapterEditor
              value={content}
              onChange={setContent}
              minHeight={420}
              placeholder="在此沉浸创作章节正文……随写随查左侧大纲设定，右侧智能副驾实时排雷并反哺精华资产。"
              targetChars={3000}
              enablePoisonCheck={false}
              enableDeslopCheck={false}
            />
          </Paper>
        </Box>

        {/* 右栏：智能副驾 Inspector & 五维精华反哺 (360px) */}
        {rightOpen && (
          <Paper
            square
            elevation={0}
            sx={{
              width: 360,
              borderLeft: 1,
              borderColor: 'divider',
              display: 'flex',
              flexDirection: 'column',
              bgcolor: 'background.paper',
            }}
          >
            <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
              <Tabs
                value={rightTab}
                onChange={(_, v) => setRightTab(v)}
                variant="fullWidth"
                sx={{ minHeight: 40, '& .MuiTab-root': { minHeight: 40, py: 0.5, fontSize: 13 } }}
              >
                <Tab value="check" label="排雷与去AI" />
                <Tab value="essence" label="精华资产反哺" />
                <Tab value="generate" label="文风生成" />
              </Tabs>
            </Box>

            <Box sx={{ flex: 1, minHeight: 0, overflow: 'auto', p: 1.5 }}>
              {/* Tab 1: 排雷与去 AI 味 */}
              {rightTab === 'check' && (
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                  <Box sx={{ display: 'flex', gap: 1 }}>
                    <Button
                      fullWidth
                      size="small"
                      variant="contained"
                      color="error"
                      onClick={handleRunFullCheck}
                      disabled={poisonLoading || deslopLoading}
                    >
                      {poisonLoading || deslopLoading ? '诊断中...' : '一键排雷与去AI味'}
                    </Button>
                    <Button
                      fullWidth
                      size="small"
                      variant="outlined"
                      color="info"
                      onClick={handleRunPlatformDiagnose}
                      disabled={diagLoading}
                    >
                      {diagLoading ? '诊断中...' : '签约预测'}
                    </Button>
                  </Box>

                  {/* 签约诊断结果 */}
                  {diagResult && (
                    <Card variant="outlined" sx={{ p: 1.5, borderColor: 'info.main' }}>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <Typography variant="subtitle2" sx={{ fontWeight: 'bold', color: 'info.main' }}>
                          签约评级: {diagResult.grade}
                        </Typography>
                        <Chip size="small" label={`签约概率: ${diagResult.signingProb}`} color="info" />
                      </Box>
                      <Typography variant="caption" sx={{ display: 'block', mt: 0.5 }}>
                        对白占比: {(diagResult.dialogueRatio * 100).toFixed(1)}% | 综合评分: {diagResult.score}分
                      </Typography>
                      {diagResult.vetoRisks.length > 0 && (
                        <Box sx={{ mt: 1 }}>
                          <Typography variant="caption" color="error.main" sx={{ fontWeight: 'bold' }}>
                            ⚠️ 平台劝退风险:
                          </Typography>
                          {diagResult.vetoRisks.map((vr, i) => (
                            <Typography key={i} variant="caption" color="error" sx={{ display: 'block' }}>
                              • {vr}
                            </Typography>
                          ))}
                        </Box>
                      )}
                    </Card>
                  )}

                  {/* 10大毒点排查结果 */}
                  {poisonResult && (
                    <Card variant="outlined" sx={{ p: 1.5, borderColor: poisonResult.findings.length > 0 ? 'warning.main' : 'success.main' }}>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <Typography variant="subtitle2" sx={{ fontWeight: 'bold' }}>
                          毒点排查: {poisonResult.verdict}
                        </Typography>
                        <Chip
                          size="small"
                          label={`违规项: ${poisonResult.findings.length}`}
                          color={poisonResult.findings.length > 0 ? 'error' : 'success'}
                        />
                      </Box>
                      {poisonResult.findings.length === 0 ? (
                        <Typography variant="caption" color="success.main" sx={{ display: 'block', mt: 1 }}>
                          ✅ 未发现虐主、战力崩溃、反派无脑等 10 大核心毒点。
                        </Typography>
                      ) : (
                        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1, mt: 1 }}>
                          {poisonResult.findings.map((f, i) => (
                            <Box key={i} sx={{ p: 1, bgcolor: 'action.hover', borderRadius: 1 }}>
                              <Typography variant="caption" sx={{ fontWeight: 'bold', color: 'error.main' }}>
                                [{f.typeName}] {f.snippet}
                              </Typography>
                              <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                                💡 建议: {f.suggestion}
                              </Typography>
                            </Box>
                          ))}
                        </Box>
                      )}
                    </Card>
                  )}

                  {/* 去 AI 味结果 */}
                  {deslopResult && (
                    <Card variant="outlined" sx={{ p: 1.5, borderColor: deslopResult.aiScore > 3 ? 'warning.main' : 'success.main' }}>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <Typography variant="subtitle2" sx={{ fontWeight: 'bold' }}>
                          AI 指纹: {deslopResult.verdictCn}
                        </Typography>
                        <Chip
                          size="small"
                          label={`AI评分: ${deslopResult.aiScore}/10`}
                          color={deslopResult.aiScore > 5 ? 'error' : deslopResult.aiScore > 2 ? 'warning' : 'success'}
                        />
                      </Box>
                      {deslopResult.suggestions.length > 0 && (
                        <Box sx={{ mt: 1 }}>
                          <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 'bold' }}>
                            口语化脱水建议:
                          </Typography>
                          {deslopResult.suggestions.slice(0, 4).map((sug, i) => (
                            <Typography key={i} variant="caption" color="text.secondary" sx={{ display: 'block' }}>
                              • {sug}
                            </Typography>
                          ))}
                        </Box>
                      )}
                    </Card>
                  )}
                </Box>
              )}

              {/* Tab 2: 精华资产与伏笔暗线 */}
              {rightTab === 'essence' && (
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
                  <Tabs
                    value={essenceSubTab}
                    onChange={(_, v) => setEssenceSubTab(v)}
                    variant="fullWidth"
                    sx={{ minHeight: 32, '& .MuiTab-root': { minHeight: 32, py: 0.5, fontSize: 12 } }}
                  >
                    <Tab value="assets" label={`五维提炼卡 (${essenceAssets.length})`} />
                    <Tab value="chains" label={`伏笔暗线 (${chains.length})`} />
                  </Tabs>

                  {essenceSubTab === 'assets' ? (
                    <>
                      <TextField
                        select
                        size="small"
                        fullWidth
                        label="资产类别"
                        value={essenceCategory}
                        onChange={(e) => setEssenceCategory(e.target.value)}
                      >
                        <MenuItem value="all">全部精华资产</MenuItem>
                        <MenuItem value="outline">骨架大纲</MenuItem>
                        <MenuItem value="hook">开篇钩子</MenuItem>
                        <MenuItem value="character">人设反差</MenuItem>
                        <MenuItem value="trope">爆款桥段</MenuItem>
                        <MenuItem value="style">反AI口语</MenuItem>
                      </TextField>

                      {essenceAssets.length === 0 ? (
                        <Typography variant="body2" color="text.secondary" sx={{ textAlign: 'center', py: 3 }}>
                          暂无提炼资产。请先在「小说精华数据库」或「灵感工坊」中提炼沉淀。
                        </Typography>
                      ) : (
                        essenceAssets.map((asset) => (
                          <Card key={asset.id} variant="outlined" sx={{ p: 1.5 }}>
                            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                              <Typography variant="subtitle2" sx={{ fontWeight: 'bold' }}>
                                {asset.title}
                              </Typography>
                              <Chip size="small" label={asset.category} variant="outlined" sx={{ height: 20 }} />
                            </Box>
                            <Typography
                              variant="caption"
                              color="text.secondary"
                              sx={{
                                display: '-webkit-box',
                                WebkitLineClamp: 3,
                                WebkitBoxOrient: 'vertical',
                                overflow: 'hidden',
                                my: 0.5,
                              }}
                            >
                              {asset.content}
                            </Typography>
                            <Box sx={{ display: 'flex', gap: 1, mt: 1 }}>
                              <Button
                                size="small"
                                variant="contained"
                                startIcon={<InputIcon />}
                                sx={{ fontSize: 11 }}
                                onClick={() => insertTextToEditor(asset.content, asset.title)}
                              >
                                插入正文
                              </Button>
                              <Button
                                size="small"
                                variant="outlined"
                                startIcon={<ContentCopyIcon />}
                                sx={{ fontSize: 11 }}
                                onClick={() => {
                                  navigator.clipboard.writeText(asset.content)
                                  setToast(`已复制: ${asset.title}`)
                                }}
                              >
                                复制
                              </Button>
                            </Box>
                          </Card>
                        ))
                      )}
                    </>
                  ) : (
                    <>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 'bold' }}>
                          草蛇灰线推进图谱
                        </Typography>
                        <Button
                          size="small"
                          variant="outlined"
                          startIcon={<AddIcon />}
                          onClick={() => {
                            setNewChainPlant(chapterNo)
                            setNewChainReveal(Math.max(chapterNo + 3, 5))
                            setNewChainClimax(Math.max(chapterNo + 8, 10))
                            setOpenNewChain(true)
                          }}
                          sx={{ fontSize: 11, py: 0.2 }}
                        >
                          记录新暗线
                        </Button>
                      </Box>

                      {chains.length === 0 ? (
                        <Typography variant="body2" color="text.secondary" sx={{ textAlign: 'center', py: 3 }}>
                          当前作品尚无伏笔暗线。点击右上角即可添加第一条草蛇灰线！
                        </Typography>
                      ) : (
                        chains.map((chain) => {
                          const isCurPlant = chain.plantChapter === chapterNo
                          const isCurReveal = chain.revealChapter === chapterNo
                          const isCurClimax = chain.climaxChapter === chapterNo
                          const isCurActive = isCurPlant || isCurReveal || isCurClimax
                          return (
                            <Card
                              key={chain.id}
                              variant="outlined"
                              sx={{
                                p: 1.5,
                                borderColor: isCurActive ? 'primary.main' : 'divider',
                                bgcolor: isCurActive ? 'action.hover' : 'inherit',
                              }}
                            >
                              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                                <Typography variant="subtitle2" sx={{ fontWeight: 'bold' }}>
                                  {chain.title}
                                </Typography>
                                <Chip
                                  size="small"
                                  label={
                                    chain.category === 'identity'
                                      ? '身份谜题'
                                      : chain.category === 'power'
                                      ? '力量伏笔'
                                      : chain.category === 'fate'
                                      ? '恩怨宿命'
                                      : chain.category === 'truth'
                                      ? '世界真相'
                                      : '草蛇灰线'
                                  }
                                  sx={{ height: 20, fontSize: 10 }}
                                />
                              </Box>

                              {isCurActive && (
                                <Chip
                                  size="small"
                                  color="primary"
                                  label={`🔔 当前第${chapterNo}章关键推进点（${isCurPlant ? '埋设' : isCurReveal ? '显露' : '高潮回收'}）`}
                                  sx={{ height: 20, fontSize: 10, mt: 0.5 }}
                                />
                              )}

                              <Box sx={{ my: 1 }}>
                                <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.3 }}>
                                  <Typography variant="caption" sx={{ fontSize: 11, color: isCurPlant ? 'primary.main' : 'text.secondary' }}>
                                    埋设: 第{chain.plantChapter}章
                                  </Typography>
                                  <Typography variant="caption" sx={{ fontSize: 11, color: isCurReveal ? 'primary.main' : 'text.secondary' }}>
                                    显露: 第{chain.revealChapter}章
                                  </Typography>
                                  <Typography variant="caption" sx={{ fontSize: 11, color: isCurClimax ? 'error.main' : 'text.secondary' }}>
                                    回收: 第{chain.climaxChapter}章
                                  </Typography>
                                </Box>
                                <LinearProgress
                                  variant="determinate"
                                  value={
                                    chapterNo <= chain.plantChapter
                                      ? 15
                                      : chapterNo >= chain.climaxChapter
                                      ? 100
                                      : Math.round(
                                          ((chapterNo - chain.plantChapter) /
                                            Math.max(1, chain.climaxChapter - chain.plantChapter)) *
                                            100
                                        )
                                  }
                                  sx={{ height: 5, borderRadius: 3 }}
                                />
                              </Box>

                              {chain.description && (
                                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
                                  {chain.description}
                                </Typography>
                              )}

                              <Box sx={{ display: 'flex', gap: 1 }}>
                                <Button
                                  size="small"
                                  variant="contained"
                                  startIcon={<InputIcon />}
                                  sx={{ fontSize: 11 }}
                                  onClick={() =>
                                    insertTextToEditor(
                                      `【伏笔暗线协同：${chain.title}】\n设计轨迹：第${chain.plantChapter}章埋设 → 第${chain.revealChapter}章显露 → 第${chain.climaxChapter}章高潮回收\n设定详情：${chain.description}`,
                                      chain.title
                                    )
                                  }
                                >
                                  引用暗线到正文
                                </Button>
                                <Button
                                  size="small"
                                  variant="outlined"
                                  startIcon={<ContentCopyIcon />}
                                  sx={{ fontSize: 11 }}
                                  onClick={() => {
                                    navigator.clipboard.writeText(chain.description || chain.title)
                                    setToast(`已复制伏笔暗线: ${chain.title}`)
                                  }}
                                >
                                  复制
                                </Button>
                              </Box>
                            </Card>
                          )
                        })
                      )}
                    </>
                  )}
                </Box>
              )}

              {/* Tab 3: 文风与 AI 生成 */}
              {rightTab === 'generate' && (
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
                  <Typography variant="body2" color="text.secondary">
                    从拆书模型中注入 voice 与题材规范，快速给当前章节注入叙事声线：
                  </Typography>
                  <TextField
                    select
                    size="small"
                    fullWidth
                    label="voice-card 声线"
                    value={sel.voice}
                    onChange={(e) => sel.setVoice(e.target.value)}
                  >
                    {sel.byKind('voice').map((a) => (
                      <MenuItem key={a.id} value={a.id}>
                        {a.name}
                      </MenuItem>
                    ))}
                  </TextField>
                  <TextField
                    select
                    size="small"
                    fullWidth
                    label="genre-pack 题材包"
                    value={sel.genrePack}
                    onChange={(e) => sel.setGenrePack(e.target.value)}
                  >
                    <MenuItem value="">无</MenuItem>
                    {sel.byKind('genre_pack').map((a) => (
                      <MenuItem key={a.id} value={a.id}>
                        {a.name}
                      </MenuItem>
                    ))}
                  </TextField>
                  <Button variant="outlined" onClick={onSwitchPipeline} startIcon={<TuneIcon />}>
                    前往工坊高级生成器
                  </Button>
                </Box>
              )}
            </Box>
          </Paper>
        )}
      </Box>

      {/* 企划定位对话框 */}
      <Dialog open={openMetaDialog} onClose={() => setOpenMetaDialog(false)} maxWidth="sm" fullWidth>
        <DialogTitle>作品企划与多平台定位</DialogTitle>
        <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
          <TextField
            select
            fullWidth
            size="small"
            label="目标签约平台"
            value={metaPlatform}
            onChange={(e) => setMetaPlatform(e.target.value)}
          >
            <MenuItem value="fanqie">番茄小说 (30秒黄金钩/每章留扣/防虐主)</MenuItem>
            <MenuItem value="qidian">起点中文网 (大纵深世界观/严密升级/反圣母)</MenuItem>
            <MenuItem value="jinjiang">晋江文学城 (人设细腻反差/推拉克制/微表情)</MenuItem>
            <MenuItem value="qimao">七猫中文网 (开局强冲突受辱/底牌强反制)</MenuItem>
            <MenuItem value="zhihu">知乎盐选 (第一人称高反转/三幕式快节奏)</MenuItem>
            <MenuItem value="general">通用网文平台</MenuItem>
          </TextField>

          <TextField
            fullWidth
            size="small"
            label="小说题材"
            value={metaGenre}
            onChange={(e) => setMetaGenre(e.target.value)}
            placeholder="例如：xianxia / dushi / xuanhuan"
          />

          <TextField
            type="number"
            fullWidth
            size="small"
            label="全书目标字数"
            value={metaTargetWords}
            onChange={(e) => setMetaTargetWords(Number(e.target.value))}
          />

          <TextField
            fullWidth
            multiline
            rows={3}
            size="small"
            label="作品一句话卖点与核心主线"
            value={metaSummary}
            onChange={(e) => setMetaSummary(e.target.value)}
            placeholder="说明主角核心爽点、金手指与主线目标"
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpenMetaDialog(false)}>取消</Button>
          <Button variant="contained" onClick={handleSaveMeta}>
            保存企划
          </Button>
        </DialogActions>
      </Dialog>

      {/* 新建作品对话框 */}
      <Dialog open={openNewProj} onClose={() => setOpenNewProj(false)}>
        <DialogTitle>新建小说作品</DialogTitle>
        <DialogContent sx={{ pt: 1 }}>
          <TextField
            autoFocus
            fullWidth
            size="small"
            label="小说作品名称"
            placeholder="例如：万界仙途"
            value={newProjName}
            onChange={(e) => setNewProjName(e.target.value)}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpenNewProj(false)}>取消</Button>
          <Button variant="contained" onClick={handleCreateProject}>
            创建
          </Button>
        </DialogActions>
      </Dialog>

      {/* 全书导出对话框 */}
      <Dialog open={openExportDialog} onClose={() => setOpenExportDialog(false)} maxWidth="xs" fullWidth>
        <DialogTitle>全书一键导出与排版生成</DialogTitle>
        <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
          <Typography variant="body2" color="text.secondary">
            当前工程《{currentProject}》已写 {stats?.totalChapters || 0} 章，共 {(stats?.totalWords || 0).toLocaleString()} 字。
          </Typography>
          <TextField
            select
            fullWidth
            size="small"
            label="导出排版格式"
            value={exportFormat}
            onChange={(e) => setExportFormat(e.target.value as 'docx' | 'md' | 'txt')}
          >
            <MenuItem value="docx">📘 Word 文档 (.docx) — 官方标准排版稿（带标题封面）</MenuItem>
            <MenuItem value="md">📝 Markdown 结构稿 (.md) — 适合 Obsidian/知识库</MenuItem>
            <MenuItem value="txt">📄 纯文本 (.txt) — 干净无格式，直接复制粘贴</MenuItem>
          </TextField>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpenExportDialog(false)}>取消</Button>
          <Button
            variant="contained"
            color="primary"
            startIcon={<FileDownloadIcon />}
            onClick={() => handleExportProject(exportFormat)}
            disabled={exporting}
          >
            {exporting ? '导出中...' : '立即下载'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* 新建章节大纲对话框 */}
      <Dialog open={openNewOutline} onClose={() => setOpenNewOutline(false)} maxWidth="sm" fullWidth>
        <DialogTitle>规划新章节大纲</DialogTitle>
        <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
          <TextField
            autoFocus
            fullWidth
            size="small"
            label="章节标题"
            placeholder="例如：第2章 惊变"
            value={newOutlineTitle}
            onChange={(e) => setNewOutlineTitle(e.target.value)}
          />
          <TextField
            fullWidth
            multiline
            rows={3}
            size="small"
            label="本章剧情细纲与冲突目标"
            placeholder="说明本章主要发生什么事件、制造什么悬念或爽点"
            value={newOutlineSummary}
            onChange={(e) => setNewOutlineSummary(e.target.value)}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpenNewOutline(false)}>取消</Button>
          <Button variant="contained" onClick={handleCreateOutline}>
            保存大纲
          </Button>
        </DialogActions>
      </Dialog>

      {/* 新建人物卡对话框 */}
      <Dialog open={openNewChar} onClose={() => setOpenNewChar(false)} maxWidth="sm" fullWidth>
        <DialogTitle>新建核心人物设定卡</DialogTitle>
        <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
          <TextField
            autoFocus
            fullWidth
            size="small"
            label="人物姓名"
            placeholder="例如：白灵儿"
            value={newCharName}
            onChange={(e) => setNewCharName(e.target.value)}
          />
          <TextField
            select
            fullWidth
            size="small"
            label="角色定位"
            value={newCharRole}
            onChange={(e) => setNewCharRole(e.target.value)}
          >
            <MenuItem value="主角">主角 (主角光环/核心行动驱动)</MenuItem>
            <MenuItem value="女主角">女主角 (羁绊/情感推拉)</MenuItem>
            <MenuItem value="反派">反派 (压迫感/利益冲突)</MenuItem>
            <MenuItem value="宿敌">宿敌 (镜像对照/势均力敌)</MenuItem>
            <MenuItem value="导师">导师 (传道/暗藏秘密)</MenuItem>
            <MenuItem value="配角">配角 (插科打诨/辅助推进)</MenuItem>
          </TextField>
          <TextField
            fullWidth
            multiline
            rows={3}
            size="small"
            label="人设反差与核心特质"
            placeholder="例如：表面清冷孤傲，实则内藏反差护短；具有关键血脉"
            value={newCharDesc}
            onChange={(e) => setNewCharDesc(e.target.value)}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpenNewChar(false)}>取消</Button>
          <Button variant="contained" onClick={handleCreateCharacter}>
            保存人物
          </Button>
        </DialogActions>
      </Dialog>

      {/* 新建灵感便签对话框 */}
      <Dialog open={openNewNote} onClose={() => setOpenNewNote(false)} maxWidth="sm" fullWidth>
        <DialogTitle>随手记下灵感便签</DialogTitle>
        <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
          <TextField
            autoFocus
            fullWidth
            size="small"
            label="便签标题"
            placeholder="例如：万剑归宗的视觉描写"
            value={newNoteTitle}
            onChange={(e) => setNewNoteTitle(e.target.value)}
          />
          <TextField
            fullWidth
            multiline
            rows={3}
            size="small"
            label="灵感详情"
            placeholder="例如：剑气如雨倒卷长空，带出金石裂帛之音"
            value={newNoteContent}
            onChange={(e) => setNewNoteContent(e.target.value)}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpenNewNote(false)}>取消</Button>
          <Button variant="contained" onClick={handleCreateNote}>
            保存便签
          </Button>
        </DialogActions>
      </Dialog>

      {/* 新建伏笔暗线对话框 */}
      <Dialog open={openNewChain} onClose={() => setOpenNewChain(false)} maxWidth="sm" fullWidth>
        <DialogTitle>记录全书草蛇灰线（伏笔暗线）</DialogTitle>
        <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
          <TextField
            autoFocus
            fullWidth
            size="small"
            label="伏笔线索名称"
            placeholder="例如：林凡胸前神秘石珠的来历"
            value={newChainTitle}
            onChange={(e) => setNewChainTitle(e.target.value)}
          />
          <TextField
            select
            fullWidth
            size="small"
            label="伏笔类型"
            value={newChainCategory}
            onChange={(e) => setNewChainCategory(e.target.value)}
          >
            <MenuItem value="identity">身份谜题 (主角或大反派隐匿身世)</MenuItem>
            <MenuItem value="power">力量伏笔 (神功残卷/异宝异动/底牌法则)</MenuItem>
            <MenuItem value="fate">恩怨宿命 (宗门灭顶旧案/复仇契机)</MenuItem>
            <MenuItem value="truth">世界真相 (天地禁制/天道伪善/世界黑幕)</MenuItem>
            <MenuItem value="emotion">情感暗涌 (红颜身份/背叛契机)</MenuItem>
          </TextField>
          <Box sx={{ display: 'flex', gap: 1.5 }}>
            <TextField
              type="number"
              fullWidth
              size="small"
              label="埋设章号 (Plant)"
              value={newChainPlant}
              onChange={(e) => setNewChainPlant(Math.max(1, Number(e.target.value)))}
            />
            <TextField
              type="number"
              fullWidth
              size="small"
              label="显露章号 (Reveal)"
              value={newChainReveal}
              onChange={(e) => setNewChainReveal(Math.max(1, Number(e.target.value)))}
            />
            <TextField
              type="number"
              fullWidth
              size="small"
              label="回收章号 (Climax)"
              value={newChainClimax}
              onChange={(e) => setNewChainClimax(Math.max(1, Number(e.target.value)))}
            />
          </Box>
          <TextField
            fullWidth
            multiline
            rows={3}
            size="small"
            label="暗线闭环规划与关键意象"
            placeholder="说明在埋设时给读者留下的微弱疑点，以及高潮时如何反转引爆"
            value={newChainDesc}
            onChange={(e) => setNewChainDesc(e.target.value)}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpenNewChain(false)}>取消</Button>
          <Button variant="contained" onClick={handleCreateChain}>
            启动暗线追踪
          </Button>
        </DialogActions>
      </Dialog>

      <Snackbar open={Boolean(toast)} autoHideDuration={3000} onClose={() => setToast('')} message={toast} />
    </Box>
  )
}

