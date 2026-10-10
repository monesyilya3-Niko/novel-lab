// 创作管理（企业级重构）：大纲 / 人物卡 / 灵感便签 / 创作者仪表盘 / 多格式导出。
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
import CircularProgress from '@mui/material/CircularProgress'
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
import ArrowUpwardIcon from '@mui/icons-material/ArrowUpward'
import ArrowDownwardIcon from '@mui/icons-material/ArrowDownward'
import HubIcon from '@mui/icons-material/Hub'
import DescriptionIcon from '@mui/icons-material/Description'
import CodeIcon from '@mui/icons-material/Code'
import ArticleIcon from '@mui/icons-material/Article'
import { writingApi, toolsApi, friendlyError } from '../api/client'
import type { WritingProject } from '../types'
import type { OutlineItem, CharacterCard, NoteItem, WritingStats, HookItem } from '../api/client'
import { useThemeMode } from '../state/ThemeModeContext'
import { ink, glassCard } from '../ink'
import CreationRateChart from './charts/CreationRateChart'
import EmotionWaveChart from './charts/EmotionWaveChart'
import RhythmRadarChart from './charts/RhythmRadarChart'

const OUTLINE_KIND_LABEL: Record<string, string> = { volume: '卷', chapter: '章' }
const OUTLINE_STATUS_LABEL: Record<string, string> = { planned: '待写', writing: '写作中', done: '已完成' }
const OUTLINE_STATUS_COLOR: Record<string, 'default' | 'primary' | 'success'> = {
  planned: 'default',
  writing: 'primary',
  done: 'success',
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
          大纲、人物、便签、创作者仪表盘与导出均按项目隔离
        </Typography>
      </Box>
      {error && <Alert severity="error" onClose={() => setError('')}>{error}</Alert>}
      {!project ? (
        <Alert severity="info">请先在「写作」页签新建写作项目</Alert>
      ) : (
        <Box sx={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
          <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ borderBottom: 1, borderColor: 'divider' }}>
            <Tab label="大纲架构" />
            <Tab label="人物卡与关系" />
            <Tab label="灵感便签" />
            <Tab label="创作者仪表盘" />
            <Tab label="规范导出" />
          </Tabs>
          <Box sx={{ flex: 1, minHeight: 0, overflow: 'auto', py: 2 }}>
            {tab === 0 && <OutlinePanel project={project} />}
            {tab === 1 && <CharacterPanel project={project} />}
            {tab === 2 && <NotePanel project={project} />}
            {tab === 3 && <DashboardPanel project={project} />}
            {tab === 4 && <ExportPanel project={project} />}
          </Box>
        </Box>
      )}
    </Box>
  )
}

// ---------------------------------------------------------------------------
// 1. 大纲架构（支持卷章拖拽/上下移重排）
// ---------------------------------------------------------------------------

