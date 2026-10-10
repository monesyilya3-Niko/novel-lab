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
import {
  essenceApi,
  writingApi,
  friendlyError,
  type EssenceBook,
  type EssenceAsset,
  type EssenceMacroAnalysisResult,
} from '../api/client'
import type { WritingProject } from '../types'

const PLATFORM_OPTIONS = [
  { value: 'general', label: '通用网文平台' },
  { value: 'qidian', label: '起点中文网 (大纵深世界观/严密升级/反圣母)' },
  { value: 'fanqie', label: '番茄小说 (30秒黄金钩/每章留扣/防虐主)' },
  { value: 'jinjiang', label: '晋江文学城 (人设细腻反差/推拉克制/微表情)' },
  { value: 'qimao', label: '七猫中文网 (开局强冲突受辱/底牌强反制)' },
  { value: 'zhihu', label: '知乎盐选 (第一人称高反转/三幕式快节奏)' },
]

const GENRE_OPTIONS = [
  { value: 'general', label: '通用题材' },
  { value: 'xianxia', label: '仙侠修真' },
  { value: 'xuanhuan', label: '玄幻异界' },
  { value: 'dushi', label: '都市职场/异能' },
  { value: 'kehuan', label: '科幻未来/星际' },
  { value: 'xuanyi', label: '悬疑怪谈/惊悚' },
  { value: 'yanqing', label: '现代/古代言情' },
  { value: 'lishi', label: '历史穿越/两宋大明' },
  { value: 'youxi', label: '网游竞技/电竞' },
  { value: 'wuxian', label: '诸天无限流' },
]

const CATEGORY_MAP: Record<string, { label: string; color: 'primary' | 'secondary' | 'success' | 'warning' | 'info' | 'default' }> = {
  outline: { label: '骨架大纲', color: 'primary' },
  hook: { label: '开篇钩子', color: 'error' as any },
  character: { label: '人设反差', color: 'secondary' },
  trope: { label: '爆款桥段', color: 'success' },
  style: { label: '反AI口语', color: 'warning' },
}

export default function EssenceWorkbench() {
  const [tab, setTab] = useState(0)

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <Paper sx={{ p: 2 }}>
        <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 2 }}>
          <Tabs value={tab} onChange={(_, v) => setTab(v)}>
            <Tab icon={<AutoAwesomeIcon fontSize="small" />} iconPosition="start" label="离线精读与解构提炼" />
            <Tab icon={<LayersIcon fontSize="small" />} iconPosition="start" label="五维精华资产库" />
            <Tab icon={<MenuBookIcon fontSize="small" />} iconPosition="start" label="已精读书籍档案" />
          </Tabs>
        </Box>

        {tab === 0 && <MacroExtractSection onAssetSaved={() => setTab(1)} />}
        {tab === 1 && <EssenceAssetsSection />}
        {tab === 2 && <EssenceBooksSection />}
      </Paper>
    </Box>
  )
}

// ---------------------------------------------------------------------------
// 1. 离线精读与宏观解构提炼
// ---------------------------------------------------------------------------

