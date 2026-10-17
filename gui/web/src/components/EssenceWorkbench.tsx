import { useState, useEffect } from 'react'
import Box from '@mui/material/Box'
import Paper from '@mui/material/Paper'
import Typography from '@mui/material/Typography'
import Button from '@mui/material/Button'
import IconButton from '@mui/material/IconButton'
import TextField from '@mui/material/TextField'
import MenuItem from '@mui/material/MenuItem'
import Chip from '@mui/material/Chip'
import Tabs from '@mui/material/Tabs'
import Tab from '@mui/material/Tab'
import Alert from '@mui/material/Alert'
import CircularProgress from '@mui/material/CircularProgress'
import Dialog from '@mui/material/Dialog'
import DialogTitle from '@mui/material/DialogTitle'
import DialogContent from '@mui/material/DialogContent'
import DialogActions from '@mui/material/DialogActions'
import Snackbar from '@mui/material/Snackbar'
import Card from '@mui/material/Card'
import CardContent from '@mui/material/CardContent'
import Divider from '@mui/material/Divider'
import Rating from '@mui/material/Rating'
import Grid from '@mui/material/Grid'
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome'
import BookmarkAddIcon from '@mui/icons-material/BookmarkAdd'
import MenuBookIcon from '@mui/icons-material/MenuBook'
import LayersIcon from '@mui/icons-material/Layers'
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline'
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline'
import AccountTreeIcon from '@mui/icons-material/AccountTree'
import AddIcon from '@mui/icons-material/Add'
import GavelIcon from '@mui/icons-material/Gavel'
import DownloadIcon from '@mui/icons-material/Download'
import { useI18n } from '../state/I18nContext'
import {
  essenceApi,
  writingApi,
  friendlyError,
  type EssenceBook,
  type EssenceAsset,
  type EssenceMacroAnalysisResult,
  type EssenceChain,
} from '../api/client'
import type { WritingProject } from '../types'

const PLATFORM_OPTIONS = [
  { value: 'general', label: '通用网文平台', shortLabel: '通用平台' },
  { value: 'qidian', label: '起点中文网 (大纵深世界观/严密升级/反圣母)', shortLabel: '起点中文网' },
  { value: 'fanqie', label: '番茄小说 (30秒黄金钩/每章留扣/防虐主)', shortLabel: '番茄小说' },
  { value: 'jinjiang', label: '晋江文学城 (人设细腻反差/推拉克制/微表情)', shortLabel: '晋江文学城' },
  { value: 'qimao', label: '七猫中文网 (开局强冲突受辱/底牌强反制)', shortLabel: '七猫中文网' },
  { value: 'zhihu', label: '知乎盐选 (第一人称高反转/三幕式快节奏)', shortLabel: '知乎盐选' },
  { value: 'royalroad', label: 'Royal Road (欧美Progression/LitRPG/高节奏升级)', shortLabel: 'Royal Road' },
  { value: 'amazon_kdp', label: 'Amazon KDP (全球商业电子书/多卷出版/精确定价)', shortLabel: 'Amazon KDP' },
  { value: 'webnovel', label: 'Webnovel (阅文出海/西方化修仙/系统穿越)', shortLabel: 'Webnovel' },
  { value: 'western_canon', label: '西方经典殿堂 (严肃奇幻/硬科幻史诗/世界观典范)', shortLabel: '西方经典' },
]

const GENRE_OPTIONS = [
  { value: 'general', label: '通用题材' },
  { value: 'xianxia', label: '仙侠修真' },
  { value: 'xuanhuan', label: '玄幻异界' },
  { value: 'xifang-qihuan', label: '西方奇幻/史诗' },
  { value: 'dushi', label: '都市职场/异能' },
  { value: 'kehuan', label: '科幻未来/星际' },
  { value: 'xuanyi', label: '悬疑怪谈/惊悚' },
  { value: 'yanqing', label: '现代/古代言情' },
  { value: 'lishi', label: '历史穿越/两宋大明' },
  { value: 'youxi', label: '网游竞技/电竞' },
  { value: 'wuxian', label: '诸天无限流' },
]

const PLATFORM_LABELS: Record<string, string> = {
  general: '通用平台',
  qidian: '起点中文网',
  fanqie: '番茄小说',
  jinjiang: '晋江文学城',
  qimao: '七猫中文网',
  zhihu: '知乎盐选',
  royalroad: 'Royal Road',
  amazon_kdp: 'Amazon KDP',
  webnovel: 'Webnovel',
  western_canon: '西方经典',
}

const GENRE_LABELS: Record<string, string> = {
  general: '通用题材',
  xianxia: '仙侠修真',
  xuanhuan: '玄幻异界',
  'xifang-qihuan': '西方奇幻',
  dushi: '都市职场',
  kehuan: '科幻未来',
  xuanyi: '悬疑怪谈',
  yanqing: '现代/古言',
  lishi: '历史穿越',
  youxi: '网游竞技',
  wuxian: '诸天无限',
}

const CATEGORY_MAP: Record<string, { key: string; defaultLabel: string; color: 'primary' | 'secondary' | 'success' | 'warning' | 'info' | 'default' | 'error' }> = {
  outline: { key: 'essence_cat_outline', defaultLabel: '骨架大纲', color: 'primary' },
  hook: { key: 'essence_cat_hook', defaultLabel: '开篇钩子', color: 'error' },
  opening: { key: 'essence_cat_hook', defaultLabel: '开篇钩子', color: 'error' },
  character: { key: 'essence_cat_character', defaultLabel: '人设反差', color: 'secondary' },
  persona: { key: 'essence_cat_character', defaultLabel: '人设反差', color: 'secondary' },
  trope: { key: 'essence_cat_trope', defaultLabel: '爆款桥段', color: 'success' },
  style: { key: 'essence_cat_style', defaultLabel: '反AI口语', color: 'warning' },
}

function getCategoryInfo(category: string, t: (k: string, fb?: string) => string) {
  const item = CATEGORY_MAP[category]
  if (!item) return { label: category, color: 'default' as const }
  return { label: t(item.key, item.defaultLabel), color: item.color }
}

