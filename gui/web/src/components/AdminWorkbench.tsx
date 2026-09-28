// 管理员系统工作台：登录门禁 / 仪表盘 / 书库管理 / 资产管理 / 操作日志 / 安全设置。
import { useState, useEffect, useCallback } from 'react'
import Box from '@mui/material/Box'
import Tabs from '@mui/material/Tabs'
import Tab from '@mui/material/Tab'
import Typography from '@mui/material/Typography'
import Button from '@mui/material/Button'
import Paper from '@mui/material/Paper'
import Alert from '@mui/material/Alert'
import CircularProgress from '@mui/material/CircularProgress'
import Chip from '@mui/material/Chip'
import Table from '@mui/material/Table'
import TableBody from '@mui/material/TableBody'
import TableCell from '@mui/material/TableCell'
import TableHead from '@mui/material/TableHead'
import TableRow from '@mui/material/TableRow'
import TextField from '@mui/material/TextField'
import Dialog from '@mui/material/Dialog'
import DialogTitle from '@mui/material/DialogTitle'
import DialogContent from '@mui/material/DialogContent'
import DialogContentText from '@mui/material/DialogContentText'
import DialogActions from '@mui/material/DialogActions'
import Grid from '@mui/material/Grid'
import Card from '@mui/material/Card'
import CardContent from '@mui/material/CardContent'
import Select from '@mui/material/Select'
import MenuItem from '@mui/material/MenuItem'
import FormControl from '@mui/material/FormControl'
import InputLabel from '@mui/material/InputLabel'
import LogoutIcon from '@mui/icons-material/Logout'
import {
  adminApi,
  friendlyError,
  onAdminUnauthorized,
  ApiError,
  type AdminDashboard,
  type AdminBookSummary,
  type AdminAuditEntry,
  type AdminSession,
} from '../api/client'
import { ink, fontStack, fadeUp } from '../ink'
import LockOutlinedIcon from '@mui/icons-material/LockOutlined'

function fmtSize(bytes: number): string {
  if (!bytes) return '0 B'
  if (bytes > 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`
  if (bytes > 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${bytes} B`
}

function fmtUptime(seconds: number): string {
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  if (h > 0) return `${h} 小时 ${m} 分`
  return `${m} 分钟`
}

export default function AdminWorkbench() {
  const [me, setMe] = useState<{ username: string } | null>(null)
  const [checking, setChecking] = useState(true)
  const [forceChangePw, setForceChangePw] = useState(false)

  const checkMe = useCallback(async () => {
    setChecking(true)
    try {
      const r = await adminApi.me()
      setMe({ username: r.username })
    } catch {
      setMe(null)
    } finally {
      setChecking(false)
    }
  }, [])

  useEffect(() => { checkMe() }, [checkMe])

  // 会话失效（401）自动回登录页
  useEffect(() => {
    onAdminUnauthorized(() => {
      setMe(null)
      setForceChangePw(false)
    })
    return () => onAdminUnauthorized(null)
  }, [])

  if (checking) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
        <CircularProgress />
      </Box>
    )
  }

  if (!me) return <LoginForm onDone={(mustChange) => { checkMe(); if (mustChange) setForceChangePw(true) }} />
  return <AdminPanels username={me.username} onLogout={() => setMe(null)} forceChangePw={forceChangePw} clearForceChangePw={() => setForceChangePw(false)} />
}

// ---------------------------------------------------------------------------
// 登录
// ---------------------------------------------------------------------------

