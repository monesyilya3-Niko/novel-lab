// ChapterEditor：章节正文编辑器（基于 Tiptap，设计灵感来自 steven-tey/novel，Apache-2.0）。
// 定位：比 textarea 更干净的中文长文编辑面，带实时字数统计与占位提示。
// 数据契约：value/onChange 均为纯文本（后端只收纯文本），编辑器内部富文本状态不外泄。
import { useState, useEffect } from 'react'
import Box from '@mui/material/Box'
import Typography from '@mui/material/Typography'
import Button from '@mui/material/Button'
import Chip from '@mui/material/Chip'
import Dialog from '@mui/material/Dialog'
import DialogTitle from '@mui/material/DialogTitle'
import DialogContent from '@mui/material/DialogContent'
import DialogActions from '@mui/material/DialogActions'
import CircularProgress from '@mui/material/CircularProgress'
import Alert from '@mui/material/Alert'
import Card from '@mui/material/Card'
import CardContent from '@mui/material/CardContent'
import { useEditor, EditorContent } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import CharacterCount from '@tiptap/extension-character-count'
import Placeholder from '@tiptap/extension-placeholder'
import { ink } from '../ink'
import { useI18n } from '../state/I18nContext'
import {
  toolsApi,
  writingApi,
  essenceApi,
  friendlyError,
  type PoisonCheckResult,
  type DeslopResult,
  type ConstitutionCheckResult,
} from '../api/client'

interface ChapterEditorProps {
  value: string
  onChange: (text: string) => void
  placeholder?: string
  minHeight?: number
  /** 字数目标（如 1500），达到后显示达标提示 */
  targetChars?: number
  /** 是否启用底栏快捷毒点排查（默认启用） */
  enablePoisonCheck?: boolean
  /** 是否启用底栏快捷去 AI 味体检（默认启用） */
  enableDeslopCheck?: boolean
  /** 是否启用底栏快捷设定与宪法审查（默认启用） */
  enableConstitutionCheck?: boolean
  constitutionRules?: any[]
  charactersForbidden?: Record<string, string[]>
}

/** 纯文本 → 编辑器初始 HTML（转义 + 换行分段）。 */
function textToHtml(text: string): string {
  return `<p>${text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\n/g, '</p><p>')}</p>`
}

