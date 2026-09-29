// 创作管理（v2.0.2）：大纲 / 人物卡 / 灵感便签 / 码字统计 / 导出。
// 挂在辅助写作工作台下的新页签「创作」，各面板按项目隔离。
import { useState, useEffect, useCallback } from 'react'
import Box from '@mui/material/Box'
import Tabs from '@mui/material/Tabs'
import Tab from '@mui/material/Tab'
import Typography from '@mui/material/Typography'
import Button from '@mui/material/Button'
import TextField from '@mui/material/TextField'
import MenuItem from '@mui/material/MenuItem'
import Paper from '@mui/material/Paper'
import Alert from '@mui/material/Alert'
import Dialog from '@mui/material/Dialog'
import DialogTitle from '@mui/material/DialogTitle'
import DialogContent from '@mui/material/DialogContent'
import DialogActions from '@mui/material/DialogActions'
import Chip from '@mui/material/Chip'
import IconButton from '@mui/material/IconButton'
import Card from '@mui/material/Card'
import CardContent from '@mui/material/CardContent'
import Grid from '@mui/material/Grid'
import DeleteIcon from '@mui/icons-material/Delete'
import EditIcon from '@mui/icons-material/Edit'
import AddIcon from '@mui/icons-material/Add'
import DownloadIcon from '@mui/icons-material/Download'
import { writingApi, friendlyError } from '../api/client'
import type { WritingProject } from '../types'
import type { OutlineItem, CharacterCard, NoteItem, WritingStats } from '../api/client'
import BarChart from './charts/BarChart'

const OUTLINE_KIND_LABEL: Record<string, string> = { volume: '卷', chapter: '章' }
const OUTLINE_STATUS_LABEL: Record<string, string> = { planned: '待写', writing: '写作中', done: '已完成' }
const OUTLINE_STATUS_COLOR: Record<string, 'default' | 'primary' | 'success'> = {
  planned: 'default', writing: 'primary', done: 'success',
}

export default function WritingExtras() {
  const [tab, setTab] = useState(0)
  const [projects, setProjects] = useState<WritingProject[]>([])
  const [project, setProject] = useState('')
  const [error, setError] = useState('')

  const loadProjects = useCallback(() => {
    writingApi
      .projects()
      .then((ps) => {
        setProjects(ps)
        if (ps.length > 0 && !ps.some((p) => p.name === project)) {
          setProject(ps[0].name)
        }
      })
      .catch((e) => setError(`加载项目失败: ${friendlyError(e)}`))
  }, [project])

  useEffect(() => {
    loadProjects()
  }, [loadProjects])

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column', gap: 2 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
        <TextField
          select
          label="写作项目"
          value={project}
          onChange={(e) => setProject(e.target.value)}
          sx={{ minWidth: 220 }}
          size="small"
        >
          {projects.map((p) => (
            <MenuItem key={p.id} value={p.name}>
              {p.name}
            </MenuItem>
          ))}
        </TextField>
        <Typography variant="body2" color="text.secondary">
          大纲、人物、便签、统计都按项目隔离管理
        </Typography>
      </Box>
      {error && <Alert severity="error" onClose={() => setError('')}>{error}</Alert>}
      {!project ? (
        <Alert severity="info">请先在「写作」页签新建写作项目</Alert>
      ) : (
        <Box sx={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
          <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ borderBottom: 1, borderColor: 'divider' }}>
            <Tab label="大纲" />
            <Tab label="人物卡" />
            <Tab label="灵感便签" />
            <Tab label="码字统计" />
            <Tab label="导出" />
          </Tabs>
          <Box sx={{ flex: 1, minHeight: 0, overflow: 'auto', py: 2 }}>
            {tab === 0 && <OutlinePanel project={project} />}
            {tab === 1 && <CharacterPanel project={project} />}
            {tab === 2 && <NotePanel project={project} />}
            {tab === 3 && <StatsPanel project={project} />}
            {tab === 4 && <ExportPanel project={project} />}
          </Box>
        </Box>
      )}
    </Box>
  )
}

