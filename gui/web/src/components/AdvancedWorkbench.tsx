// M1 高级分析 + M4 资产写入工作台：蒸馏 / 聚合 / 批量状态 / 资产编辑。
// 全量接入 I18nProvider，支持中英文双语国际化。
import { useState, useEffect, useCallback } from 'react'
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
import Chip from '@mui/material/Chip'
import { advancedApi, assetApi } from '../api/client'
import PlatformPanel from './PlatformPanel'
import { kindLabel } from '../assetKindLabels'
import { friendlyError } from '../api/client'
import { useI18n, Locale } from '../state/I18nContext'

function getLocalizedKind(kind: string, locale: Locale, t: (k: string, fb?: string) => string): string {
  if (locale === 'zh-CN') return kindLabel(kind)
  const snake = kind.replace(/[A-Z]/g, (c) => `_${c.toLowerCase()}`)
  return t(`asset_kind_${snake}`, kindLabel(kind))
}

export default function AdvancedWorkbench() {
  const { t } = useI18n()
  const [tab, setTab] = useState(0)

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <Box sx={{ display: 'flex', alignItems: 'center', borderBottom: 1, borderColor: 'divider', pr: 1 }}>
        <Tabs value={tab} onChange={(_, v) => setTab(v)} sx={{ flex: 1, px: 2 }}>
          <Tab label={t('advanced_tab_distill')} />
          <Tab label={t('advanced_tab_batch')} />
          <Tab label={t('advanced_tab_edit')} />
          <Tab label={t('advanced_tab_platform')} />
        </Tabs>
        <ContextHelpButton guideKey="advanced" />
      </Box>
      <Box sx={{ flex: 1, minHeight: 0, overflow: 'auto', p: 2 }}>
        {tab === 0 && <DistillPanel />}
        {tab === 1 && <BatchStatusPanel />}
        {tab === 2 && <AssetEditPanel />}
        {tab === 3 && <PlatformPanel />}
      </Box>
    </Box>
  )
}

// ---------------------------------------------------------------------------
// 蒸馏面板
// ---------------------------------------------------------------------------

const DIM_LABELS: Record<string, Record<Locale, string>> = {
  'voice-card': { 'zh-CN': '声线卡', 'en-US': 'Voice Card' },
  'craft-card': { 'zh-CN': '笔法卡', 'en-US': 'Craft Card' },
  'structure-obs': { 'zh-CN': '结构观测', 'en-US': 'Structure Observation' },
  'commercial-obs': { 'zh-CN': '商业观测', 'en-US': 'Commercial Observation' },
}

function DistillPanel() {
  const { t, locale } = useI18n()
  const [genre, setGenre] = useState('campus-redemption')
  const [status, setStatus] = useState<Record<string, unknown> | null>(null)
  const [result, setResult] = useState<Record<string, unknown> | null>(null)
  const [rawOpen, setRawOpen] = useState(false)
  const [loading, setLoading] = useState(false)

  const loadStatus = useCallback(async () => {
    try {
      const data = await advancedApi.distillStatus(genre)
      setStatus(data as Record<string, unknown>)
    } catch { /* P2-F12：后台轮询静默失败是预期的（避免错误刷屏），状态区保持旧值 */ }
  }, [genre])

  useEffect(() => { loadStatus() }, [loadStatus])

  const doDistill = async () => {
    setLoading(true)
    setResult(null)
    try {
      const data = await advancedApi.distillRun(genre)
      setResult(data as Record<string, unknown>)
      loadStatus()
    } catch (e) {
      setResult({ error: friendlyError(e) })
    } finally {
      setLoading(false)
    }
  }

  const books = (result?.books as string[]) ?? []
  const written = (result?.written as string[]) ?? []
  const dimensions = (result?.dimensions as string[]) ?? []

  return (
    <Box>
      <Typography variant="h6" gutterBottom>{t('distill_title')}</Typography>
      <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
        <TextField
          label={t('distill_genre_label')}
          value={genre}
          onChange={(e) => setGenre(e.target.value)}
          sx={{ minWidth: 200 }}
          size="small"
        />
        <Button variant="contained" onClick={doDistill} disabled={loading || !status?.canDistill}>
          {loading ? <CircularProgress size={20} /> : t('distill_btn_execute')}
        </Button>
      </Box>
      {status && (
        <Paper sx={{ p: 2, mb: 2 }}>
          <Typography variant="body2">
            {t('distill_status_available')}
            {(status.books as string[])?.length ?? 0}
            {t('distill_status_books_unit')}
            {(status.books as string[])?.join('、')}
          </Typography>
          <Typography variant="body2">
            {t('distill_status_existing')}
            {(status.distilledAssets as string[])?.length ?? 0}
            {t('distill_status_assets_unit')}
          </Typography>
          <Chip
            label={status.canDistill ? t('distill_chip_ready') : t('distill_chip_insufficient')}
            size="small"
            color={status.canDistill ? 'success' : 'warning'}
          />
        </Paper>
      )}
      {result && (
        result.error ? (
          <Alert severity="error" sx={{ mb: 2 }}>{String(result.error)}</Alert>
        ) : (
          <Paper sx={{ p: 2, mb: 2 }}>
            <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 1 }}>
              {t('distill_result_success')} — {books.length}{t('distill_result_books_prefix')}{written.length}{t('distill_result_outputs_suffix')}
            </Typography>
            <Typography variant="caption" color="text.secondary">{t('distill_section_books')}</Typography>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mb: 1.5 }}>
              {books.map((b) => <Chip key={b} label={b} size="small" variant="outlined" />)}
            </Box>
            <Typography variant="caption" color="text.secondary">{t('distill_section_dims')}</Typography>
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mb: 1.5 }}>
              {dimensions.map((d) => {
                const dimName = DIM_LABELS[d] ? (DIM_LABELS[d][locale] || DIM_LABELS[d]['zh-CN']) : d
                return <Chip key={d} label={dimName} size="small" color="primary" variant="outlined" />
              })}
            </Box>
            <Typography variant="caption" color="text.secondary">{t('distill_section_files')}</Typography>
            <Box component="ul" sx={{ m: 0, pl: 2.5 }}>
              {written.map((w) => (
                <Typography key={w} component="li" variant="body2" sx={{ fontFamily: 'monospace', fontSize: 12 }}>
                  {w}
                </Typography>
              ))}
            </Box>
            <Button size="small" onClick={() => setRawOpen((v) => !v)} sx={{ mt: 1 }}>
              {rawOpen ? t('distill_btn_hide_raw') : t('distill_btn_view_raw')}
            </Button>
            {rawOpen && (
              <Box component="pre" sx={{ fontSize: 12, m: 0, mt: 1, p: 1, bgcolor: 'action.hover', borderRadius: 1, overflow: 'auto' }}>
                {JSON.stringify(result, null, 2)}
              </Box>
            )}
          </Paper>
        )
      )}
    </Box>
  )
}