export default function ChapterEditor({
  value,
  onChange,
  placeholder,
  minHeight = 160,
  targetChars,
  enablePoisonCheck = true,
  enableDeslopCheck = true,
  enableConstitutionCheck = true,
  constitutionRules,
  charactersForbidden,
}: ChapterEditorProps) {
  const { t } = useI18n()
  const effectivePlaceholder = placeholder ?? t('editor_placeholder', '在此粘贴或编写章节正文……')

  const [poisonOpen, setPoisonOpen] = useState(false)
  const [poisonLoading, setPoisonLoading] = useState(false)
  const [poisonResult, setPoisonResult] = useState<PoisonCheckResult | null>(null)
  const [poisonError, setPoisonError] = useState('')

  const [deslopOpen, setDeslopOpen] = useState(false)
  const [deslopLoading, setDeslopLoading] = useState(false)
  const [deslopResult, setDeslopResult] = useState<DeslopResult | null>(null)
  const [deslopError, setDeslopError] = useState('')

  const [constitutionOpen, setConstitutionOpen] = useState(false)
  const [constitutionLoading, setConstitutionLoading] = useState(false)
  const [constitutionResult, setConstitutionResult] = useState<ConstitutionCheckResult | null>(null)
  const [constitutionError, setConstitutionError] = useState('')

  const editor = useEditor({
    extensions: [
      // 纯文本模式：只保留段落与换行，关闭加粗/标题等 mark，避免"排了版却存不下来"的误会。
      StarterKit.configure({
        bold: false,
        italic: false,
        strike: false,
        code: false,
        codeBlock: false,
        heading: false,
        blockquote: false,
        bulletList: false,
        orderedList: false,
        listItem: false,
        horizontalRule: false,
        dropcursor: false,
        gapcursor: false,
      }),
      CharacterCount,
      Placeholder.configure({ placeholder: effectivePlaceholder }),
    ],
    content: value ? textToHtml(value) : '',
    editorProps: {
      attributes: {
        style: `min-height: ${minHeight}px; outline: none; font-size: 14px; line-height: 1.9; color: ${ink.text};`,
      },
    },
    onUpdate: ({ editor }) => {
      onChange(editor.getText())
    },
  })

  // 外部 value 变化时同步回编辑器（清空或载入新文本都同步；getText 对比防循环）。
  useEffect(() => {
    if (editor && editor.getText() !== value) {
      if (value === '') {
        editor.commands.clearContent()
      } else {
        editor.commands.setContent(textToHtml(value))
      }
    }
  }, [value, editor])

  const handleQuickPoisonCheck = async () => {
    const text = editor?.getText() || value
    if (!text.trim()) {
      setPoisonError('正文为空，请先编写章节内容')
      setPoisonResult(null)
      setPoisonOpen(true)
      return
    }
    setPoisonLoading(true)
    setPoisonError('')
    setPoisonOpen(true)
    try {
      const res = await toolsApi.checkPoison(text)
      setPoisonResult(res)
    } catch (e) {
      setPoisonError(friendlyError(e))
    } finally {
      setPoisonLoading(false)
    }
  }

  const handleQuickDeslopCheck = async () => {
    const text = editor?.getText() || value
    if (!text.trim()) {
      setDeslopError('正文为空，请先编写章节内容')
      setDeslopResult(null)
      setDeslopOpen(true)
      return
    }
    setDeslopLoading(true)
    setDeslopError('')
    setDeslopOpen(true)
    try {
      const res = await writingApi.deslop(text)
      setDeslopResult(res)
    } catch (e) {
      setDeslopError(friendlyError(e))
    } finally {
      setDeslopLoading(false)
    }
  }

  const handleQuickConstitutionCheck = async () => {
    const text = editor?.getText() || value
    if (!text.trim()) {
      setConstitutionError('正文为空，请先编写章节内容')
      setConstitutionResult(null)
      setConstitutionOpen(true)
      return
    }
    setConstitutionLoading(true)
    setConstitutionError('')
    setConstitutionOpen(true)
    try {
      const res = await essenceApi.checkConstitution({
        text,
        rules: constitutionRules,
        characters_forbidden: charactersForbidden,
      })
      setConstitutionResult(res)
    } catch (e) {
      setConstitutionError(friendlyError(e))
    } finally {
      setConstitutionLoading(false)
    }
  }

  const chars = editor?.storage.characterCount.characters() ?? value.length
  const targetMet = targetChars != null && chars >= targetChars

  return (
    <Box
      sx={{
        border: `1px solid ${ink.hairline}`,
        borderRadius: 2,
        backgroundColor: ink.surface,
        '& .tiptap p': { margin: '0 0 0.9em 0' },
        '& .tiptap p.is-editor-empty:first-child::before': {
          content: 'attr(data-placeholder)',
          color: ink.textTertiary,
          float: 'left',
          height: 0,
          pointerEvents: 'none',
        },
        '&:focus-within': { borderColor: ink.accent },
      }}
    >
      <Box sx={{ px: 1.5, py: 1 }}>
        <EditorContent editor={editor} />
      </Box>
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: 1,
          px: 1.5,
          py: 0.75,
          borderTop: `1px solid ${ink.hairline}`,
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
          {enablePoisonCheck && (
            <Button
              size="small"
              variant="text"
              onClick={handleQuickPoisonCheck}
              sx={{
                fontSize: '0.78rem',
                color: ink.textSecondary,
                p: 0,
                minWidth: 'auto',
                '&:hover': { color: ink.accent },
              }}
            >
              {t('editor_poison_check', '🛡️ 毒点避雷排查')}
            </Button>
          )}
          {enableDeslopCheck && (
            <Button
              size="small"
              variant="text"
              onClick={handleQuickDeslopCheck}
              sx={{
                fontSize: '0.78rem',
                color: ink.textSecondary,
                p: 0,
                minWidth: 'auto',
                '&:hover': { color: ink.accent },
              }}
            >
              {t('editor_deslop_check', '✨ 去AI味体检')}
            </Button>
          )}
          {enableConstitutionCheck && (
            <Button
              size="small"
              variant="text"
              onClick={handleQuickConstitutionCheck}
              sx={{
                fontSize: '0.78rem',
                color: ink.textSecondary,
                p: 0,
                minWidth: 'auto',
                '&:hover': { color: ink.accent },
              }}
            >
              {t('editor_constitution_check', '📜 设定宪法审查')}
            </Button>
          )}
        </Box>

        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          {targetChars != null && (
            <Typography variant="caption" sx={{ color: targetMet ? ink.success : ink.textTertiary }}>
              {targetMet
                ? `${t('editor_target_met', '已达目标')} ${targetChars} ${t('editor_word_unit', '字')}`
                : `${t('editor_target_prefix', '目标')} ${targetChars} ${t('editor_word_unit', '字')}`}
            </Typography>
          )}
          <Typography variant="caption" sx={{ color: ink.textTertiary }}>
            {chars} {t('editor_word_unit', '字')}
          </Typography>
        </Box>
      </Box>

      {/* 快捷毒点诊断弹窗 */}
      <Dialog
        open={poisonOpen}
        onClose={() => setPoisonOpen(false)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', pb: 1 }}>
          <Typography component="span" variant="h6" fontWeight={700}>
            🛡️ 章节毒点排查诊断
          </Typography>
          {poisonResult && (
            <Chip
              size="small"
              label={poisonResult.verdict}
              color={poisonResult.score === 0 ? 'success' : poisonResult.score < 30 ? 'warning' : 'error'}
            />
          )}
        </DialogTitle>
        <DialogContent dividers sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
          {poisonLoading && (
            <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
              <CircularProgress size={32} />
            </Box>
          )}

          {poisonError && <Alert severity="error">{poisonError}</Alert>}

          {poisonResult && !poisonLoading && (
            <>
              {poisonResult.findings.length === 0 ? (
                <Alert severity="success">
                  本章未命中任何已知的过度憋屈、圣母资敌、降智舔狗、战力断崖等恶性弃坑毒点，行文节奏舒畅！
                </Alert>
              ) : (
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                  <Typography variant="caption" color="text.secondary">
                    检出 <strong>{poisonResult.totalIssues}</strong> 处潜在风险（扣分：{poisonResult.score}）：
                  </Typography>
                  {poisonResult.findings.map((f, i) => (
                    <Card key={i} variant="outlined" sx={{ bgcolor: 'action.hover' }}>
                      <CardContent sx={{ py: 1, '&:last-child': { pb: 1 } }}>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                          <Chip size="small" label={`第 ${f.line} 行`} />
                          <Typography variant="subtitle2" fontWeight={700}>
                            {f.typeName}
                          </Typography>
                          <Typography variant="caption" color="text.secondary" sx={{ ml: 'auto' }}>
                            命中：{f.matched}
                          </Typography>
                        </Box>
                        <Typography variant="caption" color="text.primary" display="block">
                          “...{f.snippet}... ”
                        </Typography>
                        <Typography variant="caption" color="success.main" display="block" sx={{ mt: 0.5, fontWeight: 600 }}>
                          【改法建议】 {f.suggestion}
                        </Typography>
                      </CardContent>
                    </Card>
                  ))}
                </Box>
              )}
            </>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setPoisonOpen(false)}>{t('editor_close_return', '关闭并返回写作')}</Button>
        </DialogActions>
      </Dialog>

      {/* 快捷去 AI 味诊断弹窗 */}
      <Dialog
        open={deslopOpen}
        onClose={() => setDeslopOpen(false)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', pb: 1 }}>
          <Typography component="span" variant="h6" fontWeight={700}>
            ✨ 章节去 AI 味诊断
          </Typography>
          {deslopResult && (
            <Chip
              size="small"
              label={`AI 指数: ${deslopResult.aiScore.toFixed(1)} (${deslopResult.verdictCn})`}
              color={deslopResult.aiScore < 15 ? 'success' : deslopResult.aiScore < 35 ? 'warning' : 'error'}
            />
          )}
        </DialogTitle>
        <DialogContent dividers sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
          {deslopLoading && (
            <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
              <CircularProgress size={32} />
            </Box>
          )}

          {deslopError && <Alert severity="error">{deslopError}</Alert>}

          {deslopResult && !deslopLoading && (
            <>
              {deslopResult.issues.length === 0 ? (
                <Alert severity="success">
                  正文行文极其自然，未检测到任何程式化套路、玄虚比喻、无由排比或俗套口癖！
                </Alert>
              ) : (
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                  <Typography variant="caption" color="text.secondary">
                    检出 <strong>{deslopResult.stats.issuesCount}</strong> 处模式化套路（总字数：{deslopResult.stats.wordCount}，总句数：{deslopResult.stats.sentenceCount}，被动句让字密度：{deslopResult.stats.rangDensity.toFixed(1)}‰）：
                  </Typography>
                  {deslopResult.issues.map((it, i) => (
                    <Card key={i} variant="outlined" sx={{ bgcolor: 'action.hover' }}>
                      <CardContent sx={{ py: 1, '&:last-child': { pb: 1 } }}>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                          <Chip size="small" label={it.label} color="warning" />
                          <Typography variant="caption" color="text.secondary" sx={{ ml: 'auto' }}>
                            扣分权重：{it.weight}
                          </Typography>
                        </Box>
                        <Typography variant="caption" color="text.primary" display="block">
                          “...{it.snippet}...”
                        </Typography>
                        <Typography variant="caption" color="info.main" display="block" sx={{ mt: 0.5, fontWeight: 600 }}>
                          【优化建议】 {it.suggestion}
                        </Typography>
                      </CardContent>
                    </Card>
                  ))}
                </Box>
              )}
            </>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeslopOpen(false)}>{t('editor_close_return', '关闭并返回写作')}</Button>
        </DialogActions>
      </Dialog>

      {/* 快捷设定与世界观宪法审查弹窗 */}
      <Dialog
        open={constitutionOpen}
        onClose={() => setConstitutionOpen(false)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', pb: 1 }}>
          <Typography component="span" variant="h6" fontWeight={700}>
            📜 章节设定与世界观宪法审查
          </Typography>
          {constitutionResult && (
            <Chip
              size="small"
              label={`合规得分: ${constitutionResult.compliance_score} (${constitutionResult.is_compliant ? '正典合规' : '存在违宪风险'})`}
              color={constitutionResult.is_compliant ? 'success' : constitutionResult.compliance_score >= 60 ? 'warning' : 'error'}
            />
          )}
        </DialogTitle>
        <DialogContent dividers sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
          {constitutionLoading && (
            <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
              <CircularProgress size={32} />
            </Box>
          )}

          {constitutionError && <Alert severity="error">{constitutionError}</Alert>}

          {constitutionResult && !constitutionLoading && (
            <>
              {constitutionResult.violations.length === 0 && constitutionResult.character_voice_alerts.length === 0 ? (
                <Alert severity="success">
                  {constitutionResult.summary || '全章设定完美合规，未触碰世界观红线，角色声线与行为严丝合缝！'}
                </Alert>
              ) : (
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
                  <Typography variant="caption" color="text.secondary">
                    {constitutionResult.summary}
                  </Typography>

                  {/* 世界观与违禁规则违纪项 */}
                  {constitutionResult.violations.length > 0 && (
                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                      <Typography variant="subtitle2" sx={{ fontWeight: 600, color: ink.accent, display: 'flex', alignItems: 'center', gap: 0.5 }}>
                        🚫 世界观违宪项 ({constitutionResult.violations.length})
                      </Typography>
                      {constitutionResult.violations.map((v, i) => (
                        <Card key={i} variant="outlined" sx={{ bgcolor: 'action.hover' }}>
                          <CardContent sx={{ py: 1, '&:last-child': { pb: 1 } }}>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                              <Chip
                                size="small"
                                label={v.rule_name}
                                color={v.severity === 'high' ? 'error' : 'warning'}
                              />
                              <Typography variant="caption" sx={{ fontWeight: 600 }}>
                                命中禁用词：【{v.matched_term}】（第 {v.line_no} 行）
                              </Typography>
                            </Box>
                            <Typography variant="caption" color="text.primary" display="block">
                              {v.snippet}
                            </Typography>
                          </CardContent>
                        </Card>
                      ))}
                    </Box>
                  )}

                  {/* 角色声线脱缰警告 */}
                  {constitutionResult.character_voice_alerts.length > 0 && (
                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1, mt: 1 }}>
                      <Typography variant="subtitle2" sx={{ fontWeight: 600, color: 'warning.main', display: 'flex', alignItems: 'center', gap: 0.5 }}>
                        🎭 角色声线脱缰警报 ({constitutionResult.character_voice_alerts.length})
                      </Typography>
                      {constitutionResult.character_voice_alerts.map((ca, i) => (
                        <Card key={i} variant="outlined" sx={{ bgcolor: 'action.hover' }}>
                          <CardContent sx={{ py: 1, '&:last-child': { pb: 1 } }}>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                              <Chip size="small" label={`角色: ${ca.character}`} color="info" />
                              <Typography variant="caption" color="error" sx={{ fontWeight: 600 }}>
                                说了禁说台词：【{ca.forbidden_phrase}】（第 {ca.line_no} 行）
                              </Typography>
                            </Box>
                            <Typography variant="caption" color="text.primary" display="block">
                              “{ca.snippet}”
                            </Typography>
                          </CardContent>
                        </Card>
                      ))}
                    </Box>
                  )}
                </Box>
              )}
            </>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConstitutionOpen(false)}>{t('editor_close_return', '关闭并返回写作')}</Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}
