import { Suspense, lazy, useEffect, useMemo, useState } from 'react'
import { ThemeProvider, createTheme } from '@mui/material/styles'
import useMediaQuery from '@mui/material/useMediaQuery'
import CssBaseline from '@mui/material/CssBaseline'
import Box from '@mui/material/Box'
import Alert from '@mui/material/Alert'
import AppBar from '@mui/material/AppBar'
import Toolbar from '@mui/material/Toolbar'
import IconButton from '@mui/material/IconButton'
import Drawer from '@mui/material/Drawer'
import MenuIcon from '@mui/icons-material/Menu'
import LightModeIcon from '@mui/icons-material/LightMode'
import DarkModeIcon from '@mui/icons-material/DarkMode'
import SettingsBrightnessIcon from '@mui/icons-material/SettingsBrightness'
import Tooltip from '@mui/material/Tooltip'
import Typography from '@mui/material/Typography'
import { AppProvider, useApp } from './state/AppContext'
import { useThemeMode } from './state/ThemeModeContext'
import { buildMuiTheme } from './theme'
import { ink, fontStack } from './ink'
import WorkbenchNav from './layout/WorkbenchNav'
import type { WorkbenchKey } from './layout/WorkbenchNav'
import ErrorBoundary from './components/ErrorBoundary'
import OnboardingWizard, { isOnboarded } from './components/OnboardingWizard'
import CommandPalette, { CommandPaletteTrigger } from './components/CommandPalette'
import WorkbenchTransition from './components/WorkbenchTransition'
import { DashboardSkeleton } from './components/SkeletonBlocks'
import Fab from '@mui/material/Fab'
import HelpOutlineIcon from '@mui/icons-material/HelpOutline'

// 4B：页面级组件 lazy 加载，主包只含框架 + 导航 + 主题
const HomeDashboard = lazy(() => import('./components/HomeDashboard'))
const AnalysisView = lazy(() => import('./components/AnalysisView'))
const AssetLibrary = lazy(() => import('./components/AssetLibrary'))
const WritingWorkbench = lazy(() => import('./components/WritingWorkbench'))
const QualityWorkbench = lazy(() => import('./components/QualityWorkbench'))
const SystemWorkbench = lazy(() => import('./components/SystemWorkbench'))
const AdvancedWorkbench = lazy(() => import('./components/AdvancedWorkbench'))
const SettingsWorkbench = lazy(() => import('./components/SettingsWorkbench'))
const AdminWorkbench = lazy(() => import('./components/AdminWorkbench'))
const HelpWorkbench = lazy(() => import('./components/HelpWorkbench'))

const SIDEBAR_WIDTH = 220

function LoadingFallback() {
  return (
    <Box sx={{ p: 3, height: '100%', overflow: 'auto' }}>
      <DashboardSkeleton />
    </Box>
  )
}

/** 主题循环切换：light → dark → system → light */
function ModeToggle() {
  const { mode, setMode } = useThemeMode()
  const next = mode === 'light' ? 'dark' : mode === 'dark' ? 'system' : 'light'
  const label = next === 'light' ? '切换亮色' : next === 'dark' ? '切换暗色' : '切换为跟随系统'
  return (
    <Tooltip title={label}>
      <IconButton color="inherit" size="small" onClick={() => setMode(next)} aria-label={label}>
        {mode === 'light' ? (
          <LightModeIcon fontSize="small" />
        ) : mode === 'dark' ? (
          <DarkModeIcon fontSize="small" />
        ) : (
          <SettingsBrightnessIcon fontSize="small" />
        )}
      </IconButton>
    </Tooltip>
  )
}

export default function App() {
  const { isDark } = useThemeMode()
  const theme = useMemo(() => createTheme(buildMuiTheme(isDark)), [isDark])
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <AppProvider>
        <AppShell />
      </AppProvider>
    </ThemeProvider>
  )
}

const WORKBENCH_ORDER: WorkbenchKey[] = [
  'home', 'analysis', 'writing', 'quality', 'assets', 'advanced', 'system', 'settings', 'admin', 'help',
]

