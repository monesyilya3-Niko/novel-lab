import { Suspense, lazy, useMemo, useState } from 'react'
import { ThemeProvider, createTheme } from '@mui/material/styles'
import useMediaQuery from '@mui/material/useMediaQuery'
import CssBaseline from '@mui/material/CssBaseline'
import Box from '@mui/material/Box'
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
import CircularProgress from '@mui/material/CircularProgress'
import { AppProvider, useApp } from './state/AppContext'
import { useThemeMode } from './state/ThemeModeContext'
import { buildMuiTheme } from './theme'
import WorkbenchNav from './layout/WorkbenchNav'
import ErrorBoundary from './components/ErrorBoundary'
import OnboardingWizard, { isOnboarded } from './components/OnboardingWizard'

// 4B：页面级组件 lazy 加载，主包只含框架 + 导航 + 主题
const HomeDashboard = lazy(() => import('./components/HomeDashboard'))
const AnalysisView = lazy(() => import('./components/AnalysisView'))
const AssetLibrary = lazy(() => import('./components/AssetLibrary'))
const WritingWorkbench = lazy(() => import('./components/WritingWorkbench'))
const QualityWorkbench = lazy(() => import('./components/QualityWorkbench'))
const SystemWorkbench = lazy(() => import('./components/SystemWorkbench'))
const AdvancedWorkbench = lazy(() => import('./components/AdvancedWorkbench'))
const SettingsWorkbench = lazy(() => import('./components/SettingsWorkbench'))

const SIDEBAR_WIDTH = 220

function LoadingFallback() {
  return (
    <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
      <CircularProgress />
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

function AppShell() {
  const { workbench, setWorkbench, overview } = useApp()
  const wide = useMediaQuery('(min-width: 961px)')
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [onboarded, setOnboarded] = useState(isOnboarded)


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
      <AppBar position="static" elevation={0} sx={{ bgcolor: 'primary.main' }}>
        <Toolbar sx={{ minHeight: 48, gap: 1 }}>
          {!wide && (
            <IconButton color="inherit" edge="start" onClick={() => setDrawerOpen(true)} aria-label="打开导航">
              <MenuIcon />
            </IconButton>
          )}
          <Typography variant="h6" sx={{ fontSize: 18, flex: 1 }}>
            novel-lab 全功能工作台
          </Typography>
          <ModeToggle />
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
                {workbench === 'home' && <HomeDashboard />}
                {workbench === 'analysis' && <AnalysisView />}
                {workbench === 'assets' && <AssetLibrary />}
                {workbench === 'advanced' && <AdvancedWorkbench />}
                {workbench === 'writing' && <WritingWorkbench />}
                {workbench === 'quality' && <QualityWorkbench />}
                {workbench === 'system' && <SystemWorkbench />}
                {workbench === 'settings' && <SettingsWorkbench />}
              </Suspense>
            </ErrorBoundary>
          </Box>
        </Box>
      </Box>
    </Box>
  )
}
