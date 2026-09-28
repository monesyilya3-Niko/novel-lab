// 命令面板 (Cmd+K)：全局快速跳转与操作。「墨」设计系统 v3。
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import Dialog from '@mui/material/Dialog'
import Box from '@mui/material/Box'
import TextField from '@mui/material/TextField'
import List from '@mui/material/List'
import ListItemButton from '@mui/material/ListItemButton'
import ListItemIcon from '@mui/material/ListItemIcon'
import ListItemText from '@mui/material/ListItemText'
import Typography from '@mui/material/Typography'
import Divider from '@mui/material/Divider'
import InputAdornment from '@mui/material/InputAdornment'
import SearchIcon from '@mui/icons-material/Search'
import HomeIcon from '@mui/icons-material/Home'
import InsightsIcon from '@mui/icons-material/Insights'
import EditNoteIcon from '@mui/icons-material/EditNote'
import FactCheckIcon from '@mui/icons-material/FactCheck'
import FolderOpenIcon from '@mui/icons-material/FolderOpen'
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome'
import TuneIcon from '@mui/icons-material/Tune'
import SettingsIcon from '@mui/icons-material/Settings'
import AdminPanelSettingsIcon from '@mui/icons-material/AdminPanelSettings'
import DarkModeIcon from '@mui/icons-material/DarkMode'
import LightModeIcon from '@mui/icons-material/LightMode'
import { useApp } from '../state/AppContext'
import { useThemeMode } from '../state/ThemeModeContext'
import type { WorkbenchKey } from '../layout/WorkbenchNav'

interface CommandItem {
  id: string
  label: string
  hint?: string
  icon: React.ReactNode
  group: string
  run: () => void
}

const WORKBENCH_META: { key: WorkbenchKey; label: string; icon: React.ReactNode; keywords: string }[] = [
  { key: 'home', label: '首页', icon: <HomeIcon fontSize="small" />, keywords: 'home 首页 概览 dashboard' },
  { key: 'analysis', label: '分析拆书', icon: <InsightsIcon fontSize="small" />, keywords: 'analysis 分析 拆书' },
  { key: 'writing', label: '辅助写作', icon: <EditNoteIcon fontSize="small" />, keywords: 'writing 写作' },
  { key: 'quality', label: '质量检验', icon: <FactCheckIcon fontSize="small" />, keywords: 'quality 质量 检验' },
  { key: 'assets', label: '资产库', icon: <FolderOpenIcon fontSize="small" />, keywords: 'assets 资产' },
  { key: 'advanced', label: '高级功能', icon: <AutoAwesomeIcon fontSize="small" />, keywords: 'advanced 高级' },
  { key: 'system', label: '系统', icon: <TuneIcon fontSize="small" />, keywords: 'system 系统' },
  { key: 'settings', label: '设置', icon: <SettingsIcon fontSize="small" />, keywords: 'settings 设置' },
  { key: 'admin', label: '管理后台', icon: <AdminPanelSettingsIcon fontSize="small" />, keywords: 'admin 管理 后台' },
]

/** 简单模糊匹配：query 的字符按序出现在 target 中 */
function fuzzyMatch(query: string, target: string): boolean {
  const q = query.toLowerCase().replace(/\s+/g, '')
  const t = target.toLowerCase()
  if (!q) return true
  let ti = 0
  for (const ch of q) {
    ti = t.indexOf(ch, ti)
    if (ti === -1) return false
    ti += 1
  }
  return true
}