export default function EssenceWorkbench() {
  const { t } = useI18n()
  const [tab, setTab] = useState(0)
  const [globalToast, setGlobalToast] = useState('')

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <Paper sx={{ p: 2 }}>
        <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 2 }}>
          <Tabs value={tab} onChange={(_, v) => setTab(v)} variant="scrollable" scrollButtons="auto">
            <Tab icon={<AutoAwesomeIcon fontSize="small" />} iconPosition="start" label={t('essence_tab_macro')} />
            <Tab icon={<LayersIcon fontSize="small" />} iconPosition="start" label={t('essence_tab_assets')} />
            <Tab icon={<AccountTreeIcon fontSize="small" />} iconPosition="start" label={t('essence_tab_chains')} />
            <Tab icon={<MenuBookIcon fontSize="small" />} iconPosition="start" label={t('essence_tab_books')} />
            <Tab icon={<GavelIcon fontSize="small" />} iconPosition="start" label={t('essence_tab_constitution')} />
          </Tabs>
        </Box>

        {tab === 0 && <MacroExtractSection onAssetSaved={() => setTab(1)} />}
        {tab === 1 && <EssenceAssetsSection />}
        {tab === 2 && <EssenceChainsSection />}
        {tab === 3 && <EssenceBooksSection onToast={setGlobalToast} />}
        {tab === 4 && <ConstitutionCheckSection />}
      </Paper>

      <Snackbar
        open={Boolean(globalToast)}
        autoHideDuration={3000}
        onClose={() => setGlobalToast('')}
        message={globalToast}
      />
    </Box>
  )
}

// ---------------------------------------------------------------------------
// 1. 离线精读与宏观解构提炼
// ---------------------------------------------------------------------------

function MacroExtractSection({ onAssetSaved }: { onAssetSaved: () => void }) {
  const { t } = useI18n()
  const [title, setTitle] = useState('')
  const [platform, setPlatform] = useState('fanqie')
  const [genre, setGenre] = useState('xianxia')
  const [text, setText] = useState('')
  const [analyzing, setAnalyzing] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState<EssenceMacroAnalysisResult | null>(null)
  const [toast, setToast] = useState('')

  const handleAnalyze = async () => {
    if (!title.trim()) {
      setError('请输入书籍名称')
      return
    }
    if (!text.trim()) {
      setError('请输入待精读分析的正文内容（建议输入前三章或多章连粘）')
      return
    }
    setError('')
    setAnalyzing(true)
    try {
      const res = await essenceApi.analyzeMacro({
        title: title.trim(),
        text: text.trim(),
        platform,
        genre,
      })
      setResult(res)
      setToast(t('essence_macro_toast_done'))
    } catch (e) {
      setError(friendlyError(e))
    } finally {
      setAnalyzing(false)
    }
  }

  const handleSaveSuggestedAsset = async (item: { category: string; title: string; summary: string; content: string }) => {
    if (!result) return
    try {
      await essenceApi.createAsset({
        book_id: result.bookId,
        category: item.category,
        title: item.title,
        content: item.content,
        summary: item.summary,
        genre: result.genre,
        platform: result.platform,
        rating: 5,
        tags: `${result.title},${item.category}`,
      })
      setToast(`${t('essence_macro_toast_saved')}${item.title}`)
      onAssetSaved()
    } catch (e) {
      setError(friendlyError(e))
    }
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2.5 }}>
      <Typography variant="body2" color="text.secondary">
        {t('essence_macro_desc')}
      </Typography>

      {error && <Alert severity="error" onClose={() => setError('')}>{error}</Alert>}

      <Paper variant="outlined" sx={{ p: 2, display: 'flex', flexDirection: 'column', gap: 2 }}>
        <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
          <TextField
            label={t('essence_macro_title_label')}
            size="small"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder={t('essence_macro_title_placeholder')}
            sx={{ flex: 1, minWidth: 220 }}
          />
          <TextField
            select
            label={t('essence_macro_platform_label')}
            size="small"
            value={platform}
            onChange={(e) => setPlatform(e.target.value)}
            sx={{ width: 220 }}
          >
            {PLATFORM_OPTIONS.map((opt) => (
              <MenuItem key={opt.value} value={opt.value}>{opt.label}</MenuItem>
            ))}
          </TextField>
          <TextField
            select
            label={t('essence_macro_genre_label')}
            size="small"
            value={genre}
            onChange={(e) => setGenre(e.target.value)}
            sx={{ width: 180 }}
          >
            {GENRE_OPTIONS.map((opt) => (
              <MenuItem key={opt.value} value={opt.value}>{opt.label}</MenuItem>
            ))}
          </TextField>
        </Box>

        <TextField
          label={t('essence_macro_text_label')}
          multiline
          rows={6}
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={t('essence_macro_text_placeholder')}
          fullWidth
        />

        <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1 }}>
          <Button
            variant="contained"
            color="primary"
            startIcon={analyzing ? <CircularProgress size={18} color="inherit" /> : <AutoAwesomeIcon />}
            onClick={handleAnalyze}
            disabled={analyzing}
          >
            {analyzing ? t('essence_macro_btn_analyzing') : t('essence_macro_btn_start')}
          </Button>
        </Box>
      </Paper>

      {result && (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <Divider>
            <Chip label={t('essence_macro_report_chip')} color="primary" variant="outlined" />
          </Divider>

          {/* 宏观指标卡 */}
          <Grid container spacing={2}>
            <Grid item xs={12} sm={6} md={2}>
              <Paper variant="outlined" sx={{ p: 1.5, textAlign: 'center' }}>
                <Typography variant="caption" color="text.secondary">{t('essence_macro_metric_chapters')}</Typography>
                <Typography variant="h6">{result.totalChapters ?? 0} 章</Typography>
              </Paper>
            </Grid>
            <Grid item xs={12} sm={6} md={2}>
              <Paper variant="outlined" sx={{ p: 1.5, textAlign: 'center' }}>
                <Typography variant="caption" color="text.secondary">{t('essence_macro_metric_words')}</Typography>
                <Typography variant="h6">{(result.totalChars ?? 0).toLocaleString()} 字</Typography>
              </Paper>
            </Grid>
            <Grid item xs={12} sm={6} md={2}>
              <Paper variant="outlined" sx={{ p: 1.5, textAlign: 'center' }}>
                <Typography variant="caption" color="text.secondary">{t('essence_macro_metric_avg_words')}</Typography>
                <Typography variant="h6">{result.avgChapterLen ?? 0} 字</Typography>
              </Paper>
            </Grid>
            <Grid item xs={12} sm={6} md={2}>
              <Paper variant="outlined" sx={{ p: 1.5, textAlign: 'center' }}>
                <Typography variant="caption" color="text.secondary">{t('essence_macro_metric_dialogue_ratio')}</Typography>
                <Typography variant="h6" color={(result.dialogueRatio ?? 0) >= 0.25 && (result.dialogueRatio ?? 0) <= 0.45 ? 'success.main' : 'warning.main'}>
                  {((result.dialogueRatio ?? 0) * 100).toFixed(1)}%
                </Typography>
              </Paper>
            </Grid>
            <Grid item xs={12} sm={6} md={2}>
              <Paper variant="outlined" sx={{ p: 1.5, textAlign: 'center' }}>
                <Typography variant="caption" color="text.secondary">{t('essence_macro_metric_climax_interval')}</Typography>
                <Typography variant="h6">{result.rhythmClimaxInterval ?? 5} 章/次</Typography>
              </Paper>
            </Grid>
            <Grid item xs={12} sm={6} md={2}>
              <Paper variant="outlined" sx={{ p: 1.5, textAlign: 'center' }}>
                <Typography variant="caption" color="text.secondary">{t('essence_macro_metric_ai_slop')}</Typography>
                <Typography variant="h6" color={(result.aiSlopScore ?? 0) < 3.0 ? 'success.main' : 'error.main'}>
                  {result.aiSlopScore ?? 1.5} 分
                </Typography>
              </Paper>
            </Grid>
          </Grid>

          {/* 黄金三章开篇解构 */}
          {result.openingThreeChapters && result.openingThreeChapters.length > 0 && (
            <Paper variant="outlined" sx={{ p: 2 }}>
              <Typography variant="subtitle2" sx={{ mb: 1.5, fontWeight: 'bold' }}>
                {t('essence_macro_h3_opening')}
              </Typography>
              <Grid container spacing={2}>
                {result.openingThreeChapters.map((ch) => (
                  <Grid item xs={12} md={4} key={ch.chapterIndex}>
                    <Card variant="outlined" sx={{ height: '100%', bgcolor: 'background.default' }}>
                      <CardContent sx={{ p: 1.5 }}>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                          <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                            第 {ch.chapterIndex} 章: {ch.title}
                          </Typography>
                          <Chip size="small" label={ch.hookType} color="primary" variant="outlined" />
                        </Box>
                        <Typography variant="caption" color="text.secondary" display="block">
                          字数: {ch.charCount} 字 | 对白: {(ch.dialogueRatio * 100).toFixed(1)}% | 期待感闭环: {ch.hasPayoffOrAnticipation ? '✅ 是' : '❌ 否'}
                        </Typography>
                        <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block', fontStyle: 'italic' }}>
                          "{ch.excerpt}"
                        </Typography>
                      </CardContent>
                    </Card>
                  </Grid>
                ))}
              </Grid>
            </Paper>
          )}

          {/* 高频反 AI 口语 */}
          {result.highFrequencySpeechPatterns && result.highFrequencySpeechPatterns.length > 0 && (
            <Paper variant="outlined" sx={{ p: 2 }}>
              <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 'bold' }}>
                {t('essence_macro_h3_speech')}
              </Typography>
              <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                {result.highFrequencySpeechPatterns.map((pat, idx) => (
                  <Chip
                    key={idx}
                    label={`${pat.phrase} (${pat.count}次)`}
                    size="small"
                    variant="outlined"
                    color="warning"
                  />
                ))}
              </Box>
            </Paper>
          )}

          {/* 自动提炼的五维资产建议 */}
          {result.suggestedAssets && result.suggestedAssets.length > 0 && (
            <Paper variant="outlined" sx={{ p: 2 }}>
              <Typography variant="subtitle2" sx={{ mb: 1.5, fontWeight: 'bold' }}>
                {t('essence_macro_h3_suggested')}
              </Typography>
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
                {result.suggestedAssets.map((asset, idx) => {
                  const catInfo = getCategoryInfo(asset.category, t)
                  return (
                    <Card key={idx} variant="outlined" sx={{ p: 1.5 }}>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          <Chip
                            size="small"
                            label={catInfo.label}
                            color={catInfo.color}
                          />
                          <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                            {asset.title}
                          </Typography>
                        </Box>
                        <Button
                          size="small"
                          variant="outlined"
                          startIcon={<BookmarkAddIcon />}
                          onClick={() => handleSaveSuggestedAsset(asset)}
                        >
                          {t('essence_macro_btn_save_asset')}
                        </Button>
                      </Box>
                      <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                        {asset.summary}
                      </Typography>
                    </Card>
                  )
                })}
              </Box>
            </Paper>
          )}
        </Box>
      )}

      <Snackbar
        open={Boolean(toast)}
        autoHideDuration={3000}
        onClose={() => setToast('')}
        message={toast}
      />
    </Box>
  )
}

