// 控制栏：开始 / 暂停 / 续传 / 重试失败，及当前任务状态展示。
import { useState } from 'react'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Typography from '@mui/material/Typography'
import Chip from '@mui/material/Chip'
import TextField from '@mui/material/TextField'
import Tooltip from '@mui/material/Tooltip'
import { useApp } from '../state/AppContext'
import type { TaskStatus } from '../types'

const STATUS_LABEL: Record<TaskStatus, string> = {
  idle: '空闲',
  running: '运行中',
  paused: '已暂停',
  done: '已完成',
  error: '出错',
}

const STATUS_COLOR: Record<TaskStatus, 'default' | 'primary' | 'success' | 'error' | 'warning'> = {
  idle: 'default',
  running: 'primary',
  paused: 'warning',
  done: 'success',
  error: 'error',
}

export default function ControlBar() {
  const {
    book,
    status,
    startAnalysis,
    pauseAnalysis,
    resumeAnalysis,
    retryFailed,
  } = useApp()
  const [genre, setGenre] = useState('未知')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const taskStatus: TaskStatus = status?.status ?? 'idle'
  const isRunning = taskStatus === 'running'
  const isPaused = taskStatus === 'paused'

  const withBusy = async (fn: () => Promise<void>) => {
    setBusy(true)
    setError(null)
    try {
      await fn()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Box
      sx={{
        px: 2,
        py: 1,
        borderTop: '1px solid #e0e0e0',
        display: 'flex',
        alignItems: 'center',
        gap: 1.5,
        bgcolor: '#fafafa',
        flexWrap: 'wrap',
      }}
    >
      <Chip
        size="small"
        label={STATUS_LABEL[taskStatus]}
        color={STATUS_COLOR[taskStatus]}
      />
      {status && (status.done > 0 || status.total > 0) && (
        <Typography variant="caption" color="text.secondary">
          {status.done}/{status.total} 批
        </Typography>
      )}

      <Box sx={{ flex: 1 }} />

      {!book ? (
        <Typography variant="caption" color="text.secondary">
          请先导入书籍
        </Typography>
      ) : (
        <>
          <TextField
            size="small"
            label="题材"
            value={genre}
            onChange={(e) => setGenre(e.target.value)}
            sx={{ width: 140 }}
            inputProps={{ style: { fontSize: 13 } }}
          />

          {!isRunning && !isPaused && taskStatus !== 'done' && (
            <Button
              variant="contained"
              size="small"
              disabled={busy}
              onClick={() => withBusy(() => startAnalysis(genre))}
            >
              开始分析
            </Button>
          )}

          {isRunning && (
            <Button
              variant="outlined"
              size="small"
              disabled={busy}
              onClick={() => withBusy(pauseAnalysis)}
            >
              暂停
            </Button>
          )}

          {isPaused && (
            <Button
              variant="contained"
              size="small"
              color="success"
              disabled={busy}
              onClick={() => withBusy(resumeAnalysis)}
            >
              续传
            </Button>
          )}

          {!isRunning && (taskStatus === 'done' || taskStatus === 'error' || taskStatus === 'paused') && (
            <Tooltip title="重跑所有失败批次">
              <Button
                variant="outlined"
                size="small"
                color="warning"
                disabled={busy}
                onClick={() => withBusy(retryFailed)}
              >
                重试失败
              </Button>
            </Tooltip>
          )}
        </>
      )}

      {error && (
        <Typography variant="caption" color="error.main" sx={{ ml: 1 }}>
          {error}
        </Typography>
      )}
    </Box>
  )
}