function MacroExtractSection({ onAssetSaved }: { onAssetSaved: () => void }) {
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
      setToast('深度精读与宏观提炼完成，已建立书籍档案！')
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
      setToast(`已成功入库资产：${item.title}`)
      onAssetSaved()
    } catch (e) {
      setError(friendlyError(e))
    }
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2.5 }}>
      <Typography variant="body2" color="text.secondary">
        100% 纯本地离线精读引擎：对长篇正文进行章节切片、黄金三章钩子探测、对白与叙述比例核算、高频反 AI 口语词频统计，提炼出可直接反哺创作的五维结构化资产。
      </Typography>

      {error && <Alert severity="error" onClose={() => setError('')}>{error}</Alert>}

      <Paper variant="outlined" sx={{ p: 2, display: 'flex', flexDirection: 'column', gap: 2 }}>
        <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
          <TextField
            label="精图书籍/样本名称"
            size="small"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="例如：《宿命之环》《我在精神病院学斩神》"
            sx={{ flex: 1, minWidth: 220 }}
          />
          <TextField
            select
            label="目标平台生态"
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
            label="所属题材类别"
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
          label="输入精读正文（支持多章连粘，自动识别章节序号）"
          multiline
          rows={6}
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="粘贴小说样本文字..."
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
            {analyzing ? '离线深度精读分析中...' : '开始深度精读与宏观解构'}
          </Button>
        </Box>
      </Paper>

      {result && (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <Divider>
            <Chip label="精读提炼报告" color="primary" variant="outlined" />
          </Divider>

          {/* 宏观指标卡 */}
          <Grid container spacing={2}>
            <Grid item xs={12} sm={6} md={2}>
              <Paper variant="outlined" sx={{ p: 1.5, textAlign: 'center' }}>
                <Typography variant="caption" color="text.secondary">总解析章节</Typography>
                <Typography variant="h6">{result.totalChapters} 章</Typography>
              </Paper>
            </Grid>
            <Grid item xs={12} sm={6} md={2}>
              <Paper variant="outlined" sx={{ p: 1.5, textAlign: 'center' }}>
                <Typography variant="caption" color="text.secondary">总精读字数</Typography>
                <Typography variant="h6">{result.totalChars.toLocaleString()} 字</Typography>
              </Paper>
            </Grid>
            <Grid item xs={12} sm={6} md={2}>
              <Paper variant="outlined" sx={{ p: 1.5, textAlign: 'center' }}>
                <Typography variant="caption" color="text.secondary">平均章字数</Typography>
                <Typography variant="h6">{result.avgChapterLen} 字</Typography>
              </Paper>
            </Grid>
            <Grid item xs={12} sm={6} md={2}>
              <Paper variant="outlined" sx={{ p: 1.5, textAlign: 'center' }}>
                <Typography variant="caption" color="text.secondary">对白占比</Typography>
                <Typography variant="h6" color={result.dialogueRatio >= 0.25 && result.dialogueRatio <= 0.45 ? 'success.main' : 'warning.main'}>
                  {(result.dialogueRatio * 100).toFixed(1)}%
                </Typography>
              </Paper>
            </Grid>
            <Grid item xs={12} sm={6} md={2}>
              <Paper variant="outlined" sx={{ p: 1.5, textAlign: 'center' }}>
                <Typography variant="caption" color="text.secondary">高潮节奏周期</Typography>
                <Typography variant="h6">{result.rhythmClimaxInterval} 章/次</Typography>
              </Paper>
            </Grid>
            <Grid item xs={12} sm={6} md={2}>
              <Paper variant="outlined" sx={{ p: 1.5, textAlign: 'center' }}>
                <Typography variant="caption" color="text.secondary">AI 味指数 (0-10)</Typography>
                <Typography variant="h6" color={result.aiSlopScore < 3.0 ? 'success.main' : 'error.main'}>
                  {result.aiSlopScore} 分
                </Typography>
              </Paper>
            </Grid>
          </Grid>

          {/* 黄金三章开篇解构 */}
          {result.openingThreeChapters && result.openingThreeChapters.length > 0 && (
            <Paper variant="outlined" sx={{ p: 2 }}>
              <Typography variant="subtitle2" sx={{ mb: 1.5, fontWeight: 'bold' }}>
                黄金三章开篇解构（抓人感与钩子演进）
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
                高频真实网感口语 / 特色句式
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
                结构化资产建议（点击一键沉淀入库）
              </Typography>
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
                {result.suggestedAssets.map((asset, idx) => (
                  <Card key={idx} variant="outlined" sx={{ p: 1.5 }}>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <Chip
                          size="small"
                          label={CATEGORY_MAP[asset.category]?.label || asset.category}
                          color={CATEGORY_MAP[asset.category]?.color || 'default'}
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
                        沉淀入库
                      </Button>
                    </Box>
                    <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                      {asset.summary}
                    </Typography>
                  </Card>
                ))}
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
    return (
      a.title.toLowerCase().includes(searchKw.toLowerCase()) ||
      a.tags.toLowerCase().includes(searchKw.toLowerCase()) ||
      a.summary.toLowerCase().includes(searchKw.toLowerCase())
    )
  })

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      {error && <Alert severity="error" onClose={() => setError('')}>{error}</Alert>}

      {/* 筛选栏 */}
      <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', alignItems: 'center' }}>
        <TextField
          select
          label="五维分类"
          size="small"
          value={selectedCategory}
          onChange={(e) => setSelectedCategory(e.target.value)}
          sx={{ width: 160 }}
        >
          <MenuItem value="all">全部五维分类</MenuItem>
          <MenuItem value="outline">骨架大纲</MenuItem>
          <MenuItem value="hook">开篇钩子</MenuItem>
          <MenuItem value="character">人设反差</MenuItem>
          <MenuItem value="trope">爆款桥段</MenuItem>
          <MenuItem value="style">反AI口语</MenuItem>
        </TextField>

        <TextField
          select
          label="生态平台"
          size="small"
          value={selectedPlatform}
          onChange={(e) => setSelectedPlatform(e.target.value)}
          sx={{ width: 160 }}
        >
          <MenuItem value="all">全平台生态</MenuItem>
          {PLATFORM_OPTIONS.map((p) => (
            <MenuItem key={p.value} value={p.value}>{p.label.split(' ')[0]}</MenuItem>
          ))}
        </TextField>

        <TextField
          label="模糊检索 (标题/标签/摘要)"
          size="small"
          value={searchKw}
          onChange={(e) => setSearchKw(e.target.value)}
          sx={{ flex: 1, minWidth: 200 }}
        />

        <Button variant="outlined" onClick={loadAssets}>
          刷新
        </Button>
      </Box>

      {/* 资产卡片瀑布流 */}
      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
          <CircularProgress />
        </Box>
      ) : filtered.length === 0 ? (
        <Paper variant="outlined" sx={{ p: 4, textAlign: 'center', color: 'text.secondary' }}>
          暂无符合条件的精读资产。可在「离线精读与解构提炼」页签粘贴正文进行智能分析萃取。
        </Paper>
      ) : (
        <Grid container spacing={2}>
          {filtered.map((item) => (
            <Grid item xs={12} md={6} key={item.id}>
              <Card variant="outlined" sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
                <CardContent sx={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 1 }}>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
                      <Chip
                        size="small"
                        label={CATEGORY_MAP[item.category]?.label || item.category}
                        color={CATEGORY_MAP[item.category]?.color || 'default'}
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
                    {item.tags.split(',').filter(Boolean).map((tag, idx) => (
                      <Chip key={idx} label={tag} size="small" variant="outlined" />
                    ))}
                    <Chip label={`生态: ${item.platform}`} size="small" variant="outlined" />
                    <Chip label={`题材: ${item.genre}`} size="small" variant="outlined" />
                  </Box>

                  {item.userNote && (
                    <Box sx={{ bgcolor: 'action.hover', p: 1, borderRadius: 1 }}>
                      <Typography variant="caption" color="text.secondary">
                        创作者感悟: {item.userNote}
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
                    删除
                  </Button>
                  <Button
                    size="small"
                    variant="contained"
                    color="success"
                    startIcon={<CheckCircleOutlineIcon />}
                    onClick={() => {
                      setAdoptDialog(item)
                      if (item.category === 'outline') setAdoptTarget('outline')
                      else if (item.category === 'character') setAdoptTarget('character')
                      else setAdoptTarget('note')
                    }}
                  >
                    一键反哺创作
                  </Button>
                </Box>
              </Card>
            </Grid>
          ))}
        </Grid>
      )}

      {/* 反哺对话框 */}
      <Dialog open={Boolean(adoptDialog)} onClose={() => setAdoptDialog(null)} maxWidth="xs" fullWidth>
        <DialogTitle>一键反哺至写作工坊</DialogTitle>
        <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
          <Typography variant="body2" color="text.secondary">
            将资产「{adoptDialog?.title}」直接注入到你当前的创作项目中，作为大纲节点、人物卡或灵感便签。
          </Typography>
          <TextField
            select
            label="目标项目"
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
            label="反哺转存形态"
            size="small"
            value={adoptTarget}
            onChange={(e) => setAdoptTarget(e.target.value)}
            fullWidth
          >
            <MenuItem value="outline">转入写作大纲 (writing_outlines)</MenuItem>
            <MenuItem value="character">转入人物卡片 (writing_characters)</MenuItem>
            <MenuItem value="note">转入灵感便签 (writing_notes)</MenuItem>
          </TextField>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setAdoptDialog(null)}>取消</Button>
          <Button variant="contained" color="primary" onClick={handleAdopt}>确认反哺</Button>
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