// ---------------------------------------------------------------------------
// 批量状态面板
// ---------------------------------------------------------------------------

const PASS_SHORT: Record<string, Record<Locale, string>> = {
  pass1_structure: { 'zh-CN': 'P1 结构', 'en-US': 'P1 Structure' },
  pass2_character: { 'zh-CN': 'P2 人物', 'en-US': 'P2 Character' },
  pass3_style: { 'zh-CN': 'P3 文风', 'en-US': 'P3 Style' },
  pass4_commercial: { 'zh-CN': 'P4 商业', 'en-US': 'P4 Commercial' },
  pass5_aggregate: { 'zh-CN': 'P5 聚合', 'en-US': 'P5 Aggregate' },
}

function BatchStatusPanel() {
  const { t, locale } = useI18n()
  const [status, setStatus] = useState<Record<string, unknown> | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    advancedApi.batchStatus()
      .then((data) => setStatus(data as Record<string, unknown>))
      .catch((e) => setError(friendlyError(e)))
  }, [])

  const books = (status?.books ?? []) as Record<string, unknown>[]

  if (error) return <Alert severity="error">{error}</Alert>

  return (
    <Box>
      <Typography variant="h6" gutterBottom>{t('batch_status_title')}</Typography>
      {books.length === 0 && (
        <Typography variant="body2" color="text.secondary">{t('batch_status_empty')}</Typography>
      )}
      {books.map((b) => (
        <Paper key={String(b.name)} sx={{ p: 1.5, mb: 1 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Typography variant="body2" sx={{ flex: 1, fontWeight: 600 }}>{String(b.name)}</Typography>
            <Chip label={`${String(b.passCount)}/5 pass`} size="small" color={(b.passCount as number) >= 5 ? 'success' : 'warning'} />
            {Boolean(b.hasAssets) && <Chip label={t('batch_chip_has_assets')} size="small" color="info" />}
          </Box>
          <Box sx={{ display: 'flex', gap: 0.5, mt: 0.5 }}>
            {Object.entries(b.passes as Record<string, boolean>).map(([k, v]) => {
              const passName = PASS_SHORT[k] ? (PASS_SHORT[k][locale] || PASS_SHORT[k]['zh-CN']) : k
              return (
                <Chip key={k} label={passName} size="small" color={v ? 'success' : 'default'} variant={v ? 'filled' : 'outlined'} />
              )
            })}
          </Box>
        </Paper>
      ))}
    </Box>
  )
}

// ---------------------------------------------------------------------------
// 资产编辑面板（M4）
// ---------------------------------------------------------------------------

function AssetEditPanel() {
  const { t, locale } = useI18n()
  const [assets, setAssets] = useState<{ id: string; name: string; kind: string }[]>([])
  const [selected, setSelected] = useState('')
  const [content, setContent] = useState('')
  const [savedContent, setSavedContent] = useState('')
  const [message, setMessage] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    assetApi.list({ limit: 100 })
      .then((j) => {
        const items = ((j as Record<string, unknown>).items ?? []) as { id: string; name: string; kind: string }[]
        setAssets(items)
      })
      .catch((e) => setError(friendlyError(e)))
  }, [])

  const selectedAsset = assets.find((a) => `${a.kind}:${a.id}` === selected)
  // 题材文风卡索引（prose_card_index）只是题材→卡片文件的寻址表，不是可编辑卡片：
  // 不进可编辑下拉，避免手改索引内容破坏寻址（查看请走「资产库」）。
  const editableAssets = assets.filter((a) => a.kind !== 'prose_card_index')
  const hasProseCardIndex = assets.some((a) => a.kind === 'prose_card_index')
  const dirty = content !== savedContent

  // 活体 JSON 校验：输入即反馈，保存前就知道合不合法
  const validation = (() => {
    if (!content.trim()) return { ok: false, msg: t('asset_edit_json_empty') }
    try {
      const v = JSON.parse(content)
      if (typeof v !== 'object' || v === null || Array.isArray(v)) {
        return { ok: false, msg: t('asset_edit_json_top_object') }
      }
      return { ok: true, msg: t('asset_edit_json_valid') }
    } catch (e) {
      return { ok: false, msg: `${t('asset_edit_json_error_prefix')}${e instanceof Error ? e.message : String(e)}` }
    }
  })()

  const loadAsset = async () => {
    if (!selected) return
    setLoading(true)
    try {
      const [kind, ...rest] = selected.split(':')
      const id = rest.join(':')
      const data = await assetApi.detail(kind, id)
      const text = JSON.stringify((data as Record<string, unknown>)?.content ?? data, null, 2)
      setContent(text)
      setSavedContent(text)
      setMessage('')
    } catch (e) {
      setMessage(friendlyError(e))
    } finally {
      setLoading(false)
    }
  }

  const saveAsset = async () => {
    if (!selected || !content || !validation.ok) return
    setLoading(true)
    setMessage('')
    try {
      const parsed = JSON.parse(content)
      const [kind, ...rest] = selected.split(':')
      const id = rest.join(':')
      await assetApi.update(kind, id, parsed)
      setSavedContent(content)
      setMessage(t('asset_edit_save_success'))
    } catch (e) {
      setMessage(friendlyError(e))
    } finally {
      setLoading(false)
    }
  }

  return (
    <Box>
      <Typography variant="h6" gutterBottom>{t('asset_edit_title')}</Typography>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      <Box sx={{ display: 'flex', gap: 2, mb: 1, flexWrap: 'wrap' }}>
        <TextField
          select
          label={t('asset_edit_select_label')}
          value={selected}
          onChange={(e) => setSelected(e.target.value)}
          sx={{ minWidth: 300, flex: 1 }}
          size="small"
        >
          {editableAssets.map((a) => {
            const labelKind = getLocalizedKind(a.kind, locale, t)
            const displayName = locale === 'en-US' ? `${a.name} (${labelKind})` : `${a.name}（${labelKind}）`
            return (
              <MenuItem key={a.id} value={`${a.kind}:${a.id}`}>
                {displayName}
              </MenuItem>
            )
          })}
        </TextField>
        <Button variant="outlined" onClick={loadAsset} disabled={!selected || loading}>
          {t('asset_edit_btn_load')}
        </Button>
        <Button variant="contained" onClick={saveAsset} disabled={!content || loading || !validation.ok || !dirty}>
          {loading ? <CircularProgress size={20} /> : t('asset_edit_btn_save')}
        </Button>
      </Box>
      {hasProseCardIndex && (
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 1 }}>
          {t('asset_edit_readonly_hint')}
        </Typography>
      )}
      {selectedAsset && (
        <Box sx={{ display: 'flex', gap: 1, mb: 1, alignItems: 'center', flexWrap: 'wrap' }}>
          <Chip label={getLocalizedKind(selectedAsset.kind, locale, t)} size="small" color="primary" variant="outlined" />
          <Chip
            label={validation.ok ? t('asset_edit_chip_json_valid') : t('asset_edit_chip_json_invalid')}
            size="small"
            color={validation.ok ? 'success' : 'error'}
            variant="outlined"
          />
          {dirty && <Chip label={t('asset_edit_chip_unsaved')} size="small" color="warning" />}
          {selectedAsset.name && <Typography variant="caption" color="text.secondary">{selectedAsset.name}</Typography>}
        </Box>
      )}
      {!validation.ok && content.trim() && (
        <Alert severity="warning" sx={{ mb: 1 }}>{validation.msg}</Alert>
      )}
      {message && (
        <Alert severity={message === t('asset_edit_save_success') ? 'success' : 'error'} sx={{ mb: 1 }}>
          {message}
        </Alert>
      )}
      <TextField
        label={t('asset_edit_content_label')}
        multiline
        rows={16}
        fullWidth
        value={content}
        onChange={(e) => setContent(e.target.value)}
        size="small"
        InputProps={{ style: { fontFamily: 'monospace', fontSize: 12 } }}
      />
    </Box>
  )
}
