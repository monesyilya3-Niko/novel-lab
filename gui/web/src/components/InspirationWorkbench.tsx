import { useState, useEffect } from 'react'
import Box from '@mui/material/Box'
import Paper from '@mui/material/Paper'
import Typography from '@mui/material/Typography'
import Button from '@mui/material/Button'
import TextField from '@mui/material/TextField'
import MenuItem from '@mui/material/MenuItem'
import Chip from '@mui/material/Chip'
import Tabs from '@mui/material/Tabs'
import Tab from '@mui/material/Tab'
import Alert from '@mui/material/Alert'
import CircularProgress from '@mui/material/CircularProgress'
import Tooltip from '@mui/material/Tooltip'
import Snackbar from '@mui/material/Snackbar'
import Card from '@mui/material/Card'
import CardContent from '@mui/material/CardContent'
import {
  toolsApi,
  friendlyError,
  type GoldfingerItem,
  type HookItem,
  type ShuangdianItem,
  type WorldSystemItem,
} from '../api/client'

export default function InspirationWorkbench() {
  const [subTab, setSubTab] = useState(0)

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <Paper sx={{ p: 2 }}>
        <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 2 }}>
          <Tabs value={subTab} onChange={(_, v) => setSubTab(v)}>
            <Tab label="起名工坊 (离线智能)" />
            <Tab label="开篇钩子库 (黄金三章)" />
            <Tab label="金手指机制库 (12大外挂)" />
            <Tab label="爽点打脸设计 (三段闭环)" />
            <Tab label="世界观体系 (力量阶梯)" />
          </Tabs>
        </Box>

        {subTab === 0 && <NameGeneratorSection />}
        {subTab === 1 && <HookLibrarySection />}
        {subTab === 2 && <GoldfingerLibrarySection />}
        {subTab === 3 && <ShuangdianLibrarySection />}
        {subTab === 4 && <WorldLibrarySection />}
      </Paper>
    </Box>
  )
}

// ---------------------------------------------------------------------------
// 1. 起名工坊
// ---------------------------------------------------------------------------

