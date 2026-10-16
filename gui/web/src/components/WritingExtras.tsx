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
import MenuBookIcon from '@mui/icons-material/MenuBook'
import AssignmentIcon from '@mui/icons-material/Assignment'
import { writingApi, toolsApi, friendlyError } from '../api/client'
import type { WritingProject } from '../types'
import type { OutlineItem, CharacterCard, NoteItem, WritingStats, HookItem, TensionAnalysisResult } from '../api/client'
import { useThemeMode } from '../state/ThemeModeContext'
import { useI18n } from '../state/I18nContext'
import { ink, glassCard } from '../ink'
import CreationRateChart from './charts/CreationRateChart'
import EmotionWaveChart from './charts/EmotionWaveChart'
import RhythmRadarChart from './charts/RhythmRadarChart'

const OUTLINE_STATUS_COLOR: Record<string, 'default' | 'primary' | 'success'> = {
  planned: 'default',
  writing: 'primary',
  done: 'success',
}

export default function WritingExtras() {
  const { t } = useI18n()
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
          label={t('extras_project_label')}
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
          {t('extras_project_desc')}
        </Typography>
      </Box>
      {error && <Alert severity="error" onClose={() => setError('')}>{error}</Alert>}
      {!project ? (
        <Alert severity="info">{t('extras_no_project_alert')}</Alert>
      ) : (
        <Box sx={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
          <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ borderBottom: 1, borderColor: 'divider' }}>
            <Tab label={t('extras_tab_outline')} />
            <Tab label={t('extras_tab_character')} />
            <Tab label={t('extras_tab_notes')} />
            <Tab label={t('extras_tab_dashboard')} />
            <Tab label={t('extras_tab_export')} />
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
  const { t } = useI18n()
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

  const kindLabel = (k: string) => (k === 'volume' ? t('extras_outline_volume') : t('extras_outline_chapter'))
  const statusLabel = (s: string) => {
    if (s === 'planned') return t('extras_outline_status_planned')
    if (s === 'writing') return t('extras_outline_status_writing')
    if (s === 'done') return t('extras_outline_status_done')
    return s
  }

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
            {t('extras_outline_add_btn')}
          </Button>
          <Button variant="outlined" color="primary" onClick={openHookTemplateDialog}>
            {t('extras_outline_hook_template_btn')}
          </Button>
        </Box>
        <Typography variant="caption" color="text.secondary">
          共 {items.filter((i) => i.kind === 'volume').length} {t('extras_outline_volume')} / {items.filter((i) => i.kind === 'chapter').length} {t('extras_outline_chapter')} ｜ 支持上下微移原子重排
        </Typography>
      </Box>

      {items.length === 0 ? (
        <Paper elevation={0} sx={{ p: 4, textAlign: 'center', ...glassCard(isDark) }}>
          <Typography color="text.secondary">{t('extras_outline_empty')}</Typography>
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
                  label={kindLabel(it.kind)}
                  size="small"
                  color={isVolume ? 'primary' : 'default'}
                  variant={isVolume ? 'filled' : 'outlined'}
                />
                <Typography variant="subtitle1" sx={{ flex: 1, fontWeight: isVolume ? 700 : 600 }}>
                  {it.title}
                </Typography>
                <Chip
                  label={statusLabel(it.status)}
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
        <DialogTitle>{editing ? t('extras_outline_edit_title') : t('extras_outline_new_title')}</DialogTitle>
        <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 2 }}>
          <TextField select label={t('extras_outline_kind')} value={kind} onChange={(e) => setKind(e.target.value)}>
            <MenuItem value="volume">{t('extras_outline_kind_volume')}</MenuItem>
            <MenuItem value="chapter">{t('extras_outline_kind_chapter')}</MenuItem>
          </TextField>
          <TextField label={t('extras_outline_item_title')} value={title} onChange={(e) => setTitle(e.target.value)} fullWidth />
          <TextField
            label={t('extras_outline_summary')}
            value={summary}
            onChange={(e) => setSummary(e.target.value)}
            fullWidth
            multiline
            rows={4}
            placeholder={t('extras_outline_summary_ph')}
          />
          <TextField select label={t('extras_outline_status')} value={status} onChange={(e) => setStatus(e.target.value)}>
            <MenuItem value="planned">{t('extras_outline_status_planned')}</MenuItem>
            <MenuItem value="writing">{t('extras_outline_status_writing')}</MenuItem>
            <MenuItem value="done">{t('extras_outline_status_done')}</MenuItem>
          </TextField>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)}>{t('action_cancel')}</Button>
          <Button variant="contained" onClick={doSave}>{t('action_save')}</Button>
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
            {t('extras_outline_template_dialog_title')}
          </Typography>
          <Typography component="span" variant="caption" color="text.secondary">
            {t('extras_outline_template_dialog_subtitle')}
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
                label={t('extras_outline_template_select')}
                value={selectedHook?.id || ''}
                onChange={(e) => {
                  const target = templates.find((tmp) => tmp.id === e.target.value)
                  if (target) setSelectedHook(target)
                }}
                fullWidth
              >
                {templates.map((tmpl) => (
                  <MenuItem key={tmpl.id} value={tmpl.id}>
                    [{tmpl.genre}] {tmpl.name}
                  </MenuItem>
                ))}
              </TextField>

              {selectedHook && (
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
                  <Paper variant="outlined" sx={{ p: 1.5, bgcolor: 'action.hover' }}>
                    <Typography variant="subtitle2" color="primary" fontWeight={700} gutterBottom>
                      {t('extras_outline_template_first300')}
                    </Typography>
                    <Typography variant="body2" sx={{ lineHeight: 1.7 }}>
                      {selectedHook.first300Words}
                    </Typography>
                  </Paper>

                  <Paper variant="outlined" sx={{ p: 1.5 }}>
                    <Typography variant="subtitle2" fontWeight={700} color="text.primary" gutterBottom>
                      {t('extras_outline_template_beat1')}
                    </Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ lineHeight: 1.7 }}>
                      {selectedHook.chapter1Beat}
                    </Typography>
                  </Paper>

                  <Paper variant="outlined" sx={{ p: 1.5 }}>
                    <Typography variant="subtitle2" fontWeight={700} color="text.primary" gutterBottom>
                      {t('extras_outline_template_beat2')}
                    </Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ lineHeight: 1.7 }}>
                      {selectedHook.chapter2Beat}
                    </Typography>
                  </Paper>

                  <Paper variant="outlined" sx={{ p: 1.5 }}>
                    <Typography variant="subtitle2" fontWeight={700} color="text.primary" gutterBottom>
                      {t('extras_outline_template_beat3')}
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
          <Button onClick={() => setTemplateOpen(false)}>{t('action_cancel')}</Button>
          <Button
            variant="contained"
            color="primary"
            onClick={doApplyTemplate}
            disabled={!selectedHook}
          >
            {t('extras_outline_template_apply')}
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
  const { t } = useI18n()
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
          {t('extras_char_add_btn')}
        </Button>
        <Typography variant="caption" color="text.secondary">
          当前共 {items.length} 位角色 ｜ 支持人物阵营与人物关系网络关联
        </Typography>
      </Box>

      {items.length === 0 ? (
        <Paper elevation={0} sx={{ p: 4, textAlign: 'center', ...glassCard(isDark) }}>
          <Typography color="text.secondary">{t('extras_char_empty')}</Typography>
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
        <DialogTitle>{editing ? t('extras_char_edit_title') : t('extras_char_new_title')}</DialogTitle>
        <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 2 }}>
          <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
            <TextField label={t('extras_char_name')} value={name} onChange={(e) => setName(e.target.value)} fullWidth />
            <Button
              variant="outlined"
              onClick={handleRandomName}
              sx={{ minWidth: 96, height: 40, whiteSpace: 'nowrap' }}
            >
              {t('extras_char_random_name')}
            </Button>
          </Box>
          <TextField
            label={t('extras_char_role')}
            value={role}
            onChange={(e) => setRole(e.target.value)}
            fullWidth
            placeholder={t('extras_char_role_ph')}
          />
          <TextField select label={t('extras_char_camp')} value={camp} onChange={(e) => setCamp(e.target.value)} fullWidth>
            <MenuItem value="主角阵营">{t('extras_char_camp_protagonist')}</MenuItem>
            <MenuItem value="反派宿敌">{t('extras_char_camp_antagonist')}</MenuItem>
            <MenuItem value="中立势力">{t('extras_char_camp_neutral')}</MenuItem>
            <MenuItem value="宗门高层">{t('extras_char_camp_sect')}</MenuItem>
            <MenuItem value="世外高人">{t('extras_char_camp_hermit')}</MenuItem>
          </TextField>
          <Box sx={{ display: 'flex', gap: 1.5 }}>
            <TextField
              label={t('extras_char_rel_target')}
              value={relationTarget}
              onChange={(e) => setRelationTarget(e.target.value)}
              sx={{ flex: 1 }}
              placeholder={t('extras_char_rel_target_ph')}
            />
            <TextField
              label={t('extras_char_rel_type')}
              value={relationType}
              onChange={(e) => setRelationType(e.target.value)}
              sx={{ width: 140 }}
              placeholder={t('extras_char_rel_type_ph')}
            />
          </Box>
          <TextField
            label={t('extras_char_desc')}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            fullWidth
            multiline
            rows={5}
            placeholder={t('extras_char_desc_ph')}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)}>{t('action_cancel')}</Button>
          <Button variant="contained" onClick={doSave}>{t('action_save')}</Button>
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
  const { t } = useI18n()
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
          {t('extras_note_add_btn')}
        </Button>
      </Box>
      {items.length === 0 ? (
        <Paper elevation={0} sx={{ p: 4, textAlign: 'center', ...glassCard(isDark) }}>
          <Typography color="text.secondary">{t('extras_note_empty')}</Typography>
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
                    {it.title || t('extras_note_untitled')}
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
        <DialogTitle>{editing ? t('extras_note_edit_title') : t('extras_note_new_title')}</DialogTitle>
        <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 2 }}>
          <TextField label={t('extras_note_title')} value={title} onChange={(e) => setTitle(e.target.value)} fullWidth />
          <TextField
            label={t('extras_note_content')}
            value={content}
            onChange={(e) => setContent(e.target.value)}
            fullWidth
            multiline
            rows={6}
            placeholder={t('extras_note_content_ph')}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)}>{t('action_cancel')}</Button>
          <Button variant="contained" onClick={doSave}>{t('action_save')}</Button>
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
  const { t } = useI18n()
  const [stats, setStats] = useState<WritingStats | null>(null)
  const [error, setError] = useState('')
  const [days, setDays] = useState(30)

  // 黄金三章与章节张力动态比对
  const [benchmark, setBenchmark] = useState<'classic' | 'fast_hook' | 'steady' | 'face_slap'>('classic')
  const [tensionResult, setTensionResult] = useState<TensionAnalysisResult | null>(null)
  const [tensionLoading, setTensionLoading] = useState(false)
  const [showTensionDialog, setShowTensionDialog] = useState(false)
  const [draftInput, setDraftInput] = useState('')

  const load = useCallback(() => {
    writingApi
      .stats(project, days)
      .then(setStats)
      .catch((e) => setError(`加载仪表盘统计失败: ${friendlyError(e)}`))
  }, [project, days])

  useEffect(() => {
    load()
  }, [load])

  const runTensionAnalysis = async (text: string, bm = benchmark) => {
    if (!text.trim()) return
    setTensionLoading(true)
    try {
      const res = await writingApi.analyzeTension({
        text,
        benchmark: bm,
      })
      setTensionResult(res)
      setShowTensionDialog(false)
    } catch (e) {
      setError(`张力分析失败: ${friendlyError(e)}`)
    } finally {
      setTensionLoading(false)
    }
  }

  const handleBenchmarkChange = (bm: 'classic' | 'fast_hook' | 'steady' | 'face_slap') => {
    setBenchmark(bm)
    if (draftInput.trim()) {
      runTensionAnalysis(draftInput, bm)
    }
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2.5 }}>
      {error && <Alert severity="error" onClose={() => setError('')}>{error}</Alert>}
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <Typography variant="h6" fontWeight={700}>
          {t('extras_dash_title')}
        </Typography>
        <TextField
          select
          label={t('extras_dash_timespan')}
          value={days}
          onChange={(e) => setDays(Number(e.target.value))}
          size="small"
          sx={{ minWidth: 130 }}
        >
          <MenuItem value={7}>{t('extras_dash_7days')}</MenuItem>
          <MenuItem value={30}>{t('extras_dash_30days')}</MenuItem>
          <MenuItem value={90}>{t('extras_dash_90days')}</MenuItem>
        </TextField>
      </Box>

      {!stats ? (
        <Typography color="text.secondary">{t('extras_dash_loading')}</Typography>
      ) : (
        <>
          {/* 四大指标卡 */}
          <Grid container spacing={2}>
            <Grid item xs={6} sm={3}>
              <Card elevation={0} sx={glassCard(isDark)}>
                <CardContent>
                  <Typography variant="caption" color="text.secondary" fontWeight={600}>{t('extras_dash_today_words')}</Typography>
                  <Typography variant="h4" fontWeight={800} sx={{ color: '#2563EB', my: 0.5 }}>
                    {stats.todayWords.toLocaleString()}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">{t('extras_dash_words_unit')}</Typography>
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={6} sm={3}>
              <Card elevation={0} sx={glassCard(isDark)}>
                <CardContent>
                  <Typography variant="caption" color="text.secondary" fontWeight={600}>{t('extras_dash_total_words')}</Typography>
                  <Typography variant="h4" fontWeight={800} sx={{ color: '#059669', my: 0.5 }}>
                    {stats.totalWords.toLocaleString()}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">{stats.totalChapters} {t('extras_dash_chapters_unit')}</Typography>
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={6} sm={3}>
              <Card elevation={0} sx={glassCard(isDark)}>
                <CardContent>
                  <Typography variant="caption" color="text.secondary" fontWeight={600}>{t('extras_dash_streak')}</Typography>
                  <Typography variant="h4" fontWeight={800} sx={{ color: '#D97706', my: 0.5 }}>
                    {stats.streakDays}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">{t('extras_dash_streak_unit')}</Typography>
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={6} sm={3}>
              <Card elevation={0} sx={glassCard(isDark)}>
                <CardContent>
                  <Typography variant="caption" color="text.secondary" fontWeight={600}>{t('extras_dash_today_chapters')}</Typography>
                  <Typography variant="h4" fontWeight={800} sx={{ color: '#8B5CF6', my: 0.5 }}>
                    {stats.todayChapters}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">{t('extras_dash_chapters_done')}</Typography>
                </CardContent>
              </Card>
            </Grid>
          </Grid>

          {/* 创作速率与字数走势折线图 */}
          <Paper elevation={0} sx={{ p: 2.5, ...glassCard(isDark) }}>
            <Typography variant="subtitle1" fontWeight={700} sx={{ mb: 1.5 }}>
              {t('extras_dash_creation_chart_title')}
            </Typography>
            <CreationRateChart data={stats.history} height={260} />
          </Paper>

          {/* 情绪起伏波形图 + 爽点节奏雷达图 */}
          <Grid container spacing={2}>
            <Grid item xs={12} md={6}>
              <Paper elevation={0} sx={{ p: 2.5, height: '100%', ...glassCard(isDark) }}>
                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1, flexWrap: 'wrap', gap: 1 }}>
                  <Typography variant="subtitle1" fontWeight={700}>
                    {t('extras_dash_wave_chart_title')}
                  </Typography>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <TextField
                      select
                      size="small"
                      value={benchmark}
                      onChange={(e) => handleBenchmarkChange(e.target.value as any)}
                      sx={{ minWidth: 130 }}
                      label={t('extras_dash_benchmark')}
                    >
                      <MenuItem value="classic">{t('extras_dash_bm_classic')}</MenuItem>
                      <MenuItem value="fast_hook">{t('extras_dash_bm_fast_hook')}</MenuItem>
                      <MenuItem value="steady">{t('extras_dash_bm_steady')}</MenuItem>
                      <MenuItem value="face_slap">{t('extras_dash_bm_face_slap')}</MenuItem>
                    </TextField>
                    <Button
                      variant="outlined"
                      size="small"
                      onClick={() => setShowTensionDialog(true)}
                    >
                      {t('extras_dash_btn_analyze')}
                    </Button>
                  </Box>
                </Box>
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
                  监测剧情平淡期与高潮爆发期，红线为章节实测，虚线为神作对标基准
                </Typography>
                {tensionResult && (
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1, flexWrap: 'wrap' }}>
                    <Chip
                      size="small"
                      label={`标杆拟合度: ${tensionResult.benchmarkAlignmentScore}%`}
                      color={tensionResult.benchmarkAlignmentScore >= 75 ? 'success' : 'primary'}
                      variant="outlined"
                    />
                    <Chip
                      size="small"
                      label={`最高潮: ${tensionResult.climaxSegment} (${tensionResult.maxTension}分)`}
                      sx={{ bgcolor: 'rgba(225, 29, 72, 0.1)', color: '#E11D48', fontWeight: 600 }}
                    />
                    <Chip
                      size="small"
                      label={`均值: ${tensionResult.avgTension} ｜ 波动: ±${tensionResult.tensionVariance}`}
                      variant="outlined"
                    />
                  </Box>
                )}
                <EmotionWaveChart
                  height={240}
                  tensionPoints={tensionResult ? tensionResult.tensionCurve : undefined}
                  benchmarkPoints={tensionResult ? tensionResult.benchmarkCurve : undefined}
                  benchmarkName={tensionResult?.benchmarkName}
                  labels={tensionResult?.segments}
                />
                {tensionResult?.pacingFeedback && tensionResult.pacingFeedback.length > 0 && (
                  <Box sx={{ mt: 1.5, p: 1.5, borderRadius: 1.5, bgcolor: isDark ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.02)' }}>
                    {tensionResult.pacingFeedback.map((f, i) => (
                      <Typography key={i} variant="caption" sx={{ display: 'block', color: 'text.secondary', mb: 0.5 }}>
                        {f}
                      </Typography>
                    ))}
                  </Box>
                )}
              </Paper>
            </Grid>
            <Grid item xs={12} md={6}>
              <Paper elevation={0} sx={{ p: 2.5, height: '100%', ...glassCard(isDark) }}>
                <Typography variant="subtitle1" fontWeight={700} sx={{ mb: 0.5 }}>
                  {t('extras_dash_radar_title')}
                </Typography>
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
                  {t('extras_dash_radar_subtitle')}
                </Typography>
                <RhythmRadarChart height={240} />
              </Paper>
            </Grid>
          </Grid>
        </>
      )}

      {/* 章节草稿张力测算弹窗 */}
      <Dialog open={showTensionDialog} onClose={() => setShowTensionDialog(false)} maxWidth="sm" fullWidth>
        <DialogTitle>测算章节情绪张力波形</DialogTitle>
        <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 2 }}>
          <Typography variant="body2" color="text.secondary">
            粘贴当前正在创作的章节草稿，系统将通过冲突关键词、标点短句节奏、人物对峙与感官微表情，计算整章情绪起伏波形并与标杆对齐。
          </Typography>
          <TextField
            label="章节正文草稿"
            multiline
            rows={8}
            value={draftInput}
            onChange={(e) => setDraftInput(e.target.value)}
            placeholder="粘贴本章草稿内容……（建议 1,000 字以上以获得更精准波形）"
            fullWidth
          />
        </DialogContent>
        <DialogActions>
          <Button
            size="small"
            onClick={() => {
              const sample = '寒风呼啸，江水刺骨冰冷。红围巾在夜色中如鲜血翻飞！少年毫不犹豫甩开外套跃入刺骨冰江！\n“救命！”呼救声微弱颤抖，水花狂暴激荡。他咬紧牙关，在生死边缘拉回了下沉的躯体！\n岸边警笛骤鸣，众人骇然围拢。危机暂退，两人精疲力竭倒在雪地中，大口喘息。'
              setDraftInput(sample)
              runTensionAnalysis(sample)
            }}
          >
            填入示范高潮草稿
          </Button>
          <Button onClick={() => setShowTensionDialog(false)}>{t('action_cancel')}</Button>
          <Button
            variant="contained"
            disabled={!draftInput.trim() || tensionLoading}
            onClick={() => runTensionAnalysis(draftInput)}
          >
            {tensionLoading ? '分析中…' : '开始比对'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}