// ---------------------------------------------------------------------------
// 大纲
// ---------------------------------------------------------------------------

function OutlinePanel({ project }: { project: string }) {
  const [items, setItems] = useState<OutlineItem[]>([])
  const [error, setError] = useState('')
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editing, setEditing] = useState<OutlineItem | null>(null)
  const [kind, setKind] = useState('chapter')
  const [title, setTitle] = useState('')
  const [summary, setSummary] = useState('')
  const [status, setStatus] = useState('planned')

  const load = useCallback(() => {
    writingApi
      .outlines(project)
      .then(setItems)
      .catch((e) => setError(`加载大纲失败: ${friendlyError(e)}`))
  }, [project])

  useEffect(() => { load() }, [load])

  const openCreate = () => {
    setEditing(null); setKind('chapter'); setTitle(''); setSummary(''); setStatus('planned')
    setDialogOpen(true)
  }
  const openEdit = (it: OutlineItem) => {
    setEditing(it); setKind(it.kind); setTitle(it.title); setSummary(it.summary); setStatus(it.status)
    setDialogOpen(true)
  }

  const doSave = async () => {
    if (!title.trim()) { setError('标题不能为空'); return }
    setError('')
    try {
      if (editing) {
        await writingApi.updateOutline(editing.id, { kind, title: title.trim(), summary, status })
      } else {
        await writingApi.createOutline({ project, kind, title: title.trim(), summary, status, sort_order: items.length })
      }
      setDialogOpen(false)
      load()
    } catch (e) {
      setError(`保存失败: ${friendlyError(e)}`)
    }
  }

  const doDelete = async (id: number) => {
    if (!window.confirm('确定删除这条大纲吗？')) return
    try {
      await writingApi.deleteOutline(id)
      load()
    } catch (e) {
      setError(`删除失败: ${friendlyError(e)}`)
    }
  }

  const doToggleStatus = async (it: OutlineItem) => {
    const order = ['planned', 'writing', 'done']
    const next = order[(order.indexOf(it.status) + 1) % order.length]
    try {
      await writingApi.updateOutline(it.id, { status: next })
      load()
    } catch (e) {
      setError(`更新状态失败: ${friendlyError(e)}`)
    }
  }

  return (
    <Box>
      {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>{error}</Alert>}
      <Box sx={{ mb: 2 }}>
        <Button variant="contained" startIcon={<AddIcon />} onClick={openCreate}>
          新增大纲
        </Button>
      </Box>
      {items.length === 0 ? (
        <Typography color="text.secondary">还没有大纲，先从第一卷/第一章开始规划吧</Typography>
      ) : (
        items.map((it) => (
          <Paper key={it.id} sx={{ p: 2, mb: 1.5 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Chip label={OUTLINE_KIND_LABEL[it.kind] ?? it.kind} size="small" variant="outlined" />
              <Typography variant="subtitle1" sx={{ flex: 1, fontWeight: 600 }}>{it.title}</Typography>
              <Chip
                label={OUTLINE_STATUS_LABEL[it.status] ?? it.status}
                size="small"
                color={OUTLINE_STATUS_COLOR[it.status] ?? 'default'}
                onClick={() => doToggleStatus(it)}
                sx={{ cursor: 'pointer' }}
                title="点击切换状态"
              />
              <IconButton size="small" onClick={() => openEdit(it)} title="编辑"><EditIcon fontSize="small" /></IconButton>
              <IconButton size="small" onClick={() => doDelete(it.id)} title="删除"><DeleteIcon fontSize="small" /></IconButton>
            </Box>
            {it.summary && (
              <Typography variant="body2" color="text.secondary" sx={{ mt: 1, whiteSpace: 'pre-wrap' }}>
                {it.summary}
              </Typography>
            )}
          </Paper>
        ))
      )}
      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{editing ? '编辑大纲' : '新增大纲'}</DialogTitle>
        <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 2 }}>
          <TextField select label="类型" value={kind} onChange={(e) => setKind(e.target.value)}>
            <MenuItem value="volume">卷</MenuItem>
            <MenuItem value="chapter">章</MenuItem>
          </TextField>
          <TextField label="标题" value={title} onChange={(e) => setTitle(e.target.value)} fullWidth />
          <TextField
            label="内容概要"
            value={summary}
            onChange={(e) => setSummary(e.target.value)}
            fullWidth
            multiline
            rows={4}
            placeholder="这一卷/章要写什么、情绪线、伏笔……"
          />
          <TextField select label="状态" value={status} onChange={(e) => setStatus(e.target.value)}>
            <MenuItem value="planned">待写</MenuItem>
            <MenuItem value="writing">写作中</MenuItem>
            <MenuItem value="done">已完成</MenuItem>
          </TextField>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)}>取消</Button>
          <Button variant="contained" onClick={doSave}>保存</Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}