function LoginForm({ onDone }: { onDone: (mustChange: boolean) => void }) {
  const [username, setUsername] = useState('admin')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async () => {
    setError('')
    setBusy(true)
    try {
      const r = await adminApi.login(username.trim(), password)
      onDone(!!r.mustChangePassword)
    } catch (e) {
      setError(friendlyError(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Box sx={{
      display: 'flex', justifyContent: 'center', alignItems: 'center',
      minHeight: '100%', p: 3,
      background: (theme) => theme.palette.mode === 'dark'
        ? `radial-gradient(ellipse 80% 60% at 50% 0%, ${ink.cinnabar}12, transparent)`
        : `radial-gradient(ellipse 80% 60% at 50% 0%, ${ink.cinnabarSoft}, transparent)`,
    }}>
      <Paper sx={{ p: 0, width: 400, overflow: 'hidden', ...fadeUp }}>
        {/* 顶部装饰条 */}
        <Box sx={{
          height: 96,
          background: `linear-gradient(135deg, ${ink.cinnabar} 0%, ${ink.cinnabarDeep} 100%)`,
          display: 'flex', alignItems: 'center', px: 4, gap: 2,
        }}>
          <Box sx={{
            width: 48, height: 48, borderRadius: 3,
            background: 'rgba(255,255,255,0.18)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            backdropFilter: 'blur(4px)',
          }}>
            <LockOutlinedIcon sx={{ color: '#fff', fontSize: 26 }} />
          </Box>
          <Box>
            <Typography variant="h6" sx={{ color: '#fff', fontFamily: fontStack.serif, fontWeight: 700, letterSpacing: '0.1em' }}>
              管理后台
            </Typography>
            <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.75)', letterSpacing: '0.2em' }}>
              ADMIN CONSOLE
            </Typography>
          </Box>
        </Box>
        <Box sx={{ p: 4 }}>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 3, lineHeight: 1.7 }}>
            后台管理仅限本机访问。首次启动的初始密码见服务端控制台日志。
          </Typography>
          {error && <Alert severity="error" sx={{ mb: 2, borderRadius: 2 }}>{error}</Alert>}
          <TextField
            fullWidth label="用户名" value={username} disabled={busy}
            onChange={(e) => setUsername(e.target.value)} sx={{ mb: 2 }}
            autoComplete="username" variant="outlined"
          />
          <TextField
            fullWidth label="密码" type="password" value={password} disabled={busy}
            onChange={(e) => setPassword(e.target.value)} autoComplete="current-password"
            onKeyDown={(e) => { if (e.key === 'Enter') submit() }} sx={{ mb: 3 }}
            variant="outlined"
          />
          <Button
            fullWidth variant="contained" size="large"
            disabled={busy || !password} onClick={submit}
            sx={{ borderRadius: 2.5, py: 1.4, fontSize: 15 }}
          >
            {busy ? '登录中…' : '登 录'}
          </Button>
        </Box>
      </Paper>
    </Box>
  )
}

// ---------------------------------------------------------------------------
// 管理面板
// ---------------------------------------------------------------------------

function AdminPanels({ username, onLogout, forceChangePw, clearForceChangePw }: {
  username: string
  onLogout: () => void
  forceChangePw: boolean
  clearForceChangePw: () => void
}) {
  // 首次登录强制改密：锁定在安全设置页，其他 Tab 禁用
  const [tab, setTab] = useState(forceChangePw ? 5 : 0)
  useEffect(() => { if (forceChangePw) setTab(5) }, [forceChangePw])

  const logout = async () => {
    try { await adminApi.logout() } finally { onLogout() }
  }

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {forceChangePw && (
        <Alert severity="warning" sx={{ borderRadius: 0 }}>
          首次登录请立即修改初始密码，修改完成前其他功能不可用。
        </Alert>
      )}
      <Box sx={{ display: 'flex', alignItems: 'center', borderBottom: 1, borderColor: 'divider', pr: 2 }}>
        <Tabs value={tab} onChange={(_, v) => { if (!forceChangePw) setTab(v) }} sx={{ px: 2, flex: 1 }}>
          <Tab label="仪表盘" disabled={forceChangePw} />
          <Tab label="书库管理" disabled={forceChangePw} />
          <Tab label="资产管理" disabled={forceChangePw} />
          <Tab label="操作日志" disabled={forceChangePw} />
          <Tab label="会话管理" disabled={forceChangePw} />
          <Tab label="安全设置" />
        </Tabs>
        <Chip label={username} size="small" sx={{ mr: 1 }} />
        <Button size="small" startIcon={<LogoutIcon />} onClick={logout}>退出</Button>
      </Box>
      <Box sx={{ flex: 1, overflow: 'auto', p: 2 }}>
        {tab === 0 && <DashboardPanel />}
        {tab === 1 && <BooksPanel />}
        {tab === 2 && <AssetsPanel />}
        {tab === 3 && <AuditPanel />}
        {tab === 4 && <SessionsPanel />}
        {tab === 5 && <SecurityPanel onLogout={onLogout} onPasswordChanged={clearForceChangePw} />}
      </Box>
    </Box>
  )
}

