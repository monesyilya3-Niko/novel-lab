import { Suspense, lazy } from 'react'
import { ThemeProvider, createTheme } from '@mui/material/styles'
import CssBaseline from '@mui/material/CssBaseline'
import Box from '@mui/material/Box'
import AppBar from '@mui/material/AppBar'
import Toolbar from '@mui/material/Toolbar'
import Typography from '@mui/material/Typography'
import CircularProgress from '@mui/material/CircularProgress'
import { AppProvider, useApp } from './state/AppContext'
import { muiThemeOptions } from './theme'
import WorkbenchNav from './layout/WorkbenchNav'

// 4B：页面级组件 lazy 加载，主包只含框架 + 导航 + 主题
const HomeDashboard = lazy(() => import('./components/HomeDashboard'))
const AnalysisView = lazy(() => import('./components/AnalysisView'))
const AssetLibrary = lazy(() => import('./components/AssetLibrary'))
const WritingWorkbench = lazy(() => import('./components/WritingWorkbench'))
const QualityWorkbench = lazy(() => import('./components/QualityWorkbench'))
const SystemWorkbench = lazy(() => import('./components/SystemWorkbench'))
const AdvancedWorkbench = lazy(() => import('./components/AdvancedWorkbench'))
const Placeholder = lazy(() => import('./components/Placeholder'))

const theme = createTheme(muiThemeOptions)

function LoadingFallback() {
  return (
    <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}>
      <CircularProgress />
    </Box>
  )
}

export default function App() {
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
  const { workbench, setWorkbench } = useApp()

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      <AppBar position="static" elevation={0} sx={{ bgcolor: 'primary.main' }}>
        <Toolbar sx={{ minHeight: 48 }}>
          <Typography variant="h6" sx={{ fontSize: 18 }}>
            novel-lab 全功能工作台
          </Typography>
        </Toolbar>
      </AppBar>

      <Box sx={{ display: 'flex', flex: 1, minHeight: 0 }}>
        <Box sx={{ width: 220, minWidth: 220, borderRight: '1px solid #e0e0e0', bgcolor: '#fafafa' }}>
          <WorkbenchNav active={workbench} onChange={setWorkbench} />
        </Box>
        <Box sx={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column' }}>
          <Box sx={{ flex: 1, minHeight: 0, overflow: 'hidden' }}>
            <Suspense fallback={<LoadingFallback />}>
              {workbench === 'home' && <HomeDashboard />}
              {workbench === 'analysis' && <AnalysisView />}
              {workbench === 'assets' && <AssetLibrary />}
              {workbench === 'advanced' && <AdvancedWorkbench />}
              {workbench === 'writing' && <WritingWorkbench />}
              {workbench === 'quality' && <QualityWorkbench />}
              {workbench === 'system' && <SystemWorkbench />}
              {workbench === 'settings' && <Placeholder title="设置" />}
            </Suspense>
          </Box>
        </Box>
      </Box>
    </Box>
  )
}
