import { useState, useEffect } from 'react'
import Box from '@mui/material/Box'
import Typography from '@mui/material/Typography'
import Button from '@mui/material/Button'
import TextField from '@mui/material/TextField'
import MenuItem from '@mui/material/MenuItem'
import Paper from '@mui/material/Paper'
import Alert from '@mui/material/Alert'
import CircularProgress from '@mui/material/CircularProgress'
import Chip from '@mui/material/Chip'
import Stack from '@mui/material/Stack'
import Divider from '@mui/material/Divider'
import Tabs from '@mui/material/Tabs'
import Tab from '@mui/material/Tab'
import FormControlLabel from '@mui/material/FormControlLabel'
import Checkbox from '@mui/material/Checkbox'
import ContentCopyIcon from '@mui/icons-material/ContentCopy'
import AutoFixHighIcon from '@mui/icons-material/AutoFixHigh'
import SearchIcon from '@mui/icons-material/Search'
import SportsEsportsIcon from '@mui/icons-material/SportsEsports'
import AssignmentTurnedInIcon from '@mui/icons-material/AssignmentTurnedIn'
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline'
import { platformApi, SubmissionDiagnosisResult } from '../api/client'
import { friendlyError } from '../api/client'
import { useI18n } from '../state/I18nContext'

interface Platform {
  id: string
  name: string
  chapterMinChars?: number
  chapterMaxChars?: number
  chapter_min_chars?: number
  chapter_max_chars?: number
  supportsSerialization?: boolean
  supports_serialization?: boolean
  climax_interval?: string
  rhythm_type?: string
  genreCount?: number
}

interface ParsedStatBox {
  type: string
  title: string
  fields: Record<string, string>
  raw_text: string
  start: number
  end: number
  char_count?: number
}

const SAMPLE_LITRPG_TEXT = `Chapter 1: The Descent into the Red Dungeon

Carl stepped onto the frostbitten stone floor, shivering as the damp dungeon air hit his bare chest. Donut clung tightly to his shoulder, her golden fur bristling with alarm.

[Status Window]
Name: Carl
Class: Dungeon Crawler
Level: 1
Health: 100/100
Mana: 50/50
Strength: 14
Agility: 11
Constitution: 13
Intelligence: 9

"Listen up, crawler," the automated voice boomed across the cavernous room. "Survival is not guaranteed, but high viewership is."

He gripped the spiked wooden club tightly and moved forward into the mist.`