// ---------------------------------------------------------------------------
// 5. 规范多格式导出（Word / Markdown / TXT）
// ---------------------------------------------------------------------------

function ExportPanel({ project }: { project: string }) {
  const { isDark } = useThemeMode()
  const { t } = useI18n()
  const [error, setError] = useState('')
  const [info, setInfo] = useState('')
  const [exportingFormat, setExportingFormat] = useState<string | null>(null)

  const handleExport = async (format: 'docx' | 'epub' | 'shunn' | 'md' | 'txt') => {
    setError('')
    setInfo('')
    setExportingFormat(format)
    try {
      const res = await writingApi.export(project, format)
      if ((format === 'docx' || format === 'epub') && res.contentBase64) {
        // Base64 解码为二进制 Blob
        const byteCharacters = atob(res.contentBase64)
        const byteNumbers = new Array(byteCharacters.length)
        for (let i = 0; i < byteCharacters.length; i++) {
          byteNumbers[i] = byteCharacters.charCodeAt(i)
        }
        const byteArray = new Uint8Array(byteNumbers)
        const mimeType =
          format === 'epub'
            ? 'application/epub+zip'
            : 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        const blob = new Blob([byteArray], { type: mimeType })
        triggerDownload(blob, res.filename)
      } else {
        // 纯文本 / Markdown / Shunn 文稿
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
          {t('extras_export_title')}
        </Typography>
        <Typography variant="caption" color="text.secondary">
          {t('extras_export_desc')}
        </Typography>
      </Box>

      <Grid container spacing={2.5}>
        {/* Word docx 导出卡 */}
        <Grid item xs={12} sm={6} md={4}>
          <Paper elevation={0} sx={{ p: 3, height: '100%', display: 'flex', flexDirection: 'column', ...glassCard(isDark) }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 1.5 }}>
              <DescriptionIcon sx={{ color: '#2563EB', fontSize: 28 }} />
              <Box>
                <Typography variant="subtitle1" fontWeight={700}>{t('extras_export_docx_title')}</Typography>
                <Typography variant="caption" color="text.secondary">{t('extras_export_docx_tag')}</Typography>
              </Box>
            </Box>
            <Typography variant="body2" color="text.secondary" sx={{ flex: 1, mb: 2, lineHeight: 1.6 }}>
              {t('extras_export_docx_desc')}
            </Typography>
            <Button
              variant="contained"
              startIcon={<DownloadIcon />}
              onClick={() => handleExport('docx')}
              disabled={!!exportingFormat}
            >
              {exportingFormat === 'docx' ? '生成 docx 中…' : t('extras_export_docx_btn')}
            </Button>
          </Paper>
        </Grid>

        {/* EPUB 3.0 电子书导出卡 */}
        <Grid item xs={12} sm={6} md={4}>
          <Paper elevation={0} sx={{ p: 3, height: '100%', display: 'flex', flexDirection: 'column', ...glassCard(isDark) }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 1.5 }}>
              <MenuBookIcon sx={{ color: '#7C3AED', fontSize: 28 }} />
              <Box>
                <Typography variant="subtitle1" fontWeight={700}>{t('extras_export_epub_title')}</Typography>
                <Typography variant="caption" color="text.secondary">{t('extras_export_epub_tag')}</Typography>
              </Box>
            </Box>
            <Typography variant="body2" color="text.secondary" sx={{ flex: 1, mb: 2, lineHeight: 1.6 }}>
              {t('extras_export_epub_desc')}
            </Typography>
            <Button
              variant="contained"
              sx={{ bgcolor: '#7C3AED', '&:hover': { bgcolor: '#6D28D9' } }}
              startIcon={<DownloadIcon />}
              onClick={() => handleExport('epub')}
              disabled={!!exportingFormat}
            >
              {exportingFormat === 'epub' ? '打包 epub 中…' : t('extras_export_epub_btn')}
            </Button>
          </Paper>
        </Grid>

        {/* William Shunn 标准投稿文稿 */}
        <Grid item xs={12} sm={6} md={4}>
          <Paper elevation={0} sx={{ p: 3, height: '100%', display: 'flex', flexDirection: 'column', ...glassCard(isDark) }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 1.5 }}>
              <AssignmentIcon sx={{ color: '#0284C7', fontSize: 28 }} />
              <Box>
                <Typography variant="subtitle1" fontWeight={700}>{t('extras_export_shunn_title')}</Typography>
                <Typography variant="caption" color="text.secondary">{t('extras_export_shunn_tag')}</Typography>
              </Box>
            </Box>
            <Typography variant="body2" color="text.secondary" sx={{ flex: 1, mb: 2, lineHeight: 1.6 }}>
              {t('extras_export_shunn_desc')}
            </Typography>
            <Button
              variant="outlined"
              color="info"
              startIcon={<DownloadIcon />}
              onClick={() => handleExport('shunn')}
              disabled={!!exportingFormat}
            >
              {exportingFormat === 'shunn' ? '生成文稿中…' : t('extras_export_shunn_btn')}
            </Button>
          </Paper>
        </Grid>

        {/* Markdown md 导出卡 */}
        <Grid item xs={12} sm={6} md={6}>
          <Paper elevation={0} sx={{ p: 3, height: '100%', display: 'flex', flexDirection: 'column', ...glassCard(isDark) }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 1.5 }}>
              <CodeIcon sx={{ color: '#059669', fontSize: 28 }} />
              <Box>
                <Typography variant="subtitle1" fontWeight={700}>{t('extras_export_md_title')}</Typography>
                <Typography variant="caption" color="text.secondary">{t('extras_export_md_tag')}</Typography>
              </Box>
            </Box>
            <Typography variant="body2" color="text.secondary" sx={{ flex: 1, mb: 2, lineHeight: 1.6 }}>
              {t('extras_export_md_desc')}
            </Typography>
            <Button
              variant="outlined"
              color="success"
              startIcon={<DownloadIcon />}
              onClick={() => handleExport('md')}
              disabled={!!exportingFormat}
            >
              {exportingFormat === 'md' ? '生成 md 中…' : t('extras_export_md_btn')}
            </Button>
          </Paper>
        </Grid>

        {/* TXT 导出卡 */}
        <Grid item xs={12} sm={6} md={6}>
          <Paper elevation={0} sx={{ p: 3, height: '100%', display: 'flex', flexDirection: 'column', ...glassCard(isDark) }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 1.5 }}>
              <ArticleIcon sx={{ color: '#D97706', fontSize: 28 }} />
              <Box>
                <Typography variant="subtitle1" fontWeight={700}>{t('extras_export_txt_title')}</Typography>
                <Typography variant="caption" color="text.secondary">{t('extras_export_txt_tag')}</Typography>
              </Box>
            </Box>
            <Typography variant="body2" color="text.secondary" sx={{ flex: 1, mb: 2, lineHeight: 1.6 }}>
              {t('extras_export_txt_desc')}
            </Typography>
            <Button
              variant="outlined"
              color="warning"
              startIcon={<DownloadIcon />}
              onClick={() => handleExport('txt')}
              disabled={!!exportingFormat}
            >
              {exportingFormat === 'txt' ? '拼接 txt 中…' : t('extras_export_txt_btn')}
            </Button>
          </Paper>
        </Grid>
      </Grid>
    </Box>
  )
}
