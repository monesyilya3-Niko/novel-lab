// 一键分析控制条：题材输入 + 「一键分析」按钮（runFullAnalysis）+ 任务状态。
import { useState } from 'react'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import TextField from '@mui/material/TextField'
import Chip from '@mui/material/Chip'
import Typography from '@mui/material/Typography'
import CircularProgress from '@mui/material/CircularProgress'
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

export interface AnalysisControlBarProps {
  /** 一键分析完成后回调（切到结果页）。 */
  onGoResult: () => void
}

export default function AnalysisControlBar({ onGoResult }: AnalysisControlBarProps) {
  const { book, status, runFullAnalysis } = useApp()
  const [genre, setGenre] = useState('未知')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const taskStatus: TaskStatus = status?.status ?? 'idle'
  const isRunning = taskStatus === 'running'

  const doRun = async () => {
    setBusy(true)
    setError(null)
    try {
      await runFullAnalysis(genre)
      onGoResult()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, flexWrap: 'wrap', py: 0.5 }}>
      {status && (
        <Chip size="small" label={STATUS_LABEL[taskStatus]} color={STATUS_COLOR[taskStatus]} />
      )}
      {status && (status.done > 0 || status.total > 0) && (
        <Typography variant="caption" color="text.secondary">
          {status.done}/{status.total} 批
        </Typography>
      )}

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
            sx={{ width: 130 }}
            inputProps={{ style: { fontSize: 13 } }}
          />
          <Button
            variant="contained"
            size="small"
            disabled={busy || isRunning}
            onClick={doRun}
            startIcon={busy ? <CircularProgress size={14} color="inherit" /> : undefined}
          >
            {isRunning ? '分析中…' : '一键分析'}
          </Button>
        </>
      )}

      {error && (
        <Typography variant="caption" color="error.main">
          {error}
        </Typography>
      )}
    </Box>
  )
}