export default function PlatformPanel() {
  const { t } = useI18n()
  const [panelTab, setPanelTab] = useState(0)

  // Tab 0: 多平台合规与签约诊断
  const [platforms, setPlatforms] = useState<Platform[]>([])
  const [selected, setSelected] = useState('')
  const [chapterText, setChapterText] = useState('')
  const [chapterTitle, setChapterTitle] = useState('')
  const [result, setResult] = useState<Record<string, unknown> | null>(null)
  const [diagnosis, setDiagnosis] = useState<SubmissionDiagnosisResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [diagnosing, setDiagnosing] = useState(false)
  const [error, setError] = useState('')

  // Tab 1: LitRPG 属性面板与海外排版
  const [litrpgTitle, setLitrpgTitle] = useState('Chapter 1: The Descent into the Red Dungeon')
  const [litrpgText, setLitrpgText] = useState(SAMPLE_LITRPG_TEXT)
  const [authorNoteHead, setAuthorNoteHead] = useState('Thanks for reading! Updates every Monday and Thursday.')
  const [authorNoteFoot, setAuthorNoteFoot] = useState('Support the story on Patreon for 5 advance chapters. Please rate and review!')
  const [wrapStatBoxes, setWrapStatBoxes] = useState(true)
  const [parsedBoxes, setParsedBoxes] = useState<ParsedStatBox[] | null>(null)
  const [formattedBBCode, setFormattedBBCode] = useState('')
  const [parsing, setParsing] = useState(false)
  const [formatting, setFormatting] = useState(false)
  const [copied, setCopied] = useState(false)
  const [litrpgError, setLitrpgError] = useState('')

  useEffect(() => {
    platformApi.list()
      .then((data) => {
        const list = (data.platforms ?? []) as Platform[]
        setPlatforms(list)
        setSelected((prev) => (prev && list.some((pl) => pl.id === prev) ? prev : (list[0]?.id ?? '')))
      })
      .catch((e) => setError(`加载平台列表失败: ${e}`))
  }, [])

  const doCheck = async () => {
    setLoading(true)
    setError('')
    try {
      const data = await platformApi.check({
        platform_id: selected,
        chapter_text: chapterText,
        chapter_title: chapterTitle,
      })
      setResult(data)
    } catch (e) {
      setError(friendlyError(e))
    } finally {
      setLoading(false)
    }
  }

  const doDiagnose = async () => {
    setDiagnosing(true)
    setError('')
    try {
      const data = await platformApi.diagnose({
        platform_id: selected,
        chapter_text: chapterText,
        chapter_title: chapterTitle,
      })
      setDiagnosis(data)
    } catch (e) {
      setError(friendlyError(e))
    } finally {
      setDiagnosing(false)
    }
  }

  const handleLoadSample = () => {
    setLitrpgTitle('Chapter 1: The Descent into the Red Dungeon')
    setLitrpgText(SAMPLE_LITRPG_TEXT)
    setAuthorNoteHead('Thanks for checking out my novel on Royal Road! Updates every Monday and Thursday.')
    setAuthorNoteFoot('Support the story on Patreon for 5 advance chapters. Please leave a rating if you enjoyed!')
    setParsedBoxes(null)
    setFormattedBBCode('')
    setLitrpgError('')
  }

  const handleParseStatBox = async () => {
    setParsing(true)
    setLitrpgError('')
    try {
      const res = await platformApi.parseStatBox(litrpgText)
      setParsedBoxes((res.stat_boxes ?? []) as unknown as ParsedStatBox[])
    } catch (e) {
      setLitrpgError(friendlyError(e))
    } finally {
      setParsing(false)
    }
  }

  const handleFormatRoyalRoad = async () => {
    setFormatting(true)
    setLitrpgError('')
    try {
      const res = await platformApi.formatRoyalRoad({
        title: litrpgTitle,
        text: litrpgText,
        author_note_head: authorNoteHead,
        author_note_foot: authorNoteFoot,
        wrap_stat_boxes: wrapStatBoxes,
      })
      setFormattedBBCode(res.formatted)
    } catch (e) {
      setLitrpgError(friendlyError(e))
    } finally {
      setFormatting(false)
    }
  }

  const handleCopy = (text: string) => {
    if (navigator?.clipboard?.writeText) {
      navigator.clipboard.writeText(text).catch(() => {})
    }
    setCopied(true)
    setTimeout(() => setCopied(false), 2500)
  }

  const currentPlatform = platforms.find((p) => p.id === selected)
  const issues = (result?.issues ?? []) as { type: string; severity: string; message: string }[]

  const getRatingColor = (rating: string) => {
    if (rating === 'A') return 'success'
    if (rating === 'B') return 'warning'
    return 'error'
  }

  const minChars = currentPlatform?.chapter_min_chars ?? currentPlatform?.chapterMinChars ?? 0
  const maxChars = currentPlatform?.chapter_max_chars ?? currentPlatform?.chapterMaxChars ?? 0

  return (
    <Box>
      <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 2 }}>
        <Tabs value={panelTab} onChange={(_, v) => setPanelTab(v)}>
          <Tab icon={<AssignmentTurnedInIcon fontSize="small" />} iconPosition="start" label={t('platform_tab_diagnose', '多平台合规与签约诊断')} />
          <Tab icon={<SportsEsportsIcon fontSize="small" />} iconPosition="start" label={t('platform_tab_litrpg', 'LitRPG 属性面板与海外排版')} />
        </Tabs>
      </Box>

      {panelTab === 0 && (
        <Box>
          <Typography variant="h6" gutterBottom>{t('platform_panel_title', '多平台适配与签约诊断')}</Typography>

          <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap', mb: 2 }}>
            <TextField select label="目标平台" value={selected} onChange={(e) => setSelected(e.target.value)} sx={{ minWidth: 180 }} size="small">
              {platforms.map((p) => <MenuItem key={p.id} value={p.id}>{p.name}</MenuItem>)}
            </TextField>
            {currentPlatform && (
              <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
                {minChars > 0 && (
                  <Chip
                    label={`${minChars}-${maxChars}字/章`}
                    size="small" color="primary" variant="outlined"
                  />
                )}
                {currentPlatform.climax_interval && (
                  <Chip label={`爽点周期: ${currentPlatform.climax_interval}`} size="small" color="secondary" variant="outlined" />
                )}
                {currentPlatform.rhythm_type && (
                  <Chip label={currentPlatform.rhythm_type} size="small" variant="outlined" />
                )}
              </Stack>
            )}
          </Box>

          {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

          <TextField
            label="章节标题（可选）" fullWidth size="small" sx={{ mb: 1.5 }}
            value={chapterTitle} onChange={(e) => setChapterTitle(e.target.value)}
          />
          <TextField
            label="章节正文" multiline rows={8} fullWidth size="small" sx={{ mb: 1.5 }}
            value={chapterText} onChange={(e) => setChapterText(e.target.value)}
            helperText={currentPlatform ? `建议 ${currentPlatform.chapterMinChars}-${currentPlatform.chapterMaxChars} 字` : ''}
          />
          <Stack direction="row" spacing={2} sx={{ mb: 2 }}>
            <Button variant="outlined" onClick={doCheck} disabled={!chapterText.trim() || loading || diagnosing}>
              {loading ? <CircularProgress size={20} /> : t('platform_check_compliance', '检查合规性')}
            </Button>
            <Button variant="contained" color="secondary" onClick={doDiagnose} disabled={!chapterText.trim() || loading || diagnosing}>
              {diagnosing ? <CircularProgress size={20} /> : t('platform_diagnose_action', '🎯 签约过稿深度诊断')}
            </Button>
          </Stack>

          {result && (
            <Paper sx={{ p: 2, mb: 2 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                <Typography variant="subtitle2">合规检查结果</Typography>
                <Chip
                  label={result.compliant ? '合规' : '不合规'}
                  size="small"
                  color={result.compliant ? 'success' : 'error'}
                />
                <Typography variant="body2" color="text.secondary">
                  {String(result.charCount)} 字
                </Typography>
              </Box>
              {issues.length > 0 && (
                <Box sx={{ mt: 1 }}>
                  {issues.map((iss, i) => (
                    <Alert key={i} severity={iss.severity === 'error' ? 'error' : 'warning'} sx={{ mb: 0.5 }}>
                      {iss.message}
                    </Alert>
                  ))}
                </Box>
              )}
            </Paper>
          )}

          {diagnosis && (
            <Paper sx={{ p: 2, mb: 2, borderLeft: (theme) => `4px solid ${diagnosis.grade === 'A' ? theme.palette.success.main : diagnosis.grade === 'B' ? theme.palette.warning.main : theme.palette.error.main}` }}>
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1.5, flexWrap: 'wrap', gap: 1 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>签约过稿诊断报告</Typography>
                  <Chip
                    label={`评级 ${diagnosis.grade} · 签约概率: ${diagnosis.signingProb}`}
                    color={getRatingColor(diagnosis.grade)}
                    size="small"
                  />
                  <Chip
                    label={`签约潜力分: ${diagnosis.score} / 100`}
                    variant="outlined"
                    color={diagnosis.score >= 80 ? 'success' : diagnosis.score >= 60 ? 'warning' : 'error'}
                    size="small"
                  />
                </Box>
                <Typography variant="caption" color="text.secondary">
                  字数: {diagnosis.charCount} | 对话占比: {(diagnosis.dialogueRatio * 100).toFixed(1)}%
                </Typography>
              </Box>

              <Divider sx={{ my: 1.5 }} />

              {diagnosis.vetoRisks.length > 0 && (
                <Box sx={{ mb: 1.5 }}>
                  <Typography variant="subtitle2" color="error.main" gutterBottom sx={{ fontWeight: 600 }}>
                    🚨 致命劝退点（直接影响编辑初筛签约）:
                  </Typography>
                  {diagnosis.vetoRisks.map((risk, idx) => (
                    <Alert key={idx} severity="error" sx={{ mb: 0.75 }}>
                      {risk}
                    </Alert>
                  ))}
                </Box>
              )}

              {diagnosis.actionableFixes.length > 0 && (
                <Box sx={{ mt: 1 }}>
                  <Typography variant="subtitle2" color="text.primary" gutterBottom sx={{ fontWeight: 600 }}>
                    💡 针对性修改建议:
                  </Typography>
                  {diagnosis.actionableFixes.map((fix, idx) => (
                    <Alert key={idx} severity="info" sx={{ mb: 0.75 }}>
                      {fix}
                    </Alert>
                  ))}
                </Box>
              )}

              {diagnosis.vetoRisks.length === 0 && diagnosis.actionableFixes.length === 0 && (
                <Alert severity="success">
                  正文节奏与篇幅极佳，未发现明显编辑劝退项，保持当前水准即可投稿！
                </Alert>
              )}
            </Paper>
          )}

          <Paper sx={{ p: 2 }}>
            <Typography variant="subtitle2" gutterBottom>平台要求</Typography>
            {platforms.map((p) => (
              <Box key={p.id} sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                <Typography variant="body2" sx={{ minWidth: 100 }}>{p.name}</Typography>
                <Typography variant="caption" color="text.secondary">
                  {p.chapterMinChars}-{p.chapterMaxChars}字 | {p.supportsSerialization ? '连载' : '短篇'} | {p.genreCount} 题材
                </Typography>
              </Box>
            ))}
          </Paper>
        </Box>
      )}

      {panelTab === 1 && (
        <Box>
          <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <SportsEsportsIcon color="primary" /> LitRPG 属性面板与 Royal Road 格式化工坊
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            智能提取 LitRPG / Progression Fantasy 的状态面板（Status Box），自动将其封装为符合 Royal Road 规范的 BBCode [spoiler] 折叠标签，并插入作者说头尾注释。
          </Typography>

          {litrpgError && <Alert severity="error" sx={{ mb: 2 }}>{litrpgError}</Alert>}

          <Box sx={{ mb: 1.5, display: 'flex', gap: 1, flexWrap: 'wrap' }}>
            <Button
              variant="outlined"
              size="small"
              onClick={handleLoadSample}
            >
              📥 {t('platform_load_sample', '填入海外爆款示例')}
            </Button>
          </Box>

          <TextField
            label="章节标题（可选）"
            fullWidth
            size="small"
            sx={{ mb: 1.5 }}
            value={litrpgTitle}
            onChange={(e) => setLitrpgTitle(e.target.value)}
          />

          <TextField
            label="章节正文（含属性面板）"
            multiline
            rows={8}
            fullWidth
            size="small"
            sx={{ mb: 1.5 }}
            value={litrpgText}
            onChange={(e) => setLitrpgText(e.target.value)}
            placeholder="在此输入包含属性面板的正文..."
          />

          <Paper sx={{ p: 1.5, mb: 2, bgcolor: 'action.hover' }}>
            <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 600 }}>
              Royal Road 连载排版参数
            </Typography>
            <Stack spacing={1.5}>
              <TextField
                label="顶部作者说 (Author's Note Top)"
                multiline
                rows={2}
                fullWidth
                size="small"
                value={authorNoteHead}
                onChange={(e) => setAuthorNoteHead(e.target.value)}
                placeholder="例如：Thanks for reading! Updates every Monday and Thursday."
              />
              <TextField
                label="底部作者说 / 呼吁投票 (Author's Note Bottom)"
                multiline
                rows={2}
                fullWidth
                size="small"
                value={authorNoteFoot}
                onChange={(e) => setAuthorNoteFoot(e.target.value)}
                placeholder="例如：Support the story on Patreon for advance chapters. Don't forget to rate!"
              />
              <FormControlLabel
                control={
                  <Checkbox
                    checked={wrapStatBoxes}
                    onChange={(e) => setWrapStatBoxes(e.target.checked)}
                    size="small"
                  />
                }
                label="自动将检测到的属性面板包裹为 [spoiler=&quot;...&quot;] 折叠块（推荐：防止手机端大面积刷屏，极大改善读者留存）"
              />
            </Stack>
          </Paper>

          <Stack direction="row" spacing={2} sx={{ mb: 2 }}>
            <Button
              variant="outlined"
              startIcon={<SearchIcon />}
              onClick={handleParseStatBox}
              disabled={!litrpgText.trim() || parsing || formatting}
            >
              {parsing ? <CircularProgress size={20} /> : t('platform_parse_stat_box', '解析属性面板')}
            </Button>
            <Button
              variant="contained"
              color="primary"
              startIcon={<AutoFixHighIcon />}
              onClick={handleFormatRoyalRoad}
              disabled={!litrpgText.trim() || parsing || formatting}
            >
              {formatting ? <CircularProgress size={20} /> : t('platform_format_royalroad', '⚡ Royal Road 一键排版')}
            </Button>
          </Stack>

          {parsedBoxes !== null && (
            <Paper sx={{ p: 2, mb: 2 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
                  属性面板识别结果
                </Typography>
                <Chip
                  label={`共识别 ${parsedBoxes.length} 个面板`}
                  color={parsedBoxes.length > 0 ? 'success' : 'default'}
                  size="small"
                />
              </Box>
              {parsedBoxes.length === 0 ? (
                <Alert severity="info">
                  未在正文中检测到符合规范的属性面板。支持格式：[Status Window]、ASCII 边框框选、或 【属性面板】。
                </Alert>
              ) : (
                <Stack spacing={1.5}>
                  {parsedBoxes.map((box, i) => (
                    <Paper key={i} variant="outlined" sx={{ p: 1.5, bgcolor: 'background.paper' }}>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1, flexWrap: 'wrap' }}>
                        <Chip label={box.title || 'Status Window'} color="primary" size="small" />
                        <Chip label={`类型: ${box.type}`} variant="outlined" size="small" />
                        <Typography variant="caption" color="text.secondary">
                          位置: 第 {box.start} - {box.end} 字符 ({box.char_count || box.raw_text?.length} 字)
                        </Typography>
                      </Box>
                      {box.fields && Object.keys(box.fields).length > 0 ? (
                        <Box sx={{ display: 'flex', gap: 0.75, flexWrap: 'wrap', mb: 1 }}>
                          {Object.entries(box.fields).map(([k, v]) => (
                            <Chip key={k} label={`${k}: ${v}`} size="small" variant="filled" />
                          ))}
                        </Box>
                      ) : null}
                      <Typography
                        component="pre"
                        sx={{
                          fontFamily: 'monospace',
                          fontSize: '0.8rem',
                          p: 1,
                          bgcolor: 'action.hover',
                          borderRadius: 1,
                          m: 0,
                          whiteSpace: 'pre-wrap',
                        }}
                      >
                        {box.raw_text}
                      </Typography>
                    </Paper>
                  ))}
                </Stack>
              )}
            </Paper>
          )}

          {formattedBBCode && (
            <Paper sx={{ p: 2, mb: 2 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
                    Royal Road BBCode 排版稿
                  </Typography>
                  <Chip label="BBCode 格式" size="small" color="secondary" variant="outlined" />
                </Box>
                <Button
                  variant="outlined"
                  size="small"
                  startIcon={copied ? <CheckCircleOutlineIcon color="success" /> : <ContentCopyIcon />}
                  onClick={() => handleCopy(formattedBBCode)}
                >
                  {copied ? t('platform_copied', '已复制！') : t('platform_copy_code', '复制排版代码')}
                </Button>
              </Box>
              {copied && (
                <Alert severity="success" sx={{ mb: 1.5 }}>
                  排版文本已成功复制到剪贴板，可直接粘贴发布至 Royal Road 章节编辑器！
                </Alert>
              )}
              <Typography
                component="pre"
                sx={{
                  fontFamily: 'monospace',
                  fontSize: '0.85rem',
                  p: 1.5,
                  bgcolor: 'action.selected',
                  borderRadius: 1,
                  m: 0,
                  whiteSpace: 'pre-wrap',
                  maxHeight: 360,
                  overflow: 'auto',
                  border: 1,
                  borderColor: 'divider',
                }}
              >
                {formattedBBCode}
              </Typography>
            </Paper>
          )}
        </Box>
      )}
    </Box>
  )
}
