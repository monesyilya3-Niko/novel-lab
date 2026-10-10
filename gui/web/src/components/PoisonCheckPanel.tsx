import { useState, useEffect } from 'react'
import Box from '@mui/material/Box'
import Paper from '@mui/material/Paper'
import Typography from '@mui/material/Typography'
import Button from '@mui/material/Button'
import TextField from '@mui/material/TextField'
import Chip from '@mui/material/Chip'
import Tabs from '@mui/material/Tabs'
import Tab from '@mui/material/Tab'
import Alert from '@mui/material/Alert'
import CircularProgress from '@mui/material/CircularProgress'
import Card from '@mui/material/Card'
import CardContent from '@mui/material/CardContent'
import Divider from '@mui/material/Divider'
import {
  toolsApi,
  friendlyError,
  type PoisonCheckResult,
  type TabooItem,
} from '../api/client'

export default function PoisonCheckPanel() {
  const [subTab, setSubTab] = useState(0)

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <Paper sx={{ p: 2 }}>
        <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 2 }}>
          <Tabs value={subTab} onChange={(_, v) => setSubTab(v)}>
            <Tab label="毒点快速排查 (本地规则)" />
            <Tab label="弃坑避雷规范库 (10大红线)" />
          </Tabs>
        </Box>

        {subTab === 0 && <PoisonScannerSection />}
        {subTab === 1 && <TabooLibrarySection />}
      </Paper>
    </Box>
  )
}

// ---------------------------------------------------------------------------
// 1. 毒点快速排查
// ---------------------------------------------------------------------------

function PoisonScannerSection() {
  const [text, setText] = useState('')
  const [result, setResult] = useState<PoisonCheckResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleScan = async () => {
    if (!text.trim()) {
      setError('请输入或粘贴需要排查的正文段落')
      return
    }
    setLoading(true)
    setError('')
    try {
      const res = await toolsApi.checkPoison(text)
      setResult(res)
    } catch (e) {
      setError(friendlyError(e))
    } finally {
      setLoading(false)
    }
  }

  const getSeverityChip = (severity: string) => {
    switch (severity) {
      case 'fatal':
        return <Chip size="small" label="致命毒点" color="error" />
      case 'critical':
        return <Chip size="small" label="严重预警" color="warning" />
      case 'high':
        return <Chip size="small" label="中度注意" color="info" />
      default:
        return <Chip size="small" label={severity} />
    }
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <Typography variant="body2" color="text.secondary">
        基于商业网文大数据提炼的纯本地 7 大核心毒点检测器（过度憋屈、圣母资敌、降智舔狗、战力断崖、长篇说教、女配白送、绿帽擦边）。不消耗大模型 Token，零网络延迟。
      </Typography>

      <TextField
        multiline
        rows={8}
        fullWidth
        placeholder="请在此粘贴需要检测的章节正文或剧情草稿..."
        value={text}
        onChange={(e) => setText(e.target.value)}
      />

      <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
        <Button
          variant="contained"
          color="primary"
          onClick={handleScan}
          disabled={loading}
          sx={{ height: 40, px: 3 }}
        >
          {loading ? <CircularProgress size={20} /> : '一键扫描毒点'}
        </Button>
        <Button
          variant="outlined"
          onClick={() => {
            setText('')
            setResult(null)
          }}
          disabled={loading}
        >
          清空
        </Button>
      </Box>

      {error && <Alert severity="error">{error}</Alert>}

      {result && (
        <Paper variant="outlined" sx={{ p: 2, mt: 1, display: 'flex', flexDirection: 'column', gap: 2 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 1 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
              <Typography variant="h6" fontWeight={700}>
                检测结果：
              </Typography>
              <Chip
                label={result.verdict}
                color={result.score === 0 ? 'success' : result.score < 30 ? 'warning' : 'error'}
                sx={{ fontWeight: 600 }}
              />
            </Box>
            <Typography variant="body2" color="text.secondary">
              毒点扣分值：<strong>{result.score}</strong> 分（0分最佳） | 检出问题：<strong>{result.totalIssues}</strong> 处
            </Typography>
          </Box>

          <Divider />

          {result.findings.length === 0 ? (
            <Alert severity="success">
              干得漂亮！本段正文未命中任何已知的恶性毒点或降智情节，行文节奏舒畅。
            </Alert>
          ) : (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
              <Typography variant="subtitle2" color="text.secondary">
                检出问题清单与修改建议：
              </Typography>
              {result.findings.map((item, idx) => (
                <Card key={idx} variant="outlined" sx={{ bgcolor: 'background.default' }}>
                  <CardContent sx={{ display: 'flex', flexDirection: 'column', gap: 1, py: 1.5, '&:last-child': { pb: 1.5 } }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
                      <Chip size="small" label={`第 ${item.line} 行`} />
                      <Typography variant="subtitle2" fontWeight={700}>
                        {item.typeName}
                      </Typography>
                      {getSeverityChip(item.severity)}
                      <Typography variant="caption" sx={{ ml: 'auto', bgcolor: 'action.hover', px: 1, py: 0.5, borderRadius: 1 }}>
                        命中关键词：{item.matched}
                      </Typography>
                    </Box>

                    <Typography variant="body2" sx={{ bgcolor: 'action.selected', p: 1, borderRadius: 1, fontStyle: 'italic' }}>
                      “...{item.snippet}...”
                    </Typography>

                    <Typography variant="caption" color="text.secondary">
                      <strong>【读者痛点】</strong> {item.reason}
                    </Typography>

                    <Typography variant="caption" color="success.main" fontWeight={600}>
                      <strong>【修改建议】</strong> {item.suggestion}
                    </Typography>
                  </CardContent>
                </Card>
              ))}
            </Box>
          )}
        </Paper>
      )}
    </Box>
  )
}

// ---------------------------------------------------------------------------
// 2. 弃坑避雷规范库
// ---------------------------------------------------------------------------

function TabooLibrarySection() {
  const [taboos, setTaboos] = useState<TabooItem[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    setLoading(true)
    toolsApi
      .getTaboos()
      .then((res) => {
        setTaboos(res.taboos || [])
      })
      .catch((e) => setError(friendlyError(e)))
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
        <CircularProgress />
      </Box>
    )
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <Typography variant="body2" color="text.secondary">
        数百万商业读者验证的 10 大弃坑毒点红线清单。下笔前对照自检，避免因为一处剧情瑕疵引发书评区差评暴动。
      </Typography>

      {error && <Alert severity="error">{error}</Alert>}

      <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))', gap: 2 }}>
        {taboos.map((t) => (
          <Card key={t.id} variant="outlined" sx={{ display: 'flex', flexDirection: 'column' }}>
            <CardContent sx={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 1 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Typography variant="subtitle1" fontWeight={700}>
                  {t.name}
                </Typography>
                <Chip
                  size="small"
                  label={t.severity === 'fatal' ? '绝对红线' : '高危警报'}
                  color={t.severity === 'fatal' ? 'error' : 'warning'}
                />
              </Box>

              <Typography variant="caption" color="text.primary">
                <strong>现象描述：</strong> {t.description}
              </Typography>

              <Typography variant="caption" color="error.main">
                <strong>读者反应：</strong> {t.readerReaction}
              </Typography>

              <Box sx={{ mt: 'auto', pt: 1, bgcolor: 'action.hover', p: 1, borderRadius: 1 }}>
                <Typography variant="caption" color="success.main" fontWeight={600}>
                  <strong>【避雷指南】</strong> {t.fixSuggestion}
                </Typography>
              </Box>
            </CardContent>
          </Card>
        ))}
      </Box>
    </Box>
  )
}