// ---------------------------------------------------------------------------
// 人物卡
// ---------------------------------------------------------------------------

function CharacterPanel({ project }: { project: string }) {
  const [items, setItems] = useState<CharacterCard[]>([])
  const [error, setError] = useState('')
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editing, setEditing] = useState<CharacterCard | null>(null)
  const [name, setName] = useState('')
  const [role, setRole] = useState('')
  const [description, setDescription] = useState('')

  const load = useCallback(() => {
    writingApi
      .characters(project)
      .then(setItems)
      .catch((e) => setError(`加载人物卡失败: ${friendlyError(e)}`))
  }, [project])

  useEffect(() => { load() }, [load])

  const openCreate = () => {
    setEditing(null); setName(''); setRole(''); setDescription('')
    setDialogOpen(true)
  }
  const openEdit = (it: CharacterCard) => {
    setEditing(it); setName(it.name); setRole(it.role); setDescription(it.description)
    setDialogOpen(true)
  }

  const doSave = async () => {
    if (!name.trim()) { setError('姓名不能为空'); return }
    setError('')
    try {
      if (editing) {
        await writingApi.updateCharacter(editing.id, { name: name.trim(), role, description })
      } else {
        await writingApi.createCharacter({ project, name: name.trim(), role, description })
      }
      setDialogOpen(false)
      load()
    } catch (e) {
      setError(`保存失败: ${friendlyError(e)}`)
    }
  }

  const doDelete = async (id: number) => {
    if (!window.confirm('确定删除这张人物卡吗？')) return
    try {
      await writingApi.deleteCharacter(id)
      load()
    } catch (e) {
      setError(`删除失败: ${friendlyError(e)}`)
    }
  }

  return (
    <Box>
      {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>{error}</Alert>}
      <Box sx={{ mb: 2 }}>
        <Button variant="contained" startIcon={<AddIcon />} onClick={openCreate}>
          新建人物卡
        </Button>
      </Box>
      {items.length === 0 ? (
        <Typography color="text.secondary">还没有人物卡，给主角建第一张卡吧</Typography>
      ) : (
        <Grid container spacing={2}>
          {items.map((it) => (
            <Grid item xs={12} sm={6} md={4} key={it.id}>
              <Card>
                <CardContent>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                    <Typography variant="h6" sx={{ flex: 1 }}>{it.name}</Typography>
                    {it.role && <Chip label={it.role} size="small" color="primary" variant="outlined" />}
                    <IconButton size="small" onClick={() => openEdit(it)} title="编辑"><EditIcon fontSize="small" /></IconButton>
                    <IconButton size="small" onClick={() => doDelete(it.id)} title="删除"><DeleteIcon fontSize="small" /></IconButton>
                  </Box>
                  {it.description && (
                    <Typography variant="body2" color="text.secondary" sx={{ whiteSpace: 'pre-wrap' }}>
                      {it.description}
                    </Typography>
                  )}
                </CardContent>
              </Card>
            </Grid>
          ))}
        </Grid>
      )}
      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{editing ? '编辑人物卡' : '新建人物卡'}</DialogTitle>
        <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 2 }}>
          <TextField label="姓名" value={name} onChange={(e) => setName(e.target.value)} fullWidth />
          <TextField
            label="定位"
            value={role}
            onChange={(e) => setRole(e.target.value)}
            fullWidth
            placeholder="如：女主 / 男主 / 反派 / 闺蜜……"
          />
          <TextField
            label="人设"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            fullWidth
            multiline
            rows={5}
            placeholder="外貌、性格、口头禅、背景故事、人物弧光……"
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)}>取消</Button>
          <Button variant="contained" onClick={doSave}>保存</Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}