function NameGeneratorSection() {
  const [kind, setKind] = useState('character')
  const [style, setStyle] = useState('xianxia')
  const [gender, setGender] = useState('all')
  const [count, setCount] = useState(12)
  const [names, setNames] = useState<string[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [copied, setCopied] = useState('')

  const handleGenerate = async () => {
    setLoading(true)
    setError('')
    try {
      const res = await toolsApi.generateNames({ kind, style, gender, count })
      setNames(res.names || [])
    } catch (e) {
      setError(friendlyError(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    handleGenerate()
  }, [])

  const copyName = (name: string) => {
    navigator.clipboard.writeText(name)
    setCopied(`已复制: ${name}`)
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <Typography variant="body2" color="text.secondary">
        纯本地离线起名算法：自动结合古典意象与现代网感，规避烂大街套路名（如林动、萧炎式流水线），点击药丸直接复制到剪贴板。
      </Typography>

      <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', alignItems: 'center' }}>
        <TextField
          select
          size="small"
          label="生成类别"
          value={kind}
          onChange={(e) => setKind(e.target.value)}
          sx={{ minWidth: 140 }}
        >
          <MenuItem value="character">人物角色</MenuItem>
          <MenuItem value="sect">宗门 / 仙门</MenuItem>
          <MenuItem value="corp">集团 / 财阀</MenuItem>
          <MenuItem value="team">电竞 / 战队</MenuItem>
          <MenuItem value="shelter">末世 / 避难所</MenuItem>
          <MenuItem value="org">怪谈 / 收容机构</MenuItem>
          <MenuItem value="skill">功法 / 战技</MenuItem>
          <MenuItem value="artifact">神兵 / 法宝</MenuItem>
        </TextField>

        {kind === 'character' && (
          <>
            <TextField
              select
              size="small"
              label="题材风格"
              value={style}
              onChange={(e) => setStyle(e.target.value)}
              sx={{ minWidth: 140 }}
            >
              <MenuItem value="xianxia">仙侠古典</MenuItem>
              <MenuItem value="dushi">都市现代</MenuItem>
              <MenuItem value="kehuan">科幻末世</MenuItem>
              <MenuItem value="lishi">历史争霸</MenuItem>
              <MenuItem value="wuxia">传统武侠</MenuItem>
            </TextField>

            <TextField
              select
              size="small"
              label="角色性别"
              value={gender}
              onChange={(e) => setGender(e.target.value)}
              sx={{ minWidth: 110 }}
            >
              <MenuItem value="all">通用 / 随机</MenuItem>
              <MenuItem value="male">男性</MenuItem>
              <MenuItem value="female">女性</MenuItem>
              <MenuItem value="neutral">中性 / 出尘</MenuItem>
            </TextField>
          </>
        )}

        <TextField
          select
          size="small"
          label="生成数量"
          value={count}
          onChange={(e) => setCount(Number(e.target.value))}
          sx={{ minWidth: 100 }}
        >
          <MenuItem value={6}>6 个</MenuItem>
          <MenuItem value={12}>12 个</MenuItem>
          <MenuItem value={24}>24 个</MenuItem>
          <MenuItem value={36}>36 个</MenuItem>
        </TextField>

        <Button
          variant="contained"
          onClick={handleGenerate}
          disabled={loading}
          sx={{ height: 40 }}
        >
          {loading ? <CircularProgress size={20} /> : '换一批 (离线随机)'}
        </Button>
      </Box>

      {error && <Alert severity="error">{error}</Alert>}

      <Paper variant="outlined" sx={{ p: 2, minHeight: 120 }}>
        {names.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            暂无生成结果，请点击「换一批」生成。
          </Typography>
        ) : (
          <Box sx={{ display: 'flex', gap: 1.5, flexWrap: 'wrap' }}>
            {names.map((n) => (
              <Tooltip key={n} title="点击复制到剪贴板">
                <Chip
                  label={n}
                  clickable
                  onClick={() => copyName(n)}
                  color="primary"
                  variant="outlined"
                  sx={{
                    fontSize: '0.95rem',
                    px: 1,
                    py: 2,
                    fontWeight: 500,
                    '&:hover': { bgcolor: 'action.hover' },
                  }}
                />
              </Tooltip>
            ))}
          </Box>
        )}
      </Paper>

      <Snackbar
        open={Boolean(copied)}
        autoHideDuration={2000}
        onClose={() => setCopied('')}
        message={copied}
      />
    </Box>
  )
}

// ---------------------------------------------------------------------------
// 2. 开篇钩子库
// ---------------------------------------------------------------------------

function HookLibrarySection() {
  const [hooks, setHooks] = useState<HookItem[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [copied, setCopied] = useState('')

  useEffect(() => {
    setLoading(true)
    toolsApi
      .getHooks()
      .then((res) => {
        setHooks(res.hooks || [])
      })
      .catch((e) => setError(friendlyError(e)))
      .finally(() => setLoading(false))
  }, [])

  const copyText = (txt: string, tip: string) => {
    navigator.clipboard.writeText(txt)
    setCopied(`已复制: ${tip}`)
  }

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
        黄金三章节奏拍点公式库：精选 10 款经实战检验的起步钩子，点击卡片右上角可直接复制前三章节奏模板。
      </Typography>

      {error && <Alert severity="error">{error}</Alert>}

      <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))', gap: 2 }}>
        {hooks.map((h) => (
          <Card key={h.id} variant="outlined" sx={{ display: 'flex', flexDirection: 'column' }}>
            <CardContent sx={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 1 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Typography variant="subtitle1" fontWeight={700}>
                  {h.name}
                </Typography>
                <Chip size="small" label={h.genre} color="secondary" />
              </Box>

              <Typography variant="caption" color="primary.main" fontWeight={600}>
                前 300 字切入：
              </Typography>
              <Typography variant="body2" sx={{ bgcolor: 'action.hover', p: 1, borderRadius: 1 }}>
                {h.first300Words}
              </Typography>

              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5, mt: 1 }}>
                <Typography variant="caption" color="text.secondary">
                  <strong>第 1 章钩子：</strong> {h.chapter1Beat}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  <strong>第 2 章反转：</strong> {h.chapter2Beat}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  <strong>第 3 章高潮：</strong> {h.chapter3Beat}
                </Typography>
              </Box>

              <Box sx={{ mt: 'auto', pt: 1, display: 'flex', justifyContent: 'flex-end' }}>
                <Button
                  size="small"
                  variant="outlined"
                  onClick={() =>
                    copyText(
                      `【${h.name}】\n切入：${h.first300Words}\n第1章：${h.chapter1Beat}\n第2章：${h.chapter2Beat}\n第3章：${h.chapter3Beat}`,
                      h.name
                    )
                  }
                >
                  复制本套三章细纲
                </Button>
              </Box>
            </CardContent>
          </Card>
        ))}
      </Box>

      <Snackbar
        open={Boolean(copied)}
        autoHideDuration={2000}
        onClose={() => setCopied('')}
        message={copied}
      />
    </Box>
  )
}

// ---------------------------------------------------------------------------
// 3. 金手指机制库
// ---------------------------------------------------------------------------

