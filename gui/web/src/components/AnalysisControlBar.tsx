// 一键分析控制条：题材下拉（必填，来自 /api/genres）+ 「一键分析」按钮 + 任务状态。
import { useEffect, useState } from 'react'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Chip from '@mui/material/Chip'
import Typography from '@mui/material/Typography'
import CircularProgress from '@mui/material/CircularProgress'
import FormControl from '@mui/material/FormControl'
import InputLabel from '@mui/material/InputLabel'
import Select from '@mui/material/Select'
import MenuItem from '@mui/material/MenuItem'
import { useApp } from '../state/AppContext'
import { getGenres } from '../api/client'
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
  const [genres, setGenres] = useState<string[]>([])
  const [genre, setGenre] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // P0-4：题材列表来自后端注册表（与后端校验同源），必填，无"未知"默认值。
  useEffect(() => {
    let cancelled = false
    getGenres()
      .then((list) => {
        if (cancelled) return
        setGenres(list)
        // 默认选中第一个，避免空值提交
        if (list.length > 0) setGenre((g) => g || list[0])
      })
      .catch(() => {
        if (!cancelled) setError('题材列表加载失败，请刷新重试')
      })
    return () => {
      cancelled = true
    }
  }, [])

  const taskStatus: TaskStatus = status?.status ?? 'idle'
  const isRunning = taskStatus === 'running'

  const doRun = async () => {
    if (!genre) {
      setError('请选择题材')
      return
    }
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
          <FormControl size="small" sx={{ minWidth: 150 }} required>
            <InputLabel id="genre-select-label">题材 *</InputLabel>
            <Select
              labelId="genre-select-label"
              value={genre}
              label="题材 *"
              onChange={(e) => setGenre(e.target.value)}
              sx={{ fontSize: 13 }}
            >
              {genres.map((g) => (
                <MenuItem key={g} value={g} sx={{ fontSize: 13 }}>
                  {g}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <Button
            variant="contained"
            size="small"
            disabled={busy || isRunning || !genre}
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
