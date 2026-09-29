// 分析结果面板：查看选定章节×批次各 pass 产出的资产 JSON。
// 首版以结构化 JSON 树 + 可读化摘要两种形式展示（P1 只做到可读 JSON）。
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import Box from '@mui/material/Box'
import Typography from '@mui/material/Typography'
import Paper from '@mui/material/Paper'
import Tabs from '@mui/material/Tabs'
import Tab from '@mui/material/Tab'
import Select from '@mui/material/Select'
import MenuItem from '@mui/material/MenuItem'
import FormControl from '@mui/material/FormControl'
import InputLabel from '@mui/material/InputLabel'
import Button from '@mui/material/Button'
import CircularProgress from '@mui/material/CircularProgress'
import Alert from '@mui/material/Alert'
import { useApp } from '../state/AppContext'
import * as api from '../api/client'

const PASS_ORDER = ['pass1_structure', 'pass2_character', 'pass3_style', 'pass4_commercial'] as const

const PASS_LABEL: Record<string, string> = {
  pass1_structure: '结构拆解',
  pass2_character: '人物弧光',
  pass3_style: '文风指纹',
  pass4_commercial: '商业评估',
}

export default function ResultPanel() {
  const { book, selectedChapter, currentChapter, batchStates } = useApp()
  const [batchIndex, setBatchIndex] = useState(0)
  const [passName, setPassName] = useState<string>('pass1_structure')
  const [asset, setAsset] = useState<Record<string, unknown> | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const bookId = book?.bookId ?? null
  const chapterIndex = selectedChapter ?? null

  const batchOptions = useMemo(() => {
    if (!currentChapter) return []
    return Array.from({ length: currentChapter.batchCount }, (_, i) => i)
  }, [currentChapter])

  const loadSeq = useRef(0)
  const load = useCallback(async (chapter: number | null, bi: number, pn: string) => {
    if (!bookId || chapter == null) {
      setAsset(null)
      return
    }
    const seq = ++loadSeq.current
    setLoading(true)
    setError(null)
    try {
      const data = await api.getAsset(bookId, chapter, bi, pn)
      // 序列守卫：迟到响应不得覆盖更新的请求（与 AppContext 的 bookResults 同模式）
      if (seq === loadSeq.current) setAsset(data)
    } catch (e) {
      if (seq === loadSeq.current) {
        setError((e as Error).message)
        setAsset(null)
      }
    } finally {
      if (seq === loadSeq.current) setLoading(false)
    }
  }, [bookId])

  // P2-F9 真修复：单 effect 统一处理"章节/批次/阶段/书"变化。
  // - 章节变化时批次强制归零，用 (新章节, 0) 直接加载，不等 setBatchIndex 重渲染，
  //   避免闭包拿到旧 batchIndex 发出"新章节+旧批次"的误请求；
  // - lastLoadKey 去重：归零引发的重渲染（batchIndex 2→0）不再二次加载。
  const lastChapterRef = useRef<number | null>(null)
  const lastLoadKey = useRef('')
  useEffect(() => {
    const bi = chapterIndex !== lastChapterRef.current ? 0 : batchIndex
    lastChapterRef.current = chapterIndex
    if (bi !== batchIndex) setBatchIndex(bi) // 同步下拉框显示
    const key = `${bookId}|${chapterIndex}|${bi}|${passName}`
    if (key === lastLoadKey.current) return
    lastLoadKey.current = key
    if (chapterIndex != null) load(chapterIndex, bi, passName)
  }, [bookId, chapterIndex, batchIndex, passName, load])

  if (!book || chapterIndex == null) {
    return (
      <Box sx={{ p: 3, textAlign: 'center' }}>
        <Typography color="text.secondary">请先选择章节查看分析结果</Typography>
      </Box>
    )
  }

  return (
    <Box sx={{ p: 3, height: '100%', overflow: 'auto' }}>
      <Typography variant="h6" gutterBottom>
        分析结果 · 第{chapterIndex}章
      </Typography>

      {/* 选择器 */}
      <Box sx={{ display: 'flex', gap: 2, mb: 2, flexWrap: 'wrap', alignItems: 'center' }}>
        <FormControl size="small" sx={{ minWidth: 140 }}>
          <InputLabel>批次</InputLabel>
          <Select
            value={batchIndex}
            label="批次"
            onChange={(e) => setBatchIndex(Number(e.target.value))}
          >
            {batchOptions.map((bi) => {
              const st = batchStates[`c${chapterIndex}-b${bi}`]?.status
              return (
                <MenuItem key={bi} value={bi}>
                  第 {bi} 批 {st ? `· ${st}` : ''}
                </MenuItem>
              )
            })}
          </Select>
        </FormControl>

        <Tabs
          value={passName}
          onChange={(_e, v) => setPassName(v as string)}
          variant="scrollable"
          scrollButtons="auto"
          sx={{ minHeight: 40 }}
        >
          {PASS_ORDER.map((p) => (
            <Tab key={p} value={p} label={PASS_LABEL[p]} sx={{ minHeight: 40 }} />
          ))}
        </Tabs>

        <Button
          size="small"
          variant="outlined"
          onClick={() => { if (chapterIndex != null) load(chapterIndex, batchIndex, passName) }}
          disabled={loading}
        >
          刷新
        </Button>
      </Box>

      {/* 内容 */}
      {loading ? (
        <Box sx={{ textAlign: 'center', py: 4 }}>
          <CircularProgress size={24} />
        </Box>
      ) : error ? (
        <Alert severity="error">{error}</Alert>
      ) : asset && Object.keys(asset).length > 0 ? (
        <Paper
          variant="outlined"
          sx={{ p: 2, bgcolor: 'background.paper', overflow: 'auto' }}
        >
          <pre
            style={{
              margin: 0,
              fontSize: 12,
              lineHeight: 1.6,
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
            }}
          >
            {JSON.stringify(asset, null, 2)}
          </pre>
        </Paper>
      ) : (
        <Box sx={{ p: 3, textAlign: 'center' }}>
          <Typography color="text.secondary">
            该批次尚未生成此 pass 的结果（请先运行分析）
          </Typography>
        </Box>
      )}
    </Box>
  )
}