// ---------------------------------------------------------------------------
// 2. 五维精华资产库
// ---------------------------------------------------------------------------

function EssenceAssetsSection() {
  const { t } = useI18n()
  const [assets, setAssets] = useState<EssenceAsset[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [selectedCategory, setSelectedCategory] = useState<string>('all')
  const [selectedPlatform, setSelectedPlatform] = useState<string>('all')
  const [searchKw, setSearchKw] = useState('')
  const [adoptDialog, setAdoptDialog] = useState<EssenceAsset | null>(null)
  const [projects, setProjects] = useState<WritingProject[]>([])
  const [adoptProject, setAdoptProject] = useState('')
  const [adoptTarget, setAdoptTarget] = useState('outline')
  const [toast, setToast] = useState('')

  const loadAssets = async () => {
    setLoading(true)
    setError('')
    try {
      const res = await essenceApi.listAssets({
        category: selectedCategory === 'all' ? undefined : selectedCategory,
        platform: selectedPlatform === 'all' ? undefined : selectedPlatform,
      })
      setAssets(res.assets || [])
    } catch (e) {
      setError(friendlyError(e))
    } finally {
      setLoading(false)
    }
  }

  const loadProjects = async () => {
    try {
      const ps = await writingApi.projects()
      setProjects(ps || [])
      if (ps && ps.length > 0 && !adoptProject) {
        setAdoptProject(ps[0].name)
      }
    } catch {
      // 容错处理
    }
  }

  useEffect(() => {
    loadAssets()
    loadProjects()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedCategory, selectedPlatform])

  const handleDelete = async (id: number) => {
    if (!window.confirm('确定删除此条资产吗？')) return
    try {
      await essenceApi.deleteAsset(id)
      setToast('资产已删除')
      loadAssets()
    } catch (e) {
      setError(friendlyError(e))
    }
  }

  const handleAdopt = async () => {
    if (!adoptDialog || !adoptProject) return
    try {
      await essenceApi.adoptAsset({
        asset_id: adoptDialog.id,
        project: adoptProject,
        target_kind: adoptTarget,
      })
      setToast(`已成功反哺到项目 [${adoptProject}]！`)
      setAdoptDialog(null)
    } catch (e) {
      setError(friendlyError(e))
    }
  }

  const filtered = assets.filter((a) => {
    if (!searchKw) return true
    const kw = searchKw.toLowerCase()
    return (
      (a.title ?? '').toLowerCase().includes(kw) ||
      (a.tags ?? '').toLowerCase().includes(kw) ||
      (a.summary ?? '').toLowerCase().includes(kw) ||
      (a.content ?? '').toLowerCase().includes(kw)
    )
  })

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      {error && <Alert severity="error" onClose={() => setError('')}>{error}</Alert>}

      {/* 筛选栏 */}
      <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', alignItems: 'center' }}>
        <TextField
          select
          label={t('essence_assets_category_filter')}
          size="small"
          value={selectedCategory}
          onChange={(e) => setSelectedCategory(e.target.value)}
          sx={{ width: 160 }}
        >
          <MenuItem value="all">{t('essence_cat_all')}</MenuItem>
          <MenuItem value="outline">{t('essence_cat_outline')}</MenuItem>
          <MenuItem value="hook">{t('essence_cat_hook')}</MenuItem>
          <MenuItem value="character">{t('essence_cat_character')}</MenuItem>
          <MenuItem value="trope">{t('essence_cat_trope')}</MenuItem>
          <MenuItem value="style">{t('essence_cat_style')}</MenuItem>
        </TextField>

        <TextField
          select
          label={t('essence_assets_platform_filter')}
          size="small"
          value={selectedPlatform}
          onChange={(e) => setSelectedPlatform(e.target.value)}
          sx={{ width: 160 }}
        >
          <MenuItem value="all">{t('essence_assets_all_platforms')}</MenuItem>
          {PLATFORM_OPTIONS.map((p) => (
            <MenuItem key={p.value} value={p.value}>{p.shortLabel || p.label.split(' ')[0]}</MenuItem>
          ))}
        </TextField>

        <TextField
          label={t('essence_assets_search_placeholder')}
          size="small"
          value={searchKw}
          onChange={(e) => setSearchKw(e.target.value)}
          sx={{ flex: 1, minWidth: 200 }}
        />

        <Button variant="outlined" onClick={loadAssets}>
          {t('essence_assets_btn_refresh')}
        </Button>
      </Box>

      {/* 资产卡片瀑布流 */}
      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
          <CircularProgress />
        </Box>
      ) : filtered.length === 0 ? (
        <Paper variant="outlined" sx={{ p: 4, textAlign: 'center', color: 'text.secondary' }}>
          {t('essence_assets_empty')}
        </Paper>
      ) : (
        <Grid container spacing={2}>
          {filtered.map((item) => {
            const catInfo = getCategoryInfo(item.category, t)
            return (
              <Grid item xs={12} md={6} key={item.id}>
                <Card variant="outlined" sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
                  <CardContent sx={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 1 }}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
                        <Chip
                          size="small"
                          label={catInfo.label}
                          color={catInfo.color}
                        />
                        <Typography variant="subtitle2" sx={{ fontWeight: 'bold' }}>
                          {item.title}
                        </Typography>
                      </Box>
                      <Rating value={item.rating} size="small" readOnly />
                    </Box>

                    <Typography variant="body2" color="text.secondary">
                      {item.summary || item.content.slice(0, 100) + '...'}
                    </Typography>

                    <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap', my: 0.5 }}>
                      {(item.tags || '').split(',').filter(Boolean).map((tag, idx) => (
                        <Chip key={idx} label={tag} size="small" variant="outlined" />
                      ))}
                      <Chip label={`${t('essence_assets_platform_prefix')}${PLATFORM_LABELS[item.platform] || item.platform}`} size="small" variant="outlined" />
                      <Chip label={`${t('essence_assets_genre_prefix')}${GENRE_LABELS[item.genre] || item.genre}`} size="small" variant="outlined" />
                    </Box>

                    {item.userNote && (
                      <Box sx={{ bgcolor: 'action.hover', p: 1, borderRadius: 1 }}>
                        <Typography variant="caption" color="text.secondary">
                          {t('essence_assets_note_prefix')}{item.userNote}
                        </Typography>
                      </Box>
                    )}
                  </CardContent>

                  <Divider />

                  <Box sx={{ p: 1, px: 2, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Button
                      size="small"
                      color="error"
                      startIcon={<DeleteOutlineIcon />}
                      onClick={() => handleDelete(item.id)}
                    >
                      {t('essence_assets_btn_delete')}
                    </Button>
                    <Button
                      size="small"
                      variant="contained"
                      color="success"
                      startIcon={<CheckCircleOutlineIcon />}
                      onClick={() => {
                        setAdoptDialog(item)
                        if (item.category === 'outline') setAdoptTarget('outline')
                        else if (item.category === 'character' || item.category === 'persona') setAdoptTarget('character')
                        else setAdoptTarget('note')
                      }}
                    >
                      {t('essence_assets_btn_adopt')}
                    </Button>
                  </Box>
                </Card>
              </Grid>
            )
          })}
        </Grid>
      )}

      {/* 反哺对话框 */}
      <Dialog open={Boolean(adoptDialog)} onClose={() => setAdoptDialog(null)} maxWidth="xs" fullWidth>
        <DialogTitle>{t('essence_assets_adopt_title')}</DialogTitle>
        <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
          <Typography variant="body2" color="text.secondary">
            将资产「{adoptDialog?.title}」直接注入到你当前的创作项目中，作为大纲节点、人物卡或灵感便签。
          </Typography>
          <TextField
            select
            label={t('essence_assets_adopt_target_project')}
            size="small"
            value={adoptProject}
            onChange={(e) => setAdoptProject(e.target.value)}
            fullWidth
          >
            {projects.map((p) => (
              <MenuItem key={p.name} value={p.name}>{p.name}</MenuItem>
            ))}
          </TextField>
          <TextField
            select
            label={t('essence_assets_adopt_target_kind')}
            size="small"
            value={adoptTarget}
            onChange={(e) => setAdoptTarget(e.target.value)}
            fullWidth
          >
            <MenuItem value="outline">{t('essence_assets_adopt_kind_outline')}</MenuItem>
            <MenuItem value="character">{t('essence_assets_adopt_kind_character')}</MenuItem>
            <MenuItem value="note">{t('essence_assets_adopt_kind_note')}</MenuItem>
          </TextField>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setAdoptDialog(null)}>{t('essence_assets_adopt_btn_cancel')}</Button>
          <Button variant="contained" color="primary" onClick={handleAdopt}>{t('essence_assets_adopt_btn_confirm')}</Button>
        </DialogActions>
      </Dialog>

      <Snackbar
        open={Boolean(toast)}
        autoHideDuration={3000}
        onClose={() => setToast('')}
        message={toast}
      />
    </Box>
  )
}

