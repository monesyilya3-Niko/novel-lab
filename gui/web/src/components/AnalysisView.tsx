// 「分析」工作台：导入 → 拆书（一键串联）→ 进度 → 结果，端到端走通。
// 左侧章节导航，右侧内容区（导入/进度/结果切换），底部控制栏。
import { useState } from 'react'
import Box from '@mui/material/Box'
import ContextHelpButton from './ContextHelpButton'
import Tabs from '@mui/material/Tabs'
import Tab from '@mui/material/Tab'
import ImportPanel from './ImportPanel'
import ChapterList from './ChapterList'
import ProgressPanel from './ProgressPanel'
import AnalysisResultView from './AnalysisResultView'
import AnalysisControlBar from './AnalysisControlBar'

type SubTab = 'import' | 'progress' | 'result'

export default function AnalysisView() {
  const [subTab, setSubTab] = useState<SubTab>('import')

  return (
    <Box sx={{ display: 'flex', height: '100%', minHeight: 0 }}>
      {/* 左侧：章节导航 */}
      <Box
        sx={{
          width: { xs: '100%', md: 280 },
          minWidth: { xs: 'auto', md: 280 },
          borderRight: { xs: 0, md: 1 },
          borderBottom: { xs: 1, md: 0 },
          borderColor: 'divider',
          bgcolor: 'background.paper',
          display: 'flex',
          flexDirection: 'column',
          maxHeight: { xs: 200, md: 'none' },
          overflow: { xs: 'auto', md: 'visible' },
        }}
      >
        <ImportPanel compact />
        <Box sx={{ flex: 1, minHeight: 0, overflow: 'auto' }}>
          <ChapterList />
        </Box>
      </Box>

      {/* 主区 */}
      <Box sx={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column' }}>
        <Box
          sx={{
            px: 2,
            pt: 1,
            borderBottom: '1px solid',
            borderColor: 'divider',
            display: 'flex',
            alignItems: 'center',
          }}
        >
          <Tabs value={subTab} onChange={(_e, v) => setSubTab(v as SubTab)} sx={{ minHeight: 40 }}>
            <Tab value="import" label="导入" sx={{ minHeight: 40 }} />
            <Tab value="progress" label="进度" sx={{ minHeight: 40 }} />
            <Tab value="result" label="结果" sx={{ minHeight: 40 }} />
          </Tabs>
          <Box sx={{ flex: 1 }} />
          <ContextHelpButton guideKey="analysis" title="查看拆书指南" />
          {/* 一键分析：直接在当前工作台内触发，完成后切到结果页（由 SSE done 自动刷新） */}
          <AnalysisControlBar onGoResult={() => setSubTab('result')} />
        </Box>
        <Box sx={{ flex: 1, minHeight: 0, overflow: 'auto' }}>
          {subTab === 'import' && <ImportPanel />}
          {subTab === 'progress' && <ProgressPanel />}
          {subTab === 'result' && <AnalysisResultView />}
        </Box>
      </Box>
    </Box>
  )
}
