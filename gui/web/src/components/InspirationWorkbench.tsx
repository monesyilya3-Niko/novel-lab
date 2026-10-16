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
  type DialogueItem,
  type CharacterPersonaItem,
  type EmotionItem,
} from '../api/client'
import { useI18n } from '../state/I18nContext'

export default function InspirationWorkbench() {
  const { t } = useI18n()
  const [subTab, setSubTab] = useState(0)

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <Paper sx={{ p: 2 }}>
        <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 2 }}>
          <Tabs value={subTab} onChange={(_, v) => setSubTab(v)} variant="scrollable" scrollButtons="auto">
            <Tab label={t('inspiration_tab_name')} />
            <Tab label={t('inspiration_tab_hook')} />
            <Tab label={t('inspiration_tab_goldfinger')} />
            <Tab label={t('inspiration_tab_shuangdian')} />
            <Tab label={t('inspiration_tab_world')} />
            <Tab label={t('inspiration_tab_dialogue')} />
            <Tab label={t('inspiration_tab_character')} />
            <Tab label={t('inspiration_tab_emotion')} />
          </Tabs>
        </Box>

        {subTab === 0 && <NameGeneratorSection />}
        {subTab === 1 && <HookLibrarySection />}
        {subTab === 2 && <GoldfingerLibrarySection />}
        {subTab === 3 && <ShuangdianLibrarySection />}
        {subTab === 4 && <WorldLibrarySection />}
        {subTab === 5 && <DialogueLibrarySection />}
        {subTab === 6 && <CharacterLibrarySection />}
        {subTab === 7 && <EmotionLibrarySection />}
      </Paper>
    </Box>
  )
}

// ---------------------------------------------------------------------------
// 1. 起名工坊
// ---------------------------------------------------------------------------