// ---------------------------------------------------------------------------
// 灵感便签
// ---------------------------------------------------------------------------

function NotePanel({ project }: { project: string }) {
  const [items, setItems] = useState<NoteItem[]>([])
  const [error, setError] = useState('')
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editing, setEditing] = useState<NoteItem | null>(null)
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')

  const load = useCallback(() => {
    writingApi
      .notes(project)
      .then(setItems)
      .catch((e) => setError(`加载便签失败: ${friendlyError(e)}`))
  }, [project])

  useEffect(() => { load() }, [load])

  const openCreate = () => {
    setEditing(null); setTitle(''); setContent('')
    setDialogOpen(true)
  }
  const openEdit = (it: NoteItem) => {
    setEditing(it); setTitle(it.title); setContent(it.content)
    setDialogOpen(true)
  }

  const doSave = async () => {
    if (!title.trim() && !content.trim()) { setError('标题与内容不能同时为空'); return }
    setError('')
    try {
      if (editing) {
        await writingApi.updateNote(editing.id, { title, content })
      } else {
        await writingApi.createNote({ project, title, content })
      }
      setDialogOpen(false)
      load()
    } catch (e) {
      setError(`保存失败: ${friendlyError(e)}`)
    }
  }

  const doDelete = async (id: number) => {
    if (!window.confirm('确定删除这条便签吗？')) return
    try {
      await writingApi.deleteNote(id)
      load()
    } catch (e) {
      setError(`删除失败: ${friendlyError(e)}`)
    }
  }

  return (
    <Box>
      {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>{error}</Alert>}
      <Box sx={{ mb: 2 }}>
        <Button variant="contained" startIcon={<AddIcon />} onClick={openCreate}>
          记一条灵感
        </Button>
      </Box>
      {items.length === 0 ? (
        <Typography color="text.secondary">灵感稍纵即逝，先记下来再说</Typography>
      ) : (
        items.map((it) => (
          <Paper key={it.id} sx={{ p: 2, mb: 1.5, cursor: 'pointer' }} onClick={() => openEdit(it)}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Typography variant="subtitle1" sx={{ flex: 1, fontWeight: 600 }}>
                {it.title || '（无标题）'}
              </Typography>
              <IconButton
                size="small"
                onClick={(e) => { e.stopPropagation(); doDelete(it.id) }}
                title="删除"
              >
                <DeleteIcon fontSize="small" />
              </IconButton>
            </Box>
            {it.content && (
              <Typography
                variant="body2"
                color="text.secondary"
                sx={{
                  mt: 0.5, whiteSpace: 'pre-wrap', display: '-webkit-box',
                  WebkitLineClamp: 3, WebkitBoxOrient: 'vertical', overflow: 'hidden',
                }}
              >
                {it.content}
              </Typography>
            )}
          </Paper>
        ))
      )}
      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{editing ? '编辑便签' : '记一条灵感'}</DialogTitle>
        <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 2 }}>
          <TextField label="标题" value={title} onChange={(e) => setTitle(e.target.value)} fullWidth />
          <TextField
            label="内容"
            value={content}
            onChange={(e) => setContent(e.target.value)}
            fullWidth
            multiline
            rows={6}
            placeholder="突然冒出来的桥段、金句、设定……"
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)}>取消</Button>
          <Button variant="contained" onClick={doSave}>保存</Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}

// ---------------------------------------------------------------------------
// 码字统计
// ---------------------------------------------------------------------------

