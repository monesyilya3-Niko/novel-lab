import { useState } from 'react'
import { ThemeProvider, createTheme } from '@mui/material/styles'
import CssBaseline from '@mui/material/CssBaseline'
import Box from '@mui/material/Box'
import AppBar from '@mui/material/AppBar'
import Toolbar from '@mui/material/Toolbar'
import Typography from '@mui/material/Typography'
import { AppProvider } from './state/AppContext'
import { muiThemeOptions } from './theme'
import WorkbenchNav from './layout/WorkbenchNav'
import type { WorkbenchKey } from './layout/WorkbenchNav'
import HomeDashboard from './components/HomeDashboard'
import AnalysisView from './components/AnalysisView'
import AssetLibrary from './components/AssetLibrary'
import WritingWorkbench from './components/WritingWorkbench'
import QualityWorkbench from './components/QualityWorkbench'
import Placeholder from './components/Placeholder'

const theme = createTheme(muiThemeOptions)

export default function App() {
  const [workbench, setWorkbench] = useState<WorkbenchKey>('home')

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <AppProvider>
        <Box sx={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
          <AppBar position="static" elevation={0} sx={{ bgcolor: 'primary.main' }}>
            <Toolbar sx={{ minHeight: 48 }}>
              <Typography variant="h6" sx={{ fontSize: 18 }}>
                novel-lab 全功能工作台
              </Typography>
            </Toolbar>
          </AppBar>

          <Box sx={{ display: 'flex', flex: 1, minHeight: 0 }}>
            {/* 左侧：工作台导航 */}
            <Box
              sx={{
                width: 220,
                minWidth: 220,
                borderRight: '1px solid #e0e0e0',
                bgcolor: '#fafafa',
              }}
            >
              <WorkbenchNav active={workbench} onChange={setWorkbench} />
            </Box>

            {/* 主区 */}
            <Box sx={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column' }}>
              <Box sx={{ flex: 1, minHeight: 0, overflow: 'hidden' }}>
                {workbench === 'home' && <HomeDashboard />}
                {workbench === 'analysis' && <AnalysisView />}
                {workbench === 'assets' && <AssetLibrary />}
                {workbench === 'writing' && <WritingWorkbench />}
                {workbench === 'quality' && <QualityWorkbench />}
                {workbench === 'system' && <Placeholder title="系统" />}
                {workbench === 'settings' && <Placeholder title="设置" />}
              </Box>
            </Box>
          </Box>
        </Box>
      </AppProvider>
    </ThemeProvider>
  )
}