function OutlinePanel({ project }: { project: string }) {
  const { isDark } = useThemeMode()
  const [items, setItems] = useState<OutlineItem[]>([])
  const [error, setError] = useState('')
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editing, setEditing] = useState<OutlineItem | null>(null)
  const [kind, setKind] = useState('chapter')
  const [title, setTitle] = useState('')
  const [summary, setSummary] = useState('')
  const [status, setStatus] = useState('planned')

  const [templateOpen, setTemplateOpen] = useState(false)
  const [templates, setTemplates] = useState<HookItem[]>([])
  const [templateLoading, setTemplateLoading] = useState(false)
  const [selectedHook, setSelectedHook] = useState<HookItem | null>(null)

  const openHookTemplateDialog = async () => {
    setTemplateOpen(true)
    if (templates.length === 0) {
      setTemplateLoading(true)
      try {
        const res = await toolsApi.getHooks()
        setTemplates(res.hooks || [])
        if (res.hooks && res.hooks.length > 0) {
          setSelectedHook(res.hooks[0])
        }
      } catch (e) {
        setError(`加载开篇模板失败: ${friendlyError(e)}`)
      } finally {
        setTemplateLoading(false)
      }
    }
  }

  const doApplyTemplate = async () => {
    if (!selectedHook) return
    setError('')
    try {
      const baseOrder = items.length
      await writingApi.createOutline({
        project,
        kind: 'chapter',
        title: `第1章：${selectedHook.name}（首章生死危机）`,
        summary: `【前300字钩子】\n${selectedHook.first300Words}\n\n【第一章节拍】\n${selectedHook.chapter1Beat}`,
        status: 'planned',
        sort_order: baseOrder,
      })
      await writingApi.createOutline({
        project,
        kind: 'chapter',
        title: `第2章：${selectedHook.name}（压迫激化与转机）`,
        summary: `【第二章节拍】\n${selectedHook.chapter2Beat}`,
        status: 'planned',
        sort_order: baseOrder + 1,
      })
      await writingApi.createOutline({
        project,
        kind: 'chapter',
        title: `第3章：${selectedHook.name}（首爽破局与爽点兑现）`,
        summary: `【第三章节拍】\n${selectedHook.chapter3Beat}`,
        status: 'planned',
        sort_order: baseOrder + 2,
      })
      setTemplateOpen(false)
      load()
    } catch (e) {
      setError(`应用黄金三章模板失败: ${friendlyError(e)}`)
    }
  }

  const load = useCallback(() => {
    writingApi
      .outlines(project)
      .then(setItems)
      .catch((e) => setError(`加载大纲失败: ${friendlyError(e)}`))
  }, [project])

  useEffect(() => {
    load()
  }, [load])

  const openCreate = () => {
    setEditing(null)
    setKind('chapter')
    setTitle('')
    setSummary('')
    setStatus('planned')
    setDialogOpen(true)
  }

  const openEdit = (it: OutlineItem) => {
    setEditing(it)
    setKind(it.kind)
    setTitle(it.title)
    setSummary(it.summary)
    setStatus(it.status)
    setDialogOpen(true)
  }

  const doSave = async () => {
    if (!title.trim()) {
      setError('标题不能为空')
      return
    }
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

  const doMove = async (index: number, direction: 'up' | 'down') => {
    const targetIndex = direction === 'up' ? index - 1 : index + 1
    if (targetIndex < 0 || targetIndex >= items.length) return
    const newItems = [...items]
    const temp = newItems[index]
    newItems[index] = newItems[targetIndex]
    newItems[targetIndex] = temp
    setItems(newItems)

    try {
      await writingApi.reorderOutlines(project, newItems.map((it) => it.id))
      load()
    } catch (e) {
      setError(`重排序失败: ${friendlyError(e)}`)
      load()
    }
  }

  return (
    <Box>
      {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError('')}>{error}</Alert>}
      <Box sx={{ mb: 2, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Box sx={{ display: 'flex', gap: 1.5 }}>
          <Button variant="contained" startIcon={<AddIcon />} onClick={openCreate}>
            新增分卷 / 章节
          </Button>
          <Button variant="outlined" color="primary" onClick={openHookTemplateDialog}>
            🚀 引用黄金三章模板
          </Button>
        </Box>
        <Typography variant="caption" color="text.secondary">
          共 {items.filter((i) => i.kind === 'volume').length} 卷 / {items.filter((i) => i.kind === 'chapter').length} 章 ｜ 支持上下微移原子重排
        </Typography>
      </Box>

      {items.length === 0 ? (
        <Paper elevation={0} sx={{ p: 4, textAlign: 'center', ...glassCard(isDark) }}>
          <Typography color="text.secondary">还没有大纲，先从第一卷/第一章开始规划架构吧</Typography>
        </Paper>
      ) : (
        items.map((it, idx) => {
          const isVolume = it.kind === 'volume'
          return (
            <Paper
              key={it.id}
              elevation={0}
              sx={{
                p: 2,
                mb: 1.5,
                ...glassCard(isDark),
                borderLeft: isVolume ? '4px solid #2563EB' : `1px solid ${isDark ? ink.nightLine : ink.hairline}`,
                ml: isVolume ? 0 : 2,
              }}
            >
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <Chip
                  label={OUTLINE_KIND_LABEL[it.kind] ?? it.kind}
                  size="small"
                  color={isVolume ? 'primary' : 'default'}
                  variant={isVolume ? 'filled' : 'outlined'}
                />
                <Typography variant="subtitle1" sx={{ flex: 1, fontWeight: isVolume ? 700 : 600 }}>
                  {it.title}
                </Typography>
                <Chip
                  label={OUTLINE_STATUS_LABEL[it.status] ?? it.status}
                  size="small"
                  color={OUTLINE_STATUS_COLOR[it.status] ?? 'default'}
                  onClick={() => doToggleStatus(it)}
                  sx={{ cursor: 'pointer' }}
                  title="点击切换状态"
                />
                <IconButton
                  size="small"
                  disabled={idx === 0}
                  onClick={() => doMove(idx, 'up')}
                  title="上移"
                >
                  <ArrowUpwardIcon fontSize="small" />
                </IconButton>
                <IconButton
                  size="small"
                  disabled={idx === items.length - 1}
                  onClick={() => doMove(idx, 'down')}
                  title="下移"
                >
                  <ArrowDownwardIcon fontSize="small" />
                </IconButton>
                <IconButton size="small" onClick={() => openEdit(it)} title="编辑">
                  <EditIcon fontSize="small" />
                </IconButton>
                <IconButton size="small" onClick={() => doDelete(it.id)} title="删除">
                  <DeleteIcon fontSize="small" />
                </IconButton>
              </Box>
              {it.summary && (
                <Typography variant="body2" color="text.secondary" sx={{ mt: 1, whiteSpace: 'pre-wrap', pl: 0.5 }}>
                  {it.summary}
                </Typography>
              )}
            </Paper>
          )
        })
      )}

      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{editing ? '编辑大纲' : '新增大纲架构'}</DialogTitle>
        <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 2 }}>
          <TextField select label="类型" value={kind} onChange={(e) => setKind(e.target.value)}>
            <MenuItem value="volume">分卷（Volume）</MenuItem>
            <MenuItem value="chapter">章节（Chapter）</MenuItem>
          </TextField>
          <TextField label="标题" value={title} onChange={(e) => setTitle(e.target.value)} fullWidth />
          <TextField
            label="内容概要 / 剧情线"
            value={summary}
            onChange={(e) => setSummary(e.target.value)}
            fullWidth
            multiline
            rows={4}
            placeholder="这一卷/章的核心冲突、情绪线、重要伏笔……"
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

      {/* 引用黄金三章开篇模板弹窗 */}
      <Dialog
        open={templateOpen}
        onClose={() => setTemplateOpen(false)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', pb: 1 }}>
          <Typography component="span" variant="h6" fontWeight={700}>
            🚀 黄金三章开篇模型库
          </Typography>
          <Typography component="span" variant="caption" color="text.secondary">
            内置 10 大提升留存率的成熟开篇节拍
          </Typography>
        </DialogTitle>
        <DialogContent dividers sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          {templateLoading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
              <CircularProgress size={32} />
            </Box>
          ) : (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <TextField
                select
                label="选择开篇模板"
                value={selectedHook?.id || ''}
                onChange={(e) => {
                  const target = templates.find((t) => t.id === e.target.value)
                  if (target) setSelectedHook(target)
                }}
                fullWidth
              >
                {templates.map((t) => (
                  <MenuItem key={t.id} value={t.id}>
                    [{t.genre}] {t.name}
                  </MenuItem>
                ))}
              </TextField>

              {selectedHook && (
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
                  <Paper variant="outlined" sx={{ p: 1.5, bgcolor: 'action.hover' }}>
                    <Typography variant="subtitle2" color="primary" fontWeight={700} gutterBottom>
                      🔥 前 300 字吸睛钩子：
                    </Typography>
                    <Typography variant="body2" sx={{ lineHeight: 1.7 }}>
                      {selectedHook.first300Words}
                    </Typography>
                  </Paper>

                  <Paper variant="outlined" sx={{ p: 1.5 }}>
                    <Typography variant="subtitle2" fontWeight={700} color="text.primary" gutterBottom>
                      第 1 章节拍（生死危机与冲突）：
                    </Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ lineHeight: 1.7 }}>
                      {selectedHook.chapter1Beat}
                    </Typography>
                  </Paper>

                  <Paper variant="outlined" sx={{ p: 1.5 }}>
                    <Typography variant="subtitle2" fontWeight={700} color="text.primary" gutterBottom>
                      第 2 章节拍（压迫激化与转机）：
                    </Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ lineHeight: 1.7 }}>
                      {selectedHook.chapter2Beat}
                    </Typography>
                  </Paper>

                  <Paper variant="outlined" sx={{ p: 1.5 }}>
                    <Typography variant="subtitle2" fontWeight={700} color="text.primary" gutterBottom>
                      第 3 章节拍（首爽破局与爽点兑现）：
                    </Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ lineHeight: 1.7 }}>
                      {selectedHook.chapter3Beat}
                    </Typography>
                  </Paper>
                </Box>
              )}
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setTemplateOpen(false)}>取消</Button>
          <Button
            variant="contained"
            color="primary"
            onClick={doApplyTemplate}
            disabled={!selectedHook}
          >
            一键应用为前三章大纲
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}