function EssenceBooksSection() {
  const [books, setBooks] = useState<EssenceBook[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [toast, setToast] = useState('')

  const loadBooks = async () => {
    setLoading(true)
    setError('')
    try {
      const res = await essenceApi.listBooks()
      setBooks(res.books || [])
    } catch (e) {
      setError(friendlyError(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadBooks()
  }, [])

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
          本地精读档案库：沉淀每部精读长篇的字数、对白率、节奏模型，支持全生命周期管理。
        </Typography>
        <Button variant="outlined" size="small" onClick={loadBooks}>
          刷新档案
        </Button>
      </Box>

      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
          <CircularProgress />
        </Box>
      ) : books.length === 0 ? (
        <Paper variant="outlined" sx={{ p: 4, textAlign: 'center', color: 'text.secondary' }}>
          暂无已精读的书籍档案。请先在「离线精读与解构提炼」页签输入样本进行解析。
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
                    <Chip size="small" label={b.genre} />
                    <Chip size="small" label={b.platform} variant="outlined" />
                  </Box>

                  <Typography variant="body2" color="text.secondary">
                    {b.totalChapters} 章 | {b.totalChars.toLocaleString()} 字
                  </Typography>

                  <Box sx={{ mt: 1, display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                    <Typography variant="caption" color="text.secondary">
                      对白占比: {(b.dialogueRatio * 100).toFixed(1)}%
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      高潮间隔: {b.rhythmClimaxInterval} 章/次
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      AI 味道评分: {b.aiSlopScore} / 10
                    </Typography>
                  </Box>
                </CardContent>
              </Card>
            </Grid>
          ))}
        </Grid>
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