function NameGeneratorSection() {
  const { t } = useI18n()
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const copyName = (name: string) => {
    navigator.clipboard.writeText(name)
    setCopied(`${t('inspiration_copied_prefix')}${name}`)
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <Typography variant="body2" color="text.secondary">
        {t('inspiration_name_desc')}
      </Typography>

      <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', alignItems: 'center' }}>
        <TextField
          select
          size="small"
          label={t('inspiration_name_kind_label')}
          value={kind}
          onChange={(e) => setKind(e.target.value)}
          sx={{ minWidth: 140 }}
        >
          <MenuItem value="character">{t('inspiration_name_kind_character')}</MenuItem>
          <MenuItem value="title">{t('inspiration_name_kind_title')}</MenuItem>
          <MenuItem value="sect">{t('inspiration_name_kind_sect')}</MenuItem>
          <MenuItem value="corp">{t('inspiration_name_kind_corp')}</MenuItem>
          <MenuItem value="team">{t('inspiration_name_kind_team')}</MenuItem>
          <MenuItem value="shelter">{t('inspiration_name_kind_shelter')}</MenuItem>
          <MenuItem value="org">{t('inspiration_name_kind_org')}</MenuItem>
          <MenuItem value="skill">{t('inspiration_name_kind_skill')}</MenuItem>
          <MenuItem value="artifact">{t('inspiration_name_kind_artifact')}</MenuItem>
        </TextField>

        {kind === 'title' && (
          <TextField
            select
            size="small"
            label={t('inspiration_name_novel_genre')}
            value={style}
            onChange={(e) => setStyle(e.target.value)}
            sx={{ minWidth: 140 }}
          >
            <MenuItem value="xianxia">{t('inspiration_genre_xianxia')}</MenuItem>
            <MenuItem value="dushi">{t('inspiration_genre_dushi')}</MenuItem>
            <MenuItem value="kehuan">{t('inspiration_genre_kehuan')}</MenuItem>
            <MenuItem value="xuanyi">{t('inspiration_genre_xuanyi')}</MenuItem>
            <MenuItem value="duanpian">{t('inspiration_genre_duanpian')}</MenuItem>
          </TextField>
        )}

        {kind === 'character' && (
          <>
            <TextField
              select
              size="small"
              label={t('inspiration_name_style_label')}
              value={style}
              onChange={(e) => setStyle(e.target.value)}
              sx={{ minWidth: 140 }}
            >
              <MenuItem value="xianxia">{t('inspiration_style_xianxia')}</MenuItem>
              <MenuItem value="dushi">{t('inspiration_style_dushi')}</MenuItem>
              <MenuItem value="kehuan">{t('inspiration_style_kehuan')}</MenuItem>
              <MenuItem value="lishi">{t('inspiration_style_lishi')}</MenuItem>
              <MenuItem value="wuxia">{t('inspiration_style_wuxia')}</MenuItem>
            </TextField>

            <TextField
              select
              size="small"
              label={t('inspiration_name_gender_label')}
              value={gender}
              onChange={(e) => setGender(e.target.value)}
              sx={{ minWidth: 110 }}
            >
              <MenuItem value="all">{t('inspiration_gender_all')}</MenuItem>
              <MenuItem value="male">{t('inspiration_gender_male')}</MenuItem>
              <MenuItem value="female">{t('inspiration_gender_female')}</MenuItem>
              <MenuItem value="neutral">{t('inspiration_gender_neutral')}</MenuItem>
            </TextField>
          </>
        )}

        <TextField
          select
          size="small"
          label={t('inspiration_name_count_label')}
          value={count}
          onChange={(e) => setCount(Number(e.target.value))}
          sx={{ minWidth: 100 }}
        >
          <MenuItem value={6}>6 {t('inspiration_count_items')}</MenuItem>
          <MenuItem value={12}>12 {t('inspiration_count_items')}</MenuItem>
          <MenuItem value={24}>24 {t('inspiration_count_items')}</MenuItem>
          <MenuItem value={36}>36 {t('inspiration_count_items')}</MenuItem>
        </TextField>

        <Button
          variant="contained"
          onClick={handleGenerate}
          disabled={loading}
          sx={{ height: 40 }}
        >
          {loading ? <CircularProgress size={20} /> : t('inspiration_name_btn_generate')}
        </Button>
      </Box>

      {error && <Alert severity="error">{error}</Alert>}

      <Paper variant="outlined" sx={{ p: 2, minHeight: 120 }}>
        {names.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            {t('inspiration_name_empty')}
          </Typography>
        ) : (
          <Box sx={{ display: 'flex', gap: 1.5, flexWrap: 'wrap' }}>
            {names.map((n) => (
              <Tooltip key={n} title={t('inspiration_chip_tooltip')}>
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
  const { t } = useI18n()
  const [hooks, setHooks] = useState<HookItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [copied, setCopied] = useState('')

  useEffect(() => {
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
    setCopied(`${t('inspiration_copied_prefix')}${tip}`)
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
        {t('inspiration_hook_desc')}
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
                {t('inspiration_hook_first_300')}
              </Typography>
              <Typography variant="body2" sx={{ bgcolor: 'action.hover', p: 1, borderRadius: 1 }}>
                {h.first300Words}
              </Typography>

              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5, mt: 1 }}>
                <Typography variant="caption" color="text.secondary">
                  <strong>{t('inspiration_hook_ch1')}</strong> {h.chapter1Beat}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  <strong>{t('inspiration_hook_ch2')}</strong> {h.chapter2Beat}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  <strong>{t('inspiration_hook_ch3')}</strong> {h.chapter3Beat}
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
                  {t('inspiration_hook_btn_copy')}
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
  const { t } = useI18n()
  const [goldfingers, setGoldfingers] = useState<GoldfingerItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [copied, setCopied] = useState('')

  useEffect(() => {
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
    setCopied(`${t('inspiration_copied_prefix')}${tip}`)
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
        {t('inspiration_gf_desc')}
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
                <strong>{t('inspiration_gf_trigger')}</strong> {g.triggerMechanism}
              </Typography>

              <Typography variant="caption" color="text.secondary">
                <strong>{t('inspiration_gf_curve')}</strong> {g.progressionCurve}
              </Typography>

              <Typography variant="caption" color="warning.main">
                <strong>{t('inspiration_gf_cost')}</strong> {g.costAndLimits?.join('； ')}
              </Typography>

              <Typography variant="caption" color="error.main">
                <strong>{t('inspiration_gf_anticollapse')}</strong> {g.antiCollapseRule}
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
                  {t('inspiration_gf_btn_copy')}
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
  const { t } = useI18n()
  const [shuangdians, setShuangdians] = useState<ShuangdianItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [copied, setCopied] = useState('')

  useEffect(() => {
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
    setCopied(`${t('inspiration_copied_prefix')}${tip}`)
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
        {t('inspiration_sd_desc')}
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
                  <strong>{t('inspiration_sd_suppression')}</strong> {s.suppression}
                </Typography>
                <Typography variant="caption" color="primary.main">
                  <strong>{t('inspiration_sd_buildup')}</strong> {s.buildUp}
                </Typography>
              </Box>

              <Box sx={{ bgcolor: 'action.hover', p: 1, borderRadius: 1, display: 'flex', flexDirection: 'column', gap: 0.5, mt: 0.5 }}>
                <Typography variant="caption" fontWeight={600} color="text.secondary">
                  {t('inspiration_sd_fourbeats')}
                </Typography>
                <Typography variant="caption">{s.mockery}</Typography>
                <Typography variant="caption">{s.silence}</Typography>
                <Typography variant="caption" fontWeight={600} color="error.dark">{s.crush}</Typography>
                <Typography variant="caption" color="text.secondary">{s.spectators}</Typography>
              </Box>

              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5, mt: 0.5 }}>
                <Typography variant="caption" color="text.secondary">
                  <strong>{t('inspiration_sd_upgradepath')}</strong> {s.upgradePath}
                </Typography>
                <Typography variant="caption" color="info.main">
                  <strong>{t('inspiration_sd_antifatigue')}</strong> {s.antiFatigueTip}
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
                  {t('inspiration_sd_btn_copy')}
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
  const { t } = useI18n()
  const [worlds, setWorlds] = useState<WorldSystemItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [copied, setCopied] = useState('')

  useEffect(() => {
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
    setCopied(`${t('inspiration_copied_prefix')}${tip}`)
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
        {t('inspiration_wd_desc')}
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
                {t('inspiration_wd_ladder')}
              </Typography>
              <Box sx={{ bgcolor: 'action.hover', p: 1, borderRadius: 1, display: 'flex', flexDirection: 'column', gap: 0.5, maxHeight: 180, overflowY: 'auto' }}>
                {w.tierLadder?.map((tItem, idx) => (
                  <Box key={idx} sx={{ borderBottom: idx < w.tierLadder.length - 1 ? '1px dashed rgba(0,0,0,0.1)' : 'none', pb: 0.5 }}>
                    <Typography variant="caption" fontWeight={700} color="text.primary">
                      {tItem.tier}
                    </Typography>
                    <Typography variant="caption" display="block" color="text.secondary">
                      {t('inspiration_wd_power')}{tItem.powerDesc}
                    </Typography>
                    <Typography variant="caption" display="block" color="warning.main">
                      {t('inspiration_wd_cost')}{tItem.breakthroughCost}
                    </Typography>
                  </Box>
                ))}
              </Box>

              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5, mt: 0.5 }}>
                <Typography variant="caption" fontWeight={600} color="error.main">
                  {t('inspiration_wd_ironrules')}
                </Typography>
                {w.ironRules?.map((rule, idx) => (
                  <Typography key={idx} variant="caption" color="text.secondary">
                    • {rule}
                  </Typography>
                ))}
              </Box>

              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                <Typography variant="caption" color="text.secondary">
                  <strong>{t('inspiration_wd_currency')}</strong> {w.currencyAndResources}
                </Typography>
                <Typography variant="caption" color="error.dark">
                  <strong>{t('inspiration_wd_collapsewarning')}</strong> {w.powerCollapseWarning}
                </Typography>
              </Box>

              <Box sx={{ mt: 'auto', pt: 1, display: 'flex', justifyContent: 'flex-end' }}>
                <Button
                  size="small"
                  variant="outlined"
                  onClick={() => {
                    const tiersStr = w.tierLadder?.map((tItem) => `${tItem.tier}: ${tItem.powerDesc} (晋阶: ${tItem.breakthroughCost})`).join('\n') || ''
                    const rulesStr = w.ironRules?.join('\n') || ''
                    copyText(
                      `【${w.name}】（${w.genre}）\n境界阶梯：\n${tiersStr}\n法则铁律：\n${rulesStr}\n货币资源：${w.currencyAndResources}\n防崩红线：${w.powerCollapseWarning}`,
                      w.name
                    )
                  }}
                >
                  {t('inspiration_wd_btn_copy')}
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
// 6. 名场面台词库
// ---------------------------------------------------------------------------

function DialogueLibrarySection() {
  const { t } = useI18n()
  const [dialogues, setDialogues] = useState<DialogueItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [copied, setCopied] = useState('')

  useEffect(() => {
    toolsApi
      .getDialogues()
      .then((res) => {
        setDialogues(res.dialogues || [])
      })
      .catch((e) => setError(friendlyError(e)))
      .finally(() => setLoading(false))
  }, [])

  const copyText = (txt: string, tip: string) => {
    navigator.clipboard.writeText(txt)
    setCopied(`${t('inspiration_copied_prefix')}${tip}`)
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
        {t('inspiration_dlg_desc')}
      </Typography>

      {error && <Alert severity="error">{error}</Alert>}

      <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(380px, 1fr))', gap: 2 }}>
        {dialogues.map((d) => (
          <Card key={d.id} variant="outlined" sx={{ display: 'flex', flexDirection: 'column' }}>
            <CardContent sx={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 1 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Typography variant="subtitle1" fontWeight={700}>
                  {d.name}
                </Typography>
                <Chip size="small" label={d.category} color="secondary" />
              </Box>

              <Box sx={{ bgcolor: 'error.50', borderLeft: 3, borderColor: 'error.main', p: 1, borderRadius: '0 4px 4px 0' }}>
                <Typography variant="caption" color="error.dark" fontWeight={700} display="block">
                  {t('inspiration_dlg_ai_bad')}
                </Typography>
                <Typography variant="caption" color="text.secondary" sx={{ textDecoration: 'line-through' }}>
                  {d.aiSlopBad}
                </Typography>
              </Box>

              <Box sx={{ bgcolor: 'success.50', borderLeft: 3, borderColor: 'success.main', p: 1, borderRadius: '0 4px 4px 0' }}>
                <Typography variant="caption" color="success.dark" fontWeight={700} display="block">
                  {t('inspiration_dlg_human_good')}
                </Typography>
                <Typography variant="body2" fontWeight={700} color="text.primary">
                  {d.humanGood}
                </Typography>
              </Box>

              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5, mt: 0.5 }}>
                <Typography variant="caption" color="text.secondary">
                  <strong>{t('inspiration_dlg_subtext')}</strong> {d.subtext}
                </Typography>
                <Typography variant="caption" color="primary.main">
                  <strong>{t('inspiration_dlg_actions')}</strong> {d.actionBeats}
                </Typography>
                <Typography variant="caption" color="info.main">
                  <strong>{t('inspiration_dlg_speechtip')}</strong> {d.speechProfileTip}
                </Typography>
              </Box>

              <Box sx={{ mt: 'auto', pt: 1, display: 'flex', justifyContent: 'flex-end' }}>
                <Button
                  size="small"
                  variant="outlined"
                  onClick={() =>
                    copyText(
                      `台词：${d.humanGood}\n动作节拍：${d.actionBeats}\n（潜台词：${d.subtext}）`,
                      d.name
                    )
                  }
                >
                  {t('inspiration_dlg_btn_copy')}
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
// 7. 爆款人设反差矩阵与人物高光弧光库
// ---------------------------------------------------------------------------

function CharacterLibrarySection() {
  const { t } = useI18n()
  const [characters, setCharacters] = useState<CharacterPersonaItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [copied, setCopied] = useState('')

  useEffect(() => {
    toolsApi
      .getCharacters()
      .then((res) => {
        setCharacters(res.characters || [])
      })
      .catch((e) => setError(friendlyError(e)))
      .finally(() => setLoading(false))
  }, [])

  const copyCharacter = (c: CharacterPersonaItem) => {
    const text = `【角色模型】：${c.name}（${c.roleType} · ${c.genre}）\n【表面标签】：${c.surfaceMask}\n【隐藏反差】：${c.hiddenContrast}\n【核心欲望】：${c.coreMotivation}\n【致命弱点】：${c.fatalFlaw}\n【防崩铁律】：${c.antiCollapseRule}\n【高光口头禅】：${c.catchphrase}\n【成长弧光】：${c.arcProgression}`
    navigator.clipboard.writeText(text)
    setCopied(`${t('inspiration_chr_copied_card')}${c.name}`)
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
        {t('inspiration_chr_desc')}
      </Typography>

      {error && <Alert severity="error">{error}</Alert>}

      <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(380px, 1fr))', gap: 2 }}>
        {characters.map((c) => (
          <Card key={c.id} variant="outlined" sx={{ display: 'flex', flexDirection: 'column' }}>
            <CardContent sx={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 1 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Typography variant="subtitle1" fontWeight={700}>
                  {c.name}
                </Typography>
                <Box sx={{ display: 'flex', gap: 0.5 }}>
                  <Chip size="small" label={c.roleType} color="primary" />
                  <Chip size="small" label={c.genre} variant="outlined" />
                </Box>
              </Box>

              <Box sx={{ bgcolor: 'action.hover', p: 1, borderRadius: 1 }}>
                <Typography variant="caption" color="text.secondary" display="block">
                  <strong>{t('inspiration_chr_surface')}</strong> {c.surfaceMask}
                </Typography>
                <Typography variant="caption" color="secondary.main" display="block" sx={{ mt: 0.5, fontWeight: 600 }}>
                  <strong>{t('inspiration_chr_contrast')}</strong> {c.hiddenContrast}
                </Typography>
              </Box>

              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                <Typography variant="caption" color="text.primary">
                  <strong>{t('inspiration_chr_desire')}</strong> {c.coreMotivation}
                </Typography>
                <Typography variant="caption" color="warning.main">
                  <strong>{t('inspiration_chr_flaw')}</strong> {c.fatalFlaw}
                </Typography>
                <Typography variant="caption" color="error.main">
                  <strong>{t('inspiration_chr_anticollapse')}</strong> {c.antiCollapseRule}
                </Typography>
                <Typography variant="caption" color="info.main">
                  <strong>{t('inspiration_chr_action')}</strong> {c.catchphrase}
                </Typography>
                <Typography variant="caption" color="success.main">
                  <strong>{t('inspiration_chr_arc')}</strong> {c.arcProgression}
                </Typography>
              </Box>

              <Box sx={{ mt: 'auto', pt: 1, display: 'flex', justifyContent: 'flex-end' }}>
                <Button size="small" variant="outlined" onClick={() => copyCharacter(c)}>
                  {t('inspiration_chr_btn_copy')}
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
// 8. 情绪高潮演出与五感通感描写库
// ---------------------------------------------------------------------------

function EmotionLibrarySection() {
  const { t } = useI18n()
  const [emotions, setEmotions] = useState<EmotionItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [copied, setCopied] = useState('')

  useEffect(() => {
    toolsApi
      .getEmotions()
      .then((res) => {
        setEmotions(res.emotions || [])
      })
      .catch((e) => setError(friendlyError(e)))
      .finally(() => setLoading(false))
  }, [])

  const copyProse = (e: EmotionItem) => {
    const text = `【高潮演出】：${e.emotionScene}\n【正文范例】：\n${e.masterProseSample}\n【五感细节】：\n视觉：${e.sensoryBreakdown.vision}\n生理：${e.sensoryBreakdown.physiology}\n触觉：${e.sensoryBreakdown.touchAndTemp}\n听觉：${e.sensoryBreakdown.soundAndSilence}\n环境：${e.environmentalResonance}\n【节拍秘籍】：${e.writingRhythmTip}`
    navigator.clipboard.writeText(text)
    setCopied(`${t('inspiration_emt_copied_scene')}${e.emotionScene}`)
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
        {t('inspiration_emt_desc')}
      </Typography>

      {error && <Alert severity="error">{error}</Alert>}

      <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(380px, 1fr))', gap: 2 }}>
        {emotions.map((e) => (
          <Card key={e.id} variant="outlined" sx={{ display: 'flex', flexDirection: 'column' }}>
            <CardContent sx={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 1 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Typography variant="subtitle1" fontWeight={700}>
                  {e.emotionScene}
                </Typography>
                <Chip size="small" label={e.category} color="secondary" />
              </Box>

              <Box sx={{ bgcolor: 'error.50', borderLeft: 3, borderColor: 'error.main', p: 1, borderRadius: '0 4px 4px 0' }}>
                <Typography variant="caption" color="error.dark" fontWeight={700} display="block">
                  {t('inspiration_dlg_ai_bad')}
                </Typography>
                <Typography variant="caption" color="text.secondary" sx={{ textDecoration: 'line-through' }}>
                  {e.aiClicheExample}
                </Typography>
              </Box>

              <Box sx={{ bgcolor: 'success.50', borderLeft: 3, borderColor: 'success.main', p: 1, borderRadius: '0 4px 4px 0' }}>
                <Typography variant="caption" color="success.dark" fontWeight={700} display="block">
                  {t('inspiration_emt_human_good')}
                </Typography>
                <Typography variant="body2" fontWeight={500} color="text.primary">
                  {e.masterProseSample}
                </Typography>
              </Box>

              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5, mt: 0.5 }}>
                <Typography variant="caption" color="text.secondary">
                  <strong>{t('inspiration_emt_vision')}</strong> {e.sensoryBreakdown.vision}
                </Typography>
                <Typography variant="caption" color="primary.main">
                  <strong>{t('inspiration_emt_physio')}</strong> {e.sensoryBreakdown.physiology}
                </Typography>
                <Typography variant="caption" color="info.main">
                  <strong>{t('inspiration_emt_touch')}</strong> {e.sensoryBreakdown.touchAndTemp}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  <strong>{t('inspiration_emt_sound')}</strong> {e.sensoryBreakdown.soundAndSilence}
                </Typography>
                <Typography variant="caption" color="warning.main">
                  <strong>{t('inspiration_emt_env')}</strong> {e.environmentalResonance}
                </Typography>
                <Typography variant="caption" color="success.main" sx={{ fontWeight: 600 }}>
                  <strong>{t('inspiration_emt_rhythm')}</strong> {e.writingRhythmTip}
                </Typography>
              </Box>

              <Box sx={{ mt: 'auto', pt: 1, display: 'flex', justifyContent: 'flex-end' }}>
                <Button size="small" variant="outlined" onClick={() => copyProse(e)}>
                  {t('inspiration_emt_btn_copy')}
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
