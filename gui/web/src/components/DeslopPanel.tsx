// 去 AI 味深度诊断与优化面板（Deslop Diagnostic Panel）
import { useState } from 'react'
import Box from '@mui/material/Box'
import Paper from '@mui/material/Paper'
import Typography from '@mui/material/Typography'
import Button from '@mui/material/Button'
import TextField from '@mui/material/TextField'
import Alert from '@mui/material/Alert'
import Chip from '@mui/material/Chip'
import LinearProgress from '@mui/material/LinearProgress'
import CircularProgress from '@mui/material/CircularProgress'
import Card from '@mui/material/Card'
import CardContent from '@mui/material/CardContent'
import Grid from '@mui/material/Grid'
import AutoFixHighIcon from '@mui/icons-material/AutoFixHigh'
import PsychologyIcon from '@mui/icons-material/Psychology'
import CompareArrowsIcon from '@mui/icons-material/CompareArrows'
import { writingApi, friendlyError, type DeslopResult } from '../api/client'
import { useThemeMode } from '../state/ThemeModeContext'
import { ink, glassCard } from '../ink'
import DiffReviewView from './DiffReviewView'

export default function DeslopPanel() {
  const { isDark } = useThemeMode()
  const [text, setText] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState<DeslopResult | null>(null)
  const [showDiff, setShowDiff] = useState(false)
  const [polishedText, setPolishedText] = useState('')

  const handleAnalyze = async () => {
    if (!text.trim()) {
      setError('请输入需要诊断的章节文本')
      return
    }
    setLoading(true)
    setError('')
    try {
      const res = await writingApi.deslop(text)
      setResult(res)
    } catch (e) {
      setError(`诊断失败: ${friendlyError(e)}`)
    } finally {
      setLoading(false)
    }
  }

  const handleQuickPolishSample = () => {
    if (!text.trim()) return
    // 模拟针对检测到的问题进行规则降噪去 AI 味
    let p = text
    p = p.replace(/这一刻[，,]?(?:时间|空气|呼吸)?仿佛(?:凝固|停止|静止)了?/g, '四周陷入了一片死寂')
    p = p.replace(/天地(?:之间|间)?仿佛只剩(?:下|下了)?/g, '目之所及只剩下')
    p = p.replace(/命运的齿轮(?:在这一刻|开始|悄然)?转动[。！？]?/g, '')
    p = p.replace(/十分愤怒感到生气/g, '攥紧了拳头')
    p = p.replace(/就在这时[，,]?/g, '')
    p = p.replace(/猛然间[，,]?/g, '')
    p = p.replace(/倒吸了一口(?:凉气|冷气)/g, '下意识屏住了呼吸')
    p = p.replace(/瞳孔(?:猛然|剧烈)?收缩/g, '目光骤然一凛')
    p = p.replace(/眼底(?:闪过|掠过)(?:一丝|一抹)?(?:复杂的|冰冷的|凌厉的)?(?:神色|光芒|暗芒)?/g, '眸色微沉')
    p = p.replace(/宛如(?:一[只头尊])?断了线的风筝/g, '整个人倒飞砸落')
    p = p.replace(/(?:不可置否|毋庸置疑|显而易见地?)/g, '')
    p = p.replace(/嘴角(?:微微)?勾起(?:一抹|一丝)?(?:玩味|戏谑|冰冷|嘲讽|残忍|淡淡)?的(?:笑意|弧度|冷笑)/g, '扯了扯嘴角')
    setPolishedText(p)
    setShowDiff(true)
  }

  if (showDiff) {
    return (
      <DiffReviewView
        originalText={text}
        polishedText={polishedText}
        onAccept={(accepted) => {
          setText(accepted)
          setShowDiff(false)
          setResult(null)
        }}
        onReject={() => setShowDiff(false)}
      />
    )
  }

  const scoreColor = (score: number) => {
    if (score < 25) return '#16A34A'
    if (score < 50) return '#D97706'
    return '#DC2626'
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', gap: 2.5 }}>
      {/* 标题说明 */}
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
          <PsychologyIcon sx={{ color: 'primary.main', fontSize: 28 }} />
          <Box>
            <Typography variant="h6" fontWeight={700}>
              去 AI 味全维度诊断与润色
            </Typography>
            <Typography variant="caption" color="text.secondary">
              精准扫描假大空修辞、同义反复、直陈式情绪喊话、机械排比与「让」字被动句
            </Typography>
          </Box>
        </Box>
        {result && (
          <Button
            variant="outlined"
            size="small"
            startIcon={<CompareArrowsIcon />}
            onClick={handleQuickPolishSample}
          >
            一键生成去味稿并对比
          </Button>
        )}
      </Box>

      {error && <Alert severity="error" onClose={() => setError('')}>{error}</Alert>}

      {/* 文本输入区 */}
      <Paper elevation={0} sx={{ p: 2, ...glassCard(isDark) }}>
        <TextField
          multiline
          rows={6}
          fullWidth
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="在此粘贴待检测的章节或片段……（支持万字长文快速诊断）"
          variant="outlined"
          size="small"
          sx={{ mb: 1.5 }}
        />
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Typography variant="caption" color="text.secondary">
            当前字数：{text.length} 字
          </Typography>
          <Box sx={{ display: 'flex', gap: 1 }}>
            <Button
              variant="contained"
              startIcon={loading ? <CircularProgress size={16} color="inherit" /> : <AutoFixHighIcon />}
              onClick={handleAnalyze}
              disabled={loading}
            >
              {loading ? '全维扫描中…' : '开始去 AI 味诊断'}
            </Button>
          </Box>
        </Box>
      </Paper>

      {/* 诊断结果报告 */}
      {result && (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, flex: 1, minHeight: 0, overflow: 'auto' }}>
          {/* 评分总览卡 */}
          <Grid container spacing={2}>
            <Grid item xs={12} md={4}>
              <Card elevation={0} sx={{ height: '100%', ...glassCard(isDark) }}>
                <CardContent sx={{ textAlign: 'center', py: 2.5 }}>
                  <Typography variant="caption" color="text.secondary" fontWeight={600}>
                    AI 味指数（越低越自然）
                  </Typography>
                  <Typography
                    variant="h3"
                    fontWeight={800}
                    sx={{ my: 1, color: scoreColor(result.aiScore) }}
                  >
                    {result.aiScore}
                  </Typography>
                  <Chip
                    label={result.verdictCn}
                    size="small"
                    sx={{
                      bgcolor: `${scoreColor(result.aiScore)}22`,
                      color: scoreColor(result.aiScore),
                      fontWeight: 700,
                    }}
                  />
                  <LinearProgress
                    variant="determinate"
                    value={Math.min(result.aiScore, 100)}
                    sx={{
                      mt: 2,
                      height: 6,
                      borderRadius: 3,
                      bgcolor: isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.06)',
                      '& .MuiLinearProgress-bar': { bgcolor: scoreColor(result.aiScore) },
                    }}
                  />
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={12} md={8}>
              <Card elevation={0} sx={{ height: '100%', ...glassCard(isDark) }}>
                <CardContent sx={{ py: 2 }}>
                  <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 1.5 }}>
                    核心优化建议
                  </Typography>
                  {result.suggestions.length === 0 ? (
                    <Typography variant="body2" color="success.main">
                      ✓ 文风非常自然生动，未检测到典型 AI 模板句式与机械套路！
                    </Typography>
                  ) : (
                    result.suggestions.map((s, idx) => (
                      <Typography key={idx} variant="body2" color="text.secondary" sx={{ mb: 1, display: 'flex', gap: 1 }}>
                        <span style={{ color: '#2563EB', fontWeight: 700 }}>•</span>
                        {s}
                      </Typography>
                    ))
                  )}
                  <Box sx={{ display: 'flex', gap: 3, mt: 2, pt: 1.5, borderTop: `1px solid ${isDark ? ink.nightLine : ink.hairline}` }}>
                    <Typography variant="caption" color="text.secondary">
                      中文字数：<b>{result.stats.wordCount}</b>
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      句子总数：<b>{result.stats.sentenceCount}</b>
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      命中疑点：<b>{result.stats.issuesCount}</b> 处
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      「让」字千字密度：<b>{result.stats.rangDensity}</b>
                    </Typography>
                  </Box>
                </CardContent>
              </Card>
            </Grid>
          </Grid>

          {/* 问题定位清单 */}
          <Paper elevation={0} sx={{ p: 2, ...glassCard(isDark) }}>
            <Typography variant="subtitle2" fontWeight={700} sx={{ mb: 1.5 }}>
              问题定位与逐句优化清单 ({result.issues.length})
            </Typography>
            {result.issues.length === 0 ? (
              <Typography variant="body2" color="text.secondary">未发现需整改的 AI 模板句式</Typography>
            ) : (
              result.issues.map((it, idx) => (
                <Box
                  key={idx}
                  sx={{
                    p: 1.5,
                    mb: 1.2,
                    borderRadius: 1.5,
                    border: `1px solid ${isDark ? ink.nightLine : ink.hairline}`,
                    bgcolor: isDark ? 'rgba(255,255,255,0.02)' : 'rgba(0,0,0,0.01)',
                  }}
                >
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.8 }}>
                    <Chip label={it.label} size="small" color="warning" variant="outlined" />
                    <Typography variant="body2" fontWeight={600} sx={{ color: '#DC2626' }}>
                      “{it.snippet}”
                    </Typography>
                  </Box>
                  <Typography variant="caption" color="text.secondary">
                    💡 优化建议：{it.suggestion}
                  </Typography>
                </Box>
              ))
            )}
          </Paper>
        </Box>
      )}
    </Box>
  )
}