// ---------------------------------------------------------------------------
// 2. 人物卡与关系网
// ---------------------------------------------------------------------------

function CharacterPanel({ project }: { project: string }) {
  const { isDark } = useThemeMode()
  const [items, setItems] = useState<CharacterCard[]>([])
  const [error, setError] = useState('')
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editing, setEditing] = useState<CharacterCard | null>(null)
  const [name, setName] = useState('')
  const [role, setRole] = useState('')
  const [description, setDescription] = useState('')
  const [camp, setCamp] = useState('主角阵营')
  const [relationTarget, setRelationTarget] = useState('')
  const [relationType, setRelationType] = useState('同盟')

  const load = useCallback(() => {
    writingApi
      .characters(project)
      .then(setItems)
      .catch((e) => setError(`加载人物卡失败: ${friendlyError(e)}`))
  }, [project])

  useEffect(() => {
    load()
  }, [load])

  const openCreate = () => {
    setEditing(null)
    setName('')
    setRole('')
    setDescription('')
    setCamp('主角阵营')
    setRelationTarget('')
    setRelationType('同盟')
    setDialogOpen(true)
  }

  const handleRandomName = async () => {
    try {
      const res = await toolsApi.generateNames({ kind: 'character', count: 1 })
      if (res.names && res.names.length > 0) {
        setName(res.names[0])
      }
    } catch (e) {
      setError(`随机起名失败: ${friendlyError(e)}`)
    }
  }

  const openEdit = (it: CharacterCard) => {
    setEditing(it)
    setName(it.name)
    setRole(it.role)
    setDescription(it.description)
    try {
      const extraObj = JSON.parse(it.extra || '{}')
      setCamp(extraObj.camp || '主角阵营')
      setRelationTarget(extraObj.relationTarget || '')
      setRelationType(extraObj.relationType || '同盟')
    } catch {
      setCamp('主角阵营')
      setRelationTarget('')
      setRelationType('同盟')
    }
    setDialogOpen(true)
  }

  const doSave = async () => {
    if (!name.trim()) {
      setError('姓名不能为空')
      return
    }
    setError('')
    const extraData = {
      camp,
      relationTarget: relationTarget.trim(),
      relationType: relationType.trim(),
    }
    try {
      if (editing) {
        await writingApi.updateCharacter(editing.id, {
          name: name.trim(),
          role,
          description,
          extra: extraData,
        })
      } else {
        await writingApi.createCharacter({
          project,
          name: name.trim(),
          role,
          description,
          extra: extraData,
        })
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
      <Box sx={{ mb: 2, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Button variant="contained" startIcon={<AddIcon />} onClick={openCreate}>
          新建人物卡
        </Button>
        <Typography variant="caption" color="text.secondary">
          当前共 {items.length} 位角色 ｜ 支持人物阵营与人物关系网络关联
        </Typography>
      </Box>

      {items.length === 0 ? (
        <Paper elevation={0} sx={{ p: 4, textAlign: 'center', ...glassCard(isDark) }}>
          <Typography color="text.secondary">还没有人物卡，先给主角建立第一张人设立体档案吧</Typography>
        </Paper>
      ) : (
        <Grid container spacing={2}>
          {items.map((it) => {
            let extraObj: any = {}
            try {
              extraObj = JSON.parse(it.extra || '{}')
            } catch {
              extraObj = {}
            }
            return (
              <Grid item xs={12} sm={6} md={4} key={it.id}>
                <Card elevation={0} sx={{ height: '100%', ...glassCard(isDark) }}>
                  <CardContent>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                      <Typography variant="h6" fontWeight={700} sx={{ flex: 1 }}>
                        {it.name}
                      </Typography>
                      {it.role && <Chip label={it.role} size="small" color="primary" variant="outlined" />}
                      <IconButton size="small" onClick={() => openEdit(it)} title="编辑">
                        <EditIcon fontSize="small" />
                      </IconButton>
                      <IconButton size="small" onClick={() => doDelete(it.id)} title="删除">
                        <DeleteIcon fontSize="small" />
                      </IconButton>
                    </Box>

                    {extraObj.camp && (
                      <Box sx={{ mb: 1 }}>
                        <Chip
                          label={extraObj.camp}
                          size="small"
                          sx={{
                            fontSize: 11,
                            bgcolor: extraObj.camp.includes('反派') ? 'rgba(220,38,38,0.1)' : 'rgba(37,99,235,0.1)',
                            color: extraObj.camp.includes('反派') ? '#DC2626' : '#2563EB',
                          }}
                        />
                      </Box>
                    )}

                    {extraObj.relationTarget && (
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 1.5 }}>
                        <HubIcon sx={{ fontSize: 14, color: 'text.secondary' }} />
                        <Typography variant="caption" color="text.secondary">
                          关系：与 <b>{extraObj.relationTarget}</b> 为 [{extraObj.relationType || '关联'}]
                        </Typography>
                      </Box>
                    )}

                    {it.description && (
                      <Typography variant="body2" color="text.secondary" sx={{ whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>
                        {it.description}
                      </Typography>
                    )}
                  </CardContent>
                </Card>
              </Grid>
            )
          })}
        </Grid>
      )}

      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{editing ? '编辑人物卡档案' : '新建人物卡档案'}</DialogTitle>
        <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 2 }}>
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
            <TextField label="姓名" value={name} onChange={(e) => setName(e.target.value)} fullWidth />
            <Button
              variant="outlined"
              onClick={handleRandomName}
              sx={{ minWidth: 96, height: 40, whiteSpace: 'nowrap' }}
            >
              🎲 随机名
            </Button>
          </Box>
          <TextField
            label="定位"
            value={role}
            onChange={(e) => setRole(e.target.value)}
            fullWidth
            placeholder="如：男主 / 女主 / 幕后黑手 / 剑术师尊……"
          />
          <TextField select label="所属阵营" value={camp} onChange={(e) => setCamp(e.target.value)} fullWidth>
            <MenuItem value="主角阵营">主角阵营</MenuItem>
            <MenuItem value="反派宿敌">反派宿敌</MenuItem>
            <MenuItem value="中立势力">中立势力</MenuItem>
            <MenuItem value="宗门高层">宗门高层</MenuItem>
            <MenuItem value="世外高人">世外高人</MenuItem>
          </TextField>
          <Box sx={{ display: 'flex', gap: 1.5 }}>
            <TextField
              label="关系关联角色"
              value={relationTarget}
              onChange={(e) => setRelationTarget(e.target.value)}
              sx={{ flex: 1 }}
              placeholder="如：林天（留空则不设）"
            />
            <TextField
              label="关系类型"
              value={relationType}
              onChange={(e) => setRelationType(e.target.value)}
              sx={{ width: 140 }}
              placeholder="如：宿敌 / 师徒 / 知己"
            />
          </Box>
          <TextField
            label="性格特质、人设背景与人物弧光"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            fullWidth
            multiline
            rows={5}
            placeholder="外貌特征、口癖、行为动机、阴暗面、核心羁绊……"
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
// 3. 灵感便签
// ---------------------------------------------------------------------------

function NotePanel({ project }: { project: string }) {
  const { isDark } = useThemeMode()
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

  useEffect(() => {
    load()
  }, [load])

  const openCreate = () => {
    setEditing(null)
    setTitle('')
    setContent('')
    setDialogOpen(true)
  }

  const openEdit = (it: NoteItem) => {
    setEditing(it)
    setTitle(it.title)
    setContent(it.content)
    setDialogOpen(true)
  }

  const doSave = async () => {
    if (!title.trim() && !content.trim()) {
      setError('标题与内容不能同时为空')
      return
    }
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
          速记灵感
        </Button>
      </Box>
      {items.length === 0 ? (
        <Paper elevation={0} sx={{ p: 4, textAlign: 'center', ...glassCard(isDark) }}>
          <Typography color="text.secondary">灵感稍纵即逝，随时把冒出的金句、桥段、反转记在这里</Typography>
        </Paper>
      ) : (
        <Grid container spacing={2}>
          {items.map((it) => (
            <Grid item xs={12} sm={6} md={4} key={it.id}>
              <Paper
                elevation={0}
                sx={{
                  p: 2,
                  height: '100%',
                  cursor: 'pointer',
                  ...glassCard(isDark),
                  display: 'flex',
                  flexDirection: 'column',
                }}
                onClick={() => openEdit(it)}
              >
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                  <Typography variant="subtitle1" fontWeight={700} sx={{ flex: 1 }}>
                    {it.title || '（无标题灵感）'}
                  </Typography>
                  <IconButton
                    size="small"
                    onClick={(e) => {
                      e.stopPropagation()
                      doDelete(it.id)
                    }}
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
                      whiteSpace: 'pre-wrap',
                      display: '-webkit-box',
                      WebkitLineClamp: 4,
                      WebkitBoxOrient: 'vertical',
                      overflow: 'hidden',
                      lineHeight: 1.6,
                    }}
                  >
                    {it.content}
                  </Typography>
                )}
              </Paper>
            </Grid>
          ))}
        </Grid>
      )}

      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{editing ? '编辑灵感便签' : '速记一条灵感'}</DialogTitle>
        <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 2 }}>
          <TextField label="标题" value={title} onChange={(e) => setTitle(e.target.value)} fullWidth />
          <TextField
            label="灵感详情"
            value={content}
            onChange={(e) => setContent(e.target.value)}
            fullWidth
            multiline
            rows={6}
            placeholder="突然想到的战斗机制、反转包袱、人物对白金句……"
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
// 4. 创作者仪表盘（字数速率折线 + 情绪起伏波形 + 爽点节奏雷达）
// ---------------------------------------------------------------------------