function GoldfingerLibrarySection() {
  const [goldfingers, setGoldfingers] = useState<GoldfingerItem[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [copied, setCopied] = useState('')

  useEffect(() => {
    setLoading(true)
    toolsApi
      .getGoldfingers()
      .then((res) => {
        setGoldfingers(res.goldfingers || [])
      })
      .catch((e) => setError(friendlyError(e)))
      .finally(() => setLoading(false))
  }, [])

  const copyText = (txt: string, tip: string) => {
    navigator.clipboard.writeText(txt)
    setCopied(`已复制: ${tip}`)
  }

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
        12 大经典外挂设定库：包含触发机制、成长曲线、使用限制与防战力崩坏铁律，帮助设定有代偿、有深度、不廉价的核心金手指。
      </Typography>

      {error && <Alert severity="error">{error}</Alert>}

      <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))', gap: 2 }}>
        {goldfingers.map((g) => (
          <Card key={g.id} variant="outlined" sx={{ display: 'flex', flexDirection: 'column' }}>
            <CardContent sx={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 1 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Typography variant="subtitle1" fontWeight={700}>
                  {g.name}
                </Typography>
                <Chip size="small" label={g.category} color="info" />
              </Box>

              <Typography variant="caption" color="text.secondary">
                <strong>触发机制：</strong> {g.triggerMechanism}
              </Typography>

              <Typography variant="caption" color="text.secondary">
                <strong>成长曲线：</strong> {g.progressionCurve}
              </Typography>

              <Typography variant="caption" color="warning.main">
                <strong>代价与限制：</strong> {g.costAndLimits?.join('； ')}
              </Typography>

              <Typography variant="caption" color="error.main">
                <strong>防崩盘铁律：</strong> {g.antiCollapseRule}
              </Typography>

              <Box sx={{ mt: 'auto', pt: 1, display: 'flex', justifyContent: 'flex-end' }}>
                <Button
                  size="small"
                  variant="outlined"
                  onClick={() =>
                    copyText(
                      `【${g.name}】\n分类：${g.category}\n触发：${g.triggerMechanism}\n成长：${g.progressionCurve}\n限制：${g.costAndLimits?.join('；')}\n防崩规则：${g.antiCollapseRule}`,
                      g.name
                    )
                  }
                >
                  复制金手指设定
                </Button>
              </Box>
            </CardContent>
          </Card>
        ))}
      </Box>

      <Snackbar
        open={Boolean(copied)}
        autoHideDuration={2000}
        onClose={() => setCopied('')}
        message={copied}
      />
    </Box>
  )
}

// ---------------------------------------------------------------------------
// 4. 爽点打脸设计库
// ---------------------------------------------------------------------------

function ShuangdianLibrarySection() {
  const [shuangdians, setShuangdians] = useState<ShuangdianItem[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [copied, setCopied] = useState('')

  useEffect(() => {
    setLoading(true)
    toolsApi
      .getShuangdians()
      .then((res) => {
        setShuangdians(res.shuangdians || [])
      })
      .catch((e) => setError(friendlyError(e)))
      .finally(() => setLoading(false))
  }, [])

  const copyText = (txt: string, tip: string) => {
    navigator.clipboard.writeText(txt)
    setCopied(`已复制: ${tip}`)
  }

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
        网文爽点与打脸逆袭闭环设计库：覆盖 12 大成熟爽点模式，包含三段式闭环（压抑-蓄势-释放）、打脸四拍（嘲讽-沉默-碾压-围观）及升级防疲劳链。
      </Typography>

      {error && <Alert severity="error">{error}</Alert>}

      <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))', gap: 2 }}>
        {shuangdians.map((s) => (
          <Card key={s.id} variant="outlined" sx={{ display: 'flex', flexDirection: 'column' }}>
            <CardContent sx={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 1 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Typography variant="subtitle1" fontWeight={700}>
                  {s.name}
                </Typography>
                <Chip size="small" label={s.category} color="warning" />
              </Box>

              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                <Typography variant="caption" color="error.main">
                  <strong>【压抑前奏】</strong> {s.suppression}
                </Typography>
                <Typography variant="caption" color="primary.main">
                  <strong>【暗中蓄势】</strong> {s.buildUp}
                </Typography>
              </Box>

              <Box sx={{ bgcolor: 'action.hover', p: 1, borderRadius: 1, display: 'flex', flexDirection: 'column', gap: 0.5, mt: 0.5 }}>
                <Typography variant="caption" fontWeight={600} color="text.secondary">
                  打脸四拍执行节拍：
                </Typography>
                <Typography variant="caption">{s.mockery}</Typography>
                <Typography variant="caption">{s.silence}</Typography>
                <Typography variant="caption" fontWeight={600} color="error.dark">{s.crush}</Typography>
                <Typography variant="caption" color="text.secondary">{s.spectators}</Typography>
              </Box>

              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5, mt: 0.5 }}>
                <Typography variant="caption" color="text.secondary">
                  <strong>升级路径：</strong> {s.upgradePath}
                </Typography>
                <Typography variant="caption" color="info.main">
                  <strong>防疲劳提示：</strong> {s.antiFatigueTip}
                </Typography>
              </Box>

              <Box sx={{ mt: 'auto', pt: 1, display: 'flex', justifyContent: 'flex-end' }}>
                <Button
                  size="small"
                  variant="outlined"
                  onClick={() =>
                    copyText(
                      `【${s.name}】（${s.category}）\n压抑：${s.suppression}\n蓄势：${s.buildUp}\n四拍执行：\n- ${s.mockery}\n- ${s.silence}\n- ${s.crush}\n- ${s.spectators}\n升级路径：${s.upgradePath}\n防疲劳提示：${s.antiFatigueTip}`,
                      s.name
                    )
                  }
                >
                  复制本套爽点模型
                </Button>
              </Box>
            </CardContent>
          </Card>
        ))}
      </Box>

      <Snackbar
        open={Boolean(copied)}
        autoHideDuration={2000}
        onClose={() => setCopied('')}
        message={copied}
      />
    </Box>
  )
}