function AppShell() {
  const { workbench, setWorkbench, overview, initError } = useApp()
  const wide = useMediaQuery('(min-width: 961px)')
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [onboarded, setOnboarded] = useState(isOnboarded)

  // 键盘快捷键：Alt+1..9 切换工作台（输入框聚焦时不劫持）
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!e.altKey || e.ctrlKey || e.metaKey) return
      const n = Number(e.key)
      if (!Number.isInteger(n) || n < 1 || n > WORKBENCH_ORDER.length) return
      const target = e.target as HTMLElement | null
      if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable)) return
      e.preventDefault()
      setWorkbench(WORKBENCH_ORDER[n - 1])
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [setWorkbench])


  const nav = (
    <WorkbenchNav
      active={workbench}
      onChange={(k) => {
        setWorkbench(k)
        setDrawerOpen(false)
      }}
    />
  )

  const showWizard = !!overview && !onboarded && overview.totalBooks === 0 && overview.totalAssets === 0

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      {showWizard && (
        <OnboardingWizard onDone={() => setOnboarded(true)} onNavigate={setWorkbench} />
      )}
      <AppBar position="static" elevation={0} sx={{
        background: (theme) => theme.palette.mode === 'dark'
          ? `linear-gradient(135deg, #2A1414 0%, ${ink.nightCard} 100%)`
          : `linear-gradient(135deg, ${ink.cinnabar} 0%, ${ink.cinnabarDeep} 100%)`,
        borderBottom: (theme) => `1px solid ${theme.palette.mode === 'dark' ? ink.nightLine : 'rgba(0,0,0,0.12)'}`,
      }}>
      {initError && (
        <Alert severity="error" sx={{ borderRadius: 0 }}>
          初始化失败：{initError}
        </Alert>
      )}
        <Toolbar sx={{ minHeight: 56, gap: 1.5, px: { xs: 2, md: 3 } }}>
          {!wide && (
            <IconButton color="inherit" edge="start" onClick={() => setDrawerOpen(true)} aria-label="打开导航" sx={{ color: '#fff' }}>
              <MenuIcon />
            </IconButton>
          )}
          <Box sx={{
            width: 32, height: 32, borderRadius: 2,
            background: 'rgba(255,255,255,0.2)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontFamily: fontStack.serif, fontWeight: 700, color: '#fff', fontSize: 18,
          }}>
            墨
          </Box>
          <Box sx={{ flex: 1 }}>
            <Typography variant="subtitle1" sx={{ color: '#fff', fontFamily: fontStack.serif, fontWeight: 700, letterSpacing: '0.15em', lineHeight: 1.2 }}>
              novel-lab
            </Typography>
            <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.7)', letterSpacing: '0.3em', fontSize: 10 }}>
              全功能工作台
            </Typography>
          </Box>
          <Box sx={{ color: '#fff' }}>
            <ModeToggle />
          </Box>
          <CommandPaletteTrigger />
        </Toolbar>
      </AppBar>

      <Box sx={{ display: 'flex', flex: 1, minHeight: 0 }}>
        {wide ? (
          <Box
            sx={{
              width: SIDEBAR_WIDTH,
              minWidth: SIDEBAR_WIDTH,
              borderRight: '1px solid',
              borderColor: 'divider',
              bgcolor: 'background.paper',
            }}
          >
            {nav}
          </Box>
        ) : (
          <Drawer
            open={drawerOpen}
            onClose={() => setDrawerOpen(false)}
            PaperProps={{ sx: { width: SIDEBAR_WIDTH, bgcolor: 'background.paper' } }}
          >
            {nav}
          </Drawer>
        )}
        <Box sx={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column' }}>
          <Box sx={{ flex: 1, minHeight: 0, overflow: 'hidden' }}>
            <ErrorBoundary>
              <Suspense fallback={<LoadingFallback />}>
                <WorkbenchTransition key={workbench}>
                {workbench === 'home' && <HomeDashboard />}
                {workbench === 'analysis' && <AnalysisView />}
                {workbench === 'assets' && <AssetLibrary />}
                {workbench === 'advanced' && <AdvancedWorkbench />}
                {workbench === 'writing' && <WritingWorkbench />}
                {workbench === 'quality' && <QualityWorkbench />}
                {workbench === 'system' && <SystemWorkbench />}
                {workbench === 'settings' && <SettingsWorkbench />}
                {workbench === 'admin' && <AdminWorkbench />}
                {workbench === 'help' && <HelpWorkbench />}
                </WorkbenchTransition>
              </Suspense>
            </ErrorBoundary>
          </Box>
        </Box>
      </Box>
      <CommandPalette />
      {/* 全局悬浮帮助按钮：任何页面一键进入帮助中心 */}
      {workbench !== 'help' && (
        <Tooltip title="帮助中心：术语、指南、工作流" placement="left">
          <Fab
            size="medium"
            onClick={() => setWorkbench('help')}
            aria-label="打开帮助中心"
            sx={{
              position: 'fixed',
              bottom: 24,
              right: 24,
              bgcolor: ink.primary,
              color: '#fff',
              '&:hover': { bgcolor: ink.primaryDeep },
              zIndex: 1200,
            }}
          >
            <HelpOutlineIcon />
          </Fab>
        </Tooltip>
      )}
    </Box>
  )
}
