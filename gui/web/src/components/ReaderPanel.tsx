// 内容阅读器：TanStack Virtual 虚拟滚动渲染长文本。
import { useMemo, useRef } from 'react'
import Box from '@mui/material/Box'
import Typography from '@mui/material/Typography'
import IconButton from '@mui/material/IconButton'
import Tooltip from '@mui/material/Tooltip'
import ArrowUpwardIcon from '@mui/icons-material/ArrowUpward'
import ArrowDownwardIcon from '@mui/icons-material/ArrowDownward'
import { useVirtualizer } from '@tanstack/react-virtual'
import { useApp } from '../state/AppContext'

export default function ReaderPanel() {
  const { currentChapter, selectedChapter, book, selectChapter } = useApp()
  const parentRef = useRef<HTMLDivElement>(null)

  // 把正文按段落切分，作为虚拟列表的行（动态行高）。
  const paragraphs = useMemo(() => {
    const text = currentChapter?.text ?? ''
    return text.split(/\n+/).filter((p) => p.trim())
  }, [currentChapter])

  const virtualizer = useVirtualizer({
    count: paragraphs.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 28,
    overscan: 10,
  })

  if (!currentChapter) {
    return (
      <Box sx={{ p: 3, textAlign: 'center' }}>
        <Typography color="text.secondary">请在左侧选择章节开始阅读</Typography>
      </Box>
    )
  }

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* 顶部：标题 + 上/下章导航 */}
      <Box
        sx={{
          px: 2,
          py: 1,
          borderBottom: '1px solid #e0e0e0',
          display: 'flex',
          alignItems: 'center',
          gap: 1,
        }}
      >
        <Tooltip title="上一章">
          <span>
            <IconButton
              size="small"
              disabled={!book || (selectedChapter ?? 1) <= 1}
              onClick={() => selectChapter((selectedChapter ?? 1) - 1)}
            >
              <ArrowUpwardIcon />
            </IconButton>
          </span>
        </Tooltip>
        <Typography variant="subtitle1" sx={{ flex: 1, textAlign: 'center', fontWeight: 600 }}>
          第{currentChapter.index}章 {currentChapter.title}
        </Typography>
        <Tooltip title="下一章">
          <span>
            <IconButton
              size="small"
              disabled={!book || (selectedChapter ?? 1) >= (book?.totalChapters ?? 1)}
              onClick={() => selectChapter((selectedChapter ?? 1) + 1)}
            >
              <ArrowDownwardIcon />
            </IconButton>
          </span>
        </Tooltip>
      </Box>

      {/* 虚拟滚动正文 */}
      <Box ref={parentRef} sx={{ flex: 1, overflow: 'auto', px: 3, py: 2 }}>
        <Box style={{ height: virtualizer.getTotalSize(), position: 'relative' }}>
          {virtualizer.getVirtualItems().map((vi) => (
            <Box
              key={vi.key}
              style={{
                position: 'absolute',
                top: 0,
                left: 0,
                width: '100%',
                transform: `translateY(${vi.start}px)`,
              }}
              ref={virtualizer.measureElement}
              data-index={vi.index}
            >
              <Typography
                variant="body1"
                sx={{ lineHeight: 1.8, textIndent: '2em', mb: 1 }}
              >
                {paragraphs[vi.index]}
              </Typography>
            </Box>
          ))}
        </Box>
      </Box>
    </Box>
  )
}