export default function CommandPalette() {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [activeIndex, setActiveIndex] = useState(0)
  const { setWorkbench } = useApp()
  const { mode, setMode } = useThemeMode()
  const listRef = useRef<HTMLDivElement>(null)

  const items: CommandItem[] = useMemo(() => {
    const list: CommandItem[] = []
    // 工作台跳转
    for (const wb of WORKBENCH_META) {
      list.push({
        id: `wb-${wb.key}`,
        label: `前往${wb.label}`,
        hint: wb.key === 'home' ? 'Alt+1' : undefined,
        icon: wb.icon,
        group: '工作台',
        run: () => setWorkbench(wb.key),
      })
    }
    // 主题切换
    list.push({
      id: 'theme-toggle',
      label: mode === 'dark' ? '切换为亮色模式' : '切换为暗色模式',
      icon: mode === 'dark' ? <LightModeIcon fontSize="small" /> : <DarkModeIcon fontSize="small" />,
      group: '操作',
      run: () => setMode(mode === 'dark' ? 'light' : 'dark'),
    })
    return list
  }, [setWorkbench, mode, setMode])

  const filtered = useMemo(() => {
    if (!query.trim()) return items
    return items.filter((it) =>
      fuzzyMatch(query, `${it.label} ${it.group} ${it.hint ?? ''}`)
    )
  }, [items, query])

  const close = useCallback(() => {
    setOpen(false)
    setQuery('')
    setActiveIndex(0)
  }, [])

  const runItem = useCallback((it: CommandItem) => {
    close()
    // 让 Dialog 关闭动画先跑，再执行跳转
    requestAnimationFrame(() => it.run())
  }, [close])

  // Cmd+K / Ctrl+K 打开
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setOpen((o) => !o)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  // 列表内键盘导航
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'ArrowDown') {
        e.preventDefault()
        setActiveIndex((i) => Math.min(i + 1, filtered.length - 1))
      } else if (e.key === 'ArrowUp') {
        e.preventDefault()
        setActiveIndex((i) => Math.max(i - 1, 0))
      } else if (e.key === 'Enter') {
        e.preventDefault()
        const it = filtered[activeIndex]
        if (it) runItem(it)
      } else if (e.key === 'Escape') {
        e.preventDefault()
        setOpen(false)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, filtered, activeIndex, runItem])

  useEffect(() => {
    setActiveIndex(0)
  }, [query])

  // 滚动到高亮项
  useEffect(() => {
    listRef.current?.querySelector(`[data-index="${activeIndex}"]`)?.scrollIntoView({ block: 'nearest' })
  }, [activeIndex])

  let lastGroup = ''
  return (
    <Dialog
      open={open}
      onClose={close}
      maxWidth="sm"
      fullWidth
      PaperProps={{
        sx: {
          position: 'fixed',
          top: '12vh',
          m: 0,
          borderRadius: 3,
          overflow: 'hidden',
          animation: 'cmdIn 0.18s cubic-bezier(0.2, 0.9, 0.3, 1.2) both',
          '@keyframes cmdIn': {
            from: { opacity: 0, transform: 'translateY(-8px) scale(0.98)' },
            to: { opacity: 1, transform: 'translateY(0) scale(1)' },
          },
        },
      }}
    >
      <Box sx={{ p: 1.5, pb: 0 }}>
        <TextField
          autoFocus
          fullWidth
          placeholder="搜索工作台或操作…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          variant="outlined"
          size="small"
          InputProps={{
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon fontSize="small" sx={{ color: 'text.secondary' }} />
              </InputAdornment>
            ),
            endAdornment: (
              <InputAdornment position="end">
                <Typography
                  variant="caption"
                  sx={{
                    px: 0.75,
                    py: 0.25,
                    borderRadius: 1,
                    bgcolor: 'action.hover',
                    color: 'text.secondary',
                    fontFamily: 'monospace',
                  }}
                >
                  ESC
                </Typography>
              </InputAdornment>
            ),
          }}
          sx={{
            '& .MuiOutlinedInput-root': { borderRadius: 2 },
          }}
        />
      </Box>
      <Box ref={listRef} sx={{ maxHeight: 320, overflowY: 'auto', px: 1.5, pb: 1.5 }}>
        {filtered.length === 0 ? (
          <Typography variant="body2" color="text.secondary" sx={{ py: 4, textAlign: 'center' }}>
            没有匹配的结果
          </Typography>
        ) : (
          <List dense disablePadding>
            {filtered.map((it, idx) => {
              const showGroup = it.group !== lastGroup
              lastGroup = it.group
              const active = idx === activeIndex
              return (
                <Box key={it.id}>
                  {showGroup && (
                    <Typography
                      variant="caption"
                      sx={{ px: 1.5, pt: 1.5, pb: 0.5, display: 'block', color: 'text.secondary', letterSpacing: '0.08em' }}
                    >
                      {it.group}
                    </Typography>
                  )}
                  <ListItemButton
                    data-index={idx}
                    selected={active}
                    onClick={() => runItem(it)}
                    onMouseEnter={() => setActiveIndex(idx)}
                    sx={{
                      borderRadius: 1.5,
                      '&.Mui-selected': {
                        bgcolor: 'action.selected',
                        '&:hover': { bgcolor: 'action.selected' },
                      },
                    }}
                  >
                    <ListItemIcon sx={{ minWidth: 36, color: active ? 'primary.main' : 'text.secondary' }}>
                      {it.icon}
                    </ListItemIcon>
                    <ListItemText
                      primary={it.label}
                      primaryTypographyProps={{ variant: 'body2', fontWeight: active ? 600 : 400 }}
                    />
                    {it.hint && (
                      <Typography variant="caption" color="text.secondary">
                        {it.hint}
                      </Typography>
                    )}
                  </ListItemButton>
                </Box>
              )
            })}
          </List>
        )}
      </Box>
      <Divider />
      <Box sx={{ px: 2, py: 1, display: 'flex', gap: 2 }}>
        {['↑↓ 导航', '↵ 选择', 'esc 关闭'].map((t) => (
          <Typography key={t} variant="caption" color="text.secondary">
            {t}
          </Typography>
        ))}
      </Box>
    </Dialog>
  )
}

/** 命令面板触发按钮（放在 AppBar 上） */
export function CommandPaletteTrigger() {
  const openPalette = () => {
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', metaKey: true, bubbles: true }))
  }
  return (
    <Box
      onClick={openPalette}
      sx={{
        display: { xs: 'none', sm: 'flex' },
        alignItems: 'center',
        gap: 1,
        px: 1.5,
        py: 0.75,
        borderRadius: 2,
        border: '1px solid rgba(255,255,255,0.3)',
        color: 'rgba(255,255,255,0.85)',
        cursor: 'pointer',
        fontSize: 13,
        minWidth: 180,
        '&:hover': { borderColor: 'rgba(255,255,255,0.6)', bgcolor: 'rgba(255,255,255,0.1)' },
      }}
    >
      <SearchIcon fontSize="small" />
      <Box component="span" sx={{ flex: 1 }}>
        搜索…
      </Box>
      <Typography
        variant="caption"
        sx={{ px: 0.75, py: 0.25, borderRadius: 1, bgcolor: 'rgba(255,255,255,0.2)', fontFamily: 'monospace', fontSize: 10 }}
      >
        ⌘K
      </Typography>
    </Box>
  )
}