// ---------------------------------------------------------------------------
// 3. 已精读书籍档案
// ---------------------------------------------------------------------------

function EssenceBooksSection({ onToast }: { onToast?: (msg: string) => void }) {
  const { t } = useI18n()
  const [books, setBooks] = useState<EssenceBook[]>([])
  const [projects, setProjects] = useState<string[]>([])
  const [adoptBookDialog, setAdoptBookDialog] = useState<EssenceBook | null>(null)
  const [adoptProject, setAdoptProject] = useState('default')
  const [adopting, setAdopting] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [toast, setToast] = useState('')

  const loadBooks = async () => {
    setLoading(true)
    setError('')
    try {
      const [res, projs] = await Promise.all([
        essenceApi.listBooks(),
        writingApi.projects().catch(() => []),
      ])
      setBooks(res.books || [])
      const validProjects = (projs || []).filter((p: WritingProject) => !p.readOnly && p.name !== 'default' && p.id !== 'default')
      const projNames = validProjects.map((p: WritingProject) => p.name)
      setProjects(projNames)
      if (projNames.length > 0) {
        setAdoptProject(projNames[0])
      } else {
        setAdoptProject('')
      }
    } catch (e) {
      setError(friendlyError(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadBooks()
  }, [])

  const downloadMarkdownFile = (filename: string, content: string) => {
    const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.click()
    URL.revokeObjectURL(url)
  }

  const handleExportOutline = async (book: EssenceBook) => {
    try {
      const res = await essenceApi.exportOutline(book.bookId)
      downloadMarkdownFile(`《${book.title}》全书五维大纲.md`, res.markdown)
      const msg = `已导出《${book.title}》全书五维大纲`
      setToast(msg)
      onToast?.(msg)
    } catch (e) {
      setError(friendlyError(e))
    }
  }

  const handleExportBeats = async (book: EssenceBook) => {
    try {
      const res = await essenceApi.exportBeats(book.bookId)
      downloadMarkdownFile(`《${book.title}》分章节拍轻提纲.md`, res.markdown)
      const msg = `已导出《${book.title}》分章节拍轻提纲`
      setToast(msg)
      onToast?.(msg)
    } catch (e) {
      setError(friendlyError(e))
    }
  }

  const handleExecuteAdoptBook = async () => {
    if (!adoptBookDialog || !adoptProject) return
    setAdopting(true)
    try {
      const res = await essenceApi.adoptBook(adoptBookDialog.bookId, adoptProject)
      const msg = `已将《${adoptBookDialog.title}》的全套五维资产 (${res.totalAdopted}项) 一键反哺至项目 [${adoptProject}]！`
      setToast(msg)
      onToast?.(msg)
      setAdoptBookDialog(null)
    } catch (e) {
      setError(friendlyError(e))
    } finally {
      setAdopting(false)
    }
  }

  const handleDelete = async (bookId: string) => {
    if (!window.confirm(`确定删除《${bookId}》的书籍精读档案吗？关联的提炼资产也会被级联删除。`)) return
    try {
      await essenceApi.deleteBook(bookId)
      setToast('书籍档案已级联删除')
      loadBooks()
    } catch (e) {
      setError(friendlyError(e))
    }
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      {error && <Alert severity="error" onClose={() => setError('')}>{error}</Alert>}

      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Typography variant="body2" color="text.secondary">
          {t('essence_books_desc')}
        </Typography>
        <Button variant="outlined" size="small" onClick={loadBooks}>
          {t('essence_books_btn_refresh')}
        </Button>
      </Box>

      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
          <CircularProgress />
        </Box>
      ) : books.length === 0 ? (
        <Paper variant="outlined" sx={{ p: 4, textAlign: 'center', color: 'text.secondary' }}>
          {t('essence_books_empty')}
        </Paper>
      ) : (
        <Grid container spacing={2}>
          {books.map((b) => (
            <Grid item xs={12} sm={6} md={4} key={b.bookId}>
              <Card variant="outlined" sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
                <CardContent sx={{ flex: 1 }}>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <Typography variant="subtitle1" sx={{ fontWeight: 'bold' }}>
                      {b.title}
                    </Typography>
                    <IconButton size="small" color="error" onClick={() => handleDelete(b.bookId)}>
                      <DeleteOutlineIcon fontSize="small" />
                    </IconButton>
                  </Box>

                  <Box sx={{ display: 'flex', gap: 0.5, my: 1 }}>
                    <Chip size="small" label={GENRE_LABELS[b.genre] || b.genre} />
                    <Chip size="small" label={PLATFORM_LABELS[b.platform] || b.platform} variant="outlined" />
                  </Box>

                  <Typography variant="body2" color="text.secondary">
                    {b.totalChapters ?? 0} 章 | {(b.totalChars ?? 0).toLocaleString()} 字
                  </Typography>

                  <Box sx={{ mt: 1, display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                    <Typography variant="caption" color="text.secondary">
                      {t('essence_books_dialogue_ratio')}{((b.dialogueRatio ?? 0) * 100).toFixed(1)}%
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {t('essence_books_climax_interval')}{b.rhythmClimaxInterval ?? 0} 章/次
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      {t('essence_books_ai_slop')}{b.aiSlopScore ?? 0} / 10
                    </Typography>
                  </Box>

                  <Divider sx={{ my: 1.5 }} />

                  <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                    <Button
                      size="small"
                      variant="outlined"
                      startIcon={<DownloadIcon fontSize="small" />}
                      onClick={() => handleExportOutline(b)}
                    >
                      {t('essence_books_btn_export_outline')}
                    </Button>
                    <Button
                      size="small"
                      variant="outlined"
                      startIcon={<DownloadIcon fontSize="small" />}
                      onClick={() => handleExportBeats(b)}
                    >
                      {t('essence_books_btn_export_beats')}
                    </Button>
                    <Button
                      size="small"
                      variant="outlined"
                      color="secondary"
                      startIcon={<BookmarkAddIcon fontSize="small" />}
                      onClick={() => setAdoptBookDialog(b)}
                    >
                      {t('essence_books_btn_adopt_book')}
                    </Button>
                  </Box>
                </CardContent>
              </Card>
            </Grid>
          ))}
        </Grid>
      )}

      {/* 整本反哺对话框 */}
      <Dialog open={Boolean(adoptBookDialog)} onClose={() => setAdoptBookDialog(null)} maxWidth="xs" fullWidth>
        <DialogTitle>{t('essence_books_adopt_title')}</DialogTitle>
        <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
          <Typography variant="body2" color="text.secondary">
            将《{adoptBookDialog?.title}》沉淀的全部五维资产（核心大纲、原型人设、爆款桥段、反AI文风）一键注入到目标项目中。
          </Typography>
          {projects.length === 0 ? (
            <Alert severity="warning">
              当前暂无可用的自定义创作项目（默认 CLI 项目为只读）。请先前往「写作工坊」新建作品后，再进行整本反哺注入。
            </Alert>
          ) : (
            <TextField
              select
              label={t('essence_books_adopt_target')}
              size="small"
              value={adoptProject}
              onChange={(e) => setAdoptProject(e.target.value)}
              fullWidth
            >
              {projects.map((p) => (
                <MenuItem key={p} value={p}>{p}</MenuItem>
              ))}
            </TextField>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setAdoptBookDialog(null)}>{t('essence_assets_adopt_btn_cancel')}</Button>
          <Button
            variant="contained"
            color="secondary"
            disabled={adopting || projects.length === 0 || !adoptProject}
            onClick={handleExecuteAdoptBook}
          >
            {adopting ? t('essence_books_adopt_btn_adopting') : t('essence_books_adopt_btn_confirm')}
          </Button>
        </DialogActions>
      </Dialog>

      <Snackbar
        open={Boolean(toast)}
        autoHideDuration={3000}
        onClose={() => setToast('')}
        message={toast}
      />
    </Box>
  )
}

// ---------------------------------------------------------------------------
// 4. 伏笔暗线图谱 (Foreshadowing Matrix)
// ---------------------------------------------------------------------------

const CHAIN_STATUS_MAP: Record<string, { key: string; defaultLabel: string; color: 'default' | 'primary' | 'warning' | 'success' }> = {
  planted: { key: 'essence_chains_status_planted', defaultLabel: '🌱 已埋下', color: 'default' },
  developing: { key: 'essence_chains_status_developing', defaultLabel: '⏳ 推进发酵', color: 'warning' },
  revealed: { key: 'essence_chains_status_revealed', defaultLabel: '🔍 已显露', color: 'primary' },
  recycled: { key: 'essence_chains_status_recycled', defaultLabel: '✅ 闭环回收', color: 'success' },
}

function EssenceChainsSection() {
  const { t } = useI18n()
  const [chains, setChains] = useState<EssenceChain[]>([])
  const [books, setBooks] = useState<EssenceBook[]>([])
  const [selectedBook, setSelectedBook] = useState<string>('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [toast, setToast] = useState('')

  // 新建暗线对话框
  const [openCreate, setOpenCreate] = useState(false)
  const [formBookId, setFormBookId] = useState('')
  const [formTitle, setFormTitle] = useState('')
  const [formCategory, setFormCategory] = useState('身份谜题')
  const [formPlant, setFormPlant] = useState(1)
  const [formReveal, setFormReveal] = useState(20)
  const [formClimax, setFormClimax] = useState(50)
  const [formDesc, setFormDesc] = useState('')
  const [formStatus, setFormStatus] = useState<'planted' | 'developing' | 'revealed' | 'recycled'>('planted')
  const [saving, setSaving] = useState(false)

  const loadData = async () => {
    setLoading(true)
    setError('')
    try {
      const [bookRes, chainRes] = await Promise.all([
        essenceApi.listBooks(),
        essenceApi.listChains(selectedBook || undefined),
      ])
      setBooks(bookRes.books || [])
      setChains(chainRes.chains || [])
      if (!formBookId && bookRes.books && bookRes.books.length > 0) {
        setFormBookId(bookRes.books[0].bookId)
      }
    } catch (e) {
      setError(friendlyError(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedBook])

  const handleCreate = async () => {
    if (!formTitle.trim()) {
      setError('请输入暗线伏笔名称')
      return
    }
    const bookId = formBookId || (books.length > 0 ? books[0].bookId : 'general')
    setSaving(true)
    try {
      await essenceApi.createChain({
        book_id: bookId,
        title: formTitle.trim(),
        category: formCategory,
        plant_chapter: formPlant,
        reveal_chapter: formReveal,
        climax_chapter: formClimax,
        description: formDesc.trim(),
        status: formStatus,
      })
      setToast('暗线伏笔已成功创建并录入图谱')
      setOpenCreate(false)
      setFormTitle('')
      setFormDesc('')
      loadData()
    } catch (e) {
      setError(friendlyError(e))
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (chainId: number) => {
    if (!window.confirm('确定删除此条伏笔暗线吗？')) return
    try {
      await essenceApi.deleteChain(chainId)
      setToast('已删除暗线')
      loadData()
    } catch (e) {
      setError(friendlyError(e))
    }
  }

  const recycledCount = chains.filter((c) => c.status === 'recycled').length
  const avgSpan =
    chains.length > 0
      ? Math.round(chains.reduce((acc, c) => acc + Math.max(0, c.climaxChapter - c.plantChapter), 0) / chains.length)
      : 0

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      {error && <Alert severity="error" onClose={() => setError('')}>{error}</Alert>}

      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 1 }}>
        <Box sx={{ display: 'flex', gap: 1.5, alignItems: 'center' }}>
          <TextField
            select
            size="small"
            label={t('essence_chains_filter_book')}
            value={selectedBook}
            onChange={(e) => setSelectedBook(e.target.value)}
            sx={{ minWidth: 200 }}
          >
            <MenuItem value="">{t('essence_chains_all_books')}</MenuItem>
            {books.map((b) => (
              <MenuItem key={b.bookId} value={b.bookId}>
                {b.title}
              </MenuItem>
            ))}
          </TextField>
          <Typography variant="body2" color="text.secondary">
            共 {chains.length} 条暗线 | 回收闭环: {recycledCount} 条 | 平均呼应跨度: {avgSpan} 章
          </Typography>
        </Box>

        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button variant="outlined" size="small" onClick={loadData}>
            {t('essence_chains_btn_refresh')}
          </Button>
          <Button
            variant="contained"
            size="small"
            startIcon={<AddIcon />}
            onClick={() => setOpenCreate(true)}
          >
            {t('essence_chains_btn_create')}
          </Button>
        </Box>
      </Box>

      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
          <CircularProgress />
        </Box>
      ) : chains.length === 0 ? (
        <Paper variant="outlined" sx={{ p: 4, textAlign: 'center', color: 'text.secondary' }}>
          {t('essence_chains_empty')}
        </Paper>
      ) : (
        <Grid container spacing={2}>
          {chains.map((c) => {
            const statusConfig = CHAIN_STATUS_MAP[c.status] || CHAIN_STATUS_MAP.planted
            const totalSpan = Math.max(1, c.climaxChapter ?? 1)
            const plantPct = Math.min(95, Math.max(2, ((c.plantChapter ?? 1) / totalSpan) * 100))
            const revealPct = Math.min(98, Math.max(plantPct + 2, ((c.revealChapter ?? 1) / totalSpan) * 100))
            return (
              <Grid item xs={12} md={6} key={c.id}>
                <Card variant="outlined" sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
                  <CardContent sx={{ flex: 1 }}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <Typography variant="subtitle1" sx={{ fontWeight: 'bold' }}>
                          {c.title}
                        </Typography>
                        <Chip size="small" label={c.category} variant="outlined" />
                        <Chip
                          size="small"
                          label={t(statusConfig.key, statusConfig.defaultLabel)}
                          color={statusConfig.color}
                        />
                      </Box>
                      <IconButton size="small" color="error" onClick={() => handleDelete(c.id)}>
                        <DeleteOutlineIcon fontSize="small" />
                      </IconButton>
                    </Box>

                    {/* 可视化伏笔跨越节点 */}
                    <Box sx={{ my: 2, p: 1.5, bgcolor: 'action.hover', borderRadius: 1.5 }}>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
                        <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                          {t('essence_chains_plant_ch')}<b>第 {c.plantChapter} 章</b>
                        </Typography>
                        <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                          {t('essence_chains_reveal_ch')}<b>第 {c.revealChapter} 章</b>
                        </Typography>
                        <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                          {t('essence_chains_climax_ch')}<b>第 {c.climaxChapter} 章</b>
                        </Typography>
                      </Box>

                      {/* 进度轨道 */}
                      <Box sx={{ position: 'relative', height: 10, bgcolor: 'divider', borderRadius: 5, my: 1 }}>
                        {/* 伏笔发展区间 */}
                        <Box
                          sx={{
                            position: 'absolute',
                            left: `${plantPct}%`,
                            width: `${Math.max(5, 100 - plantPct)}%`,
                            height: '100%',
                            bgcolor:
                              c.status === 'recycled'
                                ? 'success.main'
                                : c.status === 'revealed'
                                ? 'primary.main'
                                : 'warning.main',
                            borderRadius: 5,
                            opacity: 0.6,
                          }}
                        />
                        {/* 节点标记 */}
                        <Box
                          sx={{
                            position: 'absolute',
                            left: `${plantPct}%`,
                            top: -2,
                            width: 14,
                            height: 14,
                            borderRadius: '50%',
                            bgcolor: 'primary.dark',
                            border: '2px solid white',
                            transform: 'translateX(-50%)',
                          }}
                        />
                        <Box
                          sx={{
                            position: 'absolute',
                            left: `${revealPct}%`,
                            top: -2,
                            width: 14,
                            height: 14,
                            borderRadius: '50%',
                            bgcolor: 'warning.dark',
                            border: '2px solid white',
                            transform: 'translateX(-50%)',
                          }}
                        />
                        <Box
                          sx={{
                            position: 'absolute',
                            right: 0,
                            top: -2,
                            width: 14,
                            height: 14,
                            borderRadius: '50%',
                            bgcolor: 'error.main',
                            border: '2px solid white',
                          }}
                        />
                      </Box>
                      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', textAlign: 'center', mt: 0.5 }}>
                        张力跨度: 跨越 {Math.max(0, c.climaxChapter - c.plantChapter)} 章释放
                      </Typography>
                    </Box>

                    {c.description && (
                      <Typography variant="body2" sx={{ color: 'text.secondary', whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>
                        {c.description}
                      </Typography>
                    )}
                  </CardContent>
                </Card>
              </Grid>
            )
          })}
        </Grid>
      )}

      {/* 新建暗线对话框 */}
      <Dialog open={openCreate} onClose={() => setOpenCreate(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{t('essence_chains_dialog_title')}</DialogTitle>
        <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
          <TextField
            select
            fullWidth
            size="small"
            label={t('essence_chains_form_book')}
            value={formBookId}
            onChange={(e) => setFormBookId(e.target.value)}
          >
            {books.map((b) => (
              <MenuItem key={b.bookId} value={b.bookId}>
                {b.title}
              </MenuItem>
            ))}
            {books.length === 0 && <MenuItem value="general">通用书籍</MenuItem>}
          </TextField>

          <TextField
            fullWidth
            size="small"
            label={t('essence_chains_form_title')}
            placeholder="例如：男主身世玉佩、九品功法残卷、反派隐藏心腹"
            value={formTitle}
            onChange={(e) => setFormTitle(e.target.value)}
          />

          <TextField
            select
            fullWidth
            size="small"
            label={t('essence_chains_form_category')}
            value={formCategory}
            onChange={(e) => setFormCategory(e.target.value)}
          >
            <MenuItem value="身份谜题">身份谜题 (主角/配角隐藏血脉身世)</MenuItem>
            <MenuItem value="力量伏笔">力量伏笔 (神兵暗扣/功法反噬/禁制代价)</MenuItem>
            <MenuItem value="恩怨宿命">恩怨宿命 (灭族旧恨/宗门内奸/同盟背叛)</MenuItem>
            <MenuItem value="世界真相">世界真相 (末日成因/飞升骗局/神祇降临)</MenuItem>
            <MenuItem value="情感暗涌">情感暗涌 (白月光之死/误会冰释/道侣心结)</MenuItem>
          </TextField>

          <Box sx={{ display: 'flex', gap: 2 }}>
            <TextField
              type="number"
              size="small"
              label={t('essence_chains_form_plant')}
              value={formPlant}
              onChange={(e) => setFormPlant(Number(e.target.value))}
              fullWidth
            />
            <TextField
              type="number"
              size="small"
              label={t('essence_chains_form_reveal')}
              value={formReveal}
              onChange={(e) => setFormReveal(Number(e.target.value))}
              fullWidth
            />
            <TextField
              type="number"
              size="small"
              label={t('essence_chains_form_climax')}
              value={formClimax}
              onChange={(e) => setFormClimax(Number(e.target.value))}
              fullWidth
            />
          </Box>

          <TextField
            select
            fullWidth
            size="small"
            label={t('essence_chains_form_status')}
            value={formStatus}
            onChange={(e) => setFormStatus(e.target.value as any)}
          >
            <MenuItem value="planted">{t('essence_chains_status_planted')}</MenuItem>
            <MenuItem value="developing">{t('essence_chains_status_developing')}</MenuItem>
            <MenuItem value="revealed">{t('essence_chains_status_revealed')}</MenuItem>
            <MenuItem value="recycled">{t('essence_chains_status_recycled')}</MenuItem>
          </TextField>

          <TextField
            fullWidth
            multiline
            rows={3}
            size="small"
            label={t('essence_chains_form_desc')}
            placeholder="说明此伏笔如何前后呼应，为何能抓住读者注意力，高潮时如何反转或打脸"
            value={formDesc}
            onChange={(e) => setFormDesc(e.target.value)}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpenCreate(false)}>{t('essence_assets_adopt_btn_cancel')}</Button>
          <Button variant="contained" onClick={handleCreate} disabled={saving}>
            {saving ? '保存中...' : t('essence_chains_btn_create')}
          </Button>
        </DialogActions>
      </Dialog>

      <Snackbar
        open={Boolean(toast)}
        autoHideDuration={3000}
        onClose={() => setToast('')}
        message={toast}
      />
    </Box>
  )
}

// ---------------------------------------------------------------------------
// 5. 小说宪法与正典审查 (Novel Constitution & Canon Guard)
// ---------------------------------------------------------------------------

function ConstitutionCheckSection() {
  const { t } = useI18n()
  const [text, setText] = useState('')
  const [checking, setChecking] = useState(false)
  const [error, setError] = useState('')
  const [charVoiceInput, setCharVoiceInput] = useState('')
  const [result, setResult] = useState<{
    compliance_score: number
    is_compliant: boolean
    violations: {
      rule_id: string
      rule_name: string
      matched_term: string
      line_no: number
      snippet: string
      severity: string
    }[]
    character_voice_alerts: {
      character: string
      forbidden_phrase: string
      line_no: number
      snippet: string
    }[]
    summary: string
  } | null>(null)

  const handleCheck = async () => {
    if (!text.trim()) {
      setError('请输入待审查的小说正文或章节草稿')
      return
    }
    setError('')
    setChecking(true)

    const charactersForbidden: Record<string, string[]> = {}
    if (charVoiceInput.trim()) {
      for (const line of charVoiceInput.split('\n')) {
        const parts = line.split(/[:：]/)
        if (parts.length >= 2) {
          const charName = parts[0].trim()
          const phrases = parts[1].split(/[,，、]/).map((p) => p.trim()).filter(Boolean)
          if (charName && phrases.length > 0) {
            charactersForbidden[charName] = phrases
          }
        }
      }
    }

    try {
      const res = await essenceApi.checkConstitution({
        text: text.trim(),
        characters_forbidden: Object.keys(charactersForbidden).length > 0 ? charactersForbidden : undefined,
      })
      setResult(res)
    } catch (e) {
      setError(friendlyError(e))
    } finally {
      setChecking(false)
    }
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      {error && <Alert severity="error" onClose={() => setError('')}>{error}</Alert>}

      <Box>
        <Typography variant="h6" sx={{ fontWeight: 'bold' }}>
          {t('essence_const_title')}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          {t('essence_const_desc')}
        </Typography>
      </Box>

      <Paper variant="outlined" sx={{ p: 2, display: 'flex', flexDirection: 'column', gap: 2 }}>
        <TextField
          multiline
          rows={7}
          label={t('essence_const_text_label')}
          placeholder={t('essence_const_text_placeholder')}
          value={text}
          onChange={(e) => setText(e.target.value)}
          fullWidth
        />

        <TextField
          size="small"
          label={t('essence_const_voice_label')}
          placeholder="例如: 陆沉: 遵命, 绝望&#10;林清雪: 粗鄙"
          value={charVoiceInput}
          onChange={(e) => setCharVoiceInput(e.target.value)}
          fullWidth
          helperText={t('essence_const_voice_helper')}
        />

        <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}>
          <Button
            variant="contained"
            color="primary"
            startIcon={<GavelIcon />}
            onClick={handleCheck}
            disabled={checking}
          >
            {checking ? t('essence_const_btn_checking') : t('essence_const_btn_check')}
          </Button>
        </Box>
      </Paper>

      {result && (
        <Paper variant="outlined" sx={{ p: 2, display: 'flex', flexDirection: 'column', gap: 2 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 1 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
              <Chip
                label={result.is_compliant ? t('essence_const_chip_compliant') : t('essence_const_chip_violation')}
                color={result.is_compliant ? 'success' : 'error'}
                sx={{ fontWeight: 'bold' }}
              />
              <Typography variant="subtitle1" sx={{ fontWeight: 'bold' }}>
                {t('essence_const_score_label')}{result.compliance_score} / 100
              </Typography>
            </Box>
            <Typography variant="body2" color="text.secondary">
              {result.summary}
            </Typography>
          </Box>

          <Divider />

          {/* 违规项列表 */}
          <Box>
            <Typography variant="subtitle2" sx={{ fontWeight: 'bold', mb: 1 }}>
              {t('essence_const_violations_h')} ({result.violations.length} 项)
            </Typography>
            {result.violations.length === 0 ? (
              <Typography variant="body2" color="text.secondary">
                {t('essence_const_no_violations')}
              </Typography>
            ) : (
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                {result.violations.map((v, idx) => (
                  <Card key={idx} variant="outlined" sx={{ p: 1.5, borderColor: v.severity === 'high' ? 'error.main' : 'warning.main' }}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
                        <Chip
                          size="small"
                          label={v.severity === 'high' ? '严重违宪' : '中度偏离'}
                          color={v.severity === 'high' ? 'error' : 'warning'}
                        />
                        <Typography variant="body2" sx={{ fontWeight: 'bold' }}>
                          {v.rule_name}
                        </Typography>
                      </Box>
                      <Typography variant="caption" color="text.secondary">
                        第 {v.line_no} 行命中: 「{v.matched_term}」
                      </Typography>
                    </Box>
                    <Typography variant="body2" sx={{ mt: 1, fontFamily: 'monospace', bgcolor: 'action.hover', p: 0.5, borderRadius: 1 }}>
                      {v.snippet}
                    </Typography>
                  </Card>
                ))}
              </Box>
            )}
          </Box>

          {/* 角色声线冲突列表 */}
          <Box sx={{ mt: 1 }}>
            <Typography variant="subtitle2" sx={{ fontWeight: 'bold', mb: 1 }}>
              {t('essence_const_voice_h')} ({result.character_voice_alerts.length} 项)
            </Typography>
            {result.character_voice_alerts.length === 0 ? (
              <Typography variant="body2" color="text.secondary">
                {t('essence_const_no_voice_alerts')}
              </Typography>
            ) : (
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                {result.character_voice_alerts.map((a, idx) => (
                  <Card key={idx} variant="outlined" sx={{ p: 1.5, borderColor: 'secondary.main' }}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
                        <Chip size="small" label={`角色: ${a.character}`} color="secondary" />
                        <Typography variant="body2" sx={{ fontWeight: 'bold', color: 'error.main' }}>
                          禁说词汇: 「{a.forbidden_phrase}」
                        </Typography>
                      </Box>
                      <Typography variant="caption" color="text.secondary">
                        第 {a.line_no} 行
                      </Typography>
                    </Box>
                    <Typography variant="body2" sx={{ mt: 1, fontFamily: 'monospace', bgcolor: 'action.hover', p: 0.5, borderRadius: 1 }}>
                      {a.snippet}
                    </Typography>
                  </Card>
                ))}
              </Box>
            )}
          </Box>
        </Paper>
      )}
    </Box>
  )
}


