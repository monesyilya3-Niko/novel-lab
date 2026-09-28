// 分析进度面板：总进度条 + 章×批状态矩阵。
import { useMemo } from 'react'
import Box from '@mui/material/Box'
import Typography from '@mui/material/Typography'
import LinearProgress from '@mui/material/LinearProgress'
import Tooltip from '@mui/material/Tooltip'
import { useApp } from '../state/AppContext'
import { palette } from '../theme'

const STATUS_LABEL: Record<string, string> = {
  idle: '空闲', pending: '等待', running: '运行中',
  success: '成功', failed: '失败', skipped: '跳过',
}
// 批次状态语义色：取自 theme.ts 统一色板；pending 用中性灰（无主题角色，保留）。
const CELL_COLOR: Record<string, string> = {
  pending: '#e0e0e0',
  running: palette.primary,
  success: palette.success,
  failed: palette.error,
  skipped: palette.warning,
}

export default function ProgressPanel() {
  const { book, batchStates, status } = useApp()

  const { done, total } = useMemo(() => {
    if (!book) return { done: 0, total: 0 }
    let d = 0
    let t = 0
    for (const ch of book.chapters) {
      t += ch.batchCount
      for (let bi = 0; bi < ch.batchCount; bi++) {
        const st = batchStates[`c${ch.index}-b${bi}`]?.status
        if (st === 'success') d++
      }
    }
    return { done: d, total: t }
  }, [book, batchStates])

  const pct = total > 0 ? Math.round((done / total) * 100) : 0

  if (!book) {
    return (
      <Box sx={{ p: 3, textAlign: 'center' }}>
        <Typography color="text.secondary">请先导入书籍</Typography>
      </Box>
    )
  }

  return (
    <Box sx={{ p: 3, height: '100%', overflow: 'auto' }}>
      <Typography variant="h6" gutterBottom>
        分析进度
      </Typography>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 1 }}>
        <Box sx={{ flex: 1 }}>
          <LinearProgress variant="determinate" value={pct} sx={{ height: 10, borderRadius: 5 }} />
        </Box>
        <Typography variant="body2" color="text.secondary" sx={{ whiteSpace: 'nowrap' }}>
          {done} / {total} 批 · {pct}%
        </Typography>
      </Box>
      <Typography variant="caption" color="text.secondary">
        当前状态：{STATUS_LABEL[status?.status ?? 'idle'] ?? status?.status ?? 'idle'} · 断点 {status?.cursor || '-'}
      </Typography>

      {/* 章×批矩阵 */}
      <Box sx={{ mt: 3 }}>
        {book.chapters.map((ch) => {
          const cols = Math.max(ch.batchCount, 1)
          return (
            <Box key={ch.index} sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
              <Typography variant="caption" noWrap sx={{ width: 140, flexShrink: 0 }}>
                第{ch.index}章
              </Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: '3px' }}>
                {Array.from({ length: cols }).map((_, bi) => {
                  const key = `c${ch.index}-b${bi}`
                  const st = batchStates[key]?.status ?? 'pending'
                  return (
                    <Tooltip key={bi} title={`第${ch.index}章 第${bi}批 · ${st}`}>
                      <Box
                        sx={{
                          width: 14,
                          height: 14,
                          borderRadius: '3px',
                          bgcolor: CELL_COLOR[st] ?? CELL_COLOR.pending,
                        }}
                      />
                    </Tooltip>
                  )
                })}
              </Box>
            </Box>
          )
        })}
      </Box>

      {/* 图例 */}
      <Box sx={{ display: 'flex', gap: 2, mt: 3 }}>
        {(['pending', 'running', 'success', 'failed', 'skipped'] as const).map((s) => (
          <Box key={s} sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
            <Box sx={{ width: 12, height: 12, borderRadius: '3px', bgcolor: CELL_COLOR[s] }} />
            <Typography variant="caption" color="text.secondary">
              {s}
            </Typography>
          </Box>
        ))}
      </Box>
    </Box>
  )
}
