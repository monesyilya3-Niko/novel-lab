// 「分析」工作台：导入 → 拆书（一键串联）→ 进度 → 结果，端到端走通。
// 左侧章节导航，右侧内容区（导入/进度/结果切换），底部控制栏。
import { useState } from 'react'
import Box from '@mui/material/Box'
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
          width: 280,
          minWidth: 280,
          borderRight: '1px solid #e0e0e0',
          bgcolor: '#fff',
          display: 'flex',
          flexDirection: 'column',
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
            borderBottom: '1px solid #eee',
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
          {/* 一键分析：直接在当前工作台内触发，完成后切到结果页（由 SSE done 自动刷新） */}
          <AnalysisControlBar onGoResult={() => setSubTab('result')} />
        </Box>
        <Box sx={{ flex: 1, minHeight: 0, overflow: 'hidden' }}>
          {subTab === 'import' && <ImportPanel />}
          {subTab === 'progress' && <ProgressPanel />}
          {subTab === 'result' && <AnalysisResultView />}
        </Box>
      </Box>
    </Box>
  )
}