function DashboardPanel({ project }: { project: string }) {
  const { isDark } = useThemeMode()
  const [stats, setStats] = useState<WritingStats | null>(null)
  const [error, setError] = useState('')
  const [days, setDays] = useState(30)

  const load = useCallback(() => {
    writingApi
      .stats(project, days)
      .then(setStats)
      .catch((e) => setError(`加载仪表盘统计失败: ${friendlyError(e)}`))
  }, [project, days])

  useEffect(() => {
    load()
  }, [load])

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2.5 }}>
      {error && <Alert severity="error" onClose={() => setError('')}>{error}</Alert>}
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <Typography variant="h6" fontWeight={700}>
          创作者数据大盘
        </Typography>
        <TextField
          select
          label="时间跨度"
          value={days}
          onChange={(e) => setDays(Number(e.target.value))}
          size="small"
          sx={{ minWidth: 130 }}
        >
          <MenuItem value={7}>近 7 天</MenuItem>
          <MenuItem value={30}>近 30 天</MenuItem>
          <MenuItem value={90}>近 90 天</MenuItem>
        </TextField>
      </Box>

      {!stats ? (
        <Typography color="text.secondary">正在加载创作者大盘数据……</Typography>
      ) : (
        <>
          {/* 四大指标卡 */}
          <Grid container spacing={2}>
            <Grid item xs={6} sm={3}>
              <Card elevation={0} sx={glassCard(isDark)}>
                <CardContent>
                  <Typography variant="caption" color="text.secondary" fontWeight={600}>今日码字</Typography>
                  <Typography variant="h4" fontWeight={800} sx={{ color: '#2563EB', my: 0.5 }}>
                    {stats.todayWords.toLocaleString()}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">字</Typography>
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={6} sm={3}>
              <Card elevation={0} sx={glassCard(isDark)}>
                <CardContent>
                  <Typography variant="caption" color="text.secondary" fontWeight={600}>全书总字数</Typography>
                  <Typography variant="h4" fontWeight={800} sx={{ color: '#059669', my: 0.5 }}>
                    {stats.totalWords.toLocaleString()}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">{stats.totalChapters} 章已落盘</Typography>
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={6} sm={3}>
              <Card elevation={0} sx={glassCard(isDark)}>
                <CardContent>
                  <Typography variant="caption" color="text.secondary" fontWeight={600}>连续更文</Typography>
                  <Typography variant="h4" fontWeight={800} sx={{ color: '#D97706', my: 0.5 }}>
                    {stats.streakDays}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">天不断更</Typography>
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={6} sm={3}>
              <Card elevation={0} sx={glassCard(isDark)}>
                <CardContent>
                  <Typography variant="caption" color="text.secondary" fontWeight={600}>今日成章</Typography>
                  <Typography variant="h4" fontWeight={800} sx={{ color: '#8B5CF6', my: 0.5 }}>
                    {stats.todayChapters}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">章</Typography>
                </CardContent>
              </Card>
            </Grid>
          </Grid>

          {/* 创作速率与字数走势折线图 */}
          <Paper elevation={0} sx={{ p: 2.5, ...glassCard(isDark) }}>
            <Typography variant="subtitle1" fontWeight={700} sx={{ mb: 1.5 }}>
              每日码字与创作速率平滑折线
            </Typography>
            <CreationRateChart data={stats.history} height={260} />
          </Paper>

          {/* 情绪起伏波形图 + 爽点节奏雷达图 */}
          <Grid container spacing={2}>
            <Grid item xs={12} md={6}>
              <Paper elevation={0} sx={{ p: 2.5, height: '100%', ...glassCard(isDark) }}>
                <Typography variant="subtitle1" fontWeight={700} sx={{ mb: 0.5 }}>
                  章节情绪张力起伏波形（起承转合）
                </Typography>
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
                  监测剧情平淡期与高潮爆发期，避免全书持续平推无起伏
                </Typography>
                <EmotionWaveChart height={240} />
              </Paper>
            </Grid>
            <Grid item xs={12} md={6}>
              <Paper elevation={0} sx={{ p: 2.5, height: '100%', ...glassCard(isDark) }}>
                <Typography variant="subtitle1" fontWeight={700} sx={{ mb: 0.5 }}>
                  网文爽点节奏多维雷达图
                </Typography>
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
                  爽点推进、打脸期待、信息密度、金手指进化、章末钩子全维扫描
                </Typography>
                <RhythmRadarChart height={240} />
              </Paper>
            </Grid>
          </Grid>
        </>
      )}
    </Box>
  )
}