// ---------------------------------------------------------------------------
// 仪表盘
// ---------------------------------------------------------------------------

function DashboardPanel() {
  const [data, setData] = useState<AdminDashboard | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      setData(await adminApi.dashboard())
    } catch (e) {
      setError(friendlyError(e))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  if (loading) return <CircularProgress />
  if (error) return <Alert severity="error">{error}</Alert>
  if (!data) return null

  const cards = [
    { label: '书籍', value: String(data.books.total), sub: data.books.analyzing > 0 ? `${data.books.analyzing} 本分析中` : '全部空闲' },
    { label: '资产', value: String(data.assetsTotal), sub: Object.entries(data.assetsByKind).map(([k, v]) => `${k} ${v}`).join(' · ') || '—' },
    { label: '报告', value: String(data.reportsTotal), sub: '拆书/笔法报告' },
    { label: '数据占用', value: fmtSize(data.diskTotalBytes), sub: `运行 ${fmtUptime(data.uptimeSeconds)}` },
  ]

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h6">系统仪表盘</Typography>
        <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
          <Chip size="small" label={`v${data.version}`} />
          <Chip size="small" label={`Python ${data.python}`} />
          <Button variant="outlined" size="small" onClick={load}>刷新</Button>
        </Box>
      </Box>
      <Grid container spacing={2} sx={{ mb: 2 }}>
        {cards.map((c) => (
          <Grid item xs={6} md={3} key={c.label}>
            <Card>
              <CardContent>
                <Typography variant="caption" color="text.secondary">{c.label}</Typography>
                <Typography variant="h5">{c.value}</Typography>
                <Typography variant="caption" color="text.secondary" noWrap title={c.sub}>{c.sub}</Typography>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>
      <Paper sx={{ p: 2, mb: 2 }}>
        <Typography variant="subtitle2" gutterBottom>磁盘占用</Typography>
        {Object.entries(data.diskBytes).map(([k, v]) => (
          <Box key={k} sx={{ display: 'flex', justifyContent: 'space-between', py: 0.5 }}>
            <Typography variant="body2" color="text.secondary">{k}/</Typography>
            <Typography variant="body2">{fmtSize(v)}</Typography>
          </Box>
        ))}
      </Paper>
      {data.books.items.length > 0 && (
        <Paper sx={{ p: 2, mb: 2 }}>
          <Typography variant="subtitle2" gutterBottom>最近书籍</Typography>
          {data.books.items.map((b) => (
            <Box key={b.bookId} sx={{ display: 'flex', justifyContent: 'space-between', py: 0.5 }}>
              <Typography variant="body2">{b.title}</Typography>
              <Typography variant="body2" color="text.secondary">
                {b.totalChapters} 章 · {b.status}
              </Typography>
            </Box>
          ))}
        </Paper>
      )}
      {data.recentAudit && data.recentAudit.length > 0 && (
        <Paper sx={{ p: 2 }}>
          <Typography variant="subtitle2" gutterBottom>最近操作</Typography>
          {data.recentAudit.map((e, i) => (
            <Box key={i} sx={{ display: 'flex', gap: 1, py: 0.5, alignItems: 'center' }}>
              <Chip size="small" label={e.action} sx={{ maxWidth: 180 }} />
              <Typography variant="body2" color="text.secondary" noWrap sx={{ flex: 1 }} title={e.detail}>
                {e.username} · {e.detail}
              </Typography>
              <Typography variant="caption" color="text.secondary" sx={{ whiteSpace: 'nowrap' }}>{e.ts}</Typography>
            </Box>
          ))}
        </Paper>
      )}
    </Box>
  )
}

// ---------------------------------------------------------------------------
// 书库管理
// ---------------------------------------------------------------------------

function BooksPanel() {
  const [books, setBooks] = useState<AdminBookSummary[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [confirm, setConfirm] = useState<AdminBookSummary | null>(null)
  const [deleting, setDeleting] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      setBooks(await adminApi.books())
    } catch (e) {
      setError(friendlyError(e))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const doDelete = async () => {
    if (!confirm) return
    setDeleting(true)
    try {
      const r = await adminApi.deleteBook(confirm.bookId)
      setNotice(`已删除《${confirm.title}》，清理：${r.removed.join('、')}`)
      setConfirm(null)
      load()
    } catch (e) {
      setError(friendlyError(e))
    } finally {
      setDeleting(false)
    }
  }

  if (loading) return <CircularProgress />

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h6">书库管理（{books.length} 本）</Typography>
        <Button variant="outlined" size="small" onClick={load}>刷新</Button>
      </Box>
      {notice && <Alert severity="success" sx={{ mb: 2 }} onClose={() => setNotice('')}>{notice}</Alert>}
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      <Paper>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>书名</TableCell>
              <TableCell>章节</TableCell>
              <TableCell>状态</TableCell>
              <TableCell align="right">操作</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {books.map((b) => (
              <TableRow key={b.bookId}>
                <TableCell>{b.title}</TableCell>
                <TableCell>{b.totalChapters}</TableCell>
                <TableCell>
                  <Chip size="small" label={b.status}
                    color={b.status === 'analyzing' ? 'warning' : 'default'} />
                </TableCell>
                <TableCell align="right">
                  <Button
                    size="small" color="error"
                    disabled={b.status === 'analyzing'}
                    title={b.status === 'analyzing' ? '分析中的书籍不可删除' : '删除本书全部数据'}
                    onClick={() => setConfirm(b)}
                  >
                    删除
                  </Button>
                </TableCell>
              </TableRow>
            ))}
            {books.length === 0 && (
              <TableRow><TableCell colSpan={4} align="center" sx={{ color: 'text.secondary', py: 3 }}>
                暂无书籍
              </TableCell></TableRow>
            )}
          </TableBody>
        </Table>
      </Paper>
      <Dialog open={!!confirm} onClose={() => setConfirm(null)}>
        <DialogTitle>确认删除</DialogTitle>
        <DialogContent>
          <DialogContentText>
            将彻底删除《{confirm?.title}》的状态文件、原文、分析资产与数据库记录，此操作不可恢复。继续吗？
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setConfirm(null)} disabled={deleting}>取消</Button>
          <Button color="error" onClick={doDelete} disabled={deleting}>
            {deleting ? '删除中…' : '确认删除'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}

// ---------------------------------------------------------------------------
// 资产管理
// ---------------------------------------------------------------------------

const ASSET_KINDS = ['', 'voice_card', 'genre_pack', 'genre_prose_card', 'report']
const ASSET_KIND_LABELS: Record<string, string> = {
  '': '全部',
  voice_card: '笔法卡',
  genre_pack: '题材包',
  genre_prose_card: '笔法卡片',
  report: '报告',
}

function AssetsPanel() {
  const [kind, setKind] = useState('')
  const [items, setItems] = useState<{ id: string; name: string; kind: string }[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const r = await adminApi.assets(kind || undefined)
      setItems((r.items as { id: string; name: string; kind: string }[]) || [])
      setTotal(r.total || 0)
    } catch (e) {
      setError(friendlyError(e))
    } finally {
      setLoading(false)
    }
  }, [kind])

  useEffect(() => { load() }, [load])

  const del = async (itemKind: string, id: string, name: string) => {
    if (!window.confirm(`删除资产「${name}」？（将移入回收站）`)) return
    try {
      await adminApi.deleteAsset(itemKind, id)
      setNotice(`已删除资产「${name}」`)
      load()
    } catch (e) {
      setError(friendlyError(e))
    }
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h6">资产管理（{total}）</Typography>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <FormControl size="small" sx={{ minWidth: 130 }}>
            <InputLabel>类型</InputLabel>
            <Select value={kind} label="类型" onChange={(e) => setKind(e.target.value)}>
              {ASSET_KINDS.map((k) => (
                <MenuItem key={k} value={k}>{ASSET_KIND_LABELS[k]}</MenuItem>
              ))}
            </Select>
          </FormControl>
          <Button variant="outlined" size="small" onClick={load}>刷新</Button>
        </Box>
      </Box>
      {notice && <Alert severity="success" sx={{ mb: 2 }} onClose={() => setNotice('')}>{notice}</Alert>}
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      {loading ? <CircularProgress /> : (
        <Paper>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>名称</TableCell>
                <TableCell>类型</TableCell>
                <TableCell align="right">操作</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {items.map((it) => (
                <TableRow key={it.id}>
                  <TableCell>{it.name}</TableCell>
                  <TableCell>
                    <Chip size="small" label={ASSET_KIND_LABELS[it.kind] || it.kind} />
                  </TableCell>
                  <TableCell align="right">
                    <Button size="small" color="error"
                      onClick={() => del(it.kind, it.id, it.name)}>
                      删除
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
              {items.length === 0 && (
                <TableRow><TableCell colSpan={3} align="center" sx={{ color: 'text.secondary', py: 3 }}>
                  暂无资产
                </TableCell></TableRow>
              )}
            </TableBody>
          </Table>
        </Paper>
      )}
    </Box>
  )
}

// ---------------------------------------------------------------------------
// 操作日志
// ---------------------------------------------------------------------------

function AuditPanel() {
  const [entries, setEntries] = useState<AdminAuditEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [filterAction, setFilterAction] = useState('')
  const [filterUser, setFilterUser] = useState('')
  // 已应用的过滤条件（避免每敲一个字母就发请求）
  const [applied, setApplied] = useState({ action: '', user: '' })

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      setEntries(await adminApi.audit(200, applied.action.trim(), applied.user.trim()))
    } catch (e) {
      setError(friendlyError(e))
    } finally {
      setLoading(false)
    }
  }, [applied])

  useEffect(() => { load() }, [load])

  const applyFilter = () => setApplied({ action: filterAction, user: filterUser })
  const clearFilter = () => {
    setFilterAction(''); setFilterUser('')
    setApplied({ action: '', user: '' })
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h6">操作日志（最近 200 条）</Typography>
        <Button variant="outlined" size="small" onClick={load}>刷新</Button>
      </Box>
      <Box sx={{ display: 'flex', gap: 2, mb: 2 }}>
        <TextField size="small" label="按动作过滤" placeholder="如 admin.login"
          value={filterAction} onChange={e => setFilterAction(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') applyFilter() }} sx={{ width: 220 }} />
        <TextField size="small" label="按用户过滤" placeholder="如 admin"
          value={filterUser} onChange={e => setFilterUser(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') applyFilter() }} sx={{ width: 180 }} />
        <Button variant="outlined" size="small" onClick={applyFilter}>筛选</Button>
        {(applied.action || applied.user) && (
          <Button size="small" onClick={clearFilter}>清除</Button>
        )}
      </Box>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      {loading ? <CircularProgress /> : (
        <Paper>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>时间</TableCell>
                <TableCell>用户</TableCell>
                <TableCell>IP</TableCell>
                <TableCell>动作</TableCell>
                <TableCell>详情</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {entries.map((e, i) => (
                <TableRow key={i}>
                  <TableCell sx={{ whiteSpace: 'nowrap' }}>{e.ts}</TableCell>
                  <TableCell>{e.username}</TableCell>
                  <TableCell>{e.ip}</TableCell>
                  <TableCell><Chip size="small" label={e.action} /></TableCell>
                  <TableCell sx={{ maxWidth: 360, overflow: 'hidden', textOverflow: 'ellipsis' }}
                    title={e.detail}>{e.detail}</TableCell>
                </TableRow>
              ))}
              {entries.length === 0 && (
                <TableRow><TableCell colSpan={5} align="center" sx={{ color: 'text.secondary', py: 3 }}>
                  暂无日志
                </TableCell></TableRow>
              )}
            </TableBody>
          </Table>
        </Paper>
      )}
    </Box>
  )
}

// ---------------------------------------------------------------------------
// 会话管理
// ---------------------------------------------------------------------------

function SessionsPanel() {
  const [sessions, setSessions] = useState<AdminSession[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      setSessions(await adminApi.sessions())
    } catch (e) {
      setError(friendlyError(e))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const revoke = async (id: string, isCurrent: boolean) => {
    if (isCurrent) {
      if (!window.confirm(`这是你当前正在使用的会话！吊销后你将立即被登出。确定继续吗？`)) return
    } else if (!window.confirm(`确定吊销会话 ${id}？该会话将立即失效。`)) {
      return
    }
    try {
      await adminApi.revokeSession(id)
      load()
    } catch (e) {
      setError(friendlyError(e))
    }
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h6">在线会话（{sessions.length}）</Typography>
        <Button variant="outlined" size="small" onClick={load}>刷新</Button>
      </Box>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      {loading ? <CircularProgress /> : (
        <Paper>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>会话 ID（前缀）</TableCell>
                <TableCell>用户</TableCell>
                <TableCell>IP</TableCell>
                <TableCell>创建时间</TableCell>
                <TableCell>过期时间</TableCell>
                <TableCell>操作</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {sessions.map(s => (
                <TableRow key={s.id} sx={s.current ? { backgroundColor: 'action.selected' } : undefined}>
                  <TableCell sx={{ fontFamily: 'monospace' }}>
                    {s.id}
                    {s.current && <Chip size="small" label="当前" color="primary" sx={{ ml: 1 }} />}
                  </TableCell>
                  <TableCell>{s.username}</TableCell>
                  <TableCell>{s.ip}</TableCell>
                  <TableCell sx={{ whiteSpace: 'nowrap' }}>{s.createdAt}</TableCell>
                  <TableCell sx={{ whiteSpace: 'nowrap' }}>{s.expiresAt}</TableCell>
                  <TableCell>
                    <Button size="small" color="warning" onClick={() => revoke(s.id, !!s.current)}>吊销</Button>
                  </TableCell>
                </TableRow>
              ))}
              {sessions.length === 0 && (
                <TableRow><TableCell colSpan={6} align="center" sx={{ color: 'text.secondary', py: 3 }}>
                  无在线会话
                </TableCell></TableRow>
              )}
            </TableBody>
          </Table>
        </Paper>
      )}
    </Box>
  )
}

// ---------------------------------------------------------------------------
// 安全设置
// ---------------------------------------------------------------------------

function SecurityPanel({ onLogout, onPasswordChanged }: {
  onLogout: () => void
  onPasswordChanged?: () => void
}) {
  const [oldPw, setOldPw] = useState('')
  const [newPw, setNewPw] = useState('')
  const [newPw2, setNewPw2] = useState('')
  const [error, setError] = useState('')
  const [ok, setOk] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async () => {
    setError('')
    setOk('')
    if (newPw !== newPw2) { setError('两次输入的新密码不一致'); return }
    if (newPw.length < 8) { setError('新密码至少 8 位'); return }
    setBusy(true)
    try {
      await adminApi.changePassword(oldPw, newPw)
      setOk('密码已修改，历史会话已吊销，请重新登录。')
      setOldPw(''); setNewPw(''); setNewPw2('')
      onPasswordChanged?.()
      setTimeout(onLogout, 1500)
    } catch (e) {
      if (e instanceof ApiError && e.code === 401) {
        // 会话被吊销属于正常流程
        onLogout()
        return
      }
      setError(friendlyError(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Box sx={{ maxWidth: 480 }}>
      <Typography variant="h6" gutterBottom>修改密码</Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        修改后所有已登录会话立即失效，需要重新登录。
      </Typography>
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      {ok && <Alert severity="success" sx={{ mb: 2 }}>{ok}</Alert>}
      <TextField fullWidth label="原密码" type="password" value={oldPw} disabled={busy}
        onChange={(e) => setOldPw(e.target.value)} sx={{ mb: 2 }} autoComplete="current-password" />
      <TextField fullWidth label="新密码（至少 8 位）" type="password" value={newPw} disabled={busy}
        onChange={(e) => setNewPw(e.target.value)} sx={{ mb: 2 }} autoComplete="new-password" />
      <TextField fullWidth label="确认新密码" type="password" value={newPw2} disabled={busy}
        onChange={(e) => setNewPw2(e.target.value)} sx={{ mb: 2 }} autoComplete="new-password"
        onKeyDown={(e) => { if (e.key === 'Enter') submit() }} />
      <Button variant="contained" disabled={busy || !oldPw || !newPw} onClick={submit}>
        {busy ? '提交中…' : '修改密码'}
      </Button>
      <Paper sx={{ p: 2, mt: 3 }}>
        <Typography variant="subtitle2" gutterBottom>安全说明</Typography>
        <Typography variant="body2" color="text.secondary">
          · 密码经 PBKDF2-HMAC-SHA256（20 万轮）加盐哈希存储，服务端不保存明文{'\n'}
          · 会话 Cookie 为 HttpOnly，有效期 12 小时{'\n'}
          · 连续 5 次登录失败将锁定 IP 5 分钟{'\n'}
          · 所有管理操作记入审计日志
        </Typography>
      </Paper>
    </Box>
  )
}