function StatsPanel({ project }: { project: string }) {
  const [stats, setStats] = useState<WritingStats | null>(null)
  const [error, setError] = useState('')
  const [days, setDays] = useState(30)

  const load = useCallback(() => {
    writingApi
      .stats(project, days)
      .then(setStats)
      .catch((e) => setError(`加载统计失败: ${friendlyError(e)}`))
  }, [project, days])

  useEffect(() => { load() }, [load])

  return (
    <Box>
      {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>{error}</Alert>}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
        <TextField select label="时间范围" value={days} onChange={(e) => setDays(Number(e.target.value))} size="small" sx={{ minWidth: 140 }}>
          <MenuItem value={7}>近 7 天</MenuItem>
          <MenuItem value={30}>近 30 天</MenuItem>
          <MenuItem value={90}>近 90 天</MenuItem>
        </TextField>
      </Box>
      {!stats ? (
        <Typography color="text.secondary">加载中……</Typography>
      ) : (
        <Box>
          <Grid container spacing={2} sx={{ mb: 3 }}>
            <Grid item xs={6} sm={3}>
              <Card><CardContent>
                <Typography variant="body2" color="text.secondary">今日码字</Typography>
                <Typography variant="h4">{stats.todayWords.toLocaleString()}</Typography>
              </CardContent></Card>
            </Grid>
            <Grid item xs={6} sm={3}>
              <Card><CardContent>
                <Typography variant="body2" color="text.secondary">累计字数</Typography>
                <Typography variant="h4">{stats.totalWords.toLocaleString()}</Typography>
                <Typography variant="caption" color="text.secondary">{stats.totalChapters} 章</Typography>
              </CardContent></Card>
            </Grid>
            <Grid item xs={6} sm={3}>
              <Card><CardContent>
                <Typography variant="body2" color="text.secondary">连续码字</Typography>
                <Typography variant="h4">{stats.streakDays}<Typography component="span" variant="body1"> 天</Typography></Typography>
              </CardContent></Card>
            </Grid>
            <Grid item xs={6} sm={3}>
              <Card><CardContent>
                <Typography variant="body2" color="text.secondary">今日章节</Typography>
                <Typography variant="h4">{stats.todayChapters}</Typography>
              </CardContent></Card>
            </Grid>
          </Grid>
          <Typography variant="subtitle1" sx={{ mb: 1, fontWeight: 600 }}>每日码字趋势</Typography>
          <BarChart
            categories={stats.history.map((h) => h.date.slice(5))}
            series={[{ name: '字数', data: stats.history.map((h) => h.words) }]}
            height={260}
          />
        </Box>
      )}
    </Box>
  )
}

// ---------------------------------------------------------------------------
// 导出
// ---------------------------------------------------------------------------

function ExportPanel({ project }: { project: string }) {
  const [error, setError] = useState('')
  const [info, setInfo] = useState('')
  const [exporting, setExporting] = useState(false)

  const doExport = async () => {
    setError(''); setInfo(''); setExporting(true)
    try {
      const r = await writingApi.exportTxt(project)
      const blob = new Blob([r.content], { type: 'text/plain;charset=utf-8' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = r.filename
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
      setInfo(`已导出 ${r.chapters} 章、约 ${r.words.toLocaleString()} 字：${r.filename}`)
    } catch (e) {
      setError(`导出失败: ${friendlyError(e)}`)
    } finally {
      setExporting(false)
    }
  }

  return (
    <Box>
      {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>{error}</Alert>}
      {info && <Alert severity="success" sx={{ mb: 2 }} onClose={() => setInfo('')}>{info}</Alert>}
      <Paper sx={{ p: 3, maxWidth: 560 }}>
        <Typography variant="h6" sx={{ mb: 1 }}>导出全书 TXT</Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          把「{project}」的全部章节按顺序拼接成一个 TXT 文件下载，方便备份、投稿或导入其他排版工具。
        </Typography>
        <Button
          variant="contained"
          startIcon={<DownloadIcon />}
          onClick={doExport}
          disabled={exporting}
        >
          {exporting ? '导出中…' : '导出 TXT'}
        </Button>
      </Paper>
    </Box>
  )
}