// ---------------------------------------------------------------------------
// 5. 规范多格式导出（Word / Markdown / TXT）
// ---------------------------------------------------------------------------

function ExportPanel({ project }: { project: string }) {
  const { isDark } = useThemeMode()
  const [error, setError] = useState('')
  const [info, setInfo] = useState('')
  const [exportingFormat, setExportingFormat] = useState<string | null>(null)

  const handleExport = async (format: 'docx' | 'md' | 'txt') => {
    setError('')
    setInfo('')
    setExportingFormat(format)
    try {
      const res = await writingApi.export(project, format)
      if (format === 'docx' && res.contentBase64) {
        // Base64 解码为二进制 Blob
        const byteCharacters = atob(res.contentBase64)
        const byteNumbers = new Array(byteCharacters.length)
        for (let i = 0; i < byteCharacters.length; i++) {
          byteNumbers[i] = byteCharacters.charCodeAt(i)
        }
        const byteArray = new Uint8Array(byteNumbers)
        const blob = new Blob([byteArray], {
          type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        })
        triggerDownload(blob, res.filename)
      } else {
        // 纯文本 / Markdown
        const blob = new Blob([res.content || ''], { type: 'text/plain;charset=utf-8' })
        triggerDownload(blob, res.filename)
      }
      setInfo(`成功导出 ${res.chapters} 章、约 ${res.words.toLocaleString()} 字：${res.filename}`)
    } catch (e) {
      setError(`导出失败: ${friendlyError(e)}`)
    } finally {
      setExportingFormat(null)
    }
  }

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

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2.5 }}>
      {error && <Alert severity="error" onClose={() => setError('')}>{error}</Alert>}
      {info && <Alert severity="success" onClose={() => setInfo('')}>{info}</Alert>}

      <Box>
        <Typography variant="h6" fontWeight={700}>
          导出全书作品
        </Typography>
        <Typography variant="caption" color="text.secondary">
          纯 Python 标准库零依赖规范导出，支持直接交付排版、投稿或本地备份
        </Typography>
      </Box>

      <Grid container spacing={2.5}>
        {/* Word docx 导出卡 */}
        <Grid item xs={12} md={4}>
          <Paper elevation={0} sx={{ p: 3, height: '100%', display: 'flex', flexDirection: 'column', ...glassCard(isDark) }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 1.5 }}>
              <DescriptionIcon sx={{ color: '#2563EB', fontSize: 28 }} />
              <Box>
                <Typography variant="subtitle1" fontWeight={700}>Word 规范文档 (.docx)</Typography>
                <Typography variant="caption" color="text.secondary">出版/编辑首选</Typography>
              </Box>
            </Box>
            <Typography variant="body2" color="text.secondary" sx={{ flex: 1, mb: 2, lineHeight: 1.6 }}>
              符合网文投稿与出版规约，标题居中、章节居左、正文首行缩进 2 字符、1.5 倍行距，Word / WPS 秒开。
            </Typography>
            <Button
              variant="contained"
              startIcon={<DownloadIcon />}
              onClick={() => handleExport('docx')}
              disabled={!!exportingFormat}
            >
              {exportingFormat === 'docx' ? '生成 docx 中…' : '导出 Word (.docx)'}
            </Button>
          </Paper>
        </Grid>

        {/* Markdown md 导出卡 */}
        <Grid item xs={12} md={4}>
          <Paper elevation={0} sx={{ p: 3, height: '100%', display: 'flex', flexDirection: 'column', ...glassCard(isDark) }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 1.5 }}>
              <CodeIcon sx={{ color: '#059669', fontSize: 28 }} />
              <Box>
                <Typography variant="subtitle1" fontWeight={700}>Markdown 结构化 (.md)</Typography>
                <Typography variant="caption" color="text.secondary">跨平台排版首选</Typography>
              </Box>
            </Box>
            <Typography variant="body2" color="text.secondary" sx={{ flex: 1, mb: 2, lineHeight: 1.6 }}>
              规范二级标题与元数据，适合导入 Obsidian、Typora、Notion 或多平台分发工具。
            </Typography>
            <Button
              variant="outlined"
              color="success"
              startIcon={<DownloadIcon />}
              onClick={() => handleExport('md')}
              disabled={!!exportingFormat}
            >
              {exportingFormat === 'md' ? '生成 md 中…' : '导出 Markdown (.md)'}
            </Button>
          </Paper>
        </Grid>

        {/* TXT 导出卡 */}
        <Grid item xs={12} md={4}>
          <Paper elevation={0} sx={{ p: 3, height: '100%', display: 'flex', flexDirection: 'column', ...glassCard(isDark) }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 1.5 }}>
              <ArticleIcon sx={{ color: '#D97706', fontSize: 28 }} />
              <Box>
                <Typography variant="subtitle1" fontWeight={700}>纯文本格式 (.txt)</Typography>
                <Typography variant="caption" color="text.secondary">通用无格式备份</Typography>
              </Box>
            </Box>
            <Typography variant="body2" color="text.secondary" sx={{ flex: 1, mb: 2, lineHeight: 1.6 }}>
              UTF-8 标准编码，按章号纯净拼接，各大网文作家后台直接全选粘贴无格式污染。
            </Typography>
            <Button
              variant="outlined"
              color="warning"
              startIcon={<DownloadIcon />}
              onClick={() => handleExport('txt')}
              disabled={!!exportingFormat}
            >
              {exportingFormat === 'txt' ? '拼接 txt 中…' : '导出纯文本 (.txt)'}
            </Button>
          </Paper>
        </Grid>
      </Grid>
    </Box>
  )
}