// ---------------------------------------------------------------------------
// 5. 世界观与力量体系库
// ---------------------------------------------------------------------------

function WorldLibrarySection() {
  const [worlds, setWorlds] = useState<WorldSystemItem[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [copied, setCopied] = useState('')

  useEffect(() => {
    setLoading(true)
    toolsApi
      .getWorlds()
      .then((res) => {
        setWorlds(res.worlds || [])
      })
      .catch((e) => setError(friendlyError(e)))
      .finally(() => setLoading(false))
  }, [])

  const copyText = (txt: string, tip: string) => {
    navigator.clipboard.writeText(txt)
    setCopied(`已复制: ${tip}`)
  }

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
        多题材世界观与力量体系设定库：包含清晰境界阶梯、三大不可违背法则铁律、货币资源兑换链及战力防崩红线。
      </Typography>

      {error && <Alert severity="error">{error}</Alert>}

      <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(420px, 1fr))', gap: 2 }}>
        {worlds.map((w) => (
          <Card key={w.id} variant="outlined" sx={{ display: 'flex', flexDirection: 'column' }}>
            <CardContent sx={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 1 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Typography variant="subtitle1" fontWeight={700}>
                  {w.name}
                </Typography>
                <Chip size="small" label={w.genre} color="success" />
              </Box>

              <Typography variant="caption" fontWeight={600} color="primary.main">
                境界进阶阶梯：
              </Typography>
              <Box sx={{ bgcolor: 'action.hover', p: 1, borderRadius: 1, display: 'flex', flexDirection: 'column', gap: 0.5, maxHeight: 180, overflowY: 'auto' }}>
                {w.tierLadder?.map((t, idx) => (
                  <Box key={idx} sx={{ borderBottom: idx < w.tierLadder.length - 1 ? '1px dashed rgba(0,0,0,0.1)' : 'none', pb: 0.5 }}>
                    <Typography variant="caption" fontWeight={700} color="text.primary">
                      {t.tier}
                    </Typography>
                    <Typography variant="caption" display="block" color="text.secondary">
                      能力：{t.powerDesc}
                    </Typography>
                    <Typography variant="caption" display="block" color="warning.main">
                      代价：{t.breakthroughCost}
                    </Typography>
                  </Box>
                ))}
              </Box>

              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5, mt: 0.5 }}>
                <Typography variant="caption" fontWeight={600} color="error.main">
                  法则铁律：
                </Typography>
                {w.ironRules?.map((rule, idx) => (
                  <Typography key={idx} variant="caption" color="text.secondary">
                    • {rule}
                  </Typography>
                ))}
              </Box>

              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                <Typography variant="caption" color="text.secondary">
                  <strong>货币与资源：</strong> {w.currencyAndResources}
                </Typography>
                <Typography variant="caption" color="error.dark">
                  <strong>防崩红线：</strong> {w.powerCollapseWarning}
                </Typography>
              </Box>

              <Box sx={{ mt: 'auto', pt: 1, display: 'flex', justifyContent: 'flex-end' }}>
                <Button
                  size="small"
                  variant="outlined"
                  onClick={() => {
                    const tiersStr = w.tierLadder?.map((t) => `${t.tier}: ${t.powerDesc} (晋阶: ${t.breakthroughCost})`).join('\n') || ''
                    const rulesStr = w.ironRules?.join('\n') || ''
                    copyText(
                      `【${w.name}】（${w.genre}）\n境界阶梯：\n${tiersStr}\n法则铁律：\n${rulesStr}\n货币资源：${w.currencyAndResources}\n防崩红线：${w.powerCollapseWarning}`,
                      w.name
                    )
                  }}
                >
                  复制世界观设定
                </Button>
              </Box>
            </CardContent>
          </Card>
        ))}
      </Box>

      <Snackbar
        open={Boolean(copied)}
        autoHideDuration={2000}
        onClose={() => setCopied('')}
        message={copied}
      />
    </Box>
  )
}
